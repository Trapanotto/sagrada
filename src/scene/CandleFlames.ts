import * as THREE from 'three';

/**
 * GPU-Instanced Flickering Sanctuary & Crypt Candle Flames + Soft Warm Halos.
 * Uses only 2 draw calls total and 0 per-frame CPU updates (all flicker runs in GLSL!).
 */
export class CandleFlames {
  public readonly group = new THREE.Group();
  private readonly timeUniform = { value: 0 };

  constructor() {
    this.group.name = 'Sanctuary_CandleFlames';

    const positions: Array<[number, number, number, number]> = [];

    // 1. High Altar & Presbytery Candelabras (Y = 2.4m platform + altar/stand height)
    const altarCandles: Array<[number, number, number]> = [
      [-2.5, 4.15, -18.2],
      [-1.9, 4.22, -18.2],
      [-1.3, 4.15, -18.2],
      [1.3, 4.15, -18.2],
      [1.9, 4.22, -18.2],
      [2.5, 4.15, -18.2],
      [-5.4, 3.85, -15.6],
      [-5.1, 3.92, -15.9],
      [-5.7, 3.82, -15.9],
      [5.4, 3.85, -15.6],
      [5.1, 3.92, -15.9],
      [5.7, 3.82, -15.9],
    ];
    for (const [x, y, z] of altarCandles) {
      positions.push([x, y, z, 1.15]);
    }

    // 2. 7 Apse Chapels Votive Candle Racks along the North Semicircle (center 0, Z=-16.5, r=14.6m)
    for (let i = 0; i < 7; i++) {
      const ang = -Math.PI * 0.14 - (i / 6) * Math.PI * 0.72;
      const cx = Math.cos(ang) * 14.4;
      const cz = -16.5 + Math.sin(ang) * 14.4;
      for (let k = -2; k <= 2; k++) {
        const perpX = -Math.sin(ang) * k * 0.26;
        const perpZ = Math.cos(ang) * k * 0.26;
        positions.push([cx + perpX, 2.38 + (k % 2 === 0 ? 0.07 : 0.0), cz + perpZ, 0.85]);
      }
    }

    // 3. Nave Crossing & Side Altar Votive Stands
    for (const sx of [-1, 1]) {
      for (let k = 0; k < 4; k++) {
        positions.push([sx * 16.5, 2.32 + (k % 2) * 0.06, 12.0 + k * 0.28, 0.82]);
        positions.push([sx * 16.5, 2.32 + (k % 2) * 0.06, 28.0 + k * 0.28, 0.82]);
      }
    }

    // 4. Subterranean Crypt Sanctuary & Antoni Gaudí's Tomb (Y = -5.5m floor)
    const cryptCandles: Array<[number, number, number]> = [
      // Central Crypt High Altar
      [-1.4, -3.65, -21.0],
      [-0.7, -3.58, -21.0],
      [0.7, -3.58, -21.0],
      [1.4, -3.65, -21.0],
      // Antoni Gaudí's Tomb Chapel (Capilla del Carmen at (-9.5, -5.5, -23.5))
      [-9.9, -4.15, -23.1],
      [-9.5, -4.08, -23.0],
      [-9.1, -4.15, -23.1],
      [-10.2, -4.22, -23.8],
      [-8.8, -4.22, -23.8],
      // Flanking Crypt Chapels
      [8.5, -4.15, -23.0],
      [8.9, -4.08, -23.3],
      [0.0, -4.12, -31.8],
      [0.4, -4.16, -31.7],
      [-0.4, -4.16, -31.7],
    ];
    for (const [x, y, z] of cryptCandles) {
      positions.push([x, y, z, 1.05]);
    }

    const count = positions.length;

    // Teardrop 3D flame geometry
    const flameGeo = new THREE.ConeGeometry(0.055, 0.22, 7, 1);
    flameGeo.translate(0, 0.11, 0);

    const flameMat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: this.timeUniform,
      },
      vertexShader: /* glsl */ `
        uniform float uTime;
        varying float vH;
        varying float vFlicker;
        void main() {
          vec4 worldOrigin = modelMatrix * instanceMatrix * vec4(0.0, 0.0, 0.0, 1.0);
          float phase = worldOrigin.x * 3.7 + worldOrigin.z * 5.3 + worldOrigin.y * 2.1;
          float flick = 0.88 + 0.14 * sin(uTime * 7.8 + phase) + 0.09 * sin(uTime * 15.3 + phase * 1.7);
          vFlicker = flick;
          vH = clamp(position.y / 0.22, 0.0, 1.0);

          vec3 p = position;
          // Gentle horizontal candle-draft sway toward the tip
          p.x += sin(uTime * 5.4 + phase) * 0.022 * vH;
          p.z += cos(uTime * 4.6 + phase * 1.3) * 0.018 * vH;
          p.y *= flick;

          vec4 mvPos = modelViewMatrix * instanceMatrix * vec4(p, 1.0);
          gl_Position = projectionMatrix * mvPos;
        }
      `,
      fragmentShader: /* glsl */ `
        varying float vH;
        varying float vFlicker;
        void main() {
          vec3 core = vec3(1.0, 0.96, 0.80);
          vec3 mid = vec3(1.0, 0.62, 0.14);
          vec3 tip = vec3(0.95, 0.28, 0.04);
          vec3 col = mix(core, mid, smoothstep(0.08, 0.55, vH));
          col = mix(col, tip, smoothstep(0.55, 1.0, vH));
          float alpha = (1.0 - smoothstep(0.72, 1.0, vH)) * 0.95;
          gl_FragColor = vec4(col * (1.55 * vFlicker), alpha);
        }
      `,
    });

    const flameMesh = new THREE.InstancedMesh(flameGeo, flameMat, count);
    flameMesh.frustumCulled = false;

    // Soft spherical warm halo sprite around each flame (camera-facing billboard in vertex shader!)
    const haloGeo = new THREE.PlaneGeometry(0.68, 0.68);
    const haloMat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: this.timeUniform,
      },
      vertexShader: /* glsl */ `
        uniform float uTime;
        varying vec2 vUv;
        varying float vFlicker;
        void main() {
          vUv = uv;
          vec4 worldCenter = modelMatrix * instanceMatrix * vec4(0.0, 0.11, 0.0, 1.0);
          float phase = worldCenter.x * 3.7 + worldCenter.z * 5.3 + worldCenter.y * 2.1;
          vFlicker = 0.85 + 0.15 * sin(uTime * 6.9 + phase) + 0.08 * sin(uTime * 13.7 + phase * 1.4);

          // Billboard quad in view space
          vec4 mvCenter = viewMatrix * worldCenter;
          float scale = length(vec3(instanceMatrix[0][0], instanceMatrix[0][1], instanceMatrix[0][2]));
          mvCenter.xy += position.xy * scale * vFlicker;
          gl_Position = projectionMatrix * mvCenter;
        }
      `,
      fragmentShader: /* glsl */ `
        varying vec2 vUv;
        varying float vFlicker;
        void main() {
          float d = length(vUv - 0.5) * 2.0;
          float glow = pow(clamp(1.0 - d, 0.0, 1.0), 2.6);
          vec3 col = mix(vec3(1.0, 0.52, 0.12), vec3(1.0, 0.88, 0.55), glow);
          gl_FragColor = vec4(col * 0.72 * vFlicker, glow * 0.42);
        }
      `,
    });

    const haloMesh = new THREE.InstancedMesh(haloGeo, haloMat, count);
    haloMesh.frustumCulled = false;

    const dummy = new THREE.Object3D();
    for (let i = 0; i < count; i++) {
      const [x, y, z, s] = positions[i];
      dummy.position.set(x, y, z);
      dummy.scale.setScalar(s);
      dummy.updateMatrix();
      flameMesh.setMatrixAt(i, dummy.matrix);
      haloMesh.setMatrixAt(i, dummy.matrix);
    }
    flameMesh.instanceMatrix.needsUpdate = true;
    haloMesh.instanceMatrix.needsUpdate = true;

    this.group.add(flameMesh);
    this.group.add(haloMesh);
  }

  public update(dt: number): void {
    this.timeUniform.value += dt;
  }
}
