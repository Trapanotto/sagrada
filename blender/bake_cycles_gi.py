"""Blender Cycles path-traced GI lightmap baker for the interior and the crypt.

For each hero mesh (see LIGHTMAP_BY_MESH in src/scene/SagradaScene.ts) this:
  1. builds a dedicated second UV channel 'UVMap_Light' (exported as glTF TEXCOORD_1): Smart UV
     Project, then small detail islands (tracery, ribs, mouldings) are shrunk so the big walls, vault
     shells and floors get the texels, then everything is re-packed with a safe pixel margin;
  2. bakes DIFFUSE direct+indirect irradiance (no albedo) on the GPU. Light comes from the
     stained-glass panes themselves (their real window artwork acts as coloured area emitters), the
     crossing/apse lanterns and a dim sky, so the coloured light pools sit where the windows are;
  3. denoises with a small edge-aware filter inside each island, normalises all interior maps with
     ONE shared exposure (so floor, walls and vaults match), applies a soft shoulder and stores
     proper sRGB-encoded WebP (the runtime decodes lightmaps as SRGBColorSpace);
  4. re-exports interior.glb / cloister_crypt.glb with TEXCOORD_1 intact.

Run after build_all.py:  blender --background --python blender/bake_cycles_gi.py
"""

from __future__ import annotations

import math
import os
import sys
import time

import bmesh
import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from common import MODEL_DIR, TEX_DIR, export_glb
from layout import BAKE_LIGHTS

LM_DIR = os.path.join(TEX_DIR, "lightmaps")
INTERIOR_BAKE_LIGHTS = ("Bake_Cross", "Bake_NaveTop", "Bake_Apse")
CRYPT_BAKE_LIGHTS = tuple(k for k in BAKE_LIGHTS if k.startswith("Bake_Crypt"))   # centre, tomb, east, stair W/E
CRYPT_LIGHTMAP_RES = 2048   # the crypt surface roughly tripled (handover §4.3)
os.makedirs(LM_DIR, exist_ok=True)

BAKE_SAMPLES = 1024
WEBP_QUALITY = 90
DETAIL_AREA_M2 = 6.0      # connected UV islands smaller than this are 'detail' (tracery, ribs, pads)
MARGIN_PX = 4


def configure_cycles(samples: int) -> str:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    backend_used = "CPU"
    for backend in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = backend
            prefs.refresh_devices()
        except TypeError:
            continue
        gpus = [d for d in prefs.devices if d.type == backend]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == backend
            backend_used = backend
            break
    scene.cycles.device = "GPU" if backend_used != "CPU" else "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.use_denoising = False  # not applied to bakes; we filter in UV space ourselves
    scene.cycles.max_bounces = 6
    scene.cycles.diffuse_bounces = 4
    scene.cycles.glossy_bounces = 1
    scene.cycles.transmission_bounces = 2
    scene.cycles.transparent_max_bounces = 2
    scene.cycles.sample_clamp_indirect = 8.0
    scene.render.bake.margin = MARGIN_PX
    scene.render.bake.margin_type = "EXTEND"
    scene.render.bake.use_clear = True
    print(f"[Cycles GI] Device: {backend_used}, {samples} samples")
    return backend_used


def setup_world_sky(strength: float, color=(0.82, 0.88, 1.0, 1.0)) -> None:
    world = bpy.context.scene.world or bpy.data.worlds.new("BakeWorld")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = color
    bg.inputs["Strength"].default_value = strength
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


def add_bake_point_light(name: str, loc, color, power: float, radius: float = 2.0) -> None:
    ldata = bpy.data.lights.new(name=name, type="POINT")
    ldata.energy = power
    ldata.color = color
    ldata.shadow_soft_size = radius
    lobj = bpy.data.objects.new(name=name, object_data=ldata)
    lobj.location = loc
    bpy.context.collection.objects.link(lobj)


def add_layout_lights(names) -> None:
    for name in names:
        loc, color, power, radius = BAKE_LIGHTS[name]
        add_bake_point_light(name, loc, color, power, radius=radius)


def boost_emitters(substr: str, strength: float) -> list[tuple[bpy.types.Material, float]]:
    """Temporarily turn emissive materials (stained glass, lamps) into bake light sources."""
    saved = []
    for mat in bpy.data.materials:
        if substr not in mat.name or not mat.use_nodes:
            continue
        bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        saved.append((mat, bsdf.inputs["Emission Strength"].default_value))
        bsdf.inputs["Emission Strength"].default_value = strength
    return saved


