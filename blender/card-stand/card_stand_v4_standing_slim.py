"""
Store-counter business-card stand (Blender bpy) - standalone, NOT terrain.

v4 change (trial - kept as its own file per feedback_scope_and_naming in
case v1-v3's sloped/3-wide layout is preferred instead): cards stand
UPRIGHT on edge instead of leaning in a sloped tray, and the 3 piles sit
IN FRONT OF EACH OTHER (front-to-back) instead of side-by-side - slimmer
footprint, and it means the whole card holder is narrow enough (~70mm)
to match a trimmed, taller backplate with the logo sitting above the
cards' tops instead of a separate wide sign behind a wide tray row.

This also simplifies the geometry versus v1-v3: the holder is a single
"comb" cross-section (flat base + 4 upright fins forming 3 slots) traced
as ONE closed profile and linear-extruded along the width - same
zero-boolean technique as the old tray wedge, but this time there's
nothing to boolean-cut at all (no pocket to hollow out - standing cards
just rest in the open channel between two fins). Compact enough now
(~70 x 85 x 28mm) to be ONE print instead of 3.

Backplate keeps v3's image-stamp heightfield technique unchanged (see
preprocess_logo.py), just narrower/taller, with the logo repositioned
above where the cards' tops reach. The tenon/socket joint is now
horizontal (backplate tenons poke -Y into the holder's back fin) rather
than vertical, since both parts now sit on the counter side by side
instead of the backplate perching on top of the tray row.

Run:
  python3 preprocess_logo.py   (only needed once, or after mask changes)
  /Applications/Blender.app/Contents/MacOS/Blender --background --python card_stand_v4_standing_slim.py
"""

import bpy
import bmesh
import json
import math
import mathutils
import os

# ============================================================
# CONFIG (all mm)
# ============================================================

EXPORT_DIR = "/Users/mannil/Desktop/studio-m/TSONS/card_stand/output_v4"
EXPORT_STL = True

RENDER_IMAGES = True
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1600, 1200)
RENDER_ANGLES = {
    "front": (0.0, -1.0, 0.35),
    "side": (1.0, -0.4, 0.35),
    "top": (0.05, -0.3, 1.0),
    "iso": (0.7, -1.0, 0.55),
}

# --- Card / pile ---
CARD_SIZE = 65.0
CARD_THICKNESS = 0.45                          # ~300gsm cardstock
CARDS_PER_PILE = 50
STACK_H = CARD_THICKNESS * CARDS_PER_PILE      # 22.5mm

# --- Standing-card holder (comb: flat base + 4 upright fins = 3 slots) ---
SLOT_CLEARANCE = 0.5                           # per side, cards slide freely
HOLDER_W = 70.0                                # matches the trimmed backplate width
STANDING_SLOT_GAP = STACK_H + 2 * SLOT_CLEARANCE   # 23.5mm - stack-thickness gap between fins
FIN_THICK = 3.0                                # internal/front fin thickness
BACK_FIN_THICK = 6.0                           # thicker - hosts the tenon sockets
BASE_THICK = 4.0                               # base slab the fins stand on (front step's floor)
FIN_HEIGHT = 24.0                               # how tall each fin rises above ITS OWN floor
STEP_RISE = 7.0                                 # each successive tread's floor is this much higher -
                                                 # the base slopes, but the fins/teeth stay vertical
                                                 # (corrected from an earlier rigid-tilt attempt: the
                                                 # user wants the BOTTOM sloped, teeth straight up)

FLOOR_HS = [BASE_THICK + i * STEP_RISE for i in range(3)]   # one floor height per gap/tread
CARD_TOP_Z = FLOOR_HS[-1] + CARD_SIZE           # tallest (back) pile's top - what the logo must clear

