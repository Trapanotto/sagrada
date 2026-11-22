"""Build the surrounding Barcelona Eixample district: plazas, Plaça de Gaudí pond basin, trees, lamps & chamfered blocks."""

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
    Z_STREET,
    add_box,
    add_cylinder,
    apply_box_uv,
    bake_bvh_vertex_ao,
    export_glb,
    finalize_bmesh_object,
    get_materials,
    reset_scene,
)


def add_chamfered_eixample_block(
    bm_wall: bmesh.types.BMesh,
    bm_roof: bmesh.types.BMesh,
    bm_iron: bmesh.types.BMesh,
    bm_awning: bmesh.types.BMesh,
    cx: float,
    cy: float,
    w: float = 72.0,
    d: float = 72.0,
    h: float = 22.0,
    chamfer: float = 12.0,
    courtyard_inset: float = 16.0,
    add_street_detail: bool = False,
) -> None:
    """Authentic Ildefons Cerdà Barcelona Eixample octagonal chamfered apartment block with 3D balconies & shop awnings."""
    hw, hd = w * 0.5, d * 0.5
    c = min(chamfer, hw * 0.45, hd * 0.45)

    outer_pts = [
        (cx - hw + c, cy - hd),
        (cx + hw - c, cy - hd),
        (cx + hw, cy - hd + c),
        (cx + hw, cy + hd - c),
        (cx + hw - c, cy + hd),
        (cx - hw + c, cy + hd),
        (cx - hw, cy + hd - c),
        (cx - hw, cy - hd + c),
    ]
    ihw = hw - courtyard_inset
    ihd = hd - courtyard_inset
    ic = c * 0.55
    inner_pts = [
        (cx - ihw + ic, cy - ihd),
        (cx + ihw - ic, cy - ihd),
        (cx + ihw, cy - ihd + ic),
        (cx + ihw, cy + ihd - ic),
        (cx + ihw - ic, cy + ihd),
        (cx - ihw + ic, cy + ihd),
        (cx - ihw, cy + ihd - ic),
        (cx - ihw, cy - ihd + ic),
    ]

    n = len(outer_pts)
    ob = [bm_wall.verts.new((x, y, Z_STREET)) for x, y in outer_pts]
    ot = [bm_wall.verts.new((x, y, Z_STREET + h)) for x, y in outer_pts]
    ib = [bm_wall.verts.new((x, y, Z_STREET)) for x, y in inner_pts]
    it = [bm_wall.verts.new((x, y, Z_STREET + h)) for x, y in inner_pts]

    rob = [bm_roof.verts.new((x, y, Z_STREET + h + 0.05)) for x, y in outer_pts]
    rib = [bm_roof.verts.new((x, y, Z_STREET + h + 0.05)) for x, y in inner_pts]

    for i in range(n):
        ni = (i + 1) % n
        bm_wall.faces.new((ob[i], ob[ni], ot[ni], ot[i]))
        bm_wall.faces.new((ib[ni], ib[i], it[i], it[ni]))
        bm_roof.faces.new((rob[i], rob[ni], rib[ni], rib[i]))

        # Real projecting 3D wrought-iron balconies & ground-floor Catalan shop awnings on faces overlooking the basilica!
        if add_street_detail:
            p0 = Vector((outer_pts[i][0], outer_pts[i][1], 0.0))
            p1 = Vector((outer_pts[ni][0], outer_pts[ni][1], 0.0))
            edge = p1 - p0
            elen = edge.length
            if elen < 14.0:
                continue
            tang = edge.normalized()
            out_n = Vector((tang.y, -tang.x, 0.0))  # Outward normal
            rot_z = math.atan2(tang.y, tang.x)
            # Only detail the sides facing toward the Sagrada Família center (0, 0) for lean triangle budget!
            mid = (p0 + p1) * 0.5
            if out_n.dot(-mid.normalized()) < 0.25:
                continue
            # Roof cornice ledge
            add_box(bm_wall, (mid.x + out_n.x * 0.4, mid.y + out_n.y * 0.4, Z_STREET + h - 0.25), (elen + 0.4, 0.9, 0.55), rot_euler=(0, 0, rot_z))
            # Ground-floor Catalan café/shopfront awnings (Z = 3.8m)
            for k in range(3):
                frac = 0.2 + 0.3 * k
                ap = p0.lerp(p1, frac) + out_n * 1.15
                add_box(bm_awning, (ap.x, ap.y, Z_STREET + 3.8), (8.5, 2.2, 0.24), rot_euler=(0.26, 0.0, rot_z))
            # Projecting 3D wrought-iron balconies across upper floors (Z = 7.5m, 11.5m, 15.5m)
            for bz in (7.6, 11.6, 15.6):
                bp = mid + out_n * 0.65
                add_box(bm_wall, (bp.x, bp.y, Z_STREET + bz), (elen * 0.86, 1.2, 0.22), rot_euler=(0, 0, rot_z))
                bp_rail = mid + out_n * 1.22
                add_box(bm_iron, (bp_rail.x, bp_rail.y, Z_STREET + bz + 0.55), (elen * 0.86, 0.08, 0.95), rot_euler=(0, 0, rot_z))


