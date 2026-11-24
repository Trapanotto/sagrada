"""Master ground plan of the Sagrada Família model: the single source of truth for coordinates.

Every Blender build script and the web runtime read positions, radii, heights and extents from here.
The web side receives exactly these numbers through a generated TypeScript data file:

    python blender/layout.py            # writes src/data/layout.generated.ts
    python blender/layout.py --check    # exits 1 if src/data/layout.generated.ts is stale
    (npm run layout / npm run layout:check do the same)

This module is plain Python (no bpy), so it imports inside Blender (`from layout import ...`) and in a
normal interpreter alike.

CONVENTIONS (read before using any number)
  Plan frame = Blender frame, metres, Z up:
    +X = "east"  = Nativity façade, Carrer de la Marina, Plaça de Gaudí
    -X = "west"  = Passion façade, Carrer de Sardenya, Plaça de la Sagrada Família
    +Y = "north" = apse, Tower of Mary, crypt below, Carrer de Provença
    -Y = "south" = nave, Glory façade, Carrer de Mallorca
    Origin (0, 0) = centre of the crossing = axis of the Tower of Jesus Christ. 7.5 m module.
    The real building is rotated: model +Y points to compass azimuth ~315° (NW), +X to ~45° (NE)
    (OSM, grid angle 44.8°). The model keeps the liturgical names ("north" = apse side).
  Runtime frame (three.js, Y up), as written by the glTF exporter (export_yup=True):
    world (x, y, z) = (X, Z, -Y)   ->  runtime -Z is "north" (apse), runtime +Z is "south" (Glory).
  Heights: absolute Z in metres. Z_NAVE = 1.2 is the basilica floor. The street is NOT at Z = 0 any
    more: the outdoor ground is a plane falling towards Carrer de Mallorca, see ground_z().
  Angles: degrees, counter-clockwise from +X in the plan frame (= atan2(dy, dx) in Blender, which is
    also what CollisionSystem computes as atan2(-dz, dx) in the runtime frame).

SOURCE / CONFIDENCE TAGS used in the comments
  OFF  sagradafamilia.org (information booklets 4, 5, 7, 9, 10; official texts)
  WIKI Wikipedia (en, de, ca)
  OSM  OpenStreetMap geometry (basilica outline, tower parts, streets; queried 2026-11-23),
       rotated into this frame; traced from imagery, typically +-1 m
  DER  derived from other values (7.5 m module, symmetry, consistency between packages)
  EST  estimate / judgement where sources are silent
  RT   runtime / gameplay contract (walkability, performance), not an architectural fact
  KEEP unchanged from the previous model on purpose
  confidence: high / med / low
"""

from __future__ import annotations

import json
import math
import os
import sys

LAYOUT_VERSION = 1

# ════════════════════════════════════════════════════════════════════════════════════════════════
# 1. Frame and module
# ════════════════════════════════════════════════════════════════════════════════════════════════

GRID = 7.5                      # Gaudí's module; all main plan and vault dimensions are multiples | OFF | high
PLUS_Y_COMPASS_AZIMUTH = 315.2  # real compass bearing of model +Y (apse direction)              | OSM | high
CROSSING = (0.0, 0.0)           # origin = crossing centre = Jesus tower axis                     | KEEP | high


def to_runtime(x: float, y: float, z: float = 0.0) -> tuple[float, float, float]:
    """Plan/Blender (x, y, z) -> three.js world (x, y, z)."""
    return (x, z, -y)


def from_runtime(wx: float, wy: float, wz: float) -> tuple[float, float, float]:
    """three.js world (x, y, z) -> plan/Blender (x, y, z)."""
    return (wx, -wz, wy)


# ════════════════════════════════════════════════════════════════════════════════════════════════
# 2. Levels (absolute Z)
# ════════════════════════════════════════════════════════════════════════════════════════════════

Z_NAVE = 1.2                    # basilica floor (nave, transept, ambulatory, cloister, porches)    | KEEP | high (datum)
Z_ALTAR = Z_NAVE + 2.0          # 3.2  presbytery platform "raised two metres above the floor"     | OFF bk9 | high   (old 2.4)
Z_GALLERY = Z_NAVE + 15.0       # 16.2 choir galleries (cantories) "15 metres"; also the tower-base | OFF bk9 | med    (old 14.5)
                                #      tribunes and the bottom of every apostle-tower stair
Z_CHILDREN_CHOIR = Z_NAVE + 15.0  # 16.2 semicircular children's choir above the apse chapels     | OFF bk9 | high
Z_CRYPT = Z_NAVE - 9.0          # -7.8 crypt floor (crypt "10 m below ground level" in 1882; the   | OFF bk5+EST | low (old -5.5)
                                #      nave floor is ~3 m above the mid-block street, see ground)
Z_CRYPT_VAULT_LOW = Z_NAVE - 1.0   # 0.2  crown of crypt chapel / ambulatory vaults (8.0 m high)   | EST | med
Z_CRYPT_VAULT_CENTRAL = Z_ALTAR - 0.8  # 2.4 crown of the raised central crypt vault (10.2 m); its  | OFF bk5+DER | med
                                #      clerestory windows sit in the 2 m step under the presbytery
Z_AISLE_VAULT = Z_NAVE + 30.0   # 31.2 side naves                                                   | OFF | high
Z_NAVE_VAULT = Z_NAVE + 45.0    # 46.2 central nave + central transept                              | OFF | high
Z_CROSSING_VAULT = Z_NAVE + 60.0  # 61.2 crossing                                                   | OFF | high
Z_APSE_VAULT = Z_NAVE + 75.0    # 76.2 apse hyperboloid (old 74.5)                                  | OFF | high
Z_AMBULATORY_VAULT = Z_NAVE + 30.0  # 31.2 apse ambulatory vault (old 42.0)                         | OFF bk9 | high
Z_APSE_TRIFORIUM_VAULT = Z_NAVE + 45.0  # 46.2 apse triforium vault                                 | OFF bk9 | high
Z_APSE_SKYLIGHT_FOOT = Z_NAVE + 60.0    # 61.2 foot of the great apse skylight                      | OFF bk9 | high

# Roof decks the runtime lets you walk on (top of the roof slab over each vault zone).
ROOF_DECK_AISLE = Z_AISLE_VAULT + 0.6     # 31.8  (runtime had 30.0, i.e. below the slab)           | RT+DER | med
ROOF_DECK_NAVE = Z_NAVE_VAULT + 0.6       # 46.8  (runtime had 45.0)                                 | RT+DER | med

# Tower walk levels (runtime contracts kept; the real public levels are noted for the record).
Z_JESUS_DECK = 56.0             # crossing gallery / elevator bottom stop / Evangelist bridges      | KEEP RT | -
                                #   (real: Evangelist bridges and a Jesus level at 85 m, booklet 10 — not adopted)
Z_JESUS_VIEW = 136.0            # Jesus loggia / elevator top stop (real public level 143 m)        | KEEP RT | -
Z_EVANGELIST_DECK = 114.0       # deck inside each Evangelist pinnacle                              | KEEP RT | -
Z_MARY_ENTRY = 77.0             # skybridge Jesus -> Mary; raised from 76.0 to clear the 76.2 apse   | RT+DER | -
                                #   vault crown (the Jesus helix still passes 90° there: phase 0 -> 112°, bridge spans 63..117°)
Z_MARY_DECK = 118.0             # deck in the Mary lantern base                                     | KEEP RT | -
Z_SKYBRIDGE_TRANSEPT = 65.0     # Nativity / Passion inter-tower bridges                            | KEEP RT | -
Z_SKYBRIDGE_GLORY = 72.0        # Glory inter-tower bridges                                         | KEEP RT | -

# ════════════════════════════════════════════════════════════════════════════════════════════════
# 3. Outdoor ground: a gentle plane falling towards Carrer de Mallorca
# ════════════════════════════════════════════════════════════════════════════════════════════════
# The Eixample slopes towards the sea (~2-2.5 %). With the floor fixed at Z_NAVE, a plane through
# -1.8 m at y = 0 puts Carrer de Mallorca 4.6 m and Provença 1.85 m below the floor: the Glory entrance
# ends up "about 5 m above the street" (WIKI: 5 m / 13 ft) and the side façades need ~3 m of steps
# (the Passion façade has a broad stair in reality).
GROUND_Z0 = -1.8                # ground Z at y = 0 (Marina / Sardenya at the crossing axis)        | EST | med
GROUND_SLOPE_Y = 0.022          # dZ/dY: +2.2 % towards Provença, -2.2 % towards Mallorca           | EST (topography) | med
CURB_HEIGHT = 0.15              # carriageway sits this much below the sidewalk                     | EST | med


def ground_z(y: float) -> float:
    """Sidewalk / plaza / forecourt level at plan y (independent of x)."""
    return GROUND_Z0 + GROUND_SLOPE_Y * y


# ════════════════════════════════════════════════════════════════════════════════════════════════
# 4. Basilica body: nave, transept, apse, presbytery
# ════════════════════════════════════════════════════════════════════════════════════════════════

NAVE_HALF_WIDTH = 22.5          # 45 m interior, 5 naves: 15 central + 4 x 7.5                      | OFF/WIKI | high
CENTRAL_NAVE_HALF = 7.5         # central nave 15 m                                                 | OFF | high
INNER_AISLE_OUTER = 15.0        # inner side nave x in [7.5, 15], outer [15, 22.5]                  | OFF | high
NAVE_WALL_THICKNESS = 1.0       # exterior face at |x| = 23.5 (OSM 23.4-24.0)                       | OSM | med
NAVE_BUTTRESS_X = 25.0          # outermost buttress / pinnacle line (OSM bumps 24.9)               | OSM | med
NAVE_NORTH_Y = -15.0            # nave meets the transept                                           | OFF | high
GLORY_INNER_Y = -47.75          # inner face of the Glory wall: 90 m from the axial apse chapel     | OFF+DER | med (old -45)
INTERIOR_LENGTH = 90.0          # Glory inner face -> back of the axial apse chapel                 | OFF | high

