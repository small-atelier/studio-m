"""
Spearhead carry box - one box per Spearhead force (plus hashut_aos, the full Age of Sigmar
Hashut kit on the same footprint), holding the warscroll card stack and that force's game tokens, closed by a slip-fit lid that doubles as a dice tray. Every force shares the
footprint (165.5 x 131.2 x 24.5mm base), the well layout, the lid and the decoration; FORCES holds
what differs: colours, the back row of wells and the lid-top icons.

- box_base: an open-top tray, every pocket cut to the same DEEP_DEPTH (22mm) floor. Left column:
  3 hex-token wells stacked, lift notches through the left wall. Right column: the card slot
  (123x73, front-wall notch) up front, its floor carrying a cards + die icon inlay; behind it the
  force's back row, flush against the back wall (back-wall notches, except the dice well - loose
  dice would roll out). Mythos logo (icon + wordmark) inlaid flush into the underside.
- box_lid: a flat-top slab with a full-height hollow skirt that slides over the base. The
  force's icons on the outside top; the dice_roll icon on the INSIDE face, mirrored so it reads
  correctly with the lid flipped over as a dice tray. Exported flipped, top slab on the bed.
- Khorne only: the Blood Tithe counter - two 0-9 digit wheels on pegs in the back row, thumbed
  round through slots in the back wall (tithe_wheel, print x2).
- Tzeentch only: the Destiny Dice rack - one fixed slot per 12mm die cut into the top face in the
  back row, so each die keeps its rolled value and stands half proud to pick out (lid off).

Every part is two-colour: base + one joined inlay object (flush recess/insert, INSERT_DEPTH deep).

Boolean safety (EXACT solver):
- Each notched well is UNIONED with its own notch first (they overlap by design); the per-well
  solids don't overlap each other, so they're joined into one cutter for a single cut.
- Structural and decorative cuts are separate sequential differences, each with a volume assert.
- Every boolean happens before the bevel - an EXACT cut into a beveled shell corrupts it.

Icons: each force's own icons come from its tokens dir, the box's dice/card icons from icons/ -
all traced by ../icon-trace/extract_icon_contours.py from each folder's icon_sources.json. The
Mythos logo comes from ../card-stand/.

Run (every force, or one):
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_spearhead_box.py
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_spearhead_box.py -- --force skaven
Tithe wheel + test coupon only:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_spearhead_box.py -- --force khorne --wheel-test

Outputs land in output/<force>/, renders in output/<force>/renders/.
"""

import bpy
import bmesh
import json
import math
import mathutils
import os
import sys
import zipfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BLENDER_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
DICE_ROLL_CONTOURS_PATH = os.path.join(SCRIPT_DIR, "icons", "dice_roll_contours.json")
CARDS_CONTOURS_PATH = os.path.join(SCRIPT_DIR, "icons", "cards_contours.json")
DIE_FIVE_CONTOURS_PATH = os.path.join(SCRIPT_DIR, "icons", "die_five_contours.json")
# Mythos logo - same traced contours + font as ../objective-markers/objective_markers_v1.py
MYTHOS_CONTOURS_PATH = os.path.join(_BLENDER_DIR, "card-stand", "logo_contours_v5.json")
MYTHOS_FONT_PATH = os.path.join(_BLENDER_DIR, "card-stand", "BaskervilleBold.ttf")
FONT_PATH = os.path.join(_BLENDER_DIR, "khorne-tokens", "ArialBlack.ttf")   # Tithe wheel digits + label

EXPORT_DIR = os.path.join(SCRIPT_DIR, "output")
RENDER_RESOLUTION = (1400, 1000)

# Anycubic Slicer Next reads its own per-part extruder metadata - set to whichever ACE/AMS slot
# holds each colour on the day you slice.
BASE_EXTRUDER_SLOT = 1
INLAY_EXTRUDER_SLOT = 2

# ============================================================
# FORCES
#
# back_row, left to right from the card slot's left edge, every item flush against the back wall:
#   ("tray", body_w, notch_w)       damage-tray well, tray tip forward (see _tray_outline)
#   ("rect", w, d, notch_w)         rectangular token well
#   ("dice",)                       closed loose-dice well, takes whatever width is left
#   ("wheel",)                      Blood Tithe wheel pocket + peg + pointer (label under the pair)
#   ("rack", cols, rows)            Destiny Dice rack, cols x rows 12mm die slots
# back_row_spread: True spreads the items across the full width with equal gaps instead of
# packing them DIV_T apart.
# lid_center: {"contours", "w", optional "rot" (deg), optional "aspect" (only for raw-list
# contour files, which don't carry their own)}. lid_corners: {"contours", optional "aspect"} -
# LID_CORNER_W wide, LID_CORNER_MARGIN in from each lid edge.
# ============================================================

FORCES = {
    # Helsmiths of Hashut, full Age of Sigmar (Battletome) - DPP hex tokens + Desolation tokens,
    # ../tokens/build_tokens.py
    "hashut_aos": {
        "base_color": (1.0, 1.0, 1.0, 1.0),       # white
        "inlay_color": (0.06, 0.45, 0.12, 1.0),   # green
        "back_row": [("rect", 58.0, 32.0, 40.0), ("rect", 58.0, 32.0, 40.0)],   # 2 Desolation stacks
        "back_row_spread": False,
        "lid_center": {"contours": os.path.join(_BLENDER_DIR, "tokens", "bull_contours.json"),
                       "aspect": 1.0, "w": 46.0},
        "lid_corners": {"contours": os.path.join(_BLENDER_DIR, "tokens", "rune_contours.json"),
                        "aspect": 1.0},
    },
    # Blades of Khorne - hex tokens + damage trays, ../khorne-tokens/build_khorne_tokens.py
    "khorne": {
        "base_color": (0.04, 0.04, 0.04, 1.0),    # black
        "inlay_color": (0.65, 0.03, 0.03, 1.0),   # red
        "back_row": [("tray", 22.0, 16.0), ("tray", 22.0, 16.0), ("wheel",), ("wheel",)],
        "back_row_spread": True,
        "lid_center": {"contours": os.path.join(_BLENDER_DIR, "khorne-tokens", "khorne_contours.json"),
                       "w": 50.0},
        "lid_corners": {"contours": os.path.join(_BLENDER_DIR, "khorne-tokens", "chaos_star_contours.json")},
    },
    # Skaven - hex tokens + single/double damage trays, ../skaven-tokens/build_skaven_tokens.py
    "skaven": {
        "base_color": (0.04, 0.04, 0.04, 1.0),    # black
        "inlay_color": (0.30, 0.80, 0.10, 1.0),   # warpstone green
        # 4 single trays in 2 stacks, the Warp Lightning Cannon's double tray, spare dice
        "back_row": [("tray", 22.0, 16.0), ("tray", 22.0, 16.0), ("tray", 41.4, 32.0), ("dice",)],
        "back_row_spread": False,
        "lid_center": {"contours": os.path.join(_BLENDER_DIR, "skaven-tokens", "rat_head_contours.json"),
                       "w": 90.0, "rot": 90.0},   # turned to run along the lid's long side, top toward -X
        "lid_corners": {"contours": os.path.join(_BLENDER_DIR, "skaven-tokens", "rat_rune_contours.json")},
    },
    # Disciples of Tzeentch - hex tokens + damage trays, ../tzeentch-tokens/build_tzeentch_tokens.py
    "tzeentch": {
        "base_color": (1.0, 1.0, 1.0, 1.0),       # white
        "inlay_color": (0.05, 0.20, 0.55, 1.0),   # blue
        # 5 trays in 2 stacks, the 9 Destiny Dice, spare dice
        "back_row": [("tray", 22.0, 16.0), ("tray", 22.0, 16.0), ("rack", 3, 3), ("dice",)],
        "back_row_spread": False,
        "lid_center": {"contours": os.path.join(_BLENDER_DIR, "tzeentch-tokens", "tzeentch_flame_contours.json"),
                       "w": 70.0},
        "lid_corners": {"contours": os.path.join(_BLENDER_DIR, "khorne-tokens", "chaos_star_contours.json")},
    },
}

# ============================================================
# CONFIG (all mm)
# ============================================================

WALL_T = 2.5     # outer box walls
FLOOR_T = 2.5    # box floor
DIV_T = 2.5      # material left between adjacent wells (not cut - just gaps between cutters)
BEVEL_W = 0.6    # edge comfort/print-release

HOLE_OVERSHOOT = 0.5   # cutter overshoot past whichever face is the "open" one being punched
                        # through (a cutter flush with the surface it cuts is a coincident-face
                        # degenerate case for the EXACT solver)
