#!/usr/bin/env python3
"""Portable Hellforge — shared floor-layout data, v11.

Plain Python, NO bpy import - this is the single master for every number
both `forge_floor_tiles_v3.py` (the real Blender/bpy print geometry) and
`forge_floor_layout.py` (the plain-Python planning/SVG renderer) need:
floor dimensions, every socket position, the FDM wedge cut, the smelting
pool outline, the resin quadrant split, molten channels, props, paving.

This file used to be duplicated between the two scripts - forge_floor_
layout.py kept its own copy of the socket list and fell out of sync three
separate times (v6, v7, v9/v10) as things moved in forge_floor_tiles_v3.py.
Splitting the data out here so there is exactly one place any of this can
be wrong, instead of two places that can silently disagree.

Run standalone (`python3 forge_floor_data.py`) to just run every assertion
below and print the paving/joint summary - useful for iterating on a
layout change fast, without waiting on Blender each time.
"""
import math

# ============================================================
# CONFIG (all mm)
# ============================================================
FDM_THICKNESS = 4.0          # structural slab, matches bases.py's own base HEIGHT
RESIN_THICKNESS = 1.2        # thin detail skin, glued on top - ASSUMPTION, correct once test-printed
STEEL_SHEET_THICKNESS = 0.5  # ASSUMPTION - slotted into the FDM slab's underside rebate
STEEL_REBATE_MARGIN = 2.0    # rebate stays inset from the tile edge by this much, so the sheet is hidden

SOCKET_GROWTH = 1.0   # hole diameter = base diameter + this (loose, lift-out fit)

VERTICAL_SEAM_X = [45.0, 195.0]     # global X, resin-skin panel-seam grooves
HORIZONTAL_SEAM_Y = [95.0, 175.0]   # global Y, resin-skin panel-seam grooves
GROOVE_WIDTH = 1.2
GROOVE_DEPTH = 0.5           # must stay under RESIN_THICKNESS

GRATE_RECT = (8.0, 28.0, 162.0, 182.0)   # x0, x1, y0, y1
GRATE_SLOTS = 5
GRATE_SLOT_WIDTH = 2.2
GRATE_DEPTH = 0.8            # must stay under RESIN_THICKNESS

RIVET_DIAMETER = 1.6
RIVET_HEIGHT = 0.8
RIVET_EMBED = 0.3

CHANNEL_WIDTH = 3.0
CHANNEL_DEPTH = 0.4   # must stay under RESIN_THICKNESS
FLOW_WIDTH = 1.2
FLOW_HEIGHT = 0.15
FLOW_EMBED = 0.15

FLOOR_W = 280.0
FLOOR_D = 260.0

# ----------------------------
# v11: the Roaring Furnace moved from (210,190) to (148.5,174) - close
# enough to the wedge-cut apex (140,130) that its own growth-circle
# CONTAINS the apex (with a real 6mm safety margin, not just barely), which
# is what actually guarantees it spans all 3 FDM wedges - the 3 cuts all
# radiate outward FROM that exact point, so any circle containing it gets
# sliced into 3 arcs, one per wedge, automatically. Verified numerically
# (line-circle intersection against every other socket, same technique as
# the smelting pool), not eyeballed - the exact-center point collides with
# Dominator Engine, so this is offset south of it instead.
#
# That move crowded out 4 pieces that used to sit near the old wedge
# center: War Despot, Hobgrot Gong-bearer, Infernal Cohort 4 all had to
# move (15-33mm each, found by a greedy nearest-clear-spot search, same
# approach as every other relocation this project); Infernal Cohort 3 -
# already sitting right at the old wedge center from the v7 rework -
# turned out to already clear the new furnace position, so it didn't need
# to move again.
# ----------------------------
WEDGE_CENTER = (140.0, 130.0)
WEDGE_CUT_BL = (0.0, 260.0)     # bottom-left corner - separates LEFT/BOTTOM
WEDGE_CUT_BR = (280.0, 260.0)   # bottom-right corner - separates RIGHT/BOTTOM
WEDGE_CUT_TOP = (140.0, 0.0)    # top-mid - separates LEFT/RIGHT

FURNACE_NAME = "Roaring Furnace"
FURNACE_STL_PATH = ("/Users/mannil/studio-m/input/spearhead/"
                     "Boil Kettle & Tun System - Dwarven AleWorks - 28mm - 2860871/"
                     "files/Boil_Kettle_and_Tun_System.stl")
