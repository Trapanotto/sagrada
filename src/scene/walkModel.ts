/**
 * Analytic walk model: every floor, stair, deck, bridge and zone the runtime knows without the BVH.
 *
 * Pure functions on numbers only (no three.js, no DOM, no i18n runtime), so the floor logic can be
 * checked headlessly against the layout contracts. CollisionSystem wraps these with the 3D capsule
 * solver and translation. Every position comes from ../data/layout (blender/layout.py), never re-typed.
 *
 * Coordinates: runtime world (x, y up, z) with z = -plan y. `feetY` = eye height - EYE_HEIGHT.
 */
import {
  LAYOUT,
  cornerBuildingRect,
  groundZ,
  inCryptFootprint,
  inCryptWalkArea,
  inRect,
  inRoundedRect,
  interiorColumnsRuntime,
  outdoorGroundZ,
  planRectToWorld,
  towerByKey,
  towerRadiusAt,
  towerStairShaftsRuntime,
  walkBridgesRuntime,
  type Rect,
  type RuntimeWalkBridge,
} from '../data/layout';
import type { MessageKey } from '../i18n/de';

const LV = LAYOUT.levels;
const TAU = Math.PI * 2;

export const EYE_HEIGHT = LV.eye;
/** Max vertical step-up onto stairs / ramps / platforms. */
export const STEP_UP_MAX = 1.45;
export const Z_NAVE = LV.nave;
export const Z_CRYPT = LV.crypt;
/** Feet below this AND inside the crypt walk area = crypt level (handover §4.6: Z_NAVE - 3). */
export const UNDERGROUND_FEET_Y = Z_NAVE - 3;
/**
 * Rise below a spiral's top that stays open in the top landing / deck: the treads are the floor there and
 * it is the way back down; elsewhere the landing disc is floor. Must exceed the 1.55 m step-down window of
 * spiralTreadY (so nobody standing on the landing is pulled onto a tread) and the 1.5 m landing trigger
 * (so nobody climbing is popped up). Runtime-local rule, see the phase-2 report.
 */
export const STAIR_TOP_OPENING = 1.6;
/** Apostle landings as built by the towers package: a 100 deg opening over the last part of the stair. */
const APOSTLE_TOP_OPENING_DEG = 100;
/** Jesus 136 deck as built: open over the last 3.2 m of the stair. */
const JESUS_TOP_OPENING = 3.2;
/** Shell wall thickness at the stair tops (towers package: outer apostle shells are ~1.97-2.01 inside at z1). */
const TOWER_SHELL_WALL = 0.3;

// Runtime-local tuning that is not a plan dimension (kept from the previous runtime):
// Pond as built by the city package: the layout pond rectangle is the coping centreline, coping 0.9 m wide,
// floor 0.6 m below the water.
const POND_COPING_WIDTH = 0.9;
const POND_WADE_DEPTH = 0.6; // walkable pond bottom below the water surface
const FOUNTAIN_BASIN_ABOVE_WATER = 0.19;
const JESUS_DECK_R = 6.5; // 136 m viewing deck
const MARY_DECK_R = 3.75; // 118 m deck
const MARY_ENTRY_RING: [number, number] = [1.7, 4.1]; // 77 m entry ring
const EVANGELIST_DECK_R = 2.75; // 114 m decks
const JESUS_RING_56: [number, number] = [1.9, 7.8]; // crossing-vault gallery ring (contract §5)
const ELEVATOR_R = 2.02;
const BAPTISTERY_DAIS: Array<[number, number]> = [
  [1.95, 0.44],
  [2.55, 0.22],
]; // [radius, height above Z_NAVE]

export function clamp(v: number, lo: number, hi: number): number {
  return v < lo ? lo : v > hi ? hi : v;
}
export function smoothstep(x: number, lo: number, hi: number): number {
  if (x <= lo) return 0;
  if (x >= hi) return 1;
  const t = (x - lo) / (hi - lo);
  return t * t * (3 - 2 * t);
}
function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

// ─────────────────────────────── underground ───────────────────────────────

/** Feet in the crypt (footprint + its two spiral stairs) and below the nave: never a height test alone. */
export function isFeetUnderground(x: number, feetY: number, z: number): boolean {
  return feetY < UNDERGROUND_FEET_Y && inCryptWalkArea(x, -z);
}
/** Same test for a camera / eye position. */
export function isEyeUnderground(x: number, eyeY: number, z: number): boolean {
  return isFeetUnderground(x, eyeY - EYE_HEIGHT, z);
}
/** Camera at crypt level or on the crypt stairs (crypt candle light range; was "y < 2.2"). */
export function isNearCryptLevel(x: number, eyeY: number, z: number): boolean {
  return eyeY < Z_NAVE + 1.0 && inCryptWalkArea(x, -z);
}

