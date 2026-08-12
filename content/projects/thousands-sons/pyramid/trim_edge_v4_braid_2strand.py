"""
Pyramid edge trim V4 - "V-profile, 2-strand braid" (Blender bpy) - standalone.

Numbered to match trim_v4_braid_2strand.py's motif (same rail+
zigzag-braid family, same v<n> as its flat-trim counterpart) - see
_v1_plain.py, _v2_studs.py, _v3_fishbone_spine.py, and _v5_braid_3strand.py
for the other corner motifs, each a straight port of its flat-trim
namesake's build_border_solid onto this file's fold/leg/print-orientation
scaffolding.

A 90deg corner bracket: two 16mm-wide legs (same rail+2-strand-braid motif
as trim_v4_braid_2strand.py, reused unchanged per leg) hinged
along their shared long edge and folded to a 90deg dihedral, decorated
faces pointing outward - a generic corner bracket usable wherever two flat
trim runs meet at a right-angle edge (a vertical wall corner, a horizontal
cornice corner, etc. - the bracket itself doesn't care which).

Straight-run piece only - the mitred turn-corner blocks (where the
bracket itself needs to turn a 90deg corner) are a separate follow-up,
deferred for now.

Folding approach: build one flat decorated leg (symmetric box, same as
the flat trim strips before their final "lie flat" step), then rotate two
copies of it about the shared hinge axis (local X, at Y=0/Z=0) by 45deg
and 135deg respectively - both are just single rotations of the *same*
starting shape about the *same* axis, so the two legs come out mirror-
symmetric automatically without a separate mirror/flip step (rotations
about a common axis compose by simple angle addition). A small
APEX_OVERLAP nudges each leg slightly past the hinge line before folding,
so the two legs have real overlapping volume (not just a coincident
shared edge) for a robust boolean union - the coincidence issue flagged
throughout this pipeline.

Print orientation: after folding, apex-down/legs-up would put the
decorated faces on the underside (an overhang, the wrong way round for
support-free resin printing) - so build_and_export_corner adds one more
180deg flip about the hinge axis, landing apex-up/legs-down, decorated
faces up-and-outward at a 45deg slope each - the self-supporting
orientation (same 45deg-ish threshold the shallow embossed relief on the
flat strips already relies on, just now from the whole leg's own tilt
rather than the relief's own depth).

Run: Blender -> Scripting workspace -> Open this file -> Alt+P
"""

import bpy
import bmesh
import math
import mathutils
import os

# ============================================================
# CONFIG
# ============================================================

EXPORT_DIR = "/Users/mannil/Desktop/studio-m/TSONS/pyramid/trim/output/edge_v4_braid_2strand"
EXPORT_STL = True

RENDER_IMAGES = True
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1600, 900)

# Unlike the flat trims, the decorated faces here end up pointing mostly
# toward +Z (up, after build_and_export_corner's final Y->Z swap for
# slicer-readiness) with a +Y or -Y component depending on which leg -
# so a top-down-ish view is what actually shows the ornament on both legs
# at once, rather than the -Y-looking angles the flat trims use.
RENDER_ANGLES = {
    "front": (0.0, 1.0, 0.6),
    "side": (1.0, 0.3, 0.5),
    "top": (0.001, 0.001, 1.0),
    "iso": (0.6, 0.7, 0.7),
}

# Each leg (X=length, Y=thickness, Z=width, pre-fold - same convention as
# the flat trims). LEG_L unchanged from the flat strips - folding only
# adds spread in the width/thickness directions, not along the length, so
# the same 140mm (~3mm margin off the Photon Mono 2's 143mm plate edge)
# still applies.
LEG_W = 16.0
LEG_D = 2.0
LEG_L = 140.0

