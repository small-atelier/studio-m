"""
Themed carry box for the Blades of Khorne (Bloodbound Gore Pilgrims
Spearhead) game accessories - one box holds the warscroll card stack (or
loose dice) AND the hex tokens + damage trays from
../khorne-tokens/build_khorne_tokens.py, closed by a slip-fit lid.

Adapted from ../token-card-box/build_token_card_box.py (the Hashut box) -
the generic helpers, lift notches, full-height lid skirt, export-time lid
flip and boolean-safety patterns are carried over unchanged; see that
script's docstring and comments for the reasoning behind each.

- box_base: an open-top tray, black, same footprint and column layout as
  the Hashut box, 6 pockets all cut to the same DEEP_DEPTH (22mm) floor.
  Left column: 3 hex-token wells stacked (one per token type). Right column:
  the card slot (123x73, same as the Hashut box) up front - it doubles as
  dice storage, so its floor carries a cards + die icon inlay as a hint -
  and 2 arrow-shaped damage-tray wells (3 trays each) behind it, where the
  Hashut Desolation wells sat. Every well gets a lift notch through the
  exterior wall it's flush against - left for the hexes, front for the card
  slot, back for the trays. Two-color: base + floor-icon inlay.
- box_lid: a flat-top slab with a full-height hollow skirt that slides over
  the base's outer walls. Khorne rune inlay centered on the outside top;
  the dice_roll icon inlaid on the INSIDE face - flipped over, the lid is a
  dice-rolling tray, and that icon is mirrored so it reads correctly in
  that orientation (see build_lid). Both icons join into one inlay object.

Icons are traced by ../khorne-tokens/extract_icon_contours.py.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_khorne_token_box.py

Tithe wheel + test coupon only:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_khorne_token_box.py -- wheel-test
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
_ICON_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "khorne-tokens"))
KHORNE_CONTOURS_PATH = os.path.join(_ICON_DIR, "khorne_contours.json")
DICE_ROLL_CONTOURS_PATH = os.path.join(_ICON_DIR, "dice_roll_contours.json")
CARDS_CONTOURS_PATH = os.path.join(_ICON_DIR, "cards_contours.json")
DIE_FIVE_CONTOURS_PATH = os.path.join(_ICON_DIR, "die_five_contours.json")

EXPORT_DIR = os.path.join(SCRIPT_DIR, "output")
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1400, 1000)

BASE_COLOR = (0.04, 0.04, 0.04, 1.0)   # black - same convention as build_khorne_tokens.py
INLAY_COLOR = (0.65, 0.03, 0.03, 1.0)  # red

# Anycubic Slicer Next reads its own per-part extruder metadata - set to whichever ACE/AMS slot
# holds black/red on the day you slice.
BASE_EXTRUDER_SLOT = 1    # black
INLAY_EXTRUDER_SLOT = 2   # red

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

# --- card slot --- (same as the Hashut box)
CARD_W = 120.0          # user-supplied stack footprint
CARD_D = 70.0
CARD_H = 20.0           # stack height - drives DEEP_DEPTH, not the slot footprint
CARD_CLEARANCE = 1.5    # per-side clearance so the stack drops in/out easily
SLOT_CARD_W = CARD_W + 2.0 * CARD_CLEARANCE     # 123.0
SLOT_CARD_D = CARD_D + 2.0 * CARD_CLEARANCE     # 73.0

DEEP_DEPTH = CARD_H + 2.0        # 22.0 - every well is cut to this depth

# --- hex token wells --- (token size from ../khorne-tokens/build_khorne_tokens.py's
# HEX_FLAT_TO_FLAT - keep in sync)
HEX_TOKEN_FLAT_TO_FLAT = 33.0
HEX_WELL_CLEARANCE = 1.0
HEX_WELL_FLAT_TO_FLAT = HEX_TOKEN_FLAT_TO_FLAT + 2.0 * HEX_WELL_CLEARANCE      # 35.0
HEX_WELL_POINT_TO_POINT = HEX_WELL_FLAT_TO_FLAT * 2.0 / math.sqrt(3.0)         # ~40.41
HEX_WELL_COUNT = 3              # one stack per token type: Heads Must Roll x3, Unholy Flames x1,
                                 # Murderlust x3

# --- damage tray wells --- (tray outline from build_khorne_tokens.py's TRAY_BODY_W/TRAY_HEAD_L -
# a pentagon: square body + same-width triangular head; keep in sync)
TRAY_BODY_W = 22.0
TRAY_HEAD_L = 18.0
TRAY_WELL_CLEARANCE = 1.0
TRAY_WELL_COUNT = 2             # 6 trays x 6.5mm = 39mm, two stacks of 3 (19.5mm) fit 22mm deep

# --- lift notches --- through the exterior wall a well is flush against, down to the well floor
CARD_NOTCH_W = 80.0
HEX_NOTCH_W = 32.0     # through the left wall, across the hex's flat side (same as the Hashut box)
TRAY_NOTCH_W = 16.0    # across the tray's flat end (trays sit tip-forward, flat end at the wall)

# --- lid ---
LID_T = 3.0               # top slab thickness
LID_SKIRT = FLOOR_T + DEEP_DEPTH     # full height - the skirt reaches the table
LID_CLEARANCE = 0.3       # per-side slip-fit clearance between the skirt and the base's outer wall
LID_WALL_T = 2.0          # skirt wall thickness

LID_RUNE_W = 50.0         # outside top, centered
DICE_ROLL_W = 70.0        # inside face, centered

# --- card slot floor icons --- side by side, centered on the slot floor
CARDS_ICON_W = 30.0
DIE_ICON_W = 30.0
FLOOR_ICON_GAP = 12.0

# --- Blood Tithe wheels --- two identical 0-9 wheels (tens + units), each spinning on a peg
# printed into a shallow pocket in the base. Digits on the TOP face, read from above against a
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
POINTER_W = 7.0           # red triangle inlay on the top surface in front of the pocket
POINTER_H = 5.0
POINTER_GAP = 0.8         # from the pocket edge to the pointer tip
TITHE_LABEL = "BLOOD TITHE"    # red text on the top surface, centered under the two pointers
TITHE_LABEL_SIZE = 8.0
TITHE_LABEL_GAP = 1.5          # pointer base to label top

FONT_PATH = os.path.join(_ICON_DIR, "ArialBlack.ttf")

# --- wheel test coupon --- one pocket + peg + pointer, rim exposed at the back edge, a quick fit print
COUPON_W = WHEEL_POCKET_D + 10.0
COUPON_D = WHEEL_POCKET_D + 16.0      # extra at the front for the pointer
COUPON_H = WHEEL_POCKET_DEPTH + 2.0

# ============================================================
# LAYOUT (derived) - same footprint and column layout as the Hashut box (v8)
#
# COLUMN A, the short left end: the 3 hex wells STACKED vertically, flush against the left wall,
# each with a lift notch through the LEFT wall. COLUMN B, the long remainder, two rows: the card
# slot is the FRONT row (front-wall notch), the 2 tray wells are the BACK row (back-wall notches),
# each tray well centered in its half of column B's width - where the Hashut Desolation wells sat.
# Column A is taller than column B's two rows, so the back row pins to the back wall and the
# leftover depth is a gap between the rows.
# ============================================================


def _tray_outline():
    """Tray pentagon in its own frame: flat end at y=0, tip pointing -Y (tip-forward in the box,
    so the flat end sits against the back wall where the lift notch is)."""
    hw = TRAY_BODY_W / 2.0
    return [(-hw, 0.0), (hw, 0.0), (hw, -TRAY_BODY_W), (0.0, -TRAY_BODY_W - TRAY_HEAD_L),
            (-hw, -TRAY_BODY_W)]


TRAY_WELL_W = TRAY_BODY_W + 2.0 * TRAY_WELL_CLEARANCE                     # 24.0
TRAY_WELL_D = TRAY_BODY_W + TRAY_HEAD_L + 2.0 * TRAY_WELL_CLEARANCE       # 42.0

COL_A_W = HEX_WELL_FLAT_TO_FLAT
COL_A_H = HEX_WELL_COUNT * HEX_WELL_POINT_TO_POINT + (HEX_WELL_COUNT - 1) * DIV_T

WHEEL_COUNT = 2           # Blood Tithe tens + units
_BACK_ROW_ITEMS_W = TRAY_WELL_COUNT * TRAY_WELL_W + WHEEL_COUNT * WHEEL_POCKET_D
COL_B_W = max(SLOT_CARD_W, _BACK_ROW_ITEMS_W + (TRAY_WELL_COUNT + WHEEL_COUNT - 1) * DIV_T)
COL_B_H = SLOT_CARD_D + DIV_T + max(TRAY_WELL_D, WHEEL_POCKET_D + POINTER_GAP + POINTER_H + 1.0)

INT_FOOT_W = COL_A_W + DIV_T + COL_B_W
INT_FOOT_D = max(COL_A_H, COL_B_H)

EXT_W = INT_FOOT_W + 2.0 * WALL_T
EXT_D = INT_FOOT_D + 2.0 * WALL_T
BASE_INT_H = DEEP_DEPTH
BASE_EXT_H = FLOOR_T + BASE_INT_H

IX0, IY0 = WALL_T, WALL_T   # interior footprint origin
BACK_WALL_Y = IY0 + INT_FOOT_D

# --- Column A: 3 stacked hexes, flush left ---
_hex_cx = IX0 + COL_A_W / 2.0
HEX_WELL_CENTERS = [
    (_hex_cx, IY0 + HEX_WELL_POINT_TO_POINT / 2.0 + i * (HEX_WELL_POINT_TO_POINT + DIV_T))
    for i in range(HEX_WELL_COUNT)
]

# --- Column B ---
_col_b_x0 = IX0 + COL_A_W + DIV_T
CARD_SLOT_CENTER = (_col_b_x0 + SLOT_CARD_W / 2.0, IY0 + SLOT_CARD_D / 2.0)

# Back row, left to right: tray wells, then the tens and units wheels - all flush against the
# back wall, spread across column B's width with equal gaps between them.
_back_gap = (COL_B_W - _BACK_ROW_ITEMS_W) / (TRAY_WELL_COUNT + WHEEL_COUNT - 1)
assert _back_gap >= DIV_T, "back row items don't fit column B"
TRAY_WELL_ANCHORS = []      # (center x, y of the well's back edge = the back wall)
WHEEL_CENTERS = []
_x = _col_b_x0
for _ in range(TRAY_WELL_COUNT):
    TRAY_WELL_ANCHORS.append((_x + TRAY_WELL_W / 2.0, BACK_WALL_Y))
    _x += TRAY_WELL_W + _back_gap
for _ in range(WHEEL_COUNT):
    WHEEL_CENTERS.append((_x + WHEEL_POCKET_D / 2.0, EXT_D - WHEEL_EDGE_INSET - WHEEL_D / 2.0))
    _x += WHEEL_POCKET_D + _back_gap
WHEEL_FLOOR_Z = BASE_EXT_H - WHEEL_POCKET_DEPTH

print(f"Box exterior: {EXT_W:.1f} x {EXT_D:.1f} x {BASE_EXT_H:.1f}mm (base); "
      f"lid adds {LID_T:.1f}mm on top, {2*(LID_CLEARANCE+LID_WALL_T):.1f}mm on each footprint side")

# ============================================================
# GENERIC HELPERS (same conventions as ../khorne-tokens/build_khorne_tokens.py)
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
    along +Z - the footprint-native counterpart of build_tokens.py's
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
    boolean call - see build_tokens.py's own join_objects docstring for
    why (EXACT-solver corruption on long boolean chains)."""
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    objs[0].name = name
    return objs[0]


