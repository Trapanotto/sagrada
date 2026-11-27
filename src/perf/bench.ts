/**
 * Repeatable in-app benchmark, active only when the URL has `?bench`.
 *
 * URL parameters:
 *   tier=<low|medium|high|ultra>  forced quality tier (not written to localStorage; read in quality.ts)
 *   views=<comma list of teleport ids>  default: the 12 walk/fly teleports below
 *   frames=<n> measured frames per view (default 240), warmup=<n> unmeasured frames (default 60)
 *   w=<px> h=<px>  canvas size (drawing buffer at pixel ratio 1)
 *
 * Result: window.__benchResult and console.log('BENCH_RESULT ' + JSON). Errors: window.__benchError.
 */
import type { PerspectiveCamera, WebGLRenderer } from 'three';
import type { SagradaScene } from '../scene/SagradaScene';
import type { RenderPipeline } from '../scene/RenderPipeline';
import type { PlayerController } from '../controls/PlayerController';
import { teleportRuntime } from '../data/layout';
import { TELEPORT_PRESETS } from '../data/teleports';
import { getQuality, benchTierFromUrl } from '../utils/quality';
import { frameHooks } from './hooks';

const DEFAULT_VIEWS = [
  'placa-gaudi',
  'main-nave',
  'crossing-altar',
  'crypt-gaudi',
  'gallery-east',
  'cloister-east',
  'passion-facade',
  'glory-facade',
  'spiral-stair',
  'tower-bridge',
  'jesus-viewpoint',
  'aerial-overview',
];

const FIXED_DT = 1 / 60; // simulated frame time so time-based effects repeat between runs
const DRAIN_MAX_FRAMES = 600; // max frames to wait for GPU timer results after a view

interface Stats {
  median: number;
  p95: number;
  max: number;
  n: number;
}

interface Sample {
  cpu: number;
  gpu: number | null;
  calls: number;
  tris: number;
}

interface ViewResult {
  id: string;
  position?: number[];
  lookAt?: number[];
  error?: string;
  frames: number;
  calls: number | null;
  triangles: number | null;
  cpuMs: Stats | null;
  gpuMs: Stats | null;
  gpuSamples: number;
  memory: { geometries: number; textures: number } | null;
  programs: number | null;
  drawingBuffer: [number, number] | null;
  pixelRatio: number | null;
}

/** Captured at boot so console errors during the whole bench are reported. */
const consoleErrors: string[] = [];
let consoleErrorCount = 0;
let bootDone = false;

function pushConsoleError(text: string): void {
  consoleErrorCount++;
  if (consoleErrors.length < 20) consoleErrors.push(text.slice(0, 400));
}

/** Call first thing in bootstrap (bench mode only). */
export function benchBoot(): void {
  if (bootDone) return;
  bootDone = true;
  try {
    performance.setResourceTimingBufferSize(2000);
  } catch {
    // Ignore: resource totals may then be partial
  }
  const origError = console.error.bind(console);
  console.error = (...args: unknown[]) => {
    pushConsoleError(args.map((a) => (a instanceof Error ? a.message : String(a))).join(' '));
    origError(...args);
  };
  window.addEventListener('error', (e) => pushConsoleError(`uncaught: ${e.message}`));
  window.addEventListener('unhandledrejection', (e) => pushConsoleError(`unhandled: ${String(e.reason)}`));
}

export interface BenchDeps {
  renderer: WebGLRenderer;
  camera: PerspectiveCamera;
  sagrada: SagradaScene;
  player: PlayerController;
  post: RenderPipeline;
  /** Same state change as the start gate, minus pointer lock and audio. */
  onReady: () => void;
}

interface TimerExt {
  TIME_ELAPSED_EXT: number;
  GPU_DISJOINT_EXT: number;
}

function intParam(params: URLSearchParams, name: string, fallback: number): number {
  const v = params.get(name);
  if (v === null || v === '') return fallback;
  const n = Math.floor(Number(v));
  if (!Number.isFinite(n) || n < 0) throw new Error(`bench: invalid ${name}=${v}`);
  return n;
}

function summarize(values: number[]): Stats | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const n = sorted.length;
  const at = (q: number) => sorted[Math.min(n - 1, Math.ceil(q * n) - 1)];
  const r = (x: number) => Math.round(x * 1000) / 1000;
  return { median: r(at(0.5)), p95: r(at(0.95)), max: r(sorted[n - 1]), n };
}

