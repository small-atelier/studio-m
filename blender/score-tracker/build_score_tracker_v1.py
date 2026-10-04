"""
VP/CP/Round score tracker (Blender bpy). Functional not decorative - see
feedback_functional_parts_pipeline memory (plain extrusions + primitives,
minimal booleans, decoration kept as its own non-overlapping category per
feedback_blender_boolean_fragility) - except the wheel, which is
deliberately two-color (see below).

Mechanism: a FRONT plate (flat, square reading-windows + round peg-tip
holes + rim-access notches) and a BACK plate (flat, 9 raised peg+standoff
studs + 9 rim-access notches) sandwich 9 DIGIT WHEELS. Each wheel is a
cog-rimmed disc (grippy sinusoidal knurl, not a functional gear) with
digits 0-9 recessed in a ring on its front face and flush black inserts
in those pockets (white base + black inlay, two-color print - same
recess+insert pattern as blender/combat-modifiers/build_modifier_tokens.py).

THREE wheel variants (WHEEL_VARIANTS), not one shared design - Round
(x1), Tens (x4), Ones (x4). They differ only in where "upright" lands
relative to the wheel's own center (reading_angle): Round's window sits
straight up like a combination-lock wheel; Tens/Ones are mirror images of
each other (+90/-90 deg) so their windows land side by side, between the
pair's two peg-holes, rather than each stacked over its own peg. Every
digit's own ROTATION stays i*36 deg regardless of reading_angle - only
its PLACEMENT gets the extra offset - which is what makes "upright"
follow the window to wherever reading_angle points it (see build_wheel's
docstring for the derivation). The front plate's window placement must
use this exact same angle per wheel, or the shown digit won't be upright.

Board layout (see WHEEL_POSITIONS): portrait board, Round wheel centered
on top, then 4 rows stacked below it - Atk CP, Atk VP, Def CP, Def VP
(VP and CP both run 00-99, so every non-Round wheel position takes a
Tens or Ones wheel, same as any other stat's). The peg-tip hole sits at
each wheel's exact center; the reading window is offset per variant.

Peg/standoff: back plate grows a peg (bore-clearance diameter, reaches
through the wheel and through the front plate, flush with the outside -
glued there) sitting on a wider, shorter boss. The boss is the actual
spin bearing - the wheel's back face rests on that small-diameter boss
only, not the full plate, so friction stays low. A further axial air gap
on the FRONT side (wheel top face to front-plate inner face) means the
wheel never touches the front plate at all.

Rim-access notch: a small window alone is too small to grip and spin the
wheel by. Both plates get a notch per wheel cut into the BOARD'S OWN EDGE
(not a hole through the face) - it starts past the board's outer edge on
whichever side is nearest that wheel and reaches inward past the wheel's
own edge, so a fingertip lands on the actual knurled rim, not just open
face. This has to be OFFSET from the peg axis, not concentric with it -
a hole centered on the peg would leave the boss floating, unwelded to
the surrounding plate.

Run (all parts):
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_score_tracker.py
"""

import bpy
import bmesh
import json
import math
import mathutils
import os
import zipfile

# ============================================================
# CONFIG (all mm)
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEXT_FONT_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "card-stand", "BaskervilleBold.ttf"))

EXPORT_DIR = os.path.join(SCRIPT_DIR, "output")
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1600, 900)

PLATE_T = 2.0
WHEEL_T = 2.0
POCKET_DEPTH = 0.6    # digit recess depth - flush multi-material insert, see build_wheel
POCKET_POKE = 0.4     # pocket cutter overshoot past the face it recesses into
EMBED = 0.3          # union/overlap embed depth, see feedback_blender_boolean_fragility
OVERSHOOT = 0.5       # through-cutter overshoot past the surface it cuts

COG_TEETH = 20        # smooth sinusoidal "knurl" around the wheel rim - grip for spinning,
COG_DEPTH = 1.2       # not a functional gear (nothing meshes with it)

AXIAL_CLEARANCE = 0.3  # air gap: wheel front face -> front plate inner face
BORE_CLEARANCE = 0.6   # diametral clearance: peg -> wheel bore hole

PEG_D = 4.5   # base/main shaft - thickened; the old 3.0 moved to TIP_D instead (kept, for
              # the part through the front plate)
BORE_D = PEG_D + BORE_CLEARANCE   # bigger peg -> bigger wheel bore, automatically
BOSS_D = 7.5   # grown to keep the same 1.5mm per-side overhang past PEG_D as before
BOSS_H = 0.6

# Peg is STEPPED, not a constant diameter: full PEG_D through the boss and the wheel's
# bore, then a narrower TIP_D for the final stretch through the front plate. The step
# is a real physical shoulder (lip) sized to land exactly at the front plate's inner
# face, so the front plate bottoms out against the lip instead of against the wheel -
# gluing pressure can't ever close up AXIAL_CLEARANCE and pinch the wheel. Tip length
# matches PLATE_T exactly, so it ends flush with the front's outer face.
TIP_D = 3.0   # the old PEG_D value - kept as-is for the tip, only the base grew
FRONT_HOLE_D = TIP_D + 0.2   # snug glue fit through the front plate
PEG_MAIN_LEN = BOSS_H + WHEEL_T + AXIAL_CLEARANCE   # back plate ref -> the shoulder
TIP_LEN = PLATE_T

# back plate: everywhere EXCEPT the 9 wheel spots is built up an extra RAISE_H, on the
# EXTERIOR (back-facing) side only - the wheel-facing surface where pegs root stays a
# flat, uniform plane everywhere, so this has zero effect on the peg geometry above
# (pockets remove the raised material exactly where a peg would otherwise meet it).
# Each wheel ends up sitting in a round recessed pocket, walled in by the raised field
# around it. Pocket diameter has clearance beyond the wheel so the knurled rim can spin
# freely without rubbing the wall.
RAISE_H = 5.0
# Kept below 1.0 deliberately: at 1.0, two adjacent (tens/ones) pockets' diameters sum
# to EXACTLY WHEEL_PITCH (22mm) - a zero-gap tangent-circles case, a coincident-face
# boolean fragility trigger (found the hard way: 1.04% non-manifold on the back plate,
# traced to the pocket-cut difference alone). 0.8 leaves a real ~0.4mm wall instead.
WHEEL_POCKET_CLEARANCE = 0.8

WHEEL_D = 30.0
WHEEL_R = WHEEL_D / 2.0
WHEEL_POCKET_D = WHEEL_D + 2.0 * WHEEL_POCKET_CLEARANCE
DIGIT_R = 9.75         # ring radius the digits (and the reading window) sit at - scales with WHEEL_D
DIGIT_SIZE = 10.0      # was 4.8 (too small/illegible on a real test print), doubled to 9.6, now 10
N_DIGITS = 10