# --- Alignment joint (backplate <-> holder's back fin), now horizontal:
# both parts sit on the counter side by side, so the backplate's tenons
# poke -Y into the back fin rather than sitting on top of it. ---
TENON_OFFSET_X = 17.0
TENON_W = 10.0
TENON_H = 8.0                      # Z extent of the tenon
TENON_SOCKET_DEPTH = 4.0           # Y depth into the 6mm back fin, 2mm left behind it
TENON_FIT_CLEARANCE = 0.25
TENON_EMBED = 1.0
TENON_Z_CENTER = 28.0              # raised up from 20 per the user's ask - still within the back
                                    # fin's own height, see the assert bounding it

# --- Resin-saving arch carved into the underside (stiletto-shoe massing:
# flat toe, flat heel, one smooth arch between) - clearance kept below
# whichever tread's floor is locally binding, see build_holder(). ---
HOLLOW_SHELL_T = 3.5

# --- Backplate ---
BACKPLATE_W = 70.0                 # trimmed from v1-v3's 140mm per the user's ask
BACKPLATE_H = 160.0                 # taller still - the tallest (back) pile now reaches CARD_TOP_Z
BACKPLATE_T = 6.0
FINISH_BEVEL_W = 0.3                # holder's edge bevel

# v4 change: continuous heightfield relief (v3's technique) replaced with
# a flat single-level plateau + sharp 90-degree walls - easier to paint
# cleanly (a crisp edge to paint up to, no subtle gradient to fight) and
# it sidesteps the whole family of relief-smoothness problems (blur
# tuning, bevel-vs-grid interactions) entirely, since there's no gradient
# left to look pixelated. Built from real vector contours (marching
# squares on the mask, see extract_logo_contours.py) rather than a
# per-pixel grid - clean boolean unions/differences instead of a
# heightfield mesh.
EMBOSS_H = 2.0                      # flat raised height off the backplate face
EMBOSS_EMBED = 1.0                  # extra embed into the backplate for a clean union
CUTTER_OVERSHOOT = 1.0              # hole cutters (e.g. the "O") reach this far past the raised
                                     # face and this far past the embed depth, for a clean cut

# Backplate's own bevel is separate and bigger, and still gets applied
# to the PLAIN box (+ridge +tenons) BEFORE the logo icon/text pieces are
# added - a holdover from the old heightfield version where this
# ordering was essential (a bevel modifier on that dense grid mangled the
# fine relief), but worth keeping even now: it keeps the bevel modifier's
# edge count small and predictable (a plain box), and keeps the logo's
# own sharp 90-degree walls untouched by any bevel at all.
BACKPLATE_BEVEL_W = 1.2

# --- Decorative ridge - upside-down U (top + both sides, no bottom
# stroke - stops halfway down, not near the bottom, since the holder's
# back fin sits flush against the lower half and the two would collide
# otherwise) inset from the backplate's own edges ---
RIDGE_INSET = 4.0
RIDGE_WIDTH = 2.5
RIDGE_HEIGHT = 2.0

# --- Logo icon (vector contours, see extract_logo_contours.py) ---
LOGO_CONTOURS_PATH = "/Users/mannil/Desktop/studio-m/TSONS/card_stand/logo_contours.json"
LOGO_W = 58.0                       # narrower than v3's 122mm - constrained by the 70mm plate
LOGO_ASPECT = 499.0 / 720.0          # source mask's full h:w - contours are normalized against
                                     # the FULL image, icon just occupies the upper portion of it
LOGO_CENTER_X = 0.0
LOGO_TOP_MARGIN = 15.0

# --- MYTHOS wordmark - real vector text, not traced from the 183x127px
# source (letters were exactly the kind of fine detail that reads badly
# raster-traced at any resolution) - Baskerville visually matched the
# source lettering closely (splayed M, moderate stroke contrast, same
# serif shapes) among locally available fonts. ---
TEXT_FONT_PATH = "/System/Library/Fonts/Supplemental/Baskerville.ttc"
TEXT_STRING = "MYTHOS"
TEXT_SIZE = 15.0
TEXT_GAP_BELOW_ICON = 8.0            # gap between the icon's own bottom and the text's top