// ─────────────────────────────── spiral stairs ───────────────────────────────

export interface SpiralStair {
  /** i18n key of the badge name (tower.* / cryptStair.*), null for the nave corner stairs. */
  key: MessageKey | null;
  cx: number;
  cz: number;
  zStart: number;
  zEnd: number;
  rInner: number;
  rOuter: number;
  /** Rise per full turn. */
  pitch: number;
  /** Angle increases with height (plan frame), same flag as add_spiral_stair_shaft(clockwise=...). */
  clockwise: boolean;
  /** Angle of the first tread at zStart, radians (plan frame, CCW from +x). */
  phase: number;
  /** A landing disc r <= landingR at zEnd (STAIR_TOP_LANDINGS) is floor outside the top opening. */
  topLanding: boolean;
  /** Landing radius: rOuter, limited to the inside of the tower shell at zEnd. */
  landingR: number;
  /** Rise below zEnd left open in the landing / deck (>= STAIR_TOP_OPENING). */
  topOpening: number;
  /** The disc r <= rOuter at zStart is floor (the stair stands on it). */
  bottomLanding: boolean;
}

const DEG = Math.PI / 180;

/** 18 tower stairs + the two crypt stairs. */
export const TOWER_SPIRALS: SpiralStair[] = towerStairShaftsRuntime().map((s) => {
  const crypt = s.towerKey.startsWith('cryptStair.');
  const tower = crypt ? null : towerByKey(s.towerKey);
  const pitch = 10 / s.turnsPer10m;
  let topOpening = STAIR_TOP_OPENING;
  if (tower?.kind === 'apostle') topOpening = Math.max(topOpening, (APOSTLE_TOP_OPENING_DEG / 360) * pitch);
  if (tower?.kind === 'jesus') topOpening = Math.max(topOpening, JESUS_TOP_OPENING);
  const landingR = tower ? Math.min(s.rOuter, towerRadiusAt(tower, s.zEnd) - TOWER_SHELL_WALL) : s.rOuter;
  return {
    landingR,
    topOpening,
    key: s.towerKey as MessageKey,
    cx: s.cx,
    cz: s.cz,
    zStart: s.zStart,
    zEnd: s.zEnd,
    rInner: s.rInner,
    rOuter: s.rOuter,
    pitch,
    clockwise: s.clockwise,
    phase: s.phaseDeg * DEG,
    // Crypt stairs end in a door (no disc over the stairwell); the crypt floor is their bottom.
    topLanding: LAYOUT.stairTopLandings && !crypt,
    bottomLanding: !crypt,
  };
});
export const CRYPT_SPIRALS = TOWER_SPIRALS.filter((s) => s.key !== null && s.key.startsWith('cryptStair.'));

/**
 * Nave -> gallery corner stairs. The layout has no `clockwise` field for them: like build_interior.py
 * (ang = phase + sx * t * turns * 2pi) the east stair turns with increasing angle, the west one mirrored.
 */
export const CORNER_SPIRALS: SpiralStair[] = LAYOUT.cornerStairs.map((c) => ({
  key: null,
  cx: c.x,
  cz: -c.y,
  zStart: c.z0,
  zEnd: c.z1,
  rInner: c.rInner,
  rOuter: c.rOuter,
  pitch: (c.z1 - c.z0) / c.turns,
  clockwise: c.x > 0,
  phase: c.phaseDeg * DEG,
  topLanding: false,
  bottomLanding: false,
  landingR: c.rOuter,
  topOpening: STAIR_TOP_OPENING,
}));
const CORNER_HOLES = LAYOUT.cornerStairs.map((c) => ({ cx: c.x, cz: -c.y, r: c.hole }));

/** Fraction of a turn [0, 1) of world point (x, z) on the helix, measured from the first tread. */
export function spiralFrac(s: SpiralStair, x: number, z: number): number {
  const ang = Math.atan2(-(z - s.cz), x - s.cx);
  const signed = s.clockwise ? ang - s.phase : s.phase - ang;
  const f = signed / TAU;
  return ((f % 1) + 1) % 1;
}