def dedupe_closed_loop(points, tol=1e-9):
    """See build_tokens.py's own dedupe_closed_loop - traced contours
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
    shape/orientation as build_tokens.py's hex_points - kept consistent
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


def load_contours(path):
    """Returns (polygons, aspect h/w) - see ../khorne-tokens/extract_icon_contours.py."""
    with open(path) as f:
        data = json.load(f)
    return data["polygons"], data["aspect"]


def build_icon_solid_xy(contours, icon_w, icon_h, center_x, center_y, z0, thickness, name_prefix,
                        mirror_y=False):
    """XY-plane counterpart of build_tokens.py's build_icon_solid - same
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


def render_top(name, elev_deg=55.0, from_below=False, bounds_objs=None):
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
    scene.render.filepath = os.path.join(RENDER_DIR, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {scene.render.filepath}")
    bpy.data.objects.remove(cam, do_unlink=True)
    bpy.data.objects.remove(light, do_unlink=True)


def export_stl(obj, filename):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = os.path.join(EXPORT_DIR, filename)
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"Exported {path}")


def export_3mf(parts, path):
    """Same generic multi-object colored 3MF writer as build_tokens.py's
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
    """Same Anycubic Slicer Next project-3mf flavor as build_tokens.py's
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
# BASE
# ============================================================


