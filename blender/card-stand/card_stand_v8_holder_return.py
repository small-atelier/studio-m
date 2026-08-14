"""
Store-counter backplate, back to the card-holder pairing (Blender bpy) -
standalone, NOT terrain.

v8 change: forked from v7 (card_stand_v7_trophy.py, the "#1" trophy
plaque). Returns to the original card-stand idea (a Mythos backplate
paired with a separate card-holder piece, like v5/v6) but keeps every
structural lesson learned building the trophy:

1. #1 and the subtitle are gone - back to just icon + MYTHOS wordmark,
   like v6's backplate-solo.
2. The decorative ridge goes back to an upside-down U (top + both sides,
   no bottom stroke) - the SAME reasoning as v5/v6 originally had for
   this shape: the card holder's own back fin will sit flush against the
   lower portion of the backplate once glued, and a ridge running that
   low would collide with it. v7 had closed this into a full loop only
   because there was no holder to collide with there anymore - now
   there is again.
3. TENON_* - a pair of tenons protruding from the border zone's front
   face, in the lower-middle area the ridge no longer covers, keying
   into the EXISTING 70mm card holder's back fin sockets (built in
   card_stand_v5_flat_sharp_logo.py's build_holder()). This backplate
   is now 86mm wide (grown across the trophy iterations) - decided to
   keep reusing that 70mm holder rather than widen a matching one, so
   the backplate simply overhangs it on both sides. TENON_* values are
   copied EXACTLY from that script's own constants (position, size, fit
   clearance), not just eyeballed close, since the physical fit depends
   on both sides agreeing precisely.
4. DISH_DEPTH's own recess now stops at the same halfway line as the
   ridge, instead of running the full height like v7's standalone
   plaque - the holder's back fin needs a genuinely flat mating surface
   down there, not a recessed one.

Everything else carries over from v7 as-is: the flush border/text dish
(DISH_DEPTH matched to EMBOSS_H), the thinned BACKPLATE_T (5mm), the
genuine Bold Baskerville face (no synthetic curve offset - see
BOLD_OFFSET's own history for why that was abandoned), the back-edge
release chamfer, and the volume-growth safety assert after every union.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python card_stand_v8_holder_return.py
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

EXPORT_DIR = "/Users/mannil/pfn/projects/mjnet/studio-m/blender/card-stand/output_v8"
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

# --- Backplate ---
BACKPLATE_W = 86.0
BACKPLATE_H = 138.0
BACKPLATE_T = 5.0                   # thinned from v7's 6.0 - CENTER_T (panel thickness after the
                                     # dish) is 3.0mm, a healthy 1.5mm margin over EMBOSS_EMBED's
                                     # 1.5mm bonding depth. Real remaining risk at this thickness is
                                     # warping during cure and handling durability, not bonding -
                                     # neither is something these mesh/boolean checks can catch.
DISH_DEPTH = 2.0                    # panel recesses this far from the border's own front face -
                                     # matched to EMBOSS_H so the border and the text's own tip land
                                     # flush, rather than the border sitting proud of the text.
CENTER_T = BACKPLATE_T - DISH_DEPTH # panel's own remaining thickness after the dish
BACKPLATE_BEVEL_W = 3.0

# Width of the solid full-thickness frame around the plate's own edge,
# measured past the ridge's own outer legs (RIDGE_INSET + RIDGE_WIDTH)
# so the ridge sits entirely on solid material and the dish starts just
# inside it.
FRAME_MARGIN_PAST_RIDGE = 2.0

EMBOSS_H = 2.0                      # flat raised height off the backplate face - kept at v7's
                                     # halved value (was 3.0-4.0 originally, which is what actually
                                     # delaminated mid-print - see the site post's own history)
EMBOSS_EMBED = 1.5                  # extra embed into the backplate for a clean union
CUTTER_OVERSHOOT = 1.0

# curve_data.offset for the wordmark - kept at 0.0. A synthetic bold via
# this offset proved unstable once text is genuinely bonded to the shell
# (self-intersecting input can confuse the boolean solver badly enough
# to carve away existing shell material, not just fail to add the new
# piece - see assert_volume_grew's own comment). Real boldness now comes
# from TEXT_FONT_PATH being an actual Bold face instead.
BOLD_OFFSET = 0.0

# --- Decorative ridge - back to v5/v6's upside-down U (top + both
# sides, no bottom stroke), not v7's full loop - the holder's own back
# fin sits flush against the lower portion of the backplate once glued,
# and a ridge running that low would collide with it. ---
RIDGE_INSET = 4.0
RIDGE_WIDTH = 3.0
RIDGE_HEIGHT = 1.5

# Where the solid full-thickness frame ends and the recessed center
# panel begins - past the ridge's own outer edge, see
# FRAME_MARGIN_PAST_RIDGE above.
FRAME_INSET = RIDGE_INSET + RIDGE_WIDTH + FRAME_MARGIN_PAST_RIDGE
PANEL_W = BACKPLATE_W - 2 * FRAME_INSET

# How far the panel recesses from the front - relief inside it
# (icon/wordmark) is built off this Y instead of the plain 0 the
# border-zone ridge/nubs still use.
CENTER_FRONT_Y = BACKPLATE_T - CENTER_T

# Text pieces use Blender's curve_data.extrude, which extrudes
# SYMMETRICALLY around the curve's own center plane - unlike the icon's
# _extrude_profile, whose `offset` param IS the front tip already. This
# is the corrected location Y that lines up the text's own front tip
# with CENTER_FRONT_Y - EMBOSS_H, same as the icon (see v7's own history
# for the bug this fixes - text used to sit proud of the icon and, more
# importantly, float unbonded above the panel surface).
TEXT_FRONT_Y = CENTER_FRONT_Y + (EMBOSS_EMBED - EMBOSS_H) / 2.0

# Small chamfer around the BACK perimeter edge only, on top of the
# decorative BACKPLATE_BEVEL_W bevel - a resin-print release aid.
RELEASE_CHAMFER_W = 1.0

# --- Logo icon ---
LOGO_CONTOURS_PATH = "/Users/mannil/pfn/projects/mjnet/studio-m/blender/card-stand/logo_contours_v5.json"
LOGO_W = 58.0                # back to a size that comfortably fits PANEL_W with real margin - v7
                              # pushed this to the panel's own ceiling for a standalone plaque with
                              # nothing else competing for width; this one shares the plate with a
                              # holder-attachment area below, so isn't chasing max size the same way
LOGO_SIDE_MARGIN = 4.0
LOGO_ASPECT = 376.0 / 720.0
LOGO_CENTER_X = 0.0
LOGO_TOP_MARGIN = 12.0

# --- MYTHOS wordmark ---
TEXT_FONT_PATH = "/Users/mannil/pfn/projects/mjnet/studio-m/blender/card-stand/BaskervilleBold.ttf"
                            # genuine Bold face (extracted from Baskerville.ttc via fontTools,
                            # since Blender's font loader can't address a face within a .ttc
                            # directly) - real drawn-bold strokes, no self-intersection risk since
                            # the outline is wider by design, not synthetically expanded.
TEXT_STRING = "MYTHOS"
TEXT_SIZE = 15.0
TEXT_GAP_BELOW_ICON = 6.0
TEXT_SIDE_MARGIN = 4.0

# --- Attachment tenons - a pair of ROUND pegs protruding from the
# border zone's own front face (solid full BACKPLATE_T material, not the
# thinner recessed panel), keying into the card holder piece's back fin.
# Round instead of the original v5/v6 rectangular tenon: once the holder
# prints with its width axis vertical (see the resin-print orientation
# discussion this session - that axis change is what finally kills the
# wedge-cavity overhang that caused the earlier deformed/scarred print),
# the tenon SOCKETS become the one feature that isn't part of the
# constant cross-section, and a rectangular socket's flat top edge is a
# small unsupported bridge. A round hole with its axis horizontal
# doesn't have that problem - the void narrows to a point at the top
# following the circle's own curve instead of presenting a flat ceiling,
# so it self-supports. Position/offset/embed values still match the
# holder's own TENON_OFFSET_X/TENON_Z_CENTER - only the cross-section
# shape changed, not where it sits. The holder's own socket needs to be
# rebuilt round to match whenever that script gets updated. ---
TENON_OFFSET_X = 17.0       # distance from center X for each of the pair - matches the holder's
                             # own TENON_OFFSET_X exactly
TENON_DIAMETER = 8.0         # nominal diameter before fit clearance
TENON_SOCKET_DEPTH = 4.0     # matches the holder socket's own cut depth
TENON_FIT_CLEARANCE = 0.25   # shrinks the tenon (not the socket) for an easy slip fit
TENON_EMBED = 1.0            # how far the tenon embeds into the backplate's own front face for a
                             # clean union, beyond the plain protrusion
TENON_Z_CENTER = 28.0        # matches the holder socket's own Z position exactly
TENON_PROTRUDE_LEN = TENON_SOCKET_DEPTH - 0.5   # protrudes slightly less than the socket's own cut
                                                 # depth so the tenon doesn't bottom out before the
                                                 # two flat faces meet - same margin the original
                                                 # holder/backplate pairing used

# ============================================================
# SANITY CHECKS
# ============================================================
assert BACKPLATE_W <= 89.0, "backplate wider than the Photon Mono 2 bed's 89.6mm axis (flat print)"
assert BACKPLATE_H <= 143.0, "backplate taller than the Photon Mono 2 bed's 143.4mm axis (flat print)"
assert CENTER_T > EMBOSS_EMBED, "dished middle thinner than the relief's own embed depth"
assert LOGO_W <= PANEL_W - 2 * LOGO_SIDE_MARGIN, \
    "logo icon wider than the recessed panel - it'll touch the frame, see PANEL_W"
assert TENON_OFFSET_X + TENON_DIAMETER / 2.0 < BACKPLATE_W / 2.0 - RIDGE_INSET, \
    "tenon runs past the ridge's own inner edge"
assert 0.0 < TENON_Z_CENTER - TENON_DIAMETER / 2.0, "tenon runs off the bottom of the plate"
assert TENON_OFFSET_X + TENON_DIAMETER / 2.0 < 70.0 / 2.0, \
    "tenon runs past the 70mm holder's own edge - it must stay within the narrower holder's width"


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
    pocket/relief/nubs turn it into something more complex to select
    edges on."""
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


