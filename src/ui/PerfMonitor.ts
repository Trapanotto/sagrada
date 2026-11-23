import * as THREE from 'three';
import { t, fmtNum } from '../i18n';

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
  tierLabel?: string;
  pixelRatio?: number;
  postLabel?: string;
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
    const trisK = fmtNum(info.render.triangles / 1000, 1);
    const reflRes = extra.reflectorRes ?? 256;
    const shadowLabel = `${Math.round((extra.shadowMapSize ?? 2048) / 1024)}K`;
    const canvas = renderer.domElement;
    const qualityRows =
      extra.tierLabel !== undefined
        ? `<div class="perf-row"><span>${t('perf.tier')}</span><strong>${extra.tierLabel} · ${extra.postLabel ?? ''}</strong></div>
      <div class="perf-row"><span>${t('perf.resolution')}</span><strong>${canvas.width}×${canvas.height} (×${fmtNum(extra.pixelRatio ?? 1, 2)})</strong></div>`
        : '';
    this.bodyEl.innerHTML = `
      <div class="perf-row"><span>${t('perf.frameTime')}</span><strong>${fmtNum(this.frameMs, 1)} ms (${this.fps} FPS)</strong></div>
      ${qualityRows}
      <div class="perf-row"><span>${t('perf.drawCalls')}</span><strong>${info.render.calls}</strong></div>
      <div class="perf-row"><span>${t('perf.triangles')}</span><strong>${trisK}k</strong></div>
      <div class="perf-row"><span>${t('perf.lights')}</span><strong>${extra.activeLights} / ${extra.totalLights}</strong></div>
      <div class="perf-row"><span>${t('perf.pond')}</span><strong>${extra.reflectorActive ? t('perf.pondActive', { res: reflRes }) : t('perf.pondCulled')}</strong></div>
      <div class="perf-row"><span>${t('perf.shadows', { size: shadowLabel })}</span><strong>${extra.shadowCached ? t('perf.shadowsCached') : t('perf.shadowsFresh')}</strong></div>
      <div class="perf-row"><span>${t('perf.instancing')}</span><strong>${t('perf.instancingValue', { groups: extra.instancedGroups, saved: extra.savedDrawCalls })}</strong></div>
      <div class="perf-row"><span>${t('perf.vram')}</span><strong>${info.memory.geometries} Geo · ${info.memory.textures} Tex</strong></div>
    `;
  }
}
