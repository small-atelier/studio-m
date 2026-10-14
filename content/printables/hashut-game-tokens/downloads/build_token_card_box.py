"""
Themed carry box for the Helsmiths of Hashut game accessories - one box
holds the warscroll card stack AND all the DPP/Desolation tokens from
../tokens/build_tokens.py, closed by a slip-fit lid with a recessed bull
icon (same traced contour as the DPP token's bull, ../tokens/bull_contours.json).

The base needs no reorientation - it's built directly in print orientation
(open-top tray, floor already on the bed). The LID does: build_lid()
constructs it in its natural/assembled shape (skirt hanging down to the
bed, top slab up high) purely because that's the easiest shape to reason
about geometrically, but that orientation is actually WRONG to print in -
the solid top slab would have to bridge the entire hollow skirt cavity as
one big unsupported ceiling. main() flips the finished lid + icon insert
180 degrees (see reorient_lid_for_print) right before export, so the top
slab (with the bull/rune icons) prints FIRST as a flat, fully-supported
first layer, and the skirt prints as ordinary vertical walls growing up
from it - no bridging anywhere, and a smooth first-layer finish on the
decorated face. The flip is a real rotation, not a Z-only mirror, so nothing
prints backwards.

- box_base: a single open-top tray, solid white, with 6 pockets cut
  straight into it, all at the same DEEP_DEPTH (22mm) floor. Two columns
  (see LAYOUT): column A, the box's short left end, holds the 3 DPP hex
  wells STACKED vertically; column B, the long remainder, holds the card
  slot up front and the 2 Desolation wells side by side behind it. Every
  well gets a lift notch cut through whichever exterior wall it's flush
  against - left for the hexes, front for the card slot, back for
  Desolation (deliberately the OPPOSITE long side from the card slot's
  notch) - a token/card sitting flush in a 22mm-deep pocket is hard to
  pinch from directly above alone. Mono-color, no inlay.
- box_lid: a flat-top slab with a hollow skirt hanging down that slides
  over the base's outer walls (friction-fit, no magnets/hinges - same
  "proven over novel" reasoning as everywhere else in this army's kit),
  plus a recessed bull icon (center) and a Hashut rune in each of the 4
  corners, all as one joined inlay insert - same recess/insert two-color
  technique as every other piece (build_tokens.py, build_modifier_tokens.py):
  base_shell (color A) + icon insert (color B).

Same boolean-fragility lessons already generalized elsewhere apply here:
- Each notched well is UNIONED with its own notch first (a real boolean,
  not a plain mesh join) since well and notch deliberately overlap by
  design - joining overlapping cutters raw leaves self-intersecting
  geometry, the class of input that corrupts the EXACT solver (see
  feedback_blender_boolery_fragility). The resulting one-clean-solid-per-
  well cutters are THEN joined together (safe as a plain join - they
  don't overlap each other) for one combined difference against the
  shell.
- The lid's skirt cavity and its icon pocket are DIFFERENT classes of cut
  (structural vs decorative) and are cut as separate sequential
  differences, each with its own volume-diff assert - the same pattern
  build_tokens.py v6 had to retrofit onto the DPP/Desolation border cuts
  after combining classes silently corrupted a shell there.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_token_card_box.py
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
BULL_CONTOURS_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "tokens", "bull_contours.json"))
RUNE_CONTOURS_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "tokens", "rune_contours.json"))

EXPORT_DIR = os.path.join(SCRIPT_DIR, "output")
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1400, 1000)

BASE_COLOR = (1.0, 1.0, 1.0, 1.0)      # white - same convention as build_tokens.py
INLAY_COLOR = (0.06, 0.45, 0.12, 1.0)  # green - the lid's bull icon insert only

# ============================================================
# CONFIG (all mm)
# ============================================================

WALL_T = 2.5     # outer box walls
FLOOR_T = 2.5    # box floor
DIV_T = 2.5      # material left between adjacent wells (not cut - just gaps between cutters)
BEVEL_W = 0.6    # edge comfort/print-release, same reasoning as every other piece in this kit

HOLE_OVERSHOOT = 0.5   # cutter overshoot past whichever face is the "open" one being punched
                        # through - the same EMBED-pattern fix as build_tokens.py's own
                        # HOLE_OVERSHOOT (a cutter flush with the surface it's cutting is a
                        # coincident-face degenerate case for the EXACT solver)

# --- card slot ---
CARD_W = 120.0          # user-supplied stack footprint
CARD_D = 70.0
CARD_H = 20.0           # stack height - drives DEEP_DEPTH, not the slot footprint
CARD_CLEARANCE = 1.5    # per-side clearance so the stack drops in/out easily
SLOT_CARD_W = CARD_W + 2.0 * CARD_CLEARANCE     # 123.0
SLOT_CARD_D = CARD_D + 2.0 * CARD_CLEARANCE     # 73.0

# --- DPP hex wells --- (token size from ../tokens/build_tokens.py's DPP_FLAT_TO_FLAT, v6/v7 - the
# actual printed token, not this script's own value; keep in sync if that ever changes again)
DPP_TOKEN_FLAT_TO_FLAT = 33.0
DPP_TOKEN_T = 3.0                              # build_tokens.py's PLATE_T
DPP_WELL_CLEARANCE = 1.0        # v4: back to v2's 1.0 - v3's 2.0 wasn't what was actually wanted;
                                 # "bigger cut-out" meant the lift notch, not the well itself (see
                                 # HEX_NOTCH_W below)
DPP_WELL_FLAT_TO_FLAT = DPP_TOKEN_FLAT_TO_FLAT + 2.0 * DPP_WELL_CLEARANCE      # 35.0
DPP_WELL_POINT_TO_POINT = DPP_WELL_FLAT_TO_FLAT * 2.0 / math.sqrt(3.0)         # ~40.41
# Cut to the full DEEP_DEPTH (22mm, since v3) - no longer a shallow raised-floor well.

# --- Desolation well --- (token size from ../tokens/build_tokens.py's DESO_WIDTH/HEIGHT, v6)
DESO_TOKEN_W = 56.0
DESO_TOKEN_H = 30.0
DESO_WELL_CLEARANCE = 1.0
DESO_WELL_W = DESO_TOKEN_W + 2.0 * DESO_WELL_CLEARANCE          # 58.0
DESO_WELL_D = DESO_TOKEN_H + 2.0 * DESO_WELL_CLEARANCE          # 32.0
DESO_STACK_COUNT = 2            # v4: two separate wells (two stacks), not one - "might need a
                                 # space for 2 stack of desolation tokens"

DEEP_DEPTH = CARD_H + 2.0        # 22.0 - card slot, Desolation wells, and the spare well all cut
                                  # to this depth

# --- lift notches --- cut through whichever exterior wall a well is flush against, down to that
# well's own floor - a token/card sitting flush in a deep well is hard to pinch from directly
# above alone, this lets a fingertip get under its edge from outside the box instead.
HEX_NOTCH_W = 32.0    # v6: doubled from v4's 16 (itself bumped from v2's 10)
DESO_NOTCH_W = 40.0   # v6: doubled from v2's 20
CARD_NOTCH_W = 80.0   # v6: doubled from v4's 40

# --- bull icon on the lid ---
ICON_W = 46.0             # big and centered - "bull logo on the lid"
ICON_ASPECT = 1.0         # source bull_hashut.png is 215x215, square (see build_tokens.py)
INSERT_DEPTH = 0.6        # same flush-recess depth as build_tokens.py's own INSERT_DEPTH

# --- Hashut rune, one in each corner of the lid --- (v8)
RUNE_W = 18.0             # smaller than the bull - a corner accent, not a second focal point
RUNE_ASPECT = 1.0         # source rune_hashut.jpeg is 192x192, square (see build_tokens.py)
RUNE_MARGIN = 16.0        # inset from each edge to the rune's own center - keeps it well clear
                          # of both the outer edge and the bull icon at the lid's center

# --- lid ---
LID_T = 3.0               # top slab thickness
LID_SKIRT = FLOOR_T + DEEP_DEPTH     # v7: goes all the way down - was a fixed 8mm overlap, first
                                     # print felt like too little of the base was covered, so the
                                     # skirt now matches the base's own full height (same formula
                                     # as BASE_EXT_H) instead of a partial value, and stays correct
                                     # automatically if the base's depth ever changes again
LID_CLEARANCE = 0.3       # per-side slip-fit clearance between the skirt's inner face and the
                           # base's outer wall
LID_WALL_T = 2.0          # skirt wall thickness

# ============================================================
# LAYOUT (derived) - v5
#
# Two columns: COLUMN A is the short end (left, flush against the interior's left wall) - the 3
# DPP hexes stacked vertically, each with a lift notch through the LEFT wall. COLUMN B is the long
# side (right, the wide remainder), split into two rows so the card slot and the Desolation wells
# each get their own lift notch on OPPOSITE long sides of the box: the card slot is now the FRONT
# row (its notch breaches the front wall) and the 2 Desolation wells are the BACK row (their
# notches breach the back wall) - v4 had it the other way around with a spare well behind the card
# slot; the spare well is gone (v5) and swapping the rows is what actually gets the card slot a
# notch of its own, on the long side opposite the Desolation notches.
#
# Column A (3 stacked hexes) is still taller than column B's two rows combined, so column B's back
# row is pinned to the true back wall rather than centered, and the leftover height ends up as a
# gap BETWEEN the two rows instead of a fixed DIV_T - not a bug, just column B being shorter.
# ============================================================

COL_A_W = DPP_WELL_FLAT_TO_FLAT
COL_A_H = 3.0 * DPP_WELL_POINT_TO_POINT + 2.0 * DIV_T

CARD_ROW_W = SLOT_CARD_W
CARD_ROW_H = SLOT_CARD_D
DESO_ROW_W = DESO_STACK_COUNT * DESO_WELL_W + (DESO_STACK_COUNT - 1) * DIV_T
DESO_ROW_H = DESO_WELL_D

COL_B_W = max(CARD_ROW_W, DESO_ROW_W)
COL_B_H = CARD_ROW_H + DESO_ROW_H   # + whatever's left of COL_A_H between them, absorbed as gap
                                     # rather than a fixed DIV_T (see docstring)

INT_FOOT_W = COL_A_W + DIV_T + COL_B_W
INT_FOOT_D = max(COL_A_H, COL_B_H)

EXT_W = INT_FOOT_W + 2.0 * WALL_T
EXT_D = INT_FOOT_D + 2.0 * WALL_T
BASE_INT_H = DEEP_DEPTH
BASE_EXT_H = FLOOR_T + BASE_INT_H

IX0, IY0 = WALL_T, WALL_T   # interior footprint origin
BACK_WALL_Y = IY0 + INT_FOOT_D   # true interior back boundary - both columns reach exactly here

# --- Column A: 3 stacked hexes, flush left ---
_hex_cx = IX0 + COL_A_W / 2.0
DPP_WELL_CENTERS = [
    (_hex_cx, IY0 + DPP_WELL_POINT_TO_POINT / 2.0 + i * (DPP_WELL_POINT_TO_POINT + DIV_T))
    for i in range(3)
]

# --- Column B ---
_col_b_x0 = IX0 + COL_A_W + DIV_T

# Front row: card slot, flush against the front wall - gets a front-wall notch.
CARD_SLOT_CENTER = (_col_b_x0 + SLOT_CARD_W / 2.0, IY0 + CARD_ROW_H / 2.0)

# Back row: Desolation wells side by side, flush against the back wall - each gets a back-wall
# notch, the opposite long side from the card slot's.
_deso_row_cy = BACK_WALL_Y - DESO_ROW_H / 2.0
DESO_WELL_CENTERS = [
    (_col_b_x0 + DESO_WELL_W / 2.0 + i * (DESO_WELL_W + DIV_T), _deso_row_cy)
    for i in range(DESO_STACK_COUNT)
]

print(f"Box exterior: {EXT_W:.1f} x {EXT_D:.1f} x {BASE_EXT_H:.1f}mm (base); "
      f"lid adds {LID_T:.1f}mm on top, {2*(LID_CLEARANCE+LID_WALL_T):.1f}mm on each footprint side")

# ============================================================
# GENERIC HELPERS (same conventions as ../tokens/build_tokens.py)
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
    the bull/rune icons mirrored; rotating 180 degrees about an axis lying in the XY plane flips Y
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
    """Same idea as front_notch_points, breaching the LEFT wall instead (x=-HOLE_OVERSHOOT) - for
    column A's stacked hexes, which now sit against the box's short left end rather than its front
    edge (see LAYOUT)."""
    hw = width / 2.0
    return [(-HOLE_OVERSHOOT, center_y - hw), (well_center_x, center_y - hw),
            (well_center_x, center_y + hw), (-HOLE_OVERSHOOT, center_y + hw)]


def back_notch_points(center_x, width, well_center_y):
    """Same idea again, breaching the BACK wall - for the Desolation wells, anchored to the back
    wall in v5's layout. Targets EXT_D (the true exterior face), NOT BACK_WALL_Y - BACK_WALL_Y is
    only the INTERIOR boundary where the back wall's inner face sits; the wall itself is still
    WALL_T thick beyond that before the box's real outside. (Bug found here in v5: this used to
    target BACK_WALL_Y+HOLE_OVERSHOOT, which only nicked 0.5mm into a 2.5mm wall and never
    actually broke through - front_notch_points/left_notch_points never had this problem because
    their target, y=0/x=0, already IS the absolute exterior by construction.)"""
    hw = width / 2.0
    return [(center_x - hw, well_center_y), (center_x + hw, well_center_y),
            (center_x + hw, EXT_D + HOLE_OVERSHOOT), (center_x - hw, EXT_D + HOLE_OVERSHOOT)]


def load_contours(path):
    with open(path) as f:
        return json.load(f)


def build_icon_solid_xy(contours, icon_w, icon_h, center_x, center_y, z0, thickness, name_prefix):
    """XY-plane counterpart of build_tokens.py's build_icon_solid - same
    per-contour chained union/difference pattern (proven there), just
    footprint-oriented and single-orientation (the lid is only ever
    viewed from directly above, so no mirrored back-face pass needed).
    u -> x, v -> y (v=0 is the icon's own bottom edge)."""
    icon_x0 = center_x - icon_w / 2.0
    icon_y0 = center_y - icon_h / 2.0

    outer_pts, hole_pts = [], []
    for c in contours:
        pts = [(icon_x0 + u * icon_w, icon_y0 + v * icon_h) for u, v in c["points"]]
        pts = dedupe_closed_loop(pts)
        (hole_pts if c["hole"] else outer_pts).append(pts)
    assert outer_pts, f"{name_prefix}: traced icon has no outer contours"

    solid = extrude_xy(outer_pts[0], z0, thickness, f"{name_prefix}_0")
    for i, pts in enumerate(outer_pts[1:], start=1):
        union_onto(solid, extrude_xy(pts, z0, thickness, f"{name_prefix}_{i}"))
    for i, pts in enumerate(hole_pts):
        cutter = extrude_xy(pts, z0 - HOLE_OVERSHOOT, thickness + 2 * HOLE_OVERSHOOT,
                             f"{name_prefix}_hole_{i}")
        apply_boolean(solid, cutter, 'DIFFERENCE')

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
    cam_data.ortho_scale = size * 1.15
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


# ============================================================
# BASE
# ============================================================


def build_base():
    shell = build_box(EXT_W, EXT_D, BASE_EXT_H, (EXT_W / 2.0, EXT_D / 2.0, BASE_EXT_H / 2.0), "base_shell")
    prev_vol = mesh_volume(shell)

    # Each notched well is built as ONE clean solid (pocket UNION notch, a real boolean, not just
    # a mesh join) before joining it with the other wells for the final combined difference - a
    # plain join of two cutters that deliberately OVERLAP (the well and its own notch, by design)
    # would leave self-intersecting geometry in the merged mesh, exactly the class of input that
    # corrupts the EXACT solver (see feedback_blender_boolery_fragility). The final wells-vs-wells
    # join is still safe as a plain join - those don't overlap each other, only within a well.
    cutters = []
    for cx, cy in DPP_WELL_CENTERS:
        pts = [(cx + x, cy + y) for x, y in hex_points(DPP_WELL_FLAT_TO_FLAT)]
        pocket = extrude_xy(pts, FLOOR_T, DEEP_DEPTH + HOLE_OVERSHOOT, "dpp_well_cut")
        notch = extrude_xy(left_notch_points(cy, HEX_NOTCH_W, cx), FLOOR_T, DEEP_DEPTH, "dpp_notch_cut")
        cutters.append(union_onto(pocket, notch))

    for dcx, dcy in DESO_WELL_CENTERS:
        deso_pts = [(dcx + x, dcy + y) for x, y in rect_points(DESO_WELL_W, DESO_WELL_D)]
        deso_pocket = extrude_xy(deso_pts, FLOOR_T, DEEP_DEPTH + HOLE_OVERSHOOT, "deso_well_cut")
        deso_notch = extrude_xy(back_notch_points(dcx, DESO_NOTCH_W, dcy), FLOOR_T, DEEP_DEPTH, "deso_notch_cut")
        cutters.append(union_onto(deso_pocket, deso_notch))

    ccx, ccy = CARD_SLOT_CENTER
    card_pts = [(ccx + x, ccy + y) for x, y in rect_points(SLOT_CARD_W, SLOT_CARD_D)]
    card_pocket = extrude_xy(card_pts, FLOOR_T, DEEP_DEPTH + HOLE_OVERSHOOT, "card_slot_cut")
    card_notch = extrude_xy(front_notch_points(ccx, CARD_NOTCH_W, ccy), FLOOR_T, DEEP_DEPTH, "card_notch_cut")
    cutters.append(union_onto(card_pocket, card_notch))

    apply_boolean(shell, join_objects(cutters, "well_cutters"), 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_vol, f"base: well cut corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"

    apply_bevel(shell, BEVEL_W)
    return shell


# ============================================================
# LID
# ============================================================


def build_lid():
    lid_z0 = BASE_EXT_H - LID_SKIRT
    lid_z1 = BASE_EXT_H + LID_T
    lid_ext_w = EXT_W + 2.0 * LID_CLEARANCE + 2.0 * LID_WALL_T
    lid_ext_d = EXT_D + 2.0 * LID_CLEARANCE + 2.0 * LID_WALL_T
    cx, cy = EXT_W / 2.0, EXT_D / 2.0

    shell = build_box(lid_ext_w, lid_ext_d, lid_z1 - lid_z0, (cx, cy, (lid_z0 + lid_z1) / 2.0), "lid_shell")

    # 1) Skirt cavity - hollows out everything below the top slab (z < BASE_EXT_H), leaving a
    # LID_WALL_T ring that slides over the base's outer wall. Own sequential cut + assert -
    # structural, not decorative, see module docstring for why it's not combined with the icon cut.
    prev_vol = mesh_volume(shell)
    cavity_w = EXT_W + 2.0 * LID_CLEARANCE
    cavity_d = EXT_D + 2.0 * LID_CLEARANCE
    cavity_h = BASE_EXT_H - (lid_z0 - HOLE_OVERSHOOT)
    cavity = build_box(cavity_w, cavity_d, cavity_h, (cx, cy, BASE_EXT_H - cavity_h / 2.0), "lid_skirt_cut")
    apply_boolean(shell, cavity, 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_vol, f"lid: skirt cavity corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"

    # 2) Bull icon (center) + Hashut rune (each of the 4 corners) pockets - all decorative-icon-
    # class cutters, safe to combine into ONE cut same as the base's wells (see module docstring);
    # only the skirt cavity above needed its own separate cut (different class: structural).
    bull_contours = load_contours(BULL_CONTOURS_PATH)
    bull_h = ICON_W * ICON_ASPECT
    inserts = [build_icon_solid_xy(bull_contours, ICON_W, bull_h, cx, cy,
                                    lid_z1 - INSERT_DEPTH, INSERT_DEPTH, "lid_bull_ins")]
    cutters = [build_icon_solid_xy(bull_contours, ICON_W, bull_h, cx, cy,
                                    lid_z1 - INSERT_DEPTH, INSERT_DEPTH + HOLE_OVERSHOOT, "lid_bull_cut")]

    rune_contours = load_contours(RUNE_CONTOURS_PATH)
    rune_h = RUNE_W * RUNE_ASPECT
    corner_centers = [
        (RUNE_MARGIN, RUNE_MARGIN), (EXT_W - RUNE_MARGIN, RUNE_MARGIN),
        (RUNE_MARGIN, EXT_D - RUNE_MARGIN), (EXT_W - RUNE_MARGIN, EXT_D - RUNE_MARGIN),
    ]
    for i, (rx, ry) in enumerate(corner_centers):
        inserts.append(build_icon_solid_xy(rune_contours, RUNE_W, rune_h, rx, ry,
                                            lid_z1 - INSERT_DEPTH, INSERT_DEPTH, f"lid_rune_{i}_ins"))
        cutters.append(build_icon_solid_xy(rune_contours, RUNE_W, rune_h, rx, ry,
                                            lid_z1 - INSERT_DEPTH, INSERT_DEPTH + HOLE_OVERSHOOT, f"lid_rune_{i}_cut"))

    prev_vol = mesh_volume(shell)
    apply_boolean(shell, join_objects(cutters, "lid_icon_cutters"), 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_vol, f"lid: icon pockets corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"

    icon_insert = join_objects(inserts, "lid_icon_inlay")

    apply_bevel(shell, BEVEL_W)
    return shell, icon_insert


# ============================================================
# MAIN
# ============================================================


def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    os.makedirs(RENDER_DIR, exist_ok=True)

    clear_scene()
    base = build_base()
    lid, icon_insert = build_lid()

    base_vol, base_nm = mesh_volume(base), nonmanifold_fraction(base)
    lid_vol, lid_nm = mesh_volume(lid), nonmanifold_fraction(lid)
    icon_vol, icon_nm = mesh_volume(icon_insert), nonmanifold_fraction(icon_insert)
    print(f"base: volume={base_vol:.1f}mm3 (non-manifold {base_nm:.4f})")
    print(f"lid: volume={lid_vol:.1f}mm3 (non-manifold {lid_nm:.4f})  "
          f"icon insert: volume={icon_vol:.1f}mm3 (non-manifold {icon_nm:.4f})")

    apply_color(base, "base_mat", BASE_COLOR)
    apply_color(lid, "base_mat", BASE_COLOR)
    apply_color(icon_insert, "inlay_mat", INLAY_COLOR)

    render_top("box_assembled_closed")

    lid.location.z += 60.0   # lift the lid off for an "exploded" second shot
    icon_insert.location.z += 60.0
    render_top("box_assembled_open")

    lid.hide_render = True
    icon_insert.hide_render = True
    render_top("box_base_only", elev_deg=80.0, bounds_objs=[base])
    lid.hide_render = False
    icon_insert.hide_render = False

    base.hide_render = True
    render_top("box_lid_underside", elev_deg=45.0, from_below=True, bounds_objs=[lid, icon_insert])
    base.hide_render = False

    lid.location.z -= 60.0
    icon_insert.location.z -= 60.0

    # Flip the lid upside down for export - see reorient_lid_for_print's docstring for why this
    # is the actually-correct print orientation, not just a preference: built the way build_lid()
    # naturally makes it (skirt down, top slab up), the top slab is a huge unsupported bridge
    # spanning the entire hollow skirt cavity. Printed skirt-up instead, the top slab is the FIRST
    # layer (flat, fully supported, and gives the bull/rune icon face a smooth first-layer finish
    # against the plate) and the skirt is just ordinary vertical walls growing up from solid
    # material - no bridging anywhere.
    _lid_z0 = BASE_EXT_H - LID_SKIRT
    _lid_z1 = BASE_EXT_H + LID_T
    _lid_cy, _lid_cz = EXT_D / 2.0, (_lid_z0 + _lid_z1) / 2.0
    reorient_lid_for_print(lid, _lid_cy, _lid_cz)
    reorient_lid_for_print(icon_insert, _lid_cy, _lid_cz)
    bpy.context.view_layer.update()   # obj.bound_box is cached - without this the next render's
                                       # bounds_objs framing uses stale (pre-flip) extents

    base.hide_render = True
    render_top("box_lid_print_orientation", elev_deg=55.0, bounds_objs=[lid, icon_insert])
    # The icon face is now DOWN against the print bed (correctly invisible from above, as it
    # should be in this orientation) - view from below instead to confirm the flip kept the
    # bull/rune icons correctly shaped and non-mirrored.
    render_top("box_lid_print_orientation_icon_face", elev_deg=55.0, from_below=True,
               bounds_objs=[lid, icon_insert])
    base.hide_render = False

    export_stl(base, "box_base.stl")
    export_stl(lid, "box_lid_base.stl")
    export_stl(icon_insert, "box_lid_inlay.stl")
    export_3mf([(lid, BASE_COLOR, "lid_base"), (icon_insert, INLAY_COLOR, "lid_inlay")],
               os.path.join(EXPORT_DIR, "box_lid.3mf"))
    export_project_3mf([(lid, "lid_base", 1), (icon_insert, "lid_inlay", 2)],
                        os.path.join(EXPORT_DIR, "box_lid_anycubic.3mf"))

    print("Done.")


if __name__ == "__main__":
    main()
