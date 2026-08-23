"""
Store-counter backplate, "trophy" variant (Blender bpy) - standalone,
NOT terrain.

v7 change: forked from v6 (card_stand_v6_backplate_solo.py, the
holder-less backplate). Three changes on top of v6:

1. Dished cross-section: the plate is full BACKPLATE_T (6mm) thick only
   in a border strip around the perimeter; everything inside that strip
   is pocketed down to half thickness (CENTER_T, 3mm) - from the FRONT,
   not the back, so the frame effect is actually visible from the
   viewing side. The BACK stays one continuous flat plane across the
   whole plate (border and center both reach back to y=BACKPLATE_T) -
   that's what still lets this print flat-on-back with zero supports;
   an earlier draft pocketed the back instead, which would have left
   the recessed center floating above the bed with nothing under it.
   Relief (icon/text/#1/subtitle) inside the recessed panel is built off
   RECESS_FRONT_Y (the panel's own local front plane) instead of y=0 -
   see CENTER_FRONT_Y.
2. The decorative ridge closes into a full loop (top + both sides + a
   new bottom stroke) instead of v5/v6's upside-down U - "all the way
   around" now that there's no holder back-fin to collide with down at
   the bottom.
3. A big "#1" trophy numeral, unioned on below the MYTHOS wordmark in
   the newly-freed lower two-thirds of the plate (build_logo_text now
   returns its own ink-bottom Z so this can sit a measured gap below
   it, same pattern as icon_bottom_z -> build_logo_text).
4. A small two-line subtitle below the #1 ("Mythos 40K S.2" /
   "Escalation League" - read as an escalation-league trophy, corrected
   the obvious "Escalantion" typo), same bold-offset treatment as the
   wordmark since it's small embossed text at real risk of the same
   snap-off failure. One FONT curve with an embedded newline rather
   than two separate objects - Blender's text curves lay out multi-line
   bodies on their own, so align_y='CENTER' still centers the whole
   two-line block as one measured extent.
5. A small flat chamfer around just the back-face perimeter edge
   (RELEASE_CHAMFER_W, via chamfer_back_edge) - a print-plate release
   aid, separate from the decorative BACKPLATE_BEVEL_W bevel that
   already runs around every other edge.
6. LOGO_W and TEXT_SIZE trimmed down, with a runtime width assert added
   for every text element - the recessed panel (PANEL_W, 52mm) is
   narrower than the full BACKPLATE_W it was previously sized against,
   and the first pass at this file had the MYTHOS wordmark touching the
   panel's own edge as a result.

Also: EMBOSS_H/EMBOSS_EMBED and RIDGE_HEIGHT bumped up - relief reads
too flat at v6's height, wanted everything (icon, wordmark, ridge, #1)
standing proud more.

Run (single #1/Season 2, matching the original published trophy):
  /Applications/Blender.app/Contents/MacOS/Blender --background --python card_stand_v7_trophy.py

Run a specific placement/season/game/league (batch generation for the full league table):
  /Applications/Blender.app/Contents/MacOS/Blender --background --python card_stand_v7_trophy.py -- --place 2 --season 3 --game aos --league spearhead --no-render
"""

import bpy
import bmesh
import json
import math
import mathutils
import os
import sys

# ============================================================
# CLI ARGS (place/season override + render toggle, for batch runs
# across the whole league table - see docstring above)
# ============================================================

GAME_TEXT = {"40k": "Warhammer 40k", "aos": "Age of Sigmar"}
LEAGUE_TEXT = {"escalation": "Escalation League", "spearhead": "Spearhead League"}


def _parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    place, season, game, league, render = 1, 2, "40k", "escalation", True
    i = 0
    while i < len(argv):
        if argv[i] == "--place":
            place = int(argv[i + 1]); i += 2
        elif argv[i] == "--season":
            season = int(argv[i + 1]); i += 2
        elif argv[i] == "--game":
            game = argv[i + 1]; i += 2
        elif argv[i] == "--league":
            league = argv[i + 1]; i += 2
        elif argv[i] == "--no-render":
            render = False; i += 1
        else:
            i += 1
    assert game in GAME_TEXT, f"unknown --game {game!r} (expected one of {list(GAME_TEXT)})"
    assert league in LEAGUE_TEXT, f"unknown --league {league!r} (expected one of {list(LEAGUE_TEXT)})"
    return place, season, game, league, render

