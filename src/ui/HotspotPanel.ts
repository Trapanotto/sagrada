import * as THREE from 'three';
import { ARCHITECTURAL_HOTSPOTS, ArchitecturalHotspot } from '../data/hotspots';

const INTERIOR_ONLY_IDS = new Set([
  'double-twisted-columns',
  'hyperboloid-vaults',
  'stained-glass-east',
  'stained-glass-west',
  'high-altar-baldachin',
  'gaudi-chain-model',
  'baptistery-font',
]);

const EXTERIOR_ONLY_IDS = new Set([
  'jesus-tower',
  'mary-star',
  'evangelist-towers',
  'nativity-facade',
  'passion-facade',
  'glory-facade',
  'cloister-sacristy',
  'eixample-pond',
]);

interface MarkerState {
  shown: boolean;
  x: number;
  y: number;
  op: number;
}

export class HotspotPanel {
  public visible = true;
  private markerEls = new Map<string, HTMLButtonElement>();
  private markerStates = new Map<string, MarkerState>();
  private activeHotspot: ArchitecturalHotspot | null = null;
  private projVec = new THREE.Vector3();
  private camDir = new THREE.Vector3();
  private toTarget = new THREE.Vector3();
  private lastCamPos = new THREE.Vector3(Infinity, 0, 0);
  private lastCamQuat = new THREE.Quaternion();
  private lastW = 0;
  private lastH = 0;

  private drawer: HTMLElement;
  private catEl: HTMLElement;
  private titleEl: HTMLElement;
  private metricsEl: HTMLElement;
  private bodyEl: HTMLElement;
  private flyBtn: HTMLButtonElement;

  public onFlyTo?: (hotspot: ArchitecturalHotspot) => void;

  constructor(private markersLayer: HTMLElement) {
    this.drawer = document.getElementById('hotspot-drawer')!;
    this.catEl = document.getElementById('hotspot-category')!;
    this.titleEl = document.getElementById('hotspot-title')!;
    this.metricsEl = document.getElementById('hotspot-metrics')!;
    this.bodyEl = document.getElementById('hotspot-body')!;
    this.flyBtn = document.getElementById('hotspot-flyto') as HTMLButtonElement;

    document.getElementById('hotspot-close')!.addEventListener('click', () => this.closeDrawer());
    this.flyBtn.addEventListener('click', () => {
      if (this.activeHotspot) {
        this.onFlyTo?.(this.activeHotspot);
      }
    });

    for (const hs of ARCHITECTURAL_HOTSPOTS) {
      const btn = document.createElement('button');
      btn.className = 'hotspot-pin';
      btn.innerHTML = `<span class="pin-dot"></span><span class="pin-label">${hs.title}</span>`;
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.openDrawer(hs);
      });
      this.markersLayer.appendChild(btn);
      this.markerEls.set(hs.id, btn);
      this.markerStates.set(hs.id, { shown: false, x: -9999, y: -9999, op: -1 });
    }
  }

  public setVisible(v: boolean): void {
    this.visible = v;
    this.markersLayer.style.display = v ? 'block' : 'none';
    if (v) {
      this.lastCamPos.x = Infinity;
    } else {
      this.closeDrawer();
    }
  }

  public toggle(): boolean {
    this.setVisible(!this.visible);
    return this.visible;
  }

  public openDrawer(hs: ArchitecturalHotspot): void {
    this.activeHotspot = hs;
    this.catEl.textContent = hs.category;
    this.titleEl.textContent = hs.title;
    this.bodyEl.textContent = hs.description;
    this.metricsEl.innerHTML = hs.metrics.map((m) => `<span class="metric-pill">${m}</span>`).join('');
    this.drawer.classList.remove('hidden');

    if (document.pointerLockElement) {
      document.exitPointerLock();
    }
  }

  public closeDrawer(): void {
    this.activeHotspot = null;
    this.drawer.classList.add('hidden');
  }

  public updateProjections(camera: THREE.PerspectiveCamera, width: number, height: number): void {
    if (!this.visible) return;
    const camPos = camera.position;
    if (
      width === this.lastW &&
      height === this.lastH &&
      camPos.distanceToSquared(this.lastCamPos) < 1e-6 &&
      Math.abs(camera.quaternion.dot(this.lastCamQuat)) > 0.9999999
    ) {
      return;
    }
    this.lastW = width;
    this.lastH = height;
    this.lastCamPos.copy(camPos);
    this.lastCamQuat.copy(camera.quaternion);

    camera.getWorldDirection(this.camDir);

    const inCryptCam = camPos.y < -1.5;
    const inInteriorCam =
      !inCryptCam &&
      camPos.y < 52 &&
      Math.abs(camPos.x) < 28 &&
      camPos.z > -32 &&
      camPos.z < 46;

    for (const hs of ARCHITECTURAL_HOTSPOTS) {
      const el = this.markerEls.get(hs.id)!;
      const st = this.markerStates.get(hs.id)!;
      const worldPos = this.projVec.set(hs.position[0], hs.position[1], hs.position[2]);
      const dist = worldPos.distanceTo(camPos);

      // Context-aware visibility: hide crypt pins above ground, hide interior pins from outside/aerial, and vice-versa
      const isCryptHs = hs.position[1] < -1.0;
      if (
        (inCryptCam && !isCryptHs) ||
        (!inCryptCam && isCryptHs) ||
        (!inInteriorCam && INTERIOR_ONLY_IDS.has(hs.id)) ||
        (inInteriorCam && EXTERIOR_ONLY_IDS.has(hs.id)) ||
        dist > 260
      ) {
        if (st.shown) {
          st.shown = false;
          el.style.display = 'none';
        }
        continue;
      }

      this.toTarget.subVectors(worldPos, camPos).normalize();
      if (this.toTarget.dot(this.camDir) <= 0.12) {
        if (st.shown) {
          st.shown = false;
          el.style.display = 'none';
        }
        continue;
      }

      worldPos.project(camera);
      // Keep pins neatly inside the safe central canvas region (away from top & bottom HUD bars)
      if (worldPos.z > 1 || Math.abs(worldPos.x) > 0.92 || worldPos.y > 0.78 || worldPos.y < -0.72) {
        if (st.shown) {
          st.shown = false;
          el.style.display = 'none';
        }
        continue;
      }

      const sx = (worldPos.x * 0.5 + 0.5) * width;
      const sy = (-worldPos.y * 0.5 + 0.5) * height;
      const op = THREE.MathUtils.clamp(1.2 - dist / 240, 0.5, 1.0);

      if (!st.shown) {
        st.shown = true;
        el.style.display = 'flex';
      }
      if (Math.abs(sx - st.x) > 0.4 || Math.abs(sy - st.y) > 0.4) {
        st.x = sx;
        st.y = sy;
        el.style.transform = `translate3d(${sx.toFixed(1)}px, ${sy.toFixed(1)}px, 0) translate(-50%, -50%)`;
      }
      if (Math.abs(op - st.op) > 0.025) {
        st.op = op;
        el.style.opacity = op.toFixed(2);
      }
    }
  }
}
