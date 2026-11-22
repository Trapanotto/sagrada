"""Generate high-resolution (1024px) weathered procedural PBR textures for Sagrada Família (Stage 2 AAA)."""

from __future__ import annotations

import math
import os
import bpy
import numpy as np

TEX_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "textures_src"))
PUBLIC_TEX_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "public", "textures"))
os.makedirs(TEX_DIR, exist_ok=True)
os.makedirs(PUBLIC_TEX_DIR, exist_ok=True)


def save_rgba_png(name: str, rgba: np.ndarray, colorspace: str = "sRGB") -> str:
    h, w, _ = rgba.shape
    target_dir = PUBLIC_TEX_DIR if name in ("stained_glass_east.png", "stained_glass_west.png") else TEX_DIR
    path = os.path.join(target_dir, name)
    img = bpy.data.images.new(name=name, width=w, height=h, alpha=True, float_buffer=False)
    img.colorspace_settings.name = colorspace
    flipped = np.ascontiguousarray(np.flipud(np.clip(rgba, 0.0, 1.0)), dtype=np.float32)
    img.pixels.foreach_set(flipped.ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    return path


def save_rgb_png(name: str, rgb: np.ndarray, colorspace: str = "sRGB") -> str:
    h, w, _ = rgb.shape
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :3] = np.clip(rgb, 0.0, 1.0)
    return save_rgba_png(name, rgba, colorspace=colorspace)


def save_gray_png(name: str, gray: np.ndarray) -> str:
    rgb = np.repeat(np.clip(gray, 0.0, 1.0)[..., None], 3, axis=2)
    return save_rgb_png(name, rgb, colorspace="Non-Color")


def tileable_fbm(size: int, octaves: int = 5, base_freq: int = 4, seed: int = 42, stretch_y: float = 1.0) -> np.ndarray:
    """Fast tileable periodic FBM with optional vertical anisotropy (for rain weathering streaks)."""
    rng = np.random.default_rng(seed)
    acc = np.zeros((size, size), dtype=np.float32)
    amp = 0.5
    norm = 0.0
    for o in range(octaves):
        freq_x = max(2, int(base_freq * (2 ** o)))
        freq_y = max(2, int(round(freq_x / stretch_y)))
        grid = rng.random((freq_y, freq_x), dtype=np.float32)
        ys = np.linspace(0, freq_y, size, endpoint=False)
        xs = np.linspace(0, freq_x, size, endpoint=False)
        y0 = np.floor(ys).astype(np.int32) % freq_y
        x0 = np.floor(xs).astype(np.int32) % freq_x
        y1 = (y0 + 1) % freq_y
        x1 = (x0 + 1) % freq_x
        fy = (ys - np.floor(ys)).astype(np.float32)
        fx = (xs - np.floor(xs)).astype(np.float32)
        sy = fy * fy * (3.0 - 2.0 * fy)
        sx = fx * fx * (3.0 - 2.0 * fx)
        v00 = grid[np.ix_(y0, x0)]
        v01 = grid[np.ix_(y0, x1)]
        v10 = grid[np.ix_(y1, x0)]
        v11 = grid[np.ix_(y1, x1)]
        top = v00 * (1.0 - sx[None, :]) + v01 * sx[None, :]
        bot = v10 * (1.0 - sx[None, :]) + v11 * sx[None, :]
        val = top * (1.0 - sy[:, None]) + bot * sy[:, None]
        acc += val * amp
        norm += amp
        amp *= 0.5
    return acc / max(norm, 1e-6)


def height_to_normal(height: np.ndarray, strength: float = 2.8) -> np.ndarray:
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * 0.5 * strength
    dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * 0.5 * strength
    nx = -dx
    ny = dy
    nz = np.ones_like(height)
    inv_len = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz + 1e-8)
    return np.stack([nx * inv_len * 0.5 + 0.5, ny * inv_len * 0.5 + 0.5, nz * inv_len * 0.5 + 0.5], axis=-1).astype(np.float32)