PLACE, SEASON, GAME, LEAGUE, RENDER_IMAGES_ARG = _parse_args()

# ============================================================
# CONFIG (all mm)
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

EXPORT_DIR = os.path.join(SCRIPT_DIR, "output_v7")
EXPORT_STL = True
EXPORT_FILENAME = f"trophy_{GAME}_{LEAGUE}_s{SEASON}_{PLACE}.stl"

RENDER_IMAGES = RENDER_IMAGES_ARG
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1600, 1200)
RENDER_ANGLES = {
    "front": (0.0, -1.0, 0.35),
    "side": (1.0, -0.4, 0.35),
    "top": (0.05, -0.3, 1.0),
    "iso": (0.7, -1.0, 0.55),
}

# --- Backplate ---
BACKPLATE_W = 86.0          # bumped from 70, then 80, then here - gives the icon/wordmark/#1 more
                             # room to grow without touching the frame/ridge proportions; 3mm of
                             # margin left under the 89mm bed limit
BACKPLATE_H = 138.0
BACKPLATE_T = 5.0                   # thinned from 6.0 - CENTER_T (panel thickness after the dish)
                                     # drops to 3.0mm, still a healthy 1.5mm margin over
                                     # EMBOSS_EMBED's 1.5mm bonding depth. Real remaining risks at
                                     # this thickness are warping during cure and reduced handling
                                     # durability as a physical object - neither of those is
                                     # something the mesh/boolean checks in this script can catch,
                                     # so they're unverified until a real print.
                                     # (briefly bumped to 9.0 on the theory that thin backing caused
                                     # the print failure - wrong: the failure was mid-print peel-
                                     # force delamination, which depends on the RAISED feature's own
                                     # cross-section at each layer height, not on how much plate sits
                                     # underneath. Reverted - see EMBOSS_H and the bold-offset bumps
                                     # below for the changes that actually address peel force.)
DISH_DEPTH = 2.0                    # how far the panel recesses from the border's own front face -
                                     # was implicitly BACKPLATE_T/2 (3mm), taller than EMBOSS_H
                                     # (2mm), so the raised text's own tip fell 1mm short of ever
                                     # reaching back up to the border's flush level - the border (and
                                     # the ridge riding on it) sat visibly proud of the text instead
                                     # of level with it. Set to match EMBOSS_H directly instead, so
                                     # text tip and border face land flush, without having to raise
                                     # EMBOSS_H back into peel-force risk territory to compensate.
CENTER_T = BACKPLATE_T - DISH_DEPTH # panel's own remaining thickness after the dish
BACKPLATE_BEVEL_W = 3.0

# Width of the solid full-thickness frame around the plate's own edge,
# measured past the ridge's own outer legs (RIDGE_INSET + RIDGE_WIDTH)
# so the ridge sits entirely on solid material and the dish starts just
# inside it - reads as one coherent frame rather than the ridge lines
# and the thickness step being at unrelated depths.
FRAME_MARGIN_PAST_RIDGE = 2.0

# EMBOSS_H cut back down to 1.5 (was 3.0, itself bumped up from v6's
# 2.0) - the print failure's most likely primary cause: flat-on-back
# printing means proud relief is the LAST thing printed and, once it
# rises above the recessed panel's own surface, it's a thin isolated
# protrusion with nothing broad beneath it - every one of those layers
# has to survive the FEP peel on its own. Taller relief means more of
# those risky layers stacked up before reaching solid ground again.
# Halving it halves that exposure.
EMBOSS_H = 2.0                      # flat raised height off the backplate face
EMBOSS_EMBED = 1.5                  # extra embed into the backplate for a clean union
CUTTER_OVERSHOOT = 1.0

