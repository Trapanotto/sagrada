import * as THREE from 'three';

export interface CandleManifest {
  [group: string]: Array<[number, number, number, number]>;
}

/**
 * GPU-Instanced Flickering Sanctuary & Crypt Candle Flames + Soft Warm Halos.
 * Positions are exported directly from the Blender furnishing & crypt builders
 * (public/data/candles.json) so every flame sits with 0.0 mm precision on its wick!
 * Uses only 2 draw calls total and 0 per-frame CPU updates (all flicker runs in GLSL).
 */
export class CandleFlames {
  public readonly group = new THREE.Group();
  private readonly timeUniform = { value: 0 };
  private flameMesh: THREE.InstancedMesh | null = null;
  private haloMesh: THREE.InstancedMesh | null = null;

  constructor() {
    this.group.name = 'Sanctuary_CandleFlames';
  }

  public async loadFromManifest(url = './data/candles.json'): Promise<number> {
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`Failed to load candle manifest (${res.status})`);
    }
    const manifest = (await res.json()) as CandleManifest;
    const positions: Array<[number, number, number, number]> = [];
    for (const entries of Object.values(manifest)) {
      if (Array.isArray(entries)) {
        for (const entry of entries) {
          if (Array.isArray(entry) && entry.length >= 4) {
            positions.push([entry[0], entry[1], entry[2], entry[3]]);
          }
        }
      }
    }
    this.buildInstances(positions);
    return positions.length;
  }

  private buildInstances(positions: Array<[number, number, number, number]>): void {
    if (this.flameMesh) {
      this.group.remove(this.flameMesh);
      this.flameMesh.geometry.dispose();
      (this.flameMesh.material as THREE.Material).dispose();
      this.flameMesh = null;
    }
    if (this.haloMesh) {
      this.group.remove(this.haloMesh);
      this.haloMesh.geometry.dispose();
      (this.haloMesh.material as THREE.Material).dispose();
      this.haloMesh = null;
    }

    const count = positions.length;
    if (count === 0) return;

    // Slender organic teardrop candle flame (origin exactly at wick base!)
    const flameGeo = new THREE.ConeGeometry(0.032, 0.155, 8, 2);
    flameGeo.translate(0, 0.0775, 0);

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
          float flick = 0.89 + 0.13 * sin(uTime * 7.8 + phase) + 0.08 * sin(uTime * 15.3 + phase * 1.7);
          vFlicker = flick;
          vH = clamp(position.y / 0.155, 0.0, 1.0);

          // Organic teardrop bulge near the base, tapering sharply to the tip
          float bulge = 1.0 + 0.35 * sin(vH * 3.14159) * (1.0 - vH * 0.5);
          vec3 p = position;
          p.xz *= bulge;
          // Gentle horizontal candle-draft sway toward the tip
          p.x += sin(uTime * 5.4 + phase) * 0.015 * vH;
          p.z += cos(uTime * 4.6 + phase * 1.3) * 0.012 * vH;
          p.y *= flick;

          vec4 mvPos = modelViewMatrix * instanceMatrix * vec4(p, 1.0);
          gl_Position = projectionMatrix * mvPos;
        }
      `,
      fragmentShader: /* glsl */ `
        varying float vH;
        varying float vFlicker;
        void main() {
          vec3 blueBase = vec3(0.45, 0.65, 1.0);
          vec3 core = vec3(1.0, 0.97, 0.82);
          vec3 mid = vec3(1.0, 0.64, 0.16);
          vec3 tip = vec3(0.95, 0.28, 0.04);
          vec3 col = mix(blueBase, core, smoothstep(0.0, 0.16, vH));
          col = mix(col, mid, smoothstep(0.18, 0.62, vH));
          col = mix(col, tip, smoothstep(0.62, 1.0, vH));
          float alpha = (1.0 - smoothstep(0.74, 1.0, vH)) * 0.94;
          gl_FragColor = vec4(col * (1.45 * vFlicker), alpha);
        }
      `,
    });

    const flameMesh = new THREE.InstancedMesh(flameGeo, flameMat, count);
    flameMesh.frustumCulled = false;

    // Soft spherical warm halo sprite around each flame (camera-facing billboard in vertex shader)
    const haloGeo = new THREE.PlaneGeometry(0.44, 0.44);
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
          vec4 worldCenter = modelMatrix * instanceMatrix * vec4(0.0, 0.08, 0.0, 1.0);
          float phase = worldCenter.x * 3.7 + worldCenter.z * 5.3 + worldCenter.y * 2.1;
          vFlicker = 0.86 + 0.14 * sin(uTime * 6.9 + phase) + 0.07 * sin(uTime * 13.7 + phase * 1.4);

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
          float glow = pow(clamp(1.0 - d, 0.0, 1.0), 2.8);
          vec3 col = mix(vec3(1.0, 0.52, 0.12), vec3(1.0, 0.90, 0.60), glow);
          gl_FragColor = vec4(col * 0.82 * vFlicker, glow * 0.46);
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

    this.flameMesh = flameMesh;
    this.haloMesh = haloMesh;
    this.group.add(flameMesh);
    this.group.add(haloMesh);
  }

  public update(dt: number): void {
    this.timeUniform.value += dt;
  }
}
