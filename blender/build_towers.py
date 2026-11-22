"""Build all 18 completed towers of the Sagrada Família with trencadís pinnacles & viewpoints."""

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
    export_glb,
    finalize_bmesh_object,
    get_materials,
    reset_scene,
)


def add_parabolic_bell_tower(
    bm_stone: bmesh.types.BMesh,
    bm_mosaic: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
    cx: float,
    cy: float,
    z_base: float,
    z_top: float,
    r_base: float,
    r_neck: float,
    ribs: int = 12,
    louver_bands: int = 14,
) -> None:
    """Authentic Gaudí parabolic Apostle bell-tower with vertical ribs, horizontal louvers & trencadís pinnacle."""
    pinnacle_h = 12.5
    z_neck = z_top - pinnacle_h
    shaft_h = z_neck - z_base

    # 1. Inner perforated structural core cylinder
    core_steps = 12
    prev_ring = None
    for si in range(core_steps + 1):
        t = si / core_steps
        z = z_base + t * shaft_h
        # Parabolic taper (catenary-like curvature)
        r = (r_neck + (r_base - r_neck) * ((1.0 - t) ** 0.72)) * 0.78
        ring = [
            bm_stone.verts.new((cx + r * math.cos(2 * math.pi * k / ribs), cy + r * math.sin(2 * math.pi * k / ribs), z))
            for k in range(ribs)
        ]
        if prev_ring is not None:
            for k in range(ribs):
                nk = (k + 1) % ribs
                bm_stone.faces.new((prev_ring[k], prev_ring[nk], ring[nk], ring[k]))
        prev_ring = ring

    # 2. Prominent vertical sculpted stone ribs running full height of the tower
    for k in range(ribs):
        ang = 2.0 * math.pi * k / ribs
        ca, sa = math.cos(ang), math.sin(ang)
        seg_count = 10
        for si in range(seg_count):
            t0 = si / seg_count
            t1 = (si + 1) / seg_count
            z0 = z_base + t0 * shaft_h
            z1 = z_base + t1 * shaft_h
            r0 = r_neck + (r_base - r_neck) * ((1.0 - t0) ** 0.72)
            r1 = r_neck + (r_base - r_neck) * ((1.0 - t1) ** 0.72)
            add_cylinder(
                bm_stone,
                Vector((cx + r0 * ca, cy + r0 * sa, z0)),
                Vector((cx + r1 * ca, cy + r1 * sa, z1)),
                0.38 * (1.0 - 0.3 * t0),
                0.38 * (1.0 - 0.3 * t1),
                segments=6,
                cap=False,
            )

    # 3. Horizontal acoustic louver rings (giving the iconic Sagrada Família honeycombed texture)
    for bi in range(louver_bands):
        t = (bi + 0.5) / louver_bands
        z = z_base + 4.0 + t * (shaft_h - 6.0)
        r = (r_neck + (r_base - r_neck) * ((1.0 - t) ** 0.72)) * 0.96
        add_cylinder(bm_stone, Vector((cx, cy, z - 0.35)), Vector((cx, cy, z + 0.35)), r, r * 0.98, segments=ribs, cap=False)

    # 4. Colorful Venetian-glass trencadís mosaic finial pinnacle (miter / bishop's staff / cross)
    # Lower flaring crown collar
    add_cylinder(bm_mosaic, Vector((cx, cy, z_neck - 0.5)), Vector((cx, cy, z_neck + 2.8)), r_neck * 1.15, r_neck * 1.48, segments=12)
    # Tapered conical trencadís spire
    add_cylinder(bm_mosaic, Vector((cx, cy, z_neck + 2.8)), Vector((cx, cy, z_top - 3.0)), r_neck * 1.42, 0.52, segments=12)
    # Ceramic starburst spheres / rings around the pinnacle
    for ring_z, ring_r in ((z_neck + 3.2, r_neck * 1.45), (z_neck + 6.5, r_neck * 1.05)):
        for k in range(6):
            ang = 2.0 * math.pi * k / 6.0
            add_cylinder(
                bm_gold,
                Vector((cx + ring_r * math.cos(ang), cy + ring_r * math.sin(ang), ring_z - 0.45)),
                Vector((cx + ring_r * math.cos(ang), cy + ring_r * math.sin(ang), ring_z + 0.45)),
                0.42,
                0.28,
                segments=8,
            )
    # Cross / mitre emblem at very top
    add_cylinder(bm_gold, Vector((cx, cy, z_top - 3.2)), Vector((cx, cy, z_top)), 0.24, 0.10, segments=8)
    add_cylinder(bm_gold, Vector((cx - 1.1, cy, z_top - 1.2)), Vector((cx + 1.1, cy, z_top - 1.2)), 0.16, 0.16, segments=8)


