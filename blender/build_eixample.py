"""Build the surrounding Barcelona Eixample district on the true site plan (layout.py §12):
streets, sidewalks and the basilica block on the sloped ground plane, Plaça de Gaudí with its pond,
Plaça de la Sagrada Família, the 13 neighbouring Cerdà blocks, street trees and lamps, the distant
city, the horizon hills and the sea."""

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
    apply_box_uv,
    bake_bvh_vertex_ao,
    export_glb,
    finalize_bmesh_object,
    get_materials,
    reset_scene,
)
import layout as L
import city_lib as C

g = L.ground_z


def add_cerda_block(
    bm_wall: bmesh.types.BMesh,
    bm_roof: bmesh.types.BMesh,
    bm_iron: bmesh.types.BMesh,
    bm_awning: bmesh.types.BMesh,
    blk: dict,
    add_street_detail: bool = False,
) -> None:
    """Ildefons Cerdà chamfered apartment block (layout.CITY_BLOCKS entry) with courtyard, rooftop
    structures and, on the faces that look at the basilica, balconies, cornice and shop awnings.
    The base starts at the ground of the block's lowest (south) edge, so nothing floats on the slope."""
    x0, y0, x1, y1 = blk["x0"], blk["y0"], blk["x1"], blk["y1"]
    corners = blk.get("chamferCorners", [True, True, True, True])
    c = blk["chamfer"]
    h = blk["height"]
    inset = blk["courtyardInset"]
    w, d = x1 - x0, y1 - y0
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    outer_pts = C.chamfered_rect(x0, y0, x1, y1, c, corners)
    iw, idp = w - 2 * inset, d - 2 * inset
    ic = min(c * 0.55, 0.45 * min(iw, idp))
    inner_pts = C.chamfered_rect(x0 + inset, y0 + inset, x1 - inset, y1 - inset, ic, corners)

    z_base = g(y0) - 0.4
    z_top = g(y0) + h
    n = len(outer_pts)
    ob = [bm_wall.verts.new((x, y, z_base)) for x, y in outer_pts]
    ot = [bm_wall.verts.new((x, y, z_top)) for x, y in outer_pts]
    ib = [bm_wall.verts.new((x, y, z_base)) for x, y in inner_pts]
    it = [bm_wall.verts.new((x, y, z_top)) for x, y in inner_pts]
    rob = [bm_roof.verts.new((x, y, z_top + 0.05)) for x, y in outer_pts]
    rib = [bm_roof.verts.new((x, y, z_top + 0.05)) for x, y in inner_pts]

    site = Vector(C.SITE_CENTER)
    for i in range(n):
        ni = (i + 1) % n
        bm_wall.faces.new((ob[i], ob[ni], ot[ni], ot[i]))
        bm_wall.faces.new((ib[ni], ib[i], it[i], it[ni]))
        bm_roof.faces.new((rob[i], rob[ni], rib[ni], rib[i]))

        if not add_street_detail:
            continue
        p0 = Vector(outer_pts[i])
        p1 = Vector(outer_pts[ni])
        edge = p1 - p0
        elen = edge.length
        if elen < 14.0:
            continue
        tang = edge.normalized()
        out_n = Vector((tang.y, -tang.x))
        mid = (p0 + p1) * 0.5
        if out_n.dot((site - mid).normalized()) < 0.25:
            continue
        rot_z = math.atan2(tang.y, tang.x)
        # Roof cornice ledge
        add_box(bm_wall, (mid.x + out_n.x * 0.4, mid.y + out_n.y * 0.4, z_top - 0.25), (elen + 0.4, 0.9, 0.55), rot_euler=(0, 0, rot_z))
        # Balcony slabs follow the sloping street (local ground + floor height); iron rails in bays
        a = p0 + tang * (elen * 0.07)
        b = p1 - tang * (elen * 0.07)
        n_bays = max(1, round((b - a).length / 15.0))
        for bz in (7.6, 11.6, 15.6):
            if bz > h - 4.0:
                continue
            s0 = a + out_n * 0.65
            s1 = b + out_n * 0.65
            C.add_beam(bm_wall, Vector((s0.x, s0.y, g(s0.y) + bz)), Vector((s1.x, s1.y, g(s1.y) + bz)), 1.2, 0.22)
            for k in range(n_bays):
                f0 = k / n_bays + 0.06 / n_bays
                f1 = (k + 1) / n_bays - 0.06 / n_bays
                r0 = a.lerp(b, f0) + out_n * 1.22
                r1 = a.lerp(b, f1) + out_n * 1.22
                C.add_beam(bm_iron, Vector((r0.x, r0.y, g(r0.y) + bz + 0.55)), Vector((r1.x, r1.y, g(r1.y) + bz + 0.55)), 0.08, 0.95)
        # Ground-floor shop awnings, one per ~15 m bay, at the local sidewalk level
        n_aw = max(1, round(elen / 15.0))
        for k in range(n_aw):
            ap = p0.lerp(p1, (k + 0.5) / n_aw) + out_n * 1.15
            add_box(bm_awning, (ap.x, ap.y, g(ap.y) + 3.8), (min(8.5, elen / n_aw * 0.7), 2.2, 0.24), rot_euler=(0.26, 0.0, rot_z))

    # Roof parapet along the outer edge
    z_roof = z_top + 0.05
    for i in range(n):
        ni = (i + 1) % n
        p0 = Vector((outer_pts[i][0], outer_pts[i][1], z_roof))
        p1 = Vector((outer_pts[ni][0], outer_pts[ni][1], z_roof))
        edge = p1 - p0
        rot_z = math.atan2(edge.y, edge.x)
        mid = (p0 + p1) * 0.5
        add_box(bm_wall, (mid.x, mid.y, z_roof + 0.52), (edge.length + 0.3, 0.42, 1.05), rot_euler=(0, 0, rot_z))

    # Rooftop stairheads, chimneys and service boxes on the four wings
    seed = int(abs(cx * 3.1 + cy * 7.3)) % 100
    wy = 0.5 * d - inset * 0.5
    wx = 0.5 * w - inset * 0.5
    for idx_w, (px, py, rw, rd) in enumerate((
        (cx, cy + wy, w * 0.44, inset * 0.58),
        (cx, cy - wy, w * 0.44, inset * 0.58),
        (cx + wx, cy, inset * 0.58, d * 0.44),
        (cx - wx, cy, inset * 0.58, d * 0.44),
    )):
        ph_h = 2.6 + ((seed + idx_w * 13) % 3) * 0.85
        add_box(bm_wall, (px, py, z_roof + ph_h * 0.5), (rw * 0.42, rd * 0.65, ph_h))
        add_box(bm_roof, (px, py, z_roof + ph_h + 0.14), (rw * 0.46, rd * 0.70, 0.28))
        off = 1.0 if (idx_w % 2 == 0) else -1.0
        ch_x = px + (rw * 0.32 * off if idx_w < 2 else 0.0)
        ch_y = py + (0.0 if idx_w < 2 else rd * 0.32 * off)
        add_box(bm_roof, (ch_x, ch_y, z_roof + 1.1), (1.8, 1.4, 2.2))
        add_box(bm_iron, (ch_x + 2.2 * off, ch_y + 1.4, z_roof + 0.55), (1.9, 1.3, 1.1))