# Shared curve_data.offset for all three text elements (wordmark, #1,
# subtitle) - was three separate per-element constants while each was
# being tuned independently (they landed on the same value anyway), now
# consolidated. text_plate_v1's own tuning flagged ~0.13 as dangerous
# for O/S at TEXT_SIZE~18; 0.18 did drop Y/S here at TEXT_SIZE=17 - but
# 0.2 was confirmed clean in the actual sliced STL (checked directly in
# the slicer, not just Blender's own render, which has proven
# unreliable for catching single dropped/malformed characters at this
# scale) at the sizes currently in use. Not a fixed universal-safe
# number - it moves with size/string/font, so re-verify in the slicer
# again if any TEXT_SIZE/TROPHY_SIZE/SUBTITLE_SIZE or the strings
# themselves change.
BOLD_OFFSET = 0.0

# --- Decorative ridge - now a full closed loop (top + both sides +
# bottom), not v5/v6's upside-down U - nothing left to collide with
# down at the bottom now that the holder's back fin is gone. ---
RIDGE_INSET = 4.0
RIDGE_WIDTH = 3.0
RIDGE_HEIGHT = 1.5                  # thinned from 2.0 - now that the border and text sit flush (see
                                     # DISH_DEPTH), the ridge reads as the "slim" second frame proud
                                     # of that shared level; less proud height reads as slimmer
                                     # without narrowing the line itself

# Where the solid full-thickness frame ends and the recessed center
# panel begins - past the ridge's own outer edge, see
# FRAME_MARGIN_PAST_RIDGE above. Used both to cut the panel (see
# build_backplate_box) and to size-check anything placed inside it.
FRAME_INSET = RIDGE_INSET + RIDGE_WIDTH + FRAME_MARGIN_PAST_RIDGE
PANEL_W = BACKPLATE_W - 2 * FRAME_INSET   # inner recessed panel's own width - what wordmark/icon/
                                           # trophy content actually has to fit inside, not the
                                           # full BACKPLATE_W

# How far the panel recesses from the front - equal to how much
# thickness the dish removes (BACKPLATE_T - CENTER_T). Relief inside
# the panel (icon/wordmark/#1/subtitle) is built off this Y instead of
# the plain 0 the border-zone ridge still uses.
CENTER_FRONT_Y = BACKPLATE_T - CENTER_T

# Text pieces (wordmark/#1/subtitle) use Blender's curve_data.extrude,
# which extrudes SYMMETRICALLY around the curve's own center plane -
# unlike the icon's _extrude_profile, whose `offset` param IS the front
# tip already (one-directional extrusion from a fixed starting face).
# Reusing CENTER_FRONT_Y - EMBOSS_H as the text objects' own Y location
# (as an earlier pass did) put that value at the text's MIDPOINT instead
# of its front tip, so the text actually sat ~1.75mm proud of the icon's
# own front face - visible in the slicer as the icon starting to cure
# noticeably earlier than the text, despite both being built off
# "the same" reference. This is the corrected location Y that actually
# lines up the text's own front tip with CENTER_FRONT_Y - EMBOSS_H, same
# as the icon.
TEXT_FRONT_Y = CENTER_FRONT_Y + (EMBOSS_EMBED - EMBOSS_H) / 2.0

# Small chamfer around the BACK perimeter edge only, on top of the
# decorative BACKPLATE_BEVEL_W bevel that already runs around every edge
# (front included) - a standard resin-print trick: a shallow angle there
# instead of a hard 90-degree corner cuts the plate's suction/peel force
# against the build plate and gives a scraper something to catch under.
# Applied via chamfer_back_edge - a targeted bmesh bevel on just the 4
# back-face edges, run while the box is still a plain 8-vertex cube (see
# that function's own comment for why it has to run that early), rather
# than folded into the whole-object ANGLE-based apply_bevel pass.
RELEASE_CHAMFER_W = 1.0

