/**
 * Central graphics quality tiers (low / medium / high / ultra).
 *
 * The tier is picked automatically from device signals (touch / mobile, deviceMemory,
 * hardwareConcurrency, GPU renderer string, devicePixelRatio) and can be overridden by the
 * user from the HUD. The override is persisted in localStorage.
 *
 * Every rendering-cost decision in the app reads from the active {@link QualitySettings}
 * instead of branching on a binary "is mobile" check.
 *
 * Settings marked "boot" are read once while the scene is constructed (particle buffers,
 * shader variants, GL context attributes, texture downscaling). Settings marked "live" are
 * re-applied immediately when the user switches tiers.
 */
import { isMobileDevice, isTouchDevice } from './device';
import { t, type MessageKey } from '../i18n';

export type QualityTier = 'low' | 'medium' | 'high' | 'ultra';
export type QualityPreference = QualityTier | 'auto';

export const QUALITY_TIERS: readonly QualityTier[] = ['low', 'medium', 'high', 'ultra'];

const TIER_KEYS: Record<QualityTier, MessageKey> = {
  low: 'quality.low',
  medium: 'quality.medium',
  high: 'quality.high',
  ultra: 'quality.ultra',
};

/** User-visible strings, resolved in the current UI language on every read (see src/i18n). */
export const QUALITY_TEXT = {
  tier: (tier: QualityTier): string => t(TIER_KEYS[tier]),
  /** e.g. "Auto · High" */
  autoWith: (tierLabel: string): string => t('quality.autoWith', { tier: tierLabel }),
  get selectTitle(): string {
    return t('quality.selectTitle');
  },
  get selectAria(): string {
    return t('quality.selectAria');
  },
};

export interface QualitySettings {
  tier: QualityTier;
  // ── GL context / boot ──
  /** Hardware MSAA (default framebuffer; composer uses its own MSAA target). boot */
  antialias: boolean;
  /** Max texture edge for GLB PBR textures; larger textures are downscaled at load. boot */
  maxTextureSize: number;
  /** Anisotropic filtering level (capped by the GPU). boot */
  anisotropy: number;
  /** Keep MeshPhysicalMaterial clearcoat on the polished marble / porphyry. boot */
  keepClearcoat: boolean;
  /** Cheaper 1-octave stone anti-tiling shader without vault haze. boot */
  leanStoneShader: boolean;
  /** Sky cloud FBM octaves. boot */
  cloudOctaves: number;
  /** Textured stained-glass SpotLight projectors (2 extra lights in every lit shader). boot */
  stainedGlassProjectors: boolean;
  /** Interior reflection-probe cube face size. boot */
  probeRes: number;
  /** MSAA samples of the pond reflector target. boot */
  reflectorMultisample: number;
  birdCount: number;
  fountainParticles: number;
  dustParticles: number;
  rainDrops: number;
  incenseParticles: number;

  // ── live ──
  /** Upper pixel-ratio bound (already capped by window.devicePixelRatio). live */
  maxPixelRatio: number;
  /** Lower bound the dynamic resolution scaler may go down to. live */
  minPixelRatio: number;
  /** FPS below which DRS lowers resolution / above which it may raise it again. live */
  drsLowFps: number;
  drsHighFps: number;
  bloom: boolean;
  colorGrade: boolean;
  gtao: boolean;
  shadowMapSize: number;
  softShadows: boolean;
  reflectorRes: number;
  /** Re-render the pond reflection every N frames while the camera is still. live */
  reflectorStationaryPeriod: number;
  /** Render the reflection only every 2nd frame while moving. live */
  reflectorHalfRate: boolean;
  /** Leave trees & street furniture out of the pond reflection (vertex cost on weak GPUs). boot */
  reflectorLite: boolean;
  /** Minimum time between sun-shadow re-renders while time of day / timeline animates. live */
  shadowUpdateIntervalMs: number;
}

type TierPreset = Omit<QualitySettings, 'tier' | 'maxPixelRatio' | 'minPixelRatio'> & {
  pixelRatioCap: number;
  pixelRatioFloor: number;
};

