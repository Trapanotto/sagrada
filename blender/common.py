"""Shared architectural dimensions, PBR material factory, and Gaudí parametric geometry."""

from __future__ import annotations

import math
import os
import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEX_DIR = os.path.join(ROOT_DIR, "public", "textures")
SRC_TEX_DIR = os.path.join(ROOT_DIR, "blender", "textures_src")
CC0_DIR = os.path.join(SRC_TEX_DIR, "cc0")
MODEL_DIR = os.path.join(ROOT_DIR, "public", "models")
os.makedirs(MODEL_DIR, exist_ok=True)

# ─── Real-world Sagrada Família Metric Grid (1 unit = 1 meter) ───
# Blender Z-up coordinate system:
#   +X = East  (Nativity Facade, Plaça de Gaudí)
#   -X = West  (Passion Facade, Plaça de la Sagrada Família)
#   +Y = North (Apse, Mary Tower, Crypt below)
#   -Y = South (5-aisle Nave, Glory Facade, Grand Staircase)
#   Z = 0.0    Street level outside

GRID = 7.5  # Gaudí's 7.5m fundamental module
Z_STREET = 0.0
Z_NAVE = 1.2
Z_ALTAR = 2.4
Z_GALLERY = 14.5
Z_CRYPT = -5.5
Z_AISLE_VAULT = 31.2      # 30 m above nave floor
Z_NAVE_VAULT = 46.2       # 45 m above nave floor
Z_CROSSING_VAULT = 61.2   # 60 m above nave floor
Z_APSE_VAULT = 68.0       # Rising into Mary tower base

NAVE_SOUTH_Y = -45.0      # 5 bays south of crossing (-7.5 -> -45.0)
TRANSEPT_X = 30.0         # East/West transept span (-30 .. +30)
APSE_CENTER_Y = 22.5
APSE_RADIUS = 15.0


def reset_scene() -> None:
    """Clear the Blender scene completely."""
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _load_image(
    filename: str,
    colorspace: str = "sRGB",
    target_mean_rgb: tuple[float, float, float] | None = None,
    cache_tag: str = "",
) -> bpy.types.Image | None:
    """Load texture (preferring real CC0 photoscans) and optionally bake Catalan color calibration into pixels so glTF keeps it!"""
    stem = os.path.splitext(filename)[0]
    candidates = [
        os.path.join(CC0_DIR, stem + ".jpg"),
        os.path.join(CC0_DIR, stem + ".png"),
        os.path.join(SRC_TEX_DIR, filename),
        os.path.join(TEX_DIR, filename),
    ]
    path = next((p for p in candidates if os.path.exists(p)), None)
    if not path:
        return None

    if target_mean_rgb is not None and colorspace == "sRGB":
        import numpy as np

        cal_name = f"_cal_{cache_tag or stem}.png"
        cal_path = os.path.join(SRC_TEX_DIR, cal_name)
        existing = bpy.data.images.get(cal_name)
        if existing is not None:
            return existing
        # Bake authentic Catalan stone / foliage color calibration directly into pixel data
        # (fixes Blender glTF exporter dropping chained ShaderNodeMix tint nodes!)
        src_img = bpy.data.images.load(path, check_existing=True)
        w, h = src_img.size[0], src_img.size[1]
        arr = np.array(src_img.pixels[:], dtype=np.float32).reshape((h, w, 4))
        rgb = arr[..., :3]
        # Preserve 100% of photoscan micro-contrast while aligning mean hue & luminance smoothly
        cur_mean = np.maximum(rgb.mean(axis=(0, 1)), 1e-4)
        target = np.array(target_mean_rgb, dtype=np.float32)
        ratio = target / cur_mean
        # Gentle blend keeps authentic photoscan texture grain while unifying Catalan stone palette
        cal_rgb = np.clip(rgb * ratio[None, None, :], 0.02, 0.96)
        arr[..., :3] = cal_rgb
        cal_img = bpy.data.images.new(cal_name, width=w, height=h, alpha=False)
        cal_img.colorspace_settings.name = "sRGB"
        cal_img.pixels.foreach_set(arr.ravel())
        cal_img.filepath_raw = cal_path
        cal_img.file_format = "PNG"
        cal_img.save()
        return cal_img

    cache_key = os.path.basename(path)
    existing = bpy.data.images.get(cache_key)
    if existing is not None:
        return existing
    img = bpy.data.images.load(path)
    img.name = cache_key
    img.colorspace_settings.name = colorspace
    return img