# ============================================================
# SANITY CHECKS
# ============================================================
HOLDER_DEPTH = 3 * FIN_THICK + 3 * STANDING_SLOT_GAP + BACK_FIN_THICK
BACK_FIN_TOP_Z = FLOOR_HS[-1] + FIN_HEIGHT   # back fin's own top - also its tallest exposed face

assert STEP_RISE < FIN_HEIGHT, \
    "a step taller than the fin itself would bury the divider - lower STEP_RISE or raise FIN_HEIGHT"
assert 0.0 < TENON_Z_CENTER < BACK_FIN_TOP_Z, "tenon socket falls outside the back fin's own height"
assert HOLDER_DEPTH <= 88.0, "holder deeper than the Photon Mono 2's 89.6mm Y (with margin)"
assert HOLDER_W <= 143.0, "holder wider than the Photon Mono 2's 143.4mm X"
assert TENON_OFFSET_X + TENON_W / 2 < HOLDER_W / 2 - 5.0, \
    "tenon socket runs past the back fin's own edge"
assert BACKPLATE_W <= 143.0, "backplate wider than the Photon Mono 2 bed (143.4mm, standing on edge)"
assert BACKPLATE_T <= 89.0, "backplate thicker than the Photon Mono 2 bed's other axis"
assert BACKPLATE_H <= 164.0, "backplate taller than the Photon Mono 2's 165mm Z"


# ============================================================
# GENERIC HELPERS (shared conventions - see pump_adapter.py, columns.py)
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


def build_box(sx, sy, sz, center, name):
    """Box spanning [center - size/2, center + size/2] on each axis."""
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


def _extrude_profile(points, plane, offset, thickness, name):
    """Build a flat face from a closed 2D point loop and extrude it into a
    solid prism. `plane` is 'XZ' (points are (x, z), extrude along Y) or
    'YZ' (points are (y, z), extrude along X). `offset` is the fixed
    coordinate of the starting face; extrusion runs +thickness from there.
    Same family as _spin_profile (brazier.py/columns.py) but linear
    instead of rotational - no booleans needed for a simple solid prism."""
    bm = bmesh.new()
    if plane == 'XZ':
        verts = [bm.verts.new((p[0], offset, p[1])) for p in points]
    else:
        verts = [bm.verts.new((offset, p[0], p[1])) for p in points]
    face = bm.faces.new(verts)
    result = bmesh.ops.extrude_face_region(bm, geom=[face])
    new_verts = [v for v in result['geom'] if isinstance(v, bmesh.types.BMVert)]
    vec = (0.0, thickness, 0.0) if plane == 'XZ' else (thickness, 0.0, 0.0)
    bmesh.ops.translate(bm, vec=vec, verts=new_verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
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
        (min(xs) + max(xs)) / 2,
        (min(ys) + max(ys)) / 2,
        (min(zs) + max(zs)) / 2,
    ))
    size = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    return center, size


