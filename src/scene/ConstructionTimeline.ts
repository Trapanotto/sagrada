import * as THREE from 'three';
import { t, type Localized } from '../i18n';
import { LAYOUT } from '../data/layout';

const LV = LAYOUT.levels;
/** Lowest point of the Nativity / Passion porches and stairs (their feet sit on the sloped ground). */
const FACADE_MIN_Y = Math.min(LAYOUT.nativity.stair.bottomZ, LAYOUT.passion.stair.bottomZ) - 0.4;
/** The Glory stair reaches down to ground_z at its foot. */
const GLORY_MIN_Y = LAYOUT.glory.stair.bottomZ - 0.1;
/** Crypt: from below its floor to above the central vault crown. */
const CRYPT_MIN_Y = LV.crypt - 1.0;
const CRYPT_MAX_Y = LV.cryptVaultCentral + 0.2;
/** Cloister & corner buildings: up to the sacristy lanterns. */
const CLOISTER_MAX_Y = Math.max(...Object.values(LAYOUT.cornerBuildings).map((b) => b.top)) + 1.0;

export interface TimelineMilestone {
  year: number;
  label: Localized;
  caption: Localized;
}

export const TIMELINE_MILESTONES: TimelineMilestone[] = [
  {
    year: 1889,
    label: { de: '1889', en: '1889' },
    caption: {
      de: '1882–1889 · Grundsteinlegung & Vollendung der neugotischen Krypta',
      en: '1882–1889 · Foundation stone laid & neo-Gothic crypt completed',
    },
  },
  {
    year: 1926,
    label: { de: '1926', en: '1926' },
    caption: {
      de: '1926 · Tod Antoni Gaudís — Geburtsfassade & erster Glockenturm (Barnabas)',
      en: '1926 · Death of Antoni Gaudí — Nativity façade & first bell tower (St Barnabas)',
    },
  },
  {
    year: 1976,
    label: { de: '1976', en: '1976' },
    caption: {
      de: '1954–1976 · Alle 4 Geburts- & 4 Passions-Türme mit Knochensäulen vollendet',
      en: '1954–1976 · All 4 Nativity & 4 Passion towers completed, with the bone-like columns',
    },
  },
  {
    year: 2010,
    label: { de: '2010', en: '2010' },
    caption: {
      de: '2010 · Kirchweihe durch Papst Benedikt XVI. — Säulenwald & Gewölbe fertig',
      en: '2010 · Consecrated by Pope Benedict XVI — forest of columns & vaults complete',
    },
  },
  {
    year: 2026,
    label: { de: '2026', en: '2026' },
    caption: {
      de: '2021–2026 · Marienstern (138 m), 4 Evangelisten (135 m) & Jesus-Turm (172,5 m)',
      en: '2021–2026 · Star of Mary (138 m), 4 Evangelists (135 m) & Tower of Jesus (172.5 m)',
    },
  },
  {
    year: 2034,
    label: { de: 'Final', en: 'Final' },
    caption: {
      de: 'Finaler Entwurf · Vollendete Glorienfassade, 4 Südtürme & Große Freitreppe',
      en: 'Final design · Completed Glory façade, 4 south towers & grand staircase',
    },
  },
];

interface PhaseEntry {
  obj: THREE.Mesh;
  startYear: number;
  endYear: number;
  minY: number;
  maxY: number;
  clipPlane: THREE.Plane;
  origMaterial: THREE.Material | THREE.Material[];
  clippedMaterials: THREE.Material[] | null;
}

/**
 * Interactive Historical Construction Timelapse (1882 -> 2034+ Final Design).
 * Uses smooth per-phase vertical GPU clipping planes lazily ONLY when viewing historical years,
 * keeping Final mode (2034) free of fragment discard / Hardware Early-Z overhead!
 */
export class ConstructionTimeline {
  public currentYear = 2034;
  public playing = false;
  private clippingActive = false;
  private entries: PhaseEntry[] = [];
  private trackedUuids = new Set<string>();

  public onYearChange?: (year: number, caption: string) => void;
  public onPlayChange?: (playing: boolean) => void;
  public onLocalClippingChange?: (enabled: boolean) => void;

