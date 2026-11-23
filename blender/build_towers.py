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
    add_ellipsoid,
    add_lathe,
    export_glb,
    finalize_bmesh_object,
    get_materials,
    make_shared_mesh,
    place_mesh_instance,
    reset_scene,
)


PINNACLE_H = 12.5
PINNACLE_R_NECK = 1.6


def add_tower_shell(
    bm: bmesh.types.BMesh,
    cx: float,
    cy: float,
    z0: float,
    z1: float,
    radius_at,
    sectors: int,
    rows: int,
    cell_kind,
    thickness: float = 0.32,
    louvres: int = 0,
    bm_alt=None,
    alt_from_z: float = 1e9,
) -> None:
    """Solid double-skinned tower shaft built from (row x sector) cells.

    cell_kind(row, k, z_lo, z_hi, ang_mid) returns 'solid', 'open' (clean doorway / gallery opening)
    or 'louvre' (acoustic slot with inclined stone slats, Gaudí's bell-tower louvres). Openings get
    proper jamb faces so the masonry reads as thick stone instead of paper-thin cages.
    Cells above alt_from_z are written into bm_alt (e.g. white ceramic cladding) when given.
    """
    rings_o: list[list[Vector]] = []
    rings_i: list[list[Vector]] = []
    zs = [z0 + (z1 - z0) * i / rows for i in range(rows + 1)]
    for z in zs:
        t = (z - z0) / max(z1 - z0, 1e-6)
        r = radius_at(t)
        ro, ri = [], []
        for k in range(sectors):
            a = 2.0 * math.pi * k / sectors
            ro.append(Vector((cx + r * math.cos(a), cy + r * math.sin(a), z)))
            ri.append(Vector((cx + (r - thickness) * math.cos(a), cy + (r - thickness) * math.sin(a), z)))
        rings_o.append(ro)
        rings_i.append(ri)

    kinds = [[cell_kind(row, k, zs[row], zs[row + 1], 2.0 * math.pi * (k + 0.5) / sectors) for k in range(sectors)] for row in range(rows)]

    def quad(b, a, bb, c, d):
        # Jambs & slats: own vertices so they shade crisply (flat) against the smooth shaft
        b.faces.new((b.verts.new(a), b.verts.new(bb), b.verts.new(c), b.verts.new(d)))

    vcache: dict[tuple[int, str, int, int], bmesh.types.BMVert] = {}

    def sv(b, side: str, row: int, k: int) -> bmesh.types.BMVert:
        key = (id(b), side, row, k)
        v = vcache.get(key)
        if v is None:
            v = b.verts.new((rings_o if side == "o" else rings_i)[row][k])
            vcache[key] = v
        return v

    for row in range(rows):
        for k in range(sectors):
            nk = (k + 1) % sectors
            kind = kinds[row][k]
            target = bm_alt if (bm_alt is not None and zs[row] >= alt_from_z) else bm
            o00, o10 = rings_o[row][k], rings_o[row][nk]
            o01, o11 = rings_o[row + 1][k], rings_o[row + 1][nk]
            i00, i10 = rings_i[row][k], rings_i[row][nk]
            i01, i11 = rings_i[row + 1][k], rings_i[row + 1][nk]
            if kind == "solid":
                # Smooth shared-vertex outer & inner skins (round parabolic silhouette, no faceting)
                target.faces.new((sv(target, "o", row, k), sv(target, "o", row, nk), sv(target, "o", row + 1, nk), sv(target, "o", row + 1, k)))
                target.faces.new((sv(target, "i", row, nk), sv(target, "i", row, k), sv(target, "i", row + 1, k), sv(target, "i", row + 1, nk)))
                continue
            # Jambs only where the neighbouring cell is solid (keeps shared edges clean & cheap)
            below = kinds[row - 1][k] if row > 0 else "solid"
            above = kinds[row + 1][k] if row < rows - 1 else "solid"
            left = kinds[row][(k - 1) % sectors]
            right = kinds[row][nk]
            if below == "solid":
                quad(target, o00, i00, i10, o10)
            if above == "solid":
                quad(target, o11, i11, i01, o01)
            if left == "solid":
                quad(target, o01, i01, i00, o00)
            if right == "solid":
                quad(target, o10, i10, i11, o11)
            if kind == "louvre" and louvres > 0:
                # Inclined acoustic slats: outer edge low, inner edge high (sheds rain, hides the bells)
                h = (zs[row + 1] - zs[row])
                for j in range(louvres):
                    f = (j + 0.75) / (louvres + 0.5)
                    zl = zs[row] + h * f
                    rise = h / (louvres + 0.5) * 0.55
                    inset = 0.02
                    a0 = o00.lerp(o01, f) + (i00 - o00) * inset
                    a1 = o10.lerp(o11, f) + (i10 - o10) * inset
                    b0 = i00.lerp(i01, f) + Vector((0, 0, rise))
                    b1 = i10.lerp(i11, f) + Vector((0, 0, rise))
                    a0.z = a1.z = zl
                    t_off = Vector((0, 0, 0.09))
                    quad(target, a0 + t_off, a1 + t_off, b1 + t_off, b0 + t_off)  # top
                    quad(target, b0, b1, a1, a0)  # underside


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
    pinnacle_meshes: list,
    tower_idx: int,
    sectors: int = 16,
    rows: int = 30,
) -> None:
    """Gaudí parabolic Apostle bell-tower: solid stone shaft pierced by helical bands of louvred
    openings between vertical ribs, SANCTUS collars and the trencadís mitre/ring pinnacle."""
    z_neck = z_top - PINNACLE_H
    shaft_h = z_neck - z_base
    skybridge_z = 72.0 if abs(cy + 49.5) < 1.0 else 65.0
    is_glory = abs(cy + 49.5) < 1.0

    def radius_at(t: float) -> float:
        return r_neck + (r_base - r_neck) * ((1.0 - t) ** 0.62)

    def is_bridge_dir(ang: float) -> bool:
        ca, sa = math.cos(ang), math.sin(ang)
        if is_glory:
            return abs(ca) > 0.72 or (abs(cx) < 5.0 and sa > 0.72)
        return abs(sa) > 0.72 or (abs(cy) < 5.0 and ((cx > 0 and ca < -0.72) or (cx < 0 and ca > 0.72)))

    def cell_kind(row, k, z_lo, z_hi, ang):
        # Skybridge doorways (same angular sectors & band as the walkway network in CollisionSystem)
        if z_lo < skybridge_z + 3.4 and z_hi > skybridge_z - 0.3 and is_bridge_dir(ang):
            return "open"
        if z_lo < 33.0 or z_hi > z_neck - 1.0:
            return "solid"
        # Helical bands of louvred slots: 4 interleaved helices climbing one sector per row
        if (k + row) % 4 == 0:
            return "louvre"
        # Upper lantern zone gets a second, counter-rotating helix (denser filigree near the top)
        if z_lo > z_base + shaft_h * 0.62 and (k - row) % 8 == 0:
            return "louvre"
        return "solid"

    add_tower_shell(bm_stone, cx, cy, z_base, z_neck, lambda t: radius_at(t) * 0.97, sectors, rows, cell_kind, thickness=0.30, louvres=3)

    # Vertical stone ribs on every second sector boundary (clean gaps at the skybridge doorways)
    for k in range(0, sectors, 2):
        ang = 2.0 * math.pi * k / sectors
        ca, sa = math.cos(ang), math.sin(ang)
        door_rib = is_bridge_dir(ang) or is_bridge_dir(ang + math.pi / sectors) or is_bridge_dir(ang - math.pi / sectors)
        seg_count = 10
        for si in range(seg_count):
            t0, t1 = si / seg_count, (si + 1) / seg_count
            z0, z1 = z_base + t0 * shaft_h, z_base + t1 * shaft_h
            if door_rib and z0 < skybridge_z + 3.6 and z1 > skybridge_z - 0.5:
                continue
            r0, r1 = radius_at(t0), radius_at(t1)
            add_cylinder(
                bm_stone,
                Vector((cx + r0 * ca, cy + r0 * sa, z0)),
                Vector((cx + r1 * ca, cy + r1 * sa, z1)),
                0.24 * (1.0 - 0.3 * t0),
                0.24 * (1.0 - 0.3 * t1),
                segments=6,
                cap=False,
            )

    # SANCTUS stone string-courses + two glazed trencadís collars near the neck
    bands = 6
    for bi in range(bands):
        t = (bi + 0.5) / bands
        z = z_base + 4.0 + t * (shaft_h - 6.0)
        if (skybridge_z - 0.8) <= z <= (skybridge_z + 3.8):
            continue
        r = radius_at(t) * 1.0
        if bi >= bands - 2:
            add_cylinder(bm_mosaic, Vector((cx, cy, z - 0.5)), Vector((cx, cy, z + 0.5)), r * 1.03, r * 1.02, segments=sectors, cap=False)
        else:
            add_cylinder(bm_stone, Vector((cx, cy, z - 0.22)), Vector((cx, cy, z + 0.22)), r * 1.01, r * 1.0, segments=sectors, cap=False)

    # Shared (GPU-instanced) trencadís pinnacle: stem, white pearls & gilded mitre/cross
    s = r_neck / PINNACLE_R_NECK
    face_out = math.atan2(cy, cx) if not is_glory else -math.pi * 0.5
    for mesh in pinnacle_meshes:
        place_mesh_instance(f"{mesh.name}_{tower_idx}", mesh, (cx, cy, z_neck), rot_z=face_out, scale=(s, s, 1.0))


