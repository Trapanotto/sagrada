"""Build all 18 towers of the Sagrada Família (architecture-accuracy pass).

Target values (source / confidence) — see also the header of towers_lib.py:
  Jesus Christ   172.5 m total; stone body to 142.5 m (12th panel level); 29 m pinnacle =
                 terminal 142.5..155.65 m + 16.85 m cross, 13.5 m wide          (sagradafamilia.org, high)
  Virgin Mary    138 m; 6 m crown + 18 m hyperboloid lantern + 7.5 m star        (sagradafamilia.org, high)
  Evangelists    135 m; body 45..112.5 m, 22.5 m pinnacle, 4.5 m figure          (sagradafamilia.org, high)
  Apostles       98.5..120 m overall range                                       (SF booklet, high)
                 per tower: Nativity 98.4 / 107.0, Passion 107.4 / 112.2, Glory 112 / 120 (outer / inner)
                 (project UI texts, consistent with the range; per-tower values medium confidence)
                 pinnacle ~20 % of the height (estimate from photographs, low confidence)
True-layout pass: every plan position, base radius, stair (z0, z1, rMid, tread, turnsPer10m, phaseDeg,
clockwise), deck level and bridge comes from blender/layout.py (TOWERS, WALK_BRIDGES, TOWER_SHELL_Z0,
PASSION_SECTION, ...). The web runtime reads the same numbers from src/data/layout.ts.

Spiral-stair convention (shared with CollisionSystem.ts): the tread at height z sits at plan angle
    ang(z) = phaseDeg + sgn * 360 * (z - z0) * turnsPer10m / 10,   sgn = +1 if clockwise else -1
(degrees, counter-clockwise from +X; `clockwise: true` = the angle increases with height).
"""

from __future__ import annotations

import math
import os
import sys
import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
from common import (
    MODEL_DIR,
    add_box,
    add_cylinder,
    add_lathe,
    export_glb,
    finalize_bmesh_object,
    get_materials,
    make_pbr_material,
    make_shared_mesh,
    place_mesh_instance,
    reset_scene,
)
from towers_lib import (
    PIN_LOCAL_H,
    PIN_LOCAL_R,
    add_evangelist_terminal,
    add_jesus_cross,
    add_mary_terminal,
    add_star_12_points,
    add_tower_shell,
    apply_tower_uv,
    build_apostle_pinnacle,
    paraboloid_radius,
    superellipse_gain,
)
import layout as L
from layout import (
    APSE_CENTER,
    GALLERIES,
    PASSION_SECTION,
    STAIR_TOP_LANDINGS,
    TOWER_SHELL_Z0,
    TOWERS,
    WALK_BRIDGES,
    Z_EVANGELIST_DECK,
    Z_GALLERY,
    Z_JESUS_DECK,
    Z_JESUS_VIEW,
    Z_MARY_DECK,
    Z_MARY_ENTRY,
)

T_JESUS = L.tower("tower.jesus")
T_MARY = L.tower("tower.mary")
APOSTLES = [t for t in TOWERS if t["kind"] == "apostle"]
EVANGELISTS = [t for t in TOWERS if t["kind"] == "evangelist"]

# ── Heights (m) ──
JESUS_BASE = Z_JESUS_DECK  # 56 crossing gallery deck (runtime contract)
JESUS_GALLERY = Z_JESUS_VIEW  # 136 viewpoint deck (JesusElevator top stop, teleport)
JESUS_BODY_TOP = 142.5     # top of the stone body, 12th level of panels (sagradafamilia.org)
JESUS_CROSS_BASE = 155.65  # 172.5 - 16.85 (lower arm 7.25 + core 4.7 + upper arm 4.9)
JESUS_TOP = T_JESUS["zTop"]  # 172.5 sagradafamilia.org
MARY_BASE = T_MARY["zRef"]   # 52
MARY_CROWN = 108.5         # 6 m stone crown 108.5..114.5, 18 m lantern 114.85..132.5, star 130.5..138
MARY_TOP = T_MARY["zTop"]    # 138
EVANG_BASE = EVANGELISTS[0]["zRef"]  # 45 "from the vaults at 45 m" (sagradafamilia.org)
EVANG_BODY_TOP = 112.5     # main body top; 22.5 m pinnacle to 135 m
EVANG_TOP = EVANGELISTS[0]["zTop"]   # 135
APOSTLE_PIN_SHARE = 0.20   # pinnacle share of the overall apostle-tower height (estimate)
# Doorway band of the Jesus / Mary shells around the 77 m skybridge (1.0 m below .. 4.5 m above the deck)
MARY_DOOR_Z = (Z_MARY_ENTRY - 1.0, Z_MARY_ENTRY + 4.5)
JESUS_DOOR_Z = (Z_MARY_ENTRY - 2.5, Z_MARY_ENTRY + 5.5)
# Mary 77 m entry ring (layout §5: r 1.70 .. 4.10). Its slab is kept 0.4 m thin so its underside stays at
# 76.6, the limit the apse hyperboloid (crown 76.2) has to respect inside r 4.2.
MARY_RING_R = (T_MARY["stair"]["rInner"], 4.10)   # outer 4.10 = runtime ring (not yet a layout name)
MARY_RING_THICKNESS = 0.4


def _ring_heights(z0: float, z1: float, step: float, keys: list[float]) -> list[float]:
    """Evenly spaced ring heights with the given key heights (doorway / gallery edges) inserted."""
    n = max(2, round((z1 - z0) / step))
    zs = [z0 + (z1 - z0) * i / n for i in range(n + 1)]
    for k in keys:
        if z0 + 0.3 < k < z1 - 0.3:
            zs = [z for z in zs if abs(z - k) > step * 0.35] + [k]
    return sorted(zs)


def _angle_diff(a: float, b: float) -> float:
    return abs(((a - b + math.pi) % (2.0 * math.pi)) - math.pi)


# ───────────────────────────── Apostle bell towers ─────────────────────────────

def apostle_section(family: str, z_ref0: float):
    """Outward-only section multiplier section(z, ang) of an apostle shell: square (Nativity) /
    elliptical (Passion, long axis per PASSION_SECTION) / rounded square (Glory) at the base, blending
    into the round parabolic shaft 20 m above z_ref0. Along the façade axis (towards the neighbours)
    every section has gain 1, so the clearance between neighbours is that of the round envelope."""
    z_fade = z_ref0 + 20.0
    p_gain = PASSION_SECTION["gain"] - 1.0
    p_long_x = PASSION_SECTION["longAxis"] == "x"

    def section(z: float, ang: float) -> float:
        w = max(0.0, min(1.0, (z_fade - z) / (z_fade - z_ref0)))
        if w <= 0.0:
            return 1.0
        if family == "nativity":
            # square base turning round with height (axes along / across the façade)
            return 1.0 + (superellipse_gain(ang, 4.0) - 1.0) * w
        if family == "passion":
            # elliptical plan; long axis X = perpendicular to the façade (layout PASSION_SECTION)
            return 1.0 + p_gain * w * (math.cos(ang) ** 2 if p_long_x else math.sin(ang) ** 2)
        return 1.0 + (superellipse_gain(ang, 3.0) - 1.0) * w * 0.6

    return section


