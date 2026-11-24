"""Geometry helpers for build_towers.py (architecture-accuracy pass).

Target values used here (traceable; see also the constants in build_towers.py):
  * Tower of Jesus Christ: 172.5 m; stone body ends at 142.5 m (12th panel level); 29 m pinnacle in
    two parts: terminal 142.5..155.65 m + 17 m (16.85 m) four-armed 3-D cross, 13.5 m wide.
    Cross pieces: lower arm 7.25 m tall, central core a truncated cube with octagonal faces of 4.7 m,
    horizontal arms 4.4 x 4.5 x 4.5 m, upper arm 4.5 x 4.5 x 4.9 m; glass + white glazed ceramic.
    (sagradafamilia.org press releases 2021-2026, blog "phases construction jesus tower").
  * Tower of the Virgin Mary: 138 m; 6 m stone crown carrying twelve wrought-iron stars, then an
    18 m reinforced-concrete hyperboloid "lantern" rising from six legs and ending in three arms that
    hold the 7.5 m twelve-pointed glass star; white and blue trencadis with triangular / rhomboid
    openings (sagradafamilia.org "Last step before completing the tower of the Virgin Mary").
  * Evangelist towers: 135 m; base from the vaults at 45 m to 74 m, main body to 112.5 m, 22.5 m
    pinnacle: shaft with hexagonal shields ("Amen", "Alleluia") and trencadis palms, a trencadis
    icosahedron with gold spherical bulges (holds the spotlights), the common 9 m white-cement
    elliptical hyperboloid with two reinforced-cement wings, the open book and the 4.5 m Thassos-marble
    figure (sagradafamilia.org, Luke / Mark / Matthew terminal releases 2022-2023).
"""

from __future__ import annotations

import math

import bmesh
from mathutils import Vector

from common import add_cylinder, add_ellipsoid, add_lathe


# ───────────────────────────── profiles & sections ─────────────────────────────

def paraboloid_radius(r0: float, z0: float, z_apex: float):
    """Gaudí's parabolic tower envelope: r(z) = r0 * sqrt((z_apex - z) / (z_apex - z0))
    (a paraboloid of revolution with its vertex at the tip of the pinnacle)."""
    span = max(1e-3, z_apex - z0)

    def r_of_z(z: float) -> float:
        return r0 * math.sqrt(max(0.0, (z_apex - z) / span))

    return r_of_z


def superellipse_gain(ang: float, p: float) -> float:
    """Radius multiplier (>= 1) turning a circle into a rounded square of exponent p (p=2 -> circle)."""
    c, s = abs(math.cos(ang)), abs(math.sin(ang))
    return 1.0 / max(1e-6, (c ** p + s ** p) ** (1.0 / p))


# ───────────────────────────── solid tower shell ─────────────────────────────

