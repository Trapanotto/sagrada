import * as THREE from 'three';
import { MeshBVH } from 'three-mesh-bvh';

export interface WalkConstraints {
  groundY: number;
  clampedX: number;
  clampedZ: number;
}

const EYE_HEIGHT = 1.75;
const STEP_UP_MAX = 1.45; // Max vertical step-up allowed onto stairs/ramps/platforms
const CAPSULE_RADIUS = 0.34;
const CAPSULE_KNEE_Y = 0.52; // Clears all 0.12-0.36m stair treads & curbs while blocking walls/altars/pews/railings
const CAPSULE_HEAD_Y = 1.65;

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

// Fallback structural columns (also represented in full 3D BVH once built)
const INTERIOR_COLUMNS: Array<[number, number, number]> = [
  [-7.5, -7.5, 1.38], [7.5, -7.5, 1.38], [-7.5, 7.5, 1.38], [7.5, 7.5, 1.38],
  [-7.5, 15.0, 1.05], [7.5, 15.0, 1.05], [-7.5, 22.5, 1.05], [7.5, 22.5, 1.05],
  [-7.5, 30.0, 1.05], [7.5, 30.0, 1.05], [-7.5, 37.5, 1.05], [7.5, 37.5, 1.05],
  [-7.5, 45.0, 1.05], [7.5, 45.0, 1.05],
  [-15.0, 15.0, 0.88], [15.0, 15.0, 0.88], [-15.0, 22.5, 0.88], [15.0, 22.5, 0.88],
  [-15.0, 30.0, 0.88], [15.0, 30.0, 0.88], [-15.0, 37.5, 0.88], [15.0, 37.5, 0.88],
  [-15.0, 45.0, 0.88], [15.0, 45.0, 0.88],
  [-15.0, -7.5, 0.88], [15.0, -7.5, 0.88], [-15.0, 7.5, 0.88], [15.0, 7.5, 0.88],
  [-22.5, -7.5, 0.88], [22.5, -7.5, 0.88], [-22.5, 7.5, 0.88], [22.5, 7.5, 0.88],
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

const WALK_BRIDGES: WalkBridge[] = [
  // Emporen (14.5m) -> Between-Tower Base Gaps (14.5m)
  { x0: 21.0, y0: 14.5, z0: 14.5, x1: 30.1, y1: 14.5, z1: 7.2, halfWidth: 1.75 },
  { x0: -21.0, y0: 14.5, z0: 14.5, x1: -30.1, y1: 14.5, z1: 7.2, halfWidth: 1.75 },
  { x0: -7.6, y0: 14.5, z0: 43.0, x1: -7.6, y1: 14.5, z1: 48.2, halfWidth: 1.65 },
  { x0: 0.0, y0: 14.5, z0: 43.0, x1: 0.0, y1: 14.5, z1: 48.2, halfWidth: 1.65 },
  { x0: 7.6, y0: 14.5, z0: 43.0, x1: 7.6, y1: 14.5, z1: 48.2, halfWidth: 1.65 },

  // Segmented Between-Tower Galleries (14.5m) & Upper Skybridges (65m East/West & 72m South Glory)
  // East Nativity gaps (Z = -8.9..-5.5, -1.7..+1.7, +5.5..+8.9)
  { x0: 31.5, y0: 14.5, z0: 5.2, x1: 31.5, y1: 14.5, z1: 9.2, halfWidth: 1.65 },
  { x0: 31.5, y0: 14.5, z0: -2.0, x1: 31.5, y1: 14.5, z1: 2.0, halfWidth: 1.65 },
  { x0: 31.5, y0: 14.5, z0: -9.2, x1: 31.5, y1: 14.5, z1: -5.2, halfWidth: 1.65 },
  { x0: 31.5, y0: 65.0, z0: 5.2, x1: 31.5, y1: 65.0, z1: 9.2, halfWidth: 1.65 },
  { x0: 31.5, y0: 65.0, z0: -2.0, x1: 31.5, y1: 65.0, z1: 2.0, halfWidth: 1.65 },
  { x0: 31.5, y0: 65.0, z0: -9.2, x1: 31.5, y1: 65.0, z1: -5.2, halfWidth: 1.65 },
  // West Passion gaps
  { x0: -31.5, y0: 14.5, z0: 5.2, x1: -31.5, y1: 14.5, z1: 9.2, halfWidth: 1.65 },
  { x0: -31.5, y0: 14.5, z0: -2.0, x1: -31.5, y1: 14.5, z1: 2.0, halfWidth: 1.65 },
  { x0: -31.5, y0: 14.5, z0: -9.2, x1: -31.5, y1: 14.5, z1: -5.2, halfWidth: 1.65 },
  { x0: -31.5, y0: 65.0, z0: 5.2, x1: -31.5, y1: 65.0, z1: 9.2, halfWidth: 1.65 },
  { x0: -31.5, y0: 65.0, z0: -2.0, x1: -31.5, y1: 65.0, z1: 2.0, halfWidth: 1.65 },
  { x0: -31.5, y0: 65.0, z0: -9.2, x1: -31.5, y1: 65.0, z1: -5.2, halfWidth: 1.65 },
  // South Glory gaps (X = -9.5..-5.7, -1.9..+1.9, +5.7..+9.5)
  { x0: -9.8, y0: 14.5, z0: 49.5, x1: -5.4, y1: 14.5, z1: 49.5, halfWidth: 1.65 },
  { x0: -2.2, y0: 14.5, z0: 49.5, x1: 2.2, y1: 14.5, z1: 49.5, halfWidth: 1.65 },
  { x0: 5.4, y0: 14.5, z0: 49.5, x1: 9.8, y1: 14.5, z1: 49.5, halfWidth: 1.65 },
  { x0: -9.8, y0: 72.0, z0: 49.5, x1: -5.4, y1: 72.0, z1: 49.5, halfWidth: 1.65 },
  { x0: -2.2, y0: 72.0, z0: 49.5, x1: 2.2, y1: 72.0, z1: 49.5, halfWidth: 1.65 },
  { x0: 5.4, y0: 72.0, z0: 49.5, x1: 9.8, y1: 72.0, z1: 49.5, halfWidth: 1.65 },

  // Jesus Crossing Gallery (56m) -> All 4 Evangelist Towers (56m)
  { x0: 5.0, y0: 56.0, z0: 5.0, x1: 10.2, y1: 56.0, z1: 10.2, halfWidth: 1.55 },
  { x0: -5.0, y0: 56.0, z0: 5.0, x1: -10.2, y1: 56.0, z1: 10.2, halfWidth: 1.55 },
  { x0: 5.0, y0: 56.0, z0: -5.0, x1: 10.2, y1: 56.0, z1: -10.2, halfWidth: 1.55 },
  { x0: -5.0, y0: 56.0, z0: -5.0, x1: -10.2, y1: 56.0, z1: -10.2, halfWidth: 1.55 },

  // Horizontal 76.0m North Skybridge: Jesus Spiral (76m) <-> Virgin Mary Tower Entry (76m) ABOVE Apse Vault!
  { x0: 0.0, y0: 76.0, z0: -3.5, x1: 0.0, y1: 76.0, z1: -19.8, halfWidth: 1.65 },

  // Stepped Roof Stair-Bridges connecting Jesus Crossing (56m) <-> East/West (65m) & South Glory (72m)
  { x0: 7.0, y0: 56.0, z0: 0.0, x1: 30.2, y1: 65.0, z1: 0.0, halfWidth: 1.65 },
  { x0: -7.0, y0: 56.0, z0: 0.0, x1: -30.2, y1: 65.0, z1: 0.0, halfWidth: 1.65 },
  { x0: 0.0, y0: 56.0, z0: 7.0, x1: 0.0, y1: 72.0, z1: 48.1, halfWidth: 1.75 },

  // Nave (1.2m) <-> Subterranean Crypt (-5.5m) Straight Recessed Descending Staircase
  { x0: -21.0, y0: 1.2, z0: -13.8, x1: -11.2, y1: -5.5, z1: -13.8, halfWidth: 1.55 },
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

export const TOWER_STAIR_SHAFTS: TowerStairShaft[] = [
  { name: 'Wendeltreppe · Turm Jesu Christi', cx: 0.0, cz: 0.0, zStart: 56.0, zEnd: 136.0, rInner: 2.35, rOuter: 4.15, turnsPer10m: 1.1, clockwise: true },
  { name: 'Wendeltreppe · Marien-Turm', cx: 0.0, cz: -22.5, zStart: 76.0, zEnd: 118.0, rInner: 1.70, rOuter: 3.25, turnsPer10m: 1.25, clockwise: true },
  { name: 'Wendeltreppe · Evangelist Markus', cx: -11.5, cz: 11.5, zStart: 56.0, zEnd: 114.0, rInner: 1.05, rOuter: 2.35, turnsPer10m: 1.35, clockwise: true },
  { name: 'Wendeltreppe · Evangelist Lukas', cx: -11.5, cz: -11.5, zStart: 56.0, zEnd: 114.0, rInner: 1.05, rOuter: 2.35, turnsPer10m: 1.35, clockwise: false },
  { name: 'Wendeltreppe · Evangelist Matthäus', cx: 11.5, cz: 11.5, zStart: 56.0, zEnd: 114.0, rInner: 1.05, rOuter: 2.35, turnsPer10m: 1.35, clockwise: false },
  { name: 'Wendeltreppe · Evangelist Johannes', cx: 11.5, cz: -11.5, zStart: 56.0, zEnd: 114.0, rInner: 1.05, rOuter: 2.35, turnsPer10m: 1.35, clockwise: true },
  { name: 'Wendeltreppe · Geburtsturm SO', cx: 31.5, cz: 10.8, zStart: 14.5, zEnd: 65.0, rInner: 0.78, rOuter: 2.05, turnsPer10m: 1.68, clockwise: false },
  { name: 'Wendeltreppe · Geburtsturm Mitte-Süd', cx: 31.5, cz: 3.6, zStart: 14.5, zEnd: 65.0, rInner: 0.78, rOuter: 2.05, turnsPer10m: 1.68, clockwise: true },
  { name: 'Wendeltreppe · Geburtsturm Mitte-Nord', cx: 31.5, cz: -3.6, zStart: 14.5, zEnd: 65.0, rInner: 0.78, rOuter: 2.05, turnsPer10m: 1.68, clockwise: false },
  { name: 'Wendeltreppe · Geburtsturm NO', cx: 31.5, cz: -10.8, zStart: 14.5, zEnd: 65.0, rInner: 0.78, rOuter: 2.05, turnsPer10m: 1.68, clockwise: true },
  { name: 'Wendeltreppe · Passionsturm SW', cx: -31.5, cz: 10.8, zStart: 14.5, zEnd: 65.0, rInner: 0.78, rOuter: 2.05, turnsPer10m: 1.68, clockwise: true },
  { name: 'Wendeltreppe · Passionsturm Mitte-Süd', cx: -31.5, cz: 3.6, zStart: 14.5, zEnd: 65.0, rInner: 0.78, rOuter: 2.05, turnsPer10m: 1.68, clockwise: false },
  { name: 'Wendeltreppe · Passionsturm Mitte-Nord', cx: -31.5, cz: -3.6, zStart: 14.5, zEnd: 65.0, rInner: 0.78, rOuter: 2.05, turnsPer10m: 1.68, clockwise: true },
  { name: 'Wendeltreppe · Passionsturm NW', cx: -31.5, cz: -10.8, zStart: 14.5, zEnd: 65.0, rInner: 0.78, rOuter: 2.05, turnsPer10m: 1.68, clockwise: false },
  { name: 'Wendeltreppe · Glorienturm West', cx: -11.4, cz: 49.5, zStart: 14.5, zEnd: 72.0, rInner: 0.78, rOuter: 2.05, turnsPer10m: 1.62, clockwise: false },
  { name: 'Wendeltreppe · Glorienturm Mitte-West', cx: -3.8, cz: 49.5, zStart: 14.5, zEnd: 72.0, rInner: 0.78, rOuter: 2.05, turnsPer10m: 1.62, clockwise: true },
  { name: 'Wendeltreppe · Glorienturm Mitte-Ost', cx: 3.8, cz: 49.5, zStart: 14.5, zEnd: 72.0, rInner: 0.78, rOuter: 2.05, turnsPer10m: 1.62, clockwise: false },
  { name: 'Wendeltreppe · Glorienturm Ost', cx: 11.4, cz: 49.5, zStart: 14.5, zEnd: 72.0, rInner: 0.78, rOuter: 2.05, turnsPer10m: 1.62, clockwise: true },
];

// Non-collidable visual-only meshes (floors, stairs, distant horizon, canopies, glow accents)
const NON_COLLIDABLE_SUBSTRINGS = [
  'Floor',
  'Carpet',
  'CornerStairs',
  'EntranceStairs',
  'StairSteps',
  'RoofStairs',
  'Streets',
  'Sidewalks',
  'ParkLawns',
  'Roofs',
  'Crosswalks',
  'DistantCity',
  'HorizonHills',
  'MediterraneanSea',
  'HyperboloidVaults',
  'ColumnBranches',
  'Interior_GoldAccents',
  'Facade_CypressTree',
  'Facade_FruitPinnacles',
  'Facade_GoldAccents',
  'Facade_Doves',
  'Towers_TrencadisPinnacles',
  'Towers_GoldAccents',
  'Towers_EvangelistSculptures',
  'Tower_MaryStar',
  'Tower_JesusCross',
  'Tower_JesusElevatorShaftGlass',
  'Towers_InternalStaircases',
  'Towers_InternalStairRails',
  'LanternAndCandleGlow',
  'VotiveCandles',
  'KioskGlow',
  'PergolaWood',
  'PlanterShrubs',
  'ShopAwnings',
  'BalconiesIron',
  '_Leaves',
];

function isCollidableMeshName(name: string): boolean {
  if (!name) return false;
  // Tree foliage & lamp globe instances end with "_B"
  if (name.endsWith('_B') && (name.includes('PlaneTree') || name.includes('CypressTree') || name.includes('StreetLamp'))) {
    return false;
  }
  for (const sub of NON_COLLIDABLE_SUBSTRINGS) {
    if (name.includes(sub)) return false;
  }
  return true;
}

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
  public elevatorFloorY = 56.0;
  public bvhTriangles = 0;
  public bvhReady = false;

  private pendingMeshes: THREE.Mesh[] = [];
  private bvh: MeshBVH | null = null;
  private bvhGeo: THREE.BufferGeometry | null = null;

  // Reusable scratch objects (zero per-frame GC allocations!)
  private readonly _capSeg = new THREE.Line3();
  private readonly _capBox = new THREE.Box3();
  private readonly _triNormal = new THREE.Vector3();
  private readonly _triPt = new THREE.Vector3();
  private readonly _capPt = new THREE.Vector3();
  private readonly _ray = new THREE.Ray();

  /**
   * Registers all solid architectural & furnishing meshes from a loaded GLB root
   * for inclusion in the unified 3D BVH collision accelerator.
   */
  public registerCollisionMeshes(root: THREE.Object3D): void {
    root.updateMatrixWorld(true);
    root.traverse((obj) => {
      if (!(obj instanceof THREE.Mesh)) return;
      if (!isCollidableMeshName(obj.name)) return;
      this.pendingMeshes.push(obj);
    });
  }

  /**
   * Builds a single unified static 3D MeshBVH from all registered meshes & InstancedMeshes.
   * Called once during the loading screen so runtime capsule collision runs in <0.15 ms/frame!
   */
  public buildBVH(): { triangles: number; meshes: number; buildMs: number } {
    const t0 = performance.now();
    const posChunks: Float32Array[] = [];
    let totalFloats = 0;
    let meshCount = 0;

    const vA = new THREE.Vector3();
    const vB = new THREE.Vector3();
    const vC = new THREE.Vector3();
    const instMat = new THREE.Matrix4();
    const worldMat = new THREE.Matrix4();

    const appendGeometry = (geo: THREE.BufferGeometry, mat: THREE.Matrix4) => {
      const pos = geo.attributes.position;
      if (!pos) return;
      const index = geo.index;
      const triCount = index ? Math.floor(index.count / 3) : Math.floor(pos.count / 3);
      if (triCount === 0) return;

      const out = new Float32Array(triCount * 9);
      let cursor = 0;
      for (let i = 0; i < triCount; i++) {
        const i0 = index ? index.getX(i * 3) : i * 3;
        const i1 = index ? index.getX(i * 3 + 1) : i * 3 + 1;
        const i2 = index ? index.getX(i * 3 + 2) : i * 3 + 2;
        vA.fromBufferAttribute(pos, i0).applyMatrix4(mat);
        vB.fromBufferAttribute(pos, i1).applyMatrix4(mat);
        vC.fromBufferAttribute(pos, i2).applyMatrix4(mat);
        out[cursor++] = vA.x;
        out[cursor++] = vA.y;
        out[cursor++] = vA.z;
        out[cursor++] = vB.x;
        out[cursor++] = vB.y;
        out[cursor++] = vB.z;
        out[cursor++] = vC.x;
        out[cursor++] = vC.y;
        out[cursor++] = vC.z;
      }
      posChunks.push(out);
      totalFloats += out.length;
    };

    for (const mesh of this.pendingMeshes) {
      mesh.updateMatrixWorld(true);
      if (mesh instanceof THREE.InstancedMesh) {
        meshCount += mesh.count;
        for (let i = 0; i < mesh.count; i++) {
          mesh.getMatrixAt(i, instMat);
          worldMat.multiplyMatrices(mesh.matrixWorld, instMat);
          appendGeometry(mesh.geometry, worldMat);
        }
      } else {
        meshCount++;
        appendGeometry(mesh.geometry, mesh.matrixWorld);
      }
    }

    this.pendingMeshes.length = 0;

    if (totalFloats === 0) {
      return { triangles: 0, meshes: 0, buildMs: 0 };
    }

    const merged = new Float32Array(totalFloats);
    let offset = 0;
    for (const chunk of posChunks) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }

    if (this.bvhGeo) {
      this.bvhGeo.dispose();
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(merged, 3));
    this.bvhGeo = geo;
    this.bvh = new MeshBVH(geo, { maxLeafTris: 12 });
    this.bvhTriangles = totalFloats / 9;
    this.bvhReady = true;

    const buildMs = Math.round(performance.now() - t0);
    return { triangles: this.bvhTriangles, meshes: meshCount, buildMs };
  }

  /**
   * Resolves true 3D horizontal capsule collision against the static BVH (walls, columns,
   * High Altar, pews, statues, balustrades, crypt walls, cloister piers, facades, urban furniture).
   */
  private resolveBVHCapsuleXZ(cx: number, feetY: number, cz: number): [number, number] {
    if (!this.bvh) return [cx, cz];

    let x = cx;
    let z = cz;
    const y0 = feetY + CAPSULE_KNEE_Y;
    const y1 = feetY + CAPSULE_HEAD_Y;
    const r = CAPSULE_RADIUS;

    const seg = this._capSeg;
    const box = this._capBox;
    const triNormal = this._triNormal;
    const triPt = this._triPt;
    const capPt = this._capPt;

    // 3 solver passes guarantee smooth sliding along corners & acute masonry intersections
    for (let iter = 0; iter < 3; iter++) {
      let moved = false;
      seg.start.set(x, y0, z);
      seg.end.set(x, y1, z);
      box.min.set(x - r, y0 - r, z - r);
      box.max.set(x + r, y1 + r, z + r);

      this.bvh.shapecast({
        intersectsBounds: (b) => b.intersectsBox(box),
        intersectsTriangle: (tri) => {
          tri.getNormal(triNormal);
          // Skip walkable horizontal floors, stair treads & ceilings (handled by vertical resolver)
          if (Math.abs(triNormal.y) > 0.68) return false;

          const dist = tri.closestPointToSegment(seg, triPt, capPt);
          if (dist < r) {
            let dx = capPt.x - triPt.x;
            let dz = capPt.z - triPt.z;
            let hLen = Math.hypot(dx, dz);

            if (hLen < 1e-5) {
              // Degenerate center overlap: fall back to horizontal triangle normal
              dx = triNormal.x;
              dz = triNormal.z;
              hLen = Math.hypot(dx, dz);
              if (hLen < 1e-5) return false;
            }

            const push = (r - dist) + 0.002;
            const inv = push / hLen;
            x += dx * inv;
            z += dz * inv;
            moved = true;

            // Keep segment & AABB fresh inside the same pass to prevent double-pushing
            seg.start.x = x;
            seg.start.z = z;
            seg.end.x = x;
            seg.end.z = z;
            box.min.x = x - r;
            box.max.x = x + r;
            box.min.z = z - r;
            box.max.z = z + r;
          }
          return false;
        },
      });

      if (!moved) break;
    }

    return [x, z];
  }

  /**
   * Optional upward ceiling check so jumping in the subterranean Crypt or low Cloister arcades
   * cleanly respects overhead stone vaults instead of poking through the floor above.
   */
  public getCeilingY(x: number, feetY: number, z: number): number | null {
    // Subterranean Crypt vault peaks smoothly around -1.1m.. -0.8m
    if (feetY < -1.5 && Math.hypot(x, z - -21.0) <= 15.8) {
      return -1.1;
    }
    if (!this.bvh) return null;
    this._ray.origin.set(x, feetY + 1.1, z);
    this._ray.direction.set(0, 1, 0);
    const hit = this.bvh.raycastFirst(this._ray, THREE.DoubleSide, 0.05, 1.4);
    if (hit && hit.distance < 1.35) {
      return feetY + 1.1 + hit.distance;
    }
    return null;
  }

  /**
   * True Multi-Level Support-Surface + 3D Mesh BVH Resolver:
   * - Runs iterative 3D capsule-vs-mesh collision against walls, columns, altar, pews, railings & urban obstacles.
   * - Finds the HIGHEST walkable floor/bridge/stair/deck/roof at (x, z) below (feetY + STEP_UP_MAX).
   */
  public resolveWalkPosition(x: number, feetY: number, z: number): WalkConstraints {
    let cx = THREE.MathUtils.clamp(x, -165, 165);
    let cz = THREE.MathUtils.clamp(z, -105, 118);
    const maxStepY = feetY + STEP_UP_MAX;

    if (this.bvhReady) {
      [cx, cz] = this.resolveBVHCapsuleXZ(cx, feetY, cz);
    } else {
      // Pre-BVH analytical fallback
      const pushOutBox = (obs: BoxObstacle) => {
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
      };
      if (feetY < 24.0) {
        for (const obs of EXTERIOR_OBSTACLES) pushOutBox(obs);
      }
      if (feetY >= 0.0 && feetY < 22.0) {
        for (const [colX, colZ, colR] of INTERIOR_COLUMNS) {
          const dx = cx - colX;
          const dz = cz - colZ;
          const dist = Math.hypot(dx, dz);
          if (dist < colR && dist > 1e-4) {
            cx = colX + (dx / dist) * colR;
            cz = colZ + (dz / dist) * colR;
          }
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

    // 1. Central Glass Panorama Elevator Cabin Floor inside Tower of Jesus Christ (56m <-> 136m)
    if (feetY >= 53.0 && rCenter < 2.02 && Math.abs(feetY - this.elevatorFloorY) < 2.6) {
      consider(this.elevatorFloorY);
    }

    // 2. Top Panoramic Observation Decks & Mary Tower 76m Entry Ring
    if (rCenter <= 6.5) {
      consider(136.0);
    }
    const dMary = Math.hypot(cx, cz - -22.5);
    if (dMary <= 3.75) {
      consider(118.0);
    }
    if (dMary >= 1.70 && dMary <= 4.10) {
      consider(76.0);
    }
    for (const sx of [-1, 1]) {
      for (const sz of [-1, 1]) {
        if (Math.hypot(cx - sx * 11.5, cz - sz * 11.5) <= 2.75) {
          consider(114.0);
        }
      }
    }

    // 3. Crossing Vault Gallery Ring Deck at Y = 56.0m
    if (rCenter >= 1.9 && rCenter <= 7.8) {
      consider(56.0);
    }

    // 4. All Walkable Bridges, Connecting Galleries, Skybridges, Roof Stair-Bridges & Crypt Staircase
    for (const b of WALK_BRIDGES) {
      const { dist, t } = distToSegment2D(cx, cz, b.x0, b.z0, b.x1, b.z1);
      if (dist <= b.halfWidth) {
        const y = THREE.MathUtils.lerp(b.y0, b.y1, t);
        if (b.y1 < 0 && feetY < 2.8 && Math.abs(feetY - y) < 2.6) {
          return { groundY: y, clampedX: cx, clampedZ: cz };
        }
        consider(y);
      }
    }

    // 5. All 18 Internal Tower Helical Spiral Staircases (seamless automatic climbing UP and DOWN!)
    for (const shaft of TOWER_STAIR_SHAFTS) {
      if (feetY < shaft.zStart - 1.5 || feetY > shaft.zEnd + 1.5) continue;
      const dist = Math.hypot(cx - shaft.cx, cz - shaft.cz);
      if (dist >= shaft.rInner && dist <= shaft.rOuter) {
        const dx = cx - shaft.cx;
        const dz = cz - shaft.cz;
        const ang = Math.atan2(-dz, dx);
        const signedAng = shaft.clockwise ? ang : -ang;
        const baseAngle = ((signedAng % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2);
        const fracTurn = baseAngle / (Math.PI * 2);
        const pitchPerTurn = 10.0 / shaft.turnsPer10m;
        const estTurn = Math.round((feetY - shaft.zStart) / pitchPerTurn - fracTurn);
        let bestSpiralY: number | null = null;
        let bestDiff = Infinity;
        for (const dt of [-1, 0, 1]) {
          const candY = shaft.zStart + (estTurn + dt + fracTurn) * pitchPerTurn;
          if (candY < shaft.zStart - 0.8 || candY > shaft.zEnd + 0.8) continue;
          const clampedY = THREE.MathUtils.clamp(candY, shaft.zStart, shaft.zEnd);
          const diff = clampedY - feetY;
          if (diff <= 1.45 && diff >= -1.55 && Math.abs(diff) < bestDiff) {
            bestDiff = Math.abs(diff);
            bestSpiralY = clampedY;
          }
        }
        if (bestSpiralY !== null) {
          // While inside a spiral shaft mid-flight, return exact helix tread height so descending isn't blocked by floors below
          if (bestSpiralY > shaft.zStart + 1.2 && bestSpiralY < shaft.zEnd - 1.2) {
            return { groundY: bestSpiralY, clampedX: cx, clampedZ: cz };
          }
          consider(bestSpiralY);
        }
      }
    }

    // 6. Basilica Upper Roof Decks
    if (Math.abs(cx) <= 10.5 && cz >= -16.0 && cz <= 45.5) {
      consider(45.0);
    } else if (Math.abs(cx) <= 22.5 && cz >= -16.0 && cz <= 45.5) {
      consider(30.0);
    }
    if (Math.abs(cx) <= 30.0 && Math.abs(cz) <= 11.0) {
      consider(45.0);
    }

    // 7. 2 Walkable Gaudí Corner Helical Staircases: Nave Floor (1.2m) <-> Emporen Galleries (14.5m) at (±19.6, Z=+42.6)
    for (const sx of [-1, 1]) {
      const scx = sx * 19.6;
      const scz = 42.6;
      const dCorner = Math.hypot(cx - scx, cz - scz);
      if (dCorner >= 0.36 && dCorner <= 1.92 && feetY >= 0.4 && feetY <= 15.8) {
        const ang = Math.atan2(-(cz - scz), cx - scx);
        // Matches build_interior.py exact ang_offset (0.0 for East +X, PI for West -X) & turns = 2.5
        const rawSigned = (ang - (sx > 0 ? 0 : Math.PI)) * sx;
        const baseFrac = (((rawSigned % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2)) / (Math.PI * 2);
        const pitch = (14.5 - 1.2) / 2.5;
        const estTurn = Math.round((feetY - 1.2) / pitch - baseFrac);
        let bestCornerY: number | null = null;
        let bestDiff = Infinity;
        for (const dt of [-1, 0, 1]) {
          const candY = 1.2 + (estTurn + dt + baseFrac) * pitch;
          if (candY < 0.8 || candY > 14.9) continue;
          const clampedY = THREE.MathUtils.clamp(candY, 1.2, 14.5);
          const diff = clampedY - feetY;
          if (diff <= 1.45 && diff >= -1.55 && Math.abs(diff) < bestDiff) {
            bestDiff = Math.abs(diff);
            bestCornerY = clampedY;
          }
        }
        if (bestCornerY !== null) {
          return { groundY: bestCornerY, clampedX: cx, clampedZ: cz };
        }
      }
    }

    // 8. Elevated Choir Galleries / Emporen (Y = 14.5m) — exclude open corner spiral stairwell holes at (±19.6, Z=+42.6)!
    const inCornerHole =
      Math.hypot(cx - 19.6, cz - 42.6) < 1.82 ||
      Math.hypot(cx + 19.6, cz - 42.6) < 1.82;
    if (!inCornerHole) {
      const onSouthEmpore = cz >= 40.6 && cz <= 45.4 && Math.abs(cx) <= 18.4;
      const onEastEmpore = cx >= 16.8 && cx <= 22.4 && cz >= 13.8 && cz <= 40.8;
      const onWestEmpore = cx <= -16.8 && cx >= -22.4 && cz >= 13.8 && cz <= 40.8;
      if (onSouthEmpore || onEastEmpore || onWestEmpore) {
        consider(14.5);
      }
    }

    // 9. Eixample Apartment Rooftops (Y = 25.0m)
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
    if (feetY < -1.5 && distCrypt <= 15.6) {
      return -5.5;
    }

    // Plaça de Gaudí Reflective Pond
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
    // Stepped Baptistery Dais in East Transept (+19.2, Z=+9.8)
    const dBapt = Math.hypot(cx - 19.2, cz - 9.8);
    if (dBapt < 1.95) return 1.64;
    if (dBapt < 2.55) return 1.42;

    if (this.isOnBasilicaPodium(cx, cz)) {
      return 1.2;
    }
    // Exterior entrance steps / ramps (Nativity East, Passion West, Glory South, East/West Cloister Portals)
    if (cx > 31.8 && cx <= 37.0 && Math.abs(cz) <= 14.5) {
      return (1.0 - THREE.MathUtils.clamp((cx - 32.5) / 4.2, 0, 1)) * 1.2;
    }
    if (cx < -31.8 && cx >= -40.5 && Math.abs(cz) <= 15.0) {
      return (1.0 - THREE.MathUtils.clamp((-cx - 35.0) / 5.0, 0, 1)) * 1.2;
    }
    if (cz > 57.5 && cz <= 71.0 && Math.abs(cx) <= 19.0) {
      return (1.0 - THREE.MathUtils.clamp((cz - 58.0) / 12.5, 0, 1)) * 1.2;
    }
    if (Math.abs(cx) > 28.5 && Math.abs(cx) <= 31.2 && cz >= 25.0 && cz <= 31.2) {
      return (1.0 - THREE.MathUtils.clamp((Math.abs(cx) - 28.8) / 2.2, 0, 1)) * 1.2;
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
    const rCenter = Math.hypot(pos.x, pos.z);
    if (rCenter < 8.5 && pos.y >= 1.0 && pos.y < 134.0) {
      return THREE.MathUtils.smoothstep(134.0 - pos.y, 0.0, 6.0) * 0.92;
    }
    if (pos.y > 46.0) return 0.0;

    const naveX = THREE.MathUtils.smoothstep(25.5 - Math.abs(pos.x), 0.0, 5.5);
    const naveZ =
      THREE.MathUtils.smoothstep(pos.z - -18.0, 0.0, 5.0) *
      THREE.MathUtils.smoothstep(50.0 - pos.z, 0.0, 6.0);
    const fNave = naveX * naveZ;

    const tranX = THREE.MathUtils.smoothstep(33.5 - Math.abs(pos.x), 0.0, 6.0);
    const tranZ = THREE.MathUtils.smoothstep(16.5 - Math.abs(pos.z), 0.0, 4.0);
    const fTransept = tranX * tranZ;

    const fApse =
      THREE.MathUtils.smoothstep(21.0 - Math.hypot(pos.x, pos.z - -16.5), 0.0, 5.0) *
      THREE.MathUtils.smoothstep(-12.0 - pos.z, 0.0, 4.0);

    const fMain = Math.max(fNave, fTransept, fApse);
    if (fMain > 0.01) return Math.min(1.0, fMain);

    if (Math.abs(pos.x) < 29.5 && pos.z > -38.0 && pos.z < 47.0 && pos.y < 12.0) return 0.55;
    return 0.0;
  }

  public detectZone(pos: THREE.Vector3): string {
    const rCenter = Math.hypot(pos.x, pos.z);
    if (rCenter < 2.25 && pos.y >= 54.0 && pos.y < 138.0 && Math.abs(pos.y - 1.75 - this.elevatorFloorY) < 2.5) {
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
