"""
Hashut game tokens (Blender bpy) - Daemonic Power Point (DPP) tokens and
Desolation Tokens for the Helsmiths of Hashut AoS army
(content/projects/hashut). Built for GENUINE multi-material FDM printing
(AMS/ACE-Gen2-style auto filament swap), not paint: every icon/text
element is a RECESSED, flush insert - the base plate has a shallow pocket
cut for it, and the element itself is exported as its own separate STL/
3MF object at the exact same size, so it drops into that pocket with zero
gap. Two colors per token: the base plate (color A) and every icon/text
insert across both faces, joined into one "inlay" object (color B) since
they're all the same color and never touch each other. Same recess/insert
pattern as ~/best/site's scout-name-tags project
(assets/code/procedural-mesh/scout-name-tags/gear_name_tag.py) - see that
script's INSERT_DEPTH/make_text_obj/recess_and_export_elements for the
original working reference this was adapted from.

Double-sided: both faces carry the full design (icon + text), so either
face reads correctly when the token is flipped on the table. Icon relief
uses the same marching-squares contour approach as
card-stand/card_stand_v7_trophy.py's build_logo_icon - see
extract_icon_contours.py for how bull_contours.json / rune_contours.json
were traced from the source images.

Mirroring for the back face: a naive copy of the same (x, z) contour/text
onto the back face reads MIRRORED when viewed from behind (looking in -Y,
the geometry's handedness flips relative to the front view) - same
principle as a two-sided coin die. Every back-face piece has its points
(icon contours) or mesh vertices (text) mirrored in X before placement -
see mirror_points_x / mirror_mesh_x.

DPP token: hexagon, one physical token per power level (1/2/3) - the
level is swapped by picking the right token rather than stacking, so each
level needs its own STL/3MF. Desolation token: square, single design.

Run (all 3 DPP levels + the desolation token):
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_tokens.py

Run one DPP level only:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_tokens.py -- --dpp-level 2 --no-desolation
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
    levels, build_desolation, render = [1, 2, 3], True, True
    i = 0
    while i < len(argv):
        if argv[i] == "--dpp-level":
            levels = [int(argv[i + 1])]; i += 2
        elif argv[i] == "--no-desolation":
            build_desolation = False; i += 1
        elif argv[i] == "--no-render":
            render = False; i += 1
        else:
            i += 1
    return levels, build_desolation, render


DPP_LEVELS, BUILD_DESOLATION, RENDER_IMAGES = _parse_args()

# ============================================================
# CONFIG (all mm)
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BULL_CONTOURS_PATH = os.path.join(SCRIPT_DIR, "bull_contours.json")
RUNE_CONTOURS_PATH = os.path.join(SCRIPT_DIR, "rune_contours.json")
TEXT_FONT_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "card-stand", "BaskervilleBold.ttf"))

EXPORT_DIR = os.path.join(SCRIPT_DIR, "output")
EXPORT_STL = True
EXPORT_3MF = True

BASE_COLOR = (1.0, 1.0, 1.0, 1.0)     # white - the plate
INLAY_COLOR = (0.06, 0.45, 0.12, 1.0)  # green - every icon/text insert, both faces

# Anycubic Slicer Next doesn't read the standard 3MF color hint at all (confirmed: the generic
# export_3mf below produces a structurally correct <colorgroup> - base pindex=0/white, inlay
# pindex=1/green, checked directly in the XML - but it still imported both parts as the same
# color). It only reads its own project-3mf `extruder` metadata per part, referencing whatever
# filament is physically loaded in that numbered slot - same finding and same fix as
# ~/best/site's scout-name-tags project (see that script's own export_project_3mf/EXTRUDER_SLOT).
# Edit these to match your ACE Gen2/AMS loadout on the day you slice - not derivable from the
# model itself.
BASE_EXTRUDER_SLOT = 1    # white
INLAY_EXTRUDER_SLOT = 2   # green
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1200, 1200)

PLATE_T = 3.0               # token thickness
INSERT_DEPTH = 0.6          # flush recess depth for every icon/text insert - matches the proven
                             # depth from ~/best's scout-name-tags project (INSERT_DEPTH there).
                             # 0.6mm into a 3mm plate leaves 3.0 - 2*0.6 = 1.8mm of solid core
                             # between the front and back pockets - plenty strong.
POCKET_POKE = 0.4           # how far the POCKET CUTTER (not the insert itself) pokes out past
                             # the plate's own outer face - the EMBED-pattern lesson from
                             # feedback_blender_boolean_fragility: a cutter flush with the target
                             # surface it's cutting is a coincident-face degenerate case for the
                             # EXACT solver. The insert itself stays exactly flush (poke=0).
HOLE_OVERSHOOT = 0.5        # separate overshoot for cutting a letter/icon COUNTER (e.g. the hole
                             # in "O" or the bull's eye) out of an already-built outer piece -
                             # needs to fully punch through that piece's own (now much thinner,
                             # insert-depth-scale) thickness, not related to POCKET_POKE.
BEVEL_W = 0.5                # edge bevel - handling comfort + print-plate release, same reasoning
                              # as card_stand_v7_trophy's BACKPLATE_BEVEL_W

BORDER_INSET = 1.5           # gap from the plate's own outer edge to the border ring's outer edge
BORDER_WIDTH = 1.8           # ring thickness - same inlay green as everything else (no 3rd color:
                              # it's just another element in the same inserts/cutters lists), on
                              # both faces like every other element - see build_border_solid

BOLD_OFFSET = 0.0          # matches v7's own conclusion: curve_data.offset synthetic-bold is
                            # unstable once text actually bonds to the shell - rely on absolute
                            # size instead (see TEXT_SIZE/NUMBER_SIZE below)
TEXT_SPACING = 1.1          # curve_data.space_character - tracked letter-spacing. Root-caused:
                            # at default 1.0 kerning, some letter pairs in this font/size sit
                            # close enough to touch (confirmed via bisection: "KE", "LA" and any
                            # string containing them, e.g. DESOLATION/TOKEN, corrupted the shell
                            # to near-zero volume on union - "DP"/"PP"/single digits didn't). A
                            # touching pair makes the text's own mesh locally invalid in a way
                            # mesh_volume/nonmanifold_fraction didn't clearly flag, and the EXACT
                            # solver corrupts on it once that region actually overlaps the target.
                            # 1.05 was already enough to separate every pair tested; 1.1 for margin.

# --- DPP hexagon token ---
DPP_FLAT_TO_FLAT = 33.0     # horizontal, flat-to-flat (pointy-top hex - points at top/bottom).
                             # v5: shrunk from 38 (~13% smaller, "a tad") with every content size
                             # below scaled down to match, same proportions - re-verified all the
                             # same width/floor checks pass with margin at this size, same as v4's
                             # own tuning against the border's inner hex (DPP_INNER_FLAT_TO_FLAT).
DPP_POINT_TO_POINT = DPP_FLAT_TO_FLAT * 2.0 / math.sqrt(3.0)   # vertical, point-to-point (~38.1mm)
DPP_INNER_FLAT_TO_FLAT = DPP_FLAT_TO_FLAT - 2.0 * (BORDER_INSET + BORDER_WIDTH)   # the hex the
                             # border ring leaves hollow - every element's width/z-runoff check is
                             # against THIS, not the plate's own outline, so content never touches
                             # the border (see build_border_solid)
DPP_CONTENT_CLEARANCE = 1.0     # gap kept between content and the border's own inner edge

DPP_TEXT_STRING = "DPP"
DPP_TEXT_SIZE = 4.0          # v5: scaled down from 4.5 with the hex
DPP_TEXT_TOP_MARGIN = 6.0    # v5: scaled down from 7.0 with the hex

DPP_BULL_W = 15.0            # v5: scaled down from 17.0 with the hex (still the biggest single
                              # element - v3's "make the bull bigger" request still holds at this
                              # smaller overall size, same proportions)
DPP_BULL_ASPECT = 1.0        # source bull_hashut.png is 215x215, square
DPP_BULL_GAP_BELOW_TEXT = 1.0

DPP_NUMBER_SIZE = 9.5               # v5: scaled down from 11.0 with the hex - "#1"/"#2"/"#3", the
                                     # swappable power-level readout, still the most prominent
                                     # element at a glance by sitting biggest and lowest
DPP_NUMBER_GAP_BELOW_BULL = 1.0

# --- Desolation token ---
DESO_WIDTH = 47.0            # v5: rectangle, not square - widened specifically so "DESOLATION
                              # TOKEN" fits as ONE line at DESO_TEXT_SIZE (measured 35.4mm; inner
                              # rect usable width here is 38.4mm, ~3mm spare) instead of wrapping
DESO_HEIGHT = 30.0            # shorter than the old 35mm square - one text line instead of two
                               # needs less vertical room
DESO_INNER_W = DESO_WIDTH - 2.0 * (BORDER_INSET + BORDER_WIDTH)    # same border-clearance
DESO_INNER_H = DESO_HEIGHT - 2.0 * (BORDER_INSET + BORDER_WIDTH)   # reasoning as DPP_INNER_FLAT_TO_FLAT
DESO_CONTENT_CLEARANCE = 1.0

DESO_RUNE_W = 15.0
DESO_RUNE_ASPECT = 1.0      # source rune_hashut.jpeg is 192x192, square
DESO_RUNE_TOP_MARGIN = 2.0   # trimmed from 4.0 - the shorter plate has less vertical room to
                              # spare now that there's only one text line below the icon

DESO_TEXT_STRING = "DESOLATION TOKEN"   # one line, not two - see DESO_WIDTH
DESO_TEXT_SIZE = 4.2
DESO_TEXT_GAP_BELOW_RUNE = 2.0

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
# ICON/TEXT RELIEF (front + mirrored back), shared by both tokens
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
    with open(path) as f:
        return json.load(f)


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
# DPP HEXAGON TOKEN
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


def build_dpp_token(level):
    shell = _extrude_profile(hex_points(DPP_FLAT_TO_FLAT), 'XZ', 0.0, PLATE_T, "dpp_shell")
    apply_bevel(shell, BEVEL_W)

    bull_contours = load_contours(BULL_CONTOURS_PATH)
    bull_h = DPP_BULL_W * DPP_BULL_ASPECT
    top_z = DPP_POINT_TO_POINT / 2.0 - DPP_TEXT_TOP_MARGIN

    inserts, cutters = [], []
    for mirror, tag in ((False, "front"), (True, "back")):
        text_insert, text_bottom_z, text_w = build_text_solid(
            DPP_TEXT_STRING, DPP_TEXT_SIZE, 0.0, top_z, mirror, poke=0.0)
        text_cutter, _, _ = build_text_solid(
            DPP_TEXT_STRING, DPP_TEXT_SIZE, 0.0, top_z, mirror, poke=POCKET_POKE)
        assert text_w <= hex_width_at_z(DPP_INNER_FLAT_TO_FLAT, top_z - DPP_TEXT_SIZE / 2.0) - 2 * DPP_CONTENT_CLEARANCE, \
            f"DPP wordmark ({text_w:.1f}mm) too wide for the border's inner hex at this height - shrink DPP_TEXT_SIZE"

        bull_top_z = text_bottom_z - DPP_BULL_GAP_BELOW_TEXT
        assert DPP_BULL_W <= hex_width_at_z(DPP_INNER_FLAT_TO_FLAT, bull_top_z - bull_h / 2.0) - 2 * DPP_CONTENT_CLEARANCE, \
            f"DPP bull icon ({DPP_BULL_W}mm) too wide for the border's inner hex at this height - shrink DPP_BULL_W"
        bull_insert, bull_bottom_z = build_icon_solid(bull_contours, DPP_BULL_W, bull_h,
                                                        0.0, bull_top_z, mirror, f"dpp_bull_{tag}_ins", poke=0.0)
        bull_cutter, _ = build_icon_solid(bull_contours, DPP_BULL_W, bull_h,
                                           0.0, bull_top_z, mirror, f"dpp_bull_{tag}_cut", poke=POCKET_POKE)

        num_top_z = bull_bottom_z - DPP_NUMBER_GAP_BELOW_BULL
        num_insert, num_bottom_z, num_w = build_text_solid(
            f"#{level}", DPP_NUMBER_SIZE, 0.0, num_top_z, mirror, poke=0.0)
        num_cutter, _, _ = build_text_solid(
            f"#{level}", DPP_NUMBER_SIZE, 0.0, num_top_z, mirror, poke=POCKET_POKE)
        assert num_w <= hex_width_at_z(DPP_INNER_FLAT_TO_FLAT, num_top_z - DPP_NUMBER_SIZE / 2.0) - 2 * DPP_CONTENT_CLEARANCE, \
            f"DPP level number ({num_w:.1f}mm) too wide for the border's inner hex at this height - shrink DPP_NUMBER_SIZE"
        assert num_bottom_z > -DPP_INNER_FLAT_TO_FLAT / math.sqrt(3.0) + DPP_CONTENT_CLEARANCE, \
            "DPP level number runs off the bottom point of the border's inner hex - shrink DPP_NUMBER_SIZE or gaps"

        dpp_shrink = lambda inset: hex_points(DPP_FLAT_TO_FLAT - 2.0 * inset)
        border_insert = build_border_solid(dpp_shrink, mirror, f"dpp_border_{tag}_ins", poke=0.0)
        border_cutter = build_border_solid(dpp_shrink, mirror, f"dpp_border_{tag}_cut", poke=POCKET_POKE)

        inserts += [text_insert, bull_insert, num_insert, border_insert]
        cutters += [bull_cutter, text_cutter, num_cutter, border_cutter]

    return carve_and_collect_inlay(shell, inserts, cutters, f"dpp_level{level}")


# ============================================================
# DESOLATION TOKEN
# ============================================================


def build_desolation_token():
    shell = build_box(DESO_WIDTH, PLATE_T, DESO_HEIGHT, (0.0, PLATE_T / 2.0, 0.0), "deso_shell")
    apply_bevel(shell, BEVEL_W)

    rune_contours = load_contours(RUNE_CONTOURS_PATH)
    rune_h = DESO_RUNE_W * DESO_RUNE_ASPECT
    top_z = DESO_INNER_H / 2.0 - DESO_RUNE_TOP_MARGIN
    usable_w = DESO_INNER_W - 2 * DESO_CONTENT_CLEARANCE

    assert DESO_RUNE_W <= usable_w, "Desolation rune icon too wide for the border's inner rect - shrink DESO_RUNE_W"

    inserts, cutters = [], []
    for mirror, tag in ((False, "front"), (True, "back")):
        rune_insert, rune_bottom_z = build_icon_solid(rune_contours, DESO_RUNE_W, rune_h,
                                                        0.0, top_z, mirror, f"deso_rune_{tag}_ins", poke=0.0)
        rune_cutter, _ = build_icon_solid(rune_contours, DESO_RUNE_W, rune_h,
                                           0.0, top_z, mirror, f"deso_rune_{tag}_cut", poke=POCKET_POKE)

        text_top_z = rune_bottom_z - DESO_TEXT_GAP_BELOW_RUNE
        text_insert, text_bottom_z, text_w = build_text_solid(
            DESO_TEXT_STRING, DESO_TEXT_SIZE, 0.0, text_top_z, mirror, poke=0.0)
        text_cutter, _, _ = build_text_solid(
            DESO_TEXT_STRING, DESO_TEXT_SIZE, 0.0, text_top_z, mirror, poke=POCKET_POKE)
        assert text_w <= usable_w, \
            f"'{DESO_TEXT_STRING}' ({text_w:.1f}mm) touches the plate edge - shrink DESO_TEXT_SIZE"
        assert text_bottom_z > -DESO_INNER_H / 2.0 + DESO_CONTENT_CLEARANCE, \
            "Desolation text runs off the bottom of the border's inner rect - shrink DESO_TEXT_SIZE or gaps"

        deso_shrink = lambda inset: rect_points(DESO_WIDTH - 2.0 * inset, DESO_HEIGHT - 2.0 * inset)
        border_insert = build_border_solid(deso_shrink, mirror, f"deso_border_{tag}_ins", poke=0.0)
        border_cutter = build_border_solid(deso_shrink, mirror, f"deso_border_{tag}_cut", poke=POCKET_POKE)

        inserts += [rune_insert, text_insert, border_insert]
        cutters += [rune_cutter, text_cutter, border_cutter]

    return carve_and_collect_inlay(shell, inserts, cutters, "desolation")


# ============================================================
# MAIN
# ============================================================


def reorient_for_print(obj):
    """Every build/render function above treats Y as thickness and Z as
    the token's own in-plane "up" (hex point-to-point, square height) -
    the natural axes for hex_points/build_text_solid's math and for the
    front/back render camera (which looks along Y). Slicers, though,
    treat Z as the build direction - exported as-is, the token comes in
    standing on its edge (its ~40mm Z is read as "tall"), and needs a
    manual rotate-flat in the slicer every time. This is a proper
    rotation (x, y, z) -> (x, z, PLATE_T - y) - determinant +1, so it's a
    rotation+translation, not a mirror - that swaps thickness onto Z
    (sitting in [0, PLATE_T], flat on the bed) and moves the hex/square's
    own vertical extent onto Y. Applied ONLY right before STL/3MF export,
    after rendering (which still needs the original Y-is-thickness
    orientation for its camera setup)."""
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


def export_token(name, base, inlay):
    """Shared finish-up for one token: sanity-check both parts, color and
    render front/back with both parts in the scene together (still in the
    original build orientation, for the render camera's sake), THEN
    reorient both to lie flat for printing (see reorient_for_print) and
    export base.stl + inlay.stl (for manual multi-part import) plus a
    combined 3MF (the robust path - see export_3mf)."""
    base_vol, inlay_vol = mesh_volume(base), mesh_volume(inlay)
    base_nm, inlay_nm = nonmanifold_fraction(base), nonmanifold_fraction(inlay)
    print(f"{name}: base volume={base_vol:.1f}mm3 (non-manifold {base_nm:.4f})  "
          f"inlay volume={inlay_vol:.1f}mm3 (non-manifold {inlay_nm:.4f})")
    assert base_vol > 0.0, f"{name}: base has zero/negative volume - a boolean likely emptied it"
    assert inlay_vol > 0.0, f"{name}: inlay has zero/negative volume - a boolean likely emptied it"

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
        export_3mf([(base, BASE_COLOR, "base"), (inlay, INLAY_COLOR, "inlay")],
                   os.path.join(EXPORT_DIR, f"{name}.3mf"))
        # The one that actually works in Anycubic Slicer Next - see export_project_3mf's
        # docstring. Import THIS one; the plain .3mf above is kept for other slicers/portability.
        export_project_3mf(
            [(base, "base", BASE_EXTRUDER_SLOT), (inlay, "inlay", INLAY_EXTRUDER_SLOT)],
            os.path.join(EXPORT_DIR, f"{name}_anycubic.3mf"))


def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    if RENDER_IMAGES:
        os.makedirs(RENDER_DIR, exist_ok=True)

    for level in DPP_LEVELS:
        clear_scene()
        base, inlay = build_dpp_token(level)
        export_token(f"dpp_token_level{level}", base, inlay)

    if BUILD_DESOLATION:
        clear_scene()
        base, inlay = build_desolation_token()
        export_token("desolation_token", base, inlay)

    print("Done.")


if __name__ == "__main__":
    main()