FURNACE_HEIGHT = 63.0   # real STL is 62.7mm tall, rounded up - used to size cutters/bounds that need to clear it

# name, center x, center y, diameter. The Furnace is included here again as
# of v11 (it was dropped in v10) - it's still fused permanently into the
# resin terrain (no separate print, no removable base), but it DOES still
# get a socket: an FDM through-hole, a resin through-hole, and its own
# topper - the topper just happens to carry the real furnace body fused
# onto it, since the union happens before stamping, not instead of it.
ALL_SOCKETS = [
    ("Dominator Engine", 70.0, 70.0, 100.0),
    ("Tormentor Bombard", 210.0, 70.0, 80.0),
    ("War Despot", 82.6, 197.7, 32.0),            # v11: moved ~19mm, cleared for the furnace's new spot
    ("Hobgrot Gong-bearer", 126.5, 236.9, 25.0),  # v11: moved ~33mm, same reason
    ("Infernal Cohort 1", 25.0, 140.0, 28.5),
    ("Infernal Cohort 2", 25.0, 200.0, 28.5),
    ("Infernal Cohort 3", 158.0, 106.0, 28.5),    # unchanged in v11 - already clears the new furnace position
    ("Infernal Cohort 4", 198.8, 127.5, 28.5),    # v11: moved ~16mm, same reason
    ("Infernal Cohort 5", 250.0, 130.0, 28.5),
    ("Infernal Cohort 6", 150.0, 30.0, 28.5),
    ("Infernal Cohort 7", 55.0, 230.0, 28.5),
    ("Infernal Cohort 8", 250.0, 30.0, 28.5),
    ("Infernal Cohort 9", 262.0, 236.0, 28.5),
    ("Infernal Cohort 10", 263.0, 90.0, 28.5),
    (FURNACE_NAME, 148.5, 174.0, 100.0),
]
assert len(ALL_SOCKETS) == 15, "expected 14 models + the fused-but-still-socketed Roaring Furnace"


def _which_wedge(px, py):
    cx, cy = WEDGE_CENTER
    ang = math.degrees(math.atan2(py - cy, px - cx)) % 360
    a_bl = math.degrees(math.atan2(WEDGE_CUT_BL[1] - cy, WEDGE_CUT_BL[0] - cx)) % 360
    a_br = math.degrees(math.atan2(WEDGE_CUT_BR[1] - cy, WEDGE_CUT_BR[0] - cx)) % 360
    a_top = math.degrees(math.atan2(WEDGE_CUT_TOP[1] - cy, WEDGE_CUT_TOP[0] - cx)) % 360
    if a_bl <= ang <= a_top:
        return "tile_left"
    elif ang > a_top or ang < a_br:
        return "tile_right"
    else:
        return "tile_bottom"


TILE_NAMES = ["tile_left", "tile_right", "tile_bottom"]
_cx, _cy = WEDGE_CENTER
TILE_OUTLINES = {
    "tile_left":   [(_cx, _cy), (_cx, 0.0), (0.0, 0.0), (0.0, FLOOR_D)],
    "tile_right":  [(_cx, _cy), (FLOOR_W, FLOOR_D), (FLOOR_W, 0.0), (_cx, 0.0)],
    "tile_bottom": [(_cx, _cy), (0.0, FLOOR_D), (FLOOR_W, FLOOR_D)],
}

GRATE_TILE = "tile_left"   # which tile's build gets the grate cutout

TILES = []
for _name in TILE_NAMES:
    TILES.append({
        "name": _name,
        "outline": TILE_OUTLINES[_name],
        "sockets": [s for s in ALL_SOCKETS if _which_wedge(s[1], s[2]) == _name],
        "grate": GRATE_RECT if _name == GRATE_TILE else None,
    })
assert sum(len(t["sockets"]) for t in TILES) == len(ALL_SOCKETS)


def _point_to_segment_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq == 0:
        return ((px - x0) ** 2 + (py - y0) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / seg_len_sq))
    nx, ny = x0 + t * dx, y0 + t * dy
    return ((px - nx) ** 2 + (py - ny) ** 2) ** 0.5


