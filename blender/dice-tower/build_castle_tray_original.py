"""
Castle-style dice tray, built from scratch (Blender bpy) - not a remix of
the downloaded reference this time. That STL (input/dice-tower/
castle_style_dice_tray.stl, see build_castle_tray.py in this same folder)
is under MakerWorld's Standard Digital File License, which rules out
publishing any derivative of it - so this is an original crenellated-
wall design, same rough concept (square basin, battlements, corner
towers), built entirely from box primitives, free to publish outright.

170 x 170mm outer footprint, 150 x 150mm basin, 6mm floor. A single
curtain-wall ring (10mm thick) runs the full perimeter; 4 corner towers
anchor the corners, bulging TOWER_OVERHANG (5mm) past the tray's own
outer edge - real bastions projecting past the wall line, not flush
corner blocks; 5 merlons per straight run between the towers, evenly
spaced with equal-width crenel gaps. Same Mythos two-pocket recess+
insert technique as the plain tray (build_dice_tray.py) and the castle
remix (build_castle_tray.py) - top pocket into the basin floor, bottom
pocket into the outer underside, mirrored contour on the bottom, both
ported again rather than imported (one self-contained file per
published post, this repo's usual pattern).

Real brick geometry on the curtain wall (both faces - outer and the
basin-facing inner wall), not carved groove lines: individual raised
blocks over a recessed "core" wall, mortar gaps between them showing the
recess through. Irregular brick sizes in both directions, each course an
independently randomized width partition rather than a fixed running-
bond half-offset repeat - simpler than a true phase-shifted bond, and
already gives "irregularly intersecting" joints since nothing forces
them to align row to row. Per-brick proud-amount jitter (never past the
nominal face - see build_brick_wall_face) for a hand-laid look, plus a
soft edge bevel and a small per-merlon top-height jitter for a
weathered-battlement look, all sized to what an FDM nozzle can actually
resolve. Merlons, towers and their own end-cap faces are left smooth -
texturing those too is a lot more bookkeeping for a small visible return
at this scale (scope cut, not an oversight).

Every box-to-box join embeds a small deliberate overlap before its
union boolean, not a flush shared face - confirmed the hard way twice in
this file's own history (see radial_range()'s docstring): Z overlap
alone isn't sufficient if the SIDE faces are also exactly coincident,
even though bmesh's simple edge-manifold check won't catch it - it shows
up as duplicate boundary geometry (verified with a full-vertex STL scan)
and can read as a shadow in a render until checked with a flat, co-
located light to rule that out first.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_castle_tray_original.py
Different jitter pattern / skip renders:
  ... -- --seed 7 --no-render
"""

import bpy
import bmesh
import json
import math
import mathutils
import os
import random
import sys
import zipfile

# ============================================================
# CLI ARGS
# ============================================================


def _parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    seed, render = 1, True
    i = 0
    while i < len(argv):
        if argv[i] == "--seed":
            seed = int(argv[i + 1]); i += 2
        elif argv[i] == "--no-render":
            render = False; i += 1
        else:
            i += 1
    return seed, render


SEED, RENDER_IMAGES = _parse_args()

# ============================================================
# CONFIG (all mm)
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

MYTHOS_CONTOURS_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "card-stand", "logo_contours_v5.json"))
MYTHOS_ASPECT = 376.0 / 720.0
LOGO_TEXT = "MYTHOS"
MYTHOS_FONT_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "card-stand", "BaskervilleBold.ttf"))
TEXT_SPACING = 1.1
GAP_FRAC = 0.15

OUTER_SIZE = 170.0
WALL_THICKNESS = 10.0   # curtain wall + merlon radial footprint - see module docstring
FLOOR_THICKNESS = 6.0
CURTAIN_HEIGHT = 10.0
MERLON_HEIGHT = 8.0
TOWER_EXTRA_HEIGHT = 6.0
N_MERLONS = 5           # per straight run, evenly spaced, gap width == merlon width

# One combined dice-storage pool: a square mini-tower (complete on all 4
# sides - own crenellation, own brick texture, cavity cut from inside
# without texturing that inside face) with a half-cylinder "elongation"
# butted directly against its one face - same diameter as the square (so
# they line up flush, no step), slightly shorter, its own crenellation +
# texture too. The half-cylinder isn't a second 4-walled room - it's just
# an extension of the same structure, only the outward-facing semicircle
# actually exists (the near half is where it merges into the square).
# Both sit on the same edge (POOL_SIGN side); the other edge falls back to
# PLAIN_TOWER - the small decorative bulge the very first version of this
# file used everywhere.
POOL_SIGN = 1  # which edge (y = +HALF side) the combined pool sits on
PLAIN_TOWER_CORNERS = {(1, -POOL_SIGN), (-1, -POOL_SIGN)}
STORAGE_TOWER_INSET = 21.0  # how far in from the exact corner the pool centers on Y
PLAIN_TOWER_OVERHANG = 5.0  # small corners' own outward bulge, same as the original design

MINI_MERLON_HEIGHT = 5.0
MINI_MERLON_WIDTH = 8.0
MINI_CRENEL_WIDTH = 8.0

SQUARE_TOWER_CAVITY = 42.0
SQUARE_TOWER_WALL = 10.0
SQUARE_TOWER_OUTER = SQUARE_TOWER_CAVITY + 2.0 * SQUARE_TOWER_WALL  # 62mm
SQUARE_TOWER_FLOOR = FLOOR_THICKNESS  # retained floor under the cavity, matches the main tray
SQUARE_TOWER_EXTRA_HEIGHT = 4.0  # "slightly higher" than the oval side