WINDOW_W = 6.75        # scales with WHEEL_D
WINDOW_H = 7.8         # scales with WHEEL_D

# rim-access notch, cut into the board's own SIDE EDGE (not a hole through the face) -
# same notch on both front and back plates. Reaches in from whichever board edge is
# nearest the wheel, past the wheel's own edge, so a fingertip lands on the knurled rim
# from the side. Needed because the front window alone is too small to grip/spin by.
# How far past the wheel's tangent point the notch reaches inward. Real ceiling is the
# boss/peg at the wheel's exact center (BOSS_D/2 radius) - the notch's closest approach
# to center is WHEEL_R - NOTCH_REACH, which has to clear the boss with a real wall, not
# just avoid touching it. 8.0 corrupted the back plate to 0 volume (some other overlap,
# not yet isolated) - reverted to the proven-clean 4.5 for now.
NOTCH_REACH = 4.5

# Wedge shape (wide mouth, flat tip) - see _wedge_points.
WEDGE_OUTER_W = 20.0   # width at the board edge (the mouth) - ROW_GAP (32.6) leaves 12.6mm
WEDGE_TIP_W = 10.0      # clearance to the next row's notch, still comfortably clear


BEVEL_W = 0.4
PLATE_CORNER_R = 0.5   # must stay <= SIDE_MARGIN or the corner rounding overshoots it

WHEEL_BASE_COLOR = (1.0, 1.0, 1.0, 1.0)
WHEEL_INLAY_COLOR = (0.03, 0.03, 0.03, 1.0)
BASE_EXTRUDER_SLOT = 1
INLAY_EXTRUDER_SLOT = 2

TEXT_SPACING = 1.1     # see feedback_blender_boolean_fragility - unused here (single
                        # glyphs only, never touching), kept for parity if labels are added later

# --- board layout: wheel centers, in the plate's own (x, z) plane. Portrait board -
# narrow width (one wheel-pair wide), tall height (5 rows stacked): Round centered on
# top, then Atk CP / Atk VP / Def CP / Def VP pairs stacked below it, top to bottom.
#
# WHEEL_PITCH and ROW_GAP are DERIVED from WHEEL_POCKET_D, not hardcoded - adjacent
# pockets (tens/ones within a row, or one row's wheel to the next row's) must clear
# each other by a real wall, not just avoid overlapping outright. At exactly
# pocket-diameter spacing the two circles are tangent - a zero-gap coincident-face
# boolean fragility trigger (found the hard way: WHEEL_PITCH used to be hardcoded at
# exactly WHEEL_POCKET_D, and it corrupted the back plate to 1% non-manifold). Deriving
# both from the same formula also means a future WHEEL_D change can't reintroduce this. ---
MIN_POCKET_WALL = 1.0   # minimum solid wall between two adjacent pockets
WHEEL_PITCH = WHEEL_POCKET_D + MIN_POCKET_WALL   # tens -> ones center distance within one stat
ROW_GAP = WHEEL_POCKET_D + MIN_POCKET_WALL        # row -> row center distance

# Margin is asymmetric on purpose. Left/right pull in as tight as a real wall allows
# (SIDE_MARGIN) - the edge ends up basically tangent to the wheels there. Top gets a
# little more room than that (TOP_MARGIN > SIDE_MARGIN) so Round sits slightly off the
# very edge rather than exactly flush - purely a deliberate visual choice, not a
# structural need (SIDE_MARGIN's value is already proven safe up top too). Bottom keeps
# the original, roomier MARGIN. See the _z_shift derivation below for how the board
# rectangle (built symmetric, centered at 0) ends up with the wheel layout shifted
# inside it to make top/bottom gaps come out different on purpose.
SIDE_MARGIN = 0.6   # left, right - as tight as a printable wall allows
TOP_MARGIN = 1.5     # a bit more than SIDE_MARGIN - Round sits back from the edge slightly
MARGIN = 1.0           # bottom only, from here on

_STAT_ROWS = ["atk_cp", "atk_vp", "def_cp", "def_vp"]
_N_ROWS = 1 + len(_STAT_ROWS)  # + Round

# Round -> Atk CP gets extra room (MYTHOS_EXTRA_GAP on top of the normal ROW_GAP) for
# the Mythos badge that replaces Turn's old spot there - see build_mythos_badge. The 4
# stat rows stay evenly spaced at ROW_GAP among themselves. Derived from a fixed CLEAR
# gap target (proven enough for the badge content) rather than a flat extra number, so
# it stays correct if ROW_GAP/WHEEL_R ever change (the badge doesn't scale with the
# wheel - it needs the same physical clearance regardless of wheel size).
BADGE_CLEAR_GAP = 18.0   # grown to fit the bigger Mythos badge (see MYTHOS_ICON_W etc below)
MYTHOS_EXTRA_GAP = (2.0 * WHEEL_R + BADGE_CLEAR_GAP) - ROW_GAP

# Atk CP -> Atk VP and Def CP -> Def VP each get extra room too - both of that group's
# labels ("ATTACKER CP" + "ATTACKER VP") stack together in this ONE gap between the
# pair, instead of each being under its own row (see build_front_plate). At
# LABEL_SIZE=6.0 two stacked lines (~4.2mm effective height each, 0.7x the nominal
# size - same rule of thumb used for the Mythos text estimate) plus a line gap and
# buffer need ~14mm clear; this is that minus the ~2.6mm already free between wheel
# edges at ROW_GAP's baseline spacing.
LABEL_PAIR_EXTRA_GAP = 0.0   # structural row spacing is now uniform across all 4 stat
                               # rows - the label text has to fit in whatever's left over,
                               # not the other way around (see line_gap in build_front_plate)
# Between a group's own VP row and the next group's CP row, no label lives there
# anymore, so that gap stays at the plain minimal ROW_GAP.
_row_gaps = [
    ROW_GAP + MYTHOS_EXTRA_GAP if i == 0 else
    ROW_GAP + LABEL_PAIR_EXTRA_GAP if i in (1, 3) else
    ROW_GAP
    for i in range(_N_ROWS - 1)
]
_raw_z = [0.0]
for _g in _row_gaps:
    _raw_z.append(_raw_z[-1] - _g)

# Board rect is still built symmetric (centered at 0, see board_footprint) - asymmetric
# top/bottom margins are achieved by shifting the WHEEL layout inside it instead, so
# the top edge sits TOP_MARGIN past Round and the bottom edge sits MARGIN past Def VP.
_top_extra = max(WHEEL_R, DIGIT_R + WINDOW_H / 2.0)
_top_gap = _top_extra + TOP_MARGIN
_bottom_gap = WHEEL_R + MARGIN
_board_h = (max(_raw_z) - min(_raw_z)) + _top_gap + _bottom_gap
_required_max_z = _board_h / 2.0 - _top_gap
_z_shift = _required_max_z - max(_raw_z)
_ROW_Z = [_z + _z_shift for _z in _raw_z]