const PRESETS: Record<QualityTier, TierPreset> = {
  low: {
    antialias: false,
    maxTextureSize: 512,
    anisotropy: 2,
    keepClearcoat: false,
    leanStoneShader: true,
    cloudOctaves: 2,
    stainedGlassProjectors: false,
    probeRes: 128,
    reflectorMultisample: 0,
    birdCount: 8,
    fountainParticles: 200,
    dustParticles: 300,
    rainDrops: 650,
    incenseParticles: 32,
    pixelRatioCap: 1.0,
    pixelRatioFloor: 0.65,
    drsLowFps: 34,
    drsHighFps: 52,
    bloom: false,
    colorGrade: false,
    gtao: false,
    shadowMapSize: 1024,
    softShadows: false,
    reflectorRes: 160,
    reflectorStationaryPeriod: 12,
    reflectorHalfRate: true,
    reflectorLite: true,
    shadowUpdateIntervalMs: 250,
  },
  medium: {
    antialias: true,
    maxTextureSize: 4096,
    anisotropy: 4,
    keepClearcoat: true,
    leanStoneShader: false,
    cloudOctaves: 3,
    stainedGlassProjectors: true,
    probeRes: 256,
    reflectorMultisample: 2,
    birdCount: 16,
    fountainParticles: 420,
    dustParticles: 900,
    rainDrops: 1600,
    incenseParticles: 64,
    pixelRatioCap: 1.25,
    pixelRatioFloor: 0.75,
    drsLowFps: 42,
    drsHighFps: 56,
    bloom: false,
    colorGrade: false,
    gtao: false,
    shadowMapSize: 2048,
    softShadows: true,
    reflectorRes: 256,
    reflectorStationaryPeriod: 8,
    reflectorHalfRate: false,
    reflectorLite: false,
    shadowUpdateIntervalMs: 120,
  },
  high: {
    antialias: true,
    maxTextureSize: 4096,
    anisotropy: 8,
    keepClearcoat: true,
    leanStoneShader: false,
    cloudOctaves: 3,
    stainedGlassProjectors: true,
    probeRes: 256,
    reflectorMultisample: 4,
    birdCount: 16,
    fountainParticles: 420,
    dustParticles: 900,
    rainDrops: 1600,
    incenseParticles: 64,
    pixelRatioCap: 2.0,
    pixelRatioFloor: 0.85,
    drsLowFps: 45,
    drsHighFps: 57,
    bloom: true,
    colorGrade: true,
    gtao: false,
    shadowMapSize: 2048,
    softShadows: true,
    reflectorRes: 384,
    reflectorStationaryPeriod: 6,
    reflectorHalfRate: false,
    reflectorLite: false,
    shadowUpdateIntervalMs: 85,
  },
  ultra: {
    antialias: true,
    maxTextureSize: 4096,
    anisotropy: 16,
    keepClearcoat: true,
    leanStoneShader: false,
    cloudOctaves: 3,
    stainedGlassProjectors: true,
    probeRes: 512,
    reflectorMultisample: 4,
    birdCount: 16,
    fountainParticles: 420,
    dustParticles: 900,
    rainDrops: 1600,
    incenseParticles: 64,
    pixelRatioCap: 2.0,
    pixelRatioFloor: 1.0,
    drsLowFps: 45,
    drsHighFps: 57,
    bloom: true,
    colorGrade: true,
    gtao: true,
    shadowMapSize: 4096,
    softShadows: true,
    reflectorRes: 512,
    reflectorStationaryPeriod: 4,
    reflectorHalfRate: false,
    reflectorLite: false,
    shadowUpdateIntervalMs: 85,
  },
};

export interface DeviceSignals {
  webgl2: boolean;
  gpu: string;
  mobile: boolean;
  tablet: boolean;
  touch: boolean;
  deviceMemory: number | null;
  cores: number | null;
  dpr: number;
}

let cachedSignals: DeviceSignals | null = null;

function readGpuString(): { webgl2: boolean; gpu: string } {
  try {
    const c = document.createElement('canvas');
    const gl = c.getContext('webgl2', { failIfMajorPerformanceCaveat: false });
    if (!gl) return { webgl2: false, gpu: '' };
    let gpu = '';
    const ext = gl.getExtension('WEBGL_debug_renderer_info');
    if (ext) gpu = String(gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) ?? '');
    if (!gpu) gpu = String(gl.getParameter(gl.RENDERER) ?? '');
    // Free the probe context right away (browsers cap the number of live contexts)
    gl.getExtension('WEBGL_lose_context')?.loseContext();
    return { webgl2: true, gpu };
  } catch {
    return { webgl2: false, gpu: '' };
  }
}

export function getDeviceSignals(): DeviceSignals {
  if (cachedSignals) return cachedSignals;
  const { webgl2, gpu } = readGpuString();
  const nav = navigator as Navigator & { deviceMemory?: number };
  const ua = navigator.userAgent;
  const iPadOS = /Macintosh/.test(ua) && navigator.maxTouchPoints > 1;
  const tablet = iPadOS || /iPad|Tablet/i.test(ua) || (/Android/i.test(ua) && !/Mobile/i.test(ua));
  cachedSignals = {
    webgl2,
    gpu,
    mobile: isMobileDevice() || iPadOS,
    tablet,
    touch: isTouchDevice(),
    deviceMemory: typeof nav.deviceMemory === 'number' ? nav.deviceMemory : null,
    cores: typeof navigator.hardwareConcurrency === 'number' ? navigator.hardwareConcurrency : null,
    dpr: window.devicePixelRatio || 1,
  };
  return cachedSignals;
}