INSERT_DEPTH = 0.6     # flush-recess depth for every icon inlay, same as the tokens

# --- card slot ---
CARD_W = 120.0          # warscroll card stack footprint
CARD_D = 70.0
CARD_H = 20.0           # stack height - drives DEEP_DEPTH, not the slot footprint
CARD_CLEARANCE = 1.5    # per-side clearance so the stack drops in/out easily
SLOT_CARD_W = CARD_W + 2.0 * CARD_CLEARANCE     # 123.0
SLOT_CARD_D = CARD_D + 2.0 * CARD_CLEARANCE     # 73.0

DEEP_DEPTH = CARD_H + 2.0        # 22.0 - every well is cut to this depth

# --- hex token wells --- (33mm flat-to-flat in every force's tokens script - keep in sync)
HEX_TOKEN_FLAT_TO_FLAT = 33.0
HEX_WELL_CLEARANCE = 1.0
HEX_WELL_FLAT_TO_FLAT = HEX_TOKEN_FLAT_TO_FLAT + 2.0 * HEX_WELL_CLEARANCE      # 35.0
HEX_WELL_POINT_TO_POINT = HEX_WELL_FLAT_TO_FLAT * 2.0 / math.sqrt(3.0)         # ~40.41
HEX_WELL_COUNT = 3              # stacks of up to 7 tokens

# --- damage tray wells --- (tray outline from the tokens scripts' TRAY_BODY_W/TRAY_HEAD_L - a
# pentagon: body + same-width triangular head; keep in sync)
TRAY_BODY_D = 22.0
TRAY_HEAD_L = 18.0
TRAY_WELL_CLEARANCE = 1.0
TRAY_WELL_D = TRAY_BODY_D + TRAY_HEAD_L + 2.0 * TRAY_WELL_CLEARANCE       # 42.0

DIE_SIZE = 16.0         # loose-dice well must fit a 16mm d6

# --- Destiny Dice rack (Tzeentch) --- one square slot per die, cut straight down from the rim into
# solid base. A play-time piece: the dice stand half proud of the rim, so the lid only goes back on
# once they're out.
RACK_DIE = 12.0           # 12mm d6 - 16mm won't fit 3 rows in BACK_ROW_D
RACK_SLOT_W = RACK_DIE + 2.0 * 0.4    # same per-side clearance as the damage tray pocket
RACK_WALL = 3.0           # top face left between slots
RACK_MARGIN = 1.5         # top face from the outer slots to the item's edge
RACK_SLOT_DEPTH = RACK_DIE / 2.0      # half the die sunk, half to grip

# --- lift notches --- through the exterior wall a well is flush against, down to the well floor
CARD_NOTCH_W = 80.0
HEX_NOTCH_W = 32.0     # through the left wall, across the hex's flat side

# --- lid ---
LID_T = 3.0               # top slab thickness
LID_SKIRT = FLOOR_T + DEEP_DEPTH     # full height - the skirt reaches the table
LID_CLEARANCE = 0.3       # per-side slip-fit clearance between the skirt and the base's outer wall
LID_WALL_T = 2.0          # skirt wall thickness
LID_CORNER_MARGIN = 16.0  # inset from each lid edge to a corner icon's center
LID_CORNER_W = 22.0       # the Chaos star's ring and arrow shafts drop to ~0.75mm any smaller
DICE_ROLL_W = 70.0        # inside face, centered

# --- card slot floor icons --- side by side, centered on the slot floor
CARDS_ICON_W = 30.0
DIE_ICON_W = 30.0
FLOOR_ICON_GAP = 12.0

# --- Mythos logo --- underside of the base, centered: icon above the wordmark, same width
MYTHOS_LOGO_W = 100.0
MYTHOS_ASPECT = 376.0 / 720.0   # h/w of the traced icon, 720x720 source
MYTHOS_TEXT = "MYTHOS"
MYTHOS_TEXT_SPACING = 1.1       # touching glyphs corrupt the EXACT solver
MYTHOS_GAP_FRAC = 0.15          # icon-to-text gap, as a fraction of the icon height

# --- Blood Tithe wheels (Khorne) --- two identical 0-9 wheels (tens + units), each spinning on a
# peg printed into a shallow pocket in the base. Digits on the TOP face, read from above against a
# fixed pointer at the front of the pocket.
WHEEL_D = 30.0
WHEEL_T = 4.0
WHEEL_HOLE_D = 6.6        # peg + 0.3mm running clearance per side
PEG_D = 6.0
PEG_TOP_GAP = 0.3         # peg stops this far below the wheel's top face
WHEEL_RIM_NOTCHES = 20    # small half-round grip notches around the edge
WHEEL_RIM_NOTCH_R = 1.2
DIGIT_SIZE = 5.5          # Arial Black, same font as the tokens
DIGIT_RADIUS = 9.5        # digit center distance from the wheel center
DIGIT_SPACING = 1.1       # same tracked spacing as the tokens (touching glyphs corrupt the solver)

WHEEL_POCKET_CLEARANCE = 1.0   # per side, radial
WHEEL_TOP_GAP = 1.0       # wheel top sits this far below the base rim - the closed lid then
                          # keeps it captive on the peg (1mm < the peg's engagement)
WHEEL_POCKET_D = WHEEL_D + 2.0 * WHEEL_POCKET_CLEARANCE
WHEEL_POCKET_DEPTH = WHEEL_T + WHEEL_TOP_GAP
WHEEL_EDGE_INSET = 0.5    # wheel rim this far inside the exterior face - close enough to grip
                          # from outside, while the lid skirt still slides on
WHEEL_GRIP_SLOT_W = 20.0  # full-height slot through the wall at the wheel - the round pocket alone
                          # only breaks through ~8mm wide, too narrow for a thumb
POINTER_W = 7.0           # triangle inlay on the top surface in front of the pocket
POINTER_H = 5.0
POINTER_GAP = 0.8         # from the pocket edge to the pointer tip
TITHE_LABEL = "BLOOD TITHE"    # text on the top surface, centered under the two pointers
TITHE_LABEL_SIZE = 8.0
TITHE_LABEL_GAP = 1.5          # pointer base to label top

# --- wheel test coupon --- one pocket + peg + pointer, rim exposed at the back edge, a quick fit print
COUPON_W = WHEEL_POCKET_D + 10.0
COUPON_D = WHEEL_POCKET_D + 16.0      # extra at the front for the pointer
COUPON_H = WHEEL_POCKET_DEPTH + 2.0

# ============================================================
# LAYOUT (derived) - shared by every force
#
# COLUMN A, the short left end: the 3 hex wells STACKED vertically, flush against the left wall.
# COLUMN B, the long remainder, two rows: the card slot is the FRONT row, the force's back row
# pins to the back wall. Column A is taller than column B's two rows, so the leftover depth is a
# gap between the rows.
# ============================================================

COL_A_W = HEX_WELL_FLAT_TO_FLAT
COL_A_H = HEX_WELL_COUNT * HEX_WELL_POINT_TO_POINT + (HEX_WELL_COUNT - 1) * DIV_T
COL_B_W = SLOT_CARD_W

INT_FOOT_W = COL_A_W + DIV_T + COL_B_W
INT_FOOT_D = COL_A_H

EXT_W = INT_FOOT_W + 2.0 * WALL_T
EXT_D = INT_FOOT_D + 2.0 * WALL_T
BASE_INT_H = DEEP_DEPTH
BASE_EXT_H = FLOOR_T + BASE_INT_H

IX0, IY0 = WALL_T, WALL_T   # interior footprint origin
BACK_WALL_Y = IY0 + INT_FOOT_D
BACK_ROW_D = INT_FOOT_D - SLOT_CARD_D - DIV_T   # depth available behind the card slot

_hex_cx = IX0 + COL_A_W / 2.0
HEX_WELL_CENTERS = [
    (_hex_cx, IY0 + HEX_WELL_POINT_TO_POINT / 2.0 + i * (HEX_WELL_POINT_TO_POINT + DIV_T))
    for i in range(HEX_WELL_COUNT)
]

_col_b_x0 = IX0 + COL_A_W + DIV_T
CARD_SLOT_CENTER = (_col_b_x0 + SLOT_CARD_W / 2.0, IY0 + SLOT_CARD_D / 2.0)

WHEEL_FLOOR_Z = BASE_EXT_H - WHEEL_POCKET_DEPTH
RACK_SLOT_FLOOR_Z = BASE_EXT_H - RACK_SLOT_DEPTH
LID_Z0 = BASE_EXT_H - LID_SKIRT
LID_Z1 = BASE_EXT_H + LID_T