def _row_z(row_index):
    """row_index 0 = top (Round), higher index = further down the board. Centered on
    z=0 to match the plate rectangle, which is built centered on the origin."""
    return _ROW_Z[row_index]


WHEEL_POSITIONS = [("round", 0.0, _row_z(0))]
for _j, _name in enumerate(_STAT_ROWS):
    _z = _row_z(_j + 1)
    WHEEL_POSITIONS.append((f"{_name}_tens", -WHEEL_PITCH / 2.0, _z))
    WHEEL_POSITIONS.append((f"{_name}_ones", WHEEL_PITCH / 2.0, _z))

PEG_LEN = PEG_MAIN_LEN + TIP_LEN   # total, for reference/printing (module docstring, etc)

# row labels - recessed text in the ~10mm clear gap below each of the 4 stat rows (the
# board's center strip, x roughly -18..18, is untouched by the side notches for the
# board's full height, so this gap is free the whole way down - see build_front_plate).
# Round has no gap-label - Turn moved to the side of the wheel to free that gap for the
# Mythos badge (see TURN_LABEL_POS / build_mythos_badge).
LABEL_SIZE = 10.0   # matches DIGIT_SIZE - testing fit, board not grown to accommodate

DIVIDER_W = 36.0   # plain recessed bar between the Attacker/Defender halves
DIVIDER_H = 1.2
_WORDS = {"atk": "ATTACKER", "def": "DEFENDER"}
ROW_LABEL_TEXT = [" ".join(_WORDS.get(p, p.upper()) for p in name.split("_")) for name in _STAT_ROWS]

# Turn's position is computed in build_front_plate instead (top-right corner, needs
# board_w/board_h which aren't known yet at this point in the file).

# Mythos badge - icon + wordmark + frame, sized to fit the Round -> Atk CP gap (see
# MYTHOS_EXTRA_GAP). Reuses the already-traced logo contours from the card-stand
# project (same file blender/combat-modifiers/build_modifier_tokens.py's own Mythos
# bonus token loads) rather than re-tracing anything.
MYTHOS_CONTOURS_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "card-stand", "logo_contours_v5.json"))
MYTHOS_ASPECT = 376.0 / 720.0
MYTHOS_ICON_W = 30.0    # doubled, then +50% more
MYTHOS_TEXT_SIZE = 7.8  # reverted - doubling overflowed its own frame, see git history/chat
MYTHOS_FRAME_MARGIN = 1.0   # shrunk, so the frame hugs the (now bigger) content tighter
MYTHOS_FRAME_THICKNESS = 0.6
MYTHOS_FRAME_CORNER_R = 1.5

# ============================================================
# GENERIC HELPERS (ported as-is from blender/combat-modifiers/build_modifier_tokens.py -
# see that file's comments for why each fix exists; not re-derived here)
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


