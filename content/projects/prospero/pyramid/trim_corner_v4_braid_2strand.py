"""
Pyramid corner trim V4 - "2-strand braid" (Blender bpy) - standalone.

The decorated version of trim_corner_v1_plain.py - confirmed correct
geometry (three flat panels, one per box face - TOP, FRONT, RIGHT - each
pairwise joined along its own shared edge, so all three edges meet
properly, unlike the earlier V-bracket/miter attempts which only met at a
single point and never actually defined a real pocket). This file adds
the same rail+2-strand-braid motif as the rest of the v4 family to each
panel's outward face.

Box convention (vertex at world origin, unchanged from v1_plain): box
occupies X<=0, Y>=0, Z<=0. TOP panel proud in +Z, FRONT proud in -Y,
RIGHT proud in +X - decoration goes on those outward faces.

Each panel is decorated *before* the three are unioned together (border
per panel, then bevel, then join) - same order the flat trims use
(bevel the plain box, then union the border onto it) so the bevel doesn't
eat into the border's own margin.

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

EXPORT_DIR = "/Users/mannil/Desktop/studio-m/TSONS/pyramid/trim/output/corner_v4_braid_2strand"
EXPORT_STL = True

RENDER_IMAGES = True
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1600, 900)
RENDER_ANGLES = {
    "iso_a": (0.8, -0.9, 0.6),
    "iso_b": (-0.8, 0.9, -0.6),
    "top": (0.001, 0.001, 1.0),
    "front": (0.001, -1.0, 0.001),
}

# How far each panel reaches from the vertex along the box face it sits
# on. 48mm (3x the original 16mm, which matched the flat trims' LEG_W but
# read as too small/stubby for a standalone corner piece) - still well
# inside the Photon Mono 2's 143x89mm plate. Panel thickness (2mm) matches
# the flat trims' LEG_D, unchanged.
# EDGE_OVERLAP needs to be a real structural overlap, not just enough to
# avoid the boolean-coincidence issue - a hairline seam is a weak point
# (or may not even print as connected material) where two panels meet at
# 90deg. 1.5mm gives each panel-to-panel joint real cross-sectional area
# to bond through, not just a knife-edge touch.
CORNER_REACH = 48.0
PANEL_THICKNESS = 2.0
EDGE_OVERLAP = 1.5

# Border: same rail+2-strand-braid motif as trim_v4_braid_2strand.py,
# re-tuned for a CORNER_REACH x CORNER_REACH square panel instead of a
# long strip - ZIGZAG_PERIOD=CORNER_REACH gives 2 clean chevron legs
# across the panel, same as the original 16mm version. Tried decoupling
# this to a fixed period so a bigger panel gets more (smaller) legs
# instead of the same 2 legs scaled up - doesn't work here: unlike the
# flat strips, this panel's channel width (the zigzag's perpendicular
# span) is tied to CORNER_REACH too since it's a square panel, not a
# fixed-width long strip, so a fixed period against a growing channel
# width just makes the legs steep and spiky instead of a clean chevron.
# Scaling the period along with CORNER_REACH keeps the same leg
# proportions (channel_width/step ratio) regardless of size.
RAIL_OUTER_INSET = 1.0
RAIL_WIDTH = 0.6
ZIGZAG_CHANNEL_WIDTH = CORNER_REACH - 2 * RAIL_OUTER_INSET
ZIGZAG_PERIOD = CORNER_REACH
ZIGZAG_STRANDS = 2
ZIGZAG_STRAND_SPACING = 0.6
ZIGZAG_STRAND_WIDTH = 0.4
BORDER_EMBOSS_HEIGHT = 0.8
BORDER_EMBED_DEPTH = 0.6

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


def make_panel(x_range, y_range, z_range, name):
    cx = (x_range[0] + x_range[1]) / 2
    cy = (y_range[0] + y_range[1]) / 2
    cz = (z_range[0] + z_range[1]) / 2
    sx = x_range[1] - x_range[0]
    sy = y_range[1] - y_range[0]
    sz = z_range[1] - z_range[0]
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True, location=False, rotation=False)
    obj.location = (cx, cy, cz)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    return obj


def bevel_box_edges(obj, width, segments):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.bevel(
        bm, geom=bm.edges[:], offset=width, offset_type='OFFSET',
        segments=segments, affect='EDGES', clamp_overlap=True,
    )
    bm.to_mesh(obj.data)
    bm.free()


def add_box(bm, cx, cz, w, h, depth, angle_deg=0.0):
    mat = (mathutils.Matrix.Translation((cx, 0.0, cz))
           @ mathutils.Matrix.Rotation(math.radians(angle_deg), 4, 'Y')
           @ mathutils.Matrix.Diagonal(mathutils.Vector((w, depth, h, 1.0))))
    bmesh.ops.create_cube(bm, size=1.0, matrix=mat)


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
    solid = make_box_object(*parts[0], depth, f"{base_name}_solid")
    for cx, cz, w, h, angle in parts[1:]:
        piece = make_box_object(cx, cz, w, h, angle, depth, f"{base_name}_piece")
        apply_boolean(solid, piece, 'UNION')
    return solid


def build_zigzag_pieces(length, outer_offset, channel_width, period, n_strands, strand_spacing, strand_width):
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


def build_border_solid(panel_size, depth):
    """Border for one CORNER_REACH x CORNER_REACH square panel: a rail
    down each of the two edges NOT shared with a neighboring panel (the
    panel's own local X=const edges), with a 2-strand zigzag braid
    between them running along local Z - same rail+braid language as
    trim_v4_braid_2strand.py, just square instead of a long
    strip."""
    rail_z = panel_size / 2 - RAIL_OUTER_INSET
    rail_parts = [
        (0.0, rail_z, panel_size, RAIL_WIDTH, 0.0),
        (0.0, -rail_z, panel_size, RAIL_WIDTH, 0.0),
    ]
    zigzag = build_zigzag_pieces(
        panel_size, rail_z, ZIGZAG_CHANNEL_WIDTH, ZIGZAG_PERIOD,
        ZIGZAG_STRANDS, ZIGZAG_STRAND_SPACING, ZIGZAG_STRAND_WIDTH,
    )
    rails_solid = merge_pieces_into_solid(rail_parts, depth, "rails")
    zigzag_solid = merge_pieces_into_solid(zigzag, depth, "zigzag")
    apply_boolean(rails_solid, zigzag_solid, 'UNION')
    return rails_solid


def build_decorated_panel(x_range, y_range, z_range, outward_axis, outward_sign, name):
    """Builds one plain panel box, bevels it, then unions a rail+braid
    border onto its outward face. outward_axis is 'x', 'y', or 'z' -
    which local axis the panel is thin along (its own thickness
    direction); outward_sign is which end of that thin axis is the
    outward (decorated) face."""
    panel = make_panel(x_range, y_range, z_range, name)
    bevel_box_edges(panel, BOX_BEVEL_WIDTH, BOX_BEVEL_SEGMENTS)

    border_depth = BORDER_EMBOSS_HEIGHT + BORDER_EMBED_DEPTH
    border = build_border_solid(CORNER_REACH, border_depth)
    # build_border_solid's own local frame has its "panel_size x panel_size"
    # square in local (X,Z), with local Y as the thin/outward direction -
    # rotate it so that local Y instead points along whichever world axis
    # is this panel's own outward direction, then position it at the
    # panel's outward face (offset by the embed/emboss split, mirroring
    # the flat trims' own EMBED_DEPTH/EMBOSS_HEIGHT placement logic).
    offset = outward_sign * (PANEL_THICKNESS / 2 - (BORDER_EMBED_DEPTH - BORDER_EMBOSS_HEIGHT) / 2)
    if outward_axis == 'z':
        # local (X,Y,Z) already matches world (X,Y,Z) for a Z-thin panel
        # (border's own X,Z square maps to world X,Y; border's Y maps to
        # world Z) - so rotate border's local Y axis onto world Z: -90
        # about world X.
        border.rotation_euler.x = math.radians(-90.0)
        bpy.ops.object.select_all(action='DESELECT')
        border.select_set(True)
        bpy.context.view_layer.objects.active = border
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        cx = (x_range[0] + x_range[1]) / 2
        cy = (y_range[0] + y_range[1]) / 2
        cz = (z_range[0] + z_range[1]) / 2 + offset
        border.location = (cx, cy, cz)
    elif outward_axis == 'y':
        # border's local Y -> world Y directly, no rotation needed;
        # border's local X,Z -> world X,Z.
        cx = (x_range[0] + x_range[1]) / 2
        cy = (y_range[0] + y_range[1]) / 2 + offset
        cz = (z_range[0] + z_range[1]) / 2
        border.location = (cx, cy, cz)
    elif outward_axis == 'x':
        # rotate border's local Y onto world X: 90 about world Z (border's
        # local X,Z square maps to world Y,Z).
        border.rotation_euler.z = math.radians(90.0)
        bpy.ops.object.select_all(action='DESELECT')
        border.select_set(True)
        bpy.context.view_layer.objects.active = border
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        cx = (x_range[0] + x_range[1]) / 2 + offset
        cy = (y_range[0] + y_range[1]) / 2
        cz = (z_range[0] + z_range[1]) / 2
        border.location = (cx, cy, cz)
    bpy.ops.object.select_all(action='DESELECT')
    border.select_set(True)
    bpy.context.view_layer.objects.active = border
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

    apply_boolean(panel, border, 'UNION')
    return panel


def build_and_export_cap():
    r = CORNER_REACH
    t = PANEL_THICKNESS
    o = EDGE_OVERLAP

    top = build_decorated_panel((-r, o), (-o, r), (0, t), 'z', +1.0, "cap_top")
    front = build_decorated_panel((-r, o), (-t, 0), (-r, o), 'y', -1.0, "cap_front")
    right = build_decorated_panel((0, t), (-o, r), (-r, o), 'x', +1.0, "cap_right")

    apply_boolean(top, front, 'UNION')
    apply_boolean(top, right, 'UNION')
    cap = top
    cap.name = "trim_corner_braid_2strand"

    if EXPORT_STL:
        export_stl(cap, f"{cap.name}.stl")

    return cap


# ============================================================
# MAIN
# ============================================================

def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    clear_scene()

    build_and_export_cap()

    if RENDER_IMAGES:
        center, size = compute_scene_bounds()
        render_angles(center, size)

    frame_and_angle_view()

    print(f"Done. Corner cap exported to {EXPORT_DIR}")


if __name__ == "__main__":
    main()