/** Plan angle (radians, CCW from +x) of the tread at height z. */
export function spiralAngleAt(s: SpiralStair, z: number): number {
  return s.phase + (s.clockwise ? 1 : -1) * TAU * ((z - s.zStart) / s.pitch);
}

/** Tread height at (x, z) nearest to feetY within the walkable step window, or null (same rule as before). */
export function spiralTreadY(s: SpiralStair, x: number, feetY: number, z: number): number | null {
  const frac = spiralFrac(s, x, z);
  const estTurn = Math.round((feetY - s.zStart) / s.pitch - frac);
  let best: number | null = null;
  let bestDiff = Infinity;
  for (let dt = -1; dt <= 1; dt++) {
    const candY = s.zStart + (estTurn + dt + frac) * s.pitch;
    if (candY < s.zStart - 0.8 || candY > s.zEnd + 0.8) continue;
    const y = clamp(candY, s.zStart, s.zEnd);
    const diff = y - feetY;
    if (diff <= STEP_UP_MAX && diff >= -1.55 && Math.abs(diff) < bestDiff) {
      bestDiff = Math.abs(diff);
      best = y;
    }
  }
  return best;
}

/** Height of the highest tread at or below zEnd at this angle. */
export function spiralLastTreadY(s: SpiralStair, x: number, z: number): number {
  const f = spiralFrac(s, x, z);
  const n = Math.floor((s.zEnd - s.zStart) / s.pitch - f + 1e-9);
  return s.zStart + (n + f) * s.pitch;
}

/** True over the last STAIR_TOP_OPENING of rise: no landing / deck there, the treads are the floor. */
export function inSpiralTopOpening(s: SpiralStair, x: number, z: number): boolean {
  return s.zEnd - spiralLastTreadY(s, x, z) < s.topOpening;
}

function inAnnulus(s: SpiralStair, d: number): boolean {
  return d >= s.rInner && d <= s.rOuter;
}

// ─────────────────────────────── decks, bridges, galleries, roofs ───────────────────────────────

const spiralByKey = (key: string) => TOWER_SPIRALS.find((s) => s.key === key) ?? null;
const JESUS = towerByKey('tower.jesus');
const MARY = towerByKey('tower.mary');
export const JESUS_XZ = { x: JESUS.x, z: -JESUS.y };
export const MARY_XZ = { x: MARY.x, z: -MARY.y };
const EVANGELISTS = LAYOUT.towers.filter((t) => t.kind === 'evangelist');

interface TopDeck {
  cx: number;
  cz: number;
  r: number;
  y: number;
  shaft: SpiralStair | null;
}
export const TOP_DECKS: TopDeck[] = [
  { cx: JESUS.x, cz: -JESUS.y, r: JESUS_DECK_R, y: LV.jesusView, shaft: spiralByKey(JESUS.key) },
  { cx: MARY.x, cz: -MARY.y, r: MARY_DECK_R, y: LV.maryDeck, shaft: spiralByKey(MARY.key) },
  ...EVANGELISTS.map((t) => ({ cx: t.x, cz: -t.y, r: EVANGELIST_DECK_R, y: LV.evangelistDeck, shaft: spiralByKey(t.key) })),
];

export const WALK_BRIDGES: RuntimeWalkBridge[] = walkBridgesRuntime();

interface FloorBox {
  minX: number;
  maxX: number;
  minZ: number;
  maxZ: number;
  y: number;
}
export const ROOF_DECKS: FloorBox[] = LAYOUT.roofDecks.map(([x0, y0, x1, y1, z]) => ({ ...planRectToWorld([x0, y0, x1, y1]), y: z }));
export const GALLERY_BOXES: FloorBox[] = Object.values(LAYOUT.galleries).map((r) => ({ ...planRectToWorld(r), y: LV.gallery }));

/** Eixample blocks: pre-BVH push-out boxes and landable roofs (roof = ground at the block's south edge + height). */
export const CITY_BLOCK_BOXES: FloorBox[] = LAYOUT.city.blocks.map((b) => ({
  ...planRectToWorld(b),
  y: groundZ(Math.min(b.y0, b.y1)) + b.height,
}));

/** Pre-BVH column push-out list [x, z, r]. */
export const INTERIOR_COLUMNS = interiorColumnsRuntime();

function inBox(b: { minX: number; maxX: number; minZ: number; maxZ: number }, x: number, z: number): boolean {
  return x >= b.minX && x <= b.maxX && z >= b.minZ && z <= b.maxZ;
}