def add_tower_shell(
    bm: bmesh.types.BMesh,
    cx: float,
    cy: float,
    zs: list[float],
    radius_at_z,
    sectors: int,
    cell_kind,
    thickness: float = 0.30,
    louvres: int = 0,
    section=None,
    phase: float = 0.0,
    bm_alt=None,
    alt_from_z: float = 1e9,
) -> None:
    """Double-skinned tower shaft built from (row x sector) cells on the given ring heights.

    radius_at_z(z) gives the round envelope; section(z, ang) (optional) is an outward-only multiplier
    for square / elliptical lower sections that blend into the round parabolic shaft. The inner skin
    is offset by a constant `thickness`, so a section change never narrows the stair well.
    cell_kind(row, k, z_lo, z_hi, ang_mid) -> 'solid' | 'open' | 'louvre'.
    """
    rows = len(zs) - 1
    rings_o: list[list[Vector]] = []
    rings_i: list[list[Vector]] = []
    for z in zs:
        r = radius_at_z(z)
        ro, ri = [], []
        for k in range(sectors):
            a = phase + 2.0 * math.pi * k / sectors
            m = section(z, a) if section is not None else 1.0
            rr = r * m
            ro.append(Vector((cx + rr * math.cos(a), cy + rr * math.sin(a), z)))
            ri.append(Vector((cx + (rr - thickness) * math.cos(a), cy + (rr - thickness) * math.sin(a), z)))
        rings_o.append(ro)
        rings_i.append(ri)

    kinds = [[cell_kind(row, k, zs[row], zs[row + 1], phase + 2.0 * math.pi * (k + 0.5) / sectors) for k in range(sectors)] for row in range(rows)]

    def quad(b, a, bb, c, d):
        b.faces.new((b.verts.new(a), b.verts.new(bb), b.verts.new(c), b.verts.new(d)))

    vcache: dict = {}

    def sv(b, side: str, row: int, k: int):
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
                target.faces.new((sv(target, "o", row, k), sv(target, "o", row, nk), sv(target, "o", row + 1, nk), sv(target, "o", row + 1, k)))
                target.faces.new((sv(target, "i", row, nk), sv(target, "i", row, k), sv(target, "i", row + 1, k), sv(target, "i", row + 1, nk)))
                continue
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
                # Gaudí's stone "blinds": slats inclined outward-down to shed rain and throw the
                # sound of the bells down to the street.
                h = zs[row + 1] - zs[row]
                for j in range(louvres):
                    f = (j + 0.75) / (louvres + 0.5)
                    zl = zs[row] + h * f
                    rise = h / (louvres + 0.5) * 0.55
                    a0 = o00.lerp(o01, f) + (i00 - o00) * 0.02
                    a1 = o10.lerp(o11, f) + (i10 - o10) * 0.02
                    b0 = i00.lerp(i01, f) + Vector((0, 0, rise))
                    b1 = i10.lerp(i11, f) + Vector((0, 0, rise))
                    a0.z = a1.z = zl
                    t_off = Vector((0, 0, 0.09))
                    quad(target, a0 + t_off, a1 + t_off, b1 + t_off, b0 + t_off)
                    quad(target, b0, b1, a1, a0)


# ───────────────────────────── UVs ─────────────────────────────

def apply_tower_uv(bm: bmesh.types.BMesh, axes: list[tuple[float, float, float]], scale: float) -> None:
    """Cylindrical (arc-length x height) UVs around the nearest tower axis for the curved shells,
    planar XY for near-horizontal faces and box projection for everything away from a tower axis.
    axes: (cx, cy, max_radius). Removes the stretching / banding of pure box projection on round shafts."""
    uv_layer = bm.loops.layers.uv.verify()
    bm.faces.ensure_lookup_table()
    for face in bm.faces:
        n = face.normal
        c = face.calc_center_median()
        if abs(n.z) > 0.72:
            for loop in face.loops:
                co = loop.vert.co
                loop[uv_layer].uv = (co.x * scale, co.y * scale)
            continue
        best = None
        best_d = 1e9
        for ax, ay, rmax in axes:
            d = math.hypot(c.x - ax, c.y - ay)
            if d < rmax and d < best_d:
                best, best_d = (ax, ay), d
        if best is None or best_d < 0.25:
            ax_, ay_, az_ = abs(n.x), abs(n.y), abs(n.z)
            for loop in face.loops:
                co = loop.vert.co
                if ax_ >= ay_:
                    loop[uv_layer].uv = (co.y * scale, co.z * scale)
                else:
                    loop[uv_layer].uv = (co.x * scale, co.z * scale)
            continue
        ax, ay = best
        ang_f = math.atan2(c.y - ay, c.x - ax)
        for loop in face.loops:
            co = loop.vert.co
            a = math.atan2(co.y - ay, co.x - ax)
            da = (a - ang_f + math.pi) % (2.0 * math.pi) - math.pi
            loop[uv_layer].uv = ((ang_f + da) * best_d * scale, co.z * scale)


# ───────────────────────────── Apostle pinnacle ─────────────────────────────

PIN_LOCAL_H = 22.0   # local height of the shared pinnacle mesh (scaled per tower in Z)
PIN_LOCAL_R = 2.0    # local base radius (scaled per tower in XY to the shaft radius at the neck)

# (z, r/R) faceted shaft profile: collar, slightly swelling hollow polygonal stem, waist, mitre socket
_PIN_PROFILE = [
    (-0.6, 1.04), (0.5, 1.07), (0.9, 0.93), (3.5, 0.97), (6.5, 0.86), (9.5, 0.66),
    (11.6, 0.50), (12.2, 0.58), (12.8, 0.42),
]