# Ribs sit on the odd sector boundaries (22.5°, 67.5°, ...): none points straight at a neighbour
# 7.5 m away along the façade, so the 0.24 m rib never eats into TOWER_MIN_CLEARANCE.
APOSTLE_SECTORS = 16
APOSTLE_RIB_PHASE = math.pi / APOSTLE_SECTORS


def add_apostle_tower(
    bm_stone: bmesh.types.BMesh,
    bm_mosaic: bmesh.types.BMesh,
    bm_letters: bmesh.types.BMesh,
    tw: dict,
    pinnacle_meshes: list,
    tower_idx: int,
) -> None:
    """Parabolic apostle bell tower: paraboloid envelope whose vertex is the pinnacle tip, lower section
    square (Nativity) / elliptical (Passion) blending into the round shaft, 8 vertical ribs with helical
    bands of louvred openings between them, SANCTUS lettering climbing in a helix, HOSANNA EXCELSIS
    trencadís collar and the instanced ~20 % pinnacle. All plan values from layout.TOWERS (tw)."""
    cx, cy = tw["x"], tw["y"]
    z_ref0, z_top, r0, family = tw["zRef"], tw["zTop"], tw["rRef"], tw["family"]
    is_glory = family == "glory"
    skybridge_z = tw["stair"]["z1"]          # 65 (Nativity / Passion) or 72 (Glory) = stair top
    pin_h = APOSTLE_PIN_SHARE * z_top
    z_neck = z_top - pin_h
    z_apex = tw["zApex"]
    r_of_z = paraboloid_radius(r0, z_ref0, z_apex)
    z_shell0 = TOWER_SHELL_Z0  # 20.3: below it the façade owns the mass (gallery doorways 16.2..20.3)
    section = apostle_section(family, z_ref0)
    # directions of the neighbouring towers along the façade (Glory: +-X, Nativity / Passion: +-Y)
    neighbour_dirs = (0.0, math.pi) if is_glory else (math.pi * 0.5, -math.pi * 0.5)

    def is_bridge_dir(ang: float) -> bool:
        ca, sa = math.cos(ang), math.sin(ang)
        if is_glory:
            return abs(ca) > 0.72 or (abs(cx) < 5.0 and sa > 0.72)
        return abs(sa) > 0.72 or (abs(cy) < 5.0 and ((cx > 0 and ca < -0.72) or (cx < 0 and ca > 0.72)))

    z_louvre0 = z_ref0 + 8.0
    hand = -1 if family == "passion" else 1

    def cell_kind(row, k, z_lo, z_hi, ang):
        zm = 0.5 * (z_lo + z_hi)
        if z_lo < skybridge_z + 3.4 and z_hi > skybridge_z - 0.3 and is_bridge_dir(ang):
            return "open"
        if zm < z_louvre0 or z_hi > z_neck - 2.2:
            return "solid"
        if (k + hand * row) % 4 == 0:
            return "louvre"
        if zm > z_ref0 + (z_neck - z_ref0) * 0.62 and (k - hand * row) % 8 == 0:
            return "louvre"
        return "solid"

    sectors = APOSTLE_SECTORS
    zs = _ring_heights(z_shell0, z_neck, 2.3, [z_ref0, skybridge_z - 0.3, skybridge_z + 3.4])
    add_tower_shell(bm_stone, cx, cy, zs, r_of_z, sectors, cell_kind, thickness=0.26, louvres=2, section=section)

    # Vertical ribs on every second (odd) sector boundary, following the section
    for k in range(0, sectors, 2):
        ang = APOSTLE_RIB_PHASE + 2.0 * math.pi * k / sectors
        ca, sa = math.cos(ang), math.sin(ang)
        door_rib = is_bridge_dir(ang) or is_bridge_dir(ang + math.pi / sectors) or is_bridge_dir(ang - math.pi / sectors)
        seg_count = 11
        for si in range(seg_count):
            z0 = z_ref0 + (z_neck - z_ref0) * si / seg_count
            z1 = z_ref0 + (z_neck - z_ref0) * (si + 1) / seg_count
            if door_rib and z0 < skybridge_z + 3.6 and z1 > skybridge_z - 0.5:
                continue
            r0_ = r_of_z(z0) * section(z0, ang)
            r1_ = r_of_z(z1) * section(z1, ang)
            t0 = (z0 - z_ref0) / (z_neck - z_ref0)
            t1 = (z1 - z_ref0) / (z_neck - z_ref0)
            add_cylinder(
                bm_stone,
                Vector((cx + r0_ * ca, cy + r0_ * sa, z0)),
                Vector((cx + r1_ * ca, cy + r1_ * sa, z1)),
                0.24 * (1.0 - 0.35 * t0),
                0.24 * (1.0 - 0.35 * t1),
                segments=6,
                cap=False,
            )

    # String course where the louvred zone starts + HOSANNA EXCELSIS trencadís collar below the pinnacle
    for zb, h, bm_b, grow in ((z_louvre0 - 0.6, 0.25, bm_stone, 0.06), (z_neck - 1.5, 0.55, bm_mosaic, 0.10), (z_neck - 5.0, 0.4, bm_mosaic, 0.08)):
        if (skybridge_z - 0.8) <= zb <= (skybridge_z + 3.8):
            continue
        r = r_of_z(zb)
        add_cylinder(bm_b, Vector((cx, cy, zb - h)), Vector((cx, cy, zb + h)), r + grow, r + grow * 0.8, segments=sectors, cap=False)
    # Stone lip closing the top of the shaft under the pinnacle collar
    rn = r_of_z(z_neck)
    add_cylinder(bm_stone, Vector((cx, cy, z_neck - 0.6)), Vector((cx, cy, z_neck + 0.1)), rn + 0.12, rn + 0.12, segments=sectors, cap=True)

    # SANCTUS lettering: raised letter plaques climbing the shaft in a helix (solid cells only)
    n_letters = 21  # "SANCTUS" x 3
    z_l0, z_l1 = z_louvre0 + 3.0, z_neck - 7.0
    turns = 1.25
    a0 = math.atan2(cy, cx) if not is_glory else -math.pi * 0.5
    for i in range(n_letters):
        t = i / (n_letters - 1)
        z = z_l0 + (z_l1 - z_l0) * t
        ang = a0 + hand * 2.0 * math.pi * turns * t
        if (skybridge_z - 1.0) <= z <= (skybridge_z + 4.4):
            continue
        if min(_angle_diff(ang, d) for d in neighbour_dirs) < math.radians(28):
            continue  # no raised plaque in the 0.4 m gap facing the neighbouring tower
        r = r_of_z(z) * section(z, ang) + 0.05
        add_box(bm_letters, (cx + r * math.cos(ang), cy + r * math.sin(ang), z), (0.12, 0.62, 0.86), rot_euler=(0.0, -0.08, ang))

    # Shared (GPU-instanced) pinnacle, scaled to this tower's neck radius and pinnacle height
    s_xy = rn / PIN_LOCAL_R
    s_z = pin_h / PIN_LOCAL_H
    face_out = math.atan2(cy, cx) if not is_glory else -math.pi * 0.5
    for mesh in pinnacle_meshes:
        place_mesh_instance(f"{mesh.name}_{tower_idx}", mesh, (cx, cy, z_neck), rot_z=face_out, scale=(s_xy, s_xy, s_z))


