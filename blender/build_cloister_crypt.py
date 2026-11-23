"""Build the walkable Cloister (Kreuzgang), 2 domed Sacristies, and Subterranean Crypt with Gaudí's tomb."""

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
    Z_CRYPT,
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
from interior_lib import (
    add_clustered_pier,
    add_groin_vault_cell,
    add_paraboloid_dome,
    add_ruled_hyperboloid_shell,
    add_web_vault_sector,
    finalize_oriented,
)


def add_cloister_gallery_wing(
    bm_stone: bmesh.types.BMesh,
    bm_floor: bmesh.types.BMesh,
    x_center: float,
    y_start: float,
    y_end: float,
    width: float = 5.2,
    height: float = 9.0,
    bm_stairs: bmesh.types.BMesh | None = None,
) -> None:
    """Walkable vaulted cloister arcade running along the outer side of the nave."""
    length = abs(y_end - y_start)
    y_mid = 0.5 * (y_start + y_end)
    # Marble cloister floor slab (Z = Z_NAVE)
    add_box(bm_floor, (x_center, y_mid, Z_NAVE - 0.35), (width, length, 0.7))
    # Ribbed cloister roof slab
    add_box(bm_stone, (x_center, y_mid, Z_NAVE + height), (width + 0.8, length + 0.6, 0.9))

    # Outer arched colonnade bays (open arches letting sunlight filter into the cloister!)
    outer_x = x_center + (width * 0.48 if x_center > 0 else -width * 0.48)
    bays = max(4, int(length / 5.0))
    dy = (y_end - y_start) / bays
    sx_out = 1.0 if x_center > 0 else -1.0
    for i in range(bays + 1):
        py = y_start + i * dy
        # Outer gothic tracery pier
        add_box(bm_stone, (outer_x, py, Z_NAVE + height * 0.5), (0.85, 0.85, height))
        # Overhead vault transverse rib spanning width
        add_box(bm_stone, (x_center, py, Z_NAVE + height - 0.65), (width, 0.48, 0.75))
        if i < bays:
            mid_y = py + dy * 0.5
            # Low stone sill wall on exterior edge (leaving one middle bay open as exterior portal!)
            if i != bays // 2:
                add_box(bm_stone, (outer_x, mid_y, Z_NAVE + 0.65), (0.55, abs(dy) - 0.8, 1.3))
            elif bm_stairs is not None and length > 15.0:
                # 4 exterior stone steps linking Panot street sidewalk (Z=0) seamlessly into the open cloister portal (Z=1.2)!
                for st in range(4):
                    sz = (4 - st) * (Z_NAVE / 4.0)
                    st_x = outer_x + sx_out * (0.45 + st * 0.55)
                    add_box(bm_stairs, (st_x, mid_y, sz * 0.5), (0.58, abs(dy) - 0.9, sz))
            # Pointed arch head above bay
            add_box(bm_stone, (outer_x, mid_y, Z_NAVE + height - 1.1), (0.68, abs(dy) - 0.6, 1.5))