def setup_camera_and_light(center):
    cam_data = bpy.data.cameras.new("RenderCam")
    cam_obj = bpy.data.objects.new("RenderCam", cam_data)
    bpy.context.collection.objects.link(cam_obj)

    target = bpy.data.objects.new("RenderTarget", None)
    target.location = center
    bpy.context.collection.objects.link(target)

    track = cam_obj.constraints.new(type='TRACK_TO')
    track.target = target
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'

    # Raking key light: aimed with to_track_quat (direction the light
    # travels), not hand-picked euler angles - a near-head-on light gives a
    # flat relief almost zero shading contrast on its own top face (only
    # the short side walls catch anything), which is what a first attempt
    # at hand-derived euler angles produced here. Mostly-horizontal
    # traeval direction relative to the logo face's -Y normal is what
    # actually reveals a shallow raised plateau.
    # Direction the light TRAVELS. The logo face's outward normal is
    # roughly -Y, so illuminating it needs dir.y > 0 (light moving toward
    # +Y hits a -Y-facing surface) - a first attempt got this backwards
    # (dir.y < 0) and lit the *back* of everything, rendering pure black.
    key_dir = mathutils.Vector((0.6, 0.45, -0.6)).normalized()
    key_data = bpy.data.lights.new("RenderKey", type='SUN')
    key_data.energy = 3.0
    key_obj = bpy.data.objects.new("RenderKey", key_data)
    key_obj.rotation_euler = key_dir.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.collection.objects.link(key_obj)

    fill_dir = mathutils.Vector((-0.5, 0.35, 0.35)).normalized()
    fill_data = bpy.data.lights.new("RenderFill", type='SUN')
    fill_data.energy = 0.6
    fill_obj = bpy.data.objects.new("RenderFill", fill_data)
    fill_obj.rotation_euler = fill_dir.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.collection.objects.link(fill_obj)

    bpy.context.scene.camera = cam_obj
    return cam_obj