/** How far a bridge deck reaches past its end points (the decks are rectangles, not capsules). */
const BRIDGE_END_TOLERANCE = 0.3;

/**
 * Deck height of a bridge / ramp segment at (px, pz), or null. A rectangle of half width `halfWidth`
 * along the segment, extended by BRIDGE_END_TOLERANCE at both ends; heights are clamped to the ends.
 * (A capsule test would extend the 19 m wide Glory bridge and stair by a 19 m half-disc.)
 */
export function bridgeDeckY(b: RuntimeWalkBridge, px: number, pz: number): number | null {
  const dx = b.x1 - b.x0;
  const dz = b.z1 - b.z0;
  const len = Math.hypot(dx, dz);
  if (len < 1e-6) return Math.hypot(px - b.x0, pz - b.z0) <= b.halfWidth ? b.y0 : null;
  const along = ((px - b.x0) * dx + (pz - b.z0) * dz) / len;
  if (along < -BRIDGE_END_TOLERANCE || along > len + BRIDGE_END_TOLERANCE) return null;
  const across = Math.abs((px - b.x0) * dz - (pz - b.z0) * dx) / len;
  if (across > b.halfWidth) return null;
  return lerp(b.y0, b.y1, clamp(along / len, 0, 1));
}

// ─────────────────────────────── base ground (plan frame) ───────────────────────────────

const W = LAYOUT.cloister.walks;
/** Outer rectangle of the cloister: church, courts, walks and porches all stand on the Z_NAVE podium. */
export const CLOISTER_OUTER: Rect = [W.west[0], W.south[1], W.east[2], W.north[3]];
const CORNER_RECTS: Array<{ key: keyof typeof LAYOUT.cornerBuildings; rect: Rect }> = (
  Object.keys(LAYOUT.cornerBuildings) as Array<keyof typeof LAYOUT.cornerBuildings>
).map((key) => ({ key, rect: cornerBuildingRect(LAYOUT.cornerBuildings[key]) }));
const NAT = LAYOUT.nativity;
const PAS = LAYOUT.passion;
const GLO = LAYOUT.glory;
const ASSUMPTION: Rect = [LAYOUT.assumptionChapel.x0, LAYOUT.assumptionChapel.y0, LAYOUT.assumptionChapel.x1, LAYOUT.assumptionChapel.y1];

/** Everything whose floor is Z_NAVE (plan rectangles). */
export const PODIUM_RECTS: Rect[] = [
  CLOISTER_OUTER,
  ...CORNER_RECTS.map((c) => c.rect),
  [PAS.frontX, -PAS.halfWidth, PAS.wallX, PAS.halfWidth],
  [NAT.wallX, -NAT.halfWidth, NAT.frontX, NAT.halfWidth],
  [GLO.porch.x0, GLO.porch.y0, GLO.porch.x1, GLO.porch.y1],
  ASSUMPTION,
];

export function onPodium(x: number, y: number): boolean {
  for (let i = 0; i < PODIUM_RECTS.length; i++) if (inRect(x, y, PODIUM_RECTS[i])) return true;
  return false;
}

/** Straight entrance stair as a ramp from topZ at the porch edge to the ground at the outer edge. */
interface Ramp {
  topX: number;
  botX: number;
  halfWidth: number;
  topZ: number;
}
function rampOf(s: { x0: number; x1: number; halfWidth: number; topZ: number }): Ramp {
  const topX = Math.abs(s.x0) < Math.abs(s.x1) ? s.x0 : s.x1;
  const botX = topX === s.x0 ? s.x1 : s.x0;
  return { topX, botX, halfWidth: s.halfWidth, topZ: s.topZ };
}
export const FACADE_RAMPS: Ramp[] = [rampOf(NAT.stair), rampOf(PAS.stair)];

export function rampZ(r: Ramp, x: number, y: number): number | null {
  if (Math.abs(y) > r.halfWidth) return null;
  const lo = Math.min(r.topX, r.botX);
  const hi = Math.max(r.topX, r.botX);
  if (x < lo || x > hi) return null;
  const t = (x - r.topX) / (r.botX - r.topX);
  // Bottom follows the sloped ground at every y (the facades add a sloped cheek, handover 4.2)
  return lerp(r.topZ, groundZ(y), t);
}

const PRES = LAYOUT.presbytery;
const PRES_C = LAYOUT.apse.center;
const PRES_STEPS_Y0 = PRES.frontY - PRES.steps * PRES.tread;

