"""Build the 3 monumental facades (Nativity, Passion, Glory), exterior roofs & fruit-basket pinnacles."""

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
    Z_AISLE_VAULT,
    Z_NAVE,
    Z_NAVE_VAULT,
    add_box,
    add_cylinder,
    apply_organic_stone_displacement,
    bevel_sharp_edges,
    export_glb,
    finalize_bmesh_object,
    get_materials,
    reset_scene,
)


def add_pointed_gable(
    bm: bmesh.types.BMesh,
    center_xy: tuple[float, float],
    z_base: float,
    width: float,
    height: float,
    thickness: float,
    facing: str = "X+",
) -> None:
    """Create a sculpted pointed Gothic/Gaudí triangular gable with stepped pinnacle ribs."""
    cx, cy = center_xy
    steps = 7
    for i in range(steps):
        t = i / steps
        w = width * (1.0 - t * 0.92)
        z = z_base + t * height
        h_seg = height / steps * 1.15
        if facing in ("X+", "X-"):
            add_box(bm, (cx, cy, z + h_seg * 0.5), (thickness, w, h_seg))
        else:
            add_box(bm, (cx, cy, z + h_seg * 0.5), (w, thickness, h_seg))


def build_nativity_facade(
    bm_nat: bmesh.types.BMesh,
    bm_bronze: bmesh.types.BMesh,
    bm_cypress: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
    bm_white: bmesh.types.BMesh,
) -> None:
    """East Nativity Facade (X = +31.5): organic sandstone, 3 gabled portals, Cypress Tree of Life."""
    fx = 31.5

    # Entrance steps leading from Plaça de Gaudí (Z=0) up to Nave floor (Z=1.2)
    for step in range(6):
        sz = (step + 1) * (Z_NAVE / 6.0)
        add_box(bm_nat, (fx + 4.8 - step * 0.55, 0.0, sz * 0.5), (0.65, 28.0, sz))
    add_box(bm_nat, (fx + 1.4, 0.0, Z_NAVE * 0.5), (3.4, 28.0, Z_NAVE))

    # Massive sculpted piers flanking the 3 portals (leaving open walkthrough portals at Y = -9, 0, +9)
    pier_ys = (-14.2, -4.6, 4.6, 14.2)
    for py in pier_ys:
        add_box(bm_nat, (fx, py, 14.5), (4.2, 3.6, 29.0))
        # Organic dripping stalactite-like buttress projections
        for k in range(5):
            zk = 5.0 + k * 4.5
            r = 1.45 - k * 0.16
            add_cylinder(bm_nat, Vector((fx + 2.2, py, zk)), Vector((fx + 1.8, py, zk + 4.8)), r, r * 0.68, segments=10)

    # Upper facade wall above the 3 open portals (Z = 10.5 .. 30.0)
    # Central Charity Portal is open to Z = 10.2m (width 5.4m), side portals open to Z = 8.4m
    add_box(bm_nat, (fx, 0.0, 20.2), (3.6, 29.0, 19.6))
    # Deep sculpted archivolts framing each portal
    for py, p_w, p_h, g_h in ((-9.2, 5.2, 8.6, 24.0), (0.0, 6.2, 10.4, 30.0), (9.2, 5.2, 8.6, 24.0)):
        # Stepped parabolic archivolt ribs projecting outward
        for layer in range(4):
            lx = fx + 1.8 + layer * 0.48
            lw = p_w + layer * 0.65
            lh = p_h + layer * 0.55
            # Left & right jambs
            for sy in (-1, 1):
                add_cylinder(
                    bm_nat,
                    Vector((lx, py + sy * (lw * 0.5), Z_NAVE)),
                    Vector((lx, py + sy * (lw * 0.35), lh)),
                    0.48,
                    0.40,
                    segments=8,
                )
            # Pointed parabolic arch top
            add_cylinder(bm_nat, Vector((lx, py - lw * 0.35, lh)), Vector((lx, py, lh + 3.2)), 0.42, 0.36, segments=8)
            add_cylinder(bm_nat, Vector((lx, py + lw * 0.35, lh)), Vector((lx, py, lh + 3.2)), 0.42, 0.36, segments=8)
        # Soaring organic triangular gable pinnacle above each portal
        add_pointed_gable(bm_nat, (fx + 1.9, py), p_h + 2.6, p_w + 3.2, g_h, 2.2, facing="X+")
        # Deep sculpted rosette wheel medallion recessed inside each Nativity gable!
        rz = p_h + 5.6
        rr = 1.65 if py == 0.0 else 1.25
        for s in range(12):
            a0 = 2.0 * math.pi * s / 12.0
            a1 = 2.0 * math.pi * (s + 1) / 12.0
            add_cylinder(
                bm_nat,
                Vector((fx + 3.15, py + rr * math.cos(a0), rz + rr * math.sin(a0))),
                Vector((fx + 3.15, py + rr * math.cos(a1), rz + rr * math.sin(a1))),
                0.20,
                0.20,
                segments=6,
            )
            if s % 2 == 0:
                add_cylinder(
                    bm_gold,
                    Vector((fx + 3.05, py, rz)),
                    Vector((fx + 3.15, py + rr * math.cos(a0), rz + rr * math.sin(a0))),
                    0.09,
                    0.09,
                    segments=6,
                )
        # Organic botanical pinnacles, Gothic crocket spires & sculpted tympanum figure reliefs flanking the gable!
        for sy in (-1, 1):
            add_cylinder(bm_nat, Vector((fx + 2.9, py + sy * (p_w * 0.55), p_h + 1.2)), Vector((fx + 2.8, py + sy * (p_w * 0.52), p_h + 10.5)), 0.58, 0.12, segments=8)
            add_cylinder(bm_nat, Vector((fx + 3.3, py + sy * (p_w * 0.36), p_h + 4.0)), Vector((fx + 3.1, py + sy * (p_w * 0.32), p_h + 14.5)), 0.42, 0.09, segments=7)
            # Carved sculptural niche canopy + figure silhouette beside each portal jamb
            add_cylinder(bm_nat, Vector((fx + 3.25, py + sy * (p_w * 0.52), Z_NAVE + 2.2)), Vector((fx + 3.25, py + sy * (p_w * 0.52), Z_NAVE + 5.0)), 0.42, 0.28, segments=8)
            add_cylinder(bm_white, Vector((fx + 3.45, py + sy * (p_w * 0.52), Z_NAVE + 2.4)), Vector((fx + 3.45, py + sy * (p_w * 0.52), Z_NAVE + 4.5)), 0.24, 0.16, segments=8)
        # Sculpted tympanum narrative relief cluster over portal arch
        for fi in (-1.2, -0.4, 0.4, 1.2):
            add_cylinder(bm_nat, Vector((fx + 2.95, py + fi, p_h + 0.6)), Vector((fx + 2.95, py + fi, p_h + 2.6 - abs(fi) * 0.4)), 0.28, 0.18, segments=7)

        # Sculpted bronze doors folded open against the portal jambs (so walkthrough is clear!)
        for sy in (-1, 1):
            add_box(bm_bronze, (fx - 0.6, py + sy * (p_w * 0.44), Z_NAVE + 3.0), (2.2, 0.25, 6.0))

    # Central Sculpted Cypress Tree of Life rising above Charity Gable (Z = 38 .. 49m)
    tree_x = fx + 2.0
    add_cylinder(bm_cypress, Vector((tree_x, 0.0, 38.0)), Vector((tree_x, 0.0, 48.5)), 2.1, 0.25, segments=12)
    # Organic cypress foliage tiers & white ceramic doves perched on branches
    for tier in range(5):
        zt = 39.5 + tier * 1.8
        rt = 2.0 - tier * 0.32
        for k in range(4):
            ang = math.pi * 0.5 * k + tier * 0.6
            add_cylinder(
                bm_white,
                Vector((tree_x + rt * math.cos(ang), rt * math.sin(ang), zt)),
                Vector((tree_x + (rt + 0.55) * math.cos(ang), (rt + 0.55) * math.sin(ang), zt + 0.35)),
                0.22,
                0.08,
                segments=6,
            )
    # Red/Gold Tau Cross at the summit of the Cypress Tree
    add_cylinder(bm_gold, Vector((tree_x, 0.0, 48.0)), Vector((tree_x, 0.0, 51.2)), 0.28, 0.24, segments=8)
    add_cylinder(bm_gold, Vector((tree_x, -1.4, 50.8)), Vector((tree_x, 1.4, 50.8)), 0.24, 0.24, segments=8)