def build_cylinder(diameter, length, center, name, segments=24):
    """Cylinder of given diameter/length centered at `center`, axis along
    world Y (the tenon's own protrusion direction) - round pegs/sockets
    with a horizontal axis print without support (the void narrows to a
    point at the top following the circle's own curve, unlike a box
    hole's flat overhanging top edge). bmesh's create_cone builds along
    local Z by default, so rotate 90deg around X to lay it onto Y before
    placing it."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                           radius1=diameter / 2.0, radius2=diameter / 2.0, depth=length)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0.0, 0.0, 0.0),
                      matrix=mathutils.Matrix.Rotation(math.radians(90.0), 3, 'X'))
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
    """Real vector text, converted to a mesh, extruded to match
    EMBOSS_H/EMBOSS_EMBED. Returns the still-unpositioned mesh object."""
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
    vol = mesh_volume(obj)
    nm = nonmanifold_fraction(obj)
    print(f"{name} piece (pre-union): volume={vol:.1f}mm3  non-manifold={nm:.4f}")


def build_logo_text(shell, icon_bottom_z):
    """Real vector text (Baskerville Bold), flat-extruded to match the
    icon's height."""
    obj = _build_flat_text_mesh(TEXT_STRING, TEXT_SIZE, BOLD_OFFSET)

    local_top_y = max(v.co.y for v in obj.data.vertices)
    local_bottom_y = min(v.co.y for v in obj.data.vertices)
    text_w = max(v.co.x for v in obj.data.vertices) - min(v.co.x for v in obj.data.vertices)
    assert text_w <= PANEL_W - 2 * TEXT_SIDE_MARGIN, \
        f"MYTHOS wordmark ({text_w:.1f}mm) touches the recessed panel edge - shrink TEXT_SIZE"
    target_top_z = icon_bottom_z - TEXT_GAP_BELOW_ICON

    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    obj.location = (LOGO_CENTER_X, TEXT_FRONT_Y, target_top_z - local_top_y)
    apply_transform(obj)
    _print_piece_stats("MYTHOS wordmark", obj)
    union_onto(shell, obj)


