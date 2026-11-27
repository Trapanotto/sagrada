import './styles.css';
import * as THREE from 'three';
import { SagradaScene, AssetLoadError, getModuleLabel, type LoadStatus } from './scene/SagradaScene';
import type { WeatherMode } from './scene/WeatherSystem';
import { RenderPipeline } from './scene/RenderPipeline';
import { CollisionSystem } from './scene/CollisionSystem';
import { PlayerController } from './controls/PlayerController';
import { TouchControls } from './controls/TouchControls';
import type { CinematicTour } from './controls/CinematicTour';
import type { AmbienceAudio } from './audio/AmbienceAudio';
import { TELEPORT_PRESETS, SPAWN_PRESET, FloorLevel } from './data/teleports';
import { LAYOUT, groundWorldY, inCryptFootprint, towerByKey } from './data/layout';
import { GALLERY_BOXES, isEyeUnderground } from './scene/walkModel';
import { Minimap } from './ui/Minimap';
import { HotspotPanel } from './ui/HotspotPanel';
import { PerfMonitor } from './ui/PerfMonitor';
import { frameHooks } from './perf/hooks';
import { prefersTouchUI, triggerHaptic } from './utils/device';
import {
  t,
  loc,
  fmtNum,
  onLangChange,
  translateDom,
  initLangSwitches,
  type MessageKey,
  type MessageParams,
} from './i18n';
import {
  initQuality,
  getDeviceSignals,
  getQuality,
  getQualityPreference,
  getAutoTier,
  setQualityPreference,
  refreshQualityForDpr,
  QUALITY_TEXT,
  QUALITY_TIERS,
  QualityPreference,
  QualitySettings,
} from './utils/quality';

/** Last fatal error shown, kept as keys so it can be re-rendered after a language switch. */
let fatalError: { title: MessageKey; body: MessageKey; params?: MessageParams } | null = null;

/** Replaces the loading bar with a readable error message + reload button (never a stuck bar). */
function showFatalError(title: MessageKey, body: MessageKey, params?: MessageParams): void {
  fatalError = { title, body, params };
  const screen = document.getElementById('loading-screen');
  const box = screen?.querySelector('.loading-minimal');
  if (!screen || !box) {
    document.body.textContent = `${t(title)} — ${t(body, params)}`;
    return;
  }
  screen.classList.remove('hidden', 'fade-out', 'loading-ready');
  document.getElementById('loading-progress-wrap')?.classList.add('hidden');
  document.getElementById('loading-enter-wrap')?.classList.add('hidden');
  box.querySelector('.loading-error')?.remove();
  const wrap = document.createElement('div');
  wrap.className = 'loading-error';
  wrap.setAttribute('role', 'alert');
  const h = document.createElement('div');
  h.className = 'loading-error-title';
  h.textContent = t(title);
  const p = document.createElement('p');
  p.className = 'loading-error-body';
  p.textContent = t(body, params);
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'enter-btn';
  btn.textContent = t('error.reload');
  btn.addEventListener('click', () => window.location.reload());
  wrap.append(h, p, btn);
  box.appendChild(wrap);
}

let glStatusKey: MessageKey | null = null;
function setGlStatus(key: MessageKey | null): void {
  glStatusKey = key;
  let el = document.getElementById('gl-status');
  if (!key) {
    el?.classList.add('hidden');
    return;
  }
  if (!el) {
    el = document.createElement('div');
    el.id = 'gl-status';
    el.className = 'hud-panel';
    el.setAttribute('role', 'status');
    document.getElementById('app')?.appendChild(el);
  }
  el.textContent = t(key);
  el.classList.remove('hidden');
}

// Error screens and the GL status overlay can appear before / without the 3D scene: keep them live too
onLangChange(() => {
  if (fatalError) showFatalError(fatalError.title, fatalError.body, fatalError.params);
  if (glStatusKey) setGlStatus(glStatusKey);
});