print(f"Box exterior: {EXT_W:.1f} x {EXT_D:.1f} x {BASE_EXT_H:.1f}mm (base); "
      f"lid adds {LID_T:.1f}mm on top, {2*(LID_CLEARANCE+LID_WALL_T):.1f}mm on each footprint side")


def _tray_outline(body_w):
    """Tray pentagon in its own frame: flat end at y=0, tip pointing -Y (tip-forward in the box,
    so the flat end sits against the back wall where the lift notch is). The body is always
    TRAY_BODY_D deep; body_w is its width (wider for a double tray)."""
    hw = body_w / 2.0
    return [(-hw, 0.0), (hw, 0.0), (hw, -TRAY_BODY_D), (0.0, -TRAY_BODY_D - TRAY_HEAD_L),
            (-hw, -TRAY_BODY_D)]


def _rack_span(n):
    """Rack recess width (or depth) for n slots in a row (or column)."""
    return n * RACK_SLOT_W + (n - 1) * RACK_WALL + 2.0 * RACK_MARGIN


def _rack_slot_centers(item, x, w):
    """(x, y) of every slot in a ("rack", cols, rows) item placed at x0=x, width w."""
    cols, rows = item[1], item[2]
    cx, cy = x + w / 2.0, BACK_WALL_Y - _rack_span(rows) / 2.0
    pitch = RACK_SLOT_W + RACK_WALL
    return [(cx + (i - (cols - 1) / 2.0) * pitch, cy + (j - (rows - 1) / 2.0) * pitch)
            for i in range(cols) for j in range(rows)]


def _item_w(item):
    kind = item[0]
    if kind == "tray":
        return item[1] + 2.0 * TRAY_WELL_CLEARANCE
    if kind == "rect":
        return item[1]
    if kind == "wheel":
        return WHEEL_POCKET_D
    if kind == "rack":
        return _rack_span(item[1])
    assert kind == "dice", f"unknown back-row item {item}"
    return None   # takes whatever column B has left


def back_row_layout(force):
    """The force's back row placed left to right across column B. Returns [(item, x0, w)], x0 =
    the item's left edge."""
    items = force["back_row"]
    fixed_w = sum(_item_w(i) or 0.0 for i in items)
    gap = DIV_T
    if force["back_row_spread"]:
        assert all(_item_w(i) is not None for i in items), "a spread back row can't hold a fill item"
        gap = (COL_B_W - fixed_w) / (len(items) - 1)
        assert gap >= DIV_T, "back row items don't fit column B"
    fill_w = COL_B_W - fixed_w - gap * (len(items) - 1)
    layout, x = [], _col_b_x0
    for item in items:
        w = _item_w(item) or fill_w
        layout.append((item, x, w))
        x += w + gap
    assert x - gap <= _col_b_x0 + COL_B_W + 1e-6, "back row overflows column B"
    for item, _, w in layout:
        if item[0] == "dice":
            assert w >= DIE_SIZE + 4.0, f"dice well only {w:.1f}mm wide - back row too full"
        depth = {"tray": TRAY_WELL_D, "rect": item[2] if item[0] == "rect" else 0.0,
                 "dice": BACK_ROW_D, "wheel": WHEEL_POCKET_D + POINTER_GAP + POINTER_H,
                 "rack": _rack_span(item[2]) if item[0] == "rack" else 0.0}[item[0]]
        assert depth <= BACK_ROW_D, f"{item} too deep for the back row"
    return layout


# ============================================================
# GENERIC HELPERS
# ============================================================


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block)


def apply_boolean(target, cutter, operation):
    mod = target.modifiers.new("Bool", 'BOOLEAN')
    mod.object = cutter
    mod.operation = operation
    mod.solver = 'EXACT'
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    return target


def union_onto(base, piece):
    return apply_boolean(base, piece, 'UNION')


def apply_bevel(obj, width, segments=2):
    mod = obj.modifiers.new("Bevel", 'BEVEL')
    mod.width = width
    mod.segments = segments
    mod.limit_method = 'ANGLE'
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def reorient_lid_for_print(obj, cy, cz):
    """180-degree rotation about the X axis, through the given (cy, cz) reference - NOT a Z-only
    flip. Negating just Z (keeping X, Y as-is) is a REFLECTION (determinant -1) and would print
    the icons mirrored; rotating 180 degrees about an axis lying in the XY plane flips Y
    and Z together (determinant +1, a true rotation) so nothing reads backwards once the finished
    print is turned back over to view normally. `cy`/`cz` must be the SAME reference for every
    part of the lid (the shell and the icon inlay) - each object's own individual bounding-box
    center would rotate them about different points and break their alignment with each other."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for v in bm.verts:
        x, y, z = v.co
        v.co = (x, 2.0 * cy - y, 2.0 * cz - z)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def mesh_volume(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    volume = bm.calc_volume()
    bm.free()
    return volume


def nonmanifold_fraction(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bad = sum(1 for e in bm.edges if not e.is_manifold)
    total = len(bm.edges)
    bm.free()
    return bad / total if total else 0.0


def build_box(sx, sy, sz, center, name):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    bmesh.ops.translate(bm, vec=center, verts=bm.verts)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def extrude_xy(points, z0, thickness, name):
    """Build a flat face from a closed (x, y) point loop and extrude it
    along +Z - the footprint-native counterpart of ../tokens/build_tokens.py's
    _extrude_profile (which extrudes an (x, z) loop along Y, the right
    convention for a flat token but not for a box built with Z already as
    the print-up axis)."""
    bm = bmesh.new()
    verts = [bm.verts.new((p[0], p[1], z0)) for p in points]
    face = bm.faces.new(verts)
    result = bmesh.ops.extrude_face_region(bm, geom=[face])
    new_verts = [v for v in result['geom'] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0.0, 0.0, thickness), verts=new_verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def join_objects(objs, name):
    """Merge several non-overlapping pieces into ONE mesh before a single
    boolean call - see ../tokens/build_tokens.py's own join_objects docstring for
    why (EXACT-solver corruption on long boolean chains)."""
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    objs[0].name = name
    return objs[0]


def dedupe_closed_loop(points, tol=1e-9):
    """See ../tokens/build_tokens.py's own dedupe_closed_loop - traced contours
    repeat their first point as their last; left in, that's a degenerate
    zero-length edge that corrupts the EXACT solver."""
    if len(points) > 1:
        x0, y0 = points[0]
        x1, y1 = points[-1]
        if abs(x0 - x1) < tol and abs(y0 - y1) < tol:
            return points[:-1]
    return points


def hex_points(flat_to_flat):
    """Pointy-top regular hexagon outline (points at top/bottom), same
    shape/orientation as ../tokens/build_tokens.py's hex_points - kept consistent
    so a well reads as "the same hex, just bigger" next to the token
    itself, not a different orientation."""
    r = flat_to_flat / math.sqrt(3.0)
    pts = []
    for k in range(6):
        angle = math.radians(90.0 + 60.0 * k)
        pts.append((r * math.cos(angle), r * math.sin(angle)))
    return pts


def rect_points(w, h):
    hw, hh = w / 2.0, h / 2.0
    return [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]


def front_notch_points(center_x, width, well_center_y):
    """A lift-notch cutter: a simple rectangle centered on center_x, running from just past the
    box's own front wall face (y=-HOLE_OVERSHOOT, breaching through to the exterior) back to the
    well's own center_y - guaranteed to land well inside the well's already-cut interior (not
    just grazing its front tip), so unioning the two together (see build_base) can't leave a
    degenerate near-zero overlap for the EXACT solver to trip on."""
    hw = width / 2.0
    return [(center_x - hw, -HOLE_OVERSHOOT), (center_x + hw, -HOLE_OVERSHOOT),
            (center_x + hw, well_center_y), (center_x - hw, well_center_y)]


def left_notch_points(center_y, width, well_center_x):
    """Same idea as front_notch_points, breaching the LEFT wall instead (x=-HOLE_OVERSHOOT)."""
    hw = width / 2.0
    return [(-HOLE_OVERSHOOT, center_y - hw), (well_center_x, center_y - hw),
            (well_center_x, center_y + hw), (-HOLE_OVERSHOOT, center_y + hw)]


def back_notch_points(center_x, width, well_center_y):
    """Same idea again, breaching the BACK wall. Targets EXT_D (the true exterior face), NOT
    BACK_WALL_Y - BACK_WALL_Y is only the INTERIOR boundary where the back wall's inner face sits;
    targeting it only nicks into the wall and never breaks through."""
    hw = width / 2.0
    return [(center_x - hw, well_center_y), (center_x + hw, well_center_y),
            (center_x + hw, EXT_D + HOLE_OVERSHOOT), (center_x - hw, EXT_D + HOLE_OVERSHOOT)]


def load_contours(path, aspect=None):
    """Returns (polygons, aspect h/w). ../icon-trace/extract_icon_contours.py output carries its
    own aspect; the older raw-list files (the Hashut icons) need it passed in."""
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        assert aspect is not None, f"{path}: raw contour list needs an explicit aspect"
        return data, aspect
    return data["polygons"], data["aspect"]


def build_icon_solid_xy(contours, icon_w, icon_h, center_x, center_y, z0, thickness, name_prefix,
                        mirror_y=False):
    """XY-plane counterpart of ../tokens/build_tokens.py's build_icon_solid - same
    per-contour chained union/difference pattern (proven there), just
    footprint-oriented. u -> x, v -> y (v=0 is the icon's own bottom
    edge); mirror_y flips v for a face that's read from the other side."""
    icon_x0 = center_x - icon_w / 2.0
    icon_y0 = center_y - icon_h / 2.0

    rings = []
    for c in contours:
        pts = [(icon_x0 + u * icon_w, icon_y0 + ((1.0 - v) if mirror_y else v) * icon_h)
               for u, v in c["points"]]
        pts = dedupe_closed_loop(pts)
        area = 0.5 * abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                             for i in range(len(pts))))
        rings.append((area, c["hole"], pts))
    assert any(not hole for _, hole, _ in rings), f"{name_prefix}: traced icon has no outer contours"

    # Largest ring first: an enclosing ring is always bigger than anything nested inside it, so
    # applying union/difference in descending-area order builds any nesting depth correctly - an
    # island inside a hole (a die's pips, the filled card back) is re-added after its hole is
    # cut. All-outers-then-all-holes would cut those islands away with their enclosing hole.
    rings.sort(key=lambda r: -r[0])
    area0, hole0, pts0 = rings[0]
    assert not hole0, f"{name_prefix}: largest contour is a hole"
    solid = extrude_xy(pts0, z0, thickness, f"{name_prefix}_0")
    for i, (_, hole, pts) in enumerate(rings[1:], start=1):
        if hole:
            cutter = extrude_xy(pts, z0 - HOLE_OVERSHOOT, thickness + 2 * HOLE_OVERSHOOT,
                                f"{name_prefix}_hole_{i}")
            apply_boolean(solid, cutter, 'DIFFERENCE')
        else:
            union_onto(solid, extrude_xy(pts, z0, thickness, f"{name_prefix}_{i}"))

    return solid


