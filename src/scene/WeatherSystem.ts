import * as THREE from 'three';

export type WeatherMode = 'clear' | 'mist' | 'rain';

/**
 * Atmospheric Weather, Sanctuary Incense & Volumetric Night Streetlamp System:
 * - 'clear': Crisp Mediterranean Golden Hour / Daylight + rising golden sanctuary incense above High Altar
 * - 'mist': Dreamy Barcelona morning mist enveloping Eixample & lower basilica spires
 * - 'rain': 1,600 GPU streak raindrops (masked cleanly OUTSIDE the cathedral!), wet reflective streets & pond ripples!
 */
export class WeatherSystem {
  public readonly group = new THREE.Group();
  public mode: WeatherMode = 'clear';
  public rainFactor = 0.0;
  public mistFactor = 0.0;

  private rainPoints: THREE.Points;
  private rainUniforms = {
    uTime: { value: 0 },
    uCamPos: { value: new THREE.Vector3() },
    uOpacity: { value: 0.0 },
  };

  private incensePoints: THREE.Points;
  private incenseUniforms = {
    uTime: { value: 0 },
    uColor: { value: new THREE.Color('#ffe8c4') },
    uOpacity: { value: 0.24 },
  };

  private lampCones: THREE.InstancedMesh;
  private lampConeMat: THREE.ShaderMaterial;
  private wetMaterials: Array<{ mat: THREE.MeshStandardMaterial; baseRoughness: number; baseEnv: number }> = [];

