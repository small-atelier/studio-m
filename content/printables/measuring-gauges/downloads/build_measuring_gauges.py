"""
Mythos measuring-tool family (Blender bpy) - genuinely different shapes, built by
one script in three phases:

PHASE 1 - range/engagement gauges (3"/6"/9"): a rectangle with the top-left
corner cut away by a circular arc, so each edge becomes its own ready-made
straight-edge ruler - bottom edge = the gauge's own long value (3"/6"/9"),
top edge = 2" (the arc eats the rest off its left end), right edge = 1",
left edge = 1/2". Lay whichever edge matches the gap you're checking
directly against the two model bases - no reading a position off a taper.
Plus a full run of inch ticks along the bottom edge.

PHASE 2 - charge-measurement sticks (12.5"/13"): a plain rectangle, no
corner cut. Charge distance in both 40k and AoS is 2D6 (2-12"), so this is
a graduated scale rather than a set of fixed edges - inch ticks 1 through
12 along the bottom edge, read "N inches in from the right end." The two
length variants differ only in the blank margin past "12" (1/2" vs 1").

PHASE 3 - rigid triangular tape-measure replacement (24", 2 segments joined
by a glued tenon/socket): a genuinely different construction from the flat
family above - a solid equilateral-triangle prism, not a thin plate, so it
has no front/back duality the way phases 1-2 do. Graduated with inch ticks
1-23 (24" is simply the physical end of the assembled stick, no printed
mark needed), full-width unlabeled lines at the "used distances" (3", 6",
9", 12", 18"), and the Mythos badge in the 1"/2" zone - built once for one
face then duplicated/rotated 120°/240° onto the other two, since an
equilateral prism's three faces are exact rotations of each other. See the
PHASE 3 section below for the segment/joint/marking design in full.

These are genuinely different constructions (arc-cut vs plain rectangle vs
triangular prism, fixed edge labels vs a repeating graduated scale vs a
rotate-and-duplicate multi-face scale) - not just another size variant the
way 3"/6"/9" are of each other - so they get their own CONFIG/shape/label
sections below, but share every generic helper (the bpy/bmesh plumbing,
text/icon builders, export) so that a fix to one - like the icon voxel-
remesh below - doesn't have to be manually ported to a second copy of the
file. Phase 3 keeps its own render pipeline (point_camera/render_shot)
separate from phases 1-2's (render_face/setup_camera_and_light) - a solid
prism's faces need a genuinely different camera convention than a thin
plate's front/back (see PHASE 3's own build_text_solid_face0 docstring for
why, and this project's own history of getting that camera convention
wrong before finally verifying it analytically, not just by eye).

Same GENUINE multi-material FDM technique as blender/tokens/build_tokens.py
and blender/combat-modifiers/build_modifier_tokens.py: every tick/numeral/
badge element is a shallow flush RECESS cut into the shell, with a
same-size INSERT exported as a separate object that drops into it with
zero gap (AMS/ACE-Gen2 style auto filament swap - not paint).

Double-sided, printed FLAT with no supports - same as build_tokens.py, NOT
a stand-on-edge print. Each face's markings are just the shell's own
outermost layers (front pockets recessed from y=0, back pockets recessed
from y=PLATE_T - see face_span), so a single flat print lays both sets of
pockets down as it goes. Every back-face element has its own local geometry
X-mirrored IN PLACE before placement (mesh vertices via mirror_mesh_x for
text, normalized icon-contour u before mapping to world space for the
Mythos icon) so it reads correctly - not backwards - when the piece is
flipped over, without relocating it (mirroring an already-world-space x
around the global origin, tried once for the icon, only worked by luck
while every mirrored element sat at x=0 - see build_icon_solid).

The gauge body itself is ONE polygon extrusion, no booleans at all (see
feedback_functional_parts_pipeline) - this is a functional measuring tool,
so the shape IS the function; only the decoration (ticks, numerals, badge)
is carved in afterward, each category its own combined boolean (see
feedback_blender_boolean_fragility).

Numbers: Arial Black (bold, legible at small recessed size - see
feedback_blender_text_mesh_gotchas). MYTHOS wordmark only: BaskervilleBold,
matching every other Mythos badge in this repo. Badge position is the same
rule on every piece in the family, gauges and sticks alike: centered "1.5
inches in from the right edge."

Run (builds every gauge and every stick in one pass):
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_measuring_gauges.py
"""

import bpy
import bmesh
import json
import math
import mathutils
import os
import zipfile

# ============================================================
# CONFIG shared by both phases (all mm)
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEXT_FONT_PATH = os.path.join(SCRIPT_DIR, "ArialBlack.ttf")   # bold numerals, both faces -
                                                                 # also now the MYTHOS wordmark's
                                                                 # font (see MYTHOS_FONT_PATH)
# BaskervilleBold was the original brand font for the wordmark, but its thin serif strokes
# were part of why "MYTHOS" wasn't printing cleanly (only ~3.9mm tall at MYTHOS_TEXT_SIZE=8) -
# ArialBlack is what every numeral in this family already prints reliably, so the wordmark
# now uses it too (font_path=TEXT_FONT_PATH at both call sites below), even though it's not
# the "correct" brand face - kept defined here in case a real fix (bigger size, a different
# genuinely-bold serif) replaces this later.
MYTHOS_FONT_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "card-stand", "BaskervilleBold.ttf"))
MYTHOS_CONTOURS_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "mythos-logo", "logo_contours_v7.json"))

EXPORT_DIR = os.path.join(SCRIPT_DIR, "output")
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1600, 700)

BASE_COLOR = (0.05, 0.05, 0.05, 1.0)   # preview only - black plate
INLAY_COLOR = (1.0, 1.0, 1.0, 1.0)     # preview only - white ticks/numerals/badge

BASE_EXTRUDER_SLOT = 1    # edit to match your AMS loadout on the day you slice
INLAY_EXTRUDER_SLOT = 2

PLATE_T = 6.0            # overall thickness - "sturdy enough not to flip", 4-10mm range
INSERT_DEPTH = 1.0       # bumped up from the original 0.6 - a test print's red inlay
                          # looked washed out/less saturated than black or white at
                          # that depth (red pigments are typically less opaque on FDM
                          # filament, needing more Z-height to fully hide the color
                          # underneath before it reads as fully saturated). Still tiny
                          # relative to PLATE_T (6mm) or the triangular pieces' own
                          # ~7.3mm apothem, plenty of margin either way.
POCKET_POKE = 0.4        # pocket-cutter overshoot past the face it recesses into
                          # (EMBED pattern - a flush cutter is a degenerate coincident
                          # face for the EXACT solver, see feedback_blender_boolean_fragility)
OVERSHOOT = 0.5           # through-cutter overshoot, for punching a hole clean through
                           # an already-built piece
BEVEL_W = 0.6
BEVEL_SEGMENTS = 3

BOLD_OFFSET = 0.0
TEXT_SPACING = 1.1        # see build_tokens.py - default 1.0 kerning lets some letter
                            # pairs touch, which corrupts the boolean; 1.1 gives margin

RECT_WIDTH = 25.4       # 1" - fixed across every piece in the family
_half_w = RECT_WIDTH / 2.0

# The "current piece under construction" state - reassigned by configure_gauge()
# or configure_stick() right before each build, then read by the shared helpers
# and whichever phase's own shape/label functions. Phases run sequentially in
# main() (every gauge, then every stick), never interleaved, so there's no
# conflict in reusing the same names for both.
RECT_LENGTH = None
_half_l = None
BADGE_CX, BADGE_CZ = None, 0.0   # every piece centers its badge "1.5 inches in from
                                   # the right edge" - one rule, set by both phases'
                                   # own configure_*() so the whole family lines up.

# --- Mythos badge sizing - same on every piece in the family ---
# Driven by HEIGHT, not width, because the traced icon's real ink only fills
# 55.5% of its source image's width and 80.8% of its height (checked directly
# against logo_contours_v5.json) - crop_contours_to_content re-normalizes to
# the real bounding box so icon_w/icon_h map onto actual ink instead of a
# padded box (was the cause of small details - sun rays, stars, the crescent -
# not resolving on the nozzle: they were printing ~45% smaller than the
# nominal size implied). MYTHOS_ICON_H is set to the exact height the old
# MYTHOS_ICON_W=26/MYTHOS_ASPECT combination already produced (13.57mm,
# proven to fit the range-gauge family's tick-height ceiling with margin) -
# icon_w is DERIVED from that height and the crop's real aspect ratio.
MYTHOS_ICON_H = 26.0 * (376.0 / 720.0)
MYTHOS_TEXT_SIZE = 10.0   # bumped from 8.0 to match LABEL_SIZE (the family's own
                            # minimum numeral size) - known to introduce a small
                            # (~0.5%) non-manifold defect on gauge_small specifically
                            # (its badge has only ~12.7mm of clearance before the
                            # corner-cut taper starts eating into height, and this
                            # wordmark's half-width exceeds that) - trying it anyway
                            # to see the actual visual result before deciding whether
                            # to fix via a per-gauge override or accept/rework.