function formatHours(h: number): string {
  const hh = Math.floor(h) % 24;
  const mm = Math.floor((h - Math.floor(h)) * 60);
  return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`;
}

function yawToCompass(yaw: number): string {
  // Forward vector = (-sin(yaw), -cos(yaw)); North = -Z (yaw = 0), East = +X (yaw = -pi/2)
  const deg = (((-yaw * 180) / Math.PI) % 360 + 360) % 360;
  const dirs = t('hud.compass').split(',');
  return dirs[Math.round(deg / 45) % 8];
}

async function bootstrap(): Promise<void> {
  // Bench mode (?bench) is the only path that loads the bench module; normal loads skip it entirely
  performance.mark('sagrada:boot:start');
  const bench = new URLSearchParams(window.location.search).has('bench')
    ? await import('./perf/bench')
    : null;
  bench?.benchBoot();
  const canvas = document.getElementById('scene-canvas') as HTMLCanvasElement;

  // Apply the active language to all static markup and wire the DE | EN switches first,
  // so even the WebGL / asset error screens below appear in the right language.
  translateDom();
  initLangSwitches();

  // Central quality tier (auto-detected or user override) drives every rendering-cost decision
  const quality = initQuality();
  performance.mark('sagrada:boot:quality');
  const signals = getDeviceSignals();
  if (!signals.webgl2) {
    showFatalError('error.noWebgl2Title', 'error.noWebgl2Body');
    return;
  }
  console.info(
    `[Quality] tier=${quality.tier} (auto=${getAutoTier()}, pref=${getQualityPreference()}) gpu="${signals.gpu}" ` +
      `mem=${signals.deviceMemory ?? '?'} cores=${signals.cores ?? '?'} dpr=${signals.dpr}`
  );

  let renderer: THREE.WebGLRenderer;
  try {
    renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: quality.antialias, // Hardware MSAA except on the low tier (tile-resolve cost on mobile GPUs)
      powerPreference: 'high-performance',
    });
  } catch (err) {
    console.error(err);
    showFatalError('error.rendererFailTitle', 'error.rendererFailBody');
    return;
  }
  performance.mark('sagrada:boot:renderer');
  renderer.setPixelRatio(quality.maxPixelRatio);
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.autoUpdate = false; // Cached sun shadows: only re-rendered when sun moves or scene loads!
  renderer.shadowMap.type = quality.softShadows ? THREE.PCFSoftShadowMap : THREE.PCFShadowMap;
  renderer.localClippingEnabled = false; // Enabled lazily ONLY when user inspects historical construction timelapse!
  // Filmic ACES S-curve for warm sunlit stone, deep shadows & glowing stained glass at 0 ms cost!
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.84;
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const camera = new THREE.PerspectiveCamera(62, window.innerWidth / window.innerHeight, 0.25, 1100);
  const sagrada = new SagradaScene(renderer);
  performance.mark('sagrada:boot:scene');
  const contextAA = Boolean(renderer.getContext().getContextAttributes()?.antialias);
  const post = new RenderPipeline(renderer, sagrada.scene, camera, quality, contextAA);
  const collision = new CollisionSystem();
  collision.preload(); // fetch three-mesh-bvh in parallel with the GLBs

  // Code-split optional systems: fetched in parallel with the GLBs, never blocking the main chunk
  let audio: AmbienceAudio | null = null;
  const audioReady = import('./audio/AmbienceAudio')
    .then(({ AmbienceAudio }) => {
      audio = new AmbienceAudio();
      return audio;
    })
    .catch((err) => {
      console.warn('[Audio] module failed to load:', err);
      return null;
    });
  performance.mark('sagrada:boot:post');
  const player = new PlayerController(camera, canvas, collision);
  const touchControls = new TouchControls(canvas);
  touchControls.onLookDelta = (dx, dy) => player.applyLookDelta(dx, dy);
  touchControls.onJump = () => player.triggerJump();
  touchControls.onToggleFly = () => player.setFlyMode(!player.flyMode);
  touchControls.onElevator = () => sagrada.elevator.triggerAction(camera.position);
  touchControls.onPinchZoom = (deltaFov) => {
    camera.fov = THREE.MathUtils.clamp(camera.fov + deltaFov, 40, 78);
    camera.updateProjectionMatrix();
  };
  // Cinematic tour is loaded on first use (button / [T]) or during idle time after entering
  let tour: CinematicTour | null = null;
  let tourPromise: Promise<CinematicTour> | null = null;
  const tourActive = () => tour?.active ?? false;

  // Start at the iconic Plaça de Gaudí viewpoint across the reflective pond facing the Nativity Facade!
  player.teleportTo(SPAWN_PRESET, true);

  // UI Elements
  const loadingScreen = document.getElementById('loading-screen')!;
  const loadingFill = document.getElementById('loading-bar-fill')!;
  const loadingPercent = document.getElementById('loading-percent')!;
  const loadingStatus = document.getElementById('loading-status')!;
  const loadingProgressWrap = document.getElementById('loading-progress-wrap')!;
  const loadingEnterWrap = document.getElementById('loading-enter-wrap')!;
  const btnEnterBasilica = document.getElementById('btn-enter-basilica') as HTMLButtonElement;
  // Loading progress is kept as data (percent + lazy status message) so a language switch can re-render it
  let loadingPct = 0;
  let loadingStatusMsg: LoadStatus = () => t('loading.init');
  const renderLoadingText = () => {
    loadingPercent.textContent = t('loading.percent', { pct: loadingPct });
    loadingStatus.textContent = loadingStatusMsg();
  };
  renderLoadingText();

  const hudPanels = [
    document.getElementById('hud-top')!,
    document.getElementById('hud-time')!,
    document.getElementById('hud-teleports')!,
    document.getElementById('hud-minimap')!,
    document.getElementById('controls-banner')!,
  ];
  const crosshairEl = document.getElementById('crosshair')!;
  const elevatorPrompt = document.getElementById('elevator-prompt')!;
  const zoneBadge = document.getElementById('zone-badge')!;
  const compassDir = document.getElementById('compass-dir')!;
  const altitudeReadout = document.getElementById('altitude-readout')!;
  const modeBadge = document.getElementById('mode-badge')!;

  const btnWalkMode = document.getElementById('btn-walk-mode') as HTMLButtonElement;
  const btnGeometry = document.getElementById('btn-geometry') as HTMLButtonElement;
  const btnHotspots = document.getElementById('btn-hotspots') as HTMLButtonElement;
  const btnMinimap = document.getElementById('btn-minimap') as HTMLButtonElement;
  const selQuality = document.getElementById('sel-quality') as HTMLSelectElement;
  const btnTour = document.getElementById('btn-tour') as HTMLButtonElement;
  const btnPhoto = document.getElementById('btn-photo') as HTMLButtonElement;
  const btnAudio = document.getElementById('btn-audio') as HTMLButtonElement;
  const btnMobileSun = document.getElementById('btn-mobile-sun') as HTMLButtonElement;
  const btnMobileMenu = document.getElementById('btn-mobile-menu') as HTMLButtonElement;
  const hudActionsMenu = document.getElementById('hud-actions-menu')!;
  const hudTimePanel = document.getElementById('hud-time')!;

  // Mobile Collapsible Top-Bar Drawers (keeps >90% of smartphone screen completely open!)
  const closeMobileDrawers = () => {
    hudActionsMenu.classList.remove('mobile-open');
    hudTimePanel.classList.remove('mobile-open');
    btnMobileMenu.classList.remove('active');
    btnMobileSun.classList.remove('active');
  };
  btnMobileSun.addEventListener('click', (e) => {
    e.stopPropagation();
    triggerHaptic(10);
    const willOpen = !hudTimePanel.classList.contains('mobile-open');
    closeMobileDrawers();
    if (willOpen) {
      hudTimePanel.classList.add('mobile-open');
      btnMobileSun.classList.add('active');
    }
  });
  btnMobileMenu.addEventListener('click', (e) => {
    e.stopPropagation();
    triggerHaptic(10);
    const willOpen = !hudActionsMenu.classList.contains('mobile-open');
    closeMobileDrawers();
    if (willOpen) {
      hudActionsMenu.classList.add('mobile-open');
      btnMobileMenu.classList.add('active');
    }
  });
  canvas.addEventListener('touchstart', closeMobileDrawers, { passive: true });

  // Make Glass Panorama Elevator prompt tappable directly on touchscreens & desktop!
  elevatorPrompt.addEventListener('click', () => {
    triggerHaptic(14);
    sagrada.elevator.triggerAction(camera.position);
  });

  const tourBar = document.getElementById('tour-bar')!;
  const tourTitle = document.getElementById('tour-chapter-title')!;
  const tourSub = document.getElementById('tour-chapter-sub')!;
  const tourProgressFill = document.getElementById('tour-progress-fill')!;
  const tourPauseBtn = document.getElementById('tour-pause-btn') as HTMLButtonElement;
  const tourNextBtn = document.getElementById('tour-next-btn') as HTMLButtonElement;
  const tourStopBtn = document.getElementById('tour-stop-btn') as HTMLButtonElement;

  const photoStudio = document.getElementById('photo-studio')!;
  const photoFov = document.getElementById('photo-fov') as HTMLInputElement;
  const photoFocalVal = document.getElementById('photo-focal-val')!;
  const photoExposure = document.getElementById('photo-exposure') as HTMLInputElement;
  const photoExpVal = document.getElementById('photo-exp-val')!;
  const photoFocus = document.getElementById('photo-focus') as HTMLInputElement;
  const photoFocusVal = document.getElementById('photo-focus-val')!;
  const photoAperture = document.getElementById('photo-aperture') as HTMLInputElement;
  const photoApertureVal = document.getElementById('photo-aperture-val')!;
  const photoCaptureBtn = document.getElementById('photo-capture-btn') as HTMLButtonElement;
  const photoCleanBtn = document.getElementById('photo-clean-btn') as HTMLButtonElement;
  const photoResetBtn = document.getElementById('photo-reset-btn') as HTMLButtonElement;
  const photoExitBtn = document.getElementById('photo-exit-btn') as HTMLButtonElement;
  const photoExitPill = document.getElementById('photo-exit-pill') as HTMLButtonElement;

  const timeSlider = document.getElementById('time-slider') as HTMLInputElement;
  const timeDisplay = document.getElementById('time-display')!;
  const audioVolume = document.getElementById('audio-volume') as HTMLInputElement;

  const minimapContainer = document.getElementById('hud-minimap')!;
  const minimap = new Minimap(
    document.getElementById('minimap-canvas') as HTMLCanvasElement,
    document.getElementById('minimap-levels')!
  );
  const hotspots = new HotspotPanel(document.getElementById('hotspot-markers')!);
  const perfMonitor = new PerfMonitor(
    document.getElementById('perf-fps-pill') as HTMLButtonElement,
    document.getElementById('perf-card')!,
    document.getElementById('perf-body')!
  );

  // Wire Teleport Presets Bar
  const tpNav = document.getElementById('hud-teleports')!;
  const tpButtons: HTMLButtonElement[] = [];
  for (const preset of TELEPORT_PRESETS) {
    const btn = document.createElement('button');
    btn.className = 'tp-btn';
    btn.textContent = loc(preset.shortLabel);
    btn.title = loc(preset.label);
    btn.addEventListener('click', () => {
      triggerHaptic(10);
      tpButtons.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      minimap.setLevel(preset.level);
      player.teleportTo(preset);
    });
    tpNav.appendChild(btn);
    tpButtons.push(btn);
  }
  tpButtons[0]?.classList.add('active');

  // Wire Minimap click-to-teleport!
  minimap.onTeleportClick = (wx: number, wz: number, level: FloorLevel) => {
    const eye = collision.eyeHeight;
    let targetY = eye;
    let fly = false;
    if (level === 'crypt') {
      // Pull the click into the crypt footprint (1.5 m inside its outer wall), towards the crypt centre
      const [ccx, ccy] = LAYOUT.crypt.center;
      const c = { x: ccx, z: -ccy };
      for (let k = 0; k <= 40; k++) {
        const f = 1 - k / 40;
        const px = c.x + (wx - c.x) * f;
        const pz = c.z + (wz - c.z) * f;
        const inside =
          inCryptFootprint(px, -pz) &&
          inCryptFootprint(px + 1.5, -pz) &&
          inCryptFootprint(px - 1.5, -pz) &&
          inCryptFootprint(px, -pz + 1.5) &&
          inCryptFootprint(px, -pz - 1.5);
        if (inside || k === 40) {
          wx = px;
          wz = pz;
          break;
        }
      }
      targetY = LAYOUT.levels.crypt + eye;
    } else if (level === 'gallery') {
      // Snap to the nearest point on a gallery / tribune deck
      let best = Infinity;
      let bx = wx;
      let bz = wz;
      for (const g of GALLERY_BOXES) {
        const qx = THREE.MathUtils.clamp(wx, g.minX + 0.6, g.maxX - 0.6);
        const qz = THREE.MathUtils.clamp(wz, g.minZ + 0.6, g.maxZ - 0.6);
        const d = Math.hypot(qx - wx, qz - wz);
        if (d < best) {
          best = d;
          bx = qx;
          bz = qz;
        }
      }
      wx = bx;
      wz = bz;
      targetY = LAYOUT.levels.gallery + eye;
    } else if (level === 'towers') {
      const nat = towerByKey('tower.nativityInnerS');
      const pas = towerByKey('tower.passionInnerS');
      const glo = towerByKey('tower.gloryInnerW');
      if (Math.hypot(wx, wz) < 12) {
        wx = 4.2;
        wz = 2.8;
        targetY = LAYOUT.levels.jesusView + eye;
      } else if (Math.abs(wx - nat.x) < 10 && Math.abs(wz) < 10) {
        wx = nat.x;
        wz = 0;
        targetY = LAYOUT.levels.skybridgeTransept + eye;
      } else if (Math.abs(wx - pas.x) < 10 && Math.abs(wz) < 10) {
        wx = pas.x;
        wz = 0;
        targetY = LAYOUT.levels.skybridgeTransept + eye;
      } else if (Math.abs(wz + glo.y) < 10 && Math.abs(wx) < 10) {
        wx = 0;
        wz = -glo.y;
        targetY = LAYOUT.levels.skybridgeGlory + eye;
      } else {
        targetY = 95.0;
        fly = true;
      }
    } else {
      // Start the search just above the higher of street and basilica floor (podium, Glory bridge, stairs)
      const res = collision.resolveWalkPosition(wx, Math.max(groundWorldY(wz), LAYOUT.levels.nave) + 1.0, wz);
      wx = res.clampedX;
      wz = res.clampedZ;
      targetY = res.groundY + collision.eyeHeight;
    }
    player.teleportTo({
      position: [wx, targetY, wz],
      lookAt: [0, Math.max(targetY, 16), 0],
      flyMode: fly,
    });
  };

  // Wire Hotspot fly-to
  hotspots.onFlyTo = (hs) => {
    player.teleportTo({
      position: hs.cameraTarget,
      lookAt: hs.position,
      flyMode: hs.flyMode ?? false,
    });
  };

  // Wire HUD Buttons & Shortcuts
  const syncModeUI = (fly: boolean) => {
    btnWalkMode.textContent = t(fly ? 'btn.fly' : 'btn.walk');
    modeBadge.textContent = t(fly ? 'hud.modeFly' : 'hud.modeWalk');
    touchControls.setFlyVisible(fly);
  };
  player.onModeChange = syncModeUI;
  player.onStep = () => audio?.playFootstep();

  btnWalkMode.addEventListener('click', () => player.setFlyMode(!player.flyMode));

  const toggleGeometry = () => {
    const on = sagrada.geometryOverlay.toggle();
    btnGeometry.classList.toggle('active', on);
  };
  btnGeometry.addEventListener('click', toggleGeometry);

  const toggleHotspots = () => {
    const on = hotspots.toggle();
    btnHotspots.classList.toggle('active', on);
  };
  btnHotspots.addEventListener('click', toggleHotspots);

  const toggleMinimap = () => {
    const hidden = minimapContainer.classList.toggle('hidden');
    btnMinimap.classList.toggle('active', !hidden);
  };
  btnMinimap.addEventListener('click', toggleMinimap);

  // Graphics quality selector (Auto / Low / Medium / High / Ultra), persisted in localStorage
  const fillQualitySelect = () => {
    const autoLabel = QUALITY_TEXT.autoWith(QUALITY_TEXT.tier(getAutoTier()));
    selQuality.textContent = '';
    const opts: Array<[QualityPreference, string]> = [
      ['auto', autoLabel],
      ...QUALITY_TIERS.map((tier): [QualityPreference, string] => [tier, QUALITY_TEXT.tier(tier)]),
    ];
    for (const [value, label] of opts) {
      const o = document.createElement('option');
      o.value = value;
      o.textContent = label;
      selQuality.appendChild(o);
    }
    selQuality.value = getQualityPreference();
    selQuality.title = QUALITY_TEXT.selectTitle;
    selQuality.setAttribute('aria-label', QUALITY_TEXT.selectAria);
  };
  fillQualitySelect();

  let lastSoftShadows = quality.softShadows;
  const applyQualityLive = (q: QualitySettings) => {
    post.applyQuality(q);
    sagrada.lighting.applyQuality(q);
    sagrada.applyQuality(q);
    if (q.softShadows !== lastSoftShadows) {
      lastSoftShadows = q.softShadows;
      renderer.shadowMap.type = q.softShadows ? THREE.PCFSoftShadowMap : THREE.PCFShadowMap;
      // Shadow filtering is baked into the shader programs -> force a program refresh
      sagrada.scene.traverse((obj) => {
        const m = (obj as THREE.Mesh).material;
        if (!m) return;
        for (const mat of Array.isArray(m) ? m : [m]) mat.needsUpdate = true;
      });
    }
  };
  selQuality.addEventListener('change', () => {
    applyQualityLive(setQualityPreference(selQuality.value as QualityPreference));
    selQuality.blur();
  });

  let photoMode = false;
  let photoCleanCanvas = false;
  let hotspotsBeforeSpecial = true;
  let minimapBeforeSpecial = true;

  const hideNormalHud = () => {
    hotspotsBeforeSpecial = hotspots.visible;
    minimapBeforeSpecial = !minimapContainer.classList.contains('hidden');
    hudPanels.forEach((p) => p.classList.add('hidden'));
    hotspots.setVisible(false);
  };

  const restoreNormalHud = () => {
    hudPanels.forEach((p) => {
      if (p === minimapContainer && !minimapBeforeSpecial) return;
      p.classList.remove('hidden');
    });
    hotspots.setVisible(hotspotsBeforeSpecial);
  };

  /** Slider read-outs only (also re-run after a language switch: decimal separator, "Off"). */
  const renderPhotoLabels = () => {
    const fov = parseFloat(photoFov.value);
    // Convert vertical FOV to equivalent 35mm full-frame focal length
    const focalMm = Math.round(12 / Math.tan(THREE.MathUtils.degToRad(fov) * 0.5));
    photoFocalVal.textContent = `${focalMm} mm`;
    photoExpVal.textContent = fmtNum(parseFloat(photoExposure.value), 2);
    const ap = parseFloat(photoAperture.value);
    photoFocusVal.textContent = `${parseFloat(photoFocus.value)} m`;
    photoApertureVal.textContent = ap <= 0.000005 ? t('photo.apertureOff') : `f/${fmtNum(2.8 / (ap / 0.00018), 1)}`;
  };

  const updatePhotoCameraSettings = () => {
    const fov = parseFloat(photoFov.value);
    camera.fov = fov;
    camera.updateProjectionMatrix();
    const exp = parseFloat(photoExposure.value);
    renderer.toneMappingExposure = exp;
    const focus = parseFloat(photoFocus.value);
    const ap = parseFloat(photoAperture.value);
    renderPhotoLabels();
    post.setDof(ap > 0.000005, focus, ap);
  };

  photoFov.addEventListener('input', updatePhotoCameraSettings);
  photoExposure.addEventListener('input', updatePhotoCameraSettings);
  photoFocus.addEventListener('input', updatePhotoCameraSettings);
  photoAperture.addEventListener('input', updatePhotoCameraSettings);

  photoResetBtn.addEventListener('click', () => {
    photoFov.value = '62';
    photoExposure.value = '0.86';
    photoFocus.value = '26';
    photoAperture.value = '0';
    updatePhotoCameraSettings();
  });

  photoCaptureBtn.addEventListener('click', () => {
    // Synchronous render right before PNG capture guarantees crisp frame with zero preserveDrawingBuffer overhead!
    post.render();
    const dataUrl = canvas.toDataURL('image/png');
    const a = document.createElement('a');
    const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    a.href = dataUrl;
    a.download = `sagrada-familia-${ts}.png`;
    a.click();
  });

  const setPhotoClean = (clean: boolean) => {
    photoCleanCanvas = clean;
    if (!photoMode) return;
    photoStudio.classList.toggle('hidden', clean);
    photoExitPill.classList.toggle('hidden', !clean);
  };

  const setPhotoMode = (enabled: boolean) => {
    if (enabled && tour?.active) tour.stop();
    photoMode = enabled;
    post.drsEnabled = !enabled; // keep resolution stable while composing a shot
    photoCleanCanvas = false;
    btnPhoto.classList.toggle('active', enabled);
    if (enabled) {
      hideNormalHud();
      photoStudio.classList.remove('hidden');
      photoExitPill.classList.add('hidden');
      updatePhotoCameraSettings();
    } else {
      photoStudio.classList.add('hidden');
      photoExitPill.classList.add('hidden');
      post.setDof(false);
      camera.fov = 62;
      camera.updateProjectionMatrix();
      renderer.toneMappingExposure = 0.84;
      restoreNormalHud();
    }
  };
  btnPhoto.addEventListener('click', () => setPhotoMode(!photoMode));
  photoExitBtn.addEventListener('click', () => setPhotoMode(false));
  photoCleanBtn.addEventListener('click', () => setPhotoClean(true));
  photoExitPill.addEventListener('click', () => setPhotoClean(false));

  // Wire Cinematic Architectural Tour [T] (module loaded lazily on first use)
  const loadTour = (): Promise<CinematicTour> => {
    if (!tourPromise) {
      tourPromise = import('./controls/CinematicTour').then(({ CinematicTour }) => {
        const tourInst = new CinematicTour(camera);
        tourInst.onChapterChange = (ch) => {
          tourTitle.textContent = loc(ch.title);
          tourSub.textContent = loc(ch.subtitle);
        };
        tourInst.onProgress = (frac) => {
          tourProgressFill.style.width = `${(frac * 100).toFixed(1)}%`;
        };
        let wasActive = false;
        tourInst.onStateChange = (active, paused) => {
          btnTour.classList.toggle('active', active);
          tourBar.classList.toggle('hidden', !active);
          tourPauseBtn.textContent = t(paused ? 'tour.resume' : 'tour.pause');
          // Pause/resume also reports active=true: only hide the HUD on the actual start, otherwise the
          // second hideNormalHud() would record the already-hidden minimap/hotspots as "off" for good.
          const started = active && !wasActive;
          wasActive = active;
          if (started) {
            if (photoMode) setPhotoMode(false);
            hideNormalHud();
            if (document.pointerLockElement) document.exitPointerLock();
          } else if (!active) {
            player.syncFromCamera();
            // Keep flying if the tour left the camera well above the floor below it (ground is sloped now)
            const feet = camera.position.y - collision.eyeHeight;
            const floor = collision.resolveWalkPosition(camera.position.x, feet, camera.position.z).groundY;
            player.setFlyMode(feet - floor > 2.5);
            restoreNormalHud();
          }
        };
        tourInst.onTimeUpdate = (hours) => applyTime(hours);
        tour = tourInst;
        return tourInst;
      });
      tourPromise.catch((err) => {
        console.warn('[Tour] module failed to load:', err);
        tourPromise = null;
      });
    }
    return tourPromise;
  };
  const toggleTour = () => {
    void loadTour().then((t) => t.toggle());
  };
  btnTour.addEventListener('click', toggleTour);
  tourPauseBtn.addEventListener('click', () => tour?.togglePause());
  tourNextBtn.addEventListener('click', () => tour?.nextChapter());
  tourStopBtn.addEventListener('click', () => tour?.stop());

  const syncAudioButton = (on: boolean) => {
    btnAudio.textContent = t(on ? 'btn.audioOn' : 'btn.audio');
    btnAudio.classList.toggle('active', on);
  };
  const toggleAudio = () => {
    if (!audio) {
      void audioReady.then((a) => a && syncAudioButton(a.toggle()));
      return;
    }
    syncAudioButton(audio.toggle());
  };
  btnAudio.addEventListener('click', toggleAudio);

  audioVolume.addEventListener('input', () => {
    audio?.setVolume(parseFloat(audioVolume.value));
  });
  void audioReady.then((a) => a?.setVolume(parseFloat(audioVolume.value)));

  // Time-of-day & Historical Construction Timelapse Tabs
  const tabSun = document.getElementById('tab-sun') as HTMLButtonElement;
  const tabHistory = document.getElementById('tab-history') as HTMLButtonElement;
  const paneSun = document.getElementById('pane-sun')!;
  const paneHistory = document.getElementById('pane-history')!;

  const selectLeftTab = (tab: 'sun' | 'history') => {
    tabSun.classList.toggle('active', tab === 'sun');
    tabHistory.classList.toggle('active', tab === 'history');
    paneSun.classList.toggle('hidden', tab !== 'sun');
    paneHistory.classList.toggle('hidden', tab !== 'history');
  };
  tabSun.addEventListener('click', () => selectLeftTab('sun'));
  tabHistory.addEventListener('click', () => selectLeftTab('history'));

  const timelineSlider = document.getElementById('timeline-slider') as HTMLInputElement;
  const timelineYearDisplay = document.getElementById('timeline-year-display')!;
  const timelineCaption = document.getElementById('timeline-caption')!;
  const timelinePlayBtn = document.getElementById('timeline-play-btn') as HTMLButtonElement;
  const timelineChipBtns = Array.from(document.querySelectorAll<HTMLButtonElement>('.timeline-chips .chip-btn[data-year]'));

  sagrada.timeline.onYearChange = (year, caption) => {
    timelineSlider.value = String(year);
    timelineYearDisplay.textContent = year >= 2033.8 ? t('timeline.final') : t('timeline.year', { year: Math.round(year) });
    timelineCaption.textContent = caption;
    timelineChipBtns.forEach((b) => {
      const target = parseFloat(b.dataset.year!);
      b.classList.toggle('active', Math.abs(target - year) < 2.0);
    });
    sagrada.lighting.requestShadowUpdate(false);
  };
  sagrada.timeline.onPlayChange = (playing) => {
    timelinePlayBtn.textContent = t(playing ? 'timeline.pause' : 'timeline.play');
    timelinePlayBtn.classList.toggle('active', playing);
  };

  timelineSlider.addEventListener('input', () => {
    sagrada.timeline.setPlaying(false);
    sagrada.timeline.applyYear(parseFloat(timelineSlider.value));
  });
  timelinePlayBtn.addEventListener('click', () => {
    // Frame an epic exterior aerial view automatically if starting timelapse from deep inside
    if (!sagrada.timeline.playing && collision.getIndoorFactor(camera.position) > 0.6) {
      const aerial = TELEPORT_PRESETS[TELEPORT_PRESETS.length - 1];
      player.teleportTo(aerial);
    }
    sagrada.timeline.togglePlay();
  });
  timelineChipBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      sagrada.timeline.setPlaying(false);
      sagrada.timeline.applyYear(parseFloat(btn.dataset.year!));
    });
  });

  // Time-of-day controls (default: dramatic Barcelona Golden Hour 17:15!)
  const timeChipBtns = Array.from(document.querySelectorAll<HTMLButtonElement>('.chip-btn[data-time]'));
  const applyTime = (hours: number) => {
    sagrada.lighting.setTimeOfDay(hours);
    post.setNightBloomFactor(sagrada.lighting.nightFactor);
    timeSlider.value = String(hours);
    timeDisplay.textContent = formatHours(hours);
    timeChipBtns.forEach((b) => {
      const target = parseFloat(b.dataset.time!);
      b.classList.toggle('active', Math.abs(target - hours) < 0.15);
    });
  };
  timeSlider.addEventListener('input', () => applyTime(parseFloat(timeSlider.value)));
  timeChipBtns.forEach((btn) => {
    btn.addEventListener('click', () => applyTime(parseFloat(btn.dataset.time!)));
  });
  applyTime(18.08);

  // Weather Atmosphere Controls (Klar / Nebel / Regen)
  const weatherBtns = Array.from(document.querySelectorAll<HTMLButtonElement>('.weather-btn[data-weather]'));
  const applyWeather = (mode: WeatherMode) => {
    sagrada.weather.setMode(mode);
    weatherBtns.forEach((b) => b.classList.toggle('active', b.dataset.weather === mode));
  };
  weatherBtns.forEach((btn) => {
    btn.addEventListener('click', () => applyWeather(btn.dataset.weather as WeatherMode));
  });

  // ── Live language switch: re-render every JS-managed string without touching app state ──
  // (static markup is handled by translateDom() inside setLang(); this covers dynamic text)
  const renderLang = () => {
    renderLoadingText();
    // Seed the top-bar read-outs (the render loop keeps them current, but it is paused in hidden tabs)
    zoneBadge.textContent = collision.detectZone(camera.position);
    compassDir.textContent = yawToCompass(player.getYaw());
    altitudeReadout.textContent = t('hud.altitude', { v: fmtNum(camera.position.y, 1) });
    tpButtons.forEach((btn, i) => {
      btn.textContent = loc(TELEPORT_PRESETS[i].shortLabel);
      btn.title = loc(TELEPORT_PRESETS[i].label);
    });
    syncModeUI(player.flyMode);
    syncAudioButton(audio?.enabled ?? false);
    fillQualitySelect();
    renderPhotoLabels();
    if (tour) {
      tourTitle.textContent = loc(tour.currentChapter.title);
      tourSub.textContent = loc(tour.currentChapter.subtitle);
    }
    tourPauseBtn.textContent = t(tour?.paused ? 'tour.resume' : 'tour.pause');
    const year = sagrada.timeline.currentYear;
    timelineYearDisplay.textContent =
      year >= 2033.8 ? t('timeline.final') : t('timeline.year', { year: Math.round(year) });
    timelineCaption.textContent = sagrada.timeline.getCaptionForYear(year);
    timelinePlayBtn.textContent = t(sagrada.timeline.playing ? 'timeline.pause' : 'timeline.play');
    hotspots.refreshLanguage();
    minimap.refreshLanguage();
  };
  renderLang();
  onLangChange(renderLang);

  // Start immediately into live 3D view with ZERO confirmation modal!
  // Single click anywhere on the canvas locks mouse pointer into direct Ego-Shooter FPS control.
  player.onPointerLockChange = () => {};

  let entered = false;
  window.addEventListener('keydown', (e) => {
    if (!entered) return;
    const isTextInput =
      (e.target instanceof HTMLInputElement && e.target.type !== 'range' && e.target.type !== 'button') ||
      e.target instanceof HTMLTextAreaElement;
    if (isTextInput) return;
    if (e.code === 'KeyG') toggleGeometry();
    else if (e.code === 'KeyH') toggleHotspots();
    else if (e.code === 'KeyM') toggleMinimap();
    else if (e.code === 'KeyU') toggleAudio();
    else if (e.code === 'KeyO') perfMonitor.toggle();
    else if (e.code === 'KeyB') selectLeftTab(paneHistory.classList.contains('hidden') ? 'history' : 'sun');
    else if (e.code === 'KeyT') toggleTour();
    else if (e.code === 'KeyP') setPhotoMode(!photoMode);
    else if (e.code === 'KeyL') sagrada.elevator.triggerAction(camera.position);
    else if (e.code === 'KeyV' && photoMode) setPhotoClean(!photoCleanCanvas);
    else if (
      tour?.active &&
      ['KeyW', 'KeyA', 'KeyS', 'KeyD', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Escape'].includes(e.code)
    ) {
      tour.stop();
    }
  });

  // Release button/slider focus after pointer interaction so Arrow keys & Space always control walking immediately
  document.addEventListener('pointerup', () => {
    const active = document.activeElement;
    if (active instanceof HTMLButtonElement || (active instanceof HTMLInputElement && active.type === 'range')) {
      active.blur();
    }
  });

  // ── Robust resize / orientation / DPR handling (coalesced to one update per frame) ──
  let lastW = window.innerWidth;
  let lastH = window.innerHeight;
  let resizeQueued = false;
  const applyResize = () => {
    resizeQueued = false;
    const w = Math.max(1, Math.round(window.visualViewport?.width ?? window.innerWidth));
    const h = Math.max(1, Math.round(window.visualViewport?.height ?? window.innerHeight));
    const cw = Math.max(1, window.innerWidth);
    const ch = Math.max(1, window.innerHeight);
    // The canvas is fixed to the layout viewport; visualViewport only decides whether something changed
    if (cw === lastW && ch === lastH && w > 0 && h > 0) return;
    lastW = cw;
    lastH = ch;
    camera.aspect = cw / ch;
    camera.updateProjectionMatrix();
    post.setSize(cw, ch);
  };
  const queueResize = () => {
    if (resizeQueued) return;
    resizeQueued = true;
    requestAnimationFrame(applyResize);
  };
  window.addEventListener('resize', queueResize);
  window.visualViewport?.addEventListener('resize', queueResize);
  window.addEventListener('orientationchange', () => {
    // iOS reports the old size during the event; re-check after the rotation settles
    queueResize();
    setTimeout(queueResize, 250);
    setTimeout(queueResize, 700);
  });
  const watchDpr = () => {
    if (typeof window.matchMedia !== 'function') return;
    const mq = window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`);
    const onChange = () => {
      mq.removeEventListener('change', onChange);
      post.applyQuality(refreshQualityForDpr());
      watchDpr();
    };
    mq.addEventListener('change', onChange);
  };
  watchDpr();

  // ── WebGL context loss / restore ──
  let contextLost = false;
  let loopStarted = false;
  let rafId = 0;
  let running = false;
  canvas.addEventListener(
    'webglcontextlost',
    (e) => {
      e.preventDefault(); // signals that we want the context back
      contextLost = true;
      stopLoop();
      setGlStatus('gl.contextLost');
    },
    false
  );
  canvas.addEventListener(
    'webglcontextrestored',
    () => {
      // three.js re-initialises its GL state in its own listener (registered first); we rebuild GPU-only data
      void (async () => {
        try {
          await sagrada.lighting.handleContextRestored();
          sagrada.handleContextRestored();
          post.handleContextRestored();
          contextLost = false;
          setGlStatus(null);
          if (loopStarted && !document.hidden) startLoop();
        } catch (err) {
          console.error('[GL] context restore failed:', err);
          setGlStatus('gl.restoreFailed');
        }
      })();
    },
    false
  );

  performance.mark('sagrada:boot:ui');
  // Honest complete load: all GLBs + shared PBR WebP textures + 3D BVH + HDRIs + shader & GPU warm-up!
  try {
    const onLoadProgress = (fraction: number, status: LoadStatus) => {
      const pct = Math.min(100, Math.max(0, Math.round(fraction * 100)));
      loadingFill.style.width = `${pct}%`;
      loadingPct = pct;
      loadingStatusMsg = status;
      renderLoadingText();
    };
    await Promise.all([sagrada.loadAllModules(camera, collision, onLoadProgress), post.prepare(), audioReady]);
    performance.mark('sagrada:load:modules-done');
    // Shader warm-up for exactly the variants this tier draws, then one real frame (shadow map,
    // pond reflector, texture uploads, post stack) behind the loading card
    await sagrada.warmUp(camera, collision, post.usingComposer, () => post.render(0.016), onLoadProgress);
    performance.mark('sagrada:assets-ready');
  } catch (err) {
    console.error(err);
    if (err instanceof AssetLoadError) {
      showFatalError('error.assetFailTitle', 'error.assetFailBody', {
        modules: err.moduleIds.map(getModuleLabel).join(', '),
      });
    } else {
      showFatalError('error.genericFailTitle', 'error.genericFailBody');
    }
    return;
  }
  if (sagrada.failedModules.length > 0) {
    console.warn(`[Load] continuing without optional modules: ${sagrada.failedModules.join(', ')}`);
  }

  if (import.meta.env.DEV) {
    (window as unknown as Record<string, unknown>).__sagrada = { renderer, camera, sagrada, player, post, collision, THREE };
  }

  // Main Animation Loop (starts immediately behind frosted Enter screen so GPU is 100% hot & fluid!)
  let lastTime = performance.now();
  let hudTick = 0;
  let smoothIndoorFactor = collision.getIndoorFactor(camera.position);
  let lastZone = '';
  let lastCompass = '';
  let lastAlt = '';
  let lastElevMsg: string | null = null;
  let lastElevShown = false;
  let lastCrosshairHidden = true;
  // Force the dirty-checked HUD read-outs (zone, compass, altitude, elevator prompt) to re-render
  onLangChange(() => {
    lastZone = '';
    lastCompass = '';
    lastAlt = '';
    lastElevMsg = null;
  });

  const perfExtra = {
    activeLights: 0,
    totalLights: 0,
    reflectorActive: false,
    reflectorRes: 0,
    shadowMapSize: 0,
    shadowCached: true,
    instancedGroups: 0,
    savedDrawCalls: 0,
    tierLabel: '',
    pixelRatio: 1,
    postLabel: '',
  };

  const animate = (now: number) => {
    if (!running) return;
    rafId = requestAnimationFrame(animate);
    frameHooks.beforeFrame?.(); // bench mode only (see src/perf/hooks.ts)
    renderFrame(now);
    frameHooks.afterFrame?.();
  };
  const renderFrame = (now: number) => {
    const rawDt = frameHooks.fixedDt ?? (now - lastTime) / 1000;
    const dt = Math.min(rawDt, 0.1);
    lastTime = now;

    sagrada.timeline.update(dt);
    // Update central Jesus Tower glass panorama elevator & carry player smoothly if riding inside!
    const wasInElevator = !player.flyMode && sagrada.elevator.isPlayerInside(camera.position);
    const elevDeltaY = sagrada.elevator.update(dt);
    collision.elevatorFloorY = sagrada.elevator.currentY;
    if (wasInElevator && Math.abs(elevDeltaY) > 0.0001) {
      camera.position.y += elevDeltaY;
    }

    touchControls.updateInertia(dt);
    player.setTouchInput(
      touchControls.moveX,
      touchControls.moveY,
      touchControls.flyY,
      touchControls.isSprinting
    );

    if (tour?.active) {
      tour.update(dt);
    } else {
      player.update(dt);
    }
    const targetIndoor = collision.getIndoorFactor(camera.position);
    // Smooth cinematic indoor/outdoor eye & lighting transition (~0.5s glide, ZERO sudden snap at doorway!)
    smoothIndoorFactor = THREE.MathUtils.lerp(smoothIndoorFactor, targetIndoor, Math.min(1, dt * 2.8));
    const indoorFactor = smoothIndoorFactor;
    // Physical camera Auto-Eye-Adaptation: warm outdoor exposure (0.84), rich nave glow indoors (0.95), intimate crypt (0.82)
    if (!photoMode) {
      const targetExp =
        isEyeUnderground(camera.position.x, camera.position.y, camera.position.z)
          ? 0.96
          : THREE.MathUtils.lerp(
              THREE.MathUtils.lerp(0.84, 0.92, sagrada.lighting.nightFactor),
              0.95,
              indoorFactor
            );
      renderer.toneMappingExposure = THREE.MathUtils.lerp(
        renderer.toneMappingExposure,
        targetExp,
        Math.min(1, dt * 2.2)
      );
    }
    sagrada.update(dt, camera, indoorFactor);
    post.render(dt);

    const lightStats = sagrada.lighting.getPerfLightStats();
    perfExtra.activeLights = lightStats.activeLights;
    perfExtra.totalLights = lightStats.totalLights;
    perfExtra.reflectorActive = sagrada.reflectorActive;
    perfExtra.reflectorRes = sagrada.reflectorRes;
    perfExtra.shadowMapSize = sagrada.lighting.shadowMapSize;
    perfExtra.shadowCached = lightStats.shadowCached;
    perfExtra.instancedGroups = sagrada.instancedGroups;
    perfExtra.savedDrawCalls = sagrada.savedDrawCalls;
    perfExtra.tierLabel = QUALITY_TEXT.tier(getQuality().tier);
    perfExtra.pixelRatio = post.currentPixelRatio;
    perfExtra.postLabel = post.usingComposer ? (post.gtaoActive ? 'Composer + GTAO' : 'Composer') : t('perf.direct');
    perfMonitor.sampleFrame(dt, renderer, perfExtra);

    if (!entered) return;

    // Dynamic resolution scaling inside the tier's bounds (uses the raw frame time, 1 s windows)
    post.sampleFrame(rawDt);

    // Update UI overlays smoothly (dirty-checked to avoid per-frame DOM thrash!)
    const crossHidden = !player.isPointerLocked;
    if (crossHidden !== lastCrosshairHidden) {
      lastCrosshairHidden = crossHidden;
      crosshairEl.classList.toggle('hidden', crossHidden);
    }
    hotspots.updateProjections(camera, window.innerWidth, window.innerHeight);

    hudTick += dt;
    if (hudTick >= 0.08) {
      hudTick = 0;
      const nextZone = collision.detectZone(camera.position);
      if (nextZone !== lastZone) {
        lastZone = nextZone;
        zoneBadge.textContent = nextZone;
      }
      const nextCompass = yawToCompass(player.getYaw());
      if (nextCompass !== lastCompass) {
        lastCompass = nextCompass;
        compassDir.textContent = nextCompass;
      }
      const nextAlt = t('hud.altitude', { v: fmtNum(camera.position.y, 1) });
      if (nextAlt !== lastAlt) {
        lastAlt = nextAlt;
        altitudeReadout.textContent = nextAlt;
      }
      audio?.updateSpatial(0.08, indoorFactor, camera.position, sagrada.weather.rainFactor);

      const elevMsg =
        !tourActive() && !photoMode
          ? sagrada.elevator.getPromptText(camera.position, touchControls.isTouchActive)
          : null;
      touchControls.setElevatorAvailable(!!elevMsg);
      if (elevMsg) {
        if (elevMsg !== lastElevMsg) {
          lastElevMsg = elevMsg;
          elevatorPrompt.innerHTML = elevMsg;
        }
        if (!lastElevShown) {
          lastElevShown = true;
          elevatorPrompt.classList.remove('hidden');
        }
      } else if (lastElevShown) {
        lastElevShown = false;
        lastElevMsg = null;
        elevatorPrompt.classList.add('hidden');
      }

      if (!minimapContainer.classList.contains('hidden')) {
        minimap.render(camera.position, player.getYaw());
      }
    }
  };

  function startLoop(): void {
    if (running || contextLost) return;
    running = true;
    loopStarted = true;
    lastTime = performance.now();
    post.resetDrs();
    rafId = requestAnimationFrame(animate);
  }
  function stopLoop(): void {
    running = false;
    cancelAnimationFrame(rafId);
  }

  // Stop rendering (and pause audio) while the tab is hidden; resume without a dt spike
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      stopLoop();
      audio?.setPageHidden(true);
    } else {
      audio?.setPageHidden(false);
      queueResize();
      startLoop();
    }
  });

  if (!document.hidden) startLoop();
  else loopStarted = true; // visibilitychange will start it

  // Collision BVH right after the first frame instead of before it: the visitor cannot move before
  // the start gate is passed, and player.enabled waits for this promise (no walking without floors).
  // (rAF registered after startLoop's: the first live frame is drawn, then the BVH task runs)
  const collisionReady = new Promise<void>((resolve) => requestAnimationFrame(() => setTimeout(resolve, 0)))
    .then(() => collision.buildBVH())
    .then((s) => {
      performance.mark('sagrada:bvh-ready');
      console.info(`[Collision] 3D BVH ready: ${s.triangles.toLocaleString()} tris across ${s.meshes} meshes in ${s.buildMs} ms`);
    });
  collisionReady.catch((err) => {
    console.error(err);
    showFatalError('error.genericFailTitle', 'error.genericFailBody');
  });

  // Remaining time-of-day HDRIs only after the first frame (they are not needed to show the scene)
  const idle = (window as Window & { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => void })
    .requestIdleCallback;
  const deferredWork = () => {
    // Interior reflection probe (not needed for the outdoor start view; update() also captures it on entering)
    sagrada.captureDeferredProbe();
    sagrada.lighting.loadDeferredHdris();
  };
  if (idle) idle(deferredWork, { timeout: 3000 });
  else setTimeout(deferredWork, 1000);

  // Scene is 100% loaded, shaders compiled & live-rendering -> reveal "Basílica betreten" gate!
  loadingScreen.classList.add('loading-ready');
  loadingProgressWrap.classList.add('hidden');
  loadingEnterWrap.classList.remove('hidden');
  btnEnterBasilica.focus();

  const enterBasilica = () => {
    if (entered) return;
    entered = true;
    void collisionReady.then(() => {
      player.enabled = true;
    });
    btnEnterBasilica.blur();

    // Unlock spatial Web Audio cleanly on the user gesture (module was loaded with the scene)
    if (audio && !audio.enabled) {
      syncAudioButton(audio.toggle());
    }

    // Lock FPS mouse look cleanly inside the user click gesture (not on touch-first devices)
    if (!prefersTouchUI()) {
      player.requestPointerLock();
    }

    loadingScreen.classList.add('fade-out');
    setTimeout(() => loadingScreen.classList.add('hidden'), 340);
    hudPanels.forEach((p) => p.classList.remove('hidden'));

    // Fetch the tour module once the visitor is in (idle time), so [T] responds instantly later
    const ric = (window as Window & { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => void })
      .requestIdleCallback;
    if (ric) ric(() => void loadTour(), { timeout: 4000 });
    else setTimeout(() => void loadTour(), 2000);
  };

  btnEnterBasilica.addEventListener('click', enterBasilica);
  window.addEventListener('keydown', (e) => {
    if (!entered && (e.code === 'Enter' || e.code === 'Space')) {
      e.preventDefault();
      enterBasilica();
    }
  });

  // Bench mode: same effect as the start gate (scene visible, player live) minus pointer lock and audio
  if (bench) {
    bench.startBench({
      renderer,
      camera,
      sagrada,
      player,
      post,
      onReady: () => {
        entered = true;
        void collisionReady.then(() => {
          player.enabled = true;
        });
        loadingScreen.classList.add('hidden');
      },
    });
  }
}

void bootstrap();
