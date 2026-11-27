import * as THREE from 'three';

export interface InstancingStats {
  instancedMeshCount: number;
  originalMeshCount: number;
  savedDrawCalls: number;
}

/**
 * Automatically collapses repeated GLB meshes sharing the exact same (BufferGeometry, Material)
 * into GPU-instanced THREE.InstancedMesh objects, dramatically reducing draw calls.
 */
export function optimizeWithAutoInstancing(root: THREE.Object3D): InstancingStats {
  root.updateMatrixWorld(true);

  const groups = new Map<string, THREE.Mesh[]>();
  const allMeshes: THREE.Mesh[] = [];

  root.traverse((obj) => {
    if (obj instanceof THREE.Mesh && !(obj instanceof THREE.InstancedMesh) && !Array.isArray(obj.material)) {
      allMeshes.push(obj);
      const key = `${obj.geometry.uuid}::${obj.material.uuid}`;
      let list = groups.get(key);
      if (!list) {
        list = [];
        groups.set(key, list);
      }
      list.push(obj);
    }
  });

  let instancedMeshCount = 0;
  let savedDrawCalls = 0;
  const invRoot = new THREE.Matrix4().copy(root.matrixWorld).invert();
  const relMat = new THREE.Matrix4();

  for (const meshes of groups.values()) {
    if (meshes.length < 2) continue;

    const template = meshes[0];
    const inst = new THREE.InstancedMesh(template.geometry, template.material, meshes.length);
    inst.name = `Instanced_${template.name}`;
    inst.castShadow = template.castShadow;
    inst.receiveShadow = template.receiveShadow;

    for (let i = 0; i < meshes.length; i++) {
      const m = meshes[i];
      relMat.multiplyMatrices(invRoot, m.matrixWorld);
      inst.setMatrixAt(i, relMat);
      m.parent?.remove(m);
    }

    inst.instanceMatrix.needsUpdate = true;
    inst.computeBoundingSphere();
    inst.computeBoundingBox();
    root.add(inst);

    instancedMeshCount++;
    savedDrawCalls += meshes.length - 1;
  }

  return {
    instancedMeshCount,
    originalMeshCount: allMeshes.length,
    savedDrawCalls,
  };
}

/** Layer no camera renders: the source InstancedMeshes stay in the scene graph but only their proxies draw. */
const HIDDEN_LAYER = 31;

interface CulledSet {
  source: THREE.InstancedMesh;
  proxy: THREE.InstancedMesh;
  /** World-space bounding sphere per instance: x, y, z, r. */
  spheres: Float32Array;
  /** Full instance matrices (source order). */
  matrices: Float32Array;
  /** Instance indices currently uploaded to the proxy, -1 = full set. */
  uploaded: Int32Array;
  uploadedCount: number;
  scratch: Int32Array;
}

/**
 * Per-instance frustum culling for the auto-instanced props (trees, benches, lamps, pews, nave columns,
 * pinnacles). three.js culls an InstancedMesh as a whole against one bounding sphere spanning all its
 * instances (e.g. 41 plane trees across 150 m), so every instance is drawn whenever any is visible.
 *
 * Each source mesh keeps its full data (collision, timeline and name lookups use it) but is moved to a
 * layer no camera renders; a child proxy sharing geometry + material draws only the instances inside
 * the main view frustum or its mirror image in the pond (planar reflection). Shadow-map updates and the
 * interior cube probe see every instance ({@link showAll}). The uploaded instance set only changes when
 * the visible set does, so a still camera costs no uploads.
 */
export class InstanceCuller {
  private sets: CulledSet[] = [];
  private readonly sphere = new THREE.Sphere();
  private readonly m = new THREE.Matrix4();
  private readonly c = new THREE.Vector3();