def apply_color(obj, name, rgba):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = rgba
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def compute_scene_bounds():
    xs, ys, zs = [], [], []
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ mathutils.Vector(corner)
            xs.append(world_corner.x)
            ys.append(world_corner.y)
            zs.append(world_corner.z)
    if not xs:
        return mathutils.Vector((0.0, 0.0, 0.0)), 10.0
    center = mathutils.Vector((
        (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2,
    ))
    size = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    return center, size


def render_top(render_dir, name, elev_deg=55.0, from_below=False, bounds_objs=None):
    """Camera above (or, with from_below, below) the scene, tilted at
    elev_deg off horizontal (not a pure top-down flat shot - a slight
    angle actually shows well depths/skirt geometry; straight-down ortho
    on a mostly-flat box would just read as a silhouette). `bounds_objs`
    restricts the framing to specific objects (e.g. the base alone) even
    if other hidden objects are still in the scene."""
    if bounds_objs is not None:
        xs, ys, zs = [], [], []
        for obj in bounds_objs:
            for corner in obj.bound_box:
                wc = obj.matrix_world @ mathutils.Vector(corner)
                xs.append(wc.x); ys.append(wc.y); zs.append(wc.z)
        center = mathutils.Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
        size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
    else:
        center, size = compute_scene_bounds()
    distance = size * 1.4
    elev = math.radians(elev_deg)
    z_sign = -1.0 if from_below else 1.0
    cam_data = bpy.data.cameras.new("RenderCam")
    cam_data.type = 'ORTHO'
    # ortho_scale spans the render's WIDER axis - scale up by the aspect ratio so the object's
    # extent fits the narrower (vertical) axis too, not just the horizontal one
    cam_data.ortho_scale = size * 1.15 * RENDER_RESOLUTION[0] / RENDER_RESOLUTION[1]
    cam = bpy.data.objects.new("RenderCam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = center + mathutils.Vector(
        (0.0, -distance * math.cos(elev), z_sign * distance * math.sin(elev)))
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam

    light_data = bpy.data.lights.new("RenderLight", type='SUN')
    light_data.energy = 3.0
    light = bpy.data.objects.new("RenderLight", light_data)
    bpy.context.collection.objects.link(light)
    light.location = center + mathutils.Vector((distance * 0.4, -distance * 0.6, z_sign * distance))
    light.rotation_euler = (center - light.location).to_track_quat('-Z', 'Y').to_euler()

    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = RENDER_RESOLUTION
    scene.render.filepath = os.path.join(render_dir, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {scene.render.filepath}")
    bpy.data.objects.remove(cam, do_unlink=True)
    bpy.data.objects.remove(light, do_unlink=True)


def export_stl(obj, path):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"Exported {path}")


def export_3mf(parts, path):
    """Same generic multi-object colored 3MF writer as ../tokens/build_tokens.py's
    export_3mf - see that function's docstring."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    colors, color_index = [], {}

    def color_id(rgba):
        key = tuple(round(c, 4) for c in rgba)
        if key not in color_index:
            color_index[key] = len(colors)
            colors.append(key)
        return color_index[key]

    objects_xml, build_items = [], []
    next_id = 2
    for obj, rgba, name in parts:
        mesh = obj.data
        mesh.calc_loop_triangles()
        mw = obj.matrix_world
        verts_xml = "".join(f'<vertex x="{co.x:.5f}" y="{co.y:.5f}" z="{co.z:.5f}"/>'
                             for co in (mw @ v.co for v in mesh.vertices))
        tris_xml = "".join(f'<triangle v1="{t.vertices[0]}" v2="{t.vertices[1]}" v3="{t.vertices[2]}"/>'
                            for t in mesh.loop_triangles)
        obj_id = next_id
        next_id += 1
        objects_xml.append(
            f'<object id="{obj_id}" name="{name}" type="model" pid="1" pindex="{color_id(rgba)}">'
            f'<mesh><vertices>{verts_xml}</vertices><triangles>{tris_xml}</triangles></mesh></object>')
        build_items.append(f'<item objectid="{obj_id}"/>')

    colors_xml = "".join(
        f'<m:color color="#{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}{int(a*255):02X}"/>'
        for (r, g, b, a) in colors)
    model_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
        'xmlns:m="http://schemas.microsoft.com/3dmanufacturing/material/2015/02">'
        f'<resources><m:colorgroup id="1">{colors_xml}</m:colorgroup>'
        f'{"".join(objects_xml)}</resources><build>{"".join(build_items)}</build></model>')
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
        '</Types>')
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("3D/3dmodel.model", model_xml)
    print(f"Exported {path}")


def export_project_3mf(parts, path):
    """Same Anycubic Slicer Next project-3mf flavor as ../tokens/build_tokens.py's
    export_project_3mf (extruder-per-part metadata, not the standard 3MF
    color hint - see that function's docstring for why)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    leaf_objects_xml, components_xml, parts_config_xml = [], [], []
    next_id = 1
    for obj, name, slot in parts:
        mesh = obj.data
        mesh.calc_loop_triangles()
        mw = obj.matrix_world
        verts_xml = "".join(f'<vertex x="{co.x:.5f}" y="{co.y:.5f}" z="{co.z:.5f}"/>'
                             for co in (mw @ v.co for v in mesh.vertices))
        tris_xml = "".join(f'<triangle v1="{t.vertices[0]}" v2="{t.vertices[1]}" v3="{t.vertices[2]}"/>'
                            for t in mesh.loop_triangles)
        leaf_id = next_id
        next_id += 1
        leaf_objects_xml.append(
            f'<object id="{leaf_id}" type="model"><mesh><vertices>{verts_xml}</vertices>'
            f'<triangles>{tris_xml}</triangles></mesh></object>')
        components_xml.append(f'<component objectid="{leaf_id}"/>')
        parts_config_xml.append(
            f'<part id="{leaf_id}" subtype="normal_part"><metadata key="name" value="{name}.stl"/>'
            f'<metadata key="extruder" value="{slot}"/></part>')
    parent_id = next_id
    model_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        f'<resources>{"".join(leaf_objects_xml)}<object id="{parent_id}" type="model">'
        f'<components>{"".join(components_xml)}</components></object></resources>'
        f'<build><item objectid="{parent_id}"/></build></model>')
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
        '</Types>')
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Target="/3D/3dmodel.model" Id="rel-1" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    model_settings = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<config>'
        f'<object id="{parent_id}"><metadata key="name" value="plate"/>'
        f'{"".join(parts_config_xml)}</object></config>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("3D/3dmodel.model", model_xml)
        zf.writestr("Metadata/model_settings.config", model_settings)
    print(f"Exported {path}")



