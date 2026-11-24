"""Geometry helpers for build_facades.py (architecture accuracy pass).

Ruled surfaces (one-sheet hyperboloids), parabolic/catenary archivolts, Gaudí double-twist shafts,
palm capitals, and the small sculptural vocabulary of the three façades. Kept separate from the
shared common.py so the façade module can evolve without touching shared code.
"""

from __future__ import annotations

import math

import bmesh
from mathutils import Vector

from common import add_cylinder, add_ellipsoid, add_lathe, add_swept_tube


# ───────────────────────── solids & plan helpers (true-layout pass) ─────────────────────────

def merge_bmesh_into(dst, src) -> None:
    """Append every face of `src` into `dst` (geometry only; both get finalised as one mesh)."""
    vmap = {}
    for v in src.verts:
        vmap[v] = dst.verts.new(v.co)
    for f in src.faces:
        dst.faces.new([vmap[v] for v in f.verts])
    src.free()


def add_hexa(bm, corners: list) -> None:
    """Closed six-sided solid from 8 corners: bottom quad c0..c3 then top quad c4..c7 (same order).
    Used for warped stair treads, sloped cheek walls and piers whose top/bottom follow ground_z."""
    vs = [bm.verts.new(Vector(c)) for c in corners]
    b, t = vs[:4], vs[4:]
    bm.faces.new(list(reversed(b)))
    bm.faces.new(t)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((b[i], b[j], t[j], t[i]))