def apply_transform(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def apply_bevel(obj, width, segments=2):
    mod = obj.modifiers.new("Bevel", 'BEVEL')
    mod.width = width
    mod.segments = segments
    mod.limit_method = 'ANGLE'
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
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


def join_objects(objs, name):
    if len(objs) == 1:
        objs[0].name = name
        return objs[0]
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    objs[0].name = name
    return objs[0]


def _extrude_profile(points, offset, thickness, name):
    """Build a flat face from a closed (x, z) point loop and extrude it
    along Y (the plate's depth axis while authoring - see reorient_for_print)."""
    bm = bmesh.new()
    verts = [bm.verts.new((p[0], offset, p[1])) for p in points]
    face = bm.faces.new(verts)
    result = bmesh.ops.extrude_face_region(bm, geom=[face])
    new_verts = [v for v in result['geom'] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0.0, thickness, 0.0), verts=new_verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def _cylinder(diameter, offset, thickness, x, z, name, segments=32):
    r = diameter / 2.0
    pts = [(x + r * math.cos(2 * math.pi * i / segments), z + r * math.sin(2 * math.pi * i / segments))
           for i in range(segments)]
    return _extrude_profile(pts, offset, thickness, name)


def _rect(w, h, offset, thickness, x, z, name):
    hw, hh = w / 2.0, h / 2.0
    pts = [(x - hw, z - hh), (x + hw, z - hh), (x + hw, z + hh), (x - hw, z + hh)]
    return _extrude_profile(pts, offset, thickness, name)


def _wedge_points(inner, outer, center, tip_half_w, outer_half_w, reach_is_x):
    """4-point wedge: wide at `outer` (past the board edge), narrowing to a FLAT tip
    (not a point) at `inner`. Flat tip gives a controlled, predictable boundary near
    the peg - a circle's closest approach is a single point that curves away on either
    side, a wedge holds a known width the whole way to the tip. `reach_is_x` selects
    which axis is the reach direction (x for side notches, z for the top notch) -
    `center` is the fixed coordinate on the other axis."""
    if reach_is_x:
        return [(inner, center - tip_half_w), (outer, center - outer_half_w),
                (outer, center + outer_half_w), (inner, center + tip_half_w)]
    return [(center - tip_half_w, inner), (center - outer_half_w, outer),
            (center + outer_half_w, outer), (center + tip_half_w, inner)]


def side_notch(wheel_x, wheel_z, side, board_w, offset, thickness, name):
    """side: -1 = left edge, +1 = right edge."""
    inner_x = wheel_x + side * (WHEEL_R - NOTCH_REACH)
    outer_x = side * (board_w / 2.0 + OVERSHOOT)
    pts = _wedge_points(inner_x, outer_x, wheel_z, WEDGE_TIP_W / 2.0, WEDGE_OUTER_W / 2.0, reach_is_x=True)
    return _extrude_profile(pts, offset, thickness, name)


def top_notch(wheel_x, wheel_z, board_h, offset, thickness, name):
    inner_z = wheel_z + (WHEEL_R - NOTCH_REACH)
    outer_z = board_h / 2.0 + OVERSHOOT
    pts = _wedge_points(inner_z, outer_z, wheel_x, WEDGE_TIP_W / 2.0, WEDGE_OUTER_W / 2.0, reach_is_x=False)
    return _extrude_profile(pts, offset, thickness, name)


def wheel_notch(name, x, z, board_w, board_h, offset, thickness):
    """Round comes in from the board's top edge (it has no natural left/right
    neighbor to point a side notch away from); every other wheel notches from
    whichever side edge is nearest."""
    cut_name = f"{name}_notch_cut"
    if name == "round":
        return top_notch(x, z, board_h, offset, thickness, cut_name)
    side = 1 if x >= 0 else -1
    return side_notch(x, z, side, board_w, offset, thickness, cut_name)


def cog_circle_points(diameter, teeth, depth, x=0.0, z=0.0, n=240):
    """Circle profile with a smooth sinusoidal ripple - a grippy knurled rim, not a
    functional gear. Continuous/smooth (no sharp reentrant corners) so it stays
    boolean-safe per feedback_blender_boolean_fragility."""
    r_mid = diameter / 2.0 - depth / 2.0
    amp = depth / 2.0
    pts = []
    for i in range(n):
        theta = 2 * math.pi * i / n
        r = r_mid + amp * math.cos(teeth * theta)
        pts.append((x + r * math.sin(theta), z + r * math.cos(theta)))
    return pts


def carve_and_collect_inlay(shell, inserts, cutters, name_prefix):
    prev_volume = mesh_volume(shell)
    cutter_union = join_objects(cutters, f"{name_prefix}_cutters")
    apply_boolean(shell, cutter_union, 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_volume, (
        f"{name_prefix}: pocket cut did not remove a sane amount of material "
        f"({prev_volume:.1f} -> {vol:.1f}mm3) - likely EXACT-solver corruption."
    )
    inlay = join_objects(inserts, f"{name_prefix}_inlay")
    return shell, inlay


def rounded_rect_points(w, h, r, x=0.0, z=0.0, n_corner=6):
    hw, hh = w / 2.0 - r, h / 2.0 - r
    centers = [(x + hw, z + hh), (x - hw, z + hh), (x - hw, z - hh), (x + hw, z - hh)]
    start_angles = [0.0, 90.0, 180.0, 270.0]
    pts = []
    for (cx, cz), a0 in zip(centers, start_angles):
        for i in range(n_corner + 1):
            a = math.radians(a0 + 90.0 * i / n_corner)
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return pts


def load_contours(path):
    with open(path) as f:
        return json.load(f)


def dedupe_closed_loop(points, tol=1e-9):
    """Traced contours can come back as closed rings with the first and last point
    identical - a degenerate zero-length edge that corrupts topology if left in.
    Ported from blender/combat-modifiers/build_modifier_tokens.py's own version."""
    if len(points) > 1:
        x0, y0 = points[0]
        x1, y1 = points[-1]
        if abs(x0 - x1) < tol and abs(y0 - y1) < tol:
            return points[:-1]
    return points


def build_icon_solid_flat(contours, icon_w, icon_h, cx, icon_center_z, poke, name_prefix):
    """Traced-icon solid, single-sided (no front/back mirroring - the front plate only
    ever shows one face). Ported from build_modifier_tokens.py's build_icon_solid;
    per-contour chained union with holes cut after, same as there - see that file's
    docstring for why (built as its own free-standing composite before ever touching
    the plate, not chained directly onto a growing shell)."""
    icon_x0 = cx - icon_w / 2.0
    icon_z0 = icon_center_z - icon_h / 2.0
    thickness = POCKET_DEPTH + poke
    offset = -poke

    outer_pts, hole_pts = [], []
    for c in contours:
        pts = [(icon_x0 + u * icon_w, icon_z0 + v * icon_h) for u, v in c["points"]]
        pts = dedupe_closed_loop(pts)
        (hole_pts if c["hole"] else outer_pts).append(pts)
    assert outer_pts, f"{name_prefix}: traced icon has no outer contours"

    solid = _extrude_profile(outer_pts[0], offset, thickness, f"{name_prefix}_0")
    for i, pts in enumerate(outer_pts[1:], start=1):
        solid = apply_boolean(solid, _extrude_profile(pts, offset, thickness, f"{name_prefix}_{i}"), 'UNION')
    for i, pts in enumerate(hole_pts):
        cutter = _extrude_profile(pts, offset - OVERSHOOT, thickness + 2 * OVERSHOOT, f"{name_prefix}_hole_{i}")
        solid = apply_boolean(solid, cutter, 'DIFFERENCE')
    return solid


def build_frame_ring(w, h, ring_w, corner_r, cx, cz, poke, name_prefix):
    thickness = POCKET_DEPTH + poke
    offset = -poke
    outer = _extrude_profile(rounded_rect_points(w, h, corner_r, cx, cz), offset, thickness, f"{name_prefix}_outer")
    inner_r = max(0.3, corner_r - ring_w)
    inner_cut = _extrude_profile(rounded_rect_points(w - 2 * ring_w, h - 2 * ring_w, inner_r, cx, cz),
                                  offset - OVERSHOOT, thickness + 2 * OVERSHOOT, f"{name_prefix}_inner_cut")
    apply_boolean(outer, inner_cut, 'DIFFERENCE')
    return outer


def build_mythos_badge(cx, cz):
    """Icon + MYTHOS wordmark + frame, all recessed/inlaid - same visual language as
    the Mythos bonus token in blender/combat-modifiers/build_modifier_tokens.py,
    reusing its already-traced logo contours rather than re-tracing anything. Returns
    (inserts, cutters) to fold into the front plate's own label pass."""
    contours = load_contours(MYTHOS_CONTOURS_PATH)
    icon_h = MYTHOS_ICON_W * MYTHOS_ASPECT
    text_h_est = MYTHOS_TEXT_SIZE * 0.7
    inner_gap = 1.0
    content_h = icon_h + inner_gap + text_h_est
    top_z = cz + content_h / 2.0

    inserts, cutters = [], []
    icon_center_z = top_z - icon_h / 2.0
    for poke, bucket in ((0.0, inserts), (POCKET_POKE, cutters)):
        bucket.append(build_icon_solid_flat(contours, MYTHOS_ICON_W, icon_h, cx, icon_center_z, poke, "mythos_icon"))

    text_center_z = top_z - icon_h - inner_gap - text_h_est / 2.0
    for poke, bucket in ((0.0, inserts), (POCKET_POKE, cutters)):
        thickness = POCKET_DEPTH + poke
        glyph = _build_flat_text_mesh("MYTHOS", MYTHOS_TEXT_SIZE, thickness)
        glyph.rotation_euler = (math.radians(90.0), 0.0, 0.0)
        glyph.location = (cx, -poke + thickness / 2.0, text_center_z)
        apply_transform(glyph)
        bucket.append(glyph)

    frame_w = max(MYTHOS_ICON_W, MYTHOS_TEXT_SIZE * 3.6) + 2 * MYTHOS_FRAME_MARGIN
    frame_h = content_h + 2 * MYTHOS_FRAME_MARGIN
    for poke, bucket in ((0.0, inserts), (POCKET_POKE, cutters)):
        bucket.append(build_frame_ring(frame_w, frame_h, MYTHOS_FRAME_THICKNESS, MYTHOS_FRAME_CORNER_R,
                                        cx, cz, poke, "mythos_frame"))

    return inserts, cutters


def _build_flat_text_mesh(text, size, thickness, font_path=TEXT_FONT_PATH):
    font = bpy.data.fonts.load(font_path)
    curve_data = bpy.data.curves.new(f"{text}_curve", type='FONT')
    curve_data.body = text
    curve_data.font = font
    curve_data.size = size
    curve_data.align_x = 'CENTER'
    curve_data.align_y = 'CENTER'
    curve_data.space_character = TEXT_SPACING
    curve_data.extrude = thickness / 2.0
    obj = bpy.data.objects.new(text, curve_data)
    bpy.context.collection.objects.link(obj)

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-3)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def export_stl(obj, filename):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = os.path.join(EXPORT_DIR, filename)
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"Exported {path}")


