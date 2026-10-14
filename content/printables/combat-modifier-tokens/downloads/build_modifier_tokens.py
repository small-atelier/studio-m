"""
Generic combat-modifier tokens (Blender bpy) - not army/faction specific,
usable in both 40k and AoS. Each token is a FLIP token: front and back
show opposite states of the same stat (e.g. "+1"/"-1"), not the
mirrored-duplicate content used on the Hashut army tokens
(blender/tokens/build_tokens.py) - same double-sided-mirroring math
underneath (see module docstring there), just fed different text per
side instead of the same text twice.

Shape IS part of the category identity: each stat gets its own token
silhouette (round/shield/drop/skull/arrow/square/sword/hexagon) so
tokens are identifiable by touch/shape, not just by reading them off the
table - but every numeric token still carries the FULL phrase ("TO HIT
+1", "REND -1", "DAMAGE +1") rather than a bare value, matching real
40k wording (roll modifiers get "to" - "+1 to Hit"; characteristic
modifiers don't - "Rend -1").

Same recess+insert multi-material build as the Hashut tokens (0.6mm
flush pockets, base + inlay as separate parts, same font/EXACT-solver
fixes - letter-spacing for touching glyphs, remove_doubles for FONT-
curve-conversion artifacts, see feedback_blender_boolean_fragility
memory), plus a border ring like the Hashut tokens have - approximated
as a scaled-down copy of each shape (build_border_solid), which is only
an exact constant-width offset for the regular shapes (circle/square/
hexagon); on the concave hand-drawn ones (shield/drop/arrow/sword) it's
visually close enough at this size, not a true offset.

Run (all 8 tokens):
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_modifier_tokens.py

Run one token only:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_modifier_tokens.py -- --only rend
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
# CLI ARGS
# ============================================================


def _parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only, render = None, True
    i = 0
    while i < len(argv):
        if argv[i] == "--only":
            only = argv[i + 1]; i += 2
        elif argv[i] == "--no-render":
            render = False; i += 1
        else:
            i += 1
    return only, render


ONLY, RENDER_IMAGES = _parse_args()

# ============================================================
# CONFIG (all mm)
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEXT_FONT_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, "ArialBlack.ttf"))
# Switched from BaskervilleBold (see score-tracker project) - a serif display font's thin
# strokes/serifs don't resolve on an FDM nozzle at this scale, even at a big nominal size.
# Arial Black's uniform heavy strokes print far crisper for small embossed/inlaid labels -
# confirmed "weak"-looking on this project's own first multi-material test print.

# Bonus token: the Mythos card-stand logo (sun/mountain/moon), reusing its already-traced
# contours rather than re-tracing - see blender/card-stand/extract_logo_contours_v5.py for
# how logo_contours_v5.json was made (icon-only, no wordmark - that crop already happened
# there). 720x376 source, so width is the controlling dimension, not height.
MYTHOS_CONTOURS_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "card-stand", "logo_contours_v5.json"))
MYTHOS_ASPECT = 376.0 / 720.0
MYTHOS_ICON_W = 21.0
# Mythos wordmark keeps its own brand font (matching the card-stand project) rather than
# the global TEXT_FONT_PATH - same choice made in the score-tracker's Mythos badge variant.
MYTHOS_FONT_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "card-stand", "BaskervilleBold.ttf"))

EXPORT_DIR = os.path.join(SCRIPT_DIR, "output")
EXPORT_STL = True
EXPORT_3MF = True
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1200, 1200)

PLATE_T = 3.0
INSERT_DEPTH = 0.6
POCKET_POKE = 0.4
BEVEL_W = 0.5

BOLD_OFFSET = 0.0
TEXT_SPACING = 1.1   # see feedback_blender_boolean_fragility memory - touching glyph pairs at
                      # small sizes corrupt the EXACT solver; this is the fix, ported as-is

BASE_COLOR = (1.0, 1.0, 1.0, 1.0)
INLAY_COLOR = (0.06, 0.45, 0.12, 1.0)
BASE_EXTRUDER_SLOT = 1
INLAY_EXTRUDER_SLOT = 2

HOLE_OVERSHOOT = 0.5   # overshoot for the border ring's own inner cutter - see build_border_solid

# Border ring is back (v2 of this set) - approximated as a uniformly-SCALED-DOWN copy of the
# same shape, not a true constant-width offset. That's exact for the regular shapes (circle/
# square/hexagon - scaling from center IS a true offset for those), and only approximate for
# the hand-drawn concave ones (shield/drop/bolt/arrow/sword) - a scaled copy of a concave
# outline is narrower at the "spiky" bits and wider at the "round" bits, but at this token
# size it reads fine as a border; a true polygon offset isn't worth the complexity here.
BORDER_OUTER_FRAC = 0.90   # ring's outer edge, as a fraction of the plate's own full size
BORDER_INNER_FRAC = 0.78   # ring's inner edge - the gap between these two is the ring width

# ============================================================
# GENERIC HELPERS (ported from blender/tokens/build_tokens.py - see that
# file's own comments for why each fix exists; not re-derived here)
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


def _extrude_profile(points, offset, thickness, name):
    """Build a flat face from a closed (x, z) point loop and extrude it
    along Y. `offset` is the fixed Y of the starting face."""
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


def mirror_mesh_x(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for v in bm.verts:
        v.co.x = -v.co.x
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def mirror_points_x(points):
    """Flip a closed (x, z) point loop's X coordinate - for a traced icon's
    back-face copy, same reasoning as mirror_mesh_x for text."""
    return [(-x, z) for x, z in points]


def dedupe_closed_loop(points, tol=1e-9):
    """Traced contours (skimage find_contours) can come back as closed
    rings with the first and last point identical - a degenerate
    zero-length edge that corrupts the extruded solid's topology if left
    in. See blender/tokens/build_tokens.py's own version of this for the
    full story (~50% non-manifold edges traced back to exactly this)."""
    if len(points) > 1:
        x0, y0 = points[0]
        x1, y1 = points[-1]
        if abs(x0 - x1) < tol and abs(y0 - y1) < tol:
            return points[:-1]
    return points


def load_contours(path):
    with open(path) as f:
        return json.load(f)


def build_icon_solid(contours, icon_w, icon_h, center_x, top_z, mirror, name_prefix, poke=0.0):
    """Traced-icon solid (ported from blender/tokens/build_tokens.py) -
    built as its own free-standing composite (per-contour chained union/
    difference, holes already cut) before ever touching the shell; see
    that file's own module docstring for why (long chains directly onto
    a growing shell corrupt the EXACT solver)."""
    icon_x0 = center_x - icon_w / 2.0
    icon_z0 = top_z - icon_h
    offset, thickness = face_span(mirror, INSERT_DEPTH, poke)

    outer_pts, hole_pts = [], []
    for c in contours:
        pts = [(icon_x0 + u * icon_w, icon_z0 + v * icon_h) for u, v in c["points"]]
        pts = dedupe_closed_loop(pts)
        if mirror:
            pts = mirror_points_x(pts)
        (hole_pts if c["hole"] else outer_pts).append(pts)
    assert outer_pts, f"{name_prefix}: traced icon has no outer contours"

    solid = _extrude_profile(outer_pts[0], offset, thickness, f"{name_prefix}_0")
    for i, pts in enumerate(outer_pts[1:], start=1):
        union_onto(solid, _extrude_profile(pts, offset, thickness, f"{name_prefix}_{i}"))
    for i, pts in enumerate(hole_pts):
        cutter = _extrude_profile(pts, offset - HOLE_OVERSHOOT,
                                   thickness + 2 * HOLE_OVERSHOOT, f"{name_prefix}_hole_{i}")
        apply_boolean(solid, cutter, 'DIFFERENCE')

    return solid, icon_z0


def face_span(mirror, depth, poke):
    """(offset, thickness) for a solid on the given face - flush (poke=0,
    a real insert) or an oversized pocket cutter (poke>0)."""
    if mirror:
        return (PLATE_T - depth, depth + poke)
    return (-poke, depth + poke)


def _build_flat_text_mesh(text, size, thickness, font_path=TEXT_FONT_PATH):
    font = bpy.data.fonts.load(font_path)
    curve_data = bpy.data.curves.new(f"{text}_curve", type='FONT')
    curve_data.body = text
    curve_data.font = font
    curve_data.size = size
    curve_data.align_x = 'CENTER'
    curve_data.align_y = 'CENTER'
    curve_data.offset = BOLD_OFFSET
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


def build_text_solid(text, size, center_x, top_z, mirror, poke=0.0, font_path=TEXT_FONT_PATH):
    offset, thickness = face_span(mirror, INSERT_DEPTH, poke)
    obj = _build_flat_text_mesh(text, size, thickness, font_path)

    local_top_y = max(v.co.y for v in obj.data.vertices)
    local_bottom_y = min(v.co.y for v in obj.data.vertices)
    text_h = local_top_y - local_bottom_y
    text_w = max(v.co.x for v in obj.data.vertices) - min(v.co.x for v in obj.data.vertices)

    if mirror:
        mirror_mesh_x(obj)

    mid_y = offset + thickness / 2.0
    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    obj.location = (center_x, mid_y, top_z - local_top_y)
    apply_transform(obj)

    return obj, top_z - text_h, text_w


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


def reorient_for_print(obj):
    """Y (thickness) -> Z (build direction, [0, PLATE_T]); Z (shape's own
    in-plane vertical) -> Y. See build_tokens.py's version for the full
    derivation (proper rotation, determinant +1, not a mirror)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for v in bm.verts:
        x, y, z = v.co
        v.co = (x, z, PLATE_T - y)
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
    blender/tokens/build_tokens.py's own export_project_3mf for the full
    story (that slicer ignores the standard 3MF color hint entirely).
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


