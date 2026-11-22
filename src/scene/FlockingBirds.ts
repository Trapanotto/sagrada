import * as THREE from 'three';

interface BirdAgent {
  group: THREE.Group;
  leftWing: THREE.Mesh;
  rightWing: THREE.Mesh;
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
 */
export class FlockingBirds {
  public readonly group = new THREE.Group();
  private birds: BirdAgent[] = [];
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

    const mat = new THREE.MeshStandardMaterial({
      color: '#f7f4ee',
      roughness: 0.72,
      side: THREE.DoubleSide,
    });

    for (let i = 0; i < count; i++) {
      const bird = new THREE.Group();
      const body = new THREE.Mesh(bodyGeo, mat);
      bird.add(body);

      const leftWing = new THREE.Mesh(wingGeo, mat);
      leftWing.scale.x = -1;
      bird.add(leftWing);

      const rightWing = new THREE.Mesh(wingGeo, mat);
      bird.add(rightWing);

      this.group.add(bird);

      const nearTree = i < 6;
      this.birds.push({
        group: bird,
        leftWing,
        rightWing,
        centerX: nearTree ? 52 + (i % 3) * 6 : 82 + (Math.random() - 0.5) * 18,
        centerZ: nearTree ? (Math.random() - 0.5) * 14 : (Math.random() - 0.5) * 28,
        baseY: nearTree ? 34 + Math.random() * 18 : 14 + Math.random() * 16,
        radiusX: nearTree ? 12 + Math.random() * 10 : 18 + Math.random() * 16,
        radiusZ: nearTree ? 14 + Math.random() * 10 : 16 + Math.random() * 18,
        speed: (0.24 + Math.random() * 0.18) * (i % 2 === 0 ? 1 : -1),
        phase: Math.random() * Math.PI * 2,
        flapSpeed: 5.5 + Math.random() * 2.5,
        bobAmp: 1.2 + Math.random() * 2.0,
      });
    }
  }

  public update(dt: number, dayFactor: number): void {
    this.time += dt;
    // Doves roost at night
    this.group.visible = dayFactor > 0.12;
    if (!this.group.visible) return;

    for (const b of this.birds) {
      const a = this.time * b.speed + b.phase;
      const aNext = a + b.speed * 0.05;

      const x = b.centerX + Math.cos(a) * b.radiusX;
      const z = b.centerZ + Math.sin(a) * b.radiusZ;
      const y = b.baseY + Math.sin(a * 2.0 + b.phase) * b.bobAmp;

      const nx = b.centerX + Math.cos(aNext) * b.radiusX;
      const nz = b.centerZ + Math.sin(aNext) * b.radiusZ;
      const ny = b.baseY + Math.sin(aNext * 2.0 + b.phase) * b.bobAmp;

      b.group.position.set(x, y, z);
      b.group.lookAt(nx, ny, nz);

      // Periodic calm gliding interspersed with gentle wingbeats
      const glideCycle = Math.sin(this.time * 0.8 + b.phase * 2.0);
      const flapAmp = glideCycle > -0.25 ? 0.58 : 0.08;
      const flap = Math.sin(this.time * b.flapSpeed + b.phase) * flapAmp;
      b.leftWing.rotation.z = -flap;
      b.rightWing.rotation.z = flap;
    }
  }
}
