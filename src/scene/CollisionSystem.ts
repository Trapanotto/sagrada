import * as THREE from 'three';

export interface WalkConstraints {
  groundY: number;
  clampedX: number;
  clampedZ: number;
}

const EYE_HEIGHT = 1.75;
const STEP_UP_MAX = 1.45; // Max vertical step-up allowed onto stairs/ramps/platforms

interface BoxObstacle {
  minX: number;
  maxX: number;
  minZ: number;
  maxZ: number;
  maxY: number;
}

const EXTERIOR_OBSTACLES: BoxObstacle[] = [
  // Eixample apartment blocks (rooftops at Y=25m are landable if you jump onto them!)
  { minX: -131, maxX: -59, minZ: -144, maxZ: -72, maxY: 25 },
  { minX: -36, maxX: 36, minZ: -144, maxZ: -72, maxY: 25 },
  { minX: 59, maxX: 131, minZ: -144, maxZ: -72, maxY: 25 },
  { minX: -131, maxX: -59, minZ: 82, maxZ: 154, maxY: 25 },
  { minX: -36, maxX: 36, minZ: 88, maxZ: 160, maxY: 25 },
  { minX: 59, maxX: 131, minZ: 82, maxZ: 154, maxY: 25 },
  { minX: 142, maxX: 214, minZ: -144, maxZ: 144, maxY: 25 },
  { minX: -214, maxX: -142, minZ: -144, maxZ: 144, maxY: 25 },
];

interface WalkBridge {
  x0: number;
  y0: number;
  z0: number;
  x1: number;
  y1: number;
  z1: number;
  halfWidth: number;
}

/**
 * Complete 3D walkable pedestrian bridges, connecting galleries & stepped roof stairways
 * matching blender/build_interior.py and blender/build_towers.py (Three.js Z = -Blender Y).
 */
const WALK_BRIDGES: WalkBridge[] = [
  // Emporen (14.5m) -> All 12 Apostle Tower Base Galleries
  { x0: 21.0, y0: 14.5, z0: 14.5, x1: 31.5, y1: 14.5, z1: 4.5, halfWidth: 2.1 },
  { x0: 31.5, y0: 14.5, z0: -11.4, x1: 31.5, y1: 14.5, z1: 11.4, halfWidth: 2.0 },
  { x0: -21.0, y0: 14.5, z0: 14.5, x1: -31.5, y1: 14.5, z1: 3.6, halfWidth: 2.1 },
  { x0: -31.5, y0: 14.5, z0: -11.4, x1: -31.5, y1: 14.5, z1: 11.4, halfWidth: 2.0 },
  { x0: -3.8, y0: 14.5, z0: 43.0, x1: -3.8, y1: 14.5, z1: 49.8, halfWidth: 1.9 },
  { x0: 3.8, y0: 14.5, z0: 43.0, x1: 3.8, y1: 14.5, z1: 49.8, halfWidth: 1.9 },
  { x0: -12.0, y0: 14.5, z0: 49.5, x1: 12.0, y1: 14.5, z1: 49.5, halfWidth: 2.0 },

  // Upper Apostle Tower Skybridges (65m East/West & 72m South Glory)
  { x0: 31.5, y0: 65.0, z0: -11.5, x1: 31.5, y1: 65.0, z1: 11.5, halfWidth: 2.0 },
  { x0: -31.5, y0: 65.0, z0: -11.5, x1: -31.5, y1: 65.0, z1: 11.5, halfWidth: 2.0 },
  { x0: -12.0, y0: 72.0, z0: 49.5, x1: 12.0, y1: 72.0, z1: 49.5, halfWidth: 2.0 },

  // Jesus Crossing Gallery (56m) -> All 4 Evangelist Towers & Virgin Mary Tower (56m)
  { x0: 4.5, y0: 56.0, z0: 4.5, x1: 11.8, y1: 56.0, z1: 11.8, halfWidth: 1.7 },
  { x0: -4.5, y0: 56.0, z0: 4.5, x1: -11.8, y1: 56.0, z1: 11.8, halfWidth: 1.7 },
  { x0: 4.5, y0: 56.0, z0: -4.5, x1: 11.8, y1: 56.0, z1: -11.8, halfWidth: 1.7 },
  { x0: -4.5, y0: 56.0, z0: -4.5, x1: -11.8, y1: 56.0, z1: -11.8, halfWidth: 1.7 },
  { x0: 0.0, y0: 56.0, z0: -6.0, x1: 0.0, y1: 56.0, z1: -22.8, halfWidth: 1.85 },

  // Stepped Roof Stair-Bridges connecting Jesus Crossing (56m) <-> East/West (65m) & South Glory (72m)!
  { x0: 6.6, y0: 56.0, z0: 0.0, x1: 30.4, y1: 65.0, z1: 0.0, halfWidth: 1.85 },
  { x0: -6.6, y0: 56.0, z0: 0.0, x1: -30.4, y1: 65.0, z1: 0.0, halfWidth: 1.85 },
  { x0: 0.0, y0: 56.0, z0: 6.6, x1: 0.0, y1: 72.0, z1: 48.5, halfWidth: 1.95 },

  // Nave (1.2m) <-> Subterranean Crypt (-5.5m) Descending Staircase
  { x0: -21.5, y0: 1.2, z0: -16.5, x1: -10.5, y1: -5.5, z1: -12.0, halfWidth: 2.2 },
];

