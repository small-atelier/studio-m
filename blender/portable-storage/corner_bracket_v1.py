# Portable Storage — Corner Bracket v1
# 3D-printed corner post for the modular magnetic storage tray: panel slots
# on two outer faces, a narrower floor-retaining slot at the base, and a
# pin/socket stacking interface (identical on every bracket — the top pin
# on one tray's post mates with the bottom socket of the post above it).
# Paste into the Blender Script Editor and run (Alt+P).
#
# Geometry verified in Blender 5.1.2 (headless run, both height tiers,
# clean booleans, sane volumes, top-down cross-section checked) - not yet
# printed or fit-checked against real panels/steel/magnets though. The far
# wall of each panel slot reads as a thin standing fin in an iso view; it's
# real connected geometry (confirmed via a top-down cross-section render),
# not a boolean artifact, but worth watching on the first physical print -
# a thin tall unsupported-looking rib like that is a plausible warp/snap
# point in FDM regardless of being geometrically sound. Fasteners (screws,
# heat-set inserts) are deliberately left out of v1 — add them once the
# slot fit is validated on a physical print, not before.
#
# Docs: content/posts/modular-magnetic-storage-box/index.md

import bpy
import bmesh
import math
import mathutils
import os

# ----------------------------
# CONFIG (all mm)
# ----------------------------
TRAY_HEIGHT_TIERS = {
    "low":  28.0,   # infantry / small miniatures
    "tall": 48.0,   # cavalry / monsters / vehicles
}

POST_SIZE = 12.0   # outer square cross-section of the corner post

PANEL_THICKNESS      = 3.0   # plywood/acrylic side panel
PANEL_SLOT_CLEARANCE = 0.3   # extra slot width for a sliding fit
PANEL_SLOT_DEPTH     = 6.0   # how far the slot cuts in from each outer face

FLOOR_THICKNESS      = 1.0   # steel floor sheet
FLOOR_SLOT_CLEARANCE = 0.2
FLOOR_SLOT_HEIGHT    = 4.0   # height of the floor-retaining band, from Z=0

PIN_DIAMETER  = 5.0
PIN_HEIGHT    = 3.0
PIN_CLEARANCE = 0.15         # socket radius = pin radius + this
SOCKET_DEPTH  = PIN_HEIGHT + 0.5

EXPORT_STL = True
OUTPUT_DIR = "/Users/mannil/studio-m/blender/portable-storage/output"

# ----------------------------
# SANITY CHECKS
# ----------------------------
assert PANEL_SLOT_DEPTH < POST_SIZE, "panel slot would cut all the way through the post"
remaining_wall = POST_SIZE - PANEL_SLOT_DEPTH
assert remaining_wall >= 2.5, f"only {remaining_wall:.1f}mm of wall left behind the panel slot - thin for FDM"
for name, height in TRAY_HEIGHT_TIERS.items():
    assert FLOOR_SLOT_HEIGHT + PIN_HEIGHT + SOCKET_DEPTH < height, \
        f"'{name}' tier too short to fit the floor slot and both stacking features"


# ----------------------------
# HELPERS (shared convention - see card_stand_v8_holder_piece.py)
# ----------------------------
def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block)


def apply_boolean(target, cutter, operation='DIFFERENCE'):
    mod = target.modifiers.new("Bool", 'BOOLEAN')
    mod.object = cutter
    mod.operation = operation
    mod.solver = 'EXACT'
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    return target


def add_box_range(x_range, y_range, z_range):
    x0, x1 = x_range
    y0, y1 = y_range
    z0, z1 = z_range
    size = (x1 - x0, y1 - y0, z1 - z0)
    center = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.active_object
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def add_cylinder(diameter, z_range, loc_xy):
    z0, z1 = z_range
    bpy.ops.mesh.primitive_cylinder_add(
        radius=diameter / 2, depth=z1 - z0,
        location=(loc_xy[0], loc_xy[1], (z0 + z1) / 2),
        vertices=32,
    )
    return bpy.context.active_object