def interval_complement(lo: float, hi: float, holes: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Solid sub-intervals of [lo, hi] once the `holes` (openings) are removed."""
    out, cur = [], lo
    for a, b in sorted(holes):
        a, b = max(a, lo), min(b, hi)
        if b <= cur:
            continue
        if a > cur + 1e-3:
            out.append((cur, a))
        cur = max(cur, b)
    if hi > cur + 1e-3:
        out.append((cur, hi))
    return out


def add_section_annulus(bm, cx: float, cy: float, z0: float, z1: float, r_in: float, r_out: float, section,
                        a_from: float = 0.0, a_to: float = 2.0 * math.pi, segments: int = 16) -> None:
    """Thick ring (or ring sector a_from..a_to, radians CCW from +X) between a round inner skin r_in and
    an outer skin r_out * section(angle) — the tower base drum below the apostle shell, with the shell's
    own square / elliptical section so it continues it seamlessly. A sector gets flat end caps."""
    full = (a_to - a_from) >= 2.0 * math.pi - 1e-6
    n = segments if full else max(2, int(math.ceil(segments * (a_to - a_from) / (2.0 * math.pi))))
    cnt = n if full else n + 1
    rings = {}
    for key, z in (("b", z0), ("t", z1)):
        oo, ii = [], []
        for k in range(cnt):
            a = a_from + (a_to - a_from) * k / n
            ro = r_out * (section(a) if section is not None else 1.0)
            oo.append(bm.verts.new((cx + ro * math.cos(a), cy + ro * math.sin(a), z)))
            ii.append(bm.verts.new((cx + r_in * math.cos(a), cy + r_in * math.sin(a), z)))
        rings[key] = (oo, ii)
    (ob, ib), (ot, it) = rings["b"], rings["t"]
    rng = range(n)
    for k in rng:
        j = (k + 1) % cnt
        bm.faces.new((ob[k], ob[j], ot[j], ot[k]))      # outer skin
        bm.faces.new((ib[j], ib[k], it[k], it[j]))      # inner skin (faces the hollow)
        bm.faces.new((ot[k], ot[j], it[j], it[k]))      # top
        bm.faces.new((ob[j], ob[k], ib[k], ib[j]))      # bottom
    if not full:
        bm.faces.new((ob[0], ot[0], it[0], ib[0]))
        bm.faces.new((ob[-1], ib[-1], it[-1], ot[-1]))


def add_section_drum(bm, cx: float, cy: float, z0: float, z1: float, r: float, section, segments: int = 16) -> None:
    """Solid capped drum with outer radius r * section(angle) (tower base mass below the stair band)."""
    bot, top = [], []
    for k in range(segments):
        a = 2.0 * math.pi * k / segments
        rr = r * (section(a) if section is not None else 1.0)
        bot.append(bm.verts.new((cx + rr * math.cos(a), cy + rr * math.sin(a), z0)))
        top.append(bm.verts.new((cx + rr * math.cos(a), cy + rr * math.sin(a), z1)))
    for k in range(segments):
        j = (k + 1) % segments
        bm.faces.new((bot[k], bot[j], top[j], top[k]))
    bm.faces.new(list(reversed(bot)))
    bm.faces.new(top)


# ───────────────────────── curves ─────────────────────────

def parabolic_arch_points(base_l: Vector, base_r: Vector, rise: float, n: int = 12, sharp: float = 1.0) -> list[Vector]:
    """Points along a parabolic (catenary-like) arch from base_l to base_r rising `rise` above the
    springing line. sharp > 1 pinches the crown (Gaudí's steep 'equilibrated' arches)."""
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 2.0 * t - 1.0
        h = rise * (1.0 - abs(u) ** (2.0 / sharp))
        p = base_l.lerp(base_r, t)
        pts.append(Vector((p.x, p.y, p.z + h)))
    return pts


def add_arch_tube(bm, base_l: Vector, base_r: Vector, rise: float, r_foot: float, r_crown: float, n: int = 12, segments: int = 7, sharp: float = 1.0, ridge=(0, 0.0)) -> None:
    pts = parabolic_arch_points(base_l, base_r, rise, n, sharp)
    radii = [r_crown + (r_foot - r_crown) * abs(2.0 * i / n - 1.0) ** 1.5 for i in range(n + 1)]
    add_swept_tube(bm, pts, radii, segments=segments, cap=True, ridge=ridge)


# ───────────────────────── ruled surfaces ─────────────────────────

def add_ruled_loft(bm, curve_a: list[Vector], curve_b: list[Vector]) -> None:
    """Ruled surface between two curves with matching parameterisation (straight generators
    joining a[i] to b[i]) — used for the splayed, cave-like jambs of the Nativity porches."""
    va = [bm.verts.new(p) for p in curve_a]
    vb = [bm.verts.new(p) for p in curve_b]
    for i in range(len(va) - 1):
        bm.faces.new((va[i], va[i + 1], vb[i + 1], vb[i]))


def add_hyperboloid(bm, cx: float, cy: float, z0: float, z1: float, r_end0: float, r_end1: float, twist: float,
                    segments: int = 16, rows: int = 6, cap_top: bool = False, cap_bottom: bool = False):
    """True one-sheet hyperboloid of revolution built from its straight rulings: every generator joins
    bottom-ring point k to top-ring point k rotated by `twist`; intermediate rings are exact linear
    interpolations along those straight lines, so the waist emerges from the ruling, as in Gaudí's
    lanterns and windows. Returns the list of rings."""
    rings = []
    for j in range(rows + 1):
        t = j / rows
        ring = []
        for k in range(segments):
            a = 2.0 * math.pi * k / segments
            p0 = Vector((cx + r_end0 * math.cos(a), cy + r_end0 * math.sin(a), z0))
            p1 = Vector((cx + r_end1 * math.cos(a + twist), cy + r_end1 * math.sin(a + twist), z1))
            ring.append(bm.verts.new(p0.lerp(p1, t)))
        rings.append(ring)
    for a_r, b_r in zip(rings[:-1], rings[1:]):
        for k in range(segments):
            nk = (k + 1) % segments
            bm.faces.new((a_r[k], a_r[nk], b_r[nk], b_r[k]))
    if cap_top:
        bm.faces.new(rings[-1])
    if cap_bottom:
        bm.faces.new(list(reversed(rings[0])))
    return rings


def add_hyperboloid_lantern(bm_stone, bm_gold, cx: float, cy: float, z0: float, height: float, radius: float, segments: int = 12) -> None:
    """Glory-façade lantern: two stacked one-sheet hyperboloids (waisted body + pointed cap) with
    a slim gilt finial. Straight rulings only (twist 0.9 rad gives a waist of ~0.9*radius)."""
    zm = z0 + height * 0.62
    # Body: strongly waisted (twist 1.9 rad -> waist ≈ 0.58 r), flaring into a crown ring
    add_hyperboloid(bm_stone, cx, cy, z0, zm, radius, radius * 1.1, 1.9, segments=segments, rows=6, cap_bottom=True)
    add_hyperboloid(bm_stone, cx, cy, zm, zm + height * 0.08, radius * 1.1, radius * 0.8, 0.0, segments=segments, rows=1)
    # Spire: second hyperboloid narrowing to a neck (concave, not a straight cone)
    add_hyperboloid(bm_stone, cx, cy, zm + height * 0.08, z0 + height * 0.94, radius * 0.8, radius * 0.12, 1.2, segments=segments, rows=4, cap_top=True)
    if bm_gold is not None:
        add_cylinder(bm_gold, Vector((cx, cy, z0 + height * 0.92)), Vector((cx, cy, z0 + height * 1.08)), radius * 0.16, 0.03, segments=6)


def add_double_twist_shaft(bm, cx: float, cy: float, z0: float, z1: float, r0: float, r1: float, sides: int = 8,
                           rings: int = 10, segs: int = 24, flute: float = 0.12) -> None:
    """Gaudí double-twist column: the union of a star polygon twisted clockwise and the same polygon
    twisted anti-clockwise; the section multiplies its sides with height and tends to a circle."""
    tw = math.pi / sides
    prev = None
    for i in range(rings + 1):
        t = i / rings
        z = z0 + (z1 - z0) * t
        r = r0 + (r1 - r0) * t
        amp = flute * (1.0 - 0.8 * t ** 1.5)
        ring = []
        for k in range(segs):
            a = 2.0 * math.pi * k / segs
            def star(th):
                sector = 2.0 * math.pi / sides
                loc = ((th % sector) / sector) - 0.5
                return 1.0 - amp * (1.0 - 4.0 * loc * loc)
            rr = r * max(star(a + tw * t), star(a - tw * t))
            ring.append(bm.verts.new((cx + rr * math.cos(a), cy + rr * math.sin(a), z)))
        if prev is not None:
            for k in range(segs):
                nk = (k + 1) % segs
                bm.faces.new((prev[k], prev[nk], ring[nk], ring[k]))
        prev = ring


# ───────────────────────── Nativity vocabulary ─────────────────────────

def add_palm_trunk(bm, cx: float, cy: float, z0: float, z1: float, r0: float, r1: float, segments: int = 10) -> None:
    """Palm trunk: slight taper with the annular leaf-scar rings of a date palm (one lathe)."""
    prof = []
    n = 14
    for i in range(n + 1):
        t = i / n
        r = r0 + (r1 - r0) * t
        prof.append((z0 + (z1 - z0) * t, r * (1.0 if i % 2 == 0 else 1.07)))
    add_lathe(bm, cx, cy, prof, segments=segments, cap_bottom=True, cap_top=True)


def add_palm_capital(bm, top: Vector, length: float, fronds: int = 9, seed: int = 0) -> None:
    """Crown of drooping palm fronds (Nativity column capitals); each frond is a flattened swept blade."""
    for i in range(fronds):
        a = 2.0 * math.pi * (i + 0.37 * seed) / fronds
        d = Vector((math.cos(a), math.sin(a), 0.0))
        pts, radii = [], []
        for j in range(6):
            t = j / 5
            # Arc up then droop (parabolic frond)
            p = top + d * (length * t) + Vector((0, 0, length * (0.55 * t - 0.95 * t * t)))
            pts.append(p)
            radii.append(0.16 * (1.0 - 0.75 * t) + 0.02)
        add_swept_tube(bm, pts, radii, segments=4, cap=True)


def add_trumpet_angel(bm, base: Vector, h: float, face: float) -> None:
    """Standing angel blowing a long trumpet (crowning the Nativity palm columns)."""
    f = Vector((math.cos(face), math.sin(face), 0.0))
    s = Vector((-math.sin(face), math.cos(face), 0.0))
    add_lathe(bm, base.x, base.y, [(base.z, h * 0.18), (base.z + h * 0.4, h * 0.15), (base.z + h * 0.72, h * 0.13), (base.z + h * 0.82, h * 0.06)],
              segments=7, cap_bottom=True, cap_top=True)
    add_ellipsoid(bm, base + Vector((0, 0, h * 0.89)), (h * 0.075, h * 0.075, h * 0.09), subdivisions=1)
    for side in (-1, 1):
        add_ellipsoid(bm, base + Vector((0, 0, h * 0.68)) - f * h * 0.14 + s * side * h * 0.2, (h * 0.05, h * 0.16, h * 0.36), subdivisions=1, rot_z=face, roll=-side * 0.4)
    mouth = base + Vector((0, 0, h * 0.87)) + f * h * 0.08
    add_cylinder(bm, mouth, mouth + f * h * 0.75 + Vector((0, 0, h * 0.42)), h * 0.025, h * 0.11, segments=6)


def add_pelican(bm, base: Vector, h: float, face: float) -> None:
    """Pelican feeding its young with its own blood (Eucharistic symbol below the Nativity cypress)."""
    f = Vector((math.cos(face), math.sin(face), 0.0))
    add_ellipsoid(bm, base + Vector((0, 0, h * 0.35)), (h * 0.42, h * 0.3, h * 0.3), subdivisions=1, rot_z=face)
    neck0 = base + Vector((0, 0, h * 0.5)) + f * h * 0.25
    head = neck0 + Vector((0, 0, h * 0.42)) + f * h * 0.05
    add_cylinder(bm, neck0, head, h * 0.09, h * 0.07, segments=6)
    add_ellipsoid(bm, head, (h * 0.1, h * 0.09, h * 0.1), subdivisions=1)
    # Bill bent down onto the breast
    add_cylinder(bm, head, base + Vector((0, 0, h * 0.55)) + f * h * 0.5, h * 0.05, h * 0.02, segments=5)
    for side in (-1, 1):  # spread wings
        add_ellipsoid(bm, base + Vector((0, 0, h * 0.55)) + Vector((-math.sin(face), math.cos(face), 0)) * side * h * 0.42,
                      (h * 0.1, h * 0.45, h * 0.18), subdivisions=1, rot_z=face, roll=side * 0.5)
    for k in (-1, 0, 1):  # chicks in the nest
        add_ellipsoid(bm, base + f * h * 0.45 + Vector((-math.sin(face), math.cos(face), 0)) * k * h * 0.2 + Vector((0, 0, h * 0.08)),
                      (h * 0.1, h * 0.1, h * 0.12), subdivisions=1)


def add_letter_strokes(bm, origin: Vector, u: Vector, glyphs: list[list[tuple[float, float, float, float]]], scale: float, gap: float, r: float) -> None:
    """Draw monogram letters as stone/gilt strokes. Each glyph is a list of (u0, v0, u1, v1) strokes
    in a unit box; letters advance along u, v is vertical."""
    for gi, strokes in enumerate(glyphs):
        o = origin + u * (gi * (scale + gap))
        for u0, v0, u1, v1 in strokes:
            add_cylinder(bm, o + u * (u0 * scale) + Vector((0, 0, v0 * scale)), o + u * (u1 * scale) + Vector((0, 0, v1 * scale)), r, r, segments=5)


GLYPH_J = [(0.7, 1.0, 0.7, 0.2), (0.7, 0.2, 0.4, 0.0), (0.4, 0.0, 0.1, 0.25)]
GLYPH_H = [(0.1, 0.0, 0.1, 1.0), (0.8, 0.0, 0.8, 1.0), (0.1, 0.5, 0.8, 0.5)]
GLYPH_S = [(0.85, 0.95, 0.15, 0.75), (0.15, 0.75, 0.85, 0.3), (0.85, 0.3, 0.15, 0.05)]


def add_rock_peak(bm, base: Vector, h: float, w: float, seed: int = 0) -> None:
    """Cluster of rounded rock needles (the Montserrat crags crowning the Portal of Hope)."""
    n = 7
    for i in range(n):
        a = 2.0 * math.pi * i / n + seed
        rr = w * (0.18 + 0.22 * ((i * 37 + seed * 11) % 5) / 4.0)
        hh = h * (0.45 + 0.55 * ((i * 53 + 7) % 6) / 5.0)
        p = base + Vector((0.0, rr * math.cos(a), 0.0)) + Vector((rr * 0.4 * math.sin(a), 0, 0))
        add_lathe(bm, p.x, p.y, [(p.z, w * 0.2), (p.z + hh * 0.5, w * 0.17), (p.z + hh * 0.85, w * 0.12), (p.z + hh, w * 0.04)], segments=6, cap_top=True)
    add_lathe(bm, base.x, base.y, [(base.z, w * 0.3), (base.z + h * 0.6, w * 0.22), (base.z + h * 1.15, w * 0.05)], segments=7, cap_top=True)


def add_triangular_lantern(bm, base: Vector, h: float, w: float) -> None:
    """Three-sided lantern crowning the Portal of Faith (the Holy Trinity)."""
    add_lathe(bm, base.x, base.y, [(base.z, w * 0.5), (base.z + h * 0.55, w * 0.55), (base.z + h * 0.7, w * 0.3), (base.z + h, w * 0.04)],
              segments=3, cap_bottom=True, cap_top=True, phase=math.pi)


# ───────────────────────── Passion vocabulary ─────────────────────────

def add_bone_column_v2(bm, p0: Vector, p_mid: Vector, p1: Vector, scale: float, segments: int = 14, n: int = 20) -> None:
    """Inclined Passion column modelled on a long bone / sequoia trunk: splayed, swollen foot that
    tapers quickly, a long slightly pinched diaphysis with one 'knee' swelling, and an expanded head
    (epiphysis) where it meets the porch roof. Quadratic Bezier axis."""
    prof = ((0.0, 1.75), (0.05, 1.5), (0.14, 1.08), (0.32, 0.78), (0.47, 0.92), (0.54, 1.12), (0.62, 0.9), (0.8, 0.74), (0.92, 1.1), (1.0, 1.65))
    pts, radii = [], []
    for i in range(n + 1):
        t = i / n
        p = (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p_mid + t * t * p1
        r = prof[-1][1]
        for (ta, ra), (tb, rb) in zip(prof[:-1], prof[1:]):
            if ta <= t <= tb:
                u = (t - ta) / (tb - ta)
                u = u * u * (3 - 2 * u)
                r = ra + (rb - ra) * u
                break
        pts.append(p)
        radii.append(r * scale)
    add_swept_tube(bm, pts, radii, segments=segments, cap=True, ridge=(3, 0.08))


def add_root_flare(bm, foot: Vector, r: float, roots: int = 5, seed: int = 0) -> None:
    """Buttress roots splaying from the foot of a Passion trunk-column onto the porch floor."""
    for i in range(roots):
        # Splay mainly fore and aft (±X), so the roots do not close the gaps between neighbouring columns
        a = (0.0 if i < roots // 2 else math.pi) + (((i % (roots // 2)) / max(1, roots // 2 - 1)) - 0.5) * 1.3 + 0.05 * seed
        d = Vector((math.cos(a), math.sin(a), 0.0))
        add_swept_tube(bm, [foot + Vector((0, 0, r * 1.2)), foot + d * r * 0.9 + Vector((0, 0, r * 0.35)), foot + d * r * 1.6 + Vector((0, 0, 0.02))],
                       [r * 0.42, r * 0.3, r * 0.12], segments=5, cap=True)


# ───────────────────────── Glory vocabulary ─────────────────────────

def add_cloud_mass(bm, center: Vector, w: float, h: float, d: float, lobes: int = 9, seed: int = 0) -> None:
    """Billowing cloud: a run of overlapping squashed spheres (the Glory façade's Creed clouds)."""
    for i in range(lobes):
        t = (i + 0.5) / lobes
        n = math.sin(i * 12.9898 + seed * 78.233) * 43758.5453
        n -= math.floor(n)
        x = center.x + (t - 0.5) * w
        rz = h * (0.35 + 0.25 * n) * (0.75 + 0.25 * math.sin(math.pi * t))
        add_ellipsoid(bm, Vector((x, center.y + (n - 0.5) * d * 0.4, center.z + (n - 0.5) * h * 0.3)), (w / lobes * 0.9, d * 0.5, rz), subdivisions=1)


def add_fruit_basket(bm_stone, bm_mosaic, bm_gold, px: float, py: float, z: float, s: float = 1.0) -> None:
    """Gaudí's trencadís fruit-basket pinnacle on the nave gables: chalice stem, woven basket,
    a heap of glazed fruit and a gilt cross-shaped finial."""
    add_lathe(bm_stone, px, py, [(z, 0.55 * s), (z + 0.6 * s, 0.4 * s), (z + 1.2 * s, 0.62 * s), (z + 1.5 * s, 0.9 * s)], segments=8, cap_bottom=True, cap_top=True)
    add_lathe(bm_mosaic, px, py, [(z + 1.45 * s, 0.85 * s), (z + 2.6 * s, 1.15 * s), (z + 2.9 * s, 1.0 * s)], segments=10, cap_top=True)
    for fi in range(7):
        fa = 2.0 * math.pi * fi / 7.0
        r_f = (0.7 if fi % 2 == 0 else 0.5) * s
        add_ellipsoid(bm_mosaic, Vector((px + r_f * math.cos(fa), py + r_f * math.sin(fa), z + (3.15 if fi % 2 == 0 else 3.55) * s)), (0.4 * s, 0.4 * s, 0.4 * s), subdivisions=1)
    add_ellipsoid(bm_mosaic, Vector((px, py, z + 3.95 * s)), (0.5 * s, 0.5 * s, 0.5 * s), subdivisions=1)
    add_cylinder(bm_gold, Vector((px, py, z + 4.2 * s)), Vector((px, py, z + 5.8 * s)), 0.22 * s, 0.05 * s, segments=6)