/** Presbytery platform (Z_ALTAR) + its front steps, or null. */
export function presbyteryZ(x: number, y: number): number | null {
  if (y >= PRES_C[1] && Math.hypot(x - PRES_C[0], y - PRES_C[1]) <= PRES.radius) return PRES.z;
  if (Math.abs(x - PRES_C[0]) <= PRES.halfWidth) {
    if (y >= PRES.frontY && y <= PRES_C[1]) return PRES.z;
    if (y >= PRES_STEPS_Y0 && y < PRES.frontY) return lerp(Z_NAVE, PRES.z, (y - PRES_STEPS_Y0) / (PRES.frontY - PRES_STEPS_Y0));
  }
  return null;
}

const POND = LAYOUT.city.pond;
const FOUNTAIN = LAYOUT.city.fountain;
/** Pond coping / water bottom / fountain basin, or null outside the pond. */
export function pondFloorZ(x: number, y: number): number | null {
  if (!inRoundedRect(x, y, POND, POND.cornerRadius, -POND_COPING_WIDTH / 2)) return null;
  if (inRoundedRect(x, y, POND, POND.cornerRadius, POND_COPING_WIDTH / 2)) {
    if (Math.hypot(x - FOUNTAIN.x, y - FOUNTAIN.y) < FOUNTAIN.r) return LAYOUT.city.pondWaterZ + FOUNTAIN_BASIN_ABOVE_WATER;
    return LAYOUT.city.pondWaterZ - POND_WADE_DEPTH;
  }
  return groundZ(y) + POND.copingAboveGround;
}
export function inPondWater(x: number, y: number): boolean {
  return inRoundedRect(x, y, POND, POND.cornerRadius, POND_COPING_WIDTH / 2);
}

const BAPT = LAYOUT.hotspots['baptistery-font']?.position ?? [0, 0, 0];

/**
 * Lowest walkable surface at (x, z): crypt, crypt stairwells, pond, presbytery, baptistery dais,
 * Z_NAVE podium, Nativity / Passion stairs, or the sloped outdoor ground (with lower carriageways).
 */
export function baseGroundY(x: number, feetY: number, z: number): number {
  const py = -z;
  // Crypt stairwells: open down to the crypt floor; the treads come from the spiral resolver.
  for (let i = 0; i < CRYPT_SPIRALS.length; i++) {
    const s = CRYPT_SPIRALS[i];
    if (feetY < s.zEnd + 2 && Math.hypot(x - s.cx, z - s.cz) <= s.rOuter) return Z_CRYPT;
  }
  if (isFeetUnderground(x, feetY, z)) return Z_CRYPT;

  const pond = pondFloorZ(x, py);
  if (pond !== null) return pond;

  const pres = presbyteryZ(x, py);
  if (pres !== null) return pres;

  const dB = Math.hypot(x - BAPT[0], py - BAPT[1]);
  for (const [r, h] of BAPTISTERY_DAIS) if (dB < r) return Z_NAVE + h;

  if (onPodium(x, py)) return Z_NAVE;

  for (let i = 0; i < FACADE_RAMPS.length; i++) {
    const rz = rampZ(FACADE_RAMPS[i], x, py);
    if (rz !== null) return rz;
  }
  return outdoorGroundZ(x, py);
}

// ─────────────────────────────── full analytic support ───────────────────────────────

/**
 * Highest walkable surface at (x, z) not more than STEP_UP_MAX above feetY: base ground, elevator cabin,
 * decks, bridges (incl. Glory bridge + stair), spiral stairs, roof decks, galleries, block roofs.
 * Inside a spiral mid-flight (or on a corner stair) the tread height is returned directly so floors
 * below never block the way down.
 */