def restore_emitters(saved) -> None:
    for mat, val in saved:
        bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is not None:
            bsdf.inputs["Emission Strength"].default_value = val


def build_lightmap_uvs(obj: bpy.types.Object, cull_down_faces: bool = False) -> None:
    """Smart-project UVMap_Light; pack only the big surfaces (walls, vault shells, floors) with a pixel
    margin; collapse the thousands of tiny detail islands (tracery tubes, ribs, pads) and never-seen
    faces into one shared 16px patch, so their margins no longer eat most of the atlas."""
    mesh = obj.data
    if len(mesh.uv_layers) == 0:
        mesh.uv_layers.new(name="UVMap")
    uv_light = mesh.uv_layers.get("UVMap_Light") or mesh.uv_layers.new(name="UVMap_Light")
    mesh.uv_layers.active = uv_light

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60.0), island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    # Shrink detail islands (UV-connected components with small world area)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    uvl = bm.loops.layers.uv["UVMap_Light"]
    bm.faces.ensure_lookup_table()
    seen = set()
    detail: set[int] = set()
    shrunk = 0
    for f in bm.faces:
        if f.index in seen:
            continue
        # Flood fill through edges that are UV-continuous in UVMap_Light
        comp = []
        stack = [f]
        seen.add(f.index)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for loop in cur.loops:
                e = loop.edge
                for other in e.link_faces:
                    if other.index in seen:
                        continue
                    # UV-connected if both shared verts map to the same UVs on both faces
                    ol = [l for l in other.loops if l.edge == e]
                    if not ol:
                        continue
                    a0, a1 = loop[uvl].uv, loop.link_loop_next[uvl].uv
                    b0, b1 = ol[0].link_loop_next[uvl].uv, ol[0][uvl].uv
                    if (a0 - b0).length < 1e-5 and (a1 - b1).length < 1e-5:
                        seen.add(other.index)
                        stack.append(other)
        area = sum(c.calc_area() for c in comp)
        down = cull_down_faces and all(c.normal.z < -0.5 for c in comp)
        if area < DETAIL_AREA_M2 or down:
            detail.update(c.index for c in comp)
            shrunk += 1
    # Hide the detail faces (not just deselect them): pack_islands otherwise still reserves atlas room
    # for their islands, which shrinks the big surfaces
    for f in bm.faces:
        hidden = f.index in detail
        f.hide = hidden
        f.select = not hidden
    bm.to_mesh(mesh)
    bm.free()

    # Pack only the big islands
    mesh.uv_layers.active = mesh.uv_layers["UVMap_Light"]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.uv.select_all(action="SELECT")
    res_guess = 2048
    bpy.ops.uv.pack_islands(rotate=True, scale=True, margin_method="FRACTION", margin=(MARGIN_PX + 2) / res_guess, shape_method="CONCAVE")
    bpy.ops.mesh.reveal(select=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    # Shrink the packed layout by 1.5% and drop every detail face into a shared corner patch
    bm = bmesh.new()
    bm.from_mesh(mesh)
    uvl = bm.loops.layers.uv["UVMap_Light"]
    lo, hi = 0.988, 0.998
    # pack_islands may still reserve room for the (deselected) detail islands -> renormalise the big
    # islands' bounding box to fill the atlas (uniform scale, aspect preserved)
    big_uv = [l[uvl].uv for f in bm.faces if f.index not in detail for l in f.loops]
    if big_uv:
        umin = min(u.x for u in big_uv)
        vmin = min(u.y for u in big_uv)
        ext = max(max(u.x for u in big_uv) - umin, max(u.y for u in big_uv) - vmin, 1e-6)
        for f in bm.faces:
            if f.index in detail:
                continue
            for l in f.loops:
                l[uvl].uv.x = (l[uvl].uv.x - umin) / ext
                l[uvl].uv.y = (l[uvl].uv.y - vmin) / ext
    for f in bm.faces:
        if f.index in detail:
            us = [l[uvl].uv.x for l in f.loops]
            vs = [l[uvl].uv.y for l in f.loops]
            u0, v0 = min(us), min(vs)
            span = max(max(us) - u0, max(vs) - v0, 1e-6)
            for l in f.loops:
                l[uvl].uv.x = lo + (l[uvl].uv.x - u0) / span * (hi - lo)
                l[uvl].uv.y = lo + (l[uvl].uv.y - v0) / span * (hi - lo)
        else:
            for l in f.loops:
                l[uvl].uv.x *= 0.985
                l[uvl].uv.y *= 0.985
    for f in bm.faces:
        f.hide = False
        f.select = True
    bm.to_mesh(mesh)
    bm.free()
    # Keep TEXCOORD_0 (tiling PBR UVs) as the active / render UV map
    mesh.uv_layers.active = mesh.uv_layers[0]
    mesh.uv_layers[0].active_render = True
    print(f"[Cycles GI] {obj.name}: UVMap_Light packed ({shrunk} detail islands shrunk)")


def bake_object(obj: bpy.types.Object, res: int) -> np.ndarray:
    """Bake diffuse direct+indirect irradiance into a float RGBA array (alpha = coverage)."""
    t0 = time.time()
    img = bpy.data.images.new(name=f"Bake_{obj.name}", width=res, height=res, alpha=True, float_buffer=True)
    img.colorspace_settings.name = "Linear Rec.709"
    img.generated_color = (0.0, 0.0, 0.0, 0.0)

    temp_nodes = []
    for slot in obj.material_slots:
        mat = slot.material
        if not mat or not mat.use_nodes:
            continue
        nt = mat.node_tree
        for n in nt.nodes:
            n.select = False
        uvn = nt.nodes.new("ShaderNodeUVMap")
        uvn.uv_map = "UVMap_Light"
        tex_node = nt.nodes.new("ShaderNodeTexImage")
        tex_node.image = img
        nt.links.new(uvn.outputs["UV"], tex_node.inputs["Vector"])
        tex_node.select = True
        nt.nodes.active = tex_node
        temp_nodes.append((nt, tex_node, uvn))

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    obj.data.uv_layers.active = obj.data.uv_layers["UVMap_Light"]
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT"}, use_clear=True, margin=MARGIN_PX, uv_layer="UVMap_Light")
    obj.data.uv_layers.active = obj.data.uv_layers[0]

    for nt, node, uvn in temp_nodes:
        nt.nodes.remove(node)
        nt.nodes.remove(uvn)

    arr = np.array(img.pixels[:], dtype=np.float32).reshape((res, res, 4))
    bpy.data.images.remove(img)
    print(f"[Cycles GI] Baked {obj.name} ({res}px) in {time.time() - t0:.1f}s")
    return arr


def denoise(arr: np.ndarray, passes: int = 2) -> np.ndarray:
    """Edge-aware 5x5 cross-bilateral filter restricted to covered texels (never bleeds across islands)."""
    rgb = arr[..., :3].copy()
    cov = (arr[..., 3] > 0.5).astype(np.float32)
    for _ in range(passes):
        lum = rgb.mean(axis=2)
        acc = np.zeros_like(rgb)
        wsum = np.zeros(lum.shape, dtype=np.float32)
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                sh = np.roll(np.roll(rgb, dy, axis=0), dx, axis=1)
                shl = np.roll(np.roll(lum, dy, axis=0), dx, axis=1)
                shc = np.roll(np.roll(cov, dy, axis=0), dx, axis=1)
                w_s = math.exp(-(dx * dx + dy * dy) / (2.0 * 1.4 ** 2))
                w_r = np.exp(-((shl - lum) ** 2) / (2.0 * (0.12 * (lum + 0.02)) ** 2))
                w = w_s * w_r * shc
                acc += sh * w[..., None]
                wsum += w
        rgb = np.where(wsum[..., None] > 1e-6, acc / np.maximum(wsum[..., None], 1e-6), rgb)
    out = arr.copy()
    out[..., :3] = rgb
    return out


def encode_and_save(arr: np.ndarray, scale: float, out_filename: str) -> str:
    """Exposure-scale, soft-shoulder, sRGB-encode and write an 8-bit WebP lightmap."""
    res = arr.shape[0]
    rgb = np.maximum(arr[..., :3] * scale, 0.0)
    # Soft shoulder above 0.8 so hot spots near emitters roll off instead of clipping
    knee = 0.8
    over = np.maximum(rgb - knee, 0.0)
    rgb = np.where(rgb > knee, knee + (1.0 - knee) * (1.0 - np.exp(-over / (1.0 - knee))), rgb)
    srgb = np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * np.power(np.clip(rgb, 0.0, 1.0), 1.0 / 2.4) - 0.055)
    rgba = np.ones((res, res, 4), dtype=np.float32)
    rgba[..., :3] = np.clip(srgb, 0.0, 1.0)

    img = bpy.data.images.new(name=f"LM_{out_filename}", width=res, height=res, alpha=False, float_buffer=False)
    img.colorspace_settings.name = "sRGB"
    img.pixels.foreach_set(rgba.ravel())
    out_path = os.path.join(LM_DIR, out_filename)
    # Byte image + Image.save writes the sRGB-encoded buffer verbatim (no view transform applied)
    img.filepath_raw = out_path
    img.file_format = "WEBP"
    try:
        img.save(filepath=out_path, quality=WEBP_QUALITY)
    except TypeError:
        img.save()
    bpy.data.images.remove(img)
    print(f"[Cycles GI] Wrote {out_filename} ({os.path.getsize(out_path) / 1024:.0f} kB)")
    return out_path


