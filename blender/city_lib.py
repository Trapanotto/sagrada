"""Shared helpers for the city builders (build_eixample.py, build_plaza_life.py).

Everything here is derived from layout.py: block outlines, sidewalk curbs, the crypt cut-out in the
ground, the pond outline and the positions of street trees and lamps (both builders need the same
positions: trees/lamps in eixample, tree grates in plaza_life). The ground is the sloped plane
layout.ground_z(y); carriageways sit CURB_HEIGHT below it.
"""

from __future__ import annotations

import math
import os
import sys

import bmesh
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

sys.path.insert(0, os.path.dirname(__file__))
import layout as L  # noqa: E402

g = L.ground_z
CURB = L.CURB_HEIGHT
SITE_CENTER = L.ZONES["basilicaCenter"]          # (0, -4.2): centre of the basilica block

# Extent of the modelled ground plane (the hills ring starts at r 370; the plane reaches under it)
GROUND_EXTENT = 480.0


# ── polygons ────────────────────────────────────────────────────────────────────────────────────

def chamfered_rect(x0: float, y0: float, x1: float, y1: float, c: float,
                   corners: tuple[bool, bool, bool, bool] | list[bool] = (True, True, True, True)) -> list[tuple[float, float]]:
    """CCW outline of a Cerdà block; corners = [SW, SE, NE, NW] chamfered or square."""
    sw, se, ne, nw = corners
    pts: list[tuple[float, float]] = []
    if sw:
        pts += [(x0 + c, y0)]
    else:
        pts += [(x0, y0)]
    if se:
        pts += [(x1 - c, y0), (x1, y0 + c)]
    else:
        pts += [(x1, y0)]
    if ne:
        pts += [(x1, y1 - c), (x1 - c, y1)]
    else:
        pts += [(x1, y1)]
    if nw:
        pts += [(x0 + c, y1), (x0, y1 - c)]
    else:
        pts += [(x0, y1)]
    if sw:
        pts += [(x0, y0 + c)]
    return pts


def offset_polygon(pts: list[tuple[float, float]], d: float) -> list[tuple[float, float]]:
    """Offset a convex CCW polygon outwards by d (edges parallel, corners mitred)."""
    n = len(pts)
    lines = []
    for i in range(n):
        a = Vector(pts[i])
        b = Vector(pts[(i + 1) % n])
        t = (b - a).normalized()
        nrm = Vector((t.y, -t.x))
        lines.append((a + nrm * d, t))
    out = []
    for i in range(n):
        p0, t0 = lines[i - 1]
        p1, t1 = lines[i]
        den = t0.x * t1.y - t0.y * t1.x
        if abs(den) < 1e-9:
            out.append((p1.x, p1.y))
            continue
        s = ((p1.x - p0.x) * t1.y - (p1.y - p0.y) * t1.x) / den
        q = p0 + t0 * s
        out.append((q.x, q.y))
    return out