export function analyticSupportY(cx: number, feetY: number, cz: number, elevatorFloorY: number): number {
  const maxStepY = feetY + STEP_UP_MAX;
  let bestY = baseGroundY(cx, feetY, cz);
  const consider = (y: number) => {
    if (y <= maxStepY && y > bestY) bestY = y;
  };

  // 1. Glass elevator cabin in the Jesus tower core
  const rJesus = Math.hypot(cx - JESUS_XZ.x, cz - JESUS_XZ.z);
  if (feetY >= LV.jesusDeck - 3 && rJesus < ELEVATOR_R && Math.abs(feetY - elevatorFloorY) < 2.6) consider(elevatorFloorY);

  // 2. Top decks (136 / 118 / 114), open over the last treads of their stair
  for (let i = 0; i < TOP_DECKS.length; i++) {
    const d = TOP_DECKS[i];
    const dist = Math.hypot(cx - d.cx, cz - d.cz);
    if (dist > d.r) continue;
    if (d.shaft && inAnnulus(d.shaft, dist) && inSpiralTopOpening(d.shaft, cx, cz)) continue;
    consider(d.y);
  }
  const dMary = Math.hypot(cx - MARY_XZ.x, cz - MARY_XZ.z);
  if (dMary >= MARY_ENTRY_RING[0] && dMary <= MARY_ENTRY_RING[1]) consider(LV.maryEntry);

  // 3. Crossing-vault gallery ring at 56 (contract §5)
  if (rJesus >= JESUS_RING_56[0] && rJesus <= JESUS_RING_56[1]) consider(LV.jesusDeck);

  // 4. Bridges, skybridges, roof stair-bridges, gallery links, Glory bridge and stair
  for (let i = 0; i < WALK_BRIDGES.length; i++) {
    const y = bridgeDeckY(WALK_BRIDGES[i], cx, cz);
    if (y !== null) consider(y);
  }

  // 5. Tower and crypt spiral stairs (+ top / bottom landing discs)
  for (let i = 0; i < TOWER_SPIRALS.length; i++) {
    const s = TOWER_SPIRALS[i];
    if (feetY < s.zStart - 1.5 || feetY > s.zEnd + 1.5) continue;
    const dist = Math.hypot(cx - s.cx, cz - s.cz);
    if (dist > s.rOuter) continue;
    // Inside rInner is the newel (or, for the Jesus tower, the elevator shaft): landing on top, no bottom landing.
    if (dist < s.rInner) {
      if (s.topLanding && feetY >= s.zEnd - 1.5) consider(s.zEnd);
      continue;
    }
    if (s.topLanding && dist <= s.landingR && feetY >= s.zEnd - 1.5 && !inSpiralTopOpening(s, cx, cz)) consider(s.zEnd);
    if (s.bottomLanding && feetY <= s.zStart + 1.5) consider(s.zStart);
    const y = spiralTreadY(s, cx, feetY, cz);
    if (y !== null) {
      if (y > s.zStart + 1.2 && y < s.zEnd - 1.2) return y;
      consider(y);
    }
  }

  // 6. Roof decks above the aisles / nave / transept
  for (let i = 0; i < ROOF_DECKS.length; i++) if (inBox(ROOF_DECKS[i], cx, cz)) consider(ROOF_DECKS[i].y);

  // 7. Nave -> gallery corner spiral stairs
  for (let i = 0; i < CORNER_SPIRALS.length; i++) {
    const s = CORNER_SPIRALS[i];
    const dist = Math.hypot(cx - s.cx, cz - s.cz);
    if (inAnnulus(s, dist) && feetY >= s.zStart - 0.8 && feetY <= s.zEnd + 1.3) {
      const y = spiralTreadY(s, cx, feetY, cz);
      if (y !== null) return y;
    }
  }

  // 8. Galleries / tribunes (Z_GALLERY) minus the corner stairwell holes
  let inHole = false;
  for (let i = 0; i < CORNER_HOLES.length; i++) {
    if (Math.hypot(cx - CORNER_HOLES[i].cx, cz - CORNER_HOLES[i].cz) < CORNER_HOLES[i].r) inHole = true;
  }
  if (!inHole) {
    for (let i = 0; i < GALLERY_BOXES.length; i++) if (inBox(GALLERY_BOXES[i], cx, cz)) consider(GALLERY_BOXES[i].y);
  }

  // 9. Eixample rooftops
  for (let i = 0; i < CITY_BLOCK_BOXES.length; i++) if (inBox(CITY_BLOCK_BOXES[i], cx, cz)) consider(CITY_BLOCK_BOXES[i].y);

  return bestY;
}

/**
 * Eye height that puts a camera standing inside a spiral stair on the tread at or just below it
 * (teleport heights in the layout are not tied to the stair phase). Elsewhere returns eyeY unchanged.
 */
export function settleEyeOnSpiral(x: number, eyeY: number, z: number): number {
  const feet = eyeY - EYE_HEIGHT;
  for (const s of TOWER_SPIRALS) {
    const d = Math.hypot(x - s.cx, z - s.cz);
    if (!inAnnulus(s, d) || feet < s.zStart - 0.5 || feet > s.zEnd + 0.5) continue;
    const f = spiralFrac(s, x, z);
    const n = Math.floor((feet + 0.3 - s.zStart) / s.pitch - f);
    return clamp(s.zStart + (n + f) * s.pitch, s.zStart, s.zEnd) + EYE_HEIGHT;
  }
  return eyeY;
}

