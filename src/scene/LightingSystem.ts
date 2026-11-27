import * as THREE from 'three';
import { LAYOUT, planToWorld, planRectToWorld } from '../data/layout';
import { isEyeUnderground, isNearCryptLevel } from './walkModel';
import { FOG_DENSITY_DAY, FOG_DENSITY_NIGHT, SUN_SHADOW_FAR, SUN_SHADOW_HALF_EXTENT } from './atmosphere';
import { RGBELoader } from 'three/examples/jsm/loaders/RGBELoader.js';
import { AtmosphericParticles } from './AtmosphericParticles';
import { getBootQuality, QualitySettings } from '../utils/quality';

interface TrackedMaterials {
  east: THREE.MeshStandardMaterial[];
  west: THREE.MeshStandardMaterial[];
  apse: THREE.MeshStandardMaterial[];
  star: THREE.MeshStandardMaterial[];
  cross: THREE.MeshStandardMaterial[];
  lamps: THREE.MeshStandardMaterial[];
}


const LIGHTS = LAYOUT.lights;
/** Stained-glass projector x (east = +, west mirrored) and the nave bay z they light. */
const PROJ_X = LIGHTS.eastProjector.pos[0];
const PROJ_Z = -LIGHTS.eastProjector.pos[1];
const CRYPT_ACCENT = planToWorld(...LIGHTS.cryptAccent.pos);
/** Interior lights stay on inside the Sagrada block (+ 8 m beyond the Glory porch). */
const NEAR_INTERIOR = (() => {
  const b = planRectToWorld([LAYOUT.block.west, LAYOUT.block.south, LAYOUT.block.east, LAYOUT.block.north]);
  return { maxX: b.maxX, minZ: b.minZ - 4, maxZ: b.maxZ + 8 };
})();
export class LightingSystem {
  public readonly sunLight: THREE.DirectionalLight;
  public readonly hemiLight: THREE.HemisphereLight;
  public readonly skyMesh: THREE.Mesh;
  public readonly particles: AtmosphericParticles;
  public readonly sunDir = new THREE.Vector3(0.6, 0.7, 0.2);

  public timeHours = 18.08;
  public dayFactor = 1.0;
  public nightFactor = 0.0;
  public eastSunHit = 0.0;
  public westSunHit = 0.85;

  private skyUniforms: {
    uTime: { value: number };
    uSunDir: { value: THREE.Vector3 };
    uTopColor: { value: THREE.Color };
    uHorizonColor: { value: THREE.Color };
    uSunColor: { value: THREE.Color };
    uNightFactor: { value: number };
    uGoldenFactor: { value: number };
    uUseHdri: { value: number };
    uHdriDay: { value: THREE.Texture | null };
    uHdriSunset: { value: THREE.Texture | null };
    uHdriNight: { value: THREE.Texture | null };
  };

  // Prefiltered real 2K PureSky HDRI PMREM reflections (zero runtime re-render cost!)
  private pmremGenerator: THREE.PMREMGenerator;
  private pmremDay: THREE.Texture | null = null;
  private pmremSunset: THREE.Texture | null = null;
  private pmremNight: THREE.Texture | null = null;
  private activeEnvKey: 'day' | 'sunset' | 'night' | null = null;

  // Consolidated high-efficiency lighting:
  // Desktop: 7 permanent lights (Sun + Hemi + 2 wide SpotLight.map + 2 interior fill + 1 dual-purpose Crypt/Night zone light)
  // Mobile: 5 permanent lights (0 expensive textured SpotLights!)
  public shadowMapSize: number;
  private eastProjector: THREE.SpotLight | null = null;
  private westProjector: THREE.SpotLight | null = null;
  private naveFillLight: THREE.PointLight;
  private apseFillLight: THREE.PointLight;
  private zoneAccentLight: THREE.PointLight;
  private allLights: THREE.Light[] = [];

  private eastBeamMesh!: THREE.InstancedMesh;
  private westBeamMesh!: THREE.InstancedMesh;
  private lastBeamTilt = NaN;
  private starHaloSprite: THREE.Sprite;
  private crossHaloSprite: THREE.Sprite;

  // Pre-allocated scratch Colors & perf object for zero-GC per-frame updates
  private readonly cTopDay = new THREE.Color('#124898');
  private readonly cTopGolden = new THREE.Color('#1b356e');
  private readonly cTopNight = new THREE.Color('#050a18');
  private readonly cHorDay = new THREE.Color('#d2dfee');
  private readonly cHorGolden = new THREE.Color('#f5924c');
  private readonly cHorNight = new THREE.Color('#0e1930');
  private readonly cSunDay = new THREE.Color('#ffefd0');
  private readonly cSunGolden = new THREE.Color('#ff8730');
  private readonly cHemiSkyDay = new THREE.Color('#9ec3f0');
  private readonly cHemiGroundDay = new THREE.Color('#8a6646');
  private readonly cHemiGroundNight = new THREE.Color('#090d16');
  private readonly cCryptAccent = new THREE.Color('#ff8828');
  private readonly cNightFlood = new THREE.Color('#ffcb85');
  private readonly cNaveDay = new THREE.Color('#ffe2bc');
  private readonly cNaveWarm = new THREE.Color('#ffb86c');
  private readonly scratchTop = new THREE.Color();
  private readonly scratchHor = new THREE.Color();
  private readonly scratchSun = new THREE.Color();
  private readonly perfStats = { activeLights: 0, totalLights: 0, shadowCached: true };