def build_passion_facade(
    bm_pas: bmesh.types.BMesh,
    bm_bronze: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
) -> None:
    """West Passion Facade (X = -31.5): 6 giant inclined bone columns, stark portico, Subirachs aesthetic."""
    fx = -31.5

    # Entrance steps from Plaça de la Sagrada Família (Z=0) up to portico terrace (Z=1.2)
    for step in range(6):
        sz = (step + 1) * (Z_NAVE / 6.0)
        add_box(bm_pas, (fx - 8.2 + step * 0.55, 0.0, sz * 0.5), (0.65, 30.0, sz))
    add_box(bm_pas, (fx - 3.6, 0.0, Z_NAVE * 0.5), (6.4, 30.0, Z_NAVE))

    # Inner recessed Passion wall with 3 wide open doors (central door open 5.6m wide!)
    for py in (-14.2, -5.2, 5.2, 14.2):
        add_box(bm_pas, (fx, py, 14.5), (3.4, 4.2, 29.0))
    add_box(bm_pas, (fx, 0.0, 21.0), (3.2, 29.0, 18.0))
    # Bronze Gospel doors folded open at entrance jambs
    for sy in (-1, 1):
        add_box(bm_bronze, (fx + 0.5, sy * 2.8, Z_NAVE + 3.2), (2.4, 0.26, 6.4))

    # THE 6 ICONIC GIANT INCLINED BONE-SHAPED PORTICO COLUMNS with double-ribbed tendon flutes!
    col_ys = (-13.5, -8.1, -2.7, 2.7, 8.1, 13.5)
    for cy in col_ys:
        p0 = Vector((fx - 6.8, cy, Z_NAVE))
        p_mid = Vector((fx - 5.2, cy * 0.96, 12.0))
        p1 = Vector((fx - 3.6, cy * 0.92, 23.0))
        # Tapered bone-like lower + upper shaft with organic pinched waist & carved stone tendon ribs
        add_cylinder(bm_pas, p0, p_mid, 1.38, 0.98, segments=12)
        add_cylinder(bm_pas, p_mid, p1, 0.98, 1.48, segments=12)
        for dy_rib in (-0.85, 0.85):
            add_cylinder(bm_pas, p0 + Vector((0, dy_rib, 0)), p_mid + Vector((0.1, dy_rib * 0.72, 0)), 0.34, 0.24, segments=6)
            add_cylinder(bm_pas, p_mid + Vector((0.1, dy_rib * 0.72, 0)), p1 + Vector((0, dy_rib * 0.95, 0)), 0.24, 0.36, segments=6)
        # Sculpted angular bone-joint capital pad
        add_box(bm_pas, (p1.x, p1.y, p1.z + 0.55), (2.8, 2.6, 1.1))
        # Diagonal rear brace strut connecting column to inner wall
        add_cylinder(bm_pas, p_mid, Vector((fx - 1.2, cy, 17.5)), 0.55, 0.45, segments=8)

    # Massive overhanging triangular ribbed Passion cornice & upper colonnade (Z = 22.5 .. 38m)
    add_box(bm_pas, (fx - 3.8, 0.0, 24.5), (6.5, 31.5, 3.6))
    # Giant triangular ribbed pediment of bone-like struts above the portico
    for k in range(18):
        py = -14.5 + k * (29.0 / 17.0)
        h_tri = 14.0 * (1.0 - abs(py) / 16.0)
        if h_tri > 1.2:
            add_cylinder(
                bm_pas,
                Vector((fx - 5.2, py, 26.2)),
                Vector((fx - 3.2, py * 0.9, 26.2 + h_tri)),
                0.42,
                0.28,
                segments=6,
            )
    # Stark triangular gable crest frame
    add_cylinder(bm_pas, Vector((fx - 5.2, -15.5, 26.0)), Vector((fx - 3.4, 0.0, 41.5)), 0.85, 0.72, segments=8)
    add_cylinder(bm_pas, Vector((fx - 5.2, 15.5, 26.0)), Vector((fx - 3.4, 0.0, 41.5)), 0.85, 0.72, segments=8)
    # Golden Ascension cross / halo crowning the Passion pediment
    add_cylinder(bm_gold, Vector((fx - 3.4, 0.0, 41.2)), Vector((fx - 3.4, 0.0, 45.8)), 0.25, 0.20, segments=8)
    add_cylinder(bm_gold, Vector((fx - 3.4, -1.6, 44.2)), Vector((fx - 3.4, 1.6, 44.2)), 0.22, 0.22, segments=8)

    # Angular faceted Subirachs-style sculptural groups along the Passion portico (Flagellation, Judas, Crucifixion)
    for sy in (-1, 1):
        add_box(bm_pas, (fx - 3.2, sy * 6.8, Z_NAVE + 1.8), (1.8, 2.8, 3.6))
        # Faceted dramatic sculptural figures atop plinth
        for fi in (-0.65, 0.0, 0.65):
            add_box(bm_pas, (fx - 3.2, sy * 6.8 + fi, Z_NAVE + 4.7), (0.55, 0.48, 2.2), rot_euler=(0.08 * fi, 0.12, sy * 0.25))
    # Subirachs' iconic Flagellation column + Magic Square (33) plaque flanking the central door
    add_cylinder(bm_pas, Vector((fx - 2.4, -4.2, Z_NAVE)), Vector((fx - 2.4, -4.2, Z_NAVE + 4.2)), 0.34, 0.30, segments=8)
    add_box(bm_gold, (fx - 1.72, 4.4, Z_NAVE + 3.2), (0.14, 1.25, 1.25))
    # Horizontal iron/bronze beam of Subirachs' Crucifixion above the central portico
    add_box(bm_bronze, (fx - 2.3, 0.0, 14.5), (0.45, 7.6, 0.45))
    add_box(bm_bronze, (fx - 2.3, 0.0, 13.8), (0.45, 0.45, 4.2))


