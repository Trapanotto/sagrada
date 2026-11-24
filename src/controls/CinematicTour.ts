import * as THREE from 'three';
import type { Localized } from '../i18n';
import { LAYOUT, cryptDepthBelowNave, groundWorldY, towerByKey } from '../data/layout';

export interface TourChapter {
  title: Localized;
  subtitle: Localized;
  duration: number;
  startHour: number;
  endHour: number;
  posPoints: Array<[number, number, number]>;
  lookPoints: Array<[number, number, number]>;
}

// Anchors from the layout (runtime frame: z = -plan y). Camera paths are given relative to them where
// they frame a building, so they follow the plan; free-flight orbit points are plain numbers.
const NAT_X = towerByKey('tower.nativityInnerS').x; // Nativity tower line
const PAS_X = towerByKey('tower.passionInnerS').x; // Passion tower line
const GLORY_Z = -towerByKey('tower.gloryInnerW').y; // Glory tower line
const APSE_Z = -LAYOUT.apse.center[1];
const CRYPT_Y = LAYOUT.levels.crypt;
const TOMB = { x: LAYOUT.crypt.gaudiTomb[0], z: -LAYOUT.crypt.gaudiTomb[1] };
const BAY = LAYOUT.naveWindowBayY.map((y) => -y); // nave bay centres (runtime z): 18.75 ... 41.25
const groundAt = (z: number) => groundWorldY(z);
const CRYPT_DEPTH = cryptDepthBelowNave(); // 9 m below the basilica floor

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
      [160, groundAt(4) + 2.4, 4],
      [130, 4, -2],
      [95, 12, -4],
      [52, 6, 0],
    ],
    lookPoints: [
      [NAT_X, 34, 0],
      [NAT_X, 30, 0],
      [NAT_X, 44, 0],
      [26, 14, 0],
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
      [11.25, 4.0, BAY[1]],
      [0, 3.8, BAY[3]],
      [-11.25, 9.5, BAY[0]],
      [0, 12.0, 2],
    ],
    lookPoints: [
      [0, 18, 12],
      [0, 24, 24],
      [0, 22, -14],
      [6, 26, -20],
      [0, 15, APSE_Z],
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
      [-70, 4, 18],
      [-62, 16, -8],
      [-48, 22, 60],
      [-20, 16, 74],
      [0, 10, 100],
    ],
    lookPoints: [
      [PAS_X, 22, 0],
      [PAS_X, 28, 0],
      [-10, 26, GLORY_Z],
      [0, 36, GLORY_Z],
    ],
  },
  {
    title: { de: 'IV · Stille der Krypta', en: 'IV · The stillness of the crypt' },
    subtitle: {
      de: `Neugotisches Gewölbe (-${CRYPT_DEPTH} m) · Grab von Antoni Gaudí`,
      en: `Neo-Gothic vault (-${CRYPT_DEPTH} m) · tomb of Antoni Gaudí`,
    },
    duration: 9,
    startHour: 18.8,
    endHour: 19.2,
    posPoints: [
      [6, CRYPT_Y + 2.2, -16],
      [0, CRYPT_Y + 1.9, -19],
      [-6, CRYPT_Y + 1.9, -21],
    ],
    lookPoints: [
      [-10, CRYPT_Y + 1.4, -17],
      [-14, CRYPT_Y + 1.0, TOMB.z - 0.25],
      [TOMB.x, CRYPT_Y + 0.8, TOMB.z - 0.05],
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
      [155, 65, 125],
      [195, 118, 60],
      [150, 148, -125],
      [-125, 145, -140],
      [215, 116, 195],
    ],
    lookPoints: [
      [0, 80, -4],
      [0, 112, -12],
      [0, 134, -16],
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