def build_apostle_pinnacle_meshes(mats, mat_venetian) -> list:
    bm_stem = bmesh.new()
    bm_pearl = bmesh.new()
    bm_gold = bmesh.new()
    build_apostle_pinnacle(bm_stem, bm_pearl, bm_gold)
    return [
        make_shared_mesh(bm_stem, "Towers_TrencadisPinnacles_Mitre", mat_venetian, smooth=False, uv_scale=0.6),
        make_shared_mesh(bm_pearl, "Towers_TrencadisPinnacles_Pearls", mats["white_marble"], uv_scale=0.8, bake_ao=False),
        make_shared_mesh(bm_gold, "Towers_GoldAccents_Mitre", mats["gold_accent"], uv_scale=0.6, bake_ao=False),
    ]


# ───────────────────────────── Spiral stairs (unchanged runtime contract) ─────────────────────────────

def add_spiral_stair_shaft(
    bm_stone: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
    cx: float,
    cy: float,
    z0: float,
    z1: float,
    r_mid: float = 1.65,
    tread_w: float = 1.25,
    turns_per_10m: float = 1.55,
    step_rise: float = 0.28,
    clockwise: bool = True,
    phase_deg: float = 0.0,
) -> float:
    """Continuous overlapping helical stone staircase (same helix as the runtime's stair shafts, built
    from layout towerStairShaftsRuntime()). The first tread at z0 sits at plan angle phase_deg (CCW from
    +X, = direction of the entry bridge); ang(t) = phase + sgn * t * turns * 2pi with sgn = +1 when
    clockwise (angle increases with height). Returns the plan angle (rad) of the top tread at z1."""
    span = max(2.0, z1 - z0)
    steps = max(18, int(span / step_rise))
    turns = (span / 10.0) * turns_per_10m
    sgn = 1.0 if clockwise else -1.0
    phase = math.radians(phase_deg)
    r_rail = max(0.55, r_mid - tread_w * 0.45)

    for si in range(steps):
        t = si / max(1, steps - 1)
        ang = phase + sgn * t * turns * 2.0 * math.pi
        z = z0 + t * span
        sx = cx + r_mid * math.cos(ang)
        sy = cy + r_mid * math.sin(ang)
        add_box(bm_stone, (sx, sy, z), (tread_w, 0.68, 0.24), rot_euler=(0.0, 0.0, ang))
        if si < steps - 1 and si % 3 == 0:
            t_n = min(1.0, (si + 3) / max(1, steps - 1))
            ang_n = phase + sgn * t_n * turns * 2.0 * math.pi
            z_n = z0 + t_n * span
            p0 = Vector((cx + r_rail * math.cos(ang), cy + r_rail * math.sin(ang), z + 0.92))
            p1 = Vector((cx + r_rail * math.cos(ang_n), cy + r_rail * math.sin(ang_n), z_n + 0.92))
            add_cylinder(bm_gold, p0, p1, 0.05, 0.05, segments=5, cap=False)
    return phase + sgn * turns * 2.0 * math.pi


def add_stair_from_layout(bm_stairs, bm_rails, tw: dict, step_rise: float) -> float:
    """Spiral stair of a layout.TOWERS entry (centre, z0..z1, rMid, tread, turnsPer10m, phaseDeg, clockwise)."""
    s = tw["stair"]
    return add_spiral_stair_shaft(bm_stairs, bm_rails, tw["x"], tw["y"], s["z0"], s["z1"], r_mid=s["rMid"], tread_w=s["tread"],
                                  turns_per_10m=s["turnsPer10m"], step_rise=step_rise, clockwise=s["clockwise"], phase_deg=s["phaseDeg"])


def add_top_landing(bm, cx: float, cy: float, z: float, r: float, top_ang: float, clockwise: bool,
                    well_deg: float = 100.0, thickness: float = 0.15, segments: int = 14) -> None:
    """Top landing disc (layout STAIR_TOP_LANDINGS: floor for r <= rOuter at the stair's z1), with the
    stair well left open over the last `well_deg` of the helix (treads within ~1.6 m below the top), so
    the climber does not walk into its underside. Lives in a non-collidable stair mesh."""
    sgn = 1.0 if clockwise else -1.0
    # the open well spans [top - sgn*well, top + sgn*10°]; the disc covers the rest of the circle
    a_start = top_ang + sgn * math.radians(10.0)
    arc = 2.0 * math.pi - math.radians(well_deg + 10.0)
    top_c = bm.verts.new((cx, cy, z))
    bot_c = bm.verts.new((cx, cy, z - thickness))
    tops, bots = [], []
    for i in range(segments + 1):
        a = a_start + sgn * arc * i / segments
        tops.append(bm.verts.new((cx + r * math.cos(a), cy + r * math.sin(a), z)))
        bots.append(bm.verts.new((cx + r * math.cos(a), cy + r * math.sin(a), z - thickness)))
    for i in range(segments):
        bm.faces.new((top_c, tops[i], tops[i + 1]) if sgn > 0 else (top_c, tops[i + 1], tops[i]))
        bm.faces.new((bot_c, bots[i + 1], bots[i]) if sgn > 0 else (bot_c, bots[i], bots[i + 1]))
        bm.faces.new((tops[i], bots[i], bots[i + 1], tops[i + 1]) if sgn > 0 else (tops[i + 1], bots[i + 1], bots[i], tops[i]))
    for e_top, e_bot in ((tops[0], bots[0]), (tops[-1], bots[-1])):
        bm.faces.new((top_c, bot_c, e_bot, e_top))


# ───────────────────────────── Tower of Jesus Christ ─────────────────────────────

