"""
Mythos logo, recessed into both faces of the plain dice tray's basin
floor (Blender bpy) - two independent shallow pockets (1mm deep each,
same recess+insert technique as the combat-modifier tokens and card-stand
in blender/combat-modifiers/build_modifier_tokens.py), not one
full-thickness see-through cut. A 1mm solid membrane stays between them
in the 3mm floor, so the base tray is a complete, structurally sound
single-color part on its own even before either insert goes in.

The bottom pocket uses a MIRRORED contour - same "mirror" trick the
tokens' two faces use - so it un-mirrors and reads correct, not
backwards, when viewed from underneath. Three parts total (base + two
inserts), meant as one combined multi-material print (matching the
project's per-part-extruder .3mf convention) rather than glued-on
inserts - each pocket is only 1mm deep, so per-layer colour swapping is
cheap (~5 layers at 0.2mm), unlike a full 3mm through-cut would be.

Base mesh (input/dice-tower/dice_tray.stl) is a bought/downloaded STL,
not built from primitives here - imported as-is and only the two pocket
cutters/inserts are generated. Bounds below were measured directly off
that STL: main basin floor (top pocket site) is at z=3.0, x=[-96.0,
28.1], y=[-88.3, 105.7]; outer bottom face (bottom pocket site) is at
z=0.0, x=[-99.0, 89.0], y=[-91.3, 108.7]. Re-measure if the input file
changes.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_dice_tray.py
"""

import bpy
import bmesh
import json
import math
import mathutils
import os
import sys
import zipfile

# ============================================================
# CONFIG (all mm)
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
INPUT_STL = os.path.join(REPO_ROOT, "input", "dice-tower", "dice_tray.stl")

# Reuses the already-traced Mythos contours - same source as the
# combat-modifier bonus token, no re-tracing.
MYTHOS_CONTOURS_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "card-stand", "logo_contours_v5.json"))
MYTHOS_ASPECT = 376.0 / 720.0  # h/w, 720x376 source - width is the controlling dimension

# Wordmark below the icon, same brand font as the card-stand/combat-modifier
# Mythos pieces (not the generic TEXT_FONT_PATH those projects use for
# everything else) - sized to the SAME WIDTH as the icon above it.
LOGO_TEXT = "MYTHOS"
MYTHOS_FONT_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "card-stand", "BaskervilleBold.ttf"))
TEXT_SPACING = 1.1  # see feedback_blender_boolean_fragility memory - touching glyph pairs at
                     # small sizes corrupt the EXACT solver; ported as-is even though this is a
                     # single convert+cut, not a chained boolean, cheap insurance either way
GAP_FRAC = 0.15  # gap between icon and text, as a fraction of the icon's own height

# Top pocket's basin is long and narrow (124.1 x 194.0mm interior) - the
# icon+text lockup is itself short and wide, so laid out straight it's
# capped by the SHORT axis while most of the LONG axis sits unused.
# Rotating the whole lockup 90 degrees swaps which axis constrains it,
# letting it run ~30% bigger (icon width ~117mm vs ~94mm) before hitting
# the same margins. Not worth doing on the bottom pocket - its available
# area is closer to square, so rotating there buys almost nothing.
TOP_WIDTH_BUDGET = 94.0   # basin short axis (124.1mm) minus ~15mm margin each side
TOP_LENGTH_BUDGET = 164.0  # basin long axis (194.0mm) minus ~15mm margin each side
TOP_CENTER_X = -33.95
TOP_CENTER_Y = 8.7

# Bottom: the underside is one unbroken flat rectangle (no dividing wall
# in the way), so it can run much closer to the tray's full 188 x 200mm
# footprint - ~9mm edge margin instead of the basin's ~15mm. Available
# area here is close to square, so left un-rotated.
BOTTOM_ICON_W = 140.0
BOTTOM_CENTER_X = -5.0
BOTTOM_CENTER_Y = 8.7

FLOOR_Z0 = 0.0
FLOOR_Z1 = 3.0
POCKET_DEPTH = 1.0  # each face - leaves a 1mm solid membrane between the two pockets
CUT_POKE = 0.3  # cutter overshoot past the OUTER (open-air) face only, avoids coplanar artifacts

EXPORT_DIR = os.path.join(SCRIPT_DIR, "output")
EXPORT_STL = True
EXPORT_3MF = True
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1200, 1200)
RENDER_IMAGES = "--no-render" not in sys.argv

BASE_COLOR = (1.0, 1.0, 1.0, 1.0)
INLAY_COLOR = (0.06, 0.45, 0.12, 1.0)
BASE_EXTRUDER_SLOT = 1
INLAY_EXTRUDER_SLOT = 2