def generate_ashlar_stone(
    prefix: str,
    base_rgb: tuple[float, float, float],
    var_rgb: tuple[float, float, float],
    mortar_rgb: tuple[float, float, float],
    rows: int = 8,
    cols: int = 4,
    size: int = 1024,
    rough_base: float = 0.78,
    normal_strength: float = 3.6,
    weathering: float = 0.25,
    chisel_marks: float = 0.0,
    seed: int = 10,
) -> None:
    """High-resolution Catalan ashlar masonry with bevelled stone edges, rain-streak patina & cavity AO."""
    rng = np.random.default_rng(seed)
    n_micro = tileable_fbm(size, octaves=5, base_freq=16, seed=seed)
    n_macro = tileable_fbm(size, octaves=3, base_freq=4, seed=seed + 100)
    n_rain = tileable_fbm(size, octaves=4, base_freq=12, seed=seed + 200, stretch_y=4.5)

    y = np.linspace(0, rows, size, endpoint=False)[:, None]
    x = np.linspace(0, cols, size, endpoint=False)[None, :]
    row_idx = np.floor(y).astype(np.int32)
    x_shifted = (x + (row_idx % 2) * 0.5) % cols
    col_idx = np.floor(x_shifted).astype(np.int32)

    fy = y - np.floor(y)
    fx = x_shifted - np.floor(x_shifted)

    wobble = (n_micro - 0.5) * 0.016
    mw_y = 0.032
    mw_x = 0.020
    dy = np.minimum(fy, 1.0 - fy) + wobble
    dx = np.minimum(fx, 1.0 - fx) + wobble
    edge = np.minimum(dy / mw_y, dx / mw_x)
    stone_mask = np.clip(edge, 0.0, 1.0)
    stone_mask = stone_mask * stone_mask * (3.0 - 2.0 * stone_mask)

    # Subtle chamfered pillow profile across each individual stone block
    bevel = np.clip(np.minimum(dy / 0.14, dx / 0.09), 0.0, 1.0)
    bevel = 0.72 + 0.28 * (bevel * bevel * (3.0 - 2.0 * bevel))

    block_tone = rng.uniform(-1.0, 1.0, size=(rows, cols)).astype(np.float32)
    bt = block_tone[row_idx % rows, col_idx % cols]

    # Rain streaking & top-edge grime patina
    rain_stain = np.clip((n_rain - 0.42) * 1.9, 0.0, 1.0) * weathering
    top_grime = np.exp(-fy * 7.5) * weathering * 0.45

    albedo = np.zeros((size, size, 3), dtype=np.float32)
    for c in range(3):
        stone_c = (
            base_rgb[c]
            + bt * var_rgb[c]
            + (n_macro - 0.5) * 0.085
            + (n_micro - 0.5) * 0.065
        )
        # Apply warm-dark rain patina & subtle edge highlight
        stone_c *= (1.0 - rain_stain * (0.28 if c == 2 else 0.20) - top_grime * 0.35)
        stone_c += (1.0 - bevel) * 0.025
        albedo[..., c] = mortar_rgb[c] * (1.0 - stone_mask) + stone_c * stone_mask

    # Deep mortar cavity AO
    ao = 0.78 + 0.22 * stone_mask
    albedo *= ao[..., None]

    # Optional chiseled horizontal stone-dressing grooves (signature of Passion limestone!)
    chisel = 0.0
    if chisel_marks > 0.0:
        chisel = np.sin(y * math.pi * 16.0 + n_micro * 2.5) * 0.04 * chisel_marks

    height = stone_mask * (bevel * 0.68 + 0.22 * n_micro + 0.10 * n_macro + chisel)
    normal = height_to_normal(height, strength=normal_strength)
    roughness = np.clip(
        rough_base + (1.0 - stone_mask) * 0.18 + rain_stain * 0.12 + (n_micro - 0.5) * 0.14,
        0.18,
        0.98,
    )

    save_rgb_png(f"{prefix}_albedo.png", albedo, colorspace="sRGB")
    save_rgb_png(f"{prefix}_normal.png", normal, colorspace="Non-Color")
    save_gray_png(f"{prefix}_roughness.png", roughness)


