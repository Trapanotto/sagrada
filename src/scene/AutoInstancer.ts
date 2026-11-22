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