def shared_exposure(arrays: list[np.ndarray], target: float = 0.92, pct: float = 99.3) -> float:
    vals = np.concatenate([a[..., :3][a[..., 3] > 0.5].max(axis=1) for a in arrays])
    hi = float(np.percentile(vals, pct)) if vals.size else 1.0
    return target / max(hi, 1e-6)


def remove_lights() -> None:
    for o in list(bpy.data.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)


def bake_interior_lightmaps() -> dict:
    import build_interior

    build_interior.build_interior()
    configure_cycles(BAKE_SAMPLES)
    setup_world_sky(strength=0.35, color=(0.86, 0.90, 1.0, 1.0))

    # The stained-glass panes are the light sources: their actual artwork colours the bounce light.
    saved = boost_emitters("StainedGlass", 26.0)
    saved += boost_emitters("CandleGlow", 6.0)
    # Daylight through the vault oculi / crossing lantern and a soft apse glow (positions: layout.BAKE_LIGHTS)
    add_layout_lights(INTERIOR_BAKE_LIGHTS)

    targets = (
        ("Interior_HyperboloidVaults", "lightmap_vaults.webp", 2048),
        ("Interior_MarbleFloor", "lightmap_floor.webp", 1024),
        ("Interior_NaveWalls", "lightmap_walls.webp", 2048),
    )
    baked = []
    stats = {}
    for obj_name, lm_file, res in targets:
        obj = bpy.data.objects.get(obj_name)
        if obj is None:
            print(f"[Cycles GI] WARNING: {obj_name} missing")
            continue
        build_lightmap_uvs(obj, cull_down_faces=(obj_name == "Interior_MarbleFloor"))
        t0 = time.time()
        arr = denoise(bake_object(obj, res))
        stats[obj_name] = time.time() - t0
        baked.append((lm_file, arr))
    scale = shared_exposure([a for _, a in baked])
    print(f"[Cycles GI] Interior shared exposure scale: {scale:.4f}")
    for lm_file, arr in baked:
        encode_and_save(arr, scale, lm_file)

    restore_emitters(saved)
    remove_lights()
    export_glb(os.path.join(MODEL_DIR, "interior.glb"))
    return stats