def generate_speckled_stone(
    prefix: str,
    base_rgb: tuple[float, float, float],
    speck1_rgb: tuple[float, float, float],
    speck2_rgb: tuple[float, float, float],
    rough_base: float = 0.30,
    size: int = 1024,
    seed: int = 77,
) -> None:
    """High-res polished porphyry / basalt / granite for Gaudí's interior structural columns."""
    n1 = tileable_fbm(size, octaves=5, base_freq=22, seed=seed)
    n2 = tileable_fbm(size, octaves=4, base_freq=44, seed=seed + 31)
    n_macro = tileable_fbm(size, octaves=3, base_freq=5, seed=seed + 61)

    m1 = np.clip((n1 - 0.57) * 5.2, 0.0, 1.0)
    m2 = np.clip((n2 - 0.63) * 5.8, 0.0, 1.0)

    albedo = np.zeros((size, size, 3), dtype=np.float32)
    for c in range(3):
        v = base_rgb[c] * (0.88 + 0.24 * n_macro)
        v = v * (1.0 - m1 * 0.68) + speck1_rgb[c] * (m1 * 0.68)
        v = v * (1.0 - m2 * 0.58) + speck2_rgb[c] * (m2 * 0.58)
        albedo[..., c] = v

    height = 0.5 + 0.24 * n1 + 0.26 * n2
    normal = height_to_normal(height, strength=1.4)
    roughness = np.clip(rough_base + (n2 - 0.5) * 0.14 - m1 * 0.06, 0.10, 0.90)

    save_rgb_png(f"{prefix}_albedo.png", albedo, colorspace="sRGB")
    save_rgb_png(f"{prefix}_normal.png", normal, colorspace="Non-Color")
    save_gray_png(f"{prefix}_roughness.png", roughness)


def generate_patinated_bronze(size: int = 512) -> None:
    """Embossed sculptural bronze with subtle Catalan script relief & verdigris patina for Glory & Passion doors."""
    n_pat = tileable_fbm(size, octaves=4, base_freq=6, seed=88)
    n_fine = tileable_fbm(size, octaves=4, base_freq=20, seed=89)
    yy, xx = np.mgrid[0:size, 0:size] / float(size)

    # Embossed horizontal script lines + panel frames
    lines = np.sin(yy * math.pi * 48.0) * np.sin(xx * math.pi * 32.0 + n_fine * 6.0)
    relief = np.clip(0.5 + 0.35 * lines + 0.15 * n_fine, 0.0, 1.0)
    frame_x = np.minimum((xx * 2) % 1.0, 1.0 - ((xx * 2) % 1.0))
    frame_y = np.minimum((yy * 4) % 1.0, 1.0 - ((yy * 4) % 1.0))
    border = (np.minimum(frame_x, frame_y) < 0.05).astype(np.float32)
    height = np.clip(relief * (1.0 - border) + border * 0.92, 0.0, 1.0)

    bronze_dark = np.array([0.19, 0.14, 0.10], dtype=np.float32)
    bronze_gold = np.array([0.52, 0.38, 0.20], dtype=np.float32)
    verdigris = np.array([0.20, 0.34, 0.28], dtype=np.float32)

    albedo = bronze_dark[None, None, :] * (1.0 - height[..., None]) + bronze_gold[None, None, :] * (height[..., None] * 0.72)
    verd_mask = np.clip((n_pat - 0.56) * 2.4, 0.0, 0.45) * (1.0 - height)
    albedo = albedo * (1.0 - verd_mask[..., None]) + verdigris[None, None, :] * verd_mask[..., None]

    normal = height_to_normal(height, strength=3.4)
    roughness = np.clip(0.54 - height * 0.24 + verd_mask * 0.35, 0.18, 0.88)

    save_rgb_png("bronze_door_albedo.png", albedo, colorspace="sRGB")
    save_rgb_png("bronze_door_normal.png", normal, colorspace="Non-Color")
    save_gray_png("bronze_door_roughness.png", roughness)


