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


def save_public_webp(png_name: str, size: int = 512, quality: int = 85) -> str:
    """Write a compact WebP copy of a generated texture to public/textures/ (runtime projector textures)."""
    src = os.path.join(TEX_DIR, png_name)
    img = bpy.data.images.load(src)
    img.scale(size, size)
    out = os.path.join(PUBLIC_TEX_DIR, os.path.splitext(png_name)[0] + ".webp")
    img.filepath_raw = out
    img.file_format = "WEBP"
    try:
        img.save(filepath=out, quality=quality)
    except TypeError:
        img.save()
    bpy.data.images.remove(img)
    return out


def save_rgba_png(name: str, rgba: np.ndarray, colorspace: str = "sRGB") -> str:
    h, w, _ = rgba.shape
    # All source PNGs live in textures_src/ (the 1 MB stained-glass PNGs used to land in public/)
    target_dir = TEX_DIR
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
    # The apostle pinnacles read predominantly gold & vermilion with white accents (blue/green sparser);
    # a uniform draw averaged out to a washed-out pastel pink at viewing distance.
    weights = np.array([0.30, 0.06, 0.09, 0.31, 0.13, 0.11], dtype=np.float64)
    pcol = palette[rng.choice(len(palette), size=num_pts, p=weights / weights.sum())]

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
    grout = np.array([0.58, 0.55, 0.50], dtype=np.float32)
    albedo = pcol[cid] * edge[..., None] + grout[None, None, :] * (1.0 - edge[..., None])
    normal = height_to_normal(edge, strength=3.4)
    roughness = np.clip(0.12 * edge + 0.86 * (1.0 - edge), 0.08, 0.92)

    save_rgb_png("trencadis_albedo.png", albedo, colorspace="sRGB")
    save_rgb_png("trencadis_normal.png", normal, colorspace="Non-Color")
    save_gray_png("trencadis_roughness.png", roughness)