def sockets_straddling_into(tile_name):
    """Sockets NOT owned by this tile whose growth-circle still pokes across
    a seam into this tile's own footprint - a socket near the wedge apex
    (like the Furnace, as of v11) can need a bite cut into all 3 tiles at
    once, not just the 2 a straight seam would allow."""
    outline = TILE_OUTLINES[tile_name]
    n = len(outline)
    extra = []
    for s in ALL_SOCKETS:
        name, cx, cy, d = s
        if _which_wedge(cx, cy) == tile_name:
            continue
        r = d / 2 + SOCKET_GROWTH / 2
        min_dist = min(
            _point_to_segment_dist(cx, cy, outline[i][0], outline[i][1],
                                    outline[(i + 1) % n][0], outline[(i + 1) % n][1])
            for i in range(n)
        )
        if min_dist < r:
            extra.append(s)
    return extra


# ----------------------------
# Smelting pool - a shallow basin around the Roaring Furnace's own
# position, the visible source the molten channels spill out of. Radius
# computed PER ANGLE (line-circle intersection against every other socket
# and the floor edge), same reasoning as before - the furnace's new,
# closer-to-center spot is even tighter than its old one in some
# directions.
# ----------------------------
POOL_CENTER = ALL_SOCKETS[-1][1], ALL_SOCKETS[-1][2]   # same point as the Roaring Furnace
POOL_INNER_RADIUS = 52.5       # just outside the furnace's own growth-circle (50.5mm)
POOL_MAX_RADIUS = 85.0
POOL_CLEARANCE_MARGIN = 4.0
POOL_SAMPLES = 48
POOL_DEPTH = 0.5
POOL_VEIN_COUNT = 6
POOL_VEIN_WIDTH = 1.4
POOL_VEIN_HEIGHT = 0.15
POOL_VEIN_EMBED = 0.15
POOL_VEIN_REACH_FRAC = 0.55


def pool_safe_radius(angle_deg):
    ang = math.radians(angle_deg)
    ux, uy = math.cos(ang), math.sin(ang)
    px, py = POOL_CENTER
    r = POOL_MAX_RADIUS
    for name, cx, cy, d in ALL_SOCKETS:
        if name == FURNACE_NAME:
            continue
        rad = d / 2 + SOCKET_GROWTH / 2 + POOL_CLEARANCE_MARGIN
        ox, oy = px - cx, py - cy
        b = 2 * (ux * ox + uy * oy)
        c = ox * ox + oy * oy - rad * rad
        disc = b * b - 4 * c
        if disc < 0:
            continue
        sq = disc ** 0.5
        for t in ((-b - sq) / 2, (-b + sq) / 2):
            if t > 0:
                r = min(r, t)
    if ux > 0:
        r = min(r, (FLOOR_W - POOL_CLEARANCE_MARGIN - px) / ux)
    elif ux < 0:
        r = min(r, (px - POOL_CLEARANCE_MARGIN) / -ux)
    if uy > 0:
        r = min(r, (FLOOR_D - POOL_CLEARANCE_MARGIN - py) / uy)
    elif uy < 0:
        r = min(r, (py - POOL_CLEARANCE_MARGIN) / -uy)
    return max(POOL_INNER_RADIUS, min(r, POOL_MAX_RADIUS))


POOL_OUTLINE = []
for _i in range(POOL_SAMPLES):
    _ang = _i * 360.0 / POOL_SAMPLES
    _r = pool_safe_radius(_ang)
    _rad = math.radians(_ang)
    POOL_OUTLINE.append((POOL_CENTER[0] + _r * math.cos(_rad), POOL_CENTER[1] + _r * math.sin(_rad)))

# ----------------------------
# Molten-metal channels - v11: rerouted from the furnace's new position.
# Lengths were found the same way as the pool radius (line-circle
# intersection against every socket + the floor edge in each cardinal
# direction), then trimmed back from the safe maximum so they read as
# "stops short" rather than edge-to-edge.
# ----------------------------
MOLTEN_CHANNELS = [
    (148.5, 174.0, 148.5, 129.0),   # north, toward the back/Bombard side (safe max ~52mm, used 45mm)
    (148.5, 174.0, 148.5, 229.0),   # south, toward the front (safe max ~84mm, used 55mm)
    (148.5, 174.0, 95.0, 174.0),    # west, toward the Despot's new position (safe max ~120mm, used 53.5mm)
]

