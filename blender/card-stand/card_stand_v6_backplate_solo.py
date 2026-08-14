"""
Store-counter backplate ONLY (Blender bpy) - standalone, NOT terrain.

v6 change: forked from v5 (card_stand_v5_flat_sharp_logo.py) to make a
backplate-only variant - the standing-card holder (comb + tenon joint) is
removed entirely, so this is just the plaque: box + decorative ridge +
logo icon + wordmark, printed and handled on its own.

The wordmark is also merged back onto the backplate face directly (v5's
original approach - see build_logo_text) instead of living as its own
glued-on part (text_plate_v1.py's fix), but WITH that fix's technique
carried over: curve_data.offset bolds every stroke edge (O's ring and
S's curve both gain real wall thickness, not just a bigger font) and
TEXT_SIZE goes back up to 18 - see TEXT_BOLD_OFFSET's comment for why
15 doesn't pair safely with the offset. The backplate is already a solid
6mm box, so the "thin graze with nothing behind it" half of the original
failure doesn't apply here the way it did on the 2mm standalone plate -
only the "letters too thin" half needed carrying over.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python card_stand_v6_backplate_solo.py
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

EXPORT_DIR = "/Users/mannil/pfn/projects/mjnet/studio-m/blender/card-stand/output_v6"
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
BACKPLATE_W = 70.0
BACKPLATE_H = 138.0                 # printed flat on its back (zero supports - every raised
                                     # feature projects the same direction, straight up off the
                                     # plate), footprint directly against the bed's two shorter
                                     # axes (143.4 x 89.6mm)
BACKPLATE_T = 6.0
BACKPLATE_BEVEL_W = 3.0   # effectively the max for a 6mm-thick plate - Blender's bevel modifier
                           # clamps overlap by default, and 5mm/10mm both produced byte-identical
                           # geometry to 3mm once tested (confirmed via volume comparison) since
                           # the clamp was already engaged; more width does nothing further without
                           # more plate thickness to give it room, which the user doesn't want here

# Flat single-level plateau + sharp 90-degree walls for the logo icon -
# easier to paint cleanly (a crisp edge to paint up to, no subtle
# gradient to fight). Built from real vector contours (marching squares
# on the mask, see extract_logo_contours.py) rather than a per-pixel
# grid - clean boolean unions/differences instead of a heightfield mesh.
EMBOSS_H = 2.0                      # flat raised height off the backplate face
EMBOSS_EMBED = 1.0                  # extra embed into the backplate for a clean union
CUTTER_OVERSHOOT = 1.0              # hole cutters (e.g. the "O") reach this far past the raised
                                     # face and this far past the embed depth, for a clean cut

# Backplate's own bevel is separate and bigger, and still gets applied
# to the PLAIN box (+ridge) BEFORE the logo icon/text pieces are added -
# a holdover from the old heightfield version where this ordering was
# essential (a bevel modifier on that dense grid mangled the fine
# relief), but worth keeping even now: it keeps the bevel modifier's
# edge count small and predictable (a plain box), and keeps the logo's
# own sharp 90-degree walls untouched by any bevel at all.

# --- Decorative ridge - upside-down U (top + both sides, no bottom
# stroke) inset from the backplate's own edges. v5 stopped this halfway
# down to avoid colliding with the holder's back fin; with no holder in
# this variant that constraint is gone, but the ridge is left at v5's
# proportions since nothing was asked about it. ---
RIDGE_INSET = 4.0
RIDGE_WIDTH = 2.5
RIDGE_HEIGHT = 2.0

# --- Logo icon (vector contours, see extract_logo_contours.py) ---
LOGO_CONTOURS_PATH = "/Users/mannil/pfn/projects/mjnet/studio-m/blender/card-stand/logo_contours_v5.json"
LOGO_W = 58.0
LOGO_ASPECT = 376.0 / 720.0
LOGO_CENTER_X = 0.0
LOGO_TOP_MARGIN = 15.0

# --- MYTHOS wordmark - real vector text, not traced from the source
# raster. Baskerville visually matched the source lettering closely
# (splayed M, moderate stroke contrast, same serif shapes) among locally
# available fonts. Merged straight onto the backplate face (v5's
# approach), but with text_plate_v1's bold-offset fix carried over so
# the O/S strokes survive handling this time. ---
TEXT_FONT_PATH = "/System/Library/Fonts/Supplemental/Baskerville.ttc"
TEXT_STRING = "MYTHOS"
TEXT_SIZE = 18.0          # back up from v5's 15 - 15 is too small to pair with the bold offset
                           # below (see TEXT_BOLD_OFFSET's own comment); size trimmed from
                           # text_plate_v1's context back into TEXT_GAP_BELOW_ICON's own room here
TEXT_BOLD_OFFSET = 0.12   # curve outline offset - pushes every stroke edge out this much, the
                           # fix for O's ring / S's curve reading too thin. text_plate_v1 tested
                           # 0.08-0.22: past ~0.13 the offset self-intersects O/S's tight inner
                           # curves and the union silently collapses most of the letterforms
                           # (volume drops from ~3000mm3 to ~200mm3, non-manifold fraction jumps
                           # to 12%) - 0.12 is comfortably inside the safe range
TEXT_GAP_BELOW_ICON = 8.0            # gap between the icon's own bottom and the text's top

# ============================================================
# SANITY CHECKS
# ============================================================
assert BACKPLATE_W <= 89.0, "backplate wider than the Photon Mono 2 bed's 89.6mm axis (flat print)"
assert BACKPLATE_H <= 143.0, "backplate taller than the Photon Mono 2 bed's 143.4mm axis (flat print)"


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

    # Raking key light: aimed with to_track_quat (direction the light
    # travels), not hand-picked euler angles - the logo face's outward
    # normal is roughly -Y, so illuminating it needs dir.y > 0.
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
    or legibility, so eyeball this before trusting the wide renders."""
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
    """Real vector text (Baskerville), flat-extruded to match the icon's
    height. curve_data.offset bolds every stroke edge (text_plate_v1's
    fix) so O's ring and S's curve carry real wall thickness this time,
    rather than v5's plain (unbolded, TEXT_SIZE=15) version that snapped
    during support removal."""
    font = bpy.data.fonts.load(TEXT_FONT_PATH)
    curve_data = bpy.data.curves.new("logo_text_curve", type='FONT')
    curve_data.body = TEXT_STRING
    curve_data.font = font
    curve_data.size = TEXT_SIZE
    curve_data.align_x = 'CENTER'
    curve_data.align_y = 'CENTER'   # not 'TOP' - see below
    curve_data.offset = TEXT_BOLD_OFFSET
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
    # above the real cap-height.
    local_top_y = max(v.co.y for v in obj.data.vertices)
    target_top_z = icon_bottom_z - TEXT_GAP_BELOW_ICON

    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    obj.location = (LOGO_CENTER_X, -EMBOSS_H, target_top_z - local_top_y)
    apply_transform(obj)
    union_onto(shell, obj)


def build_backplate_box():
    """Plain box + ridge, beveled - see BACKPLATE_BEVEL_W's comment for
    why this has to happen BEFORE the logo stamp is unioned on, not
    after."""
    shell = build_box(BACKPLATE_W, BACKPLATE_T, BACKPLATE_H,
                       (0.0, BACKPLATE_T / 2.0, BACKPLATE_H / 2.0), "backplate")

    # Decorative ridge - upside-down U (top + both sides, no bottom
    # stroke). Built as 3 boxes joined into ONE ridge solid first
    # (generous overlap at the two corners), then unioned onto the
    # backplate as a single piece.
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
