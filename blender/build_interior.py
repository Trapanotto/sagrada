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
    GRID,
    MODEL_DIR,
    Z_AISLE_VAULT,
    Z_ALTAR,
    Z_APSE_VAULT,
    Z_CROSSING_VAULT,
    Z_GALLERY,
    Z_NAVE,
    Z_NAVE_VAULT,
    APSE_CENTER_Y,
    APSE_RADIUS,
    add_box,
    add_cylinder,
    add_ellipsoid,
    add_gaudi_window_tracery,
    add_swept_tube,
    apply_box_uv,
    bake_bvh_vertex_ao,
    export_glb,
    finalize_bmesh_object,
    get_materials,
    reset_scene,
)
from interior_lib import (
    HyperboloidBay,
    VaultField,
    add_column_canopy,
    build_double_twist_column_mesh,
    build_hyperboloid_bay,
    finalize_oriented,
)

# ── Target dimensions (Blender metres, floor of the nave at Z_NAVE = 1.2) ──
# Plan (sagradafamilia.org / Wikipedia): Latin cross on a 7.5 m grid; nave of five aisles,
# central nave 15 m between column axes, side aisles 7.5 m each (45 m); transept of three aisles,
# 30 m wide, 60 m long. Vault collars above the nave floor: side aisles 30 m, central nave and
# transept 45 m, crossing 60 m, apse 75 m (Z_* constants in common.py, kept).
# Apse: the model keeps its established ring of 8 columns (r = 11.2 m about y = 16.5) and the
# 7 radiating chapels (wall r = 18.8 m) because the altar, organ, candles and teleports are pinned
# to them; the real apse ring is concentric with the crypt below (see build_cloister_crypt.py).
APSE_RING_R = 11.2
APSE_RING_CY = 16.5
# Ambulatory vault collar (no published figure found; set so the ambulatory vault springs from the
# apse-wall cornice at ~37.5 m and the full height of the apse windows stays visible)
Z_AMB_VAULT = 42.0
CLERESTORY_TRACERY = False
APSE_DRUM_Z0 = 38.4  # foot of the apse clerestory drum (= ambulatory vault springing on the ring)
AISLE_DEPTH, AISLE_THROAT = 3.0, 1.0      # 7.5 x 7.5 m bays
NAVE_DEPTH, NAVE_THROAT = 4.0, 1.6        # 15 x 7.5 m bays (corners on the clerestory, below its 42.2 m glass top)
CROSS_DEPTH, CROSS_THROAT = 5.5, 3.2      # 15 x 15 m crossing; the collar stays open for the glass elevator (r 2.25)
APSE_DEPTH, APSE_THROAT = 18.0, 3.4       # great apse hyperboloid under the Mary tower