TRANSEPT_HALF_LENGTH = 30.0     # 60 m interior; Nativity / Passion inner faces at x = +-30         | OFF/WIKI | high
TRANSEPT_HALF_WIDTH = 15.0      # 30 m, 3 naves: central 15 m (|y| <= 7.5) + 2 x 7.5               | OFF/WIKI | high
TRANSEPT_EXT_WALL_Y = 16.0      # exterior faces of the transept-arm walls (OSM 14.8 N / 15.8 S)    | OSM+DER | med

APSE_CENTER = (0.0, 23.25)      # apse = crypt = Mary tower axis (crypt keystone -> altar -> Mary star | OSM Mary tower 23.3 | med (old: ring 16.5, Mary 22.5)
                                #   are one vertical line, OFF bk5); Villar's apse is off the grid (WIKI)
APSE_PRESBYTERY_RING_R = 7.5    # 10 columns delineate the presbytery (angles 0..180, step 20)      | OFF bk9 + DER | med
APSE_PRESBYTERY_COLUMNS = 10    #                                                                    | OFF bk9 | high
APSE_CHAPELS = 7                # seven apse chapels on the semicircle                              | OFF | high
APSE_CHAPEL_FRONT_R = 15.0      # ambulatory 7.5..15 (= grid), chapels open at r 15 between wall piers | DER | med
APSE_CHAPEL_BACK_R = 19.0       # interior back of the chapels -> y_max = 42.25 (90 m with Glory)   | DER | med (old 18.8 about y 16.5)
APSE_WALL_OUTER_R = 20.25       # outer face of the chapel walls; crypt "40 m wide"                 | OFF bk5 + DER | med
APSE_BUTTRESS_R = 21.25         # buttress / pinnacle tips (OSM outline r 20.2..21.5)               | OSM | med
APSE_SIDE_WALL_X = 19.0         # apse straight part (y 15 -> 23.25): interior side walls            | DER | med
APSE_PIER_ANGLES_DEG = [round(180.0 * k / APSE_CHAPELS, 4) for k in range(APSE_CHAPELS + 1)]  # 8 wall piers between/at the ends of the 7 chapels | DER | med

PRESBYTERY_RADIUS = 9.0         # platform: half-disc r 9 north of the apse centre ...               | EST | med
PRESBYTERY_HALF_WIDTH = 9.0     # ... plus rectangle |x| <= 9 from the front edge to the centre      | EST | med
PRESBYTERY_FRONT_Y = 15.0       # front edge (top step) on the transept's north edge                 | EST | med
PRESBYTERY_STEPS = 12           # 12 risers of 1/6 m, tread 0.30 -> steps occupy y 11.4 .. 15.0      | EST | med
PRESBYTERY_TREAD = 0.30
ALTAR_POS = APSE_CENTER         # main altar on the apse axis (porphyry block 2.72 m long)           | OFF bk5/bk9 | med (old y 18.0)
ALTAR_SIZE = (2.72, 1.6, 1.05)  # length (x), depth (y), height                                     | OFF (length) / EST | med
BALDACHIN_DIAMETER = 5.0        # heptagonal baldachin over the altar                               | OFF bk9 | high
BALDACHIN_Z = Z_ALTAR + 9.0     # 12.2 hanging height                                               | EST | low

# ════════════════════════════════════════════════════════════════════════════════════════════════
# 5. Column grid (foot positions). kind -> material/star: porphyry 12, basalt 10, granite 8, sandstone 6
# ════════════════════════════════════════════════════════════════════════════════════════════════


def _columns() -> list[dict]:
    cols: list[dict] = []

    def add(kind: str, x: float, y: float, z: float, group: str) -> None:
        cols.append({"kind": kind, "x": round(x, 4), "y": round(y, 4), "z": round(z, 4), "group": group})

    for sx in (-1, 1):
        for sy in (-1, 1):
            add("porphyry", sx * 7.5, sy * 7.5, Z_NAVE, "crossing")          # 4 Evangelists      | OFF | high
    for sx in (-1, 1):                                                       # 12 Apostles around the crossing | WIKI ca | med
        for sy in (-1, 1):
            add("basalt", sx * 7.5, sy * 15.0, Z_NAVE, "crossingRing")
            add("basalt", sx * 15.0, sy * 7.5, Z_NAVE, "crossingRing")
            add("basalt", sx * 15.0, sy * 15.0, Z_NAVE, "crossingRing")
    for sx in (-1, 1):
        for y in (-22.5, -30.0, -37.5, -45.0):
            add("granite", sx * 7.5, y, Z_NAVE, "nave")                       # central-nave rows | KEEP grid | high
            add("sandstone", sx * 15.0, y, Z_NAVE, "aisle")                   # aisle rows        | KEEP grid | high
        for sy in (-1, 1):
            add("granite", sx * 22.5, sy * 7.5, Z_NAVE, "transept")           # transept arms     | KEEP | high
    cx, cy = APSE_CENTER
    for k in range(APSE_PRESBYTERY_COLUMNS):                                  # presbytery ring (on the platform)
        a = math.radians(180.0 * k / (APSE_PRESBYTERY_COLUMNS - 1))
        add("granite", cx + APSE_PRESBYTERY_RING_R * math.cos(a), cy + APSE_PRESBYTERY_RING_R * math.sin(a), Z_ALTAR, "presbytery")
    return cols


COLUMNS = _columns()
COLUMN_FALLBACK_RADIUS = {"porphyry": 1.38, "basalt": 1.05, "granite": 0.88, "sandstone": 0.80}  # runtime pre-BVH push-out | KEEP RT | -

# ════════════════════════════════════════════════════════════════════════════════════════════════
# 6. Galleries (choir), tribunes and their stairs — all at Z_GALLERY
# ════════════════════════════════════════════════════════════════════════════════════════════════

GALLERIES = {
    # rectangles (x0, y0, x1, y1) of walkable deck at Z_GALLERY
    "east": (15.6, -42.75, 22.5, -15.6),       # over the outer east side nave                         | OFF+DER | med
    "west": (-22.5, -42.75, -15.6, -15.6),
    "south": (-22.5, -47.75, 22.5, -42.75),    # over the Glory entrance (cantoria)                     | DER | med
    "nativityTribune": (27.4, -15.0, 30.0, 15.0),   # inside the Nativity wall; St Joseph platform; leads into the towers | OFF bk9 + DER | med
    "passionTribune": (-30.0, -15.0, -27.4, 15.0),  # inside the Passion wall; Virgin Mary platform     | OFF bk9 + DER | med
}
# Links between choir galleries and the transept tribunes (straight bridges at Z_GALLERY, half width 1.3)
GALLERY_LINKS = [
    ((21.0, -15.0), (28.7, -13.2)),
    ((-21.0, -15.0), (-28.7, -13.2)),
]
GALLERY_LINK_HALF_WIDTH = 1.3
# Nave -> gallery corner spiral stairs (old (+-19.6, -42.6) and Z 1.2 -> 14.5)
CORNER_STAIRS = [
    {"x": sx * 19.6, "y": -45.0, "rInner": 0.36, "rOuter": 1.92, "z0": Z_NAVE, "z1": Z_GALLERY, "turns": 2.5,
     "phaseDeg": 0.0 if sx > 0 else 180.0, "hole": 1.82}
    for sx in (1, -1)
]                                                                            # DER (moved with the Glory wall) | med