# Round/oval end matches the square's own dimensions exactly (not its own
# independent 60mm spec anymore) - so the walls line up flush at the seam
# instead of the corridor being wider than the square's cavity and cutting
# into its side walls there (the likely cause of a non-manifold spike this
# shape hit before this resize).
ROUND_TOWER_CAVITY_DIAM = SQUARE_TOWER_CAVITY
ROUND_TOWER_WALL = SQUARE_TOWER_WALL
ROUND_TOWER_RADIUS = ROUND_TOWER_CAVITY_DIAM / 2.0 + ROUND_TOWER_WALL  # 31mm, == SQUARE_TOWER_OUTER / 2
ROUND_TOWER_CAVITY_DEPTH = 20.0
ROUND_TOWER_SEGMENTS = 32

EMBED = 0.15            # overlap depth/width for every union join - never a flush shared face
BEVEL_WIDTH = 0.3
HEIGHT_JITTER = 0.15    # per-merlon top-face random nudge - weathered-battlement look

# Brick pattern, cut as grooves (DIFFERENCE) rather than built as raised
# blocks (UNION) - tried the additive approach first (individual brick
# boxes over a recessed core) and it corrupted at every batch size tried
# (all ~360 joined into one union: volume collapsed to ~0; one union per
# brick, 360 sequential: 20% non-manifold edges; batched per wall-face,
# ~45 bricks each: collapsed to 0 again) - EXACT-solver UNION is fragile
# here regardless of how the work is split. Sequential DIFFERENCE cuts on
# a single always-manifold wall, by contrast, already proved solid
# earlier in this same file (the first working version's coursing
# grooves). So: full-thickness wall (no recess), horizontal AND vertical
# mortar grooves cut into it (irregular spacing, independently
# randomized per course - joints land differently row to row without a
# forced running-bond offset), plus a per-brick recess cut of random
# extra depth for the same worn-stone height variation as before, just
# achieved by recessing each brick individually instead of raising it.
# Both wall faces (outer + basin-facing inner); merlons/towers left
# smooth (scope cut - texturing their own end-cap faces too is a lot
# more bookkeeping for a small visible return at this scale).
GROOVE_WIDTH = 1.0       # mortar line width, both directions
GROOVE_DEPTH = 0.4       # baseline mortar groove depth
BRICK_JITTER_DEPTH = 0.25  # extra random per-brick recess on top of GROOVE_DEPTH
CUT_OVERSHOOT = 0.5      # cutter overshoot past the nominal face into open air
BRICK_H_MIN, BRICK_H_MAX = 3.0, 4.5   # course height range
BRICK_W_MIN, BRICK_W_MAX = 7.0, 13.0  # brick width range along the wall

# Basin (top pocket) is a clean 150 x 150mm square here (no corner
# intrusion, unlike the downloaded reference) - ~15mm margin each side.
# Outer footprint (bottom pocket) is 170 x 170mm - ~10mm margin each side.
TOP_BUDGET = 120.0
BOTTOM_BUDGET = 150.0
CENTER_X = 0.0
CENTER_Y = 0.0

# The combined pool now dips into the basin as close as y=33 (the square
# half's south face) - the top icon+text lockup, centered at the origin,
# reached to y=44.4 at its old 120mm width, well past that. The pocket
# cutter was then slicing into the pool's own brick-textured wall geometry
# instead of a flat basin floor, which is almost certainly what corrupted
# the mesh (20% non-manifold, found by isolating which of the two Mythos
# cuts caused it). Capping the lockup's half-height keeps it clear.
TOP_HEIGHT_BUDGET = 50.0  # full height budget (not half) - see main()'s icon-sizing math

POCKET_DEPTH = 1.0
CUT_POKE = 0.3

EXPORT_DIR = os.path.join(SCRIPT_DIR, "output")
EXPORT_STL = True
EXPORT_3MF = True
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1200, 1200)

BASE_COLOR = (1.0, 1.0, 1.0, 1.0)
INLAY_COLOR = (0.06, 0.45, 0.12, 1.0)
BASE_EXTRUDER_SLOT = 1
INLAY_EXTRUDER_SLOT = 2

HALF = OUTER_SIZE / 2.0
BASIN_HALF = HALF - WALL_THICKNESS
RING_TOP = FLOOR_THICKNESS + CURTAIN_HEIGHT
MERLON_TOP = RING_TOP + MERLON_HEIGHT
TOWER_TOP = MERLON_TOP + TOWER_EXTRA_HEIGHT

POOL_CENTER_Y = POOL_SIGN * (HALF - STORAGE_TOWER_INSET)
SQUARE_POOL_CENTER_X = -(HALF - STORAGE_TOWER_INSET)
POOL_FLOOR_Z = TOWER_TOP - ROUND_TOWER_CAVITY_DEPTH  # one shared depth across both halves
SQUARE_TOWER_TOP = TOWER_TOP + SQUARE_TOWER_EXTRA_HEIGHT
# Half-cylinder's flat face sits flush against the square's own east face -
# a direct butt join, not a separate far-away cap reached by a corridor.
OVAL_CAP_CENTER_X = SQUARE_POOL_CENTER_X + SQUARE_TOWER_OUTER / 2.0

# ============================================================
# GENERIC HELPERS (ported from build_dice_tray.py / objective_markers_v1.py)
# ============================================================


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block)


def new_object_from_bmesh(bm, name):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


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