# ----------------------------
# Seam joint - jigsaw-style dovetail tabs on the FDM slab only.
# ----------------------------
TAB_BASE_HALF_WIDTH = 3.0
TAB_TIP_HALF_WIDTH = 5.0
TAB_REACH = 6.0
TAB_EMBED = 1.5
TAB_HOLE_CLEARANCE = 0.3

# v11: the furnace sitting near the apex crowds out tab spots close to
# center on ALL 3 cuts now, not just BR - t-fractions re-searched (not
# hand-picked) for real clearance against the new ALL_SOCKETS, biased
# toward the outer ends of each cut, away from the furnace.
# (name, from_pt, to_pt, male_tile, female_tile, t_fractions_along_the_cut)
WEDGE_JOINTS = [
    ("BL", WEDGE_CENTER, WEDGE_CUT_BL, "tile_left", "tile_bottom", [0.82, 0.90, 0.97]),
    ("BR", WEDGE_CENTER, WEDGE_CUT_BR, "tile_right", "tile_bottom", [0.53, 0.67]),
    ("TOP", WEDGE_CENTER, WEDGE_CUT_TOP, "tile_left", "tile_right", [0.36, 0.55, 0.97]),
]


def cut_along_dir(from_pt, to_pt):
    dx, dy = to_pt[0] - from_pt[0], to_pt[1] - from_pt[1]
    length = (dx ** 2 + dy ** 2) ** 0.5
    return (dx / length, dy / length)


def perp_toward(point, along_dir, target_wedge, probe_dist=5.0):
    ax, ay = along_dir
    for perp in ((-ay, ax), (ay, -ax)):
        probe = (point[0] + perp[0] * probe_dist, point[1] + perp[1] * probe_dist)
        if _which_wedge(*probe) == target_wedge:
            return perp
    raise RuntimeError(f"could not find a perpendicular toward {target_wedge!r} from {point}")


_tab_conservative_radius = (TAB_REACH ** 2 + (TAB_TIP_HALF_WIDTH + TAB_HOLE_CLEARANCE) ** 2) ** 0.5
for _jname, _from_pt, _to_pt, _male, _female, _ts in WEDGE_JOINTS:
    for _t in _ts:
        _px = _from_pt[0] + _t * (_to_pt[0] - _from_pt[0])
        _py = _from_pt[1] + _t * (_to_pt[1] - _from_pt[1])
        for _name, _cx, _cy, _d in ALL_SOCKETS:
            _dist = ((_px - _cx) ** 2 + (_py - _cy) ** 2) ** 0.5
            _min_dist = _d / 2 + SOCKET_GROWTH / 2 + _tab_conservative_radius + 2.0
            assert _dist >= _min_dist, \
                f"joint {_jname} t={_t} too close to {_name!r} ({_dist:.1f} < {_min_dist:.1f}mm)"

# ----------------------------
# Hand-tool props
# ----------------------------
PROP_PLACEMENTS = [
    ("hammer", 15.0, 110.0, 0.0, 8.0),
    ("anvil", 61.7, 135.2, -20.0, 7.0),   # v11: moved off (95,150), 36.5mm - the bigger, closer pool now reaches that spot
    ("tongs", 269.0, 150.0, 20.0, 8.0),   # v11: nudged 1mm off (270,150) - was a knife-edge fit, not a real conflict
    ("hammer", 226.5, 119.5, 60.0, 8.0),  # v11: moved off (245,105), 23.5mm - Cohort 4's new spot claims that area
    ("ingot_pile", 260.0, 60.0, 0.0, 2.5),
    ("chisel", 58.0, 200.2, 45.0, 5.0),   # v11: nudged 2mm off (60,200)
]

# ----------------------------
# Stone-tile paving
# ----------------------------
PAVING_CELL_SIZE = 16.0
PAVING_CIRCLE_DIA = 9.5
PAVING_LINE_WIDTH = 1.0
PAVING_LINE_DEPTH = 0.35
PAVING_CORNER_GAP = 1.5


