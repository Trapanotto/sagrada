"""Blender Cycles Path-Traced Indirect GI + Ambient Occlusion Lightmap Baker (Stage AAA).

Adds a clean non-overlapping second UV channel ('UVMap_Light' -> glTF TEXCOORD_1)
to hero interior & crypt meshes, bakes denoised Cycles Global Illumination lightmaps
(capturing real stained-glass color bleeding & soft vault/column shadows!), saves
them to public/textures/lightmaps/, and re-exports interior.glb & cloister_crypt.glb
with TEXCOORD_1 intact for Three.js material.lightMap (channel = 1).
"""

from __future__ import annotations

import os
import sys
import time
import bpy

sys.path.insert(0, os.path.dirname(__file__))
from common import MODEL_DIR, TEX_DIR, export_glb

LM_DIR = os.path.join(TEX_DIR, "lightmaps")
os.makedirs(LM_DIR, exist_ok=True)


def configure_cycles(samples: int = 16) -> None:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.04
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 4
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 1
    scene.cycles.transmission_bounces = 1
    scene.cycles.transparent_max_bounces = 2
    scene.render.bake.margin = 8
    scene.render.bake.use_clear = True
    scene.render.bake.use_pass_direct = True
    scene.render.bake.use_pass_indirect = True
    scene.render.bake.use_pass_color = False  # Pure lighting + indirect color-bleed GI + AO!


def setup_world_sky(strength: float = 0.65, color=(0.82, 0.88, 1.0, 1.0)) -> None:
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("BakeWorld")
        bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = color
    bg.inputs["Strength"].default_value = strength
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


def add_bake_point_light(name: str, loc: tuple[float, float, float], color: tuple[float, float, float], power: float, radius: float = 2.0) -> None:
    ldata = bpy.data.lights.new(name=name, type="POINT")
    ldata.energy = power
    ldata.color = color
    ldata.shadow_soft_size = radius
    lobj = bpy.data.objects.new(name=name, object_data=ldata)
    lobj.location = loc
    bpy.context.collection.objects.link(lobj)