# Border: same rail+2-strand-braid motif as trim_v4_braid_2strand.py,
# unchanged - see that file for the reasoning behind these numbers.
RAIL_OUTER_INSET = 1.0
RAIL_WIDTH = 0.6
ZIGZAG_CHANNEL_WIDTH = LEG_W - 2 * RAIL_OUTER_INSET
ZIGZAG_PERIOD = 2 * ZIGZAG_CHANNEL_WIDTH
ZIGZAG_STRANDS = 2
ZIGZAG_STRAND_SPACING = 0.6
ZIGZAG_STRAND_WIDTH = 0.4
BORDER_EMBOSS_HEIGHT = 0.8
BORDER_EMBED_DEPTH = 0.6

BOX_BEVEL_WIDTH = 0.4
BOX_BEVEL_SEGMENTS = 3

# Fold: each leg is a single rotation (about the shared hinge axis) of the
# *same* starting leg shape - FOLD_ANGLE_A and FOLD_ANGLE_B differ by
# exactly 90deg (135-45=90), which is the dihedral between the two legs.
# See the module docstring for why this produces a mirror-symmetric fold
# without a separate mirror step.
FOLD_ANGLE_A = 45.0
FOLD_ANGLE_B = 135.0
# Nudges each leg's hinge-side edge APEX_OVERLAP past the shared fold line
# before rotating, so the two legs have real overlapping volume at the
# apex for the union (not just a coincident edge - the same class of
# degenerate boolean input flagged throughout this pipeline).
APEX_OVERLAP = 0.3
# Final flip so the decorated faces end up outward-and-up (self-supporting
# for printing) instead of outward-and-down - see module docstring.
PRINT_ORIENT_FLIP_DEG = 180.0


# ============================================================
# HELPERS
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


def frame_and_angle_view():
    """Point the 3D viewport at a 3/4 angle on everything in the scene and
    zoom to fit - a dead flat front-on view of an emboss shows no
    foreshortening/shading, so straight-on is close to the worst angle to
    inspect it from."""
    bpy.ops.object.select_all(action='DESELECT')
    mesh_objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    for obj in mesh_objects:
        obj.select_set(True)
    if mesh_objects:
        bpy.context.view_layer.objects.active = mesh_objects[0]

    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
            if region is None:
                continue
            with bpy.context.temp_override(window=window, area=area, region=region):
                bpy.ops.view3d.view_axis(type='FRONT')
                bpy.ops.view3d.view_orbit(angle=math.radians(-35), type='ORBITLEFT')
                bpy.ops.view3d.view_orbit(angle=math.radians(20), type='ORBITUP')
                bpy.ops.view3d.view_selected()
            return


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

    light_data = bpy.data.lights.new("RenderSun", type='SUN')
    light_data.energy = 3.0
    light_obj = bpy.data.objects.new("RenderSun", light_data)
    light_obj.rotation_euler = (math.radians(55), 0.0, math.radians(35))
    bpy.context.collection.objects.link(light_obj)

    bpy.context.scene.camera = cam_obj
    return cam_obj


def render_angles(center, size):
    os.makedirs(RENDER_DIR, exist_ok=True)
    cam_obj = setup_camera_and_light(center)

    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = RENDER_RESOLUTION[0]
    scene.render.resolution_y = RENDER_RESOLUTION[1]

    distance = size * 1.8
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


def add_box(bm, cx, cz, w, h, depth, angle_deg=0.0):
    """Appends a single axis-aligned (or Y-rotated) box into the given
    bmesh - width/height in local X/Z, `depth` in local Y (straddling
    Y=0)."""
    mat = (mathutils.Matrix.Translation((cx, 0.0, cz))
           @ mathutils.Matrix.Rotation(math.radians(angle_deg), 4, 'Y')
           @ mathutils.Matrix.Diagonal(mathutils.Vector((w, depth, h, 1.0))))
    bmesh.ops.create_cube(bm, size=1.0, matrix=mat)


def bevel_box_edges(obj, width, segments):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.bevel(
        bm, geom=bm.edges[:], offset=width, offset_type='OFFSET',
        segments=segments, affect='EDGES', clamp_overlap=True,
    )
    bm.to_mesh(obj.data)
    bm.free()


