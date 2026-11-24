import * as THREE from 'three';
import { FloorLevel } from '../data/teleports';
import { t } from '../i18n';
import { LAYOUT, cornerBuildingRect, planRectToWorld, towerRadiusAt, type Rect, type RectXY } from '../data/layout';

export class Minimap {
  private ctx: CanvasRenderingContext2D;
  private bgCanvas: HTMLCanvasElement;
  private bgCtx: CanvasRenderingContext2D;
  private cachedLevel: FloorLevel | null = null;
  private lastDrawX = Infinity;
  private lastDrawZ = Infinity;
  private lastDrawYaw = Infinity;
  private lastDrawLevel: FloorLevel | null = null;
  public activeLevel: FloorLevel = 'ground';

  // World extent displayed on the canvas (layout `minimapExtent`, runtime x / z)
  private readonly worldMinX: number;
  private readonly worldMaxX: number;
  private readonly worldMinZ: number;
  private readonly worldMaxZ: number;

  public onTeleportClick?: (worldX: number, worldZ: number, level: FloorLevel) => void;

  constructor(
    private canvas: HTMLCanvasElement,
    levelContainer: HTMLElement
  ) {
    const ext = planRectToWorld(LAYOUT.minimapExtent);
    this.worldMinX = ext.minX;
    this.worldMaxX = ext.maxX;
    this.worldMinZ = ext.minZ;
    this.worldMaxZ = ext.maxZ;
    this.ctx = canvas.getContext('2d')!;
    this.bgCanvas = document.createElement('canvas');
    this.bgCanvas.width = canvas.width;
    this.bgCanvas.height = canvas.height;
    this.bgCtx = this.bgCanvas.getContext('2d')!;

    levelContainer.querySelectorAll<HTMLButtonElement>('.level-tab').forEach((btn) => {
      btn.addEventListener('click', () => {
        const lvl = btn.dataset.level as FloorLevel;
        this.setLevel(lvl, levelContainer);
      });
    });

    canvas.addEventListener('click', (e) => {
      const rect = canvas.getBoundingClientRect();
      const px = ((e.clientX - rect.left) / rect.width) * canvas.width;
      const py = ((e.clientY - rect.top) / rect.height) * canvas.height;
      const wx = this.canvasToWorldX(px);
      const wz = this.canvasToWorldZ(py);
      this.onTeleportClick?.(wx, wz, this.activeLevel);
    });
  }

  public setLevel(level: FloorLevel, container?: HTMLElement): void {
    this.activeLevel = level;
    const tabs = (container ?? document.getElementById('minimap-levels'))?.querySelectorAll<HTMLButtonElement>('.level-tab');
    tabs?.forEach((b) => b.classList.toggle('active', b.dataset.level === level));
  }

  /** Re-bakes the cardinal labels in the current language on the next render. */
  public refreshLanguage(): void {
    this.cachedLevel = null;
    this.lastDrawLevel = null;
  }

  private worldToX(wx: number): number {
    return ((wx - this.worldMinX) / (this.worldMaxX - this.worldMinX)) * this.canvas.width;
  }

  private worldToY(wz: number): number {
    return ((wz - this.worldMinZ) / (this.worldMaxZ - this.worldMinZ)) * this.canvas.height;
  }

  private canvasToWorldX(px: number): number {
    return this.worldMinX + (px / this.canvas.width) * (this.worldMaxX - this.worldMinX);
  }

  private canvasToWorldZ(py: number): number {
    return this.worldMinZ + (py / this.canvas.height) * (this.worldMaxZ - this.worldMinZ);
  }

  private drawRectWorld(target: CanvasRenderingContext2D, x0: number, z0: number, x1: number, z1: number, fill: string, stroke?: string): void {
    const cx0 = this.worldToX(x0);
    const cy0 = this.worldToY(z0);
    const cw = this.worldToX(x1) - cx0;
    const ch = this.worldToY(z1) - cy0;
    target.fillStyle = fill;
    target.fillRect(cx0, cy0, cw, ch);
    if (stroke) {
      target.strokeStyle = stroke;
      target.lineWidth = 1;
      target.strokeRect(cx0, cy0, cw, ch);
    }
  }

