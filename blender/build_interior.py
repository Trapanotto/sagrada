"""Build the complete Sagrada Família interior (columns, vaults, galleries, stained glass, altar, pews)."""

from __future__ import annotations

import math
import os
import sys
import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
from common import (
    APSE_CENTER_Y,
    APSE_RADIUS,
    GRID,
    MODEL_DIR,
    NAVE_SOUTH_Y,
    TRANSEPT_X,
    Z_AISLE_VAULT,
    Z_ALTAR,
    Z_APSE_VAULT,
    Z_CROSSING_VAULT,
    Z_GALLERY,
    Z_NAVE,
    Z_NAVE_VAULT,
    add_box,
    add_branching_canopy,
    add_cylinder,
    add_gaudi_window_tracery,
    apply_box_uv,
    bake_bvh_vertex_ao,
    build_gaudi_column_bmesh,
    create_hyperboloid_vault_bay,
    export_glb,
    finalize_bmesh_object,
    get_materials,
    reset_scene,
)


def create_instanced_column_mesh(
    name: str,
    mat: bpy.types.Material,
    base_z: float,
    knot_z: float,
    radius: float,
    sides: int,
) -> bpy.types.Mesh:
    bm = bmesh.new()
    build_gaudi_column_bmesh(bm, base_z=base_z, knot_z=knot_z, radius_base=radius, sides=sides, rings=16, radial_segs=24)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    apply_box_uv(bm, scale=0.22)
    bake_bvh_vertex_ao(bm, max_dist=3.2, min_ao=0.52)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    mesh.materials.append(mat)
    return mesh


def place_instance(name: str, mesh: bpy.types.Mesh, loc: tuple[float, float, float], rot_z: float = 0.0) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    obj.rotation_euler = (0.0, 0.0, rot_z)
    bpy.context.collection.objects.link(obj)
    return obj