# ════════════════════════════════════════════════════════════════════════════════════════════════
# 7. Crypt (under the apse, same plan; Villar 1882 / Gaudí)
# ════════════════════════════════════════════════════════════════════════════════════════════════
# Plan "30 x 40 m": semicircle north of the apse centre + straight part to the five south chapels.
CRYPT_CENTER = APSE_CENTER                      # concentric with apse and Mary tower                | OFF bk5 | high
CRYPT_FLOOR_Z = Z_CRYPT                         # -7.8                                                | see Z_CRYPT
CRYPT_PIER_RING_R = APSE_PRESBYTERY_RING_R      # 7.5: central-space piers under the presbytery columns | DER | med
CRYPT_PIER_COUNT = APSE_PRESBYTERY_COLUMNS      # 10                                                  | DER | low
CRYPT_CHAPEL_FRONT_R = APSE_CHAPEL_FRONT_R      # 15: ambulatory 7.5..15                               | OFF bk5 + DER | med
CRYPT_CHAPEL_BACK_R = APSE_CHAPEL_BACK_R        # 19: 7 chapels on the semicircle                      | OFF bk5 | med
CRYPT_WALL_OUTER_R = APSE_WALL_OUTER_R          # 20.25 -> crypt 40.5 m wide                           | OFF bk5 | med
CRYPT_HALF_WIDTH = APSE_SIDE_WALL_X             # 19.0 interior half width of the straight part        | DER | med
CRYPT_SOUTH_WALL_Y = 13.25                      # interior back of the 5 south chapels: 30 m deep     | OFF bk5 + DER | med
CRYPT_SOUTH_CHAPEL_DEPTH = 4.0                  # south chapels y 13.25 .. 17.25                      | EST | low
CRYPT_SOUTH_CHAPEL_X = [-19.0, -11.4, -3.8, 3.8, 11.4, 19.0]  # 5 chapels x 7.6 m                     | DER | low
# South chapels west -> east. Booklet 5: centre = altar (Holy Family); on one side the Holy Sacrament
# then Our Lady of Carmel (Gaudí's tomb); on the other Our Lady of Montserrat then the Holy Christ
# (Bocabella's tomb). Which side is which is not stated: Carmel is put on the west, as in the old
# model. | OFF bk5 / EST side | low
CRYPT_SOUTH_CHAPELS = ["carmel", "sacrament", "altar", "montserrat", "holyChrist"]
CRYPT_ALTAR_POS = (0.0, 15.6)                   # altar in the central south chapel, facing north     | OFF bk5 | med
GAUDI_TOMB_POS = (-15.2, 15.25)                 # tomb slab in the Carmel chapel (old (-9.8, 23.5))   | OFF bk5 + EST | low
BOCABELLA_TOMB_POS = (15.2, 15.25)              # Holy Christ chapel                                  | OFF bk5 + EST | low
CRYPT_KEYSTONE = (APSE_CENTER[0], APSE_CENTER[1], Z_CRYPT_VAULT_CENTRAL)  # Annunciation keystone     | OFF bk5 | high (xy)
# Gaudí replaced Villar's stairs by two spiral stairs, one on either side of the semicircle (OFF bk5/bk9).
# They stand in the corners between apse side wall, transept arm and cloister; top door through the
# transept north wall (into the transept north aisle), bottom door through the crypt side wall.
CRYPT_STAIRS = [
    {"side": "west", "x": -22.0, "y": 18.6, "rInner": 0.8, "rOuter": 2.4, "z0": Z_CRYPT, "z1": Z_NAVE,
     "turns": 1.75, "clockwise": True, "phaseDeg": 0.0},      # bottom exit +x (into crypt), top exit -y (transept)
    {"side": "east", "x": 22.0, "y": 18.6, "rInner": 0.8, "rOuter": 2.4, "z0": Z_CRYPT, "z1": Z_NAVE,
     "turns": 1.75, "clockwise": False, "phaseDeg": 180.0},   # bottom exit -x (into crypt), top exit -y (transept)
]                                                                            # OFF (two spirals) / EST (xy) | low
CRYPT_STAIR_TOP_DOOR = {"yWall": (15.0, 16.2), "halfWidth": 1.2}   # opening centred on each stair's x  | DER | med
CRYPT_STAIR_BOTTOM_DOOR = {"xWall": 19.0, "y": 18.6, "halfWidth": 1.0}  # opening at |x| = 19..20.25    | DER | med

# ════════════════════════════════════════════════════════════════════════════════════════════════
# 8. Cloister, corner buildings, Assumption chapel (all floors at Z_NAVE)
# ════════════════════════════════════════════════════════════════════════════════════════════════
# A covered double-façade walk forms a rectangle round the church, passes through the narthex of
# each portal and links the 4 corner buildings (OFF bk4). Widths from the built west wing (OSM).
BLOCK_LINE_NORTH = 52.2         # building line on Carrer de Provença                               | OSM | high
BLOCK_LINE_SOUTH = -60.6        # building line on Carrer de Mallorca                               | OSM | high
BLOCK_LINE_EAST = 65.5          # building line on Carrer de la Marina                              | OSM | med
BLOCK_LINE_WEST = -65.5         # building line on Carrer de Sardenya                               | OSM | med

CLOISTER_WIDTH = 7.5            # outer-face to outer-face (OSM west wing x -39.8..-32.3)           | OSM | med
CLOISTER_CLEAR_WIDTH = 5.5      # walkable width between the inner and outer arcades                | EST | med
CLOISTER_HEIGHT = 9.0           # arcade height above Z_NAVE                                        | KEEP | low
CORNER_SIDE = 18.55             # sacristy: square base 18.55 m, 43 m high incl. 2 m crown           | OFF bk10 | high
CORNER_X0, CORNER_X1 = 22.475, 41.025   # |x| range of the four corner buildings (OSM NW sacristy x -41.0..-21.2) | OSM | high
# South corner buildings (Baptistery, Chapel of Penitence; not built, no published size): they sit
# beside the Glory façade, so they must clear the nave buttresses (|x| <= 25): 16.5 m squares,
# x 25.5 .. 42.0 — smaller than the 18.55 m sacristies.                                    | OFF bk4 (exist) / EST size | low
SOUTH_CORNER_SIDE = 16.5
SOUTH_CORNER_X0, SOUTH_CORNER_X1 = 25.5, 42.0
CORNER_BUILDINGS = {
    # centre (x, y), side, crown height. Sacristies OFF/OSM; OFF bk4: four domes ~40 m on the corners
    "sacristyWest": {"x": -31.75, "y": 42.925, "side": CORNER_SIDE, "top": 43.0, "dome": 40.0},   # built 2016 | OSM+OFF | high
    "sacristyEast": {"x": 31.75, "y": 42.925, "side": CORNER_SIDE, "top": 43.0, "dome": 40.0},    # mirror     | OFF+DER | high
    "penitenceChapel": {"x": -33.75, "y": BLOCK_LINE_SOUTH + SOUTH_CORNER_SIDE / 2, "side": SOUTH_CORNER_SIDE, "top": 40.0, "dome": 40.0},  # west side per ca-wiki | low
    "baptistery": {"x": 33.75, "y": BLOCK_LINE_SOUTH + SOUTH_CORNER_SIDE / 2, "side": SOUTH_CORNER_SIDE, "top": 40.0, "dome": 40.0},        # | low
}
_SOUTH_TOP = BLOCK_LINE_SOUTH + SOUTH_CORNER_SIDE      # -44.1
CLOISTER_WALKS = {
    # (x0, y0, x1, y1) outer faces of each walk; every walk ends inside a corner building -> closed loop
    "east": (32.5, _SOUTH_TOP, 40.0, BLOCK_LINE_NORTH - CORNER_SIDE),       # y -44.1 .. 33.65, through the Nativity porch
    "west": (-40.0, _SOUTH_TOP, -32.5, BLOCK_LINE_NORTH - CORNER_SIDE),     # through the Passion porch
    "north": (-CORNER_X0, BLOCK_LINE_NORTH - CLOISTER_WIDTH, CORNER_X0, BLOCK_LINE_NORTH),   # y 44.7 .. 52.2, through the Assumption chapel
    "south": (-SOUTH_CORNER_X0, BLOCK_LINE_SOUTH, SOUTH_CORNER_X0, BLOCK_LINE_SOUTH + CLOISTER_WIDTH),   # y -60.6 .. -53.1, through the Glory porch
}
ASSUMPTION_CHAPEL = {
    # square 10 m, in the middle of the Provença cloister walk behind the apse, two doors to the street,
    # 30 m hyperboloid dome (OFF bk5). Its street front projects 2.3 m onto the Provença sidewalk so its
    # back clears the axial apse chapel (buttress tip y 44.5).
    "x0": -5.0, "y0": 44.5, "x1": 5.0, "y1": 54.5, "domeTop": Z_NAVE + 30.0, "streetDoorsX": [-2.5, 2.5],
}                                                                            # OFF size / EST position in y | med / low

# ════════════════════════════════════════════════════════════════════════════════════════════════
# 9. Façades, porches and entrance stairs
# ════════════════════════════════════════════════════════════════════════════════════════════════

NATIVITY = {
    # façade/porch zone: from the transept wall (x 30) to the porch front (x 40, turtle columns)
    "wallX": 30.0, "frontX": 40.0, "halfWidth": 16.0, "porchFloorZ": Z_NAVE,                       # OSM | med
    "portals": [  # centre y, opening width; Hope on the left (south), Faith on the right (north) seen from outside
        {"name": "hope", "y": -11.25, "width": 4.4}, {"name": "charity", "y": 0.0, "width": 8.0}, {"name": "faith", "y": 11.25, "width": 4.4},
    ],                                                                                               # OFF names / EST widths | low
    "turtleColumns": [(40.0, -7.5), (40.0, 7.5)],     # palm columns on turtles (OSM 40.2, +-7.3) (old 34.6, +-4.55) | OSM | med
    "cypressY": 0.0,
    "stair": {"x0": 40.0, "x1": 46.0, "halfWidth": 15.5, "topZ": Z_NAVE, "bottomZ": None},          # 20 risers to ground_z(0) | DER | med
    "cloisterPassage": (32.5, 40.0),   # the east cloister walk crosses the porch at ground level (open, >= 3 m clear)
}
PASSION = {
    "wallX": -30.0, "frontX": -52.0, "halfWidth": 23.0, "porchFloorZ": Z_NAVE,                       # OSM (columns to x -50) | med
    # six leaning bone columns of the lower narthex: foot (x, y) -> head (x, y) at the porch roof underside
    "columns": [
        {"foot": (-50.0, sy * 9.0), "head": (-41.0, sy * 5.4)} for sy in (-1, 1)
    ] + [
        {"foot": (-48.5, sy * 16.5), "head": (-41.0, sy * 9.9)} for sy in (-1, 1)
    ] + [
        {"foot": (-45.5, sy * 22.0), "head": (-40.0, sy * 13.2)} for sy in (-1, 1)
    ],                                                                                               # OSM feet / EST heads | low
    "roofZ": (22.7, 26.3),                                                                           # KEEP | -
    "stair": {"x0": -58.0, "x1": -52.0, "halfWidth": 23.0, "topZ": Z_NAVE, "bottomZ": None},         # DER | med
    "cloisterPassage": (-40.0, -32.5),
}
GLORY = {
    "innerY": GLORY_INNER_Y, "wallFrontY": -53.0, "halfWidth": 24.5,                                 # DER/OSM (front -53..-55) | med
    "porch": {"y0": BLOCK_LINE_SOUTH, "y1": -53.0, "x0": -24.5, "x1": 24.5, "floorZ": Z_NAVE},       # DER | med
    "porticoColumnY": -59.6,
    "porticoColumnX": [-22.5, -15.0, -7.5, 0.0, 7.5, 15.0, 22.5],     # "seven large columns" on the grid | WIKI + DER | med
    "doorsX": [-18.75, -11.25, 0.0, 11.25, 18.75],                    # five doors, one per nave (triple at the centre) | WIKI | med
    # bridge over Carrer de Mallorca at floor level, then the descending stair: 57 m from the porch front
    "bridge": {"y0": -81.0, "y1": BLOCK_LINE_SOUTH, "halfWidth": 19.0, "deckZ": Z_NAVE, "soffitZ": Z_NAVE - 1.0},  # WIKI (passes over Mallorca) | med
    "stair": {"y0": BLOCK_LINE_SOUTH - 57.0, "y1": -81.0, "halfWidth": 19.0, "topZ": Z_NAVE, "bottomZ": None,
              "landings": 2},                                                                        # WIKI (57 m) + DER | med
    "monuments": [(-21.0, -112.0), (21.0, -112.0)],   # fire and water at the foot of the stair (old (+-19.5, -64)) | EST | low
}
for _f in (NATIVITY, PASSION):
    _f["stair"]["bottomZ"] = round(ground_z(0.0), 4)
