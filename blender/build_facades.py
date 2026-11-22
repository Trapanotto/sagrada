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
    apply_organic_stone_displacement,
    bevel_sharp_edges,
    export_glb,
    finalize_bmesh_object,
    get_materials,
    reset_scene,
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
) -> None:
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
    # Tall palm-frond column rising directly out of the turtle's carapace up into the portal arch!
    add_cylinder(bm_stone, Vector((cx, cy, shell_z + 0.35)), Vector((cx, cy, z_floor + 9.2)), 0.42, 0.34, segments=10)
    add_cylinder(bm_stone, Vector((cx, cy, z_floor + 9.0)), Vector((cx, cy, z_floor + 10.1)), 0.44, 0.72, segments=10)


def build_nativity_facade(
    bm_nat: bmesh.types.BMesh,
    bm_bronze: bmesh.types.BMesh,
    bm_cypress: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
    bm_white: bmesh.types.BMesh,
) -> None:
    """East Nativity Facade (X = +31.5): organic sandstone, 3 gabled portals, Cypress Tree of Life."""
    fx = 31.5

    # Entrance steps leading from Plaça de Gaudí (Z=0) cleanly up to Nave landing (Z=1.2) — ZERO buried steps!
    for step in range(6):
        sz = (step + 1) * (Z_NAVE / 6.0)
        add_box(bm_nat, (fx + 5.2 - step * 0.56, 0.0, sz * 0.5), (0.60, 28.0, sz))
    add_box(bm_nat, (fx + 0.9, 0.0, Z_NAVE * 0.5), (2.4, 28.0, Z_NAVE))

    # Massive sculpted piers flanking the 3 portals (split cleanly around Z=14.5..18.5m so the East 14.5m Tower-Base Gallery is 100% OPEN!)
    pier_ys = (-14.2, -4.6, 4.6, 14.2)
    for py in pier_ys:
        add_box(bm_nat, (fx, py, 7.2), (4.2, 3.6, 14.4))
        add_box(bm_nat, (fx, py, 24.4), (4.2, 3.6, 11.4))
        # Organic dripping stalactite-like buttress projections
        for k in range(5):
            zk = 5.0 + k * 4.5
            r = 1.45 - k * 0.16
            add_cylinder(bm_nat, Vector((fx + 2.2, py, zk)), Vector((fx + 1.8, py, zk + 4.8)), r, r * 0.68, segments=10)

    # Upper facade wall split cleanly around Z = 14.5..18.5m so the East Tower-Base Gallery & Spiral Stairs are 100% OPEN!
    add_box(bm_nat, (fx, 0.0, 12.2), (3.4, 29.0, 3.6))
    add_box(bm_nat, (fx, 0.0, 24.4), (3.4, 29.0, 11.4))
    # Deep sculpted archivolts framing each portal
    for py, p_w, p_h, g_h in ((-9.2, 5.2, 8.6, 24.0), (0.0, 6.2, 10.4, 30.0), (9.2, 5.2, 8.6, 24.0)):
        # Stepped parabolic archivolt ribs projecting outward
        for layer in range(4):
            lx = fx + 1.8 + layer * 0.48
            lw = p_w + layer * 0.65
            lh = p_h + layer * 0.55
            # Left & right jambs
            for sy in (-1, 1):
                add_cylinder(
                    bm_nat,
                    Vector((lx, py + sy * (lw * 0.5), Z_NAVE)),
                    Vector((lx, py + sy * (lw * 0.35), lh)),
                    0.48,
                    0.40,
                    segments=8,
                )
            # Pointed parabolic arch top
            add_cylinder(bm_nat, Vector((lx, py - lw * 0.35, lh)), Vector((lx, py, lh + 3.2)), 0.42, 0.36, segments=8)
            add_cylinder(bm_nat, Vector((lx, py + lw * 0.35, lh)), Vector((lx, py, lh + 3.2)), 0.42, 0.36, segments=8)
        # Soaring organic triangular gable pinnacle above each portal
        add_pointed_gable(bm_nat, (fx + 1.9, py), p_h + 2.6, p_w + 3.2, g_h, 2.2, facing="X+")
        # Deep sculpted rosette wheel medallion recessed inside each Nativity gable!
        rz = p_h + 5.6
        rr = 1.65 if py == 0.0 else 1.25
        for s in range(12):
            a0 = 2.0 * math.pi * s / 12.0
            a1 = 2.0 * math.pi * (s + 1) / 12.0
            add_cylinder(
                bm_nat,
                Vector((fx + 3.15, py + rr * math.cos(a0), rz + rr * math.sin(a0))),
                Vector((fx + 3.15, py + rr * math.cos(a1), rz + rr * math.sin(a1))),
                0.20,
                0.20,
                segments=6,
            )
            if s % 2 == 0:
                add_cylinder(
                    bm_gold,
                    Vector((fx + 3.05, py, rz)),
                    Vector((fx + 3.15, py + rr * math.cos(a0), rz + rr * math.sin(a0))),
                    0.09,
                    0.09,
                    segments=6,
                )
        # Organic botanical pinnacles, Gothic crocket spires & sculpted tympanum figure reliefs flanking the gable!
        for sy in (-1, 1):
            add_cylinder(bm_nat, Vector((fx + 2.9, py + sy * (p_w * 0.55), p_h + 1.2)), Vector((fx + 2.8, py + sy * (p_w * 0.52), p_h + 10.5)), 0.58, 0.12, segments=8)
            add_cylinder(bm_nat, Vector((fx + 3.3, py + sy * (p_w * 0.36), p_h + 4.0)), Vector((fx + 3.1, py + sy * (p_w * 0.32), p_h + 14.5)), 0.42, 0.09, segments=7)
            # Carved sculptural niche canopy + figure silhouette beside each portal jamb
            add_cylinder(bm_nat, Vector((fx + 3.25, py + sy * (p_w * 0.52), Z_NAVE + 2.2)), Vector((fx + 3.25, py + sy * (p_w * 0.52), Z_NAVE + 5.0)), 0.42, 0.28, segments=8)
            add_cylinder(bm_white, Vector((fx + 3.45, py + sy * (p_w * 0.52), Z_NAVE + 2.4)), Vector((fx + 3.45, py + sy * (p_w * 0.52), Z_NAVE + 4.5)), 0.24, 0.16, segments=8)
        # Sculpted tympanum narrative relief cluster over portal arch
        for fi in (-1.2, -0.4, 0.4, 1.2):
            add_cylinder(bm_nat, Vector((fx + 2.95, py + fi, p_h + 0.6)), Vector((fx + 2.95, py + fi, p_h + 2.6 - abs(fi) * 0.4)), 0.28, 0.18, segments=7)

        # Sculpted bronze doors folded open against the portal jambs (so walkthrough is clear!)
        for sy in (-1, 1):
            add_box(bm_bronze, (fx - 0.6, py + sy * (p_w * 0.44), Z_NAVE + 3.0), (2.2, 0.25, 6.0))

    # ICONIC NATIVITY FACADE TURTLE (South/Sea) & TORTOISE (North/Mountain) COLUMN PEDESTALS!
    # Positioned on the entrance landing flanking the central Charity Portal at Y = ±4.55!
    add_turtle_column_base(bm_nat, fx + 2.65, -4.55, Z_NAVE, is_sea_turtle=True)
    add_turtle_column_base(bm_nat, fx + 2.65, 4.55, Z_NAVE, is_sea_turtle=False)

    # Luminous Golden Star of Bethlehem radiant medallion crowning the Charity Portal (Z = 29.8m)
    star_x = fx + 3.35
    star_z = 29.8
    for k in range(8):
        ang = 2.0 * math.pi * k / 8.0
        ray_len = 1.95 if k % 2 == 0 else 1.25
        add_cylinder(
            bm_gold,
            Vector((star_x, 0.0, star_z)),
            Vector((star_x + 0.12, ray_len * math.cos(ang), star_z + ray_len * math.sin(ang))),
            0.22,
            0.04,
            segments=5,
        )
    # Central golden Nativity Bethlehem halo ring
    for s in range(12):
        a0 = 2.0 * math.pi * s / 12.0
        a1 = 2.0 * math.pi * (s + 1) / 12.0
        add_cylinder(
            bm_gold,
            Vector((star_x - 0.05, 1.35 * math.cos(a0), star_z + 1.35 * math.sin(a0))),
            Vector((star_x - 0.05, 1.35 * math.cos(a1), star_z + 1.35 * math.sin(a1))),
            0.12,
            0.12,
            segments=5,
        )

    # Central Sculpted Cypress Tree of Life rising above Charity Gable (Z = 38 .. 49m)
    # Multi-tiered organically sculpted Venetian-green mosaic cypress foliage (never a smooth plastic cone!)
    tree_x = fx + 2.0
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
        # Sculpted white ceramic doves perched around the cypress crown
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
    # Red/Gold Tau Cross at the summit of the Cypress Tree
    add_cylinder(bm_gold, Vector((tree_x, 0.0, 48.0)), Vector((tree_x, 0.0, 51.4)), 0.28, 0.24, segments=8)
    add_cylinder(bm_gold, Vector((tree_x, -1.45, 50.9)), Vector((tree_x, 1.45, 50.9)), 0.24, 0.24, segments=8)