def add_sacristy_pavilion(
    bm_stone: bmesh.types.BMesh,
    bm_floor: bmesh.types.BMesh,
    bm_mosaic: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
    cx: float,
    cy: float,
) -> None:
    """Sacristy (west one built 2011-2016 to Gaudí's model, Wikipedia es): square ground floor,
    octagonal (chamfered) first floor, dome of TWELVE paraboloids, hyperboloid lantern; height 35 m,
    base 18 x 18 m. Here 14 x 14 m: the apse buttresses of the facades module stand at x ~19-20.5
    and the walkable podium of the runtime is a disc of r 8.5 m about (+-27.5, 32.5)."""
    half = 7.0             # half side of the square ground floor (real: 9 m)
    z0 = Z_NAVE
    z_sq = 12.0            # top of the square storey
    z_oct = 19.0           # top of the octagonal storey = springing of the dome
    z_dome = 31.0          # dome crown at the lantern ring
    z_lantern = 35.0       # lantern top = 35 m total height (source)
    wt = 0.8
    sgn = 1.0 if cx > 0 else -1.0

    # Interior floor (walk disc r 8.5 at runtime): octagon inscribed in the square
    add_cylinder(bm_floor, Vector((cx, cy, z0 - 0.7)), Vector((cx, cy, z0)), half, half, segments=8, cap=True)

    # Square storey: four walls, door to the south (toward the cloister connector), chamfered inner corners
    for side in range(4):
        ang = side * math.pi / 2.0
        nx, ny = math.cos(ang), math.sin(ang)
        wx, wy = cx + nx * (half - wt * 0.5), cy + ny * (half - wt * 0.5)
        rot = ang + math.pi / 2.0
        if ny < -0.5:  # south face: arched doorway 4 m wide, 6.5 m high
            for s in (-1, 1):
                seg = half - 2.0
                add_box(bm_stone, (cx + s * (2.0 + seg * 0.5), wy, z0 + 0.5 * (z_sq - z0)), (seg, wt, z_sq - z0))
            add_box(bm_stone, (cx, wy, 0.5 * (z0 + 6.5 + z_sq)), (4.2, wt, z_sq - z0 - 6.5))
        else:
            # closed face with three tall window openings (sill 2 m, head 8.4 m above the floor)
            tx, ty = math.cos(rot), math.sin(rot)
            w_lo, w_hi, w_w = z0 + 2.0, z0 + 8.4, 1.2
            add_box(bm_stone, (wx, wy, 0.5 * (z0 + w_lo)), (2 * half, wt, w_lo - z0), rot_euler=(0, 0, rot))
            add_box(bm_stone, (wx, wy, 0.5 * (w_hi + z_sq)), (2 * half, wt, z_sq - w_hi), rot_euler=(0, 0, rot))
            edges = [-half] + [e for s in (-2.6, 0.0, 2.6) for e in (s - 0.5 * w_w, s + 0.5 * w_w)] + [half]
            for e0, e1 in zip(edges[0::2], edges[1::2]):
                m = 0.5 * (e0 + e1)
                add_box(bm_stone, (wx + tx * m, wy + ty * m, 0.5 * (w_lo + w_hi)), (e1 - e0, wt, w_hi - w_lo), rot_euler=(0, 0, rot))
    # Solid chamfer masses in the inner corners (keep the walkable interior inside r 8.5)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        px, py = cx + (half - 1.25) * math.cos(a) * math.sqrt(2) * 0.84, cy + (half - 1.25) * math.sin(a) * math.sqrt(2) * 0.84
        add_box(bm_stone, (px, py, 0.5 * (z0 + z_sq)), (3.0, 3.0, z_sq - z0), rot_euler=(0, 0, a))
        # corner pinnacles on the square (the obelisks around the dome)
        ox, oy = cx + (half - 0.6) * math.copysign(1.0, math.cos(a)), cy + (half - 0.6) * math.copysign(1.0, math.sin(a))
        add_lathe(bm_stone, ox, oy, [(z_sq, 0.75), (z_sq + 2.0, 0.6), (z_sq + 5.5, 0.32), (z_sq + 7.5, 0.05)], segments=8, cap_bottom=True)
        add_lathe(bm_mosaic, ox, oy, [(z_sq + 7.3, 0.0), (z_sq + 7.6, 0.28), (z_sq + 8.1, 0.0)], segments=8)
    for side in range(4):  # cornice ring of the square storey (the interior stays open up into the dome)
        ang = side * math.pi / 2.0
        add_box(bm_stone, (cx + math.cos(ang) * (half - 0.4), cy + math.sin(ang) * (half - 0.4), z_sq + 0.3), (2 * half + 0.4, 1.6, 0.6), rot_euler=(0, 0, ang + math.pi / 2.0))

    # Octagonal storey (chamfered square), walls with oculi
    r_oct = half - 0.4
    oct_pts = [(cx + r_oct / math.cos(math.pi / 8) * math.cos(math.pi / 8 + k * math.pi / 4), cy + r_oct / math.cos(math.pi / 8) * math.sin(math.pi / 8 + k * math.pi / 4)) for k in range(8)]
    for k in range(8):
        (x0, y0), (x1, y1) = oct_pts[k], oct_pts[(k + 1) % 8]
        mx, my = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        seg = math.hypot(x1 - x0, y1 - y0) + 0.3
        rot = math.atan2(y1 - y0, x1 - x0)
        tx, ty = math.cos(rot), math.sin(rot)
        zb, w_lo, w_hi = z_sq + 0.6, z_sq + 2.6, z_oct - 1.4  # one tall window per octagon face
        add_box(bm_stone, (mx, my, 0.5 * (zb + w_lo)), (seg, wt, w_lo - zb), rot_euler=(0, 0, rot))
        add_box(bm_stone, (mx, my, 0.5 * (w_hi + z_oct)), (seg, wt, z_oct - w_hi), rot_euler=(0, 0, rot))
        side_w = 0.5 * (seg - 1.8)
        for s in (-1, 1):
            off = s * (0.9 + 0.5 * side_w)
            add_box(bm_stone, (mx + tx * off, my + ty * off, 0.5 * (w_lo + w_hi)), (side_w, wt, w_hi - w_lo), rot_euler=(0, 0, rot))
    add_cylinder(bm_stone, Vector((cx, cy, z_oct - 0.2)), Vector((cx, cy, z_oct + 0.4)), r_oct + 0.4, r_oct + 0.2, segments=24, cap=False)

    # Dome of twelve paraboloids (exact ridges), springing from the octagon, open at the lantern ring
    add_paraboloid_dome(bm_stone, cx, cy, r_oct, z_oct + 0.3, z_dome, r_open=1.4, thickness=0.4, lobes=12, steps_per_lobe=4, rings=7, ecc=0.6, rib_r=0.22)
    # Lantern: hyperboloid of one sheet (straight rulings) clad in trencadís + gilded finial
    add_ruled_hyperboloid_shell(bm_mosaic, cx, cy, z_dome - 0.5, z_lantern - 0.6, 1.55, 1.9, n=20)
    add_lathe(bm_mosaic, cx, cy, [(z_lantern - 0.6, 1.55), (z_lantern - 0.2, 1.2), (z_lantern, 0.4), (z_lantern + 0.1, 0.0)], segments=20)
    add_cylinder(bm_gold, Vector((cx, cy, z_lantern)), Vector((cx, cy, z_lantern + 1.6)), 0.14, 0.05, segments=8)
    add_cylinder(bm_gold, Vector((cx - 0.45, cy, z_lantern + 1.1)), Vector((cx + 0.45, cy, z_lantern + 1.1)), 0.06, 0.06, segments=6)
    _ = sgn