def add_star_12_points(bm_star: bmesh.types.BMesh, center: Vector, radius: float = 3.85) -> None:
    """Iconic 12-pointed crystal Star of the Virgin Mary crowning the 138m tower."""
    ret = bmesh.ops.create_icosphere(bm_star, subdivisions=2, radius=radius * 0.40)
    for v in ret["verts"]:
        v.co += center

    # 12 symmetrical 3D rays (icosahedral vertex directions)
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    dirs = [
        Vector((0, 1, phi)), Vector((0, -1, phi)), Vector((0, 1, -phi)), Vector((0, -1, -phi)),
        Vector((1, phi, 0)), Vector((-1, phi, 0)), Vector((1, -phi, 0)), Vector((-1, -phi, 0)),
        Vector((phi, 0, 1)), Vector((-phi, 0, 1)), Vector((phi, 0, -1)), Vector((-phi, 0, -1)),
    ]
    for d in dirs:
        dn = d.normalized()
        add_cylinder(bm_star, center + dn * (radius * 0.25), center + dn * radius, radius * 0.24, 0.04, segments=4, cap=True)


def add_jesus_christ_tower(
    bm_stone: bmesh.types.BMesh,
    bm_mosaic: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
    bm_cross: bmesh.types.BMesh,
) -> None:
    """Central Tower of Jesus Christ (172.5m) with parabolic stone ribs, viewpoint at 136m & 17m four-armed cross."""
    z_base = 56.0
    z_gallery = 136.0
    z_terminal_base = 148.0
    z_cross_base = 155.5
    z_top = 172.5
    r_base = 10.6
    r_neck = 5.4
    ribs = 12

    # 1. Massive octagonal/12-sided ribbed parabolic main lantern shaft (56m -> 136m)
    segs = 16
    prev_ring = None
    for si in range(segs + 1):
        t = si / segs
        z = z_base + t * (z_gallery - z_base)
        r = r_neck + (r_base - r_neck) * ((1.0 - t) ** 0.85)
        ring = [
            bm_stone.verts.new((r * 0.86 * math.cos(2 * math.pi * k / ribs), r * 0.86 * math.sin(2 * math.pi * k / ribs), z))
            for k in range(ribs)
        ]
        if prev_ring is not None:
            for k in range(ribs):
                nk = (k + 1) % ribs
                bm_stone.faces.new((prev_ring[k], prev_ring[nk], ring[nk], ring[k]))
        prev_ring = ring

    # 12 external triangular stone buttress ribs + horizontal stone window rings
    for k in range(ribs):
        ang = 2.0 * math.pi * k / ribs
        ca, sa = math.cos(ang), math.sin(ang)
        for si in range(12):
            t0, t1 = si / 12.0, (si + 1) / 12.0
            z0 = z_base + t0 * (z_gallery - z_base)
            z1 = z_base + t1 * (z_gallery - z_base)
            r0 = r_neck + (r_base - r_neck) * ((1.0 - t0) ** 0.85)
            r1 = r_neck + (r_base - r_neck) * ((1.0 - t1) ** 0.85)
            add_cylinder(
                bm_stone,
                Vector((r0 * ca, r0 * sa, z0)),
                Vector((r1 * ca, r1 * sa, z1)),
                0.72 * (1.0 - 0.3 * t0),
                0.72 * (1.0 - 0.3 * t1),
                segments=6,
                cap=False,
            )

    for bi in range(14):
        t = (bi + 0.5) / 14.0
        z = z_base + 4.0 + t * (z_gallery - z_base - 6.0)
        r = (r_neck + (r_base - r_neck) * ((1.0 - t) ** 0.85)) * 0.96
        add_cylinder(bm_stone, Vector((0, 0, z - 0.5)), Vector((0, 0, z + 0.5)), r, r * 0.98, segments=ribs, cap=False)

    # 2. Walkable Panoramic Viewpoint Gallery Floor & Safety Parapet at Z = 136.0m!
    add_cylinder(bm_stone, Vector((0, 0, z_gallery - 1.2)), Vector((0, 0, z_gallery)), 6.8, 6.8, segments=16, cap=True)
    # Parapet ring around viewpoint (height 1.15m)
    for k in range(16):
        a0 = 2.0 * math.pi * k / 16.0
        a1 = 2.0 * math.pi * (k + 1) / 16.0
        am = 0.5 * (a0 + a1)
        add_box(bm_stone, (6.5 * math.cos(am), 6.5 * math.sin(am), z_gallery + 0.6), (2.55, 0.38, 1.2), rot_euler=(0, 0, am - math.pi / 2.0))
        # Slender stone colonnettes holding upper crown above viewpoint (open panoramic view!)
        if k % 2 == 0:
            add_cylinder(
                bm_stone,
                Vector((6.2 * math.cos(a0), 6.2 * math.sin(a0), z_gallery)),
                Vector((5.4 * math.cos(a0), 5.4 * math.sin(a0), z_terminal_base)),
                0.42,
                0.35,
                segments=8,
            )

    # 3. Upper Crown Terminal (148m -> 155.5m) with ceramic trencadís & gilded bands
    add_cylinder(bm_stone, Vector((0, 0, z_terminal_base)), Vector((0, 0, z_cross_base)), 5.6, 3.2, segments=12, cap=True)
    add_cylinder(bm_mosaic, Vector((0, 0, z_terminal_base + 1.0)), Vector((0, 0, z_terminal_base + 4.8)), 5.4, 4.2, segments=12, cap=False)
    add_cylinder(bm_gold, Vector((0, 0, z_cross_base - 0.6)), Vector((0, 0, z_cross_base + 0.6)), 3.5, 3.1, segments=12, cap=True)

    # 4. Iconic 17m Four-Armed Ceramic & Glass Cross of Jesus Christ (155.5m -> 172.5m)
    arm_z = z_cross_base + 9.2
    # Vertical shaft
    add_cylinder(bm_cross, Vector((0, 0, z_cross_base)), Vector((0, 0, z_top)), 1.65, 1.35, segments=8, cap=True)
    # 4 horizontal arms (facing N, S, E, W — Gaudí's four-armed cross!)
    for d in (Vector((1, 0, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0)), Vector((0, -1, 0))):
        add_cylinder(bm_cross, Vector((0, 0, arm_z)), Vector((0, 0, arm_z)) + d * 6.8, 1.35, 1.05, segments=8, cap=True)
        # Flared glass-mosaic cross arm tips
        add_cylinder(bm_gold, Vector((0, 0, arm_z)) + d * 6.5, Vector((0, 0, arm_z)) + d * 7.2, 1.45, 1.25, segments=8, cap=True)
    # Top finial cap
    add_cylinder(bm_gold, Vector((0, 0, z_top - 0.5)), Vector((0, 0, z_top + 0.6)), 1.55, 0.35, segments=8, cap=True)