def build_base():
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

    well_outline = offset_convex_polygon(_tray_outline(), TRAY_WELL_CLEARANCE)
    for tx, back_y in TRAY_WELL_ANCHORS:
        # _tray_outline's flat end is at y=0; shift so the offset well's back edge lands on the wall
        pts = [(tx + x, back_y - TRAY_WELL_CLEARANCE + y) for x, y in well_outline]
        pocket = extrude_xy(pts, FLOOR_T, DEEP_DEPTH + HOLE_OVERSHOOT, "tray_well_cut")
        notch = extrude_xy(back_notch_points(tx, TRAY_NOTCH_W, back_y - TRAY_WELL_D / 2.0),
                           FLOOR_T, DEEP_DEPTH, "tray_notch_cut")
        cutters.append(union_onto(pocket, notch))

    # Tithe wheel pockets - each breaks through the back wall, exposing the wheel rim for gripping
    for wx, wy in WHEEL_CENTERS:
        cutters.append(wheel_pocket_cutter(wx, wy, BASE_EXT_H, EXT_D))

    apply_boolean(shell, join_objects(cutters, "well_cutters"), 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_vol, f"base: well cut corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"

    # 2) Card slot floor icons - decorative class, own sequential cut after the structural wells.
    # Cutters poke up out of the floor into the (already empty) slot.
    # Wheel pegs - one combined union (they don't touch each other)
    prev_vol = mesh_volume(shell)
    union_onto(shell, join_objects([build_peg(wx, wy, WHEEL_FLOOR_Z) for wx, wy in WHEEL_CENTERS], "pegs"))
    vol = mesh_volume(shell)
    assert vol > prev_vol, f"base: peg union corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"

    inserts, icon_cutters = [], []
    label_x = sum(wx for wx, _ in WHEEL_CENTERS) / len(WHEEL_CENTERS)
    label_top = WHEEL_CENTERS[0][1] - WHEEL_POCKET_D / 2.0 - POINTER_GAP - POINTER_H - TITHE_LABEL_GAP
    label_ins = build_text_xy(TITHE_LABEL, TITHE_LABEL_SIZE, BASE_EXT_H - INSERT_DEPTH, INSERT_DEPTH,
                              label_x, 0.0, 0.0, "tithe_label_ins")
    label_h = max(v.co.y for v in label_ins.data.vertices) - min(v.co.y for v in label_ins.data.vertices)
    label_w = max(v.co.x for v in label_ins.data.vertices) - min(v.co.x for v in label_ins.data.vertices)
    label_cy = label_top - label_h / 2.0
    label_ins.data.transform(mathutils.Matrix.Translation((0.0, label_cy, 0.0)))
    assert label_cy - label_h / 2.0 > IY0 + SLOT_CARD_D + DIV_T + 1.0, "Tithe label runs into the card slot"
    assert label_x + label_w / 2.0 < EXT_W - WALL_T, "Tithe label runs off the right edge"
    _last_tray_right = TRAY_WELL_ANCHORS[-1][0] + TRAY_WELL_W / 2.0
    assert label_x - label_w / 2.0 > _last_tray_right + 1.0, "Tithe label runs into the tray wells"
    inserts.append(label_ins)
    icon_cutters.append(build_text_xy(TITHE_LABEL, TITHE_LABEL_SIZE, BASE_EXT_H - INSERT_DEPTH,
                                      INSERT_DEPTH + HOLE_OVERSHOOT, label_x, label_cy, 0.0, "tithe_label_cut"))
    for i, (wx, wy) in enumerate(WHEEL_CENTERS):
        ptr = pointer_points(wx, wy)
        inserts.append(extrude_xy(ptr, BASE_EXT_H - INSERT_DEPTH, INSERT_DEPTH, f"pointer_{i}_ins"))
        icon_cutters.append(extrude_xy(ptr, BASE_EXT_H - INSERT_DEPTH, INSERT_DEPTH + HOLE_OVERSHOOT,
                                       f"pointer_{i}_cut"))
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

    prev_vol = mesh_volume(shell)
    apply_boolean(shell, join_objects(icon_cutters, "floor_icon_cutters"), 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_vol, f"base: floor icon pockets corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"

    apply_bevel(shell, BEVEL_W)
    return shell, join_objects(inserts, "base_inlay")


# ============================================================
# LID
# ============================================================

LID_Z0 = BASE_EXT_H - LID_SKIRT
LID_Z1 = BASE_EXT_H + LID_T


def build_lid():
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
    assert DICE_ROLL_W < cavity_w - 10.0 and LID_RUNE_W < lid_ext_w - 10.0, "lid icons too wide"

    # 2) Icon pockets - outside rune (top face) + inside dice_roll (slab underside), decorative
    # class, one combined cut (separate zones: 3mm slab, 0.6mm pockets from opposite faces).
    rune, rune_aspect = load_contours(KHORNE_CONTOURS_PATH)
    dice, dice_aspect = load_contours(DICE_ROLL_CONTOURS_PATH)
    inserts = [
        build_icon_solid_xy(rune, LID_RUNE_W, LID_RUNE_W * rune_aspect, cx, cy,
                            LID_Z1 - INSERT_DEPTH, INSERT_DEPTH, "lid_rune_ins"),
        # Mirrored: the inside face is read with the lid flipped over (as a dice tray), which
        # reverses its handedness.
        build_icon_solid_xy(dice, DICE_ROLL_W, DICE_ROLL_W * dice_aspect, cx, cy,
                            BASE_EXT_H, INSERT_DEPTH, "lid_dice_ins", mirror_y=True),
    ]
    cutters = [
        build_icon_solid_xy(rune, LID_RUNE_W, LID_RUNE_W * rune_aspect, cx, cy,
                            LID_Z1 - INSERT_DEPTH, INSERT_DEPTH + HOLE_OVERSHOOT, "lid_rune_cut"),
        build_icon_solid_xy(dice, DICE_ROLL_W, DICE_ROLL_W * dice_aspect, cx, cy,
                            BASE_EXT_H - HOLE_OVERSHOOT, INSERT_DEPTH + HOLE_OVERSHOOT, "lid_dice_cut",
                            mirror_y=True),
    ]
    prev_vol = mesh_volume(shell)
    apply_boolean(shell, join_objects(cutters, "lid_icon_cutters"), 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_vol, f"lid: icon pockets corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"

    apply_bevel(shell, BEVEL_W)
    return shell, join_objects(inserts, "lid_inlay")


# ============================================================
# BLOOD TITHE WHEEL
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
    # EXACT solver (see build_khorne_tokens.py's _build_flat_text_mesh)
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


def export_two_color(name, base, inlay):
    export_stl(base, f"{name}_base.stl")
    export_stl(inlay, f"{name}_inlay.stl")
    export_3mf([(base, BASE_COLOR, "base"), (inlay, INLAY_COLOR, "inlay")],
               os.path.join(EXPORT_DIR, f"{name}.3mf"))
    # Import THIS one in Anycubic Slicer Next - see export_project_3mf's docstring.
    export_project_3mf([(base, "base", BASE_EXTRUDER_SLOT), (inlay, "inlay", INLAY_EXTRUDER_SLOT)],
                       os.path.join(EXPORT_DIR, f"{name}_anycubic.3mf"))


def build_wheel_test():
    """Wheel + test coupon: renders (wheel alone, wheel seated in the coupon) and exports."""
    clear_scene()
    wheel, wheel_inlay = build_wheel()
    report("wheel", wheel)
    report("wheel inlay", wheel_inlay)
    apply_color(wheel, "base_mat", BASE_COLOR)
    apply_color(wheel_inlay, "inlay_mat", INLAY_COLOR)
    bpy.context.view_layer.update()
    render_top("tithe_wheel", elev_deg=80.0)
    export_two_color("tithe_wheel", wheel, wheel_inlay)

    coupon, pointer, (cx, cy, floor_z) = build_wheel_coupon()
    report("coupon", coupon)
    apply_color(coupon, "base_mat", BASE_COLOR)
    apply_color(pointer, "inlay_mat", INLAY_COLOR)
    for o in (wheel, wheel_inlay):
        o.location = (cx, cy, floor_z)   # seat the wheel on the peg for the preview
    bpy.context.view_layer.update()
    render_top("tithe_wheel_coupon", elev_deg=60.0)
    for o in (wheel, wheel_inlay):
        o.location = (0.0, 0.0, 0.0)
    export_two_color("tithe_wheel_test_coupon", coupon, pointer)


def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    os.makedirs(RENDER_DIR, exist_ok=True)

    if "--" in sys.argv and "wheel-test" in sys.argv[sys.argv.index("--") + 1:]:
        build_wheel_test()
        print("Done.")
        return

    clear_scene()
    base, base_inlay = build_base()
    lid, lid_inlay = build_lid()
    for name, obj in (("base", base), ("base inlay", base_inlay), ("lid", lid), ("lid inlay", lid_inlay)):
        report(name, obj)

    # Tithe wheels: export one (print x2), then seat a pair in their pockets for the renders
    wheels = []
    for i, (wx, wy) in enumerate(WHEEL_CENTERS):
        wheel, wheel_inlay = build_wheel()
        apply_color(wheel, "base_mat", BASE_COLOR)
        apply_color(wheel_inlay, "inlay_mat", INLAY_COLOR)
        if i == 0:
            report("wheel", wheel)
            export_two_color("tithe_wheel", wheel, wheel_inlay)
        for o in (wheel, wheel_inlay):
            o.location = (wx, wy, WHEEL_FLOOR_Z)
        wheels += [wheel, wheel_inlay]

    apply_color(base, "base_mat", BASE_COLOR)
    apply_color(lid, "base_mat", BASE_COLOR)
    apply_color(base_inlay, "inlay_mat", INLAY_COLOR)
    apply_color(lid_inlay, "inlay_mat", INLAY_COLOR)
    lid_parts = [lid, lid_inlay]
    base_parts = [base, base_inlay] + wheels

    bpy.context.view_layer.update()   # obj.bound_box is cached - refresh before any render framing
    render_top("box_assembled_closed")

    for o in lid_parts:
        o.location.z += 60.0   # lift the lid off for an "exploded" second shot
    bpy.context.view_layer.update()
    render_top("box_assembled_open")

    for o in lid_parts:
        o.hide_render = True
    render_top("box_base_only", elev_deg=80.0, bounds_objs=base_parts)
    for o in lid_parts:
        o.hide_render = False
    for o in lid_parts:
        o.location.z -= 60.0

    # Flip the lid for export: printed skirt-up, the top slab is the flat first layer - no
    # bridging. This is also the dice-tray orientation, so the render from above checks that the
    # inside dice_roll icon reads correctly (not mirrored) when the lid is used that way.
    lid_cy, lid_cz = EXT_D / 2.0, (LID_Z0 + LID_Z1) / 2.0
    for o in lid_parts:
        reorient_lid_for_print(o, lid_cy, lid_cz)
    bpy.context.view_layer.update()   # obj.bound_box is cached - refresh before framing

    for o in base_parts:
        o.hide_render = True
    render_top("box_lid_as_dice_tray", elev_deg=70.0, bounds_objs=lid_parts)
    render_top("box_lid_top_face", elev_deg=70.0, from_below=True, bounds_objs=lid_parts)
    for o in base_parts:
        o.hide_render = False

    export_two_color("box_base", base, base_inlay)
    export_two_color("box_lid", lid, lid_inlay)

    print("Done.")


if __name__ == "__main__":
    main()