def add_crypt_mosaic(
    bm_light: bmesh.types.BMesh,
    bm_red: bmesh.types.BMesh,
    cx: float,
    cy: float,
    inner: list[Vector],
    outer: list[Vector],
    r1: float,
    r2: float,
    y_trans: float,
    y_south: float,
) -> None:
    """Roman-style (opus tessellatum) floor pattern: guilloche-like border bands and a central rosette
    in porphyry red / white marble, 1 cm proud of the crypt floor (visual only, name contains 'Floor')."""
    z = Z_CRYPT + 0.012
    # Central rosette (16 petals) under the keystone and two concentric bands
    rc = Vector((cx, cy - 1.0, z))
    for k in range(16):
        a0 = 2 * math.pi * k / 16
        a1 = a0 + 2 * math.pi / 32
        p0 = rc + Vector((0.6 * math.cos(a0), 0.6 * math.sin(a0), 0))
        p1 = rc + Vector((2.2 * math.cos(a1), 2.2 * math.sin(a1), 0))
        p2 = rc + Vector((0.6 * math.cos(a0 + 2 * math.pi / 16), 0.6 * math.sin(a0 + 2 * math.pi / 16), 0))
        f = (bm_red if k % 2 == 0 else bm_light).faces.new([(bm_red if k % 2 == 0 else bm_light).verts.new(p) for p in (p0, p1, p2)])
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
    for (ri, ro, bm) in ((2.5, 2.75, bm_red), (3.05, 3.2, bm_light), (r1 - 1.0, r1 - 0.8, bm_red)):
        ring_i = [bm.verts.new((rc.x + ri * math.cos(2 * math.pi * k / 40), rc.y + ri * math.sin(2 * math.pi * k / 40), z)) for k in range(40)]
        ring_o = [bm.verts.new((rc.x + ro * math.cos(2 * math.pi * k / 40), rc.y + ro * math.sin(2 * math.pi * k / 40), z)) for k in range(40)]
        for k in range(40):
            nk = (k + 1) % 40
            bm.faces.new((ring_i[k], ring_o[k], ring_o[nk], ring_i[nk]))
    # Ambulatory: chequer of red tesserae panels along the mid-line of every bay
    for k in range(7):
        a = 0.5 * (math.atan2(inner[k].y - cy, inner[k].x - cx) + math.atan2(inner[k + 1].y - cy, inner[k + 1].x - cx))
        rm = 0.5 * (r1 + r2)
        add_box(bm_red, (cx + rm * math.cos(a), cy + rm * math.sin(a), z - 0.004), (1.3, 1.3, 0.01), rot_euler=(0, 0, a + math.pi / 4))
    for x in (-7.6, -3.7, 0.0, 3.7, 7.6):
        add_box(bm_red, (x, 0.5 * (y_trans + y_south), z - 0.004), (1.1, 1.1, 0.01), rot_euler=(0, 0, math.pi / 4))