def build_passion_facade(
    bm_pas: bmesh.types.BMesh,
    bm_bronze: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
) -> None:
    """West Passion Facade (X = -31.5): 6 giant inclined bone columns, stark portico, Subirachs aesthetic."""
    fx = -31.5

    # Entrance steps from Plaça de la Sagrada Família (Z=0) cleanly up to portico terrace (Z=1.2) — ZERO buried steps!
    for step in range(6):
        sz = (step + 1) * (Z_NAVE / 6.0)
        add_box(bm_pas, (fx - 8.4 + step * 0.58, 0.0, sz * 0.5), (0.62, 30.0, sz))
    add_box(bm_pas, (fx - 2.6, 0.0, Z_NAVE * 0.5), (5.2, 30.0, Z_NAVE))

    # Inner recessed Passion wall split around Z = 14.5..18.5m so West Tower-Base Gallery & Spiral Stairs are 100% OPEN!
    for py in (-14.2, -5.2, 5.2, 14.2):
        add_box(bm_pas, (fx, py, 7.2), (3.4, 4.2, 14.4))
        add_box(bm_pas, (fx, py, 24.4), (3.4, 4.2, 11.2))
    add_box(bm_pas, (fx, 0.0, 12.2), (3.2, 29.0, 3.6))
    add_box(bm_pas, (fx, 0.0, 24.4), (3.2, 29.0, 11.4))
    # Bronze Gospel doors folded open at entrance jambs
    for sy in (-1, 1):
        add_box(bm_bronze, (fx + 0.5, sy * 2.8, Z_NAVE + 3.2), (2.4, 0.26, 6.4))

    # THE 6 ICONIC GIANT INCLINED BONE-SHAPED PORTICO COLUMNS with double-ribbed tendon flutes!
    col_ys = (-13.5, -8.1, -2.7, 2.7, 8.1, 13.5)
    for cy in col_ys:
        p0 = Vector((fx - 6.8, cy, Z_NAVE))
        p_mid = Vector((fx - 5.2, cy * 0.96, 12.0))
        p1 = Vector((fx - 3.6, cy * 0.92, 23.0))
        # Tapered bone-like lower + upper shaft with organic pinched waist & carved stone tendon ribs
        add_cylinder(bm_pas, p0, p_mid, 1.38, 0.98, segments=12)
        add_cylinder(bm_pas, p_mid, p1, 0.98, 1.48, segments=12)
        for dy_rib in (-0.85, 0.85):
            add_cylinder(bm_pas, p0 + Vector((0, dy_rib, 0)), p_mid + Vector((0.1, dy_rib * 0.72, 0)), 0.34, 0.24, segments=6)
            add_cylinder(bm_pas, p_mid + Vector((0.1, dy_rib * 0.72, 0)), p1 + Vector((0, dy_rib * 0.95, 0)), 0.24, 0.36, segments=6)
        # Sculpted angular bone-joint capital pad
        add_box(bm_pas, (p1.x, p1.y, p1.z + 0.55), (2.8, 2.6, 1.1))
        # Diagonal rear brace strut connecting column to inner wall
        add_cylinder(bm_pas, p_mid, Vector((fx - 1.2, cy, 17.5)), 0.55, 0.45, segments=8)

    # Massive overhanging triangular ribbed Passion cornice & angular Subirachs bone-truss pediment (Z = 22.5 .. 42m)
    add_box(bm_pas, (fx - 3.8, 0.0, 24.5), (6.5, 31.5, 3.6))
    # Angular stone pediment backing ridge + dramatic inclined Subirachs bridge gallery (Z = 26..33m)
    add_pointed_gable(bm_pas, (fx - 2.6, 0.0), 26.2, 29.0, 14.5, 1.6, facing="X-", crockets=False)
    # 18 Iconic stark diagonal bone-rib struts fanning outward across the Passion pediment!
    for k in range(18):
        py = -14.5 + k * (29.0 / 17.0)
        h_tri = 14.4 * (1.0 - abs(py) / 16.0)
        if h_tri > 1.2:
            add_cylinder(
                bm_pas,
                Vector((fx - 5.5, py, 26.0)),
                Vector((fx - 3.2, py * 0.90, 26.2 + h_tri)),
                0.44,
                0.28,
                segments=6,
            )
            # Crisp cross-brace bone tendons linking struts at mid-height
            if k < 17 and k % 2 == 0:
                py_next = -14.5 + (k + 1) * (29.0 / 17.0)
                add_cylinder(
                    bm_pas,
                    Vector((fx - 4.7, py, 26.2 + h_tri * 0.42)),
                    Vector((fx - 4.7, py_next, 26.2 + h_tri * 0.42)),
                    0.22,
                    0.22,
                    segments=5,
                )
    # Stark razor-sharp triangular bone pediment frame + central Subirachs Ascension stone arch
    add_cylinder(bm_pas, Vector((fx - 5.6, -15.6, 25.8)), Vector((fx - 3.4, 0.0, 41.8)), 0.92, 0.72, segments=6)
    add_cylinder(bm_pas, Vector((fx - 5.6, 15.6, 25.8)), Vector((fx - 3.4, 0.0, 41.8)), 0.92, 0.72, segments=6)
    # Diagonal angular buttress blades bracing the outer Passion bays
    for sy in (-1, 1):
        add_cylinder(bm_pas, Vector((fx - 7.4, sy * 15.2, Z_NAVE)), Vector((fx - 4.6, sy * 15.2, 24.5)), 0.95, 0.65, segments=6)
    # Golden Ascension cross / halo crowning the Passion pediment
    add_cylinder(bm_gold, Vector((fx - 3.4, 0.0, 41.4)), Vector((fx - 3.4, 0.0, 46.2)), 0.26, 0.20, segments=8)
    add_cylinder(bm_gold, Vector((fx - 3.4, -1.65, 44.5)), Vector((fx - 3.4, 1.65, 44.5)), 0.22, 0.22, segments=8)

    # Angular faceted Subirachs-style sculptural groups along the Passion portico (Flagellation, Judas, Crucifixion)
    for sy in (-1, 1):
        add_box(bm_pas, (fx - 3.2, sy * 6.8, Z_NAVE + 1.8), (1.8, 2.8, 3.6))
        # Faceted dramatic sculptural figures atop plinth
        for fi in (-0.65, 0.0, 0.65):
            add_box(bm_pas, (fx - 3.2, sy * 6.8 + fi, Z_NAVE + 4.7), (0.55, 0.48, 2.2), rot_euler=(0.08 * fi, 0.12, sy * 0.25))
    # Subirachs' iconic Flagellation column + Magic Square (33) plaque flanking the central door
    add_cylinder(bm_pas, Vector((fx - 2.4, -4.2, Z_NAVE)), Vector((fx - 2.4, -4.2, Z_NAVE + 4.2)), 0.34, 0.30, segments=8)
    add_box(bm_gold, (fx - 1.72, 4.4, Z_NAVE + 3.2), (0.14, 1.25, 1.25))
    # Horizontal iron/bronze beam of Subirachs' Crucifixion above the central portico
    add_box(bm_bronze, (fx - 2.3, 0.0, 14.5), (0.45, 7.6, 0.45))
    add_box(bm_bronze, (fx - 2.3, 0.0, 13.8), (0.45, 0.45, 4.2))