def offset_convex_polygon(points, d):
    """Grow a CONVEX polygon outward by d on every edge (a true constant-width offset, not a
    uniform scale - for the tray pentagon a scale would give the well uneven clearance). Each edge
    line is pushed out along its outward normal and adjacent lines are re-intersected."""
    n = len(points)
    area2 = sum(points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1]
                for i in range(n))
    sign = 1.0 if area2 > 0 else -1.0   # CCW -> outward normal is (dy, -dx)
    lines = []
    for i in range(n):
        (x1, y1), (x2, y2) = points[i], points[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        nx, ny = sign * dy / length, -sign * dx / length
        lines.append(((x1 + nx * d, y1 + ny * d), (dx, dy)))
    out = []
    for i in range(n):
        (px, py), (ax, ay) = lines[i - 1]
        (qx, qy), (bx, by) = lines[i]
        denom = ax * by - ay * bx
        t = ((qx - px) * by - (qy - py) * bx) / denom
        out.append((px + t * ax, py + t * ay))
    return out


# ============================================================
# MYTHOS LOGO
# ============================================================


def build_wordmark_xy(text, width, center_x, z0, thickness, name):
    """Text prism read from above, scaled to `width`, its bounding box centered on (center_x, 0).
    Returns (obj, height)."""
    curve = bpy.data.curves.new(f"{name}_curve", type='FONT')
    curve.body = text
    curve.font = bpy.data.fonts.load(MYTHOS_FONT_PATH, check_existing=True)
    curve.size = 10.0
    curve.space_character = MYTHOS_TEXT_SPACING
    curve.extrude = thickness / 2.0
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-3)
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    scale = width / (max(xs) - min(xs))
    mid_x, mid_y = (max(xs) + min(xs)) / 2.0, (max(ys) + min(ys)) / 2.0
    for v in bm.verts:
        v.co.x = center_x + (v.co.x - mid_x) * scale
        v.co.y = (v.co.y - mid_y) * scale
        v.co.z += z0 + thickness / 2.0   # the curve's own extrude is centered on z=0
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    return obj, (max(ys) - min(ys)) * scale


def build_mythos_logo(center_x, center_y, z0, thickness, name):
    """Icon above the MYTHOS wordmark, both MYTHOS_LOGO_W wide, for the base's underside: mirrored
    (y-flip + reverse_faces, not recalc_face_normals - that can invert one shell of a multi-shell
    mesh) so it reads correctly with the box turned over its front edge."""
    icon_h = MYTHOS_LOGO_W * MYTHOS_ASPECT
    gap = MYTHOS_GAP_FRAC * icon_h
    text, text_h = build_wordmark_xy(MYTHOS_TEXT, MYTHOS_LOGO_W, center_x, z0, thickness, f"{name}_text")
    total_h = icon_h + gap + text_h
    assert total_h < EXT_D - 2.0 * WALL_T and MYTHOS_LOGO_W < EXT_W - 2.0 * WALL_T, "Mythos logo too big"
    text.data.transform(mathutils.Matrix.Translation((0.0, center_y - total_h / 2.0 + text_h / 2.0, 0.0)))
    with open(MYTHOS_CONTOURS_PATH) as f:
        contours = json.load(f)
    icon = build_icon_solid_xy(contours, MYTHOS_LOGO_W, icon_h, center_x, center_y + total_h / 2.0 - icon_h / 2.0,
                               z0, thickness, f"{name}_icon")
    logo = join_objects([icon, text], name)

    bm = bmesh.new()
    bm.from_mesh(logo.data)
    for v in bm.verts:
        v.co.y = 2.0 * center_y - v.co.y
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(logo.data)
    bm.free()
    return logo


# ============================================================
# BASE
# ============================================================


