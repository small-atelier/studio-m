#!/usr/bin/env python3
"""Portable Hellforge — decorative corner trim/protector, v1.

Blender/bpy script - paste into the Script Editor and run (Alt+P), or:
  blender --background --python corner_trim.py

Flat L-shaped bracket meant to sit right at a lid/box corner, one arm
along each edge - same "flat appliqué glued onto a surface" approach as
the Hashut icon pieces (hashut_lid_icon.py / hashut_rune_icon.py), not a
3D wrap-around corner cap, since real box wall thickness/edge profile
isn't known yet (still pre-purchase). Beyond plain functional corner
protection: a beveled/faceted edge (reads as forged plate, done with one
Bevel modifier rather than hand-sculpted facets), raised rivet bosses,
a rune emblem embossed at the bracket's tip (reuses rune_contours.json,
the same traced icon as hashut_rune_icon.py), and a standing loop partway
along one arm sized for the exterior sketch's chain to actually thread
through, not just rest on top of the box.

Talon/claw shape considered and dropped - kept as a plain L-bracket
silhouette per feedback.

Boolean approach follows [[feedback_blender_boolean_fragility]]: rivets
and the chain loop are each unioned on as their own separate object (not
joined into one pre-union blob first), the rune emboss is its own single
union pass, and the bevel is applied LAST, after every union, so it only
ever has to fair one already-finished solid's edges rather than survive a
boolean against a non-manifold intermediate shape.
"""
import bpy
import bmesh
import json
import math
import mathutils
import os

# ============================================================
# CONFIG (all mm)
# ============================================================
RUNE_CONTOURS_PATH = "/Users/mannil/studio-m/blender/tokens/rune_contours.json"
EXPORT_DIR = "/Users/mannil/studio-m/blender/hellforge/output_corner_trim"
EXPORT_STL = True

RENDER_IMAGES = True
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1400, 1400)

OVERSHOOT = 1.0

ARM_LEN = 70.0      # each arm's length, from the box corner tip outward
ARM_W = 18.0        # arm width
PLATE_T = 2.5        # base plate thickness - flat appliqué, glued down, not structural

BEVEL_WIDTH = 0.8    # chamfers every outer edge - the "forged plate" look, not hand-sculpted facets
BEVEL_SEGMENTS = 2

RIVET_D = 3.0
RIVET_PROUD = 1.2    # how far each rivet stands above the plate
RIVET_EMBED = 0.4    # how far it sinks into the plate, for a clean union (not a flush/coincident face)
# (arm, offset_from_tip) - "arm" is 'x' or 'y', offset is distance along
# that arm's centerline from the tip, kept clear of the rune boss near the
# tip and the elbow near the far end
RIVET_POSITIONS = [
    ('x', 24.0), ('x', 44.0), ('x', 60.0),
    ('y', 24.0), ('y', 44.0), ('y', 60.0),
]

RUNE_BOSS_D = 16.0
RUNE_BOSS_PROUD = 1.0
RUNE_BOSS_EMBED = 0.4
RUNE_TARGET_W = 11.0   # real printed width of the embossed rune (see the scaling note in hashut_rune_icon.py)
RUNE_EMBOSS_PROUD = 0.5   # how far the rune itself stands above the boss's own top face
RUNE_BOSS_CENTER = (10.0, 10.0)   # near the tip, inset so the boss doesn't hang off either outer edge

CHAIN_LOOP_ARM = 'x'          # which arm gets the loop
CHAIN_LOOP_OFFSET = 48.0      # distance along that arm's centerline from the tip
CHAIN_LOOP_OUTER_W = 10.0     # loop footprint along the arm direction
CHAIN_LOOP_OUTER_H = 7.0      # loop standing height above the plate
CHAIN_LOOP_THICKNESS = 3.0    # loop wall thickness (also its depth across the arm width)
CHAIN_HOLE_D = 4.5            # clear enough for a small chain link / jump ring


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


