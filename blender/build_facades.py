"""Build the 3 monumental facades (Nativity, Passion, Glory), exterior roofs & fruit-basket pinnacles."""

from __future__ import annotations

import math
import os
import sys
import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
import layout as L
from layout import TOWER_SHELL_Z0, Z_AMBULATORY_VAULT, Z_GALLERY, ground_z
from common import (
    GRID,
    MODEL_DIR,
    Z_AISLE_VAULT,
    Z_NAVE,
    Z_NAVE_VAULT,
    add_box,
    add_cylinder,
    add_ellipsoid,
    add_lathe,
    add_swept_tube,
    apply_dripping_relief,
    bevel_sharp_edges,
    export_glb,
    finalize_bmesh_object,
    get_materials,
    reset_scene,
)
from facades_lib import (
    GLYPH_H,
    GLYPH_J,
    GLYPH_S,
    add_arch_tube,
    add_bone_column_v2,
    add_cloud_mass,
    add_double_twist_shaft,
    add_fruit_basket,
    add_hyperboloid_lantern,
    add_hexa,
    add_letter_strokes,
    add_palm_capital,
    add_section_annulus,
    add_section_drum,
    interval_complement,
    merge_bmesh_into,
    add_palm_trunk,
    add_pelican,
    add_rock_peak,
    add_root_flare,
    add_ruled_loft,
    parabolic_arch_points,
    add_triangular_lantern,
    add_trumpet_angel,
)


def add_pointed_gable(
    bm: bmesh.types.BMesh,
    center_xy: tuple[float, float],
    z_base: float,
    width: float,
    height: float,
    thickness: float,
    facing: str = "X+",
    rot_z: float | None = None,
    crockets: bool = True,
) -> None:
    """Create a TRUE smooth sculpted pointed Gothic/Gaudí triangular gable with parabolic taper & edge crocket ribs."""
    cx, cy = center_xy
    if rot_z is not None:
        # Local U along gable width, V along gable depth (normal pointing outward)
        ux, uy = math.cos(rot_z), math.sin(rot_z)
        vx, vy = -math.sin(rot_z), math.cos(rot_z)
    elif facing in ("X+", "X-"):
        ux, uy = 0.0, 1.0
        vx, vy = (1.0, 0.0) if facing == "X+" else (-1.0, 0.0)
    else:
        ux, uy = 1.0, 0.0
        vx, vy = (0.0, 1.0) if facing == "Y+" else (0.0, -1.0)

    def pt(u: float, v: float, z: float) -> Vector:
        return Vector((cx + u * ux + v * vx, cy + u * uy + v * vy, z))

    # Build a smooth 5-tier concave-parabolic triangular prism (zero blocky stair steps!)
    tiers = 5
    half_t = thickness * 0.5
    front_left: list[bmesh.types.BMVert] = []
    front_right: list[bmesh.types.BMVert] = []
    back_left: list[bmesh.types.BMVert] = []
    back_right: list[bmesh.types.BMVert] = []

    for i in range(tiers):
        t = i / tiers  # 0 .. 0.8
        # Slight graceful Gothic ogee/catenary inward curve toward the apex
        half_w = width * 0.5 * ((1.0 - t) ** 1.08)
        z = z_base + t * height
        front_left.append(bm.verts.new(pt(-half_w, half_t, z)))
        front_right.append(bm.verts.new(pt(half_w, half_t, z)))
        back_left.append(bm.verts.new(pt(-half_w, -half_t, z)))
        back_right.append(bm.verts.new(pt(half_w, -half_t, z)))

    # Sharp pointed apex ridge
    v_apex_f = bm.verts.new(pt(0.0, half_t * 0.72, z_base + height))
    v_apex_b = bm.verts.new(pt(0.0, -half_t * 0.72, z_base + height))

    # Bottom cap
    bm.faces.new((back_left[0], back_right[0], front_right[0], front_left[0]))

    # Side & face quads up to top tier
    for i in range(tiers - 1):
        bm.faces.new((front_left[i], front_right[i], front_right[i + 1], front_left[i + 1]))
        bm.faces.new((back_right[i], back_left[i], back_left[i + 1], back_right[i + 1]))
        bm.faces.new((back_left[i], front_left[i], front_left[i + 1], back_left[i + 1]))
        bm.faces.new((front_right[i], back_right[i], back_right[i + 1], front_right[i + 1]))

    # Triangular apex faces
    bm.faces.new((front_left[-1], front_right[-1], v_apex_f))
    bm.faces.new((back_right[-1], back_left[-1], v_apex_b))
    bm.faces.new((back_left[-1], front_left[-1], v_apex_f, v_apex_b))
    bm.faces.new((front_right[-1], back_right[-1], v_apex_b, v_apex_f))

    # Sculpted edge molding ribs + Gothic botanical crocket buds along both rising gable slopes!
    if crockets:
        p_apex = pt(0.0, half_t * 0.85, z_base + height)
        for s_u in (-1.0, 1.0):
            p_base = pt(s_u * width * 0.5, half_t * 0.95, z_base)
            add_cylinder(bm, p_base, p_apex, min(0.32, width * 0.045), min(0.16, width * 0.025), segments=6, cap=False)
            n_buds = 5 if height >= 14.0 else 3
            for b in range(1, n_buds + 1):
                tb = b / (n_buds + 1.0)
                u_b = s_u * width * 0.5 * ((1.0 - tb) ** 1.08)
                z_b = z_base + tb * height
                p_bud0 = pt(u_b, half_t * 0.85, z_b)
                p_bud1 = pt(u_b + s_u * 0.38, half_t * 1.05, z_b + 0.55)
                add_cylinder(bm, p_bud0, p_bud1, 0.22, 0.08, segments=5, cap=True)
        # Sharp finial spire crowning the gable apex
        add_cylinder(
            bm,
            pt(0.0, 0.0, z_base + height - 0.2),
            pt(0.0, 0.0, z_base + height + min(2.4, height * 0.14)),
            min(0.28, width * 0.04),
            0.05,
            segments=6,
            cap=True,
        )


def add_turtle_column_base(
    bm_stone: bmesh.types.BMesh,
    cx: float,
    cy: float,
    z_floor: float,
    is_sea_turtle: bool,
) -> float:
    """Sculpt Gaudí's iconic Nativity Facade Turtle (East/Sea) & Tortoise (West/Mountain) column pedestals!"""
    # Low carved plinth cushion
    add_cylinder(bm_stone, Vector((cx, cy, z_floor)), Vector((cx, cy, z_floor + 0.32)), 1.05, 0.96, segments=10)
    # Sculpted domed carapace shell (wider & flatter for Sea Turtle, higher & domed for Land Tortoise)
    shell_z = z_floor + 0.72
    ret = bmesh.ops.create_icosphere(bm_stone, subdivisions=2, radius=1.0)
    for v in ret["verts"]:
        v.co.x = cx + v.co.x * (0.98 if is_sea_turtle else 0.86)
        v.co.y = cy + v.co.y * (0.76 if is_sea_turtle else 0.72)
        v.co.z = shell_z + max(-0.26, v.co.z) * (0.46 if is_sea_turtle else 0.62)
    # Carved stone head projecting outward toward Plaça de Gaudí (+X)
    add_cylinder(bm_stone, Vector((cx + 0.72, cy, shell_z - 0.05)), Vector((cx + 1.38, cy, shell_z + 0.14)), 0.24, 0.18, segments=8)
    # 4 sculpted flippers (sea turtle) or sturdy legs (land tortoise)
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            p0 = Vector((cx + sx * 0.52, cy + sy * 0.48, shell_z - 0.12))
            p1 = Vector((cx + sx * (0.95 if is_sea_turtle else 0.72), cy + sy * (0.92 if is_sea_turtle else 0.68), z_floor + 0.24))
            add_cylinder(bm_stone, p0, p1, 0.22, 0.14 if is_sea_turtle else 0.20, segments=6)
    # The palm trunk (built by the caller) rises out of the carapace
    return shell_z + 0.3


def add_robed_figure(bm: bmesh.types.BMesh, base: Vector, height: float, face: float, wings: bool = False, arm_up: float = 0.0) -> None:
    """Compact sculpted robed figure (Nativity/Passion statuary): bell-shaped drapery, shoulders, head."""
    h = height
    add_lathe(
        bm, base.x, base.y,
        [(base.z, h * 0.17), (base.z + h * 0.35, h * 0.15), (base.z + h * 0.62, h * 0.13), (base.z + h * 0.78, h * 0.12), (base.z + h * 0.83, h * 0.06)],
        segments=7, cap_bottom=False, cap_top=True, phase=face, squash=(0.75, 1.0),
    )
    add_ellipsoid(bm, base + Vector((0.0, 0.0, h * 0.9)), (h * 0.075, h * 0.07, h * 0.09), subdivisions=1)
    f = Vector((math.cos(face), math.sin(face), 0.0))
    s = Vector((-math.sin(face), math.cos(face), 0.0))
    if arm_up:
        add_cylinder(bm, base + Vector((0, 0, h * 0.74)) + s * h * 0.1, base + Vector((0, 0, h * (0.74 + 0.25 * arm_up))) + s * h * 0.22 + f * h * 0.18, h * 0.04, h * 0.03, segments=5)
    if wings:
        for side in (-1, 1):
            add_ellipsoid(bm, base + Vector((0, 0, h * 0.72)) - f * h * 0.12 + s * side * h * 0.22, (h * 0.04, h * 0.16, h * 0.34), subdivisions=1, rot_z=face, roll=-side * 0.45)


def add_leaf_cluster(bm: bmesh.types.BMesh, center: Vector, radius: float, face: float, count: int = 5, seed: int = 0) -> None:
    """Carved foliage tuft: flattened, splayed leaf lobes (the facade's botanical encrustation)."""
    for i in range(count):
        a = 2.0 * math.pi * (i / count) + seed * 0.7
        tilt = 0.5 + 0.35 * math.sin(seed * 1.7 + i)
        p = center + Vector((math.cos(face) * radius * 0.3, math.sin(face) * radius * 0.3, 0.0)) \
            + Vector((-math.sin(face) * math.cos(a) * radius * 0.55, math.cos(face) * math.cos(a) * radius * 0.55, math.sin(a) * radius * 0.55))
        add_ellipsoid(bm, p, (radius * 0.18, radius * 0.55, radius * 0.28), subdivisions=1, rot_z=face + math.cos(a) * 0.6, roll=a + tilt)


