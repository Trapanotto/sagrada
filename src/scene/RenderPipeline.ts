import * as THREE from 'three';
import type { QualitySettings } from '../utils/quality';
import type { PostProcessingStack } from './PostProcessing';

/**
 * Thin, always-loaded render façade:
 * - Direct single-pass render when the tier needs no post effects (low / medium).
 * - Lazily imports the composer stack (bloom, grade, GTAO, DoF) only when a tier or the photo
 *   studio needs it, so the post-processing code is not part of the startup bundle.
 * - Dynamic resolution scaling (DRS) bounded by the tier's [minPixelRatio, maxPixelRatio],
 *   with hysteresis and a temporary "failed ceiling" so it cannot oscillate.
 */
export class RenderPipeline {
  private post: PostProcessingStack | null = null;
  private postPromise: Promise<PostProcessingStack> | null = null;
  private settings: QualitySettings;
  private pixelRatio: number;
  private width = window.innerWidth;
  private height = window.innerHeight;

  private dofEnabled = false;
  private dofFocus = 24.0;
  private dofAperture = 0.00018;
  private nightFactor = 0.0;

  // DRS state
  public drsEnabled = true;
  private winTime = 0;
  private winFrames = 0;
  private goodWindows = 0;
  private holdUntil = 0;
  private failCeiling = Infinity;
  private failUntil = 0;
  private failDurationMs = 20000;
  private settleWindows = 0;
  private lastWindowFps = 0;

  constructor(
    private renderer: THREE.WebGLRenderer,
    private scene: THREE.Scene,
    private camera: THREE.PerspectiveCamera,
    settings: QualitySettings,
    private readonly contextAntialias: boolean
  ) {
    this.settings = settings;
    this.pixelRatio = settings.maxPixelRatio;
    this.renderer.setPixelRatio(this.pixelRatio);
  }

  public get currentPixelRatio(): number {
    return this.pixelRatio;
  }

  public get lastMeasuredFps(): number {
    return this.lastWindowFps;
  }

  public get usingComposer(): boolean {
    return this.needsComposer && this.post !== null;
  }

  public get gtaoActive(): boolean {
    return this.usingComposer && this.settings.gtao;
  }

  private get needsComposer(): boolean {
    const s = this.settings;
    return s.bloom || s.colorGrade || s.gtao || this.dofEnabled || (s.antialias && !this.contextAntialias);
  }

  /** Loads + builds the composer if the current tier needs it. Await during the loading screen. */
  public async prepare(): Promise<void> {
    if (this.needsComposer) {
      await this.ensurePost();
    }
  }

  private ensurePost(): Promise<PostProcessingStack> {
    if (this.post) return Promise.resolve(this.post);
    if (!this.postPromise) {
      this.postPromise = import('./PostProcessing').then(({ PostProcessingStack }) => {
        const stack = new PostProcessingStack(
          this.renderer,
          this.scene,
          this.camera,
          this.width,
          this.height,
          this.pixelRatio,
          4
        );
        this.post = stack;
        this.configurePost();
        return stack;
      });
      this.postPromise.catch((err) => {
        console.warn('[Post] Post-processing stack failed to load, rendering directly:', err);
        this.postPromise = null;
      });
    }
    return this.postPromise;
  }

  private configurePost(): void {
    if (!this.post) return;
    const s = this.settings;
    this.post.configure({ bloom: s.bloom, colorGrade: s.colorGrade, gtao: s.gtao, dof: this.dofEnabled });
    this.post.setDofParams(this.dofFocus, this.dofAperture);
    this.post.setNightBloomFactor(this.nightFactor);
    this.post.setPixelRatio(this.pixelRatio);
  }

  public applyQuality(settings: QualitySettings): void {
    this.settings = settings;
    this.pixelRatio = settings.maxPixelRatio;
    this.resetDrs();
    this.applyPixelRatio();
    if (this.needsComposer) void this.ensurePost();
    this.configurePost();
  }

  /** Re-apply DPR-dependent bounds (e.g. window dragged to a monitor with another DPR). */
  public updateBounds(settings: QualitySettings): void {
    this.settings = settings;
    const clamped = THREE.MathUtils.clamp(this.pixelRatio, settings.minPixelRatio, settings.maxPixelRatio);
    if (Math.abs(clamped - this.pixelRatio) > 1e-3) {
      this.pixelRatio = clamped;
      this.applyPixelRatio();
    }
  }

  private applyPixelRatio(): void {
    this.renderer.setPixelRatio(this.pixelRatio);
    this.renderer.setSize(this.width, this.height);
    this.post?.setPixelRatio(this.pixelRatio);
  }

