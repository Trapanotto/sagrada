import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { GTAOPass } from 'three/examples/jsm/postprocessing/GTAOPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { BokehPass } from 'three/examples/jsm/postprocessing/BokehPass.js';
import { ShaderPass } from 'three/examples/jsm/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';

/**
 * Composer-based HDR post stack. This module is loaded on demand (dynamic import from
 * RenderPipeline) so tiers that render directly never download / parse it.
 */

const CinematicGradeShader = {
  uniforms: {
    tDiffuse: { value: null },
    uVignette: { value: 0.24 },
    uSaturation: { value: 1.06 },
    uContrast: { value: 1.08 },
    uTime: { value: 0.0 },
  },
  vertexShader: /* glsl */ `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: /* glsl */ `
    uniform sampler2D tDiffuse;
    uniform float uVignette;
    uniform float uSaturation;
    uniform float uContrast;
    uniform float uTime;
    varying vec2 vUv;

    void main() {
      vec4 texel = texture2D(tDiffuse, vUv);
      vec3 col = texel.rgb;

      float luma = dot(col, vec3(0.2126, 0.7152, 0.0722));
      col = mix(vec3(luma), col, uSaturation);
      col = (col - 0.5) * uContrast + 0.5;

      // Subtle photorealistic Split-Toning: cool shadowed stone recesses + natural warm highlights (no over-brightening)
      vec3 shadowTint = vec3(0.94, 0.97, 1.04);
      vec3 highlightTint = vec3(1.04, 1.0, 0.92);
      col *= mix(shadowTint, highlightTint, smoothstep(0.18, 0.80, luma));

      // Ultra-subtle organic 35mm film grain (breaks sky banding without noise)
      float grain = fract(sin(dot(vUv * 512.0 + fract(uTime * 0.7), vec2(12.9898, 78.233))) * 43758.5453) - 0.5;
      col += grain * 0.007;

      vec2 centered = vUv * 2.0 - 1.0;
      float vig = 1.0 - dot(centered, centered) * uVignette * 0.42;
      col *= clamp(vig, 0.66, 1.0);

      gl_FragColor = vec4(clamp(col, 0.0, 1.0), texel.a);
    }
  `,
};

/** Drawing-buffer pixels up to which GTAO reads the main pass depth instead of its own G-buffer pass. */
const GTAO_REUSE_DEPTH_MAX_PIXELS = 2.6e6;

export interface PostStackConfig {
  bloom: boolean;
  colorGrade: boolean;
  gtao: boolean;
  dof: boolean;
}

export class PostProcessingStack {
  private composer: EffectComposer;
  private gtaoPass: GTAOPass | null = null;
  private bloomPass: UnrealBloomPass;
  private bokehPass: BokehPass;
  private gradePass: ShaderPass;
  private width: number;
  private height: number;
  private wantGtao = false;

  constructor(
    renderer: THREE.WebGLRenderer,
    private scene: THREE.Scene,
    private camera: THREE.PerspectiveCamera,
    width: number,
    height: number,
    pixelRatio: number,
    msaaSamples: number
  ) {
    this.width = width;
    this.height = height;
    this.pixelRatio = pixelRatio;

    // HalfFloat HDR target with its own MSAA (independent of the canvas context's antialias flag).
    // Its depth is kept as a texture so GTAO can read the main view's depth instead of rendering the
    // whole scene a second time into its own normal/depth G-buffer (composer clones it per buffer).
    const rt = new THREE.WebGLRenderTarget(width, height, {
      type: THREE.HalfFloatType,
      samples: msaaSamples,
      depthTexture: new THREE.DepthTexture(width, height),
    });
    this.composer = new EffectComposer(renderer, rt);
    this.composer.setPixelRatio(pixelRatio);
    this.composer.setSize(width, height);

    this.composer.addPass(new RenderPass(scene, camera));

    const halfW = Math.max(1, Math.floor(width * 0.5));
    const halfH = Math.max(1, Math.floor(height * 0.5));
    this.bloomPass = new UnrealBloomPass(new THREE.Vector2(halfW, halfH), 0.26, 0.5, 1.15);
    this.bokehPass = new BokehPass(scene, camera, { focus: 24, aperture: 0.00018, maxblur: 0.012 });
    this.bokehPass.enabled = false;
    this.gradePass = new ShaderPass(CinematicGradeShader);

    this.composer.addPass(this.bloomPass);
    this.composer.addPass(this.bokehPass);
    this.composer.addPass(new OutputPass());
    this.composer.addPass(this.gradePass);
  }

  /** GTAO allocates several full/half-res targets; only build it when a tier actually asks for it. */
  private ensureGtao(): void {
    if (this.gtaoPass) return;
    const halfW = Math.max(1, Math.floor(this.width * 0.5));
    const halfH = Math.max(1, Math.floor(this.height * 0.5));
    const gtao = new GTAOPass(this.scene, this.camera, halfW, halfH);
    gtao.output = GTAOPass.OUTPUT.Default;
    gtao.blendIntensity = 0.58;
    gtao.updateGtaoMaterial({
      radius: 0.9,
      distanceExponent: 1.5,
      thickness: 1.1,
      scale: 1.0,
      samples: 8,
      distanceFallOff: 1.0,
    });
    gtao.updatePdMaterial({
      lumaPhi: 10,
      depthPhi: 2,
      normalPhi: 3,
      radius: 3,
      radiusExponent: 1,
      rings: 2,
      samples: 8,
    });
    const gtaoRender = gtao.render.bind(gtao);
    gtao.render = (renderer, writeBuffer, readBuffer, deltaTime, maskActive) => {
      if (this.gtaoReuseDepth) {
        // The composer swaps its two targets: point GTAO at the depth of the one the RenderPass drew into
        const depth = readBuffer.depthTexture;
        if (depth && gtao.gtaoMaterial.uniforms.tDepth.value !== depth) {
          gtao.gtaoMaterial.uniforms.tDepth.value = depth;
          gtao.pdMaterial.uniforms.tDepth.value = depth;
        }
      }
      gtaoRender(renderer, writeBuffer, readBuffer, deltaTime, maskActive);
    };
    // Insert directly after the RenderPass (index 1), before bloom
    this.composer.insertPass(gtao, 1);
    this.gtaoPass = gtao;
    this.gtaoReuseDepth = null;
    this.updateGtaoMode();
  }

  /**
   * GTAO G-buffer source, chosen by drawing-buffer size:
   * - up to ~2.6 MP (1080p-class): read the depth the RenderPass already wrote (normals reconstructed
   *   from depth in the GTAO shader). Saves GTAO's own full second scene render (~85 draw calls / ~350k
   *   triangles and two scene traversals per frame on ultra: ~0.5 ms CPU, GPU-neutral at 1080p) and drops
   *   the dark halos the override-material G-buffer drew around the cross / star sprites and the glass shaft.
   * - above: three's own half-resolution normal/depth pass. At 4K the 4x-MSAA depth resolve plus
   *   full-resolution depth sampling cost ~0.5–1 ms more GPU than re-rendering the scene at half size.
   * Switching recompiles the two GTAO materials once per mode (cached afterwards); it only happens on a
   * resize or a pixel-ratio change.
   */
  private gtaoReuseDepth: boolean | null = null;
  private pixelRatio = 1;

  private updateGtaoMode(): void {
    const g = this.gtaoPass;
    if (!g) return;
    const pixels = this.width * this.height * this.pixelRatio * this.pixelRatio;
    const reuse = pixels <= GTAO_REUSE_DEPTH_MAX_PIXELS && this.composer.readBuffer.depthTexture !== null;
    if (reuse === this.gtaoReuseDepth) return;
    this.gtaoReuseDepth = reuse;
    // GTAOPass keeps its G-buffer state in fields three's typings mark internal
    const internal = g as unknown as { _renderGBuffer: boolean; normalRenderTarget: THREE.WebGLRenderTarget };
    const own = internal.normalRenderTarget;
    internal._renderGBuffer = !reuse;
    const depth = reuse ? this.composer.readBuffer.depthTexture : own.depthTexture;
    const normal = reuse ? null : own.texture;
    for (const m of [g.gtaoMaterial, g.pdMaterial]) {
      m.defines.NORMAL_VECTOR_TYPE = reuse ? 0 : 1;
      m.uniforms.tDepth.value = depth;
      m.uniforms.tNormal.value = normal;
      m.needsUpdate = true;
    }
    // The composer targets only need their MSAA depth resolved when GTAO reads it
    this.composer.renderTarget1.resolveDepthBuffer = reuse;
    this.composer.renderTarget2.resolveDepthBuffer = reuse;
  }

  public configure(cfg: PostStackConfig): void {
    this.wantGtao = cfg.gtao;
    if (cfg.gtao) this.ensureGtao();
    if (this.gtaoPass) this.gtaoPass.enabled = cfg.gtao;
    this.bloomPass.enabled = cfg.bloom;
    this.gradePass.enabled = cfg.colorGrade;
    this.bokehPass.enabled = cfg.dof;
    this.setSize(this.width, this.height);
  }

  public get gtaoEnabled(): boolean {
    return this.wantGtao;
  }

  public setDofParams(focus: number, aperture: number): void {
    const u = this.bokehPass.uniforms as Record<string, THREE.IUniform>;
    if (u.focus) u.focus.value = focus;
    if (u.aperture) u.aperture.value = aperture;
  }

  public setNightBloomFactor(nightFactor: number): void {
    this.bloomPass.strength = THREE.MathUtils.lerp(0.26, 0.34, nightFactor);
    this.bloomPass.threshold = THREE.MathUtils.lerp(1.15, 1.1, nightFactor);
  }

  public setPixelRatio(pr: number): void {
    this.pixelRatio = pr;
    this.composer.setPixelRatio(pr);
    this.setSize(this.width, this.height);
  }

  public setSize(width: number, height: number): void {
    this.width = width;
    this.height = height;
    this.composer.setSize(width, height);
    const halfW = Math.max(1, Math.floor(width * 0.5));
    const halfH = Math.max(1, Math.floor(height * 0.5));
    this.gtaoPass?.setSize(halfW, halfH);
    this.bloomPass.setSize(halfW, halfH);
    this.updateGtaoMode();
  }

  public render(dt: number): void {
    const u = this.gradePass.uniforms.uTime;
    if (u) u.value = (u.value + dt) % 1000.0;
    this.composer.render(dt);
  }

  public dispose(): void {
    this.gtaoPass?.dispose();
    this.bloomPass.dispose();
    this.bokehPass.dispose();
    this.gradePass.dispose();
    this.composer.dispose();
  }
}