def build_nubs(shell):
    """Pair of ROUND tenons protruding -Y from the border zone's own
    front face (Y=0, solid full-thickness material) - keys into the card
    holder's back fin sockets. Round rather than the original v5/v6
    rectangular tenon - see TENON_DIAMETER's own comment for why (the
    holder's socket needs a horizontal-axis round hole to self-support
    once it prints with its width axis vertical). Position/embed/protrude
    logic unchanged from the rectangular version, just built as a
    cylinder instead of a box."""
    for sign in (-1, 1):
        tenon = build_cylinder(
            TENON_DIAMETER - 2 * TENON_FIT_CLEARANCE,
            TENON_PROTRUDE_LEN + TENON_EMBED,
            (sign * TENON_OFFSET_X, (TENON_EMBED - TENON_PROTRUDE_LEN) / 2.0, TENON_Z_CENTER),
            "tenon")
        union_onto(shell, tenon)


def build_backplate_box():
    """Plain box + upside-down-U ridge, beveled, then pocketed from the
    FRONT to dish the middle down to CENTER_T - all BEFORE the logo
    stamp is unioned on. Finishes with a small flat chamfer around the
    back edge only, for print-plate release, and the pair of attachment
    nubs in the lower area the ridge no longer covers."""
    shell = build_box(BACKPLATE_W, BACKPLATE_T, BACKPLATE_H,
                       (0.0, BACKPLATE_T / 2.0, BACKPLATE_H / 2.0), "backplate")
    chamfer_back_edge(shell, BACKPLATE_T, RELEASE_CHAMFER_W)

    # Decorative ridge - upside-down U (top + both sides, no bottom
    # stroke) - the holder's own back fin sits flush against the lower
    # portion once glued, and a ridge running that low would collide
    # with it.
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

    # Dish the middle: pocket the FRONT down to CENTER_T everywhere
    # except a solid full-thickness frame just past the ridge's own
    # outer edge. Stops at the SAME halfway line as the ridge (leg_z0
    # above) rather than running the full height - the holder's back fin
    # needs a genuinely flat mating surface down there, not a recessed
    # one, same reasoning as the ridge stopping there. The BACK face is
    # untouched regardless (cut only reaches as far as y=CENTER_FRONT_Y),
    # so it stays one continuous flat plane for the flat-on-back print.
    # Cut AFTER the bevel so the pocket's own walls stay sharp.
    overshoot = 2.0
    pocket_z0, pocket_z1 = leg_z0, BACKPLATE_H - FRAME_INSET
    pocket = build_box(
        BACKPLATE_W - 2 * FRAME_INSET,
        CENTER_FRONT_Y + overshoot,
        pocket_z1 - pocket_z0,
        (0.0, (CENTER_FRONT_Y - overshoot) / 2.0, (pocket_z0 + pocket_z1) / 2.0),
        "dish_pocket")
    apply_boolean(shell, pocket, 'DIFFERENCE')

    build_nubs(shell)

    return shell


