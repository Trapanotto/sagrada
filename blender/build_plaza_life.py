"""Build the Barcelona street furniture of the site on the true plan (layout.py section 12): pond
fountain, benches, kiosks, pergolas, drinking fountains, wayfinding totems, planters, bollards,
crosswalks and lane markings, taxis and tree grates. Everything stands on the sloped ground
layout.ground_z(y) (carriageway items CURB_HEIGHT lower) and nothing enters layout.KEEP_CLEAR."""

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
ROAD = -L.CURB_HEIGHT


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


def add_kiosk(bm_kiosk, bm_gold, bm_glow, cx: float, cy: float, rot_z: float = 0.0) -> None:
    """Classic Barcelona green cast-iron newspaper/info pavilion kiosk (base sunk into the slope)."""
    z = g(cy) - 0.06
    add_box(bm_kiosk, (cx, cy, z + 0.55), (4.2, 2.8, 1.1), rot_euler=(0, 0, rot_z))
    add_box(bm_glow, (cx, cy, z + 1.85), (3.7, 2.3, 1.45), rot_euler=(0, 0, rot_z))
    ca, sa = math.cos(rot_z), math.sin(rot_z)
    for dx in (-1.95, 1.95):
        for dy in (-1.25, 1.25):
            px = cx + dx * ca - dy * sa
            py = cy + dx * sa + dy * ca
            add_cylinder(bm_kiosk, Vector((px, py, g(py) - 0.05)), Vector((px, py, z + 2.85)), 0.11, 0.09, segments=8)
    add_box(bm_kiosk, (cx, cy, z + 2.95), (5.1, 3.6, 0.28), rot_euler=(0, 0, rot_z))
    add_box(bm_kiosk, (cx, cy, z + 3.32), (3.8, 2.4, 0.48), rot_euler=(0, 0, rot_z))
    add_cylinder(bm_gold, Vector((cx, cy, z + 3.55)), Vector((cx, cy, z + 4.35)), 0.14, 0.03, segments=8)


def add_pergola(bm_iron, bm_wood, cx: float, cy: float, length: float = 14.0, width: float = 4.2) -> None:
    """Mediterranean park timber-and-iron shade pergola running along y; the roof stays level, the
    posts follow the slope."""
    z_roof = g(cy - length * 0.5) + 3.4
    cols = 4
    for i in range(cols):
        y = cy - length * 0.5 + i * (length / (cols - 1))
        for sx in (-1, 1):
            x = cx + sx * width * 0.48
            add_cylinder(bm_iron, Vector((x, y, g(y) - 0.05)), Vector((x, y, z_roof)), 0.12, 0.10, segments=8)
        add_box(bm_iron, (cx, y, z_roof + 0.02), (width + 0.5, 0.18, 0.22))
    for k in range(18):
        y = cy - length * 0.5 + k * (length / 17.0)
        add_box(bm_wood, (cx, y, z_roof + 0.22), (width + 0.8, 0.14, 0.16))


def add_wayfinding_totem(bm_iron, bm_gold, cx: float, cy: float, rot_z: float = 0.0) -> None:
    """Bronze/iron tourist map monolith anchored to the sloped sidewalk."""
    z = g(cy) - 0.05
    add_box(bm_iron, (cx, cy, z + 1.35), (0.95, 0.16, 2.7), rot_euler=(0, 0, rot_z))
    add_box(bm_gold, (cx, cy, z + 1.65), (0.82, 0.20, 1.35), rot_euler=(0, 0, rot_z))


def add_canaletes_fountain(bm_kiosk, bm_gold, cx: float, cy: float) -> None:
    """Iconic Barcelona cast-iron drinking fountain (Font de Canaletes style)."""
    z = g(cy) - 0.03
    add_cylinder(bm_kiosk, Vector((cx, cy, z)), Vector((cx, cy, z + 0.35)), 0.42, 0.30, segments=10)
    add_cylinder(bm_kiosk, Vector((cx, cy, z + 0.35)), Vector((cx, cy, z + 1.35)), 0.22, 0.16, segments=10)
    add_cylinder(bm_kiosk, Vector((cx, cy, z + 1.35)), Vector((cx, cy, z + 2.65)), 0.11, 0.07, segments=8)
    add_cylinder(bm_gold, Vector((cx, cy, z + 2.60)), Vector((cx, cy, z + 3.05)), 0.24, 0.16, segments=8)


