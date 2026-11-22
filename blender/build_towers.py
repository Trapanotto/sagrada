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

    # 1. Slender Parabolic Bell-Tower Core with PIERCED Upper Acoustic Louver Slots (authentic daylight filigree!)
    core_steps = 18
    prev_ring = None
    prev_z = z_base
    skybridge_z = 72.0 if abs(cy + 49.5) < 1.0 else 65.0
    for si in range(core_steps + 1):
        t = si / core_steps
        z = z_base + t * shaft_h
        # Authentic sleeker Gaudí catenary taper (slender iconic silhouette instead of chunky cylinders!)
        r = (r_neck + (r_base - r_neck) * ((1.0 - t) ** 0.62)) * 0.94
        ring = [
            bm_stone.verts.new((cx + r * math.cos(2 * math.pi * k / ribs), cy + r * math.sin(2 * math.pi * k / ribs), z))
            for k in range(ribs)
        ]
        mid_z = 0.5 * (prev_z + z)
        is_bridge_band = (skybridge_z - 0.5) <= mid_z <= (skybridge_z + 4.2)
        # Perforate upper lantern tiers (above Z=58m) by skipping alternate faces around the ribs so light passes through!
        if prev_ring is not None and not is_bridge_band:
            for k in range(ribs):
                if mid_z > 58.0 and (si % 2 == 1) and (k % 2 == 0):
                    continue
                nk = (k + 1) % ribs
                bm_stone.faces.new((prev_ring[k], prev_ring[nk], ring[nk], ring[k]))
        prev_ring = ring
        prev_z = z

    # 2. Prominent vertical sculpted stone ribs running full height of the tower (slender catenary curve)
    for k in range(ribs):
        ang = 2.0 * math.pi * k / ribs
        ca, sa = math.cos(ang), math.sin(ang)
        seg_count = 10
        for si in range(seg_count):
            t0 = si / seg_count
            t1 = (si + 1) / seg_count
            z0 = z_base + t0 * shaft_h
            z1 = z_base + t1 * shaft_h
            r0 = r_neck + (r_base - r_neck) * ((1.0 - t0) ** 0.62)
            r1 = r_neck + (r_base - r_neck) * ((1.0 - t1) ** 0.62)
            add_cylinder(
                bm_stone,
                Vector((cx + r0 * ca, cy + r0 * sa, z0)),
                Vector((cx + r1 * ca, cy + r1 * sa, z1)),
                0.34 * (1.0 - 0.32 * t0),
                0.34 * (1.0 - 0.32 * t1),
                segments=6,
                cap=False,
            )

    # 3. Horizontal acoustic louver rings + SANCTUS / HOSANNA ceramic trencadís collar bands!
    for bi in range(louver_bands):
        t = (bi + 0.5) / louver_bands
        z = z_base + 4.0 + t * (shaft_h - 6.0)
        r = (r_neck + (r_base - r_neck) * ((1.0 - t) ** 0.62)) * 0.97
        if bi in (louver_bands - 3, louver_bands - 1):
            add_cylinder(bm_mosaic, Vector((cx, cy, z - 0.55)), Vector((cx, cy, z + 0.55)), r * 1.04, r * 1.02, segments=ribs, cap=False)
        else:
            add_cylinder(bm_stone, Vector((cx, cy, z - 0.28)), Vector((cx, cy, z + 0.28)), r, r * 0.98, segments=ribs, cap=False)

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
    """Sculpted Gaudí continuous overlapping helical stone staircase inside any of the 18 tower shafts."""
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
        # Solid overlapping stone step treads (0.68m deep, 0.24m thick -> continuous walkable ribbon, zero gaps!)
        add_box(bm_stone, (sx, sy, z), (tread_w, 0.68, 0.24), rot_euler=(0.0, 0.0, ang))
        if si < steps - 1 and si % 3 == 0:
            t_n = min(1.0, (si + 3) / max(1, steps - 1))
            ang_n = sgn * t_n * turns * 2.0 * math.pi
            z_n = z0 + t_n * span
            p0 = Vector((cx + r_rail * math.cos(ang), cy + r_rail * math.sin(ang), z + 0.92))
            p1 = Vector((cx + r_rail * math.cos(ang_n), cy + r_rail * math.sin(ang_n), z_n + 0.92))
            add_cylinder(bm_gold, p0, p1, 0.05, 0.05, segments=5, cap=False)