def render_closeup(obj, name, direction=(0.0, -1.0, 0.0)):
    """Tight, straight-on shot of a single object's own logo face - the
    non-manifold-fraction volume check catches CORRUPTION, not composition
    or legibility, so eyeball this before trusting the wide renders (see
    feedback_blender_boolean_fragility on close-crop verification)."""
    xs = [ (obj.matrix_world @ mathutils.Vector(c)) for c in obj.bound_box ]
    center = sum(xs, mathutils.Vector((0, 0, 0))) / 8.0
    size = max((max(v[i] for v in xs) - min(v[i] for v in xs)) for i in range(3))
    cam_obj = setup_camera_and_light(center)
    cam_obj.data.lens = 85.0
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = RENDER_RESOLUTION[0]
    scene.render.resolution_y = RENDER_RESOLUTION[1]
    distance = size * 1.6
    cam_obj.location = center + mathutils.Vector(direction).normalized() * distance
    scene.render.filepath = os.path.join(RENDER_DIR, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {scene.render.filepath}")


def render_angles(center, size):
    os.makedirs(RENDER_DIR, exist_ok=True)
    cam_obj = setup_camera_and_light(center)

    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    try:
        scene.eevee.use_gtao = True
    except AttributeError:
        pass
    scene.render.resolution_x = RENDER_RESOLUTION[0]
    scene.render.resolution_y = RENDER_RESOLUTION[1]

    distance = size * 3.0
    for name, direction in RENDER_ANGLES.items():
        cam_obj.location = center + mathutils.Vector(direction).normalized() * distance
        scene.render.filepath = os.path.join(RENDER_DIR, f"{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"Rendered {scene.render.filepath}")


def export_stl(obj, filename):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = os.path.join(EXPORT_DIR, filename)
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"Exported {path}")


# ============================================================
# STANDING-CARD HOLDER
# ============================================================

def build_stepped_comb_profile(fin_thicks, gaps, floor_hs, fin_height, back_drop_z=0.0):
    """Trace a stepped-base, N-upright-fin comb as ONE closed (y, z) loop -
    zero booleans, same family as the old tray wedge/flat comb
    (_extrude_profile auto-closes the last point back to the first). Each
    fin is still perfectly VERTICAL (front-face-up / top-across /
    back-face-down) - it's the FLOOR between fins that steps up by
    floor_hs[i] at each successive gap, not the fins tilting. The very
    first front face starts at the ground (z=0); the very last (back)
    fin's back face drops to back_drop_z - the ground (0.0) for a plain
    flat-bottomed comb, or higher if the caller is about to continue the
    profile into its own cutaway (see build_holder) rather than closing
    straight to the counter here."""
    n = len(fin_thicks)
    pts = [(0.0, 0.0)]
    y = 0.0
    front_floor = 0.0
    for i, ft in enumerate(fin_thicks):
        top = front_floor + fin_height
        pts.append((y, top))
        y += ft
        pts.append((y, top))
        if i < len(gaps):
            back_floor = floor_hs[i]
            pts.append((y, back_floor))
            y += gaps[i]
            pts.append((y, back_floor))
            front_floor = back_floor
        else:
            pts.append((y, back_drop_z))
    return pts, y


def build_holder():
    """Stiletto-silhouette underside (not literal - just the massing): a
    flat solid "toe" (fin0+tread1+fin1+tread2+fin2) in front, and a
    straight triangular wedge taken out of the back - a single flat
    diagonal cut (easier to clean support marks off than a curve, and
    simpler to reason about safety-wise), open at the true back rather
    than closing back down to the ground there. The back fin doesn't
    need its own separate ground contact - once glued, it leans on the
    backplate (the "heel") for support, so there's nothing wrong with its
    lower portion opening straight out the back. That opening is the
    object's own OUTER boundary, not an internal cavity - genuinely open
    to the air, so no suction seal against the counter and no trapped-
    resin/drain-hole concern. Built as ONE profile with the wedge as its
    return path - zero booleans for this feature."""
    fin_thicks = [FIN_THICK, FIN_THICK, FIN_THICK, BACK_FIN_THICK]
    gaps = [STANDING_SLOT_GAP, STANDING_SLOT_GAP, STANDING_SLOT_GAP]

    y_fin0_end = FIN_THICK
    y_tread1_end = y_fin0_end + STANDING_SLOT_GAP
    y_fin1_end = y_tread1_end + FIN_THICK
    y_tread2_end = y_fin1_end + STANDING_SLOT_GAP
    y_fin2_end = y_tread2_end + FIN_THICK
    y_tread3_end = y_fin2_end + STANDING_SLOT_GAP   # == depth - BACK_FIN_THICK, back fin starts here

    # Lower and longer: start the wedge at tread2 instead of tread3, which
    # means the whole span (tread2+fin2+tread3) is now bound by tread2's
    # shallower floor (11mm, not tread3's 18mm) to keep it a single
    # straight, unkinked line - a lower peak, but ~65% of the depth as
    # wedge instead of ~35%.
    wedge_start_y = y_fin1_end
    peak_h = FLOOR_HS[1] - HOLLOW_SHELL_T

    zigzag, depth = build_stepped_comb_profile(fin_thicks, gaps, FLOOR_HS, FIN_HEIGHT,
                                                back_drop_z=peak_h)
    assert abs(depth - HOLDER_DEPTH) < 1e-6

    profile = zigzag + [(wedge_start_y, 0.0)]
    shell = _extrude_profile(profile, 'YZ', -HOLDER_W / 2.0, HOLDER_W, "card_holder")

    # Tenon sockets cut into the back fin from its BACK face (the face
    # that will touch the backplate), going forward into the fin a few
    # mm, with a couple mm of overshoot past the back face for a clean
    # cut through it - a plain axis-aligned box against a plain
    # axis-aligned fin, same low-risk pattern as v1-v3's vertical version.
    overshoot = 2.0
    for sign in (-1, 1):
        socket = build_box(
            TENON_W, TENON_SOCKET_DEPTH + overshoot, TENON_H,
            (sign * TENON_OFFSET_X,
             depth - TENON_SOCKET_DEPTH / 2.0 + overshoot / 2.0,
             TENON_Z_CENTER),
            "tenon_socket")
        apply_boolean(shell, socket, 'DIFFERENCE')

    return shell


# ============================================================
# BACKPLATE + LOGO
# ============================================================

def load_logo_contours():
    with open(LOGO_CONTOURS_PATH) as f:
        return json.load(f)


def build_logo_icon(shell):
    """Union each outer icon contour (flat prism, genuinely sharp 90-
    degree walls - not a heightfield) onto shell, then cut each hole
    contour (the mountain has one small enclosed gap in its internal
    detail line - see extract_logo_contours.py). Returns the icon's own
    bottom Z so build_logo_text can sit a fixed gap below it."""
    contours = load_logo_contours()
    icon_h = LOGO_W * LOGO_ASPECT
    icon_x0 = LOGO_CENTER_X - LOGO_W / 2.0
    icon_z0 = BACKPLATE_H - LOGO_TOP_MARGIN - icon_h

    for c in contours:
        pts = [(icon_x0 + u * LOGO_W, icon_z0 + v * icon_h) for u, v in c["points"]]
        if c["hole"]:
            cutter = _extrude_profile(
                pts, 'XZ', -EMBOSS_H - CUTTER_OVERSHOOT,
                EMBOSS_H + EMBOSS_EMBED + 2 * CUTTER_OVERSHOOT, "icon_hole_cutter")
            apply_boolean(shell, cutter, 'DIFFERENCE')
        else:
            piece = _extrude_profile(pts, 'XZ', -EMBOSS_H, EMBOSS_H + EMBOSS_EMBED, "icon_piece")
            union_onto(shell, piece)

    return icon_z0


def build_logo_text(shell, icon_bottom_z):
    """Real vector text (Baskerville - see TEXT_FONT_PATH's comment),
    flat-extruded to match the icon's height, not traced from the
    source's 183x127px raster - letters are exactly the kind of fine
    detail that read worst as a raster trace."""
    font = bpy.data.fonts.load(TEXT_FONT_PATH)
    curve_data = bpy.data.curves.new("logo_text_curve", type='FONT')
    curve_data.body = TEXT_STRING
    curve_data.font = font
    curve_data.size = TEXT_SIZE
    curve_data.align_x = 'CENTER'
    curve_data.align_y = 'CENTER'   # not 'TOP' - see below
    curve_data.extrude = (EMBOSS_H + EMBOSS_EMBED) / 2.0
    obj = bpy.data.objects.new("logo_text", curve_data)
    bpy.context.collection.objects.link(obj)

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')

    # Measure the actual glyph ink extent instead of trusting
    # align_y='TOP' - that aligns to the font's ascender line (reserved
    # space for accents etc.), which for all-caps "MYTHOS" sits well
    # above the real cap-height, so the text rendered noticeably too low
    # relative to where it was meant to sit.
    local_top_y = max(v.co.y for v in obj.data.vertices)
    target_top_z = icon_bottom_z - TEXT_GAP_BELOW_ICON

    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    obj.location = (LOGO_CENTER_X, -EMBOSS_H, target_top_z - local_top_y)
    apply_transform(obj)
    union_onto(shell, obj)


def build_backplate_box():
    """Plain box + tenons + ridge, beveled - see BACKPLATE_BEVEL_W's
    comment for why this has to happen BEFORE the logo stamp is unioned
    on, not after."""
    shell = build_box(BACKPLATE_W, BACKPLATE_T, BACKPLATE_H,
                       (0.0, BACKPLATE_T / 2.0, BACKPLATE_H / 2.0), "backplate")

    # Horizontal tenons now (both parts sit on the counter side by side,
    # rather than the backplate perching on top of the holder as in
    # v1-v3) - protrude -Y from the front face into the holder's back-fin
    # sockets. Protrude slightly less than the socket's cut depth so the
    # tenon doesn't bottom out before the two flat faces meet.
    protrude_len = TENON_SOCKET_DEPTH - 0.5
    for sign in (-1, 1):
        tenon = build_box(
            TENON_W - 2 * TENON_FIT_CLEARANCE,
            protrude_len + TENON_EMBED,
            TENON_H - 2 * TENON_FIT_CLEARANCE,
            (sign * TENON_OFFSET_X, (TENON_EMBED - protrude_len) / 2.0, TENON_Z_CENTER),
            "tenon")
        union_onto(shell, tenon)

    # Decorative ridge - upside-down U (top + both sides, no bottom
    # stroke). Stops HALFWAY down the backplate, not near the bottom -
    # the holder's back fin sits flush against the lower half once
    # glued, and a ridge running that low would collide with it. Built
    # as 3 boxes joined into ONE ridge solid first (generous overlap at
    # the two corners), then unioned onto the backplate as a single
    # piece - safer than 3 separate unions per
    # feedback_blender_boolean_fragility's guidance on pre-resolving
    # small mutually-overlapping groups.
    ridge_y_size = RIDGE_HEIGHT + EMBOSS_EMBED
    ridge_y_center = (EMBOSS_EMBED - RIDGE_HEIGHT) / 2.0
    leg_z0, leg_z1 = BACKPLATE_H / 2.0, BACKPLATE_H - RIDGE_INSET
    leg_x = BACKPLATE_W / 2.0 - RIDGE_INSET

    ridge = build_box(RIDGE_WIDTH, ridge_y_size, leg_z1 - leg_z0,
                       (-leg_x, ridge_y_center, (leg_z0 + leg_z1) / 2.0), "ridge_left")
    right_leg = build_box(RIDGE_WIDTH, ridge_y_size, leg_z1 - leg_z0,
                           (leg_x, ridge_y_center, (leg_z0 + leg_z1) / 2.0), "ridge_right")
    top_bar = build_box(2 * leg_x + RIDGE_WIDTH + 1.0, ridge_y_size, RIDGE_WIDTH,
                         (0.0, ridge_y_center, leg_z1), "ridge_top")
    apply_boolean(ridge, top_bar, 'UNION')
    apply_boolean(ridge, right_leg, 'UNION')
    union_onto(shell, ridge)

    apply_bevel(shell, BACKPLATE_BEVEL_W)
    return shell


def build_backplate():
    shell = build_backplate_box()
    icon_bottom_z = build_logo_icon(shell)
    build_logo_text(shell, icon_bottom_z)
    # No shade-smooth pass needed now - everything is flat prisms/boxes
    # with genuinely sharp edges, not a curved heightfield to smooth.
    return shell


# ============================================================
# MAIN
# ============================================================

def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    clear_scene()

    holder = build_holder()
    backplate = build_backplate()   # bevels its own box internally, before the logo stamp is added

    apply_bevel(holder, FINISH_BEVEL_W)

    for obj in (holder, backplate):
        vol = mesh_volume(obj)
        nm = nonmanifold_fraction(obj)
        print(f"{obj.name}: volume={vol:.1f}mm3  non-manifold edge fraction={nm:.4f}")
        assert vol > 0.0, f"{obj.name} has zero/negative volume - a boolean likely emptied it"

    if EXPORT_STL:
        export_stl(holder, "card_holder.stl")
        export_stl(backplate, "backplate.stl")

    # Position for an assembled preview render only (after STL export, so
    # the exported meshes stay at their own clean per-part origins). Both
    # sit on the counter (z=0) side by side, not stacked.
    backplate.location = (0.0, HOLDER_DEPTH, 0.0)

    if RENDER_IMAGES:
        # Render-only card-stack placeholders (not exported, not part of
        # the print) - the empty holder alone doesn't show whether the
        # logo actually clears the tallest (back) pile's top, which is
        # the whole point of this render. Each sits on ITS OWN stepped
        # tread height, not tilted - the fins/teeth stay vertical.
        y = 0.0
        for i, ft in enumerate((FIN_THICK, FIN_THICK, FIN_THICK)):
            gap_center = y + ft + STANDING_SLOT_GAP / 2.0
            floor_z = FLOOR_HS[i]
            build_box(CARD_SIZE, STANDING_SLOT_GAP - 1.0, CARD_SIZE,
                      (0.0, gap_center, floor_z + CARD_SIZE / 2.0), "card_stack_placeholder")
            y += ft + STANDING_SLOT_GAP

        center_pt, size = compute_scene_bounds()
        render_angles(center_pt, size)
        render_closeup(backplate, "logo_closeup")

    print("Done.")


if __name__ == "__main__":
    main()
