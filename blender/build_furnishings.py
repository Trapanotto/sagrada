"""Build rich sacred interior furnishings, votive chapels, chandeliers & Gaudí exhibition for Sagrada Família."""

from __future__ import annotations

import math
import os
import sys
import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
from common import (
    GRID,
    MODEL_DIR,
    Z_ALTAR,
    Z_GALLERY,
    Z_NAVE,
    add_box,
    add_cylinder,
    apply_box_uv,
    bake_bvh_vertex_ao,
    build_gaudi_column_bmesh,
    export_glb,
    finalize_bmesh_object,
    get_materials,
    reset_scene,
    save_candle_anchors,
)
# Plan positions come from the master layout (blender/layout.py); nothing below re-types a plan number.
from layout import (
    ALTAR_POS,
    ALTAR_SIZE,
    APSE_CENTER,
    APSE_CHAPEL_BACK_R,
    APSE_CHAPEL_FRONT_R,
    APSE_PIER_ANGLES_DEG,
    APSE_PRESBYTERY_RING_R,
    CENTRAL_NAVE_HALF,
    COLUMNS,
    COLUMN_FALLBACK_RADIUS,
    CORNER_STAIRS,
    GLORY,
    GLORY_INNER_Y,
    INNER_AISLE_OUTER,
    NATIVITY,
    NAVE_HALF_WIDTH,
    NAVE_WINDOW_BAY_Y,
    PASSION,
    PRESBYTERY_FRONT_Y,
    PRESBYTERY_HALF_WIDTH,
    PRESBYTERY_STEPS,
    PRESBYTERY_TREAD,
    TRANSEPT_HALF_LENGTH,
    Z_CHILDREN_CHOIR,
    Z_JESUS_DECK,
)

APSE_CX, APSE_CY = APSE_CENTER
ALTAR_X, ALTAR_Y = ALTAR_POS
# Derived local placement values (furnishings only; proposed as layout additions in the report)
STALL_RING_R = APSE_PRESBYTERY_RING_R - 2.1        # 5.4: clergy stalls inside the presbytery column ring
CHAPEL_ALTAR_R = APSE_CHAPEL_BACK_R - 1.0          # 18.0: side altars near the back of each apse chapel
ORGAN_R = 0.5 * (APSE_CHAPEL_FRONT_R + APSE_CHAPEL_BACK_R)   # 17.0: organ on the children's choir ring
STEPS_FOOT_Y = PRESBYTERY_FRONT_Y - PRESBYTERY_STEPS * PRESBYTERY_TREAD   # 11.4


def add_statue_silhouette(bm: bmesh.types.BMesh, pos: Vector, scale: float = 1.0, rot_z: float = 0.0) -> None:
    """Classical sculpted white marble Saint/Angel statue silhouette on a carved plinth."""
    ca, sa = math.cos(rot_z), math.sin(rot_z)
    # Plinth base
    add_cylinder(bm, pos, pos + Vector((0, 0, 0.35 * scale)), 0.38 * scale, 0.32 * scale, segments=10)
    # Draped robe torso
    add_cylinder(bm, pos + Vector((0, 0, 0.35 * scale)), pos + Vector((0, 0, 1.45 * scale)), 0.28 * scale, 0.20 * scale, segments=10)
    # Shoulders & cloak
    add_box(bm, (pos.x, pos.y, pos.z + 1.48 * scale), (0.52 * scale, 0.28 * scale, 0.24 * scale), rot_euler=(0, 0, rot_z))
    # Head + subtle halo ring
    add_cylinder(bm, pos + Vector((0, 0, 1.60 * scale)), pos + Vector((0, 0, 1.88 * scale)), 0.14 * scale, 0.12 * scale, segments=10)
    # Sculpted arms slightly raised in blessing
    for side in (-1, 1):
        ox = side * 0.24 * ca * scale
        oy = side * 0.24 * sa * scale
        add_cylinder(
            bm,
            pos + Vector((ox, oy, 1.42 * scale)),
            pos + Vector((ox * 1.15 - sa * 0.18 * scale, oy * 1.15 + ca * 0.18 * scale, 1.24 * scale)),
            0.075 * scale,
            0.06 * scale,
            segments=6,
        )


def add_chandelier(
    bm_iron: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
    bm_glow: bmesh.types.BMesh,
    cx: float,
    cy: float,
    z_hang: float,
    z_top: float,
    radius: float = 1.65,
) -> None:
    """Gaudí modernist wrought-iron and warm amber glass hanging chandelier."""
    # Slender central suspension rod rising up to the vault/branch canopy
    add_cylinder(bm_iron, Vector((cx, cy, z_hang + 0.2)), Vector((cx, cy, z_top)), 0.035, 0.035, segments=6)
    # Central forged finial hub
    add_cylinder(bm_gold, Vector((cx, cy, z_hang - 0.55)), Vector((cx, cy, z_hang + 0.45)), 0.18, 0.12, segments=10)

    # Outer wrought-iron dodecagonal ring + radial spokes + 8 glowing amber glass lanterns
    segs = 12
    for i in range(segs):
        a0 = 2.0 * math.pi * i / segs
        a1 = 2.0 * math.pi * (i + 1) / segs
        p0 = Vector((cx + radius * math.cos(a0), cy + radius * math.sin(a0), z_hang))
        p1 = Vector((cx + radius * math.cos(a1), cy + radius * math.sin(a1), z_hang))
        add_cylinder(bm_iron, p0, p1, 0.055, 0.055, segments=6)
        if i % 2 == 0:
            add_cylinder(bm_iron, Vector((cx, cy, z_hang + 0.35)), p0, 0.035, 0.035, segments=6)
            # Glowing modernist glass lantern & brass crown cap
            add_cylinder(bm_glow, p0 - Vector((0, 0, 0.48)), p0 - Vector((0, 0, 0.05)), 0.14, 0.12, segments=8)
            add_cylinder(bm_gold, p0 - Vector((0, 0, 0.05)), p0 + Vector((0, 0, 0.12)), 0.16, 0.06, segments=8)