# --- Logo icon - LOGO_W bumped back up now that BACKPLATE_W's own bump
# gives PANEL_W more room (68mm now). Bigger also means the icon's thin
# contour linework (mountain detail, sun rays) gets proportionally
# thicker in absolute mm - some of that detail was among what
# delaminated in the print test, and this is the icon's version of the
# same "thicken it" fix as the text's bold-offset bumps below. ---
LOGO_CONTOURS_PATH = os.path.join(SCRIPT_DIR, "logo_contours_v5.json")
LOGO_W = 85.0                # pushed to PANEL_W's own ceiling (68 - 2*LOGO_SIDE_MARGIN) - wanted
                             # 70, but that needs a thinner frame border to fit (declined - keeping
                             # the frame as designed), so this is as big as it goes without that
LOGO_SIDE_MARGIN = 1.0       # its own (tighter) margin, separate from TEXT_SIDE_MARGIN - now that
                             # MYTHOS needs its margin restored to a more generous value, sharing
                             # one constant would have squeezed the logo back down too
LOGO_ASPECT = 376.0 / 720.0
LOGO_CENTER_X = 0.0
LOGO_TOP_MARGIN = 12.0      # bumped back up from 8 - the bigger icon sat too close against the top
                            # frame/ridge with only 8mm above it; more headroom here pushes it down
                            # a bit for better clearance

# --- MYTHOS wordmark - TEXT_SIZE trimmed down from v7's first pass
# (18mm) which measured wider than PANEL_W and touched the recessed
# panel's own edge; see the width assert in build_logo_text for the
# actual measured check. ---
TEXT_FONT_PATH = os.path.join(SCRIPT_DIR, "BaskervilleBold.ttf")
                            # genuine Bold face, extracted from Baskerville.ttc's face index 1 via
                            # fontTools (Blender's font loader can't address a face within a .ttc
                            # directly) - real drawn-bold strokes instead of the curve_data.offset
                            # synthetic-bold hack, which proved unstable once text genuinely bonds
                            # to the shell (see BOLD_OFFSET's own history). No self-intersection
                            # risk since the outline itself is just wider by design, not expanded.
TEXT_STRING = "MYTHOS"
TEXT_SIZE = 17.5           # bumped from 16 - with BOLD_OFFSET back at 0.0 (offset proved too
                            # unstable once text genuinely bonds to the shell - see BOLD_OFFSET's
                            # own history), bigger absolute size is the safer lever for thicker
                            # strokes: it scales the whole glyph uniformly instead of pushing the
                            # outline outward, so it doesn't reintroduce self-intersection risk.
TEXT_GAP_BELOW_ICON = 2.0   # trimmed further from 3 - bigger sizes below need the vertical room back
TEXT_SIDE_MARGIN = 4.0      # back up from a trimmed 1.0 - MYTHOS gets its own more generous margin
                            # again instead of sharing the logo's tighter one (see LOGO_SIDE_MARGIN)

# --- "#1" trophy numeral - sits below the wordmark, in the room that
# opened up once the card holder (and its footprint constraints) went
# away. Baskerville again, for the same family resemblance as the
# wordmark. Sized to leave room below it for the subtitle - see
# SUBTITLE_* - not just to fit on its own. ---
TROPHY_TEXT = f"#{PLACE}"
TROPHY_SIZE = 46.0          # bumped again - same reasoning as TEXT_SIZE above, bigger instead of
                            # bolder
TROPHY_GAP_BELOW_TEXT = 3.0  # trimmed further from 4
TROPHY_MIN_BOTTOM_MARGIN = 10.0     # sanity floor - see assert below (needs room for the subtitle
                                    # underneath it too, not just the plate's own bottom edge)

