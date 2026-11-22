import * as THREE from 'three';
import { RGBELoader } from 'three/examples/jsm/loaders/RGBELoader.js';
import { AtmosphericParticles } from './AtmosphericParticles';

interface TrackedMaterials {
  east: THREE.MeshStandardMaterial[];
  west: THREE.MeshStandardMaterial[];
  apse: THREE.MeshStandardMaterial[];
  star: THREE.MeshStandardMaterial[];
  cross: THREE.MeshStandardMaterial[];
  lamps: THREE.MeshStandardMaterial[];
}

export class LightingSystem {
  public readonly sunLight: THREE.DirectionalLight;
  public readonly hemiLight: THREE.HemisphereLight;
  public readonly skyMesh: THREE.Mesh;
  public readonly particles: AtmosphericParticles;
  public readonly sunDir = new THREE.Vector3(0.6, 0.7, 0.2);

  public timeHours = 10.5;
  public dayFactor = 1.0;
  public nightFactor = 0.0;
  public eastSunHit = 0.7;
  public westSunHit = 0.0;

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

  // 4 wide high-efficiency SpotLight.map stained-glass projectors
  private eastProjectors: THREE.SpotLight[] = [];
  private westProjectors: THREE.SpotLight[] = [];
  private apseGlassLight: THREE.PointLight;
  private interiorFillLights: THREE.PointLight[] = [];
  private cryptLights: THREE.PointLight[] = [];
  private nightSpotLights: THREE.PointLight[] = [];
  private starPointLight: THREE.PointLight;
  private crossPointLight: THREE.PointLight;

  private eastBeams: THREE.Mesh[] = [];
  private westBeams: THREE.Mesh[] = [];
  private starHaloSprite: THREE.Sprite;
  private crossHaloSprite: THREE.Sprite;

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
        #define PI 3.14159265359
        uniform float uTime;
        uniform vec3 uSunDir;
        uniform vec3 uTopColor;
        uniform vec3 uHorizonColor;
        uniform vec3 uSunColor;
        uniform float uNightFactor;
        uniform float uGoldenFactor;
        uniform float uUseHdri;
        uniform sampler2D uHdriDay;
        uniform sampler2D uHdriSunset;
        uniform sampler2D uHdriNight;
        varying vec3 vWorldDir;

        vec2 dirToEquirectUv(vec3 dir, float rotY) {
          float phi = atan(dir.z, dir.x) + rotY;
          float theta = asin(clamp(dir.y, -1.0, 1.0));
          return vec2(fract(phi / (2.0 * PI) + 0.5), theta / PI + 0.5);
        }