def make_box_object(cx, cz, w, h, angle_deg, depth, name):
    bm = bmesh.new()
    add_box(bm, cx, cz, w, h, depth, angle_deg)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def merge_pieces_into_solid(parts, depth, base_name):
    """Sequentially unions a list of (cx, cz, w, h, angle_deg) pieces into
    one watertight solid via real booleans - see
    rune_panel_v6_fishbone_3strand.py's build_border_solid for why long
    boolean-union chains are unreliable with the EXACT solver."""
    solid = make_box_object(*parts[0], depth, f"{base_name}_solid")
    for cx, cz, w, h, angle in parts[1:]:
        piece = make_box_object(cx, cz, w, h, angle, depth, f"{base_name}_piece")
        apply_boolean(solid, piece, 'UNION')
    return solid


def build_zigzag_pieces(length, outer_offset, channel_width, period, n_strands, strand_spacing, strand_width):
    """Builds the braid's zigzag pieces in the leg's own local frame: x
    spans -length/2..+length/2 (the leg's length axis), z is the width
    axis. See trim_v4_braid_2strand.py for the full derivation -
    unchanged here."""
    n_legs = max(2, round(length / (period / 2)))
    step = length / n_legs
    leg_length = math.hypot(step, channel_width)

    parts = []
    for k in range(n_legs):
        x_mid = -length / 2 + (k + 0.5) * step
        z_mid = outer_offset - channel_width / 2
        sign = 1.0 if k % 2 == 0 else -1.0
        angle = math.degrees(math.atan2(-sign * channel_width, step))
        rad = math.radians(angle)
        perp_x, perp_z = -math.sin(rad), -math.cos(rad)
        for j in range(n_strands):
            offset_index = j - (n_strands - 1) / 2.0
            if offset_index == 0:
                offset_index = 0.15
            shift = offset_index * strand_spacing
            cx = x_mid + shift * perp_x
            cz = z_mid + shift * perp_z
            parts.append((cx, cz, leg_length, strand_width, angle))
    return parts


def build_border_solid(strip_w, strip_l, depth):
    """Border: one straight rail down each long edge, plus a zigzag braid
    ribbon that spans the full channel between them - unchanged from
    trim_v4_braid_2strand.py."""
    rail_z = strip_w / 2 - RAIL_OUTER_INSET
    rail_parts = [
        (0.0, rail_z, strip_l, RAIL_WIDTH, 0.0),
        (0.0, -rail_z, strip_l, RAIL_WIDTH, 0.0),
    ]

    zigzag = build_zigzag_pieces(
        strip_l, rail_z, ZIGZAG_CHANNEL_WIDTH, ZIGZAG_PERIOD,
        ZIGZAG_STRANDS, ZIGZAG_STRAND_SPACING, ZIGZAG_STRAND_WIDTH,
    )

    rails_solid = merge_pieces_into_solid(rail_parts, depth, "rails")
    zigzag_solid = merge_pieces_into_solid(zigzag, depth, "zigzag")
    apply_boolean(rails_solid, zigzag_solid, 'UNION')
    return rails_solid


