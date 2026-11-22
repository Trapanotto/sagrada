import * as THREE from 'three';

export interface WalkConstraints {
  groundY: number;
  clampedX: number;
  clampedZ: number;
}

const EYE_HEIGHT = 1.75;

// Axis-aligned exterior obstacles (Eixample buildings & Plaça de Gaudí pond)
interface BoxObstacle {
  minX: number;
  maxX: number;
  minZ: number;
  maxZ: number;
  maxY: number;
}

const EXTERIOR_OBSTACLES: BoxObstacle[] = [
  // Eixample apartment blocks (center ±36m) — Plaça de Gaudí Pond is now fully jumpable & wadeable!
  { minX: -131, maxX: -59, minZ: -144, maxZ: -72, maxY: 25 },
  { minX: -36, maxX: 36, minZ: -144, maxZ: -72, maxY: 25 },
  { minX: 59, maxX: 131, minZ: -144, maxZ: -72, maxY: 25 },
  { minX: -131, maxX: -59, minZ: 82, maxZ: 154, maxY: 25 },
  { minX: -36, maxX: 36, minZ: 88, maxZ: 160, maxY: 25 },
  { minX: 59, maxX: 131, minZ: 82, maxZ: 154, maxY: 25 },
  { minX: 142, maxX: 214, minZ: -144, maxZ: 144, maxY: 25 },
  { minX: -214, maxX: -142, minZ: -144, maxZ: 144, maxY: 25 },
];

export class CollisionSystem {
  public readonly eyeHeight = EYE_HEIGHT;