def _pin_r(z: float) -> float:
    for (z0, r0), (z1, r1) in zip(_PIN_PROFILE[:-1], _PIN_PROFILE[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            return PIN_LOCAL_R * (r0 + (r1 - r0) * t)
    return PIN_LOCAL_R * _PIN_PROFILE[-1][1]


def build_apostle_pinnacle(bm_stem, bm_pearl, bm_gold) -> None:
    """Apostle-tower pinnacle in local space (origin = top of the stone shaft, +X = outward face).

    Staged as on the built towers: faceted polygonal stem clad in coloured Venetian-glass trencadís
    with rows of white spheres on its ridges, a waist with a ring of spheres (the bishop's ring),
    then the mitre (pointed lens) bearing a cross of white spheres on both faces, the crozier hooked
    on one side and the gilded cross at the very top."""
    R = PIN_LOCAL_R
    seg = 12
    add_lathe(bm_stem, 0.0, 0.0, [(z, r * R) for z, r in _PIN_PROFILE], segments=seg, cap_top=True, phase=math.pi / seg)

    # Mitre: pointed lens 12.6..20.2 m, flattened front-to-back
    z_m0, z_m1 = 12.5, 20.2
    lens = []
    n = 12
    for i in range(n + 1):
        t = i / n
        w = 1.55 * math.sin(math.pi * min(1.0, 0.18 + t * 0.86)) ** 0.75 + 0.04
        lens.append((z_m0 + t * (z_m1 - z_m0), w))
    add_lathe(bm_stem, 0.0, 0.0, lens, segments=12, cap_bottom=True, cap_top=True, squash=(0.45, 1.0))

    def lens_w(z: float) -> float:
        t = max(0.0, min(1.0, (z - z_m0) / (z_m1 - z_m0)))
        return 1.55 * math.sin(math.pi * min(1.0, 0.18 + t * 0.86)) ** 0.75 + 0.04

    # White spheres on the 12 ridges of the stem (3 tiers)
    for zt, pr in ((2.2, 0.36), (5.0, 0.32), (7.9, 0.27)):
        rr = _pin_r(zt) + pr * 0.45
        for k in range(0, seg, 2):
            a = 2.0 * math.pi * (k + (1 if zt == 5.0 else 0)) / seg
            add_ellipsoid(bm_pearl, (rr * math.cos(a), rr * math.sin(a), zt), (pr, pr, pr), subdivisions=1)
    # Bishop's ring: gilded torus at the waist ringed with white spheres
    ring_r, ring_z = _pin_r(12.2) + 0.12, 12.2
    pts = [Vector((ring_r * math.cos(2 * math.pi * i / 16), ring_r * math.sin(2 * math.pi * i / 16), ring_z)) for i in range(17)]
    for p0, p1 in zip(pts[:-1], pts[1:]):
        add_cylinder(bm_gold, p0, p1, 0.16, 0.16, segments=5, cap=False)
    for k in range(8):
        a = 2.0 * math.pi * (k + 0.5) / 8
        add_ellipsoid(bm_pearl, ((ring_r + 0.25) * math.cos(a), (ring_r + 0.25) * math.sin(a), ring_z), (0.26, 0.26, 0.26), subdivisions=1)
    # Cross of white spheres on both faces of the mitre
    for side in (-1, 1):
        for zc in (14.0, 15.2, 16.4, 17.6, 18.7):
            x = side * (lens_w(zc) * 0.45 + 0.12)
            add_ellipsoid(bm_pearl, (x, 0.0, zc), (0.3, 0.3, 0.3), subdivisions=1)
        for yc in (-0.85, 0.85):
            x = side * (lens_w(16.4) * 0.45 * math.sqrt(max(0.0, 1.0 - (yc / lens_w(16.4)) ** 2)) + 0.12)
            add_ellipsoid(bm_pearl, (x, yc, 16.4), (0.28, 0.28, 0.28), subdivisions=1)
    # Gilded rim seams of the mitre
    for sgn in (-1, 1):
        prev = None
        for i in range(9):
            z = z_m0 + 0.4 + (z_m1 - z_m0 - 0.4) * i / 8
            p = Vector((0.0, sgn * lens_w(z), z))
            if prev is not None:
                add_cylinder(bm_gold, prev, p, 0.1, 0.1, segments=5, cap=False)
            prev = p
    # Crozier: staff on the -Y flank with its spiral hook
    base = Vector((0.0, -1.35, 10.2))
    top = Vector((0.0, -1.75, 18.0))
    add_cylinder(bm_gold, base, top, 0.13, 0.12, segments=6, cap=False)
    ctr = top + Vector((0.0, -0.7, 0.0))
    hook = []
    for i in range(10):
        a = math.pi * 1.6 * i / 9
        rr = 0.7 * (1.0 - 0.4 * i / 9)
        hook.append(ctr + Vector((0.0, rr * math.cos(a), rr * math.sin(a))))
    for p0, p1 in zip(hook[:-1], hook[1:]):
        add_cylinder(bm_gold, p0, p1, 0.12, 0.11, segments=5, cap=False)
    # Gilded cross finial
    add_cylinder(bm_gold, Vector((0.0, 0.0, z_m1 - 0.3)), Vector((0.0, 0.0, PIN_LOCAL_H)), 0.16, 0.13, segments=6)
    add_cylinder(bm_gold, Vector((0.0, -0.6, PIN_LOCAL_H - 0.55)), Vector((0.0, 0.6, PIN_LOCAL_H - 0.55)), 0.12, 0.12, segments=6)
    add_cylinder(bm_gold, Vector((-0.6, 0.0, PIN_LOCAL_H - 0.55)), Vector((0.6, 0.0, PIN_LOCAL_H - 0.55)), 0.12, 0.12, segments=6)


# ───────────────────────────── Evangelist terminal ─────────────────────────────

def add_icosahedron(bm, center: Vector, radius: float) -> list[Vector]:
    ret = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=radius)
    for v in ret["verts"]:
        v.co += center
    return [f.calc_center_median() for f in {f for v in ret["verts"] for f in v.link_faces}]


def _wing(bm, root: Vector, f: Vector, s: Vector, side: int, span: float, height: float) -> None:
    """Big reinforced-cement wing: fan of six long flattened feathers rising from the root."""
    for i in range(7):
        t = i / 6.0
        # overlapping primaries fanning from nearly vertical (inner) to outward-and-up (outer)
        ang = math.radians(8 + 50 * t)
        length = height * (1.0 - 0.42 * t)
        d = (Vector((0, 0, 1)) * math.cos(ang) + s * side * math.sin(ang) - f * 0.15).normalized()
        mid = root + d * (length * 0.5) + s * side * span * 0.05 * t
        rad = (1.05 - 0.25 * t, 0.2, length * 0.5)
        verts = add_ellipsoid(bm, mid, (1.0, 1.0, 1.0), subdivisions=1 if i % 2 else 2)
        # orthonormal frame: z' = d, x' = s side, y' = f
        zx = d
        yx = f.cross(zx).normalized() if abs(f.dot(zx)) < 0.98 else s
        xx = zx.cross(yx).normalized()
        for v in verts:
            lv = v.co - mid
            v.co = mid + yx * (lv.x * rad[0]) + xx * (lv.y * rad[1]) + zx * (lv.z * rad[2])


def add_evangelist_terminal(bm_white, bm_mosaic, bm_gold, cx: float, cy: float, z0: float, face: float, kind: str) -> None:
    """22.5 m Evangelist pinnacle from z0 (=112.5 m): hexagonal-shield shaft, trencadís icosahedron with
    gold bulges, 9 m white elliptical hyperboloid with two great wings, open book and the 4.5 m figure."""
    f = Vector((math.cos(face), math.sin(face), 0.0))
    s = Vector((-math.sin(face), math.cos(face), 0.0))
    C = Vector((cx, cy, 0.0))

    # 1. Shaft with hexagonal shields (z0 .. z0+4.5): six slim mosaic posts (open viewpoint between
    #    them at 114 m) carrying six hexagonal 'Amen / Alleluia' shields on top.
    zs0, zs1 = z0 + 1.0, z0 + 3.6
    for k in range(6):
        a = face + math.pi / 6 + 2.0 * math.pi * k / 6
        d = Vector((math.cos(a), math.sin(a), 0.0))
        add_cylinder(bm_mosaic, C + d * 2.6 + Vector((0, 0, zs0)), C + d * 2.5 + Vector((0, 0, zs1)), 0.2, 0.2, segments=6, cap=False)
    # hexagonal drum above the open viewpoint, its six faces carrying the hexagonal shields
    add_lathe(bm_mosaic, cx, cy, [(zs1, 2.95), (zs1 + 2.2, 2.55), (zs1 + 2.6, 1.9)], segments=6, cap_bottom=True, cap_top=True, phase=face + math.pi / 6)
    for k in range(6):
        a2 = face + 2.0 * math.pi * k / 6
        d2 = Vector((math.cos(a2), math.sin(a2), 0.0))
        pc = C + d2 * 2.45 + Vector((0, 0, zs1 + 1.1))
        add_cylinder(bm_gold, pc - d2 * 0.05, pc + d2 * 0.12, 0.85, 0.85, segments=6, cap=True)

    # 2. Trencadís icosahedron with gold spherical bulges (spotlights for the Jesus cross)
    zi = z0 + 7.0
    centers = add_icosahedron(bm_mosaic, C + Vector((0, 0, zi)), 2.35)
    for p in centers:
        d = (p - (C + Vector((0, 0, zi)))).normalized()
        add_ellipsoid(bm_gold, p + d * 0.12, (0.42, 0.42, 0.42), subdivisions=1)

    # 3. 9 m white elliptical hyperboloid (ruled surface), wider across the wings
    zh0, zh1 = z0 + 9.0, z0 + 18.0
    zw, a_r, c_r = zh0 + 4.3, 1.0, 2.45  # waist slightly below mid-height: r 2.1 m at both ends
    prof = []
    for i in range(10):
        z = zh0 + (zh1 - zh0) * i / 9
        prof.append((z, a_r * math.sqrt(1.0 + ((z - zw) / c_r) ** 2)))
    ph = face
    rings = add_lathe(bm_white, cx, cy, prof, segments=14, cap_top=True, phase=ph, squash=(1.0, 1.0))
    # squash along f (thin front-back, wide across s)
    for ring in rings:
        for v in ring:
            lv = v.co - Vector((cx, cy, v.co.z))
            v.co = Vector((cx, cy, v.co.z)) + f * (lv.dot(f) * 0.72) + s * (lv.dot(s) * 1.12)

    # 4. Two great wings rising from the hyperboloid's flanks up to ~135.5 m
    for side in (-1, 1):
        root = C + Vector((0, 0, zh1 - 3.4)) + s * side * 1.25 - f * 0.35
        _wing(bm_white, root, f, s, side, span=4.0, height=7.6)

    # 5. Open book (Gospel) on the hyperboloid, abbreviation in red trencadís, then the 4.5 m figure
    zb = zh1 + 0.05
    for side in (-1, 1):
        pc = C + Vector((0, 0, zb + 0.32)) + s * side * 0.62 + f * 0.25
        verts = add_ellipsoid(bm_white, pc, (0.95, 0.62, 0.14), subdivisions=1, rot_z=face, roll=side * 0.32)
    add_ellipsoid(bm_mosaic, C + Vector((0, 0, zb + 0.55)) + f * 0.98, (0.06, 0.55, 0.3), subdivisions=1, rot_z=face)
    _add_tetramorph_figure(bm_white, C + Vector((0, 0, zb + 0.4)), f, s, face, kind)


def _add_tetramorph_figure(bm, c: Vector, f: Vector, s: Vector, face: float, kind: str) -> None:
    up = Vector((0, 0, 1))
    if kind == "angel":
        # Matthew: upright human figure (man / angel), robe, head, arms crossed over the chest
        add_lathe(bm, c.x, c.y, [(c.z, 0.95), (c.z + 1.1, 0.78), (c.z + 2.2, 0.62), (c.z + 2.9, 0.66), (c.z + 3.25, 0.4)], segments=12, cap_bottom=True, cap_top=True)
        add_ellipsoid(bm, c + up * 3.25, (0.72, 0.42, 0.28), subdivisions=1, rot_z=face + math.pi / 2)  # shoulders
        add_ellipsoid(bm, c + up * 3.72 + f * 0.05, (0.34, 0.31, 0.42), subdivisions=2, rot_z=face)  # head
        for side in (-1, 1):
            add_cylinder(bm, c + up * 3.15 + s * side * 0.62, c + up * 2.35 + s * side * 0.3 + f * 0.55, 0.17, 0.14, segments=6)
            add_cylinder(bm, c + up * 2.35 + s * side * 0.3 + f * 0.55, c + up * 2.55 - s * side * 0.25 + f * 0.62, 0.14, 0.12, segments=6)
    elif kind == "lion":
        # Mark: seated lion facing outward, great round mane, muzzle, forelegs, tail with tuft
        add_ellipsoid(bm, c + up * 0.85 - f * 0.45, (1.15, 0.82, 0.78), subdivisions=2, rot_z=face, tilt=-0.35)  # haunches
        add_ellipsoid(bm, c + up * 1.75 + f * 0.25, (0.72, 0.7, 1.05), subdivisions=2, rot_z=face, tilt=0.35)  # chest
        add_ellipsoid(bm, c + up * 2.75 + f * 0.55, (0.85, 1.1, 1.0), subdivisions=2, rot_z=face)  # mane
        add_ellipsoid(bm, c + up * 2.7 + f * 1.25, (0.5, 0.5, 0.5), subdivisions=2, rot_z=face)  # face
        add_ellipsoid(bm, c + up * 2.5 + f * 1.68, (0.32, 0.36, 0.26), subdivisions=1, rot_z=face)  # muzzle
        for side in (-1, 1):
            add_cylinder(bm, c + up * 1.5 + f * 0.75 + s * side * 0.38, c + up * 0.12 + f * 1.05 + s * side * 0.4, 0.24, 0.2, segments=6)
            add_ellipsoid(bm, c + up * 0.15 + f * 1.25 + s * side * 0.4, (0.32, 0.2, 0.14), subdivisions=1, rot_z=face)
        tail = [c + up * 0.5 - f * 1.45, c + up * 0.4 - f * 1.95 + s * 0.4, c + up * 1.0 - f * 2.1 + s * 0.6]
        for p0, p1 in zip(tail[:-1], tail[1:]):
            add_cylinder(bm, p0, p1, 0.12, 0.1, segments=5)
        add_ellipsoid(bm, tail[-1] + up * 0.15, (0.22, 0.22, 0.3), subdivisions=1)
    elif kind == "ox":
        # Luke: recumbent ox, deep body with withers hump, broad head and wide curving horns
        add_ellipsoid(bm, c + up * 0.85, (1.6, 0.92, 0.8), subdivisions=2, rot_z=face)
        add_ellipsoid(bm, c + up * 1.3 + f * 0.55, (0.7, 0.8, 0.62), subdivisions=1, rot_z=face)  # hump / withers
        head = c + up * 1.55 + f * 1.75
        add_ellipsoid(bm, head, (0.62, 0.52, 0.55), subdivisions=2, rot_z=face, tilt=0.4)
        add_ellipsoid(bm, head + f * 0.48 - up * 0.32, (0.36, 0.42, 0.3), subdivisions=1, rot_z=face)  # muzzle
        for side in (-1, 1):
            h0 = head + up * 0.35 + s * side * 0.35
            h1 = h0 + s * side * 0.75 + up * 0.15
            h2 = h1 + s * side * 0.35 + up * 0.6 + f * 0.15
            h3 = h2 - s * side * 0.12 + up * 0.45 + f * 0.1
            add_cylinder(bm, h0, h1, 0.2, 0.16, segments=6)
            add_cylinder(bm, h1, h2, 0.16, 0.11, segments=6)
            add_cylinder(bm, h2, h3, 0.11, 0.03, segments=6)
            add_ellipsoid(bm, head + up * 0.05 + s * side * 0.62 - f * 0.1, (0.15, 0.32, 0.1), subdivisions=1, rot_z=face)  # ears
            add_cylinder(bm, c + up * 0.4 + f * 1.05 + s * side * 0.42, c + up * 0.12 + f * 1.55 + s * side * 0.42, 0.22, 0.2, segments=6)  # folded forelegs
    else:
        # John: upright eagle, folded wings, head in profile with hooked beak, fanned tail, talons
        add_ellipsoid(bm, c + up * 1.45, (0.78, 0.82, 1.45), subdivisions=2, rot_z=face, tilt=0.12)
        for side in (-1, 1):
            add_ellipsoid(bm, c + up * 1.6 + s * side * 0.62 - f * 0.18, (0.62, 0.25, 1.35), subdivisions=1, rot_z=face, roll=side * 0.12)
            add_cylinder(bm, c + up * 0.35 + s * side * 0.3 + f * 0.2, c + up * 0.02 + s * side * 0.32 + f * 0.55, 0.14, 0.1, segments=5)
        head = c + up * 3.05 + f * 0.3
        add_ellipsoid(bm, head, (0.48, 0.38, 0.4), subdivisions=2, rot_z=face)
        add_cylinder(bm, head + f * 0.38 + up * 0.05, head + f * 0.95 - up * 0.15, 0.2, 0.06, segments=6)
        add_cylinder(bm, head + f * 0.95 - up * 0.15, head + f * 0.88 - up * 0.42, 0.07, 0.02, segments=5)
        add_ellipsoid(bm, c + up * 0.25 - f * 0.95, (0.65, 0.55, 0.12), subdivisions=1, rot_z=face, tilt=0.35)  # tail fan


# ───────────────────────────── Mary terminal ─────────────────────────────

def add_mary_terminal(bm_stone, bm_lantern, bm_iron, bm_star, cx: float, cy: float, z_crown0: float, crown_scale: float = 1.0) -> float:
    """6 m stone crown with twelve wrought-iron stars, 18 m hyperboloid lantern on six legs ending in three
    arms, twelve-pointed star (7.5 m) whose top is at 138 m. Returns the star centre height.
    crown_scale widens the stone crown (and the iron-star ring / lantern-leg feet) radially so it sits
    flush on the shaft top (profile designed for a 4.55 m shaft radius); lantern and star keep their size."""
    z_c1 = z_crown0 + 6.0
    s = crown_scale
    # Stone crown: flaring ring wall (inner radius > the 118 m deck)
    add_lathe(bm_stone, cx, cy, [(z_crown0, 4.55 * s), (z_crown0 + 2.0, 4.7 * s), (z_crown0 + 4.6, 4.95 * s), (z_c1, 5.15 * s),
                                 (z_c1 + 0.35, 4.9 * s), (z_c1 + 0.35, 4.3 * s), (z_crown0, 4.25 * s)], segments=24)
    # Twelve wrought-iron stars on the crown rim
    for k in range(12):
        a = 2.0 * math.pi * (k + 0.5) / 12
        p = Vector((cx + 5.05 * s * math.cos(a), cy + 5.05 * s * math.sin(a), z_c1 + 1.25))
        d = Vector((math.cos(a), math.sin(a), 0.0))
        t = Vector((-math.sin(a), math.cos(a), 0.0))
        add_cylinder(bm_iron, p - Vector((0, 0, 1.15)), p, 0.06, 0.06, segments=4, cap=False)
        for j in range(3):  # six-rayed iron star = 3 crossing bars in the tangent plane
            aa = math.pi * j / 3
            v = t * math.cos(aa) + Vector((0, 0, 1)) * math.sin(aa)
            add_cylinder(bm_iron, p - v * 0.55, p + v * 0.55, 0.06, 0.06, segments=4, cap=False)

    # Lantern: six legs from the crown top converging, then a one-sheet hyperboloid (ruled surface)
    zl0 = z_c1 + 0.35
    z_shell0 = zl0 + 5.4
    z_top = zl0 + 18.0 - 0.35
    zw, a_r = z_shell0 + 6.8, 1.35

    def r_h(z: float) -> float:
        k = math.sqrt((3.95 / a_r) ** 2 - 1.0) / (zw - z_shell0)
        return a_r * math.sqrt(1.0 + (k * (z - zw)) ** 2)

    for k in range(6):
        a = 2.0 * math.pi * k / 6
        p0 = Vector((cx + 4.45 * s * math.cos(a), cy + 4.45 * s * math.sin(a), zl0))
        p1 = Vector((cx + r_h(z_shell0) * math.cos(a), cy + r_h(z_shell0) * math.sin(a), z_shell0 + 0.5))
        add_cylinder(bm_lantern, p0, p1, 0.42, 0.34, segments=6)
    # Lattice shell with triangular / rhomboid openings (diamond pattern on a ruled hyperboloid)
    rows = 12
    zs = [z_shell0 + (z_top - z_shell0) * i / rows for i in range(rows + 1)]

    def kind(row, k, z_lo, z_hi, ang):
        # staggered rhomboid openings, closed bottom and top rings
        return "open" if 0 < row < rows - 1 and (k + row) % 2 == 0 and row % 3 != 0 else "solid"

    add_tower_shell(bm_lantern, cx, cy, zs, r_h, 16, kind, thickness=0.3)
    # Three arms holding the star
    z_star = 138.0 - 3.75
    for k in range(3):
        a = 2.0 * math.pi * k / 3 + math.pi / 6
        p0 = Vector((cx + r_h(z_top) * 0.9 * math.cos(a), cy + r_h(z_top) * 0.9 * math.sin(a), z_top))
        p1 = Vector((cx + 1.1 * math.cos(a), cy + 1.1 * math.sin(a), z_star - 1.6))
        add_cylinder(bm_lantern, p0, p1, 0.36, 0.26, segments=6)
    return z_star


def add_star_12_points(bm_star, center: Vector, radius: float = 3.75) -> None:
    """Twelve-pointed glass star (7.5 m diameter): pyramidal rays on the 12 icosahedron vertex directions."""
    ret = bmesh.ops.create_icosphere(bm_star, subdivisions=2, radius=radius * 0.42)
    for v in ret["verts"]:
        v.co += center
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    dirs = [
        Vector((0, 1, phi)), Vector((0, -1, phi)), Vector((0, 1, -phi)), Vector((0, -1, -phi)),
        Vector((1, phi, 0)), Vector((-1, phi, 0)), Vector((1, -phi, 0)), Vector((-1, -phi, 0)),
        Vector((phi, 0, 1)), Vector((-phi, 0, 1)), Vector((phi, 0, -1)), Vector((-phi, 0, -1)),
    ]
    for d in dirs:
        dn = d.normalized()
        add_cylinder(bm_star, center + dn * (radius * 0.3), center + dn * radius, radius * 0.27, 0.03, segments=5, cap=True)


# ───────────────────────────── Jesus cross ─────────────────────────────

def _hull(bm, pts: list[Vector]) -> None:
    verts = [bm.verts.new(p) for p in pts]
    res = bmesh.ops.convex_hull(bm, input=verts)
    junk = [g for g in res.get("geom_interior", []) + res.get("geom_unused", []) if isinstance(g, bmesh.types.BMVert)]
    if junk:
        bmesh.ops.delete(bm, geom=junk, context="VERTS")


def _square_prism(bm, p0: Vector, p1: Vector, h0: float, h1: float, chamfer: float = 0.0) -> None:
    """Square-section prism from p0 to p1 (half-widths h0 -> h1), axis-aligned to world X/Y/Z."""
    ax = (p1 - p0).normalized()
    u = Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((1, 0, 0))
    v = ax.cross(u).normalized()
    u = v.cross(ax).normalized()
    pts = []
    for p, h in ((p0, h0), (p1, h1)):
        for su in (-1, 1):
            for sv in (-1, 1):
                if chamfer > 0:
                    pts.append(p + u * su * h + v * sv * (h - chamfer))
                    pts.append(p + u * su * (h - chamfer) + v * sv * h)
                else:
                    pts.append(p + u * su * h + v * sv * h)
    _hull(bm, pts)


def add_jesus_cross(bm_cross, bm_gold, z_base: float, z_top: float) -> None:
    """Four-armed three-dimensional cross, 16.85 m tall (z_base..z_top) and 13.5 m wide:
    lower arm 7.25 m, truncated-cube core 4.7 m, horizontal arms 4.4 m long x 4.5 x 4.5 m,
    upper arm 4.9 m tall x 4.5 x 4.5 m (piece sizes from the Junta Constructora)."""
    z_core0 = z_base + 7.25
    z_core1 = z_core0 + 4.7
    zc = 0.5 * (z_core0 + z_core1)
    hw = 2.25
    ch = 0.45
    # Lower arm, slightly widening into the terminal
    _square_prism(bm_cross, Vector((0, 0, z_base)), Vector((0, 0, z_core0 + 0.05)), hw + 0.3, hw, chamfer=ch)
    # Core: truncated cube (all faces octagons of 4.7 m)
    h = 2.35
    xi = h * (math.sqrt(2.0) - 1.0)
    pts = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                pts.append(Vector((sx * xi, sy * h, zc + sz * h)))
                pts.append(Vector((sx * h, sy * xi, zc + sz * h)))
                pts.append(Vector((sx * h, sy * h, zc + sz * xi)))
    _hull(bm_cross, pts)
    # Four horizontal arms (N, S, E, W) and the upper arm
    for d in (Vector((1, 0, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0)), Vector((0, -1, 0))):
        _square_prism(bm_cross, Vector((0, 0, zc)) + d * 2.3, Vector((0, 0, zc)) + d * 6.75, hw, hw * 0.96, chamfer=ch)
    _square_prism(bm_cross, Vector((0, 0, z_core1 - 0.05)), Vector((0, 0, z_top)), hw, hw * 0.96, chamfer=ch)