def generate_marble_floor(size: int = 1024) -> None:
    """High-res warm Catalan travertine/marble cathedral floor with subtle veins & dark border inlays."""
    n_vein = tileable_fbm(size, octaves=5, base_freq=4, seed=201)
    n_fine = tileable_fbm(size, octaves=4, base_freq=16, seed=202)
    veins = np.abs(np.sin(np.linspace(0, math.pi * 4, size)[:, None] + n_vein * 5.2))
    veins = np.power(veins, 0.35)

    tiles = 4
    y = np.linspace(0, tiles, size, endpoint=False)[:, None]
    x = np.linspace(0, tiles, size, endpoint=False)[None, :]
    fy = y - np.floor(y)
    fx = x - np.floor(x)
    dy = np.minimum(fy, 1.0 - fy)
    dx = np.minimum(fx, 1.0 - fx)
    joint = np.clip(np.minimum(dy, dx) / 0.015, 0.0, 1.0)
    inlay = ((np.minimum(dy, dx) > 0.042) & (np.minimum(dy, dx) < 0.064)).astype(np.float32)

    cream = np.array([0.84, 0.78, 0.68], dtype=np.float32)
    vein_col = np.array([0.66, 0.59, 0.50], dtype=np.float32)
    inlay_col = np.array([0.48, 0.42, 0.35], dtype=np.float32)
    grout = np.array([0.40, 0.35, 0.30], dtype=np.float32)

    albedo = cream[None, None, :] * veins[..., None] + vein_col[None, None, :] * (1.0 - veins[..., None])
    albedo = albedo * (1.0 - inlay[..., None] * 0.58) + inlay_col[None, None, :] * (inlay[..., None] * 0.58)
    albedo = grout[None, None, :] * (1.0 - joint[..., None]) + albedo * joint[..., None]
    albedo += (n_fine[..., None] - 0.5) * 0.03

    normal = height_to_normal(joint * 0.85 + n_fine * 0.15, strength=1.6)
    roughness = np.clip(0.20 + (1.0 - joint) * 0.48 + (1.0 - veins) * 0.10, 0.10, 0.85)

    save_rgb_png("floor_marble_albedo.png", albedo, colorspace="sRGB")
    save_rgb_png("floor_marble_normal.png", normal, colorspace="Non-Color")
    save_gray_png("floor_marble_roughness.png", roughness)


def generate_trencadis_mosaic(size: int = 1024) -> None:
    """Crisp 1024px Gaudí shattered Venetian glass/ceramic mosaic for tower pinnacles & fruit baskets."""
    rng = np.random.default_rng(305)
    palette = np.array([
        [0.96, 0.77, 0.16],  # Venetian gold
        [0.10, 0.34, 0.78],  # Cobalt blue
        [0.12, 0.58, 0.42],  # Emerald green
        [0.85, 0.21, 0.14],  # Vermilion red
        [0.96, 0.94, 0.89],  # Ceramic white
        [0.94, 0.48, 0.10],  # Amber orange
    ], dtype=np.float32)

    num_pts = 240
    px = rng.random(num_pts)
    py = rng.random(num_pts)
    pcol = palette[rng.integers(0, len(palette), size=num_pts)]

    yy, xx = np.mgrid[0:size, 0:size] / float(size)
    d1 = np.full((size, size), 1e9, dtype=np.float32)
    d2 = np.full((size, size), 1e9, dtype=np.float32)
    cid = np.zeros((size, size), dtype=np.int32)

    for i in range(num_pts):
        dx = np.abs(xx - px[i])
        dx = np.minimum(dx, 1.0 - dx)
        dy = np.abs(yy - py[i])
        dy = np.minimum(dy, 1.0 - dy)
        dist = np.sqrt(dx * dx + dy * dy)
        better1 = dist < d1
        d2 = np.where(better1, d1, np.minimum(d2, dist))
        d1 = np.where(better1, dist, d1)
        cid = np.where(better1, i, cid)

    edge = np.clip((d2 - d1) / 0.0075, 0.0, 1.0)
    grout = np.array([0.85, 0.82, 0.75], dtype=np.float32)
    albedo = pcol[cid] * edge[..., None] + grout[None, None, :] * (1.0 - edge[..., None])
    normal = height_to_normal(edge, strength=3.4)
    roughness = np.clip(0.12 * edge + 0.86 * (1.0 - edge), 0.08, 0.92)

    save_rgb_png("trencadis_albedo.png", albedo, colorspace="sRGB")
    save_rgb_png("trencadis_normal.png", normal, colorspace="Non-Color")
    save_gray_png("trencadis_roughness.png", roughness)