def join_objects(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    joined = bpy.context.active_object
    joined.name = name
    return joined


def build_slab(outline, z0, z1, name):
    bm = bmesh.new()
    bottom = [bm.verts.new((x, y, z0)) for x, y in outline]
    top = [bm.verts.new((x, y, z1)) for x, y in outline]
    bm.faces.new(reversed(bottom))
    bm.faces.new(top)
    n = len(outline)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def add_cylinder(diameter, z_range, loc_xy, vertices=32):
    z0, z1 = z_range
    bpy.ops.mesh.primitive_cylinder_add(
        radius=diameter / 2, depth=z1 - z0,
        location=(loc_xy[0], loc_xy[1], (z0 + z1) / 2), vertices=vertices,
    )
    return bpy.context.active_object


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


def mesh_bounds_xy(obj):
    xs = [(obj.matrix_world @ mathutils.Vector(c)).x for c in obj.bound_box]
    ys = [(obj.matrix_world @ mathutils.Vector(c)).y for c in obj.bound_box]
    return max(xs) - min(xs), max(ys) - min(ys)


def compute_scene_bounds(objs):
    xs, ys, zs = [], [], []
    for obj in objs:
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ mathutils.Vector(corner)
            xs.append(world_corner.x)
            ys.append(world_corner.y)
            zs.append(world_corner.z)
    center = mathutils.Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2))
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


def render_iso(name, objs, top_down=False):
    os.makedirs(RENDER_DIR, exist_ok=True)
    others = [o for o in bpy.data.objects if o.type == 'MESH' and o not in objs]
    prev_hide = {o.name: o.hide_render for o in others}
    for o in others:
        o.hide_render = True
    center, size = compute_scene_bounds(objs)
    cam_obj = setup_camera_and_light(center)
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = RENDER_RESOLUTION[0]
    scene.render.resolution_y = RENDER_RESOLUTION[1]
    direction = mathutils.Vector((0.0, 0.0, 1.0)) if top_down else mathutils.Vector((0.6, -1.0, 0.7)).normalized()
    cam_obj.location = center + direction * max(size * 2.0, 20.0)
    scene.render.filepath = os.path.join(RENDER_DIR, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {scene.render.filepath}")
    for o in others:
        o.hide_render = prev_hide[o.name]


def export_stl(obj, filename):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = os.path.join(EXPORT_DIR, filename)
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"Exported {path}")


def dedupe_closed_loop(points, tol=1e-9):
    if len(points) > 1:
        x0, y0 = points[0]
        x1, y1 = points[-1]
        if abs(x0 - x1) < tol and abs(y0 - y1) < tol:
            return points[:-1]
    return points


# ============================================================
# BUILD
# ============================================================
def build_plate_outline():
    """L-shape: the tip at the origin sits exactly at the box's corner
    vertex, arms extend along the two edges. 6 vertices, standard angle-
    bracket silhouette."""
    return [
        (0.0, 0.0),
        (ARM_LEN, 0.0),
        (ARM_LEN, ARM_W),
        (ARM_W, ARM_W),
        (ARM_W, ARM_LEN),
        (0.0, ARM_LEN),
    ]


def arm_point(arm, offset):
    """Point on an arm's centerline, `offset` from the tip."""
    return (offset, ARM_W / 2.0) if arm == 'x' else (ARM_W / 2.0, offset)


def build_rivet(loc_xy):
    return add_cylinder(RIVET_D, (PLATE_T - RIVET_EMBED, PLATE_T + RIVET_PROUD), loc_xy, vertices=20)


def build_rune_boss_and_emboss():
    boss = add_cylinder(RUNE_BOSS_D, (PLATE_T - RUNE_BOSS_EMBED, PLATE_T + RUNE_BOSS_PROUD),
                         RUNE_BOSS_CENTER, vertices=32)

    with open(RUNE_CONTOURS_PATH) as f:
        contours = json.load(f)
    outer = [c for c in contours if not c["hole"]]
    xs = [p[0] for p in outer[0]["points"]]
    ys = [p[1] for p in outer[0]["points"]]
    bbox_w = max(xs) - min(xs)
    bbox_h = max(ys) - min(ys)
    bbox_cx = (max(xs) + min(xs)) / 2.0
    bbox_cy = (max(ys) + min(ys)) / 2.0
    scale = RUNE_TARGET_W / bbox_w
    rune_h = bbox_h * scale
    # centered on RUNE_BOSS_CENTER: shift so the ink's own bbox center
    # lands there, not the raw UV origin
    ox = RUNE_BOSS_CENTER[0] - bbox_cx * scale
    oy = RUNE_BOSS_CENTER[1] - bbox_cy * scale
    pts = dedupe_closed_loop([(u * scale + ox, v * scale + oy) for u, v in outer[0]["points"]])
    z0 = PLATE_T + RUNE_BOSS_PROUD - 0.3   # embeds slightly into the boss's own top for a clean union
    emboss = build_slab(pts, z0, PLATE_T + RUNE_BOSS_PROUD + RUNE_EMBOSS_PROUD, "rune_emboss")
    return boss, emboss, rune_h