  private drawCircleWorld(target: CanvasRenderingContext2D, wx: number, wz: number, radiusM: number, fill: string, stroke?: string): void {
    const cx = this.worldToX(wx);
    const cy = this.worldToY(wz);
    const r = (radiusM / (this.worldMaxX - this.worldMinX)) * this.canvas.width;
    target.beginPath();
    target.arc(cx, cy, Math.max(1.8, r), 0, Math.PI * 2);
    target.fillStyle = fill;
    target.fill();
    if (stroke) {
      target.strokeStyle = stroke;
      target.lineWidth = 1;
      target.stroke();
    }
  }

  // ── plan-frame drawing helpers (plan y = -runtime z) ──
  private planPath(target: CanvasRenderingContext2D, pts: Array<[number, number]>): void {
    target.beginPath();
    pts.forEach(([x, y], i) => {
      const px = this.worldToX(x);
      const py = this.worldToY(-y);
      if (i === 0) target.moveTo(px, py);
      else target.lineTo(px, py);
    });
    target.closePath();
  }

  private fillPlan(target: CanvasRenderingContext2D, pts: Array<[number, number]>, fill: string, stroke?: string, lineWidth = 1): void {
    this.planPath(target, pts);
    target.fillStyle = fill;
    target.fill();
    if (stroke) {
      target.strokeStyle = stroke;
      target.lineWidth = lineWidth;
      target.stroke();
    }
  }

  private rectPts(
    r: Rect | RectXY,
    chamfer = 0,
    corners: [boolean, boolean, boolean, boolean] = [true, true, true, true]
  ): Array<[number, number]> {
    const [ax, ay, bx, by] = Array.isArray(r) ? r : [r.x0, r.y0, r.x1, r.y1];
    const x0 = Math.min(ax, bx);
    const x1 = Math.max(ax, bx);
    const y0 = Math.min(ay, by);
    const y1 = Math.max(ay, by);
    const c = chamfer;
    if (c <= 0) return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
    const [sw, se, ne, nw] = corners;
    const pts: Array<[number, number]> = [];
    if (sw) pts.push([x0, y0 + c], [x0 + c, y0]);
    else pts.push([x0, y0]);
    if (se) pts.push([x1 - c, y0], [x1, y0 + c]);
    else pts.push([x1, y0]);
    if (ne) pts.push([x1, y1 - c], [x1 - c, y1]);
    else pts.push([x1, y1]);
    if (nw) pts.push([x0 + c, y1], [x0, y1 - c]);
    else pts.push([x0, y1]);
    return pts;
  }

  private roundedRectPts(r: RectXY, radius: number, seg = 6): Array<[number, number]> {
    const x0 = Math.min(r.x0, r.x1);
    const x1 = Math.max(r.x0, r.x1);
    const y0 = Math.min(r.y0, r.y1);
    const y1 = Math.max(r.y0, r.y1);
    const pts: Array<[number, number]> = [];
    const corners: Array<[number, number, number]> = [
      [x1 - radius, y0 + radius, -Math.PI / 2],
      [x1 - radius, y1 - radius, 0],
      [x0 + radius, y1 - radius, Math.PI / 2],
      [x0 + radius, y0 + radius, Math.PI],
    ];
    for (const [cx, cy, a0] of corners) {
      for (let k = 0; k <= seg; k++) {
        const a = a0 + (k / seg) * (Math.PI / 2);
        pts.push([cx + radius * Math.cos(a), cy + radius * Math.sin(a)]);
      }
    }
    return pts;
  }

  private circlePlan(target: CanvasRenderingContext2D, x: number, y: number, r: number, fill: string, stroke?: string): void {
    this.drawCircleWorld(target, x, -y, r, fill, stroke);
  }