def add_icicle_fringe(bm: bmesh.types.BMesh, x: float, y0: float, y1: float, z: float, count: int, max_len: float, seed: int = 0) -> None:
    """Row of hanging stone icicles / stalactites (the 'winter snow' fringe over the Nativity portals)."""
    for i in range(count):
        t = (i + 0.5) / count
        y = y0 + (y1 - y0) * t
        n = math.sin(i * 12.9898 + seed * 78.233) * 43758.5453
        n = n - math.floor(n)
        length = max_len * (0.35 + 0.65 * n) * (0.75 + 0.25 * math.sin(math.pi * t))
        r = 0.10 + 0.12 * n
        add_cylinder(bm, Vector((x, y, z + 0.05)), Vector((x + 0.06, y, z - length)), r, 0.015, segments=5, cap=False)

# ─────────────────────────────────────────────────────────────────────────────
# TRUE-LAYOUT FRAME (phase 2). Every plan position, level and extent below comes from layout.py.
# Each façade is built in a local frame: u runs along the façade, v is the outward distance from the
# crossing (Nativity v = +x, Passion v = -x, Glory v = -y). In v every façade has the same bands:
#   v0 (wallX / innerY) .. v_wf     ground wall with the doors (holy-water fonts stand at v0)
#   v_wf .. front                   cloister passage at floor level (contract: clear Z_NAVE..+3.2),
#                                   tower bases carried over it on a soffit at PASSAGE_SOFFIT_Z
#   v_t                             tower axis line; below TOWER_SHELL_Z0 (20.3) the façade owns the
#                                   mass, with a hollow for the apostle stair from Z_GALLERY (16.2) and a
#                                   doorway towards the interior tribune along each entry.* bridge
# Derived local numbers (not in layout.py) are named here and listed in the phase-2 report.
PASSAGE_SOFFIT_Z = Z_NAVE + 3.2 + 1.6        # 6.0: underside of the tower bases over the cloister passages
JAMB = 0.5                                   # archivolt tube / jamb allowance added to each layout opening
STAIR_HOLLOW_R = L.APOSTLE_STAIR["rOuter"] + 0.3   # 2.35: stair well kept free inside the tower-base band
ENTRY_DOOR_HALF = 1.3                        # contract: doorway >= 2.4 m wide along each entry bridge
ENTRY_DOOR_H = 2.6                           # contract: doorway >= 2.6 m high above Z_GALLERY
DOOR_SECTOR_HALF = math.radians(36.0)        # ring opening (chord 2 x 1.38 at r 2.35)
SLAB_DROP = 0.04                             # porch slabs / band floors sit 4 cm under the shared floor
                                             # levels so they never z-fight the cloister / tower decks
RELIEF_TOP = Z_GALLERY - 0.8                 # 15.4: above this the masses stay un-displaced (clean floor
                                             # under the stair wells)


def _superellipse_gain(ang: float, p: float) -> float:
    c, s = abs(math.cos(ang)), abs(math.sin(ang))
    return 1.0 / max(1e-6, (c ** p + s ** p) ** (1.0 / p))


def shell_section(tw: dict):
    """Outward plan multiplier of an apostle shell at TOWER_SHELL_Z0, mirroring towers'
    apostle_section(): square base (Nativity), ellipse with long axis per PASSION_SECTION (Passion),
    rounded square (Glory). The façade drums below 20.3 use it so the shell continues them."""
    z = TOWER_SHELL_Z0
    w = max(0.0, min(1.0, (tw["zRef"] + 20.0 - z) / 20.0))
    fam = tw["family"]
    gain = L.PASSION_SECTION["gain"] - 1.0
    long_x = L.PASSION_SECTION["longAxis"] == "x"

    def sec(a: float) -> float:
        if fam == "nativity":
            return 1.0 + (_superellipse_gain(a, 4.0) - 1.0) * w
        if fam == "passion":
            return 1.0 + gain * w * (math.cos(a) ** 2 if long_x else math.sin(a) ** 2)
        return 1.0 + (_superellipse_gain(a, 3.0) - 1.0) * w * 0.6
    return sec


def apostle_bases(family: str) -> list[dict]:
    """Towers of one façade with their round radius at the shell start (paraboloid law of layout)."""
    out = []
    for t in L.TOWERS:
        if t["family"] != family:
            continue
        r = L.paraboloid_radius(t["rRef"], t["zRef"], t["zApex"], TOWER_SHELL_Z0)
        out.append({"t": t, "r": r, "sec": shell_section(t), "u": t["x"] if family == "glory" else t["y"]})
    return out


class Frame:
    """Local façade frame (u along the façade, v outward, z up) -> Blender plan coordinates."""

    def __init__(self, kind: str):
        self.kind = kind
        # world angle (CCW from +X) of the local -v direction (towards the crossing / the tribunes)
        self.inward = {"nat": math.pi, "pas": 0.0, "glo": math.pi * 0.5}[kind]

    def p(self, u: float, v: float, z: float = 0.0) -> Vector:
        if self.kind == "nat":
            return Vector((v, u, z))
        if self.kind == "pas":
            return Vector((-v, u, z))
        return Vector((u, -v, z))

    def box(self, bm, u0: float, u1: float, v0: float, v1: float, z0: float, z1: float) -> None:
        if u1 - u0 < 1e-3 or v1 - v0 < 1e-3 or z1 - z0 < 1e-3:
            return
        c = self.p(0.5 * (u0 + u1), 0.5 * (v0 + v1), 0.5 * (z0 + z1))
        size = (v1 - v0, u1 - u0, z1 - z0) if self.kind in ("nat", "pas") else (u1 - u0, v1 - v0, z1 - z0)
        add_box(bm, tuple(c), size)

    def ground(self, u: float, v: float) -> float:
        return ground_z(self.p(u, v).y)


def build_facade_body(F: Frame, bm_mass, bm_clean, *, family: str, v0: float, v_wf: float, v_t: float,
                      u_half: float, portals: list[dict], z_base: float, upper_half: float, slot_front: float) -> list[dict]:
    """Structural mass of one façade on the true layout (see the frame note above).
    portals: [{"u": centre, "half": opening half width incl. jamb, "ceil": porch ceiling z, "front": v of the
    ceiling slab front}]. bm_mass may receive relief / bevels; bm_clean holds every surface that bounds a
    walk contract (door jambs below the soffit, the stair wells, the entry doorways) and stays exact."""
    zg = Z_GALLERY - SLAB_DROP
    towers = apostle_bases(family)
    r_min = min(tb["r"] for tb in towers)
    v_bf = v_t + 0.55 * r_min                      # front of the flat-faced pier blocks over the passage
    holes = [(p["u"] - p["half"], p["u"] + p["half"]) for p in portals]
    solids = interval_complement(-u_half, u_half, holes)
    for a, b in solids:
        F.box(bm_clean, a, b, v0, v_wf, z_base, PASSAGE_SOFFIT_Z)          # ground wall between the doors
        F.box(bm_mass, a, b, v0, v_wf, PASSAGE_SOFFIT_Z, RELIEF_TOP)
        F.box(bm_mass, a, b, v_wf, v_bf, PASSAGE_SOFFIT_Z, RELIEF_TOP)      # tower-base piers over the passage
    for p in portals:                                                       # porch ceilings / tympanum lintels
        F.box(bm_mass, p["u"] - p["half"] - 0.15, p["u"] + p["half"] + 0.15, v0, p["front"], p["ceil"], RELIEF_TOP)
    z_d0 = max(p["ceil"] for p in portals)
    for tb in towers:                                                       # round tower-base fronts
        c = F.p(tb["u"], v_t)
        add_section_drum(bm_mass, c.x, c.y, z_d0, RELIEF_TOP, tb["r"], tb["sec"])
        add_section_drum(bm_clean, c.x, c.y, RELIEF_TOP, zg, tb["r"], tb["sec"])
    F.box(bm_clean, -u_half, u_half, v0, v_bf, RELIEF_TOP, zg)              # clean floor under the stair band
    # Stair band Z_GALLERY .. TOWER_SHELL_Z0: hollow drum per tower, doorway towards the tribune
    v_back = v_t - STAIR_HOLLOW_R
    door_holes = [(tb["u"] - ENTRY_DOOR_HALF, tb["u"] + ENTRY_DOOR_HALF) for tb in towers]
    for a, b in interval_complement(-u_half, u_half, door_holes):
        F.box(bm_clean, a, b, v0, v_back, zg, TOWER_SHELL_Z0)
    for tb in towers:
        c = F.p(tb["u"], v_t)
        F.box(bm_clean, tb["u"] - ENTRY_DOOR_HALF, tb["u"] + ENTRY_DOOR_HALF, v0, v_back, Z_GALLERY + ENTRY_DOOR_H, TOWER_SHELL_Z0)
        a0 = F.inward + DOOR_SECTOR_HALF
        add_section_annulus(bm_clean, c.x, c.y, zg, Z_GALLERY + ENTRY_DOOR_H, STAIR_HOLLOW_R, tb["r"], tb["sec"],
                            a0, a0 + 2.0 * math.pi - 2.0 * DOOR_SECTOR_HALF, segments=16)
        add_section_annulus(bm_clean, c.x, c.y, Z_GALLERY + ENTRY_DOOR_H, TOWER_SHELL_Z0, STAIR_HOLLOW_R, tb["r"], tb["sec"], segments=16)
    inner_u = min(abs(tb["u"]) for tb in towers)
    g = inner_u - STAIR_HOLLOW_R - 0.05                                     # centre slot between the inner towers
    F.box(bm_clean, -g, g, v_back, slot_front, zg, TOWER_SHELL_Z0)
    # Upper end wall closing the transept / nave behind the façade (aisle vault, then the central vault)
    F.box(bm_mass, -upper_half, upper_half, v0, v0 + 1.1, TOWER_SHELL_Z0, Z_AISLE_VAULT + 1.2)
    F.box(bm_mass, -inner_u + 3.6, inner_u - 3.6, v0, v0 + 1.1, Z_AISLE_VAULT + 1.2, Z_NAVE_VAULT + 1.2)
    return towers


def add_parabolic_spandrel(bm, F: Frame, u_c: float, hw: float, z_spring: float, rise: float, z_top: float,
                           v_a: float, v_b: float, n: int = 12, sharp: float = 1.1) -> None:
    """Solid tympanum fill between a parabolic arch (springing at z_spring) and the lintel at z_top."""
    pts = parabolic_arch_points(Vector((u_c - hw, 0.0, z_spring)), Vector((u_c + hw, 0.0, z_spring)), rise, n, sharp)
    for p0, p1 in zip(pts[:-1], pts[1:]):
        if min(p0.z, p1.z) >= z_top - 0.05:
            continue
        add_hexa(bm, [F.p(p0.x, v_a, p0.z), F.p(p1.x, v_a, p1.z), F.p(p1.x, v_b, p1.z), F.p(p0.x, v_b, p0.z),
                      F.p(p0.x, v_a, z_top), F.p(p1.x, v_a, z_top), F.p(p1.x, v_b, z_top), F.p(p0.x, v_b, z_top)])