def export_3mf(parts, path):
    """Standard 3MF with the materials-extension <colorgroup> - portable across
    slicers that actually read it (Bambu Studio, PrusaSlicer, Cura...). Ported as-is
    from blender/tokens/build_tokens.py's export_3mf. `parts` is a list of
    (obj, (r, g, b, a), name), 0..1 each. A single 3MF with multiple objects keeps
    base/inlay in the same coordinate space, so they stay aligned on import."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

    colors = []
    color_index = {}

    def color_id(rgba):
        key = tuple(round(c, 4) for c in rgba)
        if key not in color_index:
            color_index[key] = len(colors)
            colors.append(key)
        return color_index[key]

    objects_xml = []
    build_items = []
    next_id = 2   # id=1 is reserved for the colorgroup resource

    for obj, rgba, name in parts:
        mesh = obj.data
        mesh.calc_loop_triangles()
        mw = obj.matrix_world

        verts_xml = "".join(
            f'<vertex x="{co.x:.5f}" y="{co.y:.5f}" z="{co.z:.5f}"/>'
            for co in (mw @ v.co for v in mesh.vertices)
        )
        tris_xml = "".join(
            f'<triangle v1="{t.vertices[0]}" v2="{t.vertices[1]}" v3="{t.vertices[2]}"/>'
            for t in mesh.loop_triangles
        )

        obj_id = next_id
        next_id += 1
        objects_xml.append(
            f'<object id="{obj_id}" name="{name}" type="model" pid="1" pindex="{color_id(rgba)}">'
            f'<mesh><vertices>{verts_xml}</vertices>'
            f'<triangles>{tris_xml}</triangles></mesh></object>'
        )
        build_items.append(f'<item objectid="{obj_id}"/>')

    colors_xml = "".join(
        f'<m:color color="#{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}{int(a*255):02X}"/>'
        for (r, g, b, a) in colors
    )

    model_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
        'xmlns:m="http://schemas.microsoft.com/3dmanufacturing/material/2015/02">'
        f'<resources><m:colorgroup id="1">{colors_xml}</m:colorgroup>'
        f'{"".join(objects_xml)}</resources>'
        f'<build>{"".join(build_items)}</build></model>'
    )

    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
        '</Types>'
    )

    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        '</Relationships>'
    )

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("3D/3dmodel.model", model_xml)
    print(f"Exported {path}")


def export_project_3mf(parts, path):
    """Anycubic Slicer Next's own project-3mf flavor - ported as-is from
    blender/combat-modifiers/build_modifier_tokens.py's export_project_3mf. That
    slicer ignores the standard 3MF color hint entirely and only reads its own
    `extruder` metadata per part, referencing whatever filament is physically
    loaded in that numbered slot. `parts` is a list of (obj, name, extruder_slot)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

    leaf_objects_xml, components_xml, parts_config_xml = [], [], []
    next_id = 1

    for obj, name, slot in parts:
        mesh = obj.data
        mesh.calc_loop_triangles()
        mw = obj.matrix_world
        verts_xml = "".join(
            f'<vertex x="{co.x:.5f}" y="{co.y:.5f}" z="{co.z:.5f}"/>'
            for co in (mw @ v.co for v in mesh.vertices)
        )
        tris_xml = "".join(
            f'<triangle v1="{t.vertices[0]}" v2="{t.vertices[1]}" v3="{t.vertices[2]}"/>'
            for t in mesh.loop_triangles
        )
        leaf_id = next_id
        next_id += 1
        leaf_objects_xml.append(
            f'<object id="{leaf_id}" type="model">'
            f'<mesh><vertices>{verts_xml}</vertices>'
            f'<triangles>{tris_xml}</triangles></mesh></object>'
        )
        components_xml.append(f'<component objectid="{leaf_id}"/>')
        parts_config_xml.append(
            f'<part id="{leaf_id}" subtype="normal_part">'
            f'<metadata key="name" value="{name}.stl"/>'
            f'<metadata key="extruder" value="{slot}"/></part>'
        )

    parent_id = next_id
    model_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        f'<resources>{"".join(leaf_objects_xml)}'
        f'<object id="{parent_id}" type="model">'
        f'<components>{"".join(components_xml)}</components></object>'
        f'</resources>'
        f'<build><item objectid="{parent_id}"/></build></model>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
        '</Types>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Target="/3D/3dmodel.model" Id="rel-1" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        '</Relationships>'
    )
    model_settings = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<config>'
        f'<object id="{parent_id}">'
        '<metadata key="name" value="plate"/>'
        f'{"".join(parts_config_xml)}'
        '</object></config>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("3D/3dmodel.model", model_xml)
        zf.writestr("Metadata/model_settings.config", model_settings)
    print(f"Exported {path}")


