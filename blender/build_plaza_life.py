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
    """Anatomically accurate Barcelona 'Banc Romàntic' wooden-slat park bench with continuous cast-iron scroll frames.
    Faces +Y (front edge at y=+0.24, slanted backrest from y=-0.20 to y=-0.34, zero floating slats or armrests!).
    """
    bm_w = bmesh.new()
    bm_i = bmesh.new()

    # 1. Ergonomic Contoured Wooden Seat Slats (4 dense flush oak planks, Z ≈ 0.44m, facing +Y)
    seat_slats = [
        (0.21, 0.445, -0.06),   # Rolled front knee lip
        (0.08, 0.455, -0.02),
        (-0.05, 0.448, 0.02),
        (-0.18, 0.436, 0.06),
    ]
    for sy, sz, tilt_x in seat_slats:
        add_box(bm_w, (0.0, sy, sz), (2.16, 0.105, 0.036), rot_euler=(tilt_x, 0.0, 0.0))

    # 2. Angled Wooden Backrest Slats (4 flush planks leaning cleanly back at 14° along the iron spine!)
    back_tilt = 0.24  # ~14° ergonomic recline toward -Y
    for k in range(4):
        s_dist = 0.16 + k * 0.125
        by = -0.21 - math.sin(back_tilt) * s_dist
        bz = 0.45 + math.cos(back_tilt) * s_dist
        add_box(bm_w, (0.0, by, bz), (2.16, 0.036, 0.098), rot_euler=(back_tilt, 0.0, 0.0))

    # 3. 3 Continuous Cast-Iron Frame Legs & Scroll Armrests (every slat & armrest solidly bolted to iron!)
    for lx in (-0.88, 0.0, 0.88):
        # Front leg (from ground Z=0.0 cleanly up to seat underside Z=0.44; outer legs continue up to Z=0.64 armrest!)
        front_top = 0.64 if lx != 0.0 else 0.43
        add_cylinder(bm_i, Vector((lx, 0.21, 0.0)), Vector((lx, 0.19, front_top)), 0.032, 0.028, segments=8)
        # Rear leg (slightly splayed backward from Z=0.0 up to seat junction at y=-0.21, Z=0.44)
        add_cylinder(bm_i, Vector((lx, -0.27, 0.0)), Vector((lx, -0.21, 0.44)), 0.034, 0.030, segments=8)
        # Inclined backrest iron spine following EXACT back_tilt angle right behind the wooden backrest slats!
        p_spine_bot = Vector((lx, -0.225, 0.43))
        p_spine_top = Vector((lx, -0.225 - math.sin(back_tilt) * 0.56, 0.43 + math.cos(back_tilt) * 0.56))
        add_cylinder(bm_i, p_spine_bot, p_spine_top, 0.028, 0.024, segments=8)
        # Horizontal seat cradle bar solidly supporting all 4 seat slats
        add_cylinder(bm_i, Vector((lx, 0.22, 0.425)), Vector((lx, -0.22, 0.415)), 0.028, 0.028, segments=8)
        # Lower leg cross-brace for structural realism
        add_cylinder(bm_i, Vector((lx, 0.19, 0.16)), Vector((lx, -0.24, 0.16)), 0.020, 0.020, segments=6)
        # Ground foot pads resting flat on Z = 0.0
        add_box(bm_i, (lx, 0.21, 0.015), (0.09, 0.10, 0.03))
        add_box(bm_i, (lx, -0.27, 0.015), (0.09, 0.10, 0.03))
        # Outer armrests solidly bridging front upright (y=0.19, Z=0.64) directly into backrest spine (y=-0.27, Z=0.64)!
        if lx != 0.0:
            add_cylinder(bm_i, Vector((lx, 0.21, 0.64)), Vector((lx, -0.27, 0.64)), 0.028, 0.026, segments=8)
            add_cylinder(bm_i, Vector((lx, 0.21, 0.64)), Vector((lx, 0.24, 0.61)), 0.026, 0.022, segments=6)

    # Longitudinal under-seat cast-iron stretcher bar linking all 3 legs
    add_cylinder(bm_i, Vector((-0.88, -0.02, 0.34)), Vector((0.88, -0.02, 0.34)), 0.022, 0.022, segments=8)

    apply_box_uv(bm_w, scale=0.65)
    bake_bvh_vertex_ao(bm_w, max_dist=1.2, min_ao=0.58)
    apply_box_uv(bm_i, scale=0.65)
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