export interface TowerStairShaft {
  name: string;
  cx: number;
  cz: number;
  zStart: number;
  zEnd: number;
  rInner: number;
  rOuter: number;
  turnsPer10m: number;
  clockwise: boolean;
}

/**
 * All 18 walkable internal helical stone staircases matching blender/build_towers.py.
 */
export const TOWER_STAIR_SHAFTS: TowerStairShaft[] = [
  // 1. Tower of Jesus Christ (56m -> 136m spiraling around glass panorama elevator!)
  { name: 'Wendeltreppe · Turm Jesu Christi', cx: 0.0, cz: 0.0, zStart: 56.0, zEnd: 136.0, rInner: 2.25, rOuter: 4.95, turnsPer10m: 1.1, clockwise: true },
  // 2. Tower of Virgin Mary (52m -> 118m over Apse)
  { name: 'Wendeltreppe · Marien-Turm', cx: 0.0, cz: -22.5, zStart: 52.0, zEnd: 118.0, rInner: 1.75, rOuter: 4.0, turnsPer10m: 1.25, clockwise: true },
  // 3. Four Towers of the Evangelists (52m -> 114m)
  { name: 'Wendeltreppe · Evangelist Markus', cx: -11.5, cz: 11.5, zStart: 52.0, zEnd: 114.0, rInner: 1.05, rOuter: 3.1, turnsPer10m: 1.35, clockwise: true },
  { name: 'Wendeltreppe · Evangelist Lukas', cx: -11.5, cz: -11.5, zStart: 52.0, zEnd: 114.0, rInner: 1.05, rOuter: 3.1, turnsPer10m: 1.35, clockwise: false },
  { name: 'Wendeltreppe · Evangelist Matthäus', cx: 11.5, cz: 11.5, zStart: 52.0, zEnd: 114.0, rInner: 1.05, rOuter: 3.1, turnsPer10m: 1.35, clockwise: false },
  { name: 'Wendeltreppe · Evangelist Johannes', cx: 11.5, cz: -11.5, zStart: 52.0, zEnd: 114.0, rInner: 1.05, rOuter: 3.1, turnsPer10m: 1.35, clockwise: true },
  // 4. Four Nativity Towers (East, 14.5m -> 65m)
  { name: 'Wendeltreppe · Geburtsturm SO', cx: 31.5, cz: 10.8, zStart: 14.5, zEnd: 65.0, rInner: 1.05, rOuter: 3.0, turnsPer10m: 1.68, clockwise: false },
  { name: 'Wendeltreppe · Geburtsturm Mitte-Süd', cx: 31.5, cz: 3.6, zStart: 14.5, zEnd: 65.0, rInner: 1.05, rOuter: 3.0, turnsPer10m: 1.68, clockwise: true },
  { name: 'Wendeltreppe · Geburtsturm Mitte-Nord', cx: 31.5, cz: -3.6, zStart: 14.5, zEnd: 65.0, rInner: 1.05, rOuter: 3.0, turnsPer10m: 1.68, clockwise: false },
  { name: 'Wendeltreppe · Geburtsturm NO', cx: 31.5, cz: -10.8, zStart: 14.5, zEnd: 65.0, rInner: 1.05, rOuter: 3.0, turnsPer10m: 1.68, clockwise: true },
  // 5. Four Passion Towers (West, 14.5m -> 65m)
  { name: 'Wendeltreppe · Passionsturm SW', cx: -31.5, cz: 10.8, zStart: 14.5, zEnd: 65.0, rInner: 1.05, rOuter: 3.0, turnsPer10m: 1.68, clockwise: true },
  { name: 'Wendeltreppe · Passionsturm Mitte-Süd', cx: -31.5, cz: 3.6, zStart: 14.5, zEnd: 65.0, rInner: 1.05, rOuter: 3.0, turnsPer10m: 1.68, clockwise: false },
  { name: 'Wendeltreppe · Passionsturm Mitte-Nord', cx: -31.5, cz: -3.6, zStart: 14.5, zEnd: 65.0, rInner: 1.05, rOuter: 3.0, turnsPer10m: 1.68, clockwise: true },
  { name: 'Wendeltreppe · Passionsturm NW', cx: -31.5, cz: -10.8, zStart: 14.5, zEnd: 65.0, rInner: 1.05, rOuter: 3.0, turnsPer10m: 1.68, clockwise: false },
  // 6. Four Glory Towers (South, 14.5m -> 72m)
  { name: 'Wendeltreppe · Glorienturm West', cx: -11.4, cz: 49.5, zStart: 14.5, zEnd: 72.0, rInner: 1.1, rOuter: 3.1, turnsPer10m: 1.62, clockwise: false },
  { name: 'Wendeltreppe · Glorienturm Mitte-West', cx: -3.8, cz: 49.5, zStart: 14.5, zEnd: 72.0, rInner: 1.1, rOuter: 3.1, turnsPer10m: 1.62, clockwise: true },
  { name: 'Wendeltreppe · Glorienturm Mitte-Ost', cx: 3.8, cz: 49.5, zStart: 14.5, zEnd: 72.0, rInner: 1.1, rOuter: 3.1, turnsPer10m: 1.62, clockwise: false },
  { name: 'Wendeltreppe · Glorienturm Ost', cx: 11.4, cz: 49.5, zStart: 14.5, zEnd: 72.0, rInner: 1.1, rOuter: 3.1, turnsPer10m: 1.62, clockwise: true },
];

