"""
Blades of Khorne (Bloodbound Gore Pilgrims Spearhead) game pieces (Blender
bpy) - +1 Rend tokens and arrow-shaped damage trays. Built for GENUINE
multi-material FDM printing (AMS/ACE-Gen2-style auto filament swap), not
paint: every icon/text element is a RECESSED, flush insert - the base part
has a shallow pocket cut for it, and the element itself is exported as its
own separate STL/3MF object at the exact same size, so it drops into that
pocket with zero gap. Two colors per piece: the base (black) and every
icon/text insert joined into one "inlay" object (red).

Adapted from ../tokens/build_tokens.py (the Hashut DPP/Desolation tokens) -
the generic helpers, recess/insert pipeline, 3MF exporters and the
boolean-safety patterns (border cut as its own sequential difference,
one combined content cut, volume-diff asserts) are carried over unchanged;
see that script's comments for the reasoning behind each.

Hex tokens: pointy-top hexagon, two different faces - front is the effect
(Khorne rune, a big value, a short label), back is the source ability as a
physical reminder, mirrored so it reads correctly when flipped. One token
per ability (see HEX_TOKENS):
  - +1 REND / Heads Must Roll (print x3) - up to 3 units, +1 Rend until the
    start of your next turn
  - +1 REND / Unholy Flames (print x1) - the enhancement, same effect on 1 unit
  - D6" MOVE / Murderlust (print x3) - up to D3 units each move D6"
Plus a generic token (GENERIC_TOKEN_NAME): the rune alone on both faces - spares,
and filler to top up the box's hex wells.

Damage tray: arrow-shaped plate with a square pocket holding one 16mm d6
showing the damage on the unit's current wounded model; the arrow points
at the unit. Single-sided - Khorne rune on the arrowhead's top face only.
Print x6.

Icons are traced by extract_icon_contours.py (khorne_contours.json).

Plain tray (damage_tray_plain): same arrow and die pocket, no rune - single-
colour, base STL only.

Run (all hex tokens + both trays):
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_khorne_tokens.py

Run one piece only:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_khorne_tokens.py -- --only tray   (or: --only hex, --only tray_plain)
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
    pieces, render = ["hex", "tray", "tray_plain"], True
    i = 0
    while i < len(argv):
        if argv[i] == "--only":
            pieces = [argv[i + 1]]; i += 2
        elif argv[i] == "--no-render":
            render = False; i += 1
        else:
            i += 1
    return pieces, render


PIECES, RENDER_IMAGES = _parse_args()

# ============================================================
# CONFIG (all mm)
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KHORNE_CONTOURS_PATH = os.path.join(SCRIPT_DIR, "khorne_contours.json")
TEXT_FONT_PATH = os.path.join(SCRIPT_DIR, "ArialBlack.ttf")   # bold sans - thin serif strokes
                             # don't resolve on an FDM nozzle at small recessed size
                             # (feedback_blender_text_mesh_gotchas)

EXPORT_DIR = os.path.join(SCRIPT_DIR, "output")
EXPORT_STL = True
EXPORT_3MF = True

BASE_COLOR = (0.04, 0.04, 0.04, 1.0)   # black - the plate/tray
INLAY_COLOR = (0.65, 0.03, 0.03, 1.0)  # red - every icon/text insert

# Anycubic Slicer Next only reads its own project-3mf `extruder` metadata per part (see
# export_project_3mf) - set these to whichever ACE Gen2/AMS slot holds black/red on the day
# you slice; not derivable from the model itself.
BASE_EXTRUDER_SLOT = 1    # black
INLAY_EXTRUDER_SLOT = 2   # red
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1200, 1200)

PLATE_T = 3.0               # Rend token thickness (face_span's back face sits at y=PLATE_T)
INSERT_DEPTH = 0.6          # flush recess depth for every icon/text insert
POCKET_POKE = 0.4           # pocket CUTTER pokes past the outer face - avoids the coincident-
                             # face degenerate case for the EXACT solver; inserts stay flush
HOLE_OVERSHOOT = 0.5        # overshoot for cutting a counter (letter/icon hole) out of a piece
BEVEL_W = 0.5               # edge bevel - handling comfort + print-plate release

BORDER_INSET = 1.5          # gap from the plate's outer edge to the border ring's outer edge
BORDER_WIDTH = 1.8          # ring thickness, same inlay color as everything else

BOLD_OFFSET = 0.0           # synthetic bold is unstable once text bonds to the shell
TEXT_SPACING = 1.1          # tracked letter-spacing - at 1.0 some Arial Black pairs touch, and
                            # a touching pair corrupts the EXACT solver (see build_tokens.py)

# ---- Hex tokens ----
HEX_FLAT_TO_FLAT = 33.0     # same as the Hashut DPP token - proven size in hand
HEX_INNER_FLAT_TO_FLAT = HEX_FLAT_TO_FLAT - 2.0 * (BORDER_INSET + BORDER_WIDTH)
HEX_CONTENT_CLEARANCE = 0.5    # gap kept between content and the border's inner edge - tighter
                               # than DPP's 1.0 to fit three elements in the same hex

HEX_RUNE_W = 9.5
HEX_RUNE_TOP_Z = 12.2       # as high as the rune's top corners clear the tapering inner hex
HEX_VALUE_SIZE = 9.0
HEX_VALUE_GAP_BELOW_RUNE = 1.2
HEX_LABEL_SIZE = 5.0
HEX_LABEL_GAP_BELOW_VALUE = 0.8
HEX_BACK_SIZE = 6.0         # back face: one word per line, block auto-centered
HEX_BACK_LINE_GAP = 1.4

# output name -> (front value, front label, back lines)
HEX_TOKENS = {
    "rend_token_heads_must_roll": ("+1", "REND", ["HEADS", "MUST", "ROLL"]),   # print x3
    "rend_token_unholy_flames": ("+1", "REND", ["UNHOLY", "FLAMES"]),          # print x1
    "murderlust_token": ('D6"', "MOVE", ["MURDER", "LUST"]),                   # print x3 -
                        # MURDERLUST on one line only fits at ~4.3mm, below what prints well
}

# Generic token: the rune alone, centered and as big as fits, on both faces - spares/fillers
GENERIC_TOKEN_NAME = "khorne_token"
GENERIC_RUNE_W = 17.0       # largest where the rune's corners still clear the tapering inner hex

# ---- Damage tray (arrow) ----
DIE_SIZE = 16.0             # standard 16mm d6
DIE_CLEARANCE = 0.4         # per side - drops in and lifts out without sticking
TRAY_POCKET_W = DIE_SIZE + 2.0 * DIE_CLEARANCE    # 16.8
TRAY_POCKET_DEPTH = 5.0
TRAY_FLOOR_T = 1.5
TRAY_T = TRAY_POCKET_DEPTH + TRAY_FLOOR_T         # 6.5 - three stack to 19.5, inside a 22mm well
TRAY_WALL = 2.6             # material around the pocket
TRAY_BODY_W = TRAY_POCKET_W + 2.0 * TRAY_WALL     # 22.0 - square body, pocket centered on origin
TRAY_HEAD_L = 18.0          # arrowhead length, base to tip - head is as wide as the body
TRAY_RUNE_W = 9.0
TRAY_RUNE_TOP_Z = 20.0      # on the arrowhead, clear of the pocket and the tapering sides
TRAY_CONTENT_CLEARANCE = 1.0

# ============================================================
# GENERIC HELPERS (same conventions as card-stand/card_stand_v7_trophy.py)
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
    solid prism. `plane` is 'XZ' (points are (x, z), extrude along Y).
    `offset` is the fixed Y of the starting face; extrusion runs
    +thickness from there."""
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
    """Merge several non-overlapping-with-each-other pieces into ONE mesh
    object before a single boolean call - the established fix in this repo
    for EXACT-solver corruption on long boolean chains (see
    feedback_blender_boolean_fragility memory / card-stand scripts):
    combine same-type cutters/pieces first, one boolean per category
    instead of one boolean per piece."""
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    objs[0].name = name
    return objs[0]


