"""
Pyramid corner trim V1 - "plain" (Blender bpy) - standalone.

A completely different construction from trim_corner_miter_v4_braid_2strand.py's
V-fold arms, after establishing those never actually defined a box-fitting
pocket (TOP and RIGHT only touched FRONT, never each other - no shared
edge between them, so no real 3-sided pocket existed no matter how the
decoration was oriented).

This is the literal "cut the corner off a box" shape: three flat panels,
one per box face (TOP, FRONT, RIGHT) meeting at a shared vertex, each
PAIR joined along its own shared edge (TOP-FRONT, FRONT-RIGHT, TOP-RIGHT)
- all three edges present, unlike the miter version's single point. Each
panel sits PANEL_THICKNESS proud of its box face, offset outward (away
from the box) - "outside out" (the panels' outer faces, where decoration
would go, face away from the box) "inside in" (the panels' inner faces,
touching the box, are flush against it, hidden).

Box convention (vertex at world origin): box occupies X<=0 (TOP/FRONT/
RIGHT panels reach CORNER_REACH in -X), Y>=0 (reach in +Y), Z<=0 (reach in
-Z) - i.e. TOP panel sits above the box's top face (proud in +Z), FRONT
sits in front of the box's front face (proud in -Y), RIGHT sits right of
the box's right face (proud in +X). Verified this time by an actual
boolean-intersection collision test against a large stand-in box in all 8
octants, not by hand-deriving which way is "outward" - see the earlier
back-and-forth in this pipeline's history for why hand-derivation kept
getting this wrong.

Plain (no rail/braid decoration yet) - getting the base shape and box fit
right first, motif to follow once this is confirmed.

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

EXPORT_DIR = "/Users/mannil/Desktop/studio-m/TSONS/pyramid/trim/output/corner_v1_plain"
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

# CORNER_REACH is the compact "hub" where all 3 panels actually meet and
# cover the vertex - kept at the original 16mm, since that's the size
# that was confirmed to box-fit correctly. Making the *whole* panel a
# bigger CORNER_REACH x CORNER_REACH square (an earlier attempt) just
# scaled the same shape up - not what's wanted. Instead, each panel gets
# two long, narrow ARM_REACH-long extensions continuing out past the hub
# along its own two shared edges (a "3-pointed star": compact where the
# panels actually join near the vertex, long narrow arms radiating out
# along each of the 3 edges beyond that). ARM_REACH=48mm is 3x the hub.
# Panel thickness (2mm) matches the flat trims' LEG_D, unchanged.
# EDGE_OVERLAP needs to be a real structural overlap, not just enough to
# avoid the boolean-coincidence issue - a hairline seam is a weak point
# (or may not even print as connected material) where two panels meet at
# 90deg (or where a hub meets its own arm). 1.5mm gives each joint real
# cross-sectional area to bond through, not just a knife-edge touch.
CORNER_REACH = 16.0
ARM_REACH = 48.0
PANEL_THICKNESS = 2.0
EDGE_OVERLAP = 1.5

# Rails along each arm's two long free edges - same rail treatment as
# trim_v1_plain.py's flat strip (the "plain" motif there is just rails,
# no braid), applied per-arm here since each arm is basically a mini
# version of that same flat strip. Not applied to the hub (where all 3
# panels overlap and join) - kept plain there, same as a mitered strip
# corner's own joint area.
RAIL_OUTER_INSET = 1.0
RAIL_WIDTH = 0.6
RAIL_EMBOSS_HEIGHT = 0.8
RAIL_EMBED_DEPTH = 0.6

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
    """Box spanning the given [min,max] ranges on each axis."""
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


def add_rail_pair(panel, along_range, width_lo_hi, along_axis, width_axis, outward_range, outward_axis, name):
    """Adds 2 rails to panel, running the length of one arm. along_range
    is the (min,max) along the arm's length; width_lo_hi is the arm's
    "true" width span (ignoring the small EDGE_OVERLAP fudge) - the 2
    rails sit RAIL_OUTER_INSET in from each end of that; outward_range is
    the panel's already-known proud/embedded depth range on its outward
    axis (+-Z for TOP, +-Y for FRONT, +-X for RIGHT). along_axis,
    width_axis, outward_axis are 'x'/'y'/'z', identifying which world
    axis plays which role for this particular arm."""
    half_rw = RAIL_WIDTH / 2
    w_lo, w_hi = width_lo_hi
    centers = (w_lo + RAIL_OUTER_INSET, w_hi - RAIL_OUTER_INSET)
    for i, c in enumerate(centers):
        ranges = {along_axis: along_range, width_axis: (c - half_rw, c + half_rw), outward_axis: outward_range}
        rail = make_panel(ranges['x'], ranges['y'], ranges['z'], f"{name}_rail{i}")
        apply_boolean(panel, rail, 'UNION')


def build_and_export_cap():
    r = CORNER_REACH
    a = ARM_REACH
    t = PANEL_THICKNESS
    o = EDGE_OVERLAP

    # Outward-face depth ranges for the rails (proud by RAIL_EMBOSS_HEIGHT,
    # embedded by RAIL_EMBED_DEPTH) on each panel's own outward axis -
    # same emboss/embed split the flat trims use for their border relief.
    rail_z_top = (t - RAIL_EMBED_DEPTH, t + RAIL_EMBOSS_HEIGHT)
    rail_y_front = (-t - RAIL_EMBOSS_HEIGHT, -t + RAIL_EMBED_DEPTH)
    rail_x_right = (t - RAIL_EMBED_DEPTH, t + RAIL_EMBOSS_HEIGHT)

    # TOP: proud in +Z above the box's top face. Hub reaches -X/+Y like
    # before; the X-arm continues further in -X (pairs with FRONT's own
    # X-arm to form the long TOP-FRONT edge run), the Y-arm continues
    # further in +Y (pairs with RIGHT's Y-arm for the TOP-RIGHT edge run).
    # Each arm is only as wide as the hub (Y in [-o,r] / X in [-r,o]) - it
    # doesn't also reach toward the *other* neighbor, so the panel's
    # footprint is a "+" cross, not a bigger filled square.
    #
    # Bevel happens BEFORE the rails are added, same order the flat trims
    # use (bevel the plain slab, then union the border on top) - so the
    # rails come out crisp/architectural while the panel's own outer
    # edges get the chamfer (scraper-release, chip-resistance).
    top_hub = make_panel((-r, o), (-o, r), (0, t), "cap_top_hub")
    top_x_arm = make_panel((-a, -r + o), (-o, r), (0, t), "cap_top_xarm")
    top_y_arm = make_panel((-r, o), (r - o, a), (0, t), "cap_top_yarm")
    apply_boolean(top_hub, top_x_arm, 'UNION')
    apply_boolean(top_hub, top_y_arm, 'UNION')
    top = top_hub
    add_rail_pair(top, (-a, -r + o), (0, r), 'x', 'y', rail_z_top, 'z', "top_xarm")
    add_rail_pair(top, (r - o, a), (-r, 0), 'y', 'x', rail_z_top, 'z', "top_yarm")

    # FRONT: proud in -Y in front of the box's front face. Hub reaches
    # -X/-Z; X-arm continues in -X (pairs with TOP's X-arm), Z-arm
    # continues in -Z (pairs with RIGHT's Z-arm for the FRONT-RIGHT edge).
    front_hub = make_panel((-r, o), (-t, 0), (-r, o), "cap_front_hub")
    front_x_arm = make_panel((-a, -r + o), (-t, 0), (-r, o), "cap_front_xarm")
    front_z_arm = make_panel((-r, o), (-t, 0), (-a, -r + o), "cap_front_zarm")
    apply_boolean(front_hub, front_x_arm, 'UNION')
    apply_boolean(front_hub, front_z_arm, 'UNION')
    front = front_hub
    add_rail_pair(front, (-a, -r + o), (-r, 0), 'x', 'z', rail_y_front, 'y', "front_xarm")
    add_rail_pair(front, (-a, -r + o), (-r, 0), 'z', 'x', rail_y_front, 'y', "front_zarm")

    # RIGHT: proud in +X to the right of the box's right face. Hub reaches
    # +Y/-Z; Y-arm continues in +Y (pairs with TOP's Y-arm), Z-arm
    # continues in -Z (pairs with FRONT's Z-arm).
    right_hub = make_panel((0, t), (-o, r), (-r, o), "cap_right_hub")
    right_y_arm = make_panel((0, t), (r - o, a), (-r, o), "cap_right_yarm")
    right_z_arm = make_panel((0, t), (-o, r), (-a, -r + o), "cap_right_zarm")
    apply_boolean(right_hub, right_y_arm, 'UNION')
    apply_boolean(right_hub, right_z_arm, 'UNION')
    right = right_hub
    add_rail_pair(right, (r - o, a), (-r, 0), 'y', 'z', rail_x_right, 'x', "right_yarm")
    add_rail_pair(right, (-a, -r + o), (0, r), 'z', 'y', rail_x_right, 'x', "right_zarm")

    apply_boolean(top, front, 'UNION')
    apply_boolean(top, right, 'UNION')
    bevel_box_edges(top, BOX_BEVEL_WIDTH, BOX_BEVEL_SEGMENTS)
    cap = top
    cap.name = "trim_corner_plain"

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
