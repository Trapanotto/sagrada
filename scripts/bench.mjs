// Runs the in-app benchmark (src/perf/bench.ts) in the installed Microsoft Edge with the NVIDIA GPU.
//
// Usage:
//   node scripts/bench.mjs --url http://127.0.0.1:5183/ --tier ultra --views main-nave,crypt-gaudi \
//     --w 1920 --h 1080 --out <file.json> [--frames 240] [--warmup 60] [--timeout 180]
// Defaults: tier ultra, all views, 1920x1080, url http://127.0.0.1:5173/.

import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
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

const opts = parseArgs(process.argv.slice(2));
const url = opts.url ?? 'http://127.0.0.1:5173/';
const tier = opts.tier ?? 'ultra';
const w = Number(opts.w ?? 1920);
const h = Number(opts.h ?? 1080);
const timeoutMs = Number(opts.timeout ?? 180) * 1000;
if (!['low', 'medium', 'high', 'ultra'].includes(tier)) fail(`unknown tier ${tier}`);

const params = new URLSearchParams({ bench: '', tier, w: String(w), h: String(h) });
if (opts.views) params.set('views', opts.views);
if (opts.frames) params.set('frames', opts.frames);
if (opts.warmup) params.set('warmup', opts.warmup);
const target = new URL(url);
target.search = params.toString();

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

let exitCode = 0;
// Hard stop if anything hangs (page or browser close) so a run never sits silently
setTimeout(() => {
  console.error(`BENCH FAILED: watchdog after ${timeoutMs + 60000} ms`);
  process.exit(2);
}, timeoutMs + 60000).unref();
try {
  const page = await browser.newPage();
  page.on('console', (msg) => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      console.error(`[page ${msg.type()}] ${msg.text()}`);
    }
  });
  page.on('response', (res) => {
    if (res.status() >= 400) console.error(`[page http ${res.status()}] ${res.url()}`);
  });
  page.on('pageerror', (err) => console.error(`[page exception] ${err.message}`));
  await page.goto(target.toString(), { waitUntil: 'load', timeout: timeoutMs });

  await page.waitForFunction('window.__benchResult !== undefined || window.__benchError !== undefined', {
    timeout: timeoutMs,
    polling: 500,
  });
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

  if (opts.out) {
    const outPath = resolve(opts.out);
    mkdirSync(dirname(outPath), { recursive: true });
    writeFileSync(outPath, JSON.stringify(result, null, 2));
    console.log(`Wrote ${outPath}`);
  }

  const fmt = (s, k) => (s ? s[k].toFixed(2) : 'n/a');
  console.log(`GPU: ${renderer} | tier=${result.params.tier} | ${w}x${h} | GPU timer: ${result.gpuTimerSupported ? 'yes' : 'NO'}`);
  console.log(
    `Startup: glb-loaded ${result.startup.glbLoadedMs} ms, assets-ready ${result.startup.assetsReadyMs} ms, first-frame ${result.startup.firstFrameMs} ms`
  );
  console.log(
    `Transfer: ${result.transfer.transferBytes} bytes (${result.transfer.resources} resources)`
  );
  console.log('');
  const header = ['view', 'calls', 'tris', 'cpu med', 'cpu p95', 'gpu med', 'gpu p95', 'gpu n'];
  const rows = result.views.map((v) => [
    v.id + (v.error ? ' (ERROR)' : ''),
    v.calls ?? 'n/a',
    v.triangles ?? 'n/a',
    fmt(v.cpuMs, 'median'),
    fmt(v.cpuMs, 'p95'),
    fmt(v.gpuMs, 'median'),
    fmt(v.gpuMs, 'p95'),
    v.gpuSamples,
  ]);
  const all = [header, ...rows];
  const widths = header.map((_, c) => Math.max(...all.map((r) => String(r[c]).length)));
  for (const r of all) console.log(r.map((x, c) => String(x).padEnd(widths[c])).join('  '));
  if (result.consoleErrors.count > 0) {
    console.log(`\nConsole errors during bench: ${result.consoleErrors.count}`);
    for (const e of result.consoleErrors.first.slice(0, 5)) console.log(`  - ${e}`);
  }
} catch (err) {
  console.error(`BENCH FAILED: ${err.message}`);
  exitCode = 1;
} finally {
  await browser.close();
}
process.exit(exitCode);