def build_leg(name, relief_sign=-1.0):
    """Builds one flat decorated leg - identical construction to
    trim_v4_braid_2strand.py's build_and_export_strip, up to
    (but not including) that file's final "lie flat for printing" step.
    Spans local X in [-LEG_L/2, LEG_L/2], Z in [-LEG_W/2, LEG_W/2], Y in
    [-LEG_D/2, LEG_D/2] (plus the relief proud of the relief_sign*LEG_D/2
    face - relief_sign=-1 for the front face, same as the flat trims;
    relief_sign=+1 puts it on the back face instead).

    Both legs here are the *same* rotation-about-a-shared-axis trick
    (fold_leg), not a true mirror of each other - rotating one shape by
    two different angles about one axis keeps their *positions* correctly
    mirror-symmetric (checked: it does), but does NOT automatically keep
    their *decorated-face normals* mirror-symmetric too - with both legs
    built relief_sign=-1, one leg's relief ends up facing into the fold
    instead of outward. Building the second leg with relief_sign=+1
    (relief on the opposite face) is what actually fixes that - putting
    the relief on the face that, after each leg's own rotation, works out
    to be the mirror of the other leg's outward face."""
    bpy.ops.mesh.primitive_cube_add(size=1)
    box = bpy.context.object
    box.name = name
    box.scale = (LEG_L, LEG_D, LEG_W)
    bpy.ops.object.transform_apply(scale=True, location=False, rotation=False)
    bevel_box_edges(box, BOX_BEVEL_WIDTH, BOX_BEVEL_SEGMENTS)

    border_depth = BORDER_EMBOSS_HEIGHT + BORDER_EMBED_DEPTH
    border = build_border_solid(LEG_W, LEG_L, border_depth)
    border.location.y = relief_sign * (LEG_D / 2 - (BORDER_EMBED_DEPTH - BORDER_EMBOSS_HEIGHT) / 2)
    apply_boolean(box, border, 'UNION')
    return box


def fold_leg(leg, total_angle_deg):
    """Shifts the leg so its Z=+LEG_W/2 edge lands APEX_OVERLAP past the
    shared hinge line (Z=0), then rotates the whole leg by total_angle_deg
    about local X (the hinge axis, which passes through Y=0/Z=0 and so is
    unaffected by the Z shift)."""
    bpy.ops.object.select_all(action='DESELECT')
    leg.select_set(True)
    bpy.context.view_layer.objects.active = leg

    leg.location.z -= (LEG_W / 2 - APEX_OVERLAP)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

    leg.rotation_euler.x = math.radians(total_angle_deg)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    return leg


def build_and_export_corner():
    leg_a = build_leg("corner_leg_a", relief_sign=-1.0)
    leg_b = build_leg("corner_leg_b", relief_sign=+1.0)

    fold_leg(leg_a, FOLD_ANGLE_A)
    fold_leg(leg_b, FOLD_ANGLE_B)

    apply_boolean(leg_a, leg_b, 'UNION')
    bracket = leg_a
    bracket.name = "trim_edge_braid_2strand"

    # See module docstring: the fold above lands apex-down/decoration-down
    # (an overhang); flip 180deg about the same hinge axis to land
    # apex-up/decoration-up-and-outward (self-supporting for printing).
    bpy.ops.object.select_all(action='DESELECT')
    bracket.select_set(True)
    bpy.context.view_layer.objects.active = bracket
    bracket.rotation_euler.x = math.radians(PRINT_ORIENT_FLIP_DEG)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

    # STL has no notion of "up" - it's raw XYZ triangles - but slicers
    # universally treat Z as the vertical/build axis on import. Up to this
    # point the apex-to-feet ("height") axis has been local Y (modeling
    # convention throughout this pipeline: X=length, Y=thickness/fold-
    # height, Z=width/spread), which would land sideways in a slicer's
    # default Z-up view. Rotate 90deg about X (length axis, untouched) so
    # local Y -> world Z: apex (Y~=0) becomes the highest Z point, the two
    # feet (Y~=-11.5) the lowest - so the exported STL drops directly into
    # a slicer already apex-up, no manual reorientation needed.
    bracket.rotation_euler.x = math.radians(90.0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

    if EXPORT_STL:
        export_stl(bracket, f"{bracket.name}.stl")

    return bracket


# ============================================================
# MAIN
# ============================================================

def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    clear_scene()

    build_and_export_corner()

    if RENDER_IMAGES:
        center, size = compute_scene_bounds()
        render_angles(center, size)

    frame_and_angle_view()

    print(f"Done. Edge bracket exported to {EXPORT_DIR}")


if __name__ == "__main__":
    main()