def build_glory_facade(
    bm_warm: bmesh.types.BMesh,
    bm_bronze: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
) -> None:
    """South Glory Facade (Y = -49.5, Completed Design): 7 tall columns, cloud portico, monumental bridge staircase."""
    fy = -49.5

    # Main facade wall framing the grand central portal (Y = -47.2, open walkthrough center X = -4.2..+4.2!)
    for px in (-21.0, -13.2, -6.2, 6.2, 13.2, 21.0):
        add_box(bm_warm, (px, fy + 2.2, 16.0), (3.4, 3.6, 32.0))
    add_box(bm_warm, (0.0, fy + 2.2, 24.0), (45.0, 3.2, 22.0))

    # Monumental Bronze Lord's Prayer Doors folded open at the center
    for sx in (-1, 1):
        add_box(bm_bronze, (sx * 4.2, fy + 3.2, Z_NAVE + 4.0), (0.32, 3.2, 8.0))
        add_box(bm_bronze, (sx * 9.8, fy + 2.2, Z_NAVE + 3.2), (3.6, 0.32, 6.4))

    # 7 Monumental Fluted Lantern Columns of the Glory Portico (spanning X = -18..+18 at Y = -56.5)
    for i in range(7):
        px = -18.0 + i * 6.0
        h_col = 26.0 + (4.5 - abs(i - 3) * 1.2)
        add_cylinder(bm_warm, Vector((px, fy - 6.8, Z_NAVE)), Vector((px, fy - 6.8, h_col)), 1.32, 0.92, segments=12)
        # 4 sculpted vertical stone flutes wrapping each Glory column
        for k in range(4):
            a = k * math.pi * 0.5 + math.pi * 0.25
            add_cylinder(
                bm_warm,
                Vector((px + 1.22 * math.cos(a), fy - 6.8 + 1.22 * math.sin(a), Z_NAVE)),
                Vector((px + 0.88 * math.cos(a), fy - 6.8 + 0.88 * math.sin(a), h_col)),
                0.24,
                0.18,
                segments=6,
            )
        # Sculpted gilded lantern crown atop each of the 7 columns
        add_cylinder(bm_gold, Vector((px, fy - 6.8, h_col)), Vector((px, fy - 6.8, h_col + 3.6)), 1.18, 0.35, segments=10)
        # Parabolic vault ribs tying portico columns back into the facade
        add_cylinder(bm_warm, Vector((px, fy - 6.8, h_col - 2.0)), Vector((px, fy + 1.0, h_col + 4.5)), 0.72, 0.65, segments=8)

    # Sweeping sculptural "Cloud & Glory" vaulted portico roof canopy (Z = 27 .. 36m)
    add_box(bm_warm, (0.0, fy - 2.8, 29.0), (42.0, 10.5, 4.2))
    add_pointed_gable(bm_warm, (0.0, fy - 5.5), 30.5, 34.0, 18.0, 3.2, facing="Y-")

    # Monumental Ceremonial Terrace & Grand Staircase descending south over Carrer de Mallorca!
    # Wide flat podium terrace right in front of the Glory portico (Y = -47..-58, Z = 1.2)
    add_box(bm_warm, (0.0, fy - 3.5, Z_NAVE * 0.5), (44.0, 13.5, Z_NAVE))
    # Grand terraced cascade stairs (Y = -58..-72, descending gently from Z = 1.2 down to Z = 0.0)
    for step in range(10):
        sz = (10 - step) * (Z_NAVE / 10.0)
        sy = -58.5 - step * 1.15
        sw = 34.0 + step * 0.8
        add_box(bm_warm, (0.0, sy, sz * 0.5), (sw, 1.25, sz))
    # Ornamental flanking parapet walls with gilded light obelisks along the grand staircase
    for sx in (-1, 1):
        add_box(bm_warm, (sx * 19.5, -64.0, 1.2), (1.4, 13.5, 2.4))
        add_cylinder(bm_gold, Vector((sx * 19.5, -70.0, 2.4)), Vector((sx * 19.5, -70.0, 6.2)), 0.55, 0.14, segments=8)