def dedupe_closed_loop(points, tol=1e-9):
    """Traced contours from skimage's find_contours come back as closed
    rings with the first and last point identical (confirmed: every hole
    contour in bull_contours.json has this, the outer ones don't) - left
    in, that duplicate vertex makes bm.faces.new build a degenerate ngon
    (a zero-length edge back to a coincident vertex), which is what was
    producing ~50% non-manifold edges on the extruded solid and letting
    the EXACT solver silently corrupt the shell on the DIFFERENCE step.
    Drop it before building any face from these points."""
    if len(points) > 1:
        x0, y0 = points[0]
        x1, y1 = points[-1]
        if abs(x0 - x1) < tol and abs(y0 - y1) < tol:
            return points[:-1]
    return points


def mirror_points_x(points):
    """Flip a closed (x, z) point loop's X coordinate - used for every
    back-face icon piece so it reads correctly (not mirrored) when the
    token is flipped over and viewed from behind. See module docstring."""
    return [(-x, z) for x, z in points]


def mirror_mesh_x(obj):
    """Same mirroring for a built text mesh - flips vertex.co.x directly
    (not a negative-scale transform, which would need its own normal
    fixup) then recalculates face normals so the boolean union still sees
    a consistent outward-facing solid."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for v in bm.verts:
        v.co.x = -v.co.x
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
        (min(xs) + max(xs)) / 2,
        (min(ys) + max(ys)) / 2,
        (min(zs) + max(zs)) / 2,
    ))
    size = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    return center, size


def setup_camera_and_light(center, distance, ortho_scale, from_back=False):
    """Camera looks along +/-Y at the given face. Two bugs fixed here after
    inspecting the first two render passes:
    1. The light has to flip to the SAME side as the camera (not stay
       fixed on the front's -Y side) - otherwise a back-face render points
       the camera at the one face the light isn't illuminating, and comes
       back solid black.
    2. The camera's rotation has to be built via a look-at (track_quat,
       world +Z kept as "up") rather than a hand-picked +/-90 degree Euler
       - a raw sign-flipped Euler rotation changes the camera's ROLL too,
       which flipped the back render top-to-bottom (bull/number/text order
       reversed) instead of just mirroring left-right the way the geometry
       itself was mirrored (see mirror_points_x / mirror_mesh_x - both
       only ever flip X, assuming a "walk around and view from behind"
       flip around the vertical axis, not a top-to-bottom coin flip)."""
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
    """Frames on every mesh currently in the scene (compute_scene_bounds
    scans bpy.context.scene.objects) - so rendering with both the base
    plate and the inlay present shows the assembled two-color result."""
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


def export_stl(obj, filename):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = os.path.join(EXPORT_DIR, filename)
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"Exported {path}")


def apply_color(obj, name, rgba):
    """Viewport/render-only material (EEVEE Principled BSDF base color) so
    the base-plate/inlay preview renders actually show the intended
    two-color look - has no bearing on the exported geometry."""
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


def export_3mf(parts, path):
    """A 3MF is just a zip of a few XML parts - no external library needed.
    Writes every part as its own named <object>, tagged with a color via
    the materials-extension <colorgroup>. Adapted from
    ~/best/site/assets/code/procedural-mesh/scout-name-tags/gear_name_tag.py's
    export_3mf - that project's own memory flags why this matters: a
    slicer auto-centers each independently-imported STL, which breaks the
    base/inlay's relative alignment - a single 3MF with multiple objects
    keeps them in the same coordinate space, so they still align exactly
    on import. `parts` is a list of (obj, (r, g, b, a), name), 0..1 each."""
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
    """Anycubic Slicer Next's own project-3mf flavor (Bambu Studio/
    OrcaSlicer lineage: Metadata/model_settings.config) - adapted directly
    from ~/best/site's scout-name-tags project (gear_name_tag.py's own
    export_project_3mf), which found that slicer ignores the standard 3MF
    color hint entirely (both <basematerials> and <colorgroup> came back
    flat/same-color on import there) and only reads its own `extruder`
    metadata per part, referencing whatever filament is physically loaded
    in that numbered slot - see BASE_EXTRUDER_SLOT/INLAY_EXTRUDER_SLOT.
    `parts` is a list of (obj, name, extruder_slot)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

    leaf_objects_xml = []
    components_xml = []
    parts_config_xml = []
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