# Numeral size for the two graduated-scale pieces (charge sticks, the 24"
# triangular stick) - both read "a tick from both edges, numeral centered
# between them," so one shared size for both rather than two separately-tuned
# constants that happen to want the same value. NOT used by the gauge family's
# own edge labels (LABEL_SIZE) - those sit in tighter, taper-constrained spots
# and were never part of this "too small" complaint to begin with.
RULER_NUM_SIZE = 17.0

# ============================================================
# GENERIC HELPERS (ported from blender/tokens/build_tokens.py - see that
# script for the fuller rationale on each of these). Shared by both phases.
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
    """Flat (x, z) point loop -> solid prism, extruded along Y (thickness axis)."""
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


def face_span(mirror, depth, poke):
    """(offset, thickness) for an element sitting on the given face - flush
    (poke=0, a real insert) or an oversized pocket CUTTER (poke>0). Front
    face is at y=0 growing into the plate (+Y); back face is at y=PLATE_T
    growing into the plate in -Y."""
    if mirror:
        return (PLATE_T - depth, depth + poke)
    return (-poke, depth + poke)


def rect_points(w, h, x=0.0, z=0.0):
    hw, hh = w / 2.0, h / 2.0
    return [(x - hw, z - hh), (x + hw, z - hh), (x + hw, z + hh), (x - hw, z + hh)]


def load_contours(path):
    with open(path) as f:
        return json.load(f)


def crop_contours_to_content(contours):
    """The traced icon's real artwork doesn't fill its own source image's full
    (0,1)x(0,1) box - checked directly on the Mythos icon: only 55.5% of the
    width and 80.8% of the height is actually used, the rest is dead margin
    baked into every point's normalized (u, v). Since build_icon_solid maps
    u/v directly onto icon_w/icon_h, that margin silently shrinks every real
    feature (sun rays, stars, the crescent) well below what a 0.6mm recess can
    resolve on an FDM nozzle - the "gaps in small details" symptom. Re-normalize
    every point to the content's own tight bounding box so icon_w/icon_h map
    onto real ink, not a padded box - same nominal size, bigger real detail."""
    us = [u for c in contours for u, v in c["points"]]
    vs = [v for c in contours for u, v in c["points"]]
    u0, u1 = min(us), max(us)
    v0, v1 = min(vs), max(vs)
    return [
        {**c, "points": [((u - u0) / (u1 - u0), (v - v0) / (v1 - v0)) for u, v in c["points"]]}
        for c in contours
    ], (v1 - v0) / (u1 - u0)


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

    # font-curve-to-mesh conversion leaves duplicate overlapping verts at the cap-fill
    # boundary - corrupts the EXACT boolean solver if left in, see build_tokens.py
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


def build_icon_solid(contours, icon_w, icon_h, center_x, top_z, mirror, name_prefix, poke=0.0):
    icon_x0 = center_x - icon_w / 2.0
    icon_z0 = top_z - icon_h
    offset, thickness = face_span(mirror, INSERT_DEPTH, poke)

    outer_pts, hole_pts = [], []
    for c in contours:
        # Mirror the NORMALIZED u (0..1) before mapping to world space, so the icon
        # flips within its own footprint regardless of center_x - mirror_points_x
        # (negate world x) mirrored around the GLOBAL origin instead, which only
        # looked right by coincidence back when every badge sat at center_x=0; once
        # the badge moved off-center the back face's icon jumped to the mirror-image
        # position across x=0 instead of staying put and just flipping in place -
        # the "logo on the underside is in the wrong place" bug.
        raw = [((1.0 - u, v) if mirror else (u, v)) for u, v in c["points"]]
        pts = [(icon_x0 + u * icon_w, icon_z0 + v * icon_h) for u, v in raw]
        pts = dedupe_closed_loop(pts)
        (hole_pts if c["hole"] else outer_pts).append(pts)
    assert outer_pts, f"{name_prefix}: traced icon has no outer contours"

    solid = _extrude_profile(outer_pts[0], offset, thickness, f"{name_prefix}_0")
    for i, pts in enumerate(outer_pts[1:], start=1):
        union_onto(solid, _extrude_profile(pts, offset, thickness, f"{name_prefix}_{i}"))
    for i, pts in enumerate(hole_pts):
        cutter = _extrude_profile(pts, offset - OVERSHOOT, thickness + 2 * OVERSHOOT, f"{name_prefix}_hole_{i}")
        apply_boolean(solid, cutter, 'DIFFERENCE')

    # The icon's traced contours (sun/moon/mountain) can leave a marginal
    # self-intersection where two of them touch after unioning - found via a
    # tiny (0.0012) non-manifold fraction on one piece's icon insert at one
    # specific world position, even though the union itself didn't corrupt.
    # remove_doubles didn't clear it (not a duplicate-vertex case), so it's a
    # real self-intersection - a small voxel remesh forces clean manifold
    # topology regardless (same fix as forcing a non-manifold boolean CUTTER
    # clean before using it, just applied to a finished insert instead).
    mod = solid.modifiers.new("ForceManifold", 'REMESH')
    mod.mode = 'VOXEL'
    mod.voxel_size = 0.08   # small relative to the icon's own feature size (rays,
                              # stars) so fine detail survives
    bpy.context.view_layer.objects.active = solid
    bpy.ops.object.modifier_apply(modifier="ForceManifold")

    return solid


def carve_and_collect_inlay(shell, inserts, cutters, name_prefix):
    prev_volume = mesh_volume(shell)
    # A real boolean UNION here, not a plain join - needed once the family grew a
    # piece (phase 3's triangular prism) where full-width tick cutters from two
    # different faces genuinely overlap in 3D near the shared edges (confirmed via
    # a bounding-box check) - a plain join leaves that overlap unresolved, which the
    # following DIFFERENCE then turns into a marginal non-manifold sliver (see
    # feedback_blender_boolean_fragility). Harmless for phases 1-2, where cutters
    # never occupied the same space to begin with.
    cutter_union = cutters[0]
    for c in cutters[1:]:
        cutter_union = union_onto(cutter_union, c)
    cutter_union.name = f"{name_prefix}_cutters"
    apply_boolean(shell, cutter_union, 'DIFFERENCE')
    vol = mesh_volume(shell)
    assert 0.0 < vol < prev_volume, (
        f"{name_prefix}: pocket cut did not remove a sane amount of material "
        f"({prev_volume:.1f} -> {vol:.1f}mm3) - likely EXACT-solver corruption."
    )
    inlay = join_objects(inserts, f"{name_prefix}_inlay")
    return shell, inlay


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
    """Anycubic Slicer Next project-3mf (per-part `extruder` metadata) -
    see build_tokens.py's export_project_3mf for the full rationale."""
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


def reorient_for_print(obj):
    """Build orientation treats Y as thickness, Z as the piece's own length.
    Slicers build along Z, so rotate (x, y, z) -> (x, z, PLATE_T - y) right
    before export - flat on the bed, no supports, both face's pockets intact
    (this is a rotation, determinant +1, not a mirror)."""
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
    center = mathutils.Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2))
    size = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    return center, size


def setup_camera_and_light(center, distance, ortho_scale, from_back=False):
    """Same convention as build_tokens.py's own camera setup - see that
    file's docstring for why: a "walk around and view from behind" flip
    (camera on the opposite Y side, light follows it, both via track_quat
    rather than a hand-picked Euler so roll doesn't flip too)."""
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
    light.rotation_euler = (center - light.location).to_track_quat('-Z', 'Y').to_euler()
    return cam, light