def build_roofs_and_pinnacles(
    bm_warm: bmesh.types.BMesh,
    bm_mosaic: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
) -> None:
    """Exterior pitched ribbed stone roofs, apse pinnacles, and Gaudí's ceramic fruit-basket finials."""
    # Central Nave Pitched Roof (X: -8..+8, Y: -46..-7.5, Z: 46..54m)
    for i in range(6):
        t = i / 5.0
        w = 16.4 * (1.0 - t * 0.85)
        add_box(bm_warm, (0.0, -26.8, Z_NAVE_VAULT + 0.8 + i * 1.35), (w, 38.5, 1.45))

    # Central Transept Pitched Roofs (X: ±8..±30, Y: -8..+8)
    for sx in (-1, 1):
        for i in range(6):
            t = i / 5.0
            w = 16.4 * (1.0 - t * 0.85)
            add_box(bm_warm, (sx * 19.0, 0.0, Z_NAVE_VAULT + 0.8 + i * 1.35), (22.5, w, 1.45))

    # Side Aisles Exterior Roof Slabs (Z = 31.2 .. 34.2m)
    for sx in (-1, 1):
        add_box(bm_warm, (sx * 15.2, -26.8, Z_AISLE_VAULT + 1.2), (15.6, 38.5, 2.4))
        # Decorative window gables + colorful trencadís fruit-basket pinnacles along nave roofline!
        for bay in range(5):
            py = -18.75 - bay * GRID
            add_pointed_gable(bm_warm, (sx * 22.8, py), Z_AISLE_VAULT + 0.5, 6.4, 9.5, 1.5, facing="X+" if sx > 0 else "X-")
            # Colorful Gaudí Fruit-Basket ceramic pinnacle atop every nave gable (Z = 41..46m)
            px = sx * 22.8
            add_cylinder(bm_mosaic, Vector((px, py, Z_AISLE_VAULT + 9.5)), Vector((px, py, Z_AISLE_VAULT + 13.0)), 0.72, 1.18, segments=10)
            # Sculpted ceramic fruit spheres crowning the basket + golden wheat/palm finial
            for fi in range(6):
                fa = 2.0 * math.pi * fi / 6.0
                fx_s = px + 0.72 * math.cos(fa)
                fy_s = py + 0.72 * math.sin(fa)
                add_cylinder(bm_mosaic, Vector((fx_s, fy_s, Z_AISLE_VAULT + 12.6)), Vector((fx_s, fy_s, Z_AISLE_VAULT + 13.7)), 0.42, 0.22, segments=8)
            add_cylinder(bm_gold, Vector((px, py, Z_AISLE_VAULT + 13.2)), Vector((px, py, Z_AISLE_VAULT + 15.6)), 0.95, 0.14, segments=10)

    # Apse Exterior Neo-Gothic Pinnacles & Gables around the semicircular north end
    num_pinnacles = 8
    r_apse = 19.4
    for i in range(num_pinnacles):
        ang = math.pi * (0.04 + 0.92 * i / (num_pinnacles - 1))
        px = r_apse * math.cos(ang)
        py = 16.5 + r_apse * math.sin(ang)
        # Tall soaring Gothic buttress pinnacle rising above the apse chapels (Z = 42..62m)
        add_cylinder(bm_warm, Vector((px, py, 40.0)), Vector((px, py, 59.0)), 1.25, 0.28, segments=8)
        add_cylinder(bm_mosaic, Vector((px, py, 59.0)), Vector((px, py, 63.0)), 0.45, 0.08, segments=8)


