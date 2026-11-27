import * as THREE from 'three';
import { LAYOUT, planToWorld, pondRuntime } from '../data/layout';
import { EYE_HEIGHT, isEyeUnderground, isNearCryptLevel } from './walkModel';
import { FOG_DENSITY_DAY } from './atmosphere';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';
import { Reflector } from 'three/examples/jsm/objects/Reflector.js';
import { LightingSystem } from './LightingSystem';
import { GeometryOverlay } from './GeometryOverlay';
import { FlockingBirds } from './FlockingBirds';
import { FountainParticles } from './FountainParticles';
import { optimizeWithAutoInstancing, InstanceCuller } from './AutoInstancer';
import { ConstructionTimeline } from './ConstructionTimeline';
import { CandleFlames } from './CandleFlames';
import { StainedGlassCarpets } from './StainedGlassCarpets';
import { WeatherSystem } from './WeatherSystem';
import { JesusElevator } from './JesusElevator';
import { CollisionSystem } from './CollisionSystem';
import { getBootQuality, QualitySettings } from '../utils/quality';
import { t, type MessageKey } from '../i18n';

/** Loading-status message, resolved lazily so the UI can re-render it after a language switch. */

const POND = pondRuntime();
const FOUNTAIN_XZ = { x: LAYOUT.city.fountain.x, z: -LAYOUT.city.fountain.y };
const BASILICA_XZ = { x: LAYOUT.zones.basilicaCenter[0], z: -LAYOUT.zones.basilicaCenter[1] };
const APSE_XZ = { x: LAYOUT.apse.center[0], z: -LAYOUT.apse.center[1] };
const CRYPT_STAIRS_XZ = LAYOUT.crypt.stairs.map((st) => ({ x: st.x, z: -st.y }));
export type LoadStatus = () => string;

interface ModelSpec {
  id: string;
  labelKey: MessageKey;
  url: string;
  weightKB: number;
}

const MODEL_SPECS: ModelSpec[] = [
  { id: 'facades', labelKey: 'module.facades', url: './models/facades.glb', weightKB: 1201 },
  { id: 'towers', labelKey: 'module.towers', url: './models/towers.glb', weightKB: 1884 },
  { id: 'interior', labelKey: 'module.interior', url: './models/interior.glb', weightKB: 1703 },
  { id: 'furnishings', labelKey: 'module.furnishings', url: './models/furnishings.glb', weightKB: 311 },
  { id: 'cloister_crypt', labelKey: 'module.cloister_crypt', url: './models/cloister_crypt.glb', weightKB: 642 },
  { id: 'eixample', labelKey: 'module.eixample', url: './models/eixample.glb', weightKB: 173 },
  { id: 'plaza_life', labelKey: 'module.plaza_life', url: './models/plaza_life.glb', weightKB: 70 },
];

/** Without these the basilica itself is missing, so loading stops with an error screen. */
const CORE_MODULE_IDS = new Set(['facades', 'towers', 'interior']);

/** Localized, human-readable module name (falls back to the id). */
export function getModuleLabel(id: string): string {
  const spec = MODEL_SPECS.find((s) => s.id === id);
  return spec ? t(spec.labelKey) : id;
}

export class AssetLoadError extends Error {
  constructor(public readonly moduleIds: string[]) {
    super(`Core 3D modules failed to load: ${moduleIds.join(', ')}`);
    this.name = 'AssetLoadError';
  }
}

/**
 * Downscales oversized textures in place (low tier: 1024² -> 512² cuts their VRAM by 75 %).
 * Runs before the first GPU upload, so nothing is uploaded twice.
 */
function downscaleTextures(root: THREE.Object3D, maxSize: number): number {
  const seen = new Set<THREE.Texture>();
  // Several Texture objects may share one decoded image (GLTFLoader clones per sampler) -> share the result
  const scaledByImage = new Map<unknown, HTMLCanvasElement>();
  let count = 0;
  root.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (!mesh.isMesh) return;
    const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    for (const m of mats) {
      const std = m as THREE.MeshStandardMaterial;
      // 2D canvas is premultiplied: keep the colour map of alpha-blended / alpha-tested materials untouched
      // (its alpha channel matters); normal / roughness / emissive maps never use alpha.
      const alphaSensitive = std.transparent || std.alphaTest > 0;
      for (const tex of [
        alphaSensitive ? null : std.map,
        std.normalMap,
        std.roughnessMap,
        std.metalnessMap,
        std.emissiveMap,
        std.aoMap,
      ]) {
        if (!tex || seen.has(tex)) continue;
        seen.add(tex);
        const img = tex.image as (ImageBitmap | HTMLImageElement | HTMLCanvasElement) | undefined;
        if (!img) continue;
        const cached = scaledByImage.get(img);
        if (cached) {
          tex.image = cached;
          tex.needsUpdate = true;
          continue;
        }
        if (!('width' in img) || !img.width || !img.height) continue;
        const scale = Math.min(1, maxSize / Math.max(img.width, img.height));
        if (scale >= 1) continue;
        const w = Math.max(1, Math.round(img.width * scale));
        const h = Math.max(1, Math.round(img.height * scale));
        const canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext('2d');
        if (!ctx) continue;
        ctx.imageSmoothingQuality = 'high';
        ctx.drawImage(img as CanvasImageSource, 0, 0, w, h);
        scaledByImage.set(img, canvas);
        tex.image = canvas;
        tex.needsUpdate = true;
        count++;
      }
    }
  });
  return count;
}

const nextFrame = (): Promise<void> =>
  new Promise((resolve) => requestAnimationFrame(() => resolve()));

const LIGHTMAP_BY_MESH: Record<string, { url: string; intensity: number }> = {
  Interior_HyperboloidVaults: { url: './textures/lightmaps/lightmap_vaults.webp', intensity: 1.4 },
  Interior_MarbleFloor: { url: './textures/lightmaps/lightmap_floor.webp', intensity: 1.2 },
  Interior_NaveWalls: { url: './textures/lightmaps/lightmap_walls.webp', intensity: 1.3 },
  Crypt_Architecture: { url: './textures/lightmaps/lightmap_crypt.webp', intensity: 0.65 },
};

export class SagradaScene {
  public readonly scene: THREE.Scene;
  public readonly lighting: LightingSystem;
  public readonly geometryOverlay: GeometryOverlay;
  public readonly timeline: ConstructionTimeline;
  public readonly birds: FlockingBirds;
  public readonly fountain: FountainParticles;
  public readonly candles: CandleFlames;
  public readonly glassCarpets: StainedGlassCarpets;
  public readonly weather: WeatherSystem;
  public readonly elevator: JesusElevator;

  /** Optional modules that failed to load (the visit continues without them). */
  public readonly failedModules: string[] = [];
  public instancedGroups = 0;
  public savedDrawCalls = 0;
  public reflectorActive = true;
  public reflectorRes: number;

  private pondReflector!: Reflector;
  private pondBox = new THREE.Box3(
    new THREE.Vector3(POND.cx - POND.width / 2, POND.waterY - 0.5, POND.cz - POND.depth / 2),
    new THREE.Vector3(POND.cx + POND.width / 2, POND.waterY + 1.5, POND.cz + POND.depth / 2)
  );
  private frustum = new THREE.Frustum();
  private projScreenMat = new THREE.Matrix4();

  // Cached 0ms/frame Nave Interior CubeCamera Reflection Probe (gives marble floor real stained-glass & column reflections!)
  private interiorProbeRT: THREE.WebGLCubeRenderTarget;
  private interiorCubeCam: THREE.CubeCamera;
  private interiorPmrem: THREE.PMREMGenerator;
  private interiorPmremReady = false;
  private interiorProbeDirty = false;
  private lastIndoorFactor = 0;
  private currentInteriorEnvRT: THREE.WebGLRenderTarget | null = null;
  private interiorReflectiveMats: THREE.MeshStandardMaterial[] = [];