def _add_organic_canopy_lobe(bm: bmesh.types.BMesh, center: Vector, rx: float, ry: float, rz: float, seed: float) -> None:
    """Solid organically sculpted leafy foliage cluster (zero broken paper-thin alpha quads!)."""
    ret = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    for v in ret["verts"]:
        p = v.co
        # Multi-frequency organic botanical clump wobble so canopy reads as real irregular leaves, never smooth balls!
        bump = (
            1.0
            + 0.22 * math.sin(p.x * 4.2 + seed) * math.cos(p.y * 3.9 - seed * 0.7)
            + 0.14 * math.sin(p.z * 5.1 + p.x * 3.3 + seed * 1.3)
        )
        v.co = Vector((center.x + p.x * rx * bump, center.y + p.y * ry * bump, center.z + p.z * rz * bump))


def create_tree_mesh(name: str, trunk_mat: bpy.types.Material, leaf_mat: bpy.types.Material, cypress: bool = False) -> tuple[bpy.types.Mesh, bpy.types.Mesh]:
    """Lush solid sculpted Mediterranean London Plane & Cypress trees with real CC0 bark + leafy PBR clusters."""
    bm_t = bmesh.new()
    bm_l = bmesh.new()

    if cypress:
        add_cylinder(bm_t, Vector((0, 0, 0)), Vector((0, 0, 2.8)), 0.24, 0.14, segments=8)
        # Sculpted tapered organic Mediterranean Cypress silhouette (7 overlapping fluted foliage tiers)
        for tier in range(7):
            t = tier / 6.0
            z = 2.4 + t * 8.8
            r = 1.38 * (1.0 - t * 0.78) * (0.78 + 0.22 * math.sin(t * math.pi))
            _add_organic_canopy_lobe(bm_l, Vector((0, 0, z)), r, r, 1.55 * (1.0 - t * 0.35), seed=tier * 2.1)
    else:
        # Authentic Barcelona London Plane tree: curved trunk splitting into 5 visible boughs + rich multi-cluster crown!
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
            # Secondary smaller sub-lobe for rich dappled silhouette
            off = Vector((math.cos(bi * 1.9) * 1.1, math.sin(bi * 1.9) * 1.1, 0.15))
            _add_organic_canopy_lobe(bm_l, p1 + off, rw * 0.68, rw * 0.68, rh * 0.72, seed=bi * 5.1)

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
    add_cylinder(bm_p, Vector((0, 0, 0)), Vector((0, 0, 5.2)), 0.16, 0.08, segments=8)
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