# ============================================================
# ICON/TEXT RELIEF (front + mirrored back), shared by both pieces
#
# Every element (icon, number, text line) is first built as its own
# free-standing solid, with any internal hole-cutting done in isolation -
# NOT by booleaning straight onto the token shell piece by piece. Only
# once a whole side's relief (icon + number + text, joined - they don't
# touch each other, so a plain mesh join is enough, no boolean needed for
# that step) is a single finished solid does it get ONE union onto the
# shell. Two sides = two booleans on the shell, not ~14 one-per-contour
# ones - see feedback_blender_boolean_fragility: the EXACT solver
# corrupts unpredictably on long chains onto the same growing target, and
# 14 sequential ops on one shell (discovered the hard way - see git log)
# was well past where card_stand_v7_trophy's own ~10-op chain (a single
# icon+wordmark+numeral+subtitle pass, one side only) still holds up.
# ============================================================


def load_contours(path):
    """Returns (polygons, aspect h/w) - see extract_icon_contours.py."""
    with open(path) as f:
        data = json.load(f)
    return data["polygons"], data["aspect"]


def face_span(mirror, depth, poke):
    """(offset, thickness) for a solid sitting on the given face: flush
    with it (poke=0, a real printable insert) or an oversized pocket
    CUTTER (poke>0, pokes out past the plate's own outer face by `poke` -
    see POCKET_POKE). Front face is at y=0, growing INTO the plate (+Y);
    back face is at y=PLATE_T, growing into the plate in -Y."""
    if mirror:
        return (PLATE_T - depth, depth + poke)
    return (-poke, depth + poke)


