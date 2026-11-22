"""Build authentic Barcelona Eixample urban furniture: benches, pond fountain, kiosks, pergolas, planters & crosswalks."""

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


def create_barcelona_bench_meshes(wood_mat: bpy.types.Material, iron_mat: bpy.types.Material) -> tuple[bpy.types.Mesh, bpy.types.Mesh]:
    """Authentic Barcelona romantic wooden-slat park bench with cast-iron scroll legs."""
    bm_w = bmesh.new()
    bm_i = bmesh.new()
    # Curved ergonomic wooden slats (seat + backrest)
    for dy, dz in ((-0.16, 0.44), (0.0, 0.46), (0.16, 0.48)):
        add_box(bm_w, (0.0, dy, dz), (2.2, 0.12, 0.045))
    for dy, dz in ((-0.26, 0.68), (-0.30, 0.84), (-0.32, 0.98)):
        add_box(bm_w, (0.0, dy, dz), (2.2, 0.05, 0.11), rot_euler=(0.18, 0.0, 0.0))
    # 3 cast-iron scroll leg frames
    for lx in (-0.95, 0.0, 0.95):
        add_box(bm_i, (lx, 0.12, 0.24), (0.07, 0.08, 0.48))
        add_box(bm_i, (lx, -0.22, 0.48), (0.07, 0.08, 0.96))
        add_box(bm_i, (lx, -0.05, 0.42), (0.07, 0.46, 0.06))
        if lx != 0.0:
            add_box(bm_i, (lx, -0.02, 0.64), (0.06, 0.42, 0.05))

    apply_box_uv(bm_w, scale=0.6)
    bake_bvh_vertex_ao(bm_w, max_dist=1.2, min_ao=0.58)
    apply_box_uv(bm_i, scale=0.6)
    mw = bpy.data.meshes.new("Mesh_BenchWood")
    mi = bpy.data.meshes.new("Mesh_BenchIron")
    bm_w.to_mesh(mw)
    bm_i.to_mesh(mi)
    bm_w.free()
    bm_i.free()
    mw.materials.append(wood_mat)
    mi.materials.append(iron_mat)
    return mw, mi


def add_kiosk(
    bm_kiosk: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
    bm_glow: bmesh.types.BMesh,
    cx: float,
    cy: float,
    rot_z: float = 0.0,
) -> None:
    """Classic Barcelona green cast-iron newspaper/info pavilion kiosk."""
    add_box(bm_kiosk, (cx, cy, Z_STREET + 0.55), (4.2, 2.8, 1.1), rot_euler=(0, 0, rot_z))
    # Illuminated warm interior showcase counter
    add_box(bm_glow, (cx, cy, Z_STREET + 1.85), (3.7, 2.3, 1.45), rot_euler=(0, 0, rot_z))
    # 4 corner cast-iron columns + overhanging modernist pagoda roof
    ca, sa = math.cos(rot_z), math.sin(rot_z)
    for dx in (-1.95, 1.95):
        for dy in (-1.25, 1.25):
            px = cx + dx * ca - dy * sa
            py = cy + dx * sa + dy * ca
            add_cylinder(bm_kiosk, Vector((px, py, Z_STREET)), Vector((px, py, Z_STREET + 2.85)), 0.11, 0.09, segments=8)
    add_box(bm_kiosk, (cx, cy, Z_STREET + 2.95), (5.1, 3.6, 0.28), rot_euler=(0, 0, rot_z))
    add_box(bm_kiosk, (cx, cy, Z_STREET + 3.32), (3.8, 2.4, 0.48), rot_euler=(0, 0, rot_z))
    add_cylinder(bm_gold, Vector((cx, cy, Z_STREET + 3.55)), Vector((cx, cy, Z_STREET + 4.35)), 0.14, 0.03, segments=8)


def add_pergola(
    bm_iron: bmesh.types.BMesh,
    bm_wood: bmesh.types.BMesh,
    cx: float,
    cy: float,
    length: float = 14.0,
    width: float = 4.2,
) -> None:
    """Mediterranean park timber-and-iron shade pergola."""
    cols = 4
    for i in range(cols):
        y = cy - length * 0.5 + i * (length / (cols - 1))
        for sx in (-1, 1):
            add_cylinder(bm_iron, Vector((cx + sx * width * 0.48, y, Z_STREET)), Vector((cx + sx * width * 0.48, y, Z_STREET + 3.4)), 0.12, 0.10, segments=8)
        add_box(bm_iron, (cx, y, Z_STREET + 3.42), (width + 0.5, 0.18, 0.22))
    # Longitudinal timber shade slats
    for k in range(18):
        y = cy - length * 0.5 + k * (length / 17.0)
        add_box(bm_wood, (cx, y, Z_STREET + 3.62), (width + 0.8, 0.14, 0.16))