def render_face(name, from_back=False):
    center, size = compute_scene_bounds()
    distance = size * 1.2
    cam, light = setup_camera_and_light(center, distance, size * 1.1, from_back=from_back)
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = RENDER_RESOLUTION
    scene.render.filepath = os.path.join(RENDER_DIR, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {scene.render.filepath}")
    bpy.data.objects.remove(cam, do_unlink=True)
    bpy.data.objects.remove(light, do_unlink=True)


def build_mythos_badge(cx, cz, mirror, tag):
    contours, content_aspect = crop_contours_to_content(load_contours(MYTHOS_CONTOURS_PATH))
    icon_h = MYTHOS_ICON_H
    icon_w = icon_h / content_aspect
    text_h_est = MYTHOS_TEXT_SIZE * 0.7
    inner_gap = 1.0
    content_h = icon_h + inner_gap + text_h_est
    top_z = cz + content_h / 2.0

    inserts, cutters = [], []
    # build_icon_solid is top-anchored (icon_z0 = top_z - icon_h) - pass the badge's
    # own content top directly, NOT a center z (that mismatch overlapped the icon
    # into the text below it and corrupted the combined cutter boolean).
    for poke, bucket in ((0.0, inserts), (POCKET_POKE, cutters)):
        bucket.append(build_icon_solid(contours, icon_w, icon_h, cx, top_z,
                                        mirror, f"mythos_icon_{tag}", poke=poke))

    text_center_z = top_z - icon_h - inner_gap - text_h_est / 2.0
    for poke, bucket in ((0.0, inserts), (POCKET_POKE, cutters)):
        bucket.append(build_text_solid("MYTHOS", MYTHOS_TEXT_SIZE, cx, text_center_z + text_h_est / 2.0,
                                        mirror, poke=poke, font_path=TEXT_FONT_PATH)[0])

    return inserts, cutters


def export_piece(name, base, inlay):
    base_vol, inlay_vol = mesh_volume(base), mesh_volume(inlay)
    base_nm, inlay_nm = nonmanifold_fraction(base), nonmanifold_fraction(inlay)
    print(f"{name}: base volume={base_vol:.1f}mm3 (non-manifold {base_nm:.4f})  "
          f"inlay volume={inlay_vol:.1f}mm3 (non-manifold {inlay_nm:.4f})")
    assert base_vol > 0.0, f"{name}: base has zero/negative volume - a boolean likely emptied it"
    assert inlay_vol > 0.0, f"{name}: inlay has zero/negative volume - a boolean likely emptied it"

    apply_color(base, "base_black", BASE_COLOR)
    apply_color(inlay, "inlay_white", INLAY_COLOR)

    # Render BEFORE reorienting - the render camera uses the build orientation
    # (Y = thickness), same as every other project's render step in this repo.
    render_face(f"{name}_front", from_back=False)
    render_face(f"{name}_back", from_back=True)

    reorient_for_print(base)
    reorient_for_print(inlay)

    export_stl(base, f"{name}_base.stl")
    export_stl(inlay, f"{name}_inlay.stl")
    export_project_3mf(
        [(base, "base", BASE_EXTRUDER_SLOT), (inlay, "inlay", INLAY_EXTRUDER_SLOT)],
        os.path.join(EXPORT_DIR, f"{name}_anycubic.3mf"))


# ============================================================
# PHASE 1 - RANGE/ENGAGEMENT GAUGES (3"/6"/9", corner-cut construction)
# ============================================================
#
# Start from a plain L"x1" rectangle (L = 3, 6, or 9 - see GAUGES below), centered
# on the origin. Cut the top-left corner away with a circular arc so that:
#   - bottom edge (full)                = L"    (unaffected reference edge)
#   - top edge (opposite the L" edge)   = 2"    (arc eats the rest off its left end)
#   - right edge (full)                 = 1"    (unaffected reference edge)
#   - left edge (opposite the 1" edge)  = 1/2"  (arc eats 1/2" off its top end)
# i.e. each of the 4 numbers is a real usable straight edge of the piece, not a
# position read off a taper - lay the relevant edge directly against what you're
# checking. The three gauges in the family only differ in the LONG edge (3"/6"/9",
# i.e. "elongating the thin part") - the short edge (1") and left edge (1/2") are
# identical on all three, so only RECT_LENGTH and the labels/positions that
# depend on it change between them.

CUT_TOP_REMAIN = 50.8    # 2" - default remaining straight length of the top edge after
                          # the cut; overridden per-gauge by configure_gauge's own
                          # cut_top_remain_in param (see the 3"-secondary variants below)
CUT_LEFT_REMAIN = 12.7   # 1/2" - default remaining straight length of the left edge
                          # after the cut; overridden per-gauge by configure_gauge's own
                          # left_remain_in param (range_gauge_369 uses 1" instead)
BADGE_CZ = 0.0
LONG_LABEL_CX_3IN = 19.0   # the 3" gauge's own already-published long-edge-label position

# small in-between graduation ticks: one full run of inch marks along the bottom
# (full) edge, 1" through (long_in - 1)" in from the right end, plus the one 1"
# mark on the top (2"-remaining) edge - same convention on every gauge, just more
# of them as the bottom edge gets longer.
TICK_LEN = 3.0
TICK_THICK = 1.2
CUT_ARC_SEGMENTS = 16

LABEL_SIZE = 10.0
LABEL_INSET = 4.5           # inboard offset from an edge to its numeral's center
SIDE_LABEL_INSET = 2.5      # tighter inset for "1"/"1/2" only, closer to their edges


def configure_gauge(long_in, long_label, top_label_cx=None, long_label_cx=None, cut_top_remain_in=2.0,
                     width_in=1.0, left_remain_in=0.5, label_size=10.0, badge_text_size=10.0,
                     left_label_cx=None):
    """Set every geometry global that depends on the long edge's length. Called
    once per gauge in GAUGES, right before building it.

    The top-left cut always removes exactly (long_in - cut_top_remain_in)" off the
    top edge to leave a cut_top_remain_in" remaining run - normally 2" (the family's
    original secondary edge), but the 6"/9" gauges also get an EXTRA variant at 3"
    (AoS Pile-In distance) instead, printed and tested alongside the 2" ones rather
    than replacing them. On the 3" gauge that 2" cut is a small 1" nick, but on the
    6"/9" gauges it's 4"/7" (or 3"/6" for the 3"-secondary variants), a genuinely
    large taper eating most of the left half of the plate. The top boundary is
    reduced anywhere under that taper; the BOTTOM edge is never touched by the cut,
    so anything bottom-anchored (the long-edge label) is safe at any x, but the
    vertically-centered badge and the top-anchored secondary-edge label are not -
    they have to live in the guaranteed-full-height flat zone from _ARC_P_TOP.x to
    +half_l, which is always exactly cut_top_remain_in" wide regardless of
    RECT_LENGTH (a bigger cut_top_remain_in actually WIDENS that zone, so the 3"
    variants have more headroom for the badge than the original 2" ones, not less)."""
    global RECT_LENGTH, _half_l, _half_w, _ARC_P_TOP, _ARC_P_LEFT, CUT_CENTER, CUT_RADIUS
    global CUT_TOP_REMAIN, CUT_LEFT_REMAIN, LABEL_SIZE, MYTHOS_TEXT_SIZE
    global LONG_LABEL, LONG_LABEL_CX, TOP_LABEL, TOP_LABEL_CX, SHORT_LABEL, LEFT_LABEL, LEFT_LABEL_CX
    global BADGE_CX, TICKS

    RECT_LENGTH = long_in * 25.4
    _half_l = RECT_LENGTH / 2.0
    # Numeral size defaults to the family's usual 10.0 - gauge_medium uses
    # RULER_NUM_SIZE (17.0) instead, matching the charge sticks/24" stick's own
    # numerals rather than the smaller size every other gauge still uses.
    LABEL_SIZE = label_size
    # Badge wordmark size defaults to the shared MYTHOS_TEXT_SIZE (10.0, used by
    # every other piece in the family) - gauge_small overrides to 8.0 specifically:
    # at 10.0 the wider "MYTHOS" collides with BOTH the "1/2" label (left) and the
    # "3" long-edge label (right/bottom) on this piece alone - confirmed visually,
    # not just as a manifold-percentage abstraction - since gauge_small crams the
    # badge, "1/2", "1", and the long-edge label into the tightest space in the
    # whole family. Every other gauge has enough room at 10.0.
    MYTHOS_TEXT_SIZE = badge_text_size
    # Width defaults to the family's usual 1" (matching RECT_WIDTH) - overridden for
    # gauge_medium, the one variant that isn't 1" wide. Every other gauge passes
    # the default, so _half_w keeps its usual value for them.
    _half_w = (width_in * 25.4) / 2.0
    SHORT_LABEL = str(int(width_in)) if width_in == int(width_in) else str(width_in)
    CUT_TOP_REMAIN = cut_top_remain_in * 25.4
    # Left-edge remaining run defaults to the family's usual 1/2" - overridden for
    # range_gauge_369 (1" instead), same override pattern as width_in above.
    CUT_LEFT_REMAIN = left_remain_in * 25.4
    LEFT_LABEL = "1/2" if left_remain_in == 0.5 else (
        str(int(left_remain_in)) if left_remain_in == int(left_remain_in) else str(left_remain_in))
    # Same default formula this label always used, now overridable per-gauge -
    # gauge_small nudges it further left (toward its own edge, away from the
    # badge) to clear the wider MYTHOS_TEXT_SIZE=10 wordmark.
    LEFT_LABEL_CX = left_label_cx if left_label_cx is not None else -_half_l + SIDE_LABEL_INSET + LABEL_SIZE
    # the two points the arc must connect, replacing the top-left corner (-half_l, half_w)
    _ARC_P_TOP = (-_half_l + (RECT_LENGTH - CUT_TOP_REMAIN), _half_w)     # on the top edge
    # Measured UP from the bottom-left corner (always at -_half_w, untouched by the
    # cut) by CUT_LEFT_REMAIN - that's what actually makes the remaining straight
    # run equal CUT_LEFT_REMAIN. The old `_half_w - CUT_LEFT_REMAIN` (measuring DOWN
    # from the top instead) only produces that same result when CUT_LEFT_REMAIN
    # happens to be exactly half the width - true for every gauge up to now (1/2" on
    # a 1" width), which is why this stayed hidden until width_in and left_remain_in
    # became independently configurable (range_gauge_369: 1" remain on a 3" width -
    # the old formula silently gave a 2" edge instead of the intended 1").
    _ARC_P_LEFT = (-_half_l, -_half_w + CUT_LEFT_REMAIN)                   # on the left edge

    # Literally "take the rectangle, cut the corner off with a circle": center the
    # circle directly on the corner's own x (the left edge's line), then move it
    # straight up until it passes through both boundary points. This is the
    # construction that keeps the arc's x AND z both monotonic along its length -
    # earlier attempts placed the center off on the chord's perpendicular bisector,
    # which numerically checked out as "concave" (farther from the corner than the
    # straight chord) but still let z dip down and back up near the left-edge end,
    # a visible wiggle. Solved by requiring center.x == corner.x == _ARC_P_LEFT.x.
    _dx = -_half_l - _ARC_P_TOP[0]
    cut_center_z = (_dx ** 2 + _ARC_P_TOP[1] ** 2 - _ARC_P_LEFT[1] ** 2) / (2.0 * (_ARC_P_TOP[1] - _ARC_P_LEFT[1]))
    CUT_CENTER = (-_half_l, cut_center_z)
    CUT_RADIUS = cut_center_z - _ARC_P_LEFT[1]

    LONG_LABEL = long_label
    flat_zone_x0 = _ARC_P_TOP[0]   # x where the boundary is back to full half_w height
    # Bottom-anchored (see docstring above) so it's free to sit anywhere in x - moved
    # off toward the slimmer/tapered end, away from the badge, on the new long gauges.
    # -25.4 is the taper's own midpoint - works out to a fixed constant regardless of
    # RECT_LENGTH (the halves of (-half_l) and (flat_zone_x0 = half_l-50.8) cancel:
    # (-half_l + half_l-50.8)/2 = -25.4 always). BUT the per-inch tick grid's offset
    # from x=0 depends on half_l mod 25.4, which differs between gauges (76.2mm
    # divides evenly by 25.4, 114.3mm doesn't) - so -25.4 lands exactly ON a tick for
    # the 6" gauge (checked numerically) while landing cleanly between two ticks for
    # the 9" gauge. GAUGES passes an explicit -12.7 for the 6" gauge to dodge that;
    # the 3" gauge keeps its own already-published position instead (LONG_LABEL_CX_3IN
    # =19, near the badge - the taper's too small there for this to be a problem).
    LONG_LABEL_CX = long_label_cx if long_label_cx is not None else -25.4
    # Badge centers on "1.5 inches in from the right edge" on every gauge in the
    # family - one uniform rule, no per-gauge special-casing needed, because it
    # happens to already equal the 3" gauge's own published position (half_l=38.1,
    # so half_l-38.1=0 exactly) while landing safely inside the guaranteed-full-
    # height flat zone on the 6"/9" gauges too.
    BADGE_CX = _half_l - 38.1
    TOP_LABEL = str(int(cut_top_remain_in)) if cut_top_remain_in == int(cut_top_remain_in) else str(cut_top_remain_in)
    # Anchored to BADGE_CX (+23.3, the clearance the original 2"-secondary 6"/9"
    # gauges already had between their badge and top label) rather than to
    # flat_zone_x0: flat_zone_x0 itself shifts left by a full inch once
    # cut_top_remain_in goes from 2" to 3", which walked the old
    # flat_zone_x0+36.0 default straight onto the badge - a real boolean
    # corruption (shell volume collapsed to 0), not just visual crowding.
    TOP_LABEL_CX = top_label_cx if top_label_cx is not None else BADGE_CX + 23.3

    TICKS = ([("bottom", i) for i in range(1, int(long_in))]
             + [("top", i) for i in range(1, int(cut_top_remain_in))]
             + [("right", i) for i in range(1, int(width_in))])


GAUGES = [
    # "2"/"3"/"1/2" nudged ~5mm (a bit under 1/4") toward their own edges, away from
    # the badge - MYTHOS_TEXT_SIZE=10 wordmark collided with both "1/2" and "3" at
    # their original (pre-nudge) positions on this piece specifically (confirmed
    # visually), the tightest layout in the family.
    {"name": "small", "long_in": 3.0, "long_label": "3",
     "top_label_cx": LONG_LABEL_CX_3IN + 5.0, "long_label_cx": LONG_LABEL_CX_3IN + 5.0,
     "cut_top_remain_in": 2.0, "left_label_cx": -38.1 + SIDE_LABEL_INSET + 10.0 - 5.0},
    # medium: a 3"/6"/9" gauge - same corner-cut construction as the rest of the
    # family, just with the WIDTH itself bumped from the usual 1" up to 3" (so the
    # short/right edge reads "3") and the secondary/top edge set to 6" instead of
    # 2"/3" - all three numbers stay real, usable straight edges. Left edge bumped
    # to 1" too (left_remain_in), instead of the family's usual 1/2". Uses
    # RULER_NUM_SIZE for its numerals instead of the smaller default LABEL_SIZE -
    # matches the charge sticks/24" stick's own numeral size.
    #
    # No standalone plain 6"/9" gauges any more - medium's own top/bottom edges
    # (6"/9") already cover what those would have provided, on top of the 3"/1"
    # edges neither of them had, so keeping them separate was pure redundancy.
    {"name": "medium", "long_in": 9.0, "long_label": "9",
     "top_label_cx": None, "long_label_cx": None, "cut_top_remain_in": 6.0, "width_in": 3.0,
     "left_remain_in": 1.0, "label_size": RULER_NUM_SIZE},
]


def gauge_outline_points():
    """One closed (x, z) loop for the whole body - a rectangle with the
    top-left corner replaced by a circular arc (see CUT_RADIUS/CUT_CENTER
    above). Single polygon, single extrusion for the shell - no booleans in
    the body itself (see feedback_functional_parts_pipeline)."""
    angle_top = math.atan2(_ARC_P_TOP[1] - CUT_CENTER[1], _ARC_P_TOP[0] - CUT_CENTER[0])
    angle_left = math.atan2(_ARC_P_LEFT[1] - CUT_CENTER[1], _ARC_P_LEFT[0] - CUT_CENTER[0])
    arc_pts = []
    for i in range(CUT_ARC_SEGMENTS + 1):
        t = i / CUT_ARC_SEGMENTS
        a = angle_top + (angle_left - angle_top) * t
        arc_pts.append((CUT_CENTER[0] + CUT_RADIUS * math.cos(a), CUT_CENTER[1] + CUT_RADIUS * math.sin(a)))

    return [
        (-_half_l, -_half_w),
        (_half_l, -_half_w),
        (_half_l, _half_w),
        *arc_pts,
    ]


def build_edge_labels(mirror, tag):
    """Each number is a real usable edge of the piece, not a taper
    position: the long-edge label on the full bottom edge, the top-edge
    label on the top edge's remaining straight run, SHORT_LABEL (normally
    "1", "3" for range_gauge_369) on the full right edge, LEFT_LABEL
    (normally "1/2", "1" for range_gauge_369) on the left edge's
    remaining straight run."""
    inserts, cutters = [], []

    def measured_height(label):
        # curve_data.size is nominal, not the real rendered height (ArialBlack at
        # size 10 measures ~5.2mm tall, not 10) - build_text_solid's z is TOP-
        # anchored, so any "bottom" or "center" placement needs the REAL height,
        # not a guess, or it lands in the wrong place.
        probe = _build_flat_text_mesh(label, LABEL_SIZE, INSERT_DEPTH)
        h = max(v.co.y for v in probe.data.vertices) - min(v.co.y for v in probe.data.vertices)
        bpy.data.objects.remove(probe, do_unlink=True)
        return h

    def place(label, x, z, anchor='top'):
        # Same (x, z) on both faces - these labels are tied to fixed physical edges,
        # not mirrored positions. Only the glyph itself needs to read correctly when
        # flipped, which build_text_solid's own mirror handling already does.
        if anchor == 'top':
            top_z = z
        elif anchor == 'bottom':
            top_z = z + measured_height(label)
        else:
            top_z = z + measured_height(label) / 2.0
        for poke, bucket in ((0.0, inserts), (POCKET_POKE, cutters)):
            glyph, _, _ = build_text_solid(label, LABEL_SIZE, x, top_z, mirror, poke=poke)
            bucket.append(glyph)

    place(TOP_LABEL, TOP_LABEL_CX, _half_w - LABEL_INSET, anchor='top')
    place(LONG_LABEL, LONG_LABEL_CX, -_half_w + LABEL_INSET, anchor='bottom')
    place(SHORT_LABEL, _half_l - SIDE_LABEL_INSET - LABEL_SIZE / 2.0, 0.0, anchor='center')
    left_run_cz = (_ARC_P_LEFT[1] + -_half_w) / 2.0
    place(LEFT_LABEL, LEFT_LABEL_CX, left_run_cz, anchor='center')

    return inserts, cutters


def build_ticks(mirror, tag):
    """Small in-between graduation marks per TICKS - each one starts right at its
    edge and extends inward by TICK_LEN, same physical (x, z) on both faces (a
    plain rectangle has no "reading direction" to mirror, unlike the numerals).

    "right" ticks (the short/width edge, only present when width_in > 1" -
    range_gauge_369's 3" edge) run the other way from "bottom"/"top": fixed near
    x=+half_l, spaced in z counting up from the bottom-right corner - a 90°
    rotation of the same construction, since that edge is graduated top-to-bottom
    instead of left-to-right."""
    inserts, cutters = [], []
    for edge, inches in TICKS:
        for poke, bucket in ((0.0, inserts), (POCKET_POKE, cutters)):
            offset, thickness = face_span(mirror, INSERT_DEPTH, poke)
            if edge == "right":
                x = _half_l - TICK_LEN / 2.0
                z = -_half_w + inches * 25.4
                pts = rect_points(TICK_LEN, TICK_THICK, x=x, z=z)
            else:
                x = _half_l - inches * 25.4
                z = (-_half_w + TICK_LEN / 2.0) if edge == "bottom" else (_half_w - TICK_LEN / 2.0)
                pts = rect_points(TICK_THICK, TICK_LEN, x=x, z=z)
            bucket.append(_extrude_profile(pts, offset, thickness, f"tick_{edge}_{inches}in_{tag}"))
    return inserts, cutters


def build_gauge():
    shell = _extrude_profile(gauge_outline_points(), 0.0, PLATE_T, "gauge_shell")
    apply_bevel(shell, BEVEL_W, BEVEL_SEGMENTS)

    inserts, cutters = [], []
    for mirror, tag in ((False, "front"), (True, "back")):
        label_ins, label_cut = build_edge_labels(mirror, tag)
        tick_ins, tick_cut = build_ticks(mirror, tag)
        badge_ins, badge_cut = build_mythos_badge(BADGE_CX, BADGE_CZ, mirror, tag)
        inserts += label_ins + tick_ins + badge_ins
        cutters += label_cut + tick_cut + badge_cut

    return carve_and_collect_inlay(shell, inserts, cutters, "engagement_gauge")


# ============================================================
# PHASE 2 - CHARGE-MEASUREMENT STICKS (12.5"/13", plain rectangle)
# ============================================================
#
# No corner cut this time means no tick-height ceiling to fight - the full
# 25.4mm plate height is available everywhere along the stick's length. The
# only thing to watch is the badge's own footprint blocking a couple of the
# inch marks in the middle of the stick - handled by dropping whichever
# marks' NUMERALS fall inside the badge's x-span (the ticks themselves stay -
# they're a thin nub right at the edge, a different z-band from the badge,
# so they don't actually collide - only the taller numerals do).

MARK_TICK_LEN = 2.0   # short enough that even the ticks kept right next to the
                       # badge (numeral dropped, tick stays) clear its z-range
                       # with margin - at 3.0 the tick's own upper edge (-9.7mm)
                       # crept 0.4mm into the badge's lower edge (-10.1mm), a
                       # coincident-face sliver the EXACT solver flagged as a
                       # tiny (0.0001) non-manifold fraction on the 13" stick
MARK_TICK_THICK = 1.2
# RULER_NUM_SIZE (shared, see CONFIG) is capped below 22 - at that size "11"/"10"
# (adjacent marks, only 25.4mm apart) crowded to the point of nearly touching.
BADGE_HALF_W_GUESS = 15.0   # generous overestimate of the badge's real half-width,
                             # used only to decide which mark numerals to drop


def measured_mark_height(label):
    probe = _build_flat_text_mesh(label, RULER_NUM_SIZE, INSERT_DEPTH)
    h = max(v.co.y for v in probe.data.vertices) - min(v.co.y for v in probe.data.vertices)
    bpy.data.objects.remove(probe, do_unlink=True)
    return h


def configure_stick(length_in):
    global RECT_LENGTH, _half_l, _half_w, BADGE_CX
    RECT_LENGTH = length_in * 25.4
    _half_l = RECT_LENGTH / 2.0
    # Reset explicitly - Phase 1's own configure_gauge can leave _half_w at a
    # non-default width (range_gauge_369, 3" wide), and build_marks below reads
    # _half_w directly, not RECT_WIDTH - without this reset, Phase 2 would
    # silently inherit whatever width Phase 1's last gauge left behind.
    _half_w = RECT_WIDTH / 2.0
    BADGE_CX = _half_l - 38.1   # same "1.5 inches in from the right edge" rule as
                                 # every gauge in the family


STICKS = [
    {"name": "charge_13in", "length_in": 13.0},
    {"name": "charge_12_5in", "length_in": 12.5},
]


def stick_outline_points():
    return rect_points(RECT_LENGTH, RECT_WIDTH)


def build_marks(mirror, tag):
    """Inch ticks 1-12, measured in from the right end (same convention as
    the range-gauge family) - a tick from BOTH edges, numeral centered between
    them (matches the tape-measure-replacement stick's own both-sides layout -
    reads the same regardless of which way the stick is oriented, and leaves
    the numeral much more vertical room to be sized up)."""
    inserts, cutters = [], []

    def clears_badge(x):
        return abs(x - BADGE_CX) > BADGE_HALF_W_GUESS

    for n in range(1, 13):
        x = _half_l - n * 25.4
        label = str(n)
        if n == 12:
            # The max-charge mark gets a full-width crossing tick instead of the
            # usual short nub - it's the one distance worth reading at a glance
            # without hunting for a number, so it doesn't get one.
            for poke, bucket in ((0.0, inserts), (POCKET_POKE, cutters)):
                offset, thickness = face_span(mirror, INSERT_DEPTH, poke)
                pts = rect_points(MARK_TICK_THICK, RECT_WIDTH, x=x, z=0.0)
                bucket.append(_extrude_profile(pts, offset, thickness, f"tick_{n}in_{tag}"))
            continue

        for poke, bucket in ((0.0, inserts), (POCKET_POKE, cutters)):
            offset, thickness = face_span(mirror, INSERT_DEPTH, poke)
            for z in (-_half_w + MARK_TICK_LEN / 2.0, _half_w - MARK_TICK_LEN / 2.0):
                pts = rect_points(MARK_TICK_THICK, MARK_TICK_LEN, x=x, z=z)
                bucket.append(_extrude_profile(pts, offset, thickness, f"tick_{n}in_{tag}_{z:.1f}"))

        # The ticks stay on every mark - thin nubs right at the edges, safely
        # clear of the badge regardless of x (different z-band). Only the
        # NUMERAL, which now spans most of the plate's own height, gets dropped
        # when it would land inside the badge's footprint.
        if clears_badge(x):
            half_h = measured_mark_height(label) / 2.0
            for poke, bucket in ((0.0, inserts), (POCKET_POKE, cutters)):
                glyph, _, _ = build_text_solid(label, RULER_NUM_SIZE, x, half_h, mirror, poke=poke)
                bucket.append(glyph)

    return inserts, cutters


def build_stick():
    shell = _extrude_profile(stick_outline_points(), 0.0, PLATE_T, "stick_shell")
    apply_bevel(shell, BEVEL_W, BEVEL_SEGMENTS)

    inserts, cutters = [], []
    for mirror, tag in ((False, "front"), (True, "back")):
        mark_ins, mark_cut = build_marks(mirror, tag)
        badge_ins, badge_cut = build_mythos_badge(BADGE_CX, BADGE_CZ, mirror, tag)
        inserts += mark_ins + badge_ins
        cutters += mark_cut + badge_cut

    return carve_and_collect_inlay(shell, inserts, cutters, "charge_stick")


# ============================================================
# PHASE 3 - TRIANGULAR TAPE-MEASURE REPLACEMENT (24", 2 segments)
# ============================================================
#
# A solid equilateral-triangle prism, not a thin plate - no front/back duality the
# way phases 1-2 have, so markings are built once per FACE (3 of them), not twice
# per SIDE. Two 12" segments (24" assembled) joined by a shoulder-stopped glued
# tenon/socket - the socket is a blind pocket carved INTO segment A's own 12"
# length (doesn't add to it), so the assembled length is exactly the sum of each
# segment's own nominal length regardless of tenon depth.
#
# Marking scheme: full-width unlabeled lines at 3"/6"/9"/12"/18" ("the used
# distances" - 3/6/9 mirror the gauge family's own edges, 12" is the short/
# specialist weapon range in both games, 18" is the stock tape measure's own
# length plus a common AoS spell-range bracket); every other inch gets a normal
# tick-from-both-edges + centered numeral; no mark at 1"/2" (the Mythos badge
# lives there instead, same "1.5 inches in from the right edge" rule as every
# other piece in the family); no mark at 24" (it's simply the physical end).
#
# Built once for face 0 (the bottom/base face, in its own local x=length,
# y=width, z=depth frame - happens to need no rotation relative to world axes),
# then duplicated and rotated 120°/240° around the stick's own long axis onto
# the other two faces - valid because an equilateral prism's three faces are
# exact rotations of each other.

SEGMENT_LEN = 12 * 25.4      # 304.8mm - each segment's own body length
TOTAL_LEN = 2 * SEGMENT_LEN  # 609.6mm (24") assembled
TRI_SIDE = 25.4              # equilateral triangle side - matches the family's "1 inch" width
TRI_HALF = TRI_SIDE / 2.0
_TRI_H = TRI_SIDE * math.sqrt(3.0) / 2.0
BASE_Z = -_TRI_H / 3.0        # z of the base (bottom) face, for a triangle centered at (0,0)

TRI_BEVEL_W = 0.4             # own bevel constants, not BEVEL_W/BEVEL_SEGMENTS - a
TRI_BEVEL_SEGMENTS = 2         # deliberately lighter edge treatment than phases 1-2's

TENON_DEPTH = 20.0            # how far the tenon reaches into the socket
SOCKET_SCALE = 0.72           # socket cross-section as a fraction of the outer triangle
TENON_SCALE = 0.68            # tenon cross-section - smaller than the socket for glue clearance
UNION_OVERLAP = 1.0           # real volumetric overlap for the tenon-to-body union (see
                               # feedback_blender_boolean_fragility - a coincident seam
                               # doesn't fuse cleanly, needs actual overlap)

TRI_TICK_LEN = 2.0
TRI_TICK_THICK = 1.2
TRI_FULL_TICK_THICK = 1.8     # heavier than normal ticks - visual weight for the
                               # "used distances" lines
# Numeral size is RULER_NUM_SIZE (shared, see CONFIG) - same value as the charge
# sticks, not a separate TRI_-prefixed constant, since both are "tick from both
# edges, numeral centered" graduated scales.
TRI_BADGE_X = TOTAL_LEN - 38.1   # "1.5 inches in from the right edge" - same rule as
                                   # the rest of the family

FULL_WIDTH_NS = {3, 6, 9, 12, 18}
SKIP_NS = {1, 2, 24}
SEGMENT_A_NS = [n for n in range(12, 25) if n not in SKIP_NS]   # 12..23
SEGMENT_B_NS = [n for n in range(1, 12) if n not in SKIP_NS]    # 3..11


def triangle_yz(side, cy=0.0, cz=0.0):
    """Equilateral triangle in the Y-Z plane, side length `side`, centered on its own
    centroid at (cy, cz), base edge down (-Z), apex up (+Z) - prints flat, base-down."""
    h = side * math.sqrt(3.0) / 2.0
    base_z = cz - h / 3.0
    apex_z = cz + 2.0 * h / 3.0
    return [
        (cy - side / 2.0, base_z),
        (cy + side / 2.0, base_z),
        (cy, apex_z),
    ]


def extrude_profile_x(points_yz, x0, length, name):
    """Y-Z point loop -> solid prism, extruded along +X (the stick's long axis)."""
    bm = bmesh.new()
    verts = [bm.verts.new((x0, p[0], p[1])) for p in points_yz]
    face = bm.faces.new(verts)
    result = bmesh.ops.extrude_face_region(bm, geom=[face])
    new_verts = [v for v in result['geom'] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(length, 0.0, 0.0), verts=new_verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def face0_span(depth, poke):
    """(offset, thickness) along world Z for a recess/insert on face 0 - mirrors
    face_span() in the flat family, just using Z as the depth axis instead of Y
    (face 0's own local frame happens to need no rotation relative to world axes)."""
    return (BASE_Z - poke, depth + poke)


def _extrude_profile_face0(points_xy, z0, thickness, name):
    """(x, y) profile -> solid prism extruded along +Z, for marks on face 0."""
    bm = bmesh.new()
    verts = [bm.verts.new((p[0], p[1], z0)) for p in points_xy]
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


def build_text_solid_face0(text, size, center_x, edge_y, anchor, poke=0.0, font_path=TEXT_FONT_PATH):
    """anchor='min' anchors the text's lowest-y edge at edge_y (text extends toward +y);
    anchor='center' centers the text on edge_y.

    Face 0's real outward viewing direction is +Z - the opposite side of the material
    from how a font glyph is natively authored (which assumes a -Z-looking viewer, the
    standard screen/print convention). Viewing a flat shape from the opposite side of
    the material it's drawn on always flips one axis - there's no camera angle that
    avoids this, only a choice of which axis flips. A local-X mirror here is the
    conventional fix for exactly this situation (the same trick used for mirror-written
    text meant to be read in a rear-view mirror): it keeps the glyph upright and just
    reverses it, which a +Z view then un-reverses back to correct, upright, correctly-
    ordered text. Confirmed analytically (checking which world axis maps to which
    camera-space axis under both viewing directions, not just eyeballing a render -
    render angle alone is easy to misjudge for this) and confirmed visually with a
    matching corrected camera - see point_camera below."""
    offset, thickness = face0_span(INSERT_DEPTH, poke)
    obj = _build_flat_text_mesh(text, size, thickness, font_path)
    mirror_mesh_x(obj)
    local_ys = [v.co.y for v in obj.data.vertices]
    local_top, local_bottom = max(local_ys), min(local_ys)
    mid_z = offset + thickness / 2.0
    if anchor == 'min':
        y_shift = edge_y - local_bottom
    else:
        y_shift = edge_y - (local_top + local_bottom) / 2.0
    obj.location = (center_x, y_shift, mid_z)
    apply_transform(obj)
    return obj, local_top - local_bottom


def build_icon_solid_face0(contours, icon_w, icon_h, center_x, top_y, name_prefix, poke=0.0):
    icon_x0 = center_x - icon_w / 2.0
    icon_y0 = top_y - icon_h
    offset, thickness = face0_span(INSERT_DEPTH, poke)

    outer_pts, hole_pts = [], []
    for c in contours:
        # mirror u (1.0 - u) - same fix as build_text_solid_face0's local-X mirror,
        # applied here to the icon's own normalized coordinate instead of mesh vertices.
        pts = [(icon_x0 + (1.0 - u) * icon_w, icon_y0 + v * icon_h) for u, v in c["points"]]
        pts = dedupe_closed_loop(pts)
        (hole_pts if c["hole"] else outer_pts).append(pts)
    assert outer_pts, f"{name_prefix}: traced icon has no outer contours"

    solid = _extrude_profile_face0(outer_pts[0], offset, thickness, f"{name_prefix}_0")
    for i, pts in enumerate(outer_pts[1:], start=1):
        union_onto(solid, _extrude_profile_face0(pts, offset, thickness, f"{name_prefix}_{i}"))
    for i, pts in enumerate(hole_pts):
        cutter = _extrude_profile_face0(pts, offset - OVERSHOOT, thickness + 2 * OVERSHOOT, f"{name_prefix}_hole_{i}")
        apply_boolean(solid, cutter, 'DIFFERENCE')

    # voxel-remesh fix for marginal self-intersections between unioned traced contours -
    # same fix and rationale as this file's own build_icon_solid, above.
    mod = solid.modifiers.new("ForceManifold", 'REMESH')
    mod.mode = 'VOXEL'
    mod.voxel_size = 0.08
    bpy.context.view_layer.objects.active = solid
    bpy.ops.object.modifier_apply(modifier="ForceManifold")
    return solid


def build_tick_face0(x_center, y_center, length, thick, poke=0.0):
    offset, thickness = face0_span(INSERT_DEPTH, poke)
    pts = rect_points(thick, length, x=x_center, z=y_center)
    return _extrude_profile_face0(pts, offset, thickness, f"tick_{x_center:.1f}_{poke:.1f}")


def build_marks_face0(n_values, total_len, full_width_ns, segment_boundary_x=None):
    """segment_boundary_x: only the 24" ranged measure needs this (its "12" mark
    sits exactly at the segment A/B joint and gets nudged off it); a single-piece
    stick has no joint to dodge, so it's None there and every full-width mark stays
    plain/symmetric."""
    inserts, cutters = [], []
    for n in n_values:
        x = total_len - n * 25.4
        if n in full_width_ns:
            length = TRI_SIDE - 2.0   # small inset from each edge
            tick_x = x
            if segment_boundary_x is not None and n == 12:
                # nudged slightly inward from the segment A/B joint so it stays a plain
                # symmetric tick - same construction as every other full-width mark,
                # no special boundary-overshoot handling needed.
                tick_x = segment_boundary_x - TRI_FULL_TICK_THICK / 2.0 - 0.3
            for poke, bucket in ((0.0, inserts), (POCKET_POKE, cutters)):
                bucket.append(build_tick_face0(tick_x, 0.0, length, TRI_FULL_TICK_THICK, poke=poke))
        else:
            # a tick from BOTH edges, numeral centered between them - reads the same
            # regardless of which way the face happens to be oriented when set down,
            # rather than hugging one edge only.
            for poke, bucket in ((0.0, inserts), (POCKET_POKE, cutters)):
                bucket.append(build_tick_face0(x, -TRI_HALF + TRI_TICK_LEN / 2.0, TRI_TICK_LEN, TRI_TICK_THICK, poke=poke))
                bucket.append(build_tick_face0(x, TRI_HALF - TRI_TICK_LEN / 2.0, TRI_TICK_LEN, TRI_TICK_THICK, poke=poke))
            for poke, bucket in ((0.0, inserts), (POCKET_POKE, cutters)):
                glyph, _ = build_text_solid_face0(str(n), RULER_NUM_SIZE, x, 0.0, 'center', poke=poke)
                bucket.append(glyph)
    return inserts, cutters


def build_mythos_badge_face0(cx, cy):
    contours, content_aspect = crop_contours_to_content(load_contours(MYTHOS_CONTOURS_PATH))
    icon_h = MYTHOS_ICON_H
    icon_w = icon_h / content_aspect
    text_h_est = MYTHOS_TEXT_SIZE * 0.7
    inner_gap = 1.0
    content_h = icon_h + inner_gap + text_h_est
    top_y = cy + content_h / 2.0

    inserts, cutters = [], []
    for poke, bucket in ((0.0, inserts), (POCKET_POKE, cutters)):
        bucket.append(build_icon_solid_face0(contours, icon_w, icon_h, cx, top_y, "mythos_icon", poke=poke))

    text_center_y = top_y - icon_h - inner_gap - text_h_est / 2.0
    for poke, bucket in ((0.0, inserts), (POCKET_POKE, cutters)):
        glyph, _ = build_text_solid_face0("MYTHOS", MYTHOS_TEXT_SIZE, cx, text_center_y, 'center',
                                           poke=poke, font_path=TEXT_FONT_PATH)
        bucket.append(glyph)
    return inserts, cutters


def rotate_copy_objects(objs, angle_deg, name_suffix):
    """Duplicate each object's mesh and bake a rotation around world X into its
    vertices - valid for moving face-0 marking geometry onto face 1 (120°) or
    face 2 (240°), since those faces are exact 120° rotations of face 0 about the
    prism's own long axis."""
    rot = mathutils.Matrix.Rotation(math.radians(angle_deg), 4, 'X')
    new_objs = []
    for obj in objs:
        new_obj = obj.copy()
        new_obj.data = obj.data.copy()
        new_obj.name = obj.name + name_suffix
        bpy.context.collection.objects.link(new_obj)
        bm = bmesh.new()
        bm.from_mesh(new_obj.data)
        bm.transform(rot)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.normal_update()
        bm.to_mesh(new_obj.data)
        bm.free()
        new_objs.append(new_obj)
    return new_objs


def build_face_marks_all(n_values, total_len, full_width_ns, badge_x, include_badge,
                          segment_boundary_x=None):
    """Build the face-0 mark set once (real geometry ops), then cheaply duplicate +
    rotate it onto the other 2 faces. Returns combined (inserts, cutters) for all 3."""
    inserts0, cutters0 = build_marks_face0(n_values, total_len, full_width_ns, segment_boundary_x)
    if include_badge:
        b_ins, b_cut = build_mythos_badge_face0(badge_x, 0.0)
        inserts0 += b_ins
        cutters0 += b_cut

    inserts1 = rotate_copy_objects(inserts0, 120, "_f1")
    cutters1 = rotate_copy_objects(cutters0, 120, "_f1")
    inserts2 = rotate_copy_objects(inserts0, 240, "_f2")
    cutters2 = rotate_copy_objects(cutters0, 240, "_f2")

    return inserts0 + inserts1 + inserts2, cutters0 + cutters1 + cutters2


def build_segment_a():
    """x: 0 -> SEGMENT_LEN. Marks for n=12..23 (12 full-width, nudged off the joint;
    24 has no mark at all - it's the physical end). Distal end (x=SEGMENT_LEN) carries
    a blind socket pocket carved INTO the segment's own length.

    Socket cut BEFORE the marks are carved - empirically, doing the tenon union on
    segment B before its own marks-carving avoided a marginal (0.0001) non-manifold
    sliver that appeared when the same union ran on an already-heavily-carved body;
    reordering the socket cut here the same way keeps both segments' build order
    consistent, even though this particular cut alone wasn't observed to trigger it
    on its own."""
    body = extrude_profile_x(triangle_yz(TRI_SIDE), 0.0, SEGMENT_LEN, "segment_a_body")
    apply_bevel(body, TRI_BEVEL_W, TRI_BEVEL_SEGMENTS)

    socket_tri = triangle_yz(TRI_SIDE * SOCKET_SCALE)
    socket_cutter = extrude_profile_x(
        socket_tri, SEGMENT_LEN - TENON_DEPTH, TENON_DEPTH + OVERSHOOT, "segment_a_socket_cutter")
    apply_boolean(body, socket_cutter, 'DIFFERENCE')

    inserts, cutters = build_face_marks_all(SEGMENT_A_NS, TOTAL_LEN, FULL_WIDTH_NS, TRI_BADGE_X,
                                             include_badge=False, segment_boundary_x=SEGMENT_LEN)
    body, inlay = carve_and_collect_inlay(body, inserts, cutters, "segment_a_marks")
    body.name = "segment_a"
    return body, inlay


def build_segment_b():
    """x: SEGMENT_LEN -> 2*SEGMENT_LEN (the stick's tip). Marks for n=3..11 (3,6,9
    full-width) plus the Mythos badge in the 1"/2" zone.

    Tenon added BEFORE the marks are carved, not after - doing it after (on an
    already heavily-carved, high-face-count body) produced a marginal (0.0001)
    non-manifold sliver from the EXACT solver, even though neither the cutter union
    nor the tenon object were individually non-manifold on their own (isolated via
    per-object checks) - a solver-robustness issue tied to mesh complexity at union
    time, not a true geometric overlap. Doing the union first, while the body is
    still simple, avoided it entirely."""
    body = extrude_profile_x(triangle_yz(TRI_SIDE), SEGMENT_LEN, SEGMENT_LEN, "segment_b_body")
    apply_bevel(body, TRI_BEVEL_W, TRI_BEVEL_SEGMENTS)

    tenon_tri = triangle_yz(TRI_SIDE * TENON_SCALE)
    tenon_len = TENON_DEPTH + UNION_OVERLAP
    tenon = extrude_profile_x(tenon_tri, SEGMENT_LEN - TENON_DEPTH, tenon_len, "segment_b_tenon")
    apply_boolean(body, tenon, 'UNION')

    inserts, cutters = build_face_marks_all(SEGMENT_B_NS, TOTAL_LEN, FULL_WIDTH_NS, TRI_BADGE_X,
                                             include_badge=True)
    body, inlay = carve_and_collect_inlay(body, inserts, cutters, "segment_b_marks")
    body.name = "segment_b"
    return body, inlay


def report_tri_segment(name, obj, prev_volume=None):
    vol = mesh_volume(obj)
    nm = nonmanifold_fraction(obj)
    print(f"{name}: volume={vol:.1f}mm3 (non-manifold {nm:.4f})")
    assert vol > 0.0, f"{name}: zero/negative volume - a boolean likely corrupted it"
    if prev_volume is not None:
        assert vol < prev_volume, (
            f"{name}: DIFFERENCE cut didn't remove material as expected "
            f"({prev_volume:.1f} -> {vol:.1f}mm3)")
    return vol


def export_tri_segment(name, base, inlay):
    """Not export_piece - a triangular prism has no front/back to render (see the
    module docstring) and is already in print orientation as built, so this skips
    render_face/reorient_for_print entirely; render_segments (below) renders both
    segments together once, after both are built."""
    apply_color(base, "base_black", BASE_COLOR)
    apply_color(inlay, "inlay_white", INLAY_COLOR)
    export_stl(base, f"{name}_base.stl")
    export_stl(inlay, f"{name}_inlay.stl")
    export_project_3mf(
        [(base, "base", BASE_EXTRUDER_SLOT), (inlay, "inlay", INLAY_EXTRUDER_SLOT)],
        os.path.join(EXPORT_DIR, f"{name}_anycubic.3mf"))


def point_camera(cam_obj, target_pos, up=mathutils.Vector((0.0, 1.0, 0.0))):
    """Explicit look-at matrix, not a to_track_quat/TRACK_TO constraint - viewing a flat
    marking from face 0's real outward direction (+Z) vs. the font's native authoring
    convention (a -Z-looking viewer) necessarily flips one screen axis (there's no way
    to view a flat pattern from the opposite side of the material without SOME axis
    flipping - only a choice of which one). to_track_quat's up-axis STRING can't be
    negated to control which axis flips, and flips a DIFFERENT axis than this explicit
    matrix does for the same up vector - the two aren't interchangeable for this
    project. This one, with up=+Y, is the convention build_text_solid_face0/
    build_icon_solid_face0's own X-mirror was verified against (confirmed both
    analytically - checking which world axis maps to which camera-space axis - and
    visually). Kept separate from phases 1-2's own setup_camera_and_light (also
    to_track_quat-based, but proven fine for THAT geometry/those angles) rather than
    "fixing" working code that isn't broken."""
    direction = (target_pos - cam_obj.location).normalized()
    right = direction.cross(up).normalized()
    true_up = right.cross(direction).normalized()
    rot = mathutils.Matrix((right, true_up, -direction)).transposed().to_4x4()
    cam_obj.matrix_world = mathutils.Matrix.Translation(cam_obj.location) @ rot


def render_shot(cam, cam_data, light, center, cam_pos, ortho_scale, filename, resolution):
    cam.location = mathutils.Vector(cam_pos)
    point_camera(cam, mathutils.Vector(center))
    cam_data.ortho_scale = ortho_scale
    light.location = cam.location + mathutils.Vector((50, -80, 80))
    point_camera(light, mathutils.Vector(center))

    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.filepath = os.path.join(RENDER_DIR, filename)
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {scene.render.filepath}")


def render_tri_segments(seg_a_base, seg_a_inlay, seg_b_base, seg_b_inlay):
    for obj in (seg_a_base, seg_b_base):
        apply_color(obj, "base_preview", BASE_COLOR)
    for obj in (seg_a_inlay, seg_b_inlay):
        apply_color(obj, "inlay_preview", INLAY_COLOR)

    cam_data = bpy.data.cameras.new("RenderCam")
    cam_data.type = 'ORTHO'
    cam = bpy.data.objects.new("RenderCam", cam_data)
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    light_data = bpy.data.lights.new("RenderLight", type='SUN')
    light_data.energy = 3.5
    light = bpy.data.objects.new("RenderLight", light_data)
    bpy.context.collection.objects.link(light)

    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'

    center_full = (SEGMENT_LEN, 0.0, 3.0)

    render_shot(cam, cam_data, light, center_full,
                (center_full[0] - 550, -550, 350), 750, "shooting_full.png", (1800, 700))

    render_shot(cam, cam_data, light, (SEGMENT_LEN, 0.0, 3.0),
                (SEGMENT_LEN - 70, -70, 45), 90, "shooting_joint.png", (1800, 700))

    render_shot(cam, cam_data, light, center_full,
                (-400, 0.0, 3.0), 45, "shooting_endon.png", (700, 700))

    render_shot(cam, cam_data, light, (TRI_BADGE_X, 0.0, BASE_Z),
                (TRI_BADGE_X, -8, BASE_Z - 60), 35, "shooting_badge.png", (900, 900))

    # true straight-on view of the whole face, camera directly below looking straight
    # up (+Z) along the face's own normal - no grazing-angle distortion, so every
    # numeral/tick/badge shows exactly as it actually reads.
    render_shot(cam, cam_data, light, (SEGMENT_LEN, 0.0, BASE_Z),
                (SEGMENT_LEN, 0.0, BASE_Z - 500), 650, "shooting_straighton.png", (2400, 500))

    bpy.data.objects.remove(cam, do_unlink=True)
    bpy.data.objects.remove(light, do_unlink=True)


# ============================================================
# PHASE 4 - TRIANGULAR CHARGE STICK (12.5"/13", single piece)
# ============================================================
#
# The flat charge stick (phase 2) kept as-is; this is a second, triangular design
# for the same two lengths - reuses phase 3's own triangular-prism machinery, just
# a single piece each (13"/12.5" both fit within one print, well under the ~13.4"
# bed-diagonal ceiling - no segments or tenon/socket joint needed here).
#
# Marking scheme mirrors phase 3's "used distances" idea, scaled to what these
# lengths actually reach: full-width unlabeled lines at 3"/6"/9"/12" (no 18" - these
# pieces don't get that far), every other inch a normal tick-from-both-edges +
# centered numeral, no mark at 1"/2" (Mythos badge there instead, "1.5 inches in
# from the right edge").

CS_FULL_WIDTH_NS = {3, 6, 9, 12}
CS_SKIP_NS = {1, 2}

CS_TOTAL_LEN = None   # set per-variant by configure_charge_stick_tri()
CS_BADGE_X = None

CHARGE_STICKS_TRI = [
    {"name": "charge_tri_13in", "length_in": 13.0},
    {"name": "charge_tri_12_5in", "length_in": 12.5},
]


def configure_charge_stick_tri(length_in):
    global CS_TOTAL_LEN, CS_BADGE_X
    CS_TOTAL_LEN = length_in * 25.4
    CS_BADGE_X = CS_TOTAL_LEN - 38.1   # "1.5 inches in from the right edge" - same
                                         # rule as the rest of the family


def build_charge_stick_tri():
    body = extrude_profile_x(triangle_yz(TRI_SIDE), 0.0, CS_TOTAL_LEN, "charge_stick_tri_body")
    apply_bevel(body, TRI_BEVEL_W, TRI_BEVEL_SEGMENTS)

    n_values = [n for n in range(1, 13) if n not in CS_SKIP_NS]
    inserts, cutters = build_face_marks_all(n_values, CS_TOTAL_LEN, CS_FULL_WIDTH_NS, CS_BADGE_X,
                                             include_badge=True)
    body, inlay = carve_and_collect_inlay(body, inserts, cutters, "charge_stick_tri_marks")
    body.name = "charge_stick_tri"
    return body, inlay


def render_charge_stick_tri(name, base, inlay):
    apply_color(base, "base_preview", BASE_COLOR)
    apply_color(inlay, "inlay_preview", INLAY_COLOR)

    cam_data = bpy.data.cameras.new("RenderCam")
    cam_data.type = 'ORTHO'
    cam = bpy.data.objects.new("RenderCam", cam_data)
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    light_data = bpy.data.lights.new("RenderLight", type='SUN')
    light_data.energy = 3.5
    light = bpy.data.objects.new("RenderLight", light_data)
    bpy.context.collection.objects.link(light)

    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'

    half = CS_TOTAL_LEN / 2.0
    render_shot(cam, cam_data, light, (half, 0.0, BASE_Z),
                (half, 0.0, BASE_Z - 400), CS_TOTAL_LEN + 50, f"{name}_straighton.png", (2000, 400))
    render_shot(cam, cam_data, light, (CS_BADGE_X, 0.0, BASE_Z),
                (CS_BADGE_X, -8, BASE_Z - 60), 35, f"{name}_badge.png", (900, 900))

    bpy.data.objects.remove(cam, do_unlink=True)
    bpy.data.objects.remove(light, do_unlink=True)


# ============================================================
# MAIN
# ============================================================


def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    os.makedirs(RENDER_DIR, exist_ok=True)

    # Phase 1: the 3"/6"/9" range/engagement gauges.
    for spec in GAUGES:
        configure_gauge(spec["long_in"], spec["long_label"], spec["top_label_cx"], spec["long_label_cx"],
                         spec.get("cut_top_remain_in", 2.0), spec.get("width_in", 1.0),
                         spec.get("left_remain_in", 0.5), spec.get("label_size", 10.0),
                         spec.get("badge_text_size", 10.0), spec.get("left_label_cx", None))
        clear_scene()
        base, inlay = build_gauge()
        export_piece(spec["name"], base, inlay)

    # Phase 2: the 12.5"/13" charge-measurement sticks.
    for spec in STICKS:
        configure_stick(spec["length_in"])
        clear_scene()
        base, inlay = build_stick()
        export_piece(spec["name"], base, inlay)

    # Phase 3: the 24" triangular tape-measure replacement (2 segments).
    clear_scene()
    print(f"Segment length: {SEGMENT_LEN:.1f}mm ({SEGMENT_LEN/25.4:.1f}\")")
    print(f"Assembled length (2 segments): {TOTAL_LEN:.1f}mm ({TOTAL_LEN/25.4:.1f}\")")

    seg_a_base, seg_a_inlay = build_segment_a()
    report_tri_segment("segment_a_base", seg_a_base)
    report_tri_segment("segment_a_inlay", seg_a_inlay)
    export_tri_segment("shooting_segment_a", seg_a_base, seg_a_inlay)

    seg_b_base, seg_b_inlay = build_segment_b()
    report_tri_segment("segment_b_base", seg_b_base)
    report_tri_segment("segment_b_inlay", seg_b_inlay)
    export_tri_segment("shooting_segment_b", seg_b_base, seg_b_inlay)

    render_tri_segments(seg_a_base, seg_a_inlay, seg_b_base, seg_b_inlay)

    # Phase 4: the 12.5"/13" triangular charge sticks - single piece each.
    for spec in CHARGE_STICKS_TRI:
        configure_charge_stick_tri(spec["length_in"])
        clear_scene()
        base, inlay = build_charge_stick_tri()
        report_tri_segment(f"{spec['name']}_base", base)
        report_tri_segment(f"{spec['name']}_inlay", inlay)
        export_tri_segment(spec["name"], base, inlay)
        render_charge_stick_tri(spec["name"], base, inlay)


if __name__ == "__main__":
    main()