def make_pbr_material(
    name: str,
    albedo_tex: str | None = None,
    normal_tex: str | None = None,
    rough_tex: str | None = None,
    base_color: tuple[float, float, float, float] = (0.8, 0.75, 0.65, 1.0),
    roughness: float = 0.72,
    metallic: float = 0.0,
    normal_strength: float = 1.0,
    emission_color: tuple[float, float, float, float] | None = None,
    emission_strength: float = 0.0,
    alpha: float = 1.0,
    alpha_tex: bool = False,
    coat_weight: float = 0.0,
    coat_roughness: float = 0.25,
    target_mean_rgb: tuple[float, float, float] | None = None,
    uv_scale: float = 1.0,
    double_sided: bool = False,
) -> bpy.types.Material:
    existing = bpy.data.materials.get(name)
    if existing is not None:
        return existing

    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    mat.use_backface_culling = not double_sided
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (700, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (280, 0)
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    bsdf.inputs["Base Color"].default_value = base_color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Alpha"].default_value = alpha
    if coat_weight > 0.0 and "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = coat_weight
        bsdf.inputs["Coat Roughness"].default_value = coat_roughness

    if emission_color is not None and emission_strength > 0.0:
        bsdf.inputs["Emission Color"].default_value = emission_color
        bsdf.inputs["Emission Strength"].default_value = emission_strength

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-750, 0)
    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-550, 0)
    mapping.inputs["Scale"].default_value = (uv_scale, uv_scale, uv_scale)
    links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])

    if albedo_tex:
        img = _load_image(albedo_tex, "sRGB", target_mean_rgb=target_mean_rgb, cache_tag=name.lower())
        if img:
            tex = nodes.new("ShaderNodeTexImage")
            tex.image = img
            tex.location = (-320, 260)
            links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
            color_out = tex.outputs["Color"]
            if alpha_tex:
                links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])

            # Single clean Multiply with baked geometric BVH Ambient Occlusion (COLOR_0) -> 100% glTF preserved!
            if emission_strength == 0.0 and not alpha_tex:
                vcol = nodes.new("ShaderNodeVertexColor")
                vcol.layer_name = "AO_Bake"
                vcol.location = (-140, 480)
                mix_ao = nodes.new("ShaderNodeMix")
                mix_ao.data_type = "RGBA"
                mix_ao.blend_type = "MULTIPLY"
                mix_ao.inputs["Factor"].default_value = 1.0
                mix_ao.location = (80, 280)
                links.new(color_out, mix_ao.inputs[6])
                links.new(vcol.outputs["Color"], mix_ao.inputs[7])
                links.new(mix_ao.outputs[2], bsdf.inputs["Base Color"])
            else:
                links.new(color_out, bsdf.inputs["Base Color"])
                if emission_strength > 0.0 and emission_color is None:
                    links.new(color_out, bsdf.inputs["Emission Color"])
                    bsdf.inputs["Emission Strength"].default_value = emission_strength

    if rough_tex:
        img = _load_image(rough_tex, "Non-Color")
        if img:
            tex = nodes.new("ShaderNodeTexImage")
            tex.image = img
            tex.location = (-200, -40)
            links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
            links.new(tex.outputs["Color"], bsdf.inputs["Roughness"])

    if normal_tex:
        img = _load_image(normal_tex, "Non-Color")
        if img:
            tex = nodes.new("ShaderNodeTexImage")
            tex.image = img
            tex.location = (-200, -340)
            links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
            nmap = nodes.new("ShaderNodeNormalMap")
            nmap.location = (20, -340)
            nmap.inputs["Strength"].default_value = normal_strength
            links.new(tex.outputs["Color"], nmap.inputs["Color"])
            links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


