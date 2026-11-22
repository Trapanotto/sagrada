import * as THREE from 'three';

/**
 * GPU-animated drifting dust & incense light motes inside the cathedral nave & crossing.
 * Reacts dynamically to morning East (turquoise/emerald) and afternoon West (amber/gold) sunbeams.
 */
export class AtmosphericParticles {
  public readonly points: THREE.Points;
  private uniforms: {
    uTime: { value: number };
    uEastIntensity: { value: number };
    uWestIntensity: { value: number };
    uDayFactor: { value: number };
    uPixelRatio: { value: number };
  };

  constructor(count = 950) {
    const positions = new Float32Array(count * 3);
    const phases = new Float32Array(count);
    const sizes = new Float32Array(count);

    for (let i = 0; i < count; i++) {
      // Distribute organically throughout the 5-aisle nave, transept & crossing
      const inCrossing = i < count * 0.25;
      const x = inCrossing ? (Math.random() - 0.5) * 32 : (Math.random() - 0.5) * 41;
      const y = 2.2 + Math.random() * (inCrossing ? 42 : 31);
      const z = inCrossing ? (Math.random() - 0.5) * 28 : 4 + Math.random() * 39;
      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;
      phases[i] = Math.random() * Math.PI * 2;
      sizes[i] = 0.65 + Math.random() * 1.45;
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
    geo.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1));

    this.uniforms = {
      uTime: { value: 0 },
      uEastIntensity: { value: 0.7 },
      uWestIntensity: { value: 0.3 },
      uDayFactor: { value: 1.0 },
      uPixelRatio: { value: Math.min(window.devicePixelRatio, 2) },
    };

    const mat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: this.uniforms,
      vertexShader: /* glsl */ `
        attribute float aPhase;
        attribute float aSize;
        uniform float uTime;
        uniform float uPixelRatio;
        varying vec3 vWorldPos;
        varying float vTwinkle;

        void main() {
          vec3 p = position;
          // Gentle cathedral air convection drift
          p.x += sin(uTime * 0.22 + aPhase) * 0.75;
          p.y += mod(uTime * 0.14 + aPhase * 3.0, 12.0) - 6.0;
          p.z += cos(uTime * 0.18 + aPhase * 1.3) * 0.75;

          vec4 wp = modelMatrix * vec4(p, 1.0);
          vWorldPos = wp.xyz;
          vTwinkle = 0.55 + 0.45 * sin(uTime * 1.4 + aPhase * 5.0);

          vec4 mvPos = viewMatrix * wp;
          float dist = max(-mvPos.z, 1.0);
          gl_PointSize = clamp((aSize * 46.0 * uPixelRatio) / dist, 1.5, 11.0);
          gl_Position = projectionMatrix * mvPos;
        }
      `,
      fragmentShader: /* glsl */ `
        uniform float uEastIntensity;
        uniform float uWestIntensity;
        uniform float uDayFactor;
        varying vec3 vWorldPos;
        varying float vTwinkle;

        void main() {
          float d = length(gl_PointCoord - vec2(0.5));
          if (d > 0.5) discard;
          float soft = pow(smoothstep(0.5, 0.0, d), 1.8);

          // East side glows cool turquoise/emerald in morning sun; West side glows warm ruby/gold in evening sun
          float eastWeight = smoothstep(-4.0, 18.0, vWorldPos.x) * uEastIntensity;
          float westWeight = smoothstep(4.0, -18.0, vWorldPos.x) * uWestIntensity;
          float centerWeight = (1.0 - smoothstep(0.0, 14.0, abs(vWorldPos.x))) * 0.35;

          vec3 colEast = vec3(0.32, 0.90, 0.86);
          vec3 colWest = vec3(1.00, 0.62, 0.24);
          vec3 colGold = vec3(1.00, 0.91, 0.70);

          vec3 col = colGold * centerWeight + colEast * eastWeight + colWest * westWeight;
          float lum = clamp(eastWeight + westWeight + centerWeight * 0.5, 0.0, 1.0);
          float alpha = soft * vTwinkle * lum * (0.14 + 0.42 * uDayFactor);
          gl_FragColor = vec4(col, alpha);
        }
      `,
    });

    this.points = new THREE.Points(geo, mat);
    this.points.frustumCulled = false;
  }

  public update(dt: number, eastSunHit: number, westSunHit: number, dayFactor: number): void {
    this.uniforms.uTime.value += dt;
    this.uniforms.uEastIntensity.value = eastSunHit;
    this.uniforms.uWestIntensity.value = westSunHit;
    this.uniforms.uDayFactor.value = dayFactor;
  }
}