def generate_stained_glass(name: str, stops: list[tuple[float, tuple[float, float, float]]], size: int = 1024, seed: int = 400) -> None:
    """Rich 1024px Joan Vila-Grau stained glass with leaded geometric ellipses, rose medallions & crystal panes."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size] / float(size)
    t = 1.0 - yy

    rgb = np.zeros((size, size, 3), dtype=np.float32)
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        mask = (t >= t0) & (t <= t1)
        f = np.clip((t - t0) / max(t1 - t0, 1e-5), 0.0, 1.0)
        for ch in range(3):
            rgb[..., ch] = np.where(mask, c0[ch] * (1.0 - f) + c1[ch] * f, rgb[..., ch])

    # Fine faceted crystal glass panes with jewel-like color shifts
    rows, cols = 28, 14
    r_idx = np.floor(yy * rows).astype(np.int32) % rows
    c_idx = np.floor(xx * cols).astype(np.int32) % cols
    jitter = rng.uniform(-0.15, 0.16, size=(rows, cols, 3)).astype(np.float32)
    rgb = np.clip(rgb + jitter[r_idx, c_idx], 0.04, 1.0)

    # Diagonal crystal diamond facets inside panes
    diag = np.abs(((xx * cols + yy * rows) % 1.0) - 0.5)
    rgb = np.clip(rgb * (0.90 + 0.22 * diag[..., None]), 0.04, 1.0)

    # Lead cames + Gaudí elliptical stone-like tracery medallions!
    fy = (yy * rows) - np.floor(yy * rows)
    fx = (xx * cols) - np.floor(xx * cols)
    lead = ((fy < 0.055) | (fy > 0.945) | (fx < 0.055) | (fx > 0.945)).astype(np.float32)
    mullion = (
        (np.abs(xx - 0.333) < 0.016)
        | (np.abs(xx - 0.667) < 0.016)
        | (xx < 0.022)
        | (xx > 0.978)
    ).astype(np.float32)

    # Iconic stacked circular/elliptical rose medallions down the center of each lancet
    rose = np.zeros((size, size), dtype=np.float32)
    for cy_r in (0.18, 0.42, 0.66, 0.86):
        dx = (xx - 0.5) * 1.15
        dy = (yy - cy_r) * 2.1
        rad = np.sqrt(dx * dx + dy * dy)
        ring = (np.abs(rad - 0.24) < 0.024) | (np.abs(rad - 0.11) < 0.016)
        rose = np.maximum(rose, ring.astype(np.float32))

    frame = np.maximum(np.maximum(lead * 0.68, mullion * 0.94), rose * 0.90)
    albedo = rgb * (1.0 - frame[..., None]) + np.array([0.07, 0.06, 0.06], dtype=np.float32) * frame[..., None]
    save_rgb_png(f"{name}.png", albedo, colorspace="sRGB")


def generate_panot_barcelona(size: int = 512) -> None:
    tiles = 4
    yy, xx = np.mgrid[0:size, 0:size] / float(size)
    fy = (yy * tiles) % 1.0 - 0.5
    fx = (xx * tiles) % 1.0 - 0.5
    r = np.sqrt(fx * fx + fy * fy)
    ang = np.arctan2(fy, fx)

    petal = np.abs(r - (0.20 + 0.13 * np.abs(np.cos(2.0 * ang))))
    groove_petal = np.clip(petal / 0.032, 0.0, 1.0)
    groove_center = np.clip(np.abs(r - 0.07) / 0.024, 0.0, 1.0)
    groove_border = np.clip(np.minimum(0.5 - np.abs(fx), 0.5 - np.abs(fy)) / 0.028, 0.0, 1.0)
    height = np.minimum(np.minimum(groove_petal, groove_center), groove_border)

    n = tileable_fbm(size, octaves=4, base_freq=8, seed=501)
    height = np.clip(height * 0.8 + n * 0.2, 0.0, 1.0)
    base = np.array([0.62, 0.60, 0.57], dtype=np.float32)
    albedo = base[None, None, :] * (0.72 + 0.28 * height[..., None])
    normal = height_to_normal(height, strength=3.6)
    roughness = np.clip(0.76 + (1.0 - height) * 0.18, 0.4, 0.96)

    save_rgb_png("panot_albedo.png", albedo, colorspace="sRGB")
    save_rgb_png("panot_normal.png", normal, colorspace="Non-Color")
    save_gray_png("panot_roughness.png", roughness)


def generate_eixample_facade(size: int = 512) -> None:
    n = tileable_fbm(size, octaves=4, base_freq=8, seed=601)
    yy, xx = np.mgrid[0:size, 0:size] / float(size)
    floors = 5
    bays = 4
    fy = (yy * floors) % 1.0
    fx = (xx * bays) % 1.0

    albedo = np.zeros((size, size, 3), dtype=np.float32)
    stucco = np.array([0.82, 0.71, 0.56], dtype=np.float32)
    albedo[..., :] = stucco[None, None, :] * (0.90 + 0.16 * n[..., None])

    cornice = ((fy < 0.09) | (fy > 0.93)).astype(np.float32)
    albedo = albedo * (1.0 - cornice[..., None] * 0.14) + np.array([0.88, 0.82, 0.72]) * (cornice[..., None] * 0.14)

    in_win = (fx > 0.28) & (fx < 0.72) & (fy > 0.18) & (fy < 0.84)
    in_shutter = (((fx > 0.16) & (fx <= 0.28)) | ((fx >= 0.72) & (fx < 0.84))) & (fy > 0.18) & (fy < 0.84)
    in_balcony = (fx > 0.12) & (fx < 0.88) & (fy > 0.68) & (fy < 0.88)
    bar = ((np.floor(fx * 28) % 2) == 0) & in_balcony

    albedo[in_win] = np.array([0.14, 0.18, 0.23], dtype=np.float32)
    albedo[in_shutter] = np.array([0.24, 0.36, 0.27], dtype=np.float32)
    albedo[bar] = np.array([0.11, 0.12, 0.13], dtype=np.float32)

    height = np.ones((size, size), dtype=np.float32) * 0.75 + cornice * 0.20
    height[in_win] = 0.20
    height[in_shutter] = 0.88
    normal = height_to_normal(height, strength=2.6)
    roughness = np.full((size, size), 0.78, dtype=np.float32)
    roughness[in_win] = 0.14

    save_rgb_png("eixample_facade_albedo.png", albedo, colorspace="sRGB")
    save_rgb_png("eixample_facade_normal.png", normal, colorspace="Non-Color")
    save_gray_png("eixample_facade_roughness.png", roughness)


def generate_crimson_carpet(size: int = 512) -> None:
    """Deep royal Catalan crimson sanctuary carpet with woven gold geometric border motif."""
    n_weave = tileable_fbm(size, octaves=4, base_freq=32, seed=701)
    yy, xx = np.mgrid[0:size, 0:size] / float(size)

    # Woven fabric micro-grain
    weave = 0.88 + 0.12 * (np.sin(xx * math.pi * 120.0) * np.sin(yy * math.pi * 120.0) * 0.5 + 0.5)
    base = np.array([0.46, 0.06, 0.08], dtype=np.float32)
    gold = np.array([0.84, 0.65, 0.22], dtype=np.float32)

    # Subtle diamond damask motif + ornate golden border stripes along X edges
    diamond = np.abs(((xx * 8.0 + yy * 8.0) % 1.0) - 0.5) + np.abs(((xx * 8.0 - yy * 8.0) % 1.0) - 0.5)
    motif = (np.abs(diamond - 0.45) < 0.045).astype(np.float32) * 0.22
    border = (((xx > 0.04) & (xx < 0.09)) | ((xx > 0.91) & (xx < 0.96))).astype(np.float32)
    gold_mask = np.clip(border * 0.85 + motif, 0.0, 1.0)

    albedo = base[None, None, :] * (1.0 - gold_mask[..., None]) + gold[None, None, :] * gold_mask[..., None]
    albedo *= (weave * (0.92 + 0.14 * n_weave))[..., None]
    normal = height_to_normal(weave * 0.6 + gold_mask * 0.4, strength=1.8)
    roughness = np.clip(0.88 - gold_mask * 0.25 + (n_weave - 0.5) * 0.08, 0.50, 0.98)

    save_rgb_png("carpet_crimson_albedo.png", albedo, colorspace="sRGB")
    save_rgb_png("carpet_crimson_normal.png", normal, colorspace="Non-Color")
    save_gray_png("carpet_crimson_roughness.png", roughness)


def generate_carved_oak(size: int = 512) -> None:
    """Rich Catalan dark cathedral oak wood with elongated grain for pews, organ casing & confessionals."""
    n_grain = tileable_fbm(size, octaves=5, base_freq=8, seed=711, stretch_y=6.0)
    n_fine = tileable_fbm(size, octaves=4, base_freq=24, seed=712, stretch_y=3.0)
    rings = 0.5 + 0.5 * np.sin(n_grain * 18.0 + np.linspace(0, math.pi * 6, size)[None, :])

    dark = np.array([0.21, 0.12, 0.07], dtype=np.float32)
    warm = np.array([0.38, 0.24, 0.13], dtype=np.float32)
    albedo = dark[None, None, :] * (1.0 - rings[..., None]) + warm[None, None, :] * rings[..., None]
    albedo *= (0.90 + 0.18 * n_fine[..., None])

    normal = height_to_normal(rings * 0.5 + n_fine * 0.5, strength=1.6)
    roughness = np.clip(0.46 + (1.0 - rings) * 0.22 + (n_fine - 0.5) * 0.10, 0.24, 0.84)

    save_rgb_png("wood_oak_albedo.png", albedo, colorspace="sRGB")
    save_rgb_png("wood_oak_normal.png", normal, colorspace="Non-Color")
    save_gray_png("wood_oak_roughness.png", roughness)


def generate_plane_leaves_rgba(size: int = 512) -> None:
    """Crisp 512x512 RGBA alpha-cutout cluster of Mediterranean London Plane leaves on twigs."""
    rng = np.random.default_rng(812)
    yy, xx = np.mgrid[0:size, 0:size] / float(size)

    rgba = np.zeros((size, size, 4), dtype=np.float32)

    # Fine central woody twigs radiating outward
    for ang, length in ((-0.45, 0.42), (0.0, 0.46), (0.45, 0.42), (-0.9, 0.34), (0.9, 0.34)):
        ca, sa = math.cos(ang), math.sin(ang)
        dx = xx - 0.5
        dy = (1.0 - yy) - 0.08
        proj = dx * sa + dy * ca
        perp = np.abs(dx * ca - dy * sa)
        twig = (proj > 0.0) & (proj < length) & (perp < 0.011 * (1.0 - proj * 0.7))
        rgba[twig, :3] = np.array([0.28, 0.21, 0.14], dtype=np.float32)
        rgba[twig, 3] = 1.0

    # 34 overlapping palmate Mediterranean leaves with natural sunlit-tip color variation & midrib veins
    for _ in range(34):
        cx = rng.uniform(0.18, 0.82)
        cy = rng.uniform(0.16, 0.84)
        rad = rng.uniform(0.085, 0.155)
        rot = rng.uniform(0, math.pi * 2.0)
        ca, sa = math.cos(rot), math.sin(rot)
        lx = (xx - cx) * ca - (yy - cy) * sa
        ly = (xx - cx) * sa + (yy - cy) * ca
        r = np.sqrt(lx * lx + ly * ly)
        ang = np.arctan2(ly, lx)
        # 5-lobed palmate plane-tree leaf silhouette
        lobe = rad * (0.72 + 0.28 * np.power(np.abs(np.cos(ang * 2.5)), 0.75)) * (0.85 + 0.25 * np.sin(ang))
        mask = r < lobe
        if not np.any(mask):
            continue
        shade = rng.uniform(0.74, 1.18)
        sun_tip = np.clip(r / max(rad, 1e-4), 0.0, 1.0)
        vein = np.exp(-np.abs(lx) * 55.0) * 0.12
        leaf_col = np.stack([
            np.clip((0.15 + 0.11 * sun_tip + vein) * shade, 0.05, 0.65),
            np.clip((0.35 + 0.17 * sun_tip + vein) * shade, 0.14, 0.82),
            np.clip((0.11 + 0.06 * sun_tip) * shade, 0.04, 0.42),
        ], axis=-1)
        rgba[mask, :3] = leaf_col[mask]
        rgba[mask, 3] = 1.0

    save_rgba_png("plane_leaves_rgba.png", rgba, colorspace="sRGB")


def generate_all_textures() -> None:
    print(f"[Textures] Generating 1024px weathered AAA PBR textures in {TEX_DIR}...")
    generate_ashlar_stone(
        "sandstone_warm",
        base_rgb=(0.79, 0.70, 0.56),
        var_rgb=(0.065, 0.055, 0.042),
        mortar_rgb=(0.51, 0.43, 0.33),
        rows=8,
        cols=4,
        size=1024,
        rough_base=0.76,
        normal_strength=3.4,
        weathering=0.22,
        seed=11,
    )
    # Historic Nativity Facade (1894-1930): visibly richer ochre, rain patina & organic relief
    generate_ashlar_stone(
        "nativity_stone",
        base_rgb=(0.64, 0.52, 0.37),
        var_rgb=(0.095, 0.075, 0.055),
        mortar_rgb=(0.33, 0.26, 0.18),
        rows=10,
        cols=5,
        size=1024,
        rough_base=0.85,
        normal_strength=5.2,
        weathering=0.58,
        seed=22,
    )
    # Stark Pale Passion Facade: chiseled limestone dressing, crisp cool contrast
    generate_ashlar_stone(
        "passion_stone",
        base_rgb=(0.83, 0.81, 0.77),
        var_rgb=(0.045, 0.042, 0.036),
        mortar_rgb=(0.60, 0.58, 0.54),
        rows=6,
        cols=3,
        size=1024,
        rough_base=0.71,
        normal_strength=3.0,
        weathering=0.14,
        chisel_marks=1.0,
        seed=33,
    )
    generate_ashlar_stone(
        "vault_stone",
        base_rgb=(0.89, 0.84, 0.75),
        var_rgb=(0.03, 0.03, 0.02),
        mortar_rgb=(0.72, 0.66, 0.56),
        rows=8,
        cols=4,
        size=1024,
        rough_base=0.60,
        normal_strength=2.0,
        weathering=0.06,
        seed=44,
    )
    generate_ashlar_stone(
        "crypt_stone",
        base_rgb=(0.54, 0.48, 0.41),
        var_rgb=(0.065, 0.055, 0.045),
        mortar_rgb=(0.30, 0.26, 0.21),
        rows=8,
        cols=4,
        size=1024,
        rough_base=0.85,
        normal_strength=4.2,
        weathering=0.45,
        seed=55,
    )
    generate_speckled_stone(
        "porphyry_red",
        base_rgb=(0.45, 0.15, 0.16),
        speck1_rgb=(0.78, 0.56, 0.52),
        speck2_rgb=(0.22, 0.06, 0.07),
        rough_base=0.22,
        size=1024,
        seed=71,
    )
    generate_speckled_stone(
        "basalt_dark",
        base_rgb=(0.20, 0.20, 0.22),
        speck1_rgb=(0.36, 0.36, 0.38),
        speck2_rgb=(0.10, 0.10, 0.12),
        rough_base=0.30,
        size=1024,
        seed=72,
    )
    generate_speckled_stone(
        "granite_grey",
        base_rgb=(0.64, 0.60, 0.57),
        speck1_rgb=(0.86, 0.82, 0.78),
        speck2_rgb=(0.30, 0.28, 0.27),
        rough_base=0.38,
        size=1024,
        seed=73,
    )
    generate_patinated_bronze()
    generate_crimson_carpet()
    generate_carved_oak()
    generate_plane_leaves_rgba()
    generate_marble_floor()
    generate_trencadis_mosaic()
    generate_panot_barcelona()
    generate_eixample_facade()

    generate_stained_glass(
        "stained_glass_east",
        [
            (0.00, (0.04, 0.15, 0.68)),
            (0.28, (0.04, 0.50, 0.76)),
            (0.55, (0.10, 0.70, 0.42)),
            (0.78, (0.74, 0.86, 0.26)),
            (1.00, (0.98, 0.96, 0.84)),
        ],
        size=1024,
        seed=401,
    )
    generate_stained_glass(
        "stained_glass_west",
        [
            (0.00, (0.72, 0.05, 0.08)),
            (0.28, (0.92, 0.23, 0.07)),
            (0.55, (0.97, 0.56, 0.09)),
            (0.80, (0.99, 0.85, 0.22)),
            (1.00, (0.99, 0.96, 0.86)),
        ],
        size=1024,
        seed=402,
    )
    generate_stained_glass(
        "stained_glass_apse",
        [
            (0.00, (0.28, 0.13, 0.62)),
            (0.32, (0.14, 0.42, 0.80)),
            (0.66, (0.78, 0.86, 0.97)),
            (1.00, (0.99, 0.95, 0.76)),
        ],
        size=1024,
        seed=403,
    )
    print("[Textures] Done.")


if __name__ == "__main__":
    generate_all_textures()