def add_confessional(
    bm_oak: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
    bm_glow: bmesh.types.BMesh,
    cx: float,
    cy: float,
    facing_x: float,
) -> None:
    """Carved Catalan oak confessional booth tucked against the outer nave wall."""
    # Main three-compartment oak booth (width along Y = 3.2m, depth along X = 1.4m, height = 3.3m)
    add_box(bm_oak, (cx, cy, Z_NAVE + 1.55), (1.35, 3.1, 3.1))
    # Stepped gothic cornice crown + central pinnacle
    add_box(bm_oak, (cx, cy, Z_NAVE + 3.22), (1.52, 3.3, 0.28))
    add_box(bm_oak, (cx, cy, Z_NAVE + 3.65), (1.15, 1.35, 0.65))
    add_cylinder(bm_gold, Vector((cx, cy, Z_NAVE + 3.95)), Vector((cx, cy, Z_NAVE + 4.55)), 0.06, 0.04, segments=6)
    add_cylinder(bm_gold, Vector((cx, cy - 0.22, Z_NAVE + 4.35)), Vector((cx, cy + 0.22, Z_NAVE + 4.35)), 0.045, 0.045, segments=6)
    # Recessed decorative front pillars + small warm availability lamp above center door
    fx = cx + facing_x * 0.72
    for dy in (-1.45, -0.52, 0.52, 1.45):
        add_cylinder(bm_oak, Vector((fx, cy + dy, Z_NAVE)), Vector((fx, cy + dy, Z_NAVE + 3.15)), 0.09, 0.08, segments=8)
    add_cylinder(bm_glow, Vector((fx + facing_x * 0.08, cy, Z_NAVE + 2.85)), Vector((fx + facing_x * 0.08, cy, Z_NAVE + 3.05)), 0.08, 0.07, segments=8)


def add_holy_water_font(bm_marble: bmesh.types.BMesh, bm_gold: bmesh.types.BMesh, cx: float, cy: float) -> None:
    """Gaudí's iconic giant sculpted clam-shell holy water basin on a curved marble pedestal."""
    add_cylinder(bm_marble, Vector((cx, cy, Z_NAVE)), Vector((cx, cy, Z_NAVE + 0.16)), 0.42, 0.34, segments=10)
    add_cylinder(bm_marble, Vector((cx, cy, Z_NAVE + 0.16)), Vector((cx, cy, Z_NAVE + 0.92)), 0.20, 0.26, segments=10)
    # Flared sculpted tridacna shell bowl
    add_cylinder(bm_marble, Vector((cx, cy, Z_NAVE + 0.90)), Vector((cx, cy, Z_NAVE + 1.22)), 0.28, 0.64, segments=14)
    add_cylinder(bm_gold, Vector((cx, cy, Z_NAVE + 1.20)), Vector((cx, cy, Z_NAVE + 1.25)), 0.65, 0.63, segments=14, cap=False)


