"""Master Blender build script: generates all PBR textures & modular GLB assets for Sagrada Família."""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

import generate_textures
import build_interior
import build_towers
import build_facades
import build_cloister_crypt
import build_eixample
import build_furnishings
import build_plaza_life


def main() -> None:
    t0 = time.time()
    print("=== Sagrada Família 3D — Blender Asset Pipeline ===")
    generate_textures.generate_all_textures()
    build_interior.build_interior()
    build_towers.build_towers()
    build_facades.build_facades()
    build_cloister_crypt.build_cloister_and_crypt()
    build_eixample.build_eixample()
    build_furnishings.build_furnishings()
    build_plaza_life.build_plaza_life()
    elapsed = time.time() - t0
    print(f"=== All assets built successfully in {elapsed:.1f}s ===")


if __name__ == "__main__":
    main()
