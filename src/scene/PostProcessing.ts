import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { GTAOPass } from 'three/examples/jsm/postprocessing/GTAOPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { BokehPass } from 'three/examples/jsm/postprocessing/BokehPass.js';
import { ShaderPass } from 'three/examples/jsm/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';

export type GraphicsTier = 'aaa' | 'ultra' | 'fast';

const CinematicGradeShader = {
  uniforms: {
    tDiffuse: { value: null },
    uVignette: { value: 0.24 },
    uSaturation: { value: 1.07 },
    uContrast: { value: 1.04 },
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
    varying vec2 vUv;

    void main() {
      vec4 texel = texture2D(tDiffuse, vUv);
      vec3 col = texel.rgb;

      float luma = dot(col, vec3(0.2126, 0.7152, 0.0722));
      col = mix(vec3(luma), col, uSaturation);
      col = (col - 0.5) * uContrast + 0.5;

      vec2 centered = vUv * 2.0 - 1.0;
      float vig = 1.0 - dot(centered, centered) * uVignette * 0.42;
      col *= clamp(vig, 0.65, 1.0);

      gl_FragColor = vec4(clamp(col, 0.0, 1.0), texel.a);
    }
  `,
};

/**
 * High-FPS AAA HDR Post-Processing Pipeline:
 * - 'aaa' (Default, 60 FPS): Hardware WebGL2 4x MSAA + Baked BVH AO (0ms) + Selective HDR Bloom + AgX + Grade
 * - 'ultra': Adds half-res GTAOPass on top for high-end discrete GPUs
 * - 'fast': Direct single-pass WebGL2 render (zero composer overhead for laptops / iGPUs)
 */
export class PostProcessingPipeline {
  private composer: EffectComposer;
  private gtaoPass: GTAOPass;
  private bloomPass: UnrealBloomPass;
  private bokehPass: BokehPass;
  private gradePass: ShaderPass;

  public tier: GraphicsTier = 'aaa';
  public dofEnabled = false;

  constructor(
    private renderer: THREE.WebGLRenderer,
    private scene: THREE.Scene,
    private camera: THREE.PerspectiveCamera
  ) {
    const w = window.innerWidth;
    const h = window.innerHeight;

    // Hardware WebGL2 4x MSAA HalfFloat HDR target — way faster & sharper than multi-pass SMAAPass!
    const rt = new THREE.WebGLRenderTarget(w, h, {
      type: THREE.HalfFloatType,
      samples: 4,
    });

    this.composer = new EffectComposer(this.renderer, rt);
    this.composer.setPixelRatio(Math.min(window.devicePixelRatio, 1.25));
    this.composer.setSize(w, h);

    const renderPass = new RenderPass(this.scene, this.camera);
    this.composer.addPass(renderPass);

    // Optional Half-Res GTAOPass (only enabled in 'ultra' tier — 'aaa' uses our zero-cost Baked BVH AO!)
    this.gtaoPass = new GTAOPass(this.scene, this.camera, Math.floor(w * 0.5), Math.floor(h * 0.5));
    this.gtaoPass.output = GTAOPass.OUTPUT.Default;
    this.gtaoPass.blendIntensity = 0.58;
    this.gtaoPass.updateGtaoMaterial({
      radius: 0.9,
      distanceExponent: 1.5,
      thickness: 1.1,
      scale: 1.0,
      samples: 8,
      distanceFallOff: 1.0,
    });
    this.gtaoPass.updatePdMaterial({
      lumaPhi: 10,
      depthPhi: 2,
      normalPhi: 3,
      radius: 3,
      radiusExponent: 1,
      rings: 2,
      samples: 8,
    });
    this.gtaoPass.enabled = false;
    this.composer.addPass(this.gtaoPass);

    // Selective HDR Bloom (half-res internal mip chain — very fast!)
    this.bloomPass = new UnrealBloomPass(new THREE.Vector2(Math.floor(w * 0.5), Math.floor(h * 0.5)), 0.30, 0.50, 1.05);
    this.composer.addPass(this.bloomPass);

    // Optional Photo-Mode Depth of Field (BokehPass — off during normal walking)
    this.bokehPass = new BokehPass(this.scene, this.camera, {
      focus: 24.0,
      aperture: 0.00018,
      maxblur: 0.012,
    });
    this.bokehPass.enabled = false;
    this.composer.addPass(this.bokehPass);

    // AgX Filmic Tone Mapping + Linear-to-sRGB conversion
    const outputPass = new OutputPass();
    this.composer.addPass(outputPass);

    // Subtle Cinematic Vignette & Architectural Color Grading
    this.gradePass = new ShaderPass(CinematicGradeShader);
    this.composer.addPass(this.gradePass);

    this.setTier('aaa');
  }

  public setTier(tier: GraphicsTier): void {
    this.tier = tier;
    if (tier === 'ultra') {
      const dpr = Math.min(window.devicePixelRatio, 1.5);
      this.renderer.setPixelRatio(dpr);
      this.composer.setPixelRatio(dpr);
      this.gtaoPass.enabled = true;
      this.bloomPass.enabled = true;
      this.gradePass.enabled = true;
      this.bokehPass.enabled = this.dofEnabled;
    } else if (tier === 'aaa') {
      const dpr = Math.min(window.devicePixelRatio, 1.25);
      this.renderer.setPixelRatio(dpr);
      this.composer.setPixelRatio(dpr);
      this.gtaoPass.enabled = false; // Zero-cost Baked BVH AO handles architectural depth at 60 FPS!
      this.bloomPass.enabled = true;
      this.gradePass.enabled = true;
      this.bokehPass.enabled = this.dofEnabled;
    } else {
      const dpr = Math.min(window.devicePixelRatio, 1.0);
      this.renderer.setPixelRatio(dpr);
      this.gtaoPass.enabled = false;
      this.bloomPass.enabled = false;
      this.gradePass.enabled = false;
      this.bokehPass.enabled = false;
    }
    this.setSize(window.innerWidth, window.innerHeight);
  }

  public cycleTier(): GraphicsTier {
    const order: GraphicsTier[] = ['aaa', 'ultra', 'fast'];
    const next = order[(order.indexOf(this.tier) + 1) % order.length];
    this.setTier(next);
    return next;
  }

  public setDof(enabled: boolean, focus?: number, aperture?: number): void {
    this.dofEnabled = enabled;
    this.bokehPass.enabled = enabled && this.tier !== 'fast';
    const u = this.bokehPass.uniforms as Record<string, THREE.IUniform>;
    if (focus !== undefined && u.focus) u.focus.value = focus;
    if (aperture !== undefined && u.aperture) u.aperture.value = aperture;
  }

  public setNightBloomFactor(nightFactor: number): void {
    this.bloomPass.strength = THREE.MathUtils.lerp(0.26, 0.50, nightFactor);
    this.bloomPass.threshold = THREE.MathUtils.lerp(1.06, 0.88, nightFactor);
  }

  public setSize(width: number, height: number): void {
    this.composer.setSize(width, height);
    this.gtaoPass.setSize(Math.max(1, Math.floor(width * 0.5)), Math.max(1, Math.floor(height * 0.5)));
    this.bloomPass.setSize(Math.max(1, Math.floor(width * 0.5)), Math.max(1, Math.floor(height * 0.5)));
  }

  public render(): void {
    if (this.tier === 'fast') {
      this.renderer.render(this.scene, this.camera);
    } else {
      this.composer.render();
    }
  }
}