  private linePlan(target: CanvasRenderingContext2D, x0: number, y0: number, x1: number, y1: number, widthM: number, color: string): void {
    target.beginPath();
    target.moveTo(this.worldToX(x0), this.worldToY(-y0));
    target.lineTo(this.worldToX(x1), this.worldToY(-y1));
    target.strokeStyle = color;
    target.lineWidth = Math.max(1.2, (widthM / (this.worldMaxX - this.worldMinX)) * this.canvas.width);
    target.lineCap = 'butt';
    target.stroke();
  }

  /** Nave + transept + apse outlines (plan). */
  private churchPts(): Array<Array<[number, number]>> {
    const n = LAYOUT.nave;
    const tr = LAYOUT.transept;
    const a = LAYOUT.apse;
    const apse: Array<[number, number]> = [
      [-a.sideWallX, tr.extWallY],
      [a.sideWallX, tr.extWallY],
    ];
    for (let k = 0; k <= 24; k++) {
      const ang = (k / 24) * Math.PI;
      apse.push([a.center[0] + a.wallOuterR * Math.cos(ang), a.center[1] + a.wallOuterR * Math.sin(ang)]);
    }
    return [
      this.rectPts([-n.halfWidth - n.wallThickness, n.gloryInnerY, n.halfWidth + n.wallThickness, n.northY]),
      this.rectPts([-tr.halfLength, -tr.extWallY, tr.halfLength, tr.extWallY]),
      apse,
    ];
  }

  private drawChurch(ctx: CanvasRenderingContext2D, fill: string, stroke: string): void {
    for (const p of this.churchPts()) this.fillPlan(ctx, p, fill, stroke);
  }