def _add_organic_canopy_lobe(bm: bmesh.types.BMesh, center: Vector, rx: float, ry: float, rz: float, seed: float, subdiv: int = 2) -> None:
    """Solid organically sculpted leafy foliage cluster (zero broken paper-thin alpha quads!)."""
    ret = bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    for v in ret["verts"]:
        p = v.co
        bump = (
            1.0
            + 0.22 * math.sin(p.x * 4.2 + seed) * math.cos(p.y * 3.9 - seed * 0.7)
            + 0.14 * math.sin(p.z * 5.1 + p.x * 3.3 + seed * 1.3)
        )
        v.co = Vector((center.x + p.x * rx * bump, center.y + p.y * ry * bump, center.z + p.z * rz * bump))


def create_tree_mesh(name: str, trunk_mat: bpy.types.Material, leaf_mat: bpy.types.Material, kind: str = "plane") -> tuple[bpy.types.Mesh, bpy.types.Mesh]:
    """Mediterranean London plane (park, full detail), London plane (street, light) and cypress."""
    bm_t = bmesh.new()
    bm_l = bmesh.new()

    if kind == "cypress":
        add_cylinder(bm_t, Vector((0, 0, 0)), Vector((0, 0, 2.8)), 0.24, 0.14, segments=8)
        for tier in range(7):
            t = tier / 6.0
            z = 2.4 + t * 8.8
            r = 1.38 * (1.0 - t * 0.78) * (0.78 + 0.22 * math.sin(t * math.pi))
            _add_organic_canopy_lobe(bm_l, Vector((0, 0, z)), r, r, 1.55 * (1.0 - t * 0.35), seed=tier * 2.1)
    elif kind == "plane":
        add_cylinder(bm_t, Vector((0, 0, 0)), Vector((0.08, -0.05, 3.6)), 0.38, 0.26, segments=9)
        boughs = [
            (Vector((0.08, -0.05, 3.3)), Vector((2.1, 0.9, 6.0)), 0.18, 0.08, 2.25, 1.85),
            (Vector((0.08, -0.05, 3.4)), Vector((-2.0, 1.2, 6.2)), 0.18, 0.08, 2.35, 1.90),
            (Vector((0.08, -0.05, 3.5)), Vector((0.6, -2.1, 5.8)), 0.17, 0.08, 2.20, 1.80),
            (Vector((0.08, -0.05, 3.2)), Vector((-1.4, -1.6, 5.7)), 0.16, 0.07, 2.05, 1.75),
            (Vector((0.08, -0.05, 3.5)), Vector((0.1, 0.2, 7.3)), 0.19, 0.08, 2.55, 2.05),
        ]
        for bi, (p0, p1, r0, r1, rw, rh) in enumerate(boughs):
            add_cylinder(bm_t, p0, p1, r0, r1, segments=7)
            _add_organic_canopy_lobe(bm_l, p1 + Vector((0, 0, 0.65)), rw, rw * 0.94, rh, seed=bi * 3.7 + 1.1)
            off = Vector((math.cos(bi * 1.9) * 1.1, math.sin(bi * 1.9) * 1.1, 0.15))
            _add_organic_canopy_lobe(bm_l, p1 + off, rw * 0.68, rw * 0.68, rh * 0.72, seed=bi * 5.1)
    else:
        # Street plane tree: same silhouette family at a fraction of the cost (lines the four streets)
        add_cylinder(bm_t, Vector((0, 0, 0)), Vector((0.06, -0.04, 3.4)), 0.30, 0.21, segments=7)
        boughs = [
            (Vector((0.06, -0.04, 3.2)), Vector((1.7, 0.7, 5.7)), 2.3, 1.8),
            (Vector((0.06, -0.04, 3.3)), Vector((-1.6, 1.0, 5.9)), 2.4, 1.9),
            (Vector((0.06, -0.04, 3.3)), Vector((0.2, -1.8, 5.6)), 2.2, 1.8),
        ]
        for bi, (p0, p1, rw, rh) in enumerate(boughs):
            add_cylinder(bm_t, p0, p1, 0.15, 0.07, segments=5, cap=False)
            _add_organic_canopy_lobe(bm_l, p1 + Vector((0, 0, 0.6)), rw, rw * 0.95, rh, seed=bi * 3.7 + 1.1, subdiv=2)
        _add_organic_canopy_lobe(bm_l, Vector((0.0, 0.1, 7.2)), 2.3, 2.2, 1.7, seed=7.7, subdiv=2)

    apply_box_uv(bm_t, scale=0.45)
    bake_bvh_vertex_ao(bm_t, max_dist=2.2, min_ao=0.52)
    bmesh.ops.recalc_face_normals(bm_l, faces=bm_l.faces)
    bm_l.normal_update()
    apply_box_uv(bm_l, scale=0.42)
    bake_bvh_vertex_ao(bm_l, max_dist=3.5, min_ao=0.42)

    mt = bpy.data.meshes.new(name + "_Trunk")
    ml = bpy.data.meshes.new(name + "_Leaves")
    bm_t.to_mesh(mt)
    bm_l.to_mesh(ml)
    bm_t.free()
    bm_l.free()
    mt.polygons.foreach_set("use_smooth", [True] * len(mt.polygons))
    ml.polygons.foreach_set("use_smooth", [True] * len(ml.polygons))
    mt.materials.append(trunk_mat)
    ml.materials.append(leaf_mat)
    return mt, ml