const WB = LAYOUT.walkBounds;
/** Walk bounds in the runtime frame. */
export const WALK_BOUNDS = planRectToWorld(WB);

export function clampToWalkBounds(x: number, z: number): { x: number; z: number } {
  return { x: clamp(x, WALK_BOUNDS.minX, WALK_BOUNDS.maxX), z: clamp(z, WALK_BOUNDS.minZ, WALK_BOUNDS.maxZ) };
}

/** Crypt vault ceiling for jumps (eye stops 0.18 below it), or null if not in the crypt. */
export function cryptCeilingY(x: number, feetY: number, z: number): number | null {
  if (feetY >= UNDERGROUND_FEET_Y || !inCryptFootprint(x, -z)) return null;
  const c = LAYOUT.crypt;
  return Math.hypot(x - c.center[0], -z - c.center[1]) < c.pierRingR ? c.vaultCentralZ : c.vaultLowZ;
}

// ─────────────────────────────── indoor factor ───────────────────────────────

const ZN = planRectToWorld(LAYOUT.zones.nave);
const ZT = planRectToWorld(LAYOUT.zones.transept);
const ZA = LAYOUT.zones.apse;
const CLOISTER_TOP = LAYOUT.cloister.floorZ + LAYOUT.cloister.height;
const WALK_RECTS: Rect[] = [W.east, W.west, W.north, W.south];

/** 0 = open sky, 1 = deep inside stone (lighting, exposure, audio). */
export function indoorFactorAt(x: number, y: number, z: number): number {
  if (isEyeUnderground(x, y, z)) return 1.0;
  const rCore = Math.hypot(x - JESUS_XZ.x, z - JESUS_XZ.z);
  const coreTop = LV.jesusView - 2;
  if (rCore < 8.5 && y >= 1.0 && y < coreTop) return smoothstep(coreTop - y, 0.0, 6.0) * 0.92;
  if (y > LV.naveVault) return 0.0;

  const ax = Math.abs(x);
  const fNave =
    smoothstep(ZN.maxX + 1.5 - ax, 0.0, 5.0) *
    smoothstep(z - (ZN.minZ - 3.0), 0.0, 5.0) *
    smoothstep(ZN.maxZ + 2.5 - z, 0.0, 6.0);
  const fTransept = smoothstep(ZT.maxX + 1.5 - ax, 0.0, 6.0) * smoothstep(ZT.maxZ + 1.5 - Math.abs(z), 0.0, 4.0);
  const fApse =
    smoothstep(ZA.r + 1.0 - Math.hypot(x - ZA.center[0], -z - ZA.center[1]), 0.0, 5.0) *
    smoothstep(-ZA.southY + 3.0 - z, 0.0, 4.0);
  const fMain = Math.max(fNave, fTransept, fApse);
  if (fMain > 0.01) return Math.min(1.0, fMain);

  const py = -z;
  if (y < Z_NAVE + 14) {
    for (const c of CORNER_RECTS) if (inRect(x, py, c.rect)) return 0.85;
    if (inRect(x, py, ASSUMPTION)) return 0.85;
  }
  if (y < CLOISTER_TOP) {
    for (const r of WALK_RECTS) if (inRect(x, py, r)) return 0.55;
  }
  return 0.0;
}

// ─────────────────────────────── zones ───────────────────────────────

export interface ZoneInfo {
  key: MessageKey;
  /** Rounded height for {y}. */
  y?: number;
  /** Tower / stair name key for {tower}. */
  towerKey?: MessageKey;
}

const NAT_X = LAYOUT.towers.find((t) => t.family === 'nativity')!.x;
const PAS_X = LAYOUT.towers.find((t) => t.family === 'passion')!.x;
const GLORY_Z = -LAYOUT.towers.find((t) => t.family === 'glory')!.y;
const PG = LAYOUT.city.placaGaudi;
const PSF = LAYOUT.city.placaSagradaFamilia;
const BLOCK = LAYOUT.block;
const CORNER_ZONE: Record<keyof typeof LAYOUT.cornerBuildings, MessageKey> = {
  sacristyWest: 'zone.sacristy',
  sacristyEast: 'zone.sacristy',
  baptistery: 'zone.baptistery',
  penitenceChapel: 'zone.penitence',
};