def build_interior() -> None:
    reset_scene()
    mats = get_materials()

    # ── 1. Marble Floor (Nave, Transepts, Apse Ambulatory, Presbytery Platform) ──
    # Exact axis-aligned rectangular cutout over the straight Crypt Stairwell (X: -21.0..-11.2, Y: +12.35..+15.25)!
    bm_floor = bmesh.new()
    # Main 5-aisle nave floor south of Crypt cutout (X: -22.8..+22.8, Y: -46.0..+12.35)
    add_box(bm_floor, (0.0, -16.825, Z_NAVE - 0.35), (45.6, 58.35, 0.7))
    # East strip beside Crypt cutout (X: -11.2..+22.8, Y: +12.35..+16.5) — clears circular High Altar with 1.1m margin!
    add_box(bm_floor, (5.8, 14.425, Z_NAVE - 0.35), (34.0, 4.15, 0.7))
    # North strip behind Crypt cutout (X: -22.8..-11.2, Y: +15.25..+16.6)
    add_box(bm_floor, (-17.0, 15.925, Z_NAVE - 0.35), (11.6, 1.35, 0.7))
    # West strip right at top of Crypt stairs (X: -22.8..-21.0, Y: +12.35..+15.25)
    add_box(bm_floor, (-21.9, 13.8, Z_NAVE - 0.35), (1.8, 2.9, 0.7))
    # East transept arm (X: +22.8..+31.2, Y: -15.2..+15.2)
    add_box(bm_floor, (27.0, 0.0, Z_NAVE - 0.35), (8.4, 30.4, 0.7))
    # West transept arm (X: -31.2..-22.8, Y: -15.2..+15.2)
    add_box(bm_floor, (-27.0, 0.0, Z_NAVE - 0.35), (8.4, 30.4, 0.7))
    # Clean horizontal sculpted marble safety balustrade guarding South, North & East edges of the open Crypt Stairwell!
    # (West side at X = -21.0 stays completely open as the walkable stair entrance!)
    add_box(bm_floor, (-16.1, 12.2, Z_NAVE + 0.50), (10.1, 0.28, 1.0))
    add_box(bm_floor, (-16.1, 15.4, Z_NAVE + 0.50), (10.1, 0.28, 1.0))
    add_box(bm_floor, (-11.1, 13.8, Z_NAVE + 0.50), (0.28, 3.48, 1.0))
    # Semicircular apse ambulatory floor (starts cleanly at Y >= 16.5, zero overlap with Crypt cutout!)
    apse_segs = 28
    top_v = []
    bot_v = []
    for i in range(apse_segs + 1):
        ang = math.pi * i / apse_segs  # 0 (East) -> pi (West) around North (+Y)
        r = APSE_RADIUS + 4.2
        px = r * math.cos(ang)
        py = APSE_CENTER_Y + r * math.sin(ang) - 6.0
        top_v.append(bm_floor.verts.new((px, py, Z_NAVE)))
        bot_v.append(bm_floor.verts.new((px, py, Z_NAVE - 0.7)))
    c_top = bm_floor.verts.new((0.0, APSE_CENTER_Y - 6.0, Z_NAVE))
    c_bot = bm_floor.verts.new((0.0, APSE_CENTER_Y - 6.0, Z_NAVE - 0.7))
    for i in range(apse_segs):
        bm_floor.faces.new((c_top, top_v[i], top_v[i + 1]))
        bm_floor.faces.new((c_bot, bot_v[i + 1], bot_v[i]))
        bm_floor.faces.new((top_v[i], bot_v[i], bot_v[i + 1], top_v[i + 1]))

    # Raised Presbytery / Altar Sanctuary Platform (stepped tiers)
    for step in range(4):
        z_s = Z_NAVE + (step + 1) * 0.30
        r_s = 10.6 - step * 0.55
        add_cylinder(
            bm_floor,
            Vector((0.0, 17.5, Z_NAVE)),
            Vector((0.0, 17.5, z_s)),
            r_s,
            r_s,
            segments=24,
            cap=True,
        )
    finalize_bmesh_object(bm_floor, "Interior_MarbleFloor", mats["floor_marble"], smooth=False, uv_scale=0.16)

    # ── 2. High Altar, Suspended Golden Baldachin & Organ ──
    bm_altar = bmesh.new()
    # Sculpted stepped porphyry altar base + monolithic mensa slab with overhang
    add_box(bm_altar, (0.0, 18.0, Z_ALTAR + 0.08), (3.85, 2.25, 0.16))
    add_box(bm_altar, (0.0, 18.0, Z_ALTAR + 0.68), (3.35, 1.72, 1.08))
    add_box(bm_altar, (0.0, 18.0, Z_ALTAR + 1.28), (3.70, 2.02, 0.12))
    add_box(bm_altar, (0.0, 18.0, Z_ALTAR + 1.40), (3.96, 2.24, 0.14))
    finalize_bmesh_object(bm_altar, "Interior_HighAltar", mats["porphyry_red"], smooth=False, uv_scale=0.35)

    bm_gold = bmesh.new()
    # Gilded antependium front relief border & brass altar cross atop High Altar
    add_box(bm_gold, (0.0, 17.12, Z_ALTAR + 0.68), (2.75, 0.06, 0.78))
    add_cylinder(bm_gold, Vector((0.0, 18.0, Z_ALTAR + 1.47)), Vector((0.0, 18.0, Z_ALTAR + 1.56)), 0.18, 0.12, segments=10)
    add_cylinder(bm_gold, Vector((0.0, 18.0, Z_ALTAR + 1.56)), Vector((0.0, 18.0, Z_ALTAR + 2.38)), 0.042, 0.032, segments=8)
    add_cylinder(bm_gold, Vector((-0.28, 18.0, Z_ALTAR + 2.12)), Vector((0.28, 18.0, Z_ALTAR + 2.12)), 0.035, 0.035, segments=8)
    # Gaudí's iconic hexagonal suspended canopy (Baldachin) at Z = 13.5m above the altar
    bal_z = 13.5
    bal_r = 5.6
    for i in range(6):
        a0 = math.pi / 3.0 * i
        a1 = math.pi / 3.0 * ((i + 1) % 6)
        p0 = Vector((bal_r * math.cos(a0), 18.0 + bal_r * math.sin(a0), bal_z))
        p1 = Vector((bal_r * math.cos(a1), 18.0 + bal_r * math.sin(a1), bal_z))
        add_cylinder(bm_gold, p0, p1, 0.22, 0.22, segments=8, cap=True)
        # Crown finials & hanging sanctuary lamps around the hexagon
        add_cylinder(bm_gold, p0, p0 + Vector((0, 0, 1.6)), 0.16, 0.04, segments=8)
        add_cylinder(bm_gold, p0, p0 - Vector((0, 0, 3.2)), 0.03, 0.03, segments=6)
        add_cylinder(bm_gold, p0 - Vector((0, 0, 3.2)), p0 - Vector((0, 0, 3.9)), 0.22, 0.12, segments=10)
        # Inner ribs to central crown
        add_cylinder(bm_gold, p0, Vector((0.0, 18.0, bal_z + 1.9)), 0.14, 0.14, segments=8)
        # Suspension cables up to the vault
        add_cylinder(bm_gold, p0 + Vector((0, 0, 0.8)), Vector((p0.x, p0.y, Z_CROSSING_VAULT - 2.0)), 0.04, 0.04, segments=6)

    # Suspended Crucifix below the baldachin
    add_cylinder(bm_gold, Vector((0.0, 18.0, bal_z - 5.2)), Vector((0.0, 18.0, bal_z - 0.6)), 0.14, 0.14, segments=8)
    add_cylinder(bm_gold, Vector((-1.6, 18.0, bal_z - 2.2)), Vector((1.6, 18.0, bal_z - 2.2)), 0.12, 0.12, segments=8)

    # Pipe Organ in the Apse Gallery (behind altar at Y = 29.5)
    for i in range(-14, 15):
        ox = i * 0.42
        h = 6.5 - abs(i) * 0.22 + (1.2 if i % 2 == 0 else 0.0)
        add_cylinder(bm_gold, Vector((ox, 30.2, Z_GALLERY + 0.5)), Vector((ox, 30.2, Z_GALLERY + 0.5 + h)), 0.11, 0.11, segments=8)

    # ── 3. Gaudí's Double-Twisted Forest of Columns (4 Stone Types) ──
    mesh_porphyry = create_instanced_column_mesh("Mesh_Col_Porphyry", mats["porphyry_red"], Z_NAVE, 20.5, 1.15, sides=12)
    mesh_basalt = create_instanced_column_mesh("Mesh_Col_Basalt", mats["basalt_dark"], Z_NAVE, 19.5, 0.86, sides=10)
    mesh_granite = create_instanced_column_mesh("Mesh_Col_Granite", mats["granite_grey"], Z_NAVE, 17.8, 0.70, sides=8)
    mesh_sandstone = create_instanced_column_mesh("Mesh_Col_Sandstone", mats["sandstone_warm"], Z_NAVE, 16.5, 0.56, sides=6)

    bm_branches = bmesh.new()

    # 3a. 4 Massive Red Porphyry Crossing Columns at (±7.5, ±7.5)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * GRID, sy * GRID
            place_instance(f"Col_Porphyry_{sx}_{sy}", mesh_porphyry, (cx, cy, 0.0))
            # Gilded tetramorph capital medallion ring
            add_cylinder(bm_gold, Vector((cx, cy, 19.8)), Vector((cx, cy, 21.4)), 1.48, 1.48, segments=16, cap=False)
            # Giant branching arms rising to the 60m crossing vault + 45m nave/transept vaults
            add_branching_canopy(bm_branches, (cx, cy), 20.8, Z_CROSSING_VAULT - 2.0, 4.4, 4, 0.62, angle_offset=math.pi / 4.0)
            add_branching_canopy(bm_branches, (cx, cy), 20.2, Z_NAVE_VAULT - 1.8, 5.2, 4, 0.48, angle_offset=0.0)

    # 3b. Dark Basalt Columns (Central Nave rows X = ±7.5, Transept rows Y = ±7.5)
    basalt_positions = []
    for bay in range(2, 7):  # Y = -15.0, -22.5, -30.0, -37.5, -45.0
        for sx in (-1, 1):
            basalt_positions.append((sx * GRID, -bay * GRID))
    for tx in (-2, -3, 2, 3):  # Transept X = ±15.0, ±22.5 at Y = ±7.5
        for sy in (-1, 1):
            basalt_positions.append((tx * GRID, sy * GRID))

    for idx, (cx, cy) in enumerate(basalt_positions):
        place_instance(f"Col_Basalt_{idx}", mesh_basalt, (cx, cy, 0.0))
        add_cylinder(bm_gold, Vector((cx, cy, 19.0)), Vector((cx, cy, 20.1)), 1.05, 1.05, segments=14, cap=False)
        add_branching_canopy(bm_branches, (cx, cy), 19.8, Z_NAVE_VAULT - 2.0, 4.2, 4, 0.44, angle_offset=math.pi / 4.0)
        # Side branches reaching toward the 30m side aisles
        add_branching_canopy(bm_branches, (cx, cy), 18.8, Z_AISLE_VAULT - 1.5, 4.0, 2, 0.36, angle_offset=0.0 if abs(cx) < 10 else math.pi / 2.0)

    # 3c. Grey Granite Columns (Inner side aisles X = ±15.0, Y = -15..-45 & Transept outer)
    granite_positions = []
    for bay in range(2, 7):
        for sx in (-1, 1):
            granite_positions.append((sx * 2.0 * GRID, -bay * GRID))
    for sx in (-1, 1):
        granite_positions.append((sx * 2.0 * GRID, 2.0 * GRID))  # North transept corners

    for idx, (cx, cy) in enumerate(granite_positions):
        place_instance(f"Col_Granite_{idx}", mesh_granite, (cx, cy, 0.0))
        add_cylinder(bm_gold, Vector((cx, cy, 17.4)), Vector((cx, cy, 18.3)), 0.85, 0.85, segments=12, cap=False)
        add_branching_canopy(bm_branches, (cx, cy), 18.1, Z_AISLE_VAULT - 1.6, 3.6, 4, 0.34, angle_offset=math.pi / 4.0)

    # 3d. Apse Ambulatory Columns (7 radial granite/porphyry columns around the sanctuary)
    for i in range(8):
        ang = math.pi * (i + 0.5) / 8.0
        cx = 11.2 * math.cos(ang)
        cy = 16.5 + 11.2 * math.sin(ang)
        place_instance(f"Col_Apse_{i}", mesh_granite, (cx, cy, 0.0), rot_z=ang)
        add_branching_canopy(bm_branches, (cx, cy), 18.2, Z_NAVE_VAULT - 2.5, 3.5, 4, 0.36, angle_offset=ang)

    # 3e. Outer Sandstone Gallery Columns along East & West Nave Walls
    for bay in range(2, 7):
        for sx in (-1, 1):
            cx, cy = sx * 21.8, -bay * GRID
            place_instance(f"Col_Wall_{sx}_{bay}", mesh_sandstone, (cx, cy, 0.0))
            add_branching_canopy(bm_branches, (cx, cy), 16.8, Z_AISLE_VAULT - 1.6, 2.6, 3, 0.28, angle_offset=math.pi if sx > 0 else 0.0)

    finalize_bmesh_object(bm_branches, "Interior_ColumnBranches", mats["sandstone_warm"], smooth=True, uv_scale=0.22)

    # ── 4. Walkable Organically Wavy Cantories (Emporen at Z = 14.5m) with OPEN Corner Stairwell Cutouts! ──
    bm_gal = bmesh.new()
    for sx in (-1, 1):
        gx = sx * 19.6
        # Stop East/West Empore slab cleanly at Y = -40.4 so the corner spiral stair at (±19.6, -42.8) has 100% open headroom!
        add_box(bm_gal, (gx, -27.4, Z_GALLERY - 0.35), (5.6, 26.0, 0.7))
        # Iconic Gaudí undulating sinusoidal wave-balustrade (swells organically outward into the nave at every 7.5m bay!)
        n_wave = 32
        y_start, y_end = -14.4, -40.4
        pts_w: list[tuple[float, float]] = []
        for k in range(n_wave + 1):
            t = k / n_wave
            wy = y_start + t * (y_end - y_start)
            # Smooth wave bulging inward toward central nave (0.44m wave amplitude synchronized with column bay rhythm)
            wave_in = 0.44 * math.sin(math.pi * (wy - y_start) / (GRID * 0.5))
            wx = sx * (16.95 - wave_in)
            pts_w.append((wx, wy))
        for k in range(n_wave):
            x0, y0 = pts_w[k]
            x1, y1 = pts_w[k + 1]
            # Sculpted wavy top stone rail, lower wave curb plinth & bulging belly fascia slab
            add_cylinder(bm_gal, Vector((x0, y0, Z_GALLERY + 1.08)), Vector((x1, y1, Z_GALLERY + 1.08)), 0.16, 0.16, segments=6, cap=False)
            add_cylinder(bm_gal, Vector((x0, y0, Z_GALLERY + 0.14)), Vector((x1, y1, Z_GALLERY + 0.14)), 0.18, 0.18, segments=6, cap=False)
            add_cylinder(bm_gal, Vector((x0, y0, Z_GALLERY - 0.25)), Vector((x1, y1, Z_GALLERY - 0.25)), 0.32, 0.32, segments=6, cap=False)
            # Paired twin slender Gothic stone colonnettes following the exact wave curve!
            xm, ym = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
            add_cylinder(bm_gal, Vector((x0, y0, Z_GALLERY + 0.22)), Vector((x0, y0, Z_GALLERY + 1.04)), 0.065, 0.055, segments=6)
            add_cylinder(bm_gal, Vector((xm, ym, Z_GALLERY + 0.22)), Vector((xm, ym, Z_GALLERY + 1.04)), 0.055, 0.050, segments=6)
        for bay in range(2, 6):
            add_box(bm_gal, (gx, -bay * GRID, Z_GALLERY - 0.9), (5.4, 0.65, 0.8))

    # South Glory Choir Gallery bridging between the two open corner stairwells (X = -17.5 .. +17.5, Y = -40.6 .. -45.4)
    add_box(bm_gal, (0.0, -43.0, Z_GALLERY - 0.35), (35.0, 4.8, 0.7))
    n_wave_s = 36
    x_s0, x_s1 = -17.4, 17.4
    pts_s: list[tuple[float, float]] = []
    for k in range(n_wave_s + 1):
        t = k / n_wave_s
        wx = x_s0 + t * (x_s1 - x_s0)
        wave_n = 0.48 * math.sin(math.pi * (wx - x_s0) / (GRID * 0.5))
        wy = -40.75 + wave_n
        pts_s.append((wx, wy))
    for k in range(n_wave_s):
        x0, y0 = pts_s[k]
        x1, y1 = pts_s[k + 1]
        add_cylinder(bm_gal, Vector((x0, y0, Z_GALLERY + 1.08)), Vector((x1, y1, Z_GALLERY + 1.08)), 0.16, 0.16, segments=6, cap=False)
        add_cylinder(bm_gal, Vector((x0, y0, Z_GALLERY + 0.14)), Vector((x1, y1, Z_GALLERY + 0.14)), 0.18, 0.18, segments=6, cap=False)
        add_cylinder(bm_gal, Vector((x0, y0, Z_GALLERY - 0.25)), Vector((x1, y1, Z_GALLERY - 0.25)), 0.32, 0.32, segments=6, cap=False)
        xm, ym = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        add_cylinder(bm_gal, Vector((x0, y0, Z_GALLERY + 0.22)), Vector((x0, y0, Z_GALLERY + 1.04)), 0.065, 0.055, segments=6)
        add_cylinder(bm_gal, Vector((xm, ym, Z_GALLERY + 0.22)), Vector((xm, ym, Z_GALLERY + 1.04)), 0.055, 0.050, segments=6)

    # 2 Walkable Gaudí Corner Helical Staircases (compact r=0.36..1.76m, ZERO overlap with columns, walls or gallery slabs!)
    bm_corner_stairs = bmesh.new()
    for sx in (-1, 1):
        scx, scy = sx * 19.6, -42.6
        n_st = 64
        turns = 2.5
        # Offset West spiral by pi so BOTH top steps finish pointing cleanly INWARD toward the South Choir Gallery (±17.5, -42.6)!
        ang_offset = 0.0 if sx > 0 else math.pi
        add_cylinder(bm_gal, Vector((scx, scy, Z_NAVE)), Vector((scx, scy, Z_GALLERY + 1.15)), 0.36, 0.34, segments=12)
        for si in range(n_st):
            t = si / (n_st - 1)
            ang = ang_offset + sx * t * turns * 2.0 * math.pi
            z_s = Z_NAVE + t * (Z_GALLERY - Z_NAVE)
            add_box(
                bm_corner_stairs,
                (scx + 1.06 * math.cos(ang), scy + 1.06 * math.sin(ang), z_s),
                (1.40, 0.56, 0.22),
                rot_euler=(0.0, 0.0, ang),
            )
        # Clean narrow top threshold landing bridging top step (X=±17.84, Y=-42.6, Z=14.5) to South Choir Gallery (X=±17.5)
        add_box(bm_gal, (sx * 17.65, -42.6, Z_GALLERY - 0.35), (0.85, 1.45, 0.7))
        # Narrow corner bridge joining East/West Empore (Y=-40.4) cleanly to South Choir Gallery (Y=-40.6) outside spiral radius
        add_box(bm_gal, (sx * 17.2, -40.5, Z_GALLERY - 0.35), (0.95, 0.70, 0.7))
    finalize_bmesh_object(bm_corner_stairs, "Interior_CornerStairs", mats["sandstone_warm"], smooth=False, uv_scale=0.18, bake_ao=False)

    # Walkable Elevated Gallery Corridor connecting East Empore (21, -14.5, 14.5m) cleanly to Nativity Gap 0-1 (30.1, -7.2, 14.5m)!
    p_g0 = Vector((21.0, -14.5, Z_GALLERY - 0.35))
    p_g1 = Vector((30.1, -7.2, Z_GALLERY - 0.35))
    g_mid = (p_g0 + p_g1) * 0.5
    g_len = (p_g1 - p_g0).length + 0.4
    g_ang = math.atan2(p_g1.y - p_g0.y, p_g1.x - p_g0.x)
    add_box(bm_gal, (g_mid.x, g_mid.y, g_mid.z), (g_len, 2.6, 0.7), rot_euler=(0, 0, g_ang))
    # Side stone parapets flanking the gallery-to-tower walkway (stops before tower gap!)
    for side in (-1, 1):
        nx = -math.sin(g_ang) * side * 1.15
        ny = math.cos(g_ang) * side * 1.15
        add_box(bm_gal, (g_mid.x + nx, g_mid.y + ny, Z_GALLERY + 0.55), (g_len - 0.4, 0.28, 1.1), rot_euler=(0, 0, g_ang))
    # Apse Organ Gallery (curved balcony behind the altar)
    for i in range(10):
        a0 = math.pi * (0.1 + 0.8 * i / 10.0)
        a1 = math.pi * (0.1 + 0.8 * (i + 1) / 10.0)
        am = 0.5 * (a0 + a1)
        r = 14.5
        seg_len = r * (a1 - a0) * 1.05
        add_box(
            bm_gal,
            (r * math.cos(am), 16.5 + r * math.sin(am), Z_GALLERY - 0.35),
            (seg_len, 3.8, 0.7),
            rot_euler=(0.0, 0.0, am - math.pi / 2.0),
        )
        add_box(
            bm_gal,
            ((r - 1.75) * math.cos(am), 16.5 + (r - 1.75) * math.sin(am), Z_GALLERY + 0.55),
            (seg_len, 0.35, 1.1),
            rot_euler=(0.0, 0.0, am - math.pi / 2.0),
        )
    finalize_bmesh_object(bm_gal, "Interior_Galleries", mats["sandstone_warm"], smooth=False, uv_scale=0.18)

    # ── 5. Hyperboloid Ceiling Vaults (30m Aisles, 45m Central Nave, 60m Crossing, Apse) ──
    bm_vault = bmesh.new()

    # 5a. Side Aisles Vaults (Z = 31.2m) — X = ±11.25 and ±18.75, Y bays -11.25 .. -41.25
    for bay_y in (-11.25, -18.75, -26.25, -33.75, -41.25):
        for sx in (-1, 1):
            create_hyperboloid_vault_bay(bm_vault, bm_gold, sx * 11.25, bay_y, Z_AISLE_VAULT, 7.5, 7.5, depth=2.6, oculus_r=0.95)
            create_hyperboloid_vault_bay(bm_vault, bm_gold, sx * 18.75, bay_y, Z_AISLE_VAULT, 7.5, 7.5, depth=2.6, oculus_r=0.95)

    # Transept Side Bays (Z = 31.2m)
    for sx in (-1, 1):
        for bx in (11.25, 18.75, 26.25):
            for sy in (-1, 1):
                create_hyperboloid_vault_bay(bm_vault, bm_gold, sx * bx, sy * 11.25, Z_AISLE_VAULT, 7.5, 7.5, depth=2.6, oculus_r=0.95)

    # 5b. Central Nave Vaults (Z = 46.2m) — 15m wide x 7.5m bays + gilded Venetian starburst palm ribs around oculi!
    for bay_y in (-11.25, -18.75, -26.25, -33.75, -41.25):
        create_hyperboloid_vault_bay(bm_vault, bm_gold, 0.0, bay_y, Z_NAVE_VAULT, 15.0, 7.5, depth=3.8, oculus_r=1.65)
        for rk in range(8):
            ra = 2.0 * math.pi * rk / 8.0
            add_cylinder(
                bm_gold,
                Vector((1.75 * math.cos(ra), bay_y + 1.75 * math.sin(ra), Z_NAVE_VAULT - 0.18)),
                Vector((3.55 * math.cos(ra), bay_y + 2.95 * math.sin(ra), Z_NAVE_VAULT - 0.62)),
                0.09,
                0.04,
                segments=5,
                cap=False,
            )

    # Central Transept Vaults (Z = 46.2m)
    for sx in (-1, 1):
        for bx in (11.25, 18.75, 26.25):
            create_hyperboloid_vault_bay(bm_vault, bm_gold, sx * bx, 0.0, Z_NAVE_VAULT, 7.5, 15.0, depth=3.8, oculus_r=1.55)

    # 5c. Central Crossing Vault (Z = 61.2m under Tower of Jesus Christ) + 12 gilded palm starburst rays!
    create_hyperboloid_vault_bay(bm_vault, bm_gold, 0.0, 0.0, Z_CROSSING_VAULT, 15.0, 15.0, depth=5.5, oculus_r=3.2, segs=24, rings=8)
    for rk in range(12):
        ra = 2.0 * math.pi * rk / 12.0
        add_cylinder(
            bm_gold,
            Vector((3.35 * math.cos(ra), 3.35 * math.sin(ra), Z_CROSSING_VAULT - 0.25)),
            Vector((6.40 * math.cos(ra), 6.40 * math.sin(ra), Z_CROSSING_VAULT - 1.35)),
            0.14,
            0.05,
            segments=5,
            cap=False,
        )

    # Upper crossing drum walls bridging from 45m vaults up to 60m crossing vault
    for sx in (-1, 1):
        add_box(bm_vault, (sx * 7.6, 0.0, 52.0), (0.8, 15.4, 15.0))
        add_box(bm_vault, (0.0, sx * 7.6, 52.0), (15.4, 0.8, 15.0))

    # Central Nave Clerestory Upper Walls bridging 30m side aisles to 45m nave vault
    for sx in (-1, 1):
        for bay in range(2, 7):
            cy = -bay * GRID + 3.75
            # Pier between clerestory windows
            add_box(bm_vault, (sx * 7.6, -bay * GRID, 37.5), (0.9, 2.2, 16.0))
            add_box(bm_vault, (sx * 7.6, cy, 43.8), (0.9, 5.5, 3.2))
            add_box(bm_vault, (sx * 7.6, cy, 31.8), (0.9, 5.5, 2.5))

    # Transept Clerestory Upper Walls bridging 30m transept side aisles to 45m central transept vault (seals upper L/R sky gaps!)
    for sy in (-1, 1):
        for sx in (-1, 1):
            for cx_bay in (11.25, 18.75, 26.25):
                px = sx * cx_bay
                add_box(bm_vault, (px + sx * 3.75, sy * 7.6, 38.5), (2.2, 0.95, 16.0))
                add_box(bm_vault, (px, sy * 7.6, 44.0), (5.6, 0.95, 3.6))
                add_box(bm_vault, (px, sy * 7.6, 32.0), (5.6, 0.95, 3.0))
    # Seal North transition walls between Crossing/Apse and North Transept side aisles (X = ±15..±23, Y = +15.2)
    for sx in (-1, 1):
        add_box(bm_vault, (sx * 16.5, 15.2, 38.5), (17.5, 1.2, 16.5))

    # 5d. Soaring Apse Vault Dome rising into Mary Tower base (Z = 56m -> 74.5m — matching real 75m Apse height!)
    create_hyperboloid_vault_bay(bm_vault, bm_gold, 0.0, 18.5, Z_APSE_VAULT, 24.0, 22.0, depth=18.0, oculus_r=3.4, segs=24, rings=8)

    # Seal exterior ceiling backing decks right above side aisles, central nave, transepts & apse drum
    # so zero sky slits ever leak between vault rosettes!
    for sx in (-1, 1):
        add_box(bm_vault, (sx * 15.2, -26.8, Z_AISLE_VAULT + 0.35), (15.8, 39.2, 0.55))
        add_box(bm_vault, (sx * 19.0, 11.25, Z_AISLE_VAULT + 0.35), (23.0, 8.2, 0.55))
        add_box(bm_vault, (sx * 19.0, -11.25, Z_AISLE_VAULT + 0.35), (23.0, 8.2, 0.55))
    add_box(bm_vault, (0.0, -26.8, Z_NAVE_VAULT + 0.45), (15.8, 39.2, 0.65))
    # Split transept ceiling backing strictly OUTSIDE the central Crossing (X = ±7.6..±30.5) so the Glass Panorama Elevator rises 100% OPEN up through the 60m Crossing Vault Oculus!
    add_box(bm_vault, (19.05, 0.0, Z_NAVE_VAULT + 0.45), (22.9, 15.8, 0.65))
    add_box(bm_vault, (-19.05, 0.0, Z_NAVE_VAULT + 0.45), (22.9, 15.8, 0.65))
    # Apse upper tapering dome-skirt is built in warm Catalan sandstone inside Section 6 (bm_walls) right below!

    finalize_bmesh_object(bm_vault, "Interior_HyperboloidVaults", mats["vault_stone"], smooth=True, uv_scale=0.14)
    finalize_bmesh_object(bm_gold, "Interior_GoldAccents", mats["gold_accent"], smooth=True, uv_scale=0.35)

    # ── 6. Exterior Nave & Apse Enclosure Walls + Stained Glass Windows ──
    bm_walls = bmesh.new()
    bm_glass_east = bmesh.new()
    bm_glass_west = bmesh.new()
    bm_glass_apse = bmesh.new()

    # East (+22.5, Cool Blue/Green Morning) & West (-22.5, Warm Red/Orange Evening) Nave Walls
    for sx, bm_glass in ((1, bm_glass_east), (-1, bm_glass_west)):
        wx = sx * 22.8
        for bay_idx in range(5):
            y_center = -18.75 - bay_idx * GRID
            # Pier column buttress on wall
            add_box(bm_walls, (wx, y_center - 3.75, 16.0), (1.4, 2.1, 31.0))
            if bay_idx == 0:
                add_box(bm_walls, (wx, y_center + 3.75, 16.0), (1.4, 2.1, 31.0))
            # Leave bay_idx == 2 open as a tall sculpted direct doorway from the Nave into the East & West Cloisters!
            if bay_idx == 2:
                add_box(bm_walls, (wx, y_center, 9.6), (1.2, 5.6, 7.6))
                add_box(bm_walls, (wx, y_center, 14.6), (1.2, 5.6, 2.4))
                add_box(bm_walls, (wx, y_center, 30.2), (1.4, 5.6, 2.8))
                # Upper stained glass lancet window above the cloister doorway
                add_box(bm_glass, (wx, y_center, 22.3), (0.16, 5.2, 13.0))
                add_gaudi_window_tracery(bm_walls, (wx - sx * 0.22, y_center, 22.3), 5.2, 13.0, facing="X")
            else:
                # Lower stone dado (Z = 0..3.6), gallery spandrel (Z = 13.5..15.8), cornice (Z = 29..32)
                add_box(bm_walls, (wx, y_center, 1.8), (1.2, 5.6, 3.6))
                add_box(bm_walls, (wx, y_center, 14.6), (1.2, 5.6, 2.4))
                add_box(bm_walls, (wx, y_center, 30.2), (1.4, 5.6, 2.8))

                # Lower tall stained glass lancet window (Z = 3.6 .. 13.4) + 3D Gaudí stone tracery
                add_box(bm_glass, (wx, y_center, 8.5), (0.16, 5.2, 9.8))
                add_gaudi_window_tracery(bm_walls, (wx - sx * 0.22, y_center, 8.5), 5.2, 9.8, facing="X")
                # Upper tall stained glass lancet window (Z = 15.8 .. 28.8) + 3D Gaudí stone tracery
                add_box(bm_glass, (wx, y_center, 22.3), (0.16, 5.2, 13.0))
                add_gaudi_window_tracery(bm_walls, (wx - sx * 0.22, y_center, 22.3), 5.2, 13.0, facing="X")

            # Clerestory stained glass at X = ±7.6 (Z = 33..42.2)
            add_box(bm_glass, (sx * 7.6, y_center, 37.6), (0.14, 5.1, 9.2))

    # Transept Clerestory stained glass panes (X = ±11.25..±26.25, Y = ±7.6, Z = 33..42.2)
    for sx, bm_glass in ((1, bm_glass_east), (-1, bm_glass_west)):
        for sy in (-1, 1):
            for cx_bay in (11.25, 18.75, 26.25):
                add_box(bm_glass, (sx * cx_bay, sy * 7.6, 38.0), (5.4, 0.16, 9.2))

    # Transept North & South Side Walls with wide ground-level Walkable Archways into East/West Cloisters & Sacristies!
    for sx, bm_glass in ((1, bm_glass_east), (-1, bm_glass_west)):
        for sy in (-1, 1):
            wy = sy * 15.2
            x_pos = sx * 26.4
            add_box(bm_walls, (sx * 22.8, wy, 16.0), (1.8, 1.6, 31.0))
            add_box(bm_walls, (sx * 30.0, wy, 16.0), (1.8, 1.6, 31.0))
            # Open 4.6m tall doorway (Z = 1.2..5.6m) directly into South & North Cloisters -> lintel beam at Z = 6.2m!
            add_box(bm_walls, (x_pos, wy, 6.2), (6.4, 1.2, 1.2))
            add_box(bm_walls, (x_pos, wy, 14.6), (6.4, 1.2, 2.4))
            add_box(bm_walls, (x_pos, wy, 30.2), (6.4, 1.4, 2.8))
            add_box(bm_glass, (x_pos, wy, 10.1), (5.8, 0.16, 6.6))
            add_gaudi_window_tracery(bm_walls, (x_pos, wy - sy * 0.22, 10.1), 5.8, 6.6, facing="Y")
            add_box(bm_glass, (x_pos, wy, 22.3), (5.8, 0.16, 13.0))
            add_gaudi_window_tracery(bm_walls, (x_pos, wy - sy * 0.22, 22.3), 5.8, 13.0, facing="Y")

    # Semicircular Apse Enclosure Wall (7 Watertight Radiating Chapels — ZERO sky slits beside stained glass!)
    num_chapels = 7
    r_apse = 18.8
    d_ang = math.pi * 0.92 / num_chapels
    chord_w = 2.0 * r_apse * math.sin(0.5 * d_ang)  # ~7.76m exact span between pier centers
    for i in range(num_chapels):
        a0 = math.pi * (0.04 + 0.92 * i / num_chapels)
        a1 = math.pi * (0.04 + 0.92 * (i + 1) / num_chapels)
        am = 0.5 * (a0 + a1)
        px = r_apse * math.cos(am)
        py = 16.5 + r_apse * math.sin(am)
        rot_z = am - math.pi / 2.0
        for a_pier in (a0, a1):
            add_box(
                bm_walls,
                (r_apse * math.cos(a_pier), 16.5 + r_apse * math.sin(a_pier), 22.0),
                (1.9, 2.4, 44.0),
                rot_euler=(0.0, 0.0, a_pier - math.pi / 2.0),
            )
        # Full-chord stone dado, gallery spandrel & cornice overlapping piers cleanly
        add_box(bm_walls, (px, py, 2.05), (chord_w + 0.2, 1.25, 4.1), rot_euler=(0.0, 0.0, rot_z))
        add_box(bm_walls, (px, py, 14.5), (chord_w + 0.2, 1.25, 2.3), rot_euler=(0.0, 0.0, rot_z))
        add_box(bm_walls, (px, py, 41.0), (chord_w + 0.4, 1.45, 6.2), rot_euler=(0.0, 0.0, rot_z))
        # Exact pier-to-pier stained glass panes + stone mullions (zero daylight leaks!)
        glass_w = chord_w - 1.35
        add_box(bm_glass_apse, (px, py, 8.75), (glass_w, 0.16, 9.7), rot_euler=(0.0, 0.0, rot_z))
        add_box(bm_glass_apse, (px, py, 27.0), (glass_w, 0.16, 23.0), rot_euler=(0.0, 0.0, rot_z))
        tx = (r_apse - 0.25) * math.cos(am)
        ty = 16.5 + (r_apse - 0.25) * math.sin(am)
        add_gaudi_window_tracery(bm_walls, (tx, ty, 8.75), glass_w, 9.5, rot_z=rot_z)
        add_gaudi_window_tracery(bm_walls, (tx, ty, 27.0), glass_w, 22.6, rot_z=rot_z)

    # Diagonal Watertight Apse-to-North-Transept Return Walls sealing East & West corners (X = ±18.6..±22.8, Y = 15.2..18.9)
    for sx in (-1, 1):
        p_apse_end = Vector((sx * r_apse * math.cos(math.pi * 0.04), 16.5 + r_apse * math.sin(math.pi * 0.04), 0.0))
        p_tran_end = Vector((sx * 22.8, 15.2, 0.0))
        mid_ret = (p_apse_end + p_tran_end) * 0.5
        ret_len = (p_tran_end - p_apse_end).length + 1.2
        ret_ang = math.atan2(p_tran_end.y - p_apse_end.y, p_tran_end.x - p_apse_end.x)
        add_box(bm_walls, (mid_ret.x, mid_ret.y, 16.0), (ret_len, 1.5, 32.0), rot_euler=(0.0, 0.0, ret_ang))

    # Graceful tapering warm-sandstone parabolic Apse dome-skirt (Z = 41.5m r=18.5 -> Z = 74.8m r=6.8)
    # Matches the golden Catalan stone of the Neo-Gothic Apse gables & tapers seamlessly into the Virgin Mary Tower!
    drum_segs = 24
    tiers_apse = [
        (41.5, 16.5, 18.5),
        (51.0, 17.6, 15.0),
        (61.5, 19.4, 11.2),
        (74.8, 21.8, 6.8),
    ]
    out_rings: list[list[bmesh.types.BMVert]] = []
    in_rings: list[list[bmesh.types.BMVert]] = []
    for z_t, cy_t, r_t in tiers_apse:
        ro, ri = [], []
        for i in range(drum_segs + 1):
            ang = math.pi * (-0.05 + 1.10 * i / drum_segs)
            ca, sa = math.cos(ang), math.sin(ang)
            ro.append(bm_walls.verts.new((r_t * ca, max(10.6, cy_t + r_t * sa), z_t)))
            ri.append(bm_walls.verts.new(((r_t - 0.65) * ca, max(11.1, cy_t + (r_t - 0.65) * sa), z_t)))
        out_rings.append(ro)
        in_rings.append(ri)
    for ti in range(len(out_rings) - 1):
        for i in range(drum_segs):
            # Solid watertight double-sided shell (outer face + inner face)
            bm_walls.faces.new((out_rings[ti][i], out_rings[ti][i + 1], out_rings[ti + 1][i + 1], out_rings[ti + 1][i]))
            bm_walls.faces.new((in_rings[ti][i + 1], in_rings[ti][i], in_rings[ti + 1][i], in_rings[ti + 1][i + 1]))
    # Top & bottom closure rims so the shell is 100% solid manifold
    for i in range(drum_segs):
        bm_walls.faces.new((out_rings[-1][i], out_rings[-1][i + 1], in_rings[-1][i + 1], in_rings[-1][i]))
        bm_walls.faces.new((in_rings[0][i], in_rings[0][i + 1], out_rings[0][i + 1], out_rings[0][i]))
    # Sculpted exterior Gothic stone ribs running gracefully up the tapering Apse roof cone into Mary Tower!
    for i in range(0, drum_segs + 1, 3):
        for ti in range(len(out_rings) - 1):
            add_cylinder(bm_walls, out_rings[ti][i].co.copy(), out_rings[ti + 1][i].co.copy(), 0.38, 0.24, segments=6, cap=False)

    finalize_bmesh_object(bm_walls, "Interior_NaveWalls", mats["sandstone_warm"], smooth=False, uv_scale=0.14)

    # Stained glass UVs stretched nicely 0..1 per window pane so vertical color gradient maps bottom->top!
    for bm_g, gname, gmat in (
        (bm_glass_east, "Interior_StainedGlass_East", mats["stained_glass_east"]),
        (bm_glass_west, "Interior_StainedGlass_West", mats["stained_glass_west"]),
        (bm_glass_apse, "Interior_StainedGlass_Apse", mats["stained_glass_apse"]),
    ):
        bmesh.ops.recalc_face_normals(bm_g, faces=bm_g.faces)
        uv_layer = bm_g.loops.layers.uv.verify()
        for f in bm_g.faces:
            xs = [l.vert.co.x for l in f.loops]
            ys = [l.vert.co.y for l in f.loops]
            zs = [l.vert.co.z for l in f.loops]
            zmin, zmax = min(zs), max(zs)
            span_z = max(zmax - zmin, 0.1)
            horiz_x = max(xs) - min(xs)
            horiz_y = max(ys) - min(ys)
            use_x = horiz_x >= horiz_y
            hmin = min(xs) if use_x else min(ys)
            hspan = max(horiz_x if use_x else horiz_y, 0.1)
            for l in f.loops:
                u = ((l.vert.co.x if use_x else l.vert.co.y) - hmin) / hspan
                v = (l.vert.co.z - zmin) / span_z
                l[uv_layer].uv = (u, v)
        mesh = bpy.data.meshes.new(gname)
        bm_g.to_mesh(mesh)
        bm_g.free()
        mesh.materials.append(gmat)
        obj = bpy.data.objects.new(gname, mesh)
        bpy.context.collection.objects.link(obj)

    # ── 7. Wooden Cathedral Pews (Central Nave, wide central walkway kept open) ──
    bm_pew = bmesh.new()
    # One reusable pew block: 4.8m wide
    add_box(bm_pew, (0.0, 0.0, 0.45), (4.6, 0.48, 0.08))    # Seat
    add_box(bm_pew, (0.0, -0.22, 0.78), (4.6, 0.08, 0.62))  # Backrest
    add_box(bm_pew, (-2.15, 0.0, 0.24), (0.14, 0.46, 0.48)) # Left leg
    add_box(bm_pew, (2.15, 0.0, 0.24), (0.14, 0.46, 0.48))  # Right leg
    apply_box_uv(bm_pew, scale=0.4)
    bake_bvh_vertex_ao(bm_pew, max_dist=1.8, min_ao=0.55)
    mesh_pew = bpy.data.meshes.new("Mesh_Pew")
    bm_pew.to_mesh(mesh_pew)
    bm_pew.free()
    mesh_pew.materials.append(mats["wood_pew"])

    pew_idx = 0
    for row in range(18):
        py = -10.5 - row * 1.45
        if abs(py - (-15.0)) < 1.1 or abs(py - (-22.5)) < 1.1 or abs(py - (-30.0)) < 1.1:
            continue  # Leave cross aisles free
        for sx in (-1, 1):
            place_instance(f"Pew_{pew_idx}", mesh_pew, (sx * 4.2, py, Z_NAVE))
            pew_idx += 1

    export_glb(os.path.join(MODEL_DIR, "interior.glb"))


if __name__ == "__main__":
    build_interior()