def build_facades() -> None:
    reset_scene()
    mats = get_materials()

    bm_nat = bmesh.new()
    bm_pas = bmesh.new()
    bm_warm = bmesh.new()
    bm_bronze = bmesh.new()
    bm_cypress = bmesh.new()
    bm_mosaic = bmesh.new()
    bm_gold = bmesh.new()
    bm_white = bmesh.new()

    build_nativity_facade(bm_nat, bm_bronze, bm_cypress, bm_gold, bm_white)
    build_passion_facade(bm_pas, bm_bronze, bm_gold)
    build_glory_facade(bm_warm, bm_bronze, bm_gold)
    build_roofs_and_pinnacles(bm_warm, bm_mosaic, bm_gold)

    # Organic 3D stalactite/botanical relief displacement on Nativity Facade + crisp stone edge bevels on Passion & Glory!
    apply_organic_stone_displacement(bm_nat, amp=0.14, min_z=2.2)
    bevel_sharp_edges(bm_pas, width=0.055, angle_deg=60.0)
    bevel_sharp_edges(bm_warm, width=0.055, angle_deg=60.0)

    finalize_bmesh_object(bm_nat, "Facade_Nativity", mats["nativity_stone"], smooth=True, uv_scale=0.16)
    finalize_bmesh_object(bm_pas, "Facade_Passion", mats["passion_stone"], smooth=False, uv_scale=0.15)
    finalize_bmesh_object(bm_warm, "Facade_GloryAndRoofs", mats["sandstone_warm"], smooth=False, uv_scale=0.14)
    finalize_bmesh_object(bm_bronze, "Facade_BronzeDoors", mats["bronze_door"], smooth=False, uv_scale=0.25)
    finalize_bmesh_object(bm_cypress, "Facade_CypressTree", mats["cypress_green"], smooth=True, uv_scale=0.30)
    finalize_bmesh_object(bm_mosaic, "Facade_FruitPinnacles", mats["trencadis"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_gold, "Facade_GoldAccents", mats["gold_accent"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_white, "Facade_Doves", mats["white_marble"], smooth=True, uv_scale=0.40)

    export_glb(os.path.join(MODEL_DIR, "facades.glb"))


if __name__ == "__main__":
    build_facades()
