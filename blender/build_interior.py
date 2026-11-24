"""Build the complete Sagrada Família interior (columns, vaults, galleries, stained glass, altar, pews).

Every plan position, radius and level comes from blender/layout.py (the master layout shared with the
web runtime); only local construction details (wall thicknesses, window tiers, vault depths) live here.
"""

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
from layout import (
    ALTAR_POS,
    ALTAR_SIZE,
    APSE_CENTER,
    APSE_CHAPEL_BACK_R,
    APSE_CHAPEL_FRONT_R,
    APSE_PIER_ANGLES_DEG,
    APSE_PRESBYTERY_RING_R,
    APSE_SIDE_WALL_X,
    APSE_WALL_OUTER_R,
    BALDACHIN_DIAMETER,
    BALDACHIN_Z,
    COLUMNS,
    CORNER_STAIRS,
    CRYPT_STAIRS,
    CRYPT_STAIR_TOP_DOOR,
    GALLERIES,
    GALLERY_LINKS,
    GALLERY_LINK_HALF_WIDTH,
    GLORY_INNER_Y,
    NAVE_HALF_WIDTH,
    NAVE_NORTH_Y,
    NAVE_WALL_THICKNESS,
    NAVE_WINDOW_BAY_Y,
    PRESBYTERY_FRONT_Y,
    PRESBYTERY_HALF_WIDTH,
    PRESBYTERY_RADIUS,
    PRESBYTERY_STEPS,
    PRESBYTERY_TREAD,
    TRANSEPT_EXT_WALL_Y,
    TRANSEPT_HALF_LENGTH,
    TRANSEPT_HALF_WIDTH,
    Z_AMBULATORY_VAULT,
    Z_APSE_SKYLIGHT_FOOT,
    Z_APSE_TRIFORIUM_VAULT,
    Z_CHILDREN_CHOIR,
    Z_JESUS_DECK,
    Z_CRYPT_VAULT_LOW,
)
from interior_lib import (
    HyperboloidBay,
    VaultField,
    add_annulus_sector,
    add_column_canopy,
    add_square_tile_with_hole,
    add_wave_balustrade,
    add_xz_prism,
    build_bay_heightfield,
    build_double_twist_column_mesh,
    build_hyperboloid_bay,
    finalize_oriented,
)

# ── Plan (from layout) ──
ACX, ACY = APSE_CENTER                    # apse = crypt = Mary tower axis (0, 23.25)
R_PRES = APSE_PRESBYTERY_RING_R           # 7.5   ring of 10 presbytery columns
R_CH0, R_CH1 = APSE_CHAPEL_FRONT_R, APSE_CHAPEL_BACK_R   # 15 / 19 chapels
R_WALL = APSE_WALL_OUTER_R                # 20.25
NAVE_WALL_X = NAVE_HALF_WIDTH + 0.5 * NAVE_WALL_THICKNESS   # 23.0 wall centre (22.5 .. 23.5)
NAVE_WALL_OUT = NAVE_HALF_WIDTH + NAVE_WALL_THICKNESS        # 23.5
TR_WALL_Y = 0.5 * (TRANSEPT_HALF_WIDTH + TRANSEPT_EXT_WALL_Y)  # 15.5 transept arm wall centre (15 .. 16)
TR_WALL_T = TRANSEPT_EXT_WALL_Y - TRANSEPT_HALF_WIDTH          # 1.0
ROW_YS = [NAVE_NORTH_Y - GRID * k for k in range(5)]          # column rows -15 .. -45
LAST_ROW_Y = ROW_YS[-1]                                       # -45: the half bays run to the Glory wall
TRIBUNE_BRIDGE_X = 28.7                   # layout WALK_BRIDGES entry.* start x on the tribunes
TRIBUNE_POCKET_Y = 15.0 + 1.2             # outer entry bridges at |y| 15 with half width 1.2 reach |y| 16.2

# ── Local construction values ──
# Window tiers. The choir galleries are at Z_GALLERY 16.2 (slab 15.5 .. 16.2), so the lower tier
# stops at 13.8 and the upper tier starts 1.2 m above the gallery deck (handover §6).
Z_DADO = 3.6
Z_LOW_TOP = 13.8
Z_UP_BOT = Z_GALLERY + 1.2                # 17.4
Z_UP_TOP = 29.0
Z_WALL_TOP = Z_AISLE_VAULT + 0.6          # 31.8 nave / transept wall cornice top
Z_APSE_WALL_TOP = Z_AMBULATORY_VAULT + 1.4  # 32.6
GALLERY_SLAB = 0.7                        # furnishings hang a chandelier from the soffit at 15.4
CLERESTORY_TRACERY = False
AISLE_DEPTH, AISLE_THROAT = 3.0, 1.0      # 7.5 x 7.5 m bays
NAVE_DEPTH, NAVE_THROAT = 4.0, 1.6        # 15 x 7.5 m bays
# Crossing: the Jesus 56 m deck (towers; slab 55.3 .. 56.0 over r 2.25 .. 7.9) sits ON the crossing vault,
# so the vault must stay below 55.3 there (handover §5/§6). The layout's Z_CROSSING_VAULT 61.2 cannot be
# met together with Z_JESUS_DECK 56; the collar is put just under the deck slab (reported as a layout problem).
Z_CROSS_COLLAR = Z_JESUS_DECK - 0.7 - 0.2  # 55.1 (gold ring top 55.21 < 55.3)
CROSS_DEPTH, CROSS_THROAT = 5.5, 2.4      # 15 x 15 m crossing; collar open r >= 2.35 for the glass elevator (r 2.08)
APSE_THROAT = 3.4                         # great apse hyperboloid; crown Z_APSE_VAULT 76.2 (< 76.6 Mary deck limit)
AMB_DEPTH = 3.5
CRYPT_DOOR_H = 2.8                        # crypt stair top doors in the transept north wall (>= 2.4)


def apse_pt(deg: float, r: float) -> tuple[float, float]:
    a = math.radians(deg)
    return (ACX + r * math.cos(a), ACY + r * math.sin(a))


RING_DEG = [180.0 * k / 9.0 for k in range(10)]          # presbytery columns 0 .. 180 in 20° steps (layout)
RING_PTS = [apse_pt(d, R_PRES) for d in RING_DEG]


def apse_depth_for_skylight() -> float:
    """Depth parameter so the apse hyperboloid passes through the ring of presbytery columns exactly at the
    foot of the great skylight (Z_APSE_SKYLIGHT_FOOT 61.2), crown at Z_APSE_VAULT 76.2."""
    poly = apse_polygon()
    r_far = max(math.hypot(px - ACX, py - ACY) for px, py in poly)
    c = (Z_APSE_VAULT - Z_APSE_SKYLIGHT_FOOT) / math.sqrt((R_PRES / APSE_THROAT) ** 2 - 1.0)
    return c * math.sqrt((r_far / APSE_THROAT) ** 2 - 1.0)


def apse_polygon() -> list[tuple[float, float]]:
    return [(-GRID, PRESBYTERY_FRONT_Y), (GRID, PRESBYTERY_FRONT_Y)] + RING_PTS