def build_side_stair(F: Frame, bm_steps, bm_cheek, st: dict, porch: tuple[float, float, float]) -> None:
    """Nativity / Passion entrance stair on the true layout: from Z_NAVE at the porch front (v_top) down to
    the sloped ground at its foot (v_bot). The runtime treats it as a ramp z = Z_NAVE + (ground_z(y) -
    Z_NAVE) * s (s = 0 at the top, 1 at the foot); every tread is warped along y with that law, so each
    tread centre lies on the ramp and the last riser lands exactly on ground_z(y) across the whole width."""
    v_top, v_bot = (abs(st["x1"]), abs(st["x0"])) if abs(st["x1"]) < abs(st["x0"]) else (abs(st["x0"]), abs(st["x1"]))
    W = st["halfWidth"]
    run = v_bot - v_top
    mean_drop = Z_NAVE - st["bottomZ"]
    n = max(4, round(mean_drop / 0.15))
    edges = [v_top] + [v_top + (k + 0.5) * run / n for k in range(n)] + [v_bot]

    def zt(j: int, u: float) -> float:
        return Z_NAVE + (F.ground(u, v_top) - Z_NAVE) * j / n

    for j in range(n):          # tread n is the ground itself
        va, vb = edges[j], edges[j + 1]
        cs = []
        for top in (False, True):
            for (vv, uu) in ((va, -W), (vb, -W), (vb, W), (va, W)):
                cs.append(F.p(uu, vv, zt(j, uu) if top else F.ground(uu, vv) - 0.5))
        add_hexa(bm_steps, cs)
    # Porch slab (walk surface is the runtime podium; slab top 4 cm under Z_NAVE)
    pv0, pv1, pw = porch
    cs = []
    for top in (False, True):
        for (vv, uu) in ((pv0, -pw), (pv1, -pw), (pv1, pw), (pv0, pw)):
            cs.append(F.p(uu, vv, Z_NAVE - SLAB_DROP if top else F.ground(uu, vv) - 0.6))
    add_hexa(bm_steps, cs)
    # Cheek walls along both sides, 0.9 m above the ramp line, footed below the ground
    for s in (-1.0, 1.0):
        u_in, u_out = s * W, s * (W + 0.8)
        cs = []
        for top in (False, True):
            for (vv, uu) in ((v_top, u_in), (v_bot + 0.3, u_in), (v_bot + 0.3, u_out), (v_top, u_out)):
                if top:
                    sfrac = max(0.0, min(1.0, (vv - v_top) / run))
                    z = Z_NAVE + (F.ground(uu, v_top) - Z_NAVE) * sfrac + 0.9
                else:
                    z = F.ground(uu, vv) - 0.5
                cs.append(F.p(uu, vv, z))
        add_hexa(bm_cheek, cs)


# ─────────────────────────────────────────────────────────────────────────────
# NATIVITY FAÇADE (east, Blender +X). Facts (architecture pass): 3 portals between the 4 bell towers:
#   Hope (south, -Y), Charity (centre, tallest, crowned by the cypress), Faith (north); two palm columns
#   on a turtle (sea side, south) and a tortoise (mountain side, north) between the portals; Charity
#   trumeau, Nativity group, Star, Coronation of Mary, pelican + JHS under the cypress, tau cross + dove.
#   Heights of the gables / cypress are photo-proportion estimates (LOW confidence), kept from the
#   previous pass. True layout: wall face x 30 (doors), porch to the turtle columns at x 40, towers on
#   x 34 at y +-7.5 / +-15, the cloister walk crossing the porch at x 32.5..40, stair x 40 -> 46.
# Portal table: name -> (archivolt rise, gable base z = porch ceiling, gable height, gable width, gable v)
NATIVITY_PORTAL_SHAPE = {
    "charity": (11.8, 13.2, 30.0, 9.6, 37.2),   # gable between the inner towers (their fronts flank it)
    "hope": (9.8, 11.2, 24.0, 8.4, 38.7),       # side gables just in front of the tower pairs
    "faith": (9.8, 11.2, 24.0, 8.4, 38.7),
}
NATIVITY_COLUMN_TOP = 13.6   # palm capital springing (estimate)


def nativity_portals() -> list[dict]:
    out = []
    for p in L.NATIVITY["portals"]:
        rise, gz, g_h, gw, gv = NATIVITY_PORTAL_SHAPE[p["name"]]
        out.append({"name": p["name"], "u": p["y"], "half": 0.5 * p["width"] + JAMB, "rise": rise, "gz": gz,
                    "g_h": g_h, "gw": gw, "gv": gv, "ceil": gz, "front": gv + 0.9})
    return out


def add_nativity_encrustation(bm: bmesh.types.BMesh) -> None:
    """Dense sculptural layer of the Nativity facade (decorative, non-collidable): figure groups on the
    three portal gables, foliage fringes, icicle curtains, tympanum groups, the palm capitals with their
    trumpeting angels, the Coronation of Mary, the pelican, and the crowns of Hope and Faith."""
    v0 = L.NATIVITY["wallX"]
    for pi_, p in enumerate(nativity_portals()):
        py, hw0, rise, gz, g_h, gw = p["u"], p["half"], p["rise"], p["gz"], p["g_h"], p["gw"]
        front = p["gv"] + 0.9
        central = p["name"] == "charity"
        add_icicle_fringe(bm, front - 0.15, py - gw * 0.48, py + gw * 0.48, gz, 18 if central else 14, 1.7, seed=pi_)
        add_icicle_fringe(bm, v0 + 2.2, py - hw0 * 0.8, py + hw0 * 0.8, Z_NAVE + rise - 0.6, 10, 1.3, seed=pi_ + 7)
        for tier, (dz, fh) in enumerate(((0.45, 1.9), (2.75, 1.7), (5.2, 1.5))):
            z_row = gz + dz
            t = (z_row - gz) / g_h
            hw = gw * 0.5 * ((1.0 - t) ** 1.08) - 0.6
            n = max(2, int(2 * hw / 0.95))
            for i in range(n):
                y = py - hw + (2 * hw) * (i + 0.5) / n
                if central and tier == 0 and abs(y - py) < 1.6:
                    continue
                add_robed_figure(bm, Vector((front + 0.28, y, z_row)), fh * (0.9 + 0.1 * math.sin(i * 2.3 + tier)), 0.0, wings=(tier == 2), arm_up=(0.8 if (i + tier) % 3 == 0 else 0.0))
        for side in (-1, 1):
            t = 0.42
            y = py + side * (gw * 0.5 * ((1.0 - t) ** 1.08) - 0.2)
            add_robed_figure(bm, Vector((front + 0.2, y, gz + g_h * t)), 2.6 if central else 2.1, 0.0, wings=True, arm_up=1.0)
        for side in (-1, 1):
            steps = int(g_h / 1.15)
            for k in range(steps):
                t = (k + 0.5) / steps
                y = py + side * (gw * 0.5 * ((1.0 - t) ** 1.08) + 0.15)
                add_leaf_cluster(bm, Vector((front - 0.2, y, gz + t * g_h)), 0.85 - 0.45 * t, 0.0, count=4, seed=k + pi_ * 13)
        # Tympanum group on a corbel above the doors, inside the archivolts
        zt = Z_NAVE + rise - 3.4
        vt = v0 + 1.4
        add_box(bm, (vt, py, zt - 0.15), (0.8, min(hw0 * 0.95, 3.2), 0.3))
        for i, dy in enumerate((-0.9, 0.0, 0.9)):
            add_robed_figure(bm, Vector((vt, py + dy, zt)), 2.0 if i != 1 else 1.6, 0.0, arm_up=0.5 if i == 0 else 0.0)
        if central:
            for side in (-1, 1):  # ox and mule beside the crib
                add_ellipsoid(bm, Vector((vt - 0.2, py + side * 1.75, zt + 0.55)), (0.75, 0.35, 0.4), subdivisions=1)
                add_ellipsoid(bm, Vector((vt + 0.35, py + side * 1.55, zt + 0.85)), (0.28, 0.2, 0.22), subdivisions=1)
            # Trumeau (genealogy of Jesus, serpent at its foot) — decorative, the doorway stays walkable
            xt = v0 + 0.9
            add_lathe(bm, xt, py, [(Z_NAVE, 0.42), (Z_NAVE + 0.5, 0.3), (Z_NAVE + 6.2, 0.26), (zt - 0.4, 0.34), (zt - 0.15, 0.55)], segments=8)
            coil = [Vector((xt + 0.42 * math.cos(a * 0.6), py + 0.42 * math.sin(a * 0.6), Z_NAVE + 0.3 + a * 0.06)) for a in range(18)]
            add_swept_tube(bm, coil, [0.09] * len(coil), segments=5)
            zc = gz + 18.6   # Coronation of Mary on the upper Charity gable
            add_box(bm, (front + 0.1, py, zc - 0.2), (0.8, 3.6, 0.4))
            add_robed_figure(bm, Vector((front + 0.35, py - 0.75, zc)), 2.3, 0.0)
            add_robed_figure(bm, Vector((front + 0.35, py + 0.75, zc)), 2.5, 0.0, arm_up=1.0)
            add_robed_figure(bm, Vector((front + 0.25, py + 1.85, zc)), 2.0, 0.0)
            add_pelican(bm, Vector((front - 0.2, py, gz + g_h - 6.2)), 2.2, 0.0)
        elif py < 0:
            add_rock_peak(bm, Vector((front - 0.9, py, gz + g_h - 1.4)), 4.2, 3.0, seed=2)     # Hope: Montserrat
        else:
            add_triangular_lantern(bm, Vector((front - 0.9, py, gz + g_h - 1.2)), 4.6, 1.7)  # Faith: Trinity
    for cx, cy in L.NATIVITY["turtleColumns"]:  # palm capitals and trumpeting angels
        top = Vector((cx, cy, NATIVITY_COLUMN_TOP))
        add_lathe(bm, top.x, top.y, [(top.z - 0.3, 0.45), (top.z + 0.4, 0.8), (top.z + 0.7, 0.75)], segments=8, cap_top=True)
        add_palm_capital(bm, top + Vector((0, 0, 0.6)), 2.1, fronds=9, seed=int(math.copysign(1, cy)))
        add_trumpet_angel(bm, top + Vector((0.1, 0, 0.75)), 2.9, 0.0)


