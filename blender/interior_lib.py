"""Geometry helpers for the interior, crypt and sacristies (architecture-accuracy pass).

Everything here is built from the rules Gaudí used, so the numbers stay traceable:

* Double-twist columns (sagradafamilia.org blog "The columns of the Sagrada Família", Junta Constructora):
  - base section is a star of n points formed by regular polygons (6 = two triangles, 8 = two squares,
    10 = two pentagons, 12 = three squares);
  - the shaft is the INTERSECTION of two prisms on that star rotating in opposite senses; where the two
    rotations reach half a point pitch the section has 2n points; that section is the base of the next
    piece, which is half as tall and turns half as much, giving 4n, then 8n points -> nearly circular;
  - column height (to the top of the knot) = 2 x points in metres, base height = points in decimetres,
    shaft height = 10 x diameter; diameter taken as 0.175 m per point (2.10 m for the 12-point porphyry
    columns, the only diameter found in a source; the others follow the published proportionality).
* Vaults: hyperboloids of one sheet built from their straight rulings, each clipped to its bay polygon.
  Identical mirrored neighbours therefore meet exactly on the bay boundary (a hyperbola), the corners
  of each bay (above the columns) are the lowest points and the collars carry the oculi.
* Sacristy dome: twelve paraboloids, the dome surface is their lower envelope (ridges between lobes).
"""

from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Vector

from common import (
    add_cylinder,
    add_lathe,
    add_swept_tube,
    apply_box_uv,
    bake_bvh_vertex_ao,
)

# ─────────────────────────────────────────────────────────────────────────────
# 1. Double-twist columns
# ─────────────────────────────────────────────────────────────────────────────

# n points -> (number of regular polygons, polygon sides)  [Gaudí's star construction]
STAR_POLYGONS = {6: (2, 3), 8: (2, 4), 10: (2, 5), 12: (3, 4)}
# Concave depth of the star sides (relative to the circumradius). The real bases have rounded
# (parabolic) concave sides rather than the knife-sharp polygon union; 0.12 keeps the 1:10
# shaft/diameter look while the doubling of points stays clearly readable.
STAR_FLUTE_DEPTH = 0.12


def column_dims(n: int) -> dict:
    """Gaudí's proportional rule for a column with an n-pointed base (all in metres, from floor)."""
    d = 0.175 * n           # base diameter: 12 -> 2.10 m (published), 10 -> 1.75, 8 -> 1.40, 6 -> 1.05
    base_h = 0.1 * n        # base height = points in decimetres
    shaft_h = 10.0 * d      # shaft height = 10 x diameter
    knot_h = 0.9 * d        # ellipsoidal knot (capital), height ~0.9 D
    knot_r = 0.62 * d
    total = base_h + shaft_h + knot_h  # ~= 2 n metres (24 / 20 / 16 / 12 m)
    return {
        "n": n, "d": d, "base_h": base_h, "shaft_h": shaft_h, "knot_h": knot_h, "knot_r": knot_r,
        "knot_c": base_h + shaft_h + 0.5 * knot_h, "total": total,
    }


def _star_radius(theta: float, n: int) -> float:
    """Unit-circumradius star with n points at theta = 2*pi*k/n and rounded concave sides."""
    sector = 2.0 * math.pi / n
    u = (theta % sector) / sector  # 0 at a point, 0.5 mid-side, 1 next point
    return 1.0 - STAR_FLUTE_DEPTH * (1.0 - (2.0 * u - 1.0) ** 2)


def _twist_profile(theta: float, n: int, level: int, frac: float) -> float:
    """Radius of the double-twist section.

    level = which piece of the shaft (1, 2, 3); frac = 0..1 inside that piece.
    Piece k rotates its base section by +/- beta_k * frac and keeps the intersection (min).
    beta_1 = pi / (2n) -> relative rotation pi/n at the top -> 2n points; beta_k halves each piece.
    """
    def top(th: float, k: int) -> float:
        if k == 0:
            return _star_radius(th, n)
        b = math.pi / (2.0 * n) / (2 ** (k - 1))
        return min(top(th + b, k - 1), top(th - b, k - 1))

    b = math.pi / (2.0 * n) / (2 ** (level - 1)) * frac
    return min(top(theta + b, level - 1), top(theta - b, level - 1))