def build_eixample() -> None:
    reset_scene()
    mats = get_materials()

    bm_asphalt = bmesh.new()
    bm_panot = bmesh.new()
    bm_grass = bmesh.new()
    bm_stone = bmesh.new()
    bm_facade = bmesh.new()
    bm_roof = bmesh.new()
    bm_iron = bmesh.new()
    bm_awning = bmesh.new()

    # ── 1. Ground Street Grid (Asphalt base at Z = -0.14m so sidewalks sit slightly elevated at Z = 0.0) ──
    add_box(bm_asphalt, (0.0, 0.0, -0.34), (460.0, 460.0, 0.4))

    # ── 2. Sagrada Família Temple Island Sidewalk (Panot Barcelona tiles, Z = 0.0) ──
    # Placed around perimeter & plazas (keeping Z above -0.15 so it doesn't interfere with Crypt at Z=-5.5)
    add_box(bm_panot, (0.0, -4.0, -0.08), (94.0, 114.0, 0.16))

    # ── 3. Plaça de Gaudí (East, X = +60..+126, Y = -46..+46) with TRUE Open Sunken Pond Basin! ──
    # Frame the sidewalk around the pond opening (X = 68..97, Y = -17..+17) so the water basin is genuinely recessed!
    pond_cx, pond_cy = 82.5, 0.0
    pond_w, pond_d = 29.0, 34.0
    # West strip (X: 60..68), East strip (X: 97..126), South strip (Y: -46..-17), North strip (Y: +17..+46)
    add_box(bm_panot, (64.0, 0.0, -0.07), (8.2, 92.0, 0.14))
    add_box(bm_panot, (111.5, 0.0, -0.07), (29.2, 92.0, 0.14))
    add_box(bm_panot, (82.5, -31.5, -0.07), (29.4, 29.2, 0.14))
    add_box(bm_panot, (82.5, 31.5, -0.07), (29.4, 29.2, 0.14))

    # Park lawn beds flanking the central pond & paths
    for sy in (-1, 1):
        add_box(bm_grass, (93.0, sy * 31.0, 0.02), (56.0, 22.0, 0.10))
    add_box(bm_grass, (112.0, 0.0, 0.02), (18.0, 34.0, 0.10))

    # Recessed dark stone pond basin floor (Z = -0.55m) + sculpted coping wall rising to Z = +0.36m
    add_box(bm_stone, (pond_cx, pond_cy, -0.62), (pond_w + 1.2, pond_d + 1.2, 0.25))
    add_box(bm_stone, (pond_cx, pond_cy - pond_d * 0.5, -0.09), (pond_w + 1.6, 0.90, 0.90))
    add_box(bm_stone, (pond_cx, pond_cy + pond_d * 0.5, -0.09), (pond_w + 1.6, 0.90, 0.90))
    add_box(bm_stone, (pond_cx - pond_w * 0.5, pond_cy, -0.09), (0.90, pond_d + 1.6, 0.90))
    add_box(bm_stone, (pond_cx + pond_w * 0.5, pond_cy, -0.09), (0.90, pond_d + 1.6, 0.90))

    # ── 4. Plaça de la Sagrada Família (West, X = -126..-60, Y = -46..+46) ──
    add_box(bm_panot, (-93.0, 0.0, -0.07), (66.0, 92.0, 0.14))
    for sx_off in (-16.0, 16.0):
        for sy_off in (-24.0, 24.0):
            add_box(bm_grass, (-93.0 + sx_off, sy_off, 0.02), (22.0, 28.0, 0.10))

    # ── 5. Surrounding Barcelona Eixample Chamfered Blocks (Manzanas) ──
    block_centers = [
        # North row (beyond Carrer de Provença, Y = +108)
        (-95.0, 108.0, 22.0),
        (0.0, 108.0, 24.0),
        (95.0, 108.0, 21.0),
        # South row (beyond Carrer de Mallorca & Glory Grand Staircase, Y = -118)
        (-95.0, -118.0, 23.0),
        (0.0, -124.0, 21.0),   # Set slightly back to honor the Glory Boulevard/Staircase!
        (95.0, -118.0, 22.0),
        # Far East row (beyond Plaça de Gaudí, X = +178)
        (178.0, -108.0, 22.0),
        (178.0, 0.0, 24.0),
        (178.0, 108.0, 21.0),
        # Far West row (beyond Plaça de la Sagrada Família, X = -178)
        (-178.0, -108.0, 23.0),
        (-178.0, 0.0, 22.0),
        (-178.0, 108.0, 24.0),
    ]
    for bx, by, bh in block_centers:
        add_box(bm_panot, (bx, by, -0.07), (80.0, 80.0, 0.14))
        add_chamfered_eixample_block(bm_facade, bm_roof, bm_iron, bm_awning, bx, by, w=72.0, d=72.0, h=bh, add_street_detail=True)

    finalize_bmesh_object(bm_asphalt, "Eixample_Streets", mats["asphalt"], smooth=False, uv_scale=0.05)
    finalize_bmesh_object(bm_panot, "Eixample_Sidewalks", mats["panot_paving"], smooth=False, uv_scale=0.35)
    finalize_bmesh_object(bm_grass, "Eixample_ParkLawns", mats["grass_park"], smooth=False, uv_scale=0.10)
    finalize_bmesh_object(bm_stone, "Eixample_PondBasin", mats["sandstone_warm"], smooth=False, uv_scale=0.25)
    finalize_bmesh_object(bm_facade, "Eixample_Buildings", mats["eixample_facade"], smooth=False, uv_scale=0.045)
    finalize_bmesh_object(bm_roof, "Eixample_Roofs", mats["eixample_terracotta"], smooth=False, uv_scale=0.08)
    finalize_bmesh_object(bm_iron, "Eixample_BalconiesIron", mats["iron_dark"], smooth=False, uv_scale=0.25, bake_ao=False)
    finalize_bmesh_object(bm_awning, "Eixample_ShopAwnings", mats["carpet_crimson"], smooth=False, uv_scale=0.25, bake_ao=False)

    # ── 6. Instanced Park Trees (Plane Trees & Cypresses) + Barcelona Street Lamps ──
    m_plane_t, m_plane_l = create_tree_mesh("Tree_Plane", mats["tree_bark"], mats["foliage_park"], cypress=False)
    m_cyp_t, m_cyp_l = create_tree_mesh("Tree_Cypress", mats["tree_bark"], mats["foliage_cypress"], cypress=True)
    m_lamp_p, m_lamp_g = create_lamp_mesh(mats["iron_dark"], mats["candle_glow"])

    plane_positions = [
        # Plaça de Gaudí (East Park framing the pond without blocking the classic Nativity Facade view!)
        (68, -28), (82, -32), (98, -30), (112, -26),
        (68, 28), (82, 32), (98, 30), (112, 26),
        (114, -10), (114, 10),
        # Plaça de la Sagrada Família (West Park)
        (-74, -30), (-92, -30), (-110, -28),
        (-74, 30), (-92, 30), (-110, 28),
        (-112, -10), (-112, 10),
        # Perimeter avenue trees along Marina, Sardenya & Provença
        (45, -45), (45, -24), (45, 24), (45, 45),
        (-45, -45), (-45, -24), (-45, 24), (-45, 45),
        (-30, 50), (-12, 50), (12, 50), (30, 50),
    ]
    for idx, (tx, ty) in enumerate(plane_positions):
        sc = 0.88 + ((idx * 37) % 10) * 0.03
        place_pair("PlaneTree", idx, m_plane_t, m_plane_l, (tx, ty, 0.0), scale=sc, rot_z=idx * 1.1)

    cypress_positions = [
        (66, -18), (66, 18), (100, -18), (100, 18),
        (-66, -16), (-66, 16), (-36, 46), (36, 46),
    ]
    for idx, (tx, ty) in enumerate(cypress_positions):
        place_pair("CypressTree", idx, m_cyp_t, m_cyp_l, (tx, ty, 0.0), scale=1.0, rot_z=idx * 0.7)

    lamp_positions = [
        (48, -35), (48, -14), (48, 14), (48, 35),
        (-48, -35), (-48, -14), (-48, 14), (-48, 35),
        (63, -22), (63, 22), (102, -22), (102, 22),
        (-63, -22), (-63, 22), (-102, -22), (-102, 22),
        (-24, -74), (24, -74), (-24, 54), (24, 54),
    ]
    for idx, (lx, ly) in enumerate(lamp_positions):
        place_pair("StreetLamp", idx, m_lamp_p, m_lamp_g, (lx, ly, 0.0))

    export_glb(os.path.join(MODEL_DIR, "eixample.glb"))


if __name__ == "__main__":
    build_eixample()