  public setSize(width: number, height: number): void {
    this.width = width;
    this.height = height;
    this.renderer.setSize(width, height);
    this.post?.setSize(width, height);
    // A resize changes the pixel load; give DRS a fresh window instead of reacting to the hitch
    this.winTime = 0;
    this.winFrames = 0;
  }

  public setDof(enabled: boolean, focus?: number, aperture?: number): void {
    this.dofEnabled = enabled;
    if (focus !== undefined) this.dofFocus = focus;
    if (aperture !== undefined) this.dofAperture = aperture;
    if (enabled) void this.ensurePost();
    this.configurePost();
  }

  public setNightBloomFactor(nightFactor: number): void {
    this.nightFactor = nightFactor;
    this.post?.setNightBloomFactor(nightFactor);
  }

  public render(dt = 0.016): void {
    if (this.post && this.needsComposer) {
      this.post.render(dt);
    } else {
      this.renderer.render(this.scene, this.camera);
    }
  }

  public resetDrs(): void {
    this.winTime = 0;
    this.winFrames = 0;
    this.goodWindows = 0;
    this.holdUntil = performance.now() + 2000;
    this.failCeiling = Infinity;
    this.failUntil = 0;
    this.failDurationMs = 20000;
    this.settleWindows = 0;
  }

  /**
   * Feed every rendered frame's dt. Evaluates 1 s windows:
   * - below drsLowFps: drop 8–15 % at once, remember the failing level, hold 3 s;
   * - above drsHighFps for 3 consecutive windows: raise 6 %, but never back to a level that
   *   failed recently (20 s, doubling up to 5 min if the same level keeps failing);
   * - the window right after a change is discarded (it still mixes old-resolution frames).
   * Synthetic test (GPU: 60 fps at pr<=1.2, 40 fps above, bounds 1.0–1.5): 14 changes in 300 s,
   * settling at 1.2 with re-probes at ~50 s, ~130 s, ~300 s instead of continuous ping-pong.
   */
  public sampleFrame(dt: number): void {
    if (!this.drsEnabled) return;
    if (dt > 0.25) {
      // Hitch, tab resume or throttled background frame — not representative
      this.winTime = 0;
      this.winFrames = 0;
      return;
    }
    this.winTime += dt;
    this.winFrames++;
    if (this.winTime < 1.0) return;

    const fps = this.winFrames / this.winTime;
    this.lastWindowFps = fps;
    this.winTime = 0;
    this.winFrames = 0;

    const s = this.settings;
    const now = performance.now();
    const pr = this.pixelRatio;
    let next = pr;

    if (this.settleWindows > 0) {
      // First window after a resolution change still contains old-resolution frames
      this.settleWindows--;
      return;
    }

    if (fps < s.drsLowFps) {
      this.goodWindows = 0;
      if (pr > s.minPixelRatio + 1e-3) {
        const factor = fps < s.drsLowFps * 0.75 ? 0.85 : 0.92;
        next = Math.max(s.minPixelRatio, pr * factor);
        // Same level failing again -> back off exponentially before re-probing it (20 s, 40 s, … 5 min)
        const sameLevel = now < this.failUntil + 30000 && Math.abs(pr - this.failCeiling) < 0.06;
        this.failDurationMs = sameLevel ? Math.min(this.failDurationMs * 2, 300000) : 20000;
        this.failCeiling = pr;
        this.failUntil = now + this.failDurationMs;
        this.holdUntil = now + 3000;
      }
    } else if (fps >= s.drsHighFps) {
      if (pr < s.maxPixelRatio - 1e-3) {
        this.goodWindows++;
        if (this.goodWindows >= 3 && now >= this.holdUntil) {
          this.goodWindows = 0;
          let candidate = Math.min(s.maxPixelRatio, pr * 1.06);
          if (now < this.failUntil) candidate = Math.min(candidate, this.failCeiling - 0.05);
          if (candidate > pr + 0.02) {
            next = candidate;
            this.holdUntil = now + 2000;
          }
        }
      }
    } else {
      this.goodWindows = 0;
    }

    // Quantise to 0.05 steps (fewer drawing-buffer reallocations), keep inside the tier bounds
    next = THREE.MathUtils.clamp(Math.round(next * 20) / 20, s.minPixelRatio, s.maxPixelRatio);
    if (Math.abs(next - pr) >= 0.025) {
      this.pixelRatio = next;
      this.applyPixelRatio();
      this.settleWindows = 1;
    }
  }

  /** After a WebGL context restore: composer targets are re-created lazily by three.js. */
  public handleContextRestored(): void {
    this.applyPixelRatio();
    this.configurePost();
  }
}