GLORY["stair"]["bottomZ"] = round(ground_z(GLORY["stair"]["y0"]), 4)
GLORY_ENTRANCE_ABOVE_MALLORCA = round(Z_NAVE - ground_z(-70.8), 3)   # 4.56 m (target "about 5 m")


# ════════════════════════════════════════════════════════════════════════════════════════════════
# 10. Towers (18). Heights unchanged (towers pass); plan positions and base radii are the new part.
# ════════════════════════════════════════════════════════════════════════════════════════════════
# Apostle towers: a pair on each side of the façade centre, on the 7.5 grid lines (OSM Nativity:
# inner +-7.65, outer +-15.07; Passion +-7.04 / +-14.19). Passion and Glory use the same grid lines
# (Glory: EST, by analogy, not built). base "r" is the radius at the reference level zRef; adjacent
# pairs are 7.5 m apart, so r_inner + r_outer must stay < 7.5 - 0.3 at every height.

NATIVITY_TOWER_X = 34.0         # OSM 33.6..34.3 (old 31.5)                                         | OSM | med-high
PASSION_TOWER_X = -36.0         # OSM -35.6..-36.6 (old -31.5); Passion towers stand further out    | OSM | med
GLORY_TOWER_Y = -51.75          # 4 m outside the Glory inner face, like the Nativity (old -49.5)    | DER | low
EVANGELIST_OFFSET = 11.5        # (+-11.5, +-11.5); OSM lobes at ~11.6, grid bay centre 11.25        | OSM | med (KEEP)
JESUS_BASE_R = 9.5              # base ~18 m (OFF bk10 "roughly eighteen metres")                    | OFF | med (KEEP)
MARY_BASE_R = 8.75              # base ~18 m (OFF bk10), OSM r 8.73 (old 7.6)                        | OFF+OSM | med-high
EVANGELIST_BASE_R = 5.5         # at 45 m; OSM lobes r ~4.8 at 80 m (old 5.2)                        | OSM+DER | low

APOSTLE_STAIR = {"rMid": 1.38, "tread": 1.04, "rInner": 0.78, "rOuter": 2.05}   # KEEP (towers + runtime) | -
TOWER_SHELL_Z0 = Z_GALLERY + 4.1   # 20.3: apostle shells start above the tower-base doorways (old 18.6 = 14.5 + 4.1) | DER | -
# Passion towers: elliptical section with gain 1.14 — the long axis must be X (perpendicular to the
# façade), otherwise neighbouring shells intersect at the base (spacing 7.5 m).            | EST | low
PASSION_SECTION = {"longAxis": "x", "gain": 1.14}
TOWER_MIN_CLEARANCE = 0.3          # minimum gap between adjacent tower shells at every height | RT | -


def _apostle(key, name, family, x, y, z_top, r, z_ref, stair_top, phase):
    return {
        "key": key, "name": name, "family": family, "kind": "apostle", "x": x, "y": y,
        "zRef": z_ref, "rRef": r, "zTop": z_top, "zApex": z_top + 1.5,
        "stair": {"z0": Z_GALLERY, "z1": stair_top, "rInner": APOSTLE_STAIR["rInner"], "rOuter": APOSTLE_STAIR["rOuter"],
                  "rMid": APOSTLE_STAIR["rMid"], "tread": APOSTLE_STAIR["tread"],
                  "turnsPer10m": 1.68 if family != "glory" else 1.62, "phaseDeg": phase},
    }


def _towers() -> list[dict]:
    t = []
    # Nativity (east), south -> north. Names/heights: OSM (Bernabeu 98, Simó 107, Judes Tadeu 107, Maties 98)
    nx, nphase = NATIVITY_TOWER_X, 180.0     # stairs start on the inner (west) side, from the tribune
    # rRef at zRef (old: outer 3.55 / inner 3.85); chosen so pairs 7.5 m apart keep >= 0.3 m at TOWER_SHELL_Z0
    t.append(_apostle("tower.nativitySE", "Barnabas", "nativity", nx, -15.0, 98.4, 3.30, 26.0, Z_SKYBRIDGE_TRANSEPT, nphase))
    t.append(_apostle("tower.nativityInnerS", "Simon", "nativity", nx, -7.5, 107.0, 3.55, 26.0, Z_SKYBRIDGE_TRANSEPT, nphase))
    t.append(_apostle("tower.nativityInnerN", "Jude Thaddeus", "nativity", nx, 7.5, 107.0, 3.55, 26.0, Z_SKYBRIDGE_TRANSEPT, nphase))
    t.append(_apostle("tower.nativityNE", "Matthias", "nativity", nx, 15.0, 98.4, 3.30, 26.0, Z_SKYBRIDGE_TRANSEPT, nphase))
    # Passion (west), south -> north. OSM: Felip 107, Tomàs 112, Bartomeu 112, Jaume el Menor 107 (old r 3.65 / 3.95)
    px, pphase = PASSION_TOWER_X, 0.0
    t.append(_apostle("tower.passionSW", "Philip", "passion", px, -15.0, 107.4, 3.30, 26.0, Z_SKYBRIDGE_TRANSEPT, pphase))
    t.append(_apostle("tower.passionInnerS", "Thomas", "passion", px, -7.5, 112.2, 3.50, 26.0, Z_SKYBRIDGE_TRANSEPT, pphase))
    t.append(_apostle("tower.passionInnerN", "Bartholomew", "passion", px, 7.5, 112.2, 3.50, 26.0, Z_SKYBRIDGE_TRANSEPT, pphase))
    t.append(_apostle("tower.passionNW", "James the Less", "passion", px, 15.0, 107.4, 3.30, 26.0, Z_SKYBRIDGE_TRANSEPT, pphase))
    # Glory (south), west -> east. Names by booklet-10 order (low confidence); 112 outer / 120 inner (KEEP)
    # (old r 3.75 / 4.10 — reduced because the new spacing is 7.5 m, not 7.6 with a 7.6 m central gap)
    gy, gphase = GLORY_TOWER_Y, 90.0         # stairs start on the inner (north) side, from the south gallery
    t.append(_apostle("tower.gloryW", "Andrew", "glory", -15.0, gy, 112.0, 3.20, 28.0, Z_SKYBRIDGE_GLORY, gphase))
    t.append(_apostle("tower.gloryInnerW", "Peter", "glory", -7.5, gy, 120.0, 3.60, 28.0, Z_SKYBRIDGE_GLORY, gphase))
    t.append(_apostle("tower.gloryInnerE", "Paul", "glory", 7.5, gy, 120.0, 3.60, 28.0, Z_SKYBRIDGE_GLORY, gphase))
    t.append(_apostle("tower.gloryE", "James the Greater", "glory", 15.0, gy, 112.0, 3.20, 28.0, Z_SKYBRIDGE_GLORY, gphase))
    # Evangelists: Blender (-,-) Mark/lion, (-,+) Luke/ox, (+,-) Matthew/angel, (+,+) John/eagle (KEEP assignment)
    e = EVANGELIST_OFFSET
    for key, name, sx, sy, cw in (("tower.mark", "Mark", -1, -1, True), ("tower.luke", "Luke", -1, 1, False),
                                  ("tower.matthew", "Matthew", 1, -1, False), ("tower.john", "John", 1, 1, True)):
        phase = math.degrees(math.atan2(-sy, -sx)) % 360.0   # stair starts facing the 56 m bridge from Jesus
        t.append({"key": key, "name": name, "family": "evangelist", "kind": "evangelist", "x": sx * e, "y": sy * e,
                  "zRef": 45.0, "rRef": EVANGELIST_BASE_R, "zTop": 135.0, "zApex": 146.2,
                  "stair": {"z0": Z_JESUS_DECK, "z1": Z_EVANGELIST_DECK, "rInner": 1.05, "rOuter": 2.35, "rMid": 1.68, "tread": 1.04,
                            "turnsPer10m": 1.35, "phaseDeg": round(phase, 3), "clockwise": cw}})
    t.append({"key": "tower.jesus", "name": "Jesus Christ", "family": "jesus", "kind": "jesus", "x": 0.0, "y": 0.0,
              "zRef": Z_JESUS_DECK, "rRef": JESUS_BASE_R, "zTop": 172.5, "zApex": 183.8,
              "stair": {"z0": Z_JESUS_DECK, "z1": Z_JESUS_VIEW, "rInner": 2.35, "rOuter": 4.15, "rMid": 3.25, "tread": 1.55,
                        "turnsPer10m": 1.1, "phaseDeg": 0.0, "clockwise": True}})
    t.append({"key": "tower.mary", "name": "Virgin Mary", "family": "mary", "kind": "mary", "x": APSE_CENTER[0], "y": APSE_CENTER[1],
              "zRef": 52.0, "rRef": MARY_BASE_R, "zTop": 138.0, "zApex": 140.0,
              "stair": {"z0": Z_MARY_ENTRY, "z1": Z_MARY_DECK, "rInner": 1.70, "rOuter": 3.25, "rMid": 2.45, "tread": 1.25,
                        "turnsPer10m": 1.25, "phaseDeg": 270.0, "clockwise": True}})
    # apostle stair handedness: KEEP the alternating pattern of the old model
    for i, tw in enumerate(t[:12]):
        fam_idx = i % 4
        tw["stair"]["clockwise"] = (fam_idx % 2 == 1) if tw["family"] in ("nativity", "glory") else (fam_idx % 2 == 0)
    return t


