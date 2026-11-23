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
Plan positions and the walkable interiors (stairs, decks, doorways, bridges) are addressed by
coordinates in src/scene/CollisionSystem.ts, JesusElevator.ts and teleports.ts and are kept unchanged.
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


# ── Heights (m) ──
JESUS_BASE = 56.0          # crossing gallery deck (runtime contract)
JESUS_GALLERY = 136.0      # viewpoint deck (runtime contract: JesusElevator top stop, teleport)
JESUS_BODY_TOP = 142.5     # top of the stone body, 12th level of panels (sagradafamilia.org)
JESUS_CROSS_BASE = 155.65  # 172.5 - 16.85 (lower arm 7.25 + core 4.7 + upper arm 4.9)
JESUS_TOP = 172.5          # sagradafamilia.org
MARY_BASE = 52.0
MARY_CROWN = 108.5         # 6 m stone crown 108.5..114.5, 18 m lantern 114.85..132.5, star 130.5..138
MARY_TOP = 138.0
EVANG_BASE = 45.0          # "from the vaults at 45 m" (sagradafamilia.org)
EVANG_BODY_TOP = 112.5     # main body top; 22.5 m pinnacle to 135 m
EVANG_TOP = 135.0
APOSTLE_PIN_SHARE = 0.20   # pinnacle share of the overall apostle-tower height (estimate)


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

