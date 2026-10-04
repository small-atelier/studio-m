"""
Mythos logo, recessed into both faces of the castle-style dice tray's
basin floor (Blender bpy) - same two-pocket recess+insert technique as
build_dice_tray.py in this same folder (that file's own docstring has
the full reasoning: two independent 1mm pockets with a solid membrane
between them, mirrored contour on the underside, everything meant as one
combined multi-material print). Duplicated rather than imported, same as
every other project script in this repo - each post publishes ONE
self-contained file, no second module to fetch alongside it.

The input STL (input/dice-tower/castle_style_dice_tray.stl) was authored
with Y as the up axis, not Z (bottom face at y=-10, basin floor at
y=-2, top rim at y=10 - found by the same horizontal-face-area scan used
on the plain tray, just checking all three axes instead of assuming Z).
First real step here is reorienting it to this project's Z-up
convention (a plain +90 degree rotation about X, y->-z/z->y - proper,
not a mirror, so no normals fix needed) - after that, every downstream
helper is identical to the plain tray's.

Basin floor is a comfortable 8mm here (bottom -10 to floor -2), nearly
square (150 x 150mm interior, 180 x 180mm outer footprint) rather than
the plain tray's long narrow one - so unlike the top pocket there,
rotating the lockup 90 degrees buys nothing (a square's available width
and height budgets are equal either way), and both top and bottom pockets
end up centered on the same point (0, -10) since the basin and the outer
footprint happen to share a center here.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_castle_tray.py
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
INPUT_STL = os.path.join(REPO_ROOT, "input", "dice-tower", "castle_style_dice_tray.stl")

MYTHOS_CONTOURS_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "card-stand", "logo_contours_v5.json"))
MYTHOS_ASPECT = 376.0 / 720.0  # h/w, 720x376 source - width is the controlling dimension

LOGO_TEXT = "MYTHOS"
MYTHOS_FONT_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "card-stand", "BaskervilleBold.ttf"))
TEXT_SPACING = 1.1
GAP_FRAC = 0.15

# Basin (top pocket site) is 150 x 150mm interior, centered at (0, -10) -
# ~15mm margin each side. Outer footprint (bottom pocket site) is 180 x
# 180mm, also centered at (0, -10) here (coincidence of this particular
# mesh, not assumed in general) - ~15mm margin off the outer edge.
TOP_BUDGET = 120.0
BOTTOM_BUDGET = 150.0
CENTER_X = 0.0
CENTER_Y = -10.0

FLOOR_Z0 = -10.0
FLOOR_Z1 = -2.0
POCKET_DEPTH = 1.0  # each face - 8mm floor here leaves a generous 6mm membrane
CUT_POKE = 0.3

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
# GENERIC HELPERS (ported from build_dice_tray.py in this same folder)
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
    return [(-x, y) for x, y in points]


def place_object(obj, center_x, center_y, mirror=False, rotate90=False):
    """See build_dice_tray.py's copy of this for the full reasoning on
    reverse_faces vs recalc_face_normals - mirroring is orientation-
    reversing and needs winding flipped explicitly; rotation is
    orientation-preserving and needs no normal fix at all."""
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
# MYTHOS ICON + WORDMARK
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
        v.co.z += z0 + thickness / 2.0

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def build_logo_lockup(contours, icon_w, icon_h, text_h, z0, thickness, name_prefix):
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
    lockup_k = MYTHOS_ASPECT * (1.0 + GAP_FRAC) + text_aspect  # block height / width

    # Basin (top) and outer footprint (bottom) are both roughly square here,
    # so - unlike the plain tray's top pocket - rotating the lockup 90
    # degrees wouldn't gain anything: a square's width and height budgets
    # are already equal either way. Width is still the binding dimension
    # since the lockup itself is wider than it is tall (lockup_k < 1).
    top_icon_w = min(TOP_BUDGET, TOP_BUDGET / lockup_k)
    top_icon_h = top_icon_w * MYTHOS_ASPECT
    top_text_h = top_icon_w * text_aspect

    bottom_icon_w = min(BOTTOM_BUDGET, BOTTOM_BUDGET / lockup_k)
    bottom_icon_h = bottom_icon_w * MYTHOS_ASPECT
    bottom_text_h = bottom_icon_w * text_aspect

    print(f"castle top lockup: icon {top_icon_w:.1f}x{top_icon_h:.1f}mm, text height {top_text_h:.1f}mm")
    print(f"castle bottom lockup: icon {bottom_icon_w:.1f}x{bottom_icon_h:.1f}mm, text height {bottom_text_h:.1f}mm")

    base = import_stl(INPUT_STL)
    # Source file was authored with Y as up, not Z - proper +90deg rotation
    # about X (y -> -z, z -> y), verified against the file's own horizontal-
    # face-area scan before writing this script. Determinant +1, no mirror,
    # no normals fix needed.
    base.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    apply_transform(base)
    base.name = "castle_tray_base"
    prev_vol = mesh_volume(base)

    top_cutter = build_logo_lockup(
        contours, top_icon_w, top_icon_h, top_text_h,
        FLOOR_Z1 - POCKET_DEPTH, POCKET_DEPTH + CUT_POKE, "castle_tray_top_cutter",
    )
    place_object(top_cutter, CENTER_X, CENTER_Y, mirror=False, rotate90=False)
    apply_boolean(base, top_cutter, 'DIFFERENCE')

    bottom_cutter = build_logo_lockup(
        contours, bottom_icon_w, bottom_icon_h, bottom_text_h,
        FLOOR_Z0 - CUT_POKE, POCKET_DEPTH + CUT_POKE, "castle_tray_bottom_cutter",
    )
    place_object(bottom_cutter, CENTER_X, CENTER_Y, mirror=True, rotate90=False)
    apply_boolean(base, bottom_cutter, 'DIFFERENCE')

    vol = mesh_volume(base)
    assert 0.0 < vol < prev_vol, (
        f"castle_tray: pocket cuts did not remove a sane amount of material "
        f"({prev_vol:.1f} -> {vol:.1f}mm3) - likely EXACT-solver corruption."
    )
    print(f"castle_tray_base: volume={vol:.1f}mm3 (non-manifold {nonmanifold_fraction(base):.4f})")

    top_insert = build_logo_lockup(
        contours, top_icon_w, top_icon_h, top_text_h,
        FLOOR_Z1 - POCKET_DEPTH, POCKET_DEPTH, "castle_tray_top_insert",
    )
    place_object(top_insert, CENTER_X, CENTER_Y, mirror=False, rotate90=False)

    bottom_insert = build_logo_lockup(
        contours, bottom_icon_w, bottom_icon_h, bottom_text_h,
        FLOOR_Z0, POCKET_DEPTH, "castle_tray_bottom_insert",
    )
    place_object(bottom_insert, CENTER_X, CENTER_Y, mirror=True, rotate90=False)

    for insert, label in ((top_insert, "top"), (bottom_insert, "bottom")):
        v = mesh_volume(insert)
        assert v > 0.0, f"castle_tray_{label}_insert: zero/negative volume"
        print(f"castle_tray_{label}_insert: volume={v:.1f}mm3 (non-manifold {nonmanifold_fraction(insert):.4f})")

    apply_color(base, "base_white", BASE_COLOR)
    apply_color(top_insert, "inlay_green", INLAY_COLOR)
    apply_color(bottom_insert, "inlay_green", INLAY_COLOR)

    if RENDER_IMAGES:
        render_face("castle_tray_top", from_below=False)
        render_face("castle_tray_bottom", from_below=True)

    if EXPORT_STL:
        export_stl(base, "castle_tray_base.stl")
        export_stl(top_insert, "castle_tray_top_insert.stl")
        export_stl(bottom_insert, "castle_tray_bottom_insert.stl")
    if EXPORT_3MF:
        export_project_3mf(
            [(base, "base", BASE_EXTRUDER_SLOT),
             (top_insert, "top_insert", INLAY_EXTRUDER_SLOT),
             (bottom_insert, "bottom_insert", INLAY_EXTRUDER_SLOT)],
            os.path.join(EXPORT_DIR, "castle_tray_anycubic.3mf"))


if __name__ == "__main__":
    main()