def build_base(force):
    layout = back_row_layout(force)
    wheel_centers = [(x + w / 2.0, EXT_D - WHEEL_EDGE_INSET - WHEEL_D / 2.0)
                     for item, x, w in layout if item[0] == "wheel"]

    shell = build_box(EXT_W, EXT_D, BASE_EXT_H, (EXT_W / 2.0, EXT_D / 2.0, BASE_EXT_H / 2.0), "base_shell")
    prev_vol = mesh_volume(shell)

    # 1) Wells - each notched well is UNIONED with its own notch first (they overlap by design),
    # then the per-well solids (which don't overlap each other) are joined for one combined cut.
    cutters = []
    ccx, ccy = CARD_SLOT_CENTER
    card_pts = [(ccx + x, ccy + y) for x, y in rect_points(SLOT_CARD_W, SLOT_CARD_D)]
    card_pocket = extrude_xy(card_pts, FLOOR_T, DEEP_DEPTH + HOLE_OVERSHOOT, "card_slot_cut")
    card_notch = extrude_xy(front_notch_points(ccx, CARD_NOTCH_W, ccy), FLOOR_T, DEEP_DEPTH, "card_notch_cut")
    cutters.append(union_onto(card_pocket, card_notch))

    for cx, cy in HEX_WELL_CENTERS:
        pts = [(cx + x, cy + y) for x, y in hex_points(HEX_WELL_FLAT_TO_FLAT)]
        pocket = extrude_xy(pts, FLOOR_T, DEEP_DEPTH + HOLE_OVERSHOOT, "hex_well_cut")
        notch = extrude_xy(left_notch_points(cy, HEX_NOTCH_W, cx), FLOOR_T, DEEP_DEPTH, "hex_notch_cut")
        cutters.append(union_onto(pocket, notch))

    for item, x, w in layout:
        kind, cx = item[0], x + w / 2.0
        if kind == "tray":
            well_outline = offset_convex_polygon(_tray_outline(item[1]), TRAY_WELL_CLEARANCE)
            # _tray_outline's flat end is at y=0; shift so the offset well's back edge lands on the wall
            pts = [(cx + px, BACK_WALL_Y - TRAY_WELL_CLEARANCE + py) for px, py in well_outline]
            pocket = extrude_xy(pts, FLOOR_T, DEEP_DEPTH + HOLE_OVERSHOOT, "tray_well_cut")
            notch = extrude_xy(back_notch_points(cx, item[2], BACK_WALL_Y - TRAY_WELL_D / 2.0),
                               FLOOR_T, DEEP_DEPTH, "tray_notch_cut")
            cutters.append(union_onto(pocket, notch))
        elif kind == "rect":
            cy = BACK_WALL_Y - item[2] / 2.0
            pts = [(cx + px, cy + py) for px, py in rect_points(w, item[2])]
            pocket = extrude_xy(pts, FLOOR_T, DEEP_DEPTH + HOLE_OVERSHOOT, "rect_well_cut")
            notch = extrude_xy(back_notch_points(cx, item[3], cy), FLOOR_T, DEEP_DEPTH, "rect_notch_cut")
            cutters.append(union_onto(pocket, notch))
        elif kind == "dice":
            cy = BACK_WALL_Y - BACK_ROW_D / 2.0
            pts = [(cx + px, cy + py) for px, py in rect_points(w, BACK_ROW_D)]
            # No lift notch - loose dice would roll out through it; they tip out instead.
            cutters.append(extrude_xy(pts, FLOOR_T, DEEP_DEPTH + HOLE_OVERSHOOT, "dice_well_cut"))
        elif kind == "rack":
            # No lift notch - the dice stand half proud and are picked straight out.
            for k, (sx, sy) in enumerate(_rack_slot_centers(item, x, w)):
                cutters.append(extrude_xy([(sx + px, sy + py) for px, py in rect_points(RACK_SLOT_W, RACK_SLOT_W)],
                                          RACK_SLOT_FLOOR_Z, RACK_SLOT_DEPTH + HOLE_OVERSHOOT, f"rack_slot_{k}_cut"))
    # Tithe wheel pockets - each breaks through the back wall, exposing the wheel rim for gripping
    for wx, wy in wheel_centers:
        cutters.append(wheel_pocket_cutter(wx, wy, BASE_EXT_H, EXT_D))

    apply_boolean(shell, join_objects(cutters, "well_cutters"), 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_vol, f"base: well cut corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"

    inserts, icon_cutters = [], []
    if wheel_centers:
        # Wheel pegs - one combined union (they don't touch each other)
        prev_vol = mesh_volume(shell)
        union_onto(shell, join_objects([build_peg(wx, wy, WHEEL_FLOOR_Z) for wx, wy in wheel_centers], "pegs"))
        vol = mesh_volume(shell)
        assert vol > prev_vol, f"base: peg union corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"

        # Pointer in front of each wheel, the label centered under the pair
        label_x = sum(wx for wx, _ in wheel_centers) / len(wheel_centers)
        label_top = wheel_centers[0][1] - WHEEL_POCKET_D / 2.0 - POINTER_GAP - POINTER_H - TITHE_LABEL_GAP
        label_ins = build_text_xy(TITHE_LABEL, TITHE_LABEL_SIZE, BASE_EXT_H - INSERT_DEPTH, INSERT_DEPTH,
                                  label_x, 0.0, 0.0, "tithe_label_ins")
        label_h = max(v.co.y for v in label_ins.data.vertices) - min(v.co.y for v in label_ins.data.vertices)
        label_w = max(v.co.x for v in label_ins.data.vertices) - min(v.co.x for v in label_ins.data.vertices)
        label_cy = label_top - label_h / 2.0
        label_ins.data.transform(mathutils.Matrix.Translation((0.0, label_cy, 0.0)))
        assert label_cy - label_h / 2.0 > IY0 + SLOT_CARD_D + DIV_T + 1.0, "Tithe label runs into the card slot"
        assert label_x + label_w / 2.0 < EXT_W - WALL_T, "Tithe label runs off the right edge"
        first_wheel = next(i for i, (item, _, _) in enumerate(layout) if item[0] == "wheel")
        if first_wheel:
            _, x, w = layout[first_wheel - 1]
            assert label_x - label_w / 2.0 > x + w + 1.0, "Tithe label runs into the well left of the wheels"
        inserts.append(label_ins)
        icon_cutters.append(build_text_xy(TITHE_LABEL, TITHE_LABEL_SIZE, BASE_EXT_H - INSERT_DEPTH,
                                          INSERT_DEPTH + HOLE_OVERSHOOT, label_x, label_cy, 0.0, "tithe_label_cut"))
        for i, (wx, wy) in enumerate(wheel_centers):
            ptr = pointer_points(wx, wy)
            inserts.append(extrude_xy(ptr, BASE_EXT_H - INSERT_DEPTH, INSERT_DEPTH, f"pointer_{i}_ins"))
            icon_cutters.append(extrude_xy(ptr, BASE_EXT_H - INSERT_DEPTH, INSERT_DEPTH + HOLE_OVERSHOOT,
                                           f"pointer_{i}_cut"))

    # 2) Card slot floor icons + underside logo - decorative class, own sequential cut after the
    # structural wells. Floor icon cutters poke up out of the floor into the (already empty) slot.
    cards, cards_aspect = load_contours(CARDS_CONTOURS_PATH)
    die, die_aspect = load_contours(DIE_FIVE_CONTOURS_PATH)
    cards_x = ccx - FLOOR_ICON_GAP / 2.0 - CARDS_ICON_W / 2.0
    die_x = ccx + FLOOR_ICON_GAP / 2.0 + DIE_ICON_W / 2.0
    for contours, w, aspect, x, tag in ((cards, CARDS_ICON_W, cards_aspect, cards_x, "cards"),
                                         (die, DIE_ICON_W, die_aspect, die_x, "die")):
        inserts.append(build_icon_solid_xy(contours, w, w * aspect, x, ccy,
                                           FLOOR_T - INSERT_DEPTH, INSERT_DEPTH, f"floor_{tag}_ins"))
        icon_cutters.append(build_icon_solid_xy(contours, w, w * aspect, x, ccy,
                                                FLOOR_T - INSERT_DEPTH, INSERT_DEPTH + HOLE_OVERSHOOT,
                                                f"floor_{tag}_cut"))
    assert max(CARDS_ICON_W * cards_aspect, DIE_ICON_W * die_aspect) < SLOT_CARD_D - 10.0, \
        "floor icons too tall for the card slot"

    # Mythos logo on the underside, flush with the bed face - well clear of the floor icons'
    # pockets in Z, so it joins the same cut. Its cutter pokes down out of the bed face.
    inserts.append(build_mythos_logo(EXT_W / 2.0, EXT_D / 2.0, 0.0, INSERT_DEPTH, "logo_ins"))
    icon_cutters.append(build_mythos_logo(EXT_W / 2.0, EXT_D / 2.0, -HOLE_OVERSHOOT,
                                          INSERT_DEPTH + HOLE_OVERSHOOT, "logo_cut"))
    assert INSERT_DEPTH < FLOOR_T - INSERT_DEPTH - 1.0, "floor too thin for both inlay layers"

    prev_vol = mesh_volume(shell)
    apply_boolean(shell, join_objects(icon_cutters, "base_icon_cutters"), 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_vol, f"base: icon pockets corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"

    apply_bevel(shell, BEVEL_W)
    return shell, join_objects(inserts, "base_inlay"), wheel_centers


# ============================================================
# LID
# ============================================================


def build_lid(force):
    lid_ext_w = EXT_W + 2.0 * LID_CLEARANCE + 2.0 * LID_WALL_T
    lid_ext_d = EXT_D + 2.0 * LID_CLEARANCE + 2.0 * LID_WALL_T
    cx, cy = EXT_W / 2.0, EXT_D / 2.0

    shell = build_box(lid_ext_w, lid_ext_d, LID_Z1 - LID_Z0, (cx, cy, (LID_Z0 + LID_Z1) / 2.0), "lid_shell")

    # 1) Skirt cavity - structural, own sequential cut + assert.
    prev_vol = mesh_volume(shell)
    cavity_w = EXT_W + 2.0 * LID_CLEARANCE
    cavity_d = EXT_D + 2.0 * LID_CLEARANCE
    cavity_h = BASE_EXT_H - (LID_Z0 - HOLE_OVERSHOOT)
    cavity = build_box(cavity_w, cavity_d, cavity_h, (cx, cy, BASE_EXT_H - cavity_h / 2.0), "lid_skirt_cut")
    apply_boolean(shell, cavity, 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_vol, f"lid: skirt cavity corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"

    # 2) Icon pockets - the force's icons (top face) + inside dice_roll (slab underside),
    # decorative class, one combined cut (separate zones: 3mm slab, 0.6mm pockets from opposite
    # faces, corner icons well clear of the center one).
    center = force["lid_center"]
    icon, icon_aspect = load_contours(center["contours"], center.get("aspect"))
    icon_w = center["w"]
    icon_h = icon_w * icon_aspect
    rot_deg = center.get("rot", 0.0)
    icon_ext_x, icon_ext_y = (icon_h, icon_w) if rot_deg % 180 else (icon_w, icon_h)
    assert icon_ext_x < lid_ext_w - 10.0 and icon_ext_y < lid_ext_d - 10.0, "lid icon too big for the lid"
    assert DICE_ROLL_W < cavity_w - 10.0, "dice_roll icon too wide for the lid"
    rot = (mathutils.Matrix.Translation((cx, cy, 0.0)) @ mathutils.Matrix.Rotation(math.radians(rot_deg), 4, 'Z')
           @ mathutils.Matrix.Translation((-cx, -cy, 0.0)))

    def rotated(obj):
        obj.data.transform(rot)
        return obj

    dice, dice_aspect = load_contours(DICE_ROLL_CONTOURS_PATH)
    inserts = [
        rotated(build_icon_solid_xy(icon, icon_w, icon_h, cx, cy,
                                    LID_Z1 - INSERT_DEPTH, INSERT_DEPTH, "lid_icon_ins")),
        # Mirrored: the inside face is read with the lid flipped over (as a dice tray), which
        # reverses its handedness.
        build_icon_solid_xy(dice, DICE_ROLL_W, DICE_ROLL_W * dice_aspect, cx, cy,
                            BASE_EXT_H, INSERT_DEPTH, "lid_dice_ins", mirror_y=True),
    ]
    cutters = [
        rotated(build_icon_solid_xy(icon, icon_w, icon_h, cx, cy,
                                    LID_Z1 - INSERT_DEPTH, INSERT_DEPTH + HOLE_OVERSHOOT, "lid_icon_cut")),
        build_icon_solid_xy(dice, DICE_ROLL_W, DICE_ROLL_W * dice_aspect, cx, cy,
                            BASE_EXT_H - HOLE_OVERSHOOT, INSERT_DEPTH + HOLE_OVERSHOOT, "lid_dice_cut",
                            mirror_y=True),
    ]

    corner = force["lid_corners"]
    if corner:
        rune, rune_aspect = load_contours(corner["contours"], corner.get("aspect"))
        rune_w, rune_h = LID_CORNER_W, LID_CORNER_W * rune_aspect
        x0, x1 = cx - lid_ext_w / 2.0 + LID_CORNER_MARGIN, cx + lid_ext_w / 2.0 - LID_CORNER_MARGIN
        y0, y1 = cy - lid_ext_d / 2.0 + LID_CORNER_MARGIN, cy + lid_ext_d / 2.0 - LID_CORNER_MARGIN
        assert x1 - rune_w / 2.0 > cx + icon_ext_x / 2.0 + 5.0 or y1 - rune_h / 2.0 > cy + icon_ext_y / 2.0 + 5.0, \
            "corner icons crowd the center icon"
        for i, (rx, ry) in enumerate(((x0, y0), (x1, y0), (x0, y1), (x1, y1))):
            inserts.append(build_icon_solid_xy(rune, rune_w, rune_h, rx, ry,
                                               LID_Z1 - INSERT_DEPTH, INSERT_DEPTH, f"lid_corner_{i}_ins"))
            cutters.append(build_icon_solid_xy(rune, rune_w, rune_h, rx, ry,
                                               LID_Z1 - INSERT_DEPTH, INSERT_DEPTH + HOLE_OVERSHOOT,
                                               f"lid_corner_{i}_cut"))

    prev_vol = mesh_volume(shell)
    apply_boolean(shell, join_objects(cutters, "lid_icon_cutters"), 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_vol, f"lid: icon pockets corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"

    apply_bevel(shell, BEVEL_W)
    return shell, join_objects(inserts, "lid_inlay")


# ============================================================
# BLOOD TITHE WHEEL (Khorne)
# ============================================================


def circle_points(r, n=96, cx=0.0, cy=0.0):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def build_text_xy(text, size, z0, thickness, cx, cy, rotation_deg, name):
    """Flat text in the XY plane, its ink bounding box centered on (cx, cy), rotated
    rotation_deg about Z (0 = reads upright from the front of the box, -Y)."""
    font = bpy.data.fonts.load(FONT_PATH, check_existing=True)
    cd = bpy.data.curves.new(f"{name}_curve", type='FONT')
    cd.body = text
    cd.font = font
    cd.size = size
    cd.align_x = 'CENTER'
    cd.align_y = 'CENTER'
    cd.space_character = DIGIT_SPACING
    cd.extrude = thickness / 2.0
    obj = bpy.data.objects.new(name, cd)
    bpy.context.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')

    # merge-by-distance: FONT-curve conversion leaves duplicate cap vertices that corrupt the
    # EXACT solver (see ../khorne-tokens/build_khorne_tokens.py's _build_flat_text_mesh)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-3)
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    # center the ink's own bounding box on the origin (align_y=CENTER uses the font's line
    # metrics, not the glyph's ink, so wheel digits would sit off-radius otherwise)
    bmesh.ops.translate(bm, vec=(-(min(xs) + max(xs)) / 2.0, -(min(ys) + max(ys)) / 2.0, 0.0), verts=bm.verts)
    bmesh.ops.transform(bm, matrix=mathutils.Matrix.Rotation(math.radians(rotation_deg), 4, 'Z'), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(cx, cy, z0 + thickness / 2.0), verts=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def build_digit_xy(text, size, z0, thickness, angle_deg, radius, name):
    """One wheel digit, centered at `radius` from the origin in direction `angle_deg`, rotated so
    its top points at the origin - the digit at the front (-Y, the pointer) reads upright."""
    a = math.radians(angle_deg)
    return build_text_xy(text, size, z0, thickness, radius * math.cos(a), radius * math.sin(a),
                         angle_deg + 90.0, name)


def build_wheel():
    """The wheel in print orientation: flat on the bed, digit face up. Returns (disc, digit inlay)."""
    shell = extrude_xy(circle_points(WHEEL_D / 2.0), 0.0, WHEEL_T, "wheel_shell")

    # Structural cuts first: center hole + rim grip notches, one combined cut (they don't overlap)
    prev_vol = mesh_volume(shell)
    cutters = [extrude_xy(circle_points(WHEEL_HOLE_D / 2.0, 48), -HOLE_OVERSHOOT, WHEEL_T + 2 * HOLE_OVERSHOOT,
                          "wheel_hole_cut")]
    r = WHEEL_D / 2.0
    for k in range(WHEEL_RIM_NOTCHES):
        a = 2 * math.pi * (k + 0.5) / WHEEL_RIM_NOTCHES   # between digit positions
        cutters.append(extrude_xy(circle_points(WHEEL_RIM_NOTCH_R, 24, r * math.cos(a), r * math.sin(a)),
                                  -HOLE_OVERSHOOT, WHEEL_T + 2 * HOLE_OVERSHOOT, f"wheel_notch_{k}"))
    apply_boolean(shell, join_objects(cutters, "wheel_struct_cutters"), 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_vol, f"wheel: hole/notch cut corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"

    assert DIGIT_RADIUS - DIGIT_SIZE * 0.5 > WHEEL_HOLE_D / 2.0 + 1.0, "digits run into the center hole"
    assert DIGIT_RADIUS + DIGIT_SIZE * 0.5 < r - WHEEL_RIM_NOTCH_R - 0.5, "digits run into the rim notches"

    inserts, digit_cutters = [], []
    for k in range(10):
        angle = -90.0 + 36.0 * k      # 0 at the front (-Y), counting counter-clockwise from above
        inserts.append(build_digit_xy(str(k), DIGIT_SIZE, WHEEL_T - INSERT_DEPTH, INSERT_DEPTH,
                                      angle, DIGIT_RADIUS, f"digit_{k}_ins"))
        digit_cutters.append(build_digit_xy(str(k), DIGIT_SIZE, WHEEL_T - INSERT_DEPTH,
                                            INSERT_DEPTH + HOLE_OVERSHOOT, angle, DIGIT_RADIUS, f"digit_{k}_cut"))
    prev_vol = mesh_volume(shell)
    apply_boolean(shell, join_objects(digit_cutters, "wheel_digit_cutters"), 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_vol, f"wheel: digit pockets corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"

    apply_bevel(shell, 0.4)
    return shell, join_objects(inserts, "wheel_inlay")


def wheel_pocket_cutter(cx, cy, top_z, wall_y):
    """Round pocket for the wheel, cut down from top_z, plus a WHEEL_GRIP_SLOT_W slot from the
    pocket center out through the exterior face at wall_y - exposes the rim for gripping. One
    clean solid (unioned - pocket and slot overlap by design)."""
    floor_z = top_z - WHEEL_POCKET_DEPTH
    pocket = extrude_xy(circle_points(WHEEL_POCKET_D / 2.0, 96, cx, cy), floor_z,
                        WHEEL_POCKET_DEPTH + HOLE_OVERSHOOT, "wheel_pocket_cut")
    hw = WHEEL_GRIP_SLOT_W / 2.0
    y_out = wall_y + HOLE_OVERSHOOT
    slot = extrude_xy([(cx - hw, cy), (cx + hw, cy), (cx + hw, y_out), (cx - hw, y_out)],
                      floor_z, WHEEL_POCKET_DEPTH + HOLE_OVERSHOOT, "wheel_grip_slot_cut")
    return union_onto(pocket, slot)


def build_peg(cx, cy, floor_z):
    return extrude_xy(circle_points(PEG_D / 2.0, 48, cx, cy), floor_z - HOLE_OVERSHOOT,
                      HOLE_OVERSHOOT + WHEEL_T - PEG_TOP_GAP, "wheel_peg")


def pointer_points(cx, cy):
    """Triangle in front of the pocket (-Y side), tip pointing at the wheel."""
    tip_y = cy - WHEEL_POCKET_D / 2.0 - POINTER_GAP
    return [(cx, tip_y), (cx + POINTER_W / 2.0, tip_y - POINTER_H), (cx - POINTER_W / 2.0, tip_y - POINTER_H)]


def build_wheel_coupon():
    """Test block with one wheel pocket, peg and pointer, rim exposed at the back edge the same
    way as in the box - prints in minutes, proves the peg/pocket clearances and the grip before
    the full box depends on them."""
    cx, cy = COUPON_W / 2.0, COUPON_D - WHEEL_EDGE_INSET - WHEEL_D / 2.0
    shell = build_box(COUPON_W, COUPON_D, COUPON_H, (COUPON_W / 2.0, COUPON_D / 2.0, COUPON_H / 2.0), "coupon")
    prev_vol = mesh_volume(shell)
    apply_boolean(shell, wheel_pocket_cutter(cx, cy, COUPON_H, COUPON_D), 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_vol, f"coupon: pocket cut corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"
    union_onto(shell, build_peg(cx, cy, COUPON_H - WHEEL_POCKET_DEPTH))

    ptr = pointer_points(cx, cy)
    insert = extrude_xy(ptr, COUPON_H - INSERT_DEPTH, INSERT_DEPTH, "pointer_ins")
    cutter = extrude_xy(ptr, COUPON_H - INSERT_DEPTH, INSERT_DEPTH + HOLE_OVERSHOOT, "pointer_cut")
    prev_vol = mesh_volume(shell)
    apply_boolean(shell, cutter, 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_vol, f"coupon: pointer pocket corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"

    apply_bevel(shell, BEVEL_W)
    return shell, insert, (cx, cy, COUPON_H - WHEEL_POCKET_DEPTH)


# ============================================================
# MAIN
# ============================================================


def report(name, obj):
    vol, nm = mesh_volume(obj), nonmanifold_fraction(obj)
    print(f"{name}: volume={vol:.1f}mm3 (non-manifold {nm:.4f})")
    assert vol > 0.0, f"{name}: zero/negative volume - a boolean likely emptied it"


def export_two_color(out_dir, name, base, inlay, force):
    export_stl(base, os.path.join(out_dir, f"{name}_base.stl"))
    export_stl(inlay, os.path.join(out_dir, f"{name}_inlay.stl"))
    export_3mf([(base, force["base_color"], "base"), (inlay, force["inlay_color"], "inlay")],
               os.path.join(out_dir, f"{name}.3mf"))
    # Import THIS one in Anycubic Slicer Next - see export_project_3mf's docstring.
    export_project_3mf([(base, "base", BASE_EXTRUDER_SLOT), (inlay, "inlay", INLAY_EXTRUDER_SLOT)],
                       os.path.join(out_dir, f"{name}_anycubic.3mf"))


def colorize(force_name, force, base_objs, inlay_objs):
    """Materials are per force - a material name shared across forces would keep the first
    force's colour (bpy.data.materials outlives clear_scene)."""
    for o in base_objs:
        apply_color(o, f"{force_name}_base_mat", force["base_color"])
    for o in inlay_objs:
        apply_color(o, f"{force_name}_inlay_mat", force["inlay_color"])


def build_wheel_test(force_name, force, out_dir, render_dir):
    """Wheel + test coupon: renders (wheel alone, wheel seated in the coupon) and exports."""
    clear_scene()
    wheel, wheel_inlay = build_wheel()
    report("wheel", wheel)
    report("wheel inlay", wheel_inlay)
    colorize(force_name, force, [wheel], [wheel_inlay])
    bpy.context.view_layer.update()
    render_top(render_dir, "tithe_wheel", elev_deg=80.0)
    export_two_color(out_dir, "tithe_wheel", wheel, wheel_inlay, force)

    coupon, pointer, (cx, cy, floor_z) = build_wheel_coupon()
    report("coupon", coupon)
    colorize(force_name, force, [coupon], [pointer])
    for o in (wheel, wheel_inlay):
        o.location = (cx, cy, floor_z)   # seat the wheel on the peg for the preview
    bpy.context.view_layer.update()
    render_top(render_dir, "tithe_wheel_coupon", elev_deg=60.0)
    for o in (wheel, wheel_inlay):
        o.location = (0.0, 0.0, 0.0)
    export_two_color(out_dir, "tithe_wheel_test_coupon", coupon, pointer, force)


def flip_lid_for_print(lid_parts):
    """Printed skirt-up, the top slab is the flat first layer - no bridging. This is also the
    dice-tray orientation, so a render from above checks that the inside dice_roll icon reads
    correctly (not mirrored) when the lid is used that way."""
    lid_cy, lid_cz = EXT_D / 2.0, (LID_Z0 + LID_Z1) / 2.0
    for o in lid_parts:
        reorient_lid_for_print(o, lid_cy, lid_cz)
    bpy.context.view_layer.update()   # obj.bound_box is cached - refresh before framing


def build_force(force_name, force, out_dir, render_dir):
    clear_scene()
    base, base_inlay, wheel_centers = build_base(force)
    lid, lid_inlay = build_lid(force)
    for name, obj in (("base", base), ("base inlay", base_inlay), ("lid", lid), ("lid inlay", lid_inlay)):
        report(name, obj)
    colorize(force_name, force, [base, lid], [base_inlay, lid_inlay])

    # Tithe wheels: export one (print x2), then seat each in its pocket for the renders
    wheels = []
    for i, (wx, wy) in enumerate(wheel_centers):
        wheel, wheel_inlay = build_wheel()
        colorize(force_name, force, [wheel], [wheel_inlay])
        if i == 0:
            report("wheel", wheel)
            export_two_color(out_dir, "tithe_wheel", wheel, wheel_inlay, force)
        for o in (wheel, wheel_inlay):
            o.location = (wx, wy, WHEEL_FLOOR_Z)
        wheels += [wheel, wheel_inlay]

    # Destiny Dice: preview-only 12mm cubes seated in the rack slots, for the renders
    destiny_dice = []
    for item, x, w in back_row_layout(force):
        if item[0] == "rack":
            for sx, sy in _rack_slot_centers(item, x, w):
                die = build_box(RACK_DIE, RACK_DIE, RACK_DIE,
                                (sx, sy, RACK_SLOT_FLOOR_Z + RACK_DIE / 2.0), "destiny_die")
                apply_bevel(die, 1.0)
                destiny_dice.append(die)
    colorize(force_name, force, [], destiny_dice)

    lid_parts = [lid, lid_inlay]
    base_parts = [base, base_inlay] + wheels + destiny_dice

    bpy.context.view_layer.update()   # obj.bound_box is cached - refresh before any render framing
    for o in destiny_dice:
        o.hide_render = True   # they stand above the rim - out of the box when it's closed
    render_top(render_dir, "box_assembled_closed")
    for o in destiny_dice:
        o.hide_render = False

    for o in lid_parts:
        o.location.z += 60.0   # lift the lid off for an "exploded" second shot
    bpy.context.view_layer.update()
    render_top(render_dir, "box_assembled_open")

    for o in lid_parts:
        o.hide_render = True
    render_top(render_dir, "box_base_only", elev_deg=80.0, bounds_objs=base_parts)
    render_top(render_dir, "box_base_underside", elev_deg=80.0, from_below=True, bounds_objs=base_parts)
    for o in lid_parts:
        o.hide_render = False
    for o in lid_parts:
        o.location.z -= 60.0

    flip_lid_for_print(lid_parts)

    for o in base_parts:
        o.hide_render = True
    render_top(render_dir, "box_lid_as_dice_tray", elev_deg=70.0, bounds_objs=lid_parts)
    render_top(render_dir, "box_lid_top_face", elev_deg=70.0, from_below=True, bounds_objs=lid_parts)
    for o in base_parts:
        o.hide_render = False

    export_two_color(out_dir, "box_base", base, base_inlay, force)
    export_two_color(out_dir, "box_lid", lid, lid_inlay, force)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    force_names = [argv[argv.index("--force") + 1]] if "--force" in argv else list(FORCES)
    wheel_test = "--wheel-test" in argv
    for force_name in force_names:
        assert force_name in FORCES, f"unknown force {force_name} - one of {', '.join(FORCES)}"
        force = FORCES[force_name]
        assert not wheel_test or any(i[0] == "wheel" for i in force["back_row"]), \
            f"--wheel-test: {force_name} has no Tithe wheels"
        out_dir = os.path.join(EXPORT_DIR, force_name)
        render_dir = os.path.join(out_dir, "renders")
        os.makedirs(render_dir, exist_ok=True)
        print(f"=== {force_name}")
        if wheel_test:
            build_wheel_test(force_name, force, out_dir, render_dir)
        else:
            build_force(force_name, force, out_dir, render_dir)
    print("Done.")


if __name__ == "__main__":
    main()
