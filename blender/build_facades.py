"""Build the 3 monumental facades (Nativity, Passion, Glory), exterior roofs & fruit-basket pinnacles."""

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
    add_letter_strokes,
    add_palm_capital,
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
# NATIVITY FAÇADE (east, Blender +X; runtime +X). Target values (architecture pass):
#   * 3 portals between 4 bell towers: Hope (left as seen from Plaça de Gaudí = south, -Y), Charity
#     (centre, largest and highest, crowned by the cypress Tree of Life), Faith (right = north, +Y).
#     [Sagrada Família booklets / Wikipedia — high confidence]
#   * 2 columns separate the 3 porticoes; at the foot of each a turtle (sea side, south) or a tortoise
#     (mountain side, north); palm-leaf capitals; trumpeting angels above. [Wikipedia — high]
#   * Charity portal: trumeau column with the genealogy of Jesus and the serpent, Nativity group above
#     the doors, Star of Bethlehem, Coronation of Mary higher up, pelican + JHS anagram under the
#     cypress, red tau cross + dove at its top. [booklets / guides — high for presence, positions medium]
#   * Hope gable crowned by the rock needles of Montserrat; Faith gable by a lantern (Trinity).
#     [guides — medium]
#   * Heights: towers 98.4 m (outer) / 107 m (inner) [official — high]. Cypress tip ~50-55 m and side
#     gable tips ~35 m are photo-proportion estimates (no published figure found) — LOW confidence.
#   * Walkable openings (runtime contract, unchanged): centre |y| < 2.8, sides 6.4 < |y| < 12.4,
#     doors at x = 30.9, entrance ramp x 32.5..36.7 (CollisionSystem analytic floor).
# Portal table: (name, centre y, door half-width hw0, archivolt rise, gable base z, gable height, gable width)
NATIVITY_PORTALS = (
    ("Hope", -9.4, 3.25, 9.8, 11.2, 24.0, 8.4),
    ("Charity", 0.0, 3.1, 11.8, 13.0, 30.0, 9.6),
    ("Faith", 9.4, 3.25, 9.8, 11.2, 24.0, 8.4),
)
NATIVITY_FX = 31.5
NATIVITY_COLUMN_Y = 4.55     # the two turtle/tortoise palm columns between the portals
NATIVITY_COLUMN_X = 34.6
NATIVITY_COLUMN_TOP = 13.6   # palm capital springing (estimate: level of the side-portal archivolt crowns)


def add_nativity_encrustation(bm: bmesh.types.BMesh, fx: float) -> None:
    """Dense sculptural layer of the Nativity facade (decorative, non-collidable):
    figure groups on the three portal gables, foliage fringes along the gable slopes, hanging icicle
    curtains, the tympanum groups, the palm capitals with their trumpeting angels, the Coronation of
    Mary, the pelican and the JHS anagram under the cypress, and the crowns of Hope and Faith."""
    for pi_, (name, py, hw0, rise, gz, g_h, gw) in enumerate(NATIVITY_PORTALS):
        front = fx + 3.25 + 0.9
        central = name == "Charity"
        # Icicle curtains under the gable base (the 'snow' of the Nativity winter) and in the porch mouth
        add_icicle_fringe(bm, front - 0.15, py - gw * 0.48, py + gw * 0.48, gz, 18 if central else 14, 1.7, seed=pi_)
        add_icicle_fringe(bm, fx + 3.6, py - hw0 * 0.8, py + hw0 * 0.8, Z_NAVE + rise - 0.6, 10, 1.3, seed=pi_ + 7)
        # Three tiers of sculpted figure groups on the gable face
        for tier, (dz, fh) in enumerate(((0.45, 1.9), (2.75, 1.7), (5.2, 1.5))):
            z_row = gz + dz
            t = (z_row - gz) / g_h
            hw = gw * 0.5 * ((1.0 - t) ** 1.08) - 0.6
            n = max(2, int(2 * hw / 0.95))
            for i in range(n):
                y = py - hw + (2 * hw) * (i + 0.5) / n
                if central and tier == 0 and abs(y - py) < 1.6:
                    continue  # the Nativity group stands here (below)
                add_robed_figure(bm, Vector((front + 0.28, y, z_row)), fh * (0.9 + 0.1 * math.sin(i * 2.3 + tier)), 0.0, wings=(tier == 2), arm_up=(0.8 if (i + tier) % 3 == 0 else 0.0))
        # Angel musicians flanking the upper gable
        for side in (-1, 1):
            t = 0.42
            z_a = gz + g_h * t
            y = py + side * (gw * 0.5 * ((1.0 - t) ** 1.08) - 0.2)
            add_robed_figure(bm, Vector((front + 0.2, y, z_a)), 2.6 if central else 2.1, 0.0, wings=True, arm_up=1.0)
        # Foliage fringe climbing both gable slopes up to the apex
        for side in (-1, 1):
            steps = int(g_h / 1.15)
            for k in range(steps):
                t = (k + 0.5) / steps
                y = py + side * (gw * 0.5 * ((1.0 - t) ** 1.08) + 0.15)
                add_leaf_cluster(bm, Vector((front - 0.2, y, gz + t * g_h)), 0.85 - 0.45 * t, 0.0, count=4, seed=k + pi_ * 13)
        # Tympanum group on a corbel above the doors (Charity: Holy Family with ox and mule;
        # Hope: flight into Egypt; Faith: Visitation) — generic robed figures at the right scale
        zt = Z_NAVE + rise - 3.4
        add_box(bm, (fx + 2.7, py, zt - 0.15), (0.8, hw0 * 0.95, 0.3))
        for i, dy in enumerate((-0.9, 0.0, 0.9)):
            add_robed_figure(bm, Vector((fx + 2.7, py + dy, zt)), 2.0 if i != 1 else 1.6, 0.0, arm_up=0.5 if i == 0 else 0.0)
        if central:
            for side in (-1, 1):  # ox and mule beside the crib
                add_ellipsoid(bm, Vector((fx + 2.5, py + side * 1.75, zt + 0.55)), (0.75, 0.35, 0.4), subdivisions=1)
                add_ellipsoid(bm, Vector((fx + 3.05, py + side * 1.55, zt + 0.85)), (0.28, 0.2, 0.22), subdivisions=1)
            # Trumeau: column of the genealogy of Jesus with the serpent coiled at its foot.
            # Decorative (non-collidable) so the central walk-through stays clear.
            add_lathe(bm, fx + 1.2, py, [(Z_NAVE, 0.42), (Z_NAVE + 0.5, 0.3), (Z_NAVE + 6.2, 0.26), (zt - 0.4, 0.34), (zt - 0.15, 0.55)], segments=8)
            coil = [Vector((fx + 1.2 + 0.42 * math.cos(a * 0.6), py + 0.42 * math.sin(a * 0.6), Z_NAVE + 0.3 + a * 0.06)) for a in range(18)]
            add_swept_tube(bm, coil, [0.09] * len(coil), segments=5)
            # Coronation of Mary: Jesus crowning Mary with Joseph at their side (upper Charity gable)
            zc = gz + 18.6
            add_box(bm, (front + 0.1, py, zc - 0.2), (0.8, 3.6, 0.4))
            add_robed_figure(bm, Vector((front + 0.35, py - 0.75, zc)), 2.3, 0.0)
            add_robed_figure(bm, Vector((front + 0.35, py + 0.75, zc)), 2.5, 0.0, arm_up=1.0)
            add_robed_figure(bm, Vector((front + 0.25, py + 1.85, zc)), 2.0, 0.0)
            # Pelican on its nest and the JHS anagram at the foot of the cypress
            add_pelican(bm, Vector((front - 0.2, py, gz + g_h - 6.2)), 2.2, 0.0)
        elif py < 0:
            # Hope: the needles of Montserrat crown the gable
            add_rock_peak(bm, Vector((front - 0.9, py, gz + g_h - 1.4)), 4.2, 3.0, seed=2)
        else:
            # Faith: three-sided lantern of the Trinity crowns the gable
            add_triangular_lantern(bm, Vector((front - 0.9, py, gz + g_h - 1.2)), 4.6, 1.7)

    # The two palm columns: palm-frond capitals and trumpeting angels above them
    for sy in (-1, 1):
        top = Vector((NATIVITY_COLUMN_X, sy * NATIVITY_COLUMN_Y, NATIVITY_COLUMN_TOP))
        add_lathe(bm, top.x, top.y, [(top.z - 0.3, 0.45), (top.z + 0.4, 0.8), (top.z + 0.7, 0.75)], segments=8, cap_top=True)
        add_palm_capital(bm, top + Vector((0, 0, 0.6)), 2.1, fronds=9, seed=sy)
        add_trumpet_angel(bm, top + Vector((0.1, 0, 0.75)), 2.9, 0.0)