  public get isHistorical(): boolean {
    return this.currentYear < 2033.8;
  }

  /**
   * Classify every mesh in a loaded GLB module into its authentic historical construction phase.
   */
  public registerModule(root: THREE.Object3D): void {
    root.traverse((obj) => {
      if (!(obj instanceof THREE.Mesh) || this.trackedUuids.has(obj.uuid)) return;
      const name = obj.name;

      // Always keep Eixample streets, plazas, parks & lamps visible across all years
      if (
        root.name === 'Module_eixample' ||
        root.name === 'Module_plaza_life' ||
        name.startsWith('Eixample_') ||
        name.startsWith('Plaza_') ||
        name.startsWith('Bench_') ||
        name.startsWith('Instanced_Bench') ||
        name.startsWith('Instanced_PlaneTree') ||
        name.startsWith('Instanced_CypressTree') ||
        name.startsWith('Instanced_StreetLamp')
      ) {
        return;
      }

      this.trackedUuids.add(obj.uuid);

      // Determine authentic historical start/end construction years + vertical range
      let startYear = 1978;
      let endYear = 2010;
      let minY = -1.0;
      let maxY = 55.0;

      if (name.includes('Crypt')) {
        startYear = 1882;
        endYear = 1889;
        minY = CRYPT_MIN_Y;
        maxY = CRYPT_MAX_Y;
      } else if (name.includes('Facade_Nativity') || name.includes('Facade_Cypress') || name.includes('Facade_Doves')) {
        startYear = 1894;
        endYear = 1928;
        minY = FACADE_MIN_Y;
        maxY = 54.0;
      } else if (name.includes('Towers_Nativity')) {
        startYear = 1912;
        endYear = 1930;
        minY = 24.0;
        maxY = 109.0;
      } else if (name.includes('Facade_Passion') || name.includes('Towers_Passion')) {
        startYear = 1954;
        endYear = 1976;
        minY = FACADE_MIN_Y;
        maxY = 115.0;
      } else if (
        name.includes('Interior_MarbleFloor') ||
        name.includes('Col_') ||
        name.includes('Instanced_Col_') ||
        name.includes('Interior_ColumnBranches') ||
        name.includes('Interior_NaveWalls') ||
        name.includes('Interior_Galleries')
      ) {
        startYear = 1978;
        endYear = 2002;
        minY = 0.0;
        maxY = 48.0;
      } else if (
        name.includes('Interior_HyperboloidVaults') ||
        name.includes('Interior_StainedGlass') ||
        name.includes('Interior_HighAltar') ||
        name.includes('Interior_GoldAccents') ||
        name.includes('Pew') ||
        name.includes('Furnish_') ||
        name.includes('Exhibit_') ||
        name.includes('Facade_FruitPinnacles') ||
        name.includes('Facade_BronzeDoors')
      ) {
        startYear = 2000;
        endYear = 2010;
        minY = 0.0;
        maxY = 70.0;
      } else if (name.includes('Tower_MaryStar')) {
        startYear = 2016;
        endYear = 2021;
        minY = 120.0;
        maxY = 140.0;
      } else if (name.includes('Towers_Evangelist')) {
        startYear = 2018;
        endYear = 2023;
        minY = 118.0;
        maxY = 138.0;
      } else if (name.includes('Towers_TrencadisPinnacles') || name.includes('Towers_GoldAccents')) {
        startYear = 2016;
        endYear = 2026;
        minY = 85.0;
        maxY = 175.0;
      } else if (name.includes('Towers_CentralAndGlory')) {
        startYear = 2012;
        endYear = 2026;
        minY = 50.0;
        maxY = 158.0;
      } else if (name.includes('Tower_JesusCross')) {
        startYear = 2024;
        endYear = 2026;
        minY = 154.0;
        maxY = 176.0;
      } else if (name.includes('Cloister_') || name.includes('Sacristy_')) {
        startYear = 2015;
        endYear = 2026;
        minY = LV.nave - 1.2;
        maxY = CLOISTER_MAX_Y;
      } else if (name.includes('Facade_GloryAndRoofs') || name.includes('Facade_GloryBridge') || name.includes('Facade_EntranceStairs_Glory')) {
        startYear = 2026;
        endYear = 2034;
        minY = GLORY_MIN_Y;
        maxY = 66.0;
      }

      // Defer material cloning & clipping planes until historical timelapse is actually used
      const clipPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 300);

      this.entries.push({
        obj,
        startYear,
        endYear,
        minY,
        maxY,
        clipPlane,
        origMaterial: obj.material,
        clippedMaterials: null,
      });
    });