        void main() {
          vec3 dir = normalize(vWorldDir);
          vec3 sunN = normalize(uSunDir);
          float h = clamp(dir.y, 0.0, 1.0);

          vec3 col;
          if (uUseHdri > 0.5) {
            // Ultra-slow Mediterranean cloud drift via gentle sky azimuth rotation
            float drift = uTime * 0.0012;
            vec2 uv = dirToEquirectUv(dir, drift);
            vec3 cDay = texture2D(uHdriDay, uv).rgb * 0.92;
            vec3 cSun = texture2D(uHdriSunset, uv).rgb * 1.12;
            vec3 cNight = texture2D(uHdriNight, uv).rgb * 0.55;

            // Smooth photographic crossfade: Day -> Golden Sunset -> Starry Night
            vec3 daySun = mix(cDay, cSun, clamp(uGoldenFactor * 1.15, 0.0, 1.0));
            col = mix(daySun, cNight, clamp(uNightFactor, 0.0, 1.0));
          } else {
            col = mix(uHorizonColor, uTopColor, pow(h, 0.54));
          }

          // Crisp HDR solar glow & sun disk aligned to Barcelona solar ephemeris
          float sunAmt = max(dot(dir, sunN), 0.0);
          col += uSunColor * pow(sunAmt, 16.0) * 0.36 * (1.0 - uNightFactor * 0.94);
          col += uSunColor * smoothstep(0.9985, 0.9996, sunAmt) * 2.8 * (1.0 - uNightFactor);

          // Ground horizon haze below eye horizon
          if (dir.y < 0.0) {
            col = mix(col, uHorizonColor * 0.42, clamp(-dir.y * 5.0, 0.0, 1.0));
          }
          gl_FragColor = vec4(col, 1.0);
        }
      `,
    });

    this.skyMesh = new THREE.Mesh(new THREE.SphereGeometry(640, 32, 20), skyMat);
    this.skyMesh.renderOrder = -10;
    this.scene.add(this.skyMesh);

    this.pmremGenerator = new THREE.PMREMGenerator(this.renderer);
    this.pmremGenerator.compileEquirectangularShader();

    // 2. Hemisphere + Crisp 2048px Cached Directional Sun Light
    this.hemiLight = new THREE.HemisphereLight('#bfd9f5', '#877258', 0.85);
    this.scene.add(this.hemiLight);

    this.sunLight = new THREE.DirectionalLight('#fff6e3', 3.0);
    this.sunLight.castShadow = true;
    this.sunLight.shadow.mapSize.set(2048, 2048);
    this.sunLight.shadow.camera.near = 25;
    this.sunLight.shadow.camera.far = 420;
    const d = 132;
    this.sunLight.shadow.camera.left = -d;
    this.sunLight.shadow.camera.right = d;
    this.sunLight.shadow.camera.top = d;
    this.sunLight.shadow.camera.bottom = -d;
    this.sunLight.shadow.bias = -0.0005;
    this.sunLight.shadow.normalBias = 0.045;
    this.sunLight.shadow.radius = 2.0;
    this.scene.add(this.sunLight);
    this.scene.add(this.sunLight.target);

    // 3. 4 Wide Textured SpotLight.map Stained-Glass Projectors (Joan Vila-Grau patterns!)
    const texLoader = new THREE.TextureLoader();
    const texEast = texLoader.load('./textures/stained_glass_east.png');
    texEast.colorSpace = THREE.SRGBColorSpace;
    texEast.wrapS = THREE.ClampToEdgeWrapping;
    texEast.wrapT = THREE.ClampToEdgeWrapping;

    const texWest = texLoader.load('./textures/stained_glass_west.png');
    texWest.colorSpace = THREE.SRGBColorSpace;
    texWest.wrapS = THREE.ClampToEdgeWrapping;
    texWest.wrapT = THREE.ClampToEdgeWrapping;

    const bayZs = [19, 35];
    for (let i = 0; i < bayZs.length; i++) {
      const es = new THREE.SpotLight('#ffffff', 220, 62, Math.PI * 0.34, 0.45, 1.05);
      es.map = texEast;
      es.position.set(21.4, 18.0, bayZs[i]);
      es.target.position.set(-4.0, 1.2, bayZs[i]);
      this.scene.add(es);
      this.scene.add(es.target);
      this.eastProjectors.push(es);

      const ws = new THREE.SpotLight('#ffffff', 220, 62, Math.PI * 0.34, 0.45, 1.05);
      ws.map = texWest;
      ws.position.set(-21.4, 18.0, bayZs[i]);
      ws.target.position.set(4.0, 1.2, bayZs[i]);
      this.scene.add(ws);
      this.scene.add(ws.target);
      this.westProjectors.push(ws);
    }

    this.apseGlassLight = new THREE.PointLight('#9ab8ff', 42, 54, 1.25);
    this.apseGlassLight.position.set(0, 17, -26);
    this.scene.add(this.apseGlassLight);

    // 4. Consolidated High-Efficiency Interior Lights (enhanced by real Cycles GI Lightmaps!)
    const interiorSpots: Array<[number, number, number, string, number, number]> = [
      [0, 32, 4, '#ffe2b4', 56, 78],
      [0, 12.0, 26, '#ffd494', 48, 62],
      [0, 13.5, -18, '#ffd48a', 52, 52],
    ];
    for (const [x, y, z, col, intensity, dist] of interiorSpots) {
      const l = new THREE.PointLight(col, intensity, dist, 1.25);
      l.position.set(x, y, z);
      this.scene.add(l);
      this.interiorFillLights.push(l);
    }

    // 5. Subterranean Crypt Warm Candlelight
    const cryptCoords: Array<[number, number, number, number]> = [
      [0, -2.0, -21, 28],
      [-9.5, -3.2, -23.5, 22],
    ];
    for (const [x, y, z, inten] of cryptCoords) {
      const cl = new THREE.PointLight('#ff9d3b', inten, 30, 1.35);
      cl.position.set(x, y, z);
      this.scene.add(cl);
      this.cryptLights.push(cl);
    }

    // 6. Night Architectural Floodlights
    const nightFloods: Array<[number, number, number, string]> = [
      [52, 26, 20, '#ffcb85'],
      [-52, 26, -15, '#dbe6ff'],
    ];
    for (const [x, y, z, col] of nightFloods) {
      const nl = new THREE.PointLight(col, 0, 145, 1.2);
      nl.position.set(x, y, z);
      this.scene.add(nl);
      this.nightSpotLights.push(nl);
    }

    // 7. Luminous Star of Mary (138m) & Cross of Jesus (172.5m)
    this.starPointLight = new THREE.PointLight('#fff0c2', 35, 105, 1.25);
    this.starPointLight.position.set(0, 134.2, -22.5);
    this.scene.add(this.starPointLight);

    this.crossPointLight = new THREE.PointLight('#fff7e0', 40, 120, 1.25);
    this.crossPointLight.position.set(0, 164.5, 0);
    this.scene.add(this.crossPointLight);

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
    this.starHaloSprite.position.set(0, 134.2, -22.5);
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
    this.crossHaloSprite.position.set(0, 165.0, 0);
    this.crossHaloSprite.scale.set(28, 28, 1);
    this.scene.add(this.crossHaloSprite);

    // 8. Soft GLSL Fresnel Volumetric Stained-Glass Sunbeams + Drifting Dust Motes
    this.buildVolumetricBeams();
    this.particles = new AtmosphericParticles(900);
    this.scene.add(this.particles.points);

    this.setTimeOfDay(this.timeHours, true);
  }

  /**
   * Non-blocking progressive 1K PureSky HDRI loader:
   * Streams day_1k.hdr first (~1.3 MB), then sunset_1k & night_1k lazily in the background
   * so the loading screen NEVER stalls on 15 MB of .hdr parsing!
   */
  public loadRealHdrisInBackground(): void {
    const rgbe = new RGBELoader();
    const prep = (t: THREE.DataTexture) => {
      t.mapping = THREE.EquirectangularReflectionMapping;
      t.minFilter = THREE.LinearFilter;
      t.magFilter = THREE.LinearFilter;
      return t;
    };

    // 1. Load daytime 1K HDRI immediately in background
    rgbe
      .loadAsync('./hdri/day_1k.hdr')
      .then((dayTex) => {
        prep(dayTex);
        this.pmremDay = this.pmremGenerator.fromEquirectangular(dayTex).texture;
        this.skyUniforms.uHdriDay.value = dayTex;
        // Temporarily share dayTex until sunset/night stream in so shader has valid samplers
        if (!this.skyUniforms.uHdriSunset.value) this.skyUniforms.uHdriSunset.value = dayTex;
        if (!this.skyUniforms.uHdriNight.value) this.skyUniforms.uHdriNight.value = dayTex;
        this.skyUniforms.uUseHdri.value = 1.0;
        this.activeEnvKey = null;
        this.setTimeOfDay(this.timeHours, false);

        // 2. Lazily stream sunset & night 1K HDRIs after scene is interactive
        return Promise.all([
          rgbe.loadAsync('./hdri/sunset_1k.hdr'),
          rgbe.loadAsync('./hdri/night_1k.hdr'),
        ]);
      })
      .then(([sunsetTex, nightTex]) => {
        prep(sunsetTex);
        prep(nightTex);
        this.pmremSunset = this.pmremGenerator.fromEquirectangular(sunsetTex).texture;
        this.pmremNight = this.pmremGenerator.fromEquirectangular(nightTex).texture;
        this.skyUniforms.uHdriSunset.value = sunsetTex;
        this.skyUniforms.uHdriNight.value = nightTex;
        this.activeEnvKey = null;
        this.setTimeOfDay(this.timeHours, false);
      })
      .catch((err) => {
        console.warn('[HDRI] Background load fallback:', err);
      });
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

  private buildVolumetricBeams(): void {
    const beamGeo = new THREE.CylinderGeometry(1.1, 4.5, 36, 18, 1, true);
    const createBeamMat = (hex: string) =>
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
        uniforms: {
          uColor: { value: new THREE.Color(hex) },
          uOpacity: { value: 0.08 },
        },
        vertexShader: /* glsl */ `
          varying vec2 vUv;
          varying vec3 vNormalV;
          varying vec3 vViewDir;
          void main() {
            vUv = uv;
            vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
            vNormalV = normalize(normalMatrix * normal);
            vViewDir = normalize(-mvPos.xyz);
            gl_Position = projectionMatrix * mvPos;
          }
        `,
        fragmentShader: /* glsl */ `
          uniform vec3 uColor;
          uniform float uOpacity;
          varying vec2 vUv;
          varying vec3 vNormalV;
          varying vec3 vViewDir;
          void main() {
            float vertFade = smoothstep(0.0, 0.30, vUv.y) * smoothstep(1.0, 0.70, vUv.y);
            float edgeFade = pow(abs(dot(normalize(vNormalV), normalize(vViewDir))), 1.85);
            gl_FragColor = vec4(uColor, vertFade * edgeFade * uOpacity);
          }
        `,
      });

    const eastColors = ['#29c5e0', '#2ee09b', '#3a86ff', '#26c9a8'];
    const westColors = ['#ff5b24', '#ff9d1c', '#f0293e', '#ffc229'];
    const zPos = [15, 23, 31, 39];

    for (let i = 0; i < zPos.length; i++) {
      const eb = new THREE.Mesh(beamGeo, createBeamMat(eastColors[i]));
      eb.position.set(11.5, 11.5, zPos[i]);
      eb.rotation.z = 0.88;
      this.scene.add(eb);
      this.eastBeams.push(eb);

      const wb = new THREE.Mesh(beamGeo, createBeamMat(westColors[i]));
      wb.position.set(-11.5, 11.5, zPos[i]);
      wb.rotation.z = -0.88;
      this.scene.add(wb);
      this.westBeams.push(wb);
    }
  }

  public registerLoadedMaterials(root: THREE.Object3D): void {
    root.traverse((obj) => {
      if (!(obj instanceof THREE.Mesh)) return;
      const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
      for (const m of mats) {
        if (!(m instanceof THREE.MeshStandardMaterial)) continue;
        if (m.name.includes('StainedGlassEast')) this.trackedMats.east.push(m);
        else if (m.name.includes('StainedGlassWest')) this.trackedMats.west.push(m);
        else if (m.name.includes('StainedGlassApse')) this.trackedMats.apse.push(m);
        else if (m.name.includes('LuminousStar')) this.trackedMats.star.push(m);
        else if (m.name.includes('LuminousCross')) this.trackedMats.cross.push(m);
        else if (m.name.includes('CandleGlow')) this.trackedMats.lamps.push(m);
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
    const goldenFactor = Math.exp(-Math.pow((elevation - 0.14) / 0.24, 2)) * dayFactor;
    const nightFactor = 1.0 - THREE.MathUtils.smoothstep(elevation, -0.15, 0.12);

    this.dayFactor = dayFactor;
    this.nightFactor = nightFactor;

    const topDay = new THREE.Color('#1d5ca8');
    const topGolden = new THREE.Color('#354374');
    const topNight = new THREE.Color('#050914');
    const horDay = new THREE.Color('#c8dff5');
    const horGolden = new THREE.Color('#f4924e');
    const horNight = new THREE.Color('#10192e');

    const topCol = topNight.clone().lerp(topDay, dayFactor).lerp(topGolden, goldenFactor * 0.68);
    const horCol = horNight.clone().lerp(horDay, dayFactor).lerp(horGolden, goldenFactor * 0.88);
    const sunCol = new THREE.Color('#fff5e0').lerp(new THREE.Color('#ff8e3c'), goldenFactor * 0.88);

    this.skyUniforms.uSunDir.value.copy(this.sunDir);
    this.skyUniforms.uTopColor.value.copy(topCol);
    this.skyUniforms.uHorizonColor.value.copy(horCol);
    this.skyUniforms.uSunColor.value.copy(sunCol);
    this.skyUniforms.uNightFactor.value = nightFactor;
    this.skyUniforms.uGoldenFactor.value = goldenFactor;

    if (this.scene.fog instanceof THREE.FogExp2) {
      this.scene.fog.color.copy(horCol);
      this.scene.fog.density = THREE.MathUtils.lerp(0.0012, 0.0019, nightFactor);
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
      }
    }

    this.sunLight.color.copy(sunCol);
    this.sunLight.intensity = dayFactor * 3.1;
    this.sunLight.castShadow = dayFactor > 0.06;
    this.requestShadowUpdate(forceShadow);

    this.hemiLight.color.copy(topCol).lerp(new THREE.Color('#d8e8fa'), 0.45 * dayFactor);
    this.hemiLight.groundColor.set('#7a654f').lerp(new THREE.Color('#0b0f1a'), nightFactor * 0.90);
    this.hemiLight.intensity = THREE.MathUtils.lerp(0.11, 0.78, dayFactor);
    this.scene.environmentIntensity = THREE.MathUtils.lerp(0.14, 0.78, dayFactor);

    const eastSunHit = Math.max(0, eastWest) * dayFactor;
    const westSunHit = Math.max(0, -eastWest) * dayFactor;
    this.eastSunHit = eastSunHit;
    this.westSunHit = westSunHit;

    const reach = THREE.MathUtils.lerp(29.0, 11.0, THREE.MathUtils.clamp(elevation / 1.0, 0, 1));
    const targetClimbY = THREE.MathUtils.lerp(7.5, 1.2, THREE.MathUtils.clamp(elevation / 0.65, 0, 1));
    const beamTilt = THREE.MathUtils.lerp(1.12, 0.48, THREE.MathUtils.clamp(elevation / 1.0, 0, 1));

    this.baseEastInt = 18 * dayFactor + eastSunHit * 440;
    for (let i = 0; i < this.eastProjectors.length; i++) {
      const es = this.eastProjectors[i];
      es.intensity = this.baseEastInt;
      es.target.position.set(21.4 - reach, targetClimbY, es.position.z);
      es.target.updateMatrixWorld();
    }
    for (let i = 0; i < this.eastBeams.length; i++) {
      const eb = this.eastBeams[i];
      eb.rotation.z = beamTilt;
      eb.position.x = 21.4 - Math.sin(beamTilt) * 11.5;
      (eb.material as THREE.ShaderMaterial).uniforms.uOpacity.value = eastSunHit * 0.16;
      eb.visible = eastSunHit > 0.03;
    }

    this.baseWestInt = 18 * dayFactor + westSunHit * 460;
    for (let i = 0; i < this.westProjectors.length; i++) {
      const ws = this.westProjectors[i];
      ws.intensity = this.baseWestInt;
      ws.target.position.set(-21.4 + reach, targetClimbY, ws.position.z);
      ws.target.updateMatrixWorld();
    }
    for (let i = 0; i < this.westBeams.length; i++) {
      const wb = this.westBeams[i];
      wb.rotation.z = -beamTilt;
      wb.position.x = -21.4 + Math.sin(beamTilt) * 11.5;
      (wb.material as THREE.ShaderMaterial).uniforms.uOpacity.value = westSunHit * 0.17;
      wb.visible = westSunHit > 0.03;
    }

    this.baseApseInt = 18 * dayFactor + 18;
    this.apseGlassLight.intensity = this.baseApseInt;

    const ambientGlass = 0.30 * dayFactor + 0.16;
    const eastGlow = ambientGlass + eastSunHit * 2.6;
    const westGlow = ambientGlass + westSunHit * 2.8;
    for (const m of this.trackedMats.east) m.emissiveIntensity = eastGlow;
    for (const m of this.trackedMats.west) m.emissiveIntensity = westGlow;
    for (const m of this.trackedMats.apse) m.emissiveIntensity = 0.65 + dayFactor * 1.25;

    this.baseInteriorInt = THREE.MathUtils.lerp(42, 68, nightFactor);
    for (const il of this.interiorFillLights) {
      il.intensity = this.baseInteriorInt;
    }

    this.baseNightInt = nightFactor * 270;
    for (const nl of this.nightSpotLights) {
      nl.intensity = this.baseNightInt;
    }

    const landmarkGlow = 1.4 + nightFactor * 4.4;
    for (const m of this.trackedMats.star) m.emissiveIntensity = landmarkGlow * 1.4;
    for (const m of this.trackedMats.cross) m.emissiveIntensity = landmarkGlow * 1.1;
    this.starPointLight.intensity = 20 + nightFactor * 150;
    this.crossPointLight.intensity = 22 + nightFactor * 160;
    (this.starHaloSprite.material as THREE.SpriteMaterial).opacity = 0.20 + nightFactor * 0.72;
    (this.crossHaloSprite.material as THREE.SpriteMaterial).opacity = 0.16 + nightFactor * 0.65;
  }

  public requestShadowUpdate(immediate = false): void {
    const now = performance.now();
    if (immediate || now - this.lastShadowUpdateMs >= 85) {
      this.renderer.shadowMap.needsUpdate = true;
      this.lastShadowUpdateMs = now;
      this.shadowUpdatedThisFrame = true;
    }
  }

  private baseEastInt = 0;
  private baseWestInt = 0;
  private baseApseInt = 0;
  private baseInteriorInt = 48;
  private baseNightInt = 0;

  public updateZoneCulling(cameraPos: THREE.Vector3, indoorFactor: number): void {
    // CRITICAL ANTI-STUTTER FIX:
    // NEVER toggle light.visible = false/true while walking! Toggling light.visible alters NUM_POINT_LIGHTS /
    // NUM_SPOT_LIGHTS in Three.js's shader cache and causes multi-second GLSL recompilation freezes when entering portals!
    // Instead, keep all 12 lights permanently visible and cleanly modulate intensity to 0.0 outside their zone!
    const inCryptRange = cameraPos.y < 2.2;
    const nearInterior =
      cameraPos.y > -2.5 &&
      cameraPos.y < 68 &&
      Math.abs(cameraPos.x) < 56 &&
      cameraPos.z > -50 &&
      cameraPos.z < 68;
    const needNightFloods = this.nightFactor > 0.04 && indoorFactor < 0.92;

    if (!inCryptRange) {
      for (const cl of this.cryptLights) cl.intensity = 0;
    }
    const intMul = nearInterior ? 1.0 : 0.0;
    for (const es of this.eastProjectors) es.intensity = this.baseEastInt * intMul;
    for (const ws of this.westProjectors) ws.intensity = this.baseWestInt * intMul;
    this.apseGlassLight.intensity = this.baseApseInt * intMul;
    for (const il of this.interiorFillLights) il.intensity = this.baseInteriorInt * intMul;

    const nightMul = needNightFloods ? 1.0 : 0.0;
    for (const nl of this.nightSpotLights) nl.intensity = this.baseNightInt * nightMul;

    this.particles.points.visible = indoorFactor > 0.15 && cameraPos.y > -1.0;
  }

  public getPerfLightStats(): { activeLights: number; totalLights: number; shadowCached: boolean } {
    const all: THREE.Light[] = [
      this.sunLight,
      this.hemiLight,
      this.apseGlassLight,
      this.starPointLight,
      this.crossPointLight,
      ...this.eastProjectors,
      ...this.westProjectors,
      ...this.interiorFillLights,
      ...this.cryptLights,
      ...this.nightSpotLights,
    ];
    let activeLights = 0;
    for (const l of all) {
      if (l.visible && l.intensity > 0.01) activeLights++;
    }
    const cached = !this.shadowUpdatedThisFrame;
    this.shadowUpdatedThisFrame = false;
    return { activeLights, totalLights: all.length, shadowCached: cached };
  }

  public update(dt: number, cameraPos: THREE.Vector3, indoorFactor: number): void {
    this.clockSec += dt;
    this.skyUniforms.uTime.value = this.clockSec;
    this.skyMesh.position.copy(cameraPos);

    this.updateZoneCulling(cameraPos, indoorFactor);

    if (this.particles.points.visible) {
      this.particles.update(dt, this.eastSunHit, this.westSunHit, this.dayFactor);
    }

    if (cameraPos.y < 2.2) {
      for (let i = 0; i < this.cryptLights.length; i++) {
        const base = i === 0 ? 28 : 22;
        const flicker = Math.sin(this.clockSec * 5.2 + i * 2.1) * 0.9 + Math.sin(this.clockSec * 11.7 + i) * 0.45;
        this.cryptLights[i].intensity = base + flicker;
      }
    }
  }
}