def build_apostle_pinnacle_meshes(mats) -> list:
    """One trencadís bishop's-mitre pinnacle, built once in local space (origin = tower neck)."""
    rn = PINNACLE_R_NECK
    h = PINNACLE_H
    bm_stem = bmesh.new()
    bm_pearl = bmesh.new()
    bm_gold = bmesh.new()

    # Faceted octagonal glazed shaft: flaring collar, bulb, slender waist, then the mitre socket
    add_lathe(
        bm_stem, 0.0, 0.0,
        [(-0.5, rn * 1.10), (0.6, rn * 1.32), (2.2, rn * 1.52), (3.4, rn * 1.38), (4.6, rn * 0.98),
         (6.2, rn * 0.72), (7.0, rn * 0.80), (7.6, rn * 0.62)],
        segments=8, cap_top=True, phase=math.pi / 8,
    )
    # Mitre: a pointed vertical lens, flattened front-to-back, glazed in trencadís
    lens = []
    n = 10
    for i in range(n + 1):
        t = i / n
        z = 7.4 + t * (h - 1.9 - 7.4)
        w = 1.45 * math.sin(math.pi * min(1.0, t * 1.08)) ** 0.8 + 0.05
        lens.append((z, w))
    add_lathe(bm_stem, 0.0, 0.0, lens, segments=12, cap_bottom=True, cap_top=True, squash=(0.42, 1.0))
    # White pearls on short spikes: lower crown ring of 8 + upper ring of 6 (the iconic white balls)
    for ring_z, ring_r, cnt, pr in ((2.4, rn * 1.78, 8, 0.36), (5.4, rn * 1.12, 6, 0.27)):
        for k in range(cnt):
            a = 2.0 * math.pi * (k + 0.5) / cnt
            p = Vector((ring_r * math.cos(a), ring_r * math.sin(a), ring_z + 0.25))
            add_cylinder(bm_gold, Vector((ring_r * 0.72 * math.cos(a), ring_r * 0.72 * math.sin(a), ring_z)), p, 0.07, 0.05, segments=5, cap=False)
            add_ellipsoid(bm_pearl, p, (pr, pr, pr), subdivisions=1)
    # Gilded mitre rim (two arcs) + cross piercing the top + ring (the bishop's ring motif)
    for side in (-1, 1):
        pts = [(side * 1.45 * math.sin(math.pi * min(1.0, (i / 8) * 1.08)) ** 0.8, 7.4 + (i / 8) * (h - 1.9 - 7.4)) for i in range(9)]
        for (y0, z0), (y1, z1) in zip(pts[:-1], pts[1:]):
            add_cylinder(bm_gold, Vector((0.0, y0, z0)), Vector((0.0, y1, z1)), 0.11, 0.11, segments=5, cap=False)
    add_cylinder(bm_gold, Vector((0.0, 0.0, h - 2.2)), Vector((0.0, 0.0, h + 0.4)), 0.17, 0.12, segments=6)
    add_cylinder(bm_gold, Vector((0.0, -0.75, h - 0.6)), Vector((0.0, 0.75, h - 0.6)), 0.12, 0.12, segments=6)
    ring = []
    for i in range(13):
        a = 2.0 * math.pi * i / 12
        ring.append(Vector((0.62 * math.cos(a), 0.0, 9.6 + 0.62 * math.sin(a))))
    for p0, p1 in zip(ring[:-1], ring[1:]):
        add_cylinder(bm_gold, p0 + Vector((0.55, 0, 0)), p1 + Vector((0.55, 0, 0)), 0.1, 0.1, segments=5, cap=False)

    return [
        make_shared_mesh(bm_stem, "Towers_TrencadisPinnacles_Mitre", mats["trencadis"], uv_scale=0.6),
        make_shared_mesh(bm_pearl, "Towers_TrencadisPinnacles_Pearls", mats["white_marble"], uv_scale=0.8, bake_ao=False),
        make_shared_mesh(bm_gold, "Towers_GoldAccents_Mitre", mats["gold_accent"], uv_scale=0.6, bake_ao=False),
    ]


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
    bm_ceramic: bmesh.types.BMesh,
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

    def r_j(t: float) -> float:
        return r_neck + (r_base - r_neck) * ((1.0 - t) ** 0.76)

    # 1. Solid stone parabolic shaft with tall slit windows between pilaster ribs; the upper third is clad
    #    in white glazed ceramic like the real tower. Open colonnade at 56..60.5m (8 roof bridges), the
    #    76m north doorway to the Mary skybridge and the 136m panoramic gallery stay exactly as before.
    def kind_j(row, k, z_lo, z_hi, ang):
        zm = 0.5 * (z_lo + z_hi)
        if zm < 62.0 or zm > 133.0:
            return "open"
        if 73.5 <= zm <= 81.5 and math.radians(58) <= ang <= math.radians(122):
            return "open"
        if k % 3 == 1 and row % 4 != 3 and zm > 64.0:
            return "open"
        return "solid"

    add_tower_shell(bm_stone, 0.0, 0.0, z_base, z_gallery, r_j, 24, 26, kind_j, thickness=0.36, bm_alt=bm_ceramic, alt_from_z=112.0)
    for k in range(ribs):
        a0 = 2.0 * math.pi * k / ribs
        for si in range(14):
            t0, t1 = si / 14, (si + 1) / 14
            z0 = z_base + t0 * (z_gallery - z_base)
            z1 = z_base + t1 * (z_gallery - z_base)
            if k == 3 and z0 < 81.5 and z1 > 73.5:
                continue  # clean 76m north doorway
            r0, r1 = r_j(t0), r_j(t1)
            add_cylinder(
                bm_stone if z0 < 112.0 else bm_ceramic,
                Vector((r0 * math.cos(a0), r0 * math.sin(a0), z0)),
                Vector((r1 * math.cos(a0), r1 * math.sin(a0), z1)),
                0.52 * (1.0 - 0.30 * t0),
                0.52 * (1.0 - 0.30 * t1),
                segments=6,
                cap=False,
            )
    # Horizontal string courses + glazed trencadís bands marking the window tiers
    for zb in (64.0, 76.3 + 6.0, 100.6, 112.0, 124.4):
        t = (zb - z_base) / (z_gallery - z_base)
        add_cylinder(bm_mosaic if zb >= 112.0 else bm_stone, Vector((0, 0, zb - 0.3)), Vector((0, 0, zb + 0.3)), r_j(t) + 0.08, r_j(t) + 0.06, segments=24, cap=False)

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

    def r_m(t: float) -> float:
        return r_neck + (r_base - r_neck) * ((1.0 - t) ** 0.72)

    # Solid parabolic shaft with tall window slits; south doorway at 76m (Jesus skybridge) and the open
    # 118m star gallery are kept in exactly the same bands as the walkway network.
    def kind_m(row, k, z_lo, z_hi, ang):
        zm = 0.5 * (z_lo + z_hi)
        if zm > 116.5:
            return "open"
        if z_lo < 80.5 and z_hi > 75.0 and math.radians(232) <= ang <= math.radians(308):
            return "open"
        if zm < 62.0:
            return "solid"
        if k % 3 == 1 and row % 4 != 3:
            return "open"
        return "solid"

    add_tower_shell(bm_stone, cx, cy, z_base, z_crown, r_m, 24, 21, kind_m, thickness=0.32)
    for k in range(ribs):
        a0 = 2.0 * math.pi * k / ribs
        for si in range(12):
            t0, t1 = si / 12, (si + 1) / 12
            z0 = z_base + t0 * (z_crown - z_base)
            z1 = z_base + t1 * (z_crown - z_base)
            if k == 9 and z0 < 81.0 and z1 > 74.5:
                continue  # south doorway
            r0, r1 = r_m(t0), r_m(t1)
            add_cylinder(
                bm_stone,
                Vector((cx + r0 * math.cos(a0), cy + r0 * math.sin(a0), z0)),
                Vector((cx + r1 * math.cos(a0), cy + r1 * math.sin(a0), z1)),
                0.40 * (1.0 - 0.30 * t0),
                0.40 * (1.0 - 0.30 * t1),
                segments=6,
                cap=False,
            )
    # Blue-and-white glazed trencadís bands on the upper tiers (the Marian colours)
    for zb in (98.0, 106.5, 114.5):
        t = (zb - z_base) / (z_crown - z_base)
        add_cylinder(bm_mosaic, Vector((cx, cy, zb - 0.35)), Vector((cx, cy, zb + 0.35)), r_m(t) + 0.08, r_m(t) + 0.06, segments=24, cap=False)

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
    kind: str,
) -> None:
    """One of the 4 Towers of the Evangelists (135.0m): slit-windowed parabolic shaft crowned by its tetramorph."""
    z_base = 52.0
    z_crown = 121.0
    r_base = 4.9
    r_neck = 2.5
    ribs = 8

    def r_e(t: float) -> float:
        return r_neck + (r_base - r_neck) * ((1.0 - t) ** 0.72)

    inward = math.atan2(-cy, -cx) % (2.0 * math.pi)

    # Solid parabolic shaft with slit windows; doorway toward the 56m crossing bridge and the open
    # 112.5..116.5m observation gallery keep the exact bands the walkway network expects.
    def kind_e(row, k, z_lo, z_hi, ang):
        zm = 0.5 * (z_lo + z_hi)
        if 112.5 <= zm <= 116.5:
            return "open"
        if zm < 60.0:
            d = abs(((ang - inward + math.pi) % (2.0 * math.pi)) - math.pi)
            return "open" if d < math.radians(52) else "solid"
        if k % 2 == 1 and row % 3 != 2:
            return "open"
        return "solid"

    add_tower_shell(bm_stone, cx, cy, z_base, z_crown, r_e, 16, 16, kind_e, thickness=0.26)
    for k in range(0, ribs):
        a0 = 2.0 * math.pi * k / ribs
        for si in range(10):
            t0, t1 = si / 10, (si + 1) / 10
            z0 = z_base + t0 * (z_crown - z_base)
            z1 = z_base + t1 * (z_crown - z_base)
            d = abs(((a0 - inward + math.pi) % (2.0 * math.pi)) - math.pi)
            if z0 < 60.5 and d < math.radians(40):
                continue  # clean doorway toward the crossing bridge
            r0, r1 = r_e(t0), r_e(t1)
            add_cylinder(
                bm_stone,
                Vector((cx + r0 * math.cos(a0), cy + r0 * math.sin(a0), z0)),
                Vector((cx + r1 * math.cos(a0), cy + r1 * math.sin(a0), z1)),
                0.30 * (1.0 - 0.30 * t0),
                0.30 * (1.0 - 0.30 * t1),
                segments=6,
                cap=False,
            )

    # Glazed lantern collar
    add_cylinder(bm_gold, Vector((cx, cy, z_crown - 0.5)), Vector((cx, cy, z_crown + 1.2)), r_neck * 1.12, r_neck * 1.0, segments=12)
    # White ceramic lantern pedestal carrying the tetramorph figure (124m -> 135m)
    add_lathe(
        bm_marble, cx, cy,
        [(z_crown + 1.0, r_neck * 0.95), (z_crown + 2.0, r_neck * 1.08), (z_crown + 3.0, r_neck * 0.8),
         (z_crown + 4.0, r_neck * 0.92), (z_crown + 4.4, r_neck * 0.7)],
        segments=12, cap_top=True,
    )
    add_tetramorph(bm_marble, bm_gold, cx, cy, z_crown + 4.3, angle_out, kind)