def generate_stained_glass(name: str, stops: list[tuple[float, tuple[float, float, float]]], size: int = 1024, seed: int = 400) -> None:
    """Authentic 1024px Joan Vila-Grau organic irregular shard stained-glass mosaic + leaded-glass normal map."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size] / float(size)
    t = 1.0 - yy

    # Smooth base vertical color progression (Gaudí's chromatic ascent from deep earth/sea tones to bright heaven!)
    rgb = np.zeros((size, size, 3), dtype=np.float32)
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        mask = (t >= t0) & (t <= t1)
        f = np.clip((t - t0) / max(t1 - t0, 1e-5), 0.0, 1.0)
        for ch in range(3):
            rgb[..., ch] = np.where(mask, c0[ch] * (1.0 - f) + c1[ch] * f, rgb[..., ch])

    # Organic Joan Vila-Grau irregular faceted glass shards via fast jittered grid Voronoi (zero repetitive bullseyes!)
    gx_n, gy_n = 12, 24
    pts_x = (np.arange(gx_n)[None, :] + rng.uniform(0.18, 0.82, size=(gy_n, gx_n))) / gx_n
    pts_y = (np.arange(gy_n)[:, None] + rng.uniform(0.18, 0.82, size=(gy_n, gx_n))) / gy_n
    cell_jitter = rng.uniform(-0.18, 0.20, size=(gy_n, gx_n, 3)).astype(np.float32)
    cell_lum = rng.uniform(0.76, 1.24, size=(gy_n, gx_n)).astype(np.float32)

    cx_idx = np.floor(xx * gx_n).astype(np.int32)
    cy_idx = np.floor(yy * gy_n).astype(np.int32)
    d1 = np.full((size, size), 1e9, dtype=np.float32)
    d2 = np.full((size, size), 1e9, dtype=np.float32)
    best_gx = np.zeros((size, size), dtype=np.int32)
    best_gy = np.zeros((size, size), dtype=np.int32)

    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            nx = (cx_idx + ox) % gx_n
            ny = (cy_idx + oy) % gy_n
            px = pts_x[ny, nx]
            py = pts_y[ny, nx]
            dx = ((xx - px + 0.5) % 1.0) - 0.5
            dy = ((yy - py + 0.5) % 1.0) - 0.5
            # Slightly taller vertical shards like authentic Vila-Grau glasswork
            dist = np.sqrt((dx * 1.15) ** 2 + (dy * 0.88) ** 2)
            better = dist < d1
            d2 = np.where(better, d1, np.minimum(d2, dist))
            d1 = np.where(better, dist, d1)
            best_gx = np.where(better, nx, best_gx)
            best_gy = np.where(better, ny, best_gy)

    # Crisp thin dark lead cames separating organic polygonal shards
    shard_edge = np.clip((d2 - d1) / 0.0052, 0.0, 1.0)
    rgb = np.clip(rgb * cell_lum[best_gy, best_gx, None] + cell_jitter[best_gy, best_gx], 0.03, 1.0)

    # Subtle hand-blown glass internal texture + slender Gothic vertical mullions
    n_glass = tileable_fbm(size, octaves=3, base_freq=18, seed=seed + 17)
    rgb = np.clip(rgb * (0.90 + 0.20 * n_glass[..., None]), 0.03, 1.0)

    mullion = (
        (np.abs(xx - 0.333) < 0.015)
        | (np.abs(xx - 0.667) < 0.015)
        | (xx < 0.020)
        | (xx > 0.980)
        | (np.abs((yy * 4.0) % 1.0 - 0.5) > 0.486)
    ).astype(np.float32)

    lead_mask = np.maximum((1.0 - shard_edge) * 0.85, mullion * 0.95)
    albedo = rgb * (1.0 - lead_mask[..., None]) + np.array([0.05, 0.045, 0.045], dtype=np.float32) * lead_mask[..., None]
    save_rgb_png(f"{name}.png", albedo, colorspace="sRGB")

    # Save shared leaded stained-glass normal map once so glass catches rich architectural specular glints!
    if name == "stained_glass_east":
        glass_h = np.clip(shard_edge * 0.72 + n_glass * 0.28 - mullion * 0.6, 0.0, 1.0)
        normal = height_to_normal(glass_h, strength=2.4)
        save_rgb_png("stained_glass_normal.png", normal, colorspace="Non-Color")


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


def generate_eixample_facade(
    prefix: str = "eixample_facade",
    stucco_rgb: tuple[float, float, float] = (0.82, 0.71, 0.56),
    shutter_rgb: tuple[float, float, float] = (0.24, 0.36, 0.27),
    seed: int = 601,
    size: int = 512,
) -> None:
    n = tileable_fbm(size, octaves=4, base_freq=8, seed=seed)
    yy, xx = np.mgrid[0:size, 0:size] / float(size)
    floors = 5
    bays = 4
    fy = (yy * floors) % 1.0
    fx = (xx * bays) % 1.0

    albedo = np.zeros((size, size, 3), dtype=np.float32)
    stucco = np.array(stucco_rgb, dtype=np.float32)
    albedo[..., :] = stucco[None, None, :] * (0.88 + 0.20 * n[..., None])

    cornice = ((fy < 0.09) | (fy > 0.93)).astype(np.float32)
    albedo = albedo * (1.0 - cornice[..., None] * 0.16) + np.array([0.90, 0.85, 0.76]) * (cornice[..., None] * 0.16)

    in_win = (fx > 0.28) & (fx < 0.72) & (fy > 0.18) & (fy < 0.84)
    in_shutter = (((fx > 0.16) & (fx <= 0.28)) | ((fx >= 0.72) & (fx < 0.84))) & (fy > 0.18) & (fy < 0.84)
    in_balcony = (fx > 0.12) & (fx < 0.88) & (fy > 0.68) & (fy < 0.88)
    bar = ((np.floor(fx * 28) % 2) == 0) & in_balcony

    albedo[in_win] = np.array([0.11, 0.15, 0.21], dtype=np.float32)
    albedo[in_shutter] = np.array(shutter_rgb, dtype=np.float32)
    albedo[bar] = np.array([0.11, 0.12, 0.13], dtype=np.float32)

    height = np.ones((size, size), dtype=np.float32) * 0.75 + cornice * 0.20
    height[in_win] = 0.20
    height[in_shutter] = 0.88
    normal = height_to_normal(height, strength=2.8)
    roughness = np.full((size, size), 0.78, dtype=np.float32)
    roughness[in_win] = 0.14

    save_rgb_png(f"{prefix}_albedo.png", albedo, colorspace="sRGB")
    save_rgb_png(f"{prefix}_normal.png", normal, colorspace="Non-Color")
    save_gray_png(f"{prefix}_roughness.png", roughness)


def generate_micro_surface_maps(size: int = 512) -> None:
    """Subtle PBR micro-normal & roughness maps for white marble, brushed gold, cast iron & terracotta."""
    # 1. White Statuary Marble (delicate grey veining + fine honed stone normal)
    n_v = tileable_fbm(size, octaves=5, base_freq=5, seed=901)
    n_f = tileable_fbm(size, octaves=4, base_freq=22, seed=902)
    veins = np.power(np.abs(np.sin(np.linspace(0, math.pi * 3, size)[:, None] + n_v * 4.8)), 0.32)
    marble = np.array([0.92, 0.90, 0.86], dtype=np.float32)[None, None, :] * (0.86 + 0.14 * veins[..., None])
    save_rgb_png("white_marble_albedo.png", marble, colorspace="sRGB")
    save_rgb_png("white_marble_normal.png", height_to_normal(veins * 0.5 + n_f * 0.5, strength=1.1), colorspace="Non-Color")
    save_gray_png("white_marble_roughness.png", np.clip(0.32 + (1.0 - veins) * 0.16, 0.18, 0.65))

    # 2. Hammered / Brushed Liturgical Gold
    n_g = tileable_fbm(size, octaves=4, base_freq=18, seed=911)
    save_rgb_png("metal_micro_normal.png", height_to_normal(n_g, strength=1.5), colorspace="Non-Color")
    save_gray_png("metal_micro_roughness.png", np.clip(0.24 + (n_g - 0.5) * 0.16, 0.12, 0.48))

    # 3. Catalan Terracotta Roof Tiles
    yy, xx = np.mgrid[0:size, 0:size] / float(size)
    ridge = 0.5 + 0.5 * np.sin(xx * math.pi * 36.0)
    step = (yy * 14.0) % 1.0
    n_t = tileable_fbm(size, octaves=4, base_freq=10, seed=921)
    terra_h = np.clip(ridge * 0.65 + step * 0.25 + n_t * 0.10, 0.0, 1.0)
    terra = np.array([0.62, 0.34, 0.23], dtype=np.float32)[None, None, :] * (0.78 + 0.32 * terra_h[..., None])
    save_rgb_png("terracotta_albedo.png", terra, colorspace="sRGB")
    save_rgb_png("terracotta_normal.png", height_to_normal(terra_h, strength=3.2), colorspace="Non-Color")
    save_gray_png("terracotta_roughness.png", np.clip(0.80 - ridge * 0.12 + (n_t - 0.5) * 0.10, 0.55, 0.95))


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


def generate_foliage_canopy(size: int = 512) -> None:
    """Lush seamless 3D foliage PBR map (albedo, normal, roughness) for solid sculpted Mediterranean tree canopies."""
    rng = np.random.default_rng(819)
    n_macro = tileable_fbm(size, octaves=4, base_freq=6, seed=820)
    yy, xx = np.mgrid[0:size, 0:size] / float(size)

    # Dark shadowy interior foliage base
    albedo = np.zeros((size, size, 3), dtype=np.float32)
    albedo[..., 0] = 0.08 + 0.05 * n_macro
    albedo[..., 1] = 0.17 + 0.08 * n_macro
    albedo[..., 2] = 0.06 + 0.03 * n_macro
    height = np.full((size, size), 0.18, dtype=np.float32)

    # Stamp 260 overlapping organic Mediterranean leaves periodically across tile
    for i in range(260):
        cx = rng.random()
        cy = rng.random()
        rad = rng.uniform(0.038, 0.072)
        rot = rng.uniform(0, math.pi * 2.0)
        ca, sa = math.cos(rot), math.sin(rot)
        dx = ((xx - cx + 0.5) % 1.0) - 0.5
        dy = ((yy - cy + 0.5) % 1.0) - 0.5
        lx = dx * ca - dy * sa
        ly = dx * sa + dy * ca
        r = np.sqrt(lx * lx + ly * ly)
        ang = np.arctan2(ly, lx)
        lobe = rad * (0.74 + 0.26 * np.abs(np.cos(ang * 2.5)))
        mask = r < lobe
        if not np.any(mask):
            continue
        layer_h = 0.30 + 0.70 * (i / 260.0)
        shade = rng.uniform(0.75, 1.22) * (0.72 + 0.35 * layer_h)
        albedo[mask, 0] = np.clip(0.15 * shade, 0.05, 0.45)
        albedo[mask, 1] = np.clip(0.35 * shade, 0.12, 0.68)
        albedo[mask, 2] = np.clip(0.11 * shade, 0.04, 0.30)
        height[mask] = layer_h * (1.0 - 0.25 * (r[mask] / max(rad, 1e-4)))

    normal = height_to_normal(height, strength=4.2)
    roughness = np.clip(0.78 - height * 0.24, 0.42, 0.92)

    save_rgb_png("foliage_canopy_albedo.png", albedo, colorspace="sRGB")
    save_rgb_png("foliage_canopy_normal.png", normal, colorspace="Non-Color")
    save_gray_png("foliage_canopy_roughness.png", roughness)


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
    generate_foliage_canopy()
    generate_marble_floor()
    generate_trencadis_mosaic()
    generate_panot_barcelona()
    generate_eixample_facade("eixample_facade", stucco_rgb=(0.82, 0.71, 0.56), shutter_rgb=(0.24, 0.36, 0.27), seed=601)
    generate_eixample_facade("eixample_terracotta", stucco_rgb=(0.76, 0.53, 0.42), shutter_rgb=(0.22, 0.27, 0.24), seed=602)
    generate_eixample_facade("eixample_cream", stucco_rgb=(0.86, 0.81, 0.72), shutter_rgb=(0.26, 0.32, 0.40), seed=603)
    generate_micro_surface_maps()

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
    # 512px WebP copies used by the runtime SpotLight projectors & floor colour carpets
    save_public_webp("stained_glass_east.png")
    save_public_webp("stained_glass_west.png")
    print("[Textures] Done.")


if __name__ == "__main__":
    generate_all_textures()