def add_wayfinding_totem(bm_iron: bmesh.types.BMesh, bm_gold: bmesh.types.BMesh, cx: float, cy: float, rot_z: float = 0.0) -> None:
    """Sleek Barcelona bronze/iron tourist map & wayfinding monolith."""
    add_box(bm_iron, (cx, cy, Z_STREET + 1.35), (0.95, 0.16, 2.7), rot_euler=(0, 0, rot_z))
    add_box(bm_gold, (cx, cy, Z_STREET + 1.65), (0.82, 0.20, 1.35), rot_euler=(0, 0, rot_z))


def add_canaletes_fountain(bm_kiosk: bmesh.types.BMesh, bm_gold: bmesh.types.BMesh, cx: float, cy: float) -> None:
    """Iconic Barcelona cast-iron drinking fountain (Font de Canaletes style)."""
    add_cylinder(bm_kiosk, Vector((cx, cy, Z_STREET)), Vector((cx, cy, Z_STREET + 0.35)), 0.42, 0.30, segments=10)
    add_cylinder(bm_kiosk, Vector((cx, cy, Z_STREET + 0.35)), Vector((cx, cy, Z_STREET + 1.35)), 0.22, 0.16, segments=10)
    add_cylinder(bm_kiosk, Vector((cx, cy, Z_STREET + 1.35)), Vector((cx, cy, Z_STREET + 2.65)), 0.11, 0.07, segments=8)
    add_cylinder(bm_gold, Vector((cx, cy, Z_STREET + 2.60)), Vector((cx, cy, Z_STREET + 3.05)), 0.24, 0.16, segments=8)