  private waterUniforms = {
    uTime: { value: 0 },
    uSunDir: { value: new THREE.Vector3(0.6, 0.7, 0.2) },
    uSunColor: { value: new THREE.Color('#fff5dc') },
    uNightFactor: { value: 0.0 },
    uRainFactor: { value: 0.0 },
  };
  private windUniform = { value: 0 };
  private hazeUniforms = {
    uHazeColor: { value: new THREE.Color('#f0dec4') },
    uHazeStrength: { value: 0.22 },
  };
  private readonly hazeDayCol = new THREE.Color('#e6b680');
  private readonly hazeNightCol = new THREE.Color('#131b30');
  private readonly nightWindowCol = new THREE.Color('#ffbd69');

  private eixampleNightMats: THREE.MeshStandardMaterial[] = [];
  private internalStairMeshes: THREE.Object3D[] = [];
  private interiorDeepMeshes: THREE.Object3D[] = [];
  private cryptMeshes: THREE.Object3D[] = [];
  private highTowerMeshes: THREE.Object3D[] = [];
  private eixampleDetailMeshes: THREE.Object3D[] = [];
  private plazaLifeRoot: THREE.Object3D | null = null;
  private eixampleRoot: THREE.Object3D | null = null;
  private exteriorShellRoots: THREE.Object3D[] = [];

  // Pre-allocated reflector visibility lists & throttle state (zero per-frame allocations!)
  private reflectorHiddenObjs: THREE.Object3D[] = [];
  private reflectorSavedVis: boolean[] = [];
  private readonly lastReflCamPos = new THREE.Vector3(Infinity, 0, 0);
  private readonly lastReflCamQuat = new THREE.Quaternion();
  private lastReflTimeHours = -1;
  private reflFrameCounter = 0;
  private reflDirty = true;
  private reflStationaryPeriod = 8;
  private reflHalfRate = false;
  /** Pond covers < ~2 % of the screen (aerial / far views): moving refreshes at the stationary rate. */
  private reflSmallOnScreen = false;
  private readonly reflCorner = new THREE.Vector3();
  /** Fine detail left out of the (160–256 px) pond reflection on tiers with reflectorLite; built lazily. */
  private reflLiteBuilt = false;
  private readonly reflLite = getBootQuality().reflectorHideDetail;
  // Per-instance culling of the auto-instanced props (see InstanceCuller in AutoInstancer.ts)
  private instanceCuller: InstanceCuller | null = null;
  private readonly probeHiddenObjs: THREE.Object3D[] = [];

  constructor(private renderer: THREE.WebGLRenderer) {
    const quality = getBootQuality();
    this.reflectorRes = quality.reflectorRes;
    this.reflStationaryPeriod = quality.reflectorStationaryPeriod;
    this.reflHalfRate = quality.reflectorHalfRate;

    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.FogExp2('#c8dff5', FOG_DENSITY_DAY);

    this.lighting = new LightingSystem(this.scene, this.renderer);
    this.geometryOverlay = new GeometryOverlay();
    this.timeline = new ConstructionTimeline();
    this.timeline.onLocalClippingChange = (enabled) => {
      this.renderer.localClippingEnabled = enabled;
      this.reflDirty = true;
      if (enabled) {
        for (let i = 0; i < this.interiorDeepMeshes.length; i++) this.interiorDeepMeshes[i].visible = true;
        for (let i = 0; i < this.cryptMeshes.length; i++) this.cryptMeshes[i].visible = true;
        for (let i = 0; i < this.highTowerMeshes.length; i++) this.highTowerMeshes[i].visible = true;
        for (let i = 0; i < this.internalStairMeshes.length; i++) this.internalStairMeshes[i].visible = true;
      }
    };
    this.scene.add(this.geometryOverlay.group);

    this.birds = new FlockingBirds(quality.birdCount);
    this.scene.add(this.birds.group);

    this.fountain = new FountainParticles(quality.fountainParticles);
    this.scene.add(this.fountain.points);

    this.candles = new CandleFlames();
    this.scene.add(this.candles.group);

    this.glassCarpets = new StainedGlassCarpets();
    this.scene.add(this.glassCarpets.group);

    this.weather = new WeatherSystem();
    this.scene.add(this.weather.group);

    this.elevator = new JesusElevator();
    this.scene.add(this.elevator.group);

    // Non-architectural overlays/particles never need to render inside the distant pond reflector
    this.reflectorHiddenObjs.push(
      this.candles.group,
      this.glassCarpets.group,
      this.weather.group,
      this.birds.group,
      this.fountain.points,
      this.elevator.group,
      this.lighting.particles.points
    );

    // Prepare cached interior reflection probe (face size per quality tier)
    const probeRes = quality.probeRes;
    this.interiorProbeRT = new THREE.WebGLCubeRenderTarget(probeRes, {
      generateMipmaps: true,
      minFilter: THREE.LinearMipmapLinearFilter,
      type: THREE.HalfFloatType,
    });
    this.interiorCubeCam = new THREE.CubeCamera(0.5, 130, this.interiorProbeRT);
    this.interiorCubeCam.position.set(...planToWorld(...LAYOUT.lights.interiorProbe.pos));
    this.scene.add(this.interiorCubeCam);
    this.interiorPmrem = new THREE.PMREMGenerator(this.renderer);

    this.lighting.onTimeBucketChanged = () => {
      if (this.lastIndoorFactor > 0.15) {
        this.captureInteriorReflectionProbe();
      } else {
        this.interiorProbeDirty = true;
      }
    };

    this.buildReflectivePond(quality.reflectorMultisample);
  }

  /**
   * Captures the real Nave interior (columns, stained glass, vaults, chandeliers) ONCE per lighting bucket
   * into a prefiltered PMREM map so the polished marble floor & porphyry columns reflect the real cathedral at 0 ms/frame!
   */
  public captureInteriorReflectionProbe(): void {
    if (this.interiorReflectiveMats.length === 0) return;
    if (!this.interiorPmremReady) {
      this.interiorPmrem.compileCubemapShader();
      this.interiorPmremReady = true;
    }
    const prevPond = this.pondReflector.visible;
    const prevGeo = this.geometryOverlay.group.visible;
    this.pondReflector.visible = false;
    this.geometryOverlay.group.visible = false;

    const savedDeep: boolean[] = [];
    for (let i = 0; i < this.interiorDeepMeshes.length; i++) {
      savedDeep[i] = this.interiorDeepMeshes[i].visible;
      this.interiorDeepMeshes[i].visible = true;
    }
    const savedExt: boolean[] = [];
    for (let i = 0; i < this.exteriorShellRoots.length; i++) {
      savedExt[i] = this.exteriorShellRoots[i].visible;
      this.exteriorShellRoots[i].visible = true;
    }
    // The probe sits in the nave: the city, plaza, crypt, tower stairs / upper towers, birds, fountain and
    // weather are invisible from there (or only as a blur through the 92 % opaque glass), but the six cube
    // faces drew all of them (~3 M triangles / ~600 draw calls per capture on low). Hide them for the capture.
    const probeHidden = this.probeHiddenObjs;
    probeHidden.length = 0;
    probeHidden.push(this.birds.group, this.fountain.points, this.weather.group, this.lighting.particles.points);
    if (this.eixampleRoot) probeHidden.push(this.eixampleRoot);
    if (this.plazaLifeRoot) probeHidden.push(this.plazaLifeRoot);
    probeHidden.push(...this.cryptMeshes, ...this.internalStairMeshes, ...this.highTowerMeshes);
    const probeSaved = probeHidden.map((o) => o.visible);
    for (const o of probeHidden) o.visible = false;
    this.instanceCuller?.showAll();

    this.interiorCubeCam.update(this.renderer, this.scene);
    for (let i = 0; i < probeHidden.length; i++) probeHidden[i].visible = probeSaved[i];
    const nextEnv = this.interiorPmrem.fromCubemap(this.interiorProbeRT.texture);

    for (const mat of this.interiorReflectiveMats) {
      mat.envMap = nextEnv.texture;
      mat.needsUpdate = true;
    }

    if (this.currentInteriorEnvRT) {
      this.currentInteriorEnvRT.dispose();
    }
    this.currentInteriorEnvRT = nextEnv;
    this.interiorProbeDirty = false;

    for (let i = 0; i < this.interiorDeepMeshes.length; i++) {
      this.interiorDeepMeshes[i].visible = savedDeep[i];
    }
    for (let i = 0; i < this.exteriorShellRoots.length; i++) {
      this.exteriorShellRoots[i].visible = savedExt[i];
    }
    this.pondReflector.visible = prevPond;
    this.geometryOverlay.group.visible = prevGeo;
  }

