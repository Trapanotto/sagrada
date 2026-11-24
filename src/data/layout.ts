/**
 * Typed accessor for the master ground plan (single source of truth: blender/layout.py).
 *
 * The numbers live in ./layout.generated.ts, written by `npm run layout` (python blender/layout.py).
 * Never edit the generated file or re-type its numbers here: change blender/layout.py and regenerate,
 * so the Blender build and the runtime always agree.
 *
 * FRAMES
 *  - Plan frame (all raw values below): Blender metres, x = east (Nativity), y = north (apse),
 *    z = up. Origin = crossing centre (Jesus tower axis). 7.5 m module.
 *  - Runtime world frame (three.js, Y up): world = (x, z, -y). Runtime -Z is "north" (apse).
 *    Use planToWorld() / planXZ() / the *Runtime() helpers instead of converting by hand.
 */
import { LAYOUT_DATA } from './layout.generated';

export type Vec2 = [number, number];
export type Vec3 = [number, number, number];
/** Axis-aligned plan rectangle [x0, y0, x1, y1]. */
export type Rect = [number, number, number, number];

export interface RectXY {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface LayoutColumn {
  kind: 'porphyry' | 'basalt' | 'granite' | 'sandstone';
  x: number;
  y: number;
  /** Foot level (Z_NAVE, or the presbytery level for the presbytery ring). */
  z: number;
  group: 'crossing' | 'crossingRing' | 'nave' | 'aisle' | 'transept' | 'presbytery';
}

export interface LayoutSpiral {
  x: number;
  y: number;
  rInner: number;
  rOuter: number;
  z0: number;
  z1: number;
  turns: number;
  phaseDeg: number;
}

export interface LayoutCornerStair extends LayoutSpiral {
  hole: number;
}

export interface LayoutCryptStair extends LayoutSpiral {
  side: 'west' | 'east';
  clockwise: boolean;
}

export interface LayoutTowerStair {
  z0: number;
  z1: number;
  rInner: number;
  rOuter: number;
  rMid: number;
  tread: number;
  turnsPer10m: number;
  /** Angle (plan frame, CCW from +x) of the first tread at z0 = direction of the entry bridge. */
  phaseDeg: number;
  clockwise: boolean;
}

export interface LayoutTower {
  /** i18n MessageKey of the tower name, also the id used by CollisionSystem's stair badges. */
  key: string;
  name: string;
  family: 'nativity' | 'passion' | 'glory' | 'evangelist' | 'jesus' | 'mary';
  kind: 'apostle' | 'evangelist' | 'jesus' | 'mary';
  x: number;
  y: number;
  /** Reference level of rRef; paraboloid r(z) = rRef * sqrt((zApex - z) / (zApex - zRef)). */
  zRef: number;
  rRef: number;
  zTop: number;
  zApex: number;
  stair: LayoutTowerStair;
}

export interface LayoutBridge {
  name: string;
  x0: number;
  y0: number;
  z0: number;
  x1: number;
  y1: number;
  z1: number;
  halfWidth: number;
}

export interface LayoutStairRun {
  halfWidth: number;
  topZ: number;
  bottomZ: number;
}

export interface LayoutCornerBuilding {
  x: number;
  y: number;
  side: number;
  top: number;
  dome: number;
}

export interface LayoutCityBlock extends RectXY {
  name: string;
  height: number;
  chamfer: number;
  courtyardInset: number;
  /** Chamfered corners [SW, SE, NE, NW] (plan frame). */
  chamferCorners: [boolean, boolean, boolean, boolean];
}

export interface LayoutViewpoint {
  /** Teleports: eye position. */
  position: Vec3;
  lookAt: Vec3;
}

export interface LayoutHotspot {
  position: Vec3;
  cameraTarget: Vec3;
}

export interface LayoutData {
  version: number;
  frame: { grid: number; plusYCompassAzimuth: number; note: string };
  levels: {
    nave: number;
    altar: number;
    gallery: number;
    childrenChoir: number;
    crypt: number;
    cryptVaultLow: number;
    cryptVaultCentral: number;
    aisleVault: number;
    naveVault: number;
    crossingVault: number;
    apseVault: number;
    ambulatoryVault: number;
    apseTriforiumVault: number;
    apseSkylightFoot: number;
    roofDeckAisle: number;
    roofDeckNave: number;
    jesusDeck: number;
    jesusView: number;
    evangelistDeck: number;
    maryEntry: number;
    maryDeck: number;
    skybridgeTransept: number;
    skybridgeGlory: number;
    eye: number;
  };
  ground: { z0: number; slopeY: number; curb: number; gloryEntranceAboveMallorca: number };
  nave: {
    halfWidth: number;
    centralHalf: number;
    innerAisleOuter: number;
    wallThickness: number;
    buttressX: number;
    northY: number;
    gloryInnerY: number;
    interiorLength: number;
  };
  transept: { halfLength: number; halfWidth: number; extWallY: number };
  apse: {
    center: Vec2;
    presbyteryRingR: number;
    presbyteryColumns: number;
    chapels: number;
    chapelFrontR: number;
    chapelBackR: number;
    wallOuterR: number;
    buttressR: number;
    sideWallX: number;
    pierAnglesDeg: number[];
  };
  presbytery: {
    z: number;
    radius: number;
    halfWidth: number;
    frontY: number;
    steps: number;
    tread: number;
    altar: Vec2;
    altarSize: Vec3;
    baldachinDiameter: number;
    baldachinZ: number;
  };
  columns: LayoutColumn[];
  columnFallbackRadius: Record<LayoutColumn['kind'], number>;
  galleries: Record<'east' | 'west' | 'south' | 'nativityTribune' | 'passionTribune', Rect>;
  cornerStairs: LayoutCornerStair[];
  crypt: {
    center: Vec2;
    floorZ: number;
    vaultLowZ: number;
    vaultCentralZ: number;
    pierRingR: number;
    pierCount: number;
    chapelFrontR: number;
    chapelBackR: number;
    wallOuterR: number;
    halfWidth: number;
    southWallY: number;
    southChapelDepth: number;
    southChapelX: number[];
    southChapels: string[];
    altar: Vec2;
    gaudiTomb: Vec2;
    bocabellaTomb: Vec2;
    keystone: Vec3;
    stairs: LayoutCryptStair[];
    stairTopDoor: { yWall: Vec2; halfWidth: number };
    stairBottomDoor: { xWall: number; y: number; halfWidth: number };
  };
  block: { north: number; south: number; east: number; west: number };
  cloister: {
    width: number;
    clearWidth: number;
    height: number;
    floorZ: number;
    walks: Record<'east' | 'west' | 'north' | 'south', Rect>;
  };
  cornerBuildings: Record<'sacristyWest' | 'sacristyEast' | 'penitenceChapel' | 'baptistery', LayoutCornerBuilding>;
  assumptionChapel: RectXY & { domeTop: number; streetDoorsX: number[] };
  nativity: {
    wallX: number;
    frontX: number;
    halfWidth: number;
    porchFloorZ: number;
    portals: Array<{ name: string; y: number; width: number }>;
    turtleColumns: Vec2[];
    cypressY: number;
    stair: LayoutStairRun & { x0: number; x1: number };
    cloisterPassage: Vec2;
  };
  passion: {
    wallX: number;
    frontX: number;
    halfWidth: number;
    porchFloorZ: number;
    columns: Array<{ foot: Vec2; head: Vec2 }>;
    roofZ: Vec2;
    stair: LayoutStairRun & { x0: number; x1: number };
    cloisterPassage: Vec2;
  };
  glory: {
    innerY: number;
    wallFrontY: number;
    halfWidth: number;
    porch: RectXY & { floorZ: number };
    porticoColumnY: number;
    porticoColumnX: number[];
    doorsX: number[];
    bridge: { y0: number; y1: number; halfWidth: number; deckZ: number; soffitZ: number };
    stair: LayoutStairRun & { y0: number; y1: number; landings: number };
    monuments: Vec2[];
  };
  towers: LayoutTower[];
  towerRules: { shellZ0: number; minClearance: number; passionSection: { longAxis: 'x' | 'y'; gain: number } };
  walkBridges: LayoutBridge[];
  stairTopLandings: boolean;
  /** [x0, y0, x1, y1, z] */
  roofDecks: Array<[number, number, number, number, number]>;
  city: {
    streets: Record<string, { axis: 'x' | 'y'; center: number; halfWidth: number }>;
    sidewalkWidth: number;
    chamferLeg: number;
    sagradaBlock: RectXY & { chamfer: number };
    placaGaudi: RectXY & { chamfer: number };
    placaSagradaFamilia: RectXY & { chamfer: number };
    pond: RectXY & { cornerRadius: number; waterBelowGround: number; copingAboveGround: number };
    pondCenter: Vec2;
    pondWaterZ: number;
    fountain: { x: number; y: number; r: number };
    gloryAvenue: RectXY;
    blocks: LayoutCityBlock[];
    distantCityMinExtent: Vec2;
    keepClear: Rect[];
    streetTree: { spacing: number; curbOffset: number };
    streetLamp: { spacing: number; curbOffset: number };
  };
  walkBounds: RectXY;
  minimapExtent: RectXY;
  spawn: string;
  teleports: Record<string, LayoutViewpoint>;
  hotspots: Record<string, LayoutHotspot>;
  naveWindowBayY: number[];
  lights: Record<string, { pos: Vec3; target?: Vec3 }>;
  zones: {
    basilicaCenter: Vec2;
    crypt: { center: Vec2; r: number; southY: number; zMax: number };
    apse: { center: Vec2; r: number; southY: number };
    nave: Rect;
    transept: Rect;
    presbytery: { center: Vec2; r: number; frontY: number; stepsY: number };
  };
}

/** The master layout (plan frame). */
export const LAYOUT: LayoutData = LAYOUT_DATA;

// ─────────────────────────────── frame conversion ───────────────────────────────

/** Plan (x east, y north, z up) -> three.js world [x, y, z]. */
export function planToWorld(x: number, y: number, z = 0): Vec3 {
  return [x, z, -y];
}

/** three.js world -> plan [x, y, z]. */
export function worldToPlan(wx: number, wy: number, wz: number): Vec3 {
  return [wx, -wz, wy];
}

/** Plan point -> runtime ground-plane coordinates { x, z }. */
export function planXZ(x: number, y: number): { x: number; z: number } {
  return { x, z: -y };
}

/** Plan rectangle -> runtime XZ box (min/max sorted, runtime z = -plan y). */
export function planRectToWorld(r: Rect | RectXY): { minX: number; maxX: number; minZ: number; maxZ: number } {
  const [x0, y0, x1, y1] = Array.isArray(r) ? r : [r.x0, r.y0, r.x1, r.y1];
  return { minX: Math.min(x0, x1), maxX: Math.max(x0, x1), minZ: Math.min(-y0, -y1), maxZ: Math.max(-y0, -y1) };
}

// ─────────────────────────────── ground ───────────────────────────────

/** Outdoor ground (sidewalk / plaza) height at plan y. The street is NOT at 0 any more. */
export function groundZ(planY: number): number {
  return LAYOUT.ground.z0 + LAYOUT.ground.slopeY * planY;
}

/** Outdoor ground height at a runtime world z. */
export function groundWorldY(worldZ: number): number {
  return groundZ(-worldZ);
}

/** True if plan point (x, y) lies in a carriageway (street minus its sidewalks on both sides). */
export function inCarriageway(x: number, y: number): boolean {
  const c = LAYOUT.city;
  for (const key in c.streets) {
    const s = c.streets[key];
    const v = s.axis === 'x' ? x : y;
    if (Math.abs(v - s.center) <= s.halfWidth - c.sidewalkWidth) return true;
  }
  return false;
}

/**
 * Outdoor walking surface at plan (x, y): sidewalks / plazas on ground_z(y), carriageways `curb` lower.
 * Everything outdoors that is not a building, stair, bridge or the pond.
 */
export function outdoorGroundZ(x: number, y: number): number {
  return groundZ(y) - (inCarriageway(x, y) ? LAYOUT.ground.curb : 0);
}

// ─────────────────────────────── plan-shape tests ───────────────────────────────

/** Point in an axis-aligned plan rectangle (either corner order). */
export function inRect(x: number, y: number, r: Rect | RectXY, margin = 0): boolean {
  const [x0, y0, x1, y1] = Array.isArray(r) ? r : [r.x0, r.y0, r.x1, r.y1];
  return (
    x >= Math.min(x0, x1) - margin &&
    x <= Math.max(x0, x1) + margin &&
    y >= Math.min(y0, y1) - margin &&
    y <= Math.max(y0, y1) + margin
  );
}

/** Point in a rectangle with rounded corners (radius clamped to half the shorter side). Negative inset grows it. */
export function inRoundedRect(x: number, y: number, r: RectXY, radius: number, inset = 0): boolean {
  const x0 = Math.min(r.x0, r.x1) + inset;
  const x1 = Math.max(r.x0, r.x1) - inset;
  const y0 = Math.min(r.y0, r.y1) + inset;
  const y1 = Math.max(r.y0, r.y1) - inset;
  if (x < x0 || x > x1 || y < y0 || y > y1) return false;
  const rad = Math.max(0, Math.min(radius - inset, (x1 - x0) / 2, (y1 - y0) / 2));
  const cx = Math.min(Math.max(x, x0 + rad), x1 - rad);
  const cy = Math.min(Math.max(y, y0 + rad), y1 - rad);
  return Math.hypot(x - cx, y - cy) <= rad;
}

/** Corner building (sacristy, baptistery, ...) as a plan rectangle. */
export function cornerBuildingRect(b: LayoutCornerBuilding): Rect {
  const h = b.side / 2;
  return [b.x - h, b.y - h, b.x + h, b.y + h];
}

/** Half extents of the pond and its centre in the runtime frame (for boxes, planes and shaders). */
export function pondRuntime(): { cx: number; cz: number; width: number; depth: number; waterY: number } {
  const p = LAYOUT.city.pond;
  return {
    cx: (p.x0 + p.x1) / 2,
    cz: -(p.y0 + p.y1) / 2,
    width: Math.abs(p.x1 - p.x0),
    depth: Math.abs(p.y1 - p.y0),
    waterY: LAYOUT.city.pondWaterZ,
  };
}

/** Crypt depth below the basilica floor (texts: "-9 m"). */
export function cryptDepthBelowNave(): number {
  return LAYOUT.levels.nave - LAYOUT.levels.crypt;
}

// ─────────────────────────────── lookups ───────────────────────────────

export function towerByKey(key: string): LayoutTower {
  const t = LAYOUT.towers.find((tw) => tw.key === key);
  if (!t) throw new Error(`layout: unknown tower ${key}`);
  return t;
}

/** Tower radius at height z (same paraboloid law as blender/towers_lib.py). */
export function towerRadiusAt(t: LayoutTower, z: number): number {
  return t.rRef * Math.sqrt(Math.max(0, (t.zApex - z) / (t.zApex - t.zRef)));
}

/** True if a plan point lies inside the crypt footprint (semicircle + straight part). */
export function inCryptFootprint(x: number, y: number): boolean {
  const c = LAYOUT.crypt;
  const r = c.wallOuterR;
  if (y >= c.center[1]) return Math.hypot(x - c.center[0], y - c.center[1]) <= r;
  return Math.abs(x - c.center[0]) <= r && y >= c.southWallY - 1.25;
}

/**
 * Crypt footprint plus the two crypt spiral stairs (which stand just outside the crypt wall).
 * Use this, not a height threshold, to decide "underground": outdoor ground now drops to about -6 m.
 */
export function inCryptWalkArea(x: number, y: number): boolean {
  if (inCryptFootprint(x, y)) return true;
  return LAYOUT.crypt.stairs.some((s) => Math.hypot(x - s.x, y - s.y) <= s.rOuter + 0.6);
}

// ─────────────────────────────── runtime-frame views ───────────────────────────────
// Shapes match the existing runtime structures so phase 2 can swap them in directly.

/**
 * Like CollisionSystem.TowerStairShaft (cz = runtime z), plus the new phaseDeg.
 *
 * Helix convention (shared with blender towers_lib / build_cloister_crypt): the tread at height z lies at
 * plan angle  phaseDeg + sgn * 360 * (z - zStart) / pitch,  sgn = +1 if clockwise else -1,
 * pitch = 10 / turnsPer10m, angles CCW from +x in the plan frame (runtime: atan2(-dz, dx)).
 */
export interface RuntimeStairShaft {
  towerKey: string;
  cx: number;
  cz: number;
  zStart: number;
  zEnd: number;
  rInner: number;
  rOuter: number;
  turnsPer10m: number;
  clockwise: boolean;
  phaseDeg: number;
}

export function towerStairShaftsRuntime(): RuntimeStairShaft[] {
  const shafts: RuntimeStairShaft[] = LAYOUT.towers.map((t) => ({
    towerKey: t.key,
    cx: t.x,
    cz: -t.y,
    zStart: t.stair.z0,
    zEnd: t.stair.z1,
    rInner: t.stair.rInner,
    rOuter: t.stair.rOuter,
    turnsPer10m: t.stair.turnsPer10m,
    clockwise: t.stair.clockwise,
    phaseDeg: t.stair.phaseDeg,
  }));
  for (const s of LAYOUT.crypt.stairs) {
    shafts.push({
      towerKey: `cryptStair.${s.side}`,
      cx: s.x,
      cz: -s.y,
      zStart: s.z0,
      zEnd: s.z1,
      rInner: s.rInner,
      rOuter: s.rOuter,
      turnsPer10m: (s.turns / (s.z1 - s.z0)) * 10,
      clockwise: s.clockwise,
      phaseDeg: s.phaseDeg,
    });
  }
  return shafts;
}

/** Like CollisionSystem.WalkBridge: x/z ground plane, y0/y1 = heights. */
export interface RuntimeWalkBridge {
  x0: number;
  y0: number;
  z0: number;
  x1: number;
  y1: number;
  z1: number;
  halfWidth: number;
}

export function walkBridgesRuntime(): RuntimeWalkBridge[] {
  return LAYOUT.walkBridges.map((b) => ({
    x0: b.x0,
    y0: b.z0,
    z0: -b.y0,
    x1: b.x1,
    y1: b.z1,
    z1: -b.y1,
    halfWidth: b.halfWidth,
  }));
}

/** Like CollisionSystem.INTERIOR_COLUMNS: [x, z, pushOutRadius]. */
export function interiorColumnsRuntime(): Array<[number, number, number]> {
  return LAYOUT.columns.map((c) => [c.x, -c.y, LAYOUT.columnFallbackRadius[c.kind]]);
}

/** Teleport / hotspot positions in the runtime frame, keyed by the ids used in teleports.ts / hotspots.ts. */
export function teleportRuntime(id: string): { position: Vec3; lookAt: Vec3 } {
  const v = LAYOUT.teleports[id];
  if (!v) throw new Error(`layout: unknown teleport ${id}`);
  return { position: planToWorld(...v.position), lookAt: planToWorld(...v.lookAt) };
}

export function hotspotRuntime(id: string): { position: Vec3; cameraTarget: Vec3 } {
  const v = LAYOUT.hotspots[id];
  if (!v) throw new Error(`layout: unknown hotspot ${id}`);
  return { position: planToWorld(...v.position), cameraTarget: planToWorld(...v.cameraTarget) };
}
