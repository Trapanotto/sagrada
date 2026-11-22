import * as THREE from 'three';
import { FloorLevel } from '../data/teleports';

export class Minimap {
  private ctx: CanvasRenderingContext2D;
  public activeLevel: FloorLevel = 'ground';

  // World extent displayed on the 230x230 canvas: X in [-120..+120], Z in [-85..+115]
  private readonly worldMinX = -118;
  private readonly worldMaxX = 118;
  private readonly worldMinZ = -75;
  private readonly worldMaxZ = 105;

  public onTeleportClick?: (worldX: number, worldZ: number, level: FloorLevel) => void;

  constructor(
    private canvas: HTMLCanvasElement,
    levelContainer: HTMLElement
  ) {
    this.ctx = canvas.getContext('2d')!;

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

  private drawRectWorld(x0: number, z0: number, x1: number, z1: number, fill: string, stroke?: string): void {
    const cx0 = this.worldToX(x0);
    const cy0 = this.worldToY(z0);
    const cw = this.worldToX(x1) - cx0;
    const ch = this.worldToY(z1) - cy0;
    this.ctx.fillStyle = fill;
    this.ctx.fillRect(cx0, cy0, cw, ch);
    if (stroke) {
      this.ctx.strokeStyle = stroke;
      this.ctx.lineWidth = 1;
      this.ctx.strokeRect(cx0, cy0, cw, ch);
    }
  }

  private drawCircleWorld(wx: number, wz: number, radiusM: number, fill: string, stroke?: string): void {
    const cx = this.worldToX(wx);
    const cy = this.worldToY(wz);
    const r = (radiusM / (this.worldMaxX - this.worldMinX)) * this.canvas.width;
    this.ctx.beginPath();
    this.ctx.arc(cx, cy, Math.max(1.8, r), 0, Math.PI * 2);
    this.ctx.fillStyle = fill;
    this.ctx.fill();
    if (stroke) {
      this.ctx.strokeStyle = stroke;
      this.ctx.lineWidth = 1;
      this.ctx.stroke();
    }
  }

  public render(playerPos: THREE.Vector3, playerYaw: number): void {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;

    // Blueprint slate background
    ctx.fillStyle = '#12151a';
    ctx.fillRect(0, 0, w, h);

    // Subtle Eixample grid
    ctx.strokeStyle = 'rgba(217, 174, 103, 0.08)';
    ctx.lineWidth = 1;
    for (let gx = -105; gx <= 105; gx += 15) {
      const px = this.worldToX(gx);
      ctx.beginPath();
      ctx.moveTo(px, 0);
      ctx.lineTo(px, h);
      ctx.stroke();
    }
    for (let gz = -60; gz <= 90; gz += 15) {
      const py = this.worldToY(gz);
      ctx.beginPath();
      ctx.moveTo(0, py);
      ctx.lineTo(w, py);
      ctx.stroke();
    }

    if (this.activeLevel === 'crypt') {
      // Ghost outline of nave above
      this.drawRectWorld(-22.5, -15, 22.5, 45, 'rgba(255,255,255,0.03)', 'rgba(255,255,255,0.09)');
      // Highlighted subterranean Neo-Gothic Crypt circle (center 0, Z=-21, r=15.5)
      this.drawCircleWorld(0, -21, 15.5, 'rgba(217, 156, 82, 0.24)', '#d9ae67');
      this.drawCircleWorld(0, -21, 7.8, 'rgba(217, 156, 82, 0.14)', 'rgba(217, 174, 103, 0.6)');
      // Gaudí's Tomb marker
      this.drawCircleWorld(-9.8, -23.5, 2.2, '#ffb74d', '#fff');
      // Descending staircase corridor
      this.drawRectWorld(-21.5, -17.5, -10.5, -11.5, 'rgba(217, 174, 103, 0.3)', '#d9ae67');
    } else if (this.activeLevel === 'gallery') {
      // Base church footprint faint
      this.drawRectWorld(-22.5, -15, 22.5, 45, 'rgba(255,255,255,0.05)', 'rgba(255,255,255,0.16)');
      this.drawRectWorld(-30, -15, 30, 15, 'rgba(255,255,255,0.05)', 'rgba(255,255,255,0.16)');
      // Walkable Cantories (East, West, South Choir, Apse Organ)
      this.drawRectWorld(16.8, 14.5, 22.4, 45.2, 'rgba(77, 225, 255, 0.28)', '#4de1ff');
      this.drawRectWorld(-22.4, 14.5, -16.8, 45.2, 'rgba(77, 225, 255, 0.28)', '#4de1ff');
      this.drawRectWorld(-22.0, 40.5, 22.0, 45.2, 'rgba(77, 225, 255, 0.28)', '#4de1ff');
      this.drawCircleWorld(0, -16.5, 14.5, 'rgba(77, 225, 255, 0.14)', '#4de1ff');
    } else if (this.activeLevel === 'towers') {
      // Church outline
      this.drawRectWorld(-22.5, -15, 22.5, 45, 'rgba(255,255,255,0.05)', 'rgba(255,255,255,0.16)');
      this.drawRectWorld(-30, -15, 30, 15, 'rgba(255,255,255,0.05)', 'rgba(255,255,255,0.16)');
      // All 18 Towers!
      // 1. Jesus Tower (172.5m)
      this.drawCircleWorld(0, 0, 9.5, 'rgba(255, 214, 102, 0.42)', '#ffd166');
      // 2. Mary Tower (138m)
      this.drawCircleWorld(0, -22.5, 7.6, 'rgba(130, 210, 255, 0.36)', '#82d2ff');
      // 3. 4 Evangelist Towers (135m)
      for (const sx of [-11.5, 11.5]) {
        for (const sz of [-11.5, 11.5]) {
          this.drawCircleWorld(sx, sz, 4.8, 'rgba(255, 255, 255, 0.24)', '#ffffff');
        }
      }
      // 4. 12 Apostle Towers (Nativity East, Passion West, Glory South)
      for (const z of [-10.8, -3.6, 3.6, 10.8]) {
        this.drawCircleWorld(31.5, z, 3.4, 'rgba(217, 174, 103, 0.38)', '#d9ae67');
        this.drawCircleWorld(-31.5, z, 3.4, 'rgba(200, 200, 210, 0.35)', '#cfd6e0');
      }
      for (const x of [-11.4, -3.8, 3.8, 11.4]) {
        this.drawCircleWorld(x, 49.5, 3.6, 'rgba(217, 174, 103, 0.38)', '#d9ae67');
      }
      // Skybridges at 65m
      this.drawRectWorld(29.8, -4.1, 33.2, 4.1, 'rgba(77, 225, 255, 0.5)', '#4de1ff');
      this.drawRectWorld(-33.2, -4.1, -29.8, 4.1, 'rgba(77, 225, 255, 0.5)', '#4de1ff');
    } else {
      // GROUND LEVEL (EG): Eixample parks, pond, cloister, sacristies, 5-aisle nave, transept, apse, grand staircase
      // Plaça de Gaudí (East) & Pond
      this.drawRectWorld(60, -45, 118, 45, 'rgba(65, 128, 72, 0.22)', 'rgba(95, 168, 102, 0.35)');
      this.drawRectWorld(68, -17, 97, 17, 'rgba(56, 152, 188, 0.55)', '#58c0e6');
      // Plaça de la Sagrada Família (West)
      this.drawRectWorld(-118, -45, -60, 45, 'rgba(65, 128, 72, 0.20)', 'rgba(95, 168, 102, 0.30)');
      // Cloister wings & 2 Sacristies
      this.drawRectWorld(23.5, 15, 29, 46, 'rgba(217, 174, 103, 0.16)', 'rgba(217, 174, 103, 0.5)');
      this.drawRectWorld(-29, 15, -23.5, 46, 'rgba(217, 174, 103, 0.16)', 'rgba(217, 174, 103, 0.5)');
      this.drawCircleWorld(27.5, -32.5, 8.2, 'rgba(217, 174, 103, 0.22)', '#d9ae67');
      this.drawCircleWorld(-27.5, -32.5, 8.2, 'rgba(217, 174, 103, 0.22)', '#d9ae67');
      // Main 5-aisle Nave + Transept + Apse
      this.drawRectWorld(-22.5, -15, 22.5, 46, 'rgba(217, 174, 103, 0.28)', '#e2be7e');
      this.drawRectWorld(-31.5, -15, 31.5, 15, 'rgba(217, 174, 103, 0.28)', '#e2be7e');
      this.drawCircleWorld(0, -16.5, 18.8, 'rgba(217, 174, 103, 0.26)', '#e2be7e');
      // High Altar
      this.drawCircleWorld(0, -17.5, 6.0, 'rgba(255, 200, 110, 0.38)', '#ffd166');
      // Glory Grand Staircase South
      this.drawRectWorld(-19, 49, 19, 71, 'rgba(217, 174, 103, 0.22)', 'rgba(217, 174, 103, 0.55)');
      // 4 Porphyry Crossing columns
      for (const sx of [-7.5, 7.5]) {
        for (const sz of [-7.5, 7.5]) {
          this.drawCircleWorld(sx, sz, 1.5, '#d9534f');
        }
      }
    }

    // Cardinal labels (N, S, O, W)
    ctx.fillStyle = 'rgba(240, 232, 218, 0.55)';
    ctx.font = '600 9px system-ui, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('N · Apsis', w * 0.5, 11);
    ctx.fillText('S · Glorien', w * 0.5, h - 5);
    ctx.textAlign = 'right';
    ctx.fillText('O · Geburt', w - 5, h * 0.45);
    ctx.textAlign = 'left';
    ctx.fillText('W · Passion', 5, h * 0.45);

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
