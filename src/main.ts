import './styles.css';
import * as THREE from 'three';
import { SagradaScene } from './scene/SagradaScene';
import { WeatherMode } from './scene/WeatherSystem';
import { PostProcessingPipeline } from './scene/PostProcessing';
import { CollisionSystem } from './scene/CollisionSystem';
import { PlayerController } from './controls/PlayerController';
import { TouchControls } from './controls/TouchControls';
import { CinematicTour } from './controls/CinematicTour';
import { AmbienceAudio } from './audio/AmbienceAudio';
import { TELEPORT_PRESETS, FloorLevel } from './data/teleports';
import { Minimap } from './ui/Minimap';
import { HotspotPanel } from './ui/HotspotPanel';
import { PerfMonitor } from './ui/PerfMonitor';
import { isMobileDevice, isTouchDevice, triggerHaptic } from './utils/device';

function formatHours(h: number): string {
  const hh = Math.floor(h) % 24;
  const mm = Math.floor((h - Math.floor(h)) * 60);
  return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`;
}

function yawToCompass(yaw: number): string {
  // Forward vector = (-sin(yaw), -cos(yaw)); North = -Z (yaw = 0), East = +X (yaw = -pi/2)
  const deg = (((-yaw * 180) / Math.PI) % 360 + 360) % 360;
  const dirs = ['N', 'NO', 'O', 'SO', 'S', 'SW', 'W', 'NW'];
  return dirs[Math.round(deg / 45) % 8];
}

async function bootstrap(): Promise<void> {
  const canvas = document.getElementById('scene-canvas') as HTMLCanvasElement;

  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true, // Used cleanly in 'fast' single-pass mode; 'aaa'/'ultra' use 4x MSAA HalfFloat RT
    powerPreference: 'high-performance',
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, isMobileDevice() ? 1.0 : 1.1));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.autoUpdate = false; // Cached 2K sun shadows: only re-rendered when sun moves or scene loads!
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.localClippingEnabled = true; // Enables smooth stone-by-stone historical construction timelapse!
  // Blender 4/5 cinema standard: realistic physical exposure (0.74 outdoors -> auto-adapts gently indoors!)
  renderer.toneMapping = THREE.AgXToneMapping;
  renderer.toneMappingExposure = 0.74;
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const camera = new THREE.PerspectiveCamera(62, window.innerWidth / window.innerHeight, 0.25, 1100);
  const sagrada = new SagradaScene(renderer);
  const post = new PostProcessingPipeline(renderer, sagrada.scene, camera);
  const collision = new CollisionSystem();
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
  const tour = new CinematicTour(camera);
  const audio = new AmbienceAudio();

  // Start at the iconic Plaça de Gaudí viewpoint across the reflective pond facing the Nativity Facade!
  player.teleportTo(TELEPORT_PRESETS[0], true);

  // UI Elements
  const loadingScreen = document.getElementById('loading-screen')!;
  const loadingFill = document.getElementById('loading-bar-fill')!;
  const loadingStatus = document.getElementById('loading-status')!;

  const hudPanels = [
    document.getElementById('hud-top')!,
    document.getElementById('hud-time')!,
    document.getElementById('hud-teleports')!,
    document.getElementById('hud-minimap')!,
    document.getElementById('controls-banner')!,
  ];
  const crosshairEl = document.getElementById('crosshair')!;
  const fpsStartOverlay = document.getElementById('fps-start-overlay')!;
  const elevatorPrompt = document.getElementById('elevator-prompt')!;
  const zoneBadge = document.getElementById('zone-badge')!;
  const compassDir = document.getElementById('compass-dir')!;
  const altitudeReadout = document.getElementById('altitude-readout')!;
  const modeBadge = document.getElementById('mode-badge')!;

  const btnWalkMode = document.getElementById('btn-walk-mode') as HTMLButtonElement;
  const btnGeometry = document.getElementById('btn-geometry') as HTMLButtonElement;
  const btnHotspots = document.getElementById('btn-hotspots') as HTMLButtonElement;
  const btnMinimap = document.getElementById('btn-minimap') as HTMLButtonElement;
  const btnGraphics = document.getElementById('btn-graphics') as HTMLButtonElement;
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
    btn.textContent = preset.shortLabel;
    btn.title = preset.label;
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
    let targetY = 1.75;
    let fly = false;
    if (level === 'crypt') {
      // Clamp inside Crypt circle
      const d = Math.hypot(wx, wz - -21);
      if (d > 13.5) {
        wx = (wx / d) * 13.5;
        wz = -21 + ((wz - -21) / d) * 13.5;
      }
      targetY = -5.5 + collision.eyeHeight;
    } else if (level === 'gallery') {
      targetY = 14.5 + collision.eyeHeight;
    } else if (level === 'towers') {
      if (Math.hypot(wx, wz) < 12) {
        wx = 4.2;
        wz = 2.8;
        targetY = 136.0 + collision.eyeHeight;
      } else if (Math.abs(wx - 31.5) < 10 && Math.abs(wz) < 10) {
        wx = 31.5;
        wz = 0;
        targetY = 65.0 + collision.eyeHeight;
      } else {
        targetY = 95.0;
        fly = true;
      }
    } else {
      const res = collision.resolveWalkPosition(wx, 1.0, wz);
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
    btnWalkMode.textContent = fly ? 'Flug [F]' : 'Gehen [F]';
    modeBadge.textContent = fly ? 'Flugmodus' : 'Gehen';
    touchControls.setFlyVisible(fly);
  };
  player.onModeChange = syncModeUI;
  player.onStep = () => audio.playFootstep();

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

  const tierLabels = { aaa: 'AAA', ultra: 'Ultra (GTAO)', fast: 'Schnell' } as const;
  btnGraphics.addEventListener('click', () => {
    const next = post.cycleTier();
    btnGraphics.textContent = tierLabels[next];
    btnGraphics.classList.toggle('active', next !== 'fast');
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

  const updatePhotoCameraSettings = () => {
    const fov = parseFloat(photoFov.value);
    camera.fov = fov;
    camera.updateProjectionMatrix();
    // Convert vertical FOV to equivalent 35mm full-frame focal length
    const focalMm = Math.round(12 / Math.tan(THREE.MathUtils.degToRad(fov) * 0.5));
    photoFocalVal.textContent = `${focalMm} mm`;

    const exp = parseFloat(photoExposure.value);
    renderer.toneMappingExposure = exp;
    photoExpVal.textContent = exp.toFixed(2);

    const focus = parseFloat(photoFocus.value);
    const ap = parseFloat(photoAperture.value);
    photoFocusVal.textContent = `${focus} m`;
    photoApertureVal.textContent = ap <= 0.000005 ? 'Aus' : `f/${(2.8 / (ap / 0.00018)).toFixed(1)}`;
    post.setDof(ap > 0.000005, focus, ap);
  };

  photoFov.addEventListener('input', updatePhotoCameraSettings);
  photoExposure.addEventListener('input', updatePhotoCameraSettings);
  photoFocus.addEventListener('input', updatePhotoCameraSettings);
  photoAperture.addEventListener('input', updatePhotoCameraSettings);

  photoResetBtn.addEventListener('click', () => {
    photoFov.value = '62';
    photoExposure.value = '0.76';
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
    if (enabled && tour.active) tour.stop();
    photoMode = enabled;
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
      renderer.toneMappingExposure = 0.74;
      restoreNormalHud();
    }
  };
  btnPhoto.addEventListener('click', () => setPhotoMode(!photoMode));
  photoExitBtn.addEventListener('click', () => setPhotoMode(false));
  photoCleanBtn.addEventListener('click', () => setPhotoClean(true));
  photoExitPill.addEventListener('click', () => setPhotoClean(false));

  // Wire Cinematic Architectural Tour [T]
  tour.onChapterChange = (ch) => {
    tourTitle.textContent = ch.title;
    tourSub.textContent = ch.subtitle;
  };
  tour.onProgress = (frac) => {
    tourProgressFill.style.width = `${(frac * 100).toFixed(1)}%`;
  };
  tour.onStateChange = (active, paused) => {
    btnTour.classList.toggle('active', active);
    tourBar.classList.toggle('hidden', !active);
    tourPauseBtn.textContent = paused ? 'Fortsetzen' : 'Pause';
    if (active) {
      if (photoMode) setPhotoMode(false);
      hideNormalHud();
      if (document.pointerLockElement) document.exitPointerLock();
    } else {
      player.syncFromCamera();
      player.setFlyMode(camera.position.y > 4.0);
      restoreNormalHud();
    }
  };
  btnTour.addEventListener('click', () => tour.toggle());
  tourPauseBtn.addEventListener('click', () => tour.togglePause());
  tourNextBtn.addEventListener('click', () => tour.nextChapter());
  tourStopBtn.addEventListener('click', () => tour.stop());

  const toggleAudio = () => {
    const on = audio.toggle();
    btnAudio.textContent = on ? 'Audio ✓' : 'Audio';
    btnAudio.classList.toggle('active', on);
  };
  btnAudio.addEventListener('click', toggleAudio);

  audioVolume.addEventListener('input', () => {
    audio.setVolume(parseFloat(audioVolume.value));
  });

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
    timelineYearDisplay.textContent = year >= 2033.8 ? 'Finaler Entwurf' : `Jahr ${Math.round(year)}`;
    timelineCaption.textContent = caption;
    timelineChipBtns.forEach((b) => {
      const target = parseFloat(b.dataset.year!);
      b.classList.toggle('active', Math.abs(target - year) < 2.0);
    });
    sagrada.lighting.requestShadowUpdate(false);
  };
  sagrada.timeline.onPlayChange = (playing) => {
    timelinePlayBtn.textContent = playing ? '⏸ Pause' : '▶ Zeitraffer';
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
  tour.onTimeUpdate = (hours) => applyTime(hours);
  timeSlider.addEventListener('input', () => applyTime(parseFloat(timeSlider.value)));
  timeChipBtns.forEach((btn) => {
    btn.addEventListener('click', () => applyTime(parseFloat(btn.dataset.time!)));
  });
  applyTime(17.55);

  // Weather Atmosphere Controls (Klar / Nebel / Regen)
  const weatherBtns = Array.from(document.querySelectorAll<HTMLButtonElement>('.weather-btn[data-weather]'));
  const applyWeather = (mode: WeatherMode) => {
    sagrada.weather.setMode(mode);
    weatherBtns.forEach((b) => b.classList.toggle('active', b.dataset.weather === mode));
  };
  weatherBtns.forEach((btn) => {
    btn.addEventListener('click', () => applyWeather(btn.dataset.weather as WeatherMode));
  });

  // Start immediately into live 3D view with ZERO confirmation modal!
  // Single click anywhere on the canvas locks mouse pointer into direct Ego-Shooter FPS control.
  fpsStartOverlay.classList.add('hidden');
  player.onPointerLockChange = () => {};

  window.addEventListener('keydown', (e) => {
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
    if (e.code === 'KeyG') toggleGeometry();
    else if (e.code === 'KeyH') toggleHotspots();
    else if (e.code === 'KeyM') toggleMinimap();
    else if (e.code === 'KeyU') toggleAudio();
    else if (e.code === 'KeyO') perfMonitor.toggle();
    else if (e.code === 'KeyB') selectLeftTab(paneHistory.classList.contains('hidden') ? 'history' : 'sun');
    else if (e.code === 'KeyT') tour.toggle();
    else if (e.code === 'KeyP') setPhotoMode(!photoMode);
    else if (e.code === 'KeyL') sagrada.elevator.triggerAction(camera.position);
    else if (e.code === 'KeyV' && photoMode) setPhotoClean(!photoCleanCanvas);
    else if (tour.active && ['KeyW', 'KeyA', 'KeyS', 'KeyD', 'Escape'].includes(e.code)) tour.stop();
  });

  // Fast Progressive Loading + Asynchronous Shader Pre-Warming (0ms freeze on portal entry!)
  try {
    await sagrada.loadAllModules(camera, (fraction, status) => {
      loadingFill.style.width = `${Math.round(fraction * 100)}%`;
      loadingStatus.textContent = status;
    });
  } catch (err) {
    loadingStatus.textContent = `Fehler beim Laden der 3D-Modelle: ${String(err)}`;
    console.error(err);
    return;
  }

  // Reveal scene & HUD immediately (zero confirmation dialog!)
  loadingScreen.classList.add('fade-out');
  setTimeout(() => loadingScreen.classList.add('hidden'), 650);
  hudPanels.forEach((p) => p.classList.remove('hidden'));

  // Handle Resize
  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    post.setSize(window.innerWidth, window.innerHeight);
  });

  // Main Animation Loop
  let lastTime = performance.now();
  let hudTick = 0;

  const animate = (now: number) => {
    requestAnimationFrame(animate);
    const dt = Math.min((now - lastTime) / 1000, 0.1);
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

    if (tour.active) {
      tour.update(dt);
    } else {
      player.update(dt);
    }
    const indoorFactor = collision.getIndoorFactor(camera.position);
    // Physical camera Auto-Eye-Adaptation: stops down in bright Barcelona sun (0.73), opens subtly indoors (0.86) & crypt (0.95)!
    if (!photoMode) {
      const targetExp =
        camera.position.y < -1.5
          ? 0.96
          : THREE.MathUtils.lerp(
              THREE.MathUtils.lerp(0.73, 0.88, sagrada.lighting.nightFactor),
              0.87,
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
    perfMonitor.sampleFrame(dt, renderer, {
      activeLights: lightStats.activeLights,
      totalLights: lightStats.totalLights,
      reflectorActive: sagrada.reflectorActive,
      shadowCached: lightStats.shadowCached,
      instancedGroups: sagrada.instancedGroups,
      savedDrawCalls: sagrada.savedDrawCalls,
    });

    // Update UI overlays smoothly
    crosshairEl.classList.toggle('hidden', !player.isPointerLocked);
    hotspots.updateProjections(camera, window.innerWidth, window.innerHeight);

    hudTick += dt;
    if (hudTick >= 0.08) {
      hudTick = 0;
      zoneBadge.textContent = collision.detectZone(camera.position);
      compassDir.textContent = yawToCompass(player.getYaw());
      altitudeReadout.textContent = `H: ${camera.position.y.toFixed(1)} m`;
      audio.updateSpatial(0.08, indoorFactor, camera.position, sagrada.weather.rainFactor);

      const elevMsg =
        !tour.active && !photoMode
          ? sagrada.elevator.getPromptText(camera.position, isMobileDevice() || window.innerWidth <= 900)
          : null;
      touchControls.setElevatorAvailable(!!elevMsg);
      if (elevMsg) {
        elevatorPrompt.innerHTML = elevMsg;
        elevatorPrompt.classList.remove('hidden');
      } else {
        elevatorPrompt.classList.add('hidden');
      }

      const fpsText = parseInt(document.getElementById('perf-fps-pill')?.textContent || '60', 10);
      if (!Number.isNaN(fpsText)) {
        post.updateMobileDrs(0.08, fpsText);
      }

      if (!minimapContainer.classList.contains('hidden')) {
        minimap.render(camera.position, player.getYaw());
      }
    }
  };
  requestAnimationFrame(animate);
}

void bootstrap();
