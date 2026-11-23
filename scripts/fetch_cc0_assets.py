"""Download CC0 Public Domain 2K photoscan PBR textures and 2K PureSky HDRIs from Poly Haven."""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CC0_DIR = os.path.join(ROOT_DIR, "blender", "textures_src", "cc0")
HDRI_DIR = os.path.join(ROOT_DIR, "public", "hdri")
os.makedirs(CC0_DIR, exist_ok=True)
os.makedirs(HDRI_DIR, exist_ok=True)

HEADERS = {"User-Agent": "SagradaFamilia3D/1.0"}

TEXTURES = {
    "sandstone_warm": "large_sandstone_blocks",
    "nativity_stone": "old_sandstone_02",
    "crypt_stone": "old_stone_wall_02",
    "granite_grey": "granite_tile_02",
    "floor_marble": "marble_01",
    "wood_oak": "dark_wood",
    "bark_platanus": "bark_platanus",
    "asphalt_real": "asphalt_02",
    "grass_real": "grass_ground",
}

HDRIS = {
    "day": "kloofendal_38d_partly_cloudy_puresky",
    "sunset": "belfast_sunset_puresky",
    "night": "kloppenheim_02_puresky",
}


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def download_file(url: str, dest: str) -> str:
    if os.path.exists(dest) and os.path.getsize(dest) > 1024:
        return f"cached {os.path.basename(dest)}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    with open(dest, "wb") as f:
        f.write(data)
    kb = len(data) / 1024
    return f"ok {os.path.basename(dest)} ({kb:.0f} KB)"


def fetch_texture_set(local_name: str, polyhaven_id: str, res: str = "1k") -> list[str]:
    files = fetch_json(f"https://api.polyhaven.com/files/{polyhaven_id}")
    jobs = []
    # Map Poly Haven keys -> our standardized PBR map names
    map_candidates = {
        "albedo": ["Diffuse", "col", "albedo"],
        "normal": ["nor_gl", "Normal"],
        "roughness": ["Rough", "rough_ao"],
    }
    for out_kind, keys in map_candidates.items():
        found_url = None
        ext = "jpg"
        for k in keys:
            node = files.get(k)
            if not isinstance(node, dict):
                continue
            rnode = node.get(res) or node.get("1k") or node.get("2k")
            if not isinstance(rnode, dict):
                continue
            for fmt in ("jpg", "png"):
                if fmt in rnode and "url" in rnode[fmt]:
                    found_url = rnode[fmt]["url"]
                    ext = fmt
                    break
            if found_url:
                break
        if found_url:
            dest = os.path.join(CC0_DIR, f"{local_name}_{out_kind}.{ext}")
            jobs.append((found_url, dest))

    results = []
    for url, dest in jobs:
        results.append(download_file(url, dest))
    return results


def fetch_hdri(local_name: str, polyhaven_id: str, res: str = "2k") -> str:
    files = fetch_json(f"https://api.polyhaven.com/files/{polyhaven_id}")
    hdri_node = files.get("hdri", {})
    rnode = hdri_node.get(res) or hdri_node.get("1k")
    url = rnode["hdr"]["url"]
    dest = os.path.join(HDRI_DIR, f"{local_name}.hdr")
    return download_file(url, dest)


def main() -> None:
    # The web app ships compact public/hdri/*_1k.hdr files; the 2K source HDRIs (~6 MB each) are only
    # fetched on request (--hdri) so a plain asset refresh never drops unused multi-MB files into public/.
    want_hdri = "--hdri" in sys.argv
    print("=== Downloading CC0 Poly Haven Photoscans" + (" & 2K PureSky HDRIs" if want_hdri else "") + " ===")
    with ThreadPoolExecutor(max_workers=6) as ex:
        tex_futs = [ex.submit(fetch_texture_set, name, pid, "1k") for name, pid in TEXTURES.items()]
        hdri_futs = [ex.submit(fetch_hdri, name, pid, "2k") for name, pid in HDRIS.items()] if want_hdri else []

        for f in tex_futs:
            print(" ", ", ".join(f.result()))
        for f in hdri_futs:
            print("  [HDRI]", f.result())
    print("=== CC0 Asset Download Complete ===")


if __name__ == "__main__":
    main()