def build_nativity_facade(bm_nat, bm_nat_mass, bm_nat_clean, bm_stairs_nat, bm_bronze, bm_cypress, bm_gold, bm_white) -> None:
    """East Nativity façade on the true layout (wall x 30, towers x 34, porch to x 40, stair to x 46)."""
    N = L.NATIVITY
    F = Frame("nat")
    v0 = N["wallX"]
    v_wf = N["cloisterPassage"][0]
    portals = nativity_portals()
    towers = apostle_bases("nativity")
    u_half = max(abs(tb["u"]) + tb["r"] for tb in towers)
    z_base = ground_z(-u_half) - 0.4
    charity = next(p for p in portals if p["name"] == "charity")
    build_facade_body(F, bm_nat_mass, bm_nat_clean, family="nativity", v0=v0, v_wf=v_wf, v_t=L.NATIVITY_TOWER_X,
                      u_half=u_half, portals=portals, z_base=z_base, upper_half=N["halfWidth"],
                      slot_front=charity["gv"] - 0.9)
    # Porch slab + entrance stair x 40 -> 46 down to the sloped ground, cheek walls
    build_side_stair(F, bm_stairs_nat, bm_nat_clean, N["stair"], (v0, N["frontX"], N["halfWidth"]))

    # Melting buttresses at the outer edges, footed on the ground beyond the cloister walk (x > 40)
    for sy in (-1, 1):
        zg0 = ground_z(sy * 17.4) - 0.2
        pts = [Vector((N["frontX"] + 0.6 - 0.19 * k, sy * (17.4 + 0.02 * k), zg0 + (32.4 - zg0) * k / 12.0)) for k in range(13)]
        radii = [1.75, 1.6, 1.52, 1.45, 1.42, 1.36, 1.25, 1.15, 1.02, 0.9, 0.76, 0.6, 0.35]
        add_swept_tube(bm_nat, pts, radii, segments=12, cap=True, ridge=(7, 0.22))

    for p in portals:
        py, hw0, rise, gz, g_h, gw, gv = p["u"], p["half"], p["rise"], p["gz"], p["g_h"], p["gw"], p["gv"]
        central = p["name"] == "charity"
        # Deep porch: 4 concentric parabolic archivolts between the doors (x 30) and the cloister walk
        # (x 32.5), each wider and taller than the last; their feet stay out of the walk.
        layers = 4
        step_w = 0.18 if central else 0.2
        lv = [v0 + 0.45 + k * 0.5 for k in range(layers)]
        for k in range(layers):
            hw = hw0 + k * step_w
            add_arch_tube(bm_nat, Vector((lv[k], py - hw, Z_NAVE)), Vector((lv[k], py + hw, Z_NAVE)),
                          rise + k * 0.5, 0.5, 0.4, n=14, segments=7, sharp=1.1)
        k_out = layers - 1
        inner = parabolic_arch_points(Vector((lv[0], py - hw0, Z_NAVE)), Vector((lv[0], py + hw0, Z_NAVE)), rise, 14, 1.1)
        outer = parabolic_arch_points(Vector((lv[k_out], py - hw0 - k_out * step_w, Z_NAVE)),
                                      Vector((lv[k_out], py + hw0 + k_out * step_w, Z_NAVE)), rise + k_out * 0.5, 14, 1.1)
        add_ruled_loft(bm_nat, [q + Vector((0, 0, 0.35)) for q in inner], [q + Vector((0, 0, 0.35)) for q in outer])
        add_parabolic_spandrel(bm_nat_clean, F, py, hw0, Z_NAVE, rise, gz, v0 + 0.05, v0 + 0.3, n=14)
        # Gable over each porch: Charity between the inner towers, Hope / Faith in front of the pairs
        add_pointed_gable(bm_nat, (gv, py), gz, gw, g_h, 1.8, facing="X+")
        for sy in (-1, 1):
            add_cylinder(bm_nat, Vector((gv + 0.65, py + sy * (gw * 0.36), gz - 1.4)), Vector((gv + 0.55, py + sy * (gw * 0.33), gz + 7.9)), 0.58, 0.12, segments=8)
        # Bronze doors folded open against the jambs (the walk-through stays clear)
        for sy in (-1, 1):
            add_box(bm_bronze, (v0 + 1.1, py + sy * (hw0 - 0.14), Z_NAVE + 3.0), (2.0, 0.25, 6.0))

    # Turtle (south / sea side) and tortoise (north / mountain side) carrying the two palm columns;
    # their plinths reach down to the ground because the stair starts on the column line (x 40)
    for cx, cy in N["turtleColumns"]:
        add_cylinder(bm_nat, Vector((cx, cy, ground_z(cy) - 0.2)), Vector((cx, cy, Z_NAVE + 0.02)), 1.05, 1.05, segments=10)
        shell_top = add_turtle_column_base(bm_nat, cx, cy, Z_NAVE, is_sea_turtle=(cy < 0))
        add_palm_trunk(bm_nat, cx, cy, shell_top, NATIVITY_COLUMN_TOP, 0.48, 0.4, segments=10)

    # Star of Bethlehem over the Nativity group of the Charity portal
    star_x = charity["gv"] + 1.05
    star_z = 21.8
    for k in range(8):
        ang = 2.0 * math.pi * k / 8.0
        ray_len = 1.6 if k % 2 == 0 else 1.0
        add_cylinder(bm_gold, Vector((star_x, 0.0, star_z)), Vector((star_x + 0.12, ray_len * math.cos(ang), star_z + ray_len * math.sin(ang))), 0.2, 0.04, segments=5)
    add_cylinder(bm_gold, Vector((star_x, 0.0, star_z)), Vector((star_x - 0.1, 0.9, star_z - 4.0)), 0.22, 0.03, segments=5)
    add_letter_strokes(bm_gold, Vector((charity["gv"] + 1.05, -1.3, 34.9)), Vector((0, 1, 0)), [GLYPH_J, GLYPH_H, GLYPH_S], 0.7, 0.2, 0.08)

    # Cypress Tree of Life rising above the Charity gable, between the inner towers
    tree_x = charity["gv"]
    for tier in range(8):
        t = tier / 7.0
        zt = 38.4 + t * 10.2
        rt = 2.15 * ((1.0 - t * 0.82) ** 0.85)
        n_lobes = 7 if tier < 5 else 5
        for k in range(n_lobes):
            ang = 2.0 * math.pi * k / n_lobes + tier * 0.55
            r_off = rt * 0.42
            lobe_r = rt * 0.55
            ret = bmesh.ops.create_icosphere(bm_cypress, subdivisions=1, radius=1.0)
            for v in ret["verts"]:
                v.co.x = tree_x + r_off * math.cos(ang) + v.co.x * lobe_r * 0.85
                v.co.y = r_off * math.sin(ang) + v.co.y * lobe_r * 0.85
                v.co.z = zt + v.co.z * lobe_r * 1.35
        if tier in (1, 3, 5):
            for k in range(3):
                ang = 2.0 * math.pi * k / 3.0 + tier * 0.9
                px = tree_x + (rt + 0.15) * math.cos(ang)
                py = (rt + 0.15) * math.sin(ang)
                ret_d = bmesh.ops.create_icosphere(bm_white, subdivisions=1, radius=0.26)
                for v in ret_d["verts"]:
                    v.co.x = px + v.co.x * 1.15
                    v.co.y = py + v.co.y * 0.85
                    v.co.z = zt + 0.1 + v.co.z * 0.72
    add_cylinder(bm_gold, Vector((tree_x, 0.0, 48.0)), Vector((tree_x, 0.0, 51.4)), 0.28, 0.24, segments=8)
    add_cylinder(bm_gold, Vector((tree_x, -1.45, 50.9)), Vector((tree_x, 1.45, 50.9)), 0.24, 0.24, segments=8)
    ret_d = bmesh.ops.create_icosphere(bm_white, subdivisions=1, radius=0.4)
    for v in ret_d["verts"]:
        v.co.x = tree_x + v.co.x * 1.2
        v.co.y = v.co.y * 0.8
        v.co.z = 52.0 + v.co.z * 0.6


def add_frustum(bm: bmesh.types.BMesh, base: Vector, w0: float, d0: float, w1: float, d1: float, height: float, face: float, lean: float = 0.0) -> None:
    """Faceted tapered block (Subirachs' angular planar sculpture vocabulary)."""
    f = Vector((math.cos(face), math.sin(face), 0.0))
    s = Vector((-math.sin(face), math.cos(face), 0.0))
    top = base + Vector((0, 0, height)) + f * (lean * height)
    vs = []
    for c, w, d in ((base, w0, d0), (top, w1, d1)):
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            vs.append(bm.verts.new(c + s * (sx * w * 0.5) + f * (sy * d * 0.5)))
    b, t = vs[:4], vs[4:]
    bm.faces.new(list(reversed(b)))
    bm.faces.new(t)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((b[i], b[j], t[j], t[i]))


def add_subirachs_figure(bm: bmesh.types.BMesh, base: Vector, h: float, face: float, kind: int = 0) -> None:
    """Angular Subirachs-style figure: planar robe, wedge torso, cubic head; kind 1 = helmeted soldier
    (helmets after Gaudí's La Pedrera chimneys), kind 2 = hooded mourner bending forward."""
    f = Vector((math.cos(face), math.sin(face), 0.0))
    lean = 0.12 if kind == 2 else 0.0
    add_frustum(bm, base, h * 0.32, h * 0.24, h * 0.24, h * 0.17, h * 0.55, face, lean * 0.5)
    chest = base + Vector((0, 0, h * 0.55)) + f * (lean * 0.5 * h * 0.55)
    add_frustum(bm, chest, h * 0.27, h * 0.17, h * 0.3, h * 0.15, h * 0.25, face + 0.08, lean)
    head_c = chest + Vector((0, 0, h * 0.25)) + f * (lean * h * 0.3)
    add_frustum(bm, head_c, h * 0.11, h * 0.12, h * 0.1, h * 0.11, h * 0.15, face - 0.12, lean)
    if kind == 1:
        add_frustum(bm, head_c + Vector((0, 0, h * 0.13)), h * 0.16, h * 0.16, h * 0.05, h * 0.05, h * 0.16, face, 0.0)
        add_cylinder(bm, chest + f * h * 0.1 + Vector((0, 0, -h * 0.4)), chest + f * h * 0.12 + Vector((0, 0, h * 0.55)), h * 0.025, h * 0.02, segments=4)  # spear
    elif kind == 2:
        add_frustum(bm, head_c + Vector((0, 0, h * 0.08)), h * 0.17, h * 0.18, h * 0.06, h * 0.08, h * 0.17, face, 0.25)