def build_double_twist_column_mesh(name: str, mat: bpy.types.Material, n: int) -> tuple[bpy.types.Mesh, dict]:
    """Column instance mesh with its foot at z = 0: star base, 3-piece double-twist shaft, ellipsoid knot."""
    dm = column_dims(n)
    r0 = 0.5 * dm["d"]
    # 4n samples (spacing pi/2n): every point AND valley of the base star and of the 2n-point section
    # falls exactly on a sample; the 4n / 8n ripples higher up are only ~1-3 % of the radius and are
    # smoothed (8n samples would double the collision triangles of the 46 columns)
    radial = 4 * n
    bm = bmesh.new()

    def ring_at(z: float, fn, scale: float = 1.0) -> list:
        out = []
        for i in range(radial):
            th = 2.0 * math.pi * i / radial
            r = r0 * scale * fn(th)
            out.append(bm.verts.new((r * math.cos(th), r * math.sin(th), z)))
        return out

    def bridge(a: list, b: list) -> None:
        for i in range(radial):
            j = (i + 1) % radial
            bm.faces.new((a[i], a[j], b[j], b[i]))

    star = lambda th: _star_radius(th, n)
    # Base (plinth): the star itself, slightly wider, height = n decimetres
    b_bot = ring_at(0.0, star, 1.06)
    b_top = ring_at(dm["base_h"] - 0.06, star, 1.06)
    b_lip = ring_at(dm["base_h"], star, 1.0)
    bm.faces.new(list(reversed(b_bot)))
    bridge(b_bot, b_top)
    bridge(b_top, b_lip)

    # Shaft: pieces of height h, h/2, h/4 (sum = shaft height) with 5 / 3 / 2 ring intervals
    h1 = dm["shaft_h"] / 1.75
    pieces = [(1, h1, 5), (2, h1 * 0.5, 3), (3, h1 * 0.25, 2)]
    z = dm["base_h"]
    prev = b_lip
    for level, h, steps in pieces:
        for s in range(1, steps + 1):
            f = s / steps
            ring = ring_at(z + f * h, lambda th, lv=level, ff=f: _twist_profile(th, n, lv, ff))
            bridge(prev, ring)
            prev = ring
        z += h

    # Ellipsoidal knot (capital) swallowing the near-circular top section
    kc, kh, kr = dm["knot_c"], dm["knot_h"], dm["knot_r"]
    k_segs = 2 * n
    profile = []
    for i in range(9):
        phi = -math.pi / 2 + math.pi * (0.08 + 0.84 * i / 8)
        profile.append((kc + 0.5 * kh * math.sin(phi), kr * math.cos(phi)))
    add_lathe(bm, 0.0, 0.0, profile, segments=k_segs, cap_bottom=True, cap_top=True)
    bm.faces.new(list(prev))  # close the shaft top (hidden inside the knot)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    apply_box_uv(bm, scale=0.22)
    bake_bvh_vertex_ao(bm, max_dist=3.2, min_ao=0.55)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    mesh.materials.append(mat)
    return mesh, dm


# ─────────────────────────────────────────────────────────────────────────────
# 2. Hyperboloid vault field (ruled surfaces per bay)
# ─────────────────────────────────────────────────────────────────────────────