def build_nativity_facade(
    bm_nat: bmesh.types.BMesh,
    bm_stairs_nat: bmesh.types.BMesh,
    bm_bronze: bmesh.types.BMesh,
    bm_cypress: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
    bm_white: bmesh.types.BMesh,
) -> None:
    """East Nativity Facade (X = +31.5): organic sandstone, 3 deep parabolic porches, Cypress Tree of Life."""
    fx = NATIVITY_FX

    # Entrance steps leading from Plaça de Gaudí (Z=0) up to the Nave landing (Z=1.2) — dedicated stair mesh
    for step in range(6):
        sz = (step + 1) * (Z_NAVE / 6.0)
        add_box(bm_stairs_nat, (fx + 5.2 - step * 0.56, 0.0, sz * 0.5), (0.60, 28.0, sz))
    add_box(bm_stairs_nat, (fx + 0.9, 0.0, Z_NAVE * 0.5), (2.4, 28.0, Z_NAVE))

    # Wall piers between/beside the portals (Z=0..14.4) carrying the towers (which start at 18.6 m)
    pier_ys = (-14.2, -4.6, 4.6, 14.2)
    for py in pier_ys:
        add_box(bm_nat, (fx, py, 7.2), (4.2, 3.6, 14.4))
    # Outer edges: one continuous 'melting' buttress per side (was 5 stacked drums). Swept, tapering,
    # with vertical runnels; the dripping relief pass turns it into Gaudí's eroded stone.
    for sy in (-1, 1):
        pts = [Vector((fx + 2.3 + 0.02 * k, sy * (14.2 + 0.03 * k), Z_NAVE + k * 2.6)) for k in range(13)]
        radii = [1.75, 1.6, 1.52, 1.45, 1.42, 1.36, 1.25, 1.15, 1.02, 0.9, 0.76, 0.6, 0.35]
        add_swept_tube(bm_nat, pts, radii, segments=12, cap=True, ridge=(7, 0.22))

    # Lintel band and the upper wall strictly between the 4 tower spiral shafts (Y=±3.6, ±10.8);
    # the tower-base gallery band Z = 14.5..18.6 stays open.
    add_box(bm_nat, (fx, 0.0, 12.2), (3.4, 29.0, 3.6))
    for y_seg, span_y in ((-14.0, 2.0), (-7.2, 2.4), (0.0, 2.4), (7.2, 2.4), (14.0, 2.0)):
        add_box(bm_nat, (fx, y_seg, 24.4), (3.4, span_y, 11.4))

    for name, py, hw0, rise, gz, g_h, gw in NATIVITY_PORTALS:
        central = name == "Charity"
        # Deep, cave-like porch: 4 concentric parabolic archivolts springing from the floor, each one
        # wider, taller and further forward than the last (porch depth ~4.5 m from door to front).
        layers = 4
        step_w = 0.18 if central else 0.2
        for k in range(layers):
            lx = fx + 1.9 + k * 0.55
            hw = hw0 + k * step_w
            add_arch_tube(
                bm_nat,
                Vector((lx, py - hw, Z_NAVE)), Vector((lx, py + hw, Z_NAVE)),
                rise + k * 0.5, 0.5, 0.4, n=14, segments=7, sharp=1.1,
            )
        # Splayed porch soffit: ruled surface joining the innermost and outermost archivolt (reads as
        # one deep stone mouth instead of separate hoops)
        k_out = layers - 1
        inner = parabolic_arch_points(Vector((fx + 1.9, py - hw0, Z_NAVE)), Vector((fx + 1.9, py + hw0, Z_NAVE)), rise, 14, 1.1)
        outer = parabolic_arch_points(Vector((fx + 1.9 + k_out * 0.55, py - hw0 - k_out * step_w, Z_NAVE)),
                                      Vector((fx + 1.9 + k_out * 0.55, py + hw0 + k_out * step_w, Z_NAVE)), rise + k_out * 0.5, 14, 1.1)
        add_ruled_loft(bm_nat, [p + Vector((0, 0, 0.35)) for p in inner], [p + Vector((0, 0, 0.35)) for p in outer])
        # Soaring organic gable over each porch (between the towers)
        add_pointed_gable(bm_nat, (fx + 3.25, py), gz, gw, g_h, 1.8, facing="X+")
        # Botanical pinnacles flanking the gable
        for sy in (-1, 1):
            add_cylinder(bm_nat, Vector((fx + 3.9, py + sy * (gw * 0.36), gz - 1.4)), Vector((fx + 3.8, py + sy * (gw * 0.33), gz + 7.9)), 0.58, 0.12, segments=8)
        # Bronze doors folded open against the jambs (walk-through stays clear)
        for sy in (-1, 1):
            add_box(bm_bronze, (fx - 0.6, py + sy * (2.68 if central else 2.85), Z_NAVE + 3.0), (2.2, 0.25, 6.0))

    # Turtle (south / sea side) and tortoise (north / mountain side) carrying the two palm columns
    for sy in (-1, 1):
        shell_top = add_turtle_column_base(bm_nat, NATIVITY_COLUMN_X, sy * NATIVITY_COLUMN_Y, Z_NAVE, is_sea_turtle=(sy < 0))
        add_palm_trunk(bm_nat, NATIVITY_COLUMN_X, sy * NATIVITY_COLUMN_Y, shell_top, NATIVITY_COLUMN_TOP, 0.48, 0.4, segments=10)

    # Star of Bethlehem over the Nativity group of the Charity portal (gilt comet star)
    star_x = fx + 4.30
    star_z = 21.8
    for k in range(8):
        ang = 2.0 * math.pi * k / 8.0
        ray_len = 1.6 if k % 2 == 0 else 1.0
        add_cylinder(bm_gold, Vector((star_x, 0.0, star_z)), Vector((star_x + 0.12, ray_len * math.cos(ang), star_z + ray_len * math.sin(ang))), 0.2, 0.04, segments=5)
    # Comet tail sweeping down toward the Holy Family
    add_cylinder(bm_gold, Vector((star_x, 0.0, star_z)), Vector((star_x - 0.1, 0.9, star_z - 4.0)), 0.22, 0.03, segments=5)
    # JHS anagram (gilt) just below the cypress, under the pelican
    add_letter_strokes(bm_gold, Vector((fx + 4.3, -1.3, 34.9)), Vector((0, 1, 0)), [GLYPH_J, GLYPH_H, GLYPH_S], 0.7, 0.2, 0.08)

    # Cypress Tree of Life rising above the Charity gable (Z ≈ 38..49 m, tau cross to 51.4 m)
    tree_x = fx + 3.25
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
        # White ceramic doves perched around the cypress crown
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
    # Red/gold tau cross at the summit of the cypress, with the dove of the Holy Spirit above
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
# PASSION FAÇADE (west, Blender -X). Target values:
#   * 6 large inclined columns shaped like bones / sequoia trunks carrying a deep porch roof
#     [Wikipedia, official — high]; column height ~ porch roof underside ≈ 22-23 m (model estimate,
#     no published figure found — LOW); lean ~8° toward the façade (model estimate — LOW).
#   * Pyramidal pediment above the porch made of 18 bone-shaped columns [Wikipedia — high].
#   * Subirachs' sculpture groups on 3 levels read along an S-shaped path, bottom-left -> top-right,
#     Crucifixion at the top centre [official booklet — high for layout, medium for exact heights].
#   * Bronze Gospel doors in the centre, magic square (sum 33) beside the Kiss of Judas [high].
#   * Walkable openings (unchanged): centre |y| < 3.1, sides 7.3 < |y| < 12.1; ramp x -40.5..-31.8.
PASSION_FX = -31.5
PASSION_COLUMN_YS = (-13.5, -8.1, -2.7, 2.7, 8.1, 13.5)
PASSION_ROOF_Z = (22.7, 26.3)   # porch roof slab underside / top