  constructor() {
    this.group.name = 'Atmosphere_WeatherSystem';

    // ── 1. GPU Rain Streak Volume (follows camera seamlessly, masked outside basilica footprint!) ──
    const rainCount = 1600;
    const rainPos = new Float32Array(rainCount * 3);
    const rainSeed = new Float32Array(rainCount);
    for (let i = 0; i < rainCount; i++) {
      rainPos[i * 3 + 0] = (Math.random() - 0.5) * 76.0;
      rainPos[i * 3 + 1] = Math.random() * 44.0;
      rainPos[i * 3 + 2] = (Math.random() - 0.5) * 76.0;
      rainSeed[i] = Math.random();
    }
    const rainGeo = new THREE.BufferGeometry();
    rainGeo.setAttribute('position', new THREE.BufferAttribute(rainPos, 3));
    rainGeo.setAttribute('aSeed', new THREE.BufferAttribute(rainSeed, 1));

    const rainMat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      uniforms: this.rainUniforms,
      vertexShader: /* glsl */ `
        attribute float aSeed;
        uniform float uTime;
        uniform vec3 uCamPos;
        varying float vAlpha;
        void main() {
          vec3 p = position;
          float speed = 22.0 + aSeed * 9.0;
          // Wrap rain box seamlessly around camera
          vec3 rel = mod(p + vec3(uTime * 1.4, -uTime * speed, uTime * 0.6) - uCamPos + vec3(38.0, 22.0, 38.0), vec3(76.0, 44.0, 76.0)) - vec3(38.0, 22.0, 38.0);
          vec3 wp = uCamPos + rel;

          // Keep cathedral interior & subterranean crypt completely dry!
          bool inNave = abs(wp.x) < 28.5 && wp.z > -34.0 && wp.z < 50.0 && wp.y < 54.0;
          bool inTransept = abs(wp.x) < 33.5 && abs(wp.z) < 16.5 && wp.y < 54.0;
          bool inTowerCore = length(wp.xz) < 10.5 && wp.y < 145.0;
          float dryMask = (inNave || inTransept || inTowerCore || wp.y < 0.05) ? 0.0 : 1.0;

          vec4 mvPos = viewMatrix * vec4(wp, 1.0);
          float distFade = smoothstep(42.0, 8.0, length(rel));
          vAlpha = dryMask * distFade * (0.45 + 0.45 * aSeed);
          gl_PointSize = clamp(240.0 / max(-mvPos.z, 1.0), 2.5, 14.0);
          gl_Position = projectionMatrix * mvPos;
        }
      `,
      fragmentShader: /* glsl */ `
        uniform float uOpacity;
        varying float vAlpha;
        void main() {
          if (vAlpha <= 0.01) discard;
          // Crisp vertical rain streak inside point sprite
          vec2 uv = gl_PointCoord - 0.5;
          float streakX = exp(-uv.x * uv.x * 160.0);
          float streakY = smoothstep(0.5, 0.0, abs(uv.y));
          float a = streakX * streakY * vAlpha * uOpacity;
          if (a < 0.01) discard;
          gl_FragColor = vec4(vec3(0.80, 0.88, 0.96), a);
        }
      `,
    });

    this.rainPoints = new THREE.Points(rainGeo, rainMat);
    this.rainPoints.frustumCulled = false;
    this.rainPoints.visible = false;
    this.group.add(this.rainPoints);

    // ── 2. Rising Golden Sanctuary Incense Smoke above High Altar (0, 3..24m, -17.5) ──
    const incCount = 64;
    const incPos = new Float32Array(incCount * 3);
    const incSeed = new Float32Array(incCount);
    for (let i = 0; i < incCount; i++) {
      const a = Math.random() * Math.PI * 2;
      const r = Math.random() * 1.6;
      incPos[i * 3 + 0] = Math.cos(a) * r;
      incPos[i * 3 + 1] = Math.random(); // normalized vertical phase 0..1
      incPos[i * 3 + 2] = -17.5 + Math.sin(a) * r;
      incSeed[i] = Math.random();
    }
    const incGeo = new THREE.BufferGeometry();
    incGeo.setAttribute('position', new THREE.BufferAttribute(incPos, 3));
    incGeo.setAttribute('aSeed', new THREE.BufferAttribute(incSeed, 1));

    const incMat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: this.incenseUniforms,
      vertexShader: /* glsl */ `
        attribute float aSeed;
        uniform float uTime;
        varying float vAlpha;
        void main() {
          float life = fract(position.y + uTime * (0.045 + aSeed * 0.025));
          float y = 3.2 + life * 21.0;
          float spread = 0.5 + life * 3.8;
          float swirl = uTime * 0.35 + aSeed * 6.283 + life * 3.1;
          vec3 wp = vec3(
            position.x * spread + sin(swirl) * (0.65 * life),
            y,
            position.z + cos(swirl * 0.85) * (0.65 * life)
          );
          vec4 mvPos = viewMatrix * vec4(wp, 1.0);
          float env = smoothstep(0.0, 0.18, life) * smoothstep(1.0, 0.28, life);
          vAlpha = env * (0.55 + 0.45 * aSeed);
          gl_PointSize = clamp((380.0 + life * 480.0) / max(-mvPos.z, 2.0), 12.0, 86.0);
          gl_Position = projectionMatrix * mvPos;
        }
      `,
      fragmentShader: /* glsl */ `
        uniform vec3 uColor;
        uniform float uOpacity;
        varying float vAlpha;
        void main() {
          float d = length(gl_PointCoord - 0.5) * 2.0;
          float soft = pow(clamp(1.0 - d, 0.0, 1.0), 2.2);
          gl_FragColor = vec4(uColor, soft * vAlpha * uOpacity);
        }
      `,
    });

    this.incensePoints = new THREE.Points(incGeo, incMat);
    this.incensePoints.frustumCulled = false;
    this.group.add(this.incensePoints);

    // ── 3. Warm Volumetric Night Streetlamp Cones (1 draw call for all 24 plaza & avenue lamps!) ──
    const lampCoords: Array<[number, number]> = [
      // Plaça de Gaudí & Pond Promenade
      [62, -22], [62, 0], [62, 22], [103, -22], [103, 0], [103, 22],
      // Carrer de Marina (East) & Carrer de Sardenya (West)
      [48, -32], [48, 32], [-48, -32], [-48, 32],
      // Plaça de la Sagrada Família (West)
      [-64, -22], [-64, 0], [-64, 22], [-98, -16], [-98, 16],
      // Carrer de Mallorca (South / Glory) & Provença (North)
      [-28, 66], [0, 74], [28, 66], [-28, -56], [0, -56], [28, -56],
    ];
    const coneGeo = new THREE.ConeGeometry(3.8, 6.2, 12, 1, true);
    coneGeo.translate(0, -3.1, 0);
    this.lampConeMat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
      uniforms: {
        uOpacity: { value: 0.0 },
      },
      vertexShader: /* glsl */ `
        varying vec2 vUv;
        varying vec3 vNormalV;
        varying vec3 vViewDir;
        void main() {
          vUv = uv;
          vec4 mvPos = modelViewMatrix * instanceMatrix * vec4(position, 1.0);
          vNormalV = normalize(normalMatrix * mat3(instanceMatrix) * normal);
          vViewDir = normalize(-mvPos.xyz);
          gl_Position = projectionMatrix * mvPos;
        }
      `,
      fragmentShader: /* glsl */ `
        uniform float uOpacity;
        varying vec2 vUv;
        varying vec3 vNormalV;
        varying vec3 vViewDir;
        void main() {
          float fadeY = smoothstep(0.0, 0.78, vUv.y) * smoothstep(1.0, 0.88, vUv.y);
          float edge = pow(abs(dot(normalize(vNormalV), normalize(vViewDir))), 1.45);
          gl_FragColor = vec4(vec3(1.0, 0.78, 0.42), fadeY * edge * uOpacity);
        }
      `,
    });

    this.lampCones = new THREE.InstancedMesh(coneGeo, this.lampConeMat, lampCoords.length);
    const dummy = new THREE.Object3D();
    for (let i = 0; i < lampCoords.length; i++) {
      dummy.position.set(lampCoords[i][0], 6.4, lampCoords[i][1]);
      dummy.updateMatrix();
      this.lampCones.setMatrixAt(i, dummy.matrix);
    }
    this.lampCones.instanceMatrix.needsUpdate = true;
    this.lampCones.visible = false;
    this.group.add(this.lampCones);
  }

  public registerExteriorGroundMaterials(root: THREE.Object3D): void {
    root.traverse((obj) => {
      if (!(obj instanceof THREE.Mesh) || !(obj.material instanceof THREE.MeshStandardMaterial)) return;
      const n = obj.name;
      const m = obj.material.name;
      if (
        n.includes('Streets') ||
        n.includes('Sidewalks') ||
        m.includes('Asphalt') ||
        m.includes('Panot')
      ) {
        if (!this.wetMaterials.some((w) => w.mat === obj.material)) {
          this.wetMaterials.push({
            mat: obj.material,
            baseRoughness: obj.material.roughness,
            baseEnv: obj.material.envMapIntensity ?? 1.0,
          });
        }
      }
    });
  }

  public setMode(mode: WeatherMode): void {
    this.mode = mode;
  }

  public update(
    dt: number,
    cameraPos: THREE.Vector3,
    indoorFactor: number,
    nightFactor: number,
    dayFactor: number,
    scene: THREE.Scene
  ): void {
    const safeDt = Math.min(dt, 0.1);
    this.rainUniforms.uTime.value += safeDt;
    this.incenseUniforms.uTime.value += safeDt;

    const targetRain = this.mode === 'rain' ? 1.0 : 0.0;
    const targetMist = this.mode === 'mist' ? 1.0 : 0.0;
    this.rainFactor = THREE.MathUtils.lerp(this.rainFactor, targetRain, Math.min(1, safeDt * 2.4));
    this.mistFactor = THREE.MathUtils.lerp(this.mistFactor, targetMist, Math.min(1, safeDt * 2.0));

    // Update GPU rain volume
    this.rainPoints.visible = this.rainFactor > 0.02;
    if (this.rainPoints.visible) {
      this.rainUniforms.uCamPos.value.copy(cameraPos);
      this.rainUniforms.uOpacity.value = this.rainFactor * 0.55;
    }

    // Wet reflective streets & Barcelona panot sidewalks during rain!
    for (const item of this.wetMaterials) {
      item.mat.roughness = THREE.MathUtils.lerp(item.baseRoughness, 0.13, this.rainFactor);
      item.mat.envMapIntensity = THREE.MathUtils.lerp(item.baseEnv, 1.95, this.rainFactor);
    }

    // Atmospheric fog boost during mist or rain
    if (scene.fog instanceof THREE.FogExp2) {
      const baseDensity = THREE.MathUtils.lerp(0.0012, 0.0019, nightFactor);
      const mistBoost = this.mistFactor * 0.0046 * (1.0 - indoorFactor * 0.68);
      const rainBoost = this.rainFactor * 0.0022 * (1.0 - indoorFactor * 0.72);
      scene.fog.density = baseDensity + mistBoost + rainBoost;
    }

    // Sanctuary incense visible indoors near nave/altar
    this.incensePoints.visible = indoorFactor > 0.25 && cameraPos.y > -1.0 && cameraPos.y < 52.0;
    if (this.incensePoints.visible) {
      this.incenseUniforms.uColor.value
        .set('#ffdcb0')
        .lerp(new THREE.Color('#ffaa5a'), (1.0 - nightFactor) * 0.45);
      this.incenseUniforms.uOpacity.value = THREE.MathUtils.lerp(0.14, 0.26, dayFactor);
    }

    // Night streetlamp volumetric cones
    const lampAlpha = THREE.MathUtils.smoothstep(nightFactor, 0.18, 0.75) * (0.22 + this.mistFactor * 0.18 + this.rainFactor * 0.14);
    this.lampCones.visible = lampAlpha > 0.01 && indoorFactor < 0.85;
    this.lampConeMat.uniforms.uOpacity.value = lampAlpha;
  }
}
