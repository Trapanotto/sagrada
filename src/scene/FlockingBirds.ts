import * as THREE from 'three';
import { LAYOUT } from '../data/layout';

const FOUNTAIN = LAYOUT.city.fountain;
const FORECOURT_X = LAYOUT.nativity.frontX + 10;

interface BirdAgent {
  centerX: number;
  centerZ: number;
  baseY: number;
  radiusX: number;
  radiusZ: number;
  speed: number;
  phase: number;
  flapSpeed: number;
  bobAmp: number;
}

/**
 * Graceful flock of white Mediterranean doves gliding over Plaça de Gaudí & the Nativity Cypress Tree.
 * GPU-instanced into 2 draw calls total (bodies + wings) with zero per-frame allocations.
 */
export class FlockingBirds {
  public readonly group = new THREE.Group();
  private birds: BirdAgent[] = [];
  private bodyInst: THREE.InstancedMesh;
  private wingInst: THREE.InstancedMesh;
  private birdDummy = new THREE.Object3D();
  private wingDummy = new THREE.Object3D();
  private wingMat = new THREE.Matrix4();
  private time = 0;

  constructor(count = 16) {
    this.group.name = 'MediterraneanDoves';

    const bodyGeo = new THREE.ConeGeometry(0.11, 0.44, 5);
    bodyGeo.rotateX(Math.PI / 2);

    const wingGeo = new THREE.BufferGeometry();
    // Swept dove wing triangle
    const wingVerts = new Float32Array([
      0.0, 0.0, 0.14,
      0.48, 0.04, -0.04,
      0.0, 0.0, -0.14,
    ]);
    wingGeo.setAttribute('position', new THREE.BufferAttribute(wingVerts, 3));
    wingGeo.computeVertexNormals();

    const mat = new THREE.MeshLambertMaterial({
      color: '#f7f4ee',
      side: THREE.DoubleSide,
    });

    this.bodyInst = new THREE.InstancedMesh(bodyGeo, mat, count);
    this.bodyInst.frustumCulled = false;
    this.wingInst = new THREE.InstancedMesh(wingGeo, mat, count * 2);
    this.wingInst.frustumCulled = false;
    this.group.add(this.bodyInst, this.wingInst);

    for (let i = 0; i < count; i++) {
      const nearTree = i < 6;
      this.birds.push({
        // Over the Nativity forecourt trees / circling the Plaça de Gaudí pond (layout)
        centerX: nearTree ? FORECOURT_X + (i % 3) * 6 : FOUNTAIN.x + (Math.random() - 0.5) * 36,
        centerZ: nearTree ? (Math.random() - 0.5) * 14 : -FOUNTAIN.y + (Math.random() - 0.5) * 40,
        baseY: nearTree ? 34 + Math.random() * 18 : 14 + Math.random() * 16,
        radiusX: nearTree ? 12 + Math.random() * 10 : 18 + Math.random() * 16,
        radiusZ: nearTree ? 14 + Math.random() * 10 : 16 + Math.random() * 18,
        speed: (0.24 + Math.random() * 0.18) * (i % 2 === 0 ? 1 : -1),
        phase: Math.random() * Math.PI * 2,
        flapSpeed: 5.5 + Math.random() * 2.5,
        bobAmp: 1.2 + Math.random() * 2.0,
      });
    }

    this.update(0, 1.0);
  }

  public update(dt: number, dayFactor: number): void {
    this.time += dt;
    // Doves roost at night
    this.group.visible = dayFactor > 0.12;
    if (!this.group.visible) return;

    for (let i = 0; i < this.birds.length; i++) {
      const b = this.birds[i];
      const a = this.time * b.speed + b.phase;
      const aNext = a + b.speed * 0.05;

      const x = b.centerX + Math.cos(a) * b.radiusX;
      const z = b.centerZ + Math.sin(a) * b.radiusZ;
      const y = b.baseY + Math.sin(a * 2.0 + b.phase) * b.bobAmp;

      const nx = b.centerX + Math.cos(aNext) * b.radiusX;
      const nz = b.centerZ + Math.sin(aNext) * b.radiusZ;
      const ny = b.baseY + Math.sin(aNext * 2.0 + b.phase) * b.bobAmp;

      this.birdDummy.position.set(x, y, z);
      this.birdDummy.lookAt(nx, ny, nz);
      this.birdDummy.updateMatrix();
      this.bodyInst.setMatrixAt(i, this.birdDummy.matrix);

      // Periodic calm gliding interspersed with gentle wingbeats
      const glideCycle = Math.sin(this.time * 0.8 + b.phase * 2.0);
      const flapAmp = glideCycle > -0.25 ? 0.58 : 0.08;
      const flap = Math.sin(this.time * b.flapSpeed + b.phase) * flapAmp;

      this.wingDummy.position.set(0, 0, 0);
      this.wingDummy.rotation.set(0, 0, -flap);
      this.wingDummy.scale.set(-1, 1, 1);
      this.wingDummy.updateMatrix();
      this.wingMat.multiplyMatrices(this.birdDummy.matrix, this.wingDummy.matrix);
      this.wingInst.setMatrixAt(i * 2, this.wingMat);

      this.wingDummy.rotation.set(0, 0, flap);
      this.wingDummy.scale.set(1, 1, 1);
      this.wingDummy.updateMatrix();
      this.wingMat.multiplyMatrices(this.birdDummy.matrix, this.wingDummy.matrix);
      this.wingInst.setMatrixAt(i * 2 + 1, this.wingMat);
    }

    this.bodyInst.instanceMatrix.needsUpdate = true;
    this.wingInst.instanceMatrix.needsUpdate = true;
  }
}
