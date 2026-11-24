import * as THREE from 'three';
import type { MeshBVH } from 'three-mesh-bvh';
import { t } from '../i18n';
import { LAYOUT } from '../data/layout';
import {
  CITY_BLOCK_BOXES,
  EYE_HEIGHT,
  INTERIOR_COLUMNS,
  Z_NAVE,
  analyticSupportY,
  clampToWalkBounds,
  cryptCeilingY,
  detectZoneInfo,
  indoorFactorAt,
} from './walkModel';

// three-mesh-bvh is only needed once the GLBs are in, so it is split out of the startup bundle and
// fetched in parallel with the model downloads (see CollisionSystem.preload()).
let bvhModulePromise: Promise<typeof import('three-mesh-bvh')> | null = null;
function loadBvhModule(): Promise<typeof import('three-mesh-bvh')> {
  if (!bvhModulePromise) bvhModulePromise = import('three-mesh-bvh');
  return bvhModulePromise;
}

export interface WalkConstraints {
  groundY: number;
  clampedX: number;
  clampedZ: number;
}

const CAPSULE_RADIUS = 0.34;
const CAPSULE_KNEE_Y = 0.52; // Clears all 0.12-0.36m stair treads & curbs while blocking walls/altars/pews/railings
const CAPSULE_HEAD_Y = 1.65;

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

/**
 * Meshes that collide only with their triangles lying wholly below a height, although their name contains a
 * non-collidable part. Facade_GloryAndRoofs holds the Glory wall, its tower bases and the portico columns
 * (must block) and the roof prisms / pinnacles over the 46.8 / 31.8 roof decks (must not): checked against
 * facades.glb that a cap just below the aisle roof deck keeps the decks, the five door tunnels, the porch
 * (except the columns themselves), the south gallery and the Glory entry bridges free.
 */
const COLLIDE_BELOW: Record<string, number> = {
  Facade_GloryAndRoofs: LAYOUT.levels.roofDeckAisle - 0.5,
};

function isCollidableMeshName(name: string): boolean {
  if (!name) return false;
  if (collideBelowFor(name) !== null) return true;
  // Tree foliage & lamp globe instances end with "_B"
  if (name.endsWith('_B') && (name.includes('PlaneTree') || name.includes('CypressTree') || name.includes('StreetLamp'))) {
    return false;
  }
  for (const sub of NON_COLLIDABLE_SUBSTRINGS) {
    if (name.includes(sub)) return false;
  }
  return true;
}

/** Height cap of a COLLIDE_BELOW mesh (also its auto-instanced copy "Instanced_<name>"), else null. */
function collideBelowFor(name: string): number | null {
  const base = name.startsWith('Instanced_') ? name.slice('Instanced_'.length) : name;
  return base in COLLIDE_BELOW ? COLLIDE_BELOW[base] : null;
}

export class CollisionSystem {
  public readonly eyeHeight = EYE_HEIGHT;
  public elevatorFloorY = LAYOUT.levels.jesusDeck;
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
  /** Starts fetching the BVH library early (call at boot). */
  public preload(): void {
    void loadBvhModule().catch(() => {
      bvhModulePromise = null;
    });
  }