def build_glory_facade(
    bm_warm: bmesh.types.BMesh,
    bm_bronze: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
) -> None:
    """South Glory Facade (Y = -49.5, Completed Design): 7 tall columns, cloud portico, monumental bridge staircase."""
    fy = -49.5

    # Main facade wall split cleanly around Z = 14.5..18.5m so South Choir Gallery -> Glory Tower bridges are 100% OPEN!
    for px in (-21.0, -13.2, -6.2, 6.2, 13.2, 21.0):
        add_box(bm_warm, (px, fy + 2.2, 7.2), (3.4, 3.6, 14.4))
        add_box(bm_warm, (px, fy + 2.2, 25.4), (3.4, 3.6, 13.4))
    add_box(bm_warm, (0.0, fy + 2.2, 12.2), (45.0, 3.2, 3.6))
    add_box(bm_warm, (0.0, fy + 2.2, 26.8), (45.0, 3.2, 16.4))

    # Monumental Bronze Lord's Prayer Doors folded open at the center
    for sx in (-1, 1):
        add_box(bm_bronze, (sx * 4.2, fy + 3.2, Z_NAVE + 4.0), (0.32, 3.2, 8.0))
        add_box(bm_bronze, (sx * 9.8, fy + 2.2, Z_NAVE + 3.2), (3.6, 0.32, 6.4))

    # 7 Monumental Fluted Lantern Columns of the Glory Portico (spanning X = -18..+18 at Y = -56.5)
    for i in range(7):
        px = -18.0 + i * 6.0
        h_col = 26.0 + (4.5 - abs(i - 3) * 1.2)
        add_cylinder(bm_warm, Vector((px, fy - 6.8, Z_NAVE)), Vector((px, fy - 6.8, h_col)), 1.32, 0.92, segments=12)
        # 4 sculpted vertical stone flutes wrapping each Glory column
        for k in range(4):
            a = k * math.pi * 0.5 + math.pi * 0.25
            add_cylinder(
                bm_warm,
                Vector((px + 1.22 * math.cos(a), fy - 6.8 + 1.22 * math.sin(a), Z_NAVE)),
                Vector((px + 0.88 * math.cos(a), fy - 6.8 + 0.88 * math.sin(a), h_col)),
                0.24,
                0.18,
                segments=6,
            )
        # Sculpted gilded lantern crown atop each of the 7 columns
        add_cylinder(bm_gold, Vector((px, fy - 6.8, h_col)), Vector((px, fy - 6.8, h_col + 3.6)), 1.18, 0.35, segments=10)
        # Parabolic vault ribs tying portico columns back into the facade
        add_cylinder(bm_warm, Vector((px, fy - 6.8, h_col - 2.0)), Vector((px, fy + 1.0, h_col + 4.5)), 0.72, 0.65, segments=8)

    # Sweeping sculptural "Cloud & Glory" vaulted portico roof canopy (Z = 27 .. 36m)
    add_box(bm_warm, (0.0, fy - 2.8, 29.0), (42.0, 10.5, 4.2))
    add_pointed_gable(bm_warm, (0.0, fy - 5.5), 30.5, 34.0, 18.0, 3.2, facing="Y-")

    # Monumental Ceremonial Terrace & Grand Staircase descending south over Carrer de Mallorca!
    # Wide flat podium terrace cleanly ending at Y = -58.0 (ZERO buried top steps!)
    add_box(bm_warm, (0.0, -52.5, Z_NAVE * 0.5), (44.0, 11.0, Z_NAVE))
    # Grand terraced cascade stairs (Y = -58.6..-70.0, descending cleanly from Z = 1.2 down to asphalt Z = -0.14!)
    for step in range(10):
        sz = (10 - step) * (Z_NAVE / 10.0) + 0.16
        sy = -58.65 - step * 1.18
        sw = 34.0 + step * 0.8
        add_box(bm_warm, (0.0, sy, sz * 0.5 - 0.16), (sw, 1.24, sz))
    # Ornamental flanking parapet walls with gilded light obelisks along the grand staircase
    for sx in (-1, 1):
        add_box(bm_warm, (sx * 19.5, -64.0, 1.2), (1.4, 13.5, 2.4))
        add_cylinder(bm_gold, Vector((sx * 19.5, -70.0, 2.4)), Vector((sx * 19.5, -70.0, 6.2)), 0.55, 0.14, segments=8)


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

    # 2. Smooth Parabolic Transept Roofs (X: ±8..±30.2, Y: -8.2..+8.2)
    for sx in (-1, 1):
        add_parabolic_roof_vault(bm_warm, bm_gold, (sx * 19.0, 0.0, Z_NAVE_VAULT + 0.2), 16.4, 22.6, 8.8, axis="X", ribs=3)

    # 3. Side Aisles Exterior Sloped Roofs + True Pointed Gables + Detailed Fruit-Basket Pinnacles (Obstkörbe)!
    for sx in (-1, 1):
        add_parabolic_roof_vault(bm_warm, bm_gold, (sx * 15.2, -26.8, Z_AISLE_VAULT + 0.2), 15.4, 38.6, 3.8, axis="Y", ribs=5)
        # Decorative pointed gables + iconic Venetian Trencadís Fruit-Basket Pinnacles along nave roofline!
        for bay in range(5):
            py = -18.75 - bay * GRID
            px = sx * 22.8
            add_pointed_gable(bm_warm, (px, py), Z_AISLE_VAULT + 0.4, 6.4, 9.6, 1.5, facing="X+" if sx > 0 else "X-")
            # Sculpted woven stone basket chalice (Z = 40.8..43.8m)
            z_bask = Z_AISLE_VAULT + 9.6
            add_cylinder(bm_warm, Vector((px, py, z_bask - 0.3)), Vector((px, py, z_bask + 1.4)), 0.72, 0.96, segments=10)
            add_cylinder(bm_mosaic, Vector((px, py, z_bask + 1.2)), Vector((px, py, z_bask + 3.0)), 0.92, 1.22, segments=10)
            # Clustered colorful Venetian ceramic fruit spheres (oranges, apples, grapes, figs) crowning the basket!
            for fi in range(7):
                fa = 2.0 * math.pi * fi / 7.0
                r_f = 0.78 if fi % 2 == 0 else 0.56
                z_f = z_bask + (3.25 if fi % 2 == 0 else 3.72)
                ret = bmesh.ops.create_icosphere(bm_mosaic, subdivisions=1, radius=0.42)
                for v in ret["verts"]:
                    v.co.x += px + r_f * math.cos(fa)
                    v.co.y += py + r_f * math.sin(fa)
                    v.co.z += z_f
            # Central top fruit globe + golden wheat-sheaf & cross pinnacle finial
            ret_top = bmesh.ops.create_icosphere(bm_mosaic, subdivisions=1, radius=0.52)
            for v in ret_top["verts"]:
                v.co.x += px
                v.co.y += py
                v.co.z += z_bask + 4.15
            add_cylinder(bm_gold, Vector((px, py, z_bask + 4.4)), Vector((px, py, z_bask + 6.4)), 0.32, 0.06, segments=8)
            add_cylinder(bm_gold, Vector((px, py - 0.65, z_bask + 5.6)), Vector((px, py + 0.65, z_bask + 5.6)), 0.12, 0.12, segments=6)

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
    bm_warm = bmesh.new()
    bm_bronze = bmesh.new()
    bm_cypress = bmesh.new()
    bm_mosaic = bmesh.new()
    bm_gold = bmesh.new()
    bm_white = bmesh.new()

    build_nativity_facade(bm_nat, bm_bronze, bm_cypress, bm_gold, bm_white)
    build_passion_facade(bm_pas, bm_bronze, bm_gold)
    build_glory_facade(bm_warm, bm_bronze, bm_gold)
    build_roofs_and_pinnacles(bm_warm, bm_mosaic, bm_gold)

    # Organic 3D stalactite/botanical relief displacement on Nativity Facade + crisp stone edge bevels on Passion & Glory!
    apply_organic_stone_displacement(bm_nat, amp=0.14, min_z=2.2)
    bevel_sharp_edges(bm_pas, width=0.055, angle_deg=60.0)
    bevel_sharp_edges(bm_warm, width=0.055, angle_deg=60.0)

    finalize_bmesh_object(bm_nat, "Facade_Nativity", mats["nativity_stone"], smooth=True, uv_scale=0.16)
    finalize_bmesh_object(bm_pas, "Facade_Passion", mats["passion_stone"], smooth=False, uv_scale=0.15)
    finalize_bmesh_object(bm_warm, "Facade_GloryAndRoofs", mats["sandstone_warm"], smooth=False, uv_scale=0.14)
    finalize_bmesh_object(bm_bronze, "Facade_BronzeDoors", mats["bronze_door"], smooth=False, uv_scale=0.25)
    finalize_bmesh_object(bm_cypress, "Facade_CypressTree", mats["cypress_green"], smooth=True, uv_scale=0.30)
    finalize_bmesh_object(bm_mosaic, "Facade_FruitPinnacles", mats["trencadis"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_gold, "Facade_GoldAccents", mats["gold_accent"], smooth=True, uv_scale=0.35)
    finalize_bmesh_object(bm_white, "Facade_Doves", mats["white_marble"], smooth=True, uv_scale=0.40)

    export_glb(os.path.join(MODEL_DIR, "facades.glb"))


if __name__ == "__main__":
    build_facades()