def assert_volume_grew(shell, prev_volume, step_name):
    """Every relief step should be a net UNION onto the shell, so volume
    should only ever increase step over step. A drop means the boolean
    solver corrupted the shell rather than just failing to add the new
    piece - see card_stand_v7_trophy.py's own history for the exact
    failure mode this catches (self-intersecting input confusing the
    solver's inside/outside classification badly enough to carve away
    existing material)."""
    vol = mesh_volume(shell)
    assert vol > prev_volume, (
        f"{step_name} DECREASED total volume ({prev_volume:.1f} -> {vol:.1f}mm3) - "
        f"the boolean union likely corrupted the shell rather than just failing to add "
        f"material."
    )
    return vol


def build_backplate():
    shell = build_backplate_box()
    vol = mesh_volume(shell)
    icon_bottom_z = build_logo_icon(shell)
    vol = assert_volume_grew(shell, vol, "icon")
    build_logo_text(shell, icon_bottom_z)
    assert_volume_grew(shell, vol, "wordmark")
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
        export_stl(backplate, "backplate.stl")

    if RENDER_IMAGES:
        center_pt, size = compute_scene_bounds()
        render_angles(center_pt, size)
        render_closeup(backplate, "logo_closeup")

    print("Done.")


if __name__ == "__main__":
    main()