TOWERS = _towers()


def tower(key: str) -> dict:
    return next(t for t in TOWERS if t["key"] == key)


def paraboloid_radius(r_ref: float, z_ref: float, z_apex: float, z: float) -> float:
    """Same law as towers_lib.paraboloid_radius: r(z) = r_ref * sqrt((z_apex - z) / (z_apex - z_ref))."""
    return r_ref * math.sqrt(max(0.0, (z_apex - z) / (z_apex - z_ref)))


# ════════════════════════════════════════════════════════════════════════════════════════════════
# 11. Walk network: bridges / skybridges / roof stairs (straight segments, linear height)
# ════════════════════════════════════════════════════════════════════════════════════════════════


def _bridges() -> list[dict]:
    b: list[dict] = []

    def add(name, x0, y0, z0, x1, y1, z1, hw):
        b.append({"name": name, "x0": round(x0, 3), "y0": round(y0, 3), "z0": round(z0, 3),
                  "x1": round(x1, 3), "y1": round(y1, 3), "z1": round(z1, 3), "halfWidth": hw})

    ro = APOSTLE_STAIR["rOuter"] - 0.25   # bridges end 0.25 m inside each stair ring
    # Tower-entry bridges at Z_GALLERY: tribune / south gallery -> start of each apostle stair
    for tw in TOWERS[:12]:
        x, y = tw["x"], tw["y"]
        if tw["family"] == "nativity":
            add(f"entry.{tw['key']}", 28.7, y, Z_GALLERY, x - ro, y, Z_GALLERY, 1.2)
        elif tw["family"] == "passion":
            add(f"entry.{tw['key']}", -28.7, y, Z_GALLERY, x + ro, y, Z_GALLERY, 1.2)
        else:
            add(f"entry.{tw['key']}", x, -46.0, Z_GALLERY, x, y + ro, Z_GALLERY, 1.2)
    # Inter-tower skybridges (stair ring to stair ring) on each façade
    for fam, z in (("nativity", Z_SKYBRIDGE_TRANSEPT), ("passion", Z_SKYBRIDGE_TRANSEPT), ("glory", Z_SKYBRIDGE_GLORY)):
        tws = [tw for tw in TOWERS if tw["family"] == fam]
        for a, c in zip(tws, tws[1:]):
            if fam == "glory":
                add(f"sky.{a['key']}-{c['key']}", a["x"] + ro, a["y"], z, c["x"] - ro, c["y"], z, 1.3)
            else:
                add(f"sky.{a['key']}-{c['key']}", a["x"], a["y"] + ro, z, c["x"], c["y"] - ro, z, 1.3)
    # Jesus crossing gallery (56) -> Evangelist stairs (KEEP geometry: Evangelists unchanged)
    for sx in (-1, 1):
        for sy in (-1, 1):
            add(f"evangelist.{sx:+d}{sy:+d}", sx * 5.0, sy * 5.0, Z_JESUS_DECK, sx * 10.2, sy * 10.2, Z_JESUS_DECK, 1.55)
    # Jesus (76) -> Mary entry ring (Mary moved +0.75 m north)
    add("mary", 0.0, 3.5, Z_MARY_ENTRY, 0.0, APSE_CENTER[1] - 2.7, Z_MARY_ENTRY, 1.65)
    # Roof stair-bridges from the 56 m deck to the centre of the inner-tower skybridge of each façade
    # (ends 0.6 m short of the skybridge axis, i.e. inside its 1.3 m half width)
    add("roof.east", 7.0, 0.0, Z_JESUS_DECK, NATIVITY_TOWER_X - 0.6, 0.0, Z_SKYBRIDGE_TRANSEPT, 1.65)
    add("roof.west", -7.0, 0.0, Z_JESUS_DECK, PASSION_TOWER_X + 0.6, 0.0, Z_SKYBRIDGE_TRANSEPT, 1.65)
    add("roof.south", 0.0, -7.0, Z_JESUS_DECK, 0.0, GLORY_TOWER_Y + 0.6, Z_SKYBRIDGE_GLORY, 1.75)
    # Choir galleries -> transept tribunes
    for (p0, p1) in GALLERY_LINKS:
        add("galleryLink", p0[0], p0[1], Z_GALLERY, p1[0], p1[1], Z_GALLERY, GALLERY_LINK_HALF_WIDTH)
    return b


WALK_BRIDGES = _bridges()

# Glory bridge + stair as walk surfaces (bridge is level; stair is a ramp for the runtime, steps visually)
GLORY_WALK = [
    {"name": "glory.bridge", "x0": 0.0, "y0": GLORY["bridge"]["y1"], "z0": Z_NAVE, "x1": 0.0, "y1": GLORY["bridge"]["y0"], "z1": Z_NAVE,
     "halfWidth": GLORY["bridge"]["halfWidth"]},
    {"name": "glory.stair", "x0": 0.0, "y0": GLORY["stair"]["y1"], "z0": Z_NAVE, "x1": 0.0, "y1": GLORY["stair"]["y0"],
     "z1": GLORY["stair"]["bottomZ"], "halfWidth": GLORY["stair"]["halfWidth"]},
]

# Top landing discs (walkable at z1 for r <= rOuter) so a spiral can be left in any direction at the top
STAIR_TOP_LANDINGS = True                                                     # RT recommendation | -

# Roof decks (x0, y0, x1, y1, z)
ROOF_DECKS = [
    (-8.3, GLORY_INNER_Y, 8.3, NAVE_NORTH_Y, ROOF_DECK_NAVE),
    (-23.5, GLORY_INNER_Y, -8.3, NAVE_NORTH_Y, ROOF_DECK_AISLE),
    (8.3, GLORY_INNER_Y, 23.5, NAVE_NORTH_Y, ROOF_DECK_AISLE),
    (-31.0, -8.3, 31.0, 8.3, ROOF_DECK_NAVE),
    (-31.0, -16.0, 31.0, -8.3, ROOF_DECK_AISLE),
    (-31.0, 8.3, 31.0, 16.0, ROOF_DECK_AISLE),
]                                                                            # DER | med

# ════════════════════════════════════════════════════════════════════════════════════════════════
# 12. City block, streets, plazas
# ════════════════════════════════════════════════════════════════════════════════════════════════
# Cerdà grid: blocks 113.3 m between building lines, 20 m streets, chamfers with 20 m faces (legs
# 14.14). Measured from OSM: the basilica block is 131 m wide (Sardenya to Marina) and 112.8 m deep.
CHAMFER_LEG = 14.14             # | WIKI (Cerdà 20 m chamfer) | high
STREETS = {
    # name: (axis, centre, half width) — carriageway + two sidewalks
    "mallorca": ("y", -70.8, 10.2),        # OSM centreline -70.7, building lines -60.6 / -81.0          | OSM | high
    "provenca": ("y", 62.35, 10.15),       # OSM 62.2; lines 52.2 / 72.5                                  | OSM | high
    "sardenya": ("x", -75.5, 10.0),        # OSM -75.5; lines -85.5 / -65.5                               | OSM | high
    "marina": ("x", 76.5, 11.0),           # OSM 76.8; lines 65.5 / 87.5                                  | OSM | med
    "lepant": ("x", 204.5, 10.0),          # OSM 204.2                                                    | OSM | med
    "sicilia": ("x", -208.8, 10.0),        # OSM -208.1                                                   | OSM | med
    "valencia": ("y", -204.3, 10.0),       # OSM                                                          | OSM | med
    "rossello": ("y", 195.8, 10.0),        # OSM 197.3                                                    | OSM | med
}
SIDEWALK_WIDTH = 5.0            # | EST (Eixample standard 5 m) | med
SAGRADA_BLOCK = {"x0": BLOCK_LINE_WEST, "y0": BLOCK_LINE_SOUTH, "x1": BLOCK_LINE_EAST, "y1": BLOCK_LINE_NORTH, "chamfer": CHAMFER_LEG}
PLACA_GAUDI = {"x0": 87.5, "y0": BLOCK_LINE_SOUTH, "x1": 194.5, "y1": BLOCK_LINE_NORTH, "chamfer": CHAMFER_LEG}  # OSM park/pond | med
PLACA_SAGRADA_FAMILIA = {"x0": -198.8, "y0": BLOCK_LINE_SOUTH, "x1": -85.5, "y1": BLOCK_LINE_NORTH, "chamfer": CHAMFER_LEG}  # OSM park | med
POND = {"x0": 98.4, "y0": -26.7, "x1": 152.9, "y1": 23.3, "cornerRadius": 8.0, "waterBelowGround": 0.45, "copingAboveGround": 0.36}  # OSM pond 54.5 x 50 (old 29 x 34 at x 82.5) | OSM | med
POND_CENTER = (round(0.5 * (POND["x0"] + POND["x1"]), 3), round(0.5 * (POND["y0"] + POND["y1"]), 3))   # (125.65, -1.7)
POND_WATER_Z = round(ground_z(POND["y0"]) - POND["waterBelowGround"], 3)   # level water below the low (south) bank
FOUNTAIN = {"x": POND_CENTER[0], "y": POND_CENTER[1], "r": 2.65}            # KEEP feature, moved with the pond | low
GLORY_AVENUE = {"x0": -25.0, "x1": 25.0, "y0": -194.3, "y1": -81.0}         # planned avenue towards Diagonal (2 blocks; only the first is modelled) | WIKI | med