  private bakeStaticBackground(level: FloorLevel): void {
    const ctx = this.bgCtx;
    const w = this.bgCanvas.width;
    const h = this.bgCanvas.height;
    const L = LAYOUT;
    const gold = '#d9ae67';

    // Blueprint slate background
    ctx.fillStyle = '#12151a';
    ctx.fillRect(0, 0, w, h);

    // Eixample blocks (faint, every level) + the Sagrada Família block
    for (const b of L.city.blocks) {
      this.fillPlan(ctx, this.rectPts(b, b.chamfer, b.chamferCorners), 'rgba(217, 174, 103, 0.04)', 'rgba(217, 174, 103, 0.12)');
    }
    this.fillPlan(ctx, this.rectPts(L.city.sagradaBlock, L.city.sagradaBlock.chamfer), 'rgba(255,255,255,0.02)', 'rgba(217, 174, 103, 0.16)');

    if (level === 'crypt') {
      // Ghost outline of the church above
      for (const p of this.churchPts()) this.fillPlan(ctx, p, 'rgba(255,255,255,0.03)', 'rgba(255,255,255,0.09)');
      // Crypt footprint: semicircle about the apse centre + straight part to the south wall
      const c = L.crypt;
      const foot: Array<[number, number]> = [
        [-c.wallOuterR, c.southWallY - 1.25],
        [c.wallOuterR, c.southWallY - 1.25],
      ];
      for (let k = 0; k <= 32; k++) {
        const ang = (k / 32) * Math.PI;
        foot.push([c.center[0] + c.wallOuterR * Math.cos(ang), c.center[1] + c.wallOuterR * Math.sin(ang)]);
      }
      this.fillPlan(ctx, foot, 'rgba(217, 156, 82, 0.24)', gold);
      this.circlePlan(ctx, c.center[0], c.center[1], c.chapelFrontR, 'rgba(217, 156, 82, 0.10)', 'rgba(217, 174, 103, 0.45)');
      this.circlePlan(ctx, c.center[0], c.center[1], c.pierRingR, 'rgba(217, 156, 82, 0.14)', 'rgba(217, 174, 103, 0.6)');
      // The two spiral stairs and Gaudí's tomb
      for (const s of c.stairs) this.circlePlan(ctx, s.x, s.y, s.rOuter, 'rgba(217, 174, 103, 0.35)', gold);
      this.circlePlan(ctx, c.gaudiTomb[0], c.gaudiTomb[1], 2.2, '#ffb74d', '#fff');
    } else if (level === 'gallery') {
      this.drawChurch(ctx, 'rgba(255,255,255,0.05)', 'rgba(255,255,255,0.16)');
      // Walkable choir galleries (cantories) and the Nativity / Passion tribunes
      for (const g of Object.values(L.galleries)) this.fillPlan(ctx, this.rectPts(g), 'rgba(77, 225, 255, 0.28)', '#4de1ff');
      for (const s of L.cornerStairs) this.circlePlan(ctx, s.x, s.y, s.rOuter, 'rgba(77, 225, 255, 0.45)', '#bdf4ff');
      for (const b of L.walkBridges) {
        if (Math.abs(b.z0 - L.levels.gallery) < 0.01 && Math.abs(b.z1 - L.levels.gallery) < 0.01) {
          this.linePlan(ctx, b.x0, b.y0, b.x1, b.y1, b.halfWidth * 2, 'rgba(77, 225, 255, 0.6)');
        }
      }
    } else if (level === 'towers') {
      this.drawChurch(ctx, 'rgba(255,255,255,0.05)', 'rgba(255,255,255,0.16)');
      // Skybridges and roof stair-bridges (56 m and up)
      for (const b of L.walkBridges) {
        if (Math.min(b.z0, b.z1) >= L.levels.jesusDeck - 0.01) {
          this.linePlan(ctx, b.x0, b.y0, b.x1, b.y1, b.halfWidth * 2, 'rgba(77, 225, 255, 0.55)');
        }
      }
      // All 18 towers at the start of their shells
      const style: Record<string, [string, string]> = {
        jesus: ['rgba(255, 214, 102, 0.42)', '#ffd166'],
        mary: ['rgba(130, 210, 255, 0.36)', '#82d2ff'],
        evangelist: ['rgba(255, 255, 255, 0.24)', '#ffffff'],
        nativity: ['rgba(217, 174, 103, 0.38)', gold],
        passion: ['rgba(200, 200, 210, 0.35)', '#cfd6e0'],
        glory: ['rgba(217, 174, 103, 0.30)', gold],
      };
      for (const tw of L.towers) {
        const [fill, stroke] = style[tw.family];
        this.circlePlan(ctx, tw.x, tw.y, towerRadiusAt(tw, L.towerRules.shellZ0), fill, stroke);
      }
    } else {
      // GROUND LEVEL: plazas, pond, cloister, corner buildings, church, presbytery, porches & stairs
      const pg = L.city.placaGaudi;
      const psf = L.city.placaSagradaFamilia;
      this.fillPlan(ctx, this.rectPts(pg, pg.chamfer), 'rgba(65, 128, 72, 0.22)', 'rgba(95, 168, 102, 0.35)');
      this.fillPlan(ctx, this.rectPts(psf, psf.chamfer), 'rgba(65, 128, 72, 0.20)', 'rgba(95, 168, 102, 0.30)');
      this.fillPlan(ctx, this.roundedRectPts(L.city.pond, L.city.pond.cornerRadius), 'rgba(56, 152, 188, 0.55)', '#58c0e6');
      for (const wk of Object.values(L.cloister.walks)) {
        this.fillPlan(ctx, this.rectPts(wk), 'rgba(217, 174, 103, 0.16)', 'rgba(217, 174, 103, 0.5)');
      }
      for (const b of Object.values(L.cornerBuildings)) {
        this.fillPlan(ctx, this.rectPts(cornerBuildingRect(b)), 'rgba(217, 174, 103, 0.22)', gold);
      }
      this.fillPlan(ctx, this.rectPts(L.assumptionChapel), 'rgba(217, 174, 103, 0.22)', gold);
      // Porches and entrance stairs
      const nat = L.nativity;
      const pas = L.passion;
      const glo = L.glory;
      const porch = 'rgba(217, 174, 103, 0.18)';
      const stair = 'rgba(217, 174, 103, 0.22)';
      const edge = 'rgba(217, 174, 103, 0.55)';
      this.fillPlan(ctx, this.rectPts([nat.wallX, -nat.halfWidth, nat.frontX, nat.halfWidth]), porch, edge);
      this.fillPlan(ctx, this.rectPts([pas.frontX, -pas.halfWidth, pas.wallX, pas.halfWidth]), porch, edge);
      this.fillPlan(ctx, this.rectPts([nat.stair.x0, -nat.stair.halfWidth, nat.stair.x1, nat.stair.halfWidth]), stair, edge);
      this.fillPlan(ctx, this.rectPts([pas.stair.x0, -pas.stair.halfWidth, pas.stair.x1, pas.stair.halfWidth]), stair, edge);
      this.fillPlan(ctx, this.rectPts(glo.porch), porch, edge);
      this.fillPlan(ctx, this.rectPts([-glo.bridge.halfWidth, glo.bridge.y0, glo.bridge.halfWidth, glo.bridge.y1]), 'rgba(217, 174, 103, 0.30)', edge);
      this.fillPlan(ctx, this.rectPts([-glo.stair.halfWidth, glo.stair.y0, glo.stair.halfWidth, glo.stair.y1]), stair, edge);
      // Church, presbytery and the crossing columns
      this.drawChurch(ctx, 'rgba(217, 174, 103, 0.28)', '#e2be7e');
      const pr = L.presbytery;
      const pres: Array<[number, number]> = [
        [-pr.halfWidth, pr.frontY],
        [pr.halfWidth, pr.frontY],
      ];
      for (let k = 0; k <= 16; k++) {
        const ang = (k / 16) * Math.PI;
        pres.push([L.apse.center[0] + pr.radius * Math.cos(ang), L.apse.center[1] + pr.radius * Math.sin(ang)]);
      }
      this.fillPlan(ctx, pres, 'rgba(255, 200, 110, 0.38)', '#ffd166');
      for (const col of L.columns) {
        if (col.group === 'crossing') this.circlePlan(ctx, col.x, col.y, 1.5, '#d9534f');
      }
    }

    // Cardinal labels (localized: N/S/O/W in German, N/S/E/W in English)
    ctx.fillStyle = 'rgba(240, 232, 218, 0.55)';
    ctx.font = '600 9px system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(t('minimap.north'), w * 0.5, 11);
    ctx.fillText(t('minimap.south'), w * 0.5, h - 5);
    ctx.textAlign = 'right';
    ctx.fillText(t('minimap.east'), w - 5, h * 0.45);
    ctx.textAlign = 'left';
    ctx.fillText(t('minimap.west'), 5, h * 0.45);

    this.cachedLevel = level;
  }

