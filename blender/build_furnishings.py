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
)


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

    # ── 1. Royal Crimson & Gold Ceremonial Carpet (Central Nave + Presbytery Sanctuary) ──
    # Long ceremonial runner from South Glory entrance to Presbytery stairs (X: -2.1..+2.1, Y: -44..+7.5)
    add_box(bm_carpet, (0.0, -18.2, Z_NAVE + 0.025), (4.2, 51.6, 0.04))
    # Cross-transept ceremonial runners (East & West portals meeting at the Crossing)
    add_box(bm_carpet, (0.0, 0.0, Z_NAVE + 0.028), (58.0, 3.6, 0.04))
    # Presbytery circular sanctuary carpet atop the stepped altar platform (Z_ALTAR = 2.4m)
    add_cylinder(bm_carpet, Vector((0.0, 17.5, Z_ALTAR + 0.01)), Vector((0.0, 17.5, Z_ALTAR + 0.05)), 8.2, 8.2, segments=28, cap=True)

    # ── 2. Sanctuary Liturgical Furniture (Ambo/Pulpit, Cathedra, Choir Stalls, Altar Rail, Candelabras, Organ Casing) ──
    # 2a. Sculpted Gaudí Ambo / Pulpit on left front of presbytery (-5.6, +13.5)
    ax, ay = -5.6, 13.5
    add_cylinder(bm_marble, Vector((ax, ay, Z_ALTAR)), Vector((ax, ay, Z_ALTAR + 1.25)), 0.58, 0.42, segments=10)
    add_box(bm_marble, (ax, ay, Z_ALTAR + 1.38), (1.15, 0.85, 0.22))
    add_box(bm_gold, (ax, ay - 0.1, Z_ALTAR + 1.56), (0.85, 0.55, 0.10), rot_euler=(-0.35, 0.0, 0.0))

    # 2b. Bishop's Cathedra (Throne) & Semicircular Carved Oak Clergy Choir Stalls behind High Altar (center 0, 17.5, r = 6.2m)
    for i in range(9):
        ang = math.pi * (0.18 + 0.64 * i / 8.0)  # Semicircle along North rear of sanctuary
        sx = 6.4 * math.cos(ang)
        sy = 17.5 + 6.4 * math.sin(ang)
        rot_z = ang + math.pi * 0.5
        is_cathedra = (i == 4)
        w_s = 1.35 if is_cathedra else 1.05
        h_back = 2.85 if is_cathedra else 1.95
        add_box(bm_oak, (sx, sy, Z_ALTAR + 0.45), (w_s, 0.72, 0.90), rot_euler=(0, 0, rot_z))
        # High carved gothic backrest
        bx = sx + 0.30 * math.cos(ang)
        by = sy + 0.30 * math.sin(ang)
        add_box(bm_oak, (bx, by, Z_ALTAR + h_back * 0.5), (w_s, 0.16, h_back), rot_euler=(0, 0, rot_z))
        if is_cathedra:
            add_cylinder(bm_gold, Vector((bx, by, Z_ALTAR + h_back)), Vector((bx, by, Z_ALTAR + h_back + 0.75)), 0.12, 0.03, segments=8)

    # 2c. 6 Tall Ornate Golden Sanctuary Candelabras flanking the High Altar
    for sx in (-4.4, -3.2, -2.1, 2.1, 3.2, 4.4):
        cy_c = 19.2 if abs(sx) > 3.0 else 18.2
        add_cylinder(bm_gold, Vector((sx, cy_c, Z_ALTAR)), Vector((sx, cy_c, Z_ALTAR + 0.16)), 0.32, 0.18, segments=10)
        add_cylinder(bm_gold, Vector((sx, cy_c, Z_ALTAR + 0.16)), Vector((sx, cy_c, Z_ALTAR + 1.55)), 0.065, 0.055, segments=8)
        add_cylinder(bm_gold, Vector((sx, cy_c, Z_ALTAR + 1.52)), Vector((sx, cy_c, Z_ALTAR + 1.60)), 0.22, 0.14, segments=10)
        add_cylinder(bm_glow, Vector((sx, cy_c, Z_ALTAR + 1.60)), Vector((sx, cy_c, Z_ALTAR + 2.12)), 0.065, 0.055, segments=8)

    # 2d. Ornate Bronze & Marble Presbytery Altar Rail (leaving wide open central approach X = -2.4..+2.4)
    for k in range(18):
        ang = -math.pi * 0.92 + math.pi * 0.84 * k / 17.0
        px = 10.2 * math.cos(ang)
        py = 17.5 + 10.2 * math.sin(ang)
        if abs(px) < 2.5 and py < 12.0:
            continue
        add_cylinder(bm_bronze, Vector((px, py, Z_NAVE)), Vector((px, py, Z_NAVE + 1.05)), 0.075, 0.065, segments=8)
        add_cylinder(bm_gold, Vector((px, py, Z_NAVE + 1.02)), Vector((px, py, Z_NAVE + 1.12)), 0.11, 0.09, segments=8)

    # 2e. Grand Carved Oak Pipe Organ Casing in the Apse Gallery (Y = +30.6, Z = 14.5m)
    add_box(bm_oak, (0.0, 30.8, Z_GALLERY + 2.4), (13.6, 1.6, 4.8))
    for ox in (-6.4, -3.2, 0.0, 3.2, 6.4):
        add_box(bm_oak, (ox, 30.2, Z_GALLERY + 4.4), (0.85, 1.9, 8.8))
        add_cylinder(bm_gold, Vector((ox, 30.2, Z_GALLERY + 8.8)), Vector((ox, 30.2, Z_GALLERY + 10.2)), 0.35, 0.06, segments=8)

    # ── 3. Seven Radiating Apse Votive Chapels (Side Altars + Saint Statues + Glowing Candle Stands) ──
    r_chapel = 16.0
    for i in range(7):
        ang = math.pi * (0.08 + 0.84 * i / 6.0)
        cx = r_chapel * math.cos(ang)
        cy = 16.5 + r_chapel * math.sin(ang)
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

        # Wrought-Iron Votive Candle Stand covered in glowing warm candles!
        vx = cx + 1.55 * math.sin(ang) + in_x * 0.65
        vy = cy - 1.55 * math.cos(ang) + in_y * 0.65
        add_box(bm_iron, (vx, vy, Z_NAVE + 0.48), (1.35, 0.48, 0.96), rot_euler=(0, 0, rot_z))
        for ci in range(5):
            off = -0.48 + ci * 0.24
            kx = vx + off * math.cos(rot_z)
            ky = vy + off * math.sin(rot_z)
            add_cylinder(bm_glow, Vector((kx, ky, Z_NAVE + 0.96)), Vector((kx, ky, Z_NAVE + 1.24)), 0.045, 0.04, segments=6)

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

    # 6 Sculpted Holy-Water Fonts flanking Nativity (East), Passion (West) & Glory (South) portals
    for fx, fy in (
        (28.5, -3.4), (28.5, 3.4),
        (-28.5, -3.4), (-28.5, 3.4),
        (-4.6, -43.5), (4.6, -43.5),
    ):
        add_holy_water_font(bm_marble, bm_gold, fx, fy)

    # ── 5. 6 Carved Catalan Oak Confessionals along Outer East & West Nave Walls ──
    for cy_c in (-18.75, -26.25, -33.75):
        add_confessional(bm_oak, bm_gold, bm_glow, 21.1, cy_c, facing_x=-1.0)
        add_confessional(bm_oak, bm_gold, bm_glow, -21.1, cy_c, facing_x=1.0)

    # ── 6. 18 Suspended Gaudí Modernist Chandeliers (Central Nave & Side Aisles at Z = 9.8m) ──
    for cy_l in (-11.25, -18.75, -26.25, -33.75, -41.25):
        add_chandelier(bm_iron, bm_gold, bm_glow, 0.0, cy_l, 11.2, 43.5, radius=2.15)
        for sx in (-1, 1):
            add_chandelier(bm_iron, bm_gold, bm_glow, sx * 11.25, cy_l, 8.8, 29.5, radius=1.35)
    # 3 crossing/transept chandeliers
    for cx_t in (-18.75, 18.75):
        add_chandelier(bm_iron, bm_gold, bm_glow, cx_t, 0.0, 10.5, 43.5, radius=1.95)
    add_chandelier(bm_iron, bm_gold, bm_glow, 0.0, 0.0, 13.5, 57.5, radius=2.85)

    # ── 7. Sculpted White Marble Saint Statues on Carved Pier Corbels along the Nave ──
    for cy_s in (-15.0, -22.5, -30.0, -37.5):
        for sx in (-1, 1):
            px_s = sx * 21.6
            # Carved stone wall corbel bracket at Z = 4.6m
            add_cylinder(bm_marble, Vector((px_s, cy_s, Z_NAVE + 3.0)), Vector((px_s, cy_s, Z_NAVE + 3.6)), 0.16, 0.48, segments=10)
            add_statue_silhouette(bm_marble, Vector((px_s, cy_s, Z_NAVE + 3.6)), scale=1.05, rot_z=math.pi if sx > 0 else 0.0)

    # ── 8. Gaudí Exhibition Showcase in West Outer Aisle (-18.8, Y = -40..-35 & -22..-17) ──
    # 8a. Iconic Inverted Hanging-Chain Funicular Model ("Hängemodell") at (-18.6, -39.5)
    ex, ey = -18.6, -39.5
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

    p_idx = 0
    for row in range(14):
        py = -16.8 - row * 1.72
        if abs(py - (-22.5)) < 1.2 or abs(py - (-30.0)) < 1.2 or abs(py - (-37.5)) < 1.2:
            continue
        for sx in (-1, 1):
            obj = bpy.data.objects.new(f"SidePew_{p_idx}", mesh_side_pew)
            obj.location = (sx * 11.25, py, Z_NAVE)
            bpy.context.collection.objects.link(obj)
            p_idx += 1

    finalize_bmesh_object(bm_carpet, "Furnish_CrimsonCarpet", mats["carpet_crimson"], smooth=False, uv_scale=0.25)
    finalize_bmesh_object(bm_oak, "Furnish_CarvedOak", mats["wood_pew"], smooth=False, uv_scale=0.35)
    finalize_bmesh_object(bm_marble, "Furnish_MarbleLiturgical", mats["white_marble"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_porphyry, "Furnish_BaptisteryPorphyry", mats["porphyry_red"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_gold, "Furnish_GoldAccents", mats["gold_accent"], smooth=True, uv_scale=0.40)
    finalize_bmesh_object(bm_bronze, "Furnish_BronzeFittings", mats["bronze_door"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_iron, "Furnish_ChandelierIron", mats["iron_dark"], smooth=True, uv_scale=0.40)
    finalize_bmesh_object(bm_glow, "Furnish_LanternAndCandleGlow", mats["candle_glow"], smooth=True, uv_scale=0.50, bake_ao=False)
    finalize_bmesh_object(bm_glass, "Furnish_MuseumGlassCases", mats["glass_case"], smooth=False, uv_scale=0.40, bake_ao=False)

    export_glb(os.path.join(MODEL_DIR, "furnishings.glb"))


if __name__ == "__main__":
    build_furnishings()