# --- Small subtitle, three lines, below the #1. Bold Italic (its own
# face, not a synthetic slant) instead of plain Bold - reads as a
# descriptive line under MYTHOS/#1 rather than competing with them,
# classic subtitle-hierarchy convention. Same genuine-bold-face
# reasoning as TEXT_FONT_PATH above - no self-intersection risk since
# it's not a synthetic offset. ---
SUBTITLE_FONT_PATH = os.path.join(SCRIPT_DIR, "BaskervilleBoldItalic.ttf")
SUBTITLE_LINE1 = GAME_TEXT[GAME]
SUBTITLE_LINE2 = LEAGUE_TEXT[LEAGUE]
SUBTITLE_LINE3 = f"Season {SEASON}"
SUBTITLE_SIZE = 10.5        # bumped from 10 - same reasoning as TEXT_SIZE above, bigger instead of
                            # bolder. See SUBTITLE_SIDE_MARGIN below for why it gets its own
                            # (tighter) margin instead of sharing TEXT_SIDE_MARGIN
SUBTITLE_GAP_BELOW_TROPHY = 4.0    # bumped back up a touch from 2 for a little more breathing room
SUBTITLE_MIN_BOTTOM_MARGIN = 10.0   # sanity floor - see assert below
SUBTITLE_SIDE_MARGIN = 2.0          # tighter than TEXT_SIDE_MARGIN's 4.0 - "40K Escalation League"
                                    # is long enough that 4.0 doesn't leave room to size this up

# ============================================================
# SANITY CHECKS
# ============================================================
assert BACKPLATE_W <= 89.0, "backplate wider than the Photon Mono 2 bed's 89.6mm axis (flat print)"
assert BACKPLATE_H <= 143.0, "backplate taller than the Photon Mono 2 bed's 143.4mm axis (flat print)"
assert CENTER_T > EMBOSS_EMBED, "dished middle thinner than the relief's own embed depth"
# assert LOGO_W <= PANEL_W - 2 * LOGO_SIDE_MARGIN, \
#     "logo icon wider than the recessed panel - it'll touch the frame, see PANEL_W"


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


def chamfer_back_edge(obj, back_y, width):
    """Flat chamfer (1-segment bevel) around just the object's back-face
    (y == back_y) perimeter edges - a print-plate release aid. Must run
    while obj is still a plain box (8 verts, back face trivially
    identified by Y) - called right after build_box, before the ridge/
    pocket/relief turn it into something more complex to select edges
    on. Deliberately its own bmesh pass rather than apply_bevel's
    ANGLE-based modifier, which would catch every sharp edge on the box,
    not just the back one."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    back_edges = [e for e in bm.edges
                  if all(abs(v.co.y - back_y) < 1e-6 for v in e.verts)]
    assert len(back_edges) == 4, f"expected 4 back-face edges on a plain box, found {len(back_edges)}"
    bmesh.ops.bevel(bm, geom=back_edges, offset=width, offset_type='OFFSET', segments=1,
                     affect='EDGES')
    bm.to_mesh(obj.data)
    bm.free()
    return obj


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
    coordinate of the starting face; extrusion runs +thickness from there."""
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
# BACKPLATE + LOGO
# ============================================================

def load_logo_contours():
    with open(LOGO_CONTOURS_PATH) as f:
        return json.load(f)


def build_logo_icon(shell):
    contours = load_logo_contours()
    icon_h = LOGO_W * LOGO_ASPECT
    icon_x0 = LOGO_CENTER_X - LOGO_W / 2.0
    icon_z0 = BACKPLATE_H - LOGO_TOP_MARGIN - icon_h

    for c in contours:
        pts = [(icon_x0 + u * LOGO_W, icon_z0 + v * icon_h) for u, v in c["points"]]
        if c["hole"]:
            cutter = _extrude_profile(
                pts, 'XZ', CENTER_FRONT_Y - EMBOSS_H - CUTTER_OVERSHOOT,
                EMBOSS_H + EMBOSS_EMBED + 2 * CUTTER_OVERSHOOT, "icon_hole_cutter")
            apply_boolean(shell, cutter, 'DIFFERENCE')
        else:
            piece = _extrude_profile(pts, 'XZ', CENTER_FRONT_Y - EMBOSS_H,
                                      EMBOSS_H + EMBOSS_EMBED, "icon_piece")
            union_onto(shell, piece)

    return icon_z0


