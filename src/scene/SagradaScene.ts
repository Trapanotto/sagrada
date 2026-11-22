import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';
import { Reflector } from 'three/examples/jsm/objects/Reflector.js';
import { LightingSystem } from './LightingSystem';
import { GeometryOverlay } from './GeometryOverlay';
import { FlockingBirds } from './FlockingBirds';
import { FountainParticles } from './FountainParticles';
import { optimizeWithAutoInstancing } from './AutoInstancer';
import { ConstructionTimeline } from './ConstructionTimeline';
import { CandleFlames } from './CandleFlames';
import { StainedGlassCarpets } from './StainedGlassCarpets';
import { WeatherSystem } from './WeatherSystem';
import { JesusElevator } from './JesusElevator';
import { CollisionSystem } from './CollisionSystem';
import { isMobileDevice } from '../utils/device';

interface ModelSpec {
  id: string;
  label: string;
  url: string;
  weightKB: number;
}

const MODEL_SPECS: ModelSpec[] = [
  { id: 'facades', label: 'Geburts-, Passions- & Glorienfassade', url: './models/facades.glb', weightKB: 540 },
  { id: 'towers', label: 'Alle 18 Türme & Wendeltreppen', url: './models/towers.glb', weightKB: 1351 },
  { id: 'interior', label: 'Innenraum, Säulenwald & Gewölbe', url: './models/interior.glb', weightKB: 1208 },
  { id: 'furnishings', label: 'Hochaltar, Kapellen & Ausstattung', url: './models/furnishings.glb', weightKB: 367 },
  { id: 'cloister_crypt', label: 'Kreuzgang, Sakristeien & Krypta', url: './models/cloister_crypt.glb', weightKB: 125 },
  { id: 'eixample', label: 'Eixample-Stadtblock & Spiegelteich', url: './models/eixample.glb', weightKB: 154 },
  { id: 'plaza_life', label: 'Parkbänke, Kioske & Stadtmöbel', url: './models/plaza_life.glb', weightKB: 79 },
];

const nextFrame = (): Promise<void> =>
  new Promise((resolve) => requestAnimationFrame(() => resolve()));