def build_passion_facade(
    bm_pas: bmesh.types.BMesh,
    bm_pcol: bmesh.types.BMesh,
    bm_pbones: bmesh.types.BMesh,
    bm_psculpt: bmesh.types.BMesh,
    bm_stairs_pas: bmesh.types.BMesh,
    bm_bronze: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
) -> None:
    """West Passion Facade (X = -31.5): 6 inclined bone columns, deep porch, 18-bone pediment, Subirachs S-path."""
    fx = PASSION_FX
    z_roof0, z_roof1 = PASSION_ROOF_Z

    # Entrance steps from Plaça de la Sagrada Família (Z=0) up to the portico terrace (Z=1.2)
    for step in range(6):
        sz = (step + 1) * (Z_NAVE / 6.0)
        add_box(bm_stairs_pas, (fx - 8.4 + step * 0.58, 0.0, sz * 0.5), (0.62, 30.0, sz))
    add_box(bm_stairs_pas, (fx - 2.6, 0.0, Z_NAVE * 0.5), (5.2, 30.0, Z_NAVE))

    # Inner recessed wall split around the open tower-base gallery band (Z = 14.5..18.6 m)
    for py in (-14.2, -5.2, 5.2, 14.2):
        add_box(bm_pas, (fx, py, 7.2), (3.4, 4.2, 14.4))
    add_box(bm_pas, (fx, 0.0, 12.2), (3.2, 29.0, 3.6))
    for y_seg, span_y in ((-14.0, 2.0), (-7.2, 2.4), (0.0, 2.4), (7.2, 2.4), (14.0, 2.0)):
        add_box(bm_pas, (fx, y_seg, 24.4), (3.2, span_y, 11.4))
    # Bronze Gospel doors folded open at the entrance jambs
    for sy in (-1, 1):
        add_box(bm_bronze, (fx + 0.5, sy * 2.8, Z_NAVE + 3.2), (2.4, 0.26, 6.4))

    # THE 6 INCLINED BONE / SEQUOIA COLUMNS: splayed swollen feet on the porch floor, long pinched
    # shafts leaning back toward the façade, flared heads merging into the porch roof. Smooth-shaded
    # mesh of their own (the old flat-shaded fluted tubes read as stacked drums).
    for i, cy in enumerate(PASSION_COLUMN_YS):
        p0 = Vector((fx - 7.6, cy, Z_NAVE))
        p_mid = Vector((fx - 6.0, cy * 0.98, 12.0))
        p1 = Vector((fx - 3.9, cy * 0.95, z_roof0 + 0.4))
        add_bone_column_v2(bm_pcol, p0, p_mid, p1, 0.92, segments=14, n=20)
        add_root_flare(bm_pbones, p0, 1.1, roots=6, seed=i)

    # Deep porch roof slab with a bone-rib underside (one rib per column, running back to the wall)
    add_box(bm_pas, (fx - 3.8, 0.0, (z_roof0 + z_roof1) * 0.5), (6.5, 31.5, z_roof1 - z_roof0))
    for cy in PASSION_COLUMN_YS:
        add_cylinder(bm_pas, Vector((fx - 7.0, cy * 0.95, z_roof0 + 0.1)), Vector((fx - 1.4, cy * 0.95, z_roof0 + 0.1)), 0.55, 0.45, segments=6)

    # Pyramidal pediment: backing gable wall + 18 bone columns rising like organ pipes to the
    # triangular cornice (count and arrangement per the built façade).
    add_pointed_gable(bm_pas, (fx - 2.6, 0.0), z_roof1 - 0.1, 29.0, 14.5, 1.6, facing="X-", crockets=False)
    for k in range(18):
        py = -14.5 + k * (29.0 / 17.0)
        h_tri = 14.4 * (1.0 - abs(py) / 15.6) - 0.4
        q0 = Vector((fx - 4.9, py, z_roof1))
        q1 = Vector((fx - 4.3, py * 0.98, z_roof1 + max(1.0, h_tri)))
        add_bone_column_v2(bm_pbones, q0, (q0 + q1) * 0.5 + Vector((-0.15, 0.0, 0.0)), q1, 0.27, segments=7, n=10)
    # Razor-sharp triangular cornice beams + Ascension crowning element
    add_cylinder(bm_pas, Vector((fx - 4.7, -15.6, z_roof1 - 0.3)), Vector((fx - 3.9, 0.0, 41.8)), 0.92, 0.72, segments=6)
    add_cylinder(bm_pas, Vector((fx - 4.7, 15.6, z_roof1 - 0.3)), Vector((fx - 3.9, 0.0, 41.8)), 0.92, 0.72, segments=6)
    # Angular buttress blades closing the outer porch bays
    for sy in (-1, 1):
        add_cylinder(bm_pas, Vector((fx - 7.4, sy * 15.2, Z_NAVE)), Vector((fx - 4.6, sy * 15.2, z_roof0)), 0.95, 0.65, segments=6)
    # Gilt cross crowning the pediment
    add_cylinder(bm_gold, Vector((fx - 3.9, 0.0, 41.4)), Vector((fx - 3.9, 0.0, 46.2)), 0.26, 0.20, segments=8)
    add_cylinder(bm_gold, Vector((fx - 3.9, -1.65, 44.5)), Vector((fx - 3.9, 1.65, 44.5)), 0.22, 0.22, segments=8)

    # ── Subirachs' groups along the S-shaped path (decorative, non-collidable mesh) ──
    # Seen from the plaza (+Y is the viewer's LEFT): level 1 reads left -> right, level 2 right -> left,
    # level 3 left -> right, ending top right with the burial.
    face_w = math.pi
    # Level 1 (ground): Last Supper (left), Kiss of Judas + magic square, Flagellation (centre),
    # Peter's denial, Ecce Homo / Pilate (right)
    for sy in (-1, 1):
        add_box(bm_pas, (fx - 3.2, sy * 5.6, Z_NAVE + 1.0), (1.8, 2.6, 2.0))  # in front of the pier, off the walk line
        for i, fi in enumerate((-0.75, 0.0, 0.75)):
            add_subirachs_figure(bm_psculpt, Vector((fx - 3.2, sy * 5.6 + fi, Z_NAVE + 2.0)), 2.3 - 0.15 * abs(fi), face_w + sy * 0.25 - fi * 0.3, kind=(1 if i == 0 else (2 if i == 2 else 0)))
    for k, y in enumerate((14.9, 13.8, 12.7)):  # Last Supper group on the far left (in front of the pier)
        add_subirachs_figure(bm_psculpt, Vector((fx - 2.9, y, Z_NAVE)), 2.1, face_w - 0.3, kind=2 if k == 1 else 0)
    # Flagellation column + Christ in the central doorway jamb
    add_cylinder(bm_pas, Vector((fx - 2.4, -4.2, Z_NAVE)), Vector((fx - 2.4, -4.2, Z_NAVE + 4.2)), 0.34, 0.30, segments=8)
    add_subirachs_figure(bm_psculpt, Vector((fx - 2.95, -4.2, Z_NAVE)), 2.2, face_w)
    # Magic square (4x4, constant 33) plaque beside the Kiss of Judas
    add_box(bm_gold, (fx - 1.72, 4.4, Z_NAVE + 3.2), (0.14, 1.25, 1.25))

    # Level 2 ledge (Z ≈ 10.6, above the doors): Way of the Cross, Veronica at the centre
    add_box(bm_pas, (fx - 2.7, 0.0, 10.35), (2.2, 25.0, 0.5))
    for k, y in enumerate((-11.0, -9.9, -8.7, -5.6, -4.6, -0.6, 0.6, 4.6, 5.7, 8.6, 9.8, 11.0)):
        add_subirachs_figure(bm_psculpt, Vector((fx - 3.1, y, 10.6)), 2.1 + 0.15 * math.sin(k * 1.7), face_w + 0.2 * math.sin(k * 2.1), kind=k % 3)
    # Veronica's veil: flat bronze-faced cloth with the face of Christ
    add_box(bm_bronze, (fx - 3.65, 0.0, 12.9), (0.08, 1.2, 1.5))

    # Level 3 ledge (Z ≈ 17.2, under the porch roof, in front of the open tower-gallery band):
    # soldiers casting lots (left), the Crucifixion (centre), the Burial (right)
    add_box(bm_pas, (fx - 3.0, 0.0, 16.95), (2.0, 25.0, 0.5))
    for k, y in enumerate((10.8, 9.6, 8.3, 6.8)):
        add_subirachs_figure(bm_psculpt, Vector((fx - 3.3, y, 17.2)), 2.1, face_w + 0.3 * math.sin(k), kind=1 if k % 2 == 0 else 0)
    for k, y in enumerate((-6.6, -7.8, -9.0, -10.2)):
        add_subirachs_figure(bm_psculpt, Vector((fx - 3.3, y, 17.2)), 2.0, face_w - 0.2, kind=2)
    # Crucified Christ on the bronze beam cross (centre top)
    add_box(bm_bronze, (fx - 3.4, 0.0, 19.6), (0.4, 0.4, 4.8))
    add_box(bm_bronze, (fx - 3.4, 0.0, 21.0), (0.4, 4.6, 0.4))
    c = Vector((fx - 3.75, 0.0, 18.4))
    add_frustum(bm_psculpt, c, 0.26, 0.2, 0.36, 0.24, 1.45, face_w)
    for side in (-1, 1):
        add_cylinder(bm_psculpt, c + Vector((0, side * 0.12, 1.35)), c + Vector((0, side * 1.25, 1.75)), 0.09, 0.07, segments=5)
    add_frustum(bm_psculpt, c + Vector((0, 0, 1.45)), 0.22, 0.22, 0.2, 0.2, 0.3, face_w + 0.3, 0.3)