  public async buildBVH(): Promise<{ triangles: number; meshes: number; buildMs: number }> {
    const { MeshBVH: MeshBVHImpl } = await loadBvhModule();
    const t0 = performance.now();
    const posChunks: Float32Array[] = [];
    let totalFloats = 0;
    let meshCount = 0;

    const vA = new THREE.Vector3();
    const vB = new THREE.Vector3();
    const vC = new THREE.Vector3();
    const instMat = new THREE.Matrix4();
    const worldMat = new THREE.Matrix4();

    const appendGeometry = (geo: THREE.BufferGeometry, mat: THREE.Matrix4, maxY = Infinity) => {
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
        if (vA.y >= maxY || vB.y >= maxY || vC.y >= maxY) continue;
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
      const used = cursor === out.length ? out : out.slice(0, cursor);
      posChunks.push(used);
      totalFloats += used.length;
    };

    for (const mesh of this.pendingMeshes) {
      mesh.updateMatrixWorld(true);
      const maxY = collideBelowFor(mesh.name) ?? Infinity;
      if (mesh instanceof THREE.InstancedMesh) {
        meshCount += mesh.count;
        for (let i = 0; i < mesh.count; i++) {
          mesh.getMatrixAt(i, instMat);
          worldMat.multiplyMatrices(mesh.matrixWorld, instMat);
          appendGeometry(mesh.geometry, worldMat, maxY);
        }
      } else {
        meshCount++;
        appendGeometry(mesh.geometry, mesh.matrixWorld, maxY);
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
    this.bvh = new MeshBVHImpl(geo, { targetLeafSize: 12 });
    this.bvhTriangles = totalFloats / 9;
    this.bvhReady = true;

    const buildMs = Math.round(performance.now() - t0);
    return { triangles: this.bvhTriangles, meshes: meshCount, buildMs };
  }

  /**
   * Resolves true 3D horizontal capsule collision against the static BVH (walls, columns,
   * High Altar, pews, statues, balustrades, crypt walls, cloister piers, facades, urban furniture).
   */
  // Capsule solver state shared with the pre-bound shapecast callbacks below (no per-query closures)
  private _solveX = 0;
  private _solveZ = 0;
  private _solveMoved = false;
  private readonly _shapecastCallbacks = {
    intersectsBounds: (b: THREE.Box3) => b.intersectsBox(this._capBox),
    intersectsTriangle: (tri: THREE.Triangle & { closestPointToSegment(seg: THREE.Line3, t: THREE.Vector3, s: THREE.Vector3): number }) => {
      const r = CAPSULE_RADIUS;
      const triNormal = this._triNormal;
      const triPt = this._triPt;
      const capPt = this._capPt;
      const seg = this._capSeg;
      const box = this._capBox;
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
        const x = (this._solveX += dx * inv);
        const z = (this._solveZ += dz * inv);
        this._solveMoved = true;

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
  };

  /** Result in this._solveX / this._solveZ. */
  private resolveBVHCapsuleXZ(cx: number, feetY: number, cz: number): void {
    this._solveX = cx;
    this._solveZ = cz;
    if (!this.bvh) return;

    const y0 = feetY + CAPSULE_KNEE_Y;
    const y1 = feetY + CAPSULE_HEAD_Y;
    const r = CAPSULE_RADIUS;
    const seg = this._capSeg;
    const box = this._capBox;

    // 3 solver passes guarantee smooth sliding along corners & acute masonry intersections
    for (let iter = 0; iter < 3; iter++) {
      this._solveMoved = false;
      const x = this._solveX;
      const z = this._solveZ;
      seg.start.set(x, y0, z);
      seg.end.set(x, y1, z);
      box.min.set(x - r, y0 - r, z - r);
      box.max.set(x + r, y1 + r, z + r);

      this.bvh.shapecast(this._shapecastCallbacks as unknown as Parameters<MeshBVH['shapecast']>[0]);

      if (!this._solveMoved) break;
    }
  }

  /**
   * Optional upward ceiling check so jumping in the crypt or low cloister arcades respects the vaults
   * instead of poking through the floor above.
   */
  public getCeilingY(x: number, feetY: number, z: number): number | null {
    const crypt = cryptCeilingY(x, feetY, z);
    if (crypt !== null) return crypt;
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
   * Multi-level support surface + 3D mesh BVH resolver:
   * - iterative 3D capsule-vs-mesh collision against walls, columns, altar, pews, railings & urban obstacles;
   * - then the HIGHEST walkable floor / bridge / stair / deck / roof at (x, z) below feetY + STEP_UP_MAX
   *   (analytic, see walkModel.ts; all positions from the layout).
   */
  public resolveWalkPosition(x: number, feetY: number, z: number): WalkConstraints {
    const bounded = clampToWalkBounds(x, z);
    let cx = bounded.x;
    let cz = bounded.z;

    if (this.bvhReady) {
      this.resolveBVHCapsuleXZ(cx, feetY, cz);
      cx = this._solveX;
      cz = this._solveZ;
    } else {
      // Pre-BVH analytical fallback: Eixample blocks and the interior columns
      for (const obs of CITY_BLOCK_BOXES) {
        if (feetY < obs.y - 1.0 && cx > obs.minX && cx < obs.maxX && cz > obs.minZ && cz < obs.maxZ) {
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
      if (feetY >= Z_NAVE - 1.2 && feetY < LAYOUT.levels.gallery + 5.8) {
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

    return { groundY: analyticSupportY(cx, feetY, cz, this.elevatorFloorY), clampedX: cx, clampedZ: cz };
  }

  public getIndoorFactor(pos: THREE.Vector3): number {
    return indoorFactorAt(pos.x, pos.y, pos.z);
  }

  /** Localized name of the area around pos (current UI language). */
  public detectZone(pos: THREE.Vector3): string {
    const zi = detectZoneInfo(pos.x, pos.y, pos.z, this.elevatorFloorY);
    const params: Record<string, string | number> = {};
    if (zi.y !== undefined) params.y = zi.y;
    if (zi.towerKey) params.tower = t(zi.towerKey);
    return t(zi.key, params);
  }
}
