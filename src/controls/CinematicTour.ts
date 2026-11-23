import * as THREE from 'three';
import type { Localized } from '../i18n';

export interface TourChapter {
  title: Localized;
  subtitle: Localized;
  duration: number;
  startHour: number;
  endHour: number;
  posPoints: Array<[number, number, number]>;
  lookPoints: Array<[number, number, number]>;
}

const TOUR_CHAPTERS: TourChapter[] = [
  {
    title: { de: 'I · Geburtsfassade im Morgenlicht', en: 'I · The Nativity façade in morning light' },
    subtitle: {
      de: 'Plaça de Gaudí · Spiegelteich & Lebensbaum-Zypresse',
      en: 'Plaça de Gaudí · reflecting pond & the cypress Tree of Life',
    },
    duration: 13,
    startHour: 8.1,
    endHour: 9.2,
    posPoints: [
      [112, 3.2, 16],
      [96, 4.5, 4],
      [74, 12.0, -4],
      [48, 8.5, 0],
    ],
    lookPoints: [
      [31, 34, 0],
      [31, 30, 0],
      [31, 44, 0],
      [24, 14, 0],
    ],
  },
  {
    title: { de: 'II · Der Säulenwald & das wandernde Licht', en: 'II · The forest of columns & the wandering light' },
    subtitle: {
      de: 'Zeitraffer 09:30 → 17:45 · Von kühlem Türkis zu glühendem Abendrot',
      en: 'Time-lapse 09:30 → 17:45 · from cool turquoise to a glowing sunset',
    },
    duration: 16,
    startHour: 9.4,
    endHour: 17.7,
    posPoints: [
      [26, 4.2, 0],
      [8, 4.0, 18],
      [0, 3.8, 34],
      [-6, 9.5, 22],
      [0, 12.0, 2],
    ],
    lookPoints: [
      [0, 18, 12],
      [0, 24, 24],
      [0, 22, -10],
      [6, 26, -16],
      [0, 15, -20],
    ],
  },
  {
    title: { de: 'III · Passionsfassade & Glorienportal', en: 'III · The Passion façade & the Glory portal' },
    subtitle: {
      de: 'Goldene Abendsonne auf den Knochensäulen & der großen Freitreppe',
      en: 'Golden evening sun on the bone-like columns & the grand staircase',
    },
    duration: 13,
    startHour: 17.7,
    endHour: 18.6,
    posPoints: [
      [-58, 5.5, 18],
      [-56, 16.0, -8],
      [-38, 22.0, 48],
      [0, 14.0, 88],
    ],
    lookPoints: [
      [-31, 22, 0],
      [-31, 28, 0],
      [-10, 26, 48],
      [0, 36, 48],
    ],
  },
  {
    title: { de: 'IV · Stille der Krypta', en: 'IV · The stillness of the crypt' },
    subtitle: { de: 'Neugotisches Gewölbe (-5,5 m) · Grab von Antoni Gaudí', en: 'Neo-Gothic vault (-5.5 m) · tomb of Antoni Gaudí' },
    duration: 9,
    startHour: 18.8,
    endHour: 19.2,
    posPoints: [
      [3.5, -3.5, -14.5],
      [0.0, -3.7, -17.0],
      [-4.2, -3.7, -19.5],
    ],
    lookPoints: [
      [-6.0, -4.3, -22.5],
      [-9.2, -4.5, -23.5],
      [-9.8, -4.7, -23.5],
    ],
  },
  {
    title: { de: 'V · Die 18 Türme bei Nacht', en: 'V · The 18 towers by night' },
    subtitle: {
      de: 'Marienstern (138 m), Evangelisten (135 m) & Turm Jesu Christi (172,5 m)',
      en: 'Star of Mary (138 m), the Evangelists (135 m) & the Tower of Jesus Christ (172.5 m)',
    },
    duration: 17,
    startHour: 19.6,
    endHour: 22.3,
    posPoints: [
      [118, 65, 95],
      [148, 118, 45],
      [115, 148, -95],
      [-95, 145, -105],
      [165, 116, 148],
    ],
    lookPoints: [
      [0, 80, -4],
      [0, 112, -10],
      [0, 134, -14],
      [0, 128, -4],
      [0, 78, -4],
    ],
  },
];

export class CinematicTour {
  public active = false;
  /** Chapter currently shown (lets the UI re-render its caption after a language switch). */
  public get currentChapter(): TourChapter {
    return TOUR_CHAPTERS[this.chapterIdx];
  }
  public paused = false;

  private chapterIdx = 0;
  private chapterElapsed = 0;
  private posCurves: THREE.CatmullRomCurve3[];
  private lookCurves: THREE.CatmullRomCurve3[];
  private tmpPos = new THREE.Vector3();
  private tmpLook = new THREE.Vector3();

  public onChapterChange?: (chapter: TourChapter, index: number, total: number) => void;
  public onTimeUpdate?: (hours: number) => void;
  public onProgress?: (fraction: number) => void;
  public onStateChange?: (active: boolean, paused: boolean) => void;

  constructor(private camera: THREE.PerspectiveCamera) {
    this.posCurves = TOUR_CHAPTERS.map(
      (c) => new THREE.CatmullRomCurve3(c.posPoints.map((p) => new THREE.Vector3(...p)), false, 'catmullrom', 0.45)
    );
    this.lookCurves = TOUR_CHAPTERS.map(
      (c) => new THREE.CatmullRomCurve3(c.lookPoints.map((p) => new THREE.Vector3(...p)), false, 'catmullrom', 0.45)
    );
  }

  public start(): void {
    this.active = true;
    this.paused = false;
    this.chapterIdx = 0;
    this.chapterElapsed = 0;
    this.onChapterChange?.(TOUR_CHAPTERS[0], 0, TOUR_CHAPTERS.length);
    this.onStateChange?.(true, false);
  }

  public stop(): void {
    if (!this.active) return;
    this.active = false;
    this.paused = false;
    this.onStateChange?.(false, false);
  }

  public toggle(): boolean {
    if (this.active) this.stop();
    else this.start();
    return this.active;
  }

  public togglePause(): boolean {
    if (!this.active) return false;
    this.paused = !this.paused;
    this.onStateChange?.(this.active, this.paused);
    return this.paused;
  }

  public nextChapter(): void {
    if (!this.active) return;
    this.chapterIdx = (this.chapterIdx + 1) % TOUR_CHAPTERS.length;
    this.chapterElapsed = 0;
    this.onChapterChange?.(TOUR_CHAPTERS[this.chapterIdx], this.chapterIdx, TOUR_CHAPTERS.length);
  }

  public update(dt: number): void {
    if (!this.active || this.paused) return;

    const ch = TOUR_CHAPTERS[this.chapterIdx];
    this.chapterElapsed += Math.min(dt, 0.08);
    if (this.chapterElapsed >= ch.duration) {
      this.nextChapter();
      return;
    }

    const rawT = THREE.MathUtils.clamp(this.chapterElapsed / ch.duration, 0, 1);
    // Gentle ease-in/out on each chapter curve
    const t = rawT * rawT * (3 - 2 * rawT);

    this.posCurves[this.chapterIdx].getPointAt(t, this.tmpPos);
    this.lookCurves[this.chapterIdx].getPointAt(t, this.tmpLook);

    this.camera.position.copy(this.tmpPos);
    this.camera.lookAt(this.tmpLook);

    const hours = THREE.MathUtils.lerp(ch.startHour, ch.endHour, rawT);
    this.onTimeUpdate?.(hours);
    this.onProgress?.((this.chapterIdx + rawT) / TOUR_CHAPTERS.length);
  }
}