# ─────────────────────────────────────────────────────────────────────────────
# PASSION FAÇADE (west, Blender -X). Facts: 6 large inclined bone / sequoia columns carrying a deep
#   porch roof; pyramidal pediment of 18 bone columns; Subirachs' groups on 3 levels along an S path
#   (Crucifixion top centre); bronze Gospel doors; magic square (33) beside the Kiss of Judas.
#   Column height / lean were estimates; the true layout now fixes their feet and heads (PASSION.columns).
#   True layout: doors at x -30, towers on x -36 (elliptical base, long axis X), cloister walk at
#   x -40..-32.5, porch to x -52, stair x -52 -> -58. The pediment stands on the porch roof right at the
#   tower fronts, between the four towers.
# Portals: the layout names no Passion openings; they share the Nativity's y and widths (proposed
# layout addition PASSION.portals).
PASSION_PORTAL_CEIL = {"charity": 13.2, "hope": 11.2, "faith": 11.2}
PASSION_PEDIMENT_V = 39.2      # backing gable of the pediment (outward distance), 2.4+ m off the tower axes


def passion_portals(v_front: float) -> list[dict]:
    return [{"name": p["name"], "u": p["y"], "half": 0.5 * p["width"] + JAMB, "ceil": PASSION_PORTAL_CEIL[p["name"]],
             "front": v_front} for p in L.NATIVITY["portals"]]


def build_passion_facade(bm_pas, bm_pas_clean, bm_pcol, bm_pbones, bm_psculpt, bm_stairs_pas, bm_bronze, bm_gold) -> None:
    """West Passion façade on the true layout."""
    P = L.PASSION
    F = Frame("pas")
    v0 = abs(P["wallX"])
    v_wf = abs(P["cloisterPassage"][1])
    v_t = abs(L.PASSION_TOWER_X)
    z_roof0, z_roof1 = P["roofZ"]
    towers = apostle_bases("passion")
    u_half = max(abs(tb["u"]) + tb["r"] for tb in towers)
    v_bf = v_t + 0.55 * min(tb["r"] for tb in towers)
    portals = passion_portals(v_bf)
    build_facade_body(F, bm_pas, bm_pas_clean, family="passion", v0=v0, v_wf=v_wf, v_t=v_t, u_half=u_half,
                      portals=portals, z_base=ground_z(-u_half) - 0.4, upper_half=L.TRANSEPT_EXT_WALL_Y,
                      slot_front=PASSION_PEDIMENT_V - 0.8)
    build_side_stair(F, bm_stairs_pas, bm_pas_clean, P["stair"], (v0, abs(P["frontX"]), P["halfWidth"]))
    # Bronze Gospel doors folded open at the central jambs
    c = next(p for p in portals if p["name"] == "charity")
    for sy in (-1, 1):
        add_box(bm_bronze, tuple(F.p(sy * (c["half"] - 0.14), v0 + 1.2, Z_NAVE + 3.2)), (2.4, 0.26, 6.4))

    # THE 6 INCLINED BONE / SEQUOIA COLUMNS: foot on the porch floor, head under the porch roof
    v_roof_back, v_roof_front = v_t + STAIR_HOLLOW_R + 0.05, max(abs(cc["head"][0]) for cc in P["columns"]) + 2.4
    for i, cc in enumerate(P["columns"]):
        p0 = Vector((cc["foot"][0], cc["foot"][1], Z_NAVE))
        p1 = Vector((cc["head"][0], cc["head"][1], z_roof0 + 0.4))
        p_mid = p0.lerp(p1, 0.5) + Vector((-0.25, 0.0, 0.0))     # slight outward bow (previous pass)
        add_bone_column_v2(bm_pcol, p0, p_mid, p1, 0.92, segments=14, n=20)
        add_root_flare(bm_pbones, p0, 1.1, roots=6, seed=i)

    # Deep porch roof slab (between the tower fronts and the column heads) with a bone rib per column
    u_roof = max(abs(cc["head"][1]) for cc in P["columns"]) + 2.8
    F.box(bm_pas, -u_roof, u_roof, v_roof_back, v_roof_front, z_roof0, z_roof1)
    for cc in P["columns"]:
        hu = cc["head"][1]
        add_cylinder(bm_pas, F.p(hu, v_roof_front - 0.5, z_roof0 + 0.1), F.p(hu, v_roof_back + 0.2, z_roof0 + 0.1), 0.55, 0.45, segments=6)

    # Pyramidal pediment between the towers: backing gable + 18 bone columns like organ pipes
    pv = PASSION_PEDIMENT_V
    add_pointed_gable(bm_pas, (-pv, 0.0), z_roof1 - 0.1, 29.0, 14.5, 1.6, facing="X-", crockets=False)
    for k in range(18):
        py = -14.5 + k * (29.0 / 17.0)
        h_tri = 14.4 * (1.0 - abs(py) / 15.6) - 0.4
        q0 = Vector((-(pv + 2.3), py, z_roof1))
        q1 = Vector((-(pv + 1.7), py * 0.98, z_roof1 + max(1.0, h_tri)))
        add_bone_column_v2(bm_pbones, q0, (q0 + q1) * 0.5 + Vector((-0.15, 0.0, 0.0)), q1, 0.27, segments=7, n=10)
    add_cylinder(bm_pas, Vector((-(pv + 2.1), -15.6, z_roof1 - 0.3)), Vector((-(pv + 1.3), 0.0, 41.8)), 0.92, 0.72, segments=6)
    add_cylinder(bm_pas, Vector((-(pv + 2.1), 15.6, z_roof1 - 0.3)), Vector((-(pv + 1.3), 0.0, 41.8)), 0.92, 0.72, segments=6)
    # Angular buttress blades closing the outer porch bays (footed outside the cloister walk)
    for sy in (-1, 1):
        add_cylinder(bm_pas, F.p(sy * 17.2, 44.5, Z_NAVE), F.p(sy * 16.2, v_roof_front - 1.8, z_roof0), 0.95, 0.65, segments=6)
    add_cylinder(bm_gold, Vector((-(pv + 1.3), 0.0, 41.4)), Vector((-(pv + 1.3), 0.0, 46.2)), 0.26, 0.20, segments=8)
    add_cylinder(bm_gold, Vector((-(pv + 1.3), -1.65, 44.5)), Vector((-(pv + 1.3), 1.65, 44.5)), 0.22, 0.22, segments=8)

    # ── Subirachs' groups along the S-shaped path (decorative, non-collidable mesh) ──
    face_w = math.pi
    v_l1 = abs(P["cloisterPassage"][0]) + 1.0       # level 1 stands on the porch, just outside the walk
    for sy in (-1, 1):
        F.box(bm_pas, sy * 5.6 - 1.3, sy * 5.6 + 1.3, v_l1 - 0.9, v_l1 + 0.9, Z_NAVE, Z_NAVE + 2.0)
        for i, fi in enumerate((-0.75, 0.0, 0.75)):
            add_subirachs_figure(bm_psculpt, F.p(sy * 5.6 + fi, v_l1, Z_NAVE + 2.0), 2.3 - 0.15 * abs(fi), face_w + sy * 0.25 - fi * 0.3, kind=(1 if i == 0 else (2 if i == 2 else 0)))
    for k, y in enumerate((14.9, 13.8, 12.7)):  # Last Supper group on the far left
        add_subirachs_figure(bm_psculpt, F.p(y, v_l1 - 0.3, Z_NAVE), 2.1, face_w - 0.3, kind=2 if k == 1 else 0)
    add_cylinder(bm_pas, F.p(-4.2, v_l1 - 0.4, Z_NAVE), F.p(-4.2, v_l1 - 0.4, Z_NAVE + 4.2), 0.34, 0.30, segments=8)   # Flagellation column
    add_subirachs_figure(bm_psculpt, F.p(-4.2, v_l1 + 0.15, Z_NAVE), 2.2, face_w)
    add_box(bm_gold, tuple(F.p(5.6, v_wf + 0.02, PASSAGE_SOFFIT_Z - 0.6)), (0.14, 1.25, 1.25))   # magic square

    # Level 2 ledge (above the doors, in front of the tower bases): Way of the Cross, Veronica
    v2 = v_bf + 1.5
    F.box(bm_pas, -12.5, 12.5, v2 - 1.1, v2 + 1.1, 10.1, 10.6)
    for k, y in enumerate((-11.0, -9.9, -8.7, -5.6, -4.6, -0.6, 0.6, 4.6, 5.7, 8.6, 9.8, 11.0)):
        add_subirachs_figure(bm_psculpt, F.p(y, v2 + 0.5, 10.6), 2.1 + 0.15 * math.sin(k * 1.7), face_w + 0.2 * math.sin(k * 2.1), kind=k % 3)
    add_box(bm_bronze, tuple(F.p(0.0, v2 + 1.05, 12.9)), (0.08, 1.2, 1.5))
    # Level 3 ledge (in front of the stair band, under the porch roof): soldiers, Crucifixion, Burial
    v3 = v_bf + 1.6
    F.box(bm_pas, -12.5, 12.5, v3 - 1.0, v3 + 1.0, 16.7, 17.2)
    for k, y in enumerate((10.8, 9.6, 8.3, 6.8)):
        add_subirachs_figure(bm_psculpt, F.p(y, v3 + 0.5, 17.2), 2.1, face_w + 0.3 * math.sin(k), kind=1 if k % 2 == 0 else 0)
    for k, y in enumerate((-6.6, -7.8, -9.0, -10.2)):
        add_subirachs_figure(bm_psculpt, F.p(y, v3 + 0.5, 17.2), 2.0, face_w - 0.2, kind=2)
    add_box(bm_bronze, tuple(F.p(0.0, v3 + 0.6, 19.6)), (0.4, 0.4, 4.8))
    add_box(bm_bronze, tuple(F.p(0.0, v3 + 0.6, 21.0)), (0.4, 4.6, 0.4))
    cpos = F.p(0.0, v3 + 0.95, 18.4)
    add_frustum(bm_psculpt, cpos, 0.26, 0.2, 0.36, 0.24, 1.45, face_w)
    for side in (-1, 1):
        add_cylinder(bm_psculpt, cpos + Vector((0, side * 0.12, 1.35)), cpos + Vector((0, side * 1.25, 1.75)), 0.09, 0.07, segments=5)
    add_frustum(bm_psculpt, cpos + Vector((0, 0, 1.45)), 0.22, 0.22, 0.2, 0.2, 0.3, face_w + 0.3, 0.3)