  private trackedMats: TrackedMaterials = {
    east: [],
    west: [],
    apse: [],
    star: [],
    cross: [],
    lamps: [],
  };

  private clockSec = 0;
  private lastShadowUpdateMs = -1000;
  private shadowIntervalMs = getBootQuality().shadowUpdateIntervalMs;
  private shadowUpdatedThisFrame = false;

  public onTimeBucketChanged?: () => void;

  constructor(
    private scene: THREE.Scene,
    private renderer: THREE.WebGLRenderer
  ) {
    // 1. Real 2K PureSky HDRI Blended Sky Dome (faster & far more photorealistic than procedural FBM!)
    this.skyUniforms = {
      uTime: { value: 0 },
      uSunDir: { value: this.sunDir.clone() },
      uTopColor: { value: new THREE.Color('#1f5aa3') },
      uHorizonColor: { value: new THREE.Color('#c8dff5') },
      uSunColor: { value: new THREE.Color('#fff5dc') },
      uNightFactor: { value: 0.0 },
      uGoldenFactor: { value: 0.0 },
      uUseHdri: { value: 0.0 },
      uHdriDay: { value: null },
      uHdriSunset: { value: null },
      uHdriNight: { value: null },
    };

    const quality = getBootQuality();
    const cloudOctaves = quality.cloudOctaves;

    const skyMat = new THREE.ShaderMaterial({
      side: THREE.BackSide,
      depthWrite: false,
      uniforms: this.skyUniforms,
      vertexShader: /* glsl */ `
        varying vec3 vWorldDir;
        void main() {
          vec4 wp = modelMatrix * vec4(position, 1.0);
          vWorldDir = normalize(position);
          gl_Position = projectionMatrix * viewMatrix * wp;
        }
      `,
      fragmentShader: /* glsl */ `
        uniform float uTime;
        uniform vec3 uSunDir;
        uniform vec3 uTopColor;
        uniform vec3 uHorizonColor;
        uniform vec3 uSunColor;
        uniform float uNightFactor;
        uniform float uGoldenFactor;
        varying vec3 vWorldDir;

        float hash21(vec2 p) {
          p = fract(p * vec2(234.34, 435.345));
          p += dot(p, p + 34.23);
          return fract(p.x * p.y);
        }

        float noise2(vec2 p) {
          vec2 i = floor(p);
          vec2 f = fract(p);
          vec2 u = f * f * (3.0 - 2.0 * f);
          return mix(
            mix(hash21(i + vec2(0.0, 0.0)), hash21(i + vec2(1.0, 0.0)), u.x),
            mix(hash21(i + vec2(0.0, 1.0)), hash21(i + vec2(1.0, 1.0)), u.x),
            u.y
          );
        }

        float fbmCloud(vec2 p) {
          float v = 0.0;
          float a = 0.54;
          mat2 rot = mat2(0.80, 0.60, -0.60, 0.80);
          for (int i = 0; i < ${cloudOctaves}; i++) {
            v += a * noise2(p);
            p = rot * p * 2.08 + vec2(13.1, 7.7);
            a *= 0.48;
          }
          return v;
        }

        void main() {
          vec3 dir = normalize(vWorldDir);
          vec3 sunN = normalize(uSunDir);
          float h = clamp(dir.y, 0.0, 1.0);
          float sunAmt = max(dot(dir, sunN), 0.0);

          // Crisp Physically-Inspired Mediterranean Rayleigh + Mie Atmospheric Sky
          vec3 zenith = uTopColor;
          vec3 horizon = uHorizonColor;
          vec3 col = mix(horizon, zenith, pow(h, 0.50));

          // Warm Mie forward-scattering glow around the sun near the horizon
          float horizonBand = exp(-h * 4.2);
          col += uSunColor * pow(sunAmt, 4.0) * (0.34 + 0.55 * uGoldenFactor) * (0.45 + 0.55 * horizonBand) * (1.0 - uNightFactor);
          col += uSunColor * pow(sunAmt, 24.0) * 0.42 * (1.0 - uNightFactor * 0.96);
          col += uSunColor * smoothstep(0.9988, 0.9996, sunAmt) * 2.6 * (1.0 - uNightFactor);

          // Single-FBM + cheap 1-octave detail Mediterranean cirrus/cumulus cloud wisps
          if (dir.y > 0.025) {
            vec2 skyUv = dir.xz / (dir.y + 0.18) * 1.45 + vec2(uTime * 0.0045, uTime * 0.0022);
            float c1 = fbmCloud(skyUv);
            float c2 = noise2(skyUv * 2.4 - vec2(uTime * 0.006, 0.0));
            float cloudMask = smoothstep(0.49, 0.78, c1 * 0.76 + c2 * 0.24) * smoothstep(0.025, 0.24, dir.y);
            vec3 cloudLit = mix(vec3(0.96, 0.96, 0.98), vec3(1.0, 0.72, 0.44), uGoldenFactor);
            vec3 cloudShade = mix(vec3(0.62, 0.70, 0.82), vec3(0.46, 0.40, 0.54), uGoldenFactor);
            vec3 cloudCol = mix(cloudShade, cloudLit, smoothstep(0.2, 0.85, sunAmt * 0.7 + c2 * 0.45));
            cloudCol = mix(cloudCol, vec3(0.06, 0.09, 0.16), uNightFactor * 0.92);
            col = mix(col, cloudCol, cloudMask * (0.62 - uNightFactor * 0.35));
          }

          // Crisp twinkling Mediterranean night stars when dark
          if (uNightFactor > 0.15 && dir.y > 0.06) {
            vec2 starCell = floor(dir.xz / (dir.y + 0.35) * 145.0);
            float s = hash21(starCell);
            if (s > 0.9945) {
              float tw = 0.65 + 0.35 * sin(uTime * 2.8 + s * 600.0);
              col += vec3(0.85, 0.92, 1.0) * tw * uNightFactor * smoothstep(0.06, 0.30, dir.y) * 1.3;
            }
          }

          // Soft ground horizon mist below eye level
          if (dir.y < 0.0) {
            col = mix(col, horizon * 0.58, clamp(-dir.y * 5.0, 0.0, 1.0));
          }
          gl_FragColor = vec4(col, 1.0);
        }
      `,
    });

    this.skyMesh = new THREE.Mesh(new THREE.SphereGeometry(640, 28, 16), skyMat);
    this.skyMesh.renderOrder = -10;
    this.scene.add(this.skyMesh);

    this.pmremGenerator = new THREE.PMREMGenerator(this.renderer);

    // 2. Hemisphere + Cached Directional Sun Light
    this.hemiLight = new THREE.HemisphereLight('#bfd9f5', '#877258', 0.85);
    this.scene.add(this.hemiLight);

    this.sunLight = new THREE.DirectionalLight('#fff6e3', 2.0);
    this.sunLight.castShadow = true;
    this.shadowMapSize = quality.shadowMapSize;
    this.sunLight.shadow.mapSize.set(this.shadowMapSize, this.shadowMapSize);
    this.sunLight.shadow.camera.near = 25;
    this.sunLight.shadow.camera.far = SUN_SHADOW_FAR;
    const d = SUN_SHADOW_HALF_EXTENT;
    this.sunLight.shadow.camera.left = -d;
    this.sunLight.shadow.camera.right = d;
    this.sunLight.shadow.camera.top = d;
    this.sunLight.shadow.camera.bottom = -d;
    this.sunLight.shadow.bias = -0.0005;
    this.sunLight.shadow.normalBias = 0.045;
    this.sunLight.shadow.radius = 2.0;
    this.scene.add(this.sunLight);
    this.scene.add(this.sunLight.target);

    // 3. Stained-Glass SpotLight.map Projectors (Desktop only: 2 wide projectors; Mobile uses GI + Floor Carpets!)
    if (quality.stainedGlassProjectors) {
      const texLoader = new THREE.TextureLoader();
      const texEast = texLoader.load('./textures/stained_glass_east.webp');
      texEast.colorSpace = THREE.SRGBColorSpace;
      texEast.wrapS = THREE.ClampToEdgeWrapping;
      texEast.wrapT = THREE.ClampToEdgeWrapping;

      const texWest = texLoader.load('./textures/stained_glass_west.webp');
      texWest.colorSpace = THREE.SRGBColorSpace;
      texWest.wrapS = THREE.ClampToEdgeWrapping;
      texWest.wrapT = THREE.ClampToEdgeWrapping;

      const es = new THREE.SpotLight('#d4fff6', 240, 68, Math.PI * 0.44, 0.50, 1.05);
      es.map = texEast;
      es.position.set(...planToWorld(...LIGHTS.eastProjector.pos));
      es.target.position.set(...planToWorld(...LIGHTS.eastProjector.target!));
      this.scene.add(es);
      this.scene.add(es.target);
      this.eastProjector = es;

      const ws = new THREE.SpotLight('#ffd2a6', 240, 68, Math.PI * 0.44, 0.50, 1.05);
      ws.map = texWest;
      ws.position.set(...planToWorld(...LIGHTS.westProjector.pos));
      ws.target.position.set(...planToWorld(...LIGHTS.westProjector.target!));
      this.scene.add(ws);
      this.scene.add(ws.target);
      this.westProjector = ws;
    }

    // 4. Consolidated High-Efficiency Interior Fill Lights (enhanced by real Cycles GI Lightmaps!)
    this.naveFillLight = new THREE.PointLight('#ffb86c', 34, 82, 1.25);
    this.naveFillLight.position.set(...planToWorld(...LIGHTS.naveFill.pos));
    this.scene.add(this.naveFillLight);

    this.apseFillLight = new THREE.PointLight('#ffbc6b', 38, 58, 1.3);
    this.apseFillLight.position.set(...planToWorld(...LIGHTS.apseFill.pos));
    this.scene.add(this.apseFillLight);

    // 5. Dual-Purpose Zone Accent Light (Crypt Candlelight below Y=2.2m <-> Exterior Night Architectural Flood outside!)
    this.zoneAccentLight = new THREE.PointLight('#ff8828', 0, 26, 1.55);
    this.zoneAccentLight.position.set(...CRYPT_ACCENT);
    this.scene.add(this.zoneAccentLight);

    this.allLights = [this.sunLight, this.hemiLight, this.naveFillLight, this.apseFillLight, this.zoneAccentLight];
    if (this.eastProjector) this.allLights.push(this.eastProjector);
    if (this.westProjector) this.allLights.push(this.westProjector);
    this.perfStats.totalLights = this.allLights.length;

    const haloTex = this.createRadialGlowTexture();
    this.starHaloSprite = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: haloTex,
        color: '#ffe8a8',
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        opacity: 0.45,
      })
    );
    this.starHaloSprite.position.set(...planToWorld(...LIGHTS.starHalo.pos));
    this.starHaloSprite.scale.set(22, 22, 1);
    this.scene.add(this.starHaloSprite);

    this.crossHaloSprite = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: haloTex,
        color: '#fff4d6',
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        opacity: 0.35,
      })
    );
    this.crossHaloSprite.position.set(...planToWorld(...LIGHTS.crossHalo.pos));
    this.crossHaloSprite.scale.set(28, 28, 1);
    this.scene.add(this.crossHaloSprite);

    // 8. Soft GLSL Fresnel Volumetric Stained-Glass Sunbeams + Drifting Dust Motes
    this.buildVolumetricBeams();
    this.particles = new AtmosphericParticles(quality.dustParticles);
    this.scene.add(this.particles.points);

    this.setTimeOfDay(this.timeHours, true);
  }

  /**
   * Loads all 3 compact 256x128 PureSky IBL HDRIs (~267 KB total) in parallel and prefilters
   * their PMREM cubemaps during loading so runtime reflections have ZERO startup stutter.
   */
  private hdriPromises: Partial<Record<'day' | 'sunset' | 'night', Promise<void>>> = {};

  private desiredEnvKey(): 'day' | 'sunset' | 'night' {
    const solarProgress = (this.timeHours - 6.5) / 13.0;
    const elevation = Math.sin(solarProgress * Math.PI) * 1.12;
    const dayFactor = THREE.MathUtils.smoothstep(elevation, -0.08, 0.28);
    const goldenFactor = Math.exp(-Math.pow((elevation - 0.24) / 0.34, 2)) * dayFactor;
    const nightFactor = 1.0 - THREE.MathUtils.smoothstep(elevation, -0.15, 0.12);
    return nightFactor > 0.55 ? 'night' : goldenFactor > 0.42 ? 'sunset' : 'day';
  }

  private loadHdri(key: 'day' | 'sunset' | 'night'): Promise<void> {
    const existing = this.hdriPromises[key];
    if (existing) return existing;
    const p = new RGBELoader()
      .loadAsync(`./hdri/${key}_1k.hdr`)
      .then((tex) => {
        tex.mapping = THREE.EquirectangularReflectionMapping;
        tex.minFilter = THREE.LinearFilter;
        tex.magFilter = THREE.LinearFilter;
        const env = this.pmremGenerator.fromEquirectangular(tex).texture;
        tex.dispose();
        if (key === 'day') this.pmremDay = env;
        else if (key === 'sunset') this.pmremSunset = env;
        else this.pmremNight = env;
        this.activeEnvKey = null;
        this.setTimeOfDay(this.timeHours, false);
      })
      .catch((err) => {
        console.warn(`[HDRI] ${key} load fallback:`, err);
        delete this.hdriPromises[key];
      });
    this.hdriPromises[key] = p;
    return p;
  }

  /**
   * Loads the HDRI needed for the current time of day first (blocks the first frame), then the
   * other two in the background (~180 KB less before the first frame). Until a bucket's HDRI has
   * arrived the previous environment stays active.
   */
  public async loadHdris(): Promise<void> {
    this.pmremGenerator.compileEquirectangularShader();
    await this.loadHdri(this.desiredEnvKey());
  }

  /** Fetch the remaining time-of-day HDRIs (call after the first frame is on screen). */
  public loadDeferredHdris(): void {
    for (const k of ['day', 'sunset', 'night'] as const) void this.loadHdri(k);
  }

  /** Ensures the environment for an arbitrary hour is (being) loaded. */
  private ensureEnvForBucket(key: 'day' | 'sunset' | 'night'): void {
    if (!this.hdriPromises[key]) void this.loadHdri(key);
  }

  public loadRealHdrisInBackground(): void {
    void this.loadHdris();
  }

  private createRadialGlowTexture(): THREE.CanvasTexture {
    const c = document.createElement('canvas');
    c.width = 128;
    c.height = 128;
    const ctx = c.getContext('2d')!;
    const g = ctx.createRadialGradient(64, 64, 2, 64, 64, 64);
    g.addColorStop(0, 'rgba(255, 250, 232, 1.0)');
    g.addColorStop(0.25, 'rgba(255, 224, 150, 0.55)');
    g.addColorStop(0.65, 'rgba(255, 195, 100, 0.12)');
    g.addColorStop(1, 'rgba(255, 180, 80, 0.0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 128, 128);
    return new THREE.CanvasTexture(c);
  }

  /**
   * 4 east + 4 west stained-glass light shafts as two InstancedMeshes (per-instance colour):
   * 2 draw calls instead of 8, identical shading.
   */
  private buildVolumetricBeams(): void {
    const beamGeo = new THREE.CylinderGeometry(1.1, 4.5, 36, 18, 1, true);
    const createBeamMat = () =>
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
        // Additive + no depth write is order-independent: one double-sided pass equals three's default
        // back-then-front pair (half the draws, no per-frame program re-resolve from the side flip)
        forceSinglePass: true,
        uniforms: {
          uOpacity: { value: 0.08 },
        },
        vertexShader: /* glsl */ `
          varying vec2 vUv;
          varying vec3 vNormalV;
          varying vec3 vViewDir;
          varying vec3 vBeamColor;
          void main() {
            vUv = uv;
            vec4 mvPos = modelViewMatrix * instanceMatrix * vec4(position, 1.0);
            vNormalV = normalize(normalMatrix * mat3(instanceMatrix) * normal);
            vViewDir = normalize(-mvPos.xyz);
            vBeamColor = instanceColor;
            gl_Position = projectionMatrix * mvPos;
          }
        `,
        fragmentShader: /* glsl */ `
          uniform float uOpacity;
          varying vec2 vUv;
          varying vec3 vNormalV;
          varying vec3 vViewDir;
          varying vec3 vBeamColor;
          void main() {
            // Ultra-soft feathered volumetric light shaft (zero hard geometric cylinder edges!)
            float vertFade = smoothstep(0.0, 0.40, vUv.y) * smoothstep(1.0, 0.56, vUv.y);
            float ndv = abs(dot(normalize(vNormalV), normalize(vViewDir)));
            float edgeFade = pow(smoothstep(0.18, 0.96, ndv), 2.8);
            gl_FragColor = vec4(vBeamColor, vertFade * edgeFade * uOpacity);
          }
        `,
      });

    const eastColors = ['#29c5e0', '#2ee09b', '#3a86ff', '#26c9a8'];
    const westColors = ['#ff5b24', '#ff9d1c', '#f0293e', '#ffc229'];

    const build = (colors: string[]) => {
      const inst = new THREE.InstancedMesh(beamGeo, createBeamMat(), colors.length);
      const c = new THREE.Color();
      for (let i = 0; i < colors.length; i++) {
        // ShaderMaterial receives the raw (linear working-space) colour, same as the former uColor uniform
        inst.setColorAt(i, c.set(colors[i]));
      }
      if (inst.instanceColor) inst.instanceColor.needsUpdate = true;
      inst.frustumCulled = false; // bounds change with the sun tilt; 1 cheap draw either way
      this.scene.add(inst);
      return inst;
    };
    this.eastBeamMesh = build(eastColors);
    this.westBeamMesh = build(westColors);
    this.layoutBeams(0.88);
  }

  /** Nave window bays (runtime z) the sunbeams fall through. */
  private readonly beamZ = LAYOUT.naveWindowBayY.map((y) => -y);
  private readonly beamDummy = new THREE.Object3D();

  private layoutBeams(beamTilt: number): void {
    const d = this.beamDummy;
    for (let i = 0; i < this.beamZ.length; i++) {
      d.position.set(PROJ_X - Math.sin(beamTilt) * 11.5, 11.5, this.beamZ[i]);
      d.rotation.set(0, 0, beamTilt);
      d.updateMatrix();
      this.eastBeamMesh.setMatrixAt(i, d.matrix);
      d.position.set(-PROJ_X + Math.sin(beamTilt) * 11.5, 11.5, this.beamZ[i]);
      d.rotation.set(0, 0, -beamTilt);
      d.updateMatrix();
      this.westBeamMesh.setMatrixAt(i, d.matrix);
    }
    this.eastBeamMesh.instanceMatrix.needsUpdate = true;
    this.westBeamMesh.instanceMatrix.needsUpdate = true;
  }

  public registerLoadedMaterials(root: THREE.Object3D): void {
    root.traverse((obj) => {
      if (!(obj instanceof THREE.Mesh)) return;
      const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
      for (const m of mats) {
        if (!(m instanceof THREE.MeshStandardMaterial)) continue;
        if (m.name.includes('StainedGlassEast') && !this.trackedMats.east.includes(m)) this.trackedMats.east.push(m);
        else if (m.name.includes('StainedGlassWest') && !this.trackedMats.west.includes(m)) this.trackedMats.west.push(m);
        else if (m.name.includes('StainedGlassApse') && !this.trackedMats.apse.includes(m)) this.trackedMats.apse.push(m);
        else if (m.name.includes('LuminousStar') && !this.trackedMats.star.includes(m)) this.trackedMats.star.push(m);
        else if (m.name.includes('LuminousCross') && !this.trackedMats.cross.includes(m)) this.trackedMats.cross.push(m);
        else if (m.name.includes('CandleGlow') && !this.trackedMats.lamps.includes(m)) this.trackedMats.lamps.push(m);
      }
    });
    this.setTimeOfDay(this.timeHours, false);
  }

  public setTimeOfDay(hours: number, forceShadow = false): void {
    this.timeHours = ((hours % 24) + 24) % 24;

    const solarProgress = (this.timeHours - 6.5) / 13.0;
    const sunAngle = solarProgress * Math.PI;
    const elevation = Math.sin(sunAngle) * 1.12;
    const eastWest = Math.cos(sunAngle);

    const sx = eastWest * Math.cos(Math.max(elevation, -0.3)) * 185;
    const sy = Math.sin(elevation) * 185;
    const sz = Math.sin(Math.max(0, sunAngle)) * 78;

    this.sunDir.set(sx, sy, sz).normalize();
    this.sunLight.position.set(sx, Math.max(sy, 8), sz);
    this.sunLight.target.position.set(0, 12, 0);

    const dayFactor = THREE.MathUtils.smoothstep(elevation, -0.08, 0.28);
    const goldenFactor = Math.exp(-Math.pow((elevation - 0.24) / 0.34, 2)) * dayFactor;
    const nightFactor = 1.0 - THREE.MathUtils.smoothstep(elevation, -0.15, 0.12);

    this.dayFactor = dayFactor;
    this.nightFactor = nightFactor;

    this.scratchTop.copy(this.cTopNight).lerp(this.cTopDay, dayFactor).lerp(this.cTopGolden, goldenFactor * 0.62);
    this.scratchHor.copy(this.cHorNight).lerp(this.cHorDay, dayFactor).lerp(this.cHorGolden, goldenFactor * 0.85);
    this.scratchSun.copy(this.cSunDay).lerp(this.cSunGolden, goldenFactor * 0.85);

    this.skyUniforms.uSunDir.value.copy(this.sunDir);
    this.skyUniforms.uTopColor.value.copy(this.scratchTop);
    this.skyUniforms.uHorizonColor.value.copy(this.scratchHor);
    this.skyUniforms.uSunColor.value.copy(this.scratchSun);
    this.skyUniforms.uNightFactor.value = nightFactor;
    this.skyUniforms.uGoldenFactor.value = goldenFactor;

    if (this.scene.fog instanceof THREE.FogExp2) {
      this.scene.fog.color.copy(this.scratchHor);
      this.scene.fog.density = THREE.MathUtils.lerp(FOG_DENSITY_DAY, FOG_DENSITY_NIGHT, nightFactor);
    }

    // Swap prefiltered real 2K PureSky HDRI PMREM instantly (0 ms!)
    const desiredEnv: 'day' | 'sunset' | 'night' =
      nightFactor > 0.55 ? 'night' : goldenFactor > 0.42 ? 'sunset' : 'day';
    if (desiredEnv !== this.activeEnvKey) {
      const tex =
        desiredEnv === 'night'
          ? this.pmremNight
          : desiredEnv === 'sunset'
            ? this.pmremSunset
            : this.pmremDay;
      if (tex) {
        this.scene.environment = tex;
        this.activeEnvKey = desiredEnv;
        this.onTimeBucketChanged?.();
      } else {
        this.ensureEnvForBucket(desiredEnv);
      }
    }

    this.sunLight.color.copy(this.scratchSun);
    // Crisp, sculptural warm Mediterranean sunlight outdoors
    this.baseSunInt = dayFactor * THREE.MathUtils.lerp(2.25, 1.85, goldenFactor * 0.65);
    this.sunLight.intensity = this.baseSunInt;
    // castShadow stays permanently on: toggling it at dusk changed NUM_DIR_LIGHT_SHADOWS and forced every
    // lit material to recompile (visible hitch on the time slider / during the tour). At night the sun's
    // intensity is ~0, so its (cached) shadow contributes nothing; we simply skip re-rendering it.
    if (dayFactor > 0.02 || forceShadow) {
      this.requestShadowUpdate(forceShadow);
    }

    // Avoid double-stacking HemisphereLight + HDRI PMREM IBL!
    // Cool Mediterranean sky fill vs warm sandstone ground bounce for rich sculptural contrast
    this.hemiLight.color.copy(this.scratchTop).lerp(this.cHemiSkyDay, 0.35 * dayFactor);
    this.hemiLight.groundColor.copy(this.cHemiGroundDay).lerp(this.cHemiGroundNight, nightFactor * 0.92);
    this.baseHemiInt = THREE.MathUtils.lerp(0.06, 0.28, dayFactor);
    this.baseEnvInt = THREE.MathUtils.lerp(0.08, 0.38, dayFactor) * THREE.MathUtils.lerp(1.0, 0.84, goldenFactor);
    this.hemiLight.intensity = this.baseHemiInt;
    this.scene.environmentIntensity = this.baseEnvInt;

    const eastSunHit = Math.max(0, eastWest) * dayFactor;
    const westSunHit = Math.max(0, -eastWest) * dayFactor;
    this.eastSunHit = eastSunHit;
    this.westSunHit = westSunHit;

    const reach = THREE.MathUtils.lerp(29.0, 11.0, THREE.MathUtils.clamp(elevation / 1.0, 0, 1));
    const targetClimbY = THREE.MathUtils.lerp(7.5, 1.2, THREE.MathUtils.clamp(elevation / 0.65, 0, 1));
    const beamTilt = THREE.MathUtils.lerp(1.12, 0.48, THREE.MathUtils.clamp(elevation / 1.0, 0, 1));

    this.baseEastInt = 16 * dayFactor + eastSunHit * 380;
    if (this.eastProjector) {
      this.eastProjector.intensity = this.baseEastInt;
      this.eastProjector.target.position.set(PROJ_X - reach, targetClimbY, PROJ_Z);
      this.eastProjector.target.updateMatrixWorld();
    }
    if (beamTilt !== this.lastBeamTilt) {
      this.lastBeamTilt = beamTilt;
      this.layoutBeams(beamTilt);
    }
    (this.eastBeamMesh.material as THREE.ShaderMaterial).uniforms.uOpacity.value = eastSunHit * 0.24;

    this.baseWestInt = 16 * dayFactor + westSunHit * 420;
    if (this.westProjector) {
      this.westProjector.intensity = this.baseWestInt;
      this.westProjector.target.position.set(-PROJ_X + reach, targetClimbY, PROJ_Z);
      this.westProjector.target.updateMatrixWorld();
    }
    (this.westBeamMesh.material as THREE.ShaderMaterial).uniforms.uOpacity.value = westSunHit * 0.26;

    this.baseApseInt = 16 * dayFactor + 24;
    this.apseFillLight.intensity = this.baseApseInt;

    const ambientGlass = 0.28 * dayFactor + 0.14;
    this.baseEastGlassGlow = ambientGlass + eastSunHit * 2.5;
    this.baseWestGlassGlow = ambientGlass + westSunHit * 2.7;
    this.baseApseGlassGlow = 0.70 + dayFactor * 1.25;
    for (const m of this.trackedMats.east) m.emissiveIntensity = this.baseEastGlassGlow;
    for (const m of this.trackedMats.west) m.emissiveIntensity = this.baseWestGlassGlow;
    for (const m of this.trackedMats.apse) m.emissiveIntensity = this.baseApseGlassGlow;

    // Sacred Chiaroscuro interior fill: let stained glass & sanctuary candles define column flutes & vaults!
    const warmMood = THREE.MathUtils.clamp(goldenFactor * 0.85 + Math.max(0, -eastWest) * 0.45 + nightFactor * 0.9, 0, 1);
    this.naveFillLight.color.copy(this.cNaveDay).lerp(this.cNaveWarm, warmMood);
    this.baseInteriorInt = THREE.MathUtils.lerp(30, 42, nightFactor);
    this.naveFillLight.intensity = this.baseInteriorInt;

    this.baseNightInt = nightFactor * 195;

    const landmarkGlow = 1.2 + nightFactor * 3.2;
    for (const m of this.trackedMats.star) m.emissiveIntensity = landmarkGlow * 1.25;
    for (const m of this.trackedMats.cross) m.emissiveIntensity = landmarkGlow * 1.0;
    (this.starHaloSprite.material as THREE.SpriteMaterial).opacity = 0.18 + nightFactor * 0.62;
    (this.crossHaloSprite.material as THREE.SpriteMaterial).opacity = 0.16 + nightFactor * 0.56;
  }

  /** Live quality switch: sun shadow-map resolution. */
  public applyQuality(q: QualitySettings): void {
    this.shadowIntervalMs = q.shadowUpdateIntervalMs;
    if (q.shadowMapSize !== this.shadowMapSize) {
      this.shadowMapSize = q.shadowMapSize;
      this.sunLight.shadow.mapSize.set(q.shadowMapSize, q.shadowMapSize);
      if (this.sunLight.shadow.map) {
        this.sunLight.shadow.map.dispose();
        this.sunLight.shadow.map = null;
      }
    }
    this.requestShadowUpdate(true);
  }

  /** After WebGL context restore: GPU-side PMREM maps are gone, rebuild them + the shadow map. */
  public async handleContextRestored(): Promise<void> {
    // Old GL handles died with the context: drop references instead of dispose() (which would try to
    // delete foreign GL objects and spam INVALID_OPERATION warnings).
    this.pmremGenerator = new THREE.PMREMGenerator(this.renderer);
    this.pmremDay = this.pmremSunset = this.pmremNight = null;
    this.activeEnvKey = null;
    this.hdriPromises = {};
    this.sunLight.shadow.map = null;
    await this.loadHdris();
    this.requestShadowUpdate(true);
  }

  public requestShadowUpdate(immediate = false): void {
    const now = performance.now();
    if (immediate || now - this.lastShadowUpdateMs >= this.shadowIntervalMs) {
      this.renderer.shadowMap.needsUpdate = true;
      this.lastShadowUpdateMs = now;
      this.shadowUpdatedThisFrame = true;
    }
  }

  private baseSunInt = 1.9;
  private baseHemiInt = 0.2;
  private baseEnvInt = 0.42;
  private baseEastInt = 0;
  private baseWestInt = 0;
  private baseApseInt = 0;
  private baseInteriorInt = 52;
  private baseNightInt = 0;
  private baseEastGlassGlow = 1.2;
  private baseWestGlassGlow = 1.2;
  private baseApseGlassGlow = 1.0;

  public updateZoneCulling(cameraPos: THREE.Vector3, indoorFactor: number): void {
    // CRITICAL ANTI-STUTTER FIX:
    // NEVER toggle light.visible = false/true while walking! Keep active lights permanently visible
    // and smoothly modulate intensities to prevent GLSL shader recompilation freezes!
    const inCryptRange = isNearCryptLevel(cameraPos.x, cameraPos.y, cameraPos.z);
    const underground = isEyeUnderground(cameraPos.x, cameraPos.y, cameraPos.z);
    const nearInterior =
      !underground &&
      cameraPos.y < 68 &&
      Math.abs(cameraPos.x) < NEAR_INTERIOR.maxX &&
      cameraPos.z > NEAR_INTERIOR.minZ &&
      cameraPos.z < NEAR_INTERIOR.maxZ;
    const needNightFloods = this.nightFactor > 0.04 && indoorFactor < 0.92;

    // REALISTIC STAINED GLASS: From OUTSIDE in daylight, stained glass is dark reflective leaded cathedral glass;
    // from INSIDE or AT NIGHT, it glows richly with transmitted jewel light!
    const glassTransmittance = Math.max(indoorFactor, THREE.MathUtils.smoothstep(this.nightFactor, 0.25, 0.85) * 0.72);
    const glassScale = THREE.MathUtils.lerp(0.08, 1.0, glassTransmittance);
    const diffuseShade = THREE.MathUtils.lerp(0.32, 1.0, glassTransmittance);
    for (const m of this.trackedMats.east) {
      m.emissiveIntensity = this.baseEastGlassGlow * glassScale;
      m.color.setScalar(diffuseShade);
    }
    for (const m of this.trackedMats.west) {
      m.emissiveIntensity = this.baseWestGlassGlow * glassScale;
      m.color.setScalar(diffuseShade);
    }
    for (const m of this.trackedMats.apse) {
      m.emissiveIntensity = this.baseApseGlassGlow * glassScale;
      m.color.setScalar(diffuseShade);
    }

    // Physical outdoor-sky & direct-sunlight occlusion inside stone cathedral walls:
    const outdoorSkyLeak = underground ? 0.06 : THREE.MathUtils.lerp(1.0, 0.22, indoorFactor);
    const sunIndoorMul = underground ? 0.0 : THREE.MathUtils.lerp(1.0, 0.16, indoorFactor);
    this.hemiLight.intensity = this.baseHemiInt * outdoorSkyLeak;
    this.scene.environmentIntensity = this.baseEnvInt * (underground ? 0.08 : THREE.MathUtils.lerp(1.0, 0.28, indoorFactor));
    this.sunLight.intensity = this.baseSunInt * sunIndoorMul;

    const intMul = nearInterior && !inCryptRange ? 1.0 : 0.0;
    if (this.eastProjector) this.eastProjector.intensity = this.baseEastInt * intMul;
    if (this.westProjector) this.westProjector.intensity = this.baseWestInt * intMul;
    this.naveFillLight.intensity = this.baseInteriorInt * intMul;
    this.apseFillLight.intensity = this.baseApseInt * intMul;

    const showEastBeams = nearInterior && this.eastSunHit > 0.03;
    const showWestBeams = nearInterior && this.westSunHit > 0.03;
    this.eastBeamMesh.visible = showEastBeams;
    this.westBeamMesh.visible = showWestBeams;

    if (inCryptRange) {
      this.zoneAccentLight.color.copy(this.cCryptAccent);
      this.zoneAccentLight.position.set(...CRYPT_ACCENT);
      this.zoneAccentLight.distance = 34;
      this.zoneAccentLight.decay = 1.35;
    } else if (needNightFloods) {
      this.zoneAccentLight.color.copy(this.cNightFlood);
      this.zoneAccentLight.position.set(48, 28, 16);
      this.zoneAccentLight.distance = 165;
      this.zoneAccentLight.decay = 1.15;
      this.zoneAccentLight.intensity = this.baseNightInt;
    } else {
      this.zoneAccentLight.intensity = 0;
    }

    this.particles.points.visible = indoorFactor > 0.15 && !underground;
    this.starHaloSprite.visible = !underground;
    this.crossHaloSprite.visible = !underground;
  }

  public getPerfLightStats(): { activeLights: number; totalLights: number; shadowCached: boolean } {
    let activeLights = 0;
    for (let i = 0; i < this.allLights.length; i++) {
      const l = this.allLights[i];
      if (l.visible && l.intensity > 0.01) activeLights++;
    }
    this.perfStats.activeLights = activeLights;
    this.perfStats.shadowCached = !this.shadowUpdatedThisFrame;
    this.shadowUpdatedThisFrame = false;
    return this.perfStats;
  }

  public update(dt: number, cameraPos: THREE.Vector3, indoorFactor: number): void {
    this.clockSec += dt;
    this.skyUniforms.uTime.value = this.clockSec;
    this.skyMesh.visible = !isEyeUnderground(cameraPos.x, cameraPos.y, cameraPos.z);
    if (this.skyMesh.visible) {
      this.skyMesh.position.copy(cameraPos);
    }

    this.updateZoneCulling(cameraPos, indoorFactor);

    if (this.particles.points.visible) {
      this.particles.update(dt, this.eastSunHit, this.westSunHit, this.dayFactor);
    }

    if (isNearCryptLevel(cameraPos.x, cameraPos.y, cameraPos.z)) {
      const flicker = Math.sin(this.clockSec * 5.2) * 0.9 + Math.sin(this.clockSec * 11.7) * 0.45;
      this.zoneAccentLight.intensity = 38 + flicker;
    }
  }
}