def add_barcelona_taxi(
    bm_iron: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
    bm_glow: bmesh.types.BMesh,
    cx: float,
    cy: float,
    rot_z: float = 0.0,
) -> None:
    """Iconic black-and-yellow Barcelona taxi parked along Carrer de la Marina / Sardenya!"""
    # Black body + yellow doors/side stripes (Barcelona's unmistakable taxi livery!)
    add_box(bm_iron, (cx, cy, 0.42), (1.85, 4.4, 0.68), rot_euler=(0, 0, rot_z))
    add_box(bm_gold, (cx, cy, 0.44), (1.90, 2.2, 0.56), rot_euler=(0, 0, rot_z))
    # Cabin roof + glowing green/amber roof taxi sign
    add_box(bm_iron, (cx, cy - 0.15, 1.05), (1.62, 2.15, 0.62), rot_euler=(0, 0, rot_z))
    add_box(bm_glow, (cx, cy, 1.44), (0.42, 0.24, 0.18), rot_euler=(0, 0, rot_z))
    # Warm headlights
    ca, sa = math.cos(rot_z), math.sin(rot_z)
    for dx in (-0.65, 0.65):
        hx = cx + dx * ca - 2.22 * sa
        hy = cy + dx * sa + 2.22 * ca
        add_box(bm_glow, (hx, hy, 0.48), (0.28, 0.10, 0.16), rot_euler=(0, 0, rot_z))


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

    # ── 2. Instanced Barcelona Park Benches around Pond, Plazas & Promenades (all solidly on Panot sidewalks!) ──
    m_bw, m_bi = create_barcelona_bench_meshes(mats["wood_pew"], mats["iron_dark"])
    benches: list[tuple[float, float, float]] = [
        # Plaça de Gaudí West rim (facing East toward the reflective pond)
        (65.0, -10.5, -math.pi * 0.5), (65.0, -3.5, -math.pi * 0.5),
        (65.0, 3.5, -math.pi * 0.5), (65.0, 10.5, -math.pi * 0.5),
        # Plaça de Gaudí East rim (facing West across the pond toward the Nativity Facade!)
        (100.2, -10.5, math.pi * 0.5), (100.2, -3.5, math.pi * 0.5),
        (100.2, 3.5, math.pi * 0.5), (100.2, 10.5, math.pi * 0.5),
        # North & South pond promenade rims (facing inward toward pond & fountain)
        (75.0, -19.8, 0.0), (82.5, -19.8, 0.0), (90.0, -19.8, 0.0),
        (75.0, 19.8, math.pi), (82.5, 19.8, math.pi), (90.0, 19.8, math.pi),
        # Plaça de la Sagrada Família (West park facing Passion Facade)
        (-65.5, -10.0, -math.pi * 0.5), (-65.5, 0.0, -math.pi * 0.5), (-65.5, 10.0, -math.pi * 0.5),
        (-86.0, -12.0, 0.0), (-86.0, 12.0, math.pi),
        (-102.0, -10.0, -math.pi * 0.5), (-102.0, 10.0, -math.pi * 0.5),
        # Temple Island South Glory Promenade (sits solidly on Z=0.0 Panot sidewalk at Y=-58.5, facing North toward Glory Facade!)
        (-28.0, -58.5, 0.0), (-22.0, -58.5, 0.0), (22.0, -58.5, 0.0), (28.0, -58.5, 0.0),
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
        add_box(bm_white, (53.5, off, -0.115), (7.5, 0.55, 0.03))
        add_box(bm_white, (-53.5, off, -0.115), (7.5, 0.55, 0.03))
        add_box(bm_white, (off, 60.0, -0.115), (0.55, 7.5, 0.03))
        add_box(bm_white, (off, -78.0, -0.115), (0.55, 7.5, 0.03))

    # Iconic Black-and-Yellow Barcelona Taxis along Carrer de la Marina (East) & Carrer de Sardenya (West)!
    for tx, ty, tr in (
        (51.8, -26.0, 0.0),
        (51.8, -34.0, 0.0),
        (55.4, 24.0, math.pi),
        (-51.8, 22.0, math.pi),
        (-55.4, -22.0, 0.0),
        (16.0, 56.5, math.pi * 0.5),
    ):
        add_barcelona_taxi(bm_iron, bm_gold, bm_glow, tx, ty, rot_z=tr)

    # Sculpted stone tree grates (Baumscheiben) framing the avenue plane trees
    for tx, ty in (
        (45, -45), (45, -24), (45, 24), (45, 45),
        (-45, -45), (-45, -24), (-45, 24), (-45, 45),
    ):
        add_box(bm_iron, (tx, ty, 0.02), (2.2, 2.2, 0.06))

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