def add_apostle_tower(
    bm_stone: bmesh.types.BMesh,
    bm_mosaic: bmesh.types.BMesh,
    bm_letters: bmesh.types.BMesh,
    cx: float,
    cy: float,
    z_ref0: float,
    z_top: float,
    r0: float,
    family: str,
    pinnacle_meshes: list,
    tower_idx: int,
) -> None:
    """Parabolic apostle bell tower: paraboloid envelope whose vertex is the pinnacle tip, lower section
    square (Nativity) / elliptical (Passion) blending into the round shaft, 8 vertical ribs with helical
    bands of louvred openings between them, SANCTUS lettering climbing in a helix, HOSANNA EXCELSIS
    trencadís collar and the instanced ~20 % pinnacle."""
    is_glory = family == "glory"
    skybridge_z = 72.0 if is_glory else 65.0
    pin_h = APOSTLE_PIN_SHARE * z_top
    z_neck = z_top - pin_h
    z_apex = z_top + 1.5
    r_of_z = paraboloid_radius(r0, z_ref0, z_apex)
    z_shell0 = 18.6  # tower-base gallery doorway 14.5..18.6 m stays open (runtime walkway)
    z_fade = z_ref0 + 20.0

    def section(z: float, ang: float) -> float:
        w = max(0.0, min(1.0, (z_fade - z) / (z_fade - z_ref0)))
        if w <= 0.0:
            return 1.0
        if family == "nativity":
            # square base turning round with height (axes along / across the façade)
            return 1.0 + (superellipse_gain(ang, 4.0) - 1.0) * w
        if family == "passion":
            # elliptical plan, long axis along the façade (Blender Y)
            return 1.0 + 0.14 * w * math.sin(ang) ** 2
        return 1.0 + (superellipse_gain(ang, 3.0) - 1.0) * w * 0.6

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

    sectors = 16
    zs = _ring_heights(z_shell0, z_neck, 2.3, [z_ref0, skybridge_z - 0.3, skybridge_z + 3.4])
    add_tower_shell(bm_stone, cx, cy, zs, r_of_z, sectors, cell_kind, thickness=0.26, louvres=2, section=section)

    # Vertical ribs on every second sector boundary, following the section
    for k in range(0, sectors, 2):
        ang = 2.0 * math.pi * k / sectors
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
) -> None:
    """Continuous overlapping helical stone staircase (matches TOWER_STAIR_SHAFTS in CollisionSystem.ts)."""
    span = max(2.0, z1 - z0)
    steps = max(18, int(span / step_rise))
    turns = (span / 10.0) * turns_per_10m
    sgn = 1.0 if clockwise else -1.0
    r_rail = max(0.55, r_mid - tread_w * 0.45)

    for si in range(steps):
        t = si / max(1, steps - 1)
        ang = sgn * t * turns * 2.0 * math.pi
        z = z0 + t * span
        sx = cx + r_mid * math.cos(ang)
        sy = cy + r_mid * math.sin(ang)
        add_box(bm_stone, (sx, sy, z), (tread_w, 0.68, 0.24), rot_euler=(0.0, 0.0, ang))
        if si < steps - 1 and si % 3 == 0:
            t_n = min(1.0, (si + 3) / max(1, steps - 1))
            ang_n = sgn * t_n * turns * 2.0 * math.pi
            z_n = z0 + t_n * span
            p0 = Vector((cx + r_rail * math.cos(ang), cy + r_rail * math.sin(ang), z + 0.92))
            p1 = Vector((cx + r_rail * math.cos(ang_n), cy + r_rail * math.sin(ang_n), z_n + 0.92))
            add_cylinder(bm_gold, p0, p1, 0.05, 0.05, segments=5, cap=False)


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
    r_base = 9.5
    # paraboloid through r(56) = 9.5 and r(142.5) = 5.4  ->  vertex at 183.8 m
    r_j = paraboloid_radius(r_base, JESUS_BASE, 183.8)
    ribs = 12
    sectors = 24
    zs = _ring_heights(JESUS_BASE, JESUS_BODY_TOP, 2.05, [62.0, 73.5, 81.5, 135.9, 139.8])
    row_of = {z: i for i, z in enumerate(zs)}

    def kind_j(row, k, z_lo, z_hi, ang):
        zm = 0.5 * (z_lo + z_hi)
        if zm < 62.0:
            return "open"  # colonnade over the crossing gallery (8 roof bridges)
        if 73.5 <= zm <= 81.5 and math.radians(58) <= ang <= math.radians(122):
            return "open"  # 76 m doorway to the Mary skybridge
        if 135.9 <= zm <= 139.8:
            return "open"  # 136 m loggia
        if zm > 140.5:
            return "solid"
        rr = row - row_of.get(62.0, 0)
        return "open" if _paraboloid_window(rr % 3, k, rr // 3, 6) else "solid"

    add_tower_shell(bm_stone, 0.0, 0.0, zs, r_j, sectors, kind_j, thickness=0.36)
    for k in range(ribs):
        a0 = 2.0 * math.pi * k / ribs
        n = 16
        for si in range(n):
            z0 = JESUS_BASE + (JESUS_BODY_TOP - JESUS_BASE) * si / n
            z1 = JESUS_BASE + (JESUS_BODY_TOP - JESUS_BASE) * (si + 1) / n
            if k == 3 and z0 < 81.5 and z1 > 73.5:
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
        add_box(bm_stone, (5.2 * math.cos(a0), 5.2 * math.sin(a0), JESUS_BASE - 0.35), (2.5, 5.4, 0.7), rot_euler=(0, 0, a0 + math.pi / 2.0))
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
    for k in range(24):
        a0 = 2.0 * math.pi * k / 24.0
        add_box(bm_stone, (4.5 * math.cos(a0), 4.5 * math.sin(a0), JESUS_GALLERY - 0.55), (1.95, 4.65, 1.1), rot_euler=(0, 0, a0 + math.pi / 2.0))
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
    cx, cy = 0.0, 22.5
    r_base = 7.6
    # paraboloid through r(52) = 7.6 and r(108.5) = 4.55 -> vertex at 140.0 m
    r_m = paraboloid_radius(r_base, MARY_BASE, 140.0)
    sectors = 24
    zs = _ring_heights(MARY_BASE, MARY_CROWN, 2.1, [62.0, 75.0, 80.5])

    def kind_m(row, k, z_lo, z_hi, ang):
        zm = 0.5 * (z_lo + z_hi)
        if z_lo < 80.5 and z_hi > 75.0 and math.radians(232) <= ang <= math.radians(308):
            return "open"  # 76 m doorway (skybridge from the Jesus tower)
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
            if k == 9 and z0 < 81.0 and z1 > 74.5:
                continue
            r0, r1 = r_m(z0), r_m(z1)
            add_cylinder(bm_stone, Vector((cx + r0 * math.cos(a0), cy + r0 * math.sin(a0), z0)), Vector((cx + r1 * math.cos(a0), cy + r1 * math.sin(a0), z1)),
                         0.40 * (1.0 - 0.3 * si / n), 0.40 * (1.0 - 0.3 * (si + 1) / n), segments=6, cap=False)
    z_star = add_mary_terminal(bm_stone, bm_lantern, bm_iron, bm_star, cx, cy, MARY_CROWN)
    add_star_12_points(bm_star, Vector((cx, cy, z_star)), radius=3.75)


# ───────────────────────────── Evangelist towers ─────────────────────────────

def add_evangelist_tower(bm_stone, bm_marble, bm_mosaic, bm_gold, cx: float, cy: float, angle_out: float, kind: str) -> None:
    """Evangelist tower (135 m): paraboloid body 45..112.5 m with pointed windows (mostly solid stone),
    22.5 m pinnacle with icosahedron, hyperboloid, wings, book and tetramorph figure."""
    r0 = 5.2
    # paraboloid through r(45) = 5.2 and r(112.5) = 3.0 -> vertex at 146.2 m
    r_e = paraboloid_radius(r0, EVANG_BASE, 146.2)
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
    add_spiral_stair_shaft(bm_internal_stairs, bm_internal_rails, 0.0, 0.0, 56.0, 136.0, r_mid=3.25, tread_w=1.55, turns_per_10m=1.1, step_rise=0.34, clockwise=True)

    # ── 2. Tower of the Virgin Mary over the apse + stair (76..118 m) ──
    add_mary_tower(bm_warm_stone, bm_lantern, bm_gold, bm_star)
    add_spiral_stair_shaft(bm_internal_stairs, bm_internal_rails, 0.0, 22.5, 76.0, 118.0, r_mid=2.45, tread_w=1.25, turns_per_10m=1.25, step_rise=0.34)
    for k in range(16):
        a0 = 2.0 * math.pi * k / 16.0
        add_box(bm_warm_stone, (2.90 * math.cos(a0), 22.5 + 2.90 * math.sin(a0), 75.65), (1.60, 2.20, 0.70), rot_euler=(0.0, 0.0, a0 + math.pi * 0.5))

    # ── 3. Evangelist towers at (±11.5, ±11.5) + stairs (56..114 m) ──
    for sx in (-1, 1):
        for sy in (-1, 1):
            ang = math.atan2(sy, sx)
            # Blender (x, y) -> CollisionSystem names: (-,-) Mark, (-,+) Luke, (+,-) Matthew, (+,+) John
            kind = {(-1, -1): "lion", (-1, 1): "ox", (1, -1): "angel", (1, 1): "eagle"}[(sx, sy)]
            add_evangelist_tower(bm_warm_stone, bm_marble, bm_mosaic, bm_gold, sx * 11.5, sy * 11.5, ang, kind)
            add_spiral_stair_shaft(bm_internal_stairs, bm_internal_rails, sx * 11.5, sy * 11.5, 56.0, 114.0, r_mid=1.68, tread_w=1.04, turns_per_10m=1.35, step_rise=0.36, clockwise=(sx * sy > 0))

    # ── 4.-6. Twelve apostle towers (positions are runtime contracts) ──
    # (cx, cy, overall height, radius at the reference level)
    nativity_specs = [(31.5, -10.8, 98.4, 3.55), (31.5, -3.6, 107.0, 3.85), (31.5, 3.6, 107.0, 3.85), (31.5, 10.8, 98.4, 3.55)]
    for idx, (cx, cy, z_top, r_b) in enumerate(nativity_specs):
        add_apostle_tower(bm_nativity_stone, bm_mosaic, bm_letters, cx, cy, 26.0, z_top, r_b, "nativity", pinnacle_meshes, idx)
        add_spiral_stair_shaft(bm_internal_stairs, bm_internal_rails, cx, cy, 14.5, 65.0, r_mid=1.38, tread_w=1.04, turns_per_10m=1.68, step_rise=0.30 if idx == 1 else 0.34, clockwise=(idx % 2 == 1))
    passion_specs = [(-31.5, -10.8, 107.4, 3.65), (-31.5, -3.6, 112.2, 3.95), (-31.5, 3.6, 112.2, 3.95), (-31.5, 10.8, 107.4, 3.65)]
    for idx, (cx, cy, z_top, r_b) in enumerate(passion_specs):
        add_apostle_tower(bm_passion_stone, bm_mosaic, bm_letters, cx, cy, 26.0, z_top, r_b, "passion", pinnacle_meshes, 4 + idx)
        add_spiral_stair_shaft(bm_internal_stairs, bm_internal_rails, cx, cy, 14.5, 65.0, r_mid=1.38, tread_w=1.04, turns_per_10m=1.68, step_rise=0.30 if idx == 1 else 0.34, clockwise=(idx % 2 == 0))
    glory_specs = [(-11.4, -49.5, 112.0, 3.75), (-3.8, -49.5, 120.0, 4.10), (3.8, -49.5, 120.0, 4.10), (11.4, -49.5, 112.0, 3.75)]
    for idx, (cx, cy, z_top, r_b) in enumerate(glory_specs):
        add_apostle_tower(bm_warm_stone, bm_mosaic, bm_letters, cx, cy, 28.0, z_top, r_b, "glory", pinnacle_meshes, 8 + idx)
        add_spiral_stair_shaft(bm_internal_stairs, bm_internal_rails, cx, cy, 14.5, 72.0, r_mid=1.38, tread_w=1.04, turns_per_10m=1.62, step_rise=0.34, clockwise=(idx % 2 == 1))

    # ── 7. Walkable network: tower-base galleries, skybridges, roof stair-bridges, decks (unchanged) ──
    def add_stepped_skybridge(bm, p0: Vector, p1: Vector, width: float = 2.6, parapet_h: float = 1.15, bm_stairs=None) -> None:
        delta = p1 - p0
        horiz = math.hypot(delta.x, delta.y)
        ang = math.atan2(delta.y, delta.x)
        dz = delta.z
        nx = -math.sin(ang)
        ny = math.cos(ang)
        if abs(dz) < 0.25:
            mid = (p0 + p1) * 0.5
            add_box(bm, (mid.x, mid.y, mid.z - 0.35), (horiz + 0.2, width, 0.7), rot_euler=(0, 0, ang))
            for side in (-1, 1):
                ox = nx * side * (width * 0.5 - 0.16)
                oy = ny * side * (width * 0.5 - 0.16)
                add_box(bm, (mid.x + ox, mid.y + oy, mid.z + parapet_h * 0.5), (horiz, 0.28, parapet_h), rot_euler=(0, 0, ang))
        else:
            steps = max(12, int(abs(dz) / 0.36))
            step_len = (horiz / steps) + 0.24
            target_stairs = bm_stairs if bm_stairs is not None else bm
            for si in range(steps):
                t = (si + 0.5) / steps
                sx_ = p0.x + delta.x * t
                sy_ = p0.y + delta.y * t
                sz_ = p0.z + dz * t
                add_box(target_stairs, (sx_, sy_, sz_ - 0.28), (step_len, width, 0.56), rot_euler=(0, 0, ang))
                for side in (-1, 1):
                    ox = nx * side * (width * 0.5 - 0.16)
                    oy = ny * side * (width * 0.5 - 0.16)
                    add_box(bm, (sx_ + ox, sy_ + oy, sz_ + parapet_h * 0.5), (step_len + 0.08, 0.28, parapet_h), rot_euler=(0, 0, ang))

    for tx, bm_side, z_sky in ((31.5, bm_nativity_stone, 65.0), (-31.5, bm_passion_stone, 65.0)):
        for y_a, y_b in ((-8.9, -5.5), (-1.7, 1.7), (5.5, 8.9)):
            add_stepped_skybridge(bm_side, Vector((tx, y_a, 14.5)), Vector((tx, y_b, 14.5)), width=2.6)
            add_stepped_skybridge(bm_side, Vector((tx, y_a, z_sky)), Vector((tx, y_b, z_sky)), width=2.6)
    for x_a, x_b in ((-9.5, -5.7), (-1.9, 1.9), (5.7, 9.5)):
        add_stepped_skybridge(bm_warm_stone, Vector((x_a, -49.5, 14.5)), Vector((x_b, -49.5, 14.5)), width=2.6)
        add_stepped_skybridge(bm_warm_stone, Vector((x_a, -49.5, 72.0)), Vector((x_b, -49.5, 72.0)), width=2.6)
    add_stepped_skybridge(bm_passion_stone, Vector((-21.0, -14.5, 14.5)), Vector((-30.1, -7.2, 14.5)), width=2.6)
    for sx_c in (-7.6, 0.0, 7.6):
        add_stepped_skybridge(bm_warm_stone, Vector((sx_c, -43.5, 14.5)), Vector((sx_c, -48.0, 14.5)), width=2.6)

    for sx in (-1, 1):
        for sy in (-1, 1):
            add_stepped_skybridge(bm_warm_stone, Vector((sx * 5.2, sy * 5.2, 56.0)), Vector((sx * 9.8, sy * 9.8, 56.0)), width=2.4)
            # 114 m deck inside each Evangelist pinnacle (runtime r <= 2.75)
            add_cylinder(bm_warm_stone, Vector((sx * 11.5, sy * 11.5, 113.3)), Vector((sx * 11.5, sy * 11.5, 114.0)), 2.65, 2.65, segments=12, cap=True)

    add_box(bm_warm_stone, (0.0, 11.78, 75.65), (2.6, 15.45, 0.70))
    for side in (-1, 1):
        add_box(bm_warm_stone, (side * 1.15, 11.4, 76.55), (0.28, 13.8, 1.15))
    # 118 m deck inside the Mary lantern base (runtime r <= 3.75)
    # (a drum from the crown top so it does not float; open underneath for the stair)
    add_lathe(bm_warm_stone, 0.0, 22.5, [(MARY_CROWN + 6.3, 3.65), (118.0, 3.65)], segments=14, cap_top=True)

    add_stepped_skybridge(bm_nativity_stone, Vector((7.2, 0.0, 56.0)), Vector((30.1, 0.0, 65.0)), width=2.6, bm_stairs=bm_roof_stairs)
    add_stepped_skybridge(bm_passion_stone, Vector((-7.2, 0.0, 56.0)), Vector((-30.1, 0.0, 65.0)), width=2.6, bm_stairs=bm_roof_stairs)
    add_stepped_skybridge(bm_warm_stone, Vector((0.0, -7.2, 56.0)), Vector((0.0, -48.0, 72.0)), width=2.8, bm_stairs=bm_roof_stairs)

    # Cylindrical UVs around each tower axis for the curved stone shells (no box-projection banding)
    axes = [(0.0, 0.0, 11.5), (0.0, 22.5, 9.5)]
    axes += [(sx * 11.5, sy * 11.5, 6.6) for sx in (-1, 1) for sy in (-1, 1)]
    axes += [(sx * 31.5, y, 5.2) for sx in (-1, 1) for y in (-10.8, -3.6, 3.6, 10.8)]
    axes += [(x, -49.5, 5.2) for x in (-11.4, -3.8, 3.8, 11.4)]
    for bm_, sc in ((bm_nativity_stone, 0.14), (bm_passion_stone, 0.14), (bm_warm_stone, 0.12), (bm_ceramic, 0.2), (bm_mosaic, 0.35), (bm_lantern, 0.35)):
        bmesh.ops.recalc_face_normals(bm_, faces=bm_.faces)
        bm_.normal_update()
        apply_tower_uv(bm_, axes, sc)

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
