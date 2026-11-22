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
import { isMobileDevice } from '../utils/device';

interface ModelSpec {
  id: string;
  label: string;
  url: string;
  priority: 'core' | 'background';
}

const MODEL_SPECS: ModelSpec[] = [
  { id: 'facades', label: 'Geburts-, Passions- & Glorienfassade', url: './models/facades.glb', priority: 'core' },
  { id: 'towers', label: 'Alle 18 Türme & Wendeltreppe', url: './models/towers.glb', priority: 'core' },
  { id: 'eixample', label: 'Eixample-Stadtblock & Blätter-Bäume', url: './models/eixample.glb', priority: 'core' },
  { id: 'interior', label: 'Innenraum, Säulenwald & Cycles-GI', url: './models/interior.glb', priority: 'core' },
  { id: 'furnishings', label: 'Liturgische Ausstattung, Kapellen & Ausstellung', url: './models/furnishings.glb', priority: 'background' },
  { id: 'cloister_crypt', label: 'Kreuzgang, Sakristeien & Krypta-GI', url: './models/cloister_crypt.glb', priority: 'background' },
  { id: 'plaza_life', label: 'Parkbänke, Kioske, Brunnen & Stadtmöbel', url: './models/plaza_life.glb', priority: 'background' },
];

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
  private pondFrameSkip = 0;

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
    this.interiorPmrem.compileCubemapShader();

    this.lighting.onTimeBucketChanged = () => this.captureInteriorReflectionProbe();

    this.buildReflectivePond();
  }

  /**
   * Captures the real Nave interior (columns, stained glass, vaults, chandeliers) ONCE per lighting bucket
   * into a prefiltered PMREM map so the polished marble floor & porphyry columns reflect the real cathedral at 0 ms/frame!
   */
  public captureInteriorReflectionProbe(): void {
    if (this.interiorReflectiveMats.length === 0) return;
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
    const reflEvery = mobile ? 3 : 2;
    const reflector = new Reflector(pondGeo, {
      clipBias: 0.003,
      textureWidth: reflRes,
      textureHeight: reflRes,
      color: 0x6f90a1,
    });
    const origBeforeRender = reflector.onBeforeRender.bind(reflector);
    reflector.onBeforeRender = (renderer, scene, camera, geometry, material, group) => {
      if (scene.overrideMaterial !== null) return;
      // Throttle reflection re-render & hide interior-only meshes (cuts reflection GPU cost by ~75%!)
      this.pondFrameSkip = (this.pondFrameSkip + 1) % reflEvery;
      if (this.pondFrameSkip !== 0) return;
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
    onProgress: (fraction: number, statusText: string) => void
  ): Promise<void> {
    const dracoLoader = new DRACOLoader();
    dracoLoader.setDecoderPath('./draco/');
    const loader = new GLTFLoader();
    loader.setDRACOLoader(dracoLoader);
    const texLoader = new THREE.TextureLoader();

    const eixampleNightTex = this.createEixampleNightWindowTexture();
    const maxAniso = Math.min(isMobileDevice() ? 4 : 16, this.renderer.capabilities.getMaxAnisotropy());
    const lightmapCache = new Map<string, THREE.Texture>();

    // Kick off non-blocking 1K PureSky HDRIs & Cycles Lightmaps immediately in background!
    this.lighting.loadRealHdrisInBackground();
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

    const processLoadedRoot = (spec: ModelSpec, root: THREE.Group) => {
      root.name = `Module_${spec.id}`;
      root.traverse((obj) => {
        if (!(obj instanceof THREE.Mesh)) return;
        const matName = obj.material instanceof THREE.MeshStandardMaterial ? obj.material.name : '';
        const isStainedGlass = obj.name.includes('StainedGlass') || matName.includes('StainedGlass');
        const isGroundOrFloor =
          obj.name.includes('Floor') ||
          obj.name.includes('Carpet') ||
          obj.name.includes('Crosswalks') ||
          obj.name.includes('Streets') ||
          obj.name.includes('Sidewalks') ||
          obj.name.includes('ParkLawns');
        const isGlassCase = obj.name.includes('GlassCases') || obj.name.includes('ElevatorShaftGlass') || matName.includes('GlassCase');
        const isFoliage = matName.includes('FoliagePark') || matName.includes('FoliageCypress');

        obj.castShadow = !isStainedGlass && !isGroundOrFloor && !isGlassCase;
        obj.receiveShadow = !isStainedGlass && !isGlassCase;

        if (obj.material instanceof THREE.MeshStandardMaterial) {
          for (const tex of [obj.material.map, obj.material.normalMap, obj.material.roughnessMap]) {
            if (tex) {
              tex.anisotropy = maxAniso;
              tex.needsUpdate = true;
            }
          }

          const lmSpec = LIGHTMAP_BY_MESH[obj.name];
          const lmTex = lightmapCache.get(obj.name);
          if (lmSpec && lmTex && obj.geometry.attributes.uv1) {
            obj.material.lightMap = lmTex;
            obj.material.lightMapIntensity = lmSpec.intensity;
            obj.material.needsUpdate = true;
          }

          if (
            matName.includes('SandstoneWarm') ||
            matName.includes('NativityStone') ||
            matName.includes('PassionStone') ||
            matName.includes('VaultStone') ||
            matName.includes('CryptStone')
          ) {
            this.injectStoneAntiTilingAndHeightFog(obj.material);
          }

          if (
            obj.name === 'Interior_MarbleFloor' ||
            matName.includes('PorphyryRed') ||
            matName.includes('GoldAccent')
          ) {
            obj.material.envMapIntensity = obj.name === 'Interior_MarbleFloor' ? 0.85 : 0.72;
            this.interiorReflectiveMats.push(obj.material);
          }

          if (isStainedGlass) {
            obj.material.side = THREE.DoubleSide;
            obj.material.roughness = 0.14;
            obj.material.transparent = true;
            obj.material.opacity = 0.92;
          }
          if (isGlassCase) {
            obj.material.transparent = true;
            obj.material.opacity = 0.22;
            obj.material.roughness = 0.06;
            obj.material.depthWrite = false;
            obj.material.side = THREE.DoubleSide;
          }
          if (matName.includes('EixampleFacade')) {
            obj.material.emissive = new THREE.Color('#ffbd69');
            obj.material.emissiveMap = eixampleNightTex;
            obj.material.emissiveIntensity = 0.0;
            this.eixampleNightMats.push(obj.material);
          }
          if (isFoliage) {
            this.injectTreeWindSway(obj.material);
          }
        }
      });

      const stats = optimizeWithAutoInstancing(root);
      this.instancedGroups += stats.instancedMeshCount;
      this.savedDrawCalls += stats.savedDrawCalls;

      this.scene.add(root);
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

    // ── PHASE 1 (FAST START): Core exterior + interior basilica (~1-2 seconds!) ──
    const coreSpecs = MODEL_SPECS.filter((s) => s.priority === 'core');
    const bgSpecs = MODEL_SPECS.filter((s) => s.priority === 'background');
    let coreLoaded = 0;

    await Promise.all(
      coreSpecs.map(async (spec) => {
        const gltf = await loader.loadAsync(spec.url);
        processLoadedRoot(spec, gltf.scene);
        coreLoaded++;
        onProgress(
          (coreLoaded / coreSpecs.length) * 0.85,
          `Geladen: ${spec.label} (${coreLoaded}/${coreSpecs.length})`
        );
      })
    );

    // Pre-warm ALL core WebGL shaders asynchronously before revealing scene -> ZERO freeze when entering portals!
    onProgress(0.94, 'Shader-Pre-Warming (kein Ruckeln beim Eintreten)…');
    this.lighting.requestShadowUpdate(true);
    await this.renderer.compileAsync(this.scene, camera);
    onProgress(1.0, 'Bereit!');

    // ── PHASE 2 (SILENT BACKGROUND STREAMING): Furnishings, Crypt, Plaza Furniture & Cycles Lightmaps ──
    void (async () => {
      await lightmapsPromise;
      // Apply Cycles GI lightmaps to already-loaded core interior meshes
      this.scene.traverse((obj) => {
        if (!(obj instanceof THREE.Mesh) || !(obj.material instanceof THREE.MeshStandardMaterial)) return;
        const lmSpec = LIGHTMAP_BY_MESH[obj.name];
        const lmTex = lightmapCache.get(obj.name);
        if (lmSpec && lmTex && obj.geometry.attributes.uv1 && !obj.material.lightMap) {
          obj.material.lightMap = lmTex;
          obj.material.lightMapIntensity = lmSpec.intensity;
          obj.material.needsUpdate = true;
        }
      });

      await Promise.all(
        bgSpecs.map(async (spec) => {
          const gltf = await loader.loadAsync(spec.url);
          processLoadedRoot(spec, gltf.scene);
        })
      );
      dracoLoader.dispose();
      // Pre-warm newly streamed interior furnishings & crypt shaders seamlessly in background
      await this.renderer.compileAsync(this.scene, camera);
      this.lighting.requestShadowUpdate(true);
      this.captureInteriorReflectionProbe();
    })();
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

    // Smart 55k-tri Interior Tower Staircase Culling: hide internal helical stairs when outdoors far from towers!
    const distBasilica = Math.hypot(cameraPos.x, cameraPos.z - 8.0);
    const showInternalStairs = indoorFactor > 0.2 || (cameraPos.y > 10.5 && distBasilica < 66.0);
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