def add_barcelona_taxi(bm_iron, bm_gold, bm_glow, cx: float, cy: float, rot_z: float = 0.0) -> None:
    """Black-and-yellow Barcelona taxi on 4 wheels resting on the carriageway (ground_z - curb).
    Local frame: length along y."""
    z_road = g(cy) + ROAD
    ca, sa = math.cos(rot_z), math.sin(rot_z)
    for dx in (-0.84, 0.84):
        for dy in (-1.35, 1.35):
            zw = g(cy + dx * sa + dy * ca) + ROAD + 0.30
            wx0 = cx + (dx - 0.10) * ca - dy * sa
            wy0 = cy + (dx - 0.10) * sa + dy * ca
            wx1 = cx + (dx + 0.10) * ca - dy * sa
            wy1 = cy + (dx + 0.10) * sa + dy * ca
            add_cylinder(bm_iron, Vector((wx0, wy0, zw)), Vector((wx1, wy1, zw)), 0.30, 0.30, segments=10)
    add_box(bm_iron, (cx, cy, z_road + 0.54), (1.85, 4.4, 0.64), rot_euler=(0, 0, rot_z))
    add_box(bm_gold, (cx, cy, z_road + 0.56), (1.90, 2.2, 0.52), rot_euler=(0, 0, rot_z))
    add_box(bm_iron, (cx + 0.15 * sa, cy - 0.15 * ca, z_road + 1.14), (1.62, 2.15, 0.60), rot_euler=(0, 0, rot_z))
    add_box(bm_glow, (cx, cy, z_road + 1.52), (0.42, 0.24, 0.18), rot_euler=(0, 0, rot_z))
    for dx in (-0.65, 0.65):
        hx = cx + dx * ca - 2.22 * sa
        hy = cy + dx * sa + 2.22 * ca
        add_box(bm_glow, (hx, hy, z_road + 0.60), (0.28, 0.10, 0.16), rot_euler=(0, 0, rot_z))


def _carriageway(name: str) -> tuple[str, float, float]:
    """(axis, near edge, far edge) of a street's carriageway: the street band minus both sidewalks."""
    axis, c, hw = L.STREETS[name]
    return axis, c - hw + L.SIDEWALK_WIDTH, c + hw - L.SIDEWALK_WIDTH


def crosswalks() -> list[tuple[str, float, float, float]]:
    """Zebra crossings at the four corners of the basilica block, where each street meets the
    straight kerb just short of the Cerdà chamfer: (street, position along it, carriageway a0, a1)."""
    b = L.SAGRADA_BLOCK
    out = []
    ys = (b["y1"] - b["chamfer"] - 1.5, b["y0"] + b["chamfer"] + 1.5)
    xs = (b["x1"] - b["chamfer"] - 1.5, b["x0"] + b["chamfer"] + 1.5)
    for street in ("marina", "sardenya"):
        _, a0, a1 = _carriageway(street)
        out += [(street, y, a0, a1) for y in ys]
    for street in ("provenca", "mallorca"):
        _, a0, a1 = _carriageway(street)
        out += [(street, x, a0, a1) for x in xs]
    return out


# Furniture positions (plan x, y[, rotation]); EST, this package. Bench local front = +Y.
BENCHES = [
    # Plaça de Gaudí, east bank (spawn): facing west across the water to the Nativity façade
    (156.6, -16.0, math.pi * 0.5), (156.6, -10.0, math.pi * 0.5), (156.6, 6.0, math.pi * 0.5), (156.6, 12.0, math.pi * 0.5),
    # north and south bank promenades, facing the pond
    (105.0, 26.6, math.pi), (119.0, 26.6, math.pi), (133.0, 26.6, math.pi), (147.0, 26.6, math.pi),
    (105.0, -30.4, 0.0), (119.0, -30.4, 0.0), (133.0, -30.4, 0.0), (147.0, -30.4, 0.0),
    # Nativity forecourt, facing the façade
    (60.5, -19.0, math.pi * 0.5), (60.5, 19.0, math.pi * 0.5),
    # Plaça de la Sagrada Família: facing the Passion façade, and along the central path
    (-89.0, -13.0, -math.pi * 0.5), (-89.0, -7.0, -math.pi * 0.5), (-89.0, 7.0, -math.pi * 0.5), (-89.0, 13.0, -math.pi * 0.5),
    (-121.0, 6.0, math.pi), (-121.0, -8.0, 0.0), (-157.0, 4.0, math.pi), (-157.0, -6.0, 0.0),
]
KIOSKS = [(160.5, -45.0, 0.35), (-112.0, 46.0, -0.35)]
PERGOLAS = [(179.0, -2.0), (-171.0, -1.0)]
DRINKING_FOUNTAINS = [(154.5, -25.0), (-90.0, 21.0)]
TOTEMS = [(48.5, 21.0, math.pi * 0.5), (48.5, -21.0, math.pi * 0.5), (-61.0, 26.0, math.pi * 0.5), (-61.0, -26.0, math.pi * 0.5),
          (54.0, -63.0, 0.0), (-54.0, -63.0, 0.0)]