function distToSegment2D(px: number, pz: number, x0: number, z0: number, x1: number, z1: number): { dist: number; t: number } {
  const dx = x1 - x0;
  const dz = z1 - z0;
  const lenSq = dx * dx + dz * dz;
  if (lenSq < 1e-6) return { dist: Math.hypot(px - x0, pz - z0), t: 0 };
  const t = THREE.MathUtils.clamp(((px - x0) * dx + (pz - z0) * dz) / lenSq, 0, 1);
  const cx = x0 + t * dx;
  const cz = z0 + t * dz;
  return { dist: Math.hypot(px - cx, pz - cz), t };
}

export class CollisionSystem {
  public readonly eyeHeight = EYE_HEIGHT;
  public elevatorFloorY = 1.2;

  /**
   * True Multi-Level Support-Surface Resolver:
   * - Finds the HIGHEST walkable floor/bridge/stair/deck/roof at (x, z) below (feetY + STEP_UP_MAX).
   * - ZERO invisible horizontal trapping walls on elevated decks, Emporen, bridges, roofs, or viewpoints:
   *   walk or jump off ANY elevated ledge and gravity cleanly carries you down to the floor below!
   */
  public resolveWalkPosition(x: number, feetY: number, z: number): WalkConstraints {
    let cx = THREE.MathUtils.clamp(x, -165, 165);
    let cz = THREE.MathUtils.clamp(z, -105, 118);
    const maxStepY = feetY + STEP_UP_MAX;

    // Only collide horizontally with Eixample apartment blocks when below their 25m rooftop!
    if (feetY < 24.0) {
      for (const obs of EXTERIOR_OBSTACLES) {
        if (cx > obs.minX && cx < obs.maxX && cz > obs.minZ && cz < obs.maxZ) {
          const dL = Math.abs(cx - obs.minX);
          const dR = Math.abs(obs.maxX - cx);
          const dT = Math.abs(cz - obs.minZ);
          const dB = Math.abs(obs.maxZ - cz);
          const m = Math.min(dL, dR, dT, dB);
          if (m === dL) cx = obs.minX;
          else if (m === dR) cx = obs.maxX;
          else if (m === dT) cz = obs.minZ;
          else cz = obs.maxZ;
        }
      }
    }

    // Start with the base ground surface (Crypt, Pond, Street, Nave, High Altar, or Eixample Rooftop)
    let bestY = this.getBaseGroundY(cx, feetY, cz);

    const consider = (surfaceY: number) => {
      if (surfaceY <= maxStepY && surfaceY > bestY) {
        bestY = surfaceY;
      }
    };

    const rCenter = Math.hypot(cx, cz);

    // 1. Central Glass Panorama Elevator Cabin Floor (0, elevatorFloorY, 0)
    if (rCenter < 2.02 && Math.abs(feetY - this.elevatorFloorY) < 2.6) {
      consider(this.elevatorFloorY);
    }

    // 2. Top Panoramic Observation Decks (NO horizontal trapping — jump right over the railing!)
    // Jesus Christ Tower Viewpoint Deck (136.0m, r <= 6.5m)
    if (rCenter <= 6.5) {
      consider(136.0);
    }
    // Virgin Mary Tower Viewpoint Deck (118.0m, r <= 4.7m)
    if (Math.hypot(cx, cz - -22.5) <= 4.7) {
      consider(118.0);
    }
    // 4 Evangelist Tower Observation Decks (114.0m, r <= 3.7m)
    for (const sx of [-1, 1]) {
      for (const sz of [-1, 1]) {
        if (Math.hypot(cx - sx * 11.5, cz - sz * 11.5) <= 3.7) {
          consider(114.0);
        }
      }
    }

    // 3. Crossing Vault Gallery Ring Deck at Y = 56.0m (connects Glass Elevator <-> Roof Skybridges & Jesus Spiral)
    if (rCenter >= 1.9 && rCenter <= 7.8) {
      consider(56.0);
    }

    // 4. All Walkable Bridges, Connecting Galleries, Skybridges, Roof Stair-Bridges & Crypt Staircase
    for (const b of WALK_BRIDGES) {
      const { dist, t } = distToSegment2D(cx, cz, b.x0, b.z0, b.x1, b.z1);
      if (dist <= b.halfWidth) {
        const y = THREE.MathUtils.lerp(b.y0, b.y1, t);
        // Special handling for descending Crypt staircase so you can step smoothly DOWN below nave floor!
        if (b.y1 < 0 && feetY < 2.8 && Math.abs(feetY - y) < 2.6) {
          return { groundY: y, clampedX: cx, clampedZ: cz };
        }
        consider(y);
      }
    }

    // 5. All 18 Internal Tower Helical Spiral Staircases (can climb smoothly OR leap off inner eye / bridges!)
    for (const shaft of TOWER_STAIR_SHAFTS) {
      if (feetY < shaft.zStart - 1.6 || feetY > shaft.zEnd + 1.8) continue;
      const dist = Math.hypot(cx - shaft.cx, cz - shaft.cz);
      if (dist >= shaft.rInner - 0.15 && dist <= shaft.rOuter + 0.15) {
        const dx = cx - shaft.cx;
        const dz = cz - shaft.cz;
        const ang = Math.atan2(-dz, dx); // Blender +Y = Three -Z
        const signedAng = shaft.clockwise ? ang : -ang;
        const baseAngle = ((signedAng % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2);
        const fracTurn = baseAngle / (Math.PI * 2);
        const pitchPerTurn = 10.0 / shaft.turnsPer10m;
        const estTurn = Math.round((feetY - shaft.zStart) / pitchPerTurn - fracTurn);
        const spiralY = THREE.MathUtils.clamp(
          shaft.zStart + (estTurn + fracTurn) * pitchPerTurn,
          shaft.zStart,
          shaft.zEnd
        );
        // Only engage the helical step if close to player's current elevation (allows falling cleanly past it!)
        if (Math.abs(feetY - spiralY) < 2.2) {
          consider(spiralY);
        }
      }
    }

    // 6. Basilica Upper Roof Decks (landable if jumping down from 56–136m towers! Jump off to street anytime!)
    // Central Nave Roof (Y = 45.0m) & Side Aisle Roofs (Y = 30.0m)
    if (Math.abs(cx) <= 10.5 && cz >= -16.0 && cz <= 45.5) {
      consider(45.0);
    } else if (Math.abs(cx) <= 22.5 && cz >= -16.0 && cz <= 45.5) {
      consider(30.0);
    }
    // Transept Roofs (Y = 45.0m)
    if (Math.abs(cx) <= 30.0 && Math.abs(cz) <= 11.0) {
      consider(45.0);
    }

    // 7. 2 Walkable Gaudí Corner Helical Staircases: Nave Floor (1.2m) <-> Emporen Galleries (14.5m) at (±19.6, Z=+42.8)!
    for (const sx of [-1, 1]) {
      const scx = sx * 19.6;
      const scz = 42.8;
      const dCorner = Math.hypot(cx - scx, cz - scz);
      if (dCorner >= 0.45 && dCorner <= 2.35 && feetY >= 0.5 && feetY <= 16.0) {
        const ang = Math.atan2(-(cz - scz), cx - scx);
        const signedAng = sx > 0 ? ang : -ang;
        const baseFrac = (((signedAng % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2)) / (Math.PI * 2);
        const pitch = (14.5 - 1.2) / 2.5;
        const estTurn = Math.round((feetY - 1.2) / pitch - baseFrac);
        const stairY = THREE.MathUtils.clamp(1.2 + (estTurn + baseFrac) * pitch, 1.2, 14.5);
        if (Math.abs(feetY - stairY) < 2.2) {
          consider(stairY);
        }
      }
    }

    // 8. Elevated Choir Galleries / Emporen (Y = 14.5m — open inner balustrades: jump straight down into the Nave!)
    const onSouthEmpore = cz >= 40.6 && cz <= 45.4 && Math.abs(cx) <= 22.4;
    const onEastEmpore = cx >= 16.8 && cx <= 22.4 && cz >= 13.8 && cz <= 45.4;
    const onWestEmpore = cx <= -16.8 && cx >= -22.4 && cz >= 13.8 && cz <= 45.4;
    if (onSouthEmpore || onEastEmpore || onWestEmpore) {
      consider(14.5);
    }

    // 9. Eixample Apartment Rooftops (Y = 25.0m — landable if leaping off the 65–136m towers!)
    for (const obs of EXTERIOR_OBSTACLES) {
      if (cx >= obs.minX && cx <= obs.maxX && cz >= obs.minZ && cz <= obs.maxZ) {
        consider(obs.maxY);
      }
    }

    return { groundY: bestY, clampedX: cx, clampedZ: cz };
  }

  private getBaseGroundY(cx: number, feetY: number, cz: number): number {
    // Subterranean Crypt (-5.5m) when already underground
    const distCrypt = Math.hypot(cx, cz - -21.0);
    if (feetY < -1.5 && distCrypt <= 15.2) {
      return -5.5;
    }

    // Plaça de Gaudí Reflective Pond (jump right over the +0.36m rim into the -0.45m water basin!)
    const inPondOuter = cx >= 67.4 && cx <= 97.6 && cz >= -17.6 && cz <= 17.6;
    const inPondWater = cx >= 68.4 && cx <= 96.6 && cz >= -16.6 && cz <= 16.6;
    if (inPondWater) {
      const distFountain = Math.hypot(cx - 82.5, cz);
      return distFountain < 2.65 ? 0.35 : -0.45;
    }
    if (inPondOuter) {
      return 0.36;
    }

    // Presbytery High Altar stepped platform (center X=0, Z=-17.5)
    const dAltar = Math.hypot(cx, cz - -17.5);
    if (dAltar < 8.8) {
      return 2.4;
    }
    if (dAltar < 10.8) {
      const t = 1.0 - (dAltar - 8.8) / 2.0;
      return 1.2 + t * 1.2;
    }
    if (this.isOnBasilicaPodium(cx, cz)) {
      return 1.2;
    }
    // Exterior entrance steps / ramps
    if (cx > 31.8 && cx <= 37.0 && Math.abs(cz) <= 14.5) {
      return (1.0 - THREE.MathUtils.clamp((cx - 32.5) / 4.2, 0, 1)) * 1.2;
    }
    if (cx < -31.8 && cx >= -40.5 && Math.abs(cz) <= 15.0) {
      return (1.0 - THREE.MathUtils.clamp((-cx - 35.0) / 5.0, 0, 1)) * 1.2;
    }
    if (cz > 57.5 && cz <= 71.0 && Math.abs(cx) <= 19.0) {
      return (1.0 - THREE.MathUtils.clamp((cz - 58.0) / 12.5, 0, 1)) * 1.2;
    }
    return 0.0;
  }

  private isOnBasilicaPodium(x: number, z: number): boolean {
    if (Math.abs(x) <= 29.0 && z >= -16.0 && z <= 58.0) return true;
    if (x >= -35.5 && x <= 33.0 && Math.abs(z) <= 15.5) return true;
    if (Math.hypot(x, z - -16.5) <= 19.5 && z <= -15.0) return true;
    if (Math.hypot(Math.abs(x) - 27.5, z - -32.5) <= 8.5) return true;
    if (Math.abs(x) >= 23.0 && Math.abs(x) <= 29.5 && z >= -26.5 && z <= -15.0) return true;
    return false;
  }

  public getIndoorFactor(pos: THREE.Vector3): number {
    if (pos.y < -1.0) return 1.0;
    if (Math.hypot(pos.x, pos.z) < 8.5 && pos.y >= 1.0 && pos.y < 134.0) return 0.92;
    if (pos.y > 44.0) return 0.0;
    const inNave = Math.abs(pos.x) < 22.8 && pos.z > -15.0 && pos.z < 47.0;
    const inTransept = Math.abs(pos.x) < 31.0 && Math.abs(pos.z) < 15.0;
    const inApse = Math.hypot(pos.x, pos.z - -16.5) < 18.8 && pos.z <= -14.0;
    if (inNave || inTransept || inApse) return 1.0;
    if (Math.abs(pos.x) < 29.5 && pos.z > -38.0 && pos.z < 47.0 && pos.y < 12.0) return 0.65;
    return 0.0;
  }

  public detectZone(pos: THREE.Vector3): string {
    const rCenter = Math.hypot(pos.x, pos.z);
    if (rCenter < 2.25 && pos.y >= 1.5 && pos.y < 138.0 && Math.abs(pos.y - 1.75 - this.elevatorFloorY) < 2.5) {
      return `Panorama-Aufzug · Turm Jesu Christi (${pos.y.toFixed(0)} m)`;
    }
    if (pos.y > 132 && rCenter < 10) return 'Turm Jesu Christi · Aussicht 136 m';
    if (pos.y > 115 && Math.hypot(pos.x, pos.z - -22.5) < 7) return 'Marien-Turm · Aussicht 118 m';
    if (pos.y > 111 && Math.abs(Math.abs(pos.x) - 11.5) < 5 && Math.abs(Math.abs(pos.z) - 11.5) < 5) {
      return 'Evangelisten-Turm · Aussicht 114 m';
    }
    if (pos.y >= 54 && pos.y <= 61 && rCenter < 8.5) return 'Vierungs-Gewölbegalerie · 56 m';

    for (const shaft of TOWER_STAIR_SHAFTS) {
      if (Math.hypot(pos.x - shaft.cx, pos.z - shaft.cz) < shaft.rOuter + 0.6 && pos.y >= shaft.zStart - 0.5 && pos.y < shaft.zEnd - 0.5) {
        return `${shaft.name} (${pos.y.toFixed(0)} m)`;
      }
    }

    if (pos.y > 54 && pos.y < 76) {
      if (Math.abs(pos.x - 31.5) < 5 && Math.abs(pos.z) < 13) return 'Turm-Brücke Ost · Geburtsfassade (65 m)';
      if (Math.abs(pos.x - -31.5) < 5 && Math.abs(pos.z) < 13) return 'Turm-Brücke West · Passionsfassade (65 m)';
      if (Math.abs(pos.z - 49.5) < 5 && Math.abs(pos.x) < 14) return 'Turm-Brücke Süd · Glorienfassade (72 m)';
      if (Math.abs(pos.z) < 4 || Math.abs(pos.x) < 4) return `Dach-Treppenbrücke (${pos.y.toFixed(0)} m)`;
    }
    if (pos.y >= 44 && pos.y <= 53 && Math.abs(pos.x) < 32 && pos.z > -26 && pos.z < 50) {
      return 'Kathedral-Dachlandschaft (45 m)';
    }
    if (pos.y > 55) return 'Luftraum · Über den 18 Türmen';
    if (pos.y < -1.5) return 'Krypta · Grab von Antoni Gaudí (-5,5 m)';
    if (pos.y > 11 && pos.y < 24 && Math.abs(pos.x) < 34 && pos.z > -32 && pos.z < 52) {
      return 'Empore & Turm-Galerie · 14,5 m Höhe';
    }
    if (Math.hypot(pos.x, pos.z - -17.5) < 12.5 && pos.y < 14) return 'Hochaltar & Apsis';
    if (Math.abs(pos.x) < 11 && Math.abs(pos.z) < 11 && pos.y < 55) return 'Vierung · Unter dem Jesus-Turm';
    if (Math.abs(pos.x) < 22.5 && pos.z >= 10 && pos.z < 46.5 && pos.y < 46) return 'Hauptschiff · Säulenwald';
    if (Math.abs(pos.x) < 31 && Math.abs(pos.z) < 15 && pos.y < 46) return 'Querschiff';
    if (Math.hypot(Math.abs(pos.x) - 27.5, pos.z - -32.5) < 9.5) return 'Sakristei-Kuppel';
    if (Math.abs(pos.x) >= 22.8 && Math.abs(pos.x) <= 29.5 && pos.z > -30 && pos.z < 47) return 'Umlaufender Kreuzgang';
    if (pos.x >= 68.4 && pos.x <= 96.6 && Math.abs(pos.z) <= 16.6 && pos.y < 2.2) {
      return 'Plaça de Gaudí · Im Spiegelteich';
    }
    if (pos.x > 52 && Math.abs(pos.z) < 48) return 'Plaça de Gaudí · Spiegelteich (Ost)';
    if (pos.x > 31 && Math.abs(pos.z) < 22) return 'Vorplatz Geburtsfassade (Ost)';
    if (pos.x < -52 && Math.abs(pos.z) < 48) return 'Plaça de la Sagrada Família (West)';
    if (pos.x < -31 && Math.abs(pos.z) < 22) return 'Vorplatz Passionsfassade (West)';
    if (pos.z > 47) return 'Glorienfassade & Große Freitreppe (Süd)';
    return 'Eixample · Umgebung Barcelona';
  }
}