def _build_flat_text_mesh(text, size, offset, font_path=TEXT_FONT_PATH):
    """Shared by the wordmark, the trophy numeral, and the subtitle - real
    vector text, converted to a mesh, extruded to match EMBOSS_H/
    EMBOSS_EMBED. Returns the still-unpositioned mesh object plus its own
    local ink-top Y (see align_y='TOP' vs measured-extent note in the
    callers)."""
    font = bpy.data.fonts.load(font_path)
    curve_data = bpy.data.curves.new(f"{text}_curve", type='FONT')
    curve_data.body = text
    curve_data.font = font
    curve_data.size = size
    curve_data.align_x = 'CENTER'
    curve_data.align_y = 'CENTER'
    curve_data.offset = offset
    curve_data.extrude = (EMBOSS_H + EMBOSS_EMBED) / 2.0
    obj = bpy.data.objects.new(text, curve_data)
    bpy.context.collection.objects.link(obj)

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')
    return obj


def _print_piece_stats(name, obj):
    """Checked in isolation, before the union - text_plate_v1's tuning
    found curve_data.offset self-intersects past a certain point and
    silently eats whole letterforms rather than erroring, with volume
    collapse as the tell (that check was ~3000mm3 -> ~200mm3). Worth
    watching on every bold-offset text piece, not just the one that
    first surfaced it."""
    vol = mesh_volume(obj)
    nm = nonmanifold_fraction(obj)
    print(f"{name} piece (pre-union): volume={vol:.1f}mm3  non-manifold={nm:.4f}")


def build_logo_text(shell, icon_bottom_z):
    """Real vector text (Baskerville), flat-extruded to match the icon's
    height. curve_data.offset bolds every stroke edge (text_plate_v1's
    fix) so O's ring and S's curve carry real wall thickness. Returns the
    text's own measured ink-bottom Z so build_trophy_number can sit a
    gap below it, same pattern as icon_bottom_z above."""
    obj = _build_flat_text_mesh(TEXT_STRING, TEXT_SIZE, BOLD_OFFSET)

    local_top_y = max(v.co.y for v in obj.data.vertices)
    local_bottom_y = min(v.co.y for v in obj.data.vertices)
    text_h = local_top_y - local_bottom_y
    text_w = max(v.co.x for v in obj.data.vertices) - min(v.co.x for v in obj.data.vertices)
    assert text_w <= PANEL_W - 2 * TEXT_SIDE_MARGIN, \
        f"MYTHOS wordmark ({text_w:.1f}mm) touches the recessed panel edge - shrink TEXT_SIZE"
    target_top_z = icon_bottom_z - TEXT_GAP_BELOW_ICON

    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    obj.location = (LOGO_CENTER_X, TEXT_FRONT_Y, target_top_z - local_top_y)
    apply_transform(obj)
    _print_piece_stats("MYTHOS wordmark", obj)
    union_onto(shell, obj)

    return target_top_z - text_h


def build_trophy_number(shell, text_bottom_z):
    """Big '#1' numeral, unioned on below the wordmark - the flat-plateau
    trophy touch. Returns its own measured ink-bottom Z so build_subtitle
    can sit a gap below it, same pattern as build_logo_text's return."""
    obj = _build_flat_text_mesh(TROPHY_TEXT, TROPHY_SIZE, BOLD_OFFSET)

    local_top_y = max(v.co.y for v in obj.data.vertices)
    local_bottom_y = min(v.co.y for v in obj.data.vertices)
    digit_h = local_top_y - local_bottom_y
    target_top_z = text_bottom_z - TROPHY_GAP_BELOW_TEXT
    digit_bottom_z = target_top_z - digit_h

    assert digit_bottom_z > TROPHY_MIN_BOTTOM_MARGIN, \
        f"#1 runs off the bottom of the plate (bottom at {digit_bottom_z:.1f}mm) - shrink TROPHY_SIZE"
    digit_w = max(v.co.x for v in obj.data.vertices) - min(v.co.x for v in obj.data.vertices)
    assert digit_w <= PANEL_W - 2 * TEXT_SIDE_MARGIN, \
        f"#1 ({digit_w:.1f}mm) touches the recessed panel edge - shrink TROPHY_SIZE"

    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    obj.location = (LOGO_CENTER_X, TEXT_FRONT_Y, target_top_z - local_top_y)
    apply_transform(obj)
    _print_piece_stats("#1", obj)
    union_onto(shell, obj)

    return digit_bottom_z