def create_lamp_mesh(iron_mat: bpy.types.Material, glow_mat: bpy.types.Material) -> tuple[bpy.types.Mesh, bpy.types.Mesh]:
    bm_p = bmesh.new()
    bm_g = bmesh.new()
    # post starts 0.3 m below the datum so it stays planted on the 2.2 % slope
    add_cylinder(bm_p, Vector((0, 0, -0.3)), Vector((0, 0, 5.2)), 0.16, 0.08, segments=8)
    add_cylinder(bm_p, Vector((0, 0, 4.9)), Vector((0, 0, 5.3)), 0.24, 0.14, segments=8)
    add_cylinder(bm_g, Vector((0, 0, 5.25)), Vector((0, 0, 5.78)), 0.22, 0.18, segments=8)
    apply_box_uv(bm_p, scale=0.5)
    apply_box_uv(bm_g, scale=0.5)
    mp = bpy.data.meshes.new("Mesh_LampPost")
    mg = bpy.data.meshes.new("Mesh_LampGlobe")
    bm_p.to_mesh(mp)
    bm_g.to_mesh(mg)
    bm_p.free()
    bm_g.free()
    mp.materials.append(iron_mat)
    mg.materials.append(glow_mat)
    return mp, mg


def place_pair(prefix: str, idx: int, m1: bpy.types.Mesh, m2: bpy.types.Mesh, pos: tuple[float, float, float], scale: float = 1.0, rot_z: float = 0.0) -> None:
    for suffix, m in (("A", m1), ("B", m2)):
        obj = bpy.data.objects.new(f"{prefix}_{idx}_{suffix}", m)
        obj.location = pos
        obj.rotation_euler = (0.0, 0.0, rot_z)
        obj.scale = (scale, scale, scale)
        bpy.context.collection.objects.link(obj)