/** Zone badge for a camera position (eye height). */
export function detectZoneInfo(x: number, y: number, z: number, elevatorFloorY: number): ZoneInfo {
  const yR = Math.round(y);
  const rCore = Math.hypot(x - JESUS_XZ.x, z - JESUS_XZ.z);
  if (rCore < 2.25 && y >= LV.jesusDeck - 2 && y < LV.jesusView + 2 && Math.abs(y - EYE_HEIGHT - elevatorFloorY) < 2.5) {
    return { key: 'zone.elevator', y: yR };
  }
  if (y > LV.jesusView - 4 && rCore < 10) return { key: 'zone.jesusView' };
  if (y > LV.maryDeck - 3 && Math.hypot(x - MARY_XZ.x, z - MARY_XZ.z) < 7) return { key: 'zone.maryView' };
  if (y > LV.evangelistDeck - 3) {
    for (const t of EVANGELISTS) if (Math.abs(x - t.x) < 5 && Math.abs(z + t.y) < 5) return { key: 'zone.evangelistView' };
  }
  if (y >= LV.jesusDeck - 2 && y <= LV.jesusDeck + 5 && rCore < 8.5) return { key: 'zone.crossingGallery' };

  for (const s of TOWER_SPIRALS) {
    if (Math.hypot(x - s.cx, z - s.cz) < s.rOuter + 0.6 && y >= s.zStart - 0.5 && y < s.zEnd - 0.5) {
      return { key: 'zone.stair', towerKey: s.key ?? undefined, y: yR };
    }
  }

  if (y > LV.jesusDeck - 2 && y < LV.maryEntry) {
    if (Math.abs(x - NAT_X) < 5 && Math.abs(z) < 18) return { key: 'zone.bridgeEast' };
    if (Math.abs(x - PAS_X) < 5 && Math.abs(z) < 18) return { key: 'zone.bridgeWest' };
    if (Math.abs(z - GLORY_Z) < 5 && Math.abs(x) < 18) return { key: 'zone.bridgeSouth' };
    if (Math.abs(z) < 4 || Math.abs(x) < 4) return { key: 'zone.roofBridge', y: yR };
  }
  if (y >= LV.roofDeckNave - 2 && y <= LV.roofDeckNave + 7 && Math.abs(x) < 32 && z > -45 && z < 48) {
    return { key: 'zone.roofscape' };
  }
  if (y > LV.jesusDeck - 1) return { key: 'zone.airspace' };
  if (isEyeUnderground(x, y, z)) return { key: 'zone.crypt' };
  if (y > LV.gallery - 2.2 && y < LV.gallery + 9.8 && Math.abs(x) < 34 && z > -45 && z < 48) return { key: 'zone.galleries' };

  const py = -z;
  if (Math.hypot(x - PRES_C[0], py - PRES_C[1]) < 12.5 && y < 14) return { key: 'zone.altar' };
  if (Math.abs(x) < 11 && Math.abs(z) < 11 && y < 55) return { key: 'zone.crossing' };
  if (y < LV.naveVault) {
    if (Math.abs(x) < LAYOUT.nave.halfWidth && z >= ZN.minZ && z < ZN.maxZ) return { key: 'zone.nave' };
    if (Math.abs(x) < ZT.maxX && Math.abs(z) < LAYOUT.transept.extWallY) return { key: 'zone.transept' };
  }
  for (const c of CORNER_RECTS) if (inRect(x, py, c.rect)) return { key: CORNER_ZONE[c.key] };
  if (inRect(x, py, ASSUMPTION)) return { key: 'zone.assumption' };
  if (y < CLOISTER_TOP + 3) {
    for (const r of WALK_RECTS) if (inRect(x, py, r)) return { key: 'zone.cloister' };
  }
  if (inPondWater(x, py) && y < LAYOUT.city.pondWaterZ + 2.6) return { key: 'zone.inPond' };
  if (inRect(x, py, PG)) return { key: 'zone.pondEast' };
  if (x > NAT.frontX && x < BLOCK.east && Math.abs(z) < 25) return { key: 'zone.nativityForecourt' };
  if (inRect(x, py, PSF)) return { key: 'zone.placaWest' };
  if (x < -NAT.frontX && x > BLOCK.west && Math.abs(z) < 25) return { key: 'zone.passionForecourt' };
  if (z > -GLO.wallFrontY) return { key: 'zone.glory' };
  return { key: 'zone.eixample' };
}