def strip_bay(x: float, width: float, z_top: float, depth: float, throat: float, tag: str) -> HyperboloidBay:
    """Half bay between the last column row (y -45) and the Glory wall (y -47.75): the hyperboloid of the
    neighbouring full bay mirrored about y -45, clipped to the strip (meets the full bay edge exactly)."""
    y0, y1 = GLORY_INNER_Y, LAST_ROW_Y
    poly = [(x - 0.5 * width, y0), (x + 0.5 * width, y0), (x + 0.5 * width, y1), (x - 0.5 * width, y1)]
    full = HyperboloidBay.rect(x, LAST_ROW_Y + 0.5 * GRID, width, GRID, z_top, depth, throat, tag)
    b = HyperboloidBay(x, LAST_ROW_Y - 0.5 * GRID, poly, z_top, depth, throat, tag + "Strip")
    b.c = full.c
    return b


def build_vault_field() -> VaultField:
    """All vault bays as hyperboloids clipped to their bay polygons (one per column bay)."""
    f = VaultField()
    for sx in (-1, 1):
        for bx in (11.25, 18.75):
            for by in NAVE_WINDOW_BAY_Y:
                f.add(HyperboloidBay.rect(sx * bx, by, GRID, GRID, Z_AISLE_VAULT, AISLE_DEPTH, AISLE_THROAT, "aisle"))
            f.add(strip_bay(sx * bx, GRID, Z_AISLE_VAULT, AISLE_DEPTH, AISLE_THROAT, "aisle"))
        for bx in (11.25, 18.75, 26.25):
            for sy in (-1, 1):
                f.add(HyperboloidBay.rect(sx * bx, sy * 11.25, GRID, GRID, Z_AISLE_VAULT, AISLE_DEPTH, AISLE_THROAT, "aisle"))
            f.add(HyperboloidBay.rect(sx * bx, 0.0, GRID, 2 * GRID, Z_NAVE_VAULT, NAVE_DEPTH, NAVE_THROAT, "nave"))
    for by in [-11.25] + NAVE_WINDOW_BAY_Y + [11.25]:
        f.add(HyperboloidBay.rect(0.0, by, 2 * GRID, GRID, Z_NAVE_VAULT, NAVE_DEPTH, NAVE_THROAT, "nave"))
    f.add(strip_bay(0.0, 2 * GRID, Z_NAVE_VAULT, NAVE_DEPTH, NAVE_THROAT, "nave"))
    f.add(HyperboloidBay.rect(0.0, 0.0, 2 * GRID, 2 * GRID, Z_CROSS_COLLAR, CROSS_DEPTH, CROSS_THROAT, "crossing"))
    # Apse: presbytery straight part (y 15 .. 23.25) + the ring of 10 presbytery columns about APSE_CENTER
    f.add(HyperboloidBay(ACX, ACY, apse_polygon(), Z_APSE_VAULT, apse_depth_for_skylight(), APSE_THROAT, "apse"))
    # Ambulatory (collar Z_AMBULATORY_VAULT): one cell per presbytery bay, out to the chapel back wall
    for i in range(9):
        a0, a1 = RING_DEG[i], RING_DEG[i + 1]
        poly = [apse_pt(a0, R_PRES), apse_pt(a0, R_CH1), apse_pt(a1, R_CH1), apse_pt(a1, R_PRES)]
        cxy = apse_pt(0.5 * (a0 + a1), 0.5 * (R_PRES + R_CH1))
        f.add(HyperboloidBay(cxy[0], cxy[1], poly, Z_AMBULATORY_VAULT, AMB_DEPTH, AISLE_THROAT, "ambulatory"))
    for sx in (-1, 1):  # straight part of the ambulatory, y 15 .. 23.25
        for xa, xb in ((R_PRES, R_CH0), (R_CH0, APSE_SIDE_WALL_X)):
            poly = [(sx * xa, PRESBYTERY_FRONT_Y), (sx * xb, PRESBYTERY_FRONT_Y), (sx * xb, ACY), (sx * xa, ACY)]
            f.add(HyperboloidBay(sx * 0.5 * (xa + xb), 0.5 * (PRESBYTERY_FRONT_Y + ACY), poly, Z_AMBULATORY_VAULT, AMB_DEPTH, AISLE_THROAT, "ambulatory"))
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


def box_span(bm, x0, x1, y0, y1, z0, z1, rot=0.0):
    """Axis box from extents (optionally rotated about its centre)."""
    if x1 - x0 < 1e-4 or y1 - y0 < 1e-4 or z1 - z0 < 1e-4:
        return
    add_box(bm, (0.5 * (x0 + x1), 0.5 * (y0 + y1), 0.5 * (z0 + z1)), (x1 - x0, y1 - y0, z1 - z0), rot_euler=(0, 0, rot))


def build_presbytery(bm_floor: bmesh.types.BMesh, bm_glass: bmesh.types.BMesh) -> None:
    """Platform at Z_ALTAR: half disc r PRESBYTERY_RADIUS north of APSE_CENTER + rectangle |x| <= 9 from the
    front edge (y 15) to the centre, 12 steps down to the nave floor (y 15 -> 11.4). The crypt's central vault
    (crown Z_CRYPT_VAULT_CENTRAL 2.4) rises into the hollow under the deck; its clerestory light comes through
    glazed openings in the 2 m riser faces (layout: 'windows in the 2 m face')."""
    R, HW, FY = PRESBYTERY_RADIUS, PRESBYTERY_HALF_WIDTH, PRESBYTERY_FRONT_Y
    deck_t = 0.5
    z_deck0 = Z_ALTAR - deck_t                      # 2.7 > crypt central crown 2.4
    z_riser0 = Z_CRYPT_VAULT_LOW                    # risers close the hollow down to the crypt vault crowns
    col_x = GRID                                    # basalt columns (±7.5, 15) stand on the front corners
    col_r = 1.0
    # deck: half disc + rectangle, with notches round the two front-corner columns
    add_annulus_sector(bm_floor, ACX, ACY, 0.0, R, 0.0, math.pi, z_deck0, Z_ALTAR, segs=24)
    box_span(bm_floor, -HW, HW, FY + col_r, ACY, z_deck0, Z_ALTAR)
    for xa, xb in ((-HW, -col_x - col_r), (-col_x + col_r, col_x - col_r), (col_x + col_r, HW)):
        box_span(bm_floor, xa, xb, FY, FY + col_r, z_deck0, Z_ALTAR)
    # risers with glazed clerestory openings (one per presbytery bay on the curve, one per straight side)
    w_lo, w_hi = Z_NAVE + 0.25, Z_ALTAR - 0.25
    t = 0.4
    for i in range(9):
        a0, a1 = math.radians(RING_DEG[i]), math.radians(RING_DEG[i + 1])
        am, da = 0.5 * (a0 + a1), a1 - a0
        win = 0.55 * da
        add_annulus_sector(bm_floor, ACX, ACY, R - t, R, a0, a1, z_riser0, w_lo, segs=3)
        add_annulus_sector(bm_floor, ACX, ACY, R - t, R, a0, a1, w_hi, z_deck0, segs=3)
        add_annulus_sector(bm_floor, ACX, ACY, R - t, R, a0, am - 0.5 * win, w_lo, w_hi, segs=1)
        add_annulus_sector(bm_floor, ACX, ACY, R - t, R, am + 0.5 * win, a1, w_lo, w_hi, segs=1)
        gx, gy = ACX + (R - 0.5 * t) * math.cos(am), ACY + (R - 0.5 * t) * math.sin(am)
        add_box(bm_glass, (gx, gy, 0.5 * (w_lo + w_hi)), (2 * R * math.sin(0.5 * win), 0.1, w_hi - w_lo), rot_euler=(0, 0, am - math.pi / 2))
    for sx in (-1, 1):
        x0, x1 = sorted((sx * (HW - t), sx * HW))
        yw0, yw1 = FY + 2.6, ACY - 1.6
        box_span(bm_floor, x0, x1, FY, ACY, z_riser0, w_lo)
        box_span(bm_floor, x0, x1, FY, ACY, w_hi, z_deck0)
        box_span(bm_floor, x0, x1, FY, yw0, w_lo, w_hi)
        box_span(bm_floor, x0, x1, yw1, ACY, w_lo, w_hi)
        add_box(bm_glass, (sx * (HW - 0.5 * t), 0.5 * (yw0 + yw1), 0.5 * (w_lo + w_hi)), (0.1, yw1 - yw0, w_hi - w_lo))
    box_span(bm_floor, -HW, HW, FY, FY + t, z_riser0, z_deck0)          # front riser (behind the steps)
    # floor of the light chamber between the riser and the crypt clerestory (r 7.75 .. riser)
    add_annulus_sector(bm_floor, ACX, ACY, R_PRES + 0.25, R - t, 0.0, math.pi, z_riser0, z_riser0 + 0.2, segs=18)
    box_span(bm_floor, -(HW - t), HW - t, FY + t, 17.0, z_riser0, z_riser0 + 0.2)
    for sx in (-1, 1):
        x0, x1 = sorted((sx * (R_PRES + 0.25), sx * (HW - t)))
        box_span(bm_floor, x0, x1, 17.0, ACY, z_riser0, z_riser0 + 0.2)
    # 12 steps (tread PRESBYTERY_TREAD) following the runtime ramp 3.2 -> 1.2 over y 15 -> 11.4
    y_foot = FY - PRESBYTERY_STEPS * PRESBYTERY_TREAD
    spans = [(-HW, -col_x - col_r, False), (-col_x - col_r, -col_x + col_r, True), (-col_x + col_r, col_x - col_r, False),
             (col_x - col_r, col_x + col_r, True), (col_x + col_r, HW, False)]
    for i in range(PRESBYTERY_STEPS):
        ya, yb = FY - (i + 1) * PRESBYTERY_TREAD, FY - i * PRESBYTERY_TREAD
        z_top = Z_NAVE + (Z_ALTAR - Z_NAVE) * (0.5 * (ya + yb) - y_foot) / (FY - y_foot)
        for xa, xb, at_col in spans:
            if at_col and yb > FY - col_r:
                continue   # leave the column base free
            box_span(bm_floor, xa, xb, ya, yb, Z_NAVE - 0.2, z_top)