def setup_camera_and_light(center, distance, ortho_scale, from_back=False):
    sign = 1.0 if from_back else -1.0
    cam_data = bpy.data.cameras.new("RenderCam")
    cam_data.type = 'ORTHO'
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
    light.location = center + mathutils.Vector((distance * 0.3, sign * distance * 1.5, distance * 0.6))
    direction = center - light.location
    light.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    return cam


def render_face(name, from_back=False):
    center, size = compute_scene_bounds()
    distance = size * 1.2
    setup_camera_and_light(center, distance, size * 1.15, from_back=from_back)
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = RENDER_RESOLUTION
    scene.render.filepath = os.path.join(RENDER_DIR, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {scene.render.filepath}")


def export_token(name, base, inlay):
    base_vol, inlay_vol = mesh_volume(base), mesh_volume(inlay)
    base_nm, inlay_nm = nonmanifold_fraction(base), nonmanifold_fraction(inlay)
    print(f"{name}: base volume={base_vol:.1f}mm3 (non-manifold {base_nm:.4f})  "
          f"inlay volume={inlay_vol:.1f}mm3 (non-manifold {inlay_nm:.4f})")
    assert base_vol > 0.0, f"{name}: base has zero/negative volume"
    assert inlay_vol > 0.0, f"{name}: inlay has zero/negative volume"

    apply_color(base, "base_white", BASE_COLOR)
    apply_color(inlay, "inlay_green", INLAY_COLOR)
    if RENDER_IMAGES:
        render_face(f"{name}_front", from_back=False)
        render_face(f"{name}_back", from_back=True)

    reorient_for_print(base)
    reorient_for_print(inlay)

    if EXPORT_STL:
        export_stl(base, f"{name}_base.stl")
        export_stl(inlay, f"{name}_inlay.stl")
    if EXPORT_3MF:
        export_project_3mf(
            [(base, "base", BASE_EXTRUDER_SLOT), (inlay, "inlay", INLAY_EXTRUDER_SLOT)],
            os.path.join(EXPORT_DIR, f"{name}_anycubic.3mf"))


# ============================================================
# SHAPES - each takes an overall size (its dominant dimension) and
# returns a closed (x, z) point loop centered on the origin. Hand-drawn,
# not traced - validated for self-intersection with shapely before ever
# reaching Blender (see the design notes this script came out of).
# ============================================================


def circle_points(diameter, n=48):
    r = diameter / 2.0
    return [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def square_points(size):
    h = size / 2.0
    return [(-h, -h), (h, -h), (h, h), (-h, h)]


def hex_points(flat_to_flat):
    r = flat_to_flat / math.sqrt(3.0)
    return [(r * math.cos(math.radians(90.0 + 60.0 * k)), r * math.sin(math.radians(90.0 + 60.0 * k)))
            for k in range(6)]


def shield_points(height, n_arc=8):
    """Wave top (v3) - left/right corners pulled up, a spike in the
    middle, with a valley dipping down between each corner and the
    spike - rather than a single smooth arc. Valley depth kept shallow
    (h_valley close to h_corner) on purpose - a first pass with a deep
    valley (down near h_spike's own base) ate into the flat content band
    from above; this one leaves the full-width flat middle (z from -3 to
    +6 at height=30) intact. Bottom is a smooth rounded arc (v4) instead
    of the v2/v3 sharp triangular point - flowing curves, not angles."""
    r = 0.5
    h_corner, h_spike, h_valley = 0.35, 0.5, 0.30
    square_bottom, tip = -0.15, -0.95
    arc_depth = square_bottom - tip
    top = [
        (-r, h_corner), (-0.22, h_valley), (0.0, h_spike), (0.22, h_valley), (r, h_corner),
    ]
    bottom = []
    for i in range(n_arc + 1):
        a = -math.pi * i / n_arc
        bottom.append((r * math.cos(a), square_bottom + arc_depth * math.sin(a)))
    pts = top + bottom
    scale = height / (h_spike - tip)
    return [(x * scale, y * scale) for x, y in pts]


def teardrop_points(height, n=16):
    pts, r, cy = [], 0.5, 0.1
    for i in range(n + 1):
        a = math.pi - (math.pi * i / n)
        pts.append((r * math.cos(a), cy + r * math.sin(a)))
    pts.append((0.0, -0.7))
    scale = height / 1.3
    return [(x * scale, y * scale) for x, y in pts]


def skull_points(height, n_arc=14):
    """Replaced the lightning bolt for Battle Shock - a diagonal zigzag
    with ~8mm-wide usable strokes couldn't hold "BATTLE SHOCK TEST"/
    "BATTLE SHOCKED" at any legible size, and needed its own separate
    border-cut step to avoid corrupting on its concave notch (see
    build_modifier_token's own comment). More literally a skull now, and
    more stylistic - a circle for the cranium with a narrower rectangle
    dropped from its lower arc for the jaw/teeth block, rather than the
    first version's straight-edged tombstone silhouette. Content still
    sits entirely in the cranium (measured ~21-23mm wide there); the jaw
    rectangle is decorative, not sized for text."""
    r, cy, rw, rh = 0.5, 0.25, 0.6, 0.35
    attach_y = cy - math.sqrt(r * r - (rw / 2) ** 2)
    rect_bottom = attach_y - rh
    ang_right = math.atan2(attach_y - cy, rw / 2)
    ang_left = math.atan2(attach_y - cy, -rw / 2)
    start = ang_right
    end = ang_left if ang_left > start else ang_left + 2 * math.pi
    pts = []
    for i in range(n_arc + 1):
        a = start + (end - start) * i / n_arc
        pts.append((r * math.cos(a), cy + r * math.sin(a)))
    pts.append((-rw / 2, rect_bottom))
    pts.append((rw / 2, rect_bottom))
    scale = height / (cy + r - rect_bottom)
    return [(x * scale, y * scale) for x, y in pts]


def arrow_points(width):
    norm = [(-0.5, 0.2), (0.1, 0.2), (0.1, 0.5), (0.5, 0.0), (0.1, -0.5), (0.1, -0.2), (-0.5, -0.2)]
    return [(x * width, y * width) for x, y in norm]


def sword_points(length):
    """Lying horizontal (blade toward +x, pommel toward -x) rather than
    standing upright - a 90 degree rotation of the same outline (still
    built in its own natural upright coordinates below, then swapped)
    gives a much bigger flat rectangle to hold text than the same shape
    ever had standing up. v2: the long rectangle (0.25 to -0.45, half-
    width 0.32) IS the blade now, not the handle/pommel - anatomically
    that's the part that should be long, not the short bit past the
    crossguard. The short bit (0.55 to 1.0) is the pommel, and is now a
    thin rectangle (half-width 0.12) instead of tapering to a point -
    no part of this sword has a sharp point any more, by request. v3:
    the small corner chamfer moved from the pommel's outer end to the
    blade's outer end instead - pommel end is a plain flat rectangle
    again. v4: blade chamfer enlarged (0.32 -> 0.16 at its tip, starting
    the taper from 0.25 instead of 0.32 down the shaft)."""
    norm = [
        (0.12, 1.0), (0.12, 0.55),
        (0.5, 0.45), (0.5, 0.32),
        (0.32, 0.25), (0.32, -0.35), (0.16, -0.45),
        (-0.16, -0.45), (-0.32, -0.35), (-0.32, 0.25),
        (-0.5, 0.32), (-0.5, 0.45), (-0.12, 0.55), (-0.12, 1.0),
    ]
    scale = length / 1.45
    scaled = [(x * scale, y * scale) for x, y in norm]
    return [(y, x) for x, y in scaled]   # rotate 90 degrees


def build_shape_shell(points, name):
    shell = _extrude_profile(points, 0.0, PLATE_T, name)
    apply_bevel(shell, BEVEL_W)
    return shell


def build_border_solid(shape_fn, size, mirror, name_prefix, poke=0.0):
    """Border ring as a scaled-down copy of the same shape - see the
    BORDER_OUTER_FRAC/BORDER_INNER_FRAC comment for why this is only an
    approximate constant-width offset on the concave hand-drawn shapes.
    Good enough for shield/drop/skull; NOT good enough for the sword or
    arrow (see build_border_solid_fixed) - their stepped guard/shaft-head
    junctions need a real offset, not a scaled copy, or the border
    visibly stops following the outline right at the step."""
    offset, thickness = face_span(mirror, INSERT_DEPTH, poke)
    outer_pts = shape_fn(size * BORDER_OUTER_FRAC)
    inner_pts = shape_fn(size * BORDER_INNER_FRAC)
    solid = _extrude_profile(outer_pts, offset, thickness, f"{name_prefix}_outer")
    cutter = _extrude_profile(inner_pts, offset - HOLE_OVERSHOOT,
                               thickness + 2 * HOLE_OVERSHOOT, f"{name_prefix}_inner_cut")
    apply_boolean(solid, cutter, 'DIFFERENCE')
    return solid


def build_border_solid_fixed(outer_pts, inner_pts, mirror, name_prefix, poke=0.0):
    """Border ring from explicit (outer, inner) point lists - a real
    constant-width polygon offset (computed once via shapely.buffer,
    system python3, round joins so concave corners like a crossguard's
    inner step don't spike) rather than a scaled-down copy. Used for the
    sword and arrow, whose stepped outlines a uniform scale visibly fails
    to track (the border stops hugging the shape right at the step)."""
    offset, thickness = face_span(mirror, INSERT_DEPTH, poke)
    solid = _extrude_profile(outer_pts, offset, thickness, f"{name_prefix}_outer")
    cutter = _extrude_profile(inner_pts, offset - HOLE_OVERSHOOT,
                               thickness + 2 * HOLE_OVERSHOOT, f"{name_prefix}_inner_cut")
    apply_boolean(solid, cutter, 'DIFFERENCE')
    return solid


# Precomputed real polygon offsets (shapely.buffer, round joins) for the sword and arrow -
# see build_border_solid_fixed's docstring for why these two need this instead of the
# generic scaled-copy border. Computed at their actual build size (30mm) directly. Arrow
# uses the same 1.5mm/3.3mm outer/inner inset as the scaled-copy shapes; the sword needed a
# thinner ring (0.8mm/1.7mm) instead - a uniform mm offset eats the SAME amount off every
# edge, and the sword's short axis (20.7mm) can't afford to lose as much to the border as
# its long axis (30mm) can - at 1.5/3.3 the blade's own hollow shrank to ~6.6mm tall, not
# enough room left for "DAMAGE" + "+1" (which is why the border seemed to "swallow" the text).
SWORD_BORDER_OUTER = [[19.89, 1.683], [19.89, -1.683], [11.379, -1.683], [11.23, -1.697], [11.086, -1.738], [10.952, -1.806], [10.834, -1.898], [10.734, -2.01], [10.657, -2.138], [10.606, -2.279], [8.694, -9.545], [7.168, -9.545], [5.918, -6.331], [5.846, -6.188], [5.746, -6.063], [5.624, -5.96], [5.484, -5.884], [5.331, -5.837], [5.172, -5.821], [-6.798, -5.821], [-8.51, -3.081], [-8.51, 3.081], [-6.798, 5.821], [5.172, 5.821], [5.331, 5.837], [5.484, 5.884], [5.624, 5.96], [5.746, 6.063], [5.846, 6.188], [5.918, 6.331], [7.168, 9.545], [8.694, 9.545], [10.606, 2.279], [10.657, 2.138], [10.734, 2.01], [10.834, 1.898], [10.952, 1.806], [11.086, 1.738], [11.23, 1.697], [11.379, 1.683]]
SWORD_BORDER_INNER = [[18.99, 0.783], [18.99, -0.783], [11.379, -0.783], [11.062, -0.813], [10.756, -0.901], [10.472, -1.045], [10.22, -1.24], [10.008, -1.478], [9.845, -1.751], [9.735, -2.05], [8.0, -8.645], [7.784, -8.645], [6.757, -6.005], [6.603, -5.702], [6.392, -5.436], [6.132, -5.218], [5.834, -5.055], [5.51, -4.955], [5.172, -4.921], [-6.299, -4.921], [-7.61, -2.823], [-7.61, 2.823], [-6.299, 4.921], [5.172, 4.921], [5.51, 4.955], [5.834, 5.055], [6.132, 5.218], [6.392, 5.436], [6.603, 5.702], [6.757, 6.005], [7.784, 8.645], [8.0, 8.645], [9.735, 2.05], [9.845, 1.751], [10.008, 1.478], [10.22, 1.24], [10.472, 1.045], [10.756, 0.901], [11.062, 0.813], [11.379, 0.783]]
ARROW_BORDER_OUTER = [[-13.5, 4.5], [3.0, 4.5], [3.293, 4.529], [3.574, 4.614], [3.833, 4.753], [4.061, 4.939], [4.247, 5.167], [4.386, 5.426], [4.471, 5.707], [4.5, 6.0], [4.5, 10.724], [13.079, 0.0], [4.5, -10.724], [4.5, -6.0], [4.471, -5.707], [4.386, -5.426], [4.247, -5.167], [4.061, -4.939], [3.833, -4.753], [3.574, -4.614], [3.293, -4.529], [3.0, -4.5], [-13.5, -4.5]]
ARROW_BORDER_INNER = [[-11.7, 2.7], [3.0, 2.7], [3.644, 2.763], [4.263, 2.951], [4.833, 3.256], [5.333, 3.667], [5.744, 4.167], [6.049, 4.737], [6.237, 5.356], [6.264, 5.637], [10.774, 0.0], [6.264, -5.637], [6.237, -5.356], [6.049, -4.737], [5.744, -4.167], [5.333, -3.667], [4.833, -3.256], [4.263, -2.951], [3.644, -2.763], [3.0, -2.7], [-11.7, -2.7]]


# ============================================================
# TOKEN SPECS - one entry per physical flip token. `lines` is a list of
# (text, size) pairs stacked top to bottom, sharing GAP between them;
# front/back each get their own `lines` list (same category label text
# on both, if any - it still gets X-mirrored on the back like everything
# else, see mirror_mesh_x - only the VALUE differs between faces).
# ============================================================

GAP = 1.5


def _lines(*pairs):
    return list(pairs)


TOKENS = [
    {
        # Full-sentence phrasing per stat class: "TO HIT/WOUND/SAVE" for roll modifiers
        # (matches real 40k wording - "+1 to Hit"), plain "REND/ATTACKS/DAMAGE" for
        # characteristic modifiers (no "to" - "Rend -1", not "Rend to -1"). Every numeric
        # token bumped in overall size vs. the first pass - holding a real label plus the
        # border ring (which eats ~22% of the shape - see BORDER_INNER_FRAC) needs more
        # room than the bare "+1"/"-1" some of these shipped with originally.
        "name": "to_hit",
        "shape_fn": circle_points, "shape_size": 30.0,
        "front": _lines(("TO HIT", 4.8), ("+1", 12.3)),
        "back": _lines(("TO HIT", 4.8), ("-1", 12.3)),
        "top_margin": 7.0,
    },
    {
        "name": "to_save",
        "shape_fn": shield_points, "shape_size": 30.0,
        "front": _lines(("TO SAVE", 4.1), ("+1", 11.2)),
        "back": _lines(("TO SAVE", 4.1), ("-1", 11.2)),
        "top_margin": 3.6,
    },
    {
        "name": "to_wound",
        "shape_fn": teardrop_points, "shape_size": 30.0,
        "front": _lines(("TO WOUND", 3.4), ("+1", 10.5)),
        "back": _lines(("TO WOUND", 3.4), ("-1", 10.5)),
        "top_margin": 7.7,
    },
    {
        # Skull, not a lightning bolt (see skull_points docstring for why) - symmetric, so
        # no center_x offset needed like the asymmetric shapes below. Cranium band (z~6-10)
        # measured ~14mm wide inside the border - comfortably holds "BATTLE SHOCK" small;
        # "TEST"/"SHOCKED" sit lower and bigger, matching the "value most prominent" pattern
        # used everywhere else in this set.
        "name": "battle_shock",
        "shape_fn": skull_points, "shape_size": 30.0,
        "front": _lines(("BATTLE SHOCK", 2.6), ("TEST", 6.5)),
        "back": _lines(("BATTLE", 3.4), ("SHOCKED", 3.7)),
        "top_margin": 9.0,
    },
    {
        # Arrow's shaft+head combined footprint is ~28-32mm wide for |z|<6.4 (measured), but
        # the original top_margin=8.0 put the text entirely ABOVE that band, in empty space
        # past the shaft's own top edge - the text built there anyway (nothing stops it) and
        # rendered as a disconnected floating fragment, not a real pocket.
        "name": "strike_order",
        "shape_fn": arrow_points, "shape_size": 30.0,
        "front": _lines(("STRIKE FIRST", 3.45),),
        "back": _lines(("STRIKE LAST", 3.45),),
        "top_margin": 1.25,
        "center_x": -1.5,
        "border_points": (ARROW_BORDER_OUTER, ARROW_BORDER_INNER),
    },
    {
        "name": "rend",
        "shape_fn": square_points, "shape_size": 30.0,
        "front": _lines(("REND", 4.9), ("+1", 12.6)),
        "back": _lines(("REND", 4.9), ("-1", 12.6)),
        "top_margin": 7.1,
    },
    {
        # Swapped shapes with Damage - hexagon has no strong metaphor either way, but reads
        # fine holding "ATTACKS" (7 letters) comfortably across its own wide middle band.
        # shape_size here is flat_to_flat, NOT the hex's own max dimension - a pointy-top
        # hex's point-to-point (vertical) span is flat_to_flat*2/sqrt(3), ~15% bigger, so
        # flat_to_flat has to be set smaller than 30 for the actual bounding box to cap at 30.
        "name": "attacks",
        "shape_fn": hex_points, "shape_size": 25.98,
        "front": _lines(("ATTACKS", 4.2), ("+1", 10.8)),
        "back": _lines(("ATTACKS", 4.2), ("-1", 10.8)),
        "top_margin": 6.3,
    },
    {
        # Swapped shapes with Attacks - a sword dealing damage is at least as fair a metaphor
        # as a sword swinging (attacking). Guard widened a second time (see sword_points) -
        # this shape now has to hold the longest label ("DAMAGE") of any of the numeric
        # tokens, not just a bare value like the first pass's sword did.
        "name": "damage",
        "shape_fn": sword_points, "shape_size": 30.0,
        "front": _lines(("DAMAGE", 3.7), ("+1", 9.8)),
        "back": _lines(("DAMAGE", 3.7), ("-1", 9.8)),
        "top_margin": 5.4,
        "center_x": 0.5,
        "border_points": (SWORD_BORDER_OUTER, SWORD_BORDER_INNER),
    },
]


def build_modifier_token(spec):
    shape_fn, size = spec["shape_fn"], spec["shape_size"]
    shell = build_shape_shell(shape_fn(size), f"{spec['name']}_shell")
    center_x = spec.get("center_x", 0.0)

    # Border cut FIRST, as its OWN separate difference - not joined into the same combined
    # cutter as the text pockets. Found the hard way on battle_shock: the border ring (itself
    # already a hollow shape from its own internal difference) is clean alone, the text
    # cutter is clean alone, but joining them into one mesh before a single boolean corrupted
    # the shell to 0 volume - the lightning bolt's concave zigzag notch is exactly the kind of
    # near-degenerate geometry the EXACT solver chokes on once two different fragile pieces
    # get combined (see feedback_blender_boolean_fragility memory). Two short sequential
    # differences instead of one combined one - same fix, applied to every shape here even
    # though only the concave ones (bolt/arrow/sword) actually needed it, for consistency.
    border_pts = spec.get("border_points")
    border_inserts, border_cutters = [], []
    for mirror, tag in ((False, "front"), (True, "back")):
        if border_pts:
            outer_pts, inner_pts = border_pts
            border_inserts.append(build_border_solid_fixed(outer_pts, inner_pts, mirror, f"{spec['name']}_border_{tag}_ins", poke=0.0))
            border_cutters.append(build_border_solid_fixed(outer_pts, inner_pts, mirror, f"{spec['name']}_border_{tag}_cut", poke=POCKET_POKE))
        else:
            border_inserts.append(build_border_solid(shape_fn, size, mirror, f"{spec['name']}_border_{tag}_ins", poke=0.0))
            border_cutters.append(build_border_solid(shape_fn, size, mirror, f"{spec['name']}_border_{tag}_cut", poke=POCKET_POKE))
    prev_vol = mesh_volume(shell)
    apply_boolean(shell, join_objects(border_cutters, f"{spec['name']}_border_cutters"), 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_vol, f"{spec['name']}: border cut corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"

    inserts, cutters = list(border_inserts), []
    for mirror, tag, lines in ((False, "front", spec["front"]), (True, "back", spec["back"])):
        top_z = spec["top_margin"]
        for i, (text, size_pt) in enumerate(lines):
            for poke, bucket in ((0.0, inserts), (POCKET_POKE, cutters)):
                solid, bottom_z, width = build_text_solid(text, size_pt, center_x, top_z, mirror, poke=poke)
                bucket.append(solid)
            top_z = bottom_z - GAP

    return carve_and_collect_inlay(shell, inserts, cutters, spec["name"])


def build_mythos_token():
    """Bonus token, not part of the combat-modifier set - the Mythos
    card-stand logo (sun/mountain/moon) on a plain square with a border,
    same icon on both faces (mirrored on the back like everything else
    here) rather than a flip token, since there's no state to flip."""
    size = 30.0
    shell = build_shape_shell(square_points(size), "mythos_shell")

    border_inserts, border_cutters = [], []
    for mirror, tag in ((False, "front"), (True, "back")):
        border_inserts.append(build_border_solid(square_points, size, mirror, f"mythos_border_{tag}_ins", poke=0.0))
        border_cutters.append(build_border_solid(square_points, size, mirror, f"mythos_border_{tag}_cut", poke=POCKET_POKE))
    prev_vol = mesh_volume(shell)
    apply_boolean(shell, join_objects(border_cutters, "mythos_border_cutters"), 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_vol, f"mythos: border cut corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"

    contours = load_contours(MYTHOS_CONTOURS_PATH)
    icon_h = MYTHOS_ICON_W * MYTHOS_ASPECT
    text_size = 4.0
    text_h_est = text_size * 0.7   # rough cap-height estimate, just to center the icon+text
                                    # block as a whole - build_text_solid returns the real
                                    # bottom_z afterward, this estimate only sets top_z
    total_h = icon_h + GAP + text_h_est
    top_z = total_h / 2.0

    inserts, cutters = list(border_inserts), []
    for mirror, tag in ((False, "front"), (True, "back")):
        icon_ins, icon_bottom_z = build_icon_solid(contours, MYTHOS_ICON_W, icon_h, 0.0, top_z, mirror,
                                                     f"mythos_icon_{tag}_ins", poke=0.0)
        icon_cut, _ = build_icon_solid(contours, MYTHOS_ICON_W, icon_h, 0.0, top_z, mirror,
                                        f"mythos_icon_{tag}_cut", poke=POCKET_POKE)
        inserts += [icon_ins]
        cutters += [icon_cut]

        text_top_z = icon_bottom_z - GAP
        for poke, bucket in ((0.0, inserts), (POCKET_POKE, cutters)):
            text_solid, _, _ = build_text_solid("MYTHOS", text_size, 0.0, text_top_z, mirror, poke=poke,
                                                 font_path=MYTHOS_FONT_PATH)
            bucket.append(text_solid)

    return carve_and_collect_inlay(shell, inserts, cutters, "mythos")


# ============================================================
# MAIN
# ============================================================


def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    if RENDER_IMAGES:
        os.makedirs(RENDER_DIR, exist_ok=True)

    for spec in TOKENS:
        if ONLY and spec["name"] != ONLY:
            continue
        clear_scene()
        base, inlay = build_modifier_token(spec)
        export_token(spec["name"], base, inlay)

    if ONLY is None or ONLY == "mythos":
        clear_scene()
        base, inlay = build_mythos_token()
        export_token("mythos", base, inlay)

    print("Done.")


if __name__ == "__main__":
    main()
