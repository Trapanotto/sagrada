import * as THREE from 'three';

/**
 * Animated sparkling parabolic water-jet fountain rising from the stone basin
 * in the center of the Plaça de Gaudí reflective pond (X = 82.5, Z = 0).
 */
export class FountainParticles {
  public readonly points: THREE.Points;
  private uniforms: {
    uTime: { value: number };
    uDayFactor: { value: number };
    uPixelRatio: { value: number };
  };

  constructor(count = 420) {
    const seeds = new Float32Array(count * 4); // (phase, angle, speed, radiusSpread)
    const positions = new Float32Array(count * 3);

    for (let i = 0; i < count; i++) {
      positions[i * 3] = 82.5;
      positions[i * 3 + 1] = 2.05;
      positions[i * 3 + 2] = 0.0;

      seeds[i * 4] = Math.random();                     // cycle phase [0..1]
      seeds[i * 4 + 1] = Math.random() * Math.PI * 2;   // radial angle
      seeds[i * 4 + 2] = 0.78 + Math.random() * 0.44;   // jet height variation
      seeds[i * 4 + 3] = 0.55 + Math.random() * 1.15;   // outward spread
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('aSeed', new THREE.BufferAttribute(seeds, 4));

    this.uniforms = {
      uTime: { value: 0 },
      uDayFactor: { value: 1.0 },
      uPixelRatio: { value: Math.min(window.devicePixelRatio, 2) },
    };

    const mat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.NormalBlending,
      uniforms: this.uniforms,
      vertexShader: /* glsl */ `
        attribute vec4 aSeed;
        uniform float uTime;
        uniform float uPixelRatio;
        varying float vLife;

        void main() {
          float t = fract(uTime * 0.65 + aSeed.x);
          vLife = t;
          float ang = aSeed.y;
          float vy = 5.4 * aSeed.z;
          float g = 9.4;
          float r = t * 2.55 * aSeed.w;

          vec3 p = position;
          p.x += cos(ang) * r;
          p.z += sin(ang) * r;
          p.y += vy * t - 0.5 * g * t * t;
          p.y = max(p.y, 0.19);

          vec4 mvPos = modelViewMatrix * vec4(p, 1.0);
          float dist = max(-mvPos.z, 1.0);
          // Soft expanding water-mist plumes instead of harsh tiny square dots!
          float sizeGrow = mix(0.65, 1.85, t);
          gl_PointSize = clamp((135.0 * sizeGrow * uPixelRatio) / dist, 3.5, 28.0);
          gl_Position = projectionMatrix * mvPos;
        }
      `,
      fragmentShader: /* glsl */ `
        uniform float uDayFactor;
        varying float vLife;

        void main() {
          float d = length(gl_PointCoord - vec2(0.5)) * 2.0;
          if (d > 1.0) discard;
          float soft = pow(1.0 - d, 2.3);
          float fade = smoothstep(0.0, 0.12, vLife) * smoothstep(1.0, 0.58, vLife);
          vec3 col = mix(vec3(0.52, 0.68, 0.84), vec3(0.95, 0.97, 1.0), uDayFactor);
          gl_FragColor = vec4(col, soft * fade * (0.18 + 0.34 * uDayFactor));
        }
      `,
    });

    this.points = new THREE.Points(geo, mat);
    this.points.frustumCulled = false;
  }

  public update(dt: number, dayFactor: number): void {
    this.uniforms.uTime.value += dt;
    this.uniforms.uDayFactor.value = dayFactor;
  }
}