class HyperboloidBay:
    """One vault cell: a hyperboloid of one sheet with vertical axis through (cx, cy), collar (throat)
    radius a at height z_top, clipped by its bay polygon (CCW list of (x, y)). The deepest point
    (farthest polygon vertex) lies `depth` below the collar."""

    def __init__(self, cx: float, cy: float, poly: list[tuple[float, float]], z_top: float, depth: float, throat: float, tag: str = ""):
        self.cx, self.cy = cx, cy
        self.poly = poly
        self.z_top = z_top
        self.depth = depth
        self.a = throat
        self.tag = tag
        r_far = max(math.hypot(px - cx, py - cy) for px, py in poly)
        self.c = depth / math.sqrt(max((r_far / throat) ** 2 - 1.0, 1e-6))

    @staticmethod
    def rect(cx: float, cy: float, sx: float, sy: float, z_top: float, depth: float, throat: float, tag: str = "") -> "HyperboloidBay":
        hx, hy = 0.5 * sx, 0.5 * sy
        return HyperboloidBay(cx, cy, [(cx - hx, cy - hy), (cx + hx, cy - hy), (cx + hx, cy + hy), (cx - hx, cy + hy)], z_top, depth, throat, tag)

    def contains(self, x: float, y: float) -> bool:
        inside = False
        pts = self.poly
        j = len(pts) - 1
        for i in range(len(pts)):
            xi, yi = pts[i]
            xj, yj = pts[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
                inside = not inside
            j = i
        return inside

    def height(self, x: float, y: float) -> float:
        r = max(math.hypot(x - self.cx, y - self.cy), self.a)
        return self.z_top - self.c * math.sqrt((r / self.a) ** 2 - 1.0)

    # Ruling: P(u, v) = C + a (cos u - v sin u, sin u + v cos u),  z = z_top - c v   (v >= 0)
    def ruling_point(self, u: float, v: float) -> Vector:
        a = self.a
        return Vector((self.cx + a * (math.cos(u) - v * math.sin(u)), self.cy + a * (math.sin(u) + v * math.cos(u)), self.z_top - self.c * v))

    def v_exit(self, u: float) -> float:
        """Smallest v > 0 at which ruling u leaves the bay polygon."""
        a = self.a
        ox, oy = self.cx + a * math.cos(u), self.cy + a * math.sin(u)
        dx, dy = -a * math.sin(u), a * math.cos(u)
        best = 1e9
        pts = self.poly
        for i in range(len(pts)):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % len(pts)]
            ex, ey = x1 - x0, y1 - y0
            den = dx * ey - dy * ex
            if abs(den) < 1e-12:
                continue
            t = ((x0 - ox) * ey - (y0 - oy) * ex) / den
            s = ((x0 - ox) * dy - (y0 - oy) * dx) / den
            if t > 1e-6 and -1e-6 <= s <= 1.0 + 1e-6:
                best = min(best, t)
        return best if best < 1e8 else 0.0

    def ruling_u_through(self, px: float, py: float) -> float:
        r = math.hypot(px - self.cx, py - self.cy)
        v = math.sqrt(max((r / self.a) ** 2 - 1.0, 0.0))
        return math.atan2(py - self.cy, px - self.cx) - math.atan(v)


class VaultField:
    def __init__(self) -> None:
        self.bays: list[HyperboloidBay] = []

    def add(self, bay: HyperboloidBay) -> HyperboloidBay:
        self.bays.append(bay)
        return bay

    def height(self, x: float, y: float) -> float | None:
        hs = [b.height(x, y) for b in self.bays if b.contains(x, y)]
        return max(hs) if hs else None