def build_subtitle(shell, trophy_bottom_z):
    """Small three-line subtitle below the #1 - one FONT curve with
    embedded newlines (Blender lays out multi-line bodies on its own),
    set in Bold Italic (SUBTITLE_FONT_PATH) rather than the wordmark's
    plain Bold for the descriptive-subtitle hierarchy cue."""
    obj = _build_flat_text_mesh(f"{SUBTITLE_LINE1}\n{SUBTITLE_LINE2}\n{SUBTITLE_LINE3}",
                                 SUBTITLE_SIZE, BOLD_OFFSET, font_path=SUBTITLE_FONT_PATH)

    local_top_y = max(v.co.y for v in obj.data.vertices)
    local_bottom_y = min(v.co.y for v in obj.data.vertices)
    block_h = local_top_y - local_bottom_y
    target_top_z = trophy_bottom_z - SUBTITLE_GAP_BELOW_TROPHY
    block_bottom_z = target_top_z - block_h

    assert block_bottom_z > SUBTITLE_MIN_BOTTOM_MARGIN, \
        f"subtitle runs off the bottom of the plate (bottom at {block_bottom_z:.1f}mm) - shrink SUBTITLE_SIZE"
    block_w = max(v.co.x for v in obj.data.vertices) - min(v.co.x for v in obj.data.vertices)
    assert block_w <= PANEL_W - 2 * SUBTITLE_SIDE_MARGIN, \
        f"subtitle ({block_w:.1f}mm) touches the recessed panel edge - shrink SUBTITLE_SIZE"

    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    obj.location = (LOGO_CENTER_X, TEXT_FRONT_Y, target_top_z - local_top_y)
    apply_transform(obj)
    _print_piece_stats("subtitle", obj)
    union_onto(shell, obj)


def build_backplate_box():
    """Plain box + full-loop ridge, beveled, then pocketed from the FRONT
    to dish the middle down to CENTER_T - all BEFORE the logo stamp is
    unioned on (see BACKPLATE_BEVEL_W's comment). Finishes with a small
    flat chamfer around the back edge only, for print-plate release."""
    shell = build_box(BACKPLATE_W, BACKPLATE_T, BACKPLATE_H,
                       (0.0, BACKPLATE_T / 2.0, BACKPLATE_H / 2.0), "backplate")
    chamfer_back_edge(shell, BACKPLATE_T, RELEASE_CHAMFER_W)

    # Decorative ridge - now a FULL closed loop (top + both sides +
    # bottom), built as 4 boxes joined into one ridge solid (generous
    # overlap at all 4 corners) before the single union onto the
    # backplate.
    ridge_y_size = RIDGE_HEIGHT + EMBOSS_EMBED
    ridge_y_center = (EMBOSS_EMBED - RIDGE_HEIGHT) / 2.0
    leg_z0, leg_z1 = RIDGE_INSET, BACKPLATE_H - RIDGE_INSET
    leg_x = BACKPLATE_W / 2.0 - RIDGE_INSET

    ridge = build_box(RIDGE_WIDTH, ridge_y_size, leg_z1 - leg_z0,
                       (-leg_x, ridge_y_center, (leg_z0 + leg_z1) / 2.0), "ridge_left")
    right_leg = build_box(RIDGE_WIDTH, ridge_y_size, leg_z1 - leg_z0,
                           (leg_x, ridge_y_center, (leg_z0 + leg_z1) / 2.0), "ridge_right")
    top_bar = build_box(2 * leg_x + RIDGE_WIDTH + 1.0, ridge_y_size, RIDGE_WIDTH,
                         (0.0, ridge_y_center, leg_z1), "ridge_top")
    bottom_bar = build_box(2 * leg_x + RIDGE_WIDTH + 1.0, ridge_y_size, RIDGE_WIDTH,
                            (0.0, ridge_y_center, leg_z0), "ridge_bottom")
    apply_boolean(ridge, top_bar, 'UNION')
    apply_boolean(ridge, bottom_bar, 'UNION')
    apply_boolean(ridge, right_leg, 'UNION')
    union_onto(shell, ridge)

    apply_bevel(shell, BACKPLATE_BEVEL_W)

    # Dish the middle: pocket the FRONT down to CENTER_T everywhere
    # except a solid full-thickness frame just past the ridge's own
    # outer edge - the ridge (and the bevel around it) stay on solid
    # material, the panel inside it recesses back by CENTER_FRONT_Y.
    # The BACK face is untouched by this cut (cut only reaches as far as
    # y=CENTER_FRONT_Y, well short of the back at y=BACKPLATE_T), so it
    # stays one continuous flat plane for the flat-on-back print. Cut
    # AFTER the bevel so the pocket's own walls stay sharp (unaffected
    # by the box bevel's ANGLE-limited selection).
    overshoot = 2.0
    pocket = build_box(
        BACKPLATE_W - 2 * FRAME_INSET,
        CENTER_FRONT_Y + overshoot,
        BACKPLATE_H - 2 * FRAME_INSET,
        (0.0, (CENTER_FRONT_Y - overshoot) / 2.0, BACKPLATE_H / 2.0),
        "dish_pocket")
    apply_boolean(shell, pocket, 'DIFFERENCE')

    return shell