def _paraboloid_window(row_in_tier: int, k: int, tier: int, period: int) -> bool:
    """Pointed (triangular) windows following the paraboloids: 3 cells wide at the bottom row of
    each 3-row tier, 1 cell in the middle row, solid top row; tiers interlock."""
    c = (tier * (period // 2)) % period
    d = (k - c) % period
    if row_in_tier == 0:
        return d in (period - 1, 0, 1)
    if row_in_tier == 1:
        return d == 0
    return False


def add_jesus_christ_tower(bm_stone, bm_mosaic, bm_gold, bm_cross, bm_glass, bm_ceramic) -> None:
    """Tower of Jesus Christ: paraboloid stone body 56..142.5 m with pointed paraboloid windows, the
    136 m loggia (runtime viewpoint), the 142.5..155.65 m terminal and the 16.85 m four-armed cross."""
    r_base = T_JESUS["rRef"]  # 9.5 at zRef 56
    # paraboloid through r(56) = 9.5 and r(142.5) = 5.4  ->  vertex at zApex 183.8 m
    r_j = paraboloid_radius(r_base, T_JESUS["zRef"], T_JESUS["zApex"])
    ribs = 12
    sectors = 24
    jd0, jd1 = JESUS_DOOR_Z
    zs = _ring_heights(JESUS_BASE, JESUS_BODY_TOP, 2.05, [62.0, jd0, jd1, 135.9, 139.8])
    row_of = {z: i for i, z in enumerate(zs)}

    def kind_j(row, k, z_lo, z_hi, ang):
        zm = 0.5 * (z_lo + z_hi)
        if zm < 62.0:
            return "open"  # colonnade over the crossing gallery (8 roof bridges)
        if jd0 <= zm <= jd1 and math.radians(58) <= ang <= math.radians(122):
            return "open"  # 77 m doorway to the Mary skybridge
        if 135.9 <= zm <= 139.8:
            return "open"  # 136 m loggia
        if zm > 140.5:
            return "solid"
        rr = row - row_of.get(62.0, 0)
        return "open" if _paraboloid_window(rr % 3, k, rr // 3, 6) else "solid"

    add_tower_shell(bm_stone, 0.0, 0.0, zs, r_j, sectors, kind_j, thickness=0.36)
    # walk bridges leaving the 56 m deck through the colonnade (roof stair-bridges, Evangelist bridges):
    # the colonnade ribs in their path are left out up to head height
    deck_dirs = []
    for b in WALK_BRIDGES:
        if abs(b["z0"] - JESUS_BASE) < 0.3 and math.hypot(b["x0"], b["y0"]) < r_base:
            deck_dirs.append((math.atan2(b["y1"] - b["y0"], b["x1"] - b["x0"]), b["halfWidth"]))
    for k in range(ribs):
        a0 = 2.0 * math.pi * k / ribs
        n = 16
        in_path = any(_angle_diff(a0, a) < math.asin(min(1.0, (hw + 0.9) / r_base)) for a, hw in deck_dirs)
        for si in range(n):
            z0 = JESUS_BASE + (JESUS_BODY_TOP - JESUS_BASE) * si / n
            z1 = JESUS_BASE + (JESUS_BODY_TOP - JESUS_BASE) * (si + 1) / n
            if k == 3 and z0 < jd1 and z1 > jd0:
                continue
            if in_path and z0 < JESUS_BASE + 3.0:
                continue
            t0 = si / n
            t1 = (si + 1) / n
            r0, r1 = r_j(z0), r_j(z1)
            add_cylinder(
                bm_stone,
                Vector((r0 * math.cos(a0), r0 * math.sin(a0), z0)),
                Vector((r1 * math.cos(a0), r1 * math.sin(a0), z1)),
                0.52 * (1.0 - 0.32 * t0),
                0.52 * (1.0 - 0.32 * t1),
                segments=6,
                cap=False,
            )
    for zb in (62.2, 100.6, 124.4, 135.7, 140.0):
        add_cylinder(bm_mosaic if zb >= 120.0 else bm_stone, Vector((0, 0, zb - 0.3)), Vector((0, 0, zb + 0.3)), r_j(zb) + 0.08, r_j(zb) + 0.06, segments=24, cap=False)

    # Glass elevator shaft and walkable decks (runtime contract: 56 m and 136 m stops, r < 2.05 cabin)
    for k in range(16):
        a0 = 2.0 * math.pi * k / 16.0
        # deck ring r 2.25 .. 7.9 (runtime floor r 1.9..7.8; inner edge clear of the r 2.08 glass shaft)
        add_box(bm_stone, (5.075 * math.cos(a0), 5.075 * math.sin(a0), JESUS_BASE - 0.35), (2.5, 5.65, 0.7), rot_euler=(0, 0, a0 + math.pi / 2.0))
        if math.sin(a0) >= -0.75:  # south boarding doorway stays open
            add_box(bm_gold, (2.3 * math.cos(a0), 2.3 * math.sin(a0), JESUS_BASE + 0.55), (0.95, 0.09, 1.05), rot_euler=(0, 0, a0 + math.pi / 2.0))
    for z_ring in (JESUS_BASE + 0.06, JESUS_GALLERY + 0.06):
        for k in range(12):
            a0 = 2.0 * math.pi * k / 12.0
            add_box(bm_gold, (2.15 * math.cos(a0), 2.15 * math.sin(a0), z_ring), (1.15, 0.22, 0.14), rot_euler=(0, 0, a0 + math.pi / 2.0))
    for k in range(6):
        ang = 2.0 * math.pi * k / 6.0
        add_cylinder(bm_gold, Vector((2.15 * math.cos(ang), 2.15 * math.sin(ang), JESUS_BASE - 0.2)), Vector((2.15 * math.cos(ang), 2.15 * math.sin(ang), JESUS_BODY_TOP)), 0.09, 0.09, segments=6)
    add_cylinder(bm_glass, Vector((0, 0, JESUS_BASE)), Vector((0, 0, JESUS_GALLERY + 4.5)), 2.08, 2.08, segments=16, cap=False)

    # 136 m viewpoint deck (annulus r 2.18..6.8) with its low balcony railing outside the loggia
    # Stair well: over the last part of the helix (treads less than 3.2 m below the deck, where a
    # climber's head would hit the 1.1 m slab) the deck keeps only its outer part beyond the stair ring.
    js = T_JESUS["stair"]
    j_sgn = 1.0 if js["clockwise"] else -1.0
    j_pitch = 10.0 / js["turnsPer10m"]
    j_top = math.radians(js["phaseDeg"]) + j_sgn * 2.0 * math.pi * (js["z1"] - js["z0"]) / j_pitch
    j_well = 2.0 * math.pi * 3.2 / j_pitch
    for k in range(24):
        a0 = 2.0 * math.pi * k / 24.0
        back = ((j_top - a0) * j_sgn) % (2.0 * math.pi)   # how far the helix still has to turn to reach the top
        if back < j_well or back > 2.0 * math.pi - math.radians(12.0):
            r_in, r_out = js["rOuter"], 6.8
        else:
            r_in, r_out = 2.18, 6.8
        rc = 0.5 * (r_in + r_out)
        add_box(bm_stone, (rc * math.cos(a0), rc * math.sin(a0), JESUS_GALLERY - 0.55), (1.95 * rc / 4.5, r_out - r_in, 1.1), rot_euler=(0, 0, a0 + math.pi / 2.0))
    for k in range(16):
        am = 2.0 * math.pi * (k + 0.5) / 16.0
        add_box(bm_stone, (6.5 * math.cos(am), 6.5 * math.sin(am), JESUS_GALLERY + 0.14), (2.55, 0.32, 0.28), rot_euler=(0, 0, am - math.pi / 2.0))
        add_box(bm_stone, (6.5 * math.cos(am), 6.5 * math.sin(am), JESUS_GALLERY + 0.88), (2.55, 0.30, 0.14), rot_euler=(0, 0, am - math.pi / 2.0))
        add_cylinder(bm_stone, Vector((6.5 * math.cos(am), 6.5 * math.sin(am), JESUS_GALLERY + 0.26)), Vector((6.5 * math.cos(am), 6.5 * math.sin(am), JESUS_GALLERY + 0.84)), 0.08, 0.07, segments=6)

    # Terminal 142.5..155.65 m: tapering stone crown, white glazed ceramic and trencadís ornaments
    rt = r_j(JESUS_BODY_TOP)
    add_lathe(bm_stone, 0.0, 0.0, [(JESUS_BODY_TOP - 0.4, rt + 0.1), (JESUS_BODY_TOP + 0.8, rt + 0.35), (JESUS_BODY_TOP + 1.6, rt + 0.1),
                                   (147.5, 4.55), (151.5, 3.75), (JESUS_CROSS_BASE + 0.1, 3.3)], segments=24, cap_top=True)
    # upper terminal in white glazed ceramic, trencadís band at its foot
    add_lathe(bm_ceramic, 0.0, 0.0, [(147.2, 4.68), (151.5, 3.83), (JESUS_CROSS_BASE + 0.15, 3.38)], segments=24)
    add_lathe(bm_mosaic, 0.0, 0.0, [(145.2, 5.05), (146.4, 4.85), (147.3, 4.67)], segments=24)
    # eight small trencadís pinnacles standing proud around the foot of the terminal
    for k in range(8):
        a = 2.0 * math.pi * (k + 0.5) / 8
        p0 = Vector((5.75 * math.cos(a), 5.75 * math.sin(a), JESUS_BODY_TOP + 0.9))
        p1 = Vector((5.45 * math.cos(a), 5.45 * math.sin(a), JESUS_BODY_TOP + 6.0))
        add_cylinder(bm_mosaic, p0, p1, 0.5, 0.06, segments=6, cap=True)

    # Four-armed three-dimensional cross, 16.85 m x 13.5 m (glass + white glazed ceramic)
    add_jesus_cross(bm_cross, bm_gold, JESUS_CROSS_BASE, JESUS_TOP)


# ───────────────────────────── Tower of the Virgin Mary ─────────────────────────────

def add_mary_tower(bm_stone, bm_lantern, bm_iron, bm_star) -> None:
    """Tower of the Virgin Mary (138 m) over the apse: paraboloid stone shaft with its many small
    windows to 108.5 m, 6 m crown with twelve iron stars, 18 m lantern and the 7.5 m star."""
    cx, cy = T_MARY["x"], T_MARY["y"]          # (0, 23.25) = APSE_CENTER
    r_base = T_MARY["rRef"]                     # 8.75 at zRef 52
    # paraboloid through r(52) = 8.75 with its vertex at zApex 140.0 m -> r(108.5) = 5.24
    r_m = paraboloid_radius(r_base, MARY_BASE, T_MARY["zApex"])
    sectors = 24
    md0, md1 = MARY_DOOR_Z
    zs = _ring_heights(MARY_BASE, MARY_CROWN, 2.1, [62.0, md0, md1])

    def kind_m(row, k, z_lo, z_hi, ang):
        zm = 0.5 * (z_lo + z_hi)
        if z_lo < md1 and z_hi > md0 and math.radians(232) <= ang <= math.radians(308):
            return "open"  # 77 m doorway (skybridge from the Jesus tower)
        if zm < 62.0 or zm > MARY_CROWN - 1.2:
            return "solid"
        return "open" if (k + 2 * row) % 4 == 0 else "solid"

    add_tower_shell(bm_stone, cx, cy, zs, r_m, sectors, kind_m, thickness=0.32)
    for k in range(12):
        a0 = 2.0 * math.pi * k / 12
        n = 12
        for si in range(n):
            z0 = MARY_BASE + (MARY_CROWN - MARY_BASE) * si / n
            z1 = MARY_BASE + (MARY_CROWN - MARY_BASE) * (si + 1) / n
            if k == 9 and z0 < md1 + 0.5 and z1 > md0 - 0.5:
                continue
            r0, r1 = r_m(z0), r_m(z1)
            add_cylinder(bm_stone, Vector((cx + r0 * math.cos(a0), cy + r0 * math.sin(a0), z0)), Vector((cx + r1 * math.cos(a0), cy + r1 * math.sin(a0), z1)),
                         0.40 * (1.0 - 0.3 * si / n), 0.40 * (1.0 - 0.3 * (si + 1) / n), segments=6, cap=False)
    # the stone crown is re-seated on the wider shaft (designed for r 4.55 at 108.5 m)
    z_star = add_mary_terminal(bm_stone, bm_lantern, bm_iron, bm_star, cx, cy, MARY_CROWN, crown_scale=r_m(MARY_CROWN) / 4.55)
    add_star_12_points(bm_star, Vector((cx, cy, z_star)), radius=3.75)


# ───────────────────────────── Evangelist towers ─────────────────────────────

EVANGELIST_FIGURE = {"tower.mark": "lion", "tower.luke": "ox", "tower.matthew": "angel", "tower.john": "eagle"}


def add_evangelist_tower(bm_stone, bm_marble, bm_mosaic, bm_gold, tw: dict) -> None:
    """Evangelist tower (135 m): paraboloid body 45..112.5 m with pointed windows (mostly solid stone),
    22.5 m pinnacle with icosahedron, hyperboloid, wings, book and tetramorph figure."""
    cx, cy = tw["x"], tw["y"]
    angle_out = math.atan2(cy, cx)
    kind = EVANGELIST_FIGURE[tw["key"]]
    r0 = tw["rRef"]  # 5.5 at zRef 45
    # paraboloid through r(45) = 5.5 with its vertex at zApex 146.2 m
    r_e = paraboloid_radius(r0, tw["zRef"], tw["zApex"])
    inward = math.atan2(-cy, -cx) % (2.0 * math.pi)
    sectors = 18
    zs = _ring_heights(EVANG_BASE, EVANG_BODY_TOP, 2.0, [55.7, 60.3, 62.0])
    row0 = zs.index(62.0)

    def kind_e(row, k, z_lo, z_hi, ang):
        zm = 0.5 * (z_lo + z_hi)
        if 55.7 <= zm <= 60.3:
            return "open" if _angle_diff(ang, inward) < math.radians(50) else "solid"  # 56 m bridge door
        if zm < 62.0 or zm > EVANG_BODY_TOP - 1.0:
            return "solid"
        rr = row - row0
        return "open" if _paraboloid_window(rr % 3, k, rr // 3, 6) else "solid"

    add_tower_shell(bm_stone, cx, cy, zs, r_e, sectors, kind_e, thickness=0.26)
    for k in range(0, sectors, 2):
        a0 = 2.0 * math.pi * k / sectors
        n = 10
        for si in range(n):
            z0 = 55.0 + (EVANG_BODY_TOP - 55.0) * si / n
            z1 = 55.0 + (EVANG_BODY_TOP - 55.0) * (si + 1) / n
            if z0 < 60.5 and _angle_diff(a0, inward) < math.radians(40):
                continue
            r0_, r1_ = r_e(z0), r_e(z1)
            add_cylinder(bm_stone, Vector((cx + r0_ * math.cos(a0), cy + r0_ * math.sin(a0), z0)), Vector((cx + r1_ * math.cos(a0), cy + r1_ * math.sin(a0), z1)),
                         0.30 * (1.0 - 0.3 * si / n), 0.30 * (1.0 - 0.3 * (si + 1) / n), segments=6, cap=False)
    # Stone rim under the 114 m viewpoint deck
    rt = r_e(EVANG_BODY_TOP)
    add_cylinder(bm_stone, Vector((cx, cy, EVANG_BODY_TOP - 0.5)), Vector((cx, cy, 113.25)), rt + 0.1, rt + 0.1, segments=sectors, cap=False)
    add_evangelist_terminal(bm_marble, bm_mosaic, bm_gold, cx, cy, EVANG_BODY_TOP, angle_out, kind)


# ───────────────────────────── Build ─────────────────────────────

def build_towers() -> None:
    reset_scene()
    mats = get_materials()
    # Venetian-glass trencadís of the apostle pinnacles (shares the trencadís textures) and the white /
    # blue trencadís of the Mary lantern
    mat_venetian = mats["trencadis"]
    mat_marian = make_pbr_material(
        "Mat_TrencadisMarian",
        normal_tex="trencadis_normal.png",
        rough_tex="trencadis_roughness.png",
        base_color=(0.80, 0.87, 0.97, 1.0),
        normal_strength=1.0,
        coat_weight=0.65,
        coat_roughness=0.12,
    )

    bm_nativity_stone = bmesh.new()
    bm_passion_stone = bmesh.new()
    bm_warm_stone = bmesh.new()
    bm_internal_stairs = bmesh.new()
    bm_internal_rails = bmesh.new()
    bm_roof_stairs = bmesh.new()
    bm_mosaic = bmesh.new()
    bm_lantern = bmesh.new()
    bm_gold = bmesh.new()
    bm_letters = bmesh.new()
    bm_marble = bmesh.new()
    bm_star = bmesh.new()
    bm_cross = bmesh.new()
    bm_glass = bmesh.new()
    bm_ceramic = bmesh.new()
    pinnacle_meshes = build_apostle_pinnacle_meshes(mats, mat_venetian)

    # ── 1. Tower of Jesus Christ + its helical stair (56..136 m) ──
    add_jesus_christ_tower(bm_warm_stone, bm_mosaic, bm_gold, bm_cross, bm_glass, bm_ceramic)
    add_stair_from_layout(bm_internal_stairs, bm_internal_rails, T_JESUS, step_rise=0.34)

    # ── 2. Tower of the Virgin Mary over the apse + stair (77..118 m) ──
    add_mary_tower(bm_warm_stone, bm_lantern, bm_gold, bm_star)
    add_stair_from_layout(bm_internal_stairs, bm_internal_rails, T_MARY, step_rise=0.34)
    # 77 m entry ring r 1.70..4.10 about the Mary axis (top at Z_MARY_ENTRY, underside 76.6)
    mx, my = T_MARY["x"], T_MARY["y"]
    r_ring = 0.5 * (MARY_RING_R[0] + MARY_RING_R[1])
    for k in range(16):
        a0 = 2.0 * math.pi * k / 16.0
        add_box(bm_warm_stone, (mx + r_ring * math.cos(a0), my + r_ring * math.sin(a0), Z_MARY_ENTRY - MARY_RING_THICKNESS * 0.5),
                (1.62, MARY_RING_R[1] - MARY_RING_R[0], MARY_RING_THICKNESS), rot_euler=(0.0, 0.0, a0 + math.pi * 0.5))

    # ── 3. Evangelist towers at (±11.5, ±11.5) + stairs (56..114 m) ──
    for tw in EVANGELISTS:
        add_evangelist_tower(bm_warm_stone, bm_marble, bm_mosaic, bm_gold, tw)
        add_stair_from_layout(bm_internal_stairs, bm_internal_rails, tw, step_rise=0.36)
        # 114 m deck inside each Evangelist pinnacle (runtime r <= 2.75)
        add_cylinder(bm_warm_stone, Vector((tw["x"], tw["y"], Z_EVANGELIST_DECK - 0.7)), Vector((tw["x"], tw["y"], Z_EVANGELIST_DECK)), 2.65, 2.65, segments=12, cap=True)

    # ── 4.-6. Twelve apostle towers (layout.TOWERS: Nativity S->N, Passion S->N, Glory W->E) ──
    family_bm = {"nativity": bm_nativity_stone, "passion": bm_passion_stone, "glory": bm_warm_stone}
    for idx, tw in enumerate(APOSTLES):
        fi = idx % 4
        add_apostle_tower(family_bm[tw["family"]], bm_mosaic, bm_letters, tw, pinnacle_meshes, idx)
        rise = 0.30 if (tw["family"] != "glory" and fi == 1) else 0.34
        top_ang = add_stair_from_layout(bm_internal_stairs, bm_internal_rails, tw, step_rise=rise)
        if STAIR_TOP_LANDINGS:
            s = tw["stair"]
            add_top_landing(bm_internal_stairs, tw["x"], tw["y"], s["z1"], s["rOuter"], top_ang, s["clockwise"])

    # ── 7. Walkable network from layout.WALK_BRIDGES (deck top on the segment z0..z1, half width) ──
    def bridge_bm(name: str):
        if "nativity" in name or name == "roof.east":
            return bm_nativity_stone
        if "passion" in name or name == "roof.west":
            return bm_passion_stone
        return bm_warm_stone

    stair_rings = [(t["x"], t["y"], t["stair"]["rOuter"], t["stair"]["z0"], t["stair"]["z1"]) for t in TOWERS]

    def ring_overlap(x: float, y: float, z: float, dx: float, dy: float) -> float:
        """Length of the bridge (pointing (dx, dy) away from its end at (x, y)) that lies inside a tower
        stair ring at this level: that part of the deck is the stair's landing, kept non-collidable so a
        climber passing beneath it on the helix does not hit the slab edge."""
        best = 0.0
        for cx, cy, ro, z0, z1 in stair_rings:
            if not (z0 - 1.0 <= z <= z1 + 1.0):
                continue
            px, py = x - cx, y - cy
            if math.hypot(px, py) >= ro:
                continue
            # solve |p + s*d| = ro for s >= 0
            bq = px * dx + py * dy
            cq = px * px + py * py - ro * ro
            best = max(best, -bq + math.sqrt(max(0.0, bq * bq - cq)))
        return best

    def add_walk_bridge(bm, b: dict, parapet_h: float = 1.15, deck_t: float = 0.7, parapets: bool = True,
                        trim0: float = 0.0, trim1: float = 0.0, gaps=(), ext0: float = 0.1, ext1: float = 0.1, bm_stairs=None) -> None:
        """Straight walk segment: deck top on the line (x0,y0,z0)->(x1,y1,z1), width 2*halfWidth.
        Level: one slab (deck_t thick) + parapets; sloped: stepped treads (into bm_stairs) + parapets.
        trim0/trim1 shorten the parapets at the ends (stair rings / decks), gaps = [(side, s0, s1)]
        leaves parapet openings (side +1 = left of the direction of travel, s along the axis in m).
        The slab inside a tower stair ring goes to the non-collidable Towers_RoofStairs mesh."""
        p0 = Vector((b["x0"], b["y0"], b["z0"]))
        p1 = Vector((b["x1"], b["y1"], b["z1"]))
        width = 2.0 * b["halfWidth"]
        delta = p1 - p0
        horiz = math.hypot(delta.x, delta.y)
        ang = math.atan2(delta.y, delta.x)
        dz = delta.z
        d2 = Vector((math.cos(ang), math.sin(ang), 0.0))
        nrm = Vector((-math.sin(ang), math.cos(ang), 0.0))

        def parapet_pieces(side: int, s0: float, s1: float):
            lo, hi = max(s0, trim0), min(s1, horiz - trim1)
            cuts = sorted((g0, g1) for sd, g0, g1 in gaps if sd == side)
            out, cur = [], lo
            for g0, g1 in cuts:
                if g0 > cur:
                    out.append((cur, min(g0, hi)))
                cur = max(cur, g1)
            if cur < hi:
                out.append((cur, hi))
            return [(a, c) for a, c in out if c - a > 0.05]

        off = b["halfWidth"] - 0.16
        if abs(dz) < 0.25:
            nc0 = ring_overlap(p0.x, p0.y, p0.z, d2.x, d2.y)
            nc1 = ring_overlap(p1.x, p1.y, p1.z, -d2.x, -d2.y)
            pieces = [(-ext0, nc0, bm_roof_stairs), (nc0, horiz - nc1, bm), (horiz - nc1, horiz + ext1, bm_roof_stairs)]
            for s0, s1, bm_p in pieces:
                if s1 - s0 < 0.02:
                    continue
                mid = p0 + d2 * (0.5 * (s0 + s1))
                add_box(bm_p, (mid.x, mid.y, p0.z - deck_t * 0.5), (s1 - s0, width, deck_t), rot_euler=(0, 0, ang))
            if parapets:
                for side in (-1, 1):
                    for s0, s1 in parapet_pieces(side, 0.0, horiz):
                        pc = p0 + d2 * (0.5 * (s0 + s1)) + nrm * (side * off)
                        add_box(bm, (pc.x, pc.y, p0.z + parapet_h * 0.5), (s1 - s0, 0.28, parapet_h), rot_euler=(0, 0, ang))
        else:
            steps = max(12, int(abs(dz) / 0.36))
            step_len = (horiz / steps) + 0.24
            target_stairs = bm_stairs if bm_stairs is not None else bm
            for si in range(steps):
                t = (si + 0.5) / steps
                pc = p0 + delta * t
                add_box(target_stairs, (pc.x, pc.y, pc.z - 0.28), (step_len, width, 0.56), rot_euler=(0, 0, ang))
            if parapets:
                # one raking parapet slab per side and piece, parallel to the flight (was one box per step)
                slope = dz / horiz
                pitch = math.atan(slope)
                for side in (-1, 1):
                    for s0, s1 in parapet_pieces(side, 0.0, horiz):
                        sm = 0.5 * (s0 + s1)
                        pp = p0 + d2 * sm + nrm * (side * off)
                        zc = p0.z + slope * sm + parapet_h * 0.5
                        add_box(bm, (pp.x, pp.y, zc), ((s1 - s0) * math.sqrt(1.0 + slope * slope), 0.28, parapet_h), rot_euler=(0, -pitch, ang))

    def point_in_gallery(x: float, y: float):
        for x0, y0, x1, y1 in GALLERIES.values():
            if x0 - 1e-6 <= x <= x1 + 1e-6 and y0 - 1e-6 <= y <= y1 + 1e-6:
                return (x0, y0, x1, y1)
        return None

    bridges = {b["name"]: b for b in WALK_BRIDGES}
    roof = [b for b in WALK_BRIDGES if b["name"].startswith("roof.")]

    def roof_gaps(sky: dict):
        """Parapet openings where a roof stair-bridge lands on this skybridge."""
        gaps = []
        p0 = Vector((sky["x0"], sky["y0"], 0.0))
        p1 = Vector((sky["x1"], sky["y1"], 0.0))
        d2 = (p1 - p0).normalized()
        nrm = Vector((-d2.y, d2.x, 0.0))
        for rb in roof:
            e = Vector((rb["x1"], rb["y1"], 0.0))
            s = (e - p0).dot(d2)
            if -0.1 <= s <= (p1 - p0).length + 0.1 and abs((e - p0).dot(nrm)) <= sky["halfWidth"] + 0.05 and abs(rb["z1"] - sky["z0"]) < 0.3:
                side = 1 if (Vector((rb["x0"], rb["y0"], 0.0)) - p0).dot(nrm) > 0 else -1
                gaps.append((side, s - rb["halfWidth"] - 0.1, s + rb["halfWidth"] + 0.1))
        return gaps

    for name, b in bridges.items():
        bm_b = bridge_bm(name)
        if name == "galleryLink":
            continue  # built by the interior package (choir gallery -> tribune at Z_GALLERY)
        if name.startswith("entry."):
            # tribune / south gallery -> start of the apostle stair at Z_GALLERY. The part over the gallery is
            # the interior's floor: start the slab at the gallery edge (no coplanar overlap). Inside the façade
            # doorway and the tower base there is no parapet (walls on both sides).
            g = point_in_gallery(b["x0"], b["y0"])
            bb = dict(b)
            hw = b["halfWidth"]
            if g is not None:
                along_x = abs(b["x1"] - b["x0"]) > abs(b["y1"] - b["y0"])
                if along_x:
                    bb["x0"] = g[2] if b["x1"] > b["x0"] else g[0]
                    lat_c, lat_lo, lat_hi = b["y0"], g[1], g[3]
                else:
                    bb["y0"] = g[1] if b["y1"] < b["y0"] else g[3]
                    lat_c, lat_lo, lat_hi = b["x0"], g[0], g[2]
                # the part of the entry band that the gallery does not cover (outer towers at |y| = 15 sit
                # on the tribune's end line): fill it between the layout start and the gallery edge
                for f0, f1 in ((lat_c - hw, min(lat_c + hw, lat_lo)), (max(lat_c - hw, lat_hi), lat_c + hw)):
                    if f1 - f0 > 0.02:
                        s0, s1 = (b["x0"], bb["x0"]) if along_x else (b["y0"], bb["y0"])
                        ctr_s, len_s = 0.5 * (s0 + s1), abs(s1 - s0)
                        ctr_l = 0.5 * (f0 + f1)
                        if along_x:
                            add_box(bm_b, (ctr_s, ctr_l, b["z0"] - 0.35), (len_s, f1 - f0, 0.7))
                        else:
                            add_box(bm_b, (ctr_l, ctr_s, b["z0"] - 0.35), (f1 - f0, len_s, 0.7))
            add_walk_bridge(bm_b, bb, parapets=False, ext0=0.0, ext1=0.15)
        elif name.startswith("sky."):
            add_walk_bridge(bm_b, b, trim0=0.4, trim1=0.4, gaps=roof_gaps(b))
        elif name.startswith("evangelist."):
            add_walk_bridge(bm_b, b, trim0=0.8, trim1=0.4)
        elif name == "mary":
            # Jesus stair ring (r <= 4.15) at the start, Mary ring (r <= 4.10) at the end stay free of parapets
            add_walk_bridge(bm_b, b, deck_t=MARY_RING_THICKNESS, trim0=1.3, trim1=1.6)
        elif name.startswith("roof."):
            # parapets start beyond the 56 m deck (r 7.8) and stop at the skybridge's own parapet line
            trim1 = 0.0
            e = Vector((b["x1"], b["y1"], 0.0))
            for sky in WALK_BRIDGES:
                if not sky["name"].startswith("sky.") or abs(sky["z0"] - b["z1"]) > 0.3:
                    continue
                q0 = Vector((sky["x0"], sky["y0"], 0.0))
                dd = (Vector((sky["x1"], sky["y1"], 0.0)) - q0).normalized()
                dist = abs((e - q0).dot(Vector((-dd.y, dd.x, 0.0))))
                if dist <= sky["halfWidth"]:
                    trim1 = max(trim1, sky["halfWidth"] - dist)
            add_walk_bridge(bm_b, b, trim0=1.0, trim1=trim1, bm_stairs=bm_roof_stairs)
        else:
            print(f"[towers] walk bridge {name} not built here")

    # 118 m deck inside the Mary lantern base (runtime r <= 3.75)
    # (a drum from the crown top so it does not float; open underneath for the stair)
    add_lathe(bm_warm_stone, mx, my, [(MARY_CROWN + 6.3, 3.65), (Z_MARY_DECK, 3.65)], segments=14, cap_top=True)

    # Cylindrical UVs around each tower axis for the curved stone shells (no box-projection banding)
    axes = [(T_JESUS["x"], T_JESUS["y"], 11.5), (mx, my, T_MARY["rRef"] * 1.25)]
    axes += [(t["x"], t["y"], t["rRef"] * 1.27) for t in EVANGELISTS]
    axes += [(t["x"], t["y"], 5.2) for t in APOSTLES]
    for bm_, sc in ((bm_nativity_stone, 0.14), (bm_passion_stone, 0.14), (bm_warm_stone, 0.12), (bm_ceramic, 0.2), (bm_mosaic, 0.35), (bm_lantern, 0.35)):
        bmesh.ops.recalc_face_normals(bm_, faces=bm_.faces)
        bm_.normal_update()
        apply_tower_uv(bm_, axes, sc)
    bmesh.ops.recalc_face_normals(bm_internal_stairs, faces=bm_internal_stairs.faces)

    finalize_bmesh_object(bm_nativity_stone, "Towers_Nativity", mats["nativity_stone"], smooth=True, auto_uv=False, weathering=0.4, ao_vert_limit=120000)
    finalize_bmesh_object(bm_passion_stone, "Towers_Passion", mats["passion_stone"], smooth=True, auto_uv=False)
    finalize_bmesh_object(bm_warm_stone, "Towers_CentralAndGlory", mats["sandstone_warm"], smooth=True, auto_uv=False, ao_vert_limit=120000)
    finalize_bmesh_object(bm_ceramic, "Towers_CentralAndGlory_Ceramic", mats["white_marble"], smooth=True, auto_uv=False)
    finalize_bmesh_object(bm_internal_stairs, "Towers_InternalStaircases", mats["sandstone_warm"], smooth=False, uv_scale=0.16, bake_ao=False)
    finalize_bmesh_object(bm_internal_rails, "Towers_InternalStairRails", mats["gold_accent"], smooth=True, uv_scale=0.35, bake_ao=False)
    finalize_bmesh_object(bm_roof_stairs, "Towers_RoofStairs", mats["sandstone_warm"], smooth=False, uv_scale=0.16, bake_ao=False)
    finalize_bmesh_object(bm_mosaic, "Towers_TrencadisPinnacles", mats["trencadis"], smooth=True, auto_uv=False)
    finalize_bmesh_object(bm_lantern, "Towers_TrencadisPinnacles_MaryLantern", mat_marian, smooth=True, auto_uv=False)
    finalize_bmesh_object(bm_gold, "Towers_GoldAccents", mats["gold_accent"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_letters, "Towers_GoldAccents_SanctusLettering", mats["gold_accent"], smooth=False, uv_scale=0.35, bake_ao=False)
    finalize_bmesh_object(bm_marble, "Towers_EvangelistSculptures", mats["white_marble"], smooth=True, uv_scale=0.25)
    finalize_bmesh_object(bm_star, "Tower_MaryStar", mats["luminous_star"], smooth=False, uv_scale=0.35)
    finalize_bmesh_object(bm_cross, "Tower_JesusCross", mats["luminous_cross"], smooth=False, uv_scale=0.25)
    finalize_bmesh_object(bm_glass, "Tower_JesusElevatorShaftGlass", mats["glass_case"], smooth=True, uv_scale=0.25, bake_ao=False)

    export_glb(os.path.join(MODEL_DIR, "towers.glb"))


if __name__ == "__main__":
    build_towers()