def _blocks() -> list[dict]:
    """Detailed Eixample blocks around the site: same count/budget as before (12 + 1 split)."""
    n0, n1 = 72.5, 185.8      # north row (beyond Provença)
    s0, s1 = -194.3, -81.0    # south row (beyond Mallorca)
    cols = {"W": (-198.8, -85.5), "C": (-65.5, 65.5), "E": (87.5, 194.5)}
    far = {"FW": (-332.1, -218.8), "FE": (214.5, 327.8)}
    hs = [22.0, 24.0, 21.0, 23.0, 21.0, 22.0, 22.0, 24.0, 21.0, 23.0, 22.0, 24.0, 22.0]
    out = []
    for name, (x0, x1) in cols.items():
        out.append({"name": f"N{name}", "x0": x0, "y0": n0, "x1": x1, "y1": n1})
    out.append({"name": "SW", "x0": cols["W"][0], "y0": s0, "x1": cols["W"][1], "y1": s1})
    out.append({"name": "SC-W", "x0": -65.5, "y0": s0, "x1": GLORY_AVENUE["x0"], "y1": s1})   # split by the Glory avenue
    out.append({"name": "SC-E", "x0": GLORY_AVENUE["x1"], "y0": s0, "x1": 65.5, "y1": s1})
    out.append({"name": "SE", "x0": cols["E"][0], "y0": s0, "x1": cols["E"][1], "y1": s1})
    for name, (x0, x1) in far.items():
        for row, (y0, y1) in (("N", (n0, n1)), ("C", (BLOCK_LINE_SOUTH, BLOCK_LINE_NORTH)), ("S", (s0, s1))):
            out.append({"name": f"{name}{row}", "x0": x0, "y0": y0, "x1": x1, "y1": y1})
    for b, h in zip(out, hs):
        b["height"] = h
        b["chamfer"] = CHAMFER_LEG
        b["courtyardInset"] = 16.0
        # corners [SW, SE, NE, NW]; the half blocks along the Glory avenue are cut straight on the avenue side
        b["chamferCorners"] = {"SC-W": [True, False, False, True], "SC-E": [False, True, True, False]}.get(b["name"], [True, True, True, True])
    return out


CITY_BLOCKS = _blocks()
DISTANT_CITY_MIN_EXTENT = (345.0, 210.0)    # distant massing only beyond |x| > 345 or |y| > 210      | DER | -
WALK_BOUNDS = {"x0": -214.0, "y0": -200.0, "x1": 214.0, "y1": 190.0}          # runtime clamp (old x +-165, runtime z -105..118) | RT | -
MINIMAP_EXTENT = {"x0": -160.0, "y0": -180.0, "x1": 160.0, "y1": 140.0}       # runtime minimap (old x +-118, runtime z -75..105) | RT | -

# Ground kept free of trees, lamps, benches, kiosks, planters (x0, y0, x1, y1): building footprint +
# porches + entrance stairs + Glory bridge/stair + 1 m margin. Street furniture goes on sidewalks only.
KEEP_CLEAR = [
    (-43.0, BLOCK_LINE_SOUTH, 43.0, BLOCK_LINE_NORTH + 2.3 + 1.0),              # cloister rectangle + corner buildings + Assumption chapel
    (NATIVITY["frontX"], -16.5, NATIVITY["stair"]["x1"] + 1.0, 16.5),             # Nativity stair
    (PASSION["stair"]["x0"] - 1.0, -24.0, -41.0, 24.0),                            # Passion porch + stair
    (-20.0, GLORY["stair"]["y0"] - 1.0, 20.0, BLOCK_LINE_SOUTH),                   # Glory bridge + stair
]
STREET_TREE = {"spacing": 9.0, "curbOffset": 1.3}       # trees 1.3 m behind the curb, every ~9 m       | EST | -
STREET_LAMP = {"spacing": 18.0, "curbOffset": 0.7}      # | EST | -

# ════════════════════════════════════════════════════════════════════════════════════════════════
# 13. Viewpoints: spawn, teleports, hotspots (plan frame; z = EYE height for teleports)
# ════════════════════════════════════════════════════════════════════════════════════════════════
EYE = 1.75                      # | KEEP RT


def _eye_ground(y: float) -> float:
    return round(ground_z(y) + EYE, 3)


TELEPORTS = {
    # id: (position xyz, lookAt xyz)  — ids/labels/levels stay as in src/data/teleports.ts
    "placa-gaudi": ((157.0, -2.0, _eye_ground(-2.0)), (34.0, 0.0, 45.0)),          # spawn: east bank, Nativity across the pond
    "main-nave": ((0.0, -40.0, Z_NAVE + EYE), (0.0, 23.25, 21.0)),
    "crossing-altar": ((0.0, -4.0, Z_NAVE + EYE), (0.0, 23.25, 14.0)),
    "gallery-east": ((19.05, -30.0, Z_GALLERY + EYE), (-4.0, 8.0, 19.7)),
    "crypt-gaudi": ((-6.0, 21.0, Z_CRYPT + EYE), (-15.2, 15.5, Z_CRYPT + 0.8)),
    "cloister-east": ((36.25, 20.0, Z_NAVE + EYE), (36.25, 40.0, Z_NAVE + 4.8)),
    "passion-facade": ((-92.0, -5.0, _eye_ground(-5.0)), (-36.0, 0.0, 24.0)),
    "glory-facade": ((0.0, -126.0, _eye_ground(-126.0)), (0.0, -52.0, 34.0)),
    "spiral-stair": ((NATIVITY_TOWER_X + 1.38, -7.5, 34.0), (NATIVITY_TOWER_X, -7.5, 42.0)),   # mid-height in the Simon stair
    "west-spiral-stair": ((PASSION_TOWER_X + 1.38, -7.5, 32.0), (PASSION_TOWER_X, -7.5, 40.0)),  # Thomas stair
    "jesus-elevator": ((0.0, -4.9, Z_JESUS_DECK + EYE), (0.0, 0.0, 58.2)),
    "tower-bridge": ((NATIVITY_TOWER_X, 0.0, Z_SKYBRIDGE_TRANSEPT + EYE), (POND_CENTER[0], POND_CENTER[1], 20.0)),
    "jesus-viewpoint": ((3.6, 3.6, Z_JESUS_VIEW + 1.9), (0.0, 48.0, 122.0)),
    "aerial-overview": ((230.0, -205.0, 150.0), (0.0, 0.0, 74.0)),
}
SPAWN = "placa-gaudi"           # first preset = initial camera                                        | RT | -

HOTSPOTS = {
    # id: (anchor xyz, cameraTarget xyz) — the panel's "fly to" target
    "jesus-tower": ((0.0, 0.0, 156.0), (55.0, -55.0, 142.0)),
    "mary-star": ((APSE_CENTER[0], APSE_CENTER[1], 134.2), (42.0, 54.75, 126.0)),
    "evangelist-towers": ((11.5, 11.5, 129.0), (45.0, 45.0, 122.0)),
    "double-twisted-columns": ((7.5, -7.5, 11.5), (0.0, -20.0, 4.5)),
    "hyperboloid-vaults": ((0.0, -18.75, 42.5), (0.0, -28.0, 3.5)),
    "stained-glass-east": ((22.2, -22.5, 11.0), (11.25, -22.5, 3.0)),
    "stained-glass-west": ((-22.2, -22.5, 11.0), (-11.25, -22.5, 3.0)),
    "high-altar-baldachin": ((ALTAR_POS[0], ALTAR_POS[1], BALDACHIN_Z + 0.8), (0.0, 4.0, 4.2)),
    "nativity-facade": ((NATIVITY["frontX"], 0.0, 24.0), (70.0, -4.0, 2.0)),
    "passion-facade": ((-45.0, 0.0, 16.0), (-66.0, -4.0, 1.0)),
    "glory-facade": ((0.0, -58.0, 20.0), (0.0, -90.0, 2.8)),
    "gaudi-tomb": ((GAUDI_TOMB_POS[0], GAUDI_TOMB_POS[1], Z_CRYPT + 1.0), (-6.0, 21.0, Z_CRYPT + 1.75)),
    "cloister-sacristy": ((31.75, 42.925, 22.0), (50.0, 60.0, 4.0)),
    "gaudi-chain-model": ((-18.6, -39.5, 3.2), (-14.5, -36.5, 2.9)),
    "baptistery-font": ((19.2, -9.8, 3.2), (13.5, -13.5, 2.9)),
    "eixample-pond": ((POND_CENTER[0], POND_CENTER[1], round(ground_z(POND_CENTER[1]) + 2.0, 3)), (157.0, 6.0, round(ground_z(6.0) + 2.0, 3))),
}