# ─────────────────────────────────────────────────────────────────────────────
# GLORY FAÇADE (south, Blender -Y; planned design). Facts: 7 doors (one per nave, triple centre door),
#   portico of 7 columns, 16 hyperboloid lanterns over the portico (layout/heights CONJECTURE), clouds
#   with the Creed (CONJECTURE), entrance ~5 m above Carrer de Mallorca with a ~57 m stair bridging the
#   street (WIKI). True layout: inner wall face y -47.75, wall front -53, towers on y -51.75, porch
#   (= cloister south walk) to the block line -60.6 with the portico on y -59.6, level bridge over
#   Mallorca to y -81 at Z_NAVE, then the stair down to ground_z at y -117.6.
GLORY_CANOPY_Z = (26.6, 29.4)       # portico roof underside / top (previous pass)
GLORY_DOOR_W = {0: 6.0, 1: 3.6, 2: 3.6}   # opening width by |index| from the centre (proposed layout addition)
GLORY_DOOR_CEIL = 10.2              # lintel / ceiling over every door tunnel


def glory_portals(v_front: float) -> list[dict]:
    xs = sorted(L.GLORY["doorsX"])
    mid = len(xs) // 2
    return [{"u": x, "half": 0.5 * GLORY_DOOR_W[abs(i - mid)] + JAMB, "w": GLORY_DOOR_W[abs(i - mid)],
             "ceil": GLORY_DOOR_CEIL, "front": v_front} for i, x in enumerate(xs)]


def build_glory_facade(bm_warm, bm_warm_clean, bm_gdeco, bm_stairs_warm, bm_gbridge, bm_bronze, bm_gold) -> None:
    """South Glory façade, porch, bridge over Carrer de Mallorca and the grand stair (true layout)."""
    G = L.GLORY
    F = Frame("glo")
    v0 = abs(G["innerY"])
    v_wf = abs(G["wallFrontY"])
    v_t = abs(L.GLORY_TOWER_Y)
    zc0, zc1 = GLORY_CANOPY_Z
    towers = apostle_bases("glory")
    v_bf = v_t + 0.55 * min(tb["r"] for tb in towers)
    portals = glory_portals(v_bf)
    build_facade_body(F, bm_warm, bm_warm_clean, family="glory", v0=v0, v_wf=v_wf, v_t=v_t, u_half=G["halfWidth"],
                      portals=portals, z_base=ground_z(G["wallFrontY"]) - 0.4, upper_half=G["halfWidth"],
                      slot_front=v_t + 1.9)

    # Door frames: parabolic arches on the wall front, the triple centre door on two corbels at 4.2 m
    vd = v_wf - 0.3
    for p in portals:
        if p["w"] > 4.0:
            sub = p["w"] / 3.0
            for k in (-1, 0, 1):
                xc = p["u"] + k * sub
                add_arch_tube(bm_gdeco, F.p(xc - 0.5 * sub, vd, 4.2), F.p(xc + 0.5 * sub, vd, 4.2), GLORY_DOOR_CEIL - 4.4, 0.26, 0.2, n=12, segments=6, sharp=1.2)
                add_parabolic_spandrel(bm_warm_clean, F, xc, 0.5 * sub, 4.2, GLORY_DOOR_CEIL - 4.4, GLORY_DOOR_CEIL, vd - 0.35, vd - 0.1)
            for k in (-0.5, 0.5):
                c = F.p(p["u"] + k * sub, vd, 0.0)
                add_lathe(bm_gdeco, c.x, c.y, [(3.6, 0.05), (4.0, 0.3), (4.3, 0.34)], segments=6, cap_top=True)
        else:
            hw = 0.5 * p["w"] + 0.25
            add_arch_tube(bm_gdeco, F.p(p["u"] - hw, vd, Z_NAVE), F.p(p["u"] + hw, vd, Z_NAVE), GLORY_DOOR_CEIL - Z_NAVE - 0.3, 0.26, 0.2, n=12, segments=6, sharp=1.2)
            add_parabolic_spandrel(bm_warm_clean, F, p["u"], hw, Z_NAVE, GLORY_DOOR_CEIL - Z_NAVE - 0.3, GLORY_DOOR_CEIL, vd - 0.35, vd - 0.1)
        # Bronze doors folded open against the jambs of each door tunnel
        for s in (-1, 1):
            depth = 3.2 if p["w"] > 4.0 else 1.8
            c = F.p(p["u"] + s * (p["half"] - 0.16), v0 + 0.3 + depth * 0.5, Z_NAVE + 3.6)
            add_box(bm_bronze, tuple(c), (0.32, depth, 7.2))

    # PORTICO: 7 columns (gifts of the Holy Spirit) on 'sin' pedestals with 'virtue' capitals
    cy = G["porticoColumnY"]
    for i, px in enumerate(G["porticoColumnX"]):
        add_lathe(bm_warm, px, cy, [(Z_NAVE - SLAB_DROP, 1.2), (Z_NAVE + 1.1, 1.16), (Z_NAVE + 2.2, 1.08), (Z_NAVE + 2.8, 0.98)], segments=10, cap_top=True, phase=0.3 * i)
        add_double_twist_shaft(bm_warm, px, cy, Z_NAVE + 2.8, zc0 - 1.6, 0.92, 0.78, sides=8, rings=12, segs=24, flute=0.14)
        add_lathe(bm_warm, px, cy, [(zc0 - 1.7, 0.8), (zc0 - 1.0, 1.2), (zc0 - 0.3, 1.4), (zc0 + 0.05, 1.8)], segments=12, cap_top=True)
        add_robed_figure(bm_gdeco, Vector((px, cy - 1.45, zc0 - 3.6)), 2.0, -math.pi * 0.5, wings=True)
        add_ellipsoid(bm_gdeco, Vector((px, cy - 0.6, Z_NAVE + 1.0)), (0.9, 0.45, 0.7), subdivisions=1)
        add_ellipsoid(bm_gdeco, Vector((px, cy - 0.85, Z_NAVE + 1.55)), (0.35, 0.3, 0.32), subdivisions=1)
    # Portico roof (in front of the tower drums, clear of the stair wells) and its parabolic arcade
    u_can = max(abs(x) for x in G["porticoColumnX"]) + 1.5
    v_can0, v_can1 = v_t + STAIR_HOLLOW_R + 0.3, abs(cy) + 1.4
    F.box(bm_warm, -u_can, u_can, v_can0, v_can1, zc0, zc1)
    xs = sorted(G["porticoColumnX"])
    for x0, x1 in zip(xs[:-1], xs[1:]):
        add_arch_tube(bm_warm, Vector((x0, cy - 0.3, zc0 - 8.6)), Vector((x1, cy - 0.3, zc0 - 8.6)), 8.4, 0.6, 0.5, n=12, segments=7, sharp=1.0)

    # 16 hyperboloid lanterns on the portico roof: two staggered rows of 8 (conjecture)
    def crescendo(x: float) -> float:
        return max(0.0, 1.0 - abs(x) / 21.5) ** 1.2
    for i in range(8):
        x = -19.25 + 5.5 * i
        add_hyperboloid_lantern(bm_warm, bm_gold, x, -(v_can1 - 1.0), zc1, 6.0 + 9.0 * crescendo(x), 1.35, segments=12)
    for i in range(8):
        x = -16.5 + i * (33.0 / 7.0)
        add_hyperboloid_lantern(bm_warm, bm_gold, x, -(v_can1 - 3.0), zc1, 9.0 + 14.0 * crescendo(x), 1.55, segments=12)

    # Clouds bearing the Creed in front of the tower bases (decorative)
    v_cloud = v_can0 + 1.2
    for row, (zc, w, depth) in enumerate(((zc1 + 3.0, 40.0, 2.2), (zc1 + 7.5, 32.0, 2.0), (zc1 + 11.5, 24.0, 2.0), (zc1 + 14.2, 16.0, 1.8))):
        add_cloud_mass(bm_gdeco, Vector((0.0, -v_cloud, zc)), w, 3.4, depth, lobes=int(w / 2.6), seed=row)
    glyph_c = [(0.9, 0.9, 0.3, 1.0), (0.3, 1.0, 0.05, 0.5), (0.05, 0.5, 0.3, 0.0), (0.3, 0.0, 0.9, 0.1)]
    glyph_r = [(0.1, 0.0, 0.1, 1.0), (0.1, 1.0, 0.75, 0.85), (0.75, 0.85, 0.75, 0.6), (0.75, 0.6, 0.1, 0.5), (0.35, 0.5, 0.85, 0.0)]
    glyph_e = [(0.1, 0.0, 0.1, 1.0), (0.1, 1.0, 0.85, 1.0), (0.1, 0.5, 0.65, 0.5), (0.1, 0.0, 0.85, 0.0)]
    glyph_d = [(0.1, 0.0, 0.1, 1.0), (0.1, 1.0, 0.6, 0.85), (0.6, 0.85, 0.85, 0.5), (0.85, 0.5, 0.6, 0.15), (0.6, 0.15, 0.1, 0.0)]
    glyph_o = [(0.5, 1.0, 0.1, 0.5), (0.1, 0.5, 0.5, 0.0), (0.5, 0.0, 0.9, 0.5), (0.9, 0.5, 0.5, 1.0)]
    add_letter_strokes(bm_gold, Vector((-6.3, -(v_cloud + 1.1), zc1 + 14.6)), Vector((1, 0, 0)), [glyph_c, glyph_r, glyph_e, glyph_d, glyph_o], 2.1, 0.55, 0.14)

    build_glory_approach(bm_warm, bm_stairs_warm, bm_gbridge, bm_gold)


def glory_stair_treads() -> list[tuple[float, float, float]]:
    """(y_start, y_end, top z) of every tread of the Glory stair, top (bridge end) to bottom.
    Equal risers of ~0.155 m from Z_NAVE to ground_z at the foot; GLORY.stair.landings longer treads
    split the flight into equal flights; tread centres follow the runtime's linear ramp."""
    st = L.GLORY["stair"]
    y_top, y_bot = st["y1"], st["y0"]
    z_top, z_bot = st["topZ"], st["bottomZ"]
    n = round((z_top - z_bot) / 0.155)
    rise = (z_top - z_bot) / n
    n_land = st["landings"]
    land_len = 2.0
    run = y_top - y_bot
    t = (run - n_land * land_len) / (n - n_land)
    land_idx = {round(n * (k + 1) / (n_land + 1)) for k in range(n_land)}
    out, y = [], y_top
    for j in range(n + 1):
        ln = t * 0.5 if j in (0, n) else (land_len if j in land_idx else t)
        out.append((y, y - ln, z_top - j * rise))
        y -= ln
    return out