const LIGHTMAP_BY_MESH: Record<string, { url: string; intensity: number }> = {
  Interior_HyperboloidVaults: { url: './textures/lightmaps/lightmap_vaults.webp', intensity: 0.58 },
  Interior_MarbleFloor: { url: './textures/lightmaps/lightmap_floor.webp', intensity: 0.48 },
  Interior_NaveWalls: { url: './textures/lightmaps/lightmap_walls.webp', intensity: 0.52 },
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

  public instancedGroups = 0;
  public savedDrawCalls = 0;
  public reflectorActive = true;

  private pondReflector!: Reflector;
  private pondBox = new THREE.Box3(new THREE.Vector3(67.5, -1.0, -17.5), new THREE.Vector3(97.5, 1.5, 17.5));
  private frustum = new THREE.Frustum();
  private projScreenMat = new THREE.Matrix4();

  // Cached 0ms/frame Nave Interior CubeCamera Reflection Probe (gives marble floor real stained-glass & column reflections!)
  private interiorProbeRT: THREE.WebGLCubeRenderTarget;
  private interiorCubeCam: THREE.CubeCamera;
  private interiorPmrem: THREE.PMREMGenerator;
  private interiorPmremReady = false;
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
  private eixampleNightMats: THREE.MeshStandardMaterial[] = [];
  private internalStairMeshes: THREE.Object3D[] = [];
  private interiorOnlyRoots: THREE.Object3D[] = [];

  constructor(private renderer: THREE.WebGLRenderer) {
    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.FogExp2('#c8dff5', 0.0012);

    this.lighting = new LightingSystem(this.scene, this.renderer);
    this.geometryOverlay = new GeometryOverlay();
    this.timeline = new ConstructionTimeline();
    this.scene.add(this.geometryOverlay.group);

    const mobile = isMobileDevice();
    this.birds = new FlockingBirds(mobile ? 8 : 16);
    this.scene.add(this.birds.group);

    this.fountain = new FountainParticles(mobile ? 200 : 420);
    this.scene.add(this.fountain.points);

    this.candles = new CandleFlames();
    this.scene.add(this.candles.group);

    this.glassCarpets = new StainedGlassCarpets();
    this.scene.add(this.glassCarpets.group);

    this.weather = new WeatherSystem();
    this.scene.add(this.weather.group);

    this.elevator = new JesusElevator();
    this.scene.add(this.elevator.group);

    // Prepare cached interior reflection probe (128px on mobile for lower VRAM, 256px on desktop)
    const probeRes = mobile ? 128 : 256;
    this.interiorProbeRT = new THREE.WebGLCubeRenderTarget(probeRes, {
      generateMipmaps: true,
      minFilter: THREE.LinearMipmapLinearFilter,
      type: THREE.HalfFloatType,
    });
    this.interiorCubeCam = new THREE.CubeCamera(0.5, 130, this.interiorProbeRT);
    this.interiorCubeCam.position.set(0, 6.5, 22);
    this.scene.add(this.interiorCubeCam);
    this.interiorPmrem = new THREE.PMREMGenerator(this.renderer);

    this.lighting.onTimeBucketChanged = () => this.captureInteriorReflectionProbe();

    this.buildReflectivePond();
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

    this.interiorCubeCam.update(this.renderer, this.scene);
    const nextEnv = this.interiorPmrem.fromCubemap(this.interiorProbeRT.texture);

    for (const mat of this.interiorReflectiveMats) {
      mat.envMap = nextEnv.texture;
      mat.needsUpdate = true;
    }

    if (this.currentInteriorEnvRT) {
      this.currentInteriorEnvRT.dispose();
    }
    this.currentInteriorEnvRT = nextEnv;

    this.pondReflector.visible = prevPond;
    this.geometryOverlay.group.visible = prevGeo;
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

  private buildReflectivePond(): void {
    const pondGeo = new THREE.PlaneGeometry(29.0, 34.0);
    const mobile = isMobileDevice();
    const reflRes = mobile ? 256 : 384;
    const reflector = new Reflector(pondGeo, {
      clipBias: 0.003,
      textureWidth: reflRes,
      textureHeight: reflRes,
      color: 0x6f90a1,
    });
    const origBeforeRender = reflector.onBeforeRender.bind(reflector);
    reflector.onBeforeRender = (renderer, scene, camera, geometry, material, group) => {
      if (scene.overrideMaterial !== null) return;
      // Render pond reflection EVERY frame in 1:1 lockstep with camera (ZERO judder/stutter when strafing!)
      // while hiding interior-only meshes to keep reflection cost ~70% lighter!
      const savedVis: Array<[THREE.Object3D, boolean]> = [];
      for (const obj of [...this.interiorOnlyRoots, ...this.internalStairMeshes, this.candles.group, this.glassCarpets.group]) {
        savedVis.push([obj, obj.visible]);
        obj.visible = false;
      }
      origBeforeRender(renderer, scene, camera, geometry, material, group);
      for (const [obj, vis] of savedVis) {
        obj.visible = vis;
      }
    };
    reflector.rotation.x = -Math.PI / 2;
    // Water surface sits cleanly at Y = +0.16m inside the +0.36m sculpted coping rim (completely clear above ground!)
    reflector.position.set(82.5, 0.16, 0.0);
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
          float distC = length(vWorldPos.xz - vec2(82.5, 0.0));
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
          col += uSunColor * spec * 1.9;

          float alpha = clamp(0.36 * (1.0 - fresnel * 0.65) + foamRing * 0.55 + spec * 0.65, 0.14, 0.85);
          gl_FragColor = vec4(col, alpha);
        }
      `,
    });

    const overlay = new THREE.Mesh(pondGeo, waterOverlayMat);
    overlay.rotation.x = -Math.PI / 2;
    overlay.position.set(82.5, 0.175, 0.0);
    this.scene.add(overlay);
  }

  /**
   * Multi-Scale Macro Anti-Tiling Weathering + Atmospheric Height Haze (Cathedral volumetric depth!).
   * Eliminates repetitive tiling across 172m towers and adds subtle warm golden elevation haze in high vaults.
   */
  private injectStoneAntiTilingAndHeightFog(mat: THREE.MeshStandardMaterial): void {
    const hazeU = this.hazeUniforms;
    mat.customProgramCacheKey = () => 'sagrada-stone-antitiling-v1';
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
    onProgress: (fraction: number, statusText: string) => void
  ): Promise<void> {
    THREE.Cache.enabled = true;

    let managerLoaded = 0;
    let managerTotal = 1;
    let glbDlFrac = 0;
    let lastEmitted = 0;
    let lastStatus = 'Architektur & Texturen werden geladen…';

    const report = (frac: number, statusText?: string) => {
      if (statusText) lastStatus = statusText;
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
      report((glbDlFrac * 0.55 + texFrac * 0.45) * 0.64, 'Architektur & Texturen werden geladen…');
    };

    const dracoLoader = new DRACOLoader(loadingManager);
    dracoLoader.setDecoderPath('./draco/');
    dracoLoader.setWorkerLimit(Math.min(4, navigator.hardwareConcurrency || 2));
    dracoLoader.preload();
    const loader = new GLTFLoader(loadingManager);
    loader.setDRACOLoader(dracoLoader);
    const texLoader = new THREE.TextureLoader(loadingManager);

    const eixampleNightTex = this.createEixampleNightWindowTexture();
    const maxAniso = Math.min(isMobileDevice() ? 4 : 16, this.renderer.capabilities.getMaxAnisotropy());
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
          this.injectStoneAntiTilingAndHeightFog(mat);
        }
        if (
          obj.name === 'Interior_MarbleFloor' ||
          matName.includes('PorphyryRed') ||
          matName.includes('GoldAccent')
        ) {
          mat.envMapIntensity = obj.name === 'Interior_MarbleFloor' ? 0.85 : 0.72;
          this.interiorReflectiveMats.push(mat);
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
          mat.emissive = new THREE.Color('#ffbd69');
          mat.emissiveMap = eixampleNightTex;
          mat.emissiveIntensity = 0.0;
          this.eixampleNightMats.push(mat);
        }
        if (isFoliage) {
          this.injectTreeWindSway(mat);
        }
      }
    };

    const processLoadedRoot = (spec: ModelSpec, root: THREE.Group) => {
      root.name = `Module_${spec.id}`;
      root.traverse((obj) => {
        if (!(obj instanceof THREE.Mesh)) return;
        const mat = obj.material instanceof THREE.MeshStandardMaterial ? obj.material : null;
        const matName = mat ? mat.name : '';
        const isStainedGlass = obj.name.includes('StainedGlass') || matName.includes('StainedGlass');
        const isGroundOrFloor =
          obj.name.includes('Floor') ||
          obj.name.includes('Carpet') ||
          obj.name.includes('Crosswalks') ||
          obj.name.includes('Streets') ||
          obj.name.includes('Sidewalks') ||
          obj.name.includes('ParkLawns');
        const isGlassCase = obj.name.includes('GlassCases') || obj.name.includes('ElevatorShaftGlass') || matName.includes('GlassCase');

        obj.castShadow = !isStainedGlass && !isGroundOrFloor && !isGlassCase;
        obj.receiveShadow = !isStainedGlass && !isGlassCase;

        if (mat) {
          const lmSpec = LIGHTMAP_BY_MESH[obj.name];
          const lmTex = lightmapCache.get(obj.name);
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
              sharedMaterials.set(matName, mat);
              configureMaterial(mat, obj);
            }
          } else {
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
      if (spec.id === 'eixample' || spec.id === 'plaza_life') {
        this.weather.registerExteriorGroundMaterials(root);
      }
      if (spec.id === 'furnishings' || spec.id === 'cloister_crypt') {
        this.interiorOnlyRoots.push(root);
      }
      if (spec.id === 'towers') {
        root.traverse((o) => {
          if (o.name === 'Towers_InternalStaircases' || o.name === 'Towers_InternalStairRails') {
            this.internalStairMeshes.push(o);
          }
        });
      }
    };

    // ── STAGE 1 (0% -> 64%): Download all 7 compact GLBs + shared WebP PBR textures + lightmaps + candles + compact HDRIs ──
    report(0.02, 'Architektur & Texturen werden geladen…');
    const totalWeight = MODEL_SPECS.reduce((sum, s) => sum + s.weightKB, 0);
    const fileProgress = new Map<string, number>();

    const updateDlProgress = () => {
      let weighted = 0;
      for (const s of MODEL_SPECS) {
        weighted += (fileProgress.get(s.id) ?? 0) * s.weightKB;
      }
      glbDlFrac = Math.min(1, weighted / totalWeight);
      const texFrac = managerLoaded / managerTotal;
      report((glbDlFrac * 0.55 + texFrac * 0.45) * 0.64, 'Architektur & Texturen werden geladen…');
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

    const loadedGltfs = await Promise.all(
      MODEL_SPECS.map(async (spec) => {
        const gltf = await loader.loadAsync(spec.url, (ev) => {
          const expectedBytes = ev.lengthComputable && ev.total > 0 ? ev.total : spec.weightKB * 1024;
          const frac = Math.min(1, ev.loaded / expectedBytes);
          fileProgress.set(spec.id, Math.max(fileProgress.get(spec.id) ?? 0, frac));
          updateDlProgress();
        });
        fileProgress.set(spec.id, 1.0);
        updateDlProgress();
        return { spec, gltf };
      })
    );

    await Promise.all([lightmapsPromise, candlesPromise]);
    dracoLoader.dispose();

    // ── STAGE 2 (64% -> 76%): Attach modules, deduplicate materials & optimize GPU instancing ──
    report(0.66, 'Szene & Materialien werden zusammengesetzt…');
    await nextFrame();
    for (let i = 0; i < loadedGltfs.length; i++) {
      const { spec, gltf } = loadedGltfs[i];
      processLoadedRoot(spec, gltf.scene);
      report(0.66 + ((i + 1) / loadedGltfs.length) * 0.10, `Modul geladen: ${spec.label}`);
      if (i % 2 === 1) await nextFrame();
    }

    // ── STAGE 3 (76% -> 88%): Build 3D BVH collision index & finish HDRI PMREM IBL ──
    report(0.78, '3D-Kollisionsgeometrie wird aufgebaut…');
    await nextFrame();
    const bvhStats = collision.buildBVH();
    console.info(`[Collision] 3D BVH ready: ${bvhStats.triangles.toLocaleString()} tris across ${bvhStats.meshes} meshes in ${bvhStats.buildMs} ms`);
    report(0.84, 'Umgebungslicht & Reflexionen werden berechnet…');
    await nextFrame();
    await hdriPromise;

    // ── STAGE 4 (88% -> 98%): Pre-compile ALL WebGL shaders, shadow map & interior reflection probe ──
    report(0.88, 'Shader & Beleuchtung werden vorbereitet…');
    await nextFrame();
    const prewarmObjs: Array<[THREE.Object3D, boolean]> = [
      [this.candles.group, this.candles.group.visible],
      [this.glassCarpets.group, this.glassCarpets.group.visible],
      [this.lighting.particles.points, this.lighting.particles.points.visible],
      ...this.internalStairMeshes.map((o): [THREE.Object3D, boolean] => [o, o.visible]),
    ];
    for (const [obj] of prewarmObjs) obj.visible = true;
    await this.renderer.compileAsync(this.scene, camera);
    for (const [obj, wasVis] of prewarmObjs) obj.visible = wasVis;

    report(0.94, 'Schatten & Spiegelungen werden gerendert…');
    await nextFrame();
    this.lighting.requestShadowUpdate(true);
    this.captureInteriorReflectionProbe();

    // Warm up the live camera view (uploads all visible GPU textures & renders pond reflector + shadow map ONCE!)
    report(0.97, 'Erster Frame wird vorbereitet…');
    await nextFrame();
    this.update(0.016, camera, collision.getIndoorFactor(camera.position));
    this.renderer.render(this.scene, camera);
    await nextFrame();
    this.renderer.render(this.scene, camera);

    report(1.0, 'Bereit zum Betreten');
  }

  public update(dt: number, camera: THREE.PerspectiveCamera, indoorFactor: number): void {
    const cameraPos = camera.position;
    this.waterUniforms.uTime.value += dt;
    this.waterUniforms.uSunDir.value.copy(this.lighting.sunDir);
    this.waterUniforms.uSunColor.value.copy(this.lighting.sunLight.color);
    this.waterUniforms.uNightFactor.value = this.lighting.nightFactor;
    this.windUniform.value += dt;

    // Restrained warm golden haze in the 45-60m vaults by day, subtle indigo at night
    this.hazeUniforms.uHazeColor.value
      .set('#d8be9a')
      .lerp(new THREE.Color('#141d32'), this.lighting.nightFactor * 0.88);
    this.hazeUniforms.uHazeStrength.value = THREE.MathUtils.lerp(0.14, 0.09, this.lighting.nightFactor);

    camera.updateMatrixWorld();
    this.projScreenMat.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    this.frustum.setFromProjectionMatrix(this.projScreenMat);
    const distPond = Math.hypot(cameraPos.x - 82.5, cameraPos.z);
    const pondVisible =
      indoorFactor < 0.85 &&
      cameraPos.y > -1.0 &&
      distPond < 250 &&
      this.frustum.intersectsBox(this.pondBox);
    this.pondReflector.visible = pondVisible;
    this.reflectorActive = pondVisible;

    // Smart 55k-tri Interior Tower Staircase Culling: ONLY show high tower spiral stairs when up on Emporen/Towers (Y > 10.5m)
    // Never pops in when simply walking through ground-level cathedral portals!
    const distBasilica = Math.hypot(cameraPos.x, cameraPos.z - 8.0);
    const showInternalStairs = cameraPos.y > 10.5 && distBasilica < 68.0;
    for (const sm of this.internalStairMeshes) {
      sm.visible = showInternalStairs;
    }

    const windowGlow = THREE.MathUtils.smoothstep(this.lighting.nightFactor, 0.12, 0.85) * 1.45;
    for (const m of this.eixampleNightMats) {
      m.emissiveIntensity = windowGlow;
    }

    this.lighting.update(dt, cameraPos, indoorFactor);

    // Update GPU candle flames, stained-glass floor carpets, weather (rain/mist/incense/streetlamp cones)
    this.candles.group.visible = indoorFactor > 0.1 || cameraPos.y < 10.0;
    if (this.candles.group.visible) {
      this.candles.update(dt);
    }
    this.glassCarpets.group.visible = indoorFactor > 0.05 && cameraPos.y > -1.0 && cameraPos.y < 52.0;
    if (this.glassCarpets.group.visible) {
      this.glassCarpets.update(this.lighting.eastSunHit, this.lighting.westSunHit, this.lighting.sunDir.y);
    }
    this.weather.update(dt, cameraPos, indoorFactor, this.lighting.nightFactor, this.lighting.dayFactor, this.scene);
    this.waterUniforms.uRainFactor.value = this.weather.rainFactor;

    this.birds.group.visible = indoorFactor < 0.85 && this.lighting.dayFactor > 0.12 && this.weather.rainFactor < 0.5;
    if (this.birds.group.visible) {
      this.birds.update(dt, this.lighting.dayFactor);
    }

    const fountainNear = indoorFactor < 0.85 && distPond < 165 && cameraPos.y > -1.0;
    this.fountain.points.visible = fountainNear;
    if (fountainNear) {
      this.fountain.update(dt, this.lighting.dayFactor);
    }
  }
}