# ─────────────────────────────────────────────────────────────────────────────
# GLORY FAÇADE (south, Blender -Y; main façade, under construction). Target values — this is the
# PLANNED design; everything beyond the published elements below is conjecture and is kept simple:
#   * Narthex with 7 doors (the 7 sacraments): one door per nave aisle (5) with the central one
#     triple [Wikipedia — high for count, positions follow the 7.5 m module].
#   * Portico of 7 large columns (gifts of the Holy Spirit; the deadly sins at their bases, the
#     virtues on top) [Wikipedia / guides — high for count].
#   * 16 hyperboloid lanterns rising in a crescendo over the portico [project descriptions — medium;
#     their layout in two staggered rows of 8 and their heights are CONJECTURE].
#   * Clouds bearing the text of the Creed above the portico [project descriptions — medium; the
#     single gilt word CREDO stands in for the full text — CONJECTURE].
#   * Entrance raised ~5 m above the street with a ~57 m stair bridging Carrer de Mallorca
#     [Wikipedia — medium]. NOT modelled at that scale: the runtime floor of the terrace is 1.2 m and
#     the stair ramp is y = -57.5..-71 (CollisionSystem), so the stair keeps its current footprint.
#   * The 4 Glory towers stand on 8 columns (official site, 2025) — the towers are another module;
#     here the wall piers under them stay where they were.
GLORY_FY = -49.5
GLORY_COLUMN_Y = GLORY_FY - 6.8      # portico column line
GLORY_CANOPY_Z = (26.6, 29.4)        # portico roof underside / top