def add_mary_tower(
    bm_stone: bmesh.types.BMesh,
    bm_mosaic: bmesh.types.BMesh,
    bm_star: bmesh.types.BMesh,
) -> None:
    """Tower of the Virgin Mary (138.0m) over the Apse (0, +22.5) crowned by the luminous 12-pointed star."""
    cx, cy = 0.0, 22.5
    z_base = 52.0
    z_crown = 123.0
    z_star_center = 134.2
    r_base = 8.4
    r_neck = 4.2
    ribs = 12

    # Hyperboloid tapering blue/white stone shaft
    segs = 14
    prev_ring = None
    for si in range(segs + 1):
        t = si / segs
        z = z_base + t * (z_crown - z_base)
        r = r_neck + (r_base - r_neck) * ((1.0 - t) ** 0.78)
        ring = [
            bm_stone.verts.new((cx + r * 0.88 * math.cos(2 * math.pi * k / ribs), cy + r * 0.88 * math.sin(2 * math.pi * k / ribs), z))
            for k in range(ribs)
        ]
        if prev_ring is not None:
            for k in range(ribs):
                nk = (k + 1) % ribs
                bm_stone.faces.new((prev_ring[k], prev_ring[nk], ring[nk], ring[k]))
        prev_ring = ring

    for k in range(ribs):
        ang = 2.0 * math.pi * k / ribs
        ca, sa = math.cos(ang), math.sin(ang)
        add_cylinder(
            bm_stone,
            Vector((cx + r_base * ca, cy + r_base * sa, z_base)),
            Vector((cx + r_neck * ca, cy + r_neck * sa, z_crown)),
            0.55,
            0.34,
            segments=6,
            cap=False,
        )

    # Flaring blue-and-white trencadís crown petals supporting the Morning Star
    add_cylinder(bm_mosaic, Vector((cx, cy, z_crown - 2.0)), Vector((cx, cy, z_crown + 5.5)), r_neck * 0.95, r_neck * 1.42, segments=12, cap=True)
    # 3 curved white support ribs holding the star aloft
    for k in range(3):
        ang = 2.0 * math.pi * k / 3.0
        p0 = Vector((cx + 3.4 * math.cos(ang), cy + 3.4 * math.sin(ang), z_crown + 4.8))
        p1 = Vector((cx + 0.8 * math.cos(ang), cy + 0.8 * math.sin(ang), z_star_center - 1.2))
        add_cylinder(bm_stone, p0, p1, 0.55, 0.32, segments=8)

    # Luminous 12-pointed Star (diameter ~7.5m, top at 138.0m)
    add_star_12_points(bm_star, Vector((cx, cy, z_star_center)), radius=3.8)