def reorient_for_print(obj, thickness):
    """Y (thickness, [0, thickness]) -> Z (print build direction); Z (shape's own
    in-plane vertical) -> Y. Ported from build_modifier_tokens.py's version. Assumes
    the object's real Y-extent IS `thickness` - true for the wheel and front plate
    (flat, uniform depth) but NOT the back plate (pegs and the raised field stick out
    well past PLATE_T) - see reorient_back_for_print for that one instead."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for v in bm.verts:
        x, y, z = v.co
        v.co = (x, z, thickness - y)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def reorient_back_for_print(obj):
    """Back plate specifically: the flat exterior face (the plate's minimum Y - after
    build_raised_field's fix, this is a single uniform plane the whole board over) ends
    up as the print-bed contact face (Z=0), with the pegs and the raised field's walls
    building straight UP from there - no supports needed for the vertical peg posts.
    Can't reuse reorient_for_print's thickness-based formula here: that assumes the
    object's real Y-extent equals a known flat thickness, which isn't true once pegs
    (up to PEG_MAIN_LEN+TIP_LEN) and the raised field (up to PLATE_T+RAISE_H) stick out
    well past PLATE_T - using PLATE_T there was a real bug (part of the geometry landing
    at negative Z, invalid for slicing) and also put the wrong face down anyway."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    y_min = min(v.co.y for v in bm.verts)
    for v in bm.verts:
        x, y, z = v.co
        v.co = (x, z, y - y_min)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    return obj


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
    return center, size, (max(xs) - min(xs)), (max(zs) - min(zs))


def setup_camera_and_light(center, distance, ortho_scale, from_back=False, raking=False):
    sign = 1.0 if from_back else -1.0
    cam_data = bpy.data.cameras.new("RenderCam")
    cam_data.type = 'ORTHO'
    cam_data.sensor_fit = 'VERTICAL'   # ortho_scale always means vertical extent - see render_scene
    cam_data.ortho_scale = ortho_scale
    cam = bpy.data.objects.new("RenderCam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = center + mathutils.Vector((0.0, sign * distance, 0.0))
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam

    light_data = bpy.data.lights.new("RenderLight", type='SUN')
    light_data.energy = 3.0
    light = bpy.data.objects.new("RenderLight", light_data)
    bpy.context.collection.objects.link(light)
    # `raking` puts the light mostly to the side (small Y/depth component) so shallow
    # embossed relief (the wheel's 0.6mm digits) actually casts a visible shadow -
    # the default near-frontal light (dominant Y term) washes flat relief out entirely.
    if raking:
        light.location = center + mathutils.Vector((distance * 1.1, sign * distance * 0.35, distance * 0.5))
    else:
        light.location = center + mathutils.Vector((distance * 0.3, sign * distance * 1.5, distance * 0.6))
    direction = center - light.location
    light.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    return cam


def render_scene(name, from_back=False, raking=False):
    center, size, x_extent, z_extent = compute_scene_bounds()
    distance = size * 1.2
    # sensor_fit is 'VERTICAL' (see setup_camera_and_light), so ortho_scale must cover the
    # full Z-extent AND, given the render's landscape aspect, whatever Z-equivalent height
    # the X-extent would need too - otherwise a tall/narrow board (or a wide/short one)
    # clips on whichever axis the naive "biggest bounding dimension" guess got wrong.
    aspect = RENDER_RESOLUTION[0] / RENDER_RESOLUTION[1]
    needed_height = max(z_extent, x_extent / aspect)
    setup_camera_and_light(center, distance, needed_height * 1.15, from_back=from_back, raking=raking)
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = RENDER_RESOLUTION
    scene.render.filepath = os.path.join(RENDER_DIR, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {scene.render.filepath}")


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


# ============================================================
# WHEEL - three variants: ROUND, TENS, ONES. All three share the same cog
# rim/bore/pocket construction; they differ only in READING_ANGLE, which
# is where the window is relative to that wheel's own center (0 = straight
# up for Round; +-90 deg for Tens/Ones, so their windows land side by side
# between the two peg-holes of a pair instead of each stacked over its own
# peg - see the front-plate window placement using the same angle).
# ============================================================

WHEEL_VARIANTS = {
    "round": 180.0,   # window below the peg, not above - see build_front_plate's window/notch note
    "tens": 90.0,
    "ones": -90.0,
}


def variant_for(name):
    if name.endswith("_tens"):
        return "tens"
    if name.endswith("_ones"):
        return "ones"
    return "round"


def build_wheel(reading_angle_deg=0.0):
    """Returns (base, inlay) - base is the white disc (cog rim, digit pockets, bore
    hole), inlay is the black digit inserts, flush in those pockets. Two-color print,
    same recess+insert pattern as blender/combat-modifiers/build_modifier_tokens.py.

    `reading_angle_deg` is where "upright" lands, measured the same way as the digit
    ring itself (clockwise from top). Digit i's ROTATION always stays i*36 deg
    (unchanged) - only its PLACEMENT angle gets the reading_angle added on top. That
    split is what makes "upright" happen at reading_angle instead of always at top:
    spinning the wheel by -i*36 (bringing digit i's placement back to reading_angle)
    also zeroes its rotation, regardless of what reading_angle is - see the window
    placement in build_front_plate/build_back_plate, which must use the same angle."""
    disc = _extrude_profile(cog_circle_points(WHEEL_D, COG_TEETH, COG_DEPTH), 0.0, WHEEL_T, "wheel_disc")
    apply_bevel(disc, BEVEL_W)

    # bore hole - own category, own single difference
    bore_cutter = _cylinder(BORE_D, -OVERSHOOT, WHEEL_T + 2 * OVERSHOOT, 0.0, 0.0, "wheel_bore_cut")
    prev_vol = mesh_volume(disc)
    apply_boolean(disc, bore_cutter, 'DIFFERENCE')
    vol = mesh_volume(disc)
    assert 0.0 < vol < prev_vol, f"wheel: bore cut corrupted the disc ({prev_vol:.1f} -> {vol:.1f}mm3)"

    # digit ring - recessed pockets + flush inserts (own category, one difference for
    # the pockets).
    reading_angle = math.radians(reading_angle_deg)
    offset = WHEEL_T - POCKET_DEPTH
    inserts, cutters = [], []
    for i in range(N_DIGITS):
        rot_angle = math.radians(i * 360.0 / N_DIGITS)
        pos_angle = rot_angle + reading_angle
        x = DIGIT_R * math.sin(pos_angle)
        z = DIGIT_R * math.cos(pos_angle)
        for poke, bucket in ((0.0, inserts), (POCKET_POKE, cutters)):
            thickness = POCKET_DEPTH + poke
            glyph = _build_flat_text_mesh(str(i), DIGIT_SIZE, thickness)
            glyph.rotation_euler = (math.radians(90.0), rot_angle, 0.0)
            glyph.location = (x, offset + thickness / 2.0, z)
            apply_transform(glyph)
            bucket.append(glyph)

    return carve_and_collect_inlay(disc, inserts, cutters, "wheel")


# ============================================================
# BACK PLATE - flat rounded rect + 9 raised peg/boss studs (one union)
# ============================================================


def build_raised_field(board_w, board_h):
    """Everywhere EXCEPT the 9 wheel spots is built up RAISE_H on the INTERIOR
    (wheel-facing, +Y) side of the PLATE_T base - so the EXTERIOR (the true backside,
    Y=0) stays a single uniform flat plane across the whole board: no stepping, no
    dimples. The wheel-facing side is where the pocket walls / raised rim around each
    wheel actually need to be - that's the side the wheel and its peg interact with.
    Own category/difference for the 9 pocket holes, before this ever gets unioned onto
    the base."""
    layer = _extrude_profile(rounded_rect_points(board_w, board_h, PLATE_CORNER_R),
                              PLATE_T - EMBED, RAISE_H + EMBED, "back_raised")
    pockets = []
    for name, x, z in WHEEL_POSITIONS:
        pockets.append(_cylinder(WHEEL_POCKET_D, PLATE_T - EMBED - OVERSHOOT, RAISE_H + EMBED + 2 * OVERSHOOT,
                                  x, z, f"{name}_pocket_cut"))
    pocket_union = join_objects(pockets, "back_pockets")
    prev_vol = mesh_volume(layer)
    apply_boolean(layer, pocket_union, 'DIFFERENCE')
    vol = mesh_volume(layer)
    assert 0.0 < vol < prev_vol, f"back plate: wheel-pocket cut corrupted the raised field ({prev_vol:.1f} -> {vol:.1f}mm3)"
    return layer


def build_back_plate(board_w, board_h):
    base = _extrude_profile(rounded_rect_points(board_w, board_h, PLATE_CORNER_R), 0.0, PLATE_T, "back_base")
    raised = build_raised_field(board_w, board_h)
    prev_vol = mesh_volume(base)
    plate = apply_boolean(base, raised, 'UNION')
    vol = mesh_volume(plate)
    assert vol > prev_vol, f"back plate: raised field union did not add material ({prev_vol:.1f} -> {vol:.1f}mm3)"

    # rim-access notch per wheel, done BEFORE the peg/boss union so the union has solid
    # plate to weld onto - see module docstring on why this can't be a hole concentric
    # with the peg (the boss would end up floating, unconnected). Thickness spans from
    # past the exterior (Y=0) face to past the raised field's inner (+Y) extent, so it
    # cuts clean through whichever layer(s) are present there.
    #
    # ONE SEQUENTIAL DIFFERENCE PER NOTCH, not all 9 joined into one cutter first - each
    # notch individually is clean against this target (verified), but joining all 9 into
    # one mesh and differencing once corrupted the plate to 0 volume. Textbook
    # feedback_blender_boolean_fragility case: a cutter clean in isolation can still
    # corrupt once combined with others against real overlapping target geometry.
    for name, x, z in WHEEL_POSITIONS:
        notch = wheel_notch(name, x, z, board_w, board_h, -OVERSHOOT, PLATE_T + RAISE_H + 2 * OVERSHOOT)
        prev_vol = mesh_volume(plate)
        apply_boolean(plate, notch, 'DIFFERENCE')
        vol = mesh_volume(plate)
        assert 0.0 < vol < prev_vol, f"back plate: {name} notch cut corrupted the plate ({prev_vol:.1f} -> {vol:.1f}mm3)"

    # peg+boss studs - peg is STEPPED (see TIP_D/PEG_MAIN_LEN/TIP_LEN config comment):
    # main shaft at PEG_D up to the lip, then a narrower tip through the front plate.
    # Root at PLATE_T (the base's own INNER/wheel-facing face), not Y=0 (the exterior) -
    # rooting at Y=0 was a real bug: since the base already fills Y=[0,PLATE_T] solid,
    # a peg/boss built from Y=0 wasted its first PLATE_T of length entombed inside the
    # base's own material (the boss, at BOSS_H=0.6 < PLATE_T=2.0, never even poked out)
    # and every downstream length (peg tip, where the front plate sits) landed PLATE_T
    # short of where it needed to be. Main/tip and boss/main genuinely overlap each
    # other (concentric, by EMBED) so they get boolean-unioned pairwise into one clean
    # solid, not just mesh-joined - joining overlapping shapes directly is the
    # feedback_blender_boolean_fragility trigger #3.
    studs = []
    for name, x, z in WHEEL_POSITIONS:
        boss = _cylinder(BOSS_D, PLATE_T - EMBED, BOSS_H + EMBED, x, z, f"{name}_boss")
        peg_main = _cylinder(PEG_D, PLATE_T - EMBED, PEG_MAIN_LEN + EMBED, x, z, f"{name}_peg_main")
        peg_tip = _cylinder(TIP_D, PLATE_T + PEG_MAIN_LEN - EMBED, TIP_LEN + EMBED, x, z, f"{name}_peg_tip")
        peg = apply_boolean(peg_main, peg_tip, 'UNION')
        stud = apply_boolean(boss, peg, 'UNION')
        studs.append(stud)

    stud_union = join_objects(studs, "back_studs")
    prev_vol = mesh_volume(plate)
    apply_boolean(plate, stud_union, 'UNION')
    vol = mesh_volume(plate)
    assert vol > prev_vol, f"back plate: peg/boss union did not add material ({prev_vol:.1f} -> {vol:.1f}mm3)"

    # Bevel LAST, after every boolean op, not first - applying it before the notch cuts
    # left slightly irregular (non-planar) edge geometry that each subsequent difference
    # compounded, growing non-manifold with every notch cut (found the hard way: 0% right
    # after bevel, climbing past 6% by the last of 9 sequential notch cuts).
    apply_bevel(plate, BEVEL_W)

    return plate


# ============================================================
# FRONT PLATE - flat rounded rect: square reading window + round peg-tip
# hole + rim-access notch per wheel (one combined cutter, one difference).
# The notch mirrors the back plate's (same side, same reach) so each wheel
# is reachable from BOTH faces, not just the back.
# ============================================================


def build_front_plate(board_w, board_h):
    plate = _extrude_profile(rounded_rect_points(board_w, board_h, PLATE_CORNER_R), 0.0, PLATE_T, "front_plate")

    cutters = []
    for name, x, z in WHEEL_POSITIONS:
        angle = math.radians(WHEEL_VARIANTS[variant_for(name)])
        win_x = x + DIGIT_R * math.sin(angle)
        win_z = z + DIGIT_R * math.cos(angle)
        window = _rect(WINDOW_W, WINDOW_H, -OVERSHOOT, PLATE_T + 2 * OVERSHOOT,
                        win_x, win_z, f"{name}_window_cut")
        pegtip = _cylinder(FRONT_HOLE_D, -OVERSHOOT, PLATE_T + 2 * OVERSHOOT, x, z, f"{name}_pegtip_cut")
        notch = wheel_notch(name, x, z, board_w, board_h, -OVERSHOOT, PLATE_T + 2 * OVERSHOOT)
        # Round's window now sits BELOW the peg (angle 180) and its notch is still a top
        # notch (above) - they no longer overlap, so no special-case union is needed here
        # (it used to, back when the window was above the peg too - see git history).
        cutters.extend([window, pegtip, notch])

    cutter_union = join_objects(cutters, "front_cutters")
    prev_vol = mesh_volume(plate)
    apply_boolean(plate, cutter_union, 'DIFFERENCE')
    vol = mesh_volume(plate)
    assert 0.0 < vol < prev_vol, f"front plate: hole/window cut corrupted the plate ({prev_vol:.1f} -> {vol:.1f}mm3)"

    # Group labels + Turn + Mythos badge - recessed pockets + flush inserts, own
    # category/pass (separate from the through-cuts above, done after them - see
    # feedback_blender_boolean_fragility on not combining unrelated cutter categories
    # into one boolean). All spatially separate from each other, so one combined pass.
    #
    # Both of a group's labels ("ATTACKER CP" + "ATTACKER VP") stack together in the ONE
    # gap between that group's own CP and VP rows (row indices (1,2) and (3,4) - widened
    # via LABEL_PAIR_EXTRA_GAP), rather than each sitting under its own row.
    label_inserts, label_cutters = [], []
    line_gap = 6.0   # more room between CP/VP; the gap itself isn't growing, so this
                      # trades away buffer space above/below the pair, not new board space
    line_offset = (LABEL_SIZE * 0.7 + line_gap) / 2.0
    for cp_row, vp_row in ((1, 2), (3, 4)):
        gap_z = (_row_z(cp_row) + _row_z(vp_row)) / 2.0
        for text, label_z in ((ROW_LABEL_TEXT[cp_row - 1], gap_z + line_offset),
                               (ROW_LABEL_TEXT[vp_row - 1], gap_z - line_offset)):
            for poke, bucket in ((0.0, label_inserts), (POCKET_POKE, label_cutters)):
                thickness = POCKET_DEPTH + poke
                glyph = _build_flat_text_mesh(text, LABEL_SIZE, thickness)
                glyph.rotation_euler = (math.radians(90.0), 0.0, 0.0)
                glyph.location = (0.0, -poke + thickness / 2.0, label_z)
                apply_transform(glyph)
                bucket.append(glyph)

    # Decorative divider - purely ornamental, fills the otherwise-empty gap between the
    # Attacker and Defender halves (Atk VP -> Def CP, no label lives there). Plain solid
    # recessed bar, not text - no font/glyph involved, just a clean geometric line.
    divider_z = (_row_z(2) + _row_z(3)) / 2.0
    for poke, bucket in ((0.0, label_inserts), (POCKET_POKE, label_cutters)):
        thickness = POCKET_DEPTH + poke
        bar = _rect(DIVIDER_W, DIVIDER_H, -poke, thickness, 0.0, divider_z, "divider")
        bucket.append(bar)

    # Top-right corner, clear of Round's pocket and the board's own edge/corner rounding.
    # Squeezed into the gap between the peg-hole (at the wheel's exact center) and
    # where the top notch's tip reaches down to, centered on the peg's own axis.
    turn_x, turn_z = 0.0, _row_z(0) + (WHEEL_R - NOTCH_REACH) / 2.0
    for poke, bucket in ((0.0, label_inserts), (POCKET_POKE, label_cutters)):
        thickness = POCKET_DEPTH + poke
        glyph = _build_flat_text_mesh("ROUNDS", LABEL_SIZE, thickness)
        glyph.rotation_euler = (math.radians(90.0), 0.0, 0.0)
        glyph.location = (turn_x, -poke + thickness / 2.0, turn_z)
        apply_transform(glyph)
        bucket.append(glyph)

    badge_z = (_row_z(0) + _row_z(1)) / 2.0 - 5.0
    badge_inserts, badge_cutters = build_mythos_badge(0.0, badge_z)
    label_inserts += badge_inserts
    label_cutters += badge_cutters

    plate, inlay = carve_and_collect_inlay(plate, label_inserts, label_cutters, "front_labels")
    # Bevel LAST, after every boolean op - see the matching comment in build_back_plate
    # for why (bevel-first left irregular geometry that each later cut compounded).
    apply_bevel(plate, BEVEL_W)
    return plate, inlay


# ============================================================
# MAIN
# ============================================================


def board_footprint():
    xs = [x for _, x, _ in WHEEL_POSITIONS]
    w = (max(xs) - min(xs)) + WHEEL_D + 2 * SIDE_MARGIN
    return w, _board_h


def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    os.makedirs(RENDER_DIR, exist_ok=True)
    board_w, board_h = board_footprint()
    print(f"Board footprint: {board_w:.1f} x {board_h:.1f} mm, peg length {PEG_LEN:.2f} mm")

    for variant, angle_deg in WHEEL_VARIANTS.items():
        clear_scene()
        wheel_base, wheel_inlay = build_wheel(angle_deg)
        print(f"wheel_{variant}_base: volume={mesh_volume(wheel_base):.1f}mm3 "
              f"non-manifold={nonmanifold_fraction(wheel_base):.4f}")
        print(f"wheel_{variant}_inlay: volume={mesh_volume(wheel_inlay):.1f}mm3 "
              f"non-manifold={nonmanifold_fraction(wheel_inlay):.4f}")
        apply_color(wheel_base, "wheel_white", (1.0, 1.0, 1.0, 1.0))
        apply_color(wheel_inlay, "wheel_black", (0.03, 0.03, 0.03, 1.0))
        render_scene(f"wheel_{variant}_face", from_back=True, raking=True)  # digits face +Y, toward the front plate
        reorient_for_print(wheel_base, WHEEL_T)
        reorient_for_print(wheel_inlay, WHEEL_T)
        export_stl(wheel_base, f"wheel_{variant}_base.stl")
        export_stl(wheel_inlay, f"wheel_{variant}_inlay.stl")
        export_3mf([(wheel_base, WHEEL_BASE_COLOR, "base"), (wheel_inlay, WHEEL_INLAY_COLOR, "inlay")],
                   os.path.join(EXPORT_DIR, f"wheel_{variant}.3mf"))
        export_project_3mf(
            [(wheel_base, "base", BASE_EXTRUDER_SLOT), (wheel_inlay, "inlay", INLAY_EXTRUDER_SLOT)],
            os.path.join(EXPORT_DIR, f"wheel_{variant}_anycubic.3mf"))

    clear_scene()
    back = build_back_plate(board_w, board_h)
    print(f"back_plate: volume={mesh_volume(back):.1f}mm3 non-manifold={nonmanifold_fraction(back):.4f}")
    apply_color(back, "back_grey", (0.6, 0.6, 0.62, 1.0))
    render_scene("back_plate")
    reorient_back_for_print(back)
    export_stl(back, "back_plate.stl")

    clear_scene()
    front_base, front_inlay = build_front_plate(board_w, board_h)
    print(f"front_base: volume={mesh_volume(front_base):.1f}mm3 non-manifold={nonmanifold_fraction(front_base):.4f}")
    print(f"front_inlay: volume={mesh_volume(front_inlay):.1f}mm3 non-manifold={nonmanifold_fraction(front_inlay):.4f}")
    apply_color(front_base, "front_white", (1.0, 1.0, 1.0, 1.0))
    apply_color(front_inlay, "front_black", (0.03, 0.03, 0.03, 1.0))
    render_scene("front_plate")
    reorient_for_print(front_base, PLATE_T)
    reorient_for_print(front_inlay, PLATE_T)
    export_stl(front_base, "front_plate_base.stl")
    export_stl(front_inlay, "front_plate_inlay.stl")
    export_3mf([(front_base, WHEEL_BASE_COLOR, "base"), (front_inlay, WHEEL_INLAY_COLOR, "inlay")],
               os.path.join(EXPORT_DIR, "front_plate.3mf"))
    export_project_3mf(
        [(front_base, "base", BASE_EXTRUDER_SLOT), (front_inlay, "inlay", INLAY_EXTRUDER_SLOT)],
        os.path.join(EXPORT_DIR, "front_plate_anycubic.3mf"))

    print("Done.")


if __name__ == "__main__":
    main()