def get_materials() -> dict[str, bpy.types.Material]:
    """Return the complete shared architectural PBR material library (unified Catalan stone palette + micro-normals!)."""
    return {
        # Unified Montjuïc Catalan Sandstone Palette (fixes dark charcoal towers & abrupt stone seams!)
        "sandstone_warm": make_pbr_material(
            "Mat_SandstoneWarm",
            albedo_tex="sandstone_warm_albedo.png",
            normal_tex="sandstone_warm_normal.png",
            rough_tex="sandstone_warm_roughness.png",
            normal_strength=1.10,
            target_mean_rgb=(0.68, 0.58, 0.45),
        ),
        "nativity_stone": make_pbr_material(
            "Mat_NativityStone",
            albedo_tex="nativity_stone_albedo.png",
            normal_tex="nativity_stone_normal.png",
            rough_tex="nativity_stone_roughness.png",
            normal_strength=1.35,
            target_mean_rgb=(0.59, 0.49, 0.37),
        ),
        "passion_stone": make_pbr_material(
            "Mat_PassionStone",
            albedo_tex="passion_stone_albedo.png",
            normal_tex="passion_stone_normal.png",
            rough_tex="passion_stone_roughness.png",
            normal_strength=1.00,
            target_mean_rgb=(0.73, 0.68, 0.60),
        ),
        "vault_stone": make_pbr_material(
            "Mat_VaultStone",
            albedo_tex="vault_stone_albedo.png",
            normal_tex="vault_stone_normal.png",
            rough_tex="vault_stone_roughness.png",
            normal_strength=0.70,
            target_mean_rgb=(0.76, 0.70, 0.60),
            double_sided=True,
        ),
        "crypt_stone": make_pbr_material(
            "Mat_CryptStone",
            albedo_tex="crypt_stone_albedo.png",
            normal_tex="crypt_stone_normal.png",
            rough_tex="crypt_stone_roughness.png",
            normal_strength=1.15,
            target_mean_rgb=(0.56, 0.49, 0.40),
            double_sided=True,
        ),
        # Honed Mineral Structural Columns (natural satin stone polish — ZERO lacquered plastic sheen!)
        "porphyry_red": make_pbr_material(
            "Mat_PorphyryRed",
            albedo_tex="porphyry_red_albedo.png",
            normal_tex="porphyry_red_normal.png",
            rough_tex="porphyry_red_roughness.png",
            normal_strength=0.65,
            coat_weight=0.18,
            coat_roughness=0.34,
        ),
        "basalt_dark": make_pbr_material(
            "Mat_BasaltDark",
            albedo_tex="basalt_dark_albedo.png",
            normal_tex="basalt_dark_normal.png",
            rough_tex="basalt_dark_roughness.png",
            normal_strength=0.70,
            coat_weight=0.10,
            coat_roughness=0.42,
        ),
        "granite_grey": make_pbr_material(
            "Mat_GraniteGrey",
            albedo_tex="granite_grey_albedo.png",
            normal_tex="granite_grey_normal.png",
            rough_tex="granite_grey_roughness.png",
            normal_strength=0.72,
            coat_weight=0.08,
            coat_roughness=0.45,
        ),
        "floor_marble": make_pbr_material(
            "Mat_FloorMarble",
            albedo_tex="floor_marble_albedo.png",
            normal_tex="floor_marble_normal.png",
            rough_tex="floor_marble_roughness.png",
            normal_strength=0.50,
            coat_weight=0.34,
            coat_roughness=0.26,
        ),
        "trencadis": make_pbr_material(
            "Mat_Trencadis",
            albedo_tex="trencadis_albedo.png",
            normal_tex="trencadis_normal.png",
            rough_tex="trencadis_roughness.png",
            normal_strength=1.0,
            coat_weight=0.65,
            coat_roughness=0.12,
        ),
        "gold_accent": make_pbr_material(
            "Mat_GoldAccent",
            base_color=(0.86, 0.67, 0.25, 1.0),
            normal_tex="metal_micro_normal.png",
            rough_tex="metal_micro_roughness.png",
            roughness=0.28,
            metallic=0.88,
            normal_strength=0.45,
        ),
        "bronze_door": make_pbr_material(
            "Mat_BronzeDoor",
            albedo_tex="bronze_door_albedo.png",
            normal_tex="bronze_door_normal.png",
            rough_tex="bronze_door_roughness.png",
            metallic=0.76,
            normal_strength=1.15,
        ),
        "wood_pew": make_pbr_material(
            "Mat_WoodPew",
            albedo_tex="wood_oak_albedo.png",
            normal_tex="wood_oak_normal.png",
            rough_tex="wood_oak_roughness.png",
            normal_strength=0.75,
        ),
        "carpet_crimson": make_pbr_material(
            "Mat_CarpetCrimson",
            albedo_tex="carpet_crimson_albedo.png",
            normal_tex="carpet_crimson_normal.png",
            rough_tex="carpet_crimson_roughness.png",
            normal_strength=0.7,
        ),
        "glass_case": make_pbr_material(
            "Mat_GlassCase",
            base_color=(0.84, 0.92, 0.95, 1.0),
            roughness=0.08,
            metallic=0.12,
            alpha=0.24,
            double_sided=True,
        ),
        "kiosk_green": make_pbr_material(
            "Mat_KioskGreen",
            base_color=(0.11, 0.24, 0.18, 1.0),
            normal_tex="metal_micro_normal.png",
            roughness=0.40,
            metallic=0.52,
            normal_strength=0.35,
        ),
        "road_white": make_pbr_material(
            "Mat_RoadWhite",
            base_color=(0.86, 0.85, 0.82, 1.0),
            roughness=0.82,
        ),
        "white_marble": make_pbr_material(
            "Mat_WhiteMarble",
            albedo_tex="white_marble_albedo.png",
            normal_tex="white_marble_normal.png",
            rough_tex="white_marble_roughness.png",
            normal_strength=0.65,
        ),
        "luminous_star": make_pbr_material(
            "Mat_LuminousStar",
            base_color=(1.0, 0.96, 0.85, 1.0),
            roughness=0.14,
            metallic=0.2,
            emission_color=(1.0, 0.94, 0.78, 1.0),
            emission_strength=2.2,
        ),
        "luminous_cross": make_pbr_material(
            "Mat_LuminousCross",
            base_color=(0.98, 0.97, 0.94, 1.0),
            roughness=0.16,
            metallic=0.25,
            emission_color=(1.0, 0.96, 0.88, 1.0),
            emission_strength=1.6,
        ),
        "stained_glass_east": make_pbr_material(
            "Mat_StainedGlassEast",
            albedo_tex="stained_glass_east.png",
            normal_tex="stained_glass_normal.png",
            roughness=0.14,
            normal_strength=0.85,
            emission_strength=1.25,
            double_sided=True,
        ),
        "stained_glass_west": make_pbr_material(
            "Mat_StainedGlassWest",
            albedo_tex="stained_glass_west.png",
            normal_tex="stained_glass_normal.png",
            roughness=0.14,
            normal_strength=0.85,
            emission_strength=1.25,
            double_sided=True,
        ),
        "stained_glass_apse": make_pbr_material(
            "Mat_StainedGlassApse",
            albedo_tex="stained_glass_apse.png",
            normal_tex="stained_glass_normal.png",
            roughness=0.14,
            normal_strength=0.85,
            emission_strength=1.15,
            double_sided=True,
        ),
        "cypress_green": make_pbr_material(
            "Mat_CypressGreen",
            albedo_tex="foliage_canopy_albedo.png",
            normal_tex="foliage_canopy_normal.png",
            rough_tex="foliage_canopy_roughness.png",
            normal_strength=1.30,
            target_mean_rgb=(0.14, 0.27, 0.14),
        ),
        "foliage_park": make_pbr_material(
            "Mat_FoliagePark",
            albedo_tex="foliage_canopy_albedo.png",
            normal_tex="foliage_canopy_normal.png",
            rough_tex="foliage_canopy_roughness.png",
            normal_strength=1.25,
            target_mean_rgb=(0.20, 0.34, 0.15),
        ),
        "foliage_cypress": make_pbr_material(
            "Mat_FoliageCypress",
            albedo_tex="foliage_canopy_albedo.png",
            normal_tex="foliage_canopy_normal.png",
            rough_tex="foliage_canopy_roughness.png",
            normal_strength=1.35,
            target_mean_rgb=(0.12, 0.23, 0.13),
        ),
        "tree_bark": make_pbr_material(
            "Mat_TreeBark",
            albedo_tex="bark_platanus_albedo.png",
            normal_tex="bark_platanus_normal.png",
            rough_tex="bark_platanus_roughness.png",
            normal_strength=1.15,
        ),
        "panot_paving": make_pbr_material(
            "Mat_PanotPaving",
            albedo_tex="panot_albedo.png",
            normal_tex="panot_normal.png",
            rough_tex="panot_roughness.png",
            normal_strength=0.95,
        ),
        "asphalt": make_pbr_material(
            "Mat_Asphalt",
            albedo_tex="asphalt_real_albedo.png",
            normal_tex="asphalt_real_normal.png",
            rough_tex="asphalt_real_roughness.png",
            normal_strength=0.9,
        ),
        "grass_park": make_pbr_material(
            "Mat_GrassPark",
            albedo_tex="grass_real_albedo.png",
            normal_tex="grass_real_normal.png",
            rough_tex="grass_real_roughness.png",
            normal_strength=0.85,
        ),
        "eixample_facade": make_pbr_material(
            "Mat_EixampleFacade",
            albedo_tex="eixample_facade_albedo.png",
            normal_tex="eixample_facade_normal.png",
            rough_tex="eixample_facade_roughness.png",
            normal_strength=0.85,
        ),
        "eixample_facade_terra": make_pbr_material(
            "Mat_EixampleFacadeTerra",
            albedo_tex="eixample_terracotta_albedo.png",
            normal_tex="eixample_terracotta_normal.png",
            rough_tex="eixample_terracotta_roughness.png",
            normal_strength=0.85,
        ),
        "eixample_facade_cream": make_pbr_material(
            "Mat_EixampleFacadeCream",
            albedo_tex="eixample_cream_albedo.png",
            normal_tex="eixample_cream_normal.png",
            rough_tex="eixample_cream_roughness.png",
            normal_strength=0.85,
        ),
        "eixample_terracotta": make_pbr_material(
            "Mat_EixampleTerracotta",
            albedo_tex="terracotta_albedo.png",
            normal_tex="terracotta_normal.png",
            rough_tex="terracotta_roughness.png",
            normal_strength=1.10,
        ),
        "horizon_hills": make_pbr_material(
            "Mat_HorizonHills",
            base_color=(0.30, 0.36, 0.31, 1.0),
            roughness=0.95,
        ),
        "mediterranean_sea": make_pbr_material(
            "Mat_MediterraneanSea",
            base_color=(0.07, 0.25, 0.42, 1.0),
            roughness=0.22,
            metallic=0.05,
        ),
        "iron_dark": make_pbr_material(
            "Mat_IronDark",
            base_color=(0.13, 0.15, 0.16, 1.0),
            normal_tex="metal_micro_normal.png",
            roughness=0.44,
            metallic=0.72,
            normal_strength=0.45,
        ),
        "candle_glow": make_pbr_material(
            "Mat_CandleGlow",
            base_color=(1.0, 0.85, 0.45, 1.0),
            emission_color=(1.0, 0.72, 0.25, 1.0),
            emission_strength=3.6,
            roughness=0.3,
        ),
    }