# ════════════════════════════════════════════════════════════════════════════════════════════════
# 14. Lights that are placed by coordinates (runtime LightingSystem / SagradaScene, GI bake)
# ════════════════════════════════════════════════════════════════════════════════════════════════
NAVE_WINDOW_BAY_Y = [-18.75, -26.25, -33.75, -41.25]   # light-beam / stained-glass projector bays (old runtime beamZ 15,23,31,39) | DER | med
LIGHTS = {
    "eastProjector": {"pos": (21.4, -26.0, 19.0), "target": (-4.0, -26.0, 1.5)},   # KEEP (nave walls unchanged)
    "westProjector": {"pos": (-21.4, -26.0, 19.0), "target": (4.0, -26.0, 1.5)},
    "naveFill": {"pos": (0.0, -20.0, 24.0)},
    "apseFill": {"pos": (APSE_CENTER[0], APSE_CENTER[1], 14.5)},
    "cryptAccent": {"pos": (0.0, APSE_CENTER[1], Z_CRYPT + 5.0)},
    "starHalo": {"pos": (APSE_CENTER[0], APSE_CENTER[1], 134.2)},
    "crossHalo": {"pos": (0.0, 0.0, 165.0)},
    "interiorProbe": {"pos": (0.0, -22.0, 6.5)},
}
BAKE_LIGHTS = {
    # name: (xyz, colour, power W, radius) — bake_cycles_gi.py
    "Bake_Cross": ((0.0, 0.0, 56.0), (1.0, 0.95, 0.86), 30000, 5.0),                   # KEEP
    "Bake_NaveTop": ((0.0, -28.0, 40.0), (1.0, 0.95, 0.86), 18000, 6.0),
    "Bake_Apse": ((APSE_CENTER[0], APSE_CENTER[1], 30.0), (0.92, 0.92, 1.0), 14000, 5.0),
    "Bake_CryptCenter": ((APSE_CENTER[0], APSE_CENTER[1], Z_CRYPT_VAULT_LOW - 1.0), (1.0, 0.68, 0.32), 3500, 1.8),
    "Bake_CryptTomb": ((GAUDI_TOMB_POS[0], GAUDI_TOMB_POS[1] + 1.0, Z_CRYPT + 2.6), (1.0, 0.64, 0.28), 1500, 1.2),
    "Bake_CryptEast": ((12.0, APSE_CENTER[1], Z_CRYPT + 3.3), (1.0, 0.70, 0.36), 1600, 1.5),
    "Bake_CryptStairW": ((CRYPT_STAIRS[0]["x"], CRYPT_STAIRS[0]["y"], Z_CRYPT + 4.5), (0.85, 0.9, 1.0), 700, 1.2),
    "Bake_CryptStairE": ((CRYPT_STAIRS[1]["x"], CRYPT_STAIRS[1]["y"], Z_CRYPT + 4.5), (0.85, 0.9, 1.0), 700, 1.2),
}

# Runtime zone volumes (plan frame), replacing the hand-tuned numbers in CollisionSystem/SagradaScene
ZONES = {
    "basilicaCenter": (0.0, -4.2),          # centre of the block / building for distance culling (old runtime z 8)
    "crypt": {"center": APSE_CENTER, "r": CRYPT_WALL_OUTER_R, "southY": CRYPT_SOUTH_WALL_Y - 1.25, "zMax": Z_NAVE - 0.5},
    "apse": {"center": APSE_CENTER, "r": APSE_WALL_OUTER_R, "southY": TRANSEPT_HALF_WIDTH},
    "nave": (-NAVE_HALF_WIDTH - 1.0, GLORY_INNER_Y, NAVE_HALF_WIDTH + 1.0, NAVE_NORTH_Y),
    "transept": (-TRANSEPT_HALF_LENGTH - 1.0, -TRANSEPT_HALF_WIDTH, TRANSEPT_HALF_LENGTH + 1.0, TRANSEPT_HALF_WIDTH),
    "presbytery": {"center": APSE_CENTER, "r": PRESBYTERY_RADIUS, "frontY": PRESBYTERY_FRONT_Y,
                   "stepsY": PRESBYTERY_FRONT_Y - PRESBYTERY_STEPS * PRESBYTERY_TREAD},
}

# ════════════════════════════════════════════════════════════════════════════════════════════════
# 15. Export to the web runtime
# ════════════════════════════════════════════════════════════════════════════════════════════════

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
TS_OUT = os.path.join(ROOT_DIR, "src", "data", "layout.generated.ts")


def _xyz(p) -> list[float]:
    return [round(float(v), 4) for v in p]


def build_export() -> dict:
    """Everything the web needs, in the PLAN frame (convert with planToWorld() in src/data/layout.ts)."""
    return {
        "version": LAYOUT_VERSION,
        "frame": {"grid": GRID, "plusYCompassAzimuth": PLUS_Y_COMPASS_AZIMUTH,
                  "note": "plan frame: x east (Nativity), y north (apse), z up; runtime world = (x, z, -y)"},
        "levels": {
            "nave": Z_NAVE, "altar": Z_ALTAR, "gallery": Z_GALLERY, "childrenChoir": Z_CHILDREN_CHOIR,
            "crypt": Z_CRYPT, "cryptVaultLow": Z_CRYPT_VAULT_LOW, "cryptVaultCentral": Z_CRYPT_VAULT_CENTRAL,
            "aisleVault": Z_AISLE_VAULT, "naveVault": Z_NAVE_VAULT, "crossingVault": Z_CROSSING_VAULT, "apseVault": Z_APSE_VAULT,
            "ambulatoryVault": Z_AMBULATORY_VAULT, "apseTriforiumVault": Z_APSE_TRIFORIUM_VAULT, "apseSkylightFoot": Z_APSE_SKYLIGHT_FOOT,
            "roofDeckAisle": ROOF_DECK_AISLE, "roofDeckNave": ROOF_DECK_NAVE,
            "jesusDeck": Z_JESUS_DECK, "jesusView": Z_JESUS_VIEW, "evangelistDeck": Z_EVANGELIST_DECK,
            "maryEntry": Z_MARY_ENTRY, "maryDeck": Z_MARY_DECK, "skybridgeTransept": Z_SKYBRIDGE_TRANSEPT, "skybridgeGlory": Z_SKYBRIDGE_GLORY,
            "eye": EYE,
        },
        "ground": {"z0": GROUND_Z0, "slopeY": GROUND_SLOPE_Y, "curb": CURB_HEIGHT,
                   "gloryEntranceAboveMallorca": GLORY_ENTRANCE_ABOVE_MALLORCA},
        "nave": {"halfWidth": NAVE_HALF_WIDTH, "centralHalf": CENTRAL_NAVE_HALF, "innerAisleOuter": INNER_AISLE_OUTER,
                 "wallThickness": NAVE_WALL_THICKNESS, "buttressX": NAVE_BUTTRESS_X, "northY": NAVE_NORTH_Y,
                 "gloryInnerY": GLORY_INNER_Y, "interiorLength": INTERIOR_LENGTH},
        "transept": {"halfLength": TRANSEPT_HALF_LENGTH, "halfWidth": TRANSEPT_HALF_WIDTH, "extWallY": TRANSEPT_EXT_WALL_Y},
        "apse": {"center": list(APSE_CENTER), "presbyteryRingR": APSE_PRESBYTERY_RING_R, "presbyteryColumns": APSE_PRESBYTERY_COLUMNS,
                 "chapels": APSE_CHAPELS, "chapelFrontR": APSE_CHAPEL_FRONT_R, "chapelBackR": APSE_CHAPEL_BACK_R,
                 "wallOuterR": APSE_WALL_OUTER_R, "buttressR": APSE_BUTTRESS_R, "sideWallX": APSE_SIDE_WALL_X,
                 "pierAnglesDeg": APSE_PIER_ANGLES_DEG},
        "presbytery": {"z": Z_ALTAR, "radius": PRESBYTERY_RADIUS, "halfWidth": PRESBYTERY_HALF_WIDTH, "frontY": PRESBYTERY_FRONT_Y,
                       "steps": PRESBYTERY_STEPS, "tread": PRESBYTERY_TREAD, "altar": list(ALTAR_POS), "altarSize": list(ALTAR_SIZE),
                       "baldachinDiameter": BALDACHIN_DIAMETER, "baldachinZ": BALDACHIN_Z},
        "columns": COLUMNS,
        "columnFallbackRadius": COLUMN_FALLBACK_RADIUS,
        "galleries": {k: list(v) for k, v in GALLERIES.items()},
        "cornerStairs": CORNER_STAIRS,
        "crypt": {"center": list(CRYPT_CENTER), "floorZ": CRYPT_FLOOR_Z, "vaultLowZ": Z_CRYPT_VAULT_LOW, "vaultCentralZ": Z_CRYPT_VAULT_CENTRAL,
                  "pierRingR": CRYPT_PIER_RING_R, "pierCount": CRYPT_PIER_COUNT, "chapelFrontR": CRYPT_CHAPEL_FRONT_R,
                  "chapelBackR": CRYPT_CHAPEL_BACK_R, "wallOuterR": CRYPT_WALL_OUTER_R, "halfWidth": CRYPT_HALF_WIDTH,
                  "southWallY": CRYPT_SOUTH_WALL_Y, "southChapelDepth": CRYPT_SOUTH_CHAPEL_DEPTH, "southChapelX": CRYPT_SOUTH_CHAPEL_X,
                  "southChapels": CRYPT_SOUTH_CHAPELS, "altar": list(CRYPT_ALTAR_POS), "gaudiTomb": list(GAUDI_TOMB_POS),
                  "bocabellaTomb": list(BOCABELLA_TOMB_POS), "keystone": _xyz(CRYPT_KEYSTONE), "stairs": CRYPT_STAIRS,
                  "stairTopDoor": {"yWall": list(CRYPT_STAIR_TOP_DOOR["yWall"]), "halfWidth": CRYPT_STAIR_TOP_DOOR["halfWidth"]},
                  "stairBottomDoor": CRYPT_STAIR_BOTTOM_DOOR},
        "block": {"north": BLOCK_LINE_NORTH, "south": BLOCK_LINE_SOUTH, "east": BLOCK_LINE_EAST, "west": BLOCK_LINE_WEST},
        "cloister": {"width": CLOISTER_WIDTH, "clearWidth": CLOISTER_CLEAR_WIDTH, "height": CLOISTER_HEIGHT, "floorZ": Z_NAVE,
                     "walks": {k: list(v) for k, v in CLOISTER_WALKS.items()}},
        "cornerBuildings": CORNER_BUILDINGS,
        "assumptionChapel": ASSUMPTION_CHAPEL,
        "nativity": NATIVITY,
        "passion": PASSION,
        "glory": GLORY,
        "towers": TOWERS,
        "towerRules": {"shellZ0": TOWER_SHELL_Z0, "minClearance": TOWER_MIN_CLEARANCE, "passionSection": PASSION_SECTION},
        "walkBridges": WALK_BRIDGES + GLORY_WALK,
        "stairTopLandings": STAIR_TOP_LANDINGS,
        "roofDecks": [list(r) for r in ROOF_DECKS],
        "city": {"streets": {k: {"axis": a, "center": c, "halfWidth": h} for k, (a, c, h) in STREETS.items()},
                 "sidewalkWidth": SIDEWALK_WIDTH, "chamferLeg": CHAMFER_LEG,
                 "sagradaBlock": SAGRADA_BLOCK, "placaGaudi": PLACA_GAUDI, "placaSagradaFamilia": PLACA_SAGRADA_FAMILIA,
                 "pond": POND, "pondCenter": list(POND_CENTER), "pondWaterZ": POND_WATER_Z, "fountain": FOUNTAIN,
                 "gloryAvenue": GLORY_AVENUE, "blocks": CITY_BLOCKS, "distantCityMinExtent": list(DISTANT_CITY_MIN_EXTENT),
                 "keepClear": [list(r) for r in KEEP_CLEAR], "streetTree": STREET_TREE, "streetLamp": STREET_LAMP},
        "walkBounds": WALK_BOUNDS,
        "minimapExtent": MINIMAP_EXTENT,
        "spawn": SPAWN,
        "teleports": {k: {"position": _xyz(p), "lookAt": _xyz(l)} for k, (p, l) in TELEPORTS.items()},
        "hotspots": {k: {"position": _xyz(p), "cameraTarget": _xyz(c)} for k, (p, c) in HOTSPOTS.items()},
        "naveWindowBayY": NAVE_WINDOW_BAY_Y,
        "lights": {k: {kk: _xyz(vv) for kk, vv in v.items()} for k, v in LIGHTS.items()},
        "zones": ZONES,
    }