def _distant_cells() -> list[tuple[float, float, float, float]]:
    """Cerdà grid cells beyond the 15 detailed ones, continued on the real pitch (113.3 m blocks,
    20 m streets), kept outside DISTANT_CITY_MIN_EXTENT and in front of the hills ring."""
    by = {b["name"]: b for b in L.CITY_BLOCKS}
    cols = [(by[k]["x0"], by[k]["x1"]) for k in ("FWN", "NW", "NC", "NE", "FEN")]
    rows = [(by["SW"]["y0"], by["SW"]["y1"]), (L.BLOCK_LINE_SOUTH, L.BLOCK_LINE_NORTH), (by["NC"]["y0"], by["NC"]["y1"])]
    street, size = 20.0, 113.3
    cols = [(cols[0][0] - street - size, cols[0][0] - street)] + cols + [(cols[-1][1] + street, cols[-1][1] + street + size)]
    for _ in range(2):
        rows = [(rows[0][0] - street - size, rows[0][0] - street)] + rows + [(rows[-1][1] + street, rows[-1][1] + street + size)]
    ex, ey = L.DISTANT_CITY_MIN_EXTENT
    out = []
    for ci, (x0, x1) in enumerate(cols):
        for ri, (y0, y1) in enumerate(rows):
            if 1 <= ci <= 5 and 2 <= ri <= 4:
                continue  # detailed blocks, the basilica block and the two plazas
            if x1 > -ex and x0 < ex:          # inside the |x| band: must lie beyond |y| > ey
                if y1 > 0:
                    y0 = max(y0, ey)
                else:
                    y1 = min(y1, -ey)
            mx, my = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
            ang = math.degrees(math.atan2(my, mx))
            if math.hypot(mx, my) > 385.0 and -145.0 <= ang <= 90.0:
                continue  # would sit in the hills ring
            if x0 < 0.0 < x1 and y1 < 0:
                ax0, ax1 = L.GLORY_AVENUE["x0"], L.GLORY_AVENUE["x1"]   # the Glory avenue continues south
                out.append((x0, y0, ax0, y1))
                out.append((ax1, y0, x1, y1))
            else:
                out.append((x0, y0, x1, y1))
    return out


TORRE_GLORIES = (140.0, -300.0)   # EST: real bearing ~ESE of the basilica, pulled in to the city ring


