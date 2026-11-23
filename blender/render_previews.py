"""Render fixed preview stills of the exported GLBs with Cycles (visual regression / fidelity check).

Imports every public/models/*.glb exactly as the web app ships them, emulates the runtime's
COLOR_0 ambient-occlusion multiply and the Cycles-GI lightmaps (TEXCOORD_1), and renders a
fixed set of camera views (coordinates taken from src/data/teleports.ts, Three.js Y-up
converted to Blender Z-up: (x, y, z)_three -> (x, -z, y)_blender).

Usage:
  blender --background --python blender/render_previews.py -- <out_dir> [--views a,b] [--samples N] [--res WxH]
"""

from __future__ import annotations

import math
import os
import sys
import time

import bpy
from mathutils import Vector

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODEL_DIR = os.path.join(ROOT_DIR, "public", "models")
LM_DIR = os.path.join(ROOT_DIR, "public", "textures", "lightmaps")
HDRI_DAY = os.path.join(ROOT_DIR, "public", "hdri", "day_1k.hdr")

MODULES = ("facades", "towers", "interior", "furnishings", "cloister_crypt", "eixample", "plaza_life")

# Must match LIGHTMAP_BY_MESH in src/scene/SagradaScene.ts
LIGHTMAPS = {
    "Interior_HyperboloidVaults": ("lightmap_vaults.webp", 0.58),
    "Interior_MarbleFloor": ("lightmap_floor.webp", 0.48),
    "Interior_NaveWalls": ("lightmap_walls.webp", 0.52),
    "Crypt_Architecture": ("lightmap_crypt.webp", 0.65),
}

# name: (camera location, look-at target, lens mm, sun (azimuth deg from +X CCW, elevation deg) or None, interior?)
VIEWS = {
    "nativity_spawn": ((103.5, -5.5, 2.35), (31.0, 0.0, 29.0), 24, (20.0, 32.0), False),
    "nativity_portals": ((52.0, -6.0, 2.6), (31.5, 0.0, 14.0), 20, (15.0, 28.0), False),
    "passion_facade": ((-58.0, -5.0, 1.75), (-31.0, 0.0, 24.0), 22, (195.0, 30.0), False),
    "glory_facade": ((0.0, -86.0, 1.75), (0.0, -48.0, 34.0), 22, (-60.0, 45.0), False),
    "tower_cluster_air": ((172.0, -152.0, 114.0), (0.0, 4.0, 74.0), 30, (-35.0, 38.0), False),
    "tower_tops": ((70.0, -55.0, 118.0), (8.0, 2.0, 110.0), 32, (-30.0, 40.0), False),
    "nave_to_apse": ((0.0, -34.0, 2.95), (0.0, 14.0, 21.0), 18, (-30.0, 45.0), True),
    "crossing_up": ((0.0, -6.0, 2.9), (0.0, 0.5, 60.0), 12, (-30.0, 45.0), True),
    "crypt": ((0.0, 14.5, -3.75), (-8.5, 23.5, -4.5), 16, None, True),
}


def parse_args() -> tuple[str, list[str], int, tuple[int, int]]:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    out_dir = os.path.join(ROOT_DIR, "renders")
    views = list(VIEWS.keys())
    samples = 96
    res = (1280, 720)
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--views":
            views = [v for v in argv[i + 1].split(",") if v]
            i += 2
        elif a == "--samples":
            samples = int(argv[i + 1])
            i += 2
        elif a == "--res":
            w, h = argv[i + 1].lower().split("x")
            res = (int(w), int(h))
            i += 2
        else:
            out_dir = a
            i += 1
    return out_dir, views, samples, res


def configure_cycles(samples: int, res: tuple[int, int]) -> None:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    device_ok = False
    for backend in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = backend
            prefs.refresh_devices()
            gpus = [d for d in prefs.devices if d.type == backend]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == backend
                device_ok = True
                print(f"[Preview] Cycles device: {backend} ({', '.join(d.name for d in gpus)})")
                break
        except TypeError:
            continue
    scene.cycles.device = "GPU" if device_ok else "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.02
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 2
    scene.cycles.transparent_max_bounces = 4
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.0


def setup_world(strength: float) -> None:
    world = bpy.context.scene.world or bpy.data.worlds.new("PreviewWorld")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    if os.path.exists(HDRI_DAY):
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(HDRI_DAY, check_existing=True)
        nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    else:
        bg.inputs["Color"].default_value = (0.55, 0.68, 0.9, 1.0)
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


def import_models() -> None:
    for mod in MODULES:
        path = os.path.join(MODEL_DIR, f"{mod}.glb")
        if os.path.exists(path):
            bpy.ops.import_scene.gltf(filepath=path)
    print(f"[Preview] Imported {len(bpy.data.objects)} objects")


def _base_color_source(mat: bpy.types.Material):
    if not mat or not mat.use_nodes:
        return None, None
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        return None, None
    inp = bsdf.inputs["Base Color"]
    return bsdf, (inp.links[0].from_socket if inp.is_linked else None)