  /** Live quality switch: pond reflection resolution & update throttling. */
  public applyQuality(q: QualitySettings): void {
    this.reflStationaryPeriod = q.reflectorStationaryPeriod;
    this.reflHalfRate = q.reflectorHalfRate;
    if (q.reflectorRes !== this.reflectorRes) {
      this.reflectorRes = q.reflectorRes;
      this.pondReflector.getRenderTarget().setSize(q.reflectorRes, q.reflectorRes);
    }
    this.reflDirty = true;
  }

  /** After WebGL context restore: render-target contents (probe, reflector) must be re-rendered. */
  public handleContextRestored(): void {
    // Old GL handles died with the context: drop references (dispose() would touch foreign GL objects)
    this.interiorPmrem = new THREE.PMREMGenerator(this.renderer);
    this.interiorPmremReady = false;
    this.currentInteriorEnvRT = null; // old GPU handle is gone with the context
    this.reflDirty = true;
    this.captureInteriorReflectionProbe();
  }

  private createEixampleNightWindowTexture(): THREE.CanvasTexture {
    const size = 512;
    const c = document.createElement('canvas');
    c.width = size;
    c.height = size;
    const ctx = c.getContext('2d')!;
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, size, size);

    const floors = 5;
    const bays = 4;
    let seed = 1337;
    const rand = () => {
      seed = (seed * 16807) % 2147483647;
      return (seed - 1) / 2147483646;
    };

    for (let f = 0; f < floors; f++) {
      for (let b = 0; b < bays; b++) {
        if (rand() > 0.52) continue;
        const x0 = (b + 0.30) * (size / bays);
        const w = 0.40 * (size / bays);
        const y0 = (f + 0.20) * (size / floors);
        const h = 0.62 * (size / floors);

        const warmPalette = ['#ffcf86', '#ffb961', '#ffe0a8', '#ffa852'];
        const col = warmPalette[Math.floor(rand() * warmPalette.length)];
        const grad = ctx.createLinearGradient(x0, y0, x0, y0 + h);
        grad.addColorStop(0, col);
        grad.addColorStop(1, '#c97c32');
        ctx.fillStyle = grad;
        ctx.fillRect(x0, y0, w, h);
      }
    }