def add_jesus_christ_tower(
    bm_stone: bmesh.types.BMesh,
    bm_mosaic: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
    bm_cross: bmesh.types.BMesh,
    bm_glass: bmesh.types.BMesh,
) -> None:
    """Central Tower of Jesus Christ (172.5m) with parabolic stone ribs, viewpoint at 136m & 17m four-armed cross."""
    z_base = 56.0
    z_gallery = 136.0
    z_terminal_base = 148.0
    z_cross_base = 155.5
    z_top = 172.5
    # Authentic sleeker 12-sided perforated parabolic silhouette (9.5m base -> 4.8m neck!)
    r_base = 9.5
    r_neck = 4.8
    ribs = 12

    # 1. Iconic Perforated 12-Sided Diagonal Triangular/Diamond Lattice Shaft (Gaudí's Hyperboloid-Fassadengitter!)
    # Open 360° colonnade at 56..60.5m (for all 8 roof bridges) and pierced diamond window bays all the way up to 136m!
    segs = 14
    for si in range(segs):
        t0, t1 = si / segs, (si + 1) / segs
        z0 = z_base + t0 * (z_gallery - z_base)
        z1 = z_base + t1 * (z_gallery - z_base)
        r0 = r_neck + (r_base - r_neck) * ((1.0 - t0) ** 0.76)
        r1 = r_neck + (r_base - r_neck) * ((1.0 - t1) ** 0.76)
        mid_z = 0.5 * (z0 + z1)
        is_open_level = mid_z < 60.5 or mid_z > 133.0
        for k in range(ribs):
            a0 = 2.0 * math.pi * k / ribs
            a1 = 2.0 * math.pi * ((k + 1) % ribs) / ribs
            p00 = Vector((r0 * math.cos(a0), r0 * math.sin(a0), z0))
            p10 = Vector((r0 * math.cos(a1), r0 * math.sin(a1), z0))
            p01 = Vector((r1 * math.cos(a0), r1 * math.sin(a0), z1))
            p11 = Vector((r1 * math.cos(a1), r1 * math.sin(a1), z1))
            # Vertical main corner buttress rib
            add_cylinder(bm_stone, p00, p01, 0.58 * (1.0 - 0.30 * t0), 0.58 * (1.0 - 0.30 * t1), segments=6, cap=False)
            if not is_open_level:
                # Iconic X-braced diagonal triangular window lattice ribs (creates genuine see-through triangular fenestration!)
                add_cylinder(bm_stone, p00, p11, 0.32 * (1.0 - 0.25 * t0), 0.28 * (1.0 - 0.25 * t1), segments=5, cap=False)
                add_cylinder(bm_stone, p10, p01, 0.32 * (1.0 - 0.25 * t0), 0.28 * (1.0 - 0.25 * t1), segments=5, cap=False)
                # Horizontal spandrel ring beam + subtle trencadís mosaic ridge accents on every 3rd tier
                add_cylinder(bm_stone, p00, p10, 0.36 * (1.0 - 0.22 * t0), 0.36 * (1.0 - 0.22 * t0), segments=5, cap=False)
                if si % 3 == 1:
                    add_cylinder(
                        bm_mosaic,
                        Vector((p00.x * 1.015, p00.y * 1.015, p00.z)),
                        Vector((p11.x * 1.015, p11.y * 1.015, p11.z)),
                        0.14,
                        0.14,
                        segments=4,
                        cap=False,
                    )
                    # Translucent triangular glass pane recessed cleanly inside the lattice!
                    v_a = bm_glass.verts.new(Vector((p00.x * 0.94, p00.y * 0.94, p00.z)))
                    v_b = bm_glass.verts.new(Vector((p10.x * 0.94, p10.y * 0.94, p10.z)))
                    v_c = bm_glass.verts.new(Vector((p11.x * 0.94, p11.y * 0.94, p11.z)))
                    v_d = bm_glass.verts.new(Vector((p01.x * 0.94, p01.y * 0.94, p01.z)))
                    bm_glass.faces.new((v_a, v_b, v_c, v_d))

    # 1b. Authentic Suspended Central Glass & Steel Panorama Elevator Shaft INSIDE Tower of Jesus Christ (56m -> 136m)
    # Real-life fidelity: NO elevator cables or rings descend into the sacred open 60m Nave Crossing below!
    # The glass lift begins strictly inside the hollow stone core of the Tower of Jesus Christ above the crossing vault.

    # Walkable Crossing Vault Gallery Ring Deck at Z = 56.0m (connects Roof Skybridges <-> Glass Lift <-> Jesus Spiral Stair!)
    for k in range(16):
        a0 = 2.0 * math.pi * k / 16.0
        r_deck = 5.2
        add_box(bm_stone, (r_deck * math.cos(a0), r_deck * math.sin(a0), z_base - 0.35), (2.5, 5.4, 0.7), rot_euler=(0, 0, a0 + math.pi / 2.0))
        # Leave South boarding doorway (Blender -Y = Three.js +Z, sin(a0) < -0.75) open for unobstructed elevator entry!
        if math.sin(a0) >= -0.75:
            add_box(bm_gold, (2.3 * math.cos(a0), 2.3 * math.sin(a0), z_base + 0.55), (0.95, 0.09, 1.05), rot_euler=(0, 0, a0 + math.pi / 2.0))

    # Slender stainless/gilded elevator guide rails + circular glass shaft enclosing the central panorama lift (56m -> 142m)
    # Anchored solidly into structural collar rings at Z = 56m and Z = 136m (ZERO elements hanging into the Nave below!)
    for z_ring in (z_base + 0.06, z_gallery + 0.06):
        for k in range(12):
            a0 = 2.0 * math.pi * k / 12.0
            add_box(bm_gold, (2.15 * math.cos(a0), 2.15 * math.sin(a0), z_ring), (1.15, 0.22, 0.14), rot_euler=(0, 0, a0 + math.pi / 2.0))
    for k in range(6):
        ang = 2.0 * math.pi * k / 6.0
        add_cylinder(bm_gold, Vector((2.15 * math.cos(ang), 2.15 * math.sin(ang), z_base - 0.2)), Vector((2.15 * math.cos(ang), 2.15 * math.sin(ang), z_gallery + 6.5)), 0.09, 0.09, segments=6)
    add_cylinder(bm_glass, Vector((0, 0, z_base)), Vector((0, 0, z_gallery + 4.5)), 2.08, 2.08, segments=16, cap=False)

    # 2. Walkable Panoramic Viewpoint Gallery Annular Ring Deck (r = 2.18..6.8m -> 100% OPEN central Elevator Shaft Opening!)
    for k in range(24):
        a0 = 2.0 * math.pi * k / 24.0
        r_ring = 4.50
        add_box(bm_stone, (r_ring * math.cos(a0), r_ring * math.sin(a0), z_gallery - 0.55), (1.95, 4.65, 1.1), rot_euler=(0, 0, a0 + math.pi / 2.0))
    # Low open pierced panoramic railing (0.90m high) — guarantees completely unobstructed 360° Barcelona views!
    for k in range(16):
        a0 = 2.0 * math.pi * k / 16.0
        a1 = 2.0 * math.pi * (k + 1) / 16.0
        am = 0.5 * (a0 + a1)
        # Low curb plinth + slender top handrail + vertical balusters
        add_box(bm_stone, (6.5 * math.cos(am), 6.5 * math.sin(am), z_gallery + 0.14), (2.55, 0.32, 0.28), rot_euler=(0, 0, am - math.pi / 2.0))
        add_box(bm_stone, (6.5 * math.cos(am), 6.5 * math.sin(am), z_gallery + 0.88), (2.55, 0.30, 0.14), rot_euler=(0, 0, am - math.pi / 2.0))
        add_cylinder(bm_stone, Vector((6.5 * math.cos(am), 6.5 * math.sin(am), z_gallery + 0.26)), Vector((6.5 * math.cos(am), 6.5 * math.sin(am), z_gallery + 0.84)), 0.08, 0.07, segments=6)
        # Slender stone colonnettes holding upper crown above viewpoint (open panoramic view!)
        if k % 2 == 0:
            add_cylinder(
                bm_stone,
                Vector((6.2 * math.cos(a0), 6.2 * math.sin(a0), z_gallery)),
                Vector((5.4 * math.cos(a0), 5.4 * math.sin(a0), z_terminal_base)),
                0.38,
                0.32,
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
    # Authentic sleeker Virgin Mary Tower with perforated diagonal star-lattice fenestration!
    r_base = 7.6
    r_neck = 3.5
    ribs = 12

    segs = 12
    for si in range(segs):
        t0, t1 = si / segs, (si + 1) / segs
        z0 = z_base + t0 * (z_crown - z_base)
        z1 = z_base + t1 * (z_crown - z_base)
        r0 = r_neck + (r_base - r_neck) * ((1.0 - t0) ** 0.72)
        r1 = r_neck + (r_base - r_neck) * ((1.0 - t1) ** 0.72)
        mid_z = 0.5 * (z0 + z1)
        is_open = mid_z < 60.0 or mid_z > 116.5
        for k in range(ribs):
            a0 = 2.0 * math.pi * k / ribs
            a1 = 2.0 * math.pi * ((k + 1) % ribs) / ribs
            p00 = Vector((cx + r0 * math.cos(a0), cy + r0 * math.sin(a0), z0))
            p10 = Vector((cx + r0 * math.cos(a1), cy + r0 * math.sin(a1), z0))
            p01 = Vector((cx + r1 * math.cos(a0), cy + r1 * math.sin(a0), z1))
            p11 = Vector((cx + r1 * math.cos(a1), cy + r1 * math.sin(a1), z1))
            add_cylinder(bm_stone, p00, p01, 0.44 * (1.0 - 0.30 * t0), 0.44 * (1.0 - 0.30 * t1), segments=6, cap=False)
            if not is_open:
                # Diagonal diamond lattice framing blue-white starlight slits!
                add_cylinder(bm_stone, p00, p11, 0.26 * (1.0 - 0.25 * t0), 0.22 * (1.0 - 0.25 * t1), segments=5, cap=False)
                add_cylinder(bm_stone, p10, p01, 0.26 * (1.0 - 0.25 * t0), 0.22 * (1.0 - 0.25 * t1), segments=5, cap=False)
                add_cylinder(bm_stone, p00, p10, 0.28 * (1.0 - 0.22 * t0), 0.28 * (1.0 - 0.22 * t0), segments=5, cap=False)
                if si >= segs - 4:
                    add_cylinder(
                        bm_mosaic,
                        Vector((cx + (p00.x - cx) * 1.015, cy + (p00.y - cy) * 1.015, p00.z)),
                        Vector((cx + (p11.x - cx) * 1.015, cy + (p11.y - cy) * 1.015, p11.z)),
                        0.14,
                        0.14,
                        segments=4,
                        cap=False,
                    )

    # Flaring 12-petal blue-and-white trencadís Morning Star crown chalice
    for k in range(12):
        ang = 2.0 * math.pi * k / 12.0
        p0 = Vector((cx + r_neck * 0.92 * math.cos(ang), cy + r_neck * 0.92 * math.sin(ang), z_crown - 1.5))
        p1 = Vector((cx + r_neck * 1.48 * math.cos(ang), cy + r_neck * 1.48 * math.sin(ang), z_crown + 5.8))
        add_cylinder(bm_mosaic, p0, p1, 0.62, 0.22, segments=6, cap=True)
    # 3 curved white support ribs holding the 12-pointed star aloft
    for k in range(3):
        ang = 2.0 * math.pi * k / 3.0
        p0 = Vector((cx + 3.4 * math.cos(ang), cy + 3.4 * math.sin(ang), z_crown + 4.8))
        p1 = Vector((cx + 0.8 * math.cos(ang), cy + 0.8 * math.sin(ang), z_star_center - 1.2))
        add_cylinder(bm_stone, p0, p1, 0.50, 0.30, segments=8)

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
    """One of the 4 Towers of the Evangelists (135.0m) with pierced diagonal lattice & illuminated white wings."""
    z_base = 52.0
    z_crown = 121.0
    r_base = 4.9
    r_neck = 2.5
    ribs = 8

    # Perforated parabolic diamond lattice shaft (open at 52..60m roof bridge & 112..116m observation deck!)
    segs = 11
    for si in range(segs):
        t0, t1 = si / segs, (si + 1) / segs
        z0 = z_base + t0 * (z_crown - z_base)
        z1 = z_base + t1 * (z_crown - z_base)
        r0 = r_neck + (r_base - r_neck) * ((1.0 - t0) ** 0.72)
        r1 = r_neck + (r_base - r_neck) * ((1.0 - t1) ** 0.72)
        mid_z = 0.5 * (z0 + z1)
        is_open = mid_z < 60.0 or (112.5 <= mid_z <= 116.5)
        for k in range(ribs):
            a0 = 2.0 * math.pi * k / ribs
            a1 = 2.0 * math.pi * ((k + 1) % ribs) / ribs
            p00 = Vector((cx + r0 * math.cos(a0), cy + r0 * math.sin(a0), z0))
            p10 = Vector((cx + r0 * math.cos(a1), cy + r0 * math.sin(a1), z0))
            p01 = Vector((cx + r1 * math.cos(a0), cy + r1 * math.sin(a0), z1))
            p11 = Vector((cx + r1 * math.cos(a1), cy + r1 * math.sin(a1), z1))
            add_cylinder(bm_stone, p00, p01, 0.36 * (1.0 - 0.30 * t0), 0.36 * (1.0 - 0.30 * t1), segments=6, cap=False)
            if not is_open:
                add_cylinder(bm_stone, p00, p11, 0.22 * (1.0 - 0.25 * t0), 0.19 * (1.0 - 0.25 * t1), segments=5, cap=False)
                add_cylinder(bm_stone, p10, p01, 0.22 * (1.0 - 0.25 * t0), 0.19 * (1.0 - 0.25 * t1), segments=5, cap=False)
                add_cylinder(bm_stone, p00, p10, 0.24 * (1.0 - 0.22 * t0), 0.24 * (1.0 - 0.22 * t0), segments=5, cap=False)

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
    bm_internal_stairs = bmesh.new()
    bm_internal_rails = bmesh.new()
    bm_mosaic = bmesh.new()
    bm_gold = bmesh.new()
    bm_marble = bmesh.new()
    bm_star = bmesh.new()
    bm_cross = bmesh.new()
    bm_glass = bmesh.new()

    # ── 1. Tower of Jesus Christ (172.5m) with Glass Panorama Elevator Shaft & Helical Staircase ──
    add_jesus_christ_tower(bm_warm_stone, bm_mosaic, bm_gold, bm_cross, bm_glass)
    add_spiral_stair_shaft(bm_internal_stairs, bm_internal_rails, 0.0, 0.0, 56.0, 136.0, r_mid=3.65, tread_w=1.85, turns_per_10m=1.1, step_rise=0.34, clockwise=True)

    # ── 2. Tower of the Virgin Mary (138.0m) over Apse (0, +22.5) + Internal Spiral Staircase ──
    add_mary_tower(bm_warm_stone, bm_mosaic, bm_star)
    add_spiral_stair_shaft(bm_internal_stairs, bm_internal_rails, 0.0, 22.5, 56.0, 118.0, r_mid=2.85, tread_w=1.40, turns_per_10m=1.25, step_rise=0.34)

    # ── 3. Four Towers of the Evangelists (135.0m) at (±11.5, ±11.5) + Internal Spiral Staircases ──
    for sx in (-1, 1):
        for sy in (-1, 1):
            ang = math.atan2(sy, sx)
            add_evangelist_tower(bm_warm_stone, bm_marble, bm_gold, sx * 11.5, sy * 11.5, ang)
            add_spiral_stair_shaft(bm_internal_stairs, bm_internal_rails, sx * 11.5, sy * 11.5, 56.0, 114.0, r_mid=1.95, tread_w=1.22, turns_per_10m=1.35, step_rise=0.36, clockwise=(sx * sy > 0))

    # ── 4. Four Apostles Towers — Nativity Facade (East, X = +31.5) + ALL 4 Internal Spiral Staircases ──
    nativity_specs = [
        (31.5, -10.8, 98.4, 3.55),
        (31.5, -3.6, 107.0, 3.85),
        (31.5, 3.6, 107.0, 3.85),
        (31.5, 10.8, 98.4, 3.55),
    ]
    for idx, (cx, cy, z_top, r_b) in enumerate(nativity_specs):
        add_parabolic_bell_tower(bm_nativity_stone, bm_mosaic, bm_gold, cx, cy, 26.0, z_top, r_b, 1.55)
        # Start closed tower drum at Z = 18.6m so the 14.5..18.6m Tower-Base Gallery doorway is 100% OPEN!
        add_cylinder(bm_nativity_stone, Vector((cx, cy, 18.6)), Vector((cx, cy, 27.0)), r_b * 0.96, r_b * 0.96, segments=14, cap=False)
        add_spiral_stair_shaft(bm_internal_stairs, bm_internal_rails, cx, cy, 14.5, 65.0, r_mid=1.62, tread_w=1.28, turns_per_10m=1.68, step_rise=0.30 if idx == 1 else 0.34, clockwise=(idx % 2 == 1))

    # Walkable Nativity Tower Skybridge connecting all East towers at Z = 65.0m!
    add_box(bm_nativity_stone, (31.5, 0.0, 64.6), (3.4, 21.8, 0.8))
    add_box(bm_nativity_stone, (33.1, 0.0, 65.45), (0.30, 21.8, 0.95))
    add_box(bm_nativity_stone, (29.9, 0.0, 65.45), (0.30, 21.8, 0.95))

    # ── 5. Four Apostles Towers — Passion Facade (West, X = -31.5) + ALL 4 Internal Spiral Staircases ──
    passion_specs = [
        (-31.5, -10.8, 107.4, 3.65),
        (-31.5, -3.6, 112.2, 3.95),
        (-31.5, 3.6, 112.2, 3.95),
        (-31.5, 10.8, 107.4, 3.65),
    ]
    for idx, (cx, cy, z_top, r_b) in enumerate(passion_specs):
        add_parabolic_bell_tower(bm_passion_stone, bm_mosaic, bm_gold, cx, cy, 26.0, z_top, r_b, 1.60)
        add_cylinder(bm_passion_stone, Vector((cx, cy, 18.6)), Vector((cx, cy, 27.0)), r_b * 0.96, r_b * 0.96, segments=14, cap=False)
        add_spiral_stair_shaft(bm_internal_stairs, bm_internal_rails, cx, cy, 14.5, 65.0, r_mid=1.65, tread_w=1.28, turns_per_10m=1.68, step_rise=0.30 if idx == 1 else 0.34, clockwise=(idx % 2 == 0))

    # Walkable Passion Tower Skybridge connecting all West towers at Z = 65.0m!
    add_box(bm_passion_stone, (-31.5, 0.0, 64.6), (3.4, 21.8, 0.8))
    add_box(bm_passion_stone, (-33.1, 0.0, 65.45), (0.30, 21.8, 0.95))
    add_box(bm_passion_stone, (-29.9, 0.0, 65.45), (0.30, 21.8, 0.95))

    # ── 6. Four Apostles Towers — Glory Facade (South, Y = -49.5) + ALL 4 Internal Spiral Staircases ──
    glory_specs = [
        (-11.4, -49.5, 112.0, 3.75),
        (-3.8, -49.5, 120.0, 4.10),
        (3.8, -49.5, 120.0, 4.10),
        (11.4, -49.5, 112.0, 3.75),
    ]
    for idx, (cx, cy, z_top, r_b) in enumerate(glory_specs):
        add_parabolic_bell_tower(bm_warm_stone, bm_mosaic, bm_gold, cx, cy, 28.0, z_top, r_b, 1.65)
        add_cylinder(bm_warm_stone, Vector((cx, cy, 18.6)), Vector((cx, cy, 29.0)), r_b * 0.96, r_b * 0.96, segments=14, cap=False)
        add_spiral_stair_shaft(bm_internal_stairs, bm_internal_rails, cx, cy, 14.5, 72.0, r_mid=1.70, tread_w=1.30, turns_per_10m=1.62, step_rise=0.34, clockwise=(idx % 2 == 1))

    # Walkable Glory Tower Skybridge at Z = 72.0m!
    add_box(bm_warm_stone, (0.0, -49.5, 71.6), (22.8, 3.4, 0.8))
    add_box(bm_warm_stone, (0.0, -47.9, 72.6), (22.8, 0.35, 1.3))
    add_box(bm_warm_stone, (0.0, -51.1, 72.6), (22.8, 0.35, 1.3))

    # ── 7. Complete Walkable Pedestrian Network: All 18 Towers, Base Galleries, Roof Stair-Bridges & Viewpoints! ──
    def add_stepped_skybridge(
        bm: bmesh.types.BMesh,
        p0: Vector,
        p1: Vector,
        width: float = 2.8,
        parapet_h: float = 1.15,
    ) -> None:
        """Creates a walkable stone bridge or stepped roof staircase with side parapets between any two 3D points."""
        delta = p1 - p0
        horiz = math.hypot(delta.x, delta.y)
        ang = math.atan2(delta.y, delta.x)
        dz = delta.z
        nx = -math.sin(ang)
        ny = math.cos(ang)

        if abs(dz) < 0.25:
            mid = (p0 + p1) * 0.5
            add_box(bm, (mid.x, mid.y, mid.z - 0.35), (horiz + 0.6, width, 0.7), rot_euler=(0, 0, ang))
            for side in (-1, 1):
                ox = nx * side * (width * 0.5 - 0.16)
                oy = ny * side * (width * 0.5 - 0.16)
                add_box(bm, (mid.x + ox, mid.y + oy, mid.z + parapet_h * 0.5), (horiz + 0.4, 0.30, parapet_h), rot_euler=(0, 0, ang))
        else:
            steps = max(12, int(abs(dz) / 0.38))
            step_len = (horiz / steps) + 0.24
            for si in range(steps):
                t = (si + 0.5) / steps
                sx = p0.x + delta.x * t
                sy = p0.y + delta.y * t
                sz = p0.z + dz * t
                add_box(bm, (sx, sy, sz - 0.28), (step_len, width, 0.56), rot_euler=(0, 0, ang))
                for side in (-1, 1):
                    ox = nx * side * (width * 0.5 - 0.16)
                    oy = ny * side * (width * 0.5 - 0.16)
                    add_box(bm, (sx + ox, sy + oy, sz + parapet_h * 0.5), (step_len + 0.08, 0.28, parapet_h), rot_euler=(0, 0, ang))

    # 7a. Tower-Base Connecting Galleries at Z = 14.5m linking ALL 12 Apostle Towers to the Emporen!
    # East Nativity base gallery (connects all 4 Nativity spiral staircases at X = +31.5)
    add_stepped_skybridge(bm_nativity_stone, Vector((31.5, -11.0, 14.5)), Vector((31.5, 11.0, 14.5)), width=3.2)
    # West Passion Empore bridge + full 4-tower base gallery at X = -31.5
    add_stepped_skybridge(bm_passion_stone, Vector((-21.0, -14.5, 14.5)), Vector((-31.5, -3.6, 14.5)), width=3.2)
    add_stepped_skybridge(bm_passion_stone, Vector((-31.5, -11.0, 14.5)), Vector((-31.5, 11.0, 14.5)), width=3.2)
    # South Choir Gallery -> Glory base connectors + full 4-tower base gallery at Y = -49.5
    for sx in (-3.8, 3.8):
        add_stepped_skybridge(bm_warm_stone, Vector((sx, -43.5, 14.5)), Vector((sx, -49.5, 14.5)), width=3.0)
    add_stepped_skybridge(bm_warm_stone, Vector((-11.8, -49.5, 14.5)), Vector((11.8, -49.5, 14.5)), width=3.2)

    # 7b. Upper Roof Skybridges (Z = 56.0m) from Jesus Crossing Gallery -> All 4 Evangelist Towers & Virgin Mary Tower!
    for sx in (-1, 1):
        for sy in (-1, 1):
            p_start = Vector((sx * 4.8, sy * 4.8, 56.0))
            p_end = Vector((sx * 11.5, sy * 11.5, 56.0))
            add_stepped_skybridge(bm_warm_stone, p_start, p_end, width=2.5)
            # Top panoramic observation deck at Z = 114.0m inside each Evangelist Tower
            add_cylinder(bm_warm_stone, Vector((sx * 11.5, sy * 11.5, 113.3)), Vector((sx * 11.5, sy * 11.5, 114.0)), 3.6, 3.6, segments=12, cap=True)
    # North Apse Roof Skybridge: Jesus Crossing (0, 6.2, 56m) -> Virgin Mary Tower (0, +22.5, 56m) + 118m Viewpoint!
    add_stepped_skybridge(bm_warm_stone, Vector((0.0, 6.2, 56.0)), Vector((0.0, 22.5, 56.0)), width=2.8)
    add_cylinder(bm_warm_stone, Vector((0.0, 22.5, 117.3)), Vector((0.0, 22.5, 118.0)), 4.6, 4.6, segments=14, cap=True)

    # 7c. Stepped Stone Roof Stair-Bridges connecting Jesus Crossing (56m) <-> East/West (65m) & South Glory (72m)!
    add_stepped_skybridge(bm_nativity_stone, Vector((6.8, 0.0, 56.0)), Vector((30.2, 0.0, 65.0)), width=2.8)
    add_stepped_skybridge(bm_passion_stone, Vector((-6.8, 0.0, 56.0)), Vector((-30.2, 0.0, 65.0)), width=2.8)
    add_stepped_skybridge(bm_warm_stone, Vector((0.0, -6.8, 56.0)), Vector((0.0, -48.2, 72.0)), width=3.0)

    finalize_bmesh_object(bm_nativity_stone, "Towers_Nativity", mats["nativity_stone"], smooth=True, uv_scale=0.14)
    finalize_bmesh_object(bm_passion_stone, "Towers_Passion", mats["passion_stone"], smooth=True, uv_scale=0.14)
    finalize_bmesh_object(bm_warm_stone, "Towers_CentralAndGlory", mats["sandstone_warm"], smooth=True, uv_scale=0.12)
    finalize_bmesh_object(bm_internal_stairs, "Towers_InternalStaircases", mats["sandstone_warm"], smooth=False, uv_scale=0.16, bake_ao=False)
    finalize_bmesh_object(bm_internal_rails, "Towers_InternalStairRails", mats["gold_accent"], smooth=True, uv_scale=0.35, bake_ao=False)
    finalize_bmesh_object(bm_mosaic, "Towers_TrencadisPinnacles", mats["trencadis"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_gold, "Towers_GoldAccents", mats["gold_accent"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_marble, "Towers_EvangelistSculptures", mats["white_marble"], smooth=True, uv_scale=0.25)
    finalize_bmesh_object(bm_star, "Tower_MaryStar", mats["luminous_star"], smooth=False, uv_scale=0.35)
    finalize_bmesh_object(bm_cross, "Tower_JesusCross", mats["luminous_cross"], smooth=False, uv_scale=0.25)
    finalize_bmesh_object(bm_glass, "Tower_JesusElevatorShaftGlass", mats["glass_case"], smooth=True, uv_scale=0.25, bake_ao=False)

    export_glb(os.path.join(MODEL_DIR, "towers.glb"))


if __name__ == "__main__":
    build_towers()