def apply_box_uv(bm: bmesh.types.BMesh, scale: float = 0.18) -> None:
    """Fast cubic/triplanar UV projection so procedural meshes have crisp world-scale UVs."""
    uv_layer = bm.loops.layers.uv.verify()
    bm.faces.ensure_lookup_table()
    for face in bm.faces:
        n = face.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        for loop in face.loops:
            co = loop.vert.co
            if az >= ax and az >= ay:
                u, v = co.x * scale, co.y * scale
            elif ax >= ay and ax >= az:
                u, v = co.y * scale, co.z * scale
            else:
                u, v = co.x * scale, co.z * scale
            loop[uv_layer].uv = (u, v)


# Precomputed Fibonacci hemisphere directions for fast C-speed BVH raycast Ambient Occlusion
_HEMI_DIRS: list[Vector] = []
_GOLD_ANG = math.pi * (3.0 - math.sqrt(5.0))
for _i in range(16):
    _y = 0.14 + 0.84 * (_i / 15.0)
    _r = math.sqrt(max(0.0, 1.0 - _y * _y))
    _th = _GOLD_ANG * _i
    _HEMI_DIRS.append(Vector((math.cos(_th) * _r, math.sin(_th) * _r, _y)).normalized())


def bake_bvh_vertex_ao(bm: bmesh.types.BMesh, max_dist: float = 5.5, min_ao: float = 0.44) -> None:
    """Fast raytraced geometric Ambient Occlusion baked directly into COLOR_0 ('AO_Bake')."""
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    if len(bm.faces) == 0:
        return

    bvh = BVHTree.FromBMesh(bm)
    color_layer = bm.loops.layers.color.get("AO_Bake") or bm.loops.layers.color.new("AO_Bake")

    vert_ao: list[float] = [1.0] * len(bm.verts)
    for idx, v in enumerate(bm.verts):
        n = v.normal
        if n.length_squared < 1e-6:
            continue
        n = n.normalized()
        up = Vector((0.0, 0.0, 1.0)) if abs(n.z) < 0.95 else Vector((1.0, 0.0, 0.0))
        t_x = up.cross(n).normalized()
        t_y = n.cross(t_x).normalized()

        origin = v.co + n * 0.04
        occ = 0.0
        for d in _HEMI_DIRS:
            ray_dir = t_x * d.x + t_y * d.y + n * d.z
            hit_loc, _hit_n, _hit_idx, hit_dist = bvh.ray_cast(origin, ray_dir, max_dist)
            if hit_loc is not None and hit_dist is not None:
                occ += 1.0 - (hit_dist / max_dist) * 0.65
        ao = 1.0 - (occ / len(_HEMI_DIRS)) * (1.0 - min_ao)
        vert_ao[idx] = max(min_ao, min(1.0, ao))

    for face in bm.faces:
        for loop in face.loops:
            a = vert_ao[loop.vert.index]
            # Slight warm crevice tint so shadowed Catalan stone looks rich, never muddy grey
            loop[color_layer] = (a, a * 0.985, a * 0.96, 1.0)