    const tex = new THREE.CanvasTexture(c);
    tex.wrapS = THREE.RepeatWrapping;
    tex.wrapT = THREE.RepeatWrapping;
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  }

  /**
   * Low / medium (reflectorHideDetail): sculpture leaves, gold / trencadís accents and pinnacle "pearls" are
   * 1–4 px features in the 160–256 px pond reflection under the ripple overlay. Leaving them out of the
   * reflection pass removes ~65k of its ~240k triangles (the sacristy domes stay: they read clearly in the
   * reflection). Runs once, after all modules are loaded.
   */
  private buildReflectorLiteList(): void {
    this.reflLiteBuilt = true;
    if (!this.reflLite) return;
    const detail = [
      'Facade_Nativity_Sculpture_Leaves',
      'Facade_GloryAndRoofs_Sculpture_Leaves',
      'Facade_Passion_BonesAndRoots_Leaves',
      'Facade_Passion_Sculpture_Leaves',
      'Facade_GoldAccents',
      'Facade_Doves',
      'Towers_GoldAccents',
      'Towers_GoldAccents_SanctusLettering',
      'Instanced_Towers_GoldAccents_Mitre_0',
      'Instanced_Towers_TrencadisPinnacles_Pearls_0',
      'Instanced_Towers_TrencadisPinnacles_Mitre_0',
      'Towers_EvangelistSculptures',
      'Cloister_Gold',
      'Sacristy_Trencadis',
    ];
    for (const name of detail) {
      const obj = this.scene.getObjectByName(name);
      if (obj && !this.reflectorHiddenObjs.includes(obj)) this.reflectorHiddenObjs.push(obj);
    }
  }

  /** Per-instance frustum culling of the auto-instanced props (built on the first update after loading). */
  private updateInstanceCulling(): void {
    if (!this.instanceCuller) {
      if (this.exteriorShellRoots.length === 0) return; // modules not attached yet
      const roots = this.scene.children.filter((o) => o.name.startsWith('Module_'));
      this.instanceCuller = new InstanceCuller(roots);
      // Stained-glass windows are flat double-sided transparent panes: three draws such materials twice
      // (back faces, then front faces) and flips material.side + needsUpdate around each draw, which
      // re-resolves their shader program twice per frame. For a flat pane only one side faces the camera,
      // so a single double-sided pass draws the same pixels with half the draw calls and no re-resolve.
      for (const root of roots) {
        root.traverse((o) => {
          const m = (o as THREE.Mesh).material;
          if (!m || Array.isArray(m) || !m.transparent || m.side !== THREE.DoubleSide) return;
          if (m.name.includes('StainedGlass')) m.forceSinglePass = true;
        });
      }
    }
    // A pending sun-shadow update renders every caster: give it the full instance sets
    if (this.renderer.shadowMap.needsUpdate) this.instanceCuller.showAll();
    else this.instanceCuller.update(this.frustum, this.pondReflector.visible ? POND.waterY : null);
  }

  /** Rough screen fraction covered by the pond (bounding box of its projected corners, NDC area / 4). */
  private pondScreenFraction(camera: THREE.Camera): number {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    const b = this.pondBox;
    const v = this.reflCorner;
    for (let i = 0; i < 8; i++) {
      v.set(i & 1 ? b.max.x : b.min.x, i & 2 ? b.max.y : b.min.y, i & 4 ? b.max.z : b.min.z);
      v.applyMatrix4(camera.matrixWorldInverse);
      if (v.z > -0.5) return 1; // a corner at / behind the camera plane: treat as large
      v.applyMatrix4((camera as THREE.PerspectiveCamera).projectionMatrix);
      minX = Math.min(minX, v.x);
      maxX = Math.max(maxX, v.x);
      minY = Math.min(minY, v.y);
      maxY = Math.max(maxY, v.y);
    }
    const w = Math.min(maxX, 1) - Math.max(minX, -1);
    const h = Math.min(maxY, 1) - Math.max(minY, -1);
    return w > 0 && h > 0 ? (w * h) / 4 : 0;
  }

  private buildReflectivePond(multisample: number): void {
    const pondGeo = new THREE.PlaneGeometry(POND.width, POND.depth);
    const reflector = new Reflector(pondGeo, {
      clipBias: 0.003,
      textureWidth: this.reflectorRes,
      textureHeight: this.reflectorRes,
      color: 0x6f90a1,
      multisample,
    });
    const origBeforeRender = reflector.onBeforeRender.bind(reflector);
    reflector.onBeforeRender = (renderer, scene, camera, geometry, material, group) => {
      if (scene.overrideMaterial !== null) return;

      // Throttle reflector renders intelligently while keeping smooth 1:1 lockstep during desktop movement
      this.reflFrameCounter++;
      const distSq = this.lastReflCamPos.distanceToSquared(camera.position);
      const qDot = Math.abs(this.lastReflCamQuat.dot(camera.quaternion));
      const camMoved = distSq > 0.0004 || 1.0 - qDot > 0.000015;
      const timeChanged = Math.abs(this.lighting.timeHours - this.lastReflTimeHours) > 0.002;
      const stationaryPeriod = this.reflStationaryPeriod;
      const shouldRender =
        this.reflDirty ||
        timeChanged ||
        this.timeline.isHistorical ||
        (camMoved && !this.reflSmallOnScreen
          ? !this.reflHalfRate || (this.reflFrameCounter & 1) === 0
          : this.reflFrameCounter % stationaryPeriod === 0);

      if (!shouldRender) return;

      if (!this.reflLiteBuilt) this.buildReflectorLiteList();
      this.reflDirty = false;
      this.lastReflCamPos.copy(camera.position);
      this.lastReflCamQuat.copy(camera.quaternion);
      this.lastReflTimeHours = this.lighting.timeHours;

      // Zero-allocation temporary hide of interior/distant detail meshes (~80% lighter reflection pass!)
      const hiddenCount = this.reflectorHiddenObjs.length;
      for (let i = 0; i < hiddenCount; i++) {
        const obj = this.reflectorHiddenObjs[i];
        this.reflectorSavedVis[i] = obj.visible;
        obj.visible = false;
      }
      origBeforeRender(renderer, scene, camera, geometry, material, group);
      for (let i = 0; i < hiddenCount; i++) {
        this.reflectorHiddenObjs[i].visible = this.reflectorSavedVis[i];
      }
    };
    reflector.rotation.x = -Math.PI / 2;
    // Water surface at the layout's pond water level, below the coping that follows the sloped bank
    reflector.position.set(POND.cx, POND.waterY, POND.cz);
    this.pondReflector = reflector;
    this.scene.add(reflector);

    const waterOverlayMat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      uniforms: this.waterUniforms,
      vertexShader: /* glsl */ `
        varying vec2 vUv;
        varying vec3 vWorldPos;
        void main() {
          vUv = uv;
          vec4 wp = modelMatrix * vec4(position, 1.0);
          vWorldPos = wp.xyz;
          gl_Position = projectionMatrix * viewMatrix * wp;
        }
      `,
      fragmentShader: /* glsl */ `
        uniform float uTime;
        uniform vec3 uSunDir;
        uniform vec3 uSunColor;
        uniform float uNightFactor;
        uniform float uRainFactor;
        varying vec2 vUv;
        varying vec3 vWorldPos;

        void main() {
          vec2 p = vUv * vec2(22.0, 26.0);
          // Concentric animated fountain ripples radiating outward from center of pond!
          float distC = length(vWorldPos.xz - vec2(${FOUNTAIN_XZ.x.toFixed(3)}, ${FOUNTAIN_XZ.z.toFixed(3)}));
          float ringWave = sin(distC * 3.8 - uTime * 4.2) * exp(-distC * 0.14);
          float foamRing = smoothstep(0.65, 0.98, sin(distC * 2.5 - uTime * 3.2)) * exp(-abs(distC - 2.4) * 1.4) * 0.55;

          // Raindrop micro-ripples dancing across the pond surface when Weather = Rain!
          float rainRipple = 0.0;
          if (uRainFactor > 0.01) {
            vec2 rp = vWorldPos.xz * 1.45;
            vec2 cell = floor(rp);
            vec2 f = fract(rp) - 0.5;
            float seed = fract(sin(dot(cell, vec2(127.1, 311.7))) * 43758.5453);
            float tR = fract(uTime * 1.65 + seed);
            float dR = length(f);
            rainRipple = sin((dR - tR * 0.45) * 42.0) * exp(-dR * 8.0) * (1.0 - tR) * uRainFactor;
          }

          float w1 = sin(p.x * 1.35 + uTime * 1.25) * cos(p.y * 1.2 - uTime * 0.9);
          float w2 = sin((p.x * 0.9 - p.y * 1.1) * 2.1 + uTime * 1.65);
          float dx = cos(p.x * 1.35 + uTime * 1.25) * 0.03 + ringWave * 0.06 + rainRipple * 0.09;
          float dz = -sin(p.y * 1.2 - uTime * 0.9) * 0.03 + ringWave * 0.06 + rainRipple * 0.09;
          vec3 N = normalize(vec3(dx, 1.0, dz));

          vec3 V = normalize(cameraPosition - vWorldPos);
          float ndv = max(dot(N, V), 0.0);
          float fresnel = pow(1.0 - ndv, 2.6);

          vec3 H = normalize(normalize(uSunDir) + V);
          float spec = pow(max(dot(N, H), 0.0), 120.0) * (1.0 - uNightFactor * 0.92);

          // Rich Mediterranean teal-blue pond water with white fountain splash foam & clear mirror reflections!
          vec3 deepCol = mix(vec3(0.05, 0.28, 0.36), vec3(0.02, 0.07, 0.13), uNightFactor);
          float rippleSheen = smoothstep(0.45, 0.95, (w1 + w2) * 0.5 + 0.5) * 0.18 + max(0.0, ringWave) * 0.22;
          vec3 col = deepCol + vec3(0.55, 0.78, 0.88) * rippleSheen * (1.0 - uNightFactor * 0.6);
          col = mix(col, vec3(0.92, 0.97, 1.0), clamp(foamRing, 0.0, 0.85));
          col += uSunColor * spec * 2.4;

          float alpha = clamp(0.36 * (1.0 - fresnel * 0.65) + foamRing * 0.55 + spec * 0.65, 0.14, 0.85);
          gl_FragColor = vec4(col, alpha);
        }
      `,
    });

    const overlay = new THREE.Mesh(pondGeo, waterOverlayMat);
    overlay.rotation.x = -Math.PI / 2;
    overlay.position.set(POND.cx, POND.waterY + 0.015, POND.cz);
    this.scene.add(overlay);
  }

  private downgradePhysicalToStandard(mat: THREE.MeshPhysicalMaterial): THREE.MeshStandardMaterial {
    const std = new THREE.MeshStandardMaterial({
      name: mat.name,
      color: mat.color,
      map: mat.map,
      normalMap: mat.normalMap,
      normalScale: mat.normalScale,
      roughnessMap: mat.roughnessMap,
      roughness: mat.name.includes('FloorMarble') ? Math.max(0.14, mat.roughness * 0.72) : mat.roughness,
      metalness: mat.metalness,
      metalnessMap: mat.metalnessMap,
      emissive: mat.emissive,
      emissiveMap: mat.emissiveMap,
      emissiveIntensity: mat.emissiveIntensity,
      side: mat.side,
      transparent: mat.transparent,
      opacity: mat.opacity,
      depthWrite: mat.depthWrite,
      alphaTest: mat.alphaTest,
      vertexColors: Boolean(mat.vertexColors),
      envMap: mat.envMap,
      envMapIntensity: mat.envMapIntensity,
      lightMap: mat.lightMap,
      lightMapIntensity: mat.lightMapIntensity,
    });
    mat.dispose();
    return std;
  }

  /**
   * Multi-Scale Macro Anti-Tiling Weathering + Atmospheric Height Haze (Cathedral volumetric depth!).
   * Uses a lean 1-octave variant on mobile GPUs to cut stone fragment shader ALU cost.
   */
  private injectStoneAntiTilingAndHeightFog(mat: THREE.MeshStandardMaterial, lean: boolean): void {
    const hazeU = this.hazeUniforms;
    mat.customProgramCacheKey = () =>
      lean ? 'sagrada-stone-antitiling-mobile-v1' : 'sagrada-stone-antitiling-v1';
    mat.onBeforeCompile = (shader) => {
      shader.uniforms.uHazeColor = hazeU.uHazeColor;
      shader.uniforms.uHazeStrength = hazeU.uHazeStrength;
      shader.vertexShader = shader.vertexShader.replace(
        '#include <common>',
        `#include <common>\nvarying vec3 vWorldPosAAA;`
      );
      shader.vertexShader = shader.vertexShader.replace(
        '#include <worldpos_vertex>',
        `#include <worldpos_vertex>\nvec4 wpAAA = vec4(transformed, 1.0);\n#ifdef USE_INSTANCING\nwpAAA = instanceMatrix * wpAAA;\n#endif\nwpAAA = modelMatrix * wpAAA;\nvWorldPosAAA = wpAAA.xyz;`
      );
      shader.fragmentShader = shader.fragmentShader.replace(
        '#include <common>',
        `#include <common>\nuniform vec3 uHazeColor;\nuniform float uHazeStrength;\nvarying vec3 vWorldPosAAA;`
      );
      if (lean) {
        shader.fragmentShader = shader.fragmentShader.replace(
          '#include <map_fragment>',
          `#include <map_fragment>
           float macroW1 = sin(vWorldPosAAA.x * 0.14 + vWorldPosAAA.z * 0.11) * cos(vWorldPosAAA.y * 0.09);
           float groundPatina = mix(0.88, 1.02, clamp(vWorldPosAAA.y * 0.0714, 0.0, 1.0));
           diffuseColor.rgb *= (0.95 + 0.08 * macroW1) * groundPatina;`
        );
      } else {
        // Break macro texture tiling via smooth 3D world-space multi-frequency stone variation + base ground patina
        shader.fragmentShader = shader.fragmentShader.replace(
          '#include <map_fragment>',
          `#include <map_fragment>
           float macroW1 = sin(vWorldPosAAA.x * 0.14 + vWorldPosAAA.z * 0.11) * cos(vWorldPosAAA.y * 0.09 - vWorldPosAAA.x * 0.07);
           float macroW2 = sin(vWorldPosAAA.y * 0.31 + vWorldPosAAA.z * 0.23) * cos(vWorldPosAAA.x * 0.27);
           float macroTone = 0.94 + 0.09 * macroW1 + 0.045 * macroW2;
           float groundPatina = mix(0.87, 1.03, smoothstep(0.0, 14.0, vWorldPosAAA.y));
           diffuseColor.rgb *= macroTone * groundPatina;`
        );
        // Subtle atmospheric height-stratified cathedral haze in high vaults (Y = 22..65m)
        shader.fragmentShader = shader.fragmentShader.replace(
          '#include <fog_fragment>',
          `#include <fog_fragment>
           float camDistAAA = length(vWorldPosAAA - cameraPosition);
           float vaultBand = smoothstep(14.0, 52.0, vWorldPosAAA.y) * (1.0 - smoothstep(68.0, 115.0, vWorldPosAAA.y));
           float heightHaze = clamp((camDistAAA / 95.0) * vaultBand * uHazeStrength, 0.0, 0.32);
           gl_FragColor.rgb = mix(gl_FragColor.rgb, uHazeColor, heightHaze);`
        );
      }
    };
    mat.needsUpdate = true;
  }

  private injectTreeWindSway(mat: THREE.MeshStandardMaterial): void {
    const windU = this.windUniform;
    mat.customProgramCacheKey = () => 'sagrada-tree-wind-v1';
    mat.onBeforeCompile = (shader) => {
      shader.uniforms.uWindTime = windU;
      shader.vertexShader = shader.vertexShader.replace(
        '#include <common>',
        `#include <common>\nuniform float uWindTime;`
      );
      shader.vertexShader = shader.vertexShader.replace(
        '#include <begin_vertex>',
        `#include <begin_vertex>
         float swayMask = clamp((position.y - 2.0) / 8.0, 0.0, 1.0);
         transformed.x += sin(uWindTime * 1.15 + position.z * 0.4 + position.y * 0.25) * 0.14 * swayMask;
         transformed.z += cos(uWindTime * 0.95 + position.x * 0.35) * 0.10 * swayMask;`
      );
    };
    mat.needsUpdate = true;
  }

  public async loadAllModules(
    camera: THREE.PerspectiveCamera,
    collision: CollisionSystem,
    onProgress: (fraction: number, status: LoadStatus) => void
  ): Promise<void> {
    THREE.Cache.enabled = true;

    let managerLoaded = 0;
    let managerTotal = 1;
    let glbDlFrac = 0;
    let lastEmitted = 0;
    const assetsStatus: LoadStatus = () => t('load.assets');
    let lastStatus: LoadStatus = assetsStatus;

    const report = (frac: number, status?: LoadStatus) => {
      if (status) lastStatus = status;
      const clamped = Math.min(1.0, Math.max(lastEmitted, frac));
      lastEmitted = clamped;
      onProgress(clamped, lastStatus);
    };

    const loadingManager = new THREE.LoadingManager();
    loadingManager.onProgress = (_url, loaded, total) => {
      managerLoaded = loaded;
      managerTotal = Math.max(1, total);
      const texFrac = managerLoaded / managerTotal;
      // Blend GLB byte progress + shared PBR WebP texture completion into 0..0.64
      report((glbDlFrac * 0.55 + texFrac * 0.45) * 0.64, assetsStatus);
    };

    const quality = getBootQuality();
    if (quality.maxTextureSize <= 512) {
      // Low tier: the asset pipeline writes 512 px PBR maps and 1024 px lightmaps next to the full-size
      // ones (blender/common.py write_low_variant): ~2.5 MB less to download, decode and upload
      loadingManager.setURLModifier((url) =>
        url.replace('/textures/pbr/', '/textures/pbr_low/').replace('/textures/lightmaps/', '/textures/lightmaps_low/')
      );
    }

    const dracoLoader = new DRACOLoader(loadingManager);
    dracoLoader.setDecoderPath('./draco/');
    dracoLoader.setWorkerLimit(Math.min(4, navigator.hardwareConcurrency || 2));
    dracoLoader.preload();
    const loader = new GLTFLoader(loadingManager);
    loader.setDRACOLoader(dracoLoader);
    const texLoader = new THREE.TextureLoader(loadingManager);

    const eixampleNightTex = this.createEixampleNightWindowTexture();
    const maxAniso = Math.min(quality.anisotropy, this.renderer.capabilities.getMaxAnisotropy());
    const lightmapCache = new Map<string, THREE.Texture>();
    // Share identical MeshStandardMaterials across all 7 GLBs (dramatically cuts GPU textures & shader compiles!)
    const sharedMaterials = new Map<string, THREE.MeshStandardMaterial>();
    const enhancedMaterials = new WeakSet<THREE.Material>();

    const configureMaterial = (mat: THREE.MeshStandardMaterial, obj: THREE.Mesh) => {
      const matName = mat.name;
      const isStainedGlass = obj.name.includes('StainedGlass') || matName.includes('StainedGlass');
      const isGlassCase = obj.name.includes('GlassCases') || obj.name.includes('ElevatorShaftGlass') || matName.includes('GlassCase');
      const isFoliage = matName.includes('FoliagePark') || matName.includes('FoliageCypress');

      if (!enhancedMaterials.has(mat)) {
        enhancedMaterials.add(mat);
        for (const tex of [mat.map, mat.normalMap, mat.roughnessMap]) {
          if (tex) {
            tex.anisotropy = maxAniso;
            tex.needsUpdate = true;
          }
        }
        if (
          matName.includes('SandstoneWarm') ||
          matName.includes('NativityStone') ||
          matName.includes('PassionStone') ||
          matName.includes('VaultStone') ||
          matName.includes('CryptStone')
        ) {
          this.injectStoneAntiTilingAndHeightFog(mat, quality.leanStoneShader);
        }
        if (
          obj.name === 'Interior_MarbleFloor' ||
          matName.includes('PorphyryRed') ||
          matName.includes('GoldAccent')
        ) {
          mat.envMapIntensity = obj.name === 'Interior_MarbleFloor' ? 0.85 : 0.72;
          if (!this.interiorReflectiveMats.includes(mat)) {
            this.interiorReflectiveMats.push(mat);
          }
        }
        if (isStainedGlass) {
          mat.side = THREE.DoubleSide;
          mat.roughness = 0.14;
          mat.transparent = true;
          mat.opacity = 0.92;
        }
        if (isGlassCase) {
          mat.transparent = true;
          mat.opacity = 0.22;
          mat.roughness = 0.06;
          mat.depthWrite = false;
          mat.side = THREE.DoubleSide;
        }
        if (matName.includes('EixampleFacade')) {
          mat.emissive.copy(this.nightWindowCol);
          mat.emissiveMap = eixampleNightTex;
          mat.emissiveIntensity = 0.0;
          if (!this.eixampleNightMats.includes(mat)) {
            this.eixampleNightMats.push(mat);
          }
        }
        if (isFoliage) {
          this.injectTreeWindSway(mat);
        }
      }
    };

    const maybeDowngradeClearcoat = (mat: THREE.MeshStandardMaterial): THREE.MeshStandardMaterial => {
      if (mat instanceof THREE.MeshPhysicalMaterial) {
        const keepClearcoat =
          quality.keepClearcoat && (mat.name.includes('FloorMarble') || mat.name.includes('PorphyryRed'));
        if (!keepClearcoat) {
          return this.downgradePhysicalToStandard(mat);
        }
      }
      return mat;
    };

    const processLoadedRoot = (spec: ModelSpec, root: THREE.Group) => {
      root.name = `Module_${spec.id}`;
      root.traverse((obj) => {
        if (!(obj instanceof THREE.Mesh)) return;
        let mat = obj.material instanceof THREE.MeshStandardMaterial ? obj.material : null;
        const matName = mat ? mat.name : '';
        const meshName = obj.name;
        const isStainedGlass = meshName.includes('StainedGlass') || matName.includes('StainedGlass');
        const isGlassCase = meshName.includes('GlassCases') || meshName.includes('ElevatorShaftGlass') || matName.includes('GlassCase');

        // Selective Shadow Casters: ONLY major sunlight-blocking exterior architecture casts 2K sun shadows!
        let castShadow = false;
        if (!isStainedGlass && !isGlassCase) {
          if (spec.id === 'facades') {
            castShadow = !meshName.includes('Doors') && !meshName.includes('Doves') && !meshName.includes('EntranceStairs');
          } else if (spec.id === 'towers') {
            castShadow = !meshName.includes('InternalStair') && !meshName.includes('RoofStairs');
          } else if (spec.id === 'interior') {
            castShadow = meshName === 'Interior_NaveWalls';
          } else if (spec.id === 'cloister_crypt') {
            castShadow = meshName === 'Cloister_And_Sacristies';
          } else if (spec.id === 'eixample') {
            castShadow =
              meshName.startsWith('Eixample_Buildings') ||
              meshName === 'Eixample_Roofs' ||
              meshName.startsWith('PlaneTree') ||
              meshName.startsWith('CypressTree');
          }
        }
        obj.castShadow = castShadow;

        const skipReceiveShadow =
          isStainedGlass ||
          isGlassCase ||
          meshName === 'Eixample_DistantCity' ||
          meshName === 'Barcelona_HorizonHills' ||
          meshName === 'Barcelona_MediterraneanSea' ||
          meshName.includes('InternalStair') ||
          meshName.startsWith('Crypt_');
        obj.receiveShadow = !skipReceiveShadow;

        if (mat) {
          const lmSpec = LIGHTMAP_BY_MESH[meshName];
          const lmTex = lightmapCache.get(meshName);
          const hasUniqueLightmap = Boolean(lmSpec && lmTex && obj.geometry.attributes.uv1);

          if (!hasUniqueLightmap && matName) {
            const cached = sharedMaterials.get(matName);
            if (cached) {
              // Dispose redundant duplicate material/texture wrappers and reuse the canonical shared material
              if (cached !== mat) {
                if (mat.map && mat.map !== cached.map) mat.map.dispose();
                if (mat.normalMap && mat.normalMap !== cached.normalMap) mat.normalMap.dispose();
                if (mat.roughnessMap && mat.roughnessMap !== cached.roughnessMap) mat.roughnessMap.dispose();
                mat.dispose();
                obj.material = cached;
              }
              configureMaterial(cached, obj);
            } else {
              mat = maybeDowngradeClearcoat(mat);
              obj.material = mat;
              sharedMaterials.set(matName, mat);
              configureMaterial(mat, obj);
            }
          } else {
            mat = maybeDowngradeClearcoat(mat);
            obj.material = mat;
            if (hasUniqueLightmap && lmSpec && lmTex) {
              mat.lightMap = lmTex;
              mat.lightMapIntensity = lmSpec.intensity;
              mat.needsUpdate = true;
            }
            configureMaterial(mat, obj);
          }
        }
      });

      const stats = optimizeWithAutoInstancing(root);
      this.instancedGroups += stats.instancedMeshCount;
      this.savedDrawCalls += stats.savedDrawCalls;

      this.scene.add(root);
      collision.registerCollisionMeshes(root);
      this.lighting.registerLoadedMaterials(root);
      this.timeline.registerModule(root);

      // Register spatial zone & pond-reflector culling lists ONCE (no per-frame scene traversals!)
      if (spec.id === 'eixample' || spec.id === 'plaza_life') {
        this.weather.registerExteriorGroundMaterials(root);
        this.weather.registerStreetLamps(root);
      }
      if (spec.id === 'facades') {
        this.exteriorShellRoots.push(root);
      } else if (spec.id === 'furnishings') {
        this.interiorDeepMeshes.push(root);
        this.reflectorHiddenObjs.push(root);
      } else if (spec.id === 'plaza_life') {
        this.plazaLifeRoot = root;
        this.reflectorHiddenObjs.push(root);
      } else if (spec.id === 'interior') {
        for (const child of root.children) {
          const n = child.name;
          if (n !== 'Interior_NaveWalls' && !n.includes('StainedGlass')) {
            this.interiorDeepMeshes.push(child);
            this.reflectorHiddenObjs.push(child);
          }
        }
      } else if (spec.id === 'cloister_crypt') {
        for (const child of root.children) {
          if (child.name.startsWith('Crypt_')) {
            this.cryptMeshes.push(child);
            this.reflectorHiddenObjs.push(child);
          }
        }
      } else if (spec.id === 'eixample') {
        this.eixampleRoot = root;
        for (const child of root.children) {
          const n = child.name;
          const isTree = n.startsWith('Instanced_PlaneTree') || n.startsWith('Instanced_CypressTree');
          const isDetail =
            n === 'Eixample_BalconiesIron' ||
            n === 'Eixample_ShopAwnings' ||
            n === 'Eixample_DistantCity' ||
            n === 'Barcelona_HorizonHills' ||
            n === 'Barcelona_MediterraneanSea' ||
            n.startsWith('Instanced_StreetLamp');
          if (isTree || isDetail) {
            this.eixampleDetailMeshes.push(child);
          }
          // Low tier: trees also stay out of the (160 px) pond reflection — ~38k fewer reflected triangles
          if (isDetail || (isTree && quality.reflectorLite)) {
            this.reflectorHiddenObjs.push(child);
          }
        }
      } else if (spec.id === 'towers') {
        this.exteriorShellRoots.push(root);
        for (const child of root.children) {
          const n = child.name;
          if (n === 'Towers_InternalStaircases' || n === 'Towers_InternalStairRails') {
            this.internalStairMeshes.push(child);
            this.reflectorHiddenObjs.push(child);
          } else if (!n.includes('Nativity') && !n.includes('Passion')) {
            this.highTowerMeshes.push(child);
          }
        }
      }
    };

    // ── STAGE 1 (0% -> 64%): Download all 7 compact GLBs + shared WebP PBR textures + lightmaps + candles + compact HDRIs ──
    report(0.02, assetsStatus);
    const totalWeight = MODEL_SPECS.reduce((sum, s) => sum + s.weightKB, 0);
    const fileProgress = new Map<string, number>();

    const updateDlProgress = () => {
      let weighted = 0;
      for (const s of MODEL_SPECS) {
        weighted += (fileProgress.get(s.id) ?? 0) * s.weightKB;
      }
      glbDlFrac = Math.min(1, weighted / totalWeight);
      const texFrac = managerLoaded / managerTotal;
      report((glbDlFrac * 0.55 + texFrac * 0.45) * 0.64, assetsStatus);
    };

    const lightmapsPromise = Promise.all(
      Object.entries(LIGHTMAP_BY_MESH).map(async ([meshName, spec]) => {
        try {
          const lmTex = await texLoader.loadAsync(spec.url);
          lmTex.flipY = false;
          lmTex.channel = 1;
          lmTex.colorSpace = THREE.SRGBColorSpace;
          lmTex.minFilter = THREE.LinearMipmapLinearFilter;
          lmTex.magFilter = THREE.LinearFilter;
          lightmapCache.set(meshName, lmTex);
        } catch {
          // Optional
        }
      })
    );

    const candlesPromise = this.candles.loadFromManifest('./data/candles.json').catch((err) => {
      console.warn('[Candles] Manifest load fallback:', err);
      return 0;
    });

    const hdriPromise = this.lighting.loadHdris();

    const settled = await Promise.allSettled(
      MODEL_SPECS.map(async (spec) => {
        try {
          const gltf = await loader.loadAsync(spec.url, (ev) => {
            const expectedBytes = ev.lengthComputable && ev.total > 0 ? ev.total : spec.weightKB * 1024;
            const frac = Math.min(1, ev.loaded / expectedBytes);
            fileProgress.set(spec.id, Math.max(fileProgress.get(spec.id) ?? 0, frac));
            updateDlProgress();
          });
          return { spec, gltf };
        } finally {
          fileProgress.set(spec.id, 1.0);
          updateDlProgress();
        }
      })
    );

    // Core architecture is mandatory; optional context modules may fail without blocking the visit.
    const loadedGltfs: Array<{ spec: ModelSpec; gltf: { scene: THREE.Group } }> = [];
    const failedCore: string[] = [];
    settled.forEach((res, i) => {
      const spec = MODEL_SPECS[i];
      if (res.status === 'fulfilled') {
        loadedGltfs.push(res.value);
      } else {
        console.error(`[Load] Module "${spec.id}" failed:`, res.reason);
        this.failedModules.push(spec.id);
        if (CORE_MODULE_IDS.has(spec.id)) failedCore.push(spec.id);
      }
    });
    if (failedCore.length > 0) {
      dracoLoader.dispose();
      throw new AssetLoadError(failedCore);
    }

    await Promise.all([lightmapsPromise, candlesPromise]);
    dracoLoader.dispose();
    performance.mark('sagrada:glb-loaded'); // bench startup milestone (all core GLBs + lightmaps)

    // ── STAGE 2 (64% -> 76%): Attach modules, deduplicate materials & optimize GPU instancing ──
    report(0.66, () => t('load.assemble'));
    await nextFrame();
    for (let i = 0; i < loadedGltfs.length; i++) {
      const { spec, gltf } = loadedGltfs[i];
      processLoadedRoot(spec, gltf.scene);
      report(0.66 + ((i + 1) / loadedGltfs.length) * 0.10, () => t('load.module', { name: t(spec.labelKey) }));
      if (i % 2 === 1) await nextFrame();
    }

    if (quality.maxTextureSize < 4096) {
      let scaled = 0;
      for (const { gltf } of loadedGltfs) scaled += downscaleTextures(gltf.scene, quality.maxTextureSize);
      if (scaled > 0) console.info(`[Quality] ${scaled} textures downscaled to <= ${quality.maxTextureSize}px`);
    }
    performance.mark('sagrada:load:assembled');

    // ── STAGE 3 (76% -> 88%): finish HDRI PMREM IBL ──
    // (the collision BVH is built right after the first frame, before the player can move: see main.ts)
    report(0.84, () => t('load.environment'));
    await nextFrame();
    await hdriPromise;
    performance.mark('sagrada:load:hdri');

    report(0.88, () => t('load.shaders'));
  }

  /**
   * Shader + GPU warm-up behind the loading card (call after loadAllModules and the render pipeline).
   * Compiles exactly the program variants the first frames use, all at once so the driver can compile
   * them in parallel (KHR_parallel_shader_compile): the "linear" variant used for every off-screen pass
   * (pond reflector, interior probe and, on tiers with a composer, the main view) and the tone-mapped
   * canvas variant only when the main view renders straight to the canvas. Synchronous first-use
   * compiles in the probe / reflector renders used to cost ~5 s on desktop.
   * The interior reflection probe is not captured here (the visitor starts outside): see
   * captureDeferredProbe(), run in idle time after the first frame or on entering the basilica.
   */
  public async warmUp(
    camera: THREE.PerspectiveCamera,
    collision: CollisionSystem,
    mainViewOffscreen: boolean,
    renderFrame: () => void,
    onProgress: (fraction: number, status: LoadStatus) => void
  ): Promise<void> {
    onProgress(0.9, () => t('load.shaders'));
    await nextFrame();
    // Start-view visibility first (zone culling, sky, particles): lights and visible set as in frame 1
    this.update(0.016, camera, collision.getIndoorFactor(camera.position));
    // compile() visits every mesh regardless of visibility; only lights are gathered from visible objects
    const linearTarget = this.interiorProbeRT;
    const prevTarget = this.renderer.getRenderTarget();
    this.renderer.setRenderTarget(linearTarget);
    const compiling: Promise<unknown>[] = [this.renderer.compileAsync(this.scene, camera)];
    this.renderer.setRenderTarget(prevTarget);
    if (!mainViewOffscreen) compiling.push(this.renderer.compileAsync(this.scene, camera));
    performance.mark('sagrada:load:compile-issued');
    // While the driver compiles in its own threads, upload every material texture (the main thread
    // would otherwise idle here and pay the uploads inside the first frame / on entering the basilica)
    this.uploadAllTextures();
    performance.mark('sagrada:load:textures-uploaded');
    await Promise.all(compiling);
    performance.mark('sagrada:load:compiled');

    onProgress(0.96, () => t('load.firstFrame'));
    await nextFrame();
    // First real frame (shadow map, pond reflector, texture uploads) behind the loading card
    this.lighting.requestShadowUpdate(true);
    this.interiorProbeDirty = true;
    this.update(0.016, camera, collision.getIndoorFactor(camera.position));
    // (still compiles the few shadow-depth / post-pass programs synchronously: ~3 on low, ~18 on ultra)
    renderFrame();
    performance.mark('sagrada:load:render1');
    onProgress(1.0, () => t('load.ready'));
  }

  private uploadAllTextures(): void {
    const seen = new Set<THREE.Texture>();
    this.scene.traverse((obj) => {
      const m = (obj as THREE.Mesh).material;
      if (!m) return;
      for (const mat of Array.isArray(m) ? m : [m]) {
        const std = mat as THREE.MeshStandardMaterial;
        for (const tex of [std.map, std.normalMap, std.roughnessMap, std.metalnessMap, std.emissiveMap, std.aoMap, std.lightMap, std.alphaMap]) {
          if (!tex || seen.has(tex) || !tex.image) continue;
          seen.add(tex);
          this.renderer.initTexture(tex);
        }
      }
    });
  }

  /** Captures the interior reflection probe if it is still pending (idle time after the first frame). */
  public captureDeferredProbe(): void {
    if (this.interiorProbeDirty) this.captureInteriorReflectionProbe();
  }

  public update(dt: number, camera: THREE.PerspectiveCamera, indoorFactor: number): void {
    const cameraPos = camera.position;
    this.lastIndoorFactor = indoorFactor;
    this.waterUniforms.uTime.value += dt;
    this.waterUniforms.uSunDir.value.copy(this.lighting.sunDir);
    this.waterUniforms.uSunColor.value.copy(this.lighting.sunLight.color);
    this.waterUniforms.uNightFactor.value = this.lighting.nightFactor;
    this.windUniform.value += dt;

    // Warm golden atmospheric haze in the 45-60m vaults by day, deep indigo at night (zero allocations!)
    this.hazeUniforms.uHazeColor.value
      .copy(this.hazeDayCol)
      .lerp(this.hazeNightCol, this.lighting.nightFactor * 0.88);
    this.hazeUniforms.uHazeStrength.value = THREE.MathUtils.lerp(0.18, 0.11, this.lighting.nightFactor);

    camera.updateMatrixWorld();
    this.projScreenMat.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    this.frustum.setFromProjectionMatrix(this.projScreenMat);
    const distPond = Math.hypot(cameraPos.x - FOUNTAIN_XZ.x, cameraPos.z - FOUNTAIN_XZ.z);
    const underground = isEyeUnderground(cameraPos.x, cameraPos.y, cameraPos.z);
    const pondVisible =
      indoorFactor < 0.85 &&
      !underground &&
      distPond < 250 &&
      this.frustum.intersectsBox(this.pondBox);
    if (pondVisible && !this.pondReflector.visible) {
      this.reflDirty = true;
    }
    this.pondReflector.visible = pondVisible;
    this.reflectorActive = pondVisible;
    this.reflSmallOnScreen = pondVisible && this.pondScreenFraction(camera) < 0.02;

    const distBasilica = Math.hypot(cameraPos.x - BASILICA_XZ.x, cameraPos.z - BASILICA_XZ.z);
    const distApse = Math.hypot(cameraPos.x - APSE_XZ.x, cameraPos.z - APSE_XZ.z);
    const distCenter = Math.hypot(cameraPos.x, cameraPos.z);

    // Conservative Spatial Zone Culling (~40-70% triangle & draw-call reduction with ZERO visual pop-in!)
    const showInternalStairs = cameraPos.y > 10.5 && distBasilica < 90.0;
    if (!this.timeline.isHistorical) {
      const inDeepCrypt = underground;
      // Near either crypt stair the nave above stays drawn (it shows through the stair doors)
      const nearCryptStairExit = inDeepCrypt && CRYPT_STAIRS_XZ.some((p) => Math.hypot(cameraPos.x - p.x, cameraPos.z - p.z) <= 6.0);
      const inDeepInterior = !inDeepCrypt && indoorFactor > 0.88 && cameraPos.y < 46.0 && !isNearCryptLevel(cameraPos.x, cameraPos.y, cameraPos.z);
      const farExterior = !inDeepCrypt && indoorFactor < 0.01 && distBasilica > 75.0;

      const showCrypt = cameraPos.y < LAYOUT.levels.nave + EYE_HEIGHT + 0.55 && distApse < 40.0;
      for (let i = 0; i < this.cryptMeshes.length; i++) {
        this.cryptMeshes[i].visible = showCrypt;
      }

      const showDeepInterior = !farExterior && (!inDeepCrypt || nearCryptStairExit);
      for (let i = 0; i < this.interiorDeepMeshes.length; i++) {
        this.interiorDeepMeshes[i].visible = showDeepInterior;
      }

      const showHighTowers = !inDeepCrypt && !inDeepInterior;
      for (let i = 0; i < this.highTowerMeshes.length; i++) {
        this.highTowerMeshes[i].visible = showHighTowers;
      }

      const showExtShells = !inDeepCrypt;
      for (let i = 0; i < this.exteriorShellRoots.length; i++) {
        this.exteriorShellRoots[i].visible = showExtShells;
      }

      if (this.eixampleRoot) this.eixampleRoot.visible = !inDeepCrypt;
      if (this.plazaLifeRoot) this.plazaLifeRoot.visible = !inDeepCrypt && !inDeepInterior;

      const showEixDetails = !inDeepCrypt && !inDeepInterior;
      for (let i = 0; i < this.eixampleDetailMeshes.length; i++) {
        this.eixampleDetailMeshes[i].visible = showEixDetails;
      }

      for (let i = 0; i < this.internalStairMeshes.length; i++) {
        this.internalStairMeshes[i].visible = showInternalStairs && !inDeepCrypt && !inDeepInterior;
      }
    } else {
      for (let i = 0; i < this.exteriorShellRoots.length; i++) this.exteriorShellRoots[i].visible = true;
      if (this.eixampleRoot) this.eixampleRoot.visible = true;
      if (this.plazaLifeRoot) this.plazaLifeRoot.visible = true;
      for (let i = 0; i < this.eixampleDetailMeshes.length; i++) this.eixampleDetailMeshes[i].visible = true;
      for (let i = 0; i < this.highTowerMeshes.length; i++) this.highTowerMeshes[i].visible = true;
    }

    // Jesus Tower Glass Elevator (strictly runs in upper tower core Y=56..136m)
    this.elevator.group.visible = cameraPos.y > 44.0 && distCenter < 34.0;

    if (this.interiorProbeDirty && indoorFactor > 0.15) {
      this.captureInteriorReflectionProbe();
    }

    const windowGlow = THREE.MathUtils.smoothstep(this.lighting.nightFactor, 0.12, 0.85) * 1.45;
    for (let i = 0; i < this.eixampleNightMats.length; i++) {
      this.eixampleNightMats[i].emissiveIntensity = windowGlow;
    }

    this.lighting.update(dt, cameraPos, indoorFactor);
    this.updateInstanceCulling();

    // Update GPU candle flames, stained-glass floor carpets, weather (rain/mist/incense/streetlamp cones)
    this.candles.group.visible = indoorFactor > 0.1 || cameraPos.y < 10.0;
    if (this.candles.group.visible) {
      this.candles.update(dt);
    }
    this.glassCarpets.group.visible = indoorFactor > 0.05 && !underground && cameraPos.y < 52.0;
    if (this.glassCarpets.group.visible) {
      this.glassCarpets.update(this.lighting.eastSunHit, this.lighting.westSunHit, this.lighting.sunDir.y);
    }
    this.weather.update(dt, cameraPos, indoorFactor, this.lighting.nightFactor, this.lighting.dayFactor, this.scene);
    this.waterUniforms.uRainFactor.value = this.weather.rainFactor;

    this.birds.group.visible = indoorFactor < 0.85 && !underground && this.lighting.dayFactor > 0.12 && this.weather.rainFactor < 0.5;
    if (this.birds.group.visible) {
      this.birds.update(dt, this.lighting.dayFactor);
    }

    const fountainNear = indoorFactor < 0.85 && distPond < 165 && !underground;
    this.fountain.points.visible = fountainNear;
    if (fountainNear) {
      this.fountain.update(dt, this.lighting.dayFactor);
    }
  }
}