def build_glory_facade(
    bm_warm: bmesh.types.BMesh,
    bm_gdeco: bmesh.types.BMesh,
    bm_stairs_warm: bmesh.types.BMesh,
    bm_bronze: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
) -> None:
    """South Glory Facade (Y = -49.5, planned design): narthex with 7 doors, portico of 7 columns,
    16 hyperboloid lanterns, the Creed clouds and the grand staircase."""
    fy = GLORY_FY
    zc0, zc1 = GLORY_CANOPY_Z

    # Narthex wall: piers between the 7 doors (walkable openings unchanged: |x| < 4.5, 7.9..11.5,
    # 14.9..19.3); the upper wall stands north of the Glory tower spirals (Y = -47.4..-45.6).
    for px in (-21.0, -13.2, -6.2, 6.2, 13.2, 21.0):
        add_box(bm_warm, (px, fy + 2.4, 7.2), (3.4, 3.2, 14.4))
        add_box(bm_warm, (px, fy + 3.0, 25.4), (3.4, 1.8, 13.4))
    add_box(bm_warm, (0.0, fy + 2.4, 12.2), (45.0, 2.8, 3.6))
    add_box(bm_warm, (0.0, fy + 3.0, 26.8), (45.0, 1.8, 16.4))

    # Seven door frames (parabolic arches on the narthex wall face). The central triple door shares
    # the 9 m opening: its two inner arches spring from corbels at Z = 4.2 m (head height stays clear).
    yd = fy + 0.7
    for xc, hw, z_spring, rise in ((-3.0, 1.45, 4.2, 5.4), (0.0, 1.45, 4.2, 5.8), (3.0, 1.45, 4.2, 5.4),
                                   (-9.7, 1.75, Z_NAVE, 8.6), (9.7, 1.75, Z_NAVE, 8.6),
                                   (-17.1, 2.15, Z_NAVE, 8.6), (17.1, 2.15, Z_NAVE, 8.6)):
        add_arch_tube(bm_gdeco, Vector((xc - hw - 0.05, yd, z_spring)), Vector((xc + hw + 0.05, yd, z_spring)), rise, 0.26, 0.2, n=12, segments=6, sharp=1.2)
    for xc in (-1.5, 1.5):  # corbels carrying the inner arches of the triple door
        add_lathe(bm_gdeco, xc, yd, [(3.6, 0.05), (4.0, 0.3), (4.3, 0.34)], segments=6, cap_top=True)
    # Bronze doors folded open (central 'Our Father' door and the side doors)
    for sx in (-1, 1):
        add_box(bm_bronze, (sx * 4.2, fy + 3.2, Z_NAVE + 4.0), (0.32, 3.2, 8.0))
        add_box(bm_bronze, (sx * 9.8, fy + 2.2, Z_NAVE + 3.2), (3.6, 0.32, 6.4))

    # PORTICO: 7 columns (gifts of the Holy Spirit) — Gaudí double-twist shafts on a 'sin' pedestal,
    # with a 'virtue' capital knot, carrying the portico roof. Spacing 6 m (x = -18..18).
    for i in range(7):
        px = -18.0 + i * 6.0
        cy = GLORY_COLUMN_Y
        # Pedestal: crouching, lumpy mass (the deadly sin trampled under the gift)
        add_lathe(bm_warm, px, cy, [(Z_NAVE, 1.5), (Z_NAVE + 1.1, 1.45), (Z_NAVE + 2.2, 1.35), (Z_NAVE + 2.8, 1.22)], segments=10, cap_top=True, phase=0.3 * i)
        add_double_twist_shaft(bm_warm, px, cy, Z_NAVE + 2.8, zc0 - 1.6, 1.2, 0.92, sides=8, rings=12, segs=24, flute=0.14)
        # Virtue capital: ellipsoidal knot flaring into the roof
        add_lathe(bm_warm, px, cy, [(zc0 - 1.7, 0.95), (zc0 - 1.0, 1.35), (zc0 - 0.3, 1.5), (zc0 + 0.05, 1.9)], segments=12, cap_top=True)
        add_robed_figure(bm_gdeco, Vector((px, cy - 1.45, zc0 - 3.6)), 2.0, -math.pi * 0.5, wings=True)
        # Sin creature crouched on the pedestal front (decorative)
        add_ellipsoid(bm_gdeco, Vector((px, cy - 1.55, Z_NAVE + 1.0)), (0.9, 0.55, 0.7), subdivisions=1)
        add_ellipsoid(bm_gdeco, Vector((px, cy - 2.05, Z_NAVE + 1.55)), (0.35, 0.3, 0.32), subdivisions=1)

    # Portico roof and its arcade: parabolic arches between the columns along the front edge
    add_box(bm_warm, (0.0, fy - 5.6, (zc0 + zc1) * 0.5), (42.0, 5.8, zc1 - zc0))
    # (springing inside the column shafts so the arcade reads continuous)
    for i in range(6):
        x0 = -18.0 + i * 6.0
        add_arch_tube(bm_warm, Vector((x0, GLORY_COLUMN_Y - 0.3, zc0 - 8.6)), Vector((x0 + 6.0, GLORY_COLUMN_Y - 0.3, zc0 - 8.6)), 8.4, 0.6, 0.5, n=12, segments=7, sharp=1.0)

    # 16 hyperboloid lanterns in a crescendo over the portico: two staggered rows of 8,
    # lower in front, taller behind, rising toward the centre (layout/heights: conjecture).
    def crescendo(x: float) -> float:
        return max(0.0, 1.0 - abs(x) / 21.5) ** 1.2
    for i in range(8):
        x = -19.25 + 5.5 * i
        add_hyperboloid_lantern(bm_warm, bm_gold, x, fy - 7.6, zc1, 6.0 + 9.0 * crescendo(x), 1.35, segments=12)
    for i in range(8):
        x = -16.5 + i * (33.0 / 7.0)
        add_hyperboloid_lantern(bm_warm, bm_gold, x, fy - 5.3, zc1, 9.0 + 14.0 * crescendo(x), 1.55, segments=12)

    # Clouds bearing the Creed above the portico, in front of the tower bases (decorative)
    for row, (zc, w, depth) in enumerate(((zc1 + 3.0, 40.0, 2.6), (zc1 + 7.5, 32.0, 2.4), (zc1 + 11.5, 24.0, 2.2), (zc1 + 14.2, 16.0, 2.0))):
        add_cloud_mass(bm_gdeco, Vector((0.0, fy - 5.0, zc)), w, 3.4, depth, lobes=int(w / 2.6), seed=row)
    # Gilt lettering of the Creed (one word as a stand-in for the full text)
    glyph_c = [(0.9, 0.9, 0.3, 1.0), (0.3, 1.0, 0.05, 0.5), (0.05, 0.5, 0.3, 0.0), (0.3, 0.0, 0.9, 0.1)]
    glyph_r = [(0.1, 0.0, 0.1, 1.0), (0.1, 1.0, 0.75, 0.85), (0.75, 0.85, 0.75, 0.6), (0.75, 0.6, 0.1, 0.5), (0.35, 0.5, 0.85, 0.0)]
    glyph_e = [(0.1, 0.0, 0.1, 1.0), (0.1, 1.0, 0.85, 1.0), (0.1, 0.5, 0.65, 0.5), (0.1, 0.0, 0.85, 0.0)]
    glyph_d = [(0.1, 0.0, 0.1, 1.0), (0.1, 1.0, 0.6, 0.85), (0.6, 0.85, 0.85, 0.5), (0.85, 0.5, 0.6, 0.15), (0.6, 0.15, 0.1, 0.0)]
    glyph_o = [(0.5, 1.0, 0.1, 0.5), (0.1, 0.5, 0.5, 0.0), (0.5, 0.0, 0.9, 0.5), (0.9, 0.5, 0.5, 1.0)]
    add_letter_strokes(bm_gold, Vector((-6.3, fy - 6.5, zc1 + 14.6)), Vector((1, 0, 0)), [glyph_c, glyph_r, glyph_e, glyph_d, glyph_o], 2.1, 0.55, 0.14)

    # Ceremonial terrace and grand staircase toward Carrer de Mallorca (footprint fixed by the runtime)
    add_box(bm_warm, (0.0, -52.5, Z_NAVE * 0.5), (44.0, 11.0, Z_NAVE))
    for step in range(10):
        sz = (10 - step) * (Z_NAVE / 10.0) + 0.16
        sy = -58.65 - step * 1.18
        sw = 34.0 + step * 0.8
        add_box(bm_stairs_warm, (0.0, sy, sz * 0.5 - 0.16), (sw, 1.24, sz))
    # Flanking parapets with the two monuments at the foot of the stair (fire and water in Gaudí's
    # scheme — represented as gilt flame finials on stone stems; form is conjecture)
    for sx in (-1, 1):
        add_box(bm_warm, (sx * 19.5, -64.0, 1.2), (1.4, 13.5, 2.4))
        add_lathe(bm_warm, sx * 19.5, -70.0, [(2.4, 0.9), (4.0, 0.6), (6.5, 0.5), (7.2, 0.85)], segments=8, cap_top=True)
        add_cylinder(bm_gold, Vector((sx * 19.5, -70.0, 7.1)), Vector((sx * 19.5, -70.0, 9.6)), 0.6, 0.06, segments=8)


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
    """Smooth parabolic roofs, detailed Venetian trencadís fruit-basket pinnacles & Neo-Gothic North Apse exterior."""
    # 1. Smooth Parabolic Central Nave Roof (X: -8.2..+8.2, Y: -46..-7.5, Z: 46.5..55.5m)
    add_parabolic_roof_vault(bm_warm, bm_gold, (0.0, -26.8, Z_NAVE_VAULT + 0.2), 16.4, 38.6, 8.8, axis="Y", ribs=5)

    # 2. Smooth Parabolic Transept Roofs (X: ±7.6..±28.8, Y: -8.2..+8.2 — clear of ±31.5m tower shafts!)
    for sx in (-1, 1):
        add_parabolic_roof_vault(bm_warm, bm_gold, (sx * 18.2, 0.0, Z_NAVE_VAULT + 0.2), 16.4, 21.2, 8.8, axis="X", ribs=3)

    # 3. Nave side elevation (owned walls/windows are in build_interior; this module adds the crowning):
    #    Target: one gabled pediment per 7.5 m bay at BOTH levels — over the aisle windows (aisle roof,
    #    ~30 m vault) and over the clerestory of the central nave (~45 m vault) — each crowned by a
    #    trencadís fruit-basket pinnacle [photos / guides — medium confidence for which level carries
    #    which finial]. Bay centres follow the interior's wall bays (y = -18.75 .. -48.75 aisle level;
    #    clerestory only where the central nave roof is, y = -18.75 .. -41.25, clear of the Glory towers).
    for sx in (-1, 1):
        add_parabolic_roof_vault(bm_warm, bm_gold, (sx * 15.2, -26.8, Z_AISLE_VAULT + 0.2), 15.4, 38.6, 3.8, axis="Y", ribs=5)
        for bay in range(5):
            py = -18.75 - bay * GRID
            px = sx * 22.8
            add_pointed_gable(bm_warm, (px, py), Z_AISLE_VAULT + 0.4, 6.4, 9.6, 1.5, facing="X+" if sx > 0 else "X-")
            add_fruit_basket(bm_warm, bm_mosaic, bm_gold, px, py, Z_AISLE_VAULT + 9.3, 0.95)
            if bay < 4:
                # Clerestory gable rising in front of the central-nave roof slope, with its fruit basket
                pxc = sx * 8.6
                add_pointed_gable(bm_warm, (pxc, py), Z_NAVE_VAULT - 4.6, 5.8, 10.0, 1.3, facing="X+" if sx > 0 else "X-")
                add_fruit_basket(bm_warm, bm_mosaic, bm_gold, pxc, py, Z_NAVE_VAULT + 5.1, 1.0)

    # 4. ICONIC NEO-GOTHIC NORTH APSE EXTERIOR (Oldest 1891–1893 part of Sagrada Família!):
    #    8 Radial Buttresses + Flying Buttress Arches + 7 Steep Chapel Gables with Golden 'M' Monograms + 14 Catalan Gargoyles!
    num_chapels = 7
    r_apse_wall = 19.2
    r_buttress = 21.8

    # 4a. 8 Radial Neo-Gothic Buttress Piers, Flying Buttress Arches (Strebebögen) & Soaring Pinnacles!
    for i in range(num_chapels + 1):
        ang = math.pi * (0.04 + 0.92 * i / num_chapels)
        ca, sa = math.cos(ang), math.sin(ang)
        bx = r_buttress * ca
        by = 16.5 + r_buttress * sa
        wx = r_apse_wall * ca
        wy = 16.5 + r_apse_wall * sa
        # Tall stepped radial buttress pier rising cleanly from ground/crypt terrace up to Z = 43m
        add_box(bm_warm, (bx, by, 21.5), (1.7, 2.8, 43.0), rot_euler=(0.0, 0.0, ang - math.pi * 0.5))
        # Double-tier Neo-Gothic Flying Buttress Arches leaping inward to the upper Apse drum!
        add_cylinder(bm_warm, Vector((bx, by, 30.0)), Vector((wx * 0.94, 16.5 + (wy - 16.5) * 0.94, 38.0)), 0.58, 0.48, segments=6)
        add_cylinder(bm_warm, Vector((bx, by, 39.5)), Vector((wx * 0.93, 16.5 + (wy - 16.5) * 0.93, 47.5)), 0.54, 0.44, segments=6)
        # Tall soaring Gothic buttress spire pinnacle rising above the apse chapels (Z = 42..64m)
        add_cylinder(bm_warm, Vector((bx * 0.95, 16.5 + (by - 16.5) * 0.95, 41.0)), Vector((bx * 0.95, 16.5 + (by - 16.5) * 0.95, 60.5)), 1.25, 0.26, segments=8)
        add_cylinder(bm_mosaic, Vector((bx * 0.95, 16.5 + (by - 16.5) * 0.95, 60.5)), Vector((bx * 0.95, 16.5 + (by - 16.5) * 0.95, 64.5)), 0.48, 0.08, segments=8)

    # 4b. 7 Steep Pointed Chapel Gables with Rosettes, Golden 'M' (Maria) Monograms & 14 Catalan Stone Gargoyles!
    for i in range(num_chapels):
        a0 = math.pi * (0.04 + 0.92 * i / num_chapels)
        a1 = math.pi * (0.04 + 0.92 * (i + 1) / num_chapels)
        am = 0.5 * (a0 + a1)
        ca, sa = math.cos(am), math.sin(am)
        gx = (r_apse_wall + 0.85) * ca
        gy = 16.5 + (r_apse_wall + 0.85) * sa
        # Outward radial direction is (ca, sa) = (-sin(rot_z), cos(rot_z)) -> rot_z = am - pi/2
        rot_g = am - math.pi * 0.5
        add_pointed_gable(bm_warm, (gx, gy), 34.5, 6.4, 13.5, 1.4, rot_z=rot_g, crockets=True)

        # Recessed circular stone rosette + golden 'M' monogram on each Apse Chapel Gable (Z = 39.2m)
        mx = (r_apse_wall + 1.65) * ca
        my = 16.5 + (r_apse_wall + 1.65) * sa
        mz = 39.2
        ux, uy = math.cos(rot_g), math.sin(rot_g)
        for s in range(10):
            ra0 = 2.0 * math.pi * s / 10.0
            ra1 = 2.0 * math.pi * (s + 1) / 10.0
            p_r0 = Vector((mx + 1.05 * math.cos(ra0) * ux, my + 1.05 * math.cos(ra0) * uy, mz + 1.05 * math.sin(ra0)))
            p_r1 = Vector((mx + 1.05 * math.cos(ra1) * ux, my + 1.05 * math.cos(ra1) * uy, mz + 1.05 * math.sin(ra1)))
            add_cylinder(bm_gold, p_r0, p_r1, 0.10, 0.10, segments=5)
        # Golden 'M' (Maria) monogram strokes inside the rosette
        p_bl = Vector((mx - 0.55 * ux, my - 0.55 * uy, mz - 0.55))
        p_tl = Vector((mx - 0.55 * ux, my - 0.55 * uy, mz + 0.55))
        p_mid = Vector((mx, my, mz - 0.10))
        p_tr = Vector((mx + 0.55 * ux, my + 0.55 * uy, mz + 0.55))
        p_br = Vector((mx + 0.55 * ux, my + 0.55 * uy, mz - 0.55))
        add_cylinder(bm_gold, p_bl, p_tl, 0.09, 0.09, segments=5)
        add_cylinder(bm_gold, p_tl, p_mid, 0.09, 0.09, segments=5)
        add_cylinder(bm_gold, p_mid, p_tr, 0.09, 0.09, segments=5)
        add_cylinder(bm_gold, p_tr, p_br, 0.09, 0.09, segments=5)

        # Pair of projecting Catalan fauna stone gargoyles (lizards/chameleons) flanking each chapel cornice!
        for ga in (a0 + 0.025, a1 - 0.025):
            gca, gsa = math.cos(ga), math.sin(ga)
            p_g0 = Vector((r_apse_wall * gca, 16.5 + r_apse_wall * gsa, 38.2))
            p_g1 = Vector(((r_apse_wall + 2.35) * gca, 16.5 + (r_apse_wall + 2.35) * gsa, 37.85))
            add_cylinder(bm_warm, p_g0, p_g1, 0.34, 0.16, segments=6)
            # Curled lizard head / snout accent at gargoyle tip
            add_cylinder(bm_warm, p_g1, p_g1 + Vector((0.35 * gca, 0.35 * gsa, 0.22)), 0.20, 0.10, segments=5)