def build_crypt(
    bm_crypt: bmesh.types.BMesh,
    bm_crypt_stairs: bmesh.types.BMesh,
    bm_floor: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
    bm_marble: bmesh.types.BMesh,
    bm_candle: bmesh.types.BMesh,
    candle_anchors: list[tuple[float, float, float, float]],
    bm_mosaic_floor: bmesh.types.BMesh,
    bm_mosaic_red: bmesh.types.BMesh,
    bm_porphyry: bmesh.types.BMesh,
) -> None:
    """Neo-Gothic crypt (Villar 1882-83 / Gaudí) under the apse, floor Z_CRYPT = -5.5 m.

    Layout (Wikipedia es/ca, basilica site; dimensions scaled to fit the runtime walk disc of r 15.6 m
    about (0, 21) and the pinned tomb / candle / teleport positions):
      * central space: semicircle + straight part, vault on TEN clustered piers (8 on the semicircle,
        2 on the straight side), central keystone with the Annunciation;
      * ambulatory around it, SEVEN radiating chapels on the semicircle facing FIVE chapels in a row on
        the straight (south) side; Gaudí's tomb in the chapel of Our Lady of Mount Carmel (westernmost
        apse chapel, pinned at (-9.8, 23.5));
      * ribbed groin vaults over ambulatory and chapels, Roman-style (opus tessellatum) mosaic floor.
    Real crypt: ~40 x 30 m, semicircular; its vaults rise higher than here (the central vault pokes ~2 m
    above the presbytery floor) - everything is kept below -0.65 m so it never shows through the street
    slab or the nave floor.
    """
    cx, cy = 0.0, 21.0
    R1, R2, R3 = 5.6, 9.6, 13.8          # central piers / ambulatory outer ring / chapel back walls
    Y_TRANS, Y_SOUTH = 15.6, 12.0        # straight side: central space ends / transverse aisle ends
    Y_SCHAP = 9.0                        # back wall of the five south chapels
    X_SCHAP = (-9.6, -5.6, -1.87, 1.87, 5.6, 9.6)
    z_f = Z_CRYPT
    z_cap = Z_CRYPT + 2.9                # pier capitals / vault springing (-2.6 m)
    z_key = -0.72                        # central keystone (top of the crypt, < -0.65)
    z_amb = -1.1                         # ambulatory groin crowns
    z_chap = -1.3                        # chapel groin crowns
    wall_top = -0.66

    def V(x: float, y: float, z: float = 0.0) -> Vector:
        return Vector((x, y, z))

    angs = [math.pi * k / 7.0 for k in range(8)]
    inner = [V(cx + R1 * math.cos(a), cy + R1 * math.sin(a)) for a in angs]
    outer = [V(cx + R2 * math.cos(a), cy + R2 * math.sin(a)) for a in angs]
    back = [V(cx + R3 * math.cos(a), cy + R3 * math.sin(a)) for a in angs]

    # Floor slab (base marble) under the whole crypt + vestibule
    add_box(bm_floor, (0.0, 0.5 * (Y_SCHAP - 0.8 + cy), Z_CRYPT - 0.25), (2 * (R3 + 0.6), cy - Y_SCHAP + 0.8, 0.5))
    add_box(bm_floor, (-11.6, 0.5 * (Y_SOUTH + Y_TRANS), Z_CRYPT - 0.25), (4.4, Y_TRANS - Y_SOUTH + 0.6, 0.5))
    add_cylinder(bm_floor, Vector((cx, cy, Z_CRYPT - 0.5)), Vector((cx, cy, Z_CRYPT)), R3 + 0.6, R3 + 0.6, segments=28, cap=True)
    add_crypt_mosaic(bm_mosaic_floor, bm_mosaic_red, cx, cy, inner, outer, R1, R2, Y_TRANS, Y_SOUTH)

    # ── Piers: 10 clustered piers around the central space, engaged piers on the ambulatory ring ──
    central_piers = inner + [V(-R1, Y_TRANS), V(R1, Y_TRANS)]
    for p in central_piers:
        add_clustered_pier(bm_crypt, p.x, p.y, z_f, z_cap, 0.42, shafts=6)
    ring_piers = outer + [V(R2, Y_TRANS), V(-R2, Y_TRANS)] + [V(x, Y_SOUTH) for x in X_SCHAP]
    for p in ring_piers:
        add_clustered_pier(bm_crypt, p.x, p.y, z_f, z_cap, 0.32, shafts=4)

    # ── Central vault: webs from each pier pair up to the Annunciation keystone ──
    key = V(cx, cy - 1.0, z_key)
    loop = [V(R1, Y_TRANS)] + inner + [V(-R1, Y_TRANS)]
    for i in range(len(loop)):
        a, b = loop[i], loop[(i + 1) % len(loop)]
        span = (b - a).length
        rise = min(1.55, 0.36 * span)
        add_web_vault_sector(bm_crypt, V(a.x, a.y, z_cap), V(b.x, b.y, z_cap), key, z_cap, rise, res_s=4, res_t=6 if span > 6 else 4)
        # rib from the pier to the keystone, following the web
        fr = (0.0, 0.35, 0.7, 1.0)
        pts = []
        for f in fr:
            q = V(a.x, a.y, z_cap).lerp(key, f)
            q.z = z_cap + (key.z - z_cap) * (1.0 - (1.0 - f) ** 2) - 0.08
            pts.append(q)
        add_swept_tube(bm_crypt, pts, [0.13] * 4, segments=5, cap=False)
    add_lathe(bm_crypt, key.x, key.y, [(key.z - 0.3, 0.75), (key.z - 0.12, 0.98), (key.z + 0.05, 1.0)], segments=20, cap_bottom=True, cap_top=True)
    # Annunciation keystone: gilded frame, porphyry ground, white figures of Gabriel and Mary
    add_cylinder(bm_gold, Vector((key.x, key.y, key.z - 0.36)), Vector((key.x, key.y, key.z - 0.3)), 0.82, 0.82, segments=20, cap=True)
    add_cylinder(bm_porphyry, Vector((key.x, key.y, key.z - 0.4)), Vector((key.x, key.y, key.z - 0.35)), 0.66, 0.66, segments=20, cap=True)
    for fx in (-0.26, 0.24):
        add_ellipsoid(bm_marble, (key.x + fx, key.y, key.z - 0.45), (0.12, 0.18, 0.07), subdivisions=1)
        add_ellipsoid(bm_marble, (key.x + fx, key.y + 0.24, key.z - 0.47), (0.07, 0.07, 0.06), subdivisions=1)
    for s in (-1, 1):  # Gabriel's wings
        add_ellipsoid(bm_gold, (key.x - 0.26 + 0.14 * s, key.y - 0.05, key.z - 0.44), (0.08, 0.2, 0.03), subdivisions=1, rot_z=0.5 * s)

    # ── Groin-vaulted ambulatory, side bays, transverse aisle and the twelve chapels ──
    cells: list[tuple[list[Vector], float]] = []
    for k in range(7):
        cells.append(([inner[k], outer[k], outer[k + 1], inner[k + 1]], z_amb))   # ambulatory
        cells.append(([outer[k], back[k], back[k + 1], outer[k + 1]], z_chap))    # apse chapel
    for s in (-1, 1):
        cells.append(([V(s * R1, Y_TRANS), V(s * R2, Y_TRANS), V(s * R2, cy), V(s * R1, cy)], z_amb))
    for i in range(5):
        x0, x1 = X_SCHAP[i], X_SCHAP[i + 1]
        cells.append(([V(x0, Y_SOUTH), V(x1, Y_SOUTH), V(x1, Y_TRANS), V(x0, Y_TRANS)], z_amb))   # transverse aisle
        cells.append(([V(x0, Y_SCHAP), V(x1, Y_SCHAP), V(x1, Y_SOUTH), V(x0, Y_SOUTH)], z_chap))  # south chapel
    for corners, crown in cells:
        boss = add_groin_vault_cell(bm_crypt, bm_crypt, corners, z_cap, crown, res=4, rib_r=0.09)
        add_cylinder(bm_gold, boss - Vector((0, 0, 0.16)), boss + Vector((0, 0, 0.02)), 0.16, 0.2, segments=6, cap=True)

    # ── Walls ──
    wt = 0.55
    for k in range(7):
        # chapel back wall: two flat panels per chapel
        for half in range(2):
            a0 = angs[k] + (angs[k + 1] - angs[k]) * half * 0.5
            a1 = angs[k] + (angs[k + 1] - angs[k]) * (half + 1) * 0.5
            p0 = V(cx + (R3 + wt * 0.5) * math.cos(a0), cy + (R3 + wt * 0.5) * math.sin(a0))
            p1 = V(cx + (R3 + wt * 0.5) * math.cos(a1), cy + (R3 + wt * 0.5) * math.sin(a1))
            m = (p0 + p1) * 0.5
            add_box(bm_crypt, (m.x, m.y, 0.5 * (z_f + wall_top)), ((p1 - p0).length + 0.4, wt, wall_top - z_f), rot_euler=(0, 0, math.atan2(p1.y - p0.y, p1.x - p0.x)))
        # small chapel altar against the back wall (the tomb chapel, k = 6, has Gaudí's tomb instead)
        if k != 6:
            am = 0.5 * (angs[k] + angs[k + 1])
            add_box(bm_marble, (cx + (R3 - 0.55) * math.cos(am), cy + (R3 - 0.55) * math.sin(am), z_f + 0.5), (1.3, 0.6, 1.0), rot_euler=(0, 0, am + math.pi / 2))
    for k in range(8):
        # radial walls between the apse chapels (k = 0 / 7 close the outermost chapels)
        a = angs[k]
        r0, r1 = R2 + 0.35, R3 + 0.2
        m = V(cx + 0.5 * (r0 + r1) * math.cos(a), cy + 0.5 * (r0 + r1) * math.sin(a))
        add_box(bm_crypt, (m.x, m.y, 0.5 * (z_f + z_cap + 0.4)), (r1 - r0, 0.5, z_cap + 0.4 - z_f), rot_euler=(0, 0, a))
    for s in (-1, 1):
        # outer walls of the straight ambulatory bays (x = +-R2, y 15.6 .. 21)
        add_box(bm_crypt, (s * (R2 + 0.3), 0.5 * (Y_TRANS + cy), 0.5 * (z_f + wall_top)), (wt, cy - Y_TRANS + 0.3, wall_top - z_f))
    # east end of the transverse aisle (the west end opens into the stair vestibule)
    add_box(bm_crypt, (R2 + 0.3, 0.5 * (Y_SOUTH + Y_TRANS), 0.5 * (z_f + wall_top)), (wt, Y_TRANS - Y_SOUTH, wall_top - z_f))
    # five south chapels: back wall, outer walls, dividers, altars
    add_box(bm_crypt, (0.0, Y_SCHAP - wt * 0.5, 0.5 * (z_f + wall_top)), (2 * R2 + 1.2, wt, wall_top - z_f))
    for x in X_SCHAP:
        outer_wall = abs(x) > 9.0
        xc = x + (0.3 if x > 0 else -0.3) if outer_wall else x
        top = wall_top if outer_wall else z_cap + 0.4
        add_box(bm_crypt, (xc, 0.5 * (Y_SCHAP + Y_SOUTH - 0.35), 0.5 * (z_f + top)), (wt if outer_wall else 0.42, Y_SOUTH - Y_SCHAP - 0.35, top - z_f))
    for i in range(5):
        xm = 0.5 * (X_SCHAP[i] + X_SCHAP[i + 1])
        add_box(bm_marble, (xm, Y_SCHAP + 0.45, z_f + 0.5), (1.3, 0.6, 1.0))
    # Vestibule at the foot of the stair tunnel (x -13.6 .. -9.6): side walls + flat stone ceiling
    for wy in (Y_SOUTH - 0.12, Y_TRANS + 0.12):
        add_box(bm_crypt, (-11.6, wy, 0.5 * (z_f + wall_top)), (4.4, 0.36, wall_top - z_f))
    add_box(bm_crypt, (-11.6, 0.5 * (Y_SOUTH + Y_TRANS), -0.8), (4.4, Y_TRANS - Y_SOUTH + 0.6, 0.28))

    # Central Crypt Altar (under the main High Altar) + 2 brass altar candlesticks
    add_box(bm_marble, (cx, cy + 1.5, Z_CRYPT + 0.65), (3.0, 1.4, 1.3))
    add_cylinder(bm_gold, Vector((cx, cy + 1.5, Z_CRYPT + 1.3)), Vector((cx, cy + 1.5, Z_CRYPT + 3.0)), 0.08, 0.06, segments=8)
    add_cylinder(bm_gold, Vector((cx - 0.55, cy + 1.5, Z_CRYPT + 2.45)), Vector((cx + 0.55, cy + 1.5, Z_CRYPT + 2.45)), 0.06, 0.06, segments=8)
    for sx_a in (-1.05, 1.05):
        ax_c, ay_c = cx + sx_a, cy + 1.5
        add_cylinder(bm_gold, Vector((ax_c, ay_c, Z_CRYPT + 1.30)), Vector((ax_c, ay_c, Z_CRYPT + 1.62)), 0.10, 0.05, segments=8)
        add_cylinder(bm_candle, Vector((ax_c, ay_c, Z_CRYPT + 1.62)), Vector((ax_c, ay_c, Z_CRYPT + 1.98)), 0.045, 0.04, segments=8)
        candle_anchors.append((ax_c, ay_c, Z_CRYPT + 2.00, 0.78))

    # ANTONI GAUDÍ'S TOMB (Chapel of Our Lady of Mount Carmel, West side of Crypt: X = -9.8, Y = 23.5)
    tx, ty = -9.8, 23.5
    add_box(bm_marble, (tx, ty, Z_CRYPT + 0.14), (2.4, 1.35, 0.28))
    add_box(bm_gold, (tx, ty, Z_CRYPT + 0.30), (1.9, 0.9, 0.04))  # Inscribed bronze/gold plaque
    # Warm glowing votive candle rack beside Gaudí's tomb
    add_box(bm_crypt, (tx - 0.62, ty + 1.4, Z_CRYPT + 0.42), (2.2, 0.45, 0.84))
    add_box(bm_gold, (tx - 0.62, ty + 1.4, Z_CRYPT + 0.85), (2.26, 0.50, 0.04))
    for k in range(6):
        vx = tx - 1.5 + k * 0.35
        vy = ty + 1.4
        z_top_g = Z_CRYPT + 1.14 + (0.04 if k % 2 == 0 else 0.0)
        add_cylinder(bm_candle, Vector((vx, vy, Z_CRYPT + 0.86)), Vector((vx, vy, z_top_g)), 0.042, 0.038, segments=7)
        candle_anchors.append((vx, vy, z_top_g + 0.02, 0.68))

    # Additional warm votive candles on proper sculpted bronze/stone candelabra stands around the central sanctuary
    for i in range(8):
        ang = 2.0 * math.pi * i / 8.0 + 0.3
        vx = cx + 4.8 * math.cos(ang)
        vy = cy + 4.8 * math.sin(ang)
        # Sculpted pedestal base + stem + drip dish resting firmly on Z_CRYPT
        add_cylinder(bm_gold, Vector((vx, vy, Z_CRYPT)), Vector((vx, vy, Z_CRYPT + 0.12)), 0.24, 0.16, segments=10)
        add_cylinder(bm_gold, Vector((vx, vy, Z_CRYPT + 0.12)), Vector((vx, vy, Z_CRYPT + 0.88)), 0.055, 0.045, segments=8)
        add_cylinder(bm_gold, Vector((vx, vy, Z_CRYPT + 0.86)), Vector((vx, vy, Z_CRYPT + 0.92)), 0.16, 0.12, segments=10)
        add_cylinder(
            bm_candle,
            Vector((vx, vy, Z_CRYPT + 0.92)),
            Vector((vx, vy, Z_CRYPT + 1.26)),
            0.055,
            0.048,
            segments=8,
        )
        candle_anchors.append((vx, vy, Z_CRYPT + 1.28, 0.82))

    # Watertight UNDERGROUND Stone Stairwell Tunnel: (-21.0, +13.8, Z=1.2) -> Crypt Entry (-11.2, +13.8, Z=-5.5)
    # CRITICAL: Every underground tunnel wall & ceiling stays strictly BELOW Z = Z_NAVE (1.2m) so NOTHING protrudes above the Nave floor!
    num_steps = 28
    p_top = Vector((-21.0, 13.8, Z_NAVE))
    p_bot = Vector((-11.2, 13.8, Z_CRYPT))
    tunnel_half_w = 1.45
    z_floor_cap = Z_NAVE - 0.04  # Strictly flush beneath the Nave marble floor!
    for s in range(num_steps):
        t = s / (num_steps - 1)
        pos = p_top.lerp(p_bot, t)
        # Solid stone step tread + deep masonry sub-base (in dedicated stair mesh so capsule climbs automatically!)
        add_box(bm_crypt_stairs, (pos.x, pos.y, pos.z - 0.35), (0.52, tunnel_half_w * 2.0 + 0.2, 0.70))
        # Left & right underground stone tunnel walls terminate cleanly at outer crypt wall (x <= -13.6) so they never jut into Crypt!
        if pos.x <= -13.55:
            wall_bot = pos.z - 0.65
            wall_top = z_floor_cap
            wall_ht = max(0.35, wall_top - wall_bot)
            for side in (-1, 1):
                wy = pos.y + side * (tunnel_half_w + 0.22)
                add_box(bm_crypt, (pos.x, wy, wall_bot + wall_ht * 0.5), (0.62, 0.44, wall_ht))
            # Sloped underground ceiling ONLY where headroom (pos.z + 3.1) is below the Nave floor!
            if pos.z + 3.05 < z_floor_cap:
                add_box(bm_crypt, (pos.x, pos.y, pos.z + 3.15), (0.65, tunnel_half_w * 2.0 + 0.9, 0.45))
    # Underground end-wall sealing beneath the very top step (strictly below Nave floor Z=1.2!)
    add_box(bm_crypt, (p_top.x - 0.35, p_top.y, Z_NAVE - 0.65), (0.45, tunnel_half_w * 2.0 + 0.9, 1.25))