def _normalise(o):
    """Tuples -> lists, floats rounded, so the output is stable and diff-friendly."""
    if isinstance(o, dict):
        return {k: _normalise(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_normalise(v) for v in o]
    if isinstance(o, float):
        r = round(o, 4)
        return 0.0 if r == 0 else r
    return o


def render_ts() -> str:
    body = json.dumps(_normalise(build_export()), indent=2, ensure_ascii=False)
    return (
        "// GENERATED by blender/layout.py — do not edit. Regenerate with `npm run layout`.\n"
        "// Plan frame (Blender): x east (Nativity), y north (apse), z up. Runtime world = (x, z, -y);\n"
        "// use the helpers in ./layout.ts instead of converting by hand.\n"
        "import type { LayoutData } from './layout';\n\n"
        f"export const LAYOUT_DATA: LayoutData = {body};\n"
    )


def validate() -> list[str]:
    """Geometric sanity checks; returns a list of problems (empty = ok)."""
    errs: list[str] = []
    # interior length
    L = APSE_CENTER[1] + APSE_CHAPEL_BACK_R - GLORY_INNER_Y
    if abs(L - INTERIOR_LENGTH) > 0.05:
        errs.append(f"interior length {L:.2f} != {INTERIOR_LENGTH}")
    # towers must not overlap: apostles from TOWER_SHELL_Z0 up, the others from their base level up
    for i, a in enumerate(TOWERS):
        for b in TOWERS[i + 1:]:
            d = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
            z = max(TOWER_SHELL_Z0 if a["kind"] == "apostle" else a["zRef"], TOWER_SHELL_Z0 if b["kind"] == "apostle" else b["zRef"])
            ra = paraboloid_radius(a["rRef"], a["zRef"], a["zApex"], z)
            rb = paraboloid_radius(b["rRef"], b["zRef"], b["zApex"], z)
            if d < ra + rb + TOWER_MIN_CLEARANCE:
                errs.append(f"towers {a['key']} / {b['key']} overlap: d {d:.2f} < {ra:.2f}+{rb:.2f}+{TOWER_MIN_CLEARANCE} at z {z}")
    # the Assumption chapel may use the Provença sidewalk but must leave >= 2.5 m before the curb
    if ASSUMPTION_CHAPEL["y1"] > BLOCK_LINE_NORTH + SIDEWALK_WIDTH - 2.5:
        errs.append("Assumption chapel blocks the Provença sidewalk")
    # apse inside the cloister north walk
    if APSE_CENTER[1] + APSE_BUTTRESS_R > CLOISTER_WALKS["north"][1]:
        errs.append("apse buttresses cross the north cloister walk")
    # cloister closes: every walk end lies inside (or on the face of) a corner building
    def in_corner(x: float, y: float) -> bool:
        for cb in CORNER_BUILDINGS.values():
            h = cb["side"] / 2 + 0.01
            if abs(x - cb["x"]) <= h and abs(y - cb["y"]) <= h:
                return True
        return False
    for k, (x0, y0, x1, y1) in CLOISTER_WALKS.items():
        xm, ym = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        ends = [(xm, y0), (xm, y1)] if k in ("east", "west") else [(x0, ym), (x1, ym)]
        for e in ends:
            if not in_corner(*e):
                errs.append(f"{k} cloister walk end {e} is not inside a corner building")
    # corner buildings clear of the nave buttresses and the apse
    for name, cb in CORNER_BUILDINGS.items():
        h = cb["side"] / 2
        if abs(cb["x"]) - h < NAVE_BUTTRESS_X and cb["y"] - h < NAVE_NORTH_Y and cb["y"] + h > GLORY["wallFrontY"]:
            errs.append(f"{name} collides with the nave buttresses")
        near = max(abs(cb["x"]) - h, 0.0), max(0.0, abs(cb["y"] - APSE_CENTER[1]) - h)
        if cb["y"] > 0 and math.hypot(*near) < APSE_BUTTRESS_R:
            errs.append(f"{name} collides with the apse")
    # buildings inside the block
    for name, cb in CORNER_BUILDINGS.items():
        h = cb["side"] / 2
        if cb["y"] + h > BLOCK_LINE_NORTH + 0.01 or cb["y"] - h < BLOCK_LINE_SOUTH - 0.01:
            errs.append(f"{name} outside the block")
    # crypt stairs clear of the crypt interior and of the transept interior
    for s in CRYPT_STAIRS:
        if abs(s["x"]) - s["rOuter"] < CRYPT_HALF_WIDTH:
            errs.append("crypt stair intrudes into the crypt interior")
        if s["y"] - s["rOuter"] < TRANSEPT_HALF_WIDTH:
            errs.append("crypt stair intrudes into the transept")
    # Glory stair length 57 m
    if abs((GLORY["porch"]["y0"] - GLORY["stair"]["y0"]) - 57.0) > 0.01:
        errs.append("Glory stair is not 57 m from the porch front")
    # nothing of the building in a street
    eps = 0.01
    for nm, (axis, c, hw) in STREETS.items():
        lo, hi = (BLOCK_LINE_SOUTH, BLOCK_LINE_NORTH) if axis == "y" else (BLOCK_LINE_WEST, BLOCK_LINE_EAST)
        if lo + eps < c - hw < hi - eps or lo + eps < c + hw < hi - eps:
            errs.append(f"street {nm} overlaps the block")
    if PASSION["stair"]["x0"] < BLOCK_LINE_WEST or NATIVITY["stair"]["x1"] > BLOCK_LINE_EAST:
        errs.append("transept stairs leave the block")
    # pond inside its plaza
    if not (PLACA_GAUDI["x0"] < POND["x0"] and POND["x1"] < PLACA_GAUDI["x1"]):
        errs.append("pond outside Plaça de Gaudí")
    return errs


def main(argv: list[str]) -> int:
    errs = validate()
    for e in errs:
        print(f"[layout] WARNING: {e}")
    text = render_ts()
    if "--check" in argv:
        try:
            with open(TS_OUT, "r", encoding="utf-8") as f:
                current = f.read()
        except FileNotFoundError:
            current = ""
        if current != text:
            print(f"[layout] {os.path.relpath(TS_OUT, ROOT_DIR)} is stale — run `npm run layout`")
            return 1
        print("[layout] generated file is up to date")
        return 1 if errs else 0
    os.makedirs(os.path.dirname(TS_OUT), exist_ok=True)
    with open(TS_OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"[layout] wrote {os.path.relpath(TS_OUT, ROOT_DIR)} ({len(text) / 1024:.1f} kB), {len(errs)} warnings")
    return 1 if errs else 0


if __name__ == "__main__":
    # Under Blender (`blender --background --python blender/layout.py`) sys.argv carries Blender's own args
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    sys.exit(main(args))