def build_facades() -> None:
    reset_scene()
    mats = get_materials()

    bm_nat = bmesh.new()
    bm_pas = bmesh.new()
    bm_pcol = bmesh.new()
    bm_pbones = bmesh.new()
    bm_psculpt = bmesh.new()
    bm_warm = bmesh.new()
    bm_gdeco = bmesh.new()
    bm_stairs_nat = bmesh.new()
    bm_stairs_pas = bmesh.new()
    bm_stairs_warm = bmesh.new()
    bm_bronze = bmesh.new()
    bm_cypress = bmesh.new()
    bm_mosaic = bmesh.new()
    bm_gold = bmesh.new()
    bm_white = bmesh.new()

    bm_deco = bmesh.new()
    build_nativity_facade(bm_nat, bm_stairs_nat, bm_bronze, bm_cypress, bm_gold, bm_white)
    add_nativity_encrustation(bm_deco, NATIVITY_FX)
    build_passion_facade(bm_pas, bm_pcol, bm_pbones, bm_psculpt, bm_stairs_pas, bm_bronze, bm_gold)
    build_glory_facade(bm_warm, bm_gdeco, bm_stairs_warm, bm_bronze, bm_gold)
    build_roofs_and_pinnacles(bm_warm, bm_mosaic, bm_gold)

    # Gaudí's dripping, organically eroded Nativity relief + crisp stone edge bevels on Passion & Glory
    apply_dripping_relief(bm_nat, amp=0.30, min_z=2.2, max_edge=1.15)
    apply_dripping_relief(bm_deco, amp=0.05, min_z=0.0, max_edge=99.0, seed=57)
    bevel_sharp_edges(bm_pas, width=0.055, angle_deg=60.0)
    bevel_sharp_edges(bm_warm, width=0.055, angle_deg=60.0)

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
    finalize_bmesh_object(bm_warm, "Facade_GloryAndRoofs", mats["sandstone_warm"], smooth=False, uv_scale=0.14)
    finalize_bmesh_object(bm_gdeco, "Facade_GloryAndRoofs_Sculpture_Leaves", mats["sandstone_warm"], smooth=True, uv_scale=0.25, ao_dist=2.5)
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