def build_glory_approach(bm_warm, bm_stairs, bm_rail, bm_gold) -> None:
    G = L.GLORY
    porch, br, st = G["porch"], G["bridge"], G["stair"]
    # Porch podium (y -60.6 .. -53; the cloister south walk floor lies on it at Z_NAVE)
    cs = []
    for top in (False, True):
        for (x, y) in ((porch["x0"], porch["y0"]), (porch["x1"], porch["y0"]), (porch["x1"], porch["y1"]), (porch["x0"], porch["y1"])):
            cs.append((x, y, Z_NAVE - SLAB_DROP if top else ground_z(y) - 0.6))
    add_hexa(bm_stairs, cs)
    # Level bridge over Carrer de Mallorca: deck top Z_NAVE, soffit at bridge.soffitZ, |x| <= halfWidth
    hw = br["halfWidth"]
    add_box(bm_stairs, (0.0, 0.5 * (br["y0"] + br["y1"]), 0.5 * (br["deckZ"] + br["soffitZ"])),
            (2.0 * hw, br["y1"] - br["y0"], br["deckZ"] - br["soffitZ"]))
    # Edge beams with parapets (collidable), soffit never below soffitZ over the street
    for sx in (-1, 1):
        add_box(bm_rail, (sx * (hw + 0.4), 0.5 * (br["y0"] + br["y1"]), 0.5 * (br["soffitZ"] + Z_NAVE + 1.1)),
                (0.8, br["y1"] - br["y0"], Z_NAVE + 1.1 - br["soffitZ"]))
        # piers on the two Mallorca sidewalks only (outside the carriageway), at |x| >= halfWidth
        c, half = L.STREETS["mallorca"][1], L.STREETS["mallorca"][2]
        for yp in (c + half - 0.5 * L.SIDEWALK_WIDTH, c - half + 0.5 * L.SIDEWALK_WIDTH):
            zb = ground_z(yp) - 0.3
            add_box(bm_rail, (sx * (hw + 0.4), yp, 0.5 * (zb + br["soffitZ"] + 0.05)), (0.8, 1.6, br["soffitZ"] + 0.05 - zb))
        # low parapet on the porch front beside the bridge (the podium drops to the sidewalk there)
        x_in, x_out = hw + 0.8, porch["x1"]
        add_box(bm_rail, (sx * 0.5 * (x_in + x_out), porch["y0"] + 0.2, 0.5 * (Z_NAVE - SLAB_DROP + Z_NAVE + 1.1)),
                (x_out - x_in, 0.4, Z_NAVE + 1.1 - (Z_NAVE - SLAB_DROP)))
    # The stair: treads down to ground_z at the foot, landings, cheek walls
    hw_s = st["halfWidth"]
    for (ya, yb, zt) in glory_stair_treads()[:-1]:          # the last half tread is the ground itself
        cs = []
        for top in (False, True):
            for (x, y) in ((-hw_s, ya), (-hw_s, yb), (hw_s, yb), (hw_s, ya)):
                cs.append((x, y, zt if top else ground_z(y) - 0.5))
        add_hexa(bm_stairs, cs)
    y_top, y_bot = st["y1"], st["y0"]

    def ramp(y: float) -> float:
        return st["topZ"] + (st["bottomZ"] - st["topZ"]) * (y_top - y) / (y_top - y_bot)
    for sx in (-1, 1):
        x_in, x_out = sx * hw_s, sx * (hw_s + 0.8)
        cs = []
        for top in (False, True):
            for (x, y) in ((x_in, y_top), (x_in, y_bot - 0.3), (x_out, y_bot - 0.3), (x_out, y_top)):
                cs.append((x, y, ramp(min(y_top, max(y_bot, y))) + 1.1 if top else ground_z(y) - 0.5))
        add_hexa(bm_rail, cs)
    # Monuments to fire and water at the foot of the stair (form is conjecture)
    for mx, my in G["monuments"]:
        g = ground_z(my)
        add_box(bm_warm, (mx, my, g + 1.0), (2.2, 2.2, 2.4))
        add_lathe(bm_warm, mx, my, [(g + 2.2, 0.9), (g + 3.8, 0.6), (g + 6.3, 0.5), (g + 7.0, 0.85)], segments=8, cap_top=True)
        add_cylinder(bm_gold, Vector((mx, my, g + 6.9)), Vector((mx, my, g + 9.4)), 0.6, 0.06, segments=8)


def add_parabolic_roof_vault(
    bm_stone: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
    center: tuple[float, float, float],
    span_w: float,
    length: float,
    height: float,
    axis: str = "Y",
    ribs: int = 5,
) -> None:
    """Create a smooth sculpted Gaudí parabolic/catenary roof prism with transverse stone ribs & gilded crest finials."""
    cx, cy, z0 = center
    # Smooth 9-point catenary/parabolic cross-section profile (u in [-0.5..+0.5]) -> ZERO stair-step boxes!
    prof_pts: list[tuple[float, float]] = []
    n_prof = 8
    for i in range(n_prof + 1):
        u = -1.0 + 2.0 * (i / n_prof)  # -1 .. +1
        # Crisp pointed catenary arch roof silhouette
        z_off = height * (1.0 - abs(u) ** 1.35)
        prof_pts.append((u * span_w * 0.5, z_off))

    half_l = length * 0.5
    ring_a: list[bmesh.types.BMVert] = []
    ring_b: list[bmesh.types.BMVert] = []
    for w_off, z_off in prof_pts:
        if axis == "Y":
            ring_a.append(bm_stone.verts.new((cx + w_off, cy - half_l, z0 + z_off)))
            ring_b.append(bm_stone.verts.new((cx + w_off, cy + half_l, z0 + z_off)))
        else:
            ring_a.append(bm_stone.verts.new((cx - half_l, cy + w_off, z0 + z_off)))
            ring_b.append(bm_stone.verts.new((cx + half_l, cy + w_off, z0 + z_off)))

    # Smooth vaulted roof slope faces
    for i in range(n_prof):
        bm_stone.faces.new((ring_a[i], ring_a[i + 1], ring_b[i + 1], ring_b[i]))
    # Bottom closure & end gable caps
    bm_stone.faces.new((ring_a[0], ring_b[0], ring_b[-1], ring_a[-1]))
    bm_stone.faces.new(list(reversed(ring_a)))
    bm_stone.faces.new(ring_b)

    # Transverse stone hyperboloid bay ribs + gilded ridge crest lanterns every bay!
    for r_idx in range(ribs):
        t_l = (r_idx + 0.5) / ribs
        l_pos = -half_l + t_l * length
        # Ridge lantern crest atop the roof spine
        if axis == "Y":
            p_top = Vector((cx, cy + l_pos, z0 + height))
            add_cylinder(bm_gold, p_top - Vector((0, 0, 0.2)), p_top + Vector((0, 0, 2.2)), 0.42, 0.10, segments=6)
            for s_w in (-1.0, 1.0):
                p_eave = Vector((cx + s_w * span_w * 0.48, cy + l_pos, z0 + 0.2))
                add_cylinder(bm_stone, p_eave, p_top, 0.34, 0.26, segments=6, cap=False)
        else:
            p_top = Vector((cx + l_pos, cy, z0 + height))
            add_cylinder(bm_gold, p_top - Vector((0, 0, 0.2)), p_top + Vector((0, 0, 2.2)), 0.42, 0.10, segments=6)
            for s_w in (-1.0, 1.0):
                p_eave = Vector((cx + l_pos, cy + s_w * span_w * 0.48, z0 + 0.2))
                add_cylinder(bm_stone, p_eave, p_top, 0.34, 0.26, segments=6, cap=False)