  constructor(roots: THREE.Object3D[], minInstances = 3) {
    const sources: THREE.InstancedMesh[] = [];
    for (const root of roots) {
      root.traverse((o) => {
        if (o instanceof THREE.InstancedMesh && o.name.startsWith('Instanced_') && o.count >= minInstances) sources.push(o);
      });
    }
    for (const source of sources) {
      source.updateMatrixWorld(true);
      const geo = source.geometry;
      if (!geo.boundingSphere) geo.computeBoundingSphere();
      const n = source.count;
      const spheres = new Float32Array(n * 4);
      for (let i = 0; i < n; i++) {
        source.getMatrixAt(i, this.m);
        this.m.premultiply(source.matrixWorld);
        this.sphere.copy(geo.boundingSphere!).applyMatrix4(this.m);
        spheres[i * 4] = this.sphere.center.x;
        spheres[i * 4 + 1] = this.sphere.center.y;
        spheres[i * 4 + 2] = this.sphere.center.z;
        spheres[i * 4 + 3] = this.sphere.radius;
      }
      const proxy = new THREE.InstancedMesh(geo, source.material, n);
      proxy.name = `${source.name}_culled`;
      proxy.castShadow = source.castShadow;
      proxy.receiveShadow = source.receiveShadow;
      proxy.renderOrder = source.renderOrder;
      (proxy.instanceMatrix.array as Float32Array).set(source.instanceMatrix.array as Float32Array);
      proxy.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      // Conservative bounds of the full set (three's per-object culling stays valid for any subset)
      if (!source.boundingSphere) source.computeBoundingSphere();
      proxy.boundingSphere = source.boundingSphere!.clone();
      source.add(proxy);
      source.layers.set(HIDDEN_LAYER);
      this.sets.push({
        source,
        proxy,
        spheres,
        matrices: (source.instanceMatrix.array as Float32Array).slice(0, n * 16),
        uploaded: new Int32Array(n).fill(-1),
        uploadedCount: -1,
        scratch: new Int32Array(n),
      });
    }
  }

  public get meshCount(): number {
    return this.sets.length;
  }

  /** Upload every instance (before shadow-map updates and the 360° interior probe). */
  public showAll(): void {
    for (const s of this.sets) {
      s.proxy.material = s.source.material;
      if (s.uploadedCount === -1 || s.uploadedCount === s.source.count) continue;
      const n = s.source.count;
      (s.proxy.instanceMatrix.array as Float32Array).set(s.matrices);
      s.proxy.instanceMatrix.clearUpdateRanges();
      s.proxy.instanceMatrix.needsUpdate = true;
      s.proxy.count = n;
      s.uploadedCount = -1;
    }
  }

  /**
   * Keep the instances whose sphere touches the main frustum, or whose mirror image across the water
   * plane y = mirrorY does (the pond reflection), when mirrorY is not null.
   */
  public update(frustum: THREE.Frustum, mirrorY: number | null): void {
    const sphere = this.sphere;
    for (const s of this.sets) {
      // Follows the timeline's clipped material swap
      s.proxy.material = s.source.material;
      if (!s.source.visible) continue; // zone-culled as a whole: keep the last upload
      const n = s.source.count;
      const sp = s.spheres;
      let k = 0;
      for (let i = 0; i < n; i++) {
        sphere.center.set(sp[i * 4], sp[i * 4 + 1], sp[i * 4 + 2]);
        sphere.radius = sp[i * 4 + 3];
        let visible = frustum.intersectsSphere(sphere);
        if (!visible && mirrorY !== null) {
          sphere.center.y = 2 * mirrorY - sphere.center.y;
          visible = frustum.intersectsSphere(sphere);
        }
        if (visible) s.scratch[k++] = i;
      }
      // Unchanged set -> nothing to upload
      let same = k === s.uploadedCount;
      for (let j = 0; same && j < k; j++) same = s.uploaded[j] === s.scratch[j];
      if (same) continue;
      if (k === n) {
        this.uploadFull(s);
        continue;
      }
      const dst = s.proxy.instanceMatrix.array as Float32Array;
      for (let j = 0; j < k; j++) {
        const i = s.scratch[j];
        dst.set(s.matrices.subarray(i * 16, i * 16 + 16), j * 16);
        s.uploaded[j] = i;
      }
      s.proxy.count = k;
      s.uploadedCount = k;
      s.proxy.instanceMatrix.clearUpdateRanges();
      if (k > 0) {
        s.proxy.instanceMatrix.addUpdateRange(0, k * 16);
        s.proxy.instanceMatrix.needsUpdate = true;
      }
    }
  }

  private uploadFull(s: CulledSet): void {
    const n = s.source.count;
    (s.proxy.instanceMatrix.array as Float32Array).set(s.matrices);
    s.proxy.instanceMatrix.clearUpdateRanges();
    s.proxy.instanceMatrix.needsUpdate = true;
    s.proxy.count = n;
    for (let i = 0; i < n; i++) s.uploaded[i] = i;
    s.uploadedCount = n;
  }
}
