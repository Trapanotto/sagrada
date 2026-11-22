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
    export_glb,
    finalize_bmesh_object,
    get_materials,
    reset_scene,
)


def add_cloister_gallery_wing(
    bm_stone: bmesh.types.BMesh,
    bm_floor: bmesh.types.BMesh,
    x_center: float,
    y_start: float,
    y_end: float,
    width: float = 5.2,
    height: float = 9.0,
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
    """Gaudí's iconic swirling 38m domed Sacristy Pavilion at the NE & NW corners of the temple."""
    r_base = 8.4
    z_drum = 12.0
    z_top = 38.0
    sides = 12

    # Walkable interior floor
    add_cylinder(bm_floor, Vector((cx, cy, Z_NAVE - 0.7)), Vector((cx, cy, Z_NAVE)), r_base, r_base, segments=sides, cap=True)

    # Lower dodecagonal wall drum with open entrance archway facing south/inward toward cloister
    for k in range(sides):
        a0 = 2.0 * math.pi * k / sides
        a1 = 2.0 * math.pi * (k + 1) / sides
        am = 0.5 * (a0 + a1)
        wx = cx + r_base * math.cos(am)
        wy = cy + r_base * math.sin(am)
        seg_w = 2.0 * r_base * math.sin(math.pi / sides)
        # Keep the inward-south archway open so player can walk inside!
        is_door = (math.sin(am) < -0.7)
        if is_door:
            add_box(bm_stone, (wx, wy, Z_NAVE + 8.5), (seg_w, 0.9, 5.2), rot_euler=(0, 0, am - math.pi / 2.0))
        else:
            add_box(bm_stone, (wx, wy, Z_NAVE + z_drum * 0.5), (seg_w, 0.95, z_drum), rot_euler=(0, 0, am - math.pi / 2.0))
        # Corner pilaster
        add_cylinder(
            bm_stone,
            Vector((cx + r_base * math.cos(a0), cy + r_base * math.sin(a0), Z_NAVE)),
            Vector((cx + r_base * math.cos(a0), cy + r_base * math.sin(a0), Z_NAVE + z_drum)),
            0.55,
            0.48,
            segments=8,
        )

    # Gaudí's dramatic hyperboloid swirling ribbed dome (Z = 13.2m -> 35.5m) with real wall thickness
    dome_steps = 10
    prev_out = None
    prev_in = None
    for si in range(dome_steps + 1):
        t = si / dome_steps
        z = Z_NAVE + z_drum + t * (z_top - 4.0 - Z_NAVE - z_drum)
        r_out = 1.6 + (r_base - 1.6) * ((1.0 - t) ** 0.72)
        r_in = max(0.85, r_out - 0.55)
        twist = t * 0.45  # Subtle signature Gaudí helical twist
        ring_out = [
            bm_stone.verts.new((cx + r_out * math.cos(2 * math.pi * k / sides + twist), cy + r_out * math.sin(2 * math.pi * k / sides + twist), z))
            for k in range(sides)
        ]
        ring_in = [
            bm_stone.verts.new((cx + r_in * math.cos(2 * math.pi * k / sides + twist), cy + r_in * math.sin(2 * math.pi * k / sides + twist), z))
            for k in range(sides)
        ]
        if prev_out is not None and prev_in is not None:
            for k in range(sides):
                nk = (k + 1) % sides
                bm_stone.faces.new((prev_out[k], prev_out[nk], ring_out[nk], ring_out[k]))
                bm_stone.faces.new((prev_in[nk], prev_in[k], ring_in[k], ring_in[nk]))
        prev_out = ring_out
        prev_in = ring_in

    # Swirling external ribs + colorful trencadís lantern finial
    for k in range(sides):
        ang0 = 2.0 * math.pi * k / sides
        ang1 = ang0 + 0.45
        add_cylinder(
            bm_stone,
            Vector((cx + r_base * math.cos(ang0), cy + r_base * math.sin(ang0), Z_NAVE + z_drum)),
            Vector((cx + 1.65 * math.cos(ang1), cy + 1.65 * math.sin(ang1), z_top - 4.0)),
            0.42,
            0.22,
            segments=6,
        )
    add_cylinder(bm_mosaic, Vector((cx, cy, z_top - 4.5)), Vector((cx, cy, z_top - 1.0)), 2.2, 0.9, segments=12)
    add_cylinder(bm_gold, Vector((cx, cy, z_top - 1.2)), Vector((cx, cy, z_top + 2.2)), 0.32, 0.08, segments=8)


def build_crypt(
    bm_crypt: bmesh.types.BMesh,
    bm_floor: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
    bm_marble: bmesh.types.BMesh,
    bm_candle: bmesh.types.BMesh,
) -> None:
    """Neo-Gothic subterranean Crypt beneath the Apse (Z = -5.5m) with 7 chapels & Antoni Gaudí's Tomb."""
    cx, cy = 0.0, 21.0
    r_main = 15.5
    r_inner = 7.8
    h_ceil = 4.6  # Vault peaks at Z = -0.9m, completely clear beneath street slab (-0.54m) and nave floor (+1.2m)

    # Circular stone crypt floor
    add_cylinder(bm_floor, Vector((cx, cy, Z_CRYPT - 0.5)), Vector((cx, cy, Z_CRYPT)), r_main + 1.2, r_main + 1.2, segments=28, cap=True)

    # True triangulated Neo-Gothic Vaulted Stone Ceiling Dome (closes seamlessly down onto perimeter walls & inner columns!)
    dome_segs = 24
    z_wall_top = Z_CRYPT + 3.95
    z_mid_ring = Z_CRYPT + 4.45
    z_boss = Z_CRYPT + 4.75
    ring_outer = [
        bm_crypt.verts.new((cx + (r_main + 0.6) * math.cos(2 * math.pi * k / dome_segs), cy + (r_main + 0.6) * math.sin(2 * math.pi * k / dome_segs), z_wall_top))
        for k in range(dome_segs)
    ]
    ring_mid = [
        bm_crypt.verts.new((cx + r_inner * math.cos(2 * math.pi * k / dome_segs), cy + r_inner * math.sin(2 * math.pi * k / dome_segs), z_mid_ring))
        for k in range(dome_segs)
    ]
    v_center = bm_crypt.verts.new((cx, cy, z_boss))
    dome_faces = []
    for k in range(dome_segs):
        nk = (k + 1) % dome_segs
        dome_faces.append(bm_crypt.faces.new((ring_outer[nk], ring_outer[k], ring_mid[k], ring_mid[nk])))
        dome_faces.append(bm_crypt.faces.new((ring_mid[nk], ring_mid[k], v_center)))
    # Extrude dome upward by 0.25m so underside normals always point DOWN into the crypt!
    ext = bmesh.ops.extrude_face_region(bm_crypt, geom=dome_faces)
    ext_verts = [ele for ele in ext["geom"] if isinstance(ele, bmesh.types.BMVert)]
    bmesh.ops.translate(bm_crypt, verts=ext_verts, vec=(0.0, 0.0, 0.25))
    # Central stone keystone boss
    add_cylinder(bm_crypt, Vector((cx, cy, z_boss - 0.30)), Vector((cx, cy, z_boss + 0.05)), 1.35, 0.95, segments=16, cap=True)

    # Outer circular Neo-Gothic crypt wall (exact height meeting z_wall_top seamlessly)
    wall_h = z_wall_top - Z_CRYPT + 0.15
    segs = 20
    for k in range(segs):
        a0 = 2.0 * math.pi * k / segs
        a1 = 2.0 * math.pi * (k + 1) / segs
        am = 0.5 * (a0 + a1)
        is_entry = (-2.55 < am < -1.95) or (3.73 < am < 4.33)
        if not is_entry:
            wx = cx + r_main * math.cos(am)
            wy = cy + r_main * math.sin(am)
            seg_w = 2.0 * r_main * math.sin(math.pi / segs) + 0.3
            add_box(bm_crypt, (wx, wy, Z_CRYPT + wall_h * 0.5), (seg_w, 0.9, wall_h), rot_euler=(0, 0, am - math.pi / 2.0))
        add_cylinder(
            bm_crypt,
            Vector((cx + (r_main - 0.4) * math.cos(a0), cy + (r_main - 0.4) * math.sin(a0), Z_CRYPT)),
            Vector((cx + (r_main - 0.4) * math.cos(a0), cy + (r_main - 0.4) * math.sin(a0), z_wall_top + 0.05)),
            0.42,
            0.38,
            segments=8,
        )

    # Inner ring of 8 clustered Neo-Gothic columns + radiating groin-vault ribs hugging the vaulted ceiling
    r_inner = 7.8
    for i in range(8):
        ang = 2.0 * math.pi * i / 8.0
        px = cx + r_inner * math.cos(ang)
        py = cy + r_inner * math.sin(ang)
        add_cylinder(bm_crypt, Vector((px, py, Z_CRYPT)), Vector((px, py, z_mid_ring + 0.1)), 0.55, 0.46, segments=12)
        # Capital ring where column meets vault ribs
        add_cylinder(bm_crypt, Vector((px, py, z_mid_ring - 0.55)), Vector((px, py, z_mid_ring + 0.05)), 0.52, 0.78, segments=12)
        # Vault ribs snugly following the ceiling from column capital to central boss and outer wall
        add_cylinder(bm_crypt, Vector((px, py, z_mid_ring - 0.18)), Vector((cx, cy, z_boss - 0.12)), 0.22, 0.20, segments=6)
        ox = cx + (r_main - 0.2) * math.cos(ang)
        oy = cy + (r_main - 0.2) * math.sin(ang)
        add_cylinder(bm_crypt, Vector((px, py, z_mid_ring - 0.18)), Vector((ox, oy, z_wall_top - 0.05)), 0.22, 0.22, segments=6)

    # Central Crypt Altar (under the main High Altar)
    add_box(bm_marble, (cx, cy + 1.5, Z_CRYPT + 0.65), (3.0, 1.4, 1.3))
    add_cylinder(bm_gold, Vector((cx, cy + 1.5, Z_CRYPT + 1.3)), Vector((cx, cy + 1.5, Z_CRYPT + 3.0)), 0.08, 0.06, segments=8)
    add_cylinder(bm_gold, Vector((cx - 0.55, cy + 1.5, Z_CRYPT + 2.45)), Vector((cx + 0.55, cy + 1.5, Z_CRYPT + 2.45)), 0.06, 0.06, segments=8)

    # ANTONI GAUDÍ'S TOMB (Chapel of Our Lady of Mount Carmel, West side of Crypt: X = -9.5, Y = 23.5)
    tx, ty = -9.8, 23.5
    add_box(bm_marble, (tx, ty, Z_CRYPT + 0.14), (2.4, 1.35, 0.28))
    add_box(bm_gold, (tx, ty, Z_CRYPT + 0.30), (1.9, 0.9, 0.04))  # Inscribed bronze/gold plaque
    # Warm glowing votive candle rack beside Gaudí's tomb & around the crypt altar
    for k in range(6):
        vx = tx - 1.5 + k * 0.35
        vy = ty + 1.4
        add_cylinder(bm_candle, Vector((vx, vy, Z_CRYPT + 0.85)), Vector((vx, vy, Z_CRYPT + 1.15)), 0.045, 0.04, segments=6)
    add_box(bm_crypt, (tx - 0.6, ty + 1.4, Z_CRYPT + 0.42), (2.2, 0.45, 0.84))

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

    # Walkable Descending Stone Staircase from West Apse Cloister (-22.0, +16.5, Z=1.2) -> Crypt Entry (-11.0, +12.5, Z=-5.5)
    num_steps = 28
    p_top = Vector((-21.5, 16.5, Z_NAVE))
    p_bot = Vector((-10.5, 12.0, Z_CRYPT))
    for s in range(num_steps):
        t = s / (num_steps - 1)
        pos = p_top.lerp(p_bot, t)
        add_box(bm_crypt, (pos.x, pos.y, pos.z - 0.15), (0.65, 2.8, 0.32), rot_euler=(0, 0, -0.38))


def build_cloister_and_crypt() -> None:
    reset_scene()
    mats = get_materials()

    bm_stone = bmesh.new()
    bm_floor = bmesh.new()
    bm_mosaic = bmesh.new()
    bm_gold = bmesh.new()
    bm_crypt = bmesh.new()
    bm_marble = bmesh.new()
    bm_candle = bmesh.new()

    # ── 1. East & West Perimeter Cloister Galleries (walkable outer arcades) ──
    add_cloister_gallery_wing(bm_stone, bm_floor, x_center=26.2, y_start=-46.0, y_end=-15.2)
    add_cloister_gallery_wing(bm_stone, bm_floor, x_center=-26.2, y_start=-46.0, y_end=-15.2)
    # North-East & North-West Cloister Connectors to the 2 Domed Sacristies
    add_cloister_gallery_wing(bm_stone, bm_floor, x_center=26.2, y_start=15.2, y_end=26.0)
    add_cloister_gallery_wing(bm_stone, bm_floor, x_center=-26.2, y_start=15.2, y_end=26.0)

    # ── 2. Two Monumental Domed Sacristies (NE & NW Corners) ──
    add_sacristy_pavilion(bm_stone, bm_floor, bm_mosaic, bm_gold, cx=27.5, cy=32.5)
    add_sacristy_pavilion(bm_stone, bm_floor, bm_mosaic, bm_gold, cx=-27.5, cy=32.5)

    # ── 3. Subterranean Neo-Gothic Crypt & Gaudí's Tomb ──
    build_crypt(bm_crypt, bm_floor, bm_gold, bm_marble, bm_candle)

    finalize_bmesh_object(bm_stone, "Cloister_And_Sacristies", mats["sandstone_warm"], smooth=False, uv_scale=0.15)
    finalize_bmesh_object(bm_floor, "Cloister_And_Crypt_Floor", mats["floor_marble"], smooth=False, uv_scale=0.18)
    finalize_bmesh_object(bm_mosaic, "Sacristy_Trencadis", mats["trencadis"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_gold, "Cloister_Gold", mats["gold_accent"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_crypt, "Crypt_Architecture", mats["crypt_stone"], smooth=False, uv_scale=0.16)
    finalize_bmesh_object(bm_marble, "Crypt_AltarAndGaudiTomb", mats["white_marble"], smooth=False, uv_scale=0.30)
    finalize_bmesh_object(bm_candle, "Crypt_VotiveCandles", mats["candle_glow"], smooth=True, uv_scale=0.50)

    export_glb(os.path.join(MODEL_DIR, "cloister_crypt.glb"))


if __name__ == "__main__":
    build_cloister_and_crypt()
