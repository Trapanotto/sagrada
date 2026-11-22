import * as THREE from 'three';

export interface PerfSnapshot {
  fps: number;
  frameMs: number;
  calls: number;
  triangles: number;
  geometries: number;
  textures: number;
  activeLights: number;
  totalLights: number;
  reflectorActive: boolean;
  reflectorRes?: number;
  shadowMapSize?: number;
  shadowCached: boolean;
  instancedGroups: number;
  savedDrawCalls: number;
}

/**
 * Lightweight zero-allocation FPS pill + collapsible diagnostics overlay ([O]).
 */
export class PerfMonitor {
  private frames = 0;
  private accumSec = 0;
  private fps = 60;
  private frameMs = 16.6;
  public expanded = false;

  private pillEl: HTMLButtonElement;
  private cardEl: HTMLElement;
  private bodyEl: HTMLElement;

  constructor(
    pillEl: HTMLButtonElement,
    cardEl: HTMLElement,
    bodyEl: HTMLElement
  ) {
    this.pillEl = pillEl;
    this.cardEl = cardEl;
    this.bodyEl = bodyEl;

    this.pillEl.addEventListener('click', () => this.toggle());
  }

  public getFps(): number {
    return this.fps;
  }

  public toggle(): boolean {
    this.expanded = !this.expanded;
    this.cardEl.classList.toggle('hidden', !this.expanded);
    this.pillEl.classList.toggle('active', this.expanded);
    return this.expanded;
  }

  public sampleFrame(dt: number, renderer: THREE.WebGLRenderer, extra: Omit<PerfSnapshot, 'fps' | 'frameMs' | 'calls' | 'triangles' | 'geometries' | 'textures'>): void {
    this.frames++;
    this.accumSec += dt;
    if (this.accumSec < 0.35) return;

    this.fps = Math.round(this.frames / this.accumSec);
    this.frameMs = (this.accumSec / this.frames) * 1000;
    this.frames = 0;
    this.accumSec = 0;

    // Color-coded compact FPS pill
    this.pillEl.textContent = `${this.fps} FPS`;
    this.pillEl.dataset.state = this.fps >= 52 ? 'good' : this.fps >= 32 ? 'mid' : 'low';

    if (!this.expanded) return;

    const info = renderer.info;
    const trisK = (info.render.triangles / 1000).toFixed(1);
    const reflRes = extra.reflectorRes ?? 256;
    const shadowLabel = extra.shadowMapSize && extra.shadowMapSize <= 1024 ? '1K' : '2K';
    this.bodyEl.innerHTML = `
      <div class="perf-row"><span>Frame-Zeit</span><strong>${this.frameMs.toFixed(1)} ms (${this.fps} FPS)</strong></div>
      <div class="perf-row"><span>Draw Calls</span><strong>${info.render.calls}</strong></div>
      <div class="perf-row"><span>Dreiecke</span><strong>${trisK}k</strong></div>
      <div class="perf-row"><span>Aktive Lichter</span><strong>${extra.activeLights} / ${extra.totalLights}</strong></div>
      <div class="perf-row"><span>Spiegelteich</span><strong>${extra.reflectorActive ? `Aktiv (${reflRes}px)` : 'Gecullt (0 ms)'}</strong></div>
      <div class="perf-row"><span>${shadowLabel}-Sonnenschatten</span><strong>${extra.shadowCached ? 'Gecacht (0 ms)' : 'Neu berechnet'}</strong></div>
      <div class="perf-row"><span>Auto-Instancing</span><strong>${extra.instancedGroups} Batches (-${extra.savedDrawCalls} Calls)</strong></div>
      <div class="perf-row"><span>VRAM Ressourcen</span><strong>${info.memory.geometries} Geo · ${info.memory.textures} Tex</strong></div>
    `;
  }
}
