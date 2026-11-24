import * as THREE from 'three';
import { LAYOUT } from '../data/layout';

const GRID = LAYOUT.frame.grid; // 7.5 m module
const OVERLAY_Y = LAYOUT.levels.nave + 0.08;

/**
 * Interactive Gaudí Geometry Overlay (toggled with [G]):
 * Visualizes the 7.5m fundamental grid, ruled straight-line hyperboloid generators,
 * double-helix column twist guides, catenary structural force curves & tower height lines.
 */
export class GeometryOverlay {
  public readonly group = new THREE.Group();

  constructor() {
    this.group.name = 'GaudiGeometryOverlay';
    this.group.visible = false;

    this.buildGrid75();
    this.buildHyperboloidGenerators();
    this.buildDoubleHelixGuides();
    this.buildCatenaryForceArches();
    this.buildTowerElevationRings();
  }

  private buildGrid75(): void {
    const pts: number[] = [];
    const y = OVERLAY_Y;
    const hw = LAYOUT.nave.halfWidth; // 22.5
    const tl = LAYOUT.transept.halfLength; // 30
    const th = LAYOUT.transept.halfWidth; // 15
    // 7.5 m grid across the nave and crossing (runtime z = -plan y: -15 at the apse side ... the Glory wall)
    const zN = -th;
    const zS = Math.floor(-LAYOUT.nave.gloryInnerY / GRID) * GRID; // 45
    for (let x = -hw; x <= hw + 1e-6; x += GRID) {
      pts.push(x, y, zN, x, y, zS);
    }
    for (let z = zN; z <= zS + 1e-6; z += GRID) {
      pts.push(-hw, y, z, hw, y, z);
    }
    // Transept grid arms
    for (let z = -th; z <= th + 1e-6; z += GRID) {
      pts.push(-tl, y, z, tl, y, z);
    }
    for (const x of [-tl, tl]) {
      pts.push(x, y, -th, x, y, th);
    }
    // Apse rings about the apse centre: presbytery columns, chapel front, chapel back
    const [acx, acy] = LAYOUT.apse.center;
    for (const r of [LAYOUT.apse.presbyteryRingR, LAYOUT.apse.chapelFrontR, LAYOUT.apse.chapelBackR]) {
      const segs = 40;
      for (let i = 0; i < segs; i++) {
        const a0 = (i / segs) * Math.PI;
        const a1 = ((i + 1) / segs) * Math.PI;
        pts.push(acx + r * Math.cos(a0), y, -(acy + r * Math.sin(a0)), acx + r * Math.cos(a1), y, -(acy + r * Math.sin(a1)));
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
    const mat = new THREE.LineBasicMaterial({ color: '#4de1ff', transparent: true, opacity: 0.55 });
    this.group.add(new THREE.LineSegments(geo, mat));
  }

  private buildHyperboloidGenerators(): void {
    // True double-ruled straight-line generators of a one-sheet hyperboloid!
    const pts: number[] = [];
    const addRuledHyperboloid = (cx: number, cy: number, cz: number, rNeck: number, rOuter: number, h: number, lines: number) => {
      const twist = Math.acos(Math.min(0.95, rNeck / rOuter));
      for (let i = 0; i < lines; i++) {
        const a = (i / lines) * Math.PI * 2;
        // Family 1 (+twist) and Family 2 (-twist) straight lines forming the curved hyperboloid!
        for (const dir of [-1, 1]) {
          const a0 = a;
          const a1 = a + dir * twist * 2.0;
          pts.push(
            cx + rOuter * Math.cos(a0), cy - h * 0.5, cz + rOuter * Math.sin(a0),
            cx + rOuter * Math.cos(a1), cy + h * 0.5, cz + rOuter * Math.sin(a1)
          );
        }
      }
    };

    // Crossing central hyperboloid + nave vault hyperboloids
    addRuledHyperboloid(0, 58.2, 0, 3.2, 7.2, 6.2, 24);
    // Nave bays: 11.25 next to the crossing, then the window bays 18.75 ... 41.25 (layout naveWindowBayY)
    for (const z of [11.25, ...LAYOUT.naveWindowBayY.map((by) => -by)]) {
      addRuledHyperboloid(0, 44.0, z, 1.65, 5.2, 4.4, 16);
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
    const mat = new THREE.LineBasicMaterial({ color: '#ffd166', transparent: true, opacity: 0.78 });
    this.group.add(new THREE.LineSegments(geo, mat));
  }

  private buildDoubleHelixGuides(): void {
    // Counter-rotating double helices around the 4 central Porphyry crossing columns
    const ptsCW: number[] = [];
    const ptsCCW: number[] = [];
    const cols: Array<[number, number]> = LAYOUT.columns.filter((c) => c.kind === 'porphyry').map((c) => [c.x, -c.y]);
    for (const [cx, cz] of cols) {
      const steps = 40;
      const r = 1.38;
      for (let strand = 0; strand < 3; strand++) {
        const offset = (strand / 3) * Math.PI * 2;
        for (let i = 0; i < steps; i++) {
          const t0 = i / steps;
          const t1 = (i + 1) / steps;
          const y0 = 1.5 + t0 * 19.0;
          const y1 = 1.5 + t1 * 19.0;
          const a0 = offset + t0 * Math.PI * 1.4;
          const a1 = offset + t1 * Math.PI * 1.4;
          ptsCW.push(cx + r * Math.cos(a0), y0, cz + r * Math.sin(a0), cx + r * Math.cos(a1), y1, cz + r * Math.sin(a1));
          const b0 = offset - t0 * Math.PI * 1.4;
          const b1 = offset - t1 * Math.PI * 1.4;
          ptsCCW.push(cx + r * Math.cos(b0), y0, cz + r * Math.sin(b0), cx + r * Math.cos(b1), y1, cz + r * Math.sin(b1));
        }
      }
    }

    const g1 = new THREE.BufferGeometry();
    g1.setAttribute('position', new THREE.Float32BufferAttribute(ptsCW, 3));
    this.group.add(new THREE.LineSegments(g1, new THREE.LineBasicMaterial({ color: '#ff6b6b', transparent: true, opacity: 0.85 })));

    const g2 = new THREE.BufferGeometry();
    g2.setAttribute('position', new THREE.Float32BufferAttribute(ptsCCW, 3));
    this.group.add(new THREE.LineSegments(g2, new THREE.LineBasicMaterial({ color: '#4ecdc4', transparent: true, opacity: 0.85 })));
  }

  private buildCatenaryForceArches(): void {
    // Inverted catenary hanging-chain force lines (Gaudí's funicular structural principle)
    const pts: number[] = [];
    const addCatenary = (zPos: number, span: number, peakY: number) => {
      const segs = 28;
      const half = span * 0.5;
      const a = 0.14;
      const maxCosh = Math.cosh(a * half);
      for (let i = 0; i < segs; i++) {
        const x0 = -half + (i / segs) * span;
        const x1 = -half + ((i + 1) / segs) * span;
        const y0 = peakY - ((Math.cosh(a * x0) - 1) / (maxCosh - 1)) * (peakY - 1.5);
        const y1 = peakY - ((Math.cosh(a * x1) - 1) / (maxCosh - 1)) * (peakY - 1.5);
        pts.push(x0, y0, zPos, x1, y1, zPos);
      }
    };

    addCatenary(0, 44.0, 60.5);
    addCatenary(15.0, 44.0, 45.8);
    addCatenary(30.0, 44.0, 45.8);

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
    this.group.add(new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color: '#ff9f1c', transparent: true, opacity: 0.72 })));
  }

  private buildTowerElevationRings(): void {
    // Horizontal elevation benchmark rings at 45m, 107m, 138m, 172.5m around the central axis
    const heights: Array<[number, number, string]> = [
      [45.0, 28, '#4de1ff'],
      [107.0, 38, '#ffd166'],
      [138.0, 26, '#90e0ef'],
      [172.5, 16, '#ff6b6b'],
    ];
    for (const [h, r, col] of heights) {
      const pts: number[] = [];
      const segs = 48;
      for (let i = 0; i < segs; i++) {
        const a0 = (i / segs) * Math.PI * 2;
        const a1 = ((i + 1) / segs) * Math.PI * 2;
        pts.push(r * Math.cos(a0), h, r * Math.sin(a0), r * Math.cos(a1), h, r * Math.sin(a1));
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
      this.group.add(new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.5 })));
    }
  }

  public setVisible(v: boolean): void {
    this.group.visible = v;
  }

  public toggle(): boolean {
    this.group.visible = !this.group.visible;
    return this.group.visible;
  }
}