def build_plaza_life() -> None:
    reset_scene()
    mats = get_materials()

    bm_stone = bmesh.new()
    bm_kiosk = bmesh.new()
    bm_iron = bmesh.new()
    bm_wood = bmesh.new()
    bm_gold = bmesh.new()
    bm_glow = bmesh.new()
    bm_shrub = bmesh.new()
    bm_white = bmesh.new()

    # ── 1. Sculpted Stone Pond Fountain Pedestal in Plaça de Gaudí Pond (X = +82.5, Y = 0.0) ──
    fx, fy = 82.5, 0.0
    add_cylinder(bm_stone, Vector((fx, fy, -0.55)), Vector((fx, fy, 0.25)), 2.8, 2.4, segments=16)
    add_cylinder(bm_stone, Vector((fx, fy, 0.25)), Vector((fx, fy, 1.15)), 0.95, 0.65, segments=12)
    add_cylinder(bm_stone, Vector((fx, fy, 1.10)), Vector((fx, fy, 1.48)), 0.72, 1.85, segments=16)  # Flared upper stone water bowl
    add_cylinder(bm_gold, Vector((fx, fy, 1.45)), Vector((fx, fy, 2.05)), 0.26, 0.10, segments=10)   # Brass fountain jet nozzle

    # ── 2. Instanced Barcelona Park Benches around Pond, Plazas & Promenades ──
    m_bw, m_bi = create_barcelona_bench_meshes(mats["wood_pew"], mats["iron_dark"])
    benches: list[tuple[float, float, float]] = [
        # Plaça de Gaudí pond promenade (facing the reflective pond & Nativity Facade!)
        (65.5, -10.0, -math.pi * 0.5), (65.5, -3.5, -math.pi * 0.5),
        (65.5, 3.5, -math.pi * 0.5), (65.5, 10.0, -math.pi * 0.5),
        (99.5, -10.0, math.pi * 0.5), (99.5, -3.5, math.pi * 0.5),
        (99.5, 3.5, math.pi * 0.5), (99.5, 10.0, math.pi * 0.5),
        (75.0, -19.5, 0.0), (82.5, -19.5, 0.0), (90.0, -19.5, 0.0),
        (75.0, 19.5, math.pi), (82.5, 19.5, math.pi), (90.0, 19.5, math.pi),
        # Plaça de la Sagrada Família (West park facing Passion Facade)
        (-66.0, -10.0, math.pi * 0.5), (-66.0, 0.0, math.pi * 0.5), (-66.0, 10.0, math.pi * 0.5),
        (-86.0, -12.0, 0.0), (-86.0, 12.0, math.pi),
        (-102.0, -10.0, -math.pi * 0.5), (-102.0, 10.0, -math.pi * 0.5),
        # South Glory Plaza flanking the grand staircase
        (-28.0, -68.0, 0.0), (-22.0, -68.0, 0.0), (22.0, -68.0, 0.0), (28.0, -68.0, 0.0),
    ]
    for idx, (bx, by, brot) in enumerate(benches):
        for suffix, mesh in (("W", m_bw), ("I", m_bi)):
            obj = bpy.data.objects.new(f"Bench_{idx}_{suffix}", mesh)
            obj.location = (bx, by, Z_STREET)
            obj.rotation_euler = (0.0, 0.0, brot)
            bpy.context.collection.objects.link(obj)

    # ── 3. Classic Barcelona Green Cast-Iron Kiosks, Pergolas, Drinking Fountains & Wayfinding Totems ──
    add_kiosk(bm_kiosk, bm_gold, bm_glow, 66.0, -37.0, rot_z=0.35)
    add_kiosk(bm_kiosk, bm_gold, bm_glow, -67.0, -35.0, rot_z=-0.35)

    add_pergola(bm_iron, bm_wood, 108.0, 28.0, length=16.0, width=4.4)
    add_pergola(bm_iron, bm_wood, -106.0, 26.0, length=16.0, width=4.4)

    add_canaletes_fountain(bm_kiosk, bm_gold, 64.5, 22.0)
    add_canaletes_fountain(bm_kiosk, bm_gold, -64.5, 22.0)

    for tx, ty, tr in (
        (46.0, 14.0, math.pi * 0.5),
        (46.0, -14.0, math.pi * 0.5),
        (-46.0, 14.0, math.pi * 0.5),
        (-46.0, -14.0, math.pi * 0.5),
        (24.0, -76.0, 0.0),
        (-24.0, -76.0, 0.0),
    ):
        add_wayfinding_totem(bm_iron, bm_gold, tx, ty, rot_z=tr)

    # ── 4. Sculpted Stone Planter Urns with Mediterranean Shrubs along Basilica Perimeter ──
    planters = [
        (42.0, -28.0), (42.0, -16.0), (42.0, 16.0), (42.0, 28.0),
        (-42.0, -28.0), (-42.0, -16.0), (-42.0, 16.0), (-42.0, 28.0),
        (-24.0, -58.0), (24.0, -58.0), (-16.0, 46.0), (16.0, 46.0),
    ]
    for px, py in planters:
        add_cylinder(bm_stone, Vector((px, py, Z_STREET)), Vector((px, py, Z_STREET + 0.85)), 0.72, 0.92, segments=10)
        ret = bmesh.ops.create_icosphere(bm_shrub, subdivisions=2, radius=0.95)
        for v in ret["verts"]:
            v.co += Vector((px, py, Z_STREET + 1.35))

    # ── 5. Wrought-Iron Sidewalk Bollards & Barcelona Street Crosswalks (Zebrastreifen) ──
    for by in range(-44, 48, 8):
        add_cylinder(bm_iron, Vector((47.2, by, Z_STREET)), Vector((47.2, by, Z_STREET + 0.92)), 0.09, 0.08, segments=8)
        add_cylinder(bm_iron, Vector((-47.2, by, Z_STREET)), Vector((-47.2, by, Z_STREET + 0.92)), 0.09, 0.08, segments=8)

    # White pedestrian crosswalk stripes spanning Carrer de Marina (+53.5), Sardenya (-53.5), Provença (+59), Mallorca (-81)
    for stripe in range(-4, 5):
        off = stripe * 1.15
        # East (Carrer de la Marina) & West (Carrer de Sardenya) crosswalks connecting plazas to basilica
        add_box(bm_white, (53.5, off, -0.115), (7.5, 0.55, 0.03))
        add_box(bm_white, (-53.5, off, -0.115), (7.5, 0.55, 0.03))
        # North (Carrer de Provença) & South (Carrer de Mallorca) crosswalks
        add_box(bm_white, (off, 60.0, -0.115), (0.55, 7.5, 0.03))
        add_box(bm_white, (off, -78.0, -0.115), (0.55, 7.5, 0.03))

    finalize_bmesh_object(bm_stone, "Plaza_FountainAndPlanters", mats["sandstone_warm"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_kiosk, "Plaza_BarcelonaKiosks", mats["kiosk_green"], smooth=False, uv_scale=0.30)
    finalize_bmesh_object(bm_iron, "Plaza_BollardsAndPergolaIron", mats["iron_dark"], smooth=True, uv_scale=0.40)
    finalize_bmesh_object(bm_wood, "Plaza_PergolaWood", mats["wood_pew"], smooth=False, uv_scale=0.35)
    finalize_bmesh_object(bm_gold, "Plaza_BrassAccents", mats["gold_accent"], smooth=True, uv_scale=0.40)
    finalize_bmesh_object(bm_glow, "Plaza_KioskGlow", mats["candle_glow"], smooth=False, uv_scale=0.40, bake_ao=False)
    finalize_bmesh_object(bm_shrub, "Plaza_PlanterShrubs", mats["foliage_park"], smooth=True, uv_scale=0.40)
    finalize_bmesh_object(bm_white, "Plaza_Crosswalks", mats["road_white"], smooth=False, uv_scale=0.20, bake_ao=False)

    export_glb(os.path.join(MODEL_DIR, "plaza_life.glb"))


if __name__ == "__main__":
    build_plaza_life()