  public render(playerPos: THREE.Vector3, playerYaw: number): void {
    if (this.cachedLevel !== this.activeLevel) {
      this.bakeStaticBackground(this.activeLevel);
    }

    if (
      this.lastDrawLevel === this.activeLevel &&
      Math.hypot(playerPos.x - this.lastDrawX, playerPos.z - this.lastDrawZ) < 0.15 &&
      Math.abs(playerYaw - this.lastDrawYaw) < 0.015
    ) {
      return;
    }

    this.lastDrawLevel = this.activeLevel;
    this.lastDrawX = playerPos.x;
    this.lastDrawZ = playerPos.z;
    this.lastDrawYaw = playerYaw;

    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;
    ctx.drawImage(this.bgCanvas, 0, 0);

    // Live Player Marker + View Direction Cone
    const px = THREE.MathUtils.clamp(this.worldToX(playerPos.x), 6, w - 6);
    const py = THREE.MathUtils.clamp(this.worldToY(playerPos.z), 6, h - 6);
    const dirX = -Math.sin(playerYaw);
    const dirY = -Math.cos(playerYaw);
    const angle = Math.atan2(dirY, dirX);

    // View cone
    ctx.beginPath();
    ctx.moveTo(px, py);
    ctx.arc(px, py, 20, angle - 0.48, angle + 0.48);
    ctx.closePath();
    ctx.fillStyle = 'rgba(255, 209, 102, 0.28)';
    ctx.fill();

    // Player dot
    ctx.beginPath();
    ctx.arc(px, py, 4.2, 0, Math.PI * 2);
    ctx.fillStyle = '#ffd166';
    ctx.fill();
    ctx.strokeStyle = '#111';
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }
}