def build_furnishings() -> None:
    reset_scene()
    mats = get_materials()

    bm_carpet = bmesh.new()
    bm_oak = bmesh.new()
    bm_marble = bmesh.new()
    bm_porphyry = bmesh.new()
    bm_gold = bmesh.new()
    bm_bronze = bmesh.new()
    bm_iron = bmesh.new()
    bm_glow = bmesh.new()
    bm_glass = bmesh.new()
    candle_anchors: list[tuple[float, float, float, float]] = []

    # ── 1. Royal Crimson & Gold Ceremonial Carpet (Central Nave + Presbytery Sanctuary) ──
    # Long ceremonial runner from the Glory doors to the foot of the presbytery steps (X: -2.1..+2.1)
    run_y0, run_y1 = GLORY_INNER_Y + 0.15, STEPS_FOOT_Y - 0.05
    add_box(bm_carpet, (0.0, 0.5 * (run_y0 + run_y1), Z_NAVE + 0.025), (4.2, run_y1 - run_y0, 0.04))
    # Cross-transept ceremonial runner between the Nativity and Passion doors, meeting at the crossing
    add_box(bm_carpet, (0.0, 0.0, Z_NAVE + 0.028), (2.0 * TRANSEPT_HALF_LENGTH - 2.0, 3.6, 0.04))
    # Presbytery sanctuary carpet on the platform (Z_ALTAR): disc about the altar inside the column ring
    # + a runner from the top step to the altar
    r_disc = APSE_PRESBYTERY_RING_R - 1.1
    add_cylinder(bm_carpet, Vector((ALTAR_X, ALTAR_Y, Z_ALTAR + 0.01)), Vector((ALTAR_X, ALTAR_Y, Z_ALTAR + 0.05)), r_disc, r_disc, segments=28, cap=True)
    pr_y0 = PRESBYTERY_FRONT_Y + 0.1
    add_box(bm_carpet, (ALTAR_X, 0.5 * (pr_y0 + ALTAR_Y), Z_ALTAR + 0.025), (4.2, ALTAR_Y - pr_y0, 0.04))

    # ── 2. Sanctuary Liturgical Furniture (Ambo/Pulpit, Cathedra, Choir Stalls, Altar Rail, Candelabras, Organ Casing) ──
    # 2a. Sculpted Gaudí Ambo / Pulpit on the left front of the presbytery platform (same offset from the altar as before)
    ax, ay = ALTAR_X - 5.6, ALTAR_Y - 4.5
    add_cylinder(bm_marble, Vector((ax, ay, Z_ALTAR)), Vector((ax, ay, Z_ALTAR + 1.25)), 0.58, 0.42, segments=10)
    add_box(bm_marble, (ax, ay, Z_ALTAR + 1.38), (1.15, 0.85, 0.22))
    add_box(bm_gold, (ax, ay - 0.1, Z_ALTAR + 1.56), (0.85, 0.55, 0.10), rot_euler=(-0.35, 0.0, 0.0))

    # 2b. Bishop's Cathedra (Throne) & Semicircular Carved Oak Clergy Choir Stalls behind the High Altar,
    # on a ring about the altar inside the 10 presbytery columns (r 7.5)
    for i in range(9):
        ang = math.pi * (0.18 + 0.64 * i / 8.0)  # Semicircle along North rear of sanctuary
        sx = ALTAR_X + STALL_RING_R * math.cos(ang)
        sy = ALTAR_Y + STALL_RING_R * math.sin(ang)
        rot_z = ang + math.pi * 0.5
        ca, sa = math.cos(ang), math.sin(ang)
        tx, ty = -sa, ca  # Tangent along stall width
        is_cathedra = (i == 4)
        w_s = 1.38 if is_cathedra else 1.02
        h_back = 2.95 if is_cathedra else 2.02

        # Carved wooden base plinth & recessed under-seat panel (instead of solid heavy box!)
        add_box(bm_oak, (sx, sy, Z_ALTAR + 0.06), (w_s, 0.72, 0.12), rot_euler=(0, 0, rot_z))
        add_box(bm_oak, (sx + 0.06 * ca, sy + 0.06 * sa, Z_ALTAR + 0.28), (w_s - 0.14, 0.52, 0.34), rot_euler=(0, 0, rot_z))
        # Contoured seat plank with slight front lip
        add_box(bm_oak, (sx - 0.02 * ca, sy - 0.02 * sa, Z_ALTAR + 0.48), (w_s + 0.04, 0.64, 0.08), rot_euler=(0, 0, rot_z))
        # Sculpted side armrest cheeks & rounded armrests
        for side in (-1, 1):
            ax_s = sx + side * (w_s * 0.46) * tx
            ay_s = sy + side * (w_s * 0.46) * ty
            add_box(bm_oak, (ax_s, ay_s, Z_ALTAR + 0.44), (0.10, 0.68, 0.76), rot_euler=(0, 0, rot_z))
            add_box(bm_oak, (ax_s - 0.04 * ca, ay_s - 0.04 * sa, Z_ALTAR + 0.84), (0.14, 0.74, 0.08), rot_euler=(0, 0, rot_z))
        # Paneled high gothic backrest + flanking stiles + molded cornice cap
        bx = sx + 0.31 * ca
        by = sy + 0.31 * sa
        add_box(bm_oak, (bx, by, Z_ALTAR + h_back * 0.5), (w_s, 0.12, h_back), rot_euler=(0, 0, rot_z))
        add_box(bm_oak, (bx - 0.06 * ca, by - 0.06 * sa, Z_ALTAR + h_back + 0.06), (w_s + 0.12, 0.24, 0.12), rot_euler=(0, 0, rot_z))
        for side in (-1, 1):
            px_s = bx + side * (w_s * 0.46) * tx - 0.05 * ca
            py_s = by + side * (w_s * 0.46) * ty - 0.05 * sa
            add_cylinder(bm_oak, Vector((px_s, py_s, Z_ALTAR + 0.48)), Vector((px_s, py_s, Z_ALTAR + h_back + 0.12)), 0.055, 0.045, segments=8)
            add_cylinder(bm_gold, Vector((px_s, py_s, Z_ALTAR + h_back + 0.12)), Vector((px_s, py_s, Z_ALTAR + h_back + 0.34)), 0.05, 0.015, segments=6)
        if is_cathedra:
            # Grand gilded episcopal canopy crest & cross finial crowning the Bishop's Cathedra
            add_box(bm_oak, (bx - 0.22 * ca, by - 0.22 * sa, Z_ALTAR + h_back + 0.18), (w_s + 0.20, 0.62, 0.14), rot_euler=(0, 0, rot_z))
            add_cylinder(bm_gold, Vector((bx - 0.18 * ca, by - 0.18 * sa, Z_ALTAR + h_back + 0.25)), Vector((bx - 0.18 * ca, by - 0.18 * sa, Z_ALTAR + h_back + 1.05)), 0.12, 0.025, segments=8)
            add_cylinder(bm_gold, Vector((bx - 0.18 * ca - 0.18 * tx, by - 0.18 * sa - 0.18 * ty, Z_ALTAR + h_back + 0.80)), Vector((bx - 0.18 * ca + 0.18 * tx, by - 0.18 * sa + 0.18 * ty, Z_ALTAR + h_back + 0.80)), 0.03, 0.03, segments=6)

    # 2c. 6 Tall Ornate Golden Sanctuary Candelabras flanking the High Altar (exact wick tips exported to candles.json!)
    a_half = 0.5 * ALTAR_SIZE[0]
    for dx in (-(a_half + 3.1), -(a_half + 2.0), -(a_half + 1.0), a_half + 1.0, a_half + 2.0, a_half + 3.1):
        sx = ALTAR_X + dx
        cy_c = ALTAR_Y + (1.2 if abs(dx) > a_half + 1.5 else 0.2)
        # Multi-tiered octagonal brass base
        add_cylinder(bm_gold, Vector((sx, cy_c, Z_ALTAR)), Vector((sx, cy_c, Z_ALTAR + 0.09)), 0.34, 0.28, segments=8)
        add_cylinder(bm_gold, Vector((sx, cy_c, Z_ALTAR + 0.09)), Vector((sx, cy_c, Z_ALTAR + 0.22)), 0.26, 0.14, segments=10)
        # Turned tapered brass stem with ornate central nodus sphere & upper collar
        add_cylinder(bm_gold, Vector((sx, cy_c, Z_ALTAR + 0.22)), Vector((sx, cy_c, Z_ALTAR + 0.86)), 0.072, 0.052, segments=10)
        add_cylinder(bm_gold, Vector((sx, cy_c, Z_ALTAR + 0.84)), Vector((sx, cy_c, Z_ALTAR + 0.96)), 0.115, 0.115, segments=10)
        add_cylinder(bm_gold, Vector((sx, cy_c, Z_ALTAR + 0.96)), Vector((sx, cy_c, Z_ALTAR + 1.50)), 0.058, 0.048, segments=10)
        # Wide sculpted brass wax drip saucer + candle socket cup
        add_cylinder(bm_gold, Vector((sx, cy_c, Z_ALTAR + 1.48)), Vector((sx, cy_c, Z_ALTAR + 1.56)), 0.11, 0.24, segments=12)
        add_cylinder(bm_gold, Vector((sx, cy_c, Z_ALTAR + 1.56)), Vector((sx, cy_c, Z_ALTAR + 1.63)), 0.23, 0.09, segments=12)
        # Tall ivory liturgical altar candle + tiny dark wick
        z_tip = Z_ALTAR + 2.14
        add_cylinder(bm_glow, Vector((sx, cy_c, Z_ALTAR + 1.61)), Vector((sx, cy_c, z_tip)), 0.062, 0.056, segments=10)
        add_cylinder(bm_iron, Vector((sx, cy_c, z_tip)), Vector((sx, cy_c, z_tip + 0.035)), 0.008, 0.006, segments=5)
        candle_anchors.append((sx, cy_c, z_tip + 0.028, 1.05))

    # 2d. Ornate Bronze & Marble Presbytery Altar Rail on the platform's front edge (top step, y = 15.0),
    # leaving the central approach |x| < 2.4 open, returning along the platform's straight sides
    rail_pts: list[tuple[float, float]] = []
    x_in, x_out = 2.6, PRESBYTERY_HALF_WIDTH - 0.15
    for k in range(6):
        px = x_in + (x_out - x_in) * k / 5.0
        rail_pts += [(px, PRESBYTERY_FRONT_Y + 0.15), (-px, PRESBYTERY_FRONT_Y + 0.15)]
    for k in range(1, 4):
        py = PRESBYTERY_FRONT_Y + 0.15 + (ALTAR_Y - PRESBYTERY_FRONT_Y - 0.15) * k / 3.0
        rail_pts += [(x_out, py), (-x_out, py)]
    # skip posts that would stand inside a column base (the basalt crossing-ring columns at (+-7.5, 15)
    # stand on the presbytery front edge)
    rail_pts = [
        (px, py) for px, py in rail_pts
        if all(math.hypot(px - c["x"], py - c["y"]) > COLUMN_FALLBACK_RADIUS[c["kind"]] + 0.2 for c in COLUMNS)
    ]
    for px, py in rail_pts:
        add_cylinder(bm_bronze, Vector((px, py, Z_ALTAR)), Vector((px, py, Z_ALTAR + 1.05)), 0.075, 0.065, segments=8)
        add_cylinder(bm_gold, Vector((px, py, Z_ALTAR + 1.02)), Vector((px, py, Z_ALTAR + 1.12)), 0.11, 0.09, segments=8)

    # 2e. Grand Carved Oak Pipe Organ Casing on the children's choir above the axial apse chapel
    # (ring r 15..19, Z 16.2), behind the altar. It follows the curve in 3 segments and stays inside the
    # axial chapel bay between the wall piers at 77.1 / 102.9 deg (~7.6 m chord at r 17).
    for k in (-1, 0, 1):
        ang = math.pi * 0.5 + k * (2.0 / ORGAN_R)
        ox, oy = APSE_CX + ORGAN_R * math.cos(ang), APSE_CY + ORGAN_R * math.sin(ang)
        add_box(bm_oak, (ox, oy, Z_CHILDREN_CHOIR + 2.4), (2.05, 1.5, 4.8), rot_euler=(0, 0, ang - math.pi * 0.5))
    for k in range(5):
        ang = math.pi * 0.5 + (k - 2) * (1.3 / ORGAN_R)
        ox, oy = APSE_CX + (ORGAN_R - 0.5) * math.cos(ang), APSE_CY + (ORGAN_R - 0.5) * math.sin(ang)
        add_box(bm_oak, (ox, oy, Z_CHILDREN_CHOIR + 4.3), (0.82, 1.7, 8.6), rot_euler=(0, 0, ang - math.pi * 0.5))
        add_cylinder(bm_gold, Vector((ox, oy, Z_CHILDREN_CHOIR + 8.6)), Vector((ox, oy, Z_CHILDREN_CHOIR + 9.9)), 0.32, 0.06, segments=8)

    # ── 3. Seven Radiating Apse Votive Chapels (Side Altars + Saint Statues + 2-Tier Wrought-Iron Votive Stands) ──
    # One per chapel, centred between consecutive wall piers (APSE_PIER_ANGLES_DEG) near the chapel back wall
    r_chapel = CHAPEL_ALTAR_R
    for i in range(len(APSE_PIER_ANGLES_DEG) - 1):
        ang = math.radians(0.5 * (APSE_PIER_ANGLES_DEG[i] + APSE_PIER_ANGLES_DEG[i + 1]))
        cx = APSE_CX + r_chapel * math.cos(ang)
        cy = APSE_CY + r_chapel * math.sin(ang)
        rot_z = ang - math.pi * 0.5
        in_x, in_y = -math.cos(ang), -math.sin(ang)

        # Carved marble Side Altar table
        add_box(bm_marble, (cx, cy, Z_NAVE + 0.55), (2.4, 0.95, 1.1), rot_euler=(0, 0, rot_z))
        add_box(bm_marble, (cx, cy, Z_NAVE + 1.14), (2.65, 1.15, 0.12), rot_euler=(0, 0, rot_z))
        # Gilded altar cross & retable backdrop
        add_cylinder(bm_gold, Vector((cx, cy, Z_NAVE + 1.2)), Vector((cx, cy, Z_NAVE + 2.55)), 0.06, 0.045, segments=8)
        add_cylinder(
            bm_gold,
            Vector((cx - 0.42 * math.sin(ang), cy + 0.42 * math.cos(ang), Z_NAVE + 2.18)),
            Vector((cx + 0.42 * math.sin(ang), cy - 0.42 * math.cos(ang), Z_NAVE + 2.18)),
            0.05,
            0.05,
            segments=8,
        )
        # Sculpted White Marble Saint Statue beside each side altar
        st_x = cx - 1.55 * math.sin(ang) + in_x * 0.25
        st_y = cy + 1.55 * math.cos(ang) + in_y * 0.25
        add_cylinder(bm_marble, Vector((st_x, st_y, Z_NAVE)), Vector((st_x, st_y, Z_NAVE + 1.1)), 0.45, 0.38, segments=10)
        add_statue_silhouette(bm_marble, Vector((st_x, st_y, Z_NAVE + 1.1)), scale=0.92, rot_z=ang + math.pi)

        # Sculpted 2-Tier Wrought-Iron & Brass Votive Candle Rack (exact candle tips exported to candles.json!)
        vx = cx + 1.55 * math.sin(ang) + in_x * 0.65
        vy = cy - 1.55 * math.cos(ang) + in_y * 0.65
        tx_v, ty_v = math.cos(rot_z), math.sin(rot_z)
        # Side legs + central offering box + brass sand/drip tray
        for side in (-0.60, 0.60):
            lx = vx + side * tx_v
            ly = vy + side * ty_v
            add_cylinder(bm_iron, Vector((lx, ly, Z_NAVE)), Vector((lx, ly, Z_NAVE + 0.96)), 0.045, 0.038, segments=8)
        add_box(bm_iron, (vx, vy, Z_NAVE + 0.42), (0.68, 0.36, 0.72), rot_euler=(0, 0, rot_z))
        add_box(bm_gold, (vx, vy, Z_NAVE + 0.94), (1.38, 0.54, 0.07), rot_euler=(0, 0, rot_z))
        # Upper rear tier bar
        add_box(bm_iron, (vx - in_x * 0.13, vy - in_y * 0.13, Z_NAVE + 1.07), (1.28, 0.16, 0.05), rot_euler=(0, 0, rot_z))
        # 5 rear votive candles + 4 front votive candles seated cleanly on the trays
        for ci in range(5):
            off = -0.48 + ci * 0.24
            kx = vx + off * tx_v - in_x * 0.13
            ky = vy + off * ty_v - in_y * 0.13
            z_base_k = Z_NAVE + 1.09
            z_top_k = z_base_k + 0.24 + (0.04 if ci % 2 == 0 else 0.0)
            add_cylinder(bm_glow, Vector((kx, ky, z_base_k)), Vector((kx, ky, z_top_k)), 0.036, 0.033, segments=7)
            add_cylinder(bm_iron, Vector((kx, ky, z_top_k)), Vector((kx, ky, z_top_k + 0.025)), 0.006, 0.005, segments=4)
            candle_anchors.append((kx, ky, z_top_k + 0.02, 0.62))
        for ci in range(4):
            off = -0.36 + ci * 0.24
            kx = vx + off * tx_v + in_x * 0.12
            ky = vy + off * ty_v + in_y * 0.12
            z_base_k = Z_NAVE + 0.97
            z_top_k = z_base_k + 0.20 + (0.03 if ci % 2 == 1 else 0.0)
            add_cylinder(bm_glow, Vector((kx, ky, z_base_k)), Vector((kx, ky, z_top_k)), 0.034, 0.031, segments=7)
            add_cylinder(bm_iron, Vector((kx, ky, z_top_k)), Vector((kx, ky, z_top_k + 0.025)), 0.006, 0.005, segments=4)
            candle_anchors.append((kx, ky, z_top_k + 0.02, 0.56))

    # ── 4. Baptistery (Taufbecken) in East Transept (+19.0, -9.5) + 6 Clam-Shell Holy-Water Fonts ──
    bx, by = 19.2, -9.8
    # Stepped octagonal marble baptistery dais
    add_cylinder(bm_marble, Vector((bx, by, Z_NAVE)), Vector((bx, by, Z_NAVE + 0.22)), 2.55, 2.55, segments=8)
    add_cylinder(bm_marble, Vector((bx, by, Z_NAVE + 0.22)), Vector((bx, by, Z_NAVE + 0.44)), 1.95, 1.95, segments=8)
    # Octagonal polished red porphyry baptismal font + golden basin rim
    add_cylinder(bm_porphyry, Vector((bx, by, Z_NAVE + 0.44)), Vector((bx, by, Z_NAVE + 1.38)), 0.85, 1.12, segments=8)
    add_cylinder(bm_gold, Vector((bx, by, Z_NAVE + 1.36)), Vector((bx, by, Z_NAVE + 1.46)), 1.16, 1.10, segments=8, cap=False)
    # 4 slender bronze canopy posts + gilded baptistery lantern crown
    for k in range(4):
        ka = k * math.pi * 0.5 + math.pi * 0.25
        px_b = bx + 1.75 * math.cos(ka)
        py_b = by + 1.75 * math.sin(ka)
        add_cylinder(bm_bronze, Vector((px_b, py_b, Z_NAVE + 0.44)), Vector((px_b, py_b, Z_NAVE + 4.4)), 0.08, 0.07, segments=8)
        add_cylinder(bm_gold, Vector((px_b, py_b, Z_NAVE + 4.4)), Vector((bx, by, Z_NAVE + 5.6)), 0.09, 0.06, segments=6)
    add_cylinder(bm_gold, Vector((bx, by, Z_NAVE + 5.5)), Vector((bx, by, Z_NAVE + 6.4)), 0.16, 0.04, segments=8)

    # Sculpted Holy-Water Fonts just inside the doors: Nativity (x 30) and Passion (x -30) portals,
    # Glory doors (y -47.75). The central doors get a pair, the lateral doors one each on the side
    # away from the door's neighbour column / corner stair, so every door approach stays open.
    fonts: list[tuple[float, float]] = []
    for facade, sgn in ((NATIVITY, 1.0), (PASSION, -1.0)):
        fx = sgn * (abs(facade["wallX"]) - 1.0)
        for portal in NATIVITY["portals"]:
            half = 0.5 * portal["width"] + 0.9
            if abs(portal["y"]) < 1e-6:
                fonts += [(fx, -half), (fx, half)]
            else:
                fonts.append((fx, portal["y"] - math.copysign(half, portal["y"])))   # inner side of Hope / Faith
    fy_g = GLORY_INNER_Y + 1.15
    for dx in GLORY["doorsX"]:
        if abs(dx) < 1e-6:
            fonts += [(-4.6, fy_g), (4.6, fy_g)]
        elif all(math.hypot(dx - s["x"], GLORY_INNER_Y - s["y"]) > s["rOuter"] + 2.0 for s in CORNER_STAIRS):
            fonts.append((dx - math.copysign(2.1, dx), fy_g))   # inner side of each lateral door
        # (no font at the outermost doors: the corner spiral stairs stand right in front of them)
    for fx, fy in fonts:
        add_holy_water_font(bm_marble, bm_gold, fx, fy)

    # ── 5. 4 Carved Catalan Oak Confessionals along Outer East & West Nave Walls (leaving Cloister Doorway & Corner Stairs 100% OPEN!) ──
    # (backs 0.43 m off the inner face of the outer nave wall, |x| = 22.5; first two window bays, far from the corner stairs)
    conf_x = NAVE_HALF_WIDTH - 0.675 - 0.425
    for cy_c in NAVE_WINDOW_BAY_Y[:2]:
        add_confessional(bm_oak, bm_gold, bm_glow, conf_x, cy_c, facing_x=-1.0)
        add_confessional(bm_oak, bm_gold, bm_glow, -conf_x, cy_c, facing_x=1.0)

    # ── 6. 19 Suspended Gaudí Modernist Chandeliers (Central Nave & Side Aisles) ──
    # Nave bay centres -11.25 .. -41.25 plus the stretched Glory bay (-46, under the south choir gallery:
    # those hang from the gallery soffit instead of the vault)
    for cy_l in (-11.25, -18.75, -26.25, -33.75, -41.25, -46.0):
        under_gallery = cy_l < -42.75
        add_chandelier(bm_iron, bm_gold, bm_glow, 0.0, cy_l, 11.2, Z_GALLERY - 0.8 if under_gallery else 43.5, radius=2.15)
        if under_gallery:
            continue   # side naves: the low gallery soffit leaves no room (and keeps the triangle budget)
        for sx in (-1, 1):
            add_chandelier(bm_iron, bm_gold, bm_glow, sx * 11.25, cy_l, 8.8, 29.5, radius=1.35)
    # 3 crossing/transept chandeliers (the crossing rod stops below the 56 m elevator stop)
    for cx_t in (-18.75, 18.75):
        add_chandelier(bm_iron, bm_gold, bm_glow, cx_t, 0.0, 10.5, 43.5, radius=1.95)
    add_chandelier(bm_iron, bm_gold, bm_glow, 0.0, 0.0, 13.5, Z_JESUS_DECK - 1.0, radius=2.85)

    # ── 7. Sculpted White Marble Saint Statues on Carved Pier Corbels along the Nave ──
    for cy_s in (-15.0, -22.5, -30.0, -37.5):
        for sx in (-1, 1):
            px_s = sx * (NAVE_HALF_WIDTH - 0.9)
            add_cylinder(bm_marble, Vector((px_s, cy_s, Z_NAVE + 3.0)), Vector((px_s, cy_s, Z_NAVE + 3.6)), 0.16, 0.48, segments=10)
            add_statue_silhouette(bm_marble, Vector((px_s, cy_s, Z_NAVE + 3.6)), scale=1.05, rot_z=math.pi if sx > 0 else 0.0)

    # ── 7b. 4 Ornate Golden Evangelist Tetramorph Medallions on the Crossing Porphyry Capitals + Vault Starbursts ──
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx_e, cy_e = sx * 7.5, sy * 7.5
            # Sculpted circular gilded evangelist medallion facing inward toward the crossing center
            in_ang = math.atan2(-sy, -sx)
            mx_e = cx_e + 1.52 * math.cos(in_ang)
            my_e = cy_e + 1.52 * math.sin(in_ang)
            add_cylinder(bm_gold, Vector((mx_e, my_e, 19.6)), Vector((mx_e, my_e, 21.6)), 0.82, 0.82, segments=16)
            add_cylinder(bm_marble, Vector((mx_e + 0.12 * math.cos(in_ang), my_e + 0.12 * math.sin(in_ang), 19.8)), Vector((mx_e + 0.12 * math.cos(in_ang), my_e + 0.12 * math.sin(in_ang), 21.4)), 0.62, 0.62, segments=12)
            # Crown of 8 golden rays around each porphyry crossing capital knot
            for k in range(8):
                ka = k * math.pi * 0.25
                p0 = Vector((cx_e + 1.35 * math.cos(ka), cy_e + 1.35 * math.sin(ka), 20.6))
                p1 = Vector((cx_e + 1.85 * math.cos(ka), cy_e + 1.85 * math.sin(ka), 21.2))
                add_cylinder(bm_gold, p0, p1, 0.08, 0.03, segments=6)

    # Golden Starburst Rosette Rays around the Central Crossing Oculus (Z = 60.5m) & Main Nave Oculi (Z = 45.6m)
    for ox, oy, oz, r0, r1, count in (
        (0.0, 0.0, 60.4, 3.3, 5.2, 16),
        (0.0, -11.25, 45.5, 1.75, 3.1, 12),
        (0.0, -18.75, 45.5, 1.75, 3.1, 12),
        (0.0, -26.25, 45.5, 1.75, 3.1, 12),
        (0.0, -33.75, 45.5, 1.75, 3.1, 12),
        (0.0, -41.25, 45.5, 1.75, 3.1, 12),   # the nave is one bay longer (Glory wall at -47.75)
    ):
        for k in range(count):
            ka = 2.0 * math.pi * k / count
            add_cylinder(
                bm_gold,
                Vector((ox + r0 * math.cos(ka), oy + r0 * math.sin(ka), oz)),
                Vector((ox + r1 * math.cos(ka), oy + r1 * math.sin(ka), oz - 0.45)),
                0.09,
                0.03,
                segments=6,
            )

    # ── 8. Gaudí Exhibition Showcase in West Outer Aisle (-18.6, Y = -37.2 & -18.5 — clear of West Corner Spiral Stair!) ──
    # 8a. Iconic Inverted Hanging-Chain Funicular Model ("Hängemodell") at (-18.6, -37.2)
    ex, ey = -18.6, -37.2
    add_box(bm_oak, (ex, ey, Z_NAVE + 0.45), (2.8, 2.8, 0.90))
    add_box(bm_glass, (ex, ey, Z_NAVE + 2.15), (2.6, 2.6, 2.50))
    # Corner brass vitrine frames + overhead mirror ceiling plate
    for dx in (-1.3, 1.3):
        for dy in (-1.3, 1.3):
            add_cylinder(bm_gold, Vector((ex + dx, ey + dy, Z_NAVE + 0.9)), Vector((ex + dx, ey + dy, Z_NAVE + 3.45)), 0.04, 0.04, segments=6)
    add_box(bm_oak, (ex, ey, Z_NAVE + 3.48), (2.75, 2.75, 0.12))
    # Suspended brass catenary chains & tiny lead weight bags inside the vitrine!
    for k in range(6):
        ang = math.pi * k / 6.0
        for s in range(10):
            t0 = -1.0 + 2.0 * s / 10.0
            t1 = -1.0 + 2.0 * (s + 1) / 10.0
            z0 = Z_NAVE + 3.38 - (1.0 - t0 * t0) * 1.95
            z1 = Z_NAVE + 3.38 - (1.0 - t1 * t1) * 1.95
            add_cylinder(
                bm_gold,
                Vector((ex + t0 * 1.05 * math.cos(ang), ey + t0 * 1.05 * math.sin(ang), z0)),
                Vector((ex + t1 * 1.05 * math.cos(ang), ey + t1 * 1.05 * math.sin(ang), z1)),
                0.018,
                0.018,
                segments=5,
            )
    # Central lead weight cluster hanging at lowest point of the catenary
    add_cylinder(bm_bronze, Vector((ex, ey, Z_NAVE + 1.15)), Vector((ex, ey, Z_NAVE + 1.48)), 0.10, 0.06, segments=8)

    # 8b. Miniature Plaster Double-Twisted Column Study Model Showcase at (-18.6, -18.5)
    mx, my = -18.6, -18.5
    add_box(bm_oak, (mx, my, Z_NAVE + 0.50), (1.8, 1.8, 1.0))
    add_box(bm_glass, (mx, my, Z_NAVE + 1.95), (1.65, 1.65, 1.9))
    bm_mini_col = bmesh.new()
    build_gaudi_column_bmesh(bm_mini_col, base_z=Z_NAVE + 1.0, knot_z=Z_NAVE + 2.65, radius_base=0.22, sides=10, rings=14, radial_segs=24)
    for v in bm_mini_col.verts:
        v.co.x += mx
        v.co.y += my
    finalize_bmesh_object(bm_mini_col, "Exhibit_PlasterColumnModel", mats["white_marble"], smooth=True, uv_scale=0.5)

    # ── 9. Instanced Side-Aisle Oak Pews (filling East & West inner aisles X = ±11.25) ──
    bm_pew = bmesh.new()
    add_box(bm_pew, (0.0, 0.0, 0.45), (4.2, 0.48, 0.08))
    add_box(bm_pew, (0.0, -0.22, 0.80), (4.2, 0.08, 0.66))
    add_box(bm_pew, (0.0, 0.24, 0.18), (4.0, 0.16, 0.06))  # Kneeler rail
    add_box(bm_pew, (-2.02, 0.0, 0.36), (0.12, 0.56, 0.72))
    add_box(bm_pew, (2.02, 0.0, 0.36), (0.12, 0.56, 0.72))
    apply_box_uv(bm_pew, scale=0.4)
    bake_bvh_vertex_ao(bm_pew, max_dist=1.8, min_ao=0.55)
    mesh_side_pew = bpy.data.meshes.new("Mesh_SidePew")
    bm_pew.to_mesh(mesh_side_pew)
    bm_pew.free()
    mesh_side_pew.materials.append(mats["wood_pew"])

    # Inner side naves (x between the central-nave and aisle column rows, 7.5 .. 15) from the transept's
    # south aisle (y -7.5) to the last nave column row (y -45). Rows are grouped per column bay and keep
    # a 2.5 m cross aisle on every column row (lateral passages + the approach from the Glory door at
    # x +-11.25, which opens into the free band y -47.75 .. -43.75).
    pew_x = 0.5 * (CENTRAL_NAVE_HALF + INNER_AISLE_OUTER)
    row_ys = sorted({c["y"] for c in COLUMNS if abs(abs(c["x"]) - INNER_AISLE_OUTER) < 1e-6 and c["y"] < 0.0}, reverse=True)
    pew_pitch, cross_half = 1.72, 1.25
    p_idx = 0
    for y_a, y_b in zip(row_ys[:-1], row_ys[1:]):
        span = (y_a - y_b) - 2.0 * cross_half
        n_rows = int(span // pew_pitch) + 1
        y_mid = 0.5 * (y_a + y_b)
        for r in range(n_rows):
            py = y_mid + (r - 0.5 * (n_rows - 1)) * pew_pitch
            for sx in (-1, 1):
                obj = bpy.data.objects.new(f"SidePew_{p_idx}", mesh_side_pew)
                obj.location = (sx * pew_x, py, Z_NAVE)
                bpy.context.collection.objects.link(obj)
                p_idx += 1
    print(f"[Furnishings] {p_idx} side pews in {len(row_ys) - 1} bays (y {row_ys[0]} .. {row_ys[-1]})")

    finalize_bmesh_object(bm_carpet, "Furnish_CrimsonCarpet", mats["carpet_crimson"], smooth=False, uv_scale=0.25)
    finalize_bmesh_object(bm_oak, "Furnish_CarvedOak", mats["wood_pew"], smooth=False, uv_scale=0.35)
    finalize_bmesh_object(bm_marble, "Furnish_MarbleLiturgical", mats["white_marble"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_porphyry, "Furnish_BaptisteryPorphyry", mats["porphyry_red"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_gold, "Furnish_GoldAccents", mats["gold_accent"], smooth=True, uv_scale=0.40)
    finalize_bmesh_object(bm_bronze, "Furnish_BronzeFittings", mats["bronze_door"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_iron, "Furnish_ChandelierIron", mats["iron_dark"], smooth=True, uv_scale=0.40)
    finalize_bmesh_object(bm_glow, "Furnish_LanternAndCandleGlow", mats["candle_glow"], smooth=True, uv_scale=0.50, bake_ao=False)
    finalize_bmesh_object(bm_glass, "Furnish_MuseumGlassCases", mats["glass_case"], smooth=False, uv_scale=0.40, bake_ao=False)

    save_candle_anchors("furnishings", candle_anchors)
    export_glb(os.path.join(MODEL_DIR, "furnishings.glb"))


if __name__ == "__main__":
    build_furnishings()