/** Pure heuristic so it can be reasoned about / unit-tested in isolation. */
export function detectQualityTier(s: DeviceSignals): QualityTier {
  if (!s.webgl2) return 'low';
  const gpu = s.gpu.toLowerCase();
  if (/swiftshader|llvmpipe|softpipe|software|basic render|microsoft basic/.test(gpu)) return 'low';

  const mem = s.deviceMemory;
  const cores = s.cores ?? 4;

  if (s.mobile) {
    const strongMobileGpu =
      /adreno[^0-9]*(7[3-9]\d|[89]\d\d)|mali-g(7[1-9]|[89]\d|\d{3})|immortalis|xclipse/.test(gpu);
    if (s.tablet && ((mem !== null && mem >= 6) || /apple/.test(gpu))) return 'medium';
    if (strongMobileGpu && mem !== null && mem >= 6) return 'medium';
    return 'low';
  }

  // Desktop / laptop
  if ((mem !== null && mem <= 2) || cores <= 2) return 'low';
  const discrete =
    /nvidia|geforce|quadro|rtx|gtx|radeon\s*(rx|pro|r9|vii)|\brx\s*\d{3,4}|intel.*\barc\b|apple m\d\s*(pro|max|ultra)/.test(gpu);
  const appleSilicon = /apple m\d|apple gpu/.test(gpu);
  const integrated = /intel|uhd|iris|hd graphics|radeon\(tm\) graphics|radeon graphics|vega \d+ graphics|mali|adreno/.test(gpu);

  if (discrete && (mem === null || mem >= 8) && cores >= 8) return 'ultra';
  if (discrete || appleSilicon) return 'high';
  if (integrated) return 'medium';
  if (mem !== null && mem <= 4) return 'medium';
  return 'high';
}

const STORAGE_KEY = 'sagrada.quality';

export function loadQualityPreference(): QualityPreference {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === 'auto' || (v && (QUALITY_TIERS as readonly string[]).includes(v))) return v as QualityPreference;
  } catch {
    // Storage blocked (private mode / sandboxed iframe)
  }
  return 'auto';
}

export function saveQualityPreference(pref: QualityPreference): void {
  try {
    if (pref === 'auto') localStorage.removeItem(STORAGE_KEY);
    else localStorage.setItem(STORAGE_KEY, pref);
  } catch {
    // Ignore
  }
}

export function buildQualitySettings(tier: QualityTier, dpr = window.devicePixelRatio || 1): QualitySettings {
  const p = PRESETS[tier];
  const { pixelRatioCap, pixelRatioFloor, ...rest } = p;
  const maxPixelRatio = Math.min(dpr, pixelRatioCap);
  const minPixelRatio = Math.min(maxPixelRatio, pixelRatioFloor);
  return { ...rest, tier, maxPixelRatio, minPixelRatio };
}

let activePreference: QualityPreference = 'auto';
let autoTier: QualityTier = 'high';
let bootSettings: QualitySettings | null = null;
let activeSettings: QualitySettings | null = null;

/** Bench mode only (`?bench&tier=<tier>`): forced tier for this page load, never persisted. */
export function benchTierFromUrl(): QualityTier | null {
  try {
    const params = new URLSearchParams(window.location.search);
    if (!params.has('bench')) return null;
    const v = params.get('tier');
    return v && (QUALITY_TIERS as readonly string[]).includes(v) ? (v as QualityTier) : null;
  } catch {
    return null;
  }
}

/** Call once at startup (before creating the renderer). */
export function initQuality(): QualitySettings {
  const signals = getDeviceSignals();
  autoTier = detectQualityTier(signals);
  activePreference = benchTierFromUrl() ?? loadQualityPreference();
  const tier = activePreference === 'auto' ? autoTier : activePreference;
  activeSettings = buildQualitySettings(tier);
  bootSettings = activeSettings;
  return activeSettings;
}

/** Settings the scene was constructed with (boot-time decisions read this). */
export function getBootQuality(): QualitySettings {
  if (!bootSettings) initQuality();
  return bootSettings!;
}

/** Currently active settings (live decisions read this). */
export function getQuality(): QualitySettings {
  if (!activeSettings) initQuality();
  return activeSettings!;
}

export function getQualityPreference(): QualityPreference {
  return activePreference;
}

export function getAutoTier(): QualityTier {
  return autoTier;
}

export function setQualityPreference(pref: QualityPreference): QualitySettings {
  activePreference = pref;
  saveQualityPreference(pref);
  const tier = pref === 'auto' ? autoTier : pref;
  activeSettings = buildQualitySettings(tier);
  return activeSettings;
}

/** Recompute DPR-dependent bounds (window moved to another monitor, zoom change). */
export function refreshQualityForDpr(): QualitySettings {
  activeSettings = buildQualitySettings(getQuality().tier);
  return activeSettings;
}