def cleanup_mesh(obj, dist=0.001):
    """Merge-by-distance + renormalize - a long chain of sequential
    booleans (1700+ cuts here) can leave near-duplicate vertices/faces
    that individually look fine (edge-manifold checks stay near 0) but
    apparently make the NEXT boolean operation much more likely to
    corrupt - found by bisecting stage-by-stage: every stage in this
    file was clean (0.0000-0.005) right up until the Mythos pocket cuts,
    which spiked to ~20% regardless of the cutter's own size or
    position. Running this right before that step is the fix being
    tried; see the module's session notes for the isolation work."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
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


def place_object(obj, center_x, center_y, mirror=False, rotate90=False):
    """See build_dice_tray.py's copy of this for the full reasoning on
    reverse_faces vs recalc_face_normals for the mirrored case."""
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

    # Fill light from the opposite lateral side, lower energy - the crenellated
    # walls throw hard raking shadows across each other under a single sun
    # (looked like a rendering defect on first pass, wasn't - see the
    # shadow-vs-geometry check in this project's session notes).
    fill_data = bpy.data.lights.new("FillLight", type='SUN')
    fill_data.energy = 1.2
    fill = bpy.data.objects.new("FillLight", fill_data)
    bpy.context.collection.objects.link(fill)
    fill.location = center + mathutils.Vector((sign * distance * 0.3, -distance * 0.6, -sign * distance * 1.2))
    fill_direction = center - fill.location
    fill.rotation_euler = fill_direction.to_track_quat('-Z', 'Y').to_euler()
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


def render_iso(name):
    """A 3/4 hero angle - the crenellations don't read from a flat top-down
    ortho view the way the plain tray's floor pockets do."""
    center, size = compute_scene_bounds()
    distance = size * 1.6
    cam_data = bpy.data.cameras.new("IsoCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = size * 1.3
    cam = bpy.data.objects.new("IsoCam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = center + mathutils.Vector((distance * 0.6, -distance * 0.9, distance * 0.7))
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam

    light_data = bpy.data.lights.new("IsoLight", type='SUN')
    light_data.energy = 3.0
    light = bpy.data.objects.new("IsoLight", light_data)
    bpy.context.collection.objects.link(light)
    light.location = center + mathutils.Vector((distance * 0.3, -distance * 1.2, distance * 1.5))
    direction = center - light.location
    light.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

    fill_data = bpy.data.lights.new("IsoFillLight", type='SUN')
    fill_data.energy = 1.2
    fill = bpy.data.objects.new("IsoFillLight", fill_data)
    bpy.context.collection.objects.link(fill)
    fill.location = center + mathutils.Vector((-distance * 0.6, distance * 0.3, distance * 1.0))
    fill_direction = center - fill.location
    fill.rotation_euler = fill_direction.to_track_quat('-Z', 'Y').to_euler()

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
# BOX PRIMITIVE
# ============================================================


def make_box(x0, x1, y0, y1, z0, z1, name):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x0 if v.co.x < 0 else x1
        v.co.y = y0 if v.co.y < 0 else y1
        v.co.z = z0 if v.co.z < 0 else z1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return new_object_from_bmesh(bm, name)


# ============================================================
# CASTLE WALL ASSEMBLY
# ============================================================


def build_wall_ring():
    # Full nominal thickness, flush both faces - the brick pattern is cut
    # INTO this afterward (grooves + per-brick recess), not built up as
    # separate raised pieces - see the brick CONFIG comment for why.
    outer = make_box(-HALF - EMBED, HALF + EMBED, -HALF - EMBED, HALF + EMBED,
                      FLOOR_THICKNESS - EMBED, RING_TOP, "ring_outer")
    inner = make_box(-BASIN_HALF, BASIN_HALF, -BASIN_HALF, BASIN_HALF,
                      FLOOR_THICKNESS - EMBED - 1.0, RING_TOP + 1.0, "ring_inner_cut")
    return apply_boolean(outer, inner, 'DIFFERENCE')


def radial_range(sign):
    """(lo, hi) for a merlon's radial (thickness) extent, genuinely
    oversized past the ring's own footprint on BOTH ends - outward past
    the tray's outer edge, inward into the basin - by EMBED.

    An exactly coincident shared face between an additive piece (a
    merlon or tower) and the ring, even with full Z-range overlap, still
    leaves duplicate boundary geometry after the union - confirmed by
    scanning the exported STL for duplicate coplanar triangles at the
    wall boundary, not just a render artifact (a flat-shaded top-down
    render showed a dark seam there first - real z-fighting, not just a
    shadow). Z overlap alone isn't enough; every shared boundary needs
    real volumetric overlap, not just some of them. The resulting
    0.15mm proud nub outward and shallow nub into the basin, at merlon
    locations only, is imperceptible at print scale."""
    if sign > 0:
        return (HALF - WALL_THICKNESS) - EMBED, HALF + EMBED
    return -HALF - EMBED, (-HALF + WALL_THICKNESS) + EMBED


def build_round_tower_mesh(cx, cy, radius, z0, z1, name):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=ROUND_TOWER_SEGMENTS,
                           radius1=radius, radius2=radius, depth=z1 - z0)
    mid_z = (z0 + z1) / 2.0
    for v in bm.verts:
        v.co.x += cx
        v.co.y += cy
        v.co.z += mid_z
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return new_object_from_bmesh(bm, name)


def build_half_cylinder_mesh(cx, cy, radius, z0, z1, cut_x, keep_sign, name):
    """Full cylinder, then trimmed to keep only the keep_sign side of the
    x=cut_x plane - the flat face is where it butts against the square
    (with a small EMBED overlap baked into cut_x by the caller, for a
    genuine union rather than an exact coincident boundary)."""
    full = build_round_tower_mesh(cx, cy, radius, z0, z1, name)
    if keep_sign > 0:
        cutter = make_box(cut_x - radius - 1.0, cut_x, cy - radius - 1.0, cy + radius + 1.0,
                           z0 - 1.0, z1 + 1.0, f"{name}_trim")
    else:
        cutter = make_box(cut_x, cut_x + radius + 1.0, cy - radius - 1.0, cy + radius + 1.0,
                           z0 - 1.0, z1 + 1.0, f"{name}_trim")
    return apply_boolean(full, cutter, 'DIFFERENCE')


def build_mini_merlons():
    """Small raised battlement nubs on top of the pool towers - added on
    top of an otherwise complete flat rim, not a full alternating
    merlon/crenel parapet like the main wall (scope cut - "some
    crenellations", not a precise match, at this small scale)."""
    merlons = []
    hs = SQUARE_TOWER_OUTER / 2.0
    mw = MINI_MERLON_WIDTH
    wall = ROUND_TOWER_WALL

    # West face (fully exposed)
    x0 = SQUARE_POOL_CENTER_X - hs
    for frac in (-0.4, 0.4):
        ny = POOL_CENTER_Y + frac * (2 * hs - mw)
        merlons.append(make_box(x0, x0 + wall, ny - mw / 2.0, ny + mw / 2.0,
                                 SQUARE_TOWER_TOP - EMBED, SQUARE_TOWER_TOP + MINI_MERLON_HEIGHT,
                                 f"sqmerlon_w_{frac}"))
    # North face (POOL_SIGN side, fully exposed)
    y0 = POOL_CENTER_Y + POOL_SIGN * hs
    y1 = y0 - POOL_SIGN * wall
    for frac in (-0.4, 0.4):
        nx = SQUARE_POOL_CENTER_X + frac * (2 * hs - mw)
        lo, hi = (min(y0, y1), max(y0, y1))
        merlons.append(make_box(nx - mw / 2.0, nx + mw / 2.0, lo, hi,
                                 SQUARE_TOWER_TOP - EMBED, SQUARE_TOWER_TOP + MINI_MERLON_HEIGHT,
                                 f"sqmerlon_n_{frac}"))
    # South face (faces into the open basin, fully exposed)
    y0 = POOL_CENTER_Y - POOL_SIGN * hs
    y1 = y0 + POOL_SIGN * wall
    for frac in (-0.4, 0.4):
        nx = SQUARE_POOL_CENTER_X + frac * (2 * hs - mw)
        lo, hi = (min(y0, y1), max(y0, y1))
        merlons.append(make_box(nx - mw / 2.0, nx + mw / 2.0, lo, hi,
                                 SQUARE_TOWER_TOP - EMBED, SQUARE_TOWER_TOP + MINI_MERLON_HEIGHT,
                                 f"sqmerlon_s_{frac}"))

    # Oval curved rim - axis-aligned nubs at a few angles across the outward
    # semicircle (not rotated to the true tangent - a small approximation,
    # acceptable at this scale for "some crenellations").
    ro = ROUND_TOWER_RADIUS
    for angle_deg in (-60.0, -20.0, 20.0, 60.0):
        a = math.radians(angle_deg)
        px = OVAL_CAP_CENTER_X + ro * math.cos(a)
        py = POOL_CENTER_Y + ro * math.sin(a)
        merlons.append(make_box(px - mw / 2.0, px + mw / 2.0, py - mw / 2.0, py + mw / 2.0,
                                 TOWER_TOP - EMBED, TOWER_TOP + MINI_MERLON_HEIGHT,
                                 f"ovalmerlon_{angle_deg}"))
    return merlons


def plain_tower_range(sign):
    """The 2 non-storage corners' own radial extent - same small bulge
    the original (pre-storage-tower) version of this file used at every
    corner: flush with the ring's inner boundary, PLAIN_TOWER_OVERHANG
    past the outer edge."""
    if sign > 0:
        return (HALF - WALL_THICKNESS) - EMBED, HALF + PLAIN_TOWER_OVERHANG
    return -HALF - PLAIN_TOWER_OVERHANG, (-HALF + WALL_THICKNESS) + EMBED


def build_towers():
    """Corner towers are functional dice-storage pods on ONE diagonal
    pair only, on the SAME edge, joined into one connected pool: a
    complete square mini-tower (all 4 sides, own crenellation) with a
    half-cylinder elongation butted flush against its one face (no wide
    connecting corridor - the halves share the same diameter, so they
    line up directly). Solid shapes only - NO cavity cut here. The
    cavity has to be cut later, against the fully-assembled base (see
    build_tower_cavity_cuts) - cutting it into the tower's own
    standalone shape first, then unioning that already-hollow tower onto
    the wall/merlons, leaves the merlon material that was already sitting
    inside the tower's footprint completely untouched (union only ADDS,
    it can't retroactively remove a neighbor's material) - exactly what
    showed up as a solid stub floating inside the cavity. The other edge
    gets the small plain bulge instead."""
    towers = []
    hs = SQUARE_TOWER_OUTER / 2.0
    towers.append(make_box(SQUARE_POOL_CENTER_X - hs, SQUARE_POOL_CENTER_X + hs,
                            POOL_CENTER_Y - hs, POOL_CENTER_Y + hs, 0.0, SQUARE_TOWER_TOP, "pool_square"))
    ro = ROUND_TOWER_RADIUS
    towers.append(build_half_cylinder_mesh(OVAL_CAP_CENTER_X, POOL_CENTER_Y, ro, 0.0, TOWER_TOP,
                                            OVAL_CAP_CENTER_X - EMBED, 1, "pool_oval"))
    towers.extend(build_mini_merlons())
    for sx, sy in PLAIN_TOWER_CORNERS:
        x0, x1 = plain_tower_range(sx)
        y0, y1 = plain_tower_range(sy)
        towers.append(make_box(x0, x1, y0, y1, 0.0, TOWER_TOP, f"plain_tower_{sx}_{sy}"))
    return towers


def build_tower_cavity_cuts():
    """The combined pool's cavity - cut against the fully-assembled base
    (after towers, merlons and walls are all already unioned together),
    so it correctly clears out ANY material in the way, not just the
    tower shapes' own original volume. Square half (42mm wide, 10mm
    walls, cut down to one shared floor depth) meets the oval half
    (same 42mm diameter now, 10mm walls) at that same depth - a true
    connected pool, not two separate wells, and no width mismatch at the
    seam anymore since both halves share the same diameter."""
    hc = SQUARE_TOWER_CAVITY / 2.0
    rc = ROUND_TOWER_CAVITY_DIAM / 2.0
    # The round cavity's trim plane is NOT at its own center (unlike the
    # housing's clean half-cylinder silhouette) - it has to reach all the
    # way back to the square cavity's own boundary to bridge the 10mm
    # wall-thickness zone between the two housings. Trimming it at the
    # center instead would leave that whole zone solid on both sides - a
    # real dividing wall, not a connected pool.
    cuts = [
        make_box(SQUARE_POOL_CENTER_X - hc, SQUARE_POOL_CENTER_X + hc,
                 POOL_CENTER_Y - hc, POOL_CENTER_Y + hc, POOL_FLOOR_Z, SQUARE_TOWER_TOP + 1.0,
                 "pool_square_cavity"),
        build_half_cylinder_mesh(OVAL_CAP_CENTER_X, POOL_CENTER_Y, rc, POOL_FLOOR_Z, TOWER_TOP + 1.0,
                                  SQUARE_POOL_CENTER_X + hc - 0.5, 1, "pool_oval_cavity"),
    ]
    return cuts


def build_merlons(rng):
    """5 merlons per straight run (between the two corner towers of that
    side), evenly spaced with equal-width crenel gaps, each with a small
    random top-height jitter for a weathered-battlement look. Returns
    (objects, layout) - layout carries each merlon's own along-range and
    actual jittered top_z, so a later pass (top-surface seam tracing)
    can trace divisions on each cap that land at its real height, not a
    second independently-drawn one that would be out of sync."""
    run_length = OUTER_SIZE - 2.0 * WALL_THICKNESS  # excludes both corner towers
    unit = run_length / (2 * N_MERLONS - 1)
    run_half = run_length / 2.0

    merlons = []
    layout = []
    # side_key: (fixed_axis, fixed_value_sign) - the wall this run belongs to;
    # the OTHER axis is the one the merlons are spaced along.
    for axis, sign in (("y", 1), ("y", -1), ("x", 1), ("x", -1)):
        fixed_lo, fixed_hi = radial_range(sign)
        for i in range(N_MERLONS):
            along_lo = -run_half + i * 2.0 * unit
            along_hi = along_lo + unit
            top_z = MERLON_TOP + rng.uniform(-HEIGHT_JITTER, HEIGHT_JITTER)
            name = f"merlon_{axis}_{sign}_{i}"
            if axis == "y":
                merlons.append(make_box(along_lo, along_hi, fixed_lo, fixed_hi,
                                         RING_TOP - EMBED, top_z, name))
            else:
                merlons.append(make_box(fixed_lo, fixed_hi, along_lo, along_hi,
                                         RING_TOP - EMBED, top_z, name))
            layout.append({"axis": axis, "sign": sign, "along_lo": along_lo,
                            "along_hi": along_hi, "top_z": top_z})
    return merlons, layout


def normalized_irregular_spans(total, n, rng, lo_frac=0.7, hi_frac=1.3):
    """n spans, each irregular around total/n, normalized to sum EXACTLY
    to total - same trick objective_markers_v1.py uses for its ring
    widths and wedge angles (avoids thin sliver pieces at either end)."""
    base = total / n
    raw = [rng.uniform(base * lo_frac, base * hi_frac) for _ in range(n)]
    scale = total / sum(raw)
    return [r * scale for r in raw]


def build_wall_segment_cuts(rng, radial_axis, along_lo, along_hi, z0, z1, face_pos, out_dir, tag):
    """Generic brick/mortar cutter builder for ANY rectangular wall
    segment - a list of DIFFERENCE cutters: horizontal mortar grooves at
    each internal course boundary, vertical mortar grooves at each
    internal brick boundary within a course (irregular, independently
    randomized per course - no forced running-bond offset, so joints
    land differently row to row on their own), and one full-cell recess
    cutter per brick for the same worn-stone height variation as before,
    just achieved by recessing each brick a random amount rather than
    raising it. Used for the 4 main wall runs AND the corner towers'
    own faces - `radial_axis` is whichever axis the face's normal points
    along ("x" or "y"), `along_lo/hi` spans the OTHER axis."""
    along_span = along_hi - along_lo

    def radial_span(depth):
        a = face_pos + out_dir * CUT_OVERSHOOT
        b = face_pos - out_dir * depth
        return (a, b) if a < b else (b, a)

    def make_cut(a0, a1, r_lo, r_hi, cz0, cz1, name):
        if radial_axis == "y":
            return make_box(a0, a1, r_lo, r_hi, cz0, cz1, name)
        return make_box(r_lo, r_hi, a0, a1, cz0, cz1, name)

    cuts = []
    avg_course_h = (BRICK_H_MIN + BRICK_H_MAX) / 2.0
    n_courses = max(1, round((z1 - z0) / avg_course_h))
    course_heights = normalized_irregular_spans(z1 - z0, n_courses, rng)
    course_bounds = [z0]
    for ch in course_heights:
        course_bounds.append(course_bounds[-1] + ch)

    for cb in course_bounds[1:-1]:
        r_lo, r_hi = radial_span(GROOVE_DEPTH)
        name = f"hgroove_{tag}_{cb:.2f}"
        cuts.append(make_cut(along_lo - 1.0, along_hi + 1.0, r_lo, r_hi,
                              cb - GROOVE_WIDTH / 2.0, cb + GROOVE_WIDTH / 2.0, name))

    for ci in range(n_courses):
        c_z0, c_z1 = course_bounds[ci], course_bounds[ci + 1]
        avg_brick_w = (BRICK_W_MIN + BRICK_W_MAX) / 2.0
        n_bricks = max(1, round(along_span / avg_brick_w))
        widths = normalized_irregular_spans(along_span, n_bricks, rng)
        bounds = [along_lo]
        for w in widths:
            bounds.append(bounds[-1] + w)

        for b in bounds[1:-1]:
            r_lo, r_hi = radial_span(GROOVE_DEPTH)
            name = f"vgroove_{tag}_{ci}_{b:.2f}"
            cuts.append(make_cut(b - GROOVE_WIDTH / 2.0, b + GROOVE_WIDTH / 2.0, r_lo, r_hi,
                                  c_z0 - 0.5, c_z1 + 0.5, name))

        margin = GROOVE_WIDTH * 0.3
        for bi in range(n_bricks):
            a0, a1 = bounds[bi] + margin, bounds[bi + 1] - margin
            depth = GROOVE_DEPTH + rng.uniform(0.0, BRICK_JITTER_DEPTH)
            r_lo, r_hi = radial_span(depth)
            name = f"brickrecess_{tag}_{ci}_{bi}"
            cuts.append(make_cut(a0, a1, r_lo, r_hi, c_z0 + margin, c_z1 - margin, name))
    return cuts


def build_brick_wall_cuts(rng, axis, sign, outer):
    """One of the 4 main wall runs, one face (outer or basin-facing
    inner). Outer coverage now runs the FULL height, z=0 (the floor
    slab's own bottom edge) up through MERLON_TOP - not just the curtain-
    wall band - so the merlons get the same brick treatment "for free":
    courses simply have nothing to cut wherever a crenel gap leaves no
    material at that height, which is a normal, safe no-op for a
    DIFFERENCE cutter. Inner coverage stays FLOOR_THICKNESS up (there's
    no wall material below that on the basin side, just open air)."""
    run_length = OUTER_SIZE - 2.0 * WALL_THICKNESS  # excludes both corner towers
    run_half = run_length / 2.0
    face_pos = sign * HALF if outer else sign * BASIN_HALF
    out_dir = sign if outer else -sign
    z0 = 0.0 if outer else FLOOR_THICKNESS
    tag = f"{axis}_{sign}_{outer}"
    return build_wall_segment_cuts(rng, axis, -run_half, run_half, z0, MERLON_TOP, face_pos, out_dir, tag)


def build_tower_brick_cuts(rng):
    """Square half of the pool gets the same flat-face brick treatment as
    the main walls (its 2 faces exposed to open air - the side facing the
    oval is the internal joint, left smooth same as any hidden seam).
    Oval cap gets horizontal coursing rings only, not full brick-with-
    vertical-joints: at this radius (40mm) relative to a normal brick
    width (~10mm), a real subdivision needs wedge-shaped voussoir stones,
    not the flat rectangular cutters build_wall_segment_cuts assumes - a
    straight box would badly under- or over-cut a ~50 degree arc.
    Deferred rather than approximated wrong; coursed-but-unjointed rings
    still read as dressed stone at this scale. The connecting neck is
    left smooth too (small connecting piece, low visible return)."""
    cuts = []
    hs = SQUARE_TOWER_OUTER / 2.0
    # West face - fully exposed, outward-facing.
    face_w = SQUARE_POOL_CENTER_X - hs
    cuts += build_wall_segment_cuts(rng, "x", POOL_CENTER_Y - hs, POOL_CENTER_Y + hs, 0.0, SQUARE_TOWER_TOP,
                                     face_w, -1, "poolsquare_wface")
    # North face (POOL_SIGN side) - fully exposed, outward-facing.
    face_n = POOL_CENTER_Y + POOL_SIGN * hs
    cuts += build_wall_segment_cuts(rng, "y", SQUARE_POOL_CENTER_X - hs, SQUARE_POOL_CENTER_X + hs,
                                     0.0, SQUARE_TOWER_TOP, face_n, POOL_SIGN, "poolsquare_nface")
    # South face - faces INTO the open basin (the square's footprint reaches
    # well past the main wall's own inner boundary here), fully exposed too.
    face_s = POOL_CENTER_Y - POOL_SIGN * hs
    cuts += build_wall_segment_cuts(rng, "y", SQUARE_POOL_CENTER_X - hs, SQUARE_POOL_CENTER_X + hs,
                                     0.0, SQUARE_TOWER_TOP, face_s, -POOL_SIGN, "poolsquare_sface")
    # East face - only the thin lip above the corridor's own height is
    # actually exposed ("slightly higher" than the oval side); below
    # TOWER_TOP this face is the internal, solid connection to the neck.
    face_e = SQUARE_POOL_CENTER_X + hs
    cuts += build_wall_segment_cuts(rng, "x", POOL_CENTER_Y - hs, POOL_CENTER_Y + hs, TOWER_TOP, SQUARE_TOWER_TOP,
                                     face_e, 1, "poolsquare_eface")

    for sx, sy in PLAIN_TOWER_CORNERS:
        x_lo, x_hi = plain_tower_range(sx)
        y_lo, y_hi = plain_tower_range(sy)
        face_x = x_hi if sx > 0 else x_lo
        cuts += build_wall_segment_cuts(rng, "x", y_lo, y_hi, 0.0, TOWER_TOP,
                                         face_x, sx, f"plaintower_{sx}_{sy}_xface")
        face_y = y_hi if sy > 0 else y_lo
        cuts += build_wall_segment_cuts(rng, "y", x_lo, x_hi, 0.0, TOWER_TOP,
                                         face_y, sy, f"plaintower_{sx}_{sy}_yface")

    avg_course_h = (BRICK_H_MIN + BRICK_H_MAX) / 2.0
    n_courses = max(1, round(TOWER_TOP / avg_course_h))
    course_heights = normalized_irregular_spans(TOWER_TOP, n_courses, rng)
    course_bounds = [0.0]
    for ch in course_heights:
        course_bounds.append(course_bounds[-1] + ch)
    r_outer = ROUND_TOWER_RADIUS + CUT_OVERSHOOT
    r_inner = ROUND_TOWER_RADIUS - GROOVE_DEPTH
    for cb in course_bounds[1:-1]:
        outer = build_round_tower_mesh(OVAL_CAP_CENTER_X, POOL_CENTER_Y, r_outer, cb - GROOVE_WIDTH / 2.0,
                                        cb + GROOVE_WIDTH / 2.0, f"ovalcap_hring_{cb:.2f}_o")
        inner = build_round_tower_mesh(OVAL_CAP_CENTER_X, POOL_CENTER_Y, r_inner, cb - GROOVE_WIDTH / 2.0 - 0.5,
                                        cb + GROOVE_WIDTH / 2.0 + 0.5, f"ovalcap_hring_{cb:.2f}_i")
        cuts.append(apply_boolean(outer, inner, 'DIFFERENCE'))
    return cuts


def build_top_seam_cuts(rng, axis, sign, along_lo, along_hi, z_top):
    """Trace the brick joints onto a flat TOP-facing surface (a merlon
    cap, or the walkway strip between merlons) - one shallow division
    line per internal boundary of an irregular along-span partition,
    same normalized_irregular_spans trick as everywhere else. Cut
    straight down GROOVE_DEPTH across the full radial footprint."""
    along_span = along_hi - along_lo
    avg_w = (BRICK_W_MIN + BRICK_W_MAX) / 2.0
    n = max(1, round(along_span / avg_w))
    if n < 2:
        return []  # too narrow to trace a division meaningfully
    widths = normalized_irregular_spans(along_span, n, rng)
    bounds = [along_lo]
    for w in widths:
        bounds.append(bounds[-1] + w)
    r_lo, r_hi = radial_range(sign)

    cuts = []
    for b in bounds[1:-1]:
        a0, a1 = b - GROOVE_WIDTH / 2.0, b + GROOVE_WIDTH / 2.0
        z0, z1 = z_top - GROOVE_DEPTH - 0.5, z_top + 0.5
        name = f"topseam_{axis}_{sign}_{z_top:.2f}_{b:.2f}"
        if axis == "y":
            cuts.append(make_box(a0, a1, r_lo, r_hi, z0, z1, name))
        else:
            cuts.append(make_box(r_lo, r_hi, a0, a1, z0, z1, name))
    return cuts


def build_all_top_seams(rng, merlon_layout):
    """Every merlon cap, plus every walkway gap between consecutive
    merlons on each wall run (the flat curtain-wall-top strip where no
    merlon sits) - both get the same joint-tracing treatment, so the
    top reads as continuous stonework with the wall below it, not a
    smooth cap sitting on a bricked wall."""
    cuts = []
    for m in merlon_layout:
        cuts += build_top_seam_cuts(rng, m["axis"], m["sign"], m["along_lo"], m["along_hi"], m["top_z"])

    run_length = OUTER_SIZE - 2.0 * WALL_THICKNESS
    run_half = run_length / 2.0
    unit = run_length / (2 * N_MERLONS - 1)
    for axis, sign in (("y", 1), ("y", -1), ("x", 1), ("x", -1)):
        for i in range(N_MERLONS - 1):
            gap_lo = -run_half + (2 * i + 1) * unit
            gap_hi = gap_lo + unit
            cuts += build_top_seam_cuts(rng, axis, sign, gap_lo, gap_hi, RING_TOP)
    return cuts


def build_brick_walls(walls, rng):
    """All 4 walls, both faces (outer + basin-facing inner) - 8 wall-face
    instances, each independently patterned. Tried building this as
    individual raised brick boxes (UNION) first - corrupted at every
    batch size tried (all ~360 joined into one union: volume collapsed
    to ~0; one union per brick, 360 sequential: 20% non-manifold edges;
    batched per wall-face, ~45 bricks each: collapsed to 0 again) -
    EXACT-solver UNION is fragile here regardless of how the work is
    split. Sequential DIFFERENCE cuts on a single always-manifold wall,
    by contrast, already proved solid earlier in this same file (the
    first working version's coursing grooves) - so cut the pattern in
    instead of building it up."""
    total = 0
    for axis, sign in (("y", 1), ("y", -1), ("x", 1), ("x", -1)):
        for outer in (True, False):
            for cut in build_brick_wall_cuts(rng, axis, sign, outer):
                apply_boolean(walls, cut, 'DIFFERENCE')
                total += 1
    for cut in build_tower_brick_cuts(rng):
        apply_boolean(walls, cut, 'DIFFERENCE')
        total += 1
    print(f"  {total} groove/recess cuts applied")
    return walls


def build_castle_walls(rng):
    # Floor unioned in HERE, before the brick cuts - not after, in the
    # caller, like the first working version had it. The brick cutters'
    # outer-face range starts at z=0 (the floor's own bottom edge, see
    # build_brick_wall_cuts), but the ring alone only has material from
    # ~FLOOR_THICKNESS up - cutting before the floor is unioned in makes
    # every cut below that a silent no-op against material that doesn't
    # exist yet. Towers were never affected (they're already part of the
    # ring and already span z=0) - only the plain wall runs' lower band
    # was invisible, exactly matching what showed up as "no seams on the
    # bottom of the walls, but the bastions are fine".
    floor = make_box(-HALF, HALF, -HALF, HALF, 0.0, FLOOR_THICKNESS + EMBED, "castle_tray_base")
    ring = build_wall_ring()
    for tower in build_towers():
        union_onto(ring, tower)
    merlons, merlon_layout = build_merlons(rng)
    for merlon in merlons:
        union_onto(ring, merlon)
    base = union_onto(floor, ring)

    prev_vol = mesh_volume(base)
    for cut in build_tower_cavity_cuts():
        apply_boolean(base, cut, 'DIFFERENCE')
    vol = mesh_volume(base)
    assert 0.0 < vol < prev_vol, (
        f"castle walls: storage cavity cuts did not remove a sane amount of material "
        f"({prev_vol:.1f} -> {vol:.1f}mm3) - likely EXACT-solver corruption."
    )

    prev_vol = mesh_volume(base)
    build_brick_walls(base, rng)
    vol = mesh_volume(base)
    assert 0.0 < vol < prev_vol, (
        f"castle walls: brick/mortar cuts did not remove a sane amount of material "
        f"({prev_vol:.1f} -> {vol:.1f}mm3) - likely EXACT-solver corruption."
    )

    prev_vol = vol
    for cut in build_all_top_seams(rng, merlon_layout):
        apply_boolean(base, cut, 'DIFFERENCE')
    vol = mesh_volume(base)
    assert 0.0 < vol < prev_vol, (
        f"castle walls: top-surface seam cuts did not remove a sane amount of material "
        f"({prev_vol:.1f} -> {vol:.1f}mm3) - likely EXACT-solver corruption."
    )

    apply_bevel(base, BEVEL_WIDTH)
    return base


# ============================================================
# MYTHOS ICON + WORDMARK (ported from build_dice_tray.py in this folder)
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
    return new_object_from_bmesh(bm, name)


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

    rng = random.Random(SEED)
    clear_scene()
    contours = load_contours(MYTHOS_CONTOURS_PATH)
    text_aspect = measure_text_aspect(LOGO_TEXT, MYTHOS_FONT_PATH)
    lockup_k = MYTHOS_ASPECT * (1.0 + GAP_FRAC) + text_aspect

    top_icon_w = min(TOP_BUDGET, TOP_BUDGET / lockup_k, TOP_HEIGHT_BUDGET / lockup_k)
    top_icon_h = top_icon_w * MYTHOS_ASPECT
    top_text_h = top_icon_w * text_aspect

    bottom_icon_w = min(BOTTOM_BUDGET, BOTTOM_BUDGET / lockup_k)
    bottom_icon_h = bottom_icon_w * MYTHOS_ASPECT
    bottom_text_h = bottom_icon_w * text_aspect

    print(f"top lockup: icon {top_icon_w:.1f}x{top_icon_h:.1f}mm, text height {top_text_h:.1f}mm")
    print(f"bottom lockup: icon {bottom_icon_w:.1f}x{bottom_icon_h:.1f}mm, text height {bottom_text_h:.1f}mm")

    base = build_castle_walls(rng)
    base.name = "castle_tray_base"
    cleanup_mesh(base)
    prev_vol = mesh_volume(base)
    print(f"castle walls assembled: volume={prev_vol:.1f}mm3 (non-manifold {nonmanifold_fraction(base):.4f})")
    center, size = compute_scene_bounds()
    xs = [(base.matrix_world @ v.co).x for v in base.data.vertices]
    ys = [(base.matrix_world @ v.co).y for v in base.data.vertices]
    print(f"bounding footprint: {max(xs) - min(xs):.1f} x {max(ys) - min(ys):.1f}mm "
          f"(x=[{min(xs):.1f},{max(xs):.1f}] y=[{min(ys):.1f},{max(ys):.1f}])")

    top_cutter = build_logo_lockup(
        contours, top_icon_w, top_icon_h, top_text_h,
        FLOOR_THICKNESS - POCKET_DEPTH, POCKET_DEPTH + CUT_POKE, "castle_top_cutter",
    )
    place_object(top_cutter, CENTER_X, CENTER_Y, mirror=False, rotate90=False)
    apply_boolean(base, top_cutter, 'DIFFERENCE')

    bottom_cutter = build_logo_lockup(
        contours, bottom_icon_w, bottom_icon_h, bottom_text_h,
        -CUT_POKE, POCKET_DEPTH + CUT_POKE, "castle_bottom_cutter",
    )
    place_object(bottom_cutter, CENTER_X, CENTER_Y, mirror=True, rotate90=False)
    apply_boolean(base, bottom_cutter, 'DIFFERENCE')

    vol = mesh_volume(base)
    assert 0.0 < vol < prev_vol, (
        f"castle_tray: Mythos pocket cuts did not remove a sane amount of material "
        f"({prev_vol:.1f} -> {vol:.1f}mm3) - likely EXACT-solver corruption."
    )
    print(f"castle_tray_base: volume={vol:.1f}mm3 (non-manifold {nonmanifold_fraction(base):.4f})")

    top_insert = build_logo_lockup(
        contours, top_icon_w, top_icon_h, top_text_h,
        FLOOR_THICKNESS - POCKET_DEPTH, POCKET_DEPTH, "castle_top_insert",
    )
    place_object(top_insert, CENTER_X, CENTER_Y, mirror=False, rotate90=False)

    bottom_insert = build_logo_lockup(
        contours, bottom_icon_w, bottom_icon_h, bottom_text_h,
        0.0, POCKET_DEPTH, "castle_bottom_insert",
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
        render_iso("castle_tray_original_hero")
        render_face("castle_tray_original_top", from_below=False)
        render_face("castle_tray_original_bottom", from_below=True)

    if EXPORT_STL:
        export_stl(base, "castle_tray_original_base.stl")
        export_stl(top_insert, "castle_tray_original_top_insert.stl")
        export_stl(bottom_insert, "castle_tray_original_bottom_insert.stl")
    if EXPORT_3MF:
        export_project_3mf(
            [(base, "base", BASE_EXTRUDER_SLOT),
             (top_insert, "top_insert", INLAY_EXTRUDER_SLOT),
             (bottom_insert, "bottom_insert", INLAY_EXTRUDER_SLOT)],
            os.path.join(EXPORT_DIR, "castle_tray_original_anycubic.3mf"))


if __name__ == "__main__":
    main()