def build_roofs_and_pinnacles(
    bm_warm: bmesh.types.BMesh,
    bm_mosaic: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
) -> None:
    """Parabolic roofs over the nave / transept / aisles, the fruit-basket gables of the nave sides and
    the neo-Gothic apse exterior (buttresses, flyers, pinnacles, chapel gables) on the true layout."""
    y_s, y_n = L.GLORY_INNER_Y, -L.CENTRAL_NAVE_HALF           # nave roofs: Glory inner face -> crossing
    y_c, length = 0.5 * (y_s + y_n), y_n - y_s
    span_c = 2.0 * (L.CENTRAL_NAVE_HALF + 0.7)                  # 16.4 (previous pass)
    # 1. Central nave roof
    add_parabolic_roof_vault(bm_warm, bm_gold, (0.0, y_c, Z_NAVE_VAULT + 0.2), span_c, length, 8.8, axis="Y", ribs=5)
    # 2. Transept roofs: crossing edge -> transept end walls (x +-30), clear of the tower shells
    x0, x1 = L.CENTRAL_NAVE_HALF + 0.1, L.TRANSEPT_HALF_LENGTH
    for sx in (-1, 1):
        add_parabolic_roof_vault(bm_warm, bm_gold, (sx * 0.5 * (x0 + x1), 0.0, Z_NAVE_VAULT + 0.2), span_c, x1 - x0, 8.8, axis="X", ribs=3)
    # 3. Nave sides: aisle roofs, one gabled pediment per 7.5 m bay at both levels with a trencadís
    #    fruit basket [photos / guides — medium]. Bays = layout NAVE_WINDOW_BAY_Y, plus one more aisle
    #    gable over the Glory end of the nave wall; clerestory gables only over the central-nave roof.
    aisle_x = 0.5 * (L.CENTRAL_NAVE_HALF + L.NAVE_HALF_WIDTH + L.NAVE_WALL_THICKNESS) - 0.05   # 15.45: x 7.5 .. 23.4
    aisle_span = L.NAVE_HALF_WIDTH + L.NAVE_WALL_THICKNESS - L.CENTRAL_NAVE_HALF - 0.2
    gable_x = L.NAVE_HALF_WIDTH + 0.5 * L.NAVE_WALL_THICKNESS   # 23.0: on the nave wall
    bays = list(L.NAVE_WINDOW_BAY_Y) + [L.NAVE_WINDOW_BAY_Y[-1] - GRID]
    for sx in (-1, 1):
        add_parabolic_roof_vault(bm_warm, bm_gold, (sx * aisle_x, y_c, Z_AISLE_VAULT + 0.2), aisle_span, length, 3.8, axis="Y", ribs=5)
        for bi, py in enumerate(bays):
            px = sx * gable_x
            add_pointed_gable(bm_warm, (px, py), Z_AISLE_VAULT + 0.4, 6.4, 9.6, 1.5, facing="X+" if sx > 0 else "X-")
            add_fruit_basket(bm_warm, bm_mosaic, bm_gold, px, py, Z_AISLE_VAULT + 9.3, 0.95)
            if bi < len(L.NAVE_WINDOW_BAY_Y):
                pxc = sx * (L.CENTRAL_NAVE_HALF + 1.1)
                add_pointed_gable(bm_warm, (pxc, py), Z_NAVE_VAULT - 4.6, 5.8, 10.0, 1.3, facing="X+" if sx > 0 else "X-")
                add_fruit_basket(bm_warm, bm_mosaic, bm_gold, pxc, py, Z_NAVE_VAULT + 5.1, 1.0)

    # 4. NEO-GOTHIC APSE EXTERIOR (1891-93), concentric with the crypt and the Mary tower:
    #    radial buttresses on the layout pier angles with flyers and pinnacles on the APSE_BUTTRESS_R
    #    ring, 7 chapel gables with rosettes and gilt 'M' monograms, 14 gargoyles.
    acx, acy = L.APSE_CENTER
    r_w = L.APSE_WALL_OUTER_R
    r_b = L.APSE_BUTTRESS_R
    cz = Z_AMBULATORY_VAULT + 1.2               # chapel cornice / gable foot (ambulatory vault 31.2)
    piers = [math.radians(a) for a in L.APSE_PIER_ANGLES_DEG]

    def rp(r: float, a: float, z: float) -> Vector:
        return Vector((acx + r * math.cos(a), acy + r * math.sin(a), z))

    for ang in piers:
        b = rp(0.5 * (r_w - 0.6 + r_b), ang, 0.0)
        z0 = ground_z(b.y) - 0.3
        z1 = cz + 4.1
        add_box(bm_warm, (b.x, b.y, 0.5 * (z0 + z1)), (1.7, r_b - (r_w - 0.6), z1 - z0), rot_euler=(0.0, 0.0, ang - math.pi * 0.5))
        # two tiers of flyers leaping inward to the chapel wall head and the upper apse
        add_cylinder(bm_warm, rp(r_b - 0.4, ang, cz - 7.2), rp(r_w * 0.94, ang, cz - 0.4), 0.58, 0.48, segments=6)
        add_cylinder(bm_warm, rp(r_b - 0.4, ang, cz + 1.3), rp(r_w * 0.85, ang, cz + 8.3), 0.54, 0.44, segments=6)
        # pinnacle on the buttress ring
        add_cylinder(bm_warm, rp(r_b - 0.4, ang, cz + 2.1), rp(r_b - 0.4, ang, cz + 21.6), 1.25, 0.26, segments=8)
        add_cylinder(bm_mosaic, rp(r_b - 0.4, ang, cz + 21.6), rp(r_b - 0.4, ang, cz + 25.6), 0.48, 0.08, segments=8)

    for i in range(len(piers) - 1):
        a0, a1 = piers[i], piers[i + 1]
        am = 0.5 * (a0 + a1)
        g = rp(r_w + 0.6, am, 0.0)
        rot_g = am - math.pi * 0.5
        add_pointed_gable(bm_warm, (g.x, g.y), cz, 6.4, 13.5, 1.4, rot_z=rot_g, crockets=True)
        m = rp(r_w + 1.4, am, cz + 4.7)
        ux, uy = math.cos(rot_g), math.sin(rot_g)
        for s in range(10):
            ra0 = 2.0 * math.pi * s / 10.0
            ra1 = 2.0 * math.pi * (s + 1) / 10.0
            p_r0 = Vector((m.x + 1.05 * math.cos(ra0) * ux, m.y + 1.05 * math.cos(ra0) * uy, m.z + 1.05 * math.sin(ra0)))
            p_r1 = Vector((m.x + 1.05 * math.cos(ra1) * ux, m.y + 1.05 * math.cos(ra1) * uy, m.z + 1.05 * math.sin(ra1)))
            add_cylinder(bm_gold, p_r0, p_r1, 0.10, 0.10, segments=5)
        p_bl = Vector((m.x - 0.55 * ux, m.y - 0.55 * uy, m.z - 0.55))
        p_tl = Vector((m.x - 0.55 * ux, m.y - 0.55 * uy, m.z + 0.55))
        p_mid = Vector((m.x, m.y, m.z - 0.10))
        p_tr = Vector((m.x + 0.55 * ux, m.y + 0.55 * uy, m.z + 0.55))
        p_br = Vector((m.x + 0.55 * ux, m.y + 0.55 * uy, m.z - 0.55))
        for q0, q1 in ((p_bl, p_tl), (p_tl, p_mid), (p_mid, p_tr), (p_tr, p_br)):
            add_cylinder(bm_gold, q0, q1, 0.09, 0.09, segments=5)
        for ga in (a0 + 0.06, a1 - 0.06):
            p_g0 = rp(r_w - 0.2, ga, cz + 3.7)
            p_g1 = rp(r_w + 2.15, ga, cz + 3.35)
            add_cylinder(bm_warm, p_g0, p_g1, 0.34, 0.16, segments=6)
            add_cylinder(bm_warm, p_g1, p_g1 + Vector((0.35 * math.cos(ga), 0.35 * math.sin(ga), 0.22)), 0.20, 0.10, segments=5)


def build_facades() -> None:
    reset_scene()
    mats = get_materials()

    bm_nat = bmesh.new()
    bm_nat_mass = bmesh.new()
    bm_nat_clean = bmesh.new()
    bm_pas = bmesh.new()
    bm_pas_clean = bmesh.new()
    bm_pcol = bmesh.new()
    bm_pbones = bmesh.new()
    bm_psculpt = bmesh.new()
    bm_warm = bmesh.new()
    bm_warm_clean = bmesh.new()
    bm_gdeco = bmesh.new()
    bm_gbridge = bmesh.new()
    bm_stairs_nat = bmesh.new()
    bm_stairs_pas = bmesh.new()
    bm_stairs_warm = bmesh.new()
    bm_bronze = bmesh.new()
    bm_cypress = bmesh.new()
    bm_mosaic = bmesh.new()
    bm_gold = bmesh.new()
    bm_white = bmesh.new()
    bm_deco = bmesh.new()

    build_nativity_facade(bm_nat, bm_nat_mass, bm_nat_clean, bm_stairs_nat, bm_bronze, bm_cypress, bm_gold, bm_white)
    add_nativity_encrustation(bm_deco)
    build_passion_facade(bm_pas, bm_pas_clean, bm_pcol, bm_pbones, bm_psculpt, bm_stairs_pas, bm_bronze, bm_gold)
    build_glory_facade(bm_warm, bm_warm_clean, bm_gdeco, bm_stairs_warm, bm_gbridge, bm_bronze, bm_gold)
    build_roofs_and_pinnacles(bm_warm, bm_mosaic, bm_gold)

    # Gaudí's dripping Nativity relief (sculpture fully, structural mass more coarsely and only above the
    # cloister soffit) + crisp stone edge bevels on Passion & Glory. The *_clean meshes bound the walk
    # contracts (doorways, stair wells, passages, stair cheeks) and are merged in un-displaced.
    apply_dripping_relief(bm_nat, amp=0.30, min_z=2.2, max_edge=1.15)
    apply_dripping_relief(bm_nat_mass, amp=0.22, min_z=PASSAGE_SOFFIT_Z + 0.6, max_edge=2.4, max_passes=3, seed=43)
    apply_dripping_relief(bm_deco, amp=0.05, min_z=0.0, max_edge=99.0, seed=57)
    bevel_sharp_edges(bm_pas, width=0.055, angle_deg=60.0)
    bevel_sharp_edges(bm_warm, width=0.055, angle_deg=60.0)
    merge_bmesh_into(bm_nat, bm_nat_mass)
    merge_bmesh_into(bm_nat, bm_nat_clean)
    merge_bmesh_into(bm_pas, bm_pas_clean)
    merge_bmesh_into(bm_warm, bm_warm_clean)

    finalize_bmesh_object(bm_nat, "Facade_Nativity", mats["nativity_stone"], smooth=True, uv_scale=0.16, weathering=0.5, ao_vert_limit=150000)
    # Decorative layers: '_Leaves' keeps them out of the collision BVH (CollisionSystem NON_COLLIDABLE_SUBSTRINGS)
    # while the 'Facade_Nativity' / 'Facade_Passion' / 'Facade_GloryAndRoofs' prefixes keep them in the right
    # construction-timeline phase; they still cast sun shadows.
    finalize_bmesh_object(bm_deco, "Facade_Nativity_Sculpture_Leaves", mats["nativity_stone"], smooth=True, uv_scale=0.3, weathering=0.5, ao_dist=2.5, ao_vert_limit=150000)
    finalize_bmesh_object(bm_pas, "Facade_Passion", mats["passion_stone"], smooth=False, uv_scale=0.15)
    # Large uv scale: the shared ashlar texture's coursing would otherwise band the columns into "drums"
    finalize_bmesh_object(bm_pcol, "Facade_Passion_Columns", mats["passion_stone"], smooth=True, uv_scale=0.05)
    finalize_bmesh_object(bm_pbones, "Facade_Passion_BonesAndRoots_Leaves", mats["passion_stone"], smooth=True, uv_scale=0.2, ao_dist=2.5)
    finalize_bmesh_object(bm_psculpt, "Facade_Passion_Sculpture_Leaves", mats["passion_stone"], smooth=False, uv_scale=0.3, ao_dist=2.0)
    finalize_bmesh_object(bm_warm, "Facade_GloryAndRoofs", mats["sandstone_warm"], smooth=False, uv_scale=0.14, ao_vert_limit=80000)
    finalize_bmesh_object(bm_gdeco, "Facade_GloryAndRoofs_Sculpture_Leaves", mats["sandstone_warm"], smooth=True, uv_scale=0.25, ao_dist=2.5)
    # New (true layout): parapets / edge beams / piers of the Glory bridge, the Glory stair cheek walls and
    # the porch-front parapets. Collidable on purpose (the name matches no NON_COLLIDABLE substring) so a
    # visitor cannot walk off the bridge onto Carrer de Mallorca.
    finalize_bmesh_object(bm_gbridge, "Facade_GloryBridge", mats["sandstone_warm"], smooth=False, uv_scale=0.14)
    finalize_bmesh_object(bm_stairs_nat, "Facade_EntranceStairs_Nativity", mats["nativity_stone"], smooth=False, uv_scale=0.16, bake_ao=False)
    finalize_bmesh_object(bm_stairs_pas, "Facade_EntranceStairs_Passion", mats["passion_stone"], smooth=False, uv_scale=0.15, bake_ao=False)
    finalize_bmesh_object(bm_stairs_warm, "Facade_EntranceStairs_Glory", mats["sandstone_warm"], smooth=False, uv_scale=0.14, bake_ao=False)
    finalize_bmesh_object(bm_bronze, "Facade_BronzeDoors", mats["bronze_door"], smooth=False, uv_scale=0.25)
    finalize_bmesh_object(bm_cypress, "Facade_CypressTree", mats["cypress_green"], smooth=True, uv_scale=0.30)
    finalize_bmesh_object(bm_mosaic, "Facade_FruitPinnacles", mats["trencadis"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_gold, "Facade_GoldAccents", mats["gold_accent"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_white, "Facade_Doves", mats["white_marble"], smooth=True, uv_scale=0.40)

    export_glb(os.path.join(MODEL_DIR, "facades.glb"))


if __name__ == "__main__":
    build_facades()
