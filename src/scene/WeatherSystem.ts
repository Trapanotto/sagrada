import * as THREE from 'three';
import { getBootQuality } from '../utils/quality';
import { LAYOUT } from '../data/layout';
import { FOG_DENSITY_DAY, FOG_DENSITY_NIGHT } from './atmosphere';

const f = (n: number) => n.toFixed(2);
const W = LAYOUT.cloister.walks;
const COVERED_TOP = LAYOUT.cloister.floorZ + LAYOUT.cloister.height;
/** GLSL: inside one of the four covered cloister walks (runtime z = -plan y). */
const CLOISTER_GLSL = Object.values(W)
  .map(([x0, y0, x1, y1]) => `(wp.x > ${f(Math.min(x0, x1))} && wp.x < ${f(Math.max(x0, x1))} && wp.z > ${f(-Math.max(y0, y1))} && wp.z < ${f(-Math.min(y0, y1))})`)
  .join(' || ');
// Dry zone of the church: nave + apse (runtime z from behind the apse to the Glory wall), transept
const DRY_NAVE_X = LAYOUT.zones.transept[2];
const DRY_NAVE_Z0 = -(LAYOUT.apse.center[1] + LAYOUT.apse.wallOuterR + 1.25);
const DRY_NAVE_Z1 = -LAYOUT.nave.gloryInnerY + 0.75;
const DRY_TRANSEPT_X = LAYOUT.transept.halfLength + 3.5;
const DRY_TRANSEPT_Z = LAYOUT.transept.extWallY + 0.5;
/** Incense rises above the high altar from 1 m above the presbytery. */
const ALTAR = LAYOUT.presbytery.altar;
const INCENSE_BASE_Y = LAYOUT.presbytery.z + 1.0;

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
  private readonly incenseDayCol = new THREE.Color('#ffdcb0');
  private readonly incenseNightCol = new THREE.Color('#ffaa5a');
  private lastAppliedRain = -1;

  private lampCones: THREE.InstancedMesh | null = null;
  private lampConeGeo: THREE.ConeGeometry;
  private lampConeMat: THREE.ShaderMaterial;
  private lampTops: THREE.Vector3[] = [];
  private wetMaterials: Array<{ mat: THREE.MeshStandardMaterial; baseRoughness: number; baseEnv: number }> = [];

  constructor() {
    this.group.name = 'Atmosphere_WeatherSystem';

    // ── 1. GPU Rain Streak Volume (follows camera seamlessly, masked outside basilica footprint!) ──
    const quality = getBootQuality();
    const rainCount = quality.rainDrops;
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
          bool inNave = abs(wp.x) < ${f(DRY_NAVE_X)} && wp.z > ${f(DRY_NAVE_Z0)} && wp.z < ${f(DRY_NAVE_Z1)} && wp.y < 54.0;
          bool inTransept = abs(wp.x) < ${f(DRY_TRANSEPT_X)} && abs(wp.z) < ${f(DRY_TRANSEPT_Z)} && wp.y < 54.0;
          bool inTowerCore = length(wp.xz) < 10.5 && wp.y < 145.0;
          bool inCloister = wp.y < ${f(COVERED_TOP)} && (${CLOISTER_GLSL});
          // Below the sloped outdoor ground (ground_z(y) = z0 + slope * y, plan y = -z)
          bool belowGround = wp.y < ${LAYOUT.ground.z0.toFixed(3)} - ${LAYOUT.ground.slopeY.toFixed(4)} * wp.z + 0.05;
          float dryMask = (inNave || inTransept || inTowerCore || inCloister || belowGround) ? 0.0 : 1.0;

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

    // ── 2. Rising Golden Sanctuary Incense Smoke above the high altar (layout presbytery altar) ──
    const incCount = quality.incenseParticles;
    const incPos = new Float32Array(incCount * 3);
    const incSeed = new Float32Array(incCount);
    for (let i = 0; i < incCount; i++) {
      const a = Math.random() * Math.PI * 2;
      const r = Math.random() * 1.6;
      incPos[i * 3 + 0] = ALTAR[0] + Math.cos(a) * r;
      incPos[i * 3 + 1] = Math.random(); // normalized vertical phase 0..1
      incPos[i * 3 + 2] = -ALTAR[1] + Math.sin(a) * r;
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
          float y = ${f(INCENSE_BASE_Y)} + life * 21.0;
          float spread = 0.5 + life * 3.8;
          float swirl = uTime * 0.35 + aSeed * 6.283 + life * 3.1;
          vec3 wp = vec3(
            ${f(ALTAR[0])} + (position.x - ${f(ALTAR[0])}) * spread + sin(swirl) * (0.65 * life),
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

    // ── 3. Warm volumetric night streetlamp cones: one instance per street-lamp globe found in the
    //       loaded city GLB (registerStreetLamps), so they follow wherever the city package placed the lamps.
    this.lampConeGeo = new THREE.ConeGeometry(3.8, 6.2, 12, 1, true);
    this.lampConeGeo.translate(0, -3.1, 0);
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
  }

  /**
   * Places one light cone under every street-lamp globe of a loaded module (meshes named StreetLamp* ending
   * in _B, also after auto-instancing). Call once per root after optimizeWithAutoInstancing.
   */
  public registerStreetLamps(root: THREE.Object3D): void {
    root.updateMatrixWorld(true);
    const tops: THREE.Vector3[] = [];
    const box = new THREE.Box3();
    const m = new THREE.Matrix4();
    const centre = new THREE.Vector3();
    root.traverse((obj) => {
      if (!(obj instanceof THREE.Mesh) || !obj.name.includes('StreetLamp') || !obj.name.endsWith('_B')) return;
      obj.geometry.computeBoundingBox();
      const gb = obj.geometry.boundingBox;
      if (!gb) return;
      const count = obj instanceof THREE.InstancedMesh ? obj.count : 1;
      for (let i = 0; i < count; i++) {
        if (obj instanceof THREE.InstancedMesh) {
          obj.getMatrixAt(i, m);
          m.premultiply(obj.matrixWorld);
        } else {
          m.copy(obj.matrixWorld);
        }
        box.copy(gb).applyMatrix4(m);
        box.getCenter(centre);
        tops.push(new THREE.Vector3(centre.x, box.min.y, centre.z));
      }
    });
    if (!tops.length) return;
    const all = [...this.lampTops, ...tops];
    this.lampTops = all;
    if (this.lampCones) {
      this.group.remove(this.lampCones);
      this.lampCones.dispose();
    }
    const cones = new THREE.InstancedMesh(this.lampConeGeo, this.lampConeMat, all.length);
    const dummy = new THREE.Object3D();
    for (let i = 0; i < all.length; i++) {
      dummy.position.copy(all[i]);
      dummy.updateMatrix();
      cones.setMatrixAt(i, dummy.matrix);
    }
    cones.instanceMatrix.needsUpdate = true;
    cones.visible = false;
    cones.frustumCulled = false;
    this.lampCones = cones;
    this.group.add(cones);
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

    // Wet reflective streets & Barcelona panot sidewalks during rain (update only when transitioning!)
    if (Math.abs(this.rainFactor - this.lastAppliedRain) > 0.002) {
      this.lastAppliedRain = this.rainFactor;
      for (let i = 0; i < this.wetMaterials.length; i++) {
        const item = this.wetMaterials[i];
        item.mat.roughness = THREE.MathUtils.lerp(item.baseRoughness, 0.13, this.rainFactor);
        item.mat.envMapIntensity = THREE.MathUtils.lerp(item.baseEnv, 1.95, this.rainFactor);
      }
    }

    // Atmospheric fog boost during mist or rain
    if (scene.fog instanceof THREE.FogExp2) {
      const baseDensity = THREE.MathUtils.lerp(FOG_DENSITY_DAY, FOG_DENSITY_NIGHT, nightFactor);
      const mistBoost = this.mistFactor * 0.0046 * (1.0 - indoorFactor * 0.68);
      const rainBoost = this.rainFactor * 0.0022 * (1.0 - indoorFactor * 0.72);
      scene.fog.density = baseDensity + mistBoost + rainBoost;
    }

    // Sanctuary incense visible indoors near nave/altar
    this.incensePoints.visible = indoorFactor > 0.25 && cameraPos.y > LAYOUT.levels.nave - 0.5 && cameraPos.y < 48.0;
    if (this.incensePoints.visible) {
      this.incenseUniforms.uColor.value
        .copy(this.incenseDayCol)
        .lerp(this.incenseNightCol, (1.0 - nightFactor) * 0.45);
      this.incenseUniforms.uOpacity.value = THREE.MathUtils.lerp(0.14, 0.26, dayFactor);
    }

    // Night streetlamp volumetric cones
    const lampAlpha = THREE.MathUtils.smoothstep(nightFactor, 0.18, 0.75) * (0.22 + this.mistFactor * 0.18 + this.rainFactor * 0.14);
    if (this.lampCones) this.lampCones.visible = lampAlpha > 0.01 && indoorFactor < 0.85;
    this.lampConeMat.uniforms.uOpacity.value = lampAlpha;
  }
}