def build_icon_solid(contours, icon_w, icon_h, center_x, top_z, mirror, name_prefix, poke=0.0):
    """Builds one icon (from traced contours) as its own free-standing
    solid, holes already cut - NOT yet unioned/differenced onto anything.
    Placed with its own top-left corner at (center_x - icon_w/2, top_z),
    scaled to icon_w x icon_h. poke=0.0 builds the real flush INSERT;
    poke=POCKET_POKE builds the oversized POCKET CUTTER for the same
    footprint (see face_span). Every point's X is mirrored for the back
    face so it reads correctly when viewed from behind (see module
    docstring). Returns (solid_obj, icon_bottom_z) - icon_bottom_z is the
    same for either poke value, since only the Y-depth changes."""
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

    # Same per-contour chained union/difference pattern as
    # card_stand_v7_trophy.build_logo_icon - proven for this class of
    # multi-hole traced icon - just running on an isolated solid instead
    # of the token shell directly.
    solid = _extrude_profile(outer_pts[0], 'XZ', offset, thickness, f"{name_prefix}_0")
    for i, pts in enumerate(outer_pts[1:], start=1):
        union_onto(solid, _extrude_profile(pts, 'XZ', offset, thickness, f"{name_prefix}_{i}"))
    for i, pts in enumerate(hole_pts):
        # Overshoot both ends of the piece's own Y span so the cutter fully punches through
        # it (a letter/icon counter, e.g. the bull's eye) regardless of front/back or poke.
        cutter = _extrude_profile(pts, 'XZ', offset - HOLE_OVERSHOOT,
                                   thickness + 2 * HOLE_OVERSHOOT, f"{name_prefix}_hole_{i}")
        apply_boolean(solid, cutter, 'DIFFERENCE')

    return solid, icon_z0


def rect_points(w, h):
    """Rectangle outline (w wide, h tall) as a closed (x, z) loop,
    centered on the origin - square_points is just rect_points(s, s)."""
    hw, hh = w / 2.0, h / 2.0
    return [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]


def square_points(size):
    return rect_points(size, size)


def build_border_solid(shrink_fn, mirror, name_prefix, poke=0.0):
    """A thin ring/frame following the plate's own outline, inset from the
    real edge by BORDER_INSET - same recess/insert convention as every
    other element (poke=0 flush insert, poke=POCKET_POKE oversized
    cutter). `shrink_fn(inset)` returns the plate's own outline shrunk
    uniformly inward by `inset` on every side - e.g.
    `lambda inset: hex_points(FLAT_TO_FLAT - 2*inset)` for a hex, or
    `lambda inset: rect_points(W - 2*inset, H - 2*inset)` for a
    (possibly non-square) rectangle, so a hex and a rectangle can share
    this one function. No X-mirroring needed - the ring is rotationally
    symmetric, so front and back are identical shapes, just built at each
    face's own depth."""
    offset, thickness = face_span(mirror, INSERT_DEPTH, poke)
    outer_pts = shrink_fn(BORDER_INSET)
    inner_pts = shrink_fn(BORDER_INSET + BORDER_WIDTH)

    solid = _extrude_profile(outer_pts, 'XZ', offset, thickness, f"{name_prefix}_outer")
    cutter = _extrude_profile(inner_pts, 'XZ', offset - HOLE_OVERSHOOT,
                               thickness + 2 * HOLE_OVERSHOOT, f"{name_prefix}_inner_cut")
    apply_boolean(solid, cutter, 'DIFFERENCE')
    return solid


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

    # FONT-curve-to-mesh conversion leaves duplicate overlapping vertices at the cap-fill
    # boundary (confirmed: every text piece tested here, even a single "1", measured
    # ~0.57 non-manifold edge fraction right after convert() - a real Blender quirk, not
    # specific to any one glyph) - exactly the self-intersecting-geometry condition that
    # corrupts the EXACT boolean solver (it's what took the Desolation token's front
    # relief union from 3653mm3 to 202mm3). Merge-by-distance cleans it to 0.0 every time.
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-3)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def build_text_solid(text, size, center_x, top_z, mirror, poke=0.0, font_path=TEXT_FONT_PATH):
    """Same front/back-mirrored placement as build_icon_solid, for real
    vector text - a single object, no internal booleans needed. poke=0.0
    builds the real flush INSERT; poke=POCKET_POKE builds the oversized
    POCKET CUTTER for the same string/position (see face_span). Returns
    (solid_obj, text_bottom_z, text_width) - z/width are the same for
    either poke value, since only the Y-depth changes."""
    offset, thickness = face_span(mirror, INSERT_DEPTH, poke)
    obj = _build_flat_text_mesh(text, size, thickness, font_path)

    local_top_y = max(v.co.y for v in obj.data.vertices)
    local_bottom_y = min(v.co.y for v in obj.data.vertices)
    text_h = local_top_y - local_bottom_y
    text_w = max(v.co.x for v in obj.data.vertices) - min(v.co.x for v in obj.data.vertices)

    if mirror:
        mirror_mesh_x(obj)

    # Curve extrude is symmetric around its own local center plane, unlike the icon's
    # _extrude_profile (whose offset IS the fixed starting face) - so the object's own Y
    # location has to be the piece's MIDPOINT, not either tip - i.e. offset + thickness/2.
    mid_y = offset + thickness / 2.0

    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    obj.location = (center_x, mid_y, top_z - local_top_y)
    apply_transform(obj)

    return obj, top_z - text_h, text_w