PLANTERS = [(63.5, 16.0), (63.5, -16.0), (64.0, 44.0), (64.0, -46.0),
            (-62.0, 32.0), (-62.0, -32.0), (-62.0, 40.0), (-62.0, -40.0),
            (27.5, -61.7), (-27.5, -61.7), (45.0, -61.7), (-45.0, -61.7)]
TAXIS = [(73.5, -28.0, 0.0), (79.5, 24.0, math.pi), (-73.5, 18.0, math.pi), (-77.5, -32.0, 0.0),
         (-31.0, -70.0, -math.pi * 0.5),      # Carrer de Mallorca, about to pass under the Glory bridge (passage kept free)
         (34.0, 62.5, -math.pi * 0.5)]

# Top of the fountain jet nozzle above the pond water (old model: 2.05 over water 0.16). The runtime
# FountainParticles emitter belongs at plan (FOUNTAIN.x, FOUNTAIN.y, POND_WATER_Z + 1.89).
FOUNTAIN_NOZZLE_ABOVE_WATER = 1.89


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

    # ── 1. Fountain in the Plaça de Gaudí pond (layout.FOUNTAIN), heights relative to the water ──
    fx, fy, w = L.FOUNTAIN["x"], L.FOUNTAIN["y"], L.POND_WATER_Z
    fr = L.FOUNTAIN["r"]
    add_cylinder(bm_stone, Vector((fx, fy, w - 0.71)), Vector((fx, fy, w + 0.09)), fr + 0.15, fr - 0.25, segments=16)
    add_cylinder(bm_stone, Vector((fx, fy, w + 0.09)), Vector((fx, fy, w + 0.99)), 0.95, 0.65, segments=12)
    add_cylinder(bm_stone, Vector((fx, fy, w + 0.94)), Vector((fx, fy, w + 1.32)), 0.72, 1.85, segments=16)
    add_cylinder(bm_gold, Vector((fx, fy, w + 1.29)), Vector((fx, fy, w + FOUNTAIN_NOZZLE_ABOVE_WATER)), 0.26, 0.10, segments=10)

    # ── 2. Benches (instanced), all on ground_z ──
    m_bw, m_bi = create_barcelona_bench_meshes(mats["wood_pew"], mats["iron_dark"])
    for idx, (bx, by, brot) in enumerate(BENCHES):
        for suffix, mesh in (("W", m_bw), ("I", m_bi)):
            obj = bpy.data.objects.new(f"Bench_{idx}_{suffix}", mesh)
            obj.location = (bx, by, g(by) - 0.02)
            obj.rotation_euler = (0.0, 0.0, brot)
            bpy.context.collection.objects.link(obj)

    # ── 3. Kiosks, pergolas, drinking fountains, totems ──
    for kx, ky, kr in KIOSKS:
        add_kiosk(bm_kiosk, bm_gold, bm_glow, kx, ky, rot_z=kr)
    for px, py in PERGOLAS:
        add_pergola(bm_iron, bm_wood, px, py, length=16.0, width=4.4)
    for dx, dy in DRINKING_FOUNTAINS:
        add_canaletes_fountain(bm_kiosk, bm_gold, dx, dy)
    for tx, ty, tr in TOTEMS:
        add_wayfinding_totem(bm_iron, bm_gold, tx, ty, rot_z=tr)

    # ── 4. Stone planter urns with shrubs ──
    for px, py in PLANTERS:
        z = g(py) - 0.04
        add_cylinder(bm_stone, Vector((px, py, z)), Vector((px, py, z + 0.85)), 0.72, 0.92, segments=10)
        ret = bmesh.ops.create_icosphere(bm_shrub, subdivisions=2, radius=0.95)
        for v in ret["verts"]:
            v.co += Vector((px, py, z + 1.35))

    # ── 5. Bollards on the forecourt kerbs (Marina / Sardenya), crosswalks, lane markings ──
    kerb_e = L.BLOCK_LINE_EAST + L.SIDEWALK_WIDTH - 0.35
    kerb_w = L.BLOCK_LINE_WEST - L.SIDEWALK_WIDTH + 0.35
    # staggered so the façade axes (y = 0) stay open between two posts
    bollards = [(kerb_e, float(y)) for y in range(-14, 15, 4)] + [(kerb_w, float(y)) for y in range(-21, 22, 6)]
    for bx, by in bollards:
        add_cylinder(bm_iron, Vector((bx, by, g(by) - 0.05)), Vector((bx, by, g(by) + 0.92)), 0.09, 0.08, segments=8)

    zebra = []
    for street, pos, a0, a1 in crosswalks():
        axis = L.STREETS[street][0]
        k = int((a1 - a0 - 0.5) // 1.0)
        for i in range(k + 1):
            t = a0 + 0.5 + i * (a1 - a0 - 1.0) / k
            if axis == "x":       # street runs along y: stripes along y, stacked across x
                C.add_quad(bm_white, t, pos, 0.5, 4.0, 0.0, ROAD + 0.012)
            else:
                C.add_quad(bm_white, pos, t, 4.0, 0.5, 0.0, ROAD + 0.012)
        zebra.append((street, pos))

    # dashed lane lines (Eixample streets are one-way, several lanes): two lines per street inside the walk bounds
    wb = L.WALK_BOUNDS
    for street in ("marina", "sardenya", "provenca", "mallorca"):
        axis, a0, a1 = _carriageway(street)
        span = (wb["y0"], wb["y1"]) if axis == "x" else (wb["x0"], wb["x1"])
        cross = [(c - hw, c + hw) for _nm, (ax, c, hw) in L.STREETS.items() if ax != axis]
        for frac in (1.0 / 3.0, 2.0 / 3.0):
            lane = a0 + (a1 - a0) * frac
            s = span[0] + 2.0
            while s < span[1] - 3.0:
                m = s + 1.5
                blocked = any(lo - 2.0 < m < hi + 2.0 for lo, hi in cross)
                blocked = blocked or any(st == street and abs(m - p) < 4.0 for st, p in zebra)
                if not blocked:
                    if axis == "x":
                        C.add_quad(bm_white, lane, m, 0.15, 3.0, 0.0, ROAD + 0.01)
                    else:
                        C.add_quad(bm_white, m, lane, 3.0, 0.15, 0.0, ROAD + 0.01)
                s += 10.0

    # ── 6. Taxis on the carriageways ──
    for tx, ty, tr in TAXIS:
        add_barcelona_taxi(bm_iron, bm_gold, bm_glow, tx, ty, rot_z=tr)

    # ── 7. Iron tree grates under every tree that stands in paving ──
    trees = [(x, y) for x, y, _ in C.street_tree_positions()] + list(C.PARK_PLANE_TREES)
    for tx, ty in trees:
        if not C.on_lawn(tx, ty):
            add_box(bm_iron, (tx, ty, g(ty) - 0.01), (1.5, 1.5, 0.05))

    # nothing may stand on the building's ground (cloister, corner buildings, Assumption chapel,
    # transept stairs, Glory bridge and stair)
    for item in BENCHES + KIOSKS + PERGOLAS + DRINKING_FOUNTAINS + TOTEMS + PLANTERS + bollards:
        assert not C.in_keep_clear(item[0], item[1], 0.5), item

    finalize_bmesh_object(bm_stone, "Plaza_FountainAndPlanters", mats["sandstone_warm"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_kiosk, "Plaza_BarcelonaKiosks", mats["kiosk_green"], smooth=False, uv_scale=0.30)
    finalize_bmesh_object(bm_iron, "Plaza_BollardsAndPergolaIron", mats["iron_dark"], smooth=True, uv_scale=0.40)
    finalize_bmesh_object(bm_wood, "Plaza_PergolaWood", mats["wood_pew"], smooth=False, uv_scale=0.35)
    finalize_bmesh_object(bm_gold, "Plaza_BrassAccents", mats["gold_accent"], smooth=True, uv_scale=0.40)
    finalize_bmesh_object(bm_glow, "Plaza_KioskGlow", mats["candle_glow"], smooth=False, uv_scale=0.40, bake_ao=False)
    finalize_bmesh_object(bm_shrub, "Plaza_PlanterShrubs", mats["foliage_park"], smooth=True, uv_scale=0.40)
    C.finalize_surface(bm_white, "Plaza_Crosswalks", mats["road_white"], uv_scale=0.20, bake_ao=False)

    export_glb(os.path.join(MODEL_DIR, "plaza_life.glb"))


if __name__ == "__main__":
    build_plaza_life()