def build_vault_field() -> VaultField:
    """All vault bays as hyperboloids clipped to their bay polygons (one per column bay)."""
    f = VaultField()
    for sx in (-1, 1):
        for bx in (11.25, 18.75):
            for by in (-18.75, -26.25, -33.75, -41.25):
                f.add(HyperboloidBay.rect(sx * bx, by, GRID, GRID, Z_AISLE_VAULT, AISLE_DEPTH, AISLE_THROAT, "aisle"))
        for bx in (11.25, 18.75, 26.25):
            for sy in (-1, 1):
                f.add(HyperboloidBay.rect(sx * bx, sy * 11.25, GRID, GRID, Z_AISLE_VAULT, AISLE_DEPTH, AISLE_THROAT, "aisle"))
            f.add(HyperboloidBay.rect(sx * bx, 0.0, GRID, 2 * GRID, Z_NAVE_VAULT, NAVE_DEPTH, NAVE_THROAT, "nave"))
    for by in (-11.25, -18.75, -26.25, -33.75, -41.25):
        f.add(HyperboloidBay.rect(0.0, by, 2 * GRID, GRID, Z_NAVE_VAULT, NAVE_DEPTH, NAVE_THROAT, "nave"))
    f.add(HyperboloidBay.rect(0.0, 0.0, 2 * GRID, 2 * GRID, Z_CROSSING_VAULT, CROSS_DEPTH, CROSS_THROAT, "crossing"))
    # Apse: presbytery (x +-7.5, y 7.5..15) + the ring of apse columns
    ring = [(APSE_RING_R * math.cos(math.pi * (i + 0.5) / 8.0), APSE_RING_CY + APSE_RING_R * math.sin(math.pi * (i + 0.5) / 8.0)) for i in range(8)]
    apse_poly = [(-GRID, GRID), (GRID, GRID), (GRID, 2 * GRID)] + ring + [(-GRID, 2 * GRID)]
    f.add(HyperboloidBay(0.0, 17.5, apse_poly, Z_APSE_VAULT, APSE_DEPTH, APSE_THROAT, "apse"))
    # Ambulatory: one cell per chapel bay between consecutive ring columns, out to the apse wall
    r_out = 18.2
    for i in range(7):
        a0, a1 = math.pi * (i + 0.5) / 8.0, math.pi * (i + 1.5) / 8.0
        am = 0.5 * (a0 + a1)
        poly = [
            (APSE_RING_R * math.cos(a0), APSE_RING_CY + APSE_RING_R * math.sin(a0)),
            (r_out * math.cos(a0), APSE_RING_CY + r_out * math.sin(a0)),
            (r_out * math.cos(a1), APSE_RING_CY + r_out * math.sin(a1)),
            (APSE_RING_R * math.cos(a1), APSE_RING_CY + APSE_RING_R * math.sin(a1)),
        ]
        rc = 0.5 * (APSE_RING_R + r_out)
        f.add(HyperboloidBay(rc * math.cos(am), APSE_RING_CY + rc * math.sin(am), poly, Z_AMB_VAULT, 3.5, AISLE_THROAT, "ambulatory"))
    return f