# ============================================================
# GENERIC HELPERS (ported from blender/combat-modifiers/build_modifier_tokens.py)
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


def dedupe_closed_loop(points, tol=1e-9):
    """Traced contours (skimage find_contours) can come back as closed
    rings with the first and last point identical - a degenerate
    zero-length edge that corrupts the extruded solid's topology if left
    in."""
    if len(points) > 1:
        x0, y0 = points[0]
        x1, y1 = points[-1]
        if abs(x0 - x1) < tol and abs(y0 - y1) < tol:
            return points[:-1]
    return points


def load_contours(path):
    with open(path) as f:
        return json.load(f)


def mirror_points_x(points):
    """Flip a closed (x, y) point loop's X coordinate - for the bottom
    pocket, so it un-mirrors and reads correct (not backwards) when
    viewed from underneath. Same reasoning as the tokens' own
    mirror_points_x for their back-face contour."""
    return [(-x, y) for x, y in points]


def place_object(obj, center_x, center_y, mirror=False, rotate90=False):
    """Final placement step for a piece built at local, origin-centered
    coordinates: optional X-mirror (read correct from underneath),
    optional 90-degree rotation (fit the top lockup along the basin's
    long axis instead of its short one), then translate to the real
    world position. Applied uniformly so icon and text pieces of the
    same lockup stay in registration with each other.

    Mirroring is orientation-REVERSING (determinant -1) and needs
    reverse_faces to flip winding correctly - recalc_face_normals is a
    heuristic that can invert one shell relative to another on a
    multi-shell mesh like this (icon + text, no shared geometry between
    them), silently canceling most of the volume even though every edge
    stays manifold (see feedback_blender_text_mesh_gotchas memory).
    Rotation is orientation-PRESERVING (determinant +1) and needs no
    normal fix at all - the existing winding is already correct."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for v in bm.verts:
        x, y = v.co.x, v.co.y
        if mirror:
            x = -x
        if rotate90:
            x, y = -y, x
        v.co.x, v.co.y = x + center_x, y + center_y
    if mirror:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def import_stl(path):
    bpy.ops.wm.stl_import(filepath=path)
    return bpy.context.selected_objects[0]


def export_stl(obj, filename):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = os.path.join(EXPORT_DIR, filename)
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"Exported {path}")


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


def export_project_3mf(parts, path):
    """Anycubic Slicer Next's project-3mf flavor - see
    build_modifier_tokens.py's own copy of this for the full story.
    `parts` is a list of (obj, name, extruder_slot)."""
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


def setup_camera_and_light(center, distance, ortho_scale, from_below=False):
    """Looks straight down (or up) the Z axis - top/bottom of the tray,
    not the face-on view used for the flat tokens. Flipping the view
    direction necessarily mirrors exactly one in-plane axis (parity) -
    picked X here (180 deg around local Y) so the mountain silhouette
    stays right-side up in the bottom render instead of flipping
    upside-down, which to_track_quat's default resolution would do."""
    sign = 1.0 if from_below else -1.0
    cam_data = bpy.data.cameras.new("RenderCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = ortho_scale
    cam = bpy.data.objects.new("RenderCam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = center + mathutils.Vector((0.0, 0.0, -sign * distance))
    cam.rotation_euler = (0.0, math.pi if from_below else 0.0, 0.0)
    bpy.context.scene.camera = cam

    light_data = bpy.data.lights.new("RenderLight", type='SUN')
    light_data.energy = 3.0
    light = bpy.data.objects.new("RenderLight", light_data)
    bpy.context.collection.objects.link(light)
    light.location = center + mathutils.Vector((-sign * distance * 0.3, distance * 0.6, -sign * distance * 1.5))
    direction = center - light.location
    light.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    return cam


def render_face(name, from_below=False):
    center, size = compute_scene_bounds()
    distance = size * 1.2
    setup_camera_and_light(center, distance, size * 1.15, from_below=from_below)
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = RENDER_RESOLUTION
    scene.render.filepath = os.path.join(RENDER_DIR, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {scene.render.filepath}")


# ============================================================
# MYTHOS ICON - full-thickness prism (XY footprint, extruded along Z),
# not the XZ-extruded-along-Y build the tokens use, since this sits flat
# in the tray floor rather than standing face-on.
# ============================================================


def _extrude_profile_xy(points, z0, thickness, name):
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


def build_mythos_prism(contours, icon_w, icon_h, local_y, z0, thickness, name_prefix):
    """Built at local X=0, local Y=local_y (mirror/rotate/final placement
    all happen later, via place_object, once the icon and text pieces of
    a lockup are both built and can be transformed identically)."""
    outer_pts, hole_pts = [], []
    for c in contours:
        pts = [(u * icon_w - icon_w / 2.0, v * icon_h - icon_h / 2.0 + local_y) for u, v in c["points"]]
        pts = dedupe_closed_loop(pts)
        (hole_pts if c["hole"] else outer_pts).append(pts)
    assert outer_pts, f"{name_prefix}: traced icon has no outer contours"

    solid = _extrude_profile_xy(outer_pts[0], z0, thickness, f"{name_prefix}_0")
    for i, pts in enumerate(outer_pts[1:], start=1):
        union_onto(solid, _extrude_profile_xy(pts, z0, thickness, f"{name_prefix}_{i}"))
    for i, pts in enumerate(hole_pts):
        cutter = _extrude_profile_xy(pts, z0 - 1.0, thickness + 2.0, f"{name_prefix}_hole_{i}")
        apply_boolean(solid, cutter, 'DIFFERENCE')

    return solid


def measure_text_aspect(text, font_path):
    """Height/width ratio of the text at some nominal size - queried once
    so callers can compute layout (target text height from a target
    width) before generating the real, final-sized text mesh."""
    font = bpy.data.fonts.load(font_path)
    curve_data = bpy.data.curves.new("measure_text_curve", type='FONT')
    curve_data.body = text
    curve_data.font = font
    curve_data.size = 10.0
    curve_data.align_x = 'CENTER'
    curve_data.align_y = 'CENTER'
    curve_data.space_character = TEXT_SPACING
    obj = bpy.data.objects.new("measure_text", curve_data)
    bpy.context.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    mesh = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.meshes.remove(mesh, do_unlink=True)
    return h / w


def build_text_prism(text, target_width, local_y, z0, thickness, name, font_path=MYTHOS_FONT_PATH):
    """Same local-frame convention as build_mythos_prism: local X=0,
    local Y=local_y, scaled so its width is exactly target_width (the
    "same width as the icon" ask) - height follows the font's own aspect."""
    font = bpy.data.fonts.load(font_path)
    curve_data = bpy.data.curves.new(f"{name}_curve", type='FONT')
    curve_data.body = text
    curve_data.font = font
    curve_data.size = 10.0
    curve_data.align_x = 'CENTER'
    curve_data.align_y = 'CENTER'
    curve_data.space_character = TEXT_SPACING
    curve_data.extrude = thickness / 2.0
    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(obj)

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-3)

    xs = [v.co.x for v in bm.verts]
    scale = target_width / (max(xs) - min(xs))
    for v in bm.verts:
        v.co.x *= scale
        v.co.y *= scale
        v.co.y += local_y
        # curve's own extrude already gives the exact world-space thickness,
        # centered on local z=0 - shift into [z0, z0 + thickness].
        v.co.z += z0 + thickness / 2.0

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def build_logo_lockup(contours, icon_w, icon_h, text_h, z0, thickness, name_prefix):
    """Icon above the wordmark, same width, gap proportional to icon
    height, both built in the local origin-centered frame - caller then
    applies place_object() for mirror/rotate/final position."""
    gap = GAP_FRAC * icon_h
    icon_local_y = (text_h + gap) / 2.0
    text_local_y = -(icon_h + gap) / 2.0

    icon = build_mythos_prism(contours, icon_w, icon_h, icon_local_y, z0, thickness, f"{name_prefix}_icon")
    text = build_text_prism(LOGO_TEXT, icon_w, text_local_y, z0, thickness, f"{name_prefix}_text")
    return join_objects([icon, text], name_prefix)


# ============================================================
# MAIN
# ============================================================


def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    if RENDER_IMAGES:
        os.makedirs(RENDER_DIR, exist_ok=True)

    clear_scene()
    contours = load_contours(MYTHOS_CONTOURS_PATH)
    text_aspect = measure_text_aspect(LOGO_TEXT, MYTHOS_FONT_PATH)

    # Top lockup sized (pre-rotation) so that after the 90-degree turn its
    # x-extent (= pre-rotation height) fits TOP_WIDTH_BUDGET and its
    # y-extent (= pre-rotation width) fits TOP_LENGTH_BUDGET - see the
    # CONFIG comment above for why rotating is worth it here.
    lockup_k = MYTHOS_ASPECT * (1.0 + GAP_FRAC) + text_aspect  # pre-rotation height / width
    top_icon_w = min(TOP_WIDTH_BUDGET / lockup_k, TOP_LENGTH_BUDGET)
    top_icon_h = top_icon_w * MYTHOS_ASPECT
    top_text_h = top_icon_w * text_aspect
    print(f"top lockup: icon {top_icon_w:.1f}x{top_icon_h:.1f}mm, text height {top_text_h:.1f}mm, "
          f"pre-rotation block {top_icon_w:.1f}x{top_icon_w * lockup_k:.1f}mm")

    bottom_icon_h = BOTTOM_ICON_W * MYTHOS_ASPECT
    bottom_text_h = BOTTOM_ICON_W * text_aspect

    base = import_stl(INPUT_STL)
    apply_transform(base)
    base.name = "dice_tray_base"
    prev_vol = mesh_volume(base)

    # Top pocket: cut down INTO the floor from the top surface (z=FLOOR_Z1),
    # overshoot pokes UP through that face into open air, never toward the
    # membrane. Rotated 90 degrees to run along the basin's long axis.
    top_cutter = build_logo_lockup(
        contours, top_icon_w, top_icon_h, top_text_h,
        FLOOR_Z1 - POCKET_DEPTH, POCKET_DEPTH + CUT_POKE, "dice_tray_top_cutter",
    )
    place_object(top_cutter, TOP_CENTER_X, TOP_CENTER_Y, mirror=False, rotate90=True)
    apply_boolean(base, top_cutter, 'DIFFERENCE')

    # Bottom pocket: cut up into the floor from the bottom surface
    # (z=FLOOR_Z0), overshoot pokes DOWN through that face. Mirrored so it
    # reads correct from underneath.
    bottom_cutter = build_logo_lockup(
        contours, BOTTOM_ICON_W, bottom_icon_h, bottom_text_h,
        FLOOR_Z0 - CUT_POKE, POCKET_DEPTH + CUT_POKE, "dice_tray_bottom_cutter",
    )
    place_object(bottom_cutter, BOTTOM_CENTER_X, BOTTOM_CENTER_Y, mirror=True, rotate90=False)
    apply_boolean(base, bottom_cutter, 'DIFFERENCE')

    vol = mesh_volume(base)
    assert 0.0 < vol < prev_vol, (
        f"dice_tray: pocket cuts did not remove a sane amount of material "
        f"({prev_vol:.1f} -> {vol:.1f}mm3) - likely EXACT-solver corruption."
    )
    base_nm = nonmanifold_fraction(base)
    print(f"dice_tray_base: volume={vol:.1f}mm3 (non-manifold {base_nm:.4f})")

    top_insert = build_logo_lockup(
        contours, top_icon_w, top_icon_h, top_text_h,
        FLOOR_Z1 - POCKET_DEPTH, POCKET_DEPTH, "dice_tray_top_insert",
    )
    place_object(top_insert, TOP_CENTER_X, TOP_CENTER_Y, mirror=False, rotate90=True)

    bottom_insert = build_logo_lockup(
        contours, BOTTOM_ICON_W, bottom_icon_h, bottom_text_h,
        FLOOR_Z0, POCKET_DEPTH, "dice_tray_bottom_insert",
    )
    place_object(bottom_insert, BOTTOM_CENTER_X, BOTTOM_CENTER_Y, mirror=True, rotate90=False)

    for insert, label in ((top_insert, "top"), (bottom_insert, "bottom")):
        v = mesh_volume(insert)
        assert v > 0.0, f"dice_tray_{label}_insert: zero/negative volume"
        print(f"dice_tray_{label}_insert: volume={v:.1f}mm3 (non-manifold {nonmanifold_fraction(insert):.4f})")

    apply_color(base, "base_white", BASE_COLOR)
    apply_color(top_insert, "inlay_green", INLAY_COLOR)
    apply_color(bottom_insert, "inlay_green", INLAY_COLOR)

    if RENDER_IMAGES:
        render_face("dice_tray_top", from_below=False)
        render_face("dice_tray_bottom", from_below=True)

    if EXPORT_STL:
        export_stl(base, "dice_tray_base.stl")
        export_stl(top_insert, "dice_tray_top_insert.stl")
        export_stl(bottom_insert, "dice_tray_bottom_insert.stl")
    if EXPORT_3MF:
        export_project_3mf(
            [(base, "base", BASE_EXTRUDER_SLOT),
             (top_insert, "top_insert", INLAY_EXTRUDER_SLOT),
             (bottom_insert, "bottom_insert", INLAY_EXTRUDER_SLOT)],
            os.path.join(EXPORT_DIR, "dice_tray_anycubic.3mf"))


if __name__ == "__main__":
    main()