def bevel_sharp_edges(bm: bmesh.types.BMesh, width: float = 0.05, angle_deg: float = 55.0) -> None:
    """Chamfer crisp 90-degree architectural stone edges so they catch realistic sunlight edge highlights!"""
    thresh = math.radians(angle_deg)
    sharp = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) >= thresh and e.calc_length() > width * 2.5]
    if sharp:
        bmesh.ops.bevel(
            bm,
            geom=sharp,
            offset=width,
            offset_type="OFFSET",
            segments=1,
            profile=0.5,
            affect="EDGES",
            clamp_overlap=True,
        )


def apply_organic_stone_displacement(bm: bmesh.types.BMesh, amp: float = 0.16, min_z: float = 2.0) -> None:
    """Subdivide and organically sculpt Nativity Facade masonry into Gaudí's drip-stone / botanical relief!"""
    # Subdivide long structural edges so organic carving has real 3D silhouette variation
    long_edges = [e for e in bm.edges if e.calc_length() > 1.35]
    if long_edges:
        bmesh.ops.subdivide_edges(bm, edges=long_edges, cuts=1, use_grid_fill=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    for v in bm.verts:
        if v.co.z < min_z:
            continue
        p = v.co
        # Multi-frequency deterministic organic drip-stone relief wave along vertex normal
        n1 = math.sin(p.x * 1.15 + p.y * 0.95) * math.cos(p.z * 0.72 + p.y * 1.3)
        n2 = math.sin(p.y * 2.7 + p.z * 1.9) * math.cos(p.x * 2.1 - p.z * 1.4) * 0.45
        # Keep steps/floor level flat, push relief outward on sculpted facade face (+X)
        mask = min(1.0, (p.z - min_z) / 3.0)
        disp = (n1 + n2) * amp * mask
        v.co += v.normal * disp


def finalize_bmesh_object(
    bm: bmesh.types.BMesh,
    name: str,
    mat: bpy.types.Material,
    smooth: bool = False,
    uv_scale: float = 0.18,
    auto_uv: bool = True,
    bake_ao: bool = True,
    ao_dist: float = 5.5,
) -> bpy.types.Object:
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    if auto_uv:
        apply_box_uv(bm, scale=uv_scale)
    if bake_ao and len(bm.verts) <= 45000:
        bake_bvh_vertex_ao(bm, max_dist=ao_dist)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    if smooth and len(mesh.polygons) > 0:
        mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def add_gaudi_window_tracery(
    bm: bmesh.types.BMesh,
    center: tuple[float, float, float],
    width: float,
    height: float,
    facing: str = "X",
    rot_z: float | None = None,
) -> None:
    """True 3D Gaudí stone mullions + stacked circular/elliptical rose tracery framing a stained-glass bay."""
    cx, cy, cz = center
    if rot_z is not None:
        u_dir = Vector((math.cos(rot_z), math.sin(rot_z), 0.0))
        n_dir = Vector((-math.sin(rot_z), math.cos(rot_z), 0.0))
    elif facing == "X":
        u_dir = Vector((0.0, 1.0, 0.0))
        n_dir = Vector((1.0, 0.0, 0.0))
    else:
        u_dir = Vector((1.0, 0.0, 0.0))
        n_dir = Vector((0.0, 1.0, 0.0))

    c_vec = Vector((cx, cy, cz))
    half_h = height * 0.48
    # Two slender vertical stone mullions dividing the lancet into 3 sub-lights
    for frac in (-0.17, 0.17):
        base = c_vec + u_dir * (width * frac)
        add_cylinder(bm, base - Vector((0, 0, half_h)), base + Vector((0, 0, half_h)), 0.14, 0.14, segments=6)

    # Stacked 3D circular/elliptical rose rings (Gaudí's hyperboloid window tracery!)
    num_rings = 2 if height < 11.5 else 3
    ring_r = min(width * 0.34, height / (num_rings * 2.45))
    for ri in range(num_rings):
        tz = -0.30 + (0.62 * ri / max(1, num_rings - 1)) if num_rings > 1 else 0.18
        rc = c_vec + Vector((0.0, 0.0, tz * height))
        segs = 12
        for s in range(segs):
            a0 = 2.0 * math.pi * s / segs
            a1 = 2.0 * math.pi * (s + 1) / segs
            p0 = rc + u_dir * (ring_r * math.cos(a0)) + Vector((0, 0, ring_r * 1.18 * math.sin(a0)))
            p1 = rc + u_dir * (ring_r * math.cos(a1)) + Vector((0, 0, ring_r * 1.18 * math.sin(a1)))
            add_cylinder(bm, p0, p1, 0.13, 0.13, segments=6, cap=False)
    # Transom stone bars crossing between rings
    for tz in (-0.25, 0.25):
        p0 = c_vec - u_dir * (width * 0.48) + Vector((0, 0, tz * height))
        p1 = c_vec + u_dir * (width * 0.48) + Vector((0, 0, tz * height))
        add_cylinder(bm, p0, p1, 0.12, 0.12, segments=6)


def add_box(
    bm: bmesh.types.BMesh,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    rot_euler: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> None:
    mat = Matrix.Translation(center)
    if rot_euler != (0.0, 0.0, 0.0):
        mat = mat @ Matrix.Rotation(rot_euler[2], 4, "Z") @ Matrix.Rotation(rot_euler[1], 4, "Y") @ Matrix.Rotation(rot_euler[0], 4, "X")
    mat = mat @ Matrix.Diagonal((size[0], size[1], size[2], 1.0))
    bmesh.ops.create_cube(bm, size=1.0, matrix=mat)


def add_cylinder(
    bm: bmesh.types.BMesh,
    p0: Vector,
    p1: Vector,
    r0: float,
    r1: float,
    segments: int = 12,
    cap: bool = True,
) -> None:
    """Add a tapered cylinder/strut from world point p0 to p1."""
    vec = p1 - p0
    length = vec.length
    if length < 1e-5:
        return
    z_axis = vec.normalized()
    up = Vector((0.0, 0.0, 1.0)) if abs(z_axis.z) < 0.99 else Vector((1.0, 0.0, 0.0))
    x_axis = up.cross(z_axis).normalized()
    y_axis = z_axis.cross(x_axis).normalized()

    ring0 = []
    ring1 = []
    for i in range(segments):
        ang = 2.0 * math.pi * i / segments
        ca, sa = math.cos(ang), math.sin(ang)
        d = x_axis * ca + y_axis * sa
        ring0.append(bm.verts.new(p0 + d * r0))
        ring1.append(bm.verts.new(p1 + d * r1))

    for i in range(segments):
        ni = (i + 1) % segments
        bm.faces.new((ring0[i], ring0[ni], ring1[ni], ring1[i]))
    if cap:
        bm.faces.new(list(reversed(ring0)))
        bm.faces.new(ring1)


def _polygon_star_radius(theta: float, sides: int, flute_depth: float) -> float:
    """Radius of a fluted regular polygon at angle theta."""
    sector = 2.0 * math.pi / sides
    local = ((theta % sector) / sector) - 0.5
    # Parabolic flute ridge for Gaudí's double-twisted intersections
    return 1.0 - flute_depth * (1.0 - 4.0 * local * local)


def build_gaudi_column_bmesh(
    bm: bmesh.types.BMesh,
    base_z: float,
    knot_z: float,
    radius_base: float,
    sides: int = 8,
    rings: int = 26,
    radial_segs: int = 40,
) -> None:
    """Generate a genuine Gaudí double-twisted column shaft (counter-rotating helical flutes)."""
    height = knot_z - base_z
    twist_total = math.pi / sides * 2.0  # Counter-rotating intersection pitch
    prev_ring = None

    # Base plinth
    add_cylinder(
        bm,
        Vector((0.0, 0.0, base_z)),
        Vector((0.0, 0.0, base_z + 0.9)),
        radius_base * 1.24,
        radius_base * 1.08,
        segments=sides * 2,
        cap=True,
    )

    for r_i in range(rings + 1):
        t = r_i / rings
        z = base_z + 0.85 + t * (height - 0.85)
        # Subtle entasis taper toward ellipsoid capital
        r_taper = radius_base * (1.04 - 0.24 * t)
        # Flute morphing: crisp star polygon at base -> doubled -> smooth circle near top
        flute_amp = 0.14 * (1.0 - 0.82 * (t ** 1.6))
        ring = []
        for s_i in range(radial_segs):
            ang = 2.0 * math.pi * s_i / radial_segs
            r_cw = _polygon_star_radius(ang + twist_total * t, sides, flute_amp)
            r_ccw = _polygon_star_radius(ang - twist_total * t, sides, flute_amp)
            # True Gaudí boolean intersection approximation of CW + CCW twisted polygons
            r_final = r_taper * max(r_cw, r_ccw)
            ring.append(bm.verts.new((r_final * math.cos(ang), r_final * math.sin(ang), z)))
        if prev_ring is not None:
            for s_i in range(radial_segs):
                ns = (s_i + 1) % radial_segs
                bm.faces.new((prev_ring[s_i], prev_ring[ns], ring[ns], ring[s_i]))
        prev_ring = ring

    # Ellipsoid capital knot
    knot_h = radius_base * 1.35
    knot_r = radius_base * 1.15
    k_rings = 8
    k_segs = 20
    prev_k = None
    for ri in range(k_rings + 1):
        phi = -math.pi * 0.48 + math.pi * 0.96 * (ri / k_rings)
        rr = knot_r * math.cos(phi)
        zz = knot_z + knot_h * 0.55 * math.sin(phi)
        ring = [bm.verts.new((rr * math.cos(2 * math.pi * si / k_segs), rr * math.sin(2 * math.pi * si / k_segs), zz)) for si in range(k_segs)]
        if prev_k is not None:
            for si in range(k_segs):
                ns = (si + 1) % k_segs
                bm.faces.new((prev_k[si], prev_k[ns], ring[ns], ring[si]))
        prev_k = ring


def add_branching_canopy(
    bm: bmesh.types.BMesh,
    origin_xy: tuple[float, float],
    knot_z: float,
    vault_z: float,
    spread_radius: float,
    branch_count: int,
    branch_r_base: float,
    angle_offset: float = 0.0,
) -> None:
    """Add Gaudí's tree-like inclined column branches radiating from the ellipsoid knot to the vaults."""
    ox, oy = origin_xy
    p0 = Vector((ox, oy, knot_z + 0.4))
    for i in range(branch_count):
        ang = angle_offset + 2.0 * math.pi * i / branch_count
        p1 = Vector((ox + spread_radius * math.cos(ang), oy + spread_radius * math.sin(ang), vault_z - 0.6))
        add_cylinder(bm, p0, p1, branch_r_base, branch_r_base * 0.62, segments=10, cap=True)
        # Capital floral rosette pad where branch meets vault
        add_cylinder(
            bm,
            p1 - Vector((0.0, 0.0, 0.3)),
            p1 + Vector((0.0, 0.0, 0.55)),
            branch_r_base * 0.72,
            branch_r_base * 1.25,
            segments=12,
            cap=True,
        )


def create_hyperboloid_vault_bay(
    bm_vault: bmesh.types.BMesh,
    bm_gold: bmesh.types.BMesh,
    cx: float,
    cy: float,
    z_top: float,
    span_x: float,
    span_y: float,
    depth: float = 3.2,
    oculus_r: float = 1.15,
    segs: int = 20,
    rings: int = 6,
) -> None:
    """Sculpted Gaudí hyperboloid vault rosette inside a rectangular ceiling bay."""
    outer_rx = span_x * 0.48
    outer_ry = span_y * 0.48
    prev_ring = None

    for ri in range(rings + 1):
        t = ri / rings  # 0 = top oculus, 1 = outer perimeter
        # Hyperbolic curve profile: steep near oculus, flaring smoothly outward
        h_frac = math.sqrt(t)
        rx = oculus_r + (outer_rx - oculus_r) * h_frac
        ry = oculus_r + (outer_ry - oculus_r) * h_frac
        z = z_top - depth * (t ** 1.35)
        ring = []
        for si in range(segs):
            ang = 2.0 * math.pi * si / segs
            # Blend from circle at oculus to rounded-square at outer bay edge
            ca, sa = math.cos(ang), math.sin(ang)
            sq_scale = 1.0 / max(abs(ca), abs(sa), 1e-4)
            blend = (t ** 2.0) * 0.45
            scale = 1.0 + blend * (min(sq_scale, 1.38) - 1.0)
            ring.append(bm_vault.verts.new((cx + rx * ca * scale, cy + ry * sa * scale, z)))
        if prev_ring is not None:
            for si in range(segs):
                ns = (si + 1) % segs
                # Face normal pointing downward into the nave
                bm_vault.faces.new((prev_ring[si], ring[si], ring[ns], prev_ring[ns]))
        prev_ring = ring

    # Outer bay ceiling slab collar filling the corners between hyperboloids
    hw, hh = span_x * 0.5, span_y * 0.5
    z_rim = z_top - depth
    corners = [
        bm_vault.verts.new((cx - hw, cy - hh, z_rim)),
        bm_vault.verts.new((cx + hw, cy - hh, z_rim)),
        bm_vault.verts.new((cx + hw, cy + hh, z_rim)),
        bm_vault.verts.new((cx - hw, cy + hh, z_rim)),
    ]
    # Add decorative ribs radiating from oculus
    for i in range(8):
        ang = math.pi * 0.25 * i
        p0 = Vector((cx + oculus_r * math.cos(ang), cy + oculus_r * math.sin(ang), z_top - 0.15))
        p1 = Vector((cx + outer_rx * 0.95 * math.cos(ang), cy + outer_ry * 0.95 * math.sin(ang), z_rim + 0.1))
        add_cylinder(bm_vault, p0, p1, 0.12, 0.16, segments=6, cap=False)

    # Corner pendentive fill triangles
    for ci, corner in enumerate(corners):
        # Connect each corner to nearby outer ring vertices
        c_ang = math.atan2(corner.co.y - cy, corner.co.x - cx)
        best_idx = min(
            range(segs),
            key=lambda idx: abs(math.atan2(prev_ring[idx].co.y - cy, prev_ring[idx].co.x - cx) - c_ang),
        )
        i_prev = (best_idx - 1) % segs
        i_next = (best_idx + 1) % segs
        bm_vault.faces.new((corner, prev_ring[best_idx], prev_ring[i_prev]))
        bm_vault.faces.new((corner, prev_ring[i_next], prev_ring[best_idx]))

    # Gilded Venetian mosaic ring around the oculus skylight
    add_cylinder(
        bm_gold,
        Vector((cx, cy, z_top - 0.35)),
        Vector((cx, cy, z_top + 0.08)),
        oculus_r * 1.14,
        oculus_r * 1.04,
        segments=segs,
        cap=False,
    )


def export_glb(filepath: str) -> None:
    """Export current Blender scene to a highly compressed glTF Binary (.glb) with Draco + WebP textures."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=filepath,
        export_format="GLB",
        export_texcoords=True,
        export_normals=True,
        export_tangents=False,
        export_materials="EXPORT",
        export_image_format="WEBP",
        export_image_quality=84,
        export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=6,
        export_apply=True,
        export_yup=True,
    )
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"[Export] {os.path.basename(filepath)} -> {size_mb:.2f} MB (Draco + WebP)")