def build_cloister_and_crypt() -> None:
    reset_scene()
    mats = get_materials()

    bm_stone = bmesh.new()
    bm_floor = bmesh.new()
    bm_mosaic = bmesh.new()
    bm_gold = bmesh.new()
    bm_crypt = bmesh.new()
    bm_crypt_stairs = bmesh.new()
    bm_cloister_stairs = bmesh.new()
    bm_marble = bmesh.new()
    bm_candle = bmesh.new()
    bm_mosaic_floor = bmesh.new()
    bm_mosaic_red = bmesh.new()
    bm_porphyry = bmesh.new()

    # ── 1. East & West Perimeter Cloister Galleries (walkable outer arcades + exterior steps) ──
    add_cloister_gallery_wing(bm_stone, bm_floor, x_center=26.2, y_start=-46.0, y_end=-15.2, bm_stairs=bm_cloister_stairs)
    add_cloister_gallery_wing(bm_stone, bm_floor, x_center=-26.2, y_start=-46.0, y_end=-15.2, bm_stairs=bm_cloister_stairs)
    # North-East & North-West cloister connectors ending at the sacristies' south wall (y = 32.5 - 7.0)
    add_cloister_gallery_wing(bm_stone, bm_floor, x_center=26.2, y_start=15.2, y_end=25.5)
    add_cloister_gallery_wing(bm_stone, bm_floor, x_center=-26.2, y_start=15.2, y_end=25.5)

    # ── 2. Two Monumental Domed Sacristies (NE & NW Corners) ──
    add_sacristy_pavilion(bm_stone, bm_floor, bm_mosaic, bm_gold, cx=27.5, cy=32.5)
    add_sacristy_pavilion(bm_stone, bm_floor, bm_mosaic, bm_gold, cx=-27.5, cy=32.5)

    # ── 3. Subterranean Neo-Gothic Crypt & Gaudí's Tomb ──
    crypt_candle_anchors: list[tuple[float, float, float, float]] = []
    build_crypt(bm_crypt, bm_crypt_stairs, bm_floor, bm_gold, bm_marble, bm_candle, crypt_candle_anchors, bm_mosaic_floor, bm_mosaic_red, bm_porphyry)

    finalize_bmesh_object(bm_stone, "Cloister_And_Sacristies", mats["sandstone_warm"], smooth=False, uv_scale=0.15)
    finalize_bmesh_object(bm_floor, "Cloister_And_Crypt_Floor", mats["floor_marble"], smooth=False, uv_scale=0.18)
    finalize_bmesh_object(bm_mosaic, "Sacristy_Trencadis", mats["trencadis"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_gold, "Cloister_Gold", mats["gold_accent"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_crypt, "Crypt_Architecture", mats["crypt_stone"], smooth=False, uv_scale=0.16)
    finalize_bmesh_object(bm_crypt_stairs, "Crypt_StairSteps", mats["crypt_stone"], smooth=False, uv_scale=0.16, bake_ao=False)
    finalize_bmesh_object(bm_cloister_stairs, "Cloister_EntranceStairs", mats["sandstone_warm"], smooth=False, uv_scale=0.16, bake_ao=False)
    finalize_bmesh_object(bm_marble, "Crypt_AltarAndGaudiTomb", mats["white_marble"], smooth=False, uv_scale=0.30)
    finalize_bmesh_object(bm_candle, "Crypt_VotiveCandles", mats["candle_glow"], smooth=True, uv_scale=0.50)
    finalize_oriented(bm_mosaic_floor, "Crypt_MosaicFloor_Marble", mats["white_marble"], smooth=False, uv_scale=0.5, ao=False)
    finalize_oriented(bm_mosaic_red, "Crypt_MosaicFloor_Porphyry", mats["porphyry_red"], smooth=False, uv_scale=0.5, ao=False)
    finalize_bmesh_object(bm_porphyry, "Crypt_KeystonePorphyry", mats["porphyry_red"], smooth=True, uv_scale=0.5, bake_ao=False)

    save_candle_anchors("crypt", crypt_candle_anchors)
    export_glb(os.path.join(MODEL_DIR, "cloister_crypt.glb"))


if __name__ == "__main__":
    build_cloister_and_crypt()