def clearance_ok(x, y, radius, label):
    for _name, cx, cy, d in ALL_SOCKETS:
        dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
        if dist < d / 2 + SOCKET_GROWTH / 2 + radius:
            return False, f"{label} at ({x:g},{y:g}) too close to socket {_name!r} ({dist:.1f}mm)"
    gx0, gx1, gy0, gy1 = GRATE_RECT
    nearest_x = max(gx0, min(x, gx1))
    nearest_y = max(gy0, min(y, gy1))
    if ((x - nearest_x) ** 2 + (y - nearest_y) ** 2) ** 0.5 < radius:
        return False, f"{label} at ({x:g},{y:g}) too close to the grate"
    for cx0, cy0, cx1, cy1 in MOLTEN_CHANNELS:
        if _point_to_segment_dist(x, y, cx0, cy0, cx1, cy1) < CHANNEL_WIDTH / 2 + radius:
            return False, f"{label} at ({x:g},{y:g}) too close to a molten channel"
    pcx, pcy = POOL_CENTER
    pool_ang = math.degrees(math.atan2(y - pcy, x - pcx))
    if ((x - pcx) ** 2 + (y - pcy) ** 2) ** 0.5 < pool_safe_radius(pool_ang) + radius:
        return False, f"{label} at ({x:g},{y:g}) too close to the smelting pool"
    for _pname, px, py, _rot, prad in PROP_PLACEMENTS:
        if (px, py) == (x, y):
            continue
        if ((x - px) ** 2 + (y - py) ** 2) ** 0.5 < radius + prad:
            return False, f"{label} at ({x:g},{y:g}) too close to prop {_pname!r}"
    return True, ""


for _pname, _px, _py, _prot, _prad in PROP_PLACEMENTS:
    _ok, _msg = clearance_ok(_px, _py, _prad, f"prop {_pname!r}")
    assert _ok, _msg
    assert _prad <= _px <= FLOOR_W - _prad and _prad <= _py <= FLOOR_D - _prad, \
        f"prop {_pname!r} too close to the floor edge"


def _generate_paving_cells():
    radius = PAVING_CELL_SIZE / 2 * 1.02
    edge_margin = PAVING_CELL_SIZE / 2 + 2.0
    candidates = []
    y = edge_margin
    while y <= FLOOR_D - edge_margin + 1e-6:
        x = edge_margin
        while x <= FLOOR_W - edge_margin + 1e-6:
            candidates.append((round(x, 1), round(y, 1)))
            x += PAVING_CELL_SIZE
        y += PAVING_CELL_SIZE

    valid = []
    for cx, cy in candidates:
        ok, _reason = clearance_ok(cx, cy, radius, "paving cell")
        if ok:
            valid.append((cx, cy))
    return valid, len(candidates)


PAVING_PATTERNS = ["square_circle", "diamond", "hatch"]


def paving_pattern_for(cx, cy):
    col = round(cx / PAVING_CELL_SIZE)
    row = round(cy / PAVING_CELL_SIZE)
    return PAVING_PATTERNS[(col + row) % len(PAVING_PATTERNS)]


PAVING_CELLS, _paving_candidate_count = _generate_paving_cells()

# ----------------------------
# Resin quadrant split (v9) - the finished, holed master terrain is cut
# into 4 rectangular pieces for the resin printer's bed, at the floor's
# center point (a plain butt seam, no dovetail joints - see the post).
# ----------------------------
RESIN_SPLIT = (FLOOR_W / 2, FLOOR_D / 2)
RESIN_QUADRANTS = [
    ("nw", (0.0, RESIN_SPLIT[0]), (0.0, RESIN_SPLIT[1])),
    ("ne", (RESIN_SPLIT[0], FLOOR_W), (0.0, RESIN_SPLIT[1])),
    ("sw", (0.0, RESIN_SPLIT[0]), (RESIN_SPLIT[1], FLOOR_D)),
    ("se", (RESIN_SPLIT[0], FLOOR_W), (RESIN_SPLIT[1], FLOOR_D)),
]


if __name__ == "__main__":
    print(f"Floor: {FLOOR_W}x{FLOOR_D}mm, {len(ALL_SOCKETS)} sockets")
    for t in TILES:
        straddling = sockets_straddling_into(t["name"])
        extra = f" (+{len(straddling)} straddling: {[s[0] for s in straddling]})" if straddling else ""
        print(f"  {t['name']}: {len(t['sockets'])} owned sockets{extra}")
    print(f"Pool: center={POOL_CENTER}, inner={POOL_INNER_RADIUS}, "
          f"range {min(pool_safe_radius(a) for a in range(0,360,5)):.1f}-"
          f"{max(pool_safe_radius(a) for a in range(0,360,5)):.1f}mm")
    print(f"Paving: {len(PAVING_CELLS)} of {_paving_candidate_count} candidate cells kept")
    print("All assertions passed.")