# ----------------------------
# BUILD
# ----------------------------
def build_bracket(tray_height):
    # Post sits with the corner at the world-origin edge (X=0, Y=0), filling
    # +X/+Y, running Z=0 (bottom, resting on the table/tray below) to
    # Z=tray_height (top).
    post = add_box_range((0, POST_SIZE), (0, POST_SIZE), (0, tray_height))
    post.name = "CornerBracket"

    panel_half = (PANEL_THICKNESS + PANEL_SLOT_CLEARANCE) / 2
    floor_half = (FLOOR_THICKNESS + FLOOR_SLOT_CLEARANCE) / 2
    mid = POST_SIZE / 2

    # Panel slots on the +X and +Y outer faces, running from just above the
    # floor band up through the top of the post.
    slot_x = add_box_range(
        (POST_SIZE - PANEL_SLOT_DEPTH, POST_SIZE + 1),
        (mid - panel_half, mid + panel_half),
        (FLOOR_SLOT_HEIGHT, tray_height + 1),
    )
    apply_boolean(post, slot_x)

    slot_y = add_box_range(
        (mid - panel_half, mid + panel_half),
        (POST_SIZE - PANEL_SLOT_DEPTH, POST_SIZE + 1),
        (FLOOR_SLOT_HEIGHT, tray_height + 1),
    )
    apply_boolean(post, slot_y)

    # Floor-retaining slots, same two outer faces, narrower band at the
    # base — the step where this slot narrows into the (wider) panel slot
    # above doubles as a seating shoulder for the panel.
    floor_slot_x = add_box_range(
        (POST_SIZE - PANEL_SLOT_DEPTH, POST_SIZE + 1),
        (mid - floor_half, mid + floor_half),
        (-1, FLOOR_SLOT_HEIGHT),
    )
    apply_boolean(post, floor_slot_x)

    floor_slot_y = add_box_range(
        (mid - floor_half, mid + floor_half),
        (POST_SIZE - PANEL_SLOT_DEPTH, POST_SIZE + 1),
        (-1, FLOOR_SLOT_HEIGHT),
    )
    apply_boolean(post, floor_slot_y)

    # Stacking pin (top) — added as solid geometry, joined onto the post.
    pin = add_cylinder(PIN_DIAMETER, (tray_height, tray_height + PIN_HEIGHT), (mid, mid))
    bpy.ops.object.select_all(action='DESELECT')
    post.select_set(True)
    pin.select_set(True)
    bpy.context.view_layer.objects.active = post
    bpy.ops.object.join()
    post = bpy.context.active_object

    # Stacking socket (bottom) — cut, sized with clearance over the pin so
    # trays seat without binding.
    socket = add_cylinder(PIN_DIAMETER + PIN_CLEARANCE * 2, (-1, SOCKET_DEPTH), (mid, mid))
    apply_boolean(post, socket)

    return post


def export_stl(obj, filename):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = os.path.join(OUTPUT_DIR, filename)
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"Exported {path}")


def mesh_volume(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    volume = bm.calc_volume()
    bm.free()
    return volume


def render_iso(name, obj):
    render_dir = os.path.join(OUTPUT_DIR, "renders")
    os.makedirs(render_dir, exist_ok=True)
    center = mathutils.Vector([(a + b) / 2 for a, b in zip(obj.bound_box[0], obj.bound_box[6])])
    center = obj.matrix_world @ center
    size = max(obj.dimensions)

    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    target = bpy.data.objects.new("T", None)
    target.location = center
    bpy.context.collection.objects.link(target)
    track = cam.constraints.new(type='TRACK_TO')
    track.target = target
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'
    light_data = bpy.data.lights.new("Sun", type='SUN')
    light_data.energy = 3.0
    light = bpy.data.objects.new("Sun", light_data)
    light.rotation_euler = (math.radians(55), 0.0, math.radians(35))
    bpy.context.collection.objects.link(light)
    cam.location = center + mathutils.Vector((0.7, -1.0, 0.7)).normalized() * max(size * 3.0, 20.0)
    bpy.context.scene.camera = cam

    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 900
    scene.render.filepath = os.path.join(render_dir, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {scene.render.filepath}")


def main():
    for name, height in TRAY_HEIGHT_TIERS.items():
        clear_scene()
        bracket = build_bracket(height)
        print(f"{name}: volume={mesh_volume(bracket):.1f}mm3 (sanity check only)")
        if EXPORT_STL:
            export_stl(bracket, f"corner_bracket_v1_{name}.stl")
        render_iso(name, bracket)


if __name__ == "__main__":
    main()