def build_hyperboloid_bay(
    bay: HyperboloidBay,
    bm_shell: bmesh.types.BMesh,
    bm_collar: bmesh.types.BMesh | None,
    bm_gold: bmesh.types.BMesh | None,
    bm_lamp: bmesh.types.BMesh | None,
    n_rulings: int = 32,
    v_fracs: tuple[float, ...] = (0.0, 0.08, 0.22, 0.45, 1.0),
    collar_band: int = 1,
) -> None:
    """Mesh the bay from its rulings. Faces face DOWN (into the church). The first `collar_band`
    strips go to bm_collar (green/gold trencadís at the collar, as on the real vaults)."""
    us = [2.0 * math.pi * i / n_rulings for i in range(n_rulings)]
    # Rulings through every polygon vertex (kinks of the clipped boundary) so corners are exact
    for px, py in bay.poly:
        us.append(bay.ruling_u_through(px, py) % (2.0 * math.pi))
    us = sorted(set(round(u, 6) for u in us))
    cols = []
    for u in us:
        vmax = bay.v_exit(u)
        cols.append([bay.ruling_point(u, f * vmax) for f in v_fracs])
    vert_cache: dict[tuple[int, int, int], bmesh.types.BMVert] = {}

    def vert(bm, i, k):
        key = (id(bm), i, k)
        v = vert_cache.get(key)
        if v is None:
            v = bm.verts.new(cols[i][k])
            vert_cache[key] = v
        return v

    nu = len(cols)
    for i in range(nu):
        j = (i + 1) % nu
        for k in range(len(v_fracs) - 1):
            target = bm_collar if (bm_collar is not None and k < collar_band) else bm_shell
            # u increases CCW, v outward/down: (i,k) (i,k+1) (j,k+1) (j,k) gives a downward normal
            f = target.faces.new((vert(target, i, k), vert(target, i, k + 1), vert(target, j, k + 1), vert(target, j, k)))
            f.normal_update()
            if f.normal.z > 0.0:
                f.normal_flip()

    if bm_gold is not None:
        add_flat_ring(bm_gold, bay.cx, bay.cy, bay.z_top, bay.a * 0.98, bay.a * 1.16, 0.22, segs=max(16, n_rulings // 2))
    if bm_lamp is not None:
        # Lamp / skylight disc filling the collar (the real oculi carry lights)
        add_cylinder(bm_lamp, Vector((bay.cx, bay.cy, bay.z_top + 0.05)), Vector((bay.cx, bay.cy, bay.z_top + 0.25)), bay.a, bay.a, segments=max(12, n_rulings // 2), cap=True)


def add_flat_ring(bm: bmesh.types.BMesh, cx: float, cy: float, z: float, r_in: float, r_out: float, h: float, segs: int = 16) -> None:
    """Closed annular ring (rectangular cross-section) so normal recalculation is unambiguous."""
    rings = []
    for (r, dz) in ((r_in, -h * 0.5), (r_out, -h * 0.5), (r_out, h * 0.5), (r_in, h * 0.5)):
        rings.append([bm.verts.new((cx + r * math.cos(2 * math.pi * k / segs), cy + r * math.sin(2 * math.pi * k / segs), z + dz)) for k in range(segs)])
    for a in range(4):
        ra, rb = rings[a], rings[(a + 1) % 4]
        for k in range(segs):
            nk = (k + 1) % segs
            bm.faces.new((ra[k], ra[nk], rb[nk], rb[k]))


def finalize_oriented(bm: bmesh.types.BMesh, name: str, mat: bpy.types.Material, smooth: bool = True, uv_scale: float = 0.14, ao: bool = True, ao_dist: float = 4.0) -> bpy.types.Object:
    """Like common.finalize_bmesh_object but keeps the authored face orientation (open shells that
    must face down into the church with single-sided materials)."""
    bm.normal_update()
    apply_box_uv(bm, scale=uv_scale)
    if ao and len(bm.verts) <= 60000:
        bake_bvh_vertex_ao(bm, max_dist=ao_dist, min_ao=0.5)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    if smooth and len(mesh.polygons):
        mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


# ─────────────────────────────────────────────────────────────────────────────
# 3. Tree canopy: knot -> inclined branches -> secondary knots -> twigs ending ON the vault surface
# ─────────────────────────────────────────────────────────────────────────────

def add_column_canopy(
    bm: bmesh.types.BMesh,
    bm_lamps: bmesh.types.BMesh | None,
    x: float,
    y: float,
    z_knot_top: float,
    angles: list[float],
    reach: float,
    r_branch: float,
    field: VaultField,
    twigs: int = 3,
    twig_spread: float = 1.0,
    split: float = 0.5,
    fallback_z: float = 30.0,
    max_z: float | None = None,
    sides: int = 6,
) -> None:
    p0 = Vector((x, y, z_knot_top - 0.15))
    for ang in angles:
        ca, sa = math.cos(ang), math.sin(ang)
        # Twig targets first (on the vault), the secondary knot sits on the way to their centroid
        tips = []
        for j in range(twigs):
            da = 0.0 if twigs == 1 else (j / (twigs - 1) - 0.5) * twig_spread
            a2 = ang + da
            rr = reach * (0.86 + 0.14 * (1.0 - abs(da)))
            tx, ty = x + rr * math.cos(a2), y + rr * math.sin(a2)
            tz = field.height(tx, ty)
            if tz is None:
                tz = fallback_z
            if max_z is not None:
                tz = min(tz, max_z)
            tips.append(Vector((tx, ty, tz - 0.12)))
        mean_z = sum(t.z for t in tips) / len(tips)
        pk = Vector((x + reach * 0.38 * ca, y + reach * 0.38 * sa, p0.z + (mean_z - p0.z) * split))
        add_swept_tube(bm, [p0.lerp(pk, f) for f in (0.0, 0.5, 1.0)], [r_branch * (1.0 - 0.15 * f) for f in (0.0, 0.5, 1.0)], segments=sides)
        kr = r_branch * 1.35
        add_lathe(
            bm, pk.x, pk.y,
            [(pk.z - kr * 1.5, kr * 0.55), (pk.z - kr * 0.7, kr * 0.95), (pk.z + kr * 0.3, kr), (pk.z + kr * 1.1, kr * 0.7), (pk.z + kr * 1.6, kr * 0.4)],
            segments=sides, cap_bottom=True, cap_top=True,
        )
        if bm_lamps is not None:
            add_lathe(bm_lamps, pk.x + ca * kr * 0.97, pk.y + sa * kr * 0.97,
                      [(pk.z - 0.12, 0.05), (pk.z, 0.13), (pk.z + 0.12, 0.05)], segments=6, cap_bottom=True, cap_top=True)
        q0 = pk + Vector((0.0, 0.0, kr * 1.1))
        for tip in tips:
            add_swept_tube(bm, [q0.lerp(tip, f) for f in (0.0, 0.5, 1.0)], [r_branch * (0.6 - 0.18 * f) for f in (0.0, 0.5, 1.0)], segments=5)
            add_cylinder(bm, tip - Vector((0.0, 0.0, 0.3)), tip + Vector((0.0, 0.0, 0.35)), r_branch * 0.42, r_branch * 0.95, segments=6, cap=True)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Crypt helpers (neo-Gothic ribbed vaults on clustered piers)
# ─────────────────────────────────────────────────────────────────────────────

def add_clustered_pier(bm: bmesh.types.BMesh, x: float, y: float, z0: float, z1: float, r: float, shafts: int = 8, cap_h: float = 0.45) -> None:
    """Gothic compound pier: core + ring of attached colonnettes + moulded base and capital."""
    add_lathe(bm, x, y, [(z0, r * 1.45), (z0 + 0.36, r * 1.4), (z0 + 0.5, r * 1.05)], segments=10, cap_bottom=False, cap_top=True)
    add_cylinder(bm, Vector((x, y, z0 + 0.45)), Vector((x, y, z1)), r * 0.82, r * 0.82, segments=10, cap=False)
    for k in range(shafts):
        a = 2.0 * math.pi * k / shafts
        sx, sy = x + r * 0.82 * math.cos(a), y + r * 0.82 * math.sin(a)
        rr = r * (0.30 if k % 2 == 0 else 0.22)
        add_cylinder(bm, Vector((sx, sy, z0 + 0.45)), Vector((sx, sy, z1 - cap_h)), rr, rr, segments=5, cap=False)
    add_lathe(bm, x, y, [(z1 - cap_h, r * 1.05), (z1 - 0.12, r * 1.45), (z1, r * 1.45)], segments=10, cap_bottom=False, cap_top=True)


def _arch_lift(t: float) -> float:
    """Pointed-arch profile 0..1..0 over t in 0..1."""
    return math.sin(math.pi * t) ** 0.75


def add_groin_vault_cell(
    bm: bmesh.types.BMesh,
    bm_ribs: bmesh.types.BMesh | None,
    corners: list[Vector],
    z_spring: float,
    z_crown: float,
    res: int = 6,
    rib_r: float = 0.11,
) -> Vector:
    """Ribbed groin vault over a (possibly irregular) quad p0 p1 p2 p3.
    Intrados = upper envelope of two intersecting pointed barrels, z = spring + max(arch(a), arch(b)) * H:
    the wall edges are pointed arches, the groins run along the diagonals and carry the ribs.
    Faces face down. Returns the boss position."""
    p0, p1, p2, p3 = corners
    H = z_crown - z_spring

    def pt(a: float, b: float) -> Vector:
        base = (p0 * (1 - a) * (1 - b) + p1 * a * (1 - b) + p2 * a * b + p3 * (1 - a) * b)
        z = z_spring + max(_arch_lift(a), _arch_lift(b)) * H
        return Vector((base.x, base.y, z))

    grid = [[bm.verts.new(pt(i / res, j / res)) for j in range(res + 1)] for i in range(res + 1)]
    for i in range(res):
        for j in range(res):
            f = bm.faces.new((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]))
            f.normal_update()
            if f.normal.z > 0:
                f.normal_flip()
    boss = pt(0.5, 0.5)
    if bm_ribs is not None:
        n = 4
        for diag in ((0.0, 0.0, 1.0, 1.0), (1.0, 0.0, 0.0, 1.0)):
            pts = []
            for s in range(n + 1):
                t = s / n
                a = diag[0] + (diag[2] - diag[0]) * t
                b = diag[1] + (diag[3] - diag[1]) * t
                pts.append(pt(a, b) - Vector((0, 0, 0.06)))
            add_swept_tube(bm_ribs, pts, [rib_r] * len(pts), segments=4, cap=False)
    return boss


def add_web_vault_sector(
    bm: bmesh.types.BMesh,
    a: Vector,
    b: Vector,
    key: Vector,
    z_spring: float,
    arch_rise: float,
    res_s: int = 4,
    res_t: int = 6,
) -> None:
    """Triangular vault web between two piers (a, b) at spring height and a keystone: the wall edge
    is a pointed arch, the web rises concavely to the key. Faces face down."""
    verts = []
    for i in range(res_s):
        s = i / res_s
        row = []
        for j in range(res_t + 1):
            t = j / res_t
            e = a.lerp(b, t)
            ez = z_spring + arch_rise * _arch_lift(t)
            k = 1.0 - (1.0 - s) ** 2
            p = Vector((e.x, e.y, ez)).lerp(key, s)
            p.z = ez + (key.z - ez) * k
            row.append(bm.verts.new(p))
        verts.append(row)
    vk = bm.verts.new(key)
    faces = []
    for i in range(res_s):
        for j in range(res_t):
            if i == res_s - 1:
                faces.append(bm.faces.new((verts[i][j], verts[i][j + 1], vk)))
            else:
                faces.append(bm.faces.new((verts[i][j], verts[i][j + 1], verts[i + 1][j + 1], verts[i + 1][j])))
    for f in faces:
        f.normal_update()
        if f.normal.z > 0:
            f.normal_flip()


# ─────────────────────────────────────────────────────────────────────────────
# 5. Twelve-paraboloid dome (sacristies)
# ─────────────────────────────────────────────────────────────────────────────

def paraboloid_dome_z(x: float, y: float, cx: float, cy: float, r_base: float, z_base: float, z_top: float, lobes: int = 12, ecc: float = 0.3, phase: float = 0.0) -> float:
    """Lower envelope of `lobes` paraboloids of revolution. Paraboloid k has its vertical axis offset by
    e = ecc*r_base AWAY from lobe direction k, so it is the lowest one over its own sector; adjacent
    paraboloids meet along vertical bisector planes -> sharp ridges between the twelve segments.
    Each satisfies z = z_top at the centre and z = z_base at r_base on the lobe axis."""
    e = ecc * r_base
    four_f = ((r_base + e) ** 2 - e ** 2) / (z_top - z_base)
    apex = z_top + e * e / four_f
    zmin = 1e9
    for k in range(lobes):
        phi = phase + 2.0 * math.pi * k / lobes
        ax, ay = cx - e * math.cos(phi), cy - e * math.sin(phi)
        d2 = (x - ax) ** 2 + (y - ay) ** 2
        zmin = min(zmin, apex - d2 / four_f)
    return zmin


def add_paraboloid_dome(
    bm_out: bmesh.types.BMesh,
    cx: float,
    cy: float,
    r_base: float,
    z_base: float,
    z_top: float,
    r_open: float,
    thickness: float = 0.45,
    lobes: int = 12,
    steps_per_lobe: int = 6,
    rings: int = 9,
    ecc: float = 0.3,
    rib_r: float = 0.0,
) -> None:
    """Closed dome shell (outer + inner surface + rims) from r_open (lantern opening) to r_base;
    the angular samples include every ridge (sector boundary) so the ridges are exact."""
    n_ang = lobes * steps_per_lobe
    phase = 0.0
    angs = [phase + math.pi / lobes + 2.0 * math.pi * i / n_ang for i in range(n_ang)]  # starts on a ridge

    def surf(r: float, th: float, off: float) -> Vector:
        x, y = cx + r * math.cos(th), cy + r * math.sin(th)
        z = paraboloid_dome_z(x, y, cx, cy, r_base, z_base, z_top, lobes, ecc=ecc, phase=phase) - off
        return Vector((x, y, max(z, z_base - off)))

    outer, inner = [], []
    for i in range(rings + 1):
        t = i / rings
        r = r_open + (r_base - r_open) * (t ** 0.85)
        outer.append([bm_out.verts.new(surf(r, th, 0.0)) for th in angs])
        inner.append([bm_out.verts.new(surf(max(r - thickness * 0.3, 0.05), th, thickness)) for th in angs])
    for i in range(rings):
        for k in range(n_ang):
            nk = (k + 1) % n_ang
            bm_out.faces.new((outer[i][k], outer[i + 1][k], outer[i + 1][nk], outer[i][nk]))
            bm_out.faces.new((inner[i][nk], inner[i + 1][nk], inner[i + 1][k], inner[i][k]))
    for k in range(n_ang):
        nk = (k + 1) % n_ang
        bm_out.faces.new((outer[0][nk], inner[0][nk], inner[0][k], outer[0][k]))
        # Base rim: drop each sample down to the drum top -> arched spandrels between the lobes
        a0, a1 = outer[-1][k], outer[-1][nk]
        b0 = bm_out.verts.new((a0.co.x, a0.co.y, z_base))
        b1 = bm_out.verts.new((a1.co.x, a1.co.y, z_base))
        if a0.co.z - z_base > 0.02 or a1.co.z - z_base > 0.02:
            bm_out.faces.new((a0, b0, b1, a1))
        c0, c1 = inner[-1][k], inner[-1][nk]
        bm_out.faces.new((a0, a1, c1, c0))
    if rib_r > 0.0:
        # stone ribs on the twelve ridges where neighbouring paraboloids meet
        for k in range(0, n_ang, steps_per_lobe):
            pts = [outer[i][k].co + Vector((0.0, 0.0, rib_r * 0.4)) for i in range(rings + 1)]
            add_swept_tube(bm_out, pts, [rib_r] * len(pts), segments=6)


def add_ruled_hyperboloid_shell(
    bm: bmesh.types.BMesh,
    cx: float,
    cy: float,
    z0: float,
    z1: float,
    r_end: float,
    twist: float,
    n: int = 16,
) -> None:
    """Hyperboloid of one sheet as n straight rulings between two circles of radius r_end at z0, z1,
    the upper circle rotated by `twist` (the lanterns / skylights). Closed by thin end rings."""
    lo = [bm.verts.new((cx + r_end * math.cos(2 * math.pi * k / n), cy + r_end * math.sin(2 * math.pi * k / n), z0)) for k in range(n)]
    hi = [bm.verts.new((cx + r_end * math.cos(2 * math.pi * k / n + twist), cy + r_end * math.sin(2 * math.pi * k / n + twist), z1)) for k in range(n)]
    mid_z = 0.5 * (z0 + z1)
    mid_r = r_end * math.cos(twist * 0.5)
    mid = [bm.verts.new((cx + mid_r * math.cos(2 * math.pi * k / n + twist * 0.5), cy + mid_r * math.sin(2 * math.pi * k / n + twist * 0.5), mid_z)) for k in range(n)]
    for k in range(n):
        nk = (k + 1) % n
        bm.faces.new((lo[k], lo[nk], mid[nk], mid[k]))
        bm.faces.new((mid[k], mid[nk], hi[nk], hi[k]))