    this.applyYear(this.currentYear);
  }

  private ensureClippedMaterials(e: PhaseEntry): THREE.Material[] {
    if (e.clippedMaterials) return e.clippedMaterials;
    const origMats = Array.isArray(e.origMaterial) ? e.origMaterial : [e.origMaterial];
    e.clippedMaterials = origMats.map((m) => {
      const cm = m.clone();
      cm.onBeforeCompile = m.onBeforeCompile;
      cm.customProgramCacheKey = m.customProgramCacheKey;
      cm.clippingPlanes = [e.clipPlane];
      cm.needsUpdate = true;
      return cm;
    });
    return e.clippedMaterials;
  }

  /** Localized caption for a (possibly fractional) year — call again after a language switch. */
  public getCaptionForYear(year: number): string {
    const y = Math.round(year);
    if (year <= 1892) return t('timeline.eraCrypt');
    if (year <= 1930) return t('timeline.eraGaudi', { year: y });
    if (year <= 1978) return t('timeline.eraPassion', { year: y });
    if (year <= 2011) return t('timeline.eraNave', { year: y });
    if (year <= 2023) return t('timeline.eraMary', { year: y });
    if (year <= 2026.5) return t('timeline.eraJesus', { year: y });
    return t('timeline.eraFinal');
  }

  public applyYear(year: number): void {
    this.currentYear = THREE.MathUtils.clamp(year, 1882, 2034);
    const isFinal = this.currentYear >= 2033.8;

    if (isFinal) {
      if (this.clippingActive) {
        this.clippingActive = false;
        this.onLocalClippingChange?.(false);
        for (const e of this.entries) {
          e.obj.material = e.origMaterial;
        }
      }
      for (const e of this.entries) {
        e.obj.visible = true;
        e.clipPlane.constant = 300;
      }
    } else {
      if (!this.clippingActive) {
        this.clippingActive = true;
        this.onLocalClippingChange?.(true);
      }
      for (const e of this.entries) {
        const clipped = this.ensureClippedMaterials(e);
        const targetMat = Array.isArray(e.origMaterial) ? clipped : clipped[0];
        if (e.obj.material !== targetMat) {
          e.obj.material = targetMat;
        }

        if (this.currentYear <= e.startYear) {
          e.obj.visible = false;
        } else if (this.currentYear >= e.endYear) {
          e.obj.visible = true;
          e.clipPlane.constant = 300;
        } else {
          e.obj.visible = true;
          const frac = (this.currentYear - e.startYear) / Math.max(0.5, e.endYear - e.startYear);
          // Smooth organic upward growth of stonework!
          e.clipPlane.constant = THREE.MathUtils.lerp(e.minY, e.maxY, frac);
        }
      }
    }

    this.onYearChange?.(this.currentYear, this.getCaptionForYear(this.currentYear));
  }

  public setPlaying(playing: boolean): void {
    this.playing = playing;
    if (playing && this.currentYear >= 2033.5) {
      this.applyYear(1882);
    }
    this.onPlayChange?.(playing);
  }

  public togglePlay(): boolean {
    this.setPlaying(!this.playing);
    return this.playing;
  }

  public update(dt: number): boolean {
    if (!this.playing) return false;
    // Smooth 16-second timelapse spanning 1882 -> 2034
    const next = this.currentYear + dt * 9.5;
    if (next >= 2034) {
      this.applyYear(2034);
      this.setPlaying(false);
    } else {
      this.applyYear(next);
    }
    return true;
  }
}