def add_evangelist_tower(
    bm_stone: bmesh.types.BMesh,
    bm_marble: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
    cx: float,
    cy: float,
    angle_out: float,
) -> None:
    """One of the 4 Towers of the Evangelists (135.0m) topped by illuminated white wings & tetramorph sculpture."""
    z_base = 52.0
    z_crown = 121.0
    r_base = 5.4
    r_neck = 2.9
    ribs = 8

    # Parabolic stone shaft
    segs = 12
    prev_ring = None
    for si in range(segs + 1):
        t = si / segs
        z = z_base + t * (z_crown - z_base)
        r = r_neck + (r_base - r_neck) * ((1.0 - t) ** 0.78)
        ring = [
            bm_stone.verts.new((cx + r * 0.86 * math.cos(2 * math.pi * k / ribs), cy + r * 0.86 * math.sin(2 * math.pi * k / ribs), z))
            for k in range(ribs)
        ]
        if prev_ring is not None:
            for k in range(ribs):
                nk = (k + 1) % ribs
                bm_stone.faces.new((prev_ring[k], prev_ring[nk], ring[nk], ring[k]))
        prev_ring = ring

    for k in range(ribs):
        ang = 2.0 * math.pi * k / ribs
        add_cylinder(
            bm_stone,
            Vector((cx + r_base * math.cos(ang), cy + r_base * math.sin(ang), z_base)),
            Vector((cx + r_neck * math.cos(ang), cy + r_neck * math.sin(ang), z_crown)),
            0.42,
            0.25,
            segments=6,
            cap=False,
        )

    # Icosahedron golden lantern collar
    add_cylinder(bm_gold, Vector((cx, cy, z_crown - 0.5)), Vector((cx, cy, z_crown + 3.2)), r_neck * 1.15, r_neck * 0.9, segments=10)

    # White sculpted Evangelist Wings + Tetramorph crest (124m -> 135m)
    # Pair of sculpted stepped feathered white marble wings
    for side in (-1, 1):
        w_ang = angle_out + side * 0.72
        for feather in range(3):
            reach = 2.4 - feather * 0.35
            h_f = 10.6 - feather * 1.4
            p0 = Vector((cx, cy, z_crown + 2.8 + feather * 0.8))
            p1 = Vector((cx + reach * math.cos(w_ang), cy + reach * math.sin(w_ang), z_crown + h_f))
            add_cylinder(bm_marble, p0, p1, 0.78 - feather * 0.14, 0.24, segments=8, cap=True)
    # Central tetramorph figure / open Gospel pedestal
    add_cylinder(bm_marble, Vector((cx, cy, z_crown + 2.8)), Vector((cx, cy, z_crown + 8.6)), 1.65, 1.15, segments=12, cap=True)