def add_tetramorph(bm_w: bmesh.types.BMesh, bm_gold: bmesh.types.BMesh, cx: float, cy: float, z: float, face: float, kind: str) -> None:
    """Simplified but recognisable silhouettes of the four Evangelist symbols crowning their towers:
    winged man (Matthew), lion (Mark), ox (Luke) and eagle (John), ~6m tall, facing outward."""
    f = Vector((math.cos(face), math.sin(face), 0.0))
    s = Vector((-math.sin(face), math.cos(face), 0.0))
    c = Vector((cx, cy, z))

    def wing(side: int, base: Vector, span: float, height: float, lift: float) -> None:
        # Feathered wing: three overlapping flattened ellipsoids fanning up and outward
        for i, (sp, ht) in enumerate(((1.0, 1.0), (0.82, 0.78), (0.6, 0.55))):
            p = base + s * side * span * 0.5 * sp + Vector((0, 0, height * 0.45 * ht + lift))
            add_ellipsoid(bm_w, p, (0.22, span * 0.55 * sp, height * 0.55 * ht), subdivisions=1, rot_z=face, roll=-side * (0.5 + 0.18 * i))

    if kind == "angel":
        add_lathe(bm_w, cx, cy, [(z, 1.15), (z + 1.6, 0.95), (z + 3.0, 0.62), (z + 3.6, 0.5), (z + 3.9, 0.32)], segments=10, cap_bottom=True)
        add_ellipsoid(bm_w, c + Vector((0, 0, 4.4)) + f * 0.05, (0.48, 0.44, 0.58), subdivisions=2)
        for side in (-1, 1):
            add_cylinder(bm_w, c + Vector((0, 0, 3.3)) + s * side * 0.55, c + Vector((0, 0, 2.6)) + s * side * 0.35 + f * 0.75, 0.2, 0.16, segments=6)
            wing(side, c + Vector((0, 0, 2.3)) - f * 0.45, 2.6, 3.6, 0.6)
        add_ellipsoid(bm_gold, c + Vector((0, 0, 5.05)) - f * 0.1, (0.7, 0.7, 0.08), subdivisions=1, tilt=0.25)  # halo
    elif kind == "lion":
        add_ellipsoid(bm_w, c + Vector((0, 0, 1.9)), (1.9, 0.85, 0.95), subdivisions=2, rot_z=face, tilt=-0.18)
        add_ellipsoid(bm_w, c + Vector((0, 0, 3.0)) + f * 1.35, (1.0, 1.15, 1.15), subdivisions=2, rot_z=face)  # mane
        add_ellipsoid(bm_w, c + Vector((0, 0, 3.05)) + f * 2.05, (0.55, 0.48, 0.5), subdivisions=1, rot_z=face)  # muzzle
        for fx, sy in ((1.1, -1), (1.1, 1), (-1.2, -1), (-1.2, 1)):
            add_cylinder(bm_w, c + f * fx + s * sy * 0.45 + Vector((0, 0, 1.4)), c + f * fx * 1.05 + s * sy * 0.5, 0.3, 0.24, segments=6)
        add_cylinder(bm_w, c - f * 1.8 + Vector((0, 0, 2.2)), c - f * 2.5 + Vector((0, 0, 3.2)), 0.12, 0.08, segments=5)
        for side in (-1, 1):
            wing(side, c + Vector((0, 0, 2.4)) - f * 0.2, 2.2, 2.8, 0.4)
    elif kind == "ox":
        add_ellipsoid(bm_w, c + Vector((0, 0, 2.0)), (2.0, 1.0, 1.05), subdivisions=2, rot_z=face)
        add_ellipsoid(bm_w, c + Vector((0, 0, 2.7)) + f * 2.0, (0.75, 0.55, 0.62), subdivisions=1, rot_z=face, tilt=0.35)
        for side in (-1, 1):
            base = c + Vector((0, 0, 3.15)) + f * 1.9 + s * side * 0.35
            add_cylinder(bm_w, base, base + s * side * 0.6 + Vector((0, 0, 0.35)), 0.13, 0.09, segments=5)
            add_cylinder(bm_w, base + s * side * 0.6 + Vector((0, 0, 0.35)), base + s * side * 0.7 + Vector((0, 0, 0.95)) + f * 0.15, 0.09, 0.03, segments=5)
        for fx, sy in ((1.2, -1), (1.2, 1), (-1.2, -1), (-1.2, 1)):
            add_cylinder(bm_w, c + f * fx + s * sy * 0.5 + Vector((0, 0, 1.4)), c + f * fx + s * sy * 0.5, 0.34, 0.28, segments=6)
        for side in (-1, 1):
            wing(side, c + Vector((0, 0, 2.6)) - f * 0.3, 2.2, 2.8, 0.4)
    else:  # eagle
        add_ellipsoid(bm_w, c + Vector((0, 0, 2.0)), (0.8, 0.75, 1.7), subdivisions=2, rot_z=face, tilt=0.12)
        add_ellipsoid(bm_w, c + Vector((0, 0, 3.85)) + f * 0.3, (0.55, 0.45, 0.5), subdivisions=1, rot_z=face)
        add_cylinder(bm_w, c + Vector((0, 0, 3.8)) + f * 0.75, c + Vector((0, 0, 3.55)) + f * 1.35, 0.2, 0.04, segments=5)  # beak
        for side in (-1, 1):
            wing(side, c + Vector((0, 0, 2.6)), 4.2, 3.4, 0.9)
        add_cylinder(bm_w, c - f * 0.5, c - f * 1.3 + Vector((0, 0, -0.2)), 0.5, 0.15, segments=6)  # tail fan


