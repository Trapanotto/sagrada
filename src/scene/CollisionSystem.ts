import * as THREE from 'three';

export interface WalkConstraints {
  groundY: number;
  clampedX: number;
  clampedZ: number;
}

const EYE_HEIGHT = 1.75;

interface BoxObstacle {
  minX: number;
  maxX: number;
  minZ: number;
  maxZ: number;
  maxY: number;
}

const EXTERIOR_OBSTACLES: BoxObstacle[] = [
  // Eixample apartment blocks (Plaça de Gaudí Pond is jumpable & wadeable!)
  { minX: -131, maxX: -59, minZ: -144, maxZ: -72, maxY: 25 },
  { minX: -36, maxX: 36, minZ: -144, maxZ: -72, maxY: 25 },
  { minX: 59, maxX: 131, minZ: -144, maxZ: -72, maxY: 25 },
  { minX: -131, maxX: -59, minZ: 82, maxZ: 154, maxY: 25 },
  { minX: -36, maxX: 36, minZ: 88, maxZ: 160, maxY: 25 },
  { minX: 59, maxX: 131, minZ: 82, maxZ: 154, maxY: 25 },
  { minX: 142, maxX: 214, minZ: -144, maxZ: 144, maxY: 25 },
  { minX: -214, maxX: -142, minZ: -144, maxZ: 144, maxY: 25 },
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
 * All 18 walkable internal helical stone staircases matching blender/build_towers.py
 * (Note: Blender Y maps to Three.js -Z!)
 */
export const TOWER_STAIR_SHAFTS: TowerStairShaft[] = [
  // 1. Tower of Jesus Christ (56m -> 136m spiraling around glass panorama elevator!)
  { name: 'Wendeltreppe · Turm Jesu Christi', cx: 0.0, cz: 0.0, zStart: 56.0, zEnd: 136.0, rInner: 2.35, rOuter: 4.85, turnsPer10m: 1.1, clockwise: true },
  // 2. Tower of Virgin Mary (52m -> 118m over Apse)
  { name: 'Wendeltreppe · Marien-Turm', cx: 0.0, cz: -22.5, zStart: 52.0, zEnd: 118.0, rInner: 1.85, rOuter: 3.9, turnsPer10m: 1.25, clockwise: true },
  // 3. Four Towers of the Evangelists (52m -> 114m)
  { name: 'Wendeltreppe · Evangelist Markus', cx: -11.5, cz: 11.5, zStart: 52.0, zEnd: 114.0, rInner: 1.15, rOuter: 3.0, turnsPer10m: 1.35, clockwise: true },
  { name: 'Wendeltreppe · Evangelist Lukas', cx: -11.5, cz: -11.5, zStart: 52.0, zEnd: 114.0, rInner: 1.15, rOuter: 3.0, turnsPer10m: 1.35, clockwise: false },
  { name: 'Wendeltreppe · Evangelist Matthäus', cx: 11.5, cz: 11.5, zStart: 52.0, zEnd: 114.0, rInner: 1.15, rOuter: 3.0, turnsPer10m: 1.35, clockwise: false },
  { name: 'Wendeltreppe · Evangelist Johannes', cx: 11.5, cz: -11.5, zStart: 52.0, zEnd: 114.0, rInner: 1.15, rOuter: 3.0, turnsPer10m: 1.35, clockwise: true },
  // 4. Four Nativity Towers (East, 14.5m -> 65m)
  { name: 'Wendeltreppe · Geburtsturm SO', cx: 31.5, cz: 10.8, zStart: 14.5, zEnd: 65.0, rInner: 1.15, rOuter: 2.95, turnsPer10m: 1.68, clockwise: false },
  { name: 'Wendeltreppe · Geburtsturm Mitte-Süd', cx: 31.5, cz: 3.6, zStart: 14.5, zEnd: 65.0, rInner: 1.15, rOuter: 2.95, turnsPer10m: 1.68, clockwise: true },
  { name: 'Wendeltreppe · Geburtsturm Mitte-Nord', cx: 31.5, cz: -3.6, zStart: 14.5, zEnd: 65.0, rInner: 1.15, rOuter: 2.95, turnsPer10m: 1.68, clockwise: false },
  { name: 'Wendeltreppe · Geburtsturm NO', cx: 31.5, cz: -10.8, zStart: 14.5, zEnd: 65.0, rInner: 1.15, rOuter: 2.95, turnsPer10m: 1.68, clockwise: true },
  // 5. Four Passion Towers (West, 14.5m -> 65m)
  { name: 'Wendeltreppe · Passionsturm SW', cx: -31.5, cz: 10.8, zStart: 14.5, zEnd: 65.0, rInner: 1.15, rOuter: 2.95, turnsPer10m: 1.68, clockwise: true },
  { name: 'Wendeltreppe · Passionsturm Mitte-Süd', cx: -31.5, cz: 3.6, zStart: 14.5, zEnd: 65.0, rInner: 1.15, rOuter: 2.95, turnsPer10m: 1.68, clockwise: false },
  { name: 'Wendeltreppe · Passionsturm Mitte-Nord', cx: -31.5, cz: -3.6, zStart: 14.5, zEnd: 65.0, rInner: 1.15, rOuter: 2.95, turnsPer10m: 1.68, clockwise: true },
  { name: 'Wendeltreppe · Passionsturm NW', cx: -31.5, cz: -10.8, zStart: 14.5, zEnd: 65.0, rInner: 1.15, rOuter: 2.95, turnsPer10m: 1.68, clockwise: false },
  // 6. Four Glory Towers (South, 14.5m -> 72m)
  { name: 'Wendeltreppe · Glorienturm West', cx: -11.4, cz: 49.5, zStart: 14.5, zEnd: 72.0, rInner: 1.2, rOuter: 3.05, turnsPer10m: 1.62, clockwise: false },
  { name: 'Wendeltreppe · Glorienturm Mitte-West', cx: -3.8, cz: 49.5, zStart: 14.5, zEnd: 72.0, rInner: 1.2, rOuter: 3.05, turnsPer10m: 1.62, clockwise: true },
  { name: 'Wendeltreppe · Glorienturm Mitte-Ost', cx: 3.8, cz: 49.5, zStart: 14.5, zEnd: 72.0, rInner: 1.2, rOuter: 3.05, turnsPer10m: 1.62, clockwise: false },
  { name: 'Wendeltreppe · Glorienturm Ost', cx: 11.4, cz: 49.5, zStart: 14.5, zEnd: 72.0, rInner: 1.2, rOuter: 3.05, turnsPer10m: 1.62, clockwise: true },
];

export class CollisionSystem {
  public readonly eyeHeight = EYE_HEIGHT;
  public elevatorFloorY = 1.2;

  /**
   * Resolves walkable floor elevation and horizontal boundary constraints across ALL levels:
   * Crypt, Street, Pond, Nave, Altar, Emporen, ALL 18 Tower Spiral Staircases, Glass Elevator, & Skybridges.
   */
  public resolveWalkPosition(x: number, feetY: number, z: number): WalkConstraints {
    let cx = THREE.MathUtils.clamp(x, -165, 165);
    let cz = THREE.MathUtils.clamp(z, -105, 118);

    // 0. Central Glass Panorama Elevator Cabin inside the Tower of Jesus Christ (0, elevatorFloorY, 0)
    const rCenter = Math.hypot(cx, cz);
    if (rCenter < 2.02 && Math.abs(feetY - this.elevatorFloorY) < 2.4) {
      // Keep cleanly inside circular glass cabin while moving (allow walking out freely at stop landings!)
      const atLanding =
        Math.abs(this.elevatorFloorY - 1.2) < 0.35 ||
        Math.abs(this.elevatorFloorY - 56.0) < 0.35 ||
        Math.abs(this.elevatorFloorY - 136.0) < 0.35;
      if (!atLanding && rCenter > 1.72) {
        cx = (cx / rCenter) * 1.72;
        cz = (cz / rCenter) * 1.72;
      }
      return { groundY: this.elevatorFloorY, clampedX: cx, clampedZ: cz };
    }

    // 1. Jesus Christ Tower Panoramic Viewpoint Deck (Y = 136.0m, r <= 6.1m)
    if (feetY > 132.5 && rCenter < 7.5) {
      if (rCenter > 6.0) {
        cx = (cx / rCenter) * 6.0;
        cz = (cz / rCenter) * 6.0;
      }
      return { groundY: 136.0, clampedX: cx, clampedZ: cz };
    }

    // 2. Check ALL 18 Internal Helical Tower Spiral Staircases!
    for (const shaft of TOWER_STAIR_SHAFTS) {
      const dist = Math.hypot(cx - shaft.cx, cz - shaft.cz);
      const inRangeY = feetY >= shaft.zStart - 1.5 && feetY <= shaft.zEnd + 2.0;
      if (!inRangeY) continue;

      // For Jesus Tower spiral staircase, inner core (r < 2.15) is the glass elevator shaft
      const minDetectR = shaft.cx === 0 && shaft.cz === 0 ? 2.1 : 0.0;
      if (dist >= minDetectR && dist <= shaft.rOuter + 0.45) {
        // Allow smooth stepping off at top skybridges or bottom landings
        if (shaft.zEnd === 65.0 && feetY > 63.0 && Math.abs(cx - shaft.cx) < 1.8) {
          return { groundY: 65.0, clampedX: cx, clampedZ: cz };
        }
        if (shaft.zEnd === 72.0 && feetY > 70.0 && Math.abs(cz - shaft.cz) < 1.8) {
          return { groundY: 72.0, clampedX: cx, clampedZ: cz };
        }
        if (shaft.cx === 0 && shaft.cz === 0 && feetY > 133.8) {
          return { groundY: 136.0, clampedX: cx, clampedZ: cz };
        }

        const dx = cx - shaft.cx;
        const dz = cz - shaft.cz;
        const rSafe = THREE.MathUtils.clamp(dist, shaft.rInner, shaft.rOuter - 0.12);
        const ang = Math.atan2(-dz, dx); // Matches Blender +Y = Three -Z
        cx = shaft.cx + Math.cos(ang) * rSafe;
        cz = shaft.cz - Math.sin(ang) * rSafe;

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
        return { groundY: spiralY, clampedX: cx, clampedZ: cz };
      }
    }

    // 2b. Crossing Vault Gallery Ring Deck at Y = 56.0m (connects Glass Elevator <-> Jesus Tower spiral staircase!)
    if (feetY >= 52.0 && feetY <= 60.0 && rCenter < 8.5) {
      if (rCenter > 7.4) {
        cx = (cx / rCenter) * 7.4;
        cz = (cz / rCenter) * 7.4;
      }
      return { groundY: 56.0, clampedX: cx, clampedZ: cz };
    }

    // 3. Nativity (65m), Passion (65m) & Glory (72m) Tower Skybridges!
    if (feetY > 45) {
      // South Glory Skybridge (Z ≈ +49.5, Y = 72.0m)
      if (cz > 34.0) {
        cx = THREE.MathUtils.clamp(cx, -11.8, 11.8);
        cz = THREE.MathUtils.clamp(cz, 48.0, 51.0);
        return { groundY: 72.0, clampedX: cx, clampedZ: cz };
      }
      if (cx > 0) {
        // East Nativity Skybridge (65m connecting all 4 Nativity towers)
        cx = THREE.MathUtils.clamp(cx, 30.1, 32.9);
        cz = THREE.MathUtils.clamp(cz, -11.0, 11.0);
      } else {
        // West Passion Skybridge (65m connecting all 4 Passion towers)
        cx = THREE.MathUtils.clamp(cx, -32.9, -30.1);
        cz = THREE.MathUtils.clamp(cz, -11.0, 11.0);
      }
      return { groundY: 65.0, clampedX: cx, clampedZ: cz };
    }

    // 3b. 2 Walkable Gaudí Corner Helical Staircases: Nave Floor (1.2m) <-> Emporen Galleries (14.5m) at (±19.6, Z=+42.8)!
    for (const sx of [-1, 1]) {
      const scx = sx * 19.6;
      const scz = 42.8;
      const dCorner = Math.hypot(cx - scx, cz - scz);
      if (dCorner < 2.25 && feetY >= 0.8 && feetY <= 16.0) {
        const ang = Math.atan2(-(cz - scz), cx - scx);
        const signedAng = sx > 0 ? ang : -ang;
        const baseFrac = (((signedAng % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2)) / (Math.PI * 2);
        const pitch = (14.5 - 1.2) / 2.5;
        const estTurn = Math.round((feetY - 1.2) / pitch - baseFrac);
        const stairY = THREE.MathUtils.clamp(1.2 + (estTurn + baseFrac) * pitch, 1.2, 14.5);
        return { groundY: stairY, clampedX: cx, clampedZ: cz };
      }
    }

    // 4. Elevated Choir Galleries / Emporen (Y = 14.5m) + East, West & South Tower Access Bridges!
    if (feetY > 9.0) {
      const onEastBridge = cx >= 20.0 && cx <= 33.2 && cz >= 1.8 && cz <= 16.0;
      const onWestBridge = cx <= -20.0 && cx >= -33.2 && cz >= 1.8 && cz <= 16.0;
      const onGloryBridge = Math.abs(Math.abs(cx) - 3.8) <= 2.2 && cz >= 43.0 && cz <= 51.0;
      const onSouth = cz >= 40.8 && cz <= 45.2 && Math.abs(cx) <= 21.8;
      const onEast = cx >= 17.1 && cx <= 22.1 && cz >= 14.0 && cz <= 45.2;
      const onWest = cx <= -17.1 && cx >= -22.1 && cz >= 14.0 && cz <= 45.2;
      if (!onEastBridge && !onWestBridge && !onGloryBridge && !onSouth && !onEast && !onWest) {
        if (cz > 39.0) {
          cz = THREE.MathUtils.clamp(cz, 41.0, 45.0);
          cx = THREE.MathUtils.clamp(cx, -21.6, 21.6);
        } else if (cx >= 0) {
          cx = THREE.MathUtils.clamp(cx, 17.2, 22.0);
          cz = THREE.MathUtils.clamp(cz, 14.2, 45.0);
        } else {
          cx = THREE.MathUtils.clamp(cx, -22.0, -17.2);
          cz = THREE.MathUtils.clamp(cz, 14.2, 45.0);
        }
      }
      return { groundY: 14.5, clampedX: cx, clampedZ: cz };
    }

    // 5. Subterranean Crypt & Walkable Descending Staircase (Three Z = -12..-36, Y = -5.5m)
    const distCrypt = Math.hypot(cx, cz - -21.0);
    if (cx >= -22.0 && cx <= -9.8 && cz >= -18.5 && cz <= -10.2 && feetY < 2.5) {
      const t = THREE.MathUtils.clamp((cx - -21.5) / (-10.5 - -21.5), 0, 1);
      const stairY = THREE.MathUtils.lerp(1.2, -5.5, t);
      if (Math.abs(feetY - stairY) < 2.2) {
        return { groundY: stairY, clampedX: cx, clampedZ: cz };
      }
    }
    if (feetY < -1.5) {
      if (distCrypt > 14.5 && !(cx < -9.0 && cz > -17.5 && cz < -10.5)) {
        const dx = cx;
        const dz = cz - -21.0;
        const scale = 14.5 / Math.max(distCrypt, 0.001);
        cx = dx * scale;
        cz = -21.0 + dz * scale;
      }
      return { groundY: -5.5, clampedX: cx, clampedZ: cz };
    }

    // 6. Ground Level (Street = 0.0, Pond = -0.45, Main Nave/Cloister/Sacristies = 1.2, High Altar = 2.4)
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

    let groundY = 0.0;

    // Plaça de Gaudí Reflective Pond (jump right over the +0.36m coping rim into the -0.45m water basin!)
    const inPondOuter = cx >= 67.4 && cx <= 97.6 && cz >= -17.6 && cz <= 17.6;
    const inPondWater = cx >= 68.4 && cx <= 96.6 && cz >= -16.6 && cz <= 16.6;
    if (inPondWater) {
      const distFountain = Math.hypot(cx - 82.5, cz);
      groundY = distFountain < 2.65 ? 0.35 : -0.45;
    } else if (inPondOuter) {
      groundY = 0.36;
    }

    // Presbytery High Altar stepped platform (center X=0, Z=-17.5)
    const dAltar = Math.hypot(cx, cz - -17.5);
    if (dAltar < 8.8) {
      groundY = 2.4;
    } else if (dAltar < 10.8) {
      const t = 1.0 - (dAltar - 8.8) / 2.0;
      groundY = 1.2 + t * 1.2;
    } else if (this.isOnBasilicaPodium(cx, cz)) {
      groundY = 1.2;
    } else if (cx > 31.8 && cx <= 37.0 && Math.abs(cz) <= 14.5) {
      const t = 1.0 - THREE.MathUtils.clamp((cx - 32.5) / 4.2, 0, 1);
      groundY = t * 1.2;
    } else if (cx < -31.8 && cx >= -40.5 && Math.abs(cz) <= 15.0) {
      const t = 1.0 - THREE.MathUtils.clamp((-cx - 35.0) / 5.0, 0, 1);
      groundY = t * 1.2;
    } else if (cz > 57.5 && cz <= 71.0 && Math.abs(cx) <= 19.0) {
      const t = 1.0 - THREE.MathUtils.clamp((cz - 58.0) / 12.5, 0, 1);
      groundY = t * 1.2;
    }

    return { groundY, clampedX: cx, clampedZ: cz };
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
    // Inside central Jesus Tower elevator / helical shaft
    if (Math.hypot(pos.x, pos.z) < 8.5 && pos.y >= 1.0 && pos.y < 134.0) return 0.92;
    if (pos.y > 58.0) return 0.0;
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
    if (pos.y >= 54 && pos.y <= 61 && rCenter < 8.5) return 'Vierungs-Gewölbegalerie · 56 m';

    for (const shaft of TOWER_STAIR_SHAFTS) {
      if (Math.hypot(pos.x - shaft.cx, pos.z - shaft.cz) < shaft.rOuter + 0.6 && pos.y >= shaft.zStart - 0.5 && pos.y < shaft.zEnd - 0.5) {
        return `${shaft.name} (${pos.y.toFixed(0)} m)`;
      }
    }

    if (pos.y > 55) {
      if (Math.abs(pos.x - 31.5) < 6 && Math.abs(pos.z) < 13 && pos.y < 76) {
        return 'Turm-Brücke Ost · Geburtsfassade (65 m)';
      }
      if (Math.abs(pos.x - -31.5) < 6 && Math.abs(pos.z) < 13 && pos.y < 76) {
        return 'Turm-Brücke West · Passionsfassade (65 m)';
      }
      if (Math.abs(pos.z - 49.5) < 6 && Math.abs(pos.x) < 14 && pos.y < 82) {
        return 'Turm-Brücke Süd · Glorienfassade (72 m)';
      }
      return 'Luftraum · Über den 18 Türmen';
    }
    if (pos.y < -1.5) return 'Krypta · Grab von Antoni Gaudí (-5,5 m)';
    if (pos.y > 11 && pos.y < 24 && Math.abs(pos.x) < 33 && pos.z > -32 && pos.z < 52) {
      return 'Empore (Cantoria) · 14,5 m Höhe';
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