def build_interior() -> None:
    reset_scene()
    mats = get_materials()
    vault = build_vault_field()
    apse_bay = next(b for b in vault.bays if b.tag == "apse")
    amb_bays = [b for b in vault.bays if b.tag == "ambulatory"]
    # foot of the apse clerestory drum = lowest ambulatory vault height on the ring of presbytery columns
    drum_feet = RING_PTS + [(sx * GRID, PRESBYTERY_FRONT_Y) for sx in (-1, 1)]
    apse_drum_z0 = min(b.height(px, py) for b in amb_bays for (px, py) in b.poly
                       if any(math.hypot(px - qx, py - qy) < 0.01 for qx, qy in drum_feet)) - 0.3

    bm_glass_east = bmesh.new()
    bm_glass_west = bmesh.new()
    bm_glass_apse = bmesh.new()

    # ── 1. Marble floor (nave to the Glory wall, transept, apse ring) + presbytery ──
    bm_floor = bmesh.new()
    zf0 = Z_NAVE - 0.7
    box_span(bm_floor, -NAVE_WALL_OUT, NAVE_WALL_OUT, GLORY_INNER_Y - 0.3, PRESBYTERY_FRONT_Y, zf0, Z_NAVE)
    for sx in (-1, 1):
        x0, x1 = sorted((sx * NAVE_WALL_OUT, sx * (TRANSEPT_HALF_LENGTH + 0.3)))
        box_span(bm_floor, x0, x1, -TRANSEPT_EXT_WALL_Y, TRANSEPT_EXT_WALL_Y, zf0, Z_NAVE)
        # apse straight part beside the presbytery (no floor over the crypt's central vault)
        x0, x1 = sorted((sx * PRESBYTERY_HALF_WIDTH, sx * R_WALL))
        box_span(bm_floor, x0, x1, PRESBYTERY_FRONT_Y, ACY, zf0, Z_NAVE)
        # threshold of the crypt stair top door through the transept north wall
        st = next(s for s in CRYPT_STAIRS if s["x"] * sx > 0)
        x0, x1 = sorted((sx * R_WALL, st["x"] + sx * CRYPT_STAIR_TOP_DOOR["halfWidth"]))
        box_span(bm_floor, x0, x1, CRYPT_STAIR_TOP_DOOR["yWall"][0], CRYPT_STAIR_TOP_DOOR["yWall"][1] + 0.1, zf0, Z_NAVE)
    add_annulus_sector(bm_floor, ACX, ACY, PRESBYTERY_RADIUS, R_WALL, 0.0, math.pi, zf0, Z_NAVE, segs=28)
    build_presbytery(bm_floor, bm_glass_apse)
    finalize_bmesh_object(bm_floor, "Interior_MarbleFloor", mats["floor_marble"], smooth=False, uv_scale=0.16)

    # ── 2. High altar (ALTAR_POS on Z_ALTAR), heptagonal baldachin, organ pipes on the children's choir ──
    ax, ay = ALTAR_POS
    al, ad, ah = ALTAR_SIZE
    bm_altar = bmesh.new()
    add_box(bm_altar, (ax, ay, Z_ALTAR + 0.08), (al + 1.13, ad + 0.65, 0.16))
    add_box(bm_altar, (ax, ay, Z_ALTAR + 0.16 + 0.5 * (ah - 0.3)), (al, ad, ah - 0.3))
    add_box(bm_altar, (ax, ay, Z_ALTAR + ah - 0.08), (al + 0.35, ad + 0.3, 0.12))
    add_box(bm_altar, (ax, ay, Z_ALTAR + ah + 0.05), (al + 0.6, ad + 0.5, 0.14))
    finalize_bmesh_object(bm_altar, "Interior_HighAltar", mats["porphyry_red"], smooth=False, uv_scale=0.35)

    bm_gold = bmesh.new()
    z_mensa = Z_ALTAR + ah + 0.12
    add_box(bm_gold, (ax, ay - 0.5 * ad - 0.03, Z_ALTAR + 0.16 + 0.5 * (ah - 0.3)), (al - 0.3, 0.06, ah - 0.45))
    add_cylinder(bm_gold, Vector((ax, ay, z_mensa)), Vector((ax, ay, z_mensa + 0.09)), 0.18, 0.12, segments=10)
    add_cylinder(bm_gold, Vector((ax, ay, z_mensa + 0.09)), Vector((ax, ay, z_mensa + 0.91)), 0.042, 0.032, segments=8)
    add_cylinder(bm_gold, Vector((ax - 0.28, ay, z_mensa + 0.65)), Vector((ax + 0.28, ay, z_mensa + 0.65)), 0.035, 0.035, segments=8)
    # Heptagonal baldachin (Ø BALDACHIN_DIAMETER) hanging at BALDACHIN_Z
    bal_z, bal_r = BALDACHIN_Z, 0.5 * BALDACHIN_DIAMETER
    for i in range(7):
        a0 = 2.0 * math.pi * i / 7.0 + math.pi / 2
        a1 = 2.0 * math.pi * (i + 1) / 7.0 + math.pi / 2
        p0 = Vector((ax + bal_r * math.cos(a0), ay + bal_r * math.sin(a0), bal_z))
        p1 = Vector((ax + bal_r * math.cos(a1), ay + bal_r * math.sin(a1), bal_z))
        add_cylinder(bm_gold, p0, p1, 0.16, 0.16, segments=8, cap=True)
        add_cylinder(bm_gold, p0, p0 + Vector((0, 0, 1.2)), 0.12, 0.03, segments=8)
        add_cylinder(bm_gold, p0, p0 - Vector((0, 0, 2.2)), 0.025, 0.025, segments=6)
        add_cylinder(bm_gold, p0 - Vector((0, 0, 2.2)), p0 - Vector((0, 0, 2.7)), 0.17, 0.09, segments=10)
        add_cylinder(bm_gold, p0, Vector((ax, ay, bal_z + 1.4)), 0.1, 0.1, segments=8)
        z_hang = (apse_bay.height(p0.x, p0.y) if apse_bay.contains(p0.x, p0.y) else Z_APSE_SKYLIGHT_FOOT) - 1.0
        add_cylinder(bm_gold, p0 + Vector((0, 0, 0.6)), Vector((p0.x, p0.y, z_hang)), 0.035, 0.035, segments=6)
    # Suspended crucifix below the baldachin
    add_cylinder(bm_gold, Vector((ax, ay, bal_z - 4.2)), Vector((ax, ay, bal_z - 0.5)), 0.12, 0.12, segments=8)
    add_cylinder(bm_gold, Vector((ax - 1.3, ay, bal_z - 1.8)), Vector((ax + 1.3, ay, bal_z - 1.8)), 0.1, 0.1, segments=8)
    # Organ pipes in the axial chapel bay of the children's choir (furnishings casing at r 17)
    org_r = 0.5 * (R_CH0 + R_CH1)
    for i in range(-7, 8):
        ang = math.pi / 2 + i * 0.4 / org_r
        ox, oy = ACX + (org_r + 0.35) * math.cos(ang), ACY + (org_r + 0.35) * math.sin(ang)
        h = 5.2 - abs(i) * 0.24 + (0.9 if i % 2 == 0 else 0.0)
        add_cylinder(bm_gold, Vector((ox, oy, Z_CHILDREN_CHOIR + 0.5)), Vector((ox, oy, Z_CHILDREN_CHOIR + 0.5 + h)), 0.1, 0.1, segments=8)

    # ── 3. Gaudí's forest of double-twist columns (layout.COLUMNS) ──
    col_meshes, col_dims = {}, {}
    for n, key, mat_key in ((12, "Porphyry", "porphyry_red"), (10, "Basalt", "basalt_dark"), (8, "Granite", "granite_grey"), (6, "Sandstone", "sandstone_warm")):
        col_meshes[key], col_dims[key] = build_double_twist_column_mesh(f"Mesh_Col_{key}", mats[mat_key], n)

    bm_branches = bmesh.new()
    bm_lamps = bmesh.new()  # lamps in the secondary knots + oculus lamps (CandleGlow = runtime lamp group)
    diag = [math.pi * (0.25 + 0.5 * k) for k in range(4)]
    counters: dict[str, int] = {}
    pres_i = 0
    for c in COLUMNS:
        kind = c["kind"].capitalize()
        cx, cy, z_foot, group = c["x"], c["y"], c["z"], c["group"]
        z_top = z_foot + col_dims[kind]["total"]
        if group == "presbytery":
            ang = math.atan2(cy - ACY, cx - ACX)
            place_instance(f"Col_Granite_Apse_{pres_i}", col_meshes["Granite"], (cx, cy, z_foot), rot_z=ang)
            pres_i += 1
            # canopy reaches out to the ambulatory vault; one vertical limb carries the apse clerestory drum
            add_column_canopy(bm_branches, bm_lamps, cx, cy, z_top, [ang - 0.75, ang + 0.75], 3.8, 0.30, vault, twigs=3, fallback_z=Z_AMBULATORY_VAULT - 3.0)
            add_swept_tube(bm_branches, [Vector((cx, cy, z_top - 0.2)), Vector((cx, cy, 0.5 * (z_top + apse_drum_z0))), Vector((cx, cy, apse_drum_z0))], [0.34, 0.30, 0.36], segments=7)
            continue
        idx = counters.get(kind, 0)
        counters[kind] = idx + 1
        place_instance(f"Col_{kind}_{idx}", col_meshes[kind], (cx, cy, z_foot))
        if group == "crossing":
            add_column_canopy(bm_branches, bm_lamps, cx, cy, z_top, [math.pi / 8 + k * math.pi / 4 for k in range(8)], 5.0, 0.42, vault, twigs=3, fallback_z=Z_AISLE_VAULT)
        elif group == "crossingRing":
            if abs(abs(cx) - GRID) < 0.01:
                angs = [k * math.pi / 3 + math.pi / 6 for k in range(6)]
            elif abs(abs(cy) - GRID) < 0.01:
                angs = [k * math.pi / 3 for k in range(6)]
            else:
                angs = diag
            add_column_canopy(bm_branches, bm_lamps, cx, cy, z_top, angs, 4.4, 0.36, vault, twigs=3, fallback_z=Z_AISLE_VAULT)
        elif group in ("nave", "transept"):
            add_column_canopy(bm_branches, bm_lamps, cx, cy, z_top, diag, 3.8, 0.30, vault, twigs=3, fallback_z=Z_AISLE_VAULT)
        else:  # aisle (6-point sandstone): carries the choir galleries
            add_column_canopy(bm_branches, bm_lamps, cx, cy, z_top, diag, 3.2, 0.24, vault, twigs=2, fallback_z=Z_AISLE_VAULT)
            sxs = 1.0 if cx > 0 else -1.0
            x_edge = GALLERIES["east"][0]
            add_swept_tube(bm_branches, [Vector((cx, cy, z_top - 0.2)), Vector((cx + sxs * 0.45, cy, z_top + 0.6)), Vector((sxs * (x_edge + 0.5), cy, Z_GALLERY - GALLERY_SLAB - 0.02))], [0.22, 0.2, 0.18], segments=6)

    # Evangelist symbols as lamps on the knots of the four porphyry crossing columns, facing the crossing.
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

    # ── 4. Choir galleries, transept tribunes, links and corner stairs (all at Z_GALLERY) ──
    bm_gal = bmesh.new()
    zg0 = Z_GALLERY - GALLERY_SLAB
    gE, gW, gS = GALLERIES["east"], GALLERIES["west"], GALLERIES["south"]
    for (x0, y0, x1, y1) in (gE, gW):
        box_span(bm_gal, x0, x1, y0, y1, zg0, Z_GALLERY)
        xe, sgn = (x0, 1.0) if x0 > 0 else (x1, -1.0)
        add_wave_balustrade(bm_gal, (xe, y0), (xe, y1), (sgn, 0.0), Z_GALLERY)
        # north end: balustrade from the inner edge to the start of the tribune link
        link_x0 = abs(GALLERY_LINKS[0][0][0]) - GALLERY_LINK_HALF_WIDTH - 0.1
        add_wave_balustrade(bm_gal, (xe, y1), (sgn * link_x0, y1), (0.0, -1.0), Z_GALLERY, amp=0.2)
        for ry in ROW_YS[1:-1]:   # beams on the column rows under the slab
            box_span(bm_gal, min(x0, x1), max(x0, x1), ry - 0.32, ry + 0.32, zg0 - 0.8, zg0)
    # south (cantoria over the Glory doors) with round holes for the corner stairs
    hole_xs = sorted(cs["x"] for cs in CORNER_STAIRS)
    cs0 = CORNER_STAIRS[0]
    tile = 0.5 * (gS[3] - gS[1])          # 2.5: square tile centred on each stair (y -47.75 .. -42.75)
    box_span(bm_gal, hole_xs[0] + tile, hole_xs[1] - tile, gS[1], gS[3], zg0, Z_GALLERY)
    for hx in hole_xs:
        add_square_tile_with_hole(bm_gal, hx, cs0["y"], tile, cs0["hole"], zg0, Z_GALLERY, segs=20)
        box_span(bm_gal, hx - tile, hx + tile, gS[1], cs0["y"] - tile, zg0, Z_GALLERY)   # strip to the Glory wall
        xo0, xo1 = (hx + tile, gS[2]) if hx > 0 else (gS[0], hx - tile)
        box_span(bm_gal, xo0, xo1, gS[1], gS[3], zg0, Z_GALLERY)
    add_wave_balustrade(bm_gal, (gW[2], gS[3]), (gE[0], gS[3]), (0.0, -1.0), Z_GALLERY)
    # transept tribunes inside the Nativity / Passion walls (towers' entry bridges start at x ±28.7)
    for key in ("nativityTribune", "passionTribune"):
        x0, y0, x1, y1 = GALLERIES[key]
        box_span(bm_gal, x0, x1, y0, y1, zg0, Z_GALLERY)
        xe, sgn = (x0, 1.0) if x0 > 0 else (x1, -1.0)
        # continue the tribune into the wall pockets up to the towers' filler decks (x ±28.7 .. ±30, |y| 15 .. 16.2)
        xa, xb = sorted((xe, sgn * TRIBUNE_BRIDGE_X))
        for sy in (-1, 1):
            ya, yb = sorted((sy * y1, sy * TRIBUNE_POCKET_Y))
            box_span(bm_gal, xa, xb, ya, yb, zg0, Z_GALLERY)
        link_y = GALLERY_LINKS[0][1][1]
        gap0, gap1 = link_y - GALLERY_LINK_HALF_WIDTH - 0.6, link_y + GALLERY_LINK_HALF_WIDTH + 0.6
        add_wave_balustrade(bm_gal, (xe, gap1 if gap0 < y0 else y0), (xe, y1), (sgn, 0.0), Z_GALLERY)
        for py in (-7.5, 0.0, 7.5):
            box_span(bm_gal, min(x0, x1), max(x0, x1), py - 0.3, py + 0.3, zg0 - 0.8, zg0)
    # straight links gallery -> tribune (layout GALLERY_LINKS, half width 1.3) with low parapets
    for (p0, p1) in GALLERY_LINKS:
        a = Vector((p0[0], p0[1], 0.0))
        b = Vector((p1[0], p1[1], 0.0))
        d = b - a
        ang = math.atan2(d.y, d.x)
        m = (a + b) * 0.5
        L = d.length + 0.6
        add_box(bm_gal, (m.x, m.y, Z_GALLERY - 0.5 * GALLERY_SLAB), (L, 2 * GALLERY_LINK_HALF_WIDTH, GALLERY_SLAB), rot_euler=(0, 0, ang))
        for side in (-1, 1):
            nx, ny = -math.sin(ang) * side * (GALLERY_LINK_HALF_WIDTH - 0.12), math.cos(ang) * side * (GALLERY_LINK_HALF_WIDTH - 0.12)
            add_box(bm_gal, (m.x + nx, m.y + ny, Z_GALLERY + 0.5), (L - 2.4, 0.24, 1.0), rot_euler=(0, 0, ang))
    # children's choir above the seven apse chapels (r 15 .. 19 at Z_CHILDREN_CHOIR) — visual, not a runtime level
    add_annulus_sector(bm_gal, ACX, ACY, R_CH0, R_CH1, 0.0, math.pi, Z_CHILDREN_CHOIR - 0.6, Z_CHILDREN_CHOIR, segs=28)
    for k in range(20):
        a0, a1 = math.pi * k / 20, math.pi * (k + 1) / 20
        p0 = Vector((ACX + (R_CH0 + 0.2) * math.cos(a0), ACY + (R_CH0 + 0.2) * math.sin(a0), Z_CHILDREN_CHOIR + 1.0))
        p1 = Vector((ACX + (R_CH0 + 0.2) * math.cos(a1), ACY + (R_CH0 + 0.2) * math.sin(a1), Z_CHILDREN_CHOIR + 1.0))
        add_cylinder(bm_gal, p0, p1, 0.12, 0.12, segments=5, cap=False)
        add_cylinder(bm_gal, p0 - Vector((0, 0, 0.95)), p0, 0.06, 0.05, segments=5, cap=False)

    # Corner spiral stairs nave -> galleries (layout CORNER_STAIRS: centre, radii, turns, phase)
    bm_corner_stairs = bmesh.new()
    for cs in CORNER_STAIRS:
        scx, scy = cs["x"], cs["y"]
        sgn = 1.0 if scx > 0 else -1.0     # same handedness as before (runtime corner-stair logic)
        r_mid = 0.5 * (cs["rInner"] + cs["rOuter"])
        width = cs["rOuter"] - cs["rInner"]
        n_st = 64
        add_cylinder(bm_gal, Vector((scx, scy, cs["z0"])), Vector((scx, scy, cs["z1"] + 1.15)), cs["rInner"], cs["rInner"] - 0.02, segments=12)
        for si in range(n_st):
            t = si / (n_st - 1)
            ang = math.radians(cs["phaseDeg"]) + sgn * t * cs["turns"] * 2.0 * math.pi
            z_s = cs["z0"] + t * (cs["z1"] - cs["z0"])
            add_box(bm_corner_stairs, (scx + r_mid * math.cos(ang), scy + r_mid * math.sin(ang), z_s - 0.11), (width, 0.56, 0.22), rot_euler=(0.0, 0.0, ang))
    finalize_bmesh_object(bm_corner_stairs, "Interior_CornerStairs", mats["sandstone_warm"], smooth=False, uv_scale=0.18, bake_ao=False)
    finalize_bmesh_object(bm_gal, "Interior_Galleries", mats["sandstone_warm"], smooth=False, uv_scale=0.18)

    bm_walls = bmesh.new()

    # ── 5. Hyperboloid vaults: one ruled hyperboloid per bay, collars = oculi with lamps ──
    bm_vault_hyp = bmesh.new()
    bm_collar = bmesh.new()  # green/gold trencadís bands at the collars
    bm_gold_field = bmesh.new()  # golden mosaic field of the apse vault
    for bay in vault.bays:
        if bay.tag.endswith("Strip"):
            build_bay_heightfield(bay, bm_vault_hyp, nu=16 if bay.tag.startswith("nave") else 8, nv=4)
            continue
        n_r = 48 if bay.tag in ("crossing", "apse") else (40 if bay.tag == "nave" else 32)
        # the crossing collar stays OPEN: the glass elevator of the Jesus tower rises through it
        build_hyperboloid_bay(bay, bm_vault_hyp, bm_collar, bm_gold, None if bay.tag == "crossing" else bm_lamps, n_rulings=n_r)
        if bay.tag == "apse":
            gb = HyperboloidBay(bay.cx, bay.cy, [(bay.cx + 7.0 * math.cos(2 * math.pi * k / 24), bay.cy + 7.0 * math.sin(2 * math.pi * k / 24)) for k in range(24)], bay.z_top - 0.04, 1.0, bay.a)
            gb.c = bay.c
            build_hyperboloid_bay(gb, bm_gold_field, None, None, None, n_rulings=36, v_fracs=(0.0, 0.3, 0.65, 1.0))

    bm_vault = bmesh.new()

    # Apse clerestory drum on the ring of presbytery columns: from the ambulatory vault springing up to the
    # edge of the great apse hyperboloid; two window tiers (below / above the triforium level 46.2).
    drum_segments = [(RING_PTS[i], RING_PTS[i + 1], True) for i in range(9)]
    for sx in (-1, 1):
        drum_segments.append(((sx * GRID, PRESBYTERY_FRONT_Y), (sx * GRID, ACY), False))
    for (x0, y0), (x1, y1), is_window in drum_segments:
        mx, my = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        seg_len = math.hypot(x1 - x0, y1 - y0)
        rot = math.atan2(y1 - y0, x1 - x0)
        z_top = max(apse_bay.height(x0, y0), apse_bay.height(x1, y1)) + 0.8
        if not is_window:
            add_box(bm_vault, (mx, my, 0.5 * (apse_drum_z0 + z_top)), (seg_len + 0.6, 0.8, z_top - apse_drum_z0), rot_euler=(0, 0, rot))
            continue
        tiers = [(apse_drum_z0 + 3.0, Z_APSE_TRIFORIUM_VAULT - 0.6), (Z_APSE_TRIFORIUM_VAULT + 0.9, z_top - 2.2)]
        zs = [apse_drum_z0] + [z for t in tiers for z in t] + [z_top]
        for za, zb in zip(zs[0::2], zs[1::2]):   # solid bands
            add_box(bm_vault, (mx, my, 0.5 * (za + zb)), (seg_len + 0.6, 0.8, zb - za), rot_euler=(0, 0, rot))
        for w_z0, w_z1 in tiers:
            for end in (0.0, 1.0):
                px, py = x0 + (x1 - x0) * end, y0 + (y1 - y0) * end
                add_box(bm_vault, (px, py, 0.5 * (w_z0 + w_z1)), (0.9, 0.9, w_z1 - w_z0), rot_euler=(0, 0, rot))
            add_box(bm_glass_apse, (mx, my, 0.5 * (w_z0 + w_z1)), (seg_len - 0.8, 0.14, w_z1 - w_z0), rot_euler=(0, 0, rot))
            nx, ny = (ACX - mx) / R_PRES * 0.22, (ACY - my) / R_PRES * 0.22
            add_cylinder(bm_walls, Vector((mx + nx, my + ny, w_z0)), Vector((mx + nx, my + ny, w_z1)), 0.09, 0.09, segments=6, cap=False)
            for zt in (w_z0 + 0.33 * (w_z1 - w_z0), w_z0 + 0.66 * (w_z1 - w_z0)):
                tx, ty = math.cos(rot) * 0.5 * (seg_len - 0.8), math.sin(rot) * 0.5 * (seg_len - 0.8)
                add_cylinder(bm_walls, Vector((mx + nx - tx, my + ny - ty, zt)), Vector((mx + nx + tx, my + ny + ty, zt)), 0.08, 0.08, segments=6, cap=False)

    # Diaphragm between the north arm of the crossing and the apse vault (y = 15)
    z_dia = max(apse_bay.height(x, PRESBYTERY_FRONT_Y) for x in (-GRID, 0.0, GRID)) + 1.0
    add_box(bm_vault, (0.0, PRESBYTERY_FRONT_Y, 0.5 * (Z_NAVE_VAULT - 4.2 + z_dia)), (2 * GRID + 0.4, 0.8, z_dia - (Z_NAVE_VAULT - 4.2)))

    # Upper crossing drum walls bridging from the 46.2 vaults up to the crossing collar (below the 56 m deck)
    zc0, zc1 = Z_NAVE_VAULT - 1.7, Z_CROSS_COLLAR
    for sx in (-1, 1):
        add_box(bm_vault, (sx * 7.6, 0.0, 0.5 * (zc0 + zc1)), (0.8, 15.4, zc1 - zc0))
        add_box(bm_vault, (0.0, sx * 7.6, 0.5 * (zc0 + zc1)), (15.4, 0.8, zc1 - zc0))

    # Central nave clerestory walls (aisle roofs 31.2 -> nave vault 46.2), crossing south arm to the Glory wall
    for sx in (-1, 1):
        for cy in [-11.25] + NAVE_WINDOW_BAY_Y:
            add_box(bm_vault, (sx * 7.6, cy - 3.75, 37.5), (0.9, 2.2, 16.0))
            add_box(bm_vault, (sx * 7.6, cy, 43.8), (0.9, 5.5, 3.2))
            add_box(bm_vault, (sx * 7.6, cy, 31.8), (0.9, 5.5, 2.5))
        box_span(bm_vault, sx * 7.6 - 0.45, sx * 7.6 + 0.45, GLORY_INNER_Y - 0.3, LAST_ROW_Y + 1.1, Z_AISLE_VAULT - 0.6, Z_NAVE_VAULT + 0.8)
        # north arm of the crossing (y 7.5 .. 15): solid walls between the arm bay and the transept aisles
        box_span(bm_vault, sx * 7.6 - 0.45, sx * 7.6 + 0.45, GRID, PRESBYTERY_FRONT_Y, Z_AISLE_VAULT - 0.6, Z_NAVE_VAULT + 0.8)

    # Transept clerestory upper walls (transept side aisles 31.2 -> central transept vault 46.2)
    for sy in (-1, 1):
        for sx in (-1, 1):
            for cx_bay in (11.25, 18.75, 26.25):
                px = sx * cx_bay
                add_box(bm_vault, (px + sx * 3.75, sy * 7.6, 38.5), (2.2, 0.95, 16.0))
                add_box(bm_vault, (px, sy * 7.6, 44.0), (5.6, 0.95, 3.6))
                add_box(bm_vault, (px, sy * 7.6, 32.0), (5.6, 0.95, 3.0))

    # Backing decks above the vaults so no sky slits leak between the vault rosettes
    yd0 = GLORY_INNER_Y - 0.3
    for sx in (-1, 1):
        box_span(bm_vault, sx * 7.3 if sx > 0 else -NAVE_WALL_OUT, NAVE_WALL_OUT if sx > 0 else -7.3, yd0, -7.3, Z_AISLE_VAULT + 0.08, Z_AISLE_VAULT + 0.63)
        add_box(bm_vault, (sx * 19.0, 11.25, Z_AISLE_VAULT + 0.35), (23.0, 8.2, 0.55))
        add_box(bm_vault, (sx * 19.0, -11.25, Z_AISLE_VAULT + 0.35), (23.0, 8.2, 0.55))
        x0, x1 = sorted((sx * (GRID + 0.4), sx * R_WALL))
        box_span(bm_vault, x0, x1, PRESBYTERY_FRONT_Y, ACY, Z_AISLE_VAULT + 0.08, Z_AISLE_VAULT + 0.63)   # apse straight part
    box_span(bm_vault, -7.9, 7.9, yd0, -7.3, Z_NAVE_VAULT + 0.12, Z_NAVE_VAULT + 0.77)
    box_span(bm_vault, -7.9, 7.9, 7.3, PRESBYTERY_FRONT_Y, Z_NAVE_VAULT + 0.12, Z_NAVE_VAULT + 0.77)          # north arm
    # transept ceiling backing strictly OUTSIDE the crossing so the elevator rises open through the oculus
    add_box(bm_vault, (19.05, 0.0, Z_NAVE_VAULT + 0.45), (22.9, 15.8, 0.65))
    add_box(bm_vault, (-19.05, 0.0, Z_NAVE_VAULT + 0.45), (22.9, 15.8, 0.65))

    bmesh.ops.recalc_face_normals(bm_vault, faces=bm_vault.faces)
    merge_bmesh_into(bm_vault_hyp, bm_vault)
    finalize_oriented(bm_vault_hyp, "Interior_HyperboloidVaults", mats["vault_stone"], smooth=True, uv_scale=0.14, ao_dist=4.0)
    finalize_oriented(bm_collar, "Interior_GoldAccents_VaultTrencadis", mats["trencadis"], smooth=True, uv_scale=0.6, ao=False)
    finalize_oriented(bm_gold_field, "Interior_GoldAccents_ApseMosaic", mats["gold_accent"], smooth=True, uv_scale=0.4, ao=False)
    finalize_bmesh_object(bm_gold, "Interior_GoldAccents", mats["gold_accent"], smooth=True, uv_scale=0.35)
    # 'LanternAndCandleGlow' keeps the lamps out of the collision BVH; 'CandleGlow' material = runtime lamp group
    finalize_bmesh_object(bm_lamps, "Interior_KnotLamps_LanternAndCandleGlow", mats["candle_glow"], smooth=True, uv_scale=0.5, bake_ao=False)

    # ── 6. Enclosure walls + stained glass ──
    # Nave side walls (x ±22.5 .. ±23.5) from the transept to the Glory wall
    for sx, bm_glass in ((1, bm_glass_east), (-1, bm_glass_west)):
        wx = sx * NAVE_WALL_X
        for ry in ROW_YS:
            ya, yb = (ry - 1.05, min(ry + 1.05, NAVE_NORTH_Y)) if ry < NAVE_NORTH_Y - 0.1 else (ry - 1.05, ry)
            box_span(bm_walls, min(wx - sx * 0.7, wx + sx * 0.7), max(wx - sx * 0.7, wx + sx * 0.7), ya, yb, 0.0, Z_WALL_TOP)
        for yc in NAVE_WINDOW_BAY_Y:
            add_box(bm_walls, (wx, yc, 0.5 * Z_DADO), (NAVE_WALL_THICKNESS, 5.6, Z_DADO))
            add_box(bm_walls, (wx, yc, 0.5 * (Z_LOW_TOP + Z_UP_BOT)), (NAVE_WALL_THICKNESS, 5.6, Z_UP_BOT - Z_LOW_TOP))
            add_box(bm_walls, (wx, yc, 0.5 * (Z_UP_TOP + Z_WALL_TOP)), (NAVE_WALL_THICKNESS + 0.4, 5.6, Z_WALL_TOP - Z_UP_TOP))
            for z0, z1 in ((Z_DADO, Z_LOW_TOP), (Z_UP_BOT, Z_UP_TOP)):
                add_box(bm_glass, (wx, yc, 0.5 * (z0 + z1)), (0.16, 5.2, z1 - z0))
                add_gaudi_window_tracery(bm_walls, (wx - sx * 0.25, yc, 0.5 * (z0 + z1)), 5.2, z1 - z0, facing="X")
            if CLERESTORY_TRACERY:
                add_gaudi_window_tracery(bm_walls, (sx * 7.6 - sx * 0.2, yc, 37.6), 5.1, 9.2, facing="X")
            add_box(bm_glass, (sx * 7.6, yc, 37.6), (0.14, 5.1, 9.2))           # clerestory glass
        # last half bay to the Glory wall: solid (corner stair behind it)
        box_span(bm_walls, min(wx - sx * 0.5, wx + sx * 0.5), max(wx - sx * 0.5, wx + sx * 0.5), GLORY_INNER_Y - 0.3, LAST_ROW_Y, 0.0, Z_WALL_TOP)

    # Transept clerestory stained glass panes
    for sx, bm_glass in ((1, bm_glass_east), (-1, bm_glass_west)):
        for sy in (-1, 1):
            for cx_bay in (11.25, 18.75, 26.25):
                add_box(bm_glass, (sx * cx_bay, sy * 7.6, 38.0), (5.4, 0.16, 9.2))

    # Transept arm walls (y ±15 .. ±16). North: from the apse side wall (x ±19) with the crypt stair top door;
    # south: from the nave wall. Both leave a pocket at gallery level where the outer tower entry bridges
    # (y ±15, half width 1.2) start on the tribune at x ±28.7.
    z_br0, z_br1 = Z_GALLERY, Z_GALLERY + 2.6
    for sx, bm_glass in ((1, bm_glass_east), (-1, bm_glass_west)):
        for sy in (-1, 1):
            y0, y1 = sorted((sy * TRANSEPT_HALF_WIDTH, sy * TRANSEPT_EXT_WALL_Y))

            def wx_span(a: float, b: float, z0: float, z1: float) -> None:
                xa, xb = sorted((sx * a, sx * b))
                box_span(bm_walls, xa, xb, y0, y1, z0, z1)

            win_a, win_b = 23.4, 27.0
            if sy > 0:
                st = next(s for s in CRYPT_STAIRS if s["x"] * sx > 0)
                hw = CRYPT_STAIR_TOP_DOOR["halfWidth"]
                d0, d1 = abs(st["x"]) - hw, abs(st["x"]) + hw
                wx_span(APSE_SIDE_WALL_X, d0, 0.0, Z_WALL_TOP)
                wx_span(d0, d1, 0.0, Z_NAVE - 0.05)
                wx_span(d0, d1, Z_NAVE + CRYPT_DOOR_H, Z_WALL_TOP)
                wx_span(d1, win_a, 0.0, Z_WALL_TOP)
            else:
                wx_span(NAVE_HALF_WIDTH, win_a, 0.0, Z_WALL_TOP)
            lo0, lo1 = 6.8, 13.4
            wx_span(win_a, win_b, 0.0, lo0)
            wx_span(win_a, win_b, lo1, Z_UP_BOT)
            wx_span(win_a, win_b, Z_UP_TOP, Z_WALL_TOP)
            # pier to the façade wall with the bridge pocket (tribune edge -> façade, |y| 15 .. 16.2 kept free
            # for the towers' filler deck); an outer skin beyond |y| 16.2 closes the pocket
            x_tri = GALLERIES["nativityTribune"][0]
            wx_span(win_b, TRANSEPT_HALF_LENGTH, 0.0, z_br0)
            wx_span(win_b, TRANSEPT_HALF_LENGTH, z_br1, Z_WALL_TOP)
            wx_span(win_b, x_tri, z_br0, z_br1)
            xa, xb = sorted((sx * x_tri, sx * TRANSEPT_HALF_LENGTH))
            ys0, ys1 = sorted((sy * (TRIBUNE_POCKET_Y + 0.01), sy * (TRIBUNE_POCKET_Y + 0.35)))
            box_span(bm_walls, xa, xb, ys0, ys1, z_br0 - GALLERY_SLAB, z_br1 + 0.3)
            xm, wwin = sx * 0.5 * (win_a + win_b), win_b - win_a - 0.4
            for z0, z1 in ((lo0, lo1), (Z_UP_BOT, Z_UP_TOP)):
                add_box(bm_glass, (xm, sy * TR_WALL_Y, 0.5 * (z0 + z1)), (wwin, 0.16, z1 - z0))
                add_gaudi_window_tracery(bm_walls, (xm, sy * (TR_WALL_Y - 0.25), 0.5 * (z0 + z1)), wwin, z1 - z0, facing="Y")

    # Apse: straight side walls (x ±19 .. ±20.25, y 15 .. 23.25) with an upper window
    r_wc = 0.5 * (R_CH1 + R_WALL)
    for sx in (-1, 1):
        x0, x1 = sorted((sx * APSE_SIDE_WALL_X, sx * R_WALL))
        ya, yb = PRESBYTERY_FRONT_Y, ACY
        wy0, wy1 = ya + 1.6, yb - 1.0
        box_span(bm_walls, x0, x1, ya, yb, 0.0, Z_UP_BOT)
        box_span(bm_walls, x0, x1, ya, yb, Z_UP_TOP, Z_APSE_WALL_TOP)
        box_span(bm_walls, x0, x1, ya, wy0, Z_UP_BOT, Z_UP_TOP)
        box_span(bm_walls, x0, x1, wy1, yb, Z_UP_BOT, Z_UP_TOP)
        add_box(bm_glass_apse, (sx * r_wc, 0.5 * (wy0 + wy1), 0.5 * (Z_UP_BOT + Z_UP_TOP)), (0.16, wy1 - wy0, Z_UP_TOP - Z_UP_BOT))
        add_cylinder(bm_walls, Vector((sx * (APSE_SIDE_WALL_X + 0.2), 0.5 * (wy0 + wy1), Z_UP_BOT)), Vector((sx * (APSE_SIDE_WALL_X + 0.2), 0.5 * (wy0 + wy1), Z_UP_TOP)), 0.1, 0.1, segments=6, cap=False)

    # Apse: seven chapels between the wall piers (APSE_PIER_ANGLES_DEG) at r 15 .. 19, wall to r 20.25.
    # Chapels reach up to the children's choir deck; above it the wall carries the upper windows.
    piers = [math.radians(a) for a in APSE_PIER_ANGLES_DEG]
    for a in piers:
        cxp, cyp = ACX + 0.5 * (R_CH0 + R_CH1) * math.cos(a), ACY + 0.5 * (R_CH0 + R_CH1) * math.sin(a)
        add_box(bm_walls, (cxp, cyp, 0.5 * (Z_CHILDREN_CHOIR - 0.6)), (R_CH1 - R_CH0 + 0.2, 1.0, Z_CHILDREN_CHOIR - 0.6), rot_euler=(0, 0, a))
        cxp, cyp = ACX + (r_wc - 0.2) * math.cos(a), ACY + (r_wc - 0.2) * math.sin(a)
        add_box(bm_walls, (cxp, cyp, 0.5 * Z_APSE_WALL_TOP), (R_WALL - R_CH1 + 0.6, 1.4, Z_APSE_WALL_TOP), rot_euler=(0, 0, a))
    for i in range(len(piers) - 1):
        a0, a1 = piers[i], piers[i + 1]
        am = 0.5 * (a0 + a1)
        chord = 2.0 * r_wc * math.sin(0.5 * (a1 - a0))
        px, py = ACX + r_wc * math.cos(am), ACY + r_wc * math.sin(am)
        rz = am - math.pi / 2.0
        for z0, z1 in ((0.0, Z_DADO), (Z_LOW_TOP - 0.2, Z_UP_BOT), (Z_UP_TOP + 0.4, Z_APSE_WALL_TOP)):
            add_box(bm_walls, (px, py, 0.5 * (z0 + z1)), (chord + 0.2, R_WALL - R_CH1, z1 - z0), rot_euler=(0, 0, rz))
        glass_w = chord - 1.6
        tx, ty = ACX + (R_CH1 + 0.1) * math.cos(am), ACY + (R_CH1 + 0.1) * math.sin(am)
        for z0, z1 in ((Z_DADO, Z_LOW_TOP - 0.2), (Z_UP_BOT, Z_UP_TOP + 0.4)):
            add_box(bm_glass_apse, (px, py, 0.5 * (z0 + z1)), (glass_w, 0.16, z1 - z0), rot_euler=(0, 0, rz))
            add_gaudi_window_tracery(bm_walls, (tx, ty, 0.5 * (z0 + z1)), glass_w, z1 - z0 - 0.4, rot_z=rz)

    # Apse roof: tapering sandstone skirt from the wall cornice up to the Tower of Mary (concentric)
    drum_segs = 24
    tiers_apse = [(Z_APSE_WALL_TOP - 0.2, R_WALL + 0.05), (40.0, 17.4), (47.0, 13.4), (53.0, 8.9)]
    out_rings, in_rings = [], []
    for z_t, r_t in tiers_apse:
        ro, ri = [], []
        for i in range(drum_segs + 1):
            ang = math.pi * i / drum_segs
            ca, sa = math.cos(ang), math.sin(ang)
            ro.append(bm_walls.verts.new((ACX + r_t * ca, ACY + r_t * sa, z_t)))
            ri.append(bm_walls.verts.new((ACX + (r_t - 0.65) * ca, ACY + (r_t - 0.65) * sa, z_t)))
        out_rings.append(ro)
        in_rings.append(ri)
    for ti in range(len(out_rings) - 1):
        for i in range(drum_segs):
            bm_walls.faces.new((out_rings[ti][i], out_rings[ti][i + 1], out_rings[ti + 1][i + 1], out_rings[ti + 1][i]))
            bm_walls.faces.new((in_rings[ti][i + 1], in_rings[ti][i], in_rings[ti + 1][i], in_rings[ti + 1][i + 1]))
    for i in range(drum_segs):
        bm_walls.faces.new((out_rings[-1][i], out_rings[-1][i + 1], in_rings[-1][i + 1], in_rings[-1][i]))
        bm_walls.faces.new((in_rings[0][i], in_rings[0][i + 1], out_rings[0][i + 1], out_rings[0][i]))
    for i in range(0, drum_segs + 1, 3):
        for ti in range(len(out_rings) - 1):
            add_cylinder(bm_walls, out_rings[ti][i].co.copy(), out_rings[ti + 1][i].co.copy(), 0.38, 0.24, segments=6, cap=False)
    # close the two ends of the half-cone above the flat roof of the apse straight part (y = APSE_CENTER)
    for sx in (-1, 1):
        prof = [(sx * (GRID + 0.4), Z_AISLE_VAULT + 0.6)] + [(sx * r_t, z_t) for z_t, r_t in tiers_apse] + [(sx * (GRID + 0.4), tiers_apse[-1][0])]
        if sx < 0:
            prof.reverse()
        add_xz_prism(bm_walls, prof, ACY - 0.5, ACY)

    finalize_bmesh_object(bm_walls, "Interior_NaveWalls", mats["sandstone_warm"], smooth=False, uv_scale=0.14)

    # Stained glass UVs stretched 0..1 per window pane so the vertical colour gradient maps bottom->top
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

    # ── 7. Wooden pews (central nave), cross aisles on every column row, Glory door band kept free ──
    bm_pew = bmesh.new()
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
    py = -9.6
    while py > -43.2 + 0.4:   # furnishings: keep y < -43.2 free (Glory doors, fonts)
        if all(abs(py - ry) >= 1.25 for ry in ROW_YS):
            for sx in (-1, 1):
                place_instance(f"Pew_{pew_idx}", mesh_pew, (sx * 4.2, py, Z_NAVE))
                pew_idx += 1
        py -= 1.45

    export_glb(os.path.join(MODEL_DIR, "interior.glb"))


if __name__ == "__main__":
    build_interior()