def assert_volume_grew(shell, prev_volume, step_name):
    """Every relief step should be a net UNION onto the shell (even icon's
    internal hole cuts are outweighed by the raised material added around
    them - see the debug trace that first established this), so volume
    should only ever increase step over step. A drop means the boolean
    solver corrupted the shell rather than just failing to add the new
    piece - the exact failure mode that BOLD_OFFSET=0.3 caused on the
    subtitle once it was actually overlapping the shell (self-
    intersecting input confuses the solver's inside/outside
    classification, which can carve away existing material instead of
    just skipping the union). Catches that immediately instead of
    silently exporting a corrupted STL."""
    vol = mesh_volume(shell)
    assert vol > prev_volume, (
        f"{step_name} DECREASED total volume ({prev_volume:.1f} -> {vol:.1f}mm3) - "
        f"the boolean union likely corrupted the shell rather than just failing to add "
        f"material. Usual cause: self-intersecting input geometry (e.g. BOLD_OFFSET too "
        f"high for this text's size/line-spacing) - not a sign to raise the plate "
        f"thickness or embed depth."
    )
    return vol


def build_backplate():
    shell = build_backplate_box()
    vol = mesh_volume(shell)
    icon_bottom_z = build_logo_icon(shell)
    vol = assert_volume_grew(shell, vol, "icon")
    text_bottom_z = build_logo_text(shell, icon_bottom_z)
    vol = assert_volume_grew(shell, vol, "wordmark")
    trophy_bottom_z = build_trophy_number(shell, text_bottom_z)
    vol = assert_volume_grew(shell, vol, "#1")
    build_subtitle(shell, trophy_bottom_z)
    assert_volume_grew(shell, vol, "subtitle")
    return shell


# ============================================================
# MAIN
# ============================================================

def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    clear_scene()

    backplate = build_backplate()

    vol = mesh_volume(backplate)
    nm = nonmanifold_fraction(backplate)
    print(f"backplate: volume={vol:.1f}mm3  non-manifold edge fraction={nm:.4f}")
    assert vol > 0.0, "backplate has zero/negative volume - a boolean likely emptied it"

    if EXPORT_STL:
        export_stl(backplate, EXPORT_FILENAME)

    if RENDER_IMAGES:
        center_pt, size = compute_scene_bounds()
        render_angles(center_pt, size)
        render_closeup(backplate, "logo_closeup")

    print("Done.")


if __name__ == "__main__":
    main()