def build_towers() -> None:
    reset_scene()
    mats = get_materials()

    bm_nativity_stone = bmesh.new()
    bm_passion_stone = bmesh.new()
    bm_warm_stone = bmesh.new()
    bm_mosaic = bmesh.new()
    bm_gold = bmesh.new()
    bm_marble = bmesh.new()
    bm_star = bmesh.new()
    bm_cross = bmesh.new()

    # ── 1. Tower of Jesus Christ (172.5m) at Crossing Center (0, 0) ──
    add_jesus_christ_tower(bm_warm_stone, bm_mosaic, bm_gold, bm_cross)

    # ── 2. Tower of the Virgin Mary (138.0m) over Apse (0, +22.5) ──
    add_mary_tower(bm_warm_stone, bm_mosaic, bm_star)

    # ── 3. Four Towers of the Evangelists (135.0m) at (±11.5, ±11.5) ──
    for sx in (-1, 1):
        for sy in (-1, 1):
            ang = math.atan2(sy, sx)
            add_evangelist_tower(bm_warm_stone, bm_marble, bm_gold, sx * 11.5, sy * 11.5, ang)

    # ── 4. Four Apostles Towers — Nativity Facade (East, X = +31.5) ──
    nativity_specs = [
        (31.5, -10.8, 98.4, 3.55),
        (31.5, -3.6, 107.0, 3.85),
        (31.5, 3.6, 107.0, 3.85),
        (31.5, 10.8, 98.4, 3.55),
    ]
    for cx, cy, z_top, r_b in nativity_specs:
        add_parabolic_bell_tower(bm_nativity_stone, bm_mosaic, bm_gold, cx, cy, 26.0, z_top, r_b, 1.55)

    # Walkable Nativity Tower Skybridge between inner East towers at Z = 65.0m!
    add_box(bm_nativity_stone, (31.5, 0.0, 64.6), (3.4, 8.2, 0.8))
    add_box(bm_nativity_stone, (33.1, 0.0, 65.6), (0.35, 8.2, 1.3))
    add_box(bm_nativity_stone, (29.9, 0.0, 65.6), (0.35, 8.2, 1.3))

    # Walkable Gaudí Fibonacci Snail-Shell Spiral Staircase inside inner SE Nativity Tower (31.5, -3.6, Z = 14.5m -> 65.0m)!
    st_cx, st_cy = 31.5, -3.6
    st_z0, st_z1 = 14.5, 65.0
    st_steps = 156
    st_turns = 8.5
    # Hollow dramatic central spiral well with thin outer tower cylinder drum (Z = 14..27m below tower shaft)
    add_cylinder(bm_nativity_stone, Vector((st_cx, st_cy, 13.8)), Vector((st_cx, st_cy, 27.0)), 3.85, 3.85, segments=16, cap=False)
    for si in range(st_steps):
        t = si / (st_steps - 1)
        ang = t * st_turns * 2.0 * math.pi
        z = st_z0 + t * (st_z1 - st_z0)
        r_mid = 1.92
        sx = st_cx + r_mid * math.cos(ang)
        sy = st_cy + r_mid * math.sin(ang)
        # Cantilevered sculpted stone tread around hollow central oculus well
        add_box(bm_nativity_stone, (sx, sy, z), (1.75, 0.62, 0.24), rot_euler=(0.0, 0.0, ang))
        # Inner sculpted spiral handrail balustrade along the open snail-shell eye (r = 1.05m)
        if si < st_steps - 1:
            t_n = (si + 1) / (st_steps - 1)
            ang_n = t_n * st_turns * 2.0 * math.pi
            z_n = st_z0 + t_n * (st_z1 - st_z0)
            p_rail0 = Vector((st_cx + 1.05 * math.cos(ang), st_cy + 1.05 * math.sin(ang), z + 0.95))
            p_rail1 = Vector((st_cx + 1.05 * math.cos(ang_n), st_cy + 1.05 * math.sin(ang_n), z_n + 0.95))
            add_cylinder(bm_gold, p_rail0, p_rail1, 0.06, 0.06, segments=6, cap=False)
            if si % 3 == 0:
                add_cylinder(
                    bm_nativity_stone,
                    Vector((st_cx + 1.05 * math.cos(ang), st_cy + 1.05 * math.sin(ang), z)),
                    p_rail0,
                    0.055,
                    0.055,
                    segments=6,
                )

    # ── 5. Four Apostles Towers — Passion Facade (West, X = -31.5) ──
    passion_specs = [
        (-31.5, -10.8, 107.4, 3.65),
        (-31.5, -3.6, 112.2, 3.95),
        (-31.5, 3.6, 112.2, 3.95),
        (-31.5, 10.8, 107.4, 3.65),
    ]
    for cx, cy, z_top, r_b in passion_specs:
        add_parabolic_bell_tower(bm_passion_stone, bm_mosaic, bm_gold, cx, cy, 26.0, z_top, r_b, 1.60)

    # Passion Tower Skybridge at Z = 65.0m (with Ascension sculpture plinth)
    add_box(bm_passion_stone, (-31.5, 0.0, 64.6), (3.4, 8.2, 0.8))
    add_box(bm_passion_stone, (-33.1, 0.0, 65.6), (0.35, 8.2, 1.3))
    add_box(bm_passion_stone, (-29.9, 0.0, 65.6), (0.35, 8.2, 1.3))

    # ── 6. Four Apostles Towers — Glory Facade (South, Y = -49.5, completed design) ──
    glory_specs = [
        (-11.4, -49.5, 112.0, 3.75),
        (-3.8, -49.5, 120.0, 4.10),
        (3.8, -49.5, 120.0, 4.10),
        (11.4, -49.5, 112.0, 3.75),
    ]
    for cx, cy, z_top, r_b in glory_specs:
        add_parabolic_bell_tower(bm_warm_stone, bm_mosaic, bm_gold, cx, cy, 28.0, z_top, r_b, 1.65)

    finalize_bmesh_object(bm_nativity_stone, "Towers_Nativity", mats["nativity_stone"], smooth=True, uv_scale=0.14)
    finalize_bmesh_object(bm_passion_stone, "Towers_Passion", mats["passion_stone"], smooth=True, uv_scale=0.14)
    finalize_bmesh_object(bm_warm_stone, "Towers_CentralAndGlory", mats["sandstone_warm"], smooth=True, uv_scale=0.12)
    finalize_bmesh_object(bm_mosaic, "Towers_TrencadisPinnacles", mats["trencadis"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_gold, "Towers_GoldAccents", mats["gold_accent"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_marble, "Towers_EvangelistSculptures", mats["white_marble"], smooth=True, uv_scale=0.25)
    finalize_bmesh_object(bm_star, "Tower_MaryStar", mats["luminous_star"], smooth=False, uv_scale=0.35)
    finalize_bmesh_object(bm_cross, "Tower_JesusCross", mats["luminous_cross"], smooth=False, uv_scale=0.25)

    export_glb(os.path.join(MODEL_DIR, "towers.glb"))


if __name__ == "__main__":
    build_towers()