function medianOf(values: number[]): number | null {
  return summarize(values)?.median ?? null;
}

/** Starts the bench once the scene is fully loaded. Runs entirely from the frame hooks. */
export function startBench(deps: BenchDeps): void {
  const { renderer, camera, sagrada, player, post } = deps;
  const startedAt = performance.now();
  try {
    const params = new URLSearchParams(window.location.search);
    const views = (params.get('views') ?? '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    const viewIds = views.length > 0 ? views : DEFAULT_VIEWS;
    const frames = intParam(params, 'frames', 240);
    const warmup = intParam(params, 'warmup', 60);
    const w = intParam(params, 'w', 0);
    const h = intParam(params, 'h', 0);
    if (frames < 1) throw new Error('bench: frames must be >= 1');

    const gl = renderer.getContext() as WebGL2RenderingContext;
    const timer = gl.getExtension('EXT_disjoint_timer_query_webgl2') as TimerExt | null;
    const dbg = gl.getExtension('WEBGL_debug_renderer_info');
    const gpuRenderer = String(gl.getParameter(dbg ? dbg.UNMASKED_RENDERER_WEBGL : gl.RENDERER));
    const gpuVendor = String(gl.getParameter(dbg ? dbg.UNMASKED_VENDOR_WEBGL : gl.VENDOR));

    // Per-frame totals: we reset the counters ourselves so multi-pass frames (composer, reflector,
    // shadow) are summed, not just the last render() call.
    renderer.info.autoReset = false;
    post.drsEnabled = false; // keep resolution fixed for repeatability
    sagrada.lighting.setTimeOfDay(9.5);
    post.setNightBloomFactor(sagrada.lighting.nightFactor);
    sagrada.weather.setMode('clear');
    if (w > 0 && h > 0) {
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      post.setSize(w, h);
    }
    deps.onReady();
    frameHooks.fixedDt = FIXED_DT;

    let firstFrameMarked = false;
    const results: ViewResult[] = [];

    type Phase = 'warmup' | 'measure' | 'drain';
    let vi = -1;
    let phase: Phase = 'warmup';
    let count = 0;
    let samples: Sample[] = [];
    let view: { id: string; error?: string; position?: number[]; lookAt?: number[] } = { id: '' };
    let query: WebGLQuery | null = null;
    let frameT0 = 0;
    let pending: Array<{ q: WebGLQuery; sample: Sample }> = [];
    let memory: ViewResult['memory'] = null;
    let programs: number | null = null;
    let drawingBuffer: [number, number] | null = null;
    let pixelRatio: number | null = null;
    let finished = false;

    const resolveTimers = (): void => {
      if (!timer || pending.length === 0) return;
      const disjoint = Boolean(gl.getParameter(timer.GPU_DISJOINT_EXT));
      const still: typeof pending = [];
      for (const p of pending) {
        if (gl.getQueryParameter(p.q, gl.QUERY_RESULT_AVAILABLE)) {
          const ns = Number(gl.getQueryParameter(p.q, gl.QUERY_RESULT));
          p.sample.gpu = disjoint ? null : ns / 1e6;
          gl.deleteQuery(p.q);
        } else {
          still.push(p);
        }
      }
      pending = still;
    };

    const finishView = (): void => {
      resolveTimers();
      for (const p of pending) {
        gl.deleteQuery(p.q);
      }
      pending = [];
      const gpuValues = samples.map((s) => s.gpu).filter((g): g is number => g !== null);
      results.push({
        id: view.id,
        position: view.position,
        lookAt: view.lookAt,
        error: view.error,
        frames: samples.length,
        calls: medianOf(samples.map((s) => s.calls)),
        triangles: medianOf(samples.map((s) => s.tris)),
        cpuMs: summarize(samples.map((s) => s.cpu)),
        gpuMs: summarize(gpuValues),
        gpuSamples: gpuValues.length,
        memory,
        programs,
        drawingBuffer,
        pixelRatio,
      });
      samples = [];
    };

    const beginView = (): void => {
      vi++;
      const id = viewIds[vi];
      view = { id };
      samples = [];
      phase = 'warmup';
      count = 0;
      try {
        const rt = teleportRuntime(id);
        const preset = TELEPORT_PRESETS.find((p) => p.id === id);
        view.position = rt.position;
        view.lookAt = rt.lookAt;
        // Same path as the HUD teleport buttons, but instant; the player stands still (no input).
        player.teleportTo({ position: rt.position, lookAt: rt.lookAt, flyMode: preset?.flyMode ?? false }, true);
      } catch (err) {
        view.error = err instanceof Error ? err.message : String(err);
      }
    };

    const finalize = (): void => {
      finished = true;
      const nav = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined;
      const markTime = (name: string): number | null => {
        const m = performance.getEntriesByName(name, 'mark')[0];
        return m ? Math.round(m.startTime) : null;
      };
      const resources = performance.getEntriesByType('resource') as PerformanceResourceTiming[];
      const sum = (f: (r: PerformanceResourceTiming) => number) => resources.reduce((a, r) => a + f(r), 0);
      const quality = getQuality();
      const result = {
        schema: 'sagrada-bench/1',
        finishedAt: new Date().toISOString(),
        userAgent: navigator.userAgent,
        gpu: { renderer: gpuRenderer, vendor: gpuVendor, webgl: String(gl.getParameter(gl.VERSION)) },
        gpuTimerSupported: timer !== null,
        params: {
          tier: quality.tier,
          requestedTier: benchTierFromUrl(),
          views: viewIds,
          frames,
          warmup,
          canvasSize: w > 0 && h > 0 ? [w, h] : null,
          viewport: [window.innerWidth, window.innerHeight],
          devicePixelRatio: window.devicePixelRatio,
          fixedDt: FIXED_DT,
        },
        startup: {
          domContentLoadedMs: nav ? Math.round(nav.domContentLoadedEventEnd) : null,
          glbLoadedMs: markTime('sagrada:glb-loaded'),
          assetsReadyMs: markTime('sagrada:assets-ready'),
          firstFrameMs: markTime('sagrada:first-frame'),
        },
        transfer: {
          transferBytes: sum((r) => r.transferSize),
          encodedBodyBytes: sum((r) => r.encodedBodySize),
          decodedBodyBytes: sum((r) => r.decodedBodySize),
          resources: resources.length,
        },
        views: results,
        consoleErrors: { count: consoleErrorCount, first: consoleErrors },
        benchDurationMs: Math.round(performance.now() - startedAt),
      };
      (window as unknown as Record<string, unknown>).__benchResult = result;
      console.log('BENCH_RESULT ' + JSON.stringify(result));
      frameHooks.beforeFrame = undefined;
      frameHooks.afterFrame = undefined;
      frameHooks.fixedDt = undefined;
    };

    frameHooks.beforeFrame = () => {
      if (finished) return;
      frameT0 = performance.now();
      renderer.info.reset();
      if (phase === 'measure' && timer) {
        query = gl.createQuery();
        if (query) gl.beginQuery(timer.TIME_ELAPSED_EXT, query);
      }
    };

    frameHooks.afterFrame = () => {
      if (finished) return;
      const cpu = performance.now() - frameT0;
      if (!firstFrameMarked) {
        firstFrameMarked = true;
        performance.mark('sagrada:first-frame');
      }
      if (phase === 'warmup') {
        // Unmeasured frames; the measured frames start on the next frame
        if (++count >= warmup) {
          phase = 'measure';
          count = 0;
        }
        return;
      }
      if (phase === 'measure') {
        const sample: Sample = {
          cpu,
          gpu: null,
          calls: renderer.info.render.calls,
          tris: renderer.info.render.triangles,
        };
        if (query) {
          gl.endQuery(timer!.TIME_ELAPSED_EXT);
          pending.push({ q: query, sample });
          query = null;
        }
        samples.push(sample);
        count++;
        if (count >= frames) {
          phase = 'drain';
          count = 0;
          memory = {
            geometries: renderer.info.memory.geometries,
            textures: renderer.info.memory.textures,
          };
          programs = renderer.info.programs?.length ?? null;
          drawingBuffer = [gl.drawingBufferWidth, gl.drawingBufferHeight];
          pixelRatio = renderer.getPixelRatio();
        }
        return;
      }
      // drain: let the GPU timer results land, then move on
      resolveTimers();
      count++;
      if (pending.length === 0 || count >= DRAIN_MAX_FRAMES) {
        finishView(); // also deletes any timer queries still unresolved (their GPU time stays null)
        if (vi + 1 < viewIds.length) {
          beginView();
        } else {
          finalize();
        }
      }
    };

    beginView();
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    (window as unknown as Record<string, unknown>).__benchError = message;
    console.error('[bench]', message);
  }
}