def carve_and_collect_inlay(shell, inserts, cutters, name_prefix):
    """ONE combined pocket cut (all cutters joined - safe, they occupy
    separate zones per element and per face, see face_span/module
    docstring) removes material from the shell for every icon/text
    element on both faces; the matching flush inserts are joined into ONE
    inlay object (same color, never touching) - NOT unioned onto the
    shell, since it's meant to print/be handled as its own separate part.
    Returns (shell, inlay)."""
    prev_volume = mesh_volume(shell)
    cutter_union = join_objects(cutters, f"{name_prefix}_cutters")
    apply_boolean(shell, cutter_union, 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_volume, (
        f"{name_prefix}: pocket cut did not remove a sane amount of material "
        f"({prev_volume:.1f} -> {vol:.1f}mm3) - likely EXACT-solver corruption, see "
        f"feedback_blender_boolean_fragility memory."
    )

    inlay = join_objects(inserts, f"{name_prefix}_inlay")
    return shell, inlay



# ============================================================
# HEX OUTLINE
# ============================================================


def hex_points(flat_to_flat):
    """Pointy-top regular hexagon outline (points at top/bottom, flat
    sides left/right) as a closed (x, z) loop, centered on the origin."""
    r = flat_to_flat / math.sqrt(3.0)
    pts = []
    for k in range(6):
        angle = math.radians(90.0 + 60.0 * k)
        pts.append((r * math.cos(angle), r * math.sin(angle)))
    return pts


def hex_width_at_z(flat_to_flat, z):
    """Usable horizontal width of the pointy-top hex at vertical offset z
    from center - used to sanity-check content doesn't touch the sloped
    sides near the top/bottom points."""
    r = flat_to_flat / math.sqrt(3.0)
    az = abs(z)
    if az >= r:
        return 0.0
    # Full flat_to_flat width holds up to the side vertices (at z = +-r/2 for a pointy-top
    # hex); above/below that the two slanted edges taper linearly to the top/bottom point.
    side_vertex_z = r / 2.0
    if az <= side_vertex_z:
        return flat_to_flat
    # linear taper from (apothem, side_vertex_z) to (0, r)
    t = (az - side_vertex_z) / (r - side_vertex_z)
    return flat_to_flat * (1.0 - t)



def width_between(width_fn, top_z, bottom_z):
    """Narrowest usable width over an element's full vertical span - checks
    both edges, not just the center, so a rectangular icon's corners are
    caught against a tapering outline."""
    return min(width_fn(top_z), width_fn(bottom_z))


# ============================================================
# HEX TOKEN
# ============================================================


def build_hex_token(value, label, back_lines):
    shell = _extrude_profile(hex_points(HEX_FLAT_TO_FLAT), 'XZ', 0.0, PLATE_T, "hex_shell")
    apply_bevel(shell, BEVEL_W)

    rune_contours, rune_aspect = load_contours(KHORNE_CONTOURS_PATH)
    rune_h = HEX_RUNE_W * rune_aspect
    inner_w = lambda z: hex_width_at_z(HEX_INNER_FLAT_TO_FLAT, z) - 2 * HEX_CONTENT_CLEARANCE

    inserts, cutters = [], []

    def add_text_line(text, size, top_z, mirror):
        insert, bottom_z, text_w = build_text_solid(text, size, 0.0, top_z, mirror, poke=0.0)
        cutter, _, _ = build_text_solid(text, size, 0.0, top_z, mirror, poke=POCKET_POKE)
        assert text_w <= width_between(inner_w, top_z, bottom_z), \
            f"'{text}' ({text_w:.1f}mm) too wide for the border's inner hex at this height - shrink its size or gaps"
        inserts.append(insert)
        cutters.append(cutter)
        return bottom_z

    # Front: the effect - rune, "+1", "REND"
    rune_insert, rune_bottom_z = build_icon_solid(rune_contours, HEX_RUNE_W, rune_h,
                                                    0.0, HEX_RUNE_TOP_Z, False, "hex_rune_ins", poke=0.0)
    rune_cutter, _ = build_icon_solid(rune_contours, HEX_RUNE_W, rune_h,
                                       0.0, HEX_RUNE_TOP_Z, False, "hex_rune_cut", poke=POCKET_POKE)
    assert HEX_RUNE_W <= width_between(inner_w, HEX_RUNE_TOP_Z, rune_bottom_z), \
        "Hex rune too wide for the border's inner hex at this height - shrink HEX_RUNE_W or lower HEX_RUNE_TOP_Z"
    inserts.append(rune_insert)
    cutters.append(rune_cutter)
    num_bottom_z = add_text_line(value, HEX_VALUE_SIZE,
                                 rune_bottom_z - HEX_VALUE_GAP_BELOW_RUNE, False)
    add_text_line(label, HEX_LABEL_SIZE, num_bottom_z - HEX_LABEL_GAP_BELOW_VALUE, False)

    # Back: the source ability, one word per line (mirrored so it reads correctly when flipped).
    # Stacked from z=0 first, then the whole block is shifted to center on the hex - the line
    # count differs per variant, so a fixed top z would only center one of them.
    lines, top_z = [], 0.0
    for word in back_lines:
        insert, bottom_z, text_w = build_text_solid(word, HEX_BACK_SIZE, 0.0, top_z, True, poke=0.0)
        cutter, _, _ = build_text_solid(word, HEX_BACK_SIZE, 0.0, top_z, True, poke=POCKET_POKE)
        lines.append((word, insert, cutter, top_z, bottom_z, text_w))
        top_z = bottom_z - HEX_BACK_LINE_GAP
    shift = -(lines[0][3] + lines[-1][4]) / 2.0
    for word, insert, cutter, line_top, line_bottom, text_w in lines:
        for obj in (insert, cutter):
            obj.data.transform(mathutils.Matrix.Translation((0.0, 0.0, shift)))
        assert text_w <= width_between(inner_w, line_top + shift, line_bottom + shift), \
            f"'{word}' ({text_w:.1f}mm) too wide for the border's inner hex at this height - shrink HEX_BACK_SIZE"
        inserts.append(insert)
        cutters.append(cutter)
    assert lines[0][3] + shift < HEX_INNER_FLAT_TO_FLAT / math.sqrt(3.0) - HEX_CONTENT_CLEARANCE, \
        "Back text block taller than the border's inner hex - shrink HEX_BACK_SIZE or HEX_BACK_LINE_GAP"

    hex_shrink = lambda inset: hex_points(HEX_FLAT_TO_FLAT - 2.0 * inset)
    border_cutters = []
    for mirror, tag in ((False, "front"), (True, "back")):
        inserts.append(build_border_solid(hex_shrink, mirror, f"hex_border_{tag}_ins", poke=0.0))
        border_cutters.append(build_border_solid(hex_shrink, mirror, f"hex_border_{tag}_cut", poke=POCKET_POKE))

    # Border cut FIRST as its own separate sequential difference, before the combined content
    # cut - a border-ring cutter joined into the same boolean as content cutters can corrupt
    # the mesh even when each is clean alone.
    prev_vol = mesh_volume(shell)
    apply_boolean(shell, join_objects(border_cutters, "hex_border_cutters"), 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_vol, f"hex: border cut corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"

    return carve_and_collect_inlay(shell, inserts, cutters, "hex")


def build_generic_hex_token():
    shell = _extrude_profile(hex_points(HEX_FLAT_TO_FLAT), 'XZ', 0.0, PLATE_T, "generic_shell")
    apply_bevel(shell, BEVEL_W)

    rune_contours, rune_aspect = load_contours(KHORNE_CONTOURS_PATH)
    rune_h = GENERIC_RUNE_W * rune_aspect
    top_z = rune_h / 2.0
    inner_w = lambda z: hex_width_at_z(HEX_INNER_FLAT_TO_FLAT, z) - 2 * HEX_CONTENT_CLEARANCE
    assert GENERIC_RUNE_W <= width_between(inner_w, top_z, -top_z), \
        "Generic rune too wide for the border's inner hex at its corners - shrink GENERIC_RUNE_W"

    inserts, cutters, border_cutters = [], [], []
    hex_shrink = lambda inset: hex_points(HEX_FLAT_TO_FLAT - 2.0 * inset)
    for mirror, tag in ((False, "front"), (True, "back")):
        ins, _ = build_icon_solid(rune_contours, GENERIC_RUNE_W, rune_h, 0.0, top_z, mirror,
                                  f"generic_rune_{tag}_ins", poke=0.0)
        cut, _ = build_icon_solid(rune_contours, GENERIC_RUNE_W, rune_h, 0.0, top_z, mirror,
                                  f"generic_rune_{tag}_cut", poke=POCKET_POKE)
        inserts += [ins, build_border_solid(hex_shrink, mirror, f"generic_border_{tag}_ins", poke=0.0)]
        cutters.append(cut)
        border_cutters.append(build_border_solid(hex_shrink, mirror, f"generic_border_{tag}_cut", poke=POCKET_POKE))

    # Border cut first, its own sequential difference - same reason as build_hex_token
    prev_vol = mesh_volume(shell)
    apply_boolean(shell, join_objects(border_cutters, "generic_border_cutters"), 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_vol, f"generic: border cut corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"

    return carve_and_collect_inlay(shell, inserts, cutters, "generic")


# ============================================================
# DAMAGE TRAY (arrow)
# ============================================================

TRAY_HEAD_BASE_Z = TRAY_BODY_W / 2.0
TRAY_TIP_Z = TRAY_HEAD_BASE_Z + TRAY_HEAD_L


def arrow_points():
    """Arrow outline as a closed (x, z) loop, pointing +Z: a square body
    centered on the origin (the die pocket's center) with a same-width
    triangular head on top - a pentagon."""
    hb = TRAY_BODY_W / 2.0
    return [(-hb, -hb), (hb, -hb), (hb, TRAY_HEAD_BASE_Z), (0.0, TRAY_TIP_Z), (-hb, TRAY_HEAD_BASE_Z)]


def arrowhead_width_at_z(z):
    if z <= TRAY_HEAD_BASE_Z:
        return TRAY_BODY_W
    return TRAY_BODY_W * max(0.0, TRAY_TIP_Z - z) / TRAY_HEAD_L


def build_damage_tray(plain=False):
    shell = _extrude_profile(arrow_points(), 'XZ', 0.0, TRAY_T, "tray_shell")
    apply_bevel(shell, BEVEL_W)

    # Die pocket: structural cut, its own sequential difference (different class of cut from
    # the decorative inlay pockets, same reasoning as the box's wells vs icon pockets).
    pocket = build_box(TRAY_POCKET_W, TRAY_POCKET_DEPTH + POCKET_POKE, TRAY_POCKET_W,
                       (0.0, (TRAY_POCKET_DEPTH - POCKET_POKE) / 2.0, 0.0), "tray_pocket_cut")
    prev_vol = mesh_volume(shell)
    apply_boolean(shell, pocket, 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_vol, f"tray: die pocket cut corrupted the shell ({prev_vol:.1f} -> {vol:.1f}mm3)"
    if plain:
        return shell, None

    rune_contours, rune_aspect = load_contours(KHORNE_CONTOURS_PATH)
    rune_h = TRAY_RUNE_W * rune_aspect
    rune_insert, rune_bottom_z = build_icon_solid(rune_contours, TRAY_RUNE_W, rune_h,
                                                    0.0, TRAY_RUNE_TOP_Z, False, "tray_rune_ins", poke=0.0)
    rune_cutter, _ = build_icon_solid(rune_contours, TRAY_RUNE_W, rune_h,
                                       0.0, TRAY_RUNE_TOP_Z, False, "tray_rune_cut", poke=POCKET_POKE)
    usable = lambda z: arrowhead_width_at_z(z) - 2 * TRAY_CONTENT_CLEARANCE
    assert TRAY_RUNE_W <= width_between(usable, TRAY_RUNE_TOP_Z, rune_bottom_z), \
        "Tray rune too wide for the arrowhead at this height - shrink TRAY_RUNE_W or lower TRAY_RUNE_TOP_Z"
    assert rune_bottom_z >= TRAY_POCKET_W / 2.0 + TRAY_CONTENT_CLEARANCE, \
        "Tray rune runs into the die pocket's wall - raise TRAY_RUNE_TOP_Z or shrink TRAY_RUNE_W"

    return carve_and_collect_inlay(shell, [rune_insert], [rune_cutter], "tray")


# ============================================================
# MAIN
# ============================================================


def reorient_for_print(obj, thickness):
    """Build/render math treats Y as thickness and Z as the piece's own
    in-plane "up"; slicers treat Z as the build direction. Proper rotation
    (x, y, z) -> (x, z, thickness - y) (determinant +1, not a mirror) lays
    the piece flat on the bed with the front face (y=0) on top. Applied
    ONLY right before export, after rendering."""
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


def export_piece(name, base, inlay, thickness, render_back):
    """Sanity-check both parts, color and render (still in build orientation,
    for the render camera), then reorient flat for printing and export
    base.stl + inlay.stl plus the combined 3MFs."""
    base_vol, base_nm = mesh_volume(base), nonmanifold_fraction(base)
    print(f"{name}: base volume={base_vol:.1f}mm3 (non-manifold {base_nm:.4f})")
    assert base_vol > 0.0, f"{name}: base has zero/negative volume - a boolean likely emptied it"
    if inlay is None:
        # Single-colour piece (damage_tray_plain): base STL only.
        apply_color(base, "base_black", BASE_COLOR)
        if RENDER_IMAGES:
            render_face(f"{name}_front", from_back=False)
        reorient_for_print(base, thickness)
        if EXPORT_STL:
            export_stl(base, f"{name}.stl")
        return
    inlay_vol, inlay_nm = mesh_volume(inlay), nonmanifold_fraction(inlay)
    print(f"{name}: inlay volume={inlay_vol:.1f}mm3 (non-manifold {inlay_nm:.4f})")
    assert inlay_vol > 0.0, f"{name}: inlay has zero/negative volume - a boolean likely emptied it"

    apply_color(base, "base_black", BASE_COLOR)
    apply_color(inlay, "inlay_red", INLAY_COLOR)
    if RENDER_IMAGES:
        render_face(f"{name}_front", from_back=False)
        if render_back:
            render_face(f"{name}_back", from_back=True)

    reorient_for_print(base, thickness)
    reorient_for_print(inlay, thickness)

    if EXPORT_STL:
        export_stl(base, f"{name}_base.stl")
        export_stl(inlay, f"{name}_inlay.stl")
    if EXPORT_3MF:
        export_3mf([(base, BASE_COLOR, "base"), (inlay, INLAY_COLOR, "inlay")],
                   os.path.join(EXPORT_DIR, f"{name}.3mf"))
        # Import THIS one in Anycubic Slicer Next - see export_project_3mf's docstring.
        export_project_3mf(
            [(base, "base", BASE_EXTRUDER_SLOT), (inlay, "inlay", INLAY_EXTRUDER_SLOT)],
            os.path.join(EXPORT_DIR, f"{name}_anycubic.3mf"))


def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    if RENDER_IMAGES:
        os.makedirs(RENDER_DIR, exist_ok=True)

    if "hex" in PIECES:
        for name, (value, label, back_lines) in HEX_TOKENS.items():
            clear_scene()
            base, inlay = build_hex_token(value, label, back_lines)
            export_piece(name, base, inlay, PLATE_T, render_back=True)
        clear_scene()
        base, inlay = build_generic_hex_token()
        export_piece(GENERIC_TOKEN_NAME, base, inlay, PLATE_T, render_back=True)

    if "tray" in PIECES:
        clear_scene()
        base, inlay = build_damage_tray()
        export_piece("damage_tray", base, inlay, TRAY_T, render_back=False)

    if "tray_plain" in PIECES:
        clear_scene()
        base, _ = build_damage_tray(plain=True)
        export_piece("damage_tray_plain", base, None, TRAY_T, render_back=False)

    print("Done.")


if __name__ == "__main__":
    main()