def build_chain_loop():
    """A standing loop (outer rounded rect minus an inner hole, extruded)
    partway along one arm - sized for a small chain link to thread
    through, not just decorative. Oriented so the hole axis runs along the
    arm's length, so a chain draped across the lid naturally threads
    through it rather than needing to loop sideways."""
    cx, cy = arm_point(CHAIN_LOOP_ARM, CHAIN_LOOP_OFFSET)
    half_w = CHAIN_LOOP_OUTER_W / 2.0
    half_t = CHAIN_LOOP_THICKNESS / 2.0
    z0, z1 = PLATE_T - 0.4, PLATE_T + CHAIN_LOOP_OUTER_H
    if CHAIN_LOOP_ARM == 'x':
        outline = [(cx - half_t, cy - half_w), (cx + half_t, cy - half_w),
                   (cx + half_t, cy + half_w), (cx - half_t, cy + half_w)]
    else:
        outline = [(cx - half_w, cy - half_t), (cx + half_w, cy - half_t),
                   (cx + half_w, cy + half_t), (cx - half_w, cy + half_t)]
    loop = build_slab(outline, z0, z1, "chain_loop")
    hole_z = PLATE_T + CHAIN_LOOP_OUTER_H - CHAIN_HOLE_D / 2.0 - 1.5
    hole_axis = (0, 1, 0) if CHAIN_LOOP_ARM == 'x' else (1, 0, 0)
    bpy.ops.mesh.primitive_cylinder_add(radius=CHAIN_HOLE_D / 2.0, depth=ARM_W + 2 * OVERSHOOT,
                                         location=(cx, cy, hole_z), vertices=24)
    hole_cutter = bpy.context.active_object
    if CHAIN_LOOP_ARM == 'x':
        hole_cutter.rotation_euler = (math.radians(90), 0.0, 0.0)
    else:
        hole_cutter.rotation_euler = (0.0, math.radians(90), 0.0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    apply_boolean(loop, hole_cutter, 'DIFFERENCE')
    return loop


def main():
    clear_scene()

    plate = build_slab(build_plate_outline(), 0.0, PLATE_T, "corner_trim_plate")

    rivets = [build_rivet(arm_point(arm, off)) for arm, off in RIVET_POSITIONS]
    apply_boolean(plate, join_objects(rivets, "rivets"), 'UNION')

    boss, emboss, rune_h = build_rune_boss_and_emboss()
    apply_boolean(plate, boss, 'UNION')
    apply_boolean(plate, emboss, 'UNION')
    print(f"rune emboss real size: {RUNE_TARGET_W:.1f}x{rune_h:.1f}mm")

    loop = build_chain_loop()
    apply_boolean(plate, loop, 'UNION')

    # bevel LAST, once the solid is finished - see module docstring
    apply_bevel(plate, BEVEL_WIDTH, BEVEL_SEGMENTS)

    w, h = mesh_bounds_xy(plate)
    print(f"corner trim: {w:.1f}x{h:.1f}mm footprint, volume={mesh_volume(plate):.0f}mm3")

    if EXPORT_STL:
        export_stl(plate, "corner_trim_v1.stl")
    if RENDER_IMAGES:
        render_iso("corner_trim_v1_iso", [plate])
        render_iso("corner_trim_v1_top", [plate], top_down=True)

    print("Done.")


if __name__ == "__main__":
    main()
