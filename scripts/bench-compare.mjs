// Compares two bench result files (from scripts/bench.mjs, single-run or multi-run format).
//
// Usage: node scripts/bench-compare.mjs <before.json> <after.json>
//
// Per view: draw calls, triangles, CPU median and GPU median, before -> after and % change.
// Startup marks and transferred bytes are listed after the views.
// A CPU/GPU/startup change smaller than the run-to-run spread (max-min across the runs of either
// file) is marked "within noise". Only applied when both files contain more than one run.

import { readFileSync } from 'node:fs';

function load(path) {
  const data = JSON.parse(readFileSync(path, 'utf8'));
  // Multi-run files keep every run in `runs`; single-run files (sagrada-bench/1) are one run
  const runs = Array.isArray(data.runs) ? data.runs : [data];
  return { path, data, runs };
}

function median(values) {
  const v = values.filter((x) => typeof x === 'number' && Number.isFinite(x)).sort((a, b) => a - b);
  if (v.length === 0) return null;
  const mid = Math.floor(v.length / 2);
  return v.length % 2 ? v[mid] : (v[mid - 1] + v[mid]) / 2;
}

/** Summary of one metric over runs: central value (median), spread (max - min) and sample count. */
function summary(values) {
  const v = values.filter((x) => typeof x === 'number' && Number.isFinite(x));
  if (v.length === 0) return null;
  return { value: median(v), spread: Math.max(...v) - Math.min(...v), n: v.length };
}

function viewMetrics(file) {
  const ids = file.runs[0].views.map((v) => v.id);
  const byId = {};
  for (const id of ids) {
    const per = file.runs.map((r) => r.views.find((v) => v.id === id)).filter(Boolean);
    byId[id] = {
      error: per.some((v) => v.error),
      calls: summary(per.map((v) => v.calls)),
      triangles: summary(per.map((v) => v.triangles)),
      cpu: summary(per.map((v) => v.cpuMs?.median ?? null)),
      gpu: summary(per.map((v) => v.gpuMs?.median ?? null)),
    };
  }
  return byId;
}

function startupMetrics(file) {
  const marks = {
    'domContentLoaded ms': (r) => r.startup.domContentLoadedMs,
    'glb-loaded ms': (r) => r.startup.glbLoadedMs,
    'assets-ready ms': (r) => r.startup.assetsReadyMs,
    'first-frame ms': (r) => r.startup.firstFrameMs,
    'transfer bytes': (r) => r.transfer.transferBytes,
  };
  const out = {};
  for (const [name, get] of Object.entries(marks)) out[name] = summary(file.runs.map(get));
  return out;
}

const fmt = (x, digits = 2) => (x === null || x === undefined ? 'n/a' : x.toFixed(digits));
const pct = (b, a) => (b === 0 || b === null || a === null ? 'n/a' : `${((a - b) / b * 100).toFixed(1)}%`);

/** Cell for a timed metric: "b -> a (+x.x%)", plus "within noise" when the change is inside the spread. */
function timedCell(b, a, multiRun) {
  if (!b || !a) return 'n/a';
  const base = `${fmt(b.value)} -> ${fmt(a.value)} (${pct(b.value, a.value)})`;
  if (!multiRun) return base;
  const spread = Math.max(b.spread, a.spread);
  const delta = Math.abs(a.value - b.value);
  return delta < spread ? `${base} within noise` : base;
}

/** Cell for a deterministic count (calls, triangles, bytes): no noise flag. */
function exactCell(b, a) {
  if (!b || !a) return 'n/a';
  return `${fmt(b.value, 0)} -> ${fmt(a.value, 0)} (${pct(b.value, a.value)})`;
}

function printTable(header, rows) {
  const all = [header, ...rows];
  const widths = header.map((_, c) => Math.max(...all.map((r) => String(r[c]).length)));
  for (const r of all) console.log(r.map((x, c) => String(x).padEnd(widths[c])).join('  '));
}

const [beforePath, afterPath] = process.argv.slice(2);
if (!beforePath || !afterPath) {
  console.error('usage: node scripts/bench-compare.mjs <before.json> <after.json>');
  process.exit(1);
}
const before = load(beforePath);
const after = load(afterPath);
const multiRun = before.runs.length > 1 && after.runs.length > 1;

const describe = (f) =>
  `${f.path}\n  runs: ${f.runs.length} | tier ${f.data.params?.tier ?? f.runs[0].params.tier} | ` +
  `${f.data.params?.canvasSize?.join('x') ?? f.runs[0].params.canvasSize?.join('x') ?? 'n/a'} | ` +
  `GPU ${f.data.gpu?.renderer ?? f.runs[0].gpu.renderer}`;
console.log(`before: ${describe(before)}`);
console.log(`after:  ${describe(after)}`);
const pb = before.runs[0].params;
const pa = after.runs[0].params;
if (pb.tier !== pa.tier || JSON.stringify(pb.canvasSize) !== JSON.stringify(pa.canvasSize) || pb.frames !== pa.frames) {
  console.log('WARNING: tier, canvas size or frame count differ between the files');
}
if (!multiRun) {
  console.log('NOTE: fewer than two runs in one file, so no run-to-run noise check (use --runs 3 or more)');
}
console.log('');

const vb = viewMetrics(before);
const va = viewMetrics(after);
const viewIds = Object.keys(vb).filter((id) => id in va);
const onlyIn = [...Object.keys(vb).filter((id) => !(id in va)), ...Object.keys(va).filter((id) => !(id in vb))];
const rows = viewIds.map((id) => {
  const b = vb[id];
  const a = va[id];
  return [
    id + (b.error || a.error ? ' (ERROR)' : ''),
    exactCell(b.calls, a.calls),
    exactCell(b.triangles, a.triangles),
    timedCell(b.cpu, a.cpu, multiRun),
    timedCell(b.gpu, a.gpu, multiRun),
  ];
});
printTable(['view', 'calls', 'triangles', 'CPU med ms', 'GPU med ms'], rows);
if (onlyIn.length > 0) console.log(`\nViews in only one file (skipped): ${onlyIn.join(', ')}`);

console.log('');
const sb = startupMetrics(before);
const sa = startupMetrics(after);
const startupRows = Object.keys(sb).map((name) => {
  const b = sb[name];
  const a = sa[name];
  const isBytes = name === 'transfer bytes';
  const cell = isBytes ? exactCell(b, a) : timedCell(b, a, multiRun);
  return [name, cell];
});
printTable(['startup / transfer', 'before -> after (% change)'], startupRows);

if (multiRun) {
  console.log('\nCPU, GPU and startup changes smaller than the run-to-run spread are "within noise". Calls, triangles and bytes are exact.');
}
