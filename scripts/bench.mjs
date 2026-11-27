// Runs the in-app benchmark (src/perf/bench.ts) in the installed Microsoft Edge with the NVIDIA GPU.
//
// Usage:
//   node scripts/bench.mjs --url http://127.0.0.1:5183/ --tier ultra --views main-nave,crypt-gaudi \
//     --w 1920 --h 1080 --out <file.json> [--frames 240] [--warmup 60] [--timeout 180]
//     [--runs 3] [--seed 1] [--shots <dir>]
// Defaults: tier ultra, all views, 1920x1080, url http://127.0.0.1:5173/, runs 1, seed 1.
//
// --runs N     launches a fresh browser N times. The output JSON keeps every run (`runs`) and an
//              `aggregate`: per view and per startup mark, median/min/max over the runs. CPU and GPU
//              values are the per-run medians, aggregated the same way. The stdout table shows the aggregate.
// --shots DIR  saves a PNG of the canvas after each measured view as <tier>_<w>x<h>_<view>.png
//              (with several runs the same name is written again by each run; the last run wins).

import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve, join } from 'node:path';
import puppeteer from 'puppeteer-core';

const EDGE_PATH = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';

function parseArgs(argv) {
  const opts = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--')) throw new Error(`unexpected argument: ${a}`);
    const key = a.slice(2);
    const value = argv[i + 1];
    if (value === undefined || value.startsWith('--')) throw new Error(`missing value for --${key}`);
    opts[key] = value;
    i++;
  }
  return opts;
}

function fail(message) {
  throw new Error(message);
}

/** Median of the non-null numbers, with min, max and count; null when there are none. */
function stat(values) {
  const v = values.filter((x) => typeof x === 'number' && Number.isFinite(x)).sort((a, b) => a - b);
  if (v.length === 0) return null;
  const mid = Math.floor(v.length / 2);
  const median = v.length % 2 ? v[mid] : (v[mid - 1] + v[mid]) / 2;
  const r = (x) => Math.round(x * 1000) / 1000;
  return { median: r(median), min: r(v[0]), max: r(v[v.length - 1]), n: v.length };
}

function aggregate(runs) {
  const startupKeys = ['domContentLoadedMs', 'glbLoadedMs', 'assetsReadyMs', 'firstFrameMs'];
  const transferKeys = ['transferBytes', 'encodedBodyBytes', 'decodedBodyBytes', 'resources'];
  const startup = {};
  for (const k of startupKeys) startup[k] = stat(runs.map((r) => r.startup[k]));
  const transfer = {};
  for (const k of transferKeys) transfer[k] = stat(runs.map((r) => r.transfer[k]));

  const ids = runs[0].views.map((v) => v.id);
  const views = ids.map((id) => {
    const per = runs.map((r) => r.views.find((v) => v.id === id)).filter(Boolean);
    const errors = per.map((v) => v.error).filter(Boolean);
    return {
      id,
      error: errors.length > 0 ? errors[0] : undefined,
      calls: stat(per.map((v) => v.calls)),
      triangles: stat(per.map((v) => v.triangles)),
      cpuMedianMs: stat(per.map((v) => v.cpuMs?.median ?? null)),
      gpuMedianMs: stat(per.map((v) => v.gpuMs?.median ?? null)),
      gpuSamples: stat(per.map((v) => v.gpuSamples)),
    };
  });
  return { startup, transfer, views };
}

const opts = parseArgs(process.argv.slice(2));
const url = opts.url ?? 'http://127.0.0.1:5173/';
const tier = opts.tier ?? 'ultra';
const w = Number(opts.w ?? 1920);
const h = Number(opts.h ?? 1080);
const timeoutMs = Number(opts.timeout ?? 180) * 1000;
const runCount = Number(opts.runs ?? 1);
if (!['low', 'medium', 'high', 'ultra'].includes(tier)) fail(`unknown tier ${tier}`);
if (!Number.isInteger(runCount) || runCount < 1) fail(`--runs must be a positive integer, got ${opts.runs}`);
const shotsDir = opts.shots ? resolve(opts.shots) : null;
if (shotsDir) mkdirSync(shotsDir, { recursive: true });

function buildTarget() {
  const params = new URLSearchParams({ bench: '', tier, w: String(w), h: String(h) });
  if (opts.views) params.set('views', opts.views);
  if (opts.frames) params.set('frames', opts.frames);
  if (opts.warmup) params.set('warmup', opts.warmup);
  if (opts.seed) params.set('seed', opts.seed);
  if (shotsDir) params.set('hold', '1');
  const target = new URL(url);
  target.search = params.toString();
  return target.toString();
}

