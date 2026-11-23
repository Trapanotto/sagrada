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
    uSaturation: { value: 1.05 },
    uContrast: { value: 1.04 },
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
      vec3 shadowTint = vec3(0.95, 0.98, 1.03);
      vec3 highlightTint = vec3(1.015, 0.995, 0.96);
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

    // HalfFloat HDR target with its own MSAA (independent of the canvas context's antialias flag)
    const rt = new THREE.WebGLRenderTarget(width, height, {
      type: THREE.HalfFloatType,
      samples: msaaSamples,
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
    // Insert directly after the RenderPass (index 1), before bloom
    this.composer.insertPass(gtao, 1);
    this.gtaoPass = gtao;
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