def build_towers() -> None:
    reset_scene()
    mats = get_materials()

    bm_nativity_stone = bmesh.new()
    bm_passion_stone = bmesh.new()
    bm_warm_stone = bmesh.new()
    bm_internal_stairs = bmesh.new()
    bm_internal_rails = bmesh.new()
    bm_roof_stairs = bmesh.new()
    bm_mosaic = bmesh.new()
    bm_gold = bmesh.new()
    bm_marble = bmesh.new()
    bm_star = bmesh.new()
    bm_cross = bmesh.new()
    bm_glass = bmesh.new()
    bm_ceramic = bmesh.new()
    pinnacle_meshes = build_apostle_pinnacle_meshes(mats)

    # ── 1. Tower of Jesus Christ (172.5m) with Glass Panorama Elevator Shaft & Helical Staircase ──
    add_jesus_christ_tower(bm_warm_stone, bm_mosaic, bm_gold, bm_cross, bm_glass, bm_ceramic)
    add_spiral_stair_shaft(bm_internal_stairs, bm_internal_rails, 0.0, 0.0, 56.0, 136.0, r_mid=3.25, tread_w=1.55, turns_per_10m=1.1, step_rise=0.34, clockwise=True)

    # ── 2. Tower of the Virgin Mary (138.0m) over Apse (0, +22.5) + Internal Spiral Staircase (starts ABOVE 74.5m Apse Vault!) ──
    add_mary_tower(bm_warm_stone, bm_mosaic, bm_star)
    add_spiral_stair_shaft(bm_internal_stairs, bm_internal_rails, 0.0, 22.5, 76.0, 118.0, r_mid=2.45, tread_w=1.25, turns_per_10m=1.25, step_rise=0.34)
    # Mary Tower 76.0m annular entry landing (leaves inner 1.7m shaft eye open above the vault & stays strictly inside outer walls)
    for k in range(16):
        a0 = 2.0 * math.pi * k / 16.0
        add_box(
            bm_warm_stone,
            (2.90 * math.cos(a0), 22.5 + 2.90 * math.sin(a0), 75.65),
            (1.60, 2.20, 0.70),
            rot_euler=(0.0, 0.0, a0 + math.pi * 0.5),
        )

    # ── 3. Four Towers of the Evangelists (135.0m) at (±11.5, ±11.5) + Internal Spiral Staircases ──
    for sx in (-1, 1):
        for sy in (-1, 1):
            ang = math.atan2(sy, sx)
            # Blender (x, y) -> CollisionSystem names: (-,-) Mark, (-,+) Luke, (+,-) Matthew, (+,+) John
            kind = {(-1, -1): "lion", (-1, 1): "ox", (1, -1): "angel", (1, 1): "eagle"}[(sx, sy)]
            add_evangelist_tower(bm_warm_stone, bm_marble, bm_gold, sx * 11.5, sy * 11.5, ang, kind)
            add_spiral_stair_shaft(bm_internal_stairs, bm_internal_rails, sx * 11.5, sy * 11.5, 56.0, 114.0, r_mid=1.68, tread_w=1.04, turns_per_10m=1.35, step_rise=0.36, clockwise=(sx * sy > 0))

    # ── 4. Four Apostles Towers — Nativity Facade (East, X = +31.5) + ALL 4 Internal Spiral Staircases ──
    nativity_specs = [
        (31.5, -10.8, 98.4, 3.55),
        (31.5, -3.6, 107.0, 3.85),
        (31.5, 3.6, 107.0, 3.85),
        (31.5, 10.8, 98.4, 3.55),
    ]
    for idx, (cx, cy, z_top, r_b) in enumerate(nativity_specs):
        add_parabolic_bell_tower(bm_nativity_stone, bm_mosaic, bm_gold, cx, cy, 26.0, z_top, r_b, 1.55, pinnacle_meshes, idx)
        # Start closed tower drum at Z = 18.6m so the 14.5..18.6m Tower-Base Gallery doorway is 100% OPEN!
        add_cylinder(bm_nativity_stone, Vector((cx, cy, 18.6)), Vector((cx, cy, 27.0)), r_b * 0.96, r_b * 0.96, segments=14, cap=False)
        add_spiral_stair_shaft(bm_internal_stairs, bm_internal_rails, cx, cy, 14.5, 65.0, r_mid=1.38, tread_w=1.04, turns_per_10m=1.68, step_rise=0.30 if idx == 1 else 0.34, clockwise=(idx % 2 == 1))

    # ── 5. Four Apostles Towers — Passion Facade (West, X = -31.5) + ALL 4 Internal Spiral Staircases ──
    passion_specs = [
        (-31.5, -10.8, 107.4, 3.65),
        (-31.5, -3.6, 112.2, 3.95),
        (-31.5, 3.6, 112.2, 3.95),
        (-31.5, 10.8, 107.4, 3.65),
    ]
    for idx, (cx, cy, z_top, r_b) in enumerate(passion_specs):
        add_parabolic_bell_tower(bm_passion_stone, bm_mosaic, bm_gold, cx, cy, 26.0, z_top, r_b, 1.60, pinnacle_meshes, 4 + idx)
        add_cylinder(bm_passion_stone, Vector((cx, cy, 18.6)), Vector((cx, cy, 27.0)), r_b * 0.96, r_b * 0.96, segments=14, cap=False)
        add_spiral_stair_shaft(bm_internal_stairs, bm_internal_rails, cx, cy, 14.5, 65.0, r_mid=1.38, tread_w=1.04, turns_per_10m=1.68, step_rise=0.30 if idx == 1 else 0.34, clockwise=(idx % 2 == 0))

    # ── 6. Four Apostles Towers — Glory Facade (South, Y = -49.5) + ALL 4 Internal Spiral Staircases ──
    glory_specs = [
        (-11.4, -49.5, 112.0, 3.75),
        (-3.8, -49.5, 120.0, 4.10),
        (3.8, -49.5, 120.0, 4.10),
        (11.4, -49.5, 112.0, 3.75),
    ]
    for idx, (cx, cy, z_top, r_b) in enumerate(glory_specs):
        add_parabolic_bell_tower(bm_warm_stone, bm_mosaic, bm_gold, cx, cy, 28.0, z_top, r_b, 1.65, pinnacle_meshes, 8 + idx)
        add_cylinder(bm_warm_stone, Vector((cx, cy, 18.6)), Vector((cx, cy, 29.0)), r_b * 0.96, r_b * 0.96, segments=14, cap=False)
        add_spiral_stair_shaft(bm_internal_stairs, bm_internal_rails, cx, cy, 14.5, 72.0, r_mid=1.38, tread_w=1.04, turns_per_10m=1.62, step_rise=0.34, clockwise=(idx % 2 == 1))

    # ── 7. Complete Walkable Pedestrian Network: All 18 Towers, Segmented Between-Tower Galleries, Roof Stair-Bridges & Viewpoints! ──
    def add_stepped_skybridge(
        bm: bmesh.types.BMesh,
        p0: Vector,
        p1: Vector,
        width: float = 2.6,
        parapet_h: float = 1.15,
        bm_stairs: bmesh.types.BMesh | None = None,
    ) -> None:
        """Creates a walkable stone bridge or stepped roof staircase with side parapets strictly between towers."""
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
                sx = p0.x + delta.x * t
                sy = p0.y + delta.y * t
                sz = p0.z + dz * t
                add_box(target_stairs, (sx, sy, sz - 0.28), (step_len, width, 0.56), rot_euler=(0, 0, ang))
                for side in (-1, 1):
                    ox = nx * side * (width * 0.5 - 0.16)
                    oy = ny * side * (width * 0.5 - 0.16)
                    add_box(bm, (sx + ox, sy + oy, sz + parapet_h * 0.5), (step_len + 0.08, 0.28, parapet_h), rot_euler=(0, 0, ang))

    # 7a. Tower-Base Connecting Galleries (Z = 14.5m) & Upper Skybridges (Z = 65m/72m) strictly BETWEEN the 4 tower shafts!
    for tx, bm_side, z_sky in ((31.5, bm_nativity_stone, 65.0), (-31.5, bm_passion_stone, 65.0)):
        for y_a, y_b in ((-8.9, -5.5), (-1.7, 1.7), (5.5, 8.9)):
            add_stepped_skybridge(bm_side, Vector((tx, y_a, 14.5)), Vector((tx, y_b, 14.5)), width=2.6)
            add_stepped_skybridge(bm_side, Vector((tx, y_a, z_sky)), Vector((tx, y_b, z_sky)), width=2.6)

    for x_a, x_b in ((-9.5, -5.7), (-1.9, 1.9), (5.7, 9.5)):
        add_stepped_skybridge(bm_warm_stone, Vector((x_a, -49.5, 14.5)), Vector((x_b, -49.5, 14.5)), width=2.6)
        add_stepped_skybridge(bm_warm_stone, Vector((x_a, -49.5, 72.0)), Vector((x_b, -49.5, 72.0)), width=2.6)

    # Entry stubs from Emporen / South Choir into the clear between-tower gaps (ZERO spiral intersection!)
    add_stepped_skybridge(bm_passion_stone, Vector((-21.0, -14.5, 14.5)), Vector((-30.1, -7.2, 14.5)), width=2.6)
    for sx_c in (-7.6, 0.0, 7.6):
        add_stepped_skybridge(bm_warm_stone, Vector((sx_c, -43.5, 14.5)), Vector((sx_c, -48.0, 14.5)), width=2.6)

    # 7b. Upper Roof Skybridges (Z = 56.0m) from Jesus Crossing Gallery -> All 4 Evangelist Towers (ends cleanly at tower rim!)
    for sx in (-1, 1):
        for sy in (-1, 1):
            p_start = Vector((sx * 5.2, sy * 5.2, 56.0))
            p_end = Vector((sx * 9.8, sy * 9.8, 56.0))
            add_stepped_skybridge(bm_warm_stone, p_start, p_end, width=2.4)
            # Top panoramic observation deck at Z = 114.0m seated cleanly INSIDE each Evangelist Tower (r = 2.65m < 2.96m!)
            add_cylinder(bm_warm_stone, Vector((sx * 11.5, sy * 11.5, 113.3)), Vector((sx * 11.5, sy * 11.5, 114.0)), 2.65, 2.65, segments=12, cap=True)

    # Horizontal 76.0m North Skybridge: Jesus Tower Spiral outer edge (0, 4.05, 76m) -> Virgin Mary Tower (0, 19.5, 76m), 100% CLEAR ABOVE 74.5m Apse Vault!
    add_box(bm_warm_stone, (0.0, 11.78, 75.65), (2.6, 15.45, 0.70))
    for side in (-1, 1):
        add_box(bm_warm_stone, (side * 1.15, 11.4, 76.55), (0.28, 13.8, 1.15))
    # 118m observation deck seated cleanly INSIDE Mary Tower (r = 3.65m < 4.10m!)
    add_cylinder(bm_warm_stone, Vector((0.0, 22.5, 117.3)), Vector((0.0, 22.5, 118.0)), 3.65, 3.65, segments=14, cap=True)

    # 7c. Stepped Stone Roof Stair-Bridges connecting Jesus Crossing (56m) <-> East/West Gap 1-2 (65m) & South Glory Gap 1-2 (72m)!
    add_stepped_skybridge(bm_nativity_stone, Vector((7.2, 0.0, 56.0)), Vector((30.1, 0.0, 65.0)), width=2.6, bm_stairs=bm_roof_stairs)
    add_stepped_skybridge(bm_passion_stone, Vector((-7.2, 0.0, 56.0)), Vector((-30.1, 0.0, 65.0)), width=2.6, bm_stairs=bm_roof_stairs)
    add_stepped_skybridge(bm_warm_stone, Vector((0.0, -7.2, 56.0)), Vector((0.0, -48.0, 72.0)), width=2.8, bm_stairs=bm_roof_stairs)

    finalize_bmesh_object(bm_nativity_stone, "Towers_Nativity", mats["nativity_stone"], smooth=True, uv_scale=0.14, weathering=0.4, ao_vert_limit=120000)
    finalize_bmesh_object(bm_passion_stone, "Towers_Passion", mats["passion_stone"], smooth=True, uv_scale=0.14)
    finalize_bmesh_object(bm_warm_stone, "Towers_CentralAndGlory", mats["sandstone_warm"], smooth=True, uv_scale=0.12, ao_vert_limit=120000)
    finalize_bmesh_object(bm_ceramic, "Towers_CentralAndGlory_Ceramic", mats["white_marble"], smooth=True, uv_scale=0.2)
    finalize_bmesh_object(bm_internal_stairs, "Towers_InternalStaircases", mats["sandstone_warm"], smooth=False, uv_scale=0.16, bake_ao=False)
    finalize_bmesh_object(bm_internal_rails, "Towers_InternalStairRails", mats["gold_accent"], smooth=True, uv_scale=0.35, bake_ao=False)
    finalize_bmesh_object(bm_roof_stairs, "Towers_RoofStairs", mats["sandstone_warm"], smooth=False, uv_scale=0.16, bake_ao=False)
    finalize_bmesh_object(bm_mosaic, "Towers_TrencadisPinnacles", mats["trencadis"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_gold, "Towers_GoldAccents", mats["gold_accent"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_marble, "Towers_EvangelistSculptures", mats["white_marble"], smooth=True, uv_scale=0.25)
    finalize_bmesh_object(bm_star, "Tower_MaryStar", mats["luminous_star"], smooth=False, uv_scale=0.35)
    finalize_bmesh_object(bm_cross, "Tower_JesusCross", mats["luminous_cross"], smooth=False, uv_scale=0.25)
    finalize_bmesh_object(bm_glass, "Tower_JesusElevatorShaftGlass", mats["glass_case"], smooth=True, uv_scale=0.25, bake_ao=False)

    export_glb(os.path.join(MODEL_DIR, "towers.glb"))


if __name__ == "__main__":
    build_towers()
