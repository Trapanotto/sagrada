"""Shared architectural dimensions, PBR material factory, and Gaudí parametric geometry."""

from __future__ import annotations

import json
import math
import os
import re
import struct
import time
import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEX_DIR = os.path.join(ROOT_DIR, "public", "textures")
PBR_TEX_DIR = os.path.join(TEX_DIR, "pbr")
DATA_DIR = os.path.join(ROOT_DIR, "public", "data")
SRC_TEX_DIR = os.path.join(ROOT_DIR, "blender", "textures_src")
CC0_DIR = os.path.join(SRC_TEX_DIR, "cc0")
MODEL_DIR = os.path.join(ROOT_DIR, "public", "models")
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(PBR_TEX_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# ─── Real-world Sagrada Família Metric Grid (1 unit = 1 meter) ───
# Blender Z-up coordinate system:
#   +X = East  (Nativity Facade, Plaça de Gaudí)
#   -X = West  (Passion Facade, Plaça de la Sagrada Família)
#   +Y = North (Apse, Mary Tower, Crypt below)
#   -Y = South (5-aisle Nave, Glory Facade, Grand Staircase)
#   Z = 0.0    Street level outside

# Plan constants come from the master layout (blender/layout.py), the single source of truth
# shared with the web runtime. The old names below are kept as aliases for the builders.
import layout
from layout import (
    GRID, Z_NAVE, Z_ALTAR, Z_GALLERY, Z_CRYPT,
    Z_AISLE_VAULT, Z_NAVE_VAULT, Z_CROSSING_VAULT, Z_APSE_VAULT, ground_z,
)

Z_STREET = 0.0            # legacy flat street datum; the real ground is layout.ground_z(y)
NAVE_SOUTH_Y = layout.GLORY_INNER_Y
TRANSEPT_X = layout.TRANSEPT_HALF_LENGTH
APSE_CENTER_Y = layout.APSE_CENTER[1]
APSE_RADIUS = layout.APSE_CHAPEL_BACK_R


def reset_scene() -> None:
    """Clear the Blender scene completely."""
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _load_image(
    filename: str,
    colorspace: str = "sRGB",
    target_mean_rgb: tuple[float, float, float] | None = None,
    cache_tag: str = "",
    max_size: int = 0,
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
        # Always recalibrate from the source scan (a cached PNG would silently ignore palette changes)
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
        _cap_size(cal_img, max_size or 1024)
        return cal_img

    cache_key = os.path.basename(path)
    existing = bpy.data.images.get(cache_key)
    if existing is not None:
        return existing
    img = bpy.data.images.load(path)
    img.name = cache_key
    img.colorspace_settings.name = colorspace
    _cap_size(img, max_size if max_size else (512 if colorspace == "Non-Color" and "rough" in stem else 1024))
    return img


def _cap_size(img: bpy.types.Image, max_size: int) -> None:
    """Downscale textures that are larger than they need to be (phone budget): roughness maps and
    ground/bark scans only ever read at low frequency, so 512px is visually identical."""
    w, h = img.size[0], img.size[1]
    if max(w, h) > max_size:
        s = max_size / max(w, h)
        img.scale(max(1, int(w * s)), max(1, int(h * s)))


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
    tex_max: int = 0,
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
        img = _load_image(albedo_tex, "sRGB", target_mean_rgb=target_mean_rgb, cache_tag=name.lower(), max_size=tex_max)
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
        img = _load_image(rough_tex, "Non-Color", max_size=min(tex_max or 512, 512))
        if img:
            tex = nodes.new("ShaderNodeTexImage")
            tex.image = img
            tex.location = (-200, -40)
            links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
            links.new(tex.outputs["Color"], bsdf.inputs["Roughness"])

    if normal_tex:
        img = _load_image(normal_tex, "Non-Color", max_size=tex_max)
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
            # Older 1894-1930 Nativity sandstone: browner & darker than the post-1950s stone
            target_mean_rgb=(0.53, 0.44, 0.34),
        ),
        # Passion (1954-76): pale, smooth cut ashlar. Re-uses the large-sandstone-blocks photoscan
        # recalibrated to the cooler cream-grey of the newer stone (the old crazy-paving scan read
        # as broken floor tiles on the bone columns).
        "passion_stone": make_pbr_material(
            "Mat_PassionStone",
            albedo_tex="sandstone_warm_albedo.png",
            normal_tex="sandstone_warm_normal.png",
            rough_tex="sandstone_warm_roughness.png",
            normal_strength=0.85,
            target_mean_rgb=(0.74, 0.70, 0.63),
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
            tex_max=512,
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
            tex_max=512,
            normal_strength=0.9,
        ),
        "grass_park": make_pbr_material(
            "Mat_GrassPark",
            albedo_tex="grass_real_albedo.png",
            normal_tex="grass_real_normal.png",
            rough_tex="grass_real_roughness.png",
            tex_max=512,
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


def _hash3(ix: int, iy: int, iz: int, seed: int) -> float:
    h = (ix * 374761393 + iy * 668265263 + iz * 2147483647 + seed * 144269504) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def value_noise3(x: float, y: float, z: float, seed: int = 0) -> float:
    """Smooth deterministic 3D value noise in [0, 1] (pure Python, no numpy dependency)."""
    ix, iy, iz = math.floor(x), math.floor(y), math.floor(z)
    fx, fy, fz = x - ix, y - iy, z - iz
    ux, uy, uz = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy), fz * fz * (3 - 2 * fz)
    acc = 0.0
    for dz in (0, 1):
        wz = uz if dz else 1.0 - uz
        for dy in (0, 1):
            wy = uy if dy else 1.0 - uy
            for dx in (0, 1):
                wx = ux if dx else 1.0 - ux
                acc += wx * wy * wz * _hash3(ix + dx, iy + dy, iz + dz, seed)
    return acc


def fbm3(x: float, y: float, z: float, octaves: int = 3, seed: int = 0) -> float:
    amp, tot, norm, f = 0.5, 0.0, 0.0, 1.0
    for o in range(octaves):
        tot += amp * value_noise3(x * f, y * f, z * f, seed + o * 17)
        norm += amp
        amp *= 0.5
        f *= 2.03
    return tot / norm


def add_lathe(
    bm: bmesh.types.BMesh,
    cx: float,
    cy: float,
    profile: list[tuple[float, float]],
    segments: int = 12,
    cap_bottom: bool = False,
    cap_top: bool = False,
    phase: float = 0.0,
    squash: tuple[float, float] = (1.0, 1.0),
) -> list[list[bmesh.types.BMVert]]:
    """Revolve a (z, r) profile around a vertical axis -> smooth turned/lathed solid (bulbs, lanterns, knots)."""
    rings: list[list[bmesh.types.BMVert]] = []
    for z, r in profile:
        rings.append([
            bm.verts.new((
                cx + r * squash[0] * math.cos(phase + 2.0 * math.pi * k / segments),
                cy + r * squash[1] * math.sin(phase + 2.0 * math.pi * k / segments),
                z,
            ))
            for k in range(segments)
        ])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(segments):
            nk = (k + 1) % segments
            bm.faces.new((a[k], a[nk], b[nk], b[k]))
    if cap_bottom and profile[0][1] > 1e-4:
        bm.faces.new(list(reversed(rings[0])))
    if cap_top and profile[-1][1] > 1e-4:
        bm.faces.new(rings[-1])
    return rings


def add_ellipsoid(
    bm: bmesh.types.BMesh,
    center: tuple[float, float, float] | Vector,
    radii: tuple[float, float, float],
    subdivisions: int = 1,
    rot_z: float = 0.0,
    tilt: float = 0.0,
    roll: float = 0.0,
) -> list[bmesh.types.BMVert]:
    """Icosphere-based ellipsoid (heads, buds, doves, knots) with optional yaw / pitch / roll."""
    ret = bmesh.ops.create_icosphere(bm, subdivisions=subdivisions, radius=1.0)
    rot = Matrix.Rotation(rot_z, 3, "Z") @ Matrix.Rotation(tilt, 3, "Y") @ Matrix.Rotation(roll, 3, "X")
    c = Vector(center)
    for v in ret["verts"]:
        v.co = c + rot @ Vector((v.co.x * radii[0], v.co.y * radii[1], v.co.z * radii[2]))
    return ret["verts"]


def apply_soot_weathering(bm: bmesh.types.BMesh, strength: float = 0.5, seed: int = 7) -> None:
    """Darken the baked AO colour layer with vertical rain/soot streaks, crevice grime and a dirty plinth zone.

    Used for the 1894-1930 Nativity stone, which in reality is visibly darker and sootier than the
    pale post-1950s stone. Works purely on COLOR_0 so it costs zero texture memory or shader ALU.
    """
    layer = bm.loops.layers.color.get("AO_Bake")
    if layer is None:
        return
    vert_f: dict[int, float] = {}
    bm.verts.ensure_lookup_table()
    for v in bm.verts:
        p = v.co
        # Vertical streaks: stretched noise (tall in Z) breaks up into drip-like runs
        streak = fbm3(p.x * 0.55 + p.y * 0.55, p.y * 0.35 - p.x * 0.35, p.z * 0.06, octaves=3, seed=seed)
        streak = max(0.0, min(1.0, (streak - 0.38) * 2.4))
        blotch = fbm3(p.x * 0.12, p.y * 0.12, p.z * 0.12, octaves=2, seed=seed + 5)
        up = max(0.0, v.normal.z)  # ledges catch dust & soot
        down = max(0.0, -v.normal.z)  # undersides stay sheltered & dark
        plinth = max(0.0, 1.0 - p.z / 6.0)
        dark = strength * (0.30 * streak + 0.22 * blotch + 0.16 * up + 0.12 * down + 0.10 * plinth)
        vert_f[v.index] = max(0.35, 1.0 - dark)
    for f in bm.faces:
        for loop in f.loops:
            k = vert_f[loop.vert.index]
            r, g, b, a = loop[layer]
            # Soot is slightly cool/grey compared with the warm sandstone underneath
            loop[layer] = (r * k, g * (k * 0.99 + 0.01), b * (k * 0.97 + 0.03), a)


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


def apply_dripping_relief(
    bm: bmesh.types.BMesh,
    amp: float = 0.28,
    min_z: float = 2.2,
    max_edge: float = 1.1,
    max_passes: int = 4,
    seed: int = 31,
) -> None:
    """Gaudí's 'melting' Nativity stone: refine long edges, then displace along the normal with
    vertically stretched multi-octave noise so the surface reads as dripping, organically eroded relief.
    Everything below min_z stays untouched so walkable thresholds & collision near the ground remain clean."""
    for _ in range(max_passes):
        long_edges = [e for e in bm.edges if e.calc_length() > max_edge and max(v.co.z for v in e.verts) > min_z]
        if not long_edges:
            break
        bmesh.ops.subdivide_edges(bm, edges=long_edges, cuts=1, use_grid_fill=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    offsets = []
    for v in bm.verts:
        p = v.co
        if p.z < min_z:
            offsets.append(None)
            continue
        drip = fbm3(p.x * 0.45, p.y * 0.45, p.z * 0.11, octaves=3, seed=seed)  # tall vertical runs
        knob = fbm3(p.x * 1.3, p.y * 1.3, p.z * 1.3, octaves=2, seed=seed + 9)  # pitted small-scale relief
        mask = min(1.0, (p.z - min_z) / 2.5)
        d = ((drip - 0.5) * 1.6 + (knob - 0.5) * 0.7) * amp * mask
        offsets.append(v.normal * d)
    for v, off in zip(bm.verts, offsets):
        if off is not None:
            v.co += off


def finalize_bmesh_object(
    bm: bmesh.types.BMesh,
    name: str,
    mat: bpy.types.Material,
    smooth: bool = False,
    uv_scale: float = 0.18,
    auto_uv: bool = True,
    bake_ao: bool = True,
    ao_dist: float = 5.5,
    weathering: float = 0.0,
    ao_vert_limit: int = 45000,
) -> bpy.types.Object:
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    if auto_uv:
        apply_box_uv(bm, scale=uv_scale)
    if bake_ao and len(bm.verts) <= ao_vert_limit:
        bake_bvh_vertex_ao(bm, max_dist=ao_dist)
        if weathering > 0.0:
            apply_soot_weathering(bm, strength=weathering)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    if smooth and len(mesh.polygons) > 0:
        mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def make_shared_mesh(
    bm: bmesh.types.BMesh,
    name: str,
    mat: bpy.types.Material,
    smooth: bool = True,
    uv_scale: float = 0.3,
    bake_ao: bool = True,
    ao_dist: float = 1.5,
) -> bpy.types.Mesh:
    """Finalize a bmesh into reusable mesh DATA (no object) so repeated ornaments share one glTF mesh
    and are collapsed into a single InstancedMesh by the runtime AutoInstancer."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    apply_box_uv(bm, scale=uv_scale)
    if bake_ao:
        bake_bvh_vertex_ao(bm, max_dist=ao_dist, min_ao=0.6)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    if smooth and len(mesh.polygons):
        mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    mesh.materials.append(mat)
    return mesh


def place_mesh_instance(
    name: str,
    mesh: bpy.types.Mesh,
    loc: tuple[float, float, float] | Vector,
    rot_z: float = 0.0,
    scale: float | tuple[float, float, float] = 1.0,
) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, mesh)
    obj.location = tuple(loc)
    obj.rotation_euler = (0.0, 0.0, rot_z)
    obj.scale = (scale, scale, scale) if isinstance(scale, (int, float)) else scale
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
    """Authentic 3-tier Gaudí Hyperboloid Window Tracery:
    1. Lower twin pointed lancets with slender central mullion
    2. Giant middle elliptical rose wheel with 8 radial stone spokes + inner ring
    3. Upper triple hyperboloid circular oculi framed by a sweeping parabolic arch!
    """
    cx, cy, cz = center
    if rot_z is not None:
        u_dir = Vector((math.cos(rot_z), math.sin(rot_z), 0.0))
    elif facing == "X":
        u_dir = Vector((0.0, 1.0, 0.0))
    else:
        u_dir = Vector((1.0, 0.0, 0.0))

    c_vec = Vector((cx, cy, cz))
    half_h = height * 0.48
    half_w = width * 0.46

    # 1. Lower slender twin lancets (bottom -> mid-transom at -0.10*H)
    z_transom = -0.12 * height
    for frac in (-0.22, 0.0, 0.22):
        base = c_vec + u_dir * (width * frac)
        add_cylinder(bm, base - Vector((0, 0, half_h)), base + Vector((0, 0, z_transom)), 0.12, 0.11, segments=6)
    # Transom bar & twin pointed lancet heads
    add_cylinder(
        bm,
        c_vec - u_dir * half_w + Vector((0, 0, z_transom)),
        c_vec + u_dir * half_w + Vector((0, 0, z_transom)),
        0.13,
        0.13,
        segments=6,
    )
    for side in (-0.24, 0.24):
        p_l = c_vec + u_dir * (width * (side - 0.20)) + Vector((0, 0, z_transom - 0.9))
        p_r = c_vec + u_dir * (width * (side + 0.20)) + Vector((0, 0, z_transom - 0.9))
        p_t = c_vec + u_dir * (width * side) + Vector((0, 0, z_transom))
        add_cylinder(bm, p_l, p_t, 0.11, 0.10, segments=5)
        add_cylinder(bm, p_r, p_t, 0.11, 0.10, segments=5)

    # 2. Iconic Giant Middle Elliptical Stone Rose Wheel with 8 Radial Spokes (center at +0.11*H)
    rose_c = c_vec + Vector((0.0, 0.0, 0.11 * height))
    rx = min(width * 0.36, height * 0.19)
    rz = rx * 1.18
    segs = 14
    for s in range(segs):
        a0 = 2.0 * math.pi * s / segs
        a1 = 2.0 * math.pi * (s + 1) / segs
        p0 = rose_c + u_dir * (rx * math.cos(a0)) + Vector((0, 0, rz * math.sin(a0)))
        p1 = rose_c + u_dir * (rx * math.cos(a1)) + Vector((0, 0, rz * math.sin(a1)))
        add_cylinder(bm, p0, p1, 0.14, 0.14, segments=6, cap=False)
        # Inner jewel boss ring
        if s % 2 == 0:
            a2 = 2.0 * math.pi * (s + 2) / segs
            q0 = rose_c + u_dir * (rx * 0.34 * math.cos(a0)) + Vector((0, 0, rz * 0.34 * math.sin(a0)))
            q1 = rose_c + u_dir * (rx * 0.34 * math.cos(a2)) + Vector((0, 0, rz * 0.34 * math.sin(a2)))
            add_cylinder(bm, q0, q1, 0.10, 0.10, segments=5, cap=False)
    # 8 curved radial spokes inside the rose wheel
    for sp in range(8):
        ang = 2.0 * math.pi * sp / 8.0
        p_in = rose_c + u_dir * (rx * 0.34 * math.cos(ang)) + Vector((0, 0, rz * 0.34 * math.sin(ang)))
        p_out = rose_c + u_dir * (rx * math.cos(ang)) + Vector((0, 0, rz * math.sin(ang)))
        add_cylinder(bm, p_in, p_out, 0.09, 0.10, segments=5, cap=False)

    # 3. Upper Triple Hyperboloid Circular Oculi + Sweeping Parabolic Top Hood Arch
    oc_specs = [
        (0.0, 0.38 * height, min(width * 0.18, height * 0.085)),
        (-0.24 * width, 0.30 * height, min(width * 0.13, height * 0.065)),
        (0.24 * width, 0.30 * height, min(width * 0.13, height * 0.065)),
    ]
    for ou, oz, orad in oc_specs:
        oc_c = c_vec + u_dir * ou + Vector((0.0, 0.0, oz))
        for s in range(8):
            a0 = 2.0 * math.pi * s / 8.0
            a1 = 2.0 * math.pi * (s + 1) / 8.0
            p0 = oc_c + u_dir * (orad * math.cos(a0)) + Vector((0, 0, orad * math.sin(a0)))
            p1 = oc_c + u_dir * (orad * math.cos(a1)) + Vector((0, 0, orad * math.sin(a1)))
            add_cylinder(bm, p0, p1, 0.10, 0.10, segments=5, cap=False)

    # Sweeping outer parabolic stone arch head framing the top of the window
    for s in range(8):
        t0 = -1.0 + 2.0 * (s / 8.0)
        t1 = -1.0 + 2.0 * ((s + 1) / 8.0)
        p0 = c_vec + u_dir * (half_w * t0) + Vector((0, 0, half_h - 0.22 * height * (t0 * t0)))
        p1 = c_vec + u_dir * (half_w * t1) + Vector((0, 0, half_h - 0.22 * height * (t1 * t1)))
        add_cylinder(bm, p0, p1, 0.15, 0.15, segments=6, cap=False)


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


def add_swept_tube(
    bm: bmesh.types.BMesh,
    pts: list[Vector],
    radii: list[float],
    segments: int = 10,
    cap: bool = True,
    ridge: tuple[int, float] = (0, 0.0),
) -> None:
    """Smooth tube swept along a polyline with a per-point radius profile (bones, branches, tendons).
    ridge=(n, depth) adds n longitudinal tendon ridges (Gaudí/Subirachs bone columns)."""
    n_r, depth = ridge
    rings = []
    prev_x = None
    for i, p in enumerate(pts):
        if i == 0:
            tan = (pts[1] - pts[0]).normalized()
        elif i == len(pts) - 1:
            tan = (pts[-1] - pts[-2]).normalized()
        else:
            tan = (pts[i + 1] - pts[i - 1]).normalized()
        if prev_x is None:
            up = Vector((0.0, 0.0, 1.0)) if abs(tan.z) < 0.95 else Vector((1.0, 0.0, 0.0))
            x_axis = up.cross(tan).normalized()
        else:
            x_axis = (prev_x - tan * prev_x.dot(tan)).normalized()  # parallel transport (no twisting)
        y_axis = tan.cross(x_axis).normalized()
        prev_x = x_axis
        ring = []
        for k in range(segments):
            a = 2.0 * math.pi * k / segments
            r = radii[i]
            if n_r:
                r *= 1.0 + depth * max(0.0, math.cos(a * n_r)) ** 3
            ring.append(bm.verts.new(p + (x_axis * math.cos(a) + y_axis * math.sin(a)) * r))
        rings.append(ring)
    for a_r, b_r in zip(rings[:-1], rings[1:]):
        for k in range(segments):
            nk = (k + 1) % segments
            bm.faces.new((a_r[k], a_r[nk], b_r[nk], b_r[k]))
    if cap:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])


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


def add_tree_canopy(
    bm: bmesh.types.BMesh,
    origin_xy: tuple[float, float],
    knot_z: float,
    vault_z: float,
    spread_radius: float,
    branch_count: int,
    branch_r_base: float,
    angle_offset: float = 0.0,
    sub_branches: int = 3,
    split_frac: float = 0.52,
    bm_lamps: bmesh.types.BMesh | None = None,
) -> None:
    """Gaudí's tree column canopy: from the elliptical knot, a few thick inclined branches rise to
    secondary knots and split again into thinner twigs carrying the vault (instead of a flat fan)."""
    ox, oy = origin_xy
    p0 = Vector((ox, oy, knot_z + 0.35))
    rise = vault_z - 0.6 - p0.z
    for i in range(branch_count):
        ang = angle_offset + 2.0 * math.pi * i / branch_count
        ca, sa = math.cos(ang), math.sin(ang)
        pk = Vector((ox + spread_radius * 0.42 * ca, oy + spread_radius * 0.42 * sa, p0.z + rise * split_frac))
        # Swept (multi-ring) tubes: mid-length rings get their own vertex AO instead of inheriting the
        # fully occluded knot/vault ends (which turned whole branches black)
        add_swept_tube(bm, [p0.lerp(pk, f) for f in (0.0, 0.5, 1.0)], [branch_r_base * (1.0 - 0.18 * f) for f in (0.0, 0.5, 1.0)], segments=7)
        # Secondary knot (small elongated ellipsoid, as on the real columns)
        kr = branch_r_base * 1.3
        add_lathe(
            bm, pk.x, pk.y,
            [(pk.z - kr * 1.6, kr * 0.55), (pk.z - kr * 0.7, kr * 0.95), (pk.z + kr * 0.3, kr), (pk.z + kr * 1.2, kr * 0.7), (pk.z + kr * 1.7, kr * 0.4)],
            segments=6, cap_bottom=True, cap_top=True,
        )
        if bm_lamps is not None:
            add_lathe(bm_lamps, pk.x + ca * kr * 0.98, pk.y + sa * kr * 0.98,
                      [(pk.z - 0.12, 0.05), (pk.z, 0.13), (pk.z + 0.12, 0.05)], segments=6, cap_bottom=True, cap_top=True)
        for j in range(sub_branches):
            if sub_branches == 1:
                da = 0.0
            else:
                da = (j / (sub_branches - 1) - 0.5) * 1.15
            a2 = ang + da
            reach = spread_radius * (0.82 + 0.18 * (1.0 - abs(da)))
            p1 = Vector((ox + reach * math.cos(a2), oy + reach * math.sin(a2), vault_z - 0.6))
            q0 = pk + Vector((0, 0, kr * 1.2))
            add_swept_tube(bm, [q0.lerp(p1, f) for f in (0.0, 0.5, 1.0)], [branch_r_base * (0.58 - 0.16 * f) for f in (0.0, 0.5, 1.0)], segments=5)
            # Flared capital pad where the twig meets the vault
            add_cylinder(bm, p1 - Vector((0.0, 0.0, 0.25)), p1 + Vector((0.0, 0.0, 0.5)), branch_r_base * 0.45, branch_r_base * 0.95, segments=6, cap=True)


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


def save_candle_anchors(group_name: str, anchors_blender: list[tuple[float, float, float, float]]) -> None:
    """Persist exact candle flame tip coordinates (converted Blender Z-up -> Three.js Y-up) to public/data/candles.json."""
    candles_path = os.path.join(DATA_DIR, "candles.json")
    data: dict[str, list[list[float]]] = {}
    if os.path.exists(candles_path):
        try:
            with open(candles_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
        except Exception:
            data = {}
    # Blender (x, y, z) -> Three.js (x, z, -y)
    data[group_name] = [
        [round(bx, 4), round(bz, 4), round(-by, 4), round(sc, 3)]
        for bx, by, bz, sc in anchors_blender
    ]
    with open(candles_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[Candles] Saved {len(anchors_blender)} exact wick anchors for '{group_name}' -> public/data/candles.json")


# Low quality tier (phones): the runtime swaps textures/<dir>/ for textures/<dir>_low/ (see
# SagradaScene.loadAllModules), so it downloads, decodes and uploads small maps instead of downscaling
# the full-size ones on the CPU. PBR maps are capped at 512 px (the low tier's maxTextureSize).
LOW_TEX_MAX = 512
LOW_WEBP_QUALITY = 80


def write_low_variant(src_path: str, dst_dir: str, max_size: int, quality: int = LOW_WEBP_QUALITY) -> None:
    """Writes <dst_dir>/<basename> = src_path downscaled to <= max_size (Lanczos), or a byte copy if already small."""
    import OpenImageIO as oiio  # bundled with Blender

    os.makedirs(dst_dir, exist_ok=True)
    dst_path = os.path.join(dst_dir, os.path.basename(src_path))
    buf = oiio.ImageBuf(src_path)
    spec = buf.spec()
    w, h = spec.width, spec.height
    if max(w, h) <= max_size:
        with open(src_path, "rb") as f:
            blob = f.read()
    else:
        s = max_size / max(w, h)
        nw, nh = max(1, round(w * s)), max(1, round(h * s))
        small = oiio.ImageBufAlgo.resize(buf, filtername="lanczos3", roi=oiio.ROI(0, nw, 0, nh, 0, 1, 0, spec.nchannels))
        small.specmod().attribute("compression", f"webp:{quality}")
        tmp_path = dst_path + ".tmp.webp"
        if not small.write(tmp_path):
            raise RuntimeError(f"low variant write failed: {small.geterror()}")
        with open(tmp_path, "rb") as f:
            blob = f.read()
        os.remove(tmp_path)
    if os.path.exists(dst_path):
        with open(dst_path, "rb") as f:
            if f.read() == blob:
                return
    for attempt in range(8):
        try:
            with open(dst_path, "wb") as out_f:
                out_f.write(blob)
            return
        except OSError:
            if attempt == 7:
                raise
            time.sleep(0.5 * (attempt + 1))


def _externalize_glb_textures(filepath: str) -> None:
    """Replace embedded WebP image bufferViews inside a GLB with shared ../textures/pbr/<name>.webp URIs."""
    with open(filepath, "rb") as f:
        raw = f.read()

    if len(raw) < 28 or raw[:4] != b"glTF":
        return

    json_len = struct.unpack_from("<I", raw, 12)[0]
    json_type = raw[16:20]
    if json_type != b"JSON":
        return
    gltf = json.loads(raw[20 : 20 + json_len].decode("utf-8"))

    bin_header_off = 20 + json_len
    if bin_header_off + 8 > len(raw):
        return
    bin_len = struct.unpack_from("<I", raw, bin_header_off)[0]
    bin_data = raw[bin_header_off + 8 : bin_header_off + 8 + bin_len]

    images = gltf.get("images")
    buffer_views = gltf.get("bufferViews")
    if not images or not buffer_views:
        return

    removed_bvs: set[int] = set()
    for idx, im in enumerate(images):
        bv_idx = im.get("bufferView")
        if bv_idx is None:
            continue
        raw_name = im.get("name") or f"tex_{idx}"
        clean_stem = re.sub(r"\.\d+$", "", os.path.splitext(raw_name)[0])
        mime = im.get("mimeType", "image/webp")
        ext = ".webp" if "webp" in mime else (".jpg" if "jpeg" in mime else ".png")
        out_name = clean_stem + ext
        out_path = os.path.join(PBR_TEX_DIR, out_name)

        # Always (re)write so public/textures/pbr is the real output of the current sources
        # (previously stale files were silently kept, making the pipeline non-reproducible).
        bv = buffer_views[bv_idx]
        off = bv.get("byteOffset", 0)
        blen = bv["byteLength"]
        blob = bin_data[off : off + blen]
        same = False
        if os.path.exists(out_path) and os.path.getsize(out_path) == len(blob):
            with open(out_path, "rb") as in_f:
                same = in_f.read() == blob
        if not same:
            # Retry: OneDrive / antivirus can briefly lock freshly written files (EINVAL / EACCES)
            for attempt in range(8):
                try:
                    with open(out_path, "wb") as out_f:
                        out_f.write(blob)
                    break
                except OSError:
                    if attempt == 7:
                        raise
                    time.sleep(0.5 * (attempt + 1))
        write_low_variant(out_path, PBR_TEX_DIR + "_low", LOW_TEX_MAX)

        removed_bvs.add(bv_idx)
        im.pop("bufferView", None)
        im.pop("mimeType", None)
        im["uri"] = f"../textures/pbr/{out_name}"

    if not removed_bvs:
        return

    # Rebuild compact BIN chunk containing ONLY non-image bufferViews (4-byte aligned)
    new_bvs = []
    bv_remap: dict[int, int] = {}
    new_bin_parts: list[bytes] = []
    cursor = 0

    for old_idx, bv in enumerate(buffer_views):
        if old_idx in removed_bvs:
            continue
        off = bv.get("byteOffset", 0)
        blen = bv["byteLength"]
        chunk = bin_data[off : off + blen]
        pad = (4 - (cursor % 4)) % 4
        if pad:
            new_bin_parts.append(b"\x00" * pad)
            cursor += pad
        nbv = dict(bv)
        nbv["byteOffset"] = cursor
        bv_remap[old_idx] = len(new_bvs)
        new_bvs.append(nbv)
        new_bin_parts.append(chunk)
        cursor += blen

    # Pad final BIN chunk to 4-byte boundary
    end_pad = (4 - (cursor % 4)) % 4
    if end_pad:
        new_bin_parts.append(b"\x00" * end_pad)
        cursor += end_pad

    gltf["bufferViews"] = new_bvs
    if gltf.get("buffers"):
        gltf["buffers"][0]["byteLength"] = cursor

    # Remap all remaining bufferView references
    for acc in gltf.get("accessors", []):
        if "bufferView" in acc:
            acc["bufferView"] = bv_remap[acc["bufferView"]]
        sparse = acc.get("sparse")
        if sparse:
            if "indices" in sparse and "bufferView" in sparse["indices"]:
                sparse["indices"]["bufferView"] = bv_remap[sparse["indices"]["bufferView"]]
            if "values" in sparse and "bufferView" in sparse["values"]:
                sparse["values"]["bufferView"] = bv_remap[sparse["values"]["bufferView"]]
    for mesh in gltf.get("meshes", []):
        for prim in mesh.get("primitives", []):
            draco = prim.get("extensions", {}).get("KHR_draco_mesh_compression")
            if draco and "bufferView" in draco:
                draco["bufferView"] = bv_remap[draco["bufferView"]]

    new_json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    j_pad = (4 - (len(new_json_bytes) % 4)) % 4
    if j_pad:
        new_json_bytes += b" " * j_pad

    new_bin_bytes = b"".join(new_bin_parts)
    total_len = 12 + 8 + len(new_json_bytes) + 8 + len(new_bin_bytes)

    out_glb = bytearray()
    out_glb += struct.pack("<4sII", b"glTF", 2, total_len)
    out_glb += struct.pack("<I4s", len(new_json_bytes), b"JSON")
    out_glb += new_json_bytes
    out_glb += struct.pack("<I4s", len(new_bin_bytes), b"BIN\x00")
    out_glb += new_bin_bytes

    with open(filepath, "wb") as f:
        f.write(out_glb)


def export_glb(filepath: str) -> None:
    """Export current Blender scene to a highly compressed glTF Binary (.glb) with Draco + shared external WebP textures."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=filepath,
        export_format="GLB",
        export_texcoords=True,
        export_normals=True,
        export_tangents=False,
        export_materials="EXPORT",
        # Only the baked 'AO_Bake' attribute -> COLOR_0 (Blender 5.x defaults also emit a redundant COLOR_1 copy)
        export_vertex_color="MATERIAL",
        export_all_vertex_colors=False,
        export_active_vertex_color_when_no_material=True,
        export_image_format="WEBP",
        export_image_quality=80,
        export_draco_mesh_compression_enable=True,
        # Level 10 + 8-bit normals and vertex colours (the baked AO is an 8-bit value anyway):
        # ~12 % smaller GLBs than level 6 / 10-bit / 10-bit. Positions (14 bit) and UVs (12 bit) unchanged.
        export_draco_mesh_compression_level=10,
        export_draco_normal_quantization=8,
        export_draco_color_quantization=8,
        export_apply=True,
        export_yup=True,
    )
    _externalize_glb_textures(filepath)
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"[Export] {os.path.basename(filepath)} -> {size_mb:.2f} MB (Draco + shared WebP)")