def merge_bmesh_into(dst: bmesh.types.BMesh, src: bmesh.types.BMesh) -> None:
    tmp = bpy.data.meshes.new("_merge_tmp")
    src.to_mesh(tmp)
    src.free()
    dst.from_mesh(tmp)
    bpy.data.meshes.remove(tmp)


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

    # ── 3. Gaudí's forest of double-twist columns (4 stones / 4 star types) ──
    # Target values (see interior_lib.column_dims): knot top = 2 x points [m] above the floor,
    # diameter 0.175 m x points, shaft = 10 x diameter. Placement (sagradafamilia.org columns article,
    # medium confidence for everything except the porphyry crossing columns):
    #   12-point red porphyry  : the 4 crossing columns (carry the Jesus lantern + Evangelist towers)
    #   10-point dark basalt   : the 8 columns ringing the crossing (+-7.5,+-15) / (+-15,+-7.5)
    #    8-point grey granite  : central nave rows x = +-7.5, transept rows, apse ring
    #    6-point sandstone     : side-aisle rows x = +-15 (lightest load: side aisles + choir galleries)
    vault = build_vault_field()

    col_meshes = {}
    col_dims = {}
    for n, key, mat_key in ((12, "Porphyry", "porphyry_red"), (10, "Basalt", "basalt_dark"), (8, "Granite", "granite_grey"), (6, "Sandstone", "sandstone_warm")):
        col_meshes[key], col_dims[key] = build_double_twist_column_mesh(f"Mesh_Col_{key}", mats[mat_key], n)

    bm_branches = bmesh.new()
    bm_lamps = bmesh.new()  # lamps in the secondary knots + oculus lamps (CandleGlow = runtime lamp group)
    diag = [math.pi * (0.25 + 0.5 * k) for k in range(4)]
    # (type, x, y, foot z, branch angles, reach, branch radius, twigs)
    columns: list[tuple[str, float, float, float, list[float], float, float, int]] = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            columns.append(("Porphyry", sx * GRID, sy * GRID, Z_NAVE, [math.pi / 8 + k * math.pi / 4 for k in range(8)], 5.0, 0.42, 3))
    for sx in (-1, 1):
        for sy in (-1, 1):
            # presbytery side (+y) columns stand on the raised sanctuary platform (Z_ALTAR)
            columns.append(("Basalt", sx * GRID, sy * 2 * GRID, Z_ALTAR if sy > 0 else Z_NAVE, [k * math.pi / 3 + math.pi / 6 for k in range(6)], 4.4, 0.36, 3))
            columns.append(("Basalt", sx * 2 * GRID, sy * GRID, Z_NAVE, [k * math.pi / 3 for k in range(6)], 4.4, 0.36, 3))
    for bay in range(3, 7):  # nave central rows y = -22.5 .. -45
        for sx in (-1, 1):
            columns.append(("Granite", sx * GRID, -bay * GRID, Z_NAVE, diag, 3.8, 0.30, 3))
    for sx in (-1, 1):
        for sy in (-1, 1):
            columns.append(("Granite", sx * 3 * GRID, sy * GRID, Z_NAVE, diag, 3.8, 0.30, 3))
    for bay in range(2, 7):  # side-aisle rows x = +-15, y = -15 .. -45
        for sx in (-1, 1):
            columns.append(("Sandstone", sx * 2 * GRID, -bay * GRID, Z_NAVE, diag, 3.2, 0.24, 2))
    for sx in (-1, 1):
        columns.append(("Sandstone", sx * 2 * GRID, 2 * GRID, Z_NAVE, diag, 3.2, 0.24, 2))

    counters: dict[str, int] = {}
    for kind, cx, cy, z_foot, angs, reach, rb, tw in columns:
        idx = counters.get(kind, 0)
        counters[kind] = idx + 1
        place_instance(f"Col_{kind}_{idx}", col_meshes[kind], (cx, cy, z_foot))
        z_top = z_foot + col_dims[kind]["total"]
        add_column_canopy(bm_branches, bm_lamps, cx, cy, z_top, angs, reach, rb, vault, twigs=tw, fallback_z=Z_AISLE_VAULT)
        if kind == "Sandstone" and -41.0 < cy < -14.0:
            # 6-point columns bear the choir galleries: short corbel branch up to the cantoria slab edge
            sxs = 1.0 if cx > 0 else -1.0
            add_swept_tube(bm_branches, [Vector((cx, cy, z_top - 0.2)), Vector((cx + sxs * 0.9, cy, z_top + 0.15)), Vector((cx + sxs * 1.85, cy, Z_GALLERY - 0.72))], [0.22, 0.2, 0.18], segments=6)

    # Apse ring (8 granite columns between the 7 chapels): canopies reach out to the ambulatory vault,
    # one vertical limb carries the apse clerestory drum built on the ring.
    for i in range(8):
        ang = math.pi * (i + 0.5) / 8.0
        cx = APSE_RING_R * math.cos(ang)
        cy = APSE_RING_CY + APSE_RING_R * math.sin(ang)
        place_instance(f"Col_Granite_Apse_{i}", col_meshes["Granite"], (cx, cy, Z_NAVE), rot_z=ang)
        z_top = Z_NAVE + col_dims["Granite"]["total"]
        add_column_canopy(bm_branches, bm_lamps, cx, cy, z_top, [ang - 0.75, ang + 0.75], 3.8, 0.30, vault, twigs=3, fallback_z=Z_AMB_VAULT - 3.0)
        add_swept_tube(bm_branches, [Vector((cx, cy, z_top - 0.2)), Vector((cx, cy, 0.5 * (z_top + APSE_DRUM_Z0))), Vector((cx, cy, APSE_DRUM_Z0))], [0.34, 0.30, 0.36], segments=7)

    # Evangelist symbols as lamps on the knots of the four porphyry crossing columns, facing the crossing.
    # Column under each Evangelist tower: Matthew (angel) +x Glory side, Mark (lion) -x Glory side,
    # Luke (ox) -x apse side, John (eagle) +x apse side.
    evangelists = {(1, -1): "angel", (-1, -1): "lion", (-1, 1): "ox", (1, 1): "eagle"}
    kd = col_dims["Porphyry"]
    for (sx, sy), symbol in evangelists.items():
        d = Vector((-sx, -sy, 0.0)).normalized()
        c = Vector((sx * GRID, sy * GRID, Z_NAVE + kd["knot_c"])) + d * (kd["knot_r"] * 0.93)
        rot = math.atan2(d.y, d.x)
        add_ellipsoid(bm_gold, c - d * 0.08, (0.2, 0.72, 0.98), subdivisions=2, rot_z=rot)
        add_ellipsoid(bm_lamps, c + d * 0.06, (0.16, 0.56, 0.80), subdivisions=2, rot_z=rot)
        side = Vector((-d.y, d.x, 0.0))
        front = c + d * 0.24
        if symbol in ("angel", "eagle"):
            for s in (-1, 1):
                add_ellipsoid(bm_gold, front + side * (0.24 * s) + Vector((0, 0, 0.18)), (0.05, 0.22, 0.10), subdivisions=1, rot_z=rot, roll=0.5 * s)
            add_ellipsoid(bm_gold, front + Vector((0, 0, 0.36 if symbol == "angel" else 0.26)), (0.06, 0.09, 0.09), subdivisions=1, rot_z=rot)
        elif symbol == "ox":
            for s in (-1, 1):
                add_cylinder(bm_gold, front + side * (0.08 * s) + Vector((0, 0, 0.22)), front + side * (0.24 * s) + Vector((0, 0, 0.42)), 0.04, 0.012, segments=5)
            add_ellipsoid(bm_gold, front + Vector((0, 0, 0.12)), (0.06, 0.13, 0.12), subdivisions=1, rot_z=rot)
        else:  # lion: mane disc + head
            add_ellipsoid(bm_gold, front + Vector((0, 0, 0.2)), (0.05, 0.2, 0.2), subdivisions=1, rot_z=rot)
            add_ellipsoid(bm_gold, front + d * 0.05 + Vector((0, 0, 0.2)), (0.05, 0.1, 0.1), subdivisions=1, rot_z=rot)

    finalize_bmesh_object(bm_branches, "Interior_ColumnBranches", mats["sandstone_warm"], smooth=True, uv_scale=0.22, ao_dist=1.8, ao_vert_limit=90000)

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

    bm_walls = bmesh.new()
    bm_glass_east = bmesh.new()
    bm_glass_west = bmesh.new()
    bm_glass_apse = bmesh.new()

    # ── 5. Hyperboloid vaults: one ruled hyperboloid per bay, collars = oculi with lamps ──
    bm_vault_hyp = bmesh.new()
    bm_collar = bmesh.new()  # green/gold trencadís bands at the collars
    bm_gold_field = bmesh.new()  # golden mosaic field of the apse vault
    for bay in vault.bays:
        n_r = 48 if bay.tag in ("crossing", "apse") else (40 if bay.tag == "nave" else 32)
        # the crossing collar stays OPEN: the glass elevator of the Jesus tower rises through it
        build_hyperboloid_bay(bay, bm_vault_hyp, bm_collar, bm_gold, None if bay.tag == "crossing" else bm_lamps, n_rulings=n_r)
        if bay.tag == "apse":
            # Gold field = the upper zone of the same hyperboloid (r <= 7 m), offset 4 cm inward
            gb = HyperboloidBay(bay.cx, bay.cy, [(bay.cx + 7.0 * math.cos(2 * math.pi * k / 24), bay.cy + 7.0 * math.sin(2 * math.pi * k / 24)) for k in range(24)], bay.z_top - 0.04, 1.0, bay.a)
            gb.c = bay.c
            build_hyperboloid_bay(gb, bm_gold_field, None, None, None, n_rulings=36, v_fracs=(0.0, 0.3, 0.65, 1.0))

    # Box masonry (drums, clerestories, backing decks) goes to its own bmesh so its normals can be
    # recalculated without flipping the down-facing hyperboloid shells; both are merged afterwards.
    bm_vault = bmesh.new()

    # Apse clerestory drum on the ring of apse columns: from the ambulatory vault springing up to the
    # edge of the great apse hyperboloid, one stained-glass window per chapel bay.
    apse_bay = next(b for b in vault.bays if b.tag == "apse")
    ring_pts = [(APSE_RING_R * math.cos(math.pi * (i + 0.5) / 8.0), APSE_RING_CY + APSE_RING_R * math.sin(math.pi * (i + 0.5) / 8.0)) for i in range(8)]
    drum_segments = list(zip(ring_pts[:-1], ring_pts[1:]))
    for sx in (-1, 1):
        drum_segments.append(((sx * GRID, 2 * GRID), ring_pts[0] if sx > 0 else ring_pts[-1]))
        drum_segments.append(((sx * GRID, GRID), (sx * GRID, 2 * GRID)))
    for si, ((x0, y0), (x1, y1)) in enumerate(drum_segments):
        mx, my = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        seg_len = math.hypot(x1 - x0, y1 - y0)
        rot = math.atan2(y1 - y0, x1 - x0)
        z_top = max(apse_bay.height(x0, y0), apse_bay.height(x1, y1)) + 0.8
        is_window = si < 7
        if not is_window:
            add_box(bm_vault, (mx, my, 0.5 * (APSE_DRUM_Z0 + z_top)), (seg_len + 0.6, 0.8, z_top - APSE_DRUM_Z0), rot_euler=(0, 0, rot))
            continue
        w_z0, w_z1 = APSE_DRUM_Z0 + 3.2, APSE_DRUM_Z0 + 14.2
        add_box(bm_vault, (mx, my, 0.5 * (APSE_DRUM_Z0 + w_z0)), (seg_len + 0.6, 0.8, w_z0 - APSE_DRUM_Z0), rot_euler=(0, 0, rot))
        add_box(bm_vault, (mx, my, 0.5 * (w_z1 + z_top)), (seg_len + 0.6, 0.8, z_top - w_z1), rot_euler=(0, 0, rot))
        for end in (0.0, 1.0):
            px, py = x0 + (x1 - x0) * end, y0 + (y1 - y0) * end
            add_box(bm_vault, (px, py, 0.5 * (w_z0 + w_z1)), (1.0, 0.9, w_z1 - w_z0), rot_euler=(0, 0, rot))
        add_box(bm_glass_apse, (mx, my, 0.5 * (w_z0 + w_z1)), (seg_len - 0.9, 0.14, w_z1 - w_z0), rot_euler=(0, 0, rot))
        nx, ny = -math.sin(rot), math.cos(rot)  # inward (left) normal of the CCW ring -> tracery on the inside
        add_gaudi_window_tracery(bm_walls, (mx + nx * 0.2, my + ny * 0.2, 0.5 * (w_z0 + w_z1)), seg_len - 0.9, w_z1 - w_z0, rot_z=rot)

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

    # Merge: box masonry (normals recalculated) + hyperboloid shells (authored down-facing normals)
    bmesh.ops.recalc_face_normals(bm_vault, faces=bm_vault.faces)
    merge_bmesh_into(bm_vault_hyp, bm_vault)
    finalize_oriented(bm_vault_hyp, "Interior_HyperboloidVaults", mats["vault_stone"], smooth=True, uv_scale=0.14, ao_dist=4.0)
    finalize_oriented(bm_collar, "Interior_GoldAccents_VaultTrencadis", mats["trencadis"], smooth=True, uv_scale=0.6, ao=False)
    finalize_oriented(bm_gold_field, "Interior_GoldAccents_ApseMosaic", mats["gold_accent"], smooth=True, uv_scale=0.4, ao=False)
    finalize_bmesh_object(bm_gold, "Interior_GoldAccents", mats["gold_accent"], smooth=True, uv_scale=0.35)
    # 'LanternAndCandleGlow' keeps the lamps out of the collision BVH; 'CandleGlow' material = runtime lamp group
    finalize_bmesh_object(bm_lamps, "Interior_KnotLamps_LanternAndCandleGlow", mats["candle_glow"], smooth=True, uv_scale=0.5, bake_ao=False)

    # ── 6. Exterior Nave & Apse Enclosure Walls + Stained Glass Windows ──

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
            # clerestory tracery (lancets, elliptical rose, circular oculi) on the nave side
            if CLERESTORY_TRACERY:
                add_gaudi_window_tracery(bm_walls, (sx * 7.6 - sx * 0.2, y_center, 37.6), 5.1, 9.2, facing="X")

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
