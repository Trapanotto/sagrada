"""Build the walkable cloister (closed rectangle round the church), the four corner buildings (two
sacristies, Baptistery, Penitence chapel), the Assumption chapel, and the crypt under the apse with
its two spiral stairs and Gaudí's tomb.

All plan positions, radii, levels and extents come from blender/layout.py.
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
    Z_NAVE,
    add_box,
    add_cylinder,
    add_ellipsoid,
    add_lathe,
    add_swept_tube,
    export_glb,
    finalize_bmesh_object,
    get_materials,
    reset_scene,
    save_candle_anchors,
)
from layout import (
    APSE_PIER_ANGLES_DEG,
    ASSUMPTION_CHAPEL,
    BOCABELLA_TOMB_POS,
    CLOISTER_CLEAR_WIDTH,
    CLOISTER_HEIGHT,
    CLOISTER_WALKS,
    CLOISTER_WIDTH,
    CORNER_BUILDINGS,
    CRYPT_ALTAR_POS,
    CRYPT_CENTER,
    CRYPT_CHAPEL_BACK_R,
    CRYPT_CHAPEL_FRONT_R,
    CRYPT_FLOOR_Z,
    CRYPT_HALF_WIDTH,
    CRYPT_KEYSTONE,
    CRYPT_PIER_COUNT,
    CRYPT_PIER_RING_R,
    CRYPT_SOUTH_CHAPEL_DEPTH,
    CRYPT_SOUTH_CHAPEL_X,
    CRYPT_SOUTH_WALL_Y,
    CRYPT_STAIRS,
    CRYPT_STAIR_BOTTOM_DOOR,
    CRYPT_STAIR_TOP_DOOR,
    CRYPT_WALL_OUTER_R,
    GAUDI_TOMB_POS,
    GLORY,
    NATIVITY,
    PASSION,
    PRESBYTERY_FRONT_Y,
    PRESBYTERY_HALF_WIDTH,
    PRESBYTERY_RADIUS,
    Z_CRYPT_VAULT_LOW,
    ground_z,
)
from interior_lib import (
    add_annulus_sector,
    add_clustered_pier,
    add_groin_vault_cell,
    add_paraboloid_dome,
    add_ruled_hyperboloid_shell,
    add_square_tile_with_hole,
    add_wall_with_openings,
    add_web_vault_sector,
    finalize_oriented,
)

Z_GROUND_EPS = 0.0         # façade porch slabs sit 0.04 below Z_NAVE, so the walk floors stay at the layout level
CRYPT_WALL_TOP = Z_NAVE - 0.75   # 0.45: under the 0.7 m nave floor slab


def box_span(bm, x0, x1, y0, y1, z0, z1):
    if x1 - x0 < 1e-4 or y1 - y0 < 1e-4 or z1 - z0 < 1e-4:
        return
    add_box(bm, (0.5 * (x0 + x1), 0.5 * (y0 + y1), 0.5 * (z0 + z1)), (x1 - x0, y1 - y0, z1 - z0))


# ─────────────────────────────────────────────────────────────────────────────
# Cloister walks
# ─────────────────────────────────────────────────────────────────────────────

def walk_segments() -> list[tuple[str, float, float, float, float, bool]]:
    """(walk, x0, y0, x1, y1, roofed) pieces of the four walks. Where a walk crosses a façade porch the
    porch (façade package) provides walls and roof; the walk keeps only its floor there."""
    segs = []
    e = CLOISTER_WALKS["east"]
    # the walk passes under the outer Nativity tower bases (|y| 16 .. 18.4, soffit z 6.0, façade package):
    # the roofed walk starts just beyond them
    nat = NATIVITY["halfWidth"] + 2.5
    segs += [("east", e[0], e[1], e[2], -nat, True), ("east", e[0], -nat, e[2], nat, False), ("east", e[0], nat, e[2], e[3], True)]
    w = CLOISTER_WALKS["west"]
    pas = PASSION["halfWidth"]
    segs += [("west", w[0], w[1], w[2], -pas, True), ("west", w[0], -pas, w[2], pas, False), ("west", w[0], pas, w[2], w[3], True)]
    n = CLOISTER_WALKS["north"]
    ac = ASSUMPTION_CHAPEL
    segs += [("north", n[0], n[1], ac["x0"], n[3], True), ("north", ac["x1"], n[1], n[2], n[3], True)]
    s = CLOISTER_WALKS["south"]
    gp = GLORY["porch"]
    segs += [("south", s[0], s[1], gp["x0"], s[3], False), ("south", gp["x0"], s[1], gp["x1"], s[3], False), ("south", gp["x1"], s[1], s[2], s[3], False)]
    return segs


def add_cloister_walk(bm_stone, bm_floor, walk: str, x0: float, y0: float, x1: float, y1: float, roofed: bool) -> None:
    """One straight piece of the covered double-façade walk: floor at Z_NAVE, outer wall with windows
    (street side, down to the sloped ground), inner arcade towards the patio, roof slab with ribs.
    Bays of ~7.5 m with few boxes each (the walk is ~3.4x longer than before)."""
    along_y = walk in ("east", "west")
    porch = not roofed and walk != "south"
    z_top = Z_NAVE - (Z_GROUND_EPS if (porch or (walk == "south" and abs(0.5 * (x0 + x1)) < GLORY["porch"]["x1"])) else 0.0)
    box_span(bm_floor, x0, x1, y0, y1, Z_NAVE - 0.45, z_top)
    if not roofed:
        return
    H = CLOISTER_HEIGHT
    wt = 0.5 * (CLOISTER_WIDTH - CLOISTER_CLEAR_WIDTH)      # 1.0 wall / arcade thickness
    L = (y1 - y0) if along_y else (x1 - x0)
    n_bays = max(1, round(L / 7.5))
    pitch = L / n_bays
    if along_y:
        outer_sgn = 1.0 if walk == "east" else -1.0
        x_out = x1 - 0.5 * wt if walk == "east" else x0 + 0.5 * wt
        x_in = x0 + 0.5 * wt if walk == "east" else x1 - 0.5 * wt
        cx_mid, rot = 0.5 * (x0 + x1), math.pi / 2
        u0 = y0
        lines = [(x_out, "outer"), (x_in, "inner")]
        ground = ground_z(min(y0, y1)) - 0.3
    else:
        x_out = None
        y_out = y1 - 0.5 * wt if walk == "north" else y0 + 0.5 * wt
        y_in = y0 + 0.5 * wt if walk == "north" else y1 - 0.5 * wt
        rot = 0.0
        u0 = x0
        lines = [(y_out, "outer"), (y_in, "inner")]
        ground = ground_z(y1 if walk == "north" else y0) - 0.3
    for pos, kind in lines:
        openings = []
        for b in range(n_bays):
            a, c = b * pitch + 0.7, (b + 1) * pitch - 0.7
            if kind == "outer":
                openings.append((a - 0.5 * L + 0.5, c - 0.5 * L - 0.5, Z_NAVE + 1.0, Z_NAVE + 6.2))
            else:
                openings.append((a - 0.5 * L, c - 0.5 * L, Z_NAVE - 0.1, Z_NAVE + 5.6))
        mid = u0 + 0.5 * L
        cx, cy = (pos, mid) if along_y else (mid, pos)
        zb = ground if kind == "outer" else Z_NAVE - 0.45
        add_wall_with_openings(bm_stone, cx, cy, rot, L, wt, zb, Z_NAVE + H, openings)
        if kind == "inner":
            # pointed-arch soffits of the arcade (stepped), one per bay
            for b in range(n_bays):
                a, c = b * pitch + 0.7, (b + 1) * pitch - 0.7
                span = c - a
                for k in range(4):
                    t0, t1 = k / 4, (k + 1) / 4
                    tm = 0.5 * (t0 + t1)
                    z_soffit = Z_NAVE + 4.0 + 1.6 * math.sin(math.pi * tm) ** 0.7
                    um = u0 + a + span * tm
                    px, py = (pos, um) if along_y else (um, pos)
                    add_box(bm_stone, (px, py, 0.5 * (z_soffit + Z_NAVE + 5.6)), (span * 0.25 + 0.02, wt * 0.8, Z_NAVE + 5.6 - z_soffit), rot_euler=(0, 0, rot))
    # roof slab + transverse ribs on the bay lines
    box_span(bm_stone, x0 - (0.2 if along_y else 0.0), x1 + (0.2 if along_y else 0.0), y0 - (0.0 if along_y else 0.2), y1 + (0.0 if along_y else 0.2), Z_NAVE + H, Z_NAVE + H + 0.6)
    for b in range(1, n_bays):
        u = u0 + b * pitch
        if along_y:
            box_span(bm_stone, x0, x1, u - 0.22, u + 0.22, Z_NAVE + H - 0.7, Z_NAVE + H)
        else:
            box_span(bm_stone, u - 0.22, u + 0.22, y0, y1, Z_NAVE + H - 0.7, Z_NAVE + H)


def build_patio_floor(bm: bmesh.types.BMesh) -> None:
    """The ground inside the cloister rectangle is walkable at Z_NAVE in the runtime (basilica podium), so
    the patios between church and cloister get a paved deck just under Z_NAVE (hidden under every church
    floor it overlaps). Left open: the presbytery hollow over the crypt's central vault and the two crypt
    stair towers (square tiles with a round hole)."""
    z0, z1 = Z_NAVE - 0.33, Z_NAVE - 0.03
    xi = CLOISTER_WALKS["east"][0]                  # 32.5 inner face of the E/W walks
    ys = CLOISTER_WALKS["south"][3]                 # -53.1
    yn = CLOISTER_WALKS["north"][1]                 # 44.7
    yp = PRESBYTERY_FRONT_Y
    box_span(bm, -xi, xi, ys, yp, z0, z1)
    st = CRYPT_STAIRS[0]
    half = st["rOuter"] + 0.6
    r_hole = st["rOuter"] + 0.2
    sx0, sx1 = abs(st["x"]) - half, abs(st["x"]) + half
    sy0, sy1 = st["y"] - half, st["y"] + half
    for sx in (-1, 1):
        def bx(a, b, c, d):
            xa, xb = sorted((sx * a, sx * b))
            box_span(bm, xa, xb, c, d, z0, z1)
        bx(PRESBYTERY_HALF_WIDTH, sx0, yp, yn)
        bx(sx1, xi, yp, yn)
        bx(sx0, sx1, yp, sy0)
        bx(sx0, sx1, sy1, yn)
        add_square_tile_with_hole(bm, sx * abs(st["x"]), st["y"], half, r_hole, z0, z1, segs=16)
    box_span(bm, -PRESBYTERY_HALF_WIDTH, PRESBYTERY_HALF_WIDTH, CRYPT_CENTER[1] + PRESBYTERY_RADIUS, yn, z0, z1)


# ─────────────────────────────────────────────────────────────────────────────
# Corner buildings and Assumption chapel (one pavilion function)
# ─────────────────────────────────────────────────────────────────────────────

def pavilion_doors(cx: float, cy: float, half: float) -> dict[int, list[float]]:
    """Door centres (world point) per face index (0 E, 1 N, 2 W, 3 S) where a cloister walk ends on the face."""
    doors: dict[int, list[tuple[float, float]]] = {0: [], 1: [], 2: [], 3: []}
    for name, (x0, y0, x1, y1) in CLOISTER_WALKS.items():
        xm, ym = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        ends = [(xm, y0), (xm, y1)] if name in ("east", "west") else [(x0, ym), (x1, ym)]
        for ex, ey in ends:
            if abs(ex - cx) <= half + 0.02 and abs(ey - cy) <= half + 0.02:
                if abs(abs(ey - cy) - half) < 0.05:
                    doors[1 if ey > cy else 3].append((ex, ey))
                elif abs(abs(ex - cx) - half) < 0.05:
                    doors[0 if ex > cx else 2].append((ex, ey))
    return doors


def add_pavilion(
    bm_stone, bm_floor, bm_mosaic, bm_gold, cx: float, cy: float, side: float, z_top: float, z_dome_max: float,
    detail: int = 4, extra_doors: dict[int, list[tuple[float, float]]] | None = None,
    closed_doors: dict[int, list[tuple[float, float]]] | None = None,
) -> None:
    """Square storey with doorways for the cloister walks, octagonal storey with windows, dome of twelve
    paraboloids, hyperboloid lantern (Gaudí's sacristy model). Walls reach down to the sloped ground."""
    half = 0.5 * side
    z0 = Z_NAVE
    z_dome = min(z_dome_max, z_top - 3.0)
    z_sq = z0 + 0.36 * (z_dome - z0)
    z_oct = z0 + 0.60 * (z_dome - z0)
    z_lantern = z_top
    wt = 0.8
    z_ground = ground_z(cy - half) - 0.3
    doors = pavilion_doors(cx, cy, half)
    for k, v in (extra_doors or {}).items():
        doors[k] += v
    door_w, door_h = CLOISTER_CLEAR_WIDTH, 3.8

    box_span(bm_floor, cx - half + wt, cx + half - wt, cy - half + wt, cy + half - wt, z0 - 0.4, z0)
    for face in range(4):
        ang = face * math.pi / 2.0
        nx, ny = math.cos(ang), math.sin(ang)
        wx, wy = cx + nx * (half - 0.5 * wt), cy + ny * (half - 0.5 * wt)
        rot = ang + math.pi / 2.0
        tx, ty = math.cos(rot), math.sin(rot)
        L = 2 * half
        ops = []
        for (dx, dy) in doors[face]:
            u = (dx - cx) * tx + (dy - cy) * ty
            ops.append((u - 0.5 * door_w, u + 0.5 * door_w, z0 - 0.5, z0 + door_h))
        w_lo, w_hi, w_w = z0 + 4.6, z_sq - 2.0, 1.3
        for s in (-0.55, 0.0, 0.55):
            u = s * half
            if all(not (o[0] - 0.4 < u < o[1] + 0.4) for o in ops):
                ops.append((u - 0.5 * w_w, u + 0.5 * w_w, w_lo, w_hi))
        add_wall_with_openings(bm_stone, wx, wy, rot, L, wt, z_ground, z_sq, ops)
        for (dx, dy) in (closed_doors or {}).get(face, []):     # bronze street doors (closed)
            u = (dx - cx) * tx + (dy - cy) * ty
            add_box(bm_gold, (cx + nx * (half - 0.15) + tx * u, cy + ny * (half - 0.15) + ty * u, z0 + 1.6), (1.8, 0.06, 3.2), rot_euler=(0, 0, rot))
        add_box(bm_stone, (cx + nx * (half - 0.2), cy + ny * (half - 0.2), z_sq + 0.3), (L + 0.4, 1.2, 0.6), rot_euler=(0, 0, rot))
    # squinches (octagon transition, above head height) + corner pinnacles
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        sxc, syc = math.copysign(1.0, math.cos(a)), math.copysign(1.0, math.sin(a))
        add_box(bm_stone, (cx + sxc * (half - 1.3), cy + syc * (half - 1.3), z_sq - 0.9), (2.6, 2.6, 1.8), rot_euler=(0, 0, a))
        ox, oy = cx + sxc * (half - 0.6), cy + syc * (half - 0.6)
        ph = 0.22 * (z_dome - z0)
        add_lathe(bm_stone, ox, oy, [(z_sq, 0.8), (z_sq + 0.27 * ph, 0.62), (z_sq + 0.73 * ph, 0.33), (z_sq + ph, 0.05)], segments=8, cap_bottom=True)
        add_lathe(bm_mosaic, ox, oy, [(z_sq + ph - 0.25, 0.0), (z_sq + ph + 0.05, 0.3), (z_sq + ph + 0.6, 0.0)], segments=8)
    # octagonal storey with one tall window per face
    r_oct = half - 0.4
    oct_pts = [(cx + r_oct / math.cos(math.pi / 8) * math.cos(math.pi / 8 + k * math.pi / 4), cy + r_oct / math.cos(math.pi / 8) * math.sin(math.pi / 8 + k * math.pi / 4)) for k in range(8)]
    for k in range(8):
        (x0, y0), (x1, y1) = oct_pts[k], oct_pts[(k + 1) % 8]
        seg = math.hypot(x1 - x0, y1 - y0) + 0.3
        rot = math.atan2(y1 - y0, x1 - x0)
        add_wall_with_openings(bm_stone, 0.5 * (x0 + x1), 0.5 * (y0 + y1), rot, seg, wt, z_sq + 0.6, z_oct,
                               [(-0.9, 0.9, z_sq + 2.4, z_oct - 1.4)])
    add_cylinder(bm_stone, Vector((cx, cy, z_oct - 0.2)), Vector((cx, cy, z_oct + 0.4)), r_oct + 0.4, r_oct + 0.2, segments=24, cap=False)
    add_paraboloid_dome(bm_stone, cx, cy, r_oct, z_oct + 0.3, z_dome, r_open=0.2 * r_oct, thickness=0.4, lobes=12,
                        steps_per_lobe=detail, rings=detail + 3, ecc=0.6, rib_r=0.22)
    r_l = 0.2 * r_oct + 0.15
    add_ruled_hyperboloid_shell(bm_mosaic, cx, cy, z_dome - 0.5, z_lantern - 0.6, r_l, 1.9, n=4 * detail + 4)
    add_lathe(bm_mosaic, cx, cy, [(z_lantern - 0.6, r_l), (z_lantern - 0.2, 0.78 * r_l), (z_lantern, 0.25 * r_l), (z_lantern + 0.1, 0.0)], segments=4 * detail + 4)
    add_cylinder(bm_gold, Vector((cx, cy, z_lantern)), Vector((cx, cy, z_lantern + 1.6)), 0.14, 0.05, segments=8)
    add_cylinder(bm_gold, Vector((cx - 0.45, cy, z_lantern + 1.1)), Vector((cx + 0.45, cy, z_lantern + 1.1)), 0.06, 0.06, segments=6)


# ─────────────────────────────────────────────────────────────────────────────
# Crypt
# ─────────────────────────────────────────────────────────────────────────────

def add_crypt_mosaic(bm_light, bm_red, cx, cy, r_pier, r_front, y_front) -> None:
    """Roman-style (opus tessellatum) floor: rosette under the keystone, concentric bands, red panels in
    the ambulatory bays and the transverse aisle (1 cm proud of the floor, visual only)."""
    z = CRYPT_FLOOR_Z + 0.012
    rc = Vector((cx, cy, z))
    for k in range(16):
        a0 = 2 * math.pi * k / 16
        a1 = a0 + 2 * math.pi / 32
        bm = bm_red if k % 2 == 0 else bm_light
        pts = [rc + Vector((0.6 * math.cos(a0), 0.6 * math.sin(a0), 0)), rc + Vector((2.2 * math.cos(a1), 2.2 * math.sin(a1), 0)),
               rc + Vector((0.6 * math.cos(a0 + 2 * math.pi / 16), 0.6 * math.sin(a0 + 2 * math.pi / 16), 0))]
        f = bm.faces.new([bm.verts.new(p) for p in pts])
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
    for (ri, ro, bm, a_end, n) in ((2.5, 2.75, bm_red, 2 * math.pi, 40), (3.05, 3.2, bm_light, 2 * math.pi, 40), (r_pier - 1.0, r_pier - 0.8, bm_red, math.pi, 24)):
        closed = a_end > 6.0
        cnt = n if closed else n + 1
        ring_i = [bm.verts.new((cx + ri * math.cos(a_end * k / n), cy + ri * math.sin(a_end * k / n), z)) for k in range(cnt)]
        ring_o = [bm.verts.new((cx + ro * math.cos(a_end * k / n), cy + ro * math.sin(a_end * k / n), z)) for k in range(cnt)]
        for k in range(n):
            nk = (k + 1) % cnt
            f = bm.faces.new((ring_i[k], ring_o[k], ring_o[nk], ring_i[nk]))
            f.normal_update()
            if f.normal.z < 0:
                f.normal_flip()
    rm = 0.5 * (r_pier + r_front)
    for k in range(CRYPT_PIER_COUNT - 1):
        a = math.radians(20.0 * k + 10.0)
        add_box(bm_red, (cx + rm * math.cos(a), cy + rm * math.sin(a), z - 0.004), (1.3, 1.3, 0.01), rot_euler=(0, 0, a + math.pi / 4))
    for x in (-17.0, -11.25, 11.25, 17.0):
        add_box(bm_red, (x, 0.5 * (y_front + cy), z - 0.004), (1.1, 1.1, 0.01), rot_euler=(0, 0, math.pi / 4))


def stair_angle(s: dict, t: float) -> float:
    """Tread angle (rad) at fraction t of the spiral: phaseDeg + sgn * t * turns * 2pi, sgn = +1 if clockwise
    (towers_lib / src/scene/walkModel.ts convention)."""
    sgn = 1.0 if s["clockwise"] else -1.0
    return math.radians(s["phaseDeg"]) + sgn * t * s["turns"] * 2.0 * math.pi


def build_crypt_stair(s: dict, bm_crypt, bm_tower, bm_steps, bm_floor, bm_mosaic) -> None:
    """Gaudí's spiral stair from the crypt floor to the nave floor in a solid drum (inner r 2.42, outer
    r 2.6); bottom door through the crypt side wall, top door towards -y through the transept north wall.
    The drum stands outdoors above ground (corner between apse, transept and cloister) with a small roof."""
    cx, cy, z0, z1 = s["x"], s["y"], s["z0"], s["z1"]
    r_in, r_out = s["rInner"], s["rOuter"]
    r_w0, r_w1 = r_out + 0.02, 2.6
    r_mid = 0.5 * (r_in + r_out)
    span = z1 - z0
    n = int(round(span / 0.175))
    for i in range(n + 1):
        t = i / n
        a = stair_angle(s, t)
        z_line = z0 + t * span
        z_tread = z_line + 0.12 if i > 0 else z0          # first tread flush with the crypt floor
        add_box(bm_steps, (cx + r_mid * math.cos(a), cy + r_mid * math.sin(a), z_tread - 0.17), (r_out - r_in + 0.06, 0.74, 0.34), rot_euler=(0, 0, a))
    # top landing: sector from the arrival direction onwards (never over the approach treads)
    a_top = stair_angle(s, 1.0)
    sgn = 1.0 if s["clockwise"] else -1.0
    a0, a1 = sorted((a_top - sgn * math.radians(8.0), a_top + sgn * math.radians(130.0)))
    add_annulus_sector(bm_steps, cx, cy, r_in, r_w0 + 0.02, a0, a1, z1 - 0.3, z1, segs=10)
    # crypt floor under the drum
    add_cylinder(bm_floor, Vector((cx, cy, z0 - 0.5)), Vector((cx, cy, z0)), r_w1, r_w1, segments=20, cap=True)
    # newel
    z_roof = z1 + 3.4
    add_cylinder(bm_crypt, Vector((cx, cy, z0)), Vector((cx, cy, z_roof)), r_in, r_in, segments=12, cap=True)
    # drum wall with two doors
    bd = CRYPT_STAIR_BOTTOM_DOOR
    a_bot = stair_angle(s, 0.0)
    hb = math.asin(min(0.99, bd["halfWidth"] / r_w0))
    ht = math.asin(min(0.99, CRYPT_STAIR_TOP_DOOR["halfWidth"] / r_w0))
    a_exit = math.radians(270.0)
    segs = 40
    for k in range(segs):
        th0, th1 = 2 * math.pi * k / segs, 2 * math.pi * (k + 1) / segs
        thm = 0.5 * (th0 + th1)

        def near(a, h):
            d = (thm - a + math.pi) % (2 * math.pi) - math.pi
            return abs(d) < h

        gaps = []
        if near(a_bot, hb):
            gaps.append((z0, z0 + 2.6))
        if near(a_exit, ht):
            gaps.append((z1, z1 + 2.8))
        z = z0
        spans = []
        for g0, g1 in gaps:
            spans.append((z, g0))
            z = g1
        spans.append((z, z_roof))
        for za, zb in spans:
            for zs, ze, bm in ((za, min(zb, CRYPT_WALL_TOP), bm_crypt), (max(za, CRYPT_WALL_TOP), zb, bm_tower)):
                if ze - zs > 1e-3:
                    add_annulus_sector(bm, cx, cy, r_w0, r_w1, th0, th1, zs, ze, segs=1)
    # roof of the drum (above ground) + trencadís finial
    add_lathe(bm_tower, cx, cy, [(z_roof, r_w1 + 0.25), (z_roof + 0.35, r_w1 + 0.1), (z_roof + 1.4, 1.2), (z_roof + 2.0, 0.25)], segments=20, cap_bottom=True, cap_top=True)
    add_lathe(bm_mosaic, cx, cy, [(z_roof + 1.9, 0.0), (z_roof + 2.3, 0.4), (z_roof + 2.9, 0.0)], segments=10)
    # door frame where the drum meets the crypt side wall
    sxs = 1.0 if cx > 0 else -1.0
    xw = CRYPT_HALF_WIDTH
    for yy in (cy - bd["halfWidth"] - 0.25, cy + bd["halfWidth"] + 0.25):
        xa, xb = sorted((sxs * xw, sxs * (abs(cx) - 2.25)))
        box_span(bm_crypt, xa, xb, yy - 0.25, yy + 0.25, z0, CRYPT_WALL_TOP)
    xa, xb = sorted((sxs * xw, sxs * (abs(cx) - 2.45)))
    box_span(bm_crypt, xa, xb, cy - bd["halfWidth"], cy + bd["halfWidth"], z0 + 2.6, CRYPT_WALL_TOP)
    box_span(bm_floor, xa, xb, cy - bd["halfWidth"] - 0.5, cy + bd["halfWidth"] + 0.5, z0 - 0.5, z0)


def build_crypt(bm_crypt, bm_tower, bm_steps, bm_floor, bm_gold, bm_marble, bm_candle, candle_anchors,
                bm_mosaic_floor, bm_mosaic_red, bm_porphyry, bm_mosaic) -> None:
    """Neo-Gothic crypt (Villar 1882-83 / Gaudí) under the apse, same plan as the apse and concentric with
    it and the Tower of Mary (layout.crypt):
      * central space: ring of CRYPT_PIER_COUNT clustered piers at r 7.5 + straight part to the south chapels,
        raised central vault (crown at the Annunciation keystone, Z_CRYPT_VAULT_CENTRAL) with a clerestory
        band under the presbytery;
      * ambulatory r 7.5 .. 15, seven chapels r 15 .. 19 on the semicircle, five chapels on the south side
        (Carmel with Gaudí's tomb, Sacrament, altar, Montserrat, Holy Christ with Bocabella's tomb);
      * ribbed groin vaults (crown Z_CRYPT_VAULT_LOW), Roman-style mosaic floor, two spiral stairs."""
    cx, cy = CRYPT_CENTER
    zf = CRYPT_FLOOR_Z
    R1, R2, R3, RW = CRYPT_PIER_RING_R, CRYPT_CHAPEL_FRONT_R, CRYPT_CHAPEL_BACK_R, CRYPT_WALL_OUTER_R
    HW = CRYPT_HALF_WIDTH
    YS = CRYPT_SOUTH_WALL_Y
    YF = YS + CRYPT_SOUTH_CHAPEL_DEPTH          # 17.25 front of the south chapels
    XS = CRYPT_SOUTH_CHAPEL_X
    z_cap = zf + 4.4                            # pier capitals / vault springing
    z_low = Z_CRYPT_VAULT_LOW                   # 0.2
    z_key = CRYPT_KEYSTONE[2]                   # 2.4
    z_cl0, z_cl1 = CRYPT_WALL_TOP, z_key - 0.4  # clerestory band 0.45 .. 2.0
    wt = 0.5
    z_open = zf + 4.2                           # chapel arch openings

    def V(x, y, z=0.0):
        return Vector((x, y, z))

    ring_deg = [180.0 * k / (CRYPT_PIER_COUNT - 1) for k in range(CRYPT_PIER_COUNT)]
    inner = [V(cx + R1 * math.cos(math.radians(a)), cy + R1 * math.sin(math.radians(a))) for a in ring_deg]
    outer = [V(cx + (R2 - 0.1) * math.cos(math.radians(a)), cy + (R2 - 0.1) * math.sin(math.radians(a))) for a in ring_deg]
    pier_a = [math.radians(a) for a in APSE_PIER_ANGLES_DEG]

    # ── floor ──
    add_annulus_sector(bm_floor, cx, cy, 0.0, RW, 0.0, math.pi, zf - 0.5, zf, segs=28)
    box_span(bm_floor, -RW, RW, YS - 1.25, cy, zf - 0.5, zf)
    add_crypt_mosaic(bm_mosaic_floor, bm_mosaic_red, cx, cy, R1, R2, YF)

    # ── piers ──
    central = inner + [V(-R1, YF), V(R1, YF)]
    for p in central:
        add_clustered_pier(bm_crypt, p.x, p.y, zf, z_cap, 0.46, shafts=6)
        add_cylinder(bm_crypt, V(p.x, p.y, z_cap), V(p.x, p.y, z_cl1), 0.4, 0.36, segments=10, cap=False)
        add_lathe(bm_crypt, p.x, p.y, [(z_cl1 - 0.25, 0.4), (z_cl1, 0.62)], segments=10, cap_bottom=False, cap_top=True)
    for p in outer[1:-1]:      # engaged piers on the chapel front wall
        add_clustered_pier(bm_crypt, p.x, p.y, zf, z_cap, 0.3, shafts=4)
    for x in (-15.0, -11.4, -3.8, 3.8, 11.4, 15.0):   # engaged piers on the south chapel front
        add_clustered_pier(bm_crypt, x, YF - 0.1, zf, z_cap, 0.3, shafts=4)

    # ── central vault: arches between the central piers, clerestory band, shallow ribbed vault ──
    key = V(CRYPT_KEYSTONE[0], CRYPT_KEYSTONE[1], z_key)
    loop = inner + [V(-R1, YF), V(R1, YF)]
    for i in range(len(loop)):
        a, b = loop[i], loop[(i + 1) % len(loop)]
        d = b - a
        span = d.length
        rot = math.atan2(d.y, d.x)
        m = (a + b) * 0.5
        n_st = 6 if span > 4 else 4
        rise = min(3.0, 0.45 * span)
        for k in range(n_st):   # stepped pointed-arch spandrel from the arch up to the clerestory sill
            tm = (k + 0.5) / n_st
            z_s = z_cap + rise * math.sin(math.pi * tm) ** 0.75
            p = a.lerp(b, tm)
            add_box(bm_crypt, (p.x, p.y, 0.5 * (z_s + z_cl0)), (span / n_st + 0.02, wt, z_cl0 - z_s), rot_euler=(0, 0, rot))
        n_mull = max(1, int(span // 3.2))
        ops = [((k + 0.5) / (n_mull + 1) * span - 0.5 * span + 0.35, (k + 1.5) / (n_mull + 1) * span - 0.5 * span - 0.35, z_cl0 + 0.12, z_cl1 - 0.15) for k in range(n_mull + 1)]
        ops = [(-0.5 * span + 0.45 + k * (span - 0.9) / (n_mull + 1) + 0.18, -0.5 * span + 0.45 + (k + 1) * (span - 0.9) / (n_mull + 1) - 0.18, z_cl0 + 0.12, z_cl1 - 0.15) for k in range(n_mull + 1)]
        add_wall_with_openings(bm_crypt, m.x, m.y, rot, span + 0.3, wt, z_cl0, z_cl1 + 0.05, ops)
        add_web_vault_sector(bm_crypt, V(a.x, a.y, z_cl1), V(b.x, b.y, z_cl1), key, z_cl1, 0.12, res_s=3, res_t=6 if span > 6 else 3)
        pts = []
        for f in (0.0, 0.4, 0.75, 1.0):
            q = V(a.x, a.y, z_cl1).lerp(key, f)
            q.z = z_cl1 + (key.z - z_cl1) * (1.0 - (1.0 - f) ** 2) - 0.08
            pts.append(q)
        add_swept_tube(bm_crypt, pts, [0.13] * 4, segments=5, cap=False)
    add_lathe(bm_crypt, key.x, key.y, [(key.z - 0.3, 0.75), (key.z - 0.12, 0.98), (key.z + 0.05, 1.0)], segments=20, cap_bottom=True, cap_top=True)
    # Annunciation keystone: gilded frame, porphyry ground, white figures of Gabriel and Mary
    add_cylinder(bm_gold, V(key.x, key.y, key.z - 0.36), V(key.x, key.y, key.z - 0.3), 0.82, 0.82, segments=20, cap=True)
    add_cylinder(bm_porphyry, V(key.x, key.y, key.z - 0.4), V(key.x, key.y, key.z - 0.35), 0.66, 0.66, segments=20, cap=True)
    for fx in (-0.26, 0.24):
        add_ellipsoid(bm_marble, (key.x + fx, key.y, key.z - 0.45), (0.12, 0.18, 0.07), subdivisions=1)
        add_ellipsoid(bm_marble, (key.x + fx, key.y + 0.24, key.z - 0.47), (0.07, 0.07, 0.06), subdivisions=1)
    for s in (-1, 1):
        add_ellipsoid(bm_gold, (key.x - 0.26 + 0.14 * s, key.y - 0.05, key.z - 0.44), (0.08, 0.2, 0.03), subdivisions=1, rot_z=0.5 * s)

    # ── groin-vaulted ambulatory, chapels, straight bays, south chapels ──
    cells: list[list[Vector]] = []
    for k in range(CRYPT_PIER_COUNT - 1):
        cells.append([inner[k], outer[k], outer[k + 1], inner[k + 1]])
    for k in range(len(pier_a) - 1):
        a0, a1 = pier_a[k], pier_a[k + 1]
        cells.append([V(cx + (R2 + 0.25) * math.cos(a0), cy + (R2 + 0.25) * math.sin(a0)), V(cx + R3 * math.cos(a0), cy + R3 * math.sin(a0)),
                      V(cx + R3 * math.cos(a1), cy + R3 * math.sin(a1)), V(cx + (R2 + 0.25) * math.cos(a1), cy + (R2 + 0.25) * math.sin(a1))])
    for s in (-1, 1):
        for xa, xb in ((R1, R2), (R2, HW)):
            cells.append([V(s * xa, YF), V(s * xb, YF), V(s * xb, cy), V(s * xa, cy)])
    for i in range(len(XS) - 1):
        cells.append([V(XS[i], YS), V(XS[i + 1], YS), V(XS[i + 1], YF), V(XS[i], YF)])
    for corners in cells:
        boss = add_groin_vault_cell(bm_crypt, bm_crypt, corners, z_cap, z_low, res=4, rib_r=0.09)
        add_cylinder(bm_gold, boss - V(0, 0, 0.16), boss + V(0, 0, 0.02), 0.16, 0.2, segments=6, cap=True)

    # ── walls ──
    add_annulus_sector(bm_crypt, cx, cy, R3, RW, 0.0, math.pi, zf, CRYPT_WALL_TOP, segs=28)    # outer semicircle
    box_span(bm_crypt, -RW, RW, YS - 1.25, YS, zf, CRYPT_WALL_TOP)                              # south back wall
    for s, st in ((1, next(t for t in CRYPT_STAIRS if t["x"] > 0)), (-1, next(t for t in CRYPT_STAIRS if t["x"] < 0))):
        # straight side walls, split round the stair drum (door frame built with the stair)
        h = math.sqrt(max(0.0, (st["rOuter"] + 0.02) ** 2 - (abs(st["x"]) - RW) ** 2))
        xa, xb = sorted((s * HW, s * RW))
        box_span(bm_crypt, xa, xb, YS - 1.25, st["y"] - h, zf, CRYPT_WALL_TOP)
        box_span(bm_crypt, xa, xb, st["y"] + h, cy, zf, CRYPT_WALL_TOP)
        xa2, xb2 = sorted((s * HW, s * (abs(st["x"]) - 2.25)))
        box_span(bm_crypt, xa2, xb2, st["y"] - h, st["y"] - CRYPT_STAIR_BOTTOM_DOOR["halfWidth"] - 0.5, zf, CRYPT_WALL_TOP)
        box_span(bm_crypt, xa2, xb2, st["y"] + CRYPT_STAIR_BOTTOM_DOOR["halfWidth"] + 0.5, st["y"] + h, zf, CRYPT_WALL_TOP)
    # chapel front wall on r 15 with seven arched openings, radial walls between the chapels
    for k in range(len(pier_a) - 1):
        a0, a1 = pier_a[k], pier_a[k + 1]
        am = 0.5 * (a0 + a1)
        ho = math.asin(2.7 / R2)
        add_annulus_sector(bm_crypt, cx, cy, R2, R2 + wt, a0, am - ho, zf, CRYPT_WALL_TOP, segs=2)
        add_annulus_sector(bm_crypt, cx, cy, R2, R2 + wt, am + ho, a1, zf, CRYPT_WALL_TOP, segs=2)
        add_annulus_sector(bm_crypt, cx, cy, R2, R2 + wt, am - ho, am + ho, z_open, CRYPT_WALL_TOP, segs=4)
        add_box(bm_marble, (cx + (R3 - 0.5) * math.cos(am), cy + (R3 - 0.5) * math.sin(am), zf + 0.5), (1.4, 0.6, 1.0), rot_euler=(0, 0, am + math.pi / 2))
    for a in pier_a:
        m = V(cx + 0.5 * (R2 + R3) * math.cos(a), cy + 0.5 * (R2 + R3) * math.sin(a))
        add_box(bm_crypt, (m.x, m.y, 0.5 * (zf + CRYPT_WALL_TOP)), (R3 - R2 + 0.1, 0.5, CRYPT_WALL_TOP - zf), rot_euler=(0, 0, a))
    # five south chapels: dividers, front wall with openings, altars and the two tombs
    for x in XS[1:-1]:
        box_span(bm_crypt, x - 0.25, x + 0.25, YS, YF, zf, CRYPT_WALL_TOP)
    ops = []
    for i in range(len(XS) - 1):
        xm, w = 0.5 * (XS[i] + XS[i + 1]), XS[i + 1] - XS[i] - 1.2
        ops.append((xm - 0.5 * w, xm + 0.5 * w, zf - 0.1, z_open))
    add_wall_with_openings(bm_crypt, 0.0, YF, 0.0, 2 * HW, wt, zf, CRYPT_WALL_TOP, ops)
    for i in range(len(XS) - 1):
        xm = 0.5 * (XS[i] + XS[i + 1])
        if abs(xm - CRYPT_ALTAR_POS[0]) > 0.1:
            add_box(bm_marble, (xm, YS + 0.45, zf + 0.5), (1.4, 0.6, 1.0))
    ax, ay = CRYPT_ALTAR_POS
    add_box(bm_marble, (ax, ay, zf + 0.65), (3.0, 1.4, 1.3))
    add_cylinder(bm_gold, V(ax, ay - 0.5, zf + 1.3), V(ax, ay - 0.5, zf + 3.0), 0.08, 0.06, segments=8)
    add_cylinder(bm_gold, V(ax - 0.55, ay - 0.5, zf + 2.45), V(ax + 0.55, ay - 0.5, zf + 2.45), 0.06, 0.06, segments=8)
    for sx_a in (-1.05, 1.05):
        acx = ax + sx_a
        add_cylinder(bm_gold, V(acx, ay, zf + 1.30), V(acx, ay, zf + 1.62), 0.10, 0.05, segments=8)
        add_cylinder(bm_candle, V(acx, ay, zf + 1.62), V(acx, ay, zf + 1.98), 0.045, 0.04, segments=8)
        candle_anchors.append((acx, ay, zf + 2.00, 0.78))
    # Antoni Gaudí's tomb (Carmel chapel) and Josep Maria Bocabella's tomb (Holy Christ chapel)
    for (tx, ty), plaque in ((GAUDI_TOMB_POS, True), (BOCABELLA_TOMB_POS, True)):
        add_box(bm_marble, (tx, ty, zf + 0.14), (2.4, 1.35, 0.28))
        add_box(bm_gold, (tx, ty, zf + 0.30), (1.9, 0.9, 0.04))
    # votive candle rack along the outer side wall of the Carmel chapel
    tx, ty = GAUDI_TOMB_POS
    rx = -HW + 0.55
    add_box(bm_crypt, (rx, ty, zf + 0.42), (0.45, 2.2, 0.84))
    add_box(bm_gold, (rx, ty, zf + 0.85), (0.50, 2.26, 0.04))
    for k in range(6):
        vy = ty - 0.875 + k * 0.35
        z_top_g = zf + 1.14 + (0.04 if k % 2 == 0 else 0.0)
        add_cylinder(bm_candle, V(rx, vy, zf + 0.86), V(rx, vy, z_top_g), 0.042, 0.038, segments=7)
        candle_anchors.append((rx, vy, z_top_g + 0.02, 0.68))
    # eight candelabra round the central space
    for i in range(8):
        ang = 2.0 * math.pi * i / 8.0 + 0.3
        vx, vy = cx + 4.8 * math.cos(ang), cy + 4.8 * math.sin(ang)
        add_cylinder(bm_gold, V(vx, vy, zf), V(vx, vy, zf + 0.12), 0.24, 0.16, segments=10)
        add_cylinder(bm_gold, V(vx, vy, zf + 0.12), V(vx, vy, zf + 0.88), 0.055, 0.045, segments=8)
        add_cylinder(bm_gold, V(vx, vy, zf + 0.86), V(vx, vy, zf + 0.92), 0.16, 0.12, segments=10)
        add_cylinder(bm_candle, V(vx, vy, zf + 0.92), V(vx, vy, zf + 1.26), 0.055, 0.048, segments=8)
        candle_anchors.append((vx, vy, zf + 1.28, 0.82))

    # ── the two spiral stairs (replace the old straight tunnel) ──
    for st in CRYPT_STAIRS:
        build_crypt_stair(st, bm_crypt, bm_tower, bm_steps, bm_floor, bm_mosaic)


def build_cloister_and_crypt() -> None:
    reset_scene()
    mats = get_materials()

    bm_stone = bmesh.new()
    bm_floor = bmesh.new()
    bm_patio = bmesh.new()
    bm_mosaic = bmesh.new()
    bm_gold = bmesh.new()
    bm_crypt = bmesh.new()
    bm_crypt_floor = bmesh.new()
    bm_crypt_stairs = bmesh.new()
    bm_marble = bmesh.new()
    bm_candle = bmesh.new()
    bm_mosaic_floor = bmesh.new()
    bm_mosaic_red = bmesh.new()
    bm_porphyry = bmesh.new()

    # ── 1. Cloister: closed rectangle through the three porches, linking the four corner buildings ──
    for seg in walk_segments():
        add_cloister_walk(bm_stone, bm_floor, *seg)
    build_patio_floor(bm_patio)

    # ── 2. Corner buildings: sacristies (N), Baptistery / Penitence chapel (S); Assumption chapel ──
    for name, cb in CORNER_BUILDINGS.items():
        detail = 4 if name.startswith("sacristy") else 3
        add_pavilion(bm_stone, bm_floor, bm_mosaic, bm_gold, cb["x"], cb["y"], cb["side"], cb["top"], cb["dome"], detail=detail)
    ac = ASSUMPTION_CHAPEL
    acx, acy = 0.5 * (ac["x0"] + ac["x1"]), 0.5 * (ac["y0"] + ac["y1"])
    side = ac["x1"] - ac["x0"]
    n = CLOISTER_WALKS["north"]
    yw = 0.5 * (n[1] + n[3])
    add_pavilion(bm_stone, bm_floor, bm_mosaic, bm_gold, acx, acy, side, ac["domeTop"], ac["domeTop"], detail=3,
                 extra_doors={0: [(ac["x1"], yw)], 2: [(ac["x0"], yw)]},
                 closed_doors={1: [(x, ac["y1"]) for x in ac["streetDoorsX"]]})

    # ── 3. Crypt ──
    crypt_candle_anchors: list[tuple[float, float, float, float]] = []
    build_crypt(bm_crypt, bm_stone, bm_crypt_stairs, bm_crypt_floor, bm_gold, bm_marble, bm_candle, crypt_candle_anchors,
                bm_mosaic_floor, bm_mosaic_red, bm_porphyry, bm_mosaic)
    merge = bpy.data.meshes.new("_m")
    bm_crypt_floor.to_mesh(merge)
    bm_crypt_floor.free()
    bm_floor.from_mesh(merge)
    bpy.data.meshes.remove(merge)

    finalize_bmesh_object(bm_stone, "Cloister_And_Sacristies", mats["sandstone_warm"], smooth=False, uv_scale=0.15)
    finalize_bmesh_object(bm_floor, "Cloister_And_Crypt_Floor", mats["floor_marble"], smooth=False, uv_scale=0.18)
    finalize_bmesh_object(bm_patio, "Cloister_PatioFloor", mats["panot_paving"], smooth=False, uv_scale=0.25, bake_ao=False)
    finalize_bmesh_object(bm_mosaic, "Sacristy_Trencadis", mats["trencadis"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_gold, "Cloister_Gold", mats["gold_accent"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_crypt, "Crypt_Architecture", mats["crypt_stone"], smooth=False, uv_scale=0.16)
    finalize_bmesh_object(bm_crypt_stairs, "Crypt_StairSteps", mats["crypt_stone"], smooth=False, uv_scale=0.16, bake_ao=False)
    finalize_bmesh_object(bm_marble, "Crypt_AltarAndGaudiTomb", mats["white_marble"], smooth=False, uv_scale=0.30)
    finalize_bmesh_object(bm_candle, "Crypt_VotiveCandles", mats["candle_glow"], smooth=True, uv_scale=0.50)
    finalize_oriented(bm_mosaic_floor, "Crypt_MosaicFloor_Marble", mats["white_marble"], smooth=False, uv_scale=0.5, ao=False)
    finalize_oriented(bm_mosaic_red, "Crypt_MosaicFloor_Porphyry", mats["porphyry_red"], smooth=False, uv_scale=0.5, ao=False)
    finalize_bmesh_object(bm_porphyry, "Crypt_KeystonePorphyry", mats["porphyry_red"], smooth=True, uv_scale=0.5, bake_ao=False)

    assert len(crypt_candle_anchors) == 16, len(crypt_candle_anchors)
    save_candle_anchors("crypt", crypt_candle_anchors)
    export_glb(os.path.join(MODEL_DIR, "cloister_crypt.glb"))


if __name__ == "__main__":
    build_cloister_and_crypt()