def rounded_rect(x0: float, y0: float, x1: float, y1: float, r: float, seg: int = 6) -> list[tuple[float, float]]:
    """CCW rounded rectangle."""
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90.0), (x1 - r, y1 - r, 0.0), (x0 + r, y1 - r, 90.0), (x0 + r, y0 + r, 180.0)):
        for k in range(seg + 1):
            a = math.radians(a0 + 90.0 * k / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def block_outline(b: dict) -> list[tuple[float, float]]:
    return chamfered_rect(b["x0"], b["y0"], b["x1"], b["y1"], b.get("chamfer", L.CHAMFER_LEG),
                          b.get("chamferCorners", (True, True, True, True)))


def curb_outline(b: dict) -> list[tuple[float, float]]:
    """Kerb line = building line pushed out by the sidewalk width."""
    return offset_polygon(block_outline(b), L.SIDEWALK_WIDTH)


def crypt_ground_hole() -> list[tuple[float, float]]:
    """Cut-out of the outdoor ground plane over the crypt and its two spiral stairs (CW = hole).

    The ground plane (z ~ -1.3 here) would otherwise slice through the crypt (floor -7.8, vaults to
    2.4) and the stair shafts. The cut stays 0.25 m inside the crypt's outer wall face
    (CRYPT_WALL_OUTER_R) and 0.1 m inside the stair shafts (rOuter 2.4 + 0.2 wall), so its edge is
    always hidden inside masonry."""
    cx, cy = L.CRYPT_CENTER
    r = L.CRYPT_WALL_OUTER_R - 0.25                  # 20.0
    y_s = L.CRYPT_SOUTH_WALL_Y - 1.25 + 0.25         # 12.25 (outer south face 12.0)
    st = L.CRYPT_STAIRS[1]
    sx, sy, sr = abs(st["x"]), st["y"], st["rOuter"] + 0.1
    dy = math.sqrt(max(0.0, sr * sr - (r - sx) ** 2)) if sx - sr < r else 0.0
    a_lo = math.degrees(math.atan2(-dy, r - sx))      # where the stair circle meets x = r
    a_hi = -a_lo
    pts: list[tuple[float, float]] = [(-r, y_s), (r, y_s), (r, sy - dy)]
    n = 10
    for k in range(1, n):
        a = math.radians(a_lo + (a_hi - a_lo) * k / n)
        pts.append((sx + sr * math.cos(a), sy + sr * math.sin(a)))
    pts.append((r, sy + dy))
    seg = 16
    for k in range(seg + 1):
        a = math.pi * k / seg
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    pts.append((-r, sy + dy))
    for k in range(1, n):
        a = math.radians(180.0 - a_hi + (a_hi - a_lo) * k / n)
        pts.append((-sx + sr * math.cos(a), sy + sr * math.sin(a)))
    pts.append((-r, sy - dy))
    return pts   # CCW outline of the hole region


def point_in_poly(x: float, y: float, pts: list[tuple[float, float]]) -> bool:
    inside = False
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def in_keep_clear(x: float, y: float, margin: float = 0.0) -> bool:
    for (x0, y0, x1, y1) in L.KEEP_CLEAR:
        if x0 - margin <= x <= x1 + margin and y0 - margin <= y <= y1 + margin:
            return True
    return False


# ── mesh helpers ────────────────────────────────────────────────────────────────────────────────

def add_ground_slab(bm: bmesh.types.BMesh, outer: list[tuple[float, float]], holes=(), z_off: float = 0.0,
                    curb: float = CURB, hole_walls: float = 0.0) -> None:
    """Top surface of a paved / planted area lying on the sloped ground (z = ground_z(y) + z_off),
    with a vertical kerb face of height `curb` round the outer edge (and `hole_walls` deep round holes)."""
    loops = [list(outer)] + [list(h) for h in holes]
    flat = [p for lp in loops for p in lp]
    tris = tessellate_polygon([[(x, y, 0.0) for x, y in lp] for lp in loops])
    vs = [bm.verts.new((x, y, g(y) + z_off)) for x, y in flat]
    for t in tris:
        try:
            f = bm.faces.new((vs[t[0]], vs[t[1]], vs[t[2]]))
        except ValueError:
            continue
        if f.normal.z < 0:
            f.normal_flip()
    if curb > 0.0:
        _wall_ring(bm, outer, z_off, z_off - curb, outward=True)
    if hole_walls > 0.0:
        for h in holes:
            _wall_ring(bm, h, z_off, z_off - hole_walls, outward=False)


def _wall_ring(bm, pts, z_top_off, z_bot_off, outward=True):
    n = len(pts)
    top = [bm.verts.new((x, y, g(y) + z_top_off)) for x, y in pts]
    bot = [bm.verts.new((x, y, g(y) + z_bot_off)) for x, y in pts]
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((bot[i], bot[j], top[j], top[i]))
        f.normal_update()
        e = Vector(pts[j]) - Vector(pts[i])
        out = Vector((e.y, -e.x, 0.0))  # outward for a CCW loop
        if (f.normal.dot(out) < 0) == outward:
            f.normal_flip()


def add_beam(bm: bmesh.types.BMesh, p0: Vector, p1: Vector, width: float, height: float) -> None:
    """Box from p0 to p1 (may slope), horizontal width across, vertical height (centred on the axis)."""
    ax = p1 - p0
    side = Vector((-ax.y, ax.x, 0.0))
    if side.length < 1e-6:
        return
    side.normalize()
    side *= width * 0.5
    up = Vector((0.0, 0.0, height * 0.5))
    corners = []
    for p in (p0, p1):
        corners.append([bm.verts.new(p + s * side + u * up) for s, u in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    a, b = corners
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(tuple(reversed(a)))
    bm.faces.new(tuple(b))


def add_quad(bm: bmesh.types.BMesh, cx: float, cy: float, sx: float, sy: float, rot: float, z_off: float) -> None:
    """Flat marking/grate quad lying on the sloped ground at ground_z + z_off."""
    ca, sa = math.cos(rot), math.sin(rot)
    vs = []
    for dx, dy in ((-sx, -sy), (sx, -sy), (sx, sy), (-sx, sy)):
        x = cx + (dx * ca - dy * sa) * 0.5
        y = cy + (dx * sa + dy * ca) * 0.5
        vs.append(bm.verts.new((x, y, g(y) + z_off)))
    bm.faces.new(vs)


def finalize_surface(bm: bmesh.types.BMesh, name: str, mat, uv_scale: float = 0.18, bake_ao: bool = True):
    """Like common.finalize_bmesh_object but keeps the authored face winding: open sheets (ground
    slabs, pond walls) have no inside, so recalc_face_normals could turn them upside down."""
    import bpy
    from common import apply_box_uv, bake_bvh_vertex_ao
    bm.normal_update()
    apply_box_uv(bm, scale=uv_scale)
    if bake_ao and len(bm.verts) <= 45000:
        bake_bvh_vertex_ao(bm, max_dist=5.5)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


# ── street furniture positions (shared by both builders) ────────────────────────────────────────

def _sagrada_faces():
    """Straight faces of the basilica block: (name, a, b, outward normal) along the building line."""
    b = L.SAGRADA_BLOCK
    c = b["chamfer"]
    x0, y0, x1, y1 = b["x0"], b["y0"], b["x1"], b["y1"]
    return [
        ("provenca", Vector((x0 + c, y1)), Vector((x1 - c, y1)), Vector((0, 1))),
        ("mallorca", Vector((x0 + c, y0)), Vector((x1 - c, y0)), Vector((0, -1))),
        ("marina", Vector((x1, y0 + c)), Vector((x1, y1 - c)), Vector((1, 0))),
        ("sardenya", Vector((x0, y0 + c)), Vector((x0, y1 - c)), Vector((-1, 0))),
    ]


# Gaps in the street-tree rows (EST, this package): Glory bridge span on Mallorca, the Nativity
# stair front / the spawn view axis on Marina, the Passion stair front on Sardenya, the Assumption
# chapel doors on Provença.
_TREE_SKIP = {
    "mallorca": lambda p: abs(p.x) < L.GLORY_AVENUE["x1"] + 2.0,
    "marina": lambda p: abs(p.y) < L.NATIVITY["stair"]["halfWidth"] + 3.5,
    "sardenya": lambda p: abs(p.y) < L.PASSION["stair"]["halfWidth"] + 2.0,
    "provenca": lambda p: abs(p.x) < abs(L.ASSUMPTION_CHAPEL["x0"]) + 4.0,
}


def _row(spacing: float, behind_building_line: float, skip_extra: dict | None = None):
    out = []
    for name, a, b, n in _sagrada_faces():
        length = (b - a).length
        k = int(length // spacing)
        mid = (a + b) * 0.5
        t = (b - a).normalized()
        for i in range(k):
            off = (i - (k - 1) * 0.5) * spacing
            p = mid + t * off + n * behind_building_line
            if _TREE_SKIP[name](p) or (skip_extra and skip_extra.get(name, lambda q: False)(p)):
                continue
            if in_keep_clear(p.x, p.y):
                continue
            out.append((round(p.x, 3), round(p.y, 3), name))
    return out


def street_tree_positions() -> list[tuple[float, float, str]]:
    """Street trees on the basilica-block sidewalks (STREET_TREE: every 9 m, 1.3 m behind the kerb)
    plus the opposite sidewalks of Provença and Mallorca (the other two streets face the plazas)."""
    d = L.SIDEWALK_WIDTH - L.STREET_TREE["curbOffset"]
    pts = _row(L.STREET_TREE["spacing"], d)
    sp = L.STREET_TREE["spacing"]
    # opposite sidewalks: Provença north side (block NC) and Mallorca south side (blocks SC-W / SC-E)
    for street, sign in (("provenca", 1), ("mallorca", -1)):
        axis, c, hw = L.STREETS[street]
        y = c + sign * (hw - L.SIDEWALK_WIDTH + L.STREET_TREE["curbOffset"])   # 1.3 m behind the far kerb
        b = L.SAGRADA_BLOCK
        xa, xb = b["x0"] + b["chamfer"], b["x1"] - b["chamfer"]
        k = int((xb - xa) // sp)
        for i in range(k):
            x = (i - (k - 1) * 0.5) * sp
            if street == "mallorca" and abs(x) < L.GLORY_AVENUE["x1"] + 2.0:
                continue
            pts.append((round(x, 3), round(y, 3), street + "Far"))
    return pts


def street_lamp_positions() -> list[tuple[float, float, str]]:
    d = L.SIDEWALK_WIDTH - L.STREET_LAMP["curbOffset"]
    # lamps keep the Glory bridge and the chapel clear but may stand on the view axes (thin posts)
    out = []
    for name, a, b, n in _sagrada_faces():
        length = (b - a).length
        k = int(length // L.STREET_LAMP["spacing"])
        mid = (a + b) * 0.5
        t = (b - a).normalized()
        for i in range(k):
            off = (i - (k - 1) * 0.5) * L.STREET_LAMP["spacing"]
            p = mid + t * off + n * d
            if name in ("mallorca", "provenca") and _TREE_SKIP[name](p):
                continue
            if in_keep_clear(p.x, p.y):
                continue
            out.append((round(p.x, 3), round(p.y, 3), name))
    return out


def pond_inner(inset: float = 0.45) -> list[tuple[float, float]]:
    p = L.POND
    return rounded_rect(p["x0"] + inset, p["y0"] + inset, p["x1"] - inset, p["y1"] - inset, p["cornerRadius"] - inset)


def pond_outer(outset: float = 0.45) -> list[tuple[float, float]]:
    p = L.POND
    return rounded_rect(p["x0"] - outset, p["y0"] - outset, p["x1"] + outset, p["y1"] + outset, p["cornerRadius"] + outset)


# Park layout inside the two plazas (EST, this package). Rectangles are lawn beds (x0, y0, x1, y1).
GAUDI_LAWNS = [
    (99.0, 35.5, 150.0, 47.0),      # north bed between the bank promenade and Provença
    (99.0, -55.5, 150.0, -40.0),    # south bed towards Mallorca
    (165.0, 15.0, 189.0, 44.0),     # east beds behind the spawn promenade
    (165.0, -53.0, 189.0, -13.0),
]
SF_LAWNS = [
    (-116.0, 10.0, -92.0, 40.0), (-116.0, -50.0, -92.0, -14.0),
    (-152.0, 10.0, -126.0, 44.0), (-152.0, -52.0, -126.0, -12.0),
    (-190.0, 8.0, -162.0, 36.0), (-190.0, -46.0, -162.0, -10.0),
]
NATIVITY_LAWNS = [(50.0, 24.0, 62.5, 40.0), (50.0, -44.0, 62.5, -24.0)]


def on_lawn(x: float, y: float) -> bool:
    return any(x0 <= x <= x1 and y0 <= y <= y1 for (x0, y0, x1, y1) in GAUDI_LAWNS + SF_LAWNS + NATIVITY_LAWNS)


# Park trees (full-detail plane trees). Plaça de Gaudí: rows along the north and south banks, two
# trees framing the façade view on the west bank, groups in the east beds. Plaça de la Sagrada
# Família: round its lawns. EST positions, this package.
PARK_PLANE_TREES = [
    (103.0, 30.5), (117.0, 31.5), (131.0, 30.5), (145.0, 31.5),
    (103.0, -34.5), (117.0, -35.5), (131.0, -34.5), (145.0, -35.5),
    (93.0, 19.0), (93.0, -23.0),
    (171.0, 33.0), (183.0, 22.0), (172.0, -24.0), (184.0, -40.0), (170.0, -48.0),
    (-104.0, 25.0), (-104.0, -32.0), (-121.0, 45.0), (-121.0, -55.0),
    (-139.0, 27.0), (-139.0, -32.0), (-157.0, 47.0), (-176.0, 22.0), (-176.0, -28.0),
]
CYPRESSES = [
    (96.0, 28.0), (96.0, -31.5),        # west corners of the pond, flanking the Nativity view
    (159.0, 25.0), (159.0, -29.0),      # east bank, behind the spawn promenade
    (56.25, 32.0), (56.25, -34.0),      # Nativity forecourt lawns
    (-88.0, 31.0), (-88.0, -36.0),      # Plaça de la Sagrada Família, facing the Passion façade
]
PLAZA_LAMPS = [
    (110.0, 27.6), (138.0, 27.6), (110.0, -31.0), (138.0, -31.0),   # pond promenade
    (156.5, 17.0), (156.5, -21.0),                                   # spawn bank
    (-96.0, 5.0), (-96.0, -15.0), (-140.0, 0.5), (-176.0, -7.0),     # Plaça de la Sagrada Família
]