/** One fresh browser, one full bench pass. Returns the in-page result object. */
async function runOnce(index) {
  const browser = await puppeteer.launch({
    executablePath: EDGE_PATH,
    headless: true,
    defaultViewport: { width: w, height: h, deviceScaleFactor: 1 },
    args: [
      '--headless=new',
      '--use-angle=d3d11',
      '--enable-gpu',
      '--ignore-gpu-blocklist',
      '--enable-webgl',
      '--no-first-run',
      '--no-default-browser-check',
      '--disable-background-timer-throttling',
      '--disable-renderer-backgrounding',
      '--disable-backgrounding-occluded-windows',
    ],
  });
  try {
    const page = await browser.newPage();
    page.on('console', (msg) => {
      if (msg.type() === 'error' || msg.type() === 'warning') {
        console.error(`[run ${index} page ${msg.type()}] ${msg.text()}`);
      }
    });
    page.on('response', (res) => {
      if (res.status() >= 400) console.error(`[run ${index} page http ${res.status()}] ${res.url()}`);
    });
    page.on('pageerror', (err) => console.error(`[run ${index} page exception] ${err.message}`));
    await page.goto(buildTarget(), { waitUntil: 'load', timeout: timeoutMs });

    const finishedExpr = 'window.__benchResult !== undefined || window.__benchError !== undefined';
    if (shotsDir) {
      // The page holds after each view (hold=1): save the canvas, then let it continue
      while (true) {
        await page.waitForFunction(`window.__benchPaused || ${finishedExpr}`, { timeout: timeoutMs, polling: 200 });
        const state = await page.evaluate(() => ({
          paused: window.__benchPaused ?? null,
          finished: window.__benchResult !== undefined || window.__benchError !== undefined,
        }));
        if (state.paused) {
          const canvas = await page.$('#scene-canvas');
          if (!canvas) fail('no #scene-canvas to screenshot');
          const file = join(shotsDir, `${tier}_${w}x${h}_${state.paused}.png`);
          await canvas.screenshot({ path: file });
          console.log(`Screenshot ${file}`);
          await page.evaluate(() => {
            window.__benchResume = true;
          });
          await page.waitForFunction('!window.__benchPaused', { timeout: timeoutMs, polling: 100 });
          continue;
        }
        if (state.finished) break;
      }
    } else {
      await page.waitForFunction(finishedExpr, { timeout: timeoutMs, polling: 500 });
    }

    const outcome = await page.evaluate(() => ({
      result: window.__benchResult ?? null,
      error: window.__benchError ?? null,
    }));
    if (outcome.error) fail(outcome.error);
    const result = outcome.result;

    const renderer = String(result.gpu.renderer ?? '');
    if (!/nvidia|geforce|rtx|gtx/i.test(renderer) || /swiftshader|llvmpipe|software|basic render/i.test(renderer)) {
      fail(`GPU is not the NVIDIA hardware GPU: "${renderer}"`);
    }
    if (result.params.tier !== tier) fail(`tier mismatch: page ran ${result.params.tier}, expected ${tier}`);
    return result;
  } finally {
    await browser.close();
  }
}

let exitCode = 0;
// Hard stop if anything hangs (page or browser close) so a run never sits silently
setTimeout(() => {
  console.error(`BENCH FAILED: watchdog after ${timeoutMs * runCount + 60000} ms`);
  process.exit(2);
}, timeoutMs * runCount + 60000).unref();
try {
  const runs = [];
  for (let i = 1; i <= runCount; i++) {
    if (runCount > 1) console.log(`Run ${i}/${runCount} ...`);
    runs.push(await runOnce(i));
  }
  const first = runs[0];
  const agg = aggregate(runs);
  const output = {
    schema: 'sagrada-bench-runs/1',
    runCount,
    url,
    seed: Number(opts.seed ?? 1),
    gpu: first.gpu,
    gpuTimerSupported: first.gpuTimerSupported,
    params: first.params,
    aggregate: agg,
    runs,
  };

  if (opts.out) {
    const outPath = resolve(opts.out);
    mkdirSync(dirname(outPath), { recursive: true });
    writeFileSync(outPath, JSON.stringify(output, null, 2));
    console.log(`Wrote ${outPath}`);
  }

  const renderer = String(first.gpu.renderer ?? '');
  const med = (s) => (s ? s.median.toFixed(2) : 'n/a');
  const range = (s) => (s ? `${s.min.toFixed(2)}..${s.max.toFixed(2)}` : 'n/a');
  console.log(
    `GPU: ${renderer} | tier=${first.params.tier} | ${w}x${h} | GPU timer: ${first.gpuTimerSupported ? 'yes' : 'NO'} | runs: ${runCount}`
  );
  console.log(
    `Startup (median, range over runs): glb-loaded ${med(agg.startup.glbLoadedMs)} [${range(agg.startup.glbLoadedMs)}] ms, ` +
      `assets-ready ${med(agg.startup.assetsReadyMs)} [${range(agg.startup.assetsReadyMs)}] ms, ` +
      `first-frame ${med(agg.startup.firstFrameMs)} [${range(agg.startup.firstFrameMs)}] ms`
  );
  console.log(
    `Transfer (median): ${agg.transfer.transferBytes?.median ?? 'n/a'} bytes [${range(agg.transfer.transferBytes)}] (${agg.transfer.resources?.median ?? 'n/a'} resources)`
  );
  console.log('');
  const header = ['view', 'calls', 'tris', 'cpu med', 'cpu range', 'gpu med', 'gpu range', 'runs'];
  const rows = agg.views.map((v) => [
    v.id + (v.error ? ' (ERROR)' : ''),
    v.calls?.median ?? 'n/a',
    v.triangles?.median ?? 'n/a',
    med(v.cpuMedianMs),
    range(v.cpuMedianMs),
    med(v.gpuMedianMs),
    range(v.gpuMedianMs),
    v.gpuMedianMs?.n ?? 0,
  ]);
  const all = [header, ...rows];
  const widths = header.map((_, c) => Math.max(...all.map((r) => String(r[c]).length)));
  for (const r of all) console.log(r.map((x, c) => String(x).padEnd(widths[c])).join('  '));
  const consoleCount = runs.reduce((a, r) => a + r.consoleErrors.count, 0);
  if (consoleCount > 0) {
    console.log(`\nConsole errors during bench (all runs): ${consoleCount}`);
    for (const e of runs[0].consoleErrors.first.slice(0, 5)) console.log(`  - ${e}`);
  }
} catch (err) {
  console.error(`BENCH FAILED: ${err.message}`);
  exitCode = 1;
}
process.exit(exitCode);