  /**
   * Resolves the walkable floor elevation and horizontal boundary constraints
   * across all architectural levels (Crypt, Street, Nave, Altar, Galleries, Tower Viewpoints).
   */
  public resolveWalkPosition(x: number, feetY: number, z: number): WalkConstraints {
    let cx = THREE.MathUtils.clamp(x, -165, 165);
    let cz = THREE.MathUtils.clamp(z, -105, 118);

    // 1. Jesus Christ Tower Panoramic Viewpoint (Y ≈ 136m)
    if (feetY > 110) {
      const r = Math.hypot(cx, cz);
      const maxR = 5.95;
      if (r > maxR) {
        cx = (cx / r) * maxR;
        cz = (cz / r) * maxR;
      }
      return { groundY: 136.0, clampedX: cx, clampedZ: cz };
    }

    // 2. Gaudí Walkable Helical Spiral Staircase inside inner SE Nativity Tower (31.5, Z=+3.6, Y = 14.5m -> 65.0m)!
    const dSpiral = Math.hypot(cx - 31.5, cz - 3.6);
    if (dSpiral < 3.55 && feetY >= 13.0 && feetY <= 67.5) {
      // Allow exiting cleanly onto the 65m Turm-Brücke Ost when near top and moving north (cz < 2.2)
      if (feetY > 62.5 && cz < 2.2) {
        return { groundY: 65.0, clampedX: THREE.MathUtils.clamp(cx, 30.2, 32.8), clampedZ: cz };
      }
      // Keep player cleanly on the cantilevered annular stone tread (r = 1.25 .. 2.75) around the hollow eye!
      const dx = cx - 31.5;
      const dz = cz - 3.6;
      const rSafe = THREE.MathUtils.clamp(dSpiral, 1.32, 2.65);
      const ang = Math.atan2(-dz, dx); // Matches Blender +Y = Three -Z
      cx = 31.5 + Math.cos(ang) * rSafe;
      cz = 3.6 - Math.sin(ang) * rSafe;

      // Resolve nearest helical turn matching current player feetY (8.5 turns over 50.5m = 5.941m per turn)
      const pitchPerTurn = (65.0 - 14.5) / 8.5;
      const baseAngle = ((ang % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2);
      const fracTurn = baseAngle / (Math.PI * 2);
      const estTurn = Math.round((feetY - 14.5) / pitchPerTurn - fracTurn);
      const spiralY = THREE.MathUtils.clamp(14.5 + (estTurn + fracTurn) * pitchPerTurn, 14.5, 65.0);
      return { groundY: spiralY, clampedX: cx, clampedZ: cz };
    }

    // 3. Nativity / Passion Tower Skybridges (Y ≈ 65m)
    if (feetY > 45) {
      if (cx > 0) {
        cx = THREE.MathUtils.clamp(cx, 30.2, 32.8);
        cz = THREE.MathUtils.clamp(cz, -3.7, 4.4);
      } else {
        cx = THREE.MathUtils.clamp(cx, -32.8, -30.2);
        cz = THREE.MathUtils.clamp(cz, -3.7, 3.7);
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

    // 4. Elevated Choir Galleries / Emporen (Y ≈ 14.5m) + East Gallery-to-Tower Passage!
    if (feetY > 9.0) {
      // Walkable bridge from East Empore (21, 14.5) to Nativity Spiral Staircase Base (31.5, 3.6)
      const onTowerBridge = cx >= 20.0 && cx <= 33.0 && cz >= 2.0 && cz <= 16.0;
      const onSouth = cz >= 40.8 && cz <= 45.2 && Math.abs(cx) <= 21.8;
      const onEast = cx >= 17.1 && cx <= 22.1 && cz >= 14.0 && cz <= 45.2;
      const onWest = cx <= -17.1 && cx >= -22.1 && cz >= 14.5 && cz <= 45.2;
      if (!onTowerBridge && !onSouth && !onEast && !onWest) {
        if (cz > 39.0) {
          cz = THREE.MathUtils.clamp(cz, 41.0, 45.0);
          cx = THREE.MathUtils.clamp(cx, -21.6, 21.6);
        } else if (cx >= 0) {
          cx = THREE.MathUtils.clamp(cx, 17.2, 22.0);
          cz = THREE.MathUtils.clamp(cz, 14.2, 45.0);
        } else {
          cx = THREE.MathUtils.clamp(cx, -22.0, -17.2);
          cz = THREE.MathUtils.clamp(cz, 14.8, 45.0);
        }
      }
      return { groundY: 14.5, clampedX: cx, clampedZ: cz };
    }

    // 4. Subterranean Crypt & Walkable Descending Staircase (Three Z = -12..-36, Y = -5.5m)
    const distCrypt = Math.hypot(cx, cz - -21.0);
    // Staircase ramp corridor from (-21.5, -16.5, Y=1.2) -> (-10.5, -12.0, Y=-5.5)
    if (cx >= -22.0 && cx <= -9.8 && cz >= -18.5 && cz <= -10.2 && feetY < 2.5) {
      const t = THREE.MathUtils.clamp((cx - -21.5) / (-10.5 - -21.5), 0, 1);
      const stairY = THREE.MathUtils.lerp(1.2, -5.5, t);
      if (Math.abs(feetY - stairY) < 2.2) {
        return { groundY: stairY, clampedX: cx, clampedZ: cz };
      }
    }
    if (feetY < -1.5) {
      // Keep inside circular Neo-Gothic Crypt (r <= 14.5) except staircase exit
      if (distCrypt > 14.5 && !(cx < -9.0 && cz > -17.5 && cz < -10.5)) {
        const dx = cx;
        const dz = cz - -21.0;
        const scale = 14.5 / Math.max(distCrypt, 0.001);
        cx = dx * scale;
        cz = -21.0 + dz * scale;
      }
      return { groundY: -5.5, clampedX: cx, clampedZ: cz };
    }

    // 5. Ground Level (Street = 0.0, Steps/Ramps, Main Nave/Cloister/Sacristies = 1.2, High Altar = 2.4)
    // Push out of exterior obstacles (Pond & Eixample apartment blocks)
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
      if (distFountain < 2.65) {
        // Climb onto the stone fountain base pedestal inside the pond!
        groundY = 0.35;
      } else {
        groundY = -0.45;
      }
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
      // Nativity Facade East entrance steps (smooth ramp)
      const t = 1.0 - THREE.MathUtils.clamp((cx - 32.5) / 4.2, 0, 1);
      groundY = t * 1.2;
    } else if (cx < -31.8 && cx >= -40.5 && Math.abs(cz) <= 15.0) {
      // Passion Facade West entrance steps (smooth ramp)
      const t = 1.0 - THREE.MathUtils.clamp((-cx - 35.0) / 5.0, 0, 1);
      groundY = t * 1.2;
    } else if (cz > 57.5 && cz <= 71.0 && Math.abs(cx) <= 19.0) {
      // Glory Facade South Grand Staircase (smooth ramp)
      const t = 1.0 - THREE.MathUtils.clamp((cz - 58.0) / 12.5, 0, 1);
      groundY = t * 1.2;
    }

    return { groundY, clampedX: cx, clampedZ: cz };
  }

  private isOnBasilicaPodium(x: number, z: number): boolean {
    // 5-aisle nave + cloister wings (X: -29..+29, Z: -16..+58)
    if (Math.abs(x) <= 29.0 && z >= -16.0 && z <= 58.0) return true;
    // Transept arms (X: -35..+33, Z: -15.5..+15.5)
    if (x >= -35.5 && x <= 33.0 && Math.abs(z) <= 15.5) return true;
    // Apse semicircle (center 0, -16.5, r=19.5)
    if (Math.hypot(x, z - -16.5) <= 19.5 && z <= -15.0) return true;
    // NE & NW Sacristies (center ±27.5, -32.5, r=8.5)
    if (Math.hypot(Math.abs(x) - 27.5, z - -32.5) <= 8.5) return true;
    // North cloister connectors
    if (Math.abs(x) >= 23.0 && Math.abs(x) <= 29.5 && z >= -26.5 && z <= -15.0) return true;
    return false;
  }

  /**
   * Returns 0.0 (completely outdoors) .. 1.0 (deep indoors / crypt) for smooth acoustic crossfade.
   */
  public getIndoorFactor(pos: THREE.Vector3): number {
    if (pos.y < -1.0) return 1.0; // Subterranean Crypt
    if (pos.y > 58.0) return 0.0; // High up in the sky / tower viewpoints
    // Inside Main Nave / Transepts / Apse
    const inNave = Math.abs(pos.x) < 22.8 && pos.z > -15.0 && pos.z < 47.0;
    const inTransept = Math.abs(pos.x) < 31.0 && Math.abs(pos.z) < 15.0;
    const inApse = Math.hypot(pos.x, pos.z - -16.5) < 18.8 && pos.z <= -14.0;
    if (inNave || inTransept || inApse) return 1.0;
    // Semi-sheltered Cloister / Sacristies
    if (Math.abs(pos.x) < 29.5 && pos.z > -38.0 && pos.z < 47.0 && pos.y < 12.0) return 0.65;
    return 0.0;
  }

  /**
   * Human-readable German architectural zone indicator for the HUD.
   */
  public detectZone(pos: THREE.Vector3): string {
    if (pos.y > 125 && Math.hypot(pos.x, pos.z) < 12) return 'Turm Jesu Christi · Aussicht 136 m';
    if (Math.hypot(pos.x - 31.5, pos.z - 3.6) < 4.2 && pos.y >= 13.5 && pos.y < 64.2) {
      return `Gaudí-Wendeltreppe · Ostturm (${pos.y.toFixed(0)} m)`;
    }
    if (pos.y > 55) {
      if (Math.abs(pos.x - 31.5) < 6 && Math.abs(pos.z) < 7 && pos.y < 76) {
        return 'Turm-Brücke Ost · Geburtsfassade (65 m)';
      }
      if (Math.abs(pos.x - -31.5) < 6 && Math.abs(pos.z) < 7 && pos.y < 76) {
        return 'Turm-Brücke West · Passionsfassade (65 m)';
      }
      return 'Luftraum · Über den 18 Türmen';
    }
    if (pos.y < -1.5) return 'Krypta · Grab von Antoni Gaudí (-5,5 m)';
    if (pos.y > 11 && pos.y < 24 && Math.abs(pos.x) < 23 && pos.z > -32 && pos.z < 46) {
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
