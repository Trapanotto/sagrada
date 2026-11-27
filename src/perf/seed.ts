/**
 * Bench mode only: replaces Math.random with a seeded mulberry32 generator so particles, birds and
 * rain are placed identically on every run. Installed from benchBoot(), which runs before the scene
 * is constructed (the scene modules only call Math.random inside constructors and functions).
 *
 * URL parameter: seed=<integer> (default 1).
 */
export function installBenchSeed(): number {
  const raw = new URLSearchParams(window.location.search).get('seed');
  const parsed = raw === null || raw === '' ? 1 : Math.floor(Number(raw));
  const seed = Number.isFinite(parsed) ? parsed >>> 0 : 1;
  let state = seed;
  Math.random = (): number => {
    // mulberry32
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return seed;
}