def bake_crypt_lightmaps() -> dict:
    import build_cloister_crypt

    build_cloister_crypt.build_cloister_and_crypt()
    configure_cycles(BAKE_SAMPLES)
    setup_world_sky(strength=0.04, color=(0.25, 0.22, 0.18, 1.0))
    saved = boost_emitters("CandleGlow", 40.0)

    # Warm votive candlelight inside the crypt + faint daylight down the two spiral stairs (layout.BAKE_LIGHTS)
    add_layout_lights(CRYPT_BAKE_LIGHTS)

    stats = {}
    obj = bpy.data.objects.get("Crypt_Architecture")
    if obj is not None:
        build_lightmap_uvs(obj)
        t0 = time.time()
        arr = denoise(bake_object(obj, CRYPT_LIGHTMAP_RES))
        stats["Crypt_Architecture"] = time.time() - t0
        encode_and_save(arr, shared_exposure([arr], target=0.95), "lightmap_crypt.webp")

    restore_emitters(saved)
    remove_lights()
    export_glb(os.path.join(MODEL_DIR, "cloister_crypt.glb"))
    return stats


def main() -> None:
    t0 = time.time()
    print("=== Blender Cycles Path-Traced GI Lightmap Baking ===")
    stats = bake_interior_lightmaps()
    stats.update(bake_crypt_lightmaps())
    for k, v in stats.items():
        print(f"[Cycles GI] bake+filter {k}: {v:.1f}s")
    print(f"=== Cycles Lightmap Baking Complete in {time.time() - t0:.1f}s ===")


if __name__ == "__main__":
    main()