def bake_object_lightmap(obj: bpy.types.Object, out_filename: str, res: int = 1024) -> str:
    """Create UVMap_Light (TEXCOORD_1), bake denoised Cycles GI into image, and save as WebP."""
    t0 = time.time()
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    mesh = obj.data
    # Ensure UVMap (TEXCOORD_0) exists first, then create UVMap_Light (TEXCOORD_1)
    if len(mesh.uv_layers) == 0:
        mesh.uv_layers.new(name="UVMap")
    uv_light = mesh.uv_layers.get("UVMap_Light") or mesh.uv_layers.new(name="UVMap_Light")
    uv_light.active = True
    uv_light.active_render = False  # Keep TEXCOORD_0 as primary for textures

    # Generate non-overlapping lightmap UVs
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.012, area_weight=0.0, correct_aspect=True, scale_to_bounds=True)
    bpy.ops.object.mode_set(mode="OBJECT")

    # Create target bake image
    img_name = f"Bake_{out_filename}"
    img = bpy.data.images.new(name=img_name, width=res, height=res, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "sRGB"

    # Temporarily attach an unconnected Image Texture node selected as bake target on every material slot
    temp_nodes = []
    for slot in obj.material_slots:
        mat = slot.material
        if not mat or not mat.use_nodes:
            continue
        nt = mat.node_tree
        for n in nt.nodes:
            n.select = False
        tex_node = nt.nodes.new("ShaderNodeTexImage")
        tex_node.image = img
        tex_node.select = True
        nt.nodes.active = tex_node
        temp_nodes.append((nt, tex_node))

    # Activate UVMap_Light specifically for Cycles baking (re-fetch after Edit->Object mode switch!)
    uv_light_post = obj.data.uv_layers["UVMap_Light"]
    uv_light_post.active = True
    uv_light_post.active_render = True
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT"}, use_clear=True, margin=8)

    # Restore primary UVMap as active render UV so TEXCOORD_0 stays tiled CC0 stone!
    obj.data.uv_layers[0].active = True
    obj.data.uv_layers[0].active_render = True

    # Clean up temporary bake nodes
    for nt, node in temp_nodes:
        nt.nodes.remove(node)

    # Save lightmap as crisp WebP (very small, sRGB tone-safe)
    out_path = os.path.join(LM_DIR, out_filename)
    img.filepath_raw = out_path
    img.file_format = "WEBP"
    bpy.context.scene.render.image_settings.file_format = "WEBP"
    bpy.context.scene.render.image_settings.quality = 88
    img.save_render(out_path) if False else img.save()
    bpy.data.images.remove(img)
    print(f"[Cycles GI] Baked {obj.name} -> {out_filename} ({res}px) in {time.time() - t0:.1f}s")
    return out_path


def bake_interior_lightmaps() -> None:
    """Import freshly built interior.glb, bake Cycles GI lightmaps for Vaults & Floor/Walls, re-export with TEXCOORD_1."""
    import build_interior

    build_interior.build_interior()
    configure_cycles(samples=16)
    setup_world_sky(strength=0.45, color=(0.86, 0.90, 1.0, 1.0))

    # Add realistic balanced stained-glass & sky-oculus light sources for true Cycles Indirect GI & Color Bleeding!
    # East cool sapphire/emerald bounce
    add_bake_point_light("Bake_East1", (17.0, -18.0, 15.0), (0.30, 0.82, 0.92), 18000, radius=4.5)
    add_bake_point_light("Bake_East2", (17.0, -34.0, 15.0), (0.28, 0.86, 0.68), 18000, radius=4.5)
    # West warm amber/gold bounce
    add_bake_point_light("Bake_West1", (-17.0, -18.0, 15.0), (1.0, 0.56, 0.22), 19000, radius=4.5)
    add_bake_point_light("Bake_West2", (-17.0, -34.0, 15.0), (1.0, 0.42, 0.18), 19000, radius=4.5)
    # Crossing skylight oculus & Apse warm glow
    add_bake_point_light("Bake_Cross", (0.0, 0.0, 48.0), (1.0, 0.94, 0.82), 36000, radius=6.0)
    add_bake_point_light("Bake_NaveTop", (0.0, -26.0, 36.0), (1.0, 0.92, 0.78), 26000, radius=5.0)
    add_bake_point_light("Bake_Apse", (0.0, 20.0, 26.0), (0.88, 0.90, 1.0), 24000, radius=5.0)

    for obj_name, lm_file in (
        ("Interior_HyperboloidVaults", "lightmap_vaults.webp"),
        ("Interior_MarbleFloor", "lightmap_floor.webp"),
        ("Interior_NaveWalls", "lightmap_walls.webp"),
    ):
        obj = bpy.data.objects.get(obj_name)
        if obj is not None:
            bake_object_lightmap(obj, lm_file, res=1024)

    # Remove temporary bake lights before re-exporting interior.glb with TEXCOORD_1!
    for o in list(bpy.data.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)

    export_glb(os.path.join(MODEL_DIR, "interior.glb"))


def bake_crypt_lightmaps() -> None:
    """Build cloister_crypt, bake Cycles candlelit GI lightmap for Crypt_Architecture, re-export with TEXCOORD_1."""
    import build_cloister_crypt

    build_cloister_crypt.build_cloister_and_crypt()
    configure_cycles(samples=16)
    setup_world_sky(strength=0.10, color=(0.25, 0.22, 0.18, 1.0))

    # Warm flickering votive candlelight inside the Neo-Gothic Crypt
    add_bake_point_light("Bake_CryptCenter", (0.0, 21.0, -2.2), (1.0, 0.68, 0.32), 4500, radius=1.8)
    add_bake_point_light("Bake_CryptTomb", (-9.5, 23.5, -3.2), (1.0, 0.64, 0.28), 3200, radius=1.2)
    add_bake_point_light("Bake_CryptEast", (8.5, 21.0, -3.0), (1.0, 0.70, 0.36), 2800, radius=1.5)

    crypt_obj = bpy.data.objects.get("Crypt_Architecture")
    if crypt_obj is not None:
        bake_object_lightmap(crypt_obj, "lightmap_crypt.webp", res=1024)

    for o in list(bpy.data.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)

    export_glb(os.path.join(MODEL_DIR, "cloister_crypt.glb"))


def main() -> None:
    t0 = time.time()
    print("=== Blender Cycles Path-Traced GI Lightmap Baking ===")
    bake_interior_lightmaps()
    bake_crypt_lightmaps()
    print(f"=== Cycles Lightmap Baking Complete in {time.time() - t0:.1f}s ===")


if __name__ == "__main__":
    main()