def build_eixample() -> None:
    reset_scene()
    mats = get_materials()

    bm_asphalt = bmesh.new()
    bm_panot = bmesh.new()
    bm_grass = bmesh.new()
    bm_stone = bmesh.new()
    bm_facade_ochre = bmesh.new()
    bm_facade_terra = bmesh.new()
    bm_facade_cream = bmesh.new()
    bm_roof = bmesh.new()
    bm_iron = bmesh.new()
    bm_awning = bmesh.new()
    bm_hills = bmesh.new()
    bm_sea = bmesh.new()
    bm_horizon_city = bmesh.new()

    crypt_hole = C.crypt_ground_hole()

    # ── 1. Carriageways: one tilted plane CURB below the ground, cut open over the crypt ──
    R = C.GROUND_EXTENT
    C.add_ground_slab(bm_asphalt, [(-R, -R), (R, -R), (R, R), (-R, R)], holes=[crypt_hole, C.pond_outer()], z_off=-L.CURB_HEIGHT, curb=0.0)

    # ── 2. Basilica block: sidewalk ring + forecourts on the sloped ground (building sits on top) ──
    C.add_ground_slab(bm_panot, C.curb_outline(L.SAGRADA_BLOCK), holes=[crypt_hole])

    # ── 3. Plaça de Gaudí with the pond, Plaça de la Sagrada Família ──
    C.add_ground_slab(bm_panot, C.curb_outline(L.PLACA_GAUDI), holes=[C.pond_outer()])
    C.add_ground_slab(bm_panot, C.curb_outline(L.PLACA_SAGRADA_FAMILIA))
    for (x0, y0, x1, y1) in C.GAUDI_LAWNS + C.SF_LAWNS + C.NATIVITY_LAWNS:
        C.add_ground_slab(bm_grass, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z_off=0.08, curb=0.12)

    # Pond basin: level floor, inner wall, sloping coping that follows the bank, outer face
    water = L.POND_WATER_Z
    cop = L.POND["copingAboveGround"]
    inner = C.pond_inner()
    outer = C.pond_outer()
    floor_z = water - 0.6
    fl = [bm_stone.verts.new((x, y, floor_z)) for x, y in inner]
    bm_stone.faces.new(fl)
    ni = len(inner)
    it = [bm_stone.verts.new((x, y, g(y) + cop)) for x, y in inner]
    ib = [bm_stone.verts.new((x, y, floor_z)) for x, y in inner]
    ot = [bm_stone.verts.new((x, y, g(y) + cop)) for x, y in outer]
    obv = [bm_stone.verts.new((x, y, g(y) - 0.12)) for x, y in outer]
    for i in range(ni):
        j = (i + 1) % ni
        bm_stone.faces.new((ib[j], ib[i], it[i], it[j]))       # inner wall (faces the water)
        bm_stone.faces.new((it[i], ot[i], ot[j], it[j]))       # coping top
        bm_stone.faces.new((obv[i], obv[j], ot[j], ot[i]))     # outer face down into the paving

    # ── 4. Glory avenue (pedestrian) between the two half blocks south of Mallorca ──
    av = L.GLORY_AVENUE
    sw = L.SIDEWALK_WIDTH
    ax0, ax1, ay0, ay1 = av["x0"] + sw, av["x1"] - sw, av["y0"] - sw, av["y1"] + sw
    C.add_ground_slab(bm_panot, [(ax0, ay0), (ax1, ay0), (ax1, ay1), (ax0, ay1)], curb=0.0)
    for yy, s in ((ay0, -1), (ay1, 1)):
        a = bm_panot.verts.new((ax0, yy, g(yy) - L.CURB_HEIGHT))
        b = bm_panot.verts.new((ax1, yy, g(yy) - L.CURB_HEIGHT))
        c_ = bm_panot.verts.new((ax1, yy, g(yy)))
        d_ = bm_panot.verts.new((ax0, yy, g(yy)))
        bm_panot.faces.new((a, b, c_, d_) if s < 0 else (b, a, d_, c_))

    # ── 5. The 13 neighbouring Cerdà blocks (layout.CITY_BLOCKS) ──
    facade_buckets = [bm_facade_ochre, bm_facade_terra, bm_facade_cream]
    for idx_b, blk in enumerate(L.CITY_BLOCKS):
        C.add_ground_slab(bm_panot, C.curb_outline(blk))
        far = blk["name"].startswith("F")
        add_cerda_block(facade_buckets[idx_b % 3], bm_roof, bm_iron, bm_awning, blk, add_street_detail=not far)

    # ── 6. Distant city, Torre Glòries, Collserola/Montjuïc ridge, the sea ──
    for (x0, y0, x1, y1) in _distant_cells():
        tx, ty = TORRE_GLORIES
        if x0 - 16 < tx < x1 + 16 and y0 - 16 < ty < y1 + 16:
            continue
        h_city = 17.0 + (int(abs((x0 + x1) * 3.5 + (y0 + y1) * 6.5)) % 5) * 2.4
        pts = C.chamfered_rect(x0, y0, x1, y1, min(L.CHAMFER_LEG, 0.3 * (x1 - x0)))
        zb, zt = g(y0) - 1.0, g(y0) + h_city
        vb = [bm_horizon_city.verts.new((x, y, zb)) for x, y in pts]
        vt = [bm_horizon_city.verts.new((x, y, zt)) for x, y in pts]
        for i in range(len(pts)):
            j = (i + 1) % len(pts)
            bm_horizon_city.faces.new((vb[i], vb[j], vt[j], vt[i]))
        bm_roof.faces.new([bm_roof.verts.new((x, y, zt + 0.02)) for x, y in pts])

    tx, ty = TORRE_GLORIES
    zt0 = g(ty) - 0.5
    add_cylinder(bm_sea, Vector((tx, ty, zt0)), Vector((tx, ty, zt0 + 92.0)), 14.5, 13.8, segments=14, cap=True)
    add_cylinder(bm_sea, Vector((tx, ty, zt0 + 92.0)), Vector((tx, ty, zt0 + 128.0)), 13.8, 3.2, segments=14, cap=True)

    # Ridge ring r 370..560 (unchanged shape), now seated on the sloped ground plane
    n_ridge = 36
    r_inner, r_outer = 370.0, 560.0
    prev_in = prev_peak = prev_out = None
    for i in range(n_ridge + 1):
        ang = math.radians(-145.0 + (235.0 * i / n_ridge))
        ca, sa = math.cos(ang), math.sin(ang)
        t = i / n_ridge
        env = math.sin(t * math.pi)
        h_peak = (
            38.0
            + 52.0 * math.exp(-((t - 0.54) / 0.16) ** 2)  # Tibidabo
            + 34.0 * math.exp(-((t - 0.14) / 0.12) ** 2)  # Montjuïc
            + 26.0 * math.exp(-((t - 0.78) / 0.18) ** 2)  # Eastern Collserola
            + 12.0 * math.sin(t * 21.0)
            + 7.0 * math.cos(t * 37.0)
        ) * (0.25 + 0.75 * env)
        r_mid = 0.5 * (r_inner + r_outer) + 18.0 * math.sin(t * 17.0)
        v_in = bm_hills.verts.new((r_inner * ca, r_inner * sa, g(r_inner * sa) - 2.0))
        v_pk = bm_hills.verts.new((r_mid * ca, r_mid * sa, g(r_mid * sa) + max(6.0, h_peak)))
        v_out = bm_hills.verts.new((r_outer * ca, r_outer * sa, g(r_outer * sa) - 4.0))
        if prev_in is not None:
            bm_hills.faces.new((prev_in, v_in, v_pk, prev_peak))
            bm_hills.faces.new((prev_peak, v_pk, v_out, prev_out))
        prev_in, prev_peak, prev_out = v_in, v_pk, v_out

    # Mediterranean: level water south-east of the site (plan -Y), meeting the edge of the ground plane
    sea_z = g(-R) - 0.35
    add_box(bm_sea, (250.0, -R - 400.0, sea_z - 0.15), (2200.0, 820.0, 0.3))

    C.finalize_surface(bm_asphalt, "Eixample_Streets", mats["asphalt"], uv_scale=0.05)
    C.finalize_surface(bm_panot, "Eixample_Sidewalks", mats["panot_paving"], uv_scale=0.35)
    C.finalize_surface(bm_grass, "Eixample_ParkLawns", mats["grass_park"], uv_scale=0.10)
    C.finalize_surface(bm_stone, "Eixample_PondBasin", mats["sandstone_warm"], uv_scale=0.25)
    finalize_bmesh_object(bm_facade_ochre, "Eixample_BuildingsOchre", mats["eixample_facade"], smooth=False, uv_scale=0.045)
    finalize_bmesh_object(bm_facade_terra, "Eixample_BuildingsTerra", mats["eixample_facade_terra"], smooth=False, uv_scale=0.045)
    finalize_bmesh_object(bm_facade_cream, "Eixample_BuildingsCream", mats["eixample_facade_cream"], smooth=False, uv_scale=0.045)
    finalize_bmesh_object(bm_horizon_city, "Eixample_DistantCity", mats["eixample_facade_cream"], smooth=False, uv_scale=0.04, bake_ao=False)
    finalize_bmesh_object(bm_roof, "Eixample_Roofs", mats["eixample_terracotta"], smooth=False, uv_scale=0.08)
    finalize_bmesh_object(bm_iron, "Eixample_BalconiesIron", mats["iron_dark"], smooth=False, uv_scale=0.25, bake_ao=False)
    finalize_bmesh_object(bm_awning, "Eixample_ShopAwnings", mats["carpet_crimson"], smooth=False, uv_scale=0.25, bake_ao=False)
    finalize_bmesh_object(bm_hills, "Barcelona_HorizonHills", mats["horizon_hills"], smooth=True, uv_scale=0.015, bake_ao=False)
    finalize_bmesh_object(bm_sea, "Barcelona_MediterraneanSea", mats["mediterranean_sea"], smooth=True, uv_scale=0.02, bake_ao=False)

    # ── 7. Instanced trees and lamps, every one standing on ground_z(y) ──
    m_plane_t, m_plane_l = create_tree_mesh("Tree_Plane", mats["tree_bark"], mats["foliage_park"], kind="plane")
    m_street_t, m_street_l = create_tree_mesh("Tree_PlaneStreet", mats["tree_bark"], mats["foliage_park"], kind="street")
    m_cyp_t, m_cyp_l = create_tree_mesh("Tree_Cypress", mats["tree_bark"], mats["foliage_cypress"], kind="cypress")
    m_lamp_p, m_lamp_g = create_lamp_mesh(mats["iron_dark"], mats["candle_glow"])

    def z_at(x: float, y: float) -> float:
        return g(y) + (0.08 if C.on_lawn(x, y) else 0.0) - 0.05

    idx = 0
    for tx, ty in C.PARK_PLANE_TREES:
        sc = 0.9 + ((idx * 37) % 10) * 0.025
        place_pair("PlaneTree", idx, m_plane_t, m_plane_l, (tx, ty, z_at(tx, ty)), scale=sc, rot_z=idx * 1.1)
        idx += 1
    for tx, ty, street in C.street_tree_positions():
        sc = 0.92 + ((idx * 29) % 7) * 0.025
        if street in ("mallorca", "provenca"):
            sc = min(sc, 0.85)   # 3.7 m from the building line: keep the crowns off the cloister / corner-building faces
        place_pair("PlaneTree", idx, m_street_t, m_street_l, (tx, ty, z_at(tx, ty)), scale=sc, rot_z=idx * 0.9)
        idx += 1

    for k, (tx, ty) in enumerate(C.CYPRESSES):
        place_pair("CypressTree", k, m_cyp_t, m_cyp_l, (tx, ty, z_at(tx, ty)), scale=1.0, rot_z=k * 0.7)

    lamps = [(x, y) for x, y, _ in C.street_lamp_positions()] + C.PLAZA_LAMPS
    for k, (lx, ly) in enumerate(lamps):
        place_pair("StreetLamp", k, m_lamp_p, m_lamp_g, (lx, ly, g(ly)))

    for (x, y) in C.PARK_PLANE_TREES + C.CYPRESSES + lamps:
        assert not C.in_keep_clear(x, y), (x, y)

    export_glb(os.path.join(MODEL_DIR, "eixample.glb"))


if __name__ == "__main__":
    build_eixample()