def emulate_runtime_shading() -> None:
    """Multiply COLOR_0 into base colour (as three.js vertexColors does) and add lightmaps as emission."""
    ao_attr = "AO_PREVIEW"
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        me = obj.data
        src = me.color_attributes[0] if len(me.color_attributes) else None
        if src is None:
            ca = me.color_attributes.new(ao_attr, "FLOAT_COLOR", "CORNER")
            for d in ca.data:
                d.color = (1.0, 1.0, 1.0, 1.0)
        elif src.name != ao_attr:
            src.name = ao_attr

    done: set[str] = set()
    for mat in bpy.data.materials:
        if mat.name in done:
            continue
        done.add(mat.name)
        bsdf, src = _base_color_source(mat)
        if bsdf is None:
            continue
        nt = mat.node_tree
        # Remove any vertex-colour node the importer may already have wired in
        attr = nt.nodes.new("ShaderNodeVertexColor")
        attr.layer_name = ao_attr
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        if src is not None:
            nt.links.new(src, mix.inputs[6])
        else:
            mix.inputs[6].default_value = bsdf.inputs["Base Color"].default_value
        nt.links.new(attr.outputs["Color"], mix.inputs[7])
        nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])

    for obj_name, (lm_file, intensity) in LIGHTMAPS.items():
        obj = bpy.data.objects.get(obj_name)
        lm_path = os.path.join(LM_DIR, lm_file)
        if obj is None or obj.type != "MESH" or not os.path.exists(lm_path) or len(obj.data.uv_layers) < 2:
            continue
        uv1 = obj.data.uv_layers[1].name
        for slot in obj.material_slots:
            if slot.material is None:
                continue
            mat = slot.material.copy()
            mat.name = f"{slot.material.name}_LM_{obj_name}"
            slot.material = mat
            nt = mat.node_tree
            bsdf, base = _base_color_source(mat)
            if bsdf is None:
                continue
            uvn = nt.nodes.new("ShaderNodeUVMap")
            uvn.uv_map = uv1
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image = bpy.data.images.load(lm_path, check_existing=True)
            tex.image.colorspace_settings.name = "sRGB"
            nt.links.new(uvn.outputs["UV"], tex.inputs["Vector"])
            mul = nt.nodes.new("ShaderNodeMix")
            mul.data_type = "RGBA"
            mul.blend_type = "MULTIPLY"
            mul.inputs["Factor"].default_value = 1.0
            if base is not None:
                nt.links.new(base, mul.inputs[6])
            nt.links.new(tex.outputs["Color"], mul.inputs[7])
            nt.links.new(mul.outputs[2], bsdf.inputs["Emission Color"])
            # three.js: indirectDiffuse += lightMap * intensity * albedo / PI
            bsdf.inputs["Emission Strength"].default_value = intensity / math.pi


def add_point(name: str, loc, color, power: float, radius: float) -> bpy.types.Object:
    ld = bpy.data.lights.new(name, "POINT")
    ld.energy = power
    ld.color = color
    ld.shadow_soft_size = radius
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    bpy.context.collection.objects.link(ob)
    return ob


def setup_lights() -> tuple[bpy.types.Object, list[bpy.types.Object]]:
    sd = bpy.data.lights.new("PreviewSun", "SUN")
    sd.energy = 4.2
    sd.angle = math.radians(0.6)
    sd.color = (1.0, 0.96, 0.9)
    sun = bpy.data.objects.new("PreviewSun", sd)
    bpy.context.collection.objects.link(sun)
    # Rough Blender equivalents of the runtime interior fill lights (LightingSystem.ts)
    fills = [
        add_point("Fill_Nave", (0.0, -16.0, 24.0), (1.0, 0.88, 0.69), 60000, 3.0),
        add_point("Fill_Apse", (0.0, 19.0, 14.5), (0.89, 0.85, 0.78), 30000, 3.0),
        add_point("Fill_Crypt", (-3.0, 21.5, -2.2), (1.0, 0.62, 0.23), 2500, 1.0),
    ]
    return sun, fills


def aim(cam: bpy.types.Object, loc, target) -> None:
    cam.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def main() -> None:
    out_dir, views, samples, res = parse_args()
    os.makedirs(out_dir, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    configure_cycles(samples, res)
    import_models()
    emulate_runtime_shading()
    sun, fills = setup_lights()

    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.clip_start = 0.1
    cam_data.clip_end = 2500.0
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    for name in views:
        if name not in VIEWS:
            print(f"[Preview] Unknown view {name}")
            continue
        loc, target, lens, sun_dir, interior = VIEWS[name]
        t0 = time.time()
        cam_data.lens = lens
        aim(cam, loc, target)
        if sun_dir is None:
            sun.hide_render = True
        else:
            sun.hide_render = False
            az, el = math.radians(sun_dir[0]), math.radians(sun_dir[1])
            to_sun = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))
            sun.rotation_euler = (-to_sun).to_track_quat("-Z", "Y").to_euler()
        for f in fills:
            f.hide_render = not interior
        setup_world(0.35 if interior else 1.0)
        bpy.context.scene.view_settings.exposure = 0.6 if interior else 0.0
        bpy.context.scene.render.filepath = os.path.join(out_dir, f"{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"[Preview] {name} rendered in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
