"""
Pyramid trim strip V5 - "3-strand braid" (Blender bpy) - standalone.

Same as trim_v4_braid_2strand.py (rails down each long edge,
zigzag braid ribbon between them touching both rails as it alternates),
except each zigzag leg is drawn as 3 parallel strands instead of 2
(ZIGZAG_STRANDS), with a tighter strand spacing/width so the ribbon's
overall footprint comes out close to the 2-strand version - same knob as
runes/rune_panel_v6_fishbone_3strand.py vs. v5.

One of a family of border motifs for the same strip footprint - see
trim_v1_plain.py, _v2_studs.py, _v3_fishbone_spine.py, and
_v4_braid_2strand.py for the others.

Cut to length/mitred by hand after printing - a generic straight trim
strip, not tied to any specific piece or angle, reusable across the
board's various straight trim runs wherever this border motif fits.

Sized to the Anycubic Photon Mono 2's 143 x 89mm plate: strip length
140mm (down the plate's long axis, ~3mm margin off the true 143mm edge),
strip width 16mm (well inside the 89mm short axis). Direct-to-plate, no
supports - same shallow emboss-on-flat-back logic as the rune panels.

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

EXPORT_DIR = "/Users/mannil/Desktop/studio-m/TSONS/pyramid/trim/output/v5_braid_3strand"
EXPORT_STL = True

RENDER_IMAGES = True
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1600, 900)
RENDER_ANGLES = {
    "front": (0.0, -1.0, 0.15),
    "side": (1.0, -0.1, 0.15),
    "top": (0.001, -0.3, 1.0),
    "iso": (0.6, -1.0, 0.6),
}

# Strip (X=length, Y=thickness, Z=width, pre-flatten - see
# build_and_export_strip). X is the length axis to match build_zigzag_pieces
# / build_border_solid, which build along local X (length) / local Z
# (width) - the same (cx, cz)=(X, Z) convention add_box uses throughout.
STRIP_W = 16.0
STRIP_D = 2.0
STRIP_L = 140.0

# ------------------------------------------------------------
# Border: one straight rail down each long edge, with a zigzag braid
# ribbon between them that touches each rail's own centerline as it
# alternates - so the braid reads as flowing continuously into the rails
# rather than floating independently inside them.
#
# RAIL_OUTER_INSET is the rail's centerline distance from the strip's true
# edge (1.0mm, same as the rune panel borders). CHANNEL_WIDTH is therefore
# STRIP_W - 2*RAIL_OUTER_INSET = 14.0mm.
#
# ZIGZAG_PERIOD = 2 * CHANNEL_WIDTH gives each leg a clean 45deg angle
# (period/2 == channel width) and, at STRIP_L=140, divides it into exactly
# 10 legs with no remainder.
# ------------------------------------------------------------
RAIL_OUTER_INSET = 1.0
RAIL_WIDTH = 0.6
ZIGZAG_CHANNEL_WIDTH = STRIP_W - 2 * RAIL_OUTER_INSET
ZIGZAG_PERIOD = 2 * ZIGZAG_CHANNEL_WIDTH
ZIGZAG_STRANDS = 3
ZIGZAG_STRAND_SPACING = 0.55
ZIGZAG_STRAND_WIDTH = 0.35
BORDER_EMBOSS_HEIGHT = 0.8
BORDER_EMBED_DEPTH = 0.6

# Chamfer on all 12 slab edges - same reasoning as the rune panels: softens
# the raw-slab look, and once laid flat for printing gives a scraper
# something to wedge under on the bottom perimeter. Must stay clear of
# where the rail starts (RAIL_OUTER_INSET - RAIL_WIDTH/2 = 0.7mm from the
# true edge) so the bevel doesn't eat into the flat area the rail unions
# onto.
BOX_BEVEL_WIDTH = 0.4
BOX_BEVEL_SEGMENTS = 3


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
    Y=0). Blender's Y-axis rotation matrix sends local X to world
    (cos(angle), -sin(angle)) in the (x,z) plane - see
    build_zigzag_pieces, which depends on this exact convention to aim
    each leg at its touch points."""
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
    one watertight solid via real booleans. Kept as its own short chain
    (only the zigzag's ~30 pieces at 3 strands) rather than folded into one
    giant union with the rails - see rune_panel_v6_fishbone_3strand.py's
    build_border_solid for why long boolean-union chains are unreliable
    with the EXACT solver."""
    solid = make_box_object(*parts[0], depth, f"{base_name}_solid")
    for cx, cz, w, h, angle in parts[1:]:
        piece = make_box_object(cx, cz, w, h, angle, depth, f"{base_name}_piece")
        apply_boolean(solid, piece, 'UNION')
    return solid


def build_zigzag_pieces(length, outer_offset, channel_width, period, n_strands, strand_spacing, strand_width):
    """Builds the braid's zigzag pieces in the strip's own local frame: x
    spans -length/2..+length/2 (the strip's length axis), z is the width
    axis. Legs alternate touching z=outer_offset (top rail's centerline,
    even k) and z=outer_offset-channel_width (bottom rail's centerline,
    odd k), each leg drawn as n_strands parallel copies offset
    perpendicular to its own direction (a ribbon, not a single line) - see
    rune_panel_v5_fishbone_2strand.py's build_zigzag_edge_canonical, which
    this is a direct port of. Returns a list of (cx, cz, w, h, angle_deg)."""
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
            # Nudge the centered strand (odd n_strands only) off exact
            # zero - an exact-coincidence boolean input that has silently
            # dropped/duplicated geometry elsewhere in this pipeline.
            if offset_index == 0:
                offset_index = 0.15
            shift = offset_index * strand_spacing
            cx = x_mid + shift * perp_x
            cz = z_mid + shift * perp_z
            parts.append((cx, cz, leg_length, strand_width, angle))
    return parts


def build_border_solid(strip_w, strip_l, depth):
    """Border: one straight rail down each long edge (at
    +-(strip_w/2 - RAIL_OUTER_INSET)), plus a zigzag braid ribbon that
    spans the full channel between them, touching each rail's centerline
    as it alternates."""
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


def build_and_export_strip():
    bpy.ops.mesh.primitive_cube_add(size=1)
    box = bpy.context.object
    box.name = "trim_braid_3strand"
    box.scale = (STRIP_L, STRIP_D, STRIP_W)
    bpy.ops.object.transform_apply(scale=True, location=False, rotation=False)
    bevel_box_edges(box, BOX_BEVEL_WIDTH, BOX_BEVEL_SEGMENTS)

    border_depth = BORDER_EMBOSS_HEIGHT + BORDER_EMBED_DEPTH
    border = build_border_solid(STRIP_W, STRIP_L, border_depth)
    # Box front face is at y=-STRIP_D/2 (outward normal -Y). The border
    # solid is built symmetric around its own local Y=0, so shift it in -Y
    # until its far edge stands proud past the front face by
    # BORDER_EMBOSS_HEIGHT and its near edge is buried BORDER_EMBED_DEPTH
    # past the surface (avoids a flush/coincident union boundary).
    border.location.y = -STRIP_D / 2 + (BORDER_EMBED_DEPTH - BORDER_EMBOSS_HEIGHT) / 2
    apply_boolean(box, border, 'UNION')

    # Lie flat for direct-to-plate resin printing: local Y (thickness) ->
    # world -Z (down, on the plate), local Z (STRIP_W, the strip's width)
    # -> world Y; local X (STRIP_L, the strip's long axis) stays world X.
    # Same -90deg-about-X trick as the rune panels - see
    # rune_panel_v6_fishbone_3strand.py's build_and_export_panel for the
    # full derivation.
    box.rotation_euler.x = math.radians(-90)
    bpy.ops.object.select_all(action='DESELECT')
    box.select_set(True)
    bpy.context.view_layer.objects.active = box
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

    if EXPORT_STL:
        export_stl(box, f"{box.name}.stl")

    return box


# ============================================================
# MAIN
# ============================================================

def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    clear_scene()

    build_and_export_strip()

    if RENDER_IMAGES:
        center, size = compute_scene_bounds()
        render_angles(center, size)

    frame_and_angle_view()

    print(f"Done. Strip exported to {EXPORT_DIR}")


if __name__ == "__main__":
    main()
