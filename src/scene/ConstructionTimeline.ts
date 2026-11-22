import * as THREE from 'three';

export interface TimelineMilestone {
  year: number;
  label: string;
  caption: string;
}

export const TIMELINE_MILESTONES: TimelineMilestone[] = [
  { year: 1889, label: '1889', caption: '1882–1889 · Grundsteinlegung & Vollendung der neugotischen Krypta' },
  { year: 1926, label: '1926', caption: '1926 · Tod Antoni Gaudís — Geburtsfassade & erster Glockenturm (Barnabas)' },
  { year: 1976, label: '1976', caption: '1954–1976 · Alle 4 Geburts- & 4 Passions-Türme mit Knochensäulen vollendet' },
  { year: 2010, label: '2010', caption: '2010 · Kirchweihe durch Papst Benedikt XVI. — Säulenwald & Gewölbe fertig' },
  { year: 2026, label: '2026', caption: '2021–2026 · Marienstern (138 m), 4 Evangelisten (135 m) & Jesus-Turm (172,5 m)' },
  { year: 2034, label: 'Final', caption: 'Finaler Entwurf · Vollendete Glorienfassade, 4 Südtürme & Große Freitreppe' },
];

interface PhaseEntry {
  obj: THREE.Object3D;
  startYear: number;
  endYear: number;
  minY: number;
  maxY: number;
  clipPlane: THREE.Plane;
  materials: THREE.Material[];
}

/**
 * Interactive Historical Construction Timelapse (1882 -> 2034+ Final Design).
 * Uses smooth per-phase vertical GPU clipping planes so the basilica literally rises
 * stone-by-stone through 150 years of real architectural history!
 */
export class ConstructionTimeline {
  public currentYear = 2034;
  public playing = false;
  private entries: PhaseEntry[] = [];
  private trackedUuids = new Set<string>();

  public onYearChange?: (year: number, caption: string) => void;
  public onPlayChange?: (playing: boolean) => void;

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
        minY = -6.5;
        maxY = 1.5;
      } else if (name.includes('Facade_Nativity') || name.includes('Facade_Cypress') || name.includes('Facade_Doves')) {
        startYear = 1894;
        endYear = 1928;
        minY = 0.0;
        maxY = 54.0;
      } else if (name.includes('Towers_Nativity')) {
        startYear = 1912;
        endYear = 1930;
        minY = 24.0;
        maxY = 109.0;
      } else if (name.includes('Facade_Passion') || name.includes('Towers_Passion')) {
        startYear = 1954;
        endYear = 1976;
        minY = 0.0;
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
        minY = 0.0;
        maxY = 42.0;
      } else if (name.includes('Facade_GloryAndRoofs')) {
        startYear = 2026;
        endYear = 2034;
        minY = 0.0;
        maxY = 66.0;
      }

      // Clone material only if needed so each phase owns an independent clipping plane
      const origMats = Array.isArray(obj.material) ? obj.material : [obj.material];
      const clipPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 300);
      const clonedMats = origMats.map((m) => {
        const cm = m.clone();
        cm.clippingPlanes = [clipPlane];
        return cm;
      });
      obj.material = Array.isArray(obj.material) ? clonedMats : clonedMats[0];

      this.entries.push({
        obj,
        startYear,
        endYear,
        minY,
        maxY,
        clipPlane,
        materials: clonedMats,
      });
    });

    this.applyYear(this.currentYear);
  }

  public getCaptionForYear(year: number): string {
    if (year <= 1892) return '1882–1889 · Grundsteinlegung & Bau der neugotischen Krypta';
    if (year <= 1930) return `${Math.round(year)} · Ära Antoni Gaudí — Geburtsfassade & erste Glockentürme`;
    if (year <= 1978) return `${Math.round(year)} · Passionsfassade mit Knochensäulen & 4 Westtürmen`;
    if (year <= 2011) return `${Math.round(year)} · Vollendung des Säulenwalds, Gewölbe & Weihe (2010)`;
    if (year <= 2023) return `${Math.round(year)} · Marien-Turm mit Morgenstern (138 m) & Evangelisten-Türme (135 m)`;
    if (year <= 2026.5) return `${Math.round(year)} · 100. Todestag Gaudís — Turm Jesu Christi (172,5 m) & Kreuzgang`;
    return 'Finaler Entwurf · Glorienfassade (Süd), 4 Südtürme & Große Freitreppe';
  }

  public applyYear(year: number): void {
    this.currentYear = THREE.MathUtils.clamp(year, 1882, 2034);
    const isFinal = this.currentYear >= 2033.8;

    for (const e of this.entries) {
      if (isFinal) {
        e.obj.visible = true;
        e.clipPlane.constant = 300;
        continue;
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
