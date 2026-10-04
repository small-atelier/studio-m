#!/usr/bin/env python3
"""Portable Hellforge — small hand-tool props (hammer, tongs), v1.

Blender/bpy script - paste into the Script Editor and run (Alt+P), or:
  blender --background --python tools_props.py

Standalone scatter props, not sockets or toppers - meant to be glued
directly onto the finished resin skin near a couple of the "worker"
Infernal Cohort infantry, the way real tools get left lying around a
working forge. Not baked into forge_floor_tiles_v3.py's geometry - keeping
them separate avoids adding more boolean risk to that pipeline this late,
and lets them be placed by hand wherever looks right once the floor is
actually painted.

Both are built almost entirely as single silhouette extrusions (see
[[feedback_functional_parts_pipeline]]) - the hammer is ONE polygon, no
boolean at all. The tongs need one short union (pivot + 2 arms, each arm
only overlapping the shared pivot, never each other - the safe case from
[[feedback_blender_boolean_fragility]]).

Scale note: these sit next to 28mm miniatures, so they're small - a few mm
across. Positions/sizing are a first pass, not test-fitted against a
printed part yet.
"""
import bpy
import bmesh
import math
import os

# ============================================================
# CONFIG (all mm)
# ============================================================
EXPORT_DIR = "/Users/mannil/studio-m/blender/hellforge/output_props"
EXPORT_STL = True
RENDER_IMAGES = True
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")

PROP_THICKNESS = 2.5   # how tall each prop stands off the floor, lying flat

# Suggested scatter positions on the finished floor (global XY, same frame
# as forge_floor_layout.py / forge_floor_tiles_v3.py) - glued on by hand,
# not cut into the tile geometry. Picked near an Infernal Cohort worker on
# each tile, clear of every socket - not re-verified by the layout
# checker script, worth a quick visual check before committing to glue.
SUGGESTED_PLACEMENTS = [
    ("hammer", 70.0, 165.0, 30.0),    # tile_a, near Infernal Cohort 2/10
    ("tongs", 350.0, 195.0, -20.0),   # tile_b, near Infernal Cohort 7
]


# ============================================================
# HELPERS (shared convention - see forge_floor_tiles_v3.py)
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


def build_slab(outline, z0, z1, name):
    """Extrude a flat polygon straight up - same helper as
    forge_floor_tiles_v3.py, duplicated here so this script stays
    standalone/pasteable on its own."""
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


def mesh_volume(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    volume = bm.calc_volume()
    bm.free()
    return volume


def render_iso(name, obj):
    import mathutils
    os.makedirs(RENDER_DIR, exist_ok=True)
    center = mathutils.Vector(obj.bound_box[0]) + (mathutils.Vector(obj.bound_box[6]) - mathutils.Vector(obj.bound_box[0])) / 2
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
    cam.location = center + mathutils.Vector((0.7, -1.0, 0.8)).normalized() * max(size * 6.0, 15.0)
    bpy.context.scene.camera = cam

    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 800
    scene.render.filepath = os.path.join(RENDER_DIR, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {scene.render.filepath}")


def export_stl(obj, filename):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = os.path.join(EXPORT_DIR, filename)
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"Exported {path}")


# ============================================================
# HAMMER - a single T-shaped silhouette, no boolean at all
# ============================================================
HAMMER_HANDLE_LEN = 10.0
HAMMER_HANDLE_HALF_W = 0.75
HAMMER_HEAD_LEN = 4.0
HAMMER_HEAD_HALF_W = 2.5


def build_hammer():
    hw, hhw = HAMMER_HANDLE_HALF_W, HAMMER_HEAD_HALF_W
    hl, hd = HAMMER_HANDLE_LEN, HAMMER_HEAD_LEN
    outline = [
        (-hw, 0.0), (hw, 0.0), (hw, hl),
        (hhw, hl), (hhw, hl + hd), (-hhw, hl + hd),
        (-hhw, hl), (-hw, hl),
    ]
    obj = build_slab(outline, 0.0, PROP_THICKNESS, "hammer")
    return obj


# ============================================================
# TONGS - pivot + 2 arms, each arm only overlaps the shared pivot (never
# each other) - the safe union case
# ============================================================
TONGS_ARM_LEN = 9.0
TONGS_ARM_HALF_W = 0.6
TONGS_SPREAD_DEG = 16.0   # half-angle between the two arms
TONGS_PIVOT_RADIUS = 1.3
TONGS_EMBED = 0.4         # how far each arm's base overlaps into the pivot


def _add_arm(angle_deg):
    """A thin box lying along +Y, base at the origin, then rotated about Z
    so it points out from the pivot at the given angle.

    Order matters here: the +Y offset has to be BAKED into the mesh data
    (transform_apply with location=True) before the rotation is applied,
    otherwise the object's `.location` gets overwritten before it's ever
    used and the mesh stays centered on the origin - both arms then come
    out symmetric about the pivot (an hourglass/bowtie) instead of each
    extending outward from it. Caught by looking at the render, not
    something the volume check would have flagged."""
    length = TONGS_ARM_LEN + TONGS_EMBED
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.0, length / 2 - TONGS_EMBED, PROP_THICKNESS / 2))
    obj = bpy.context.active_object
    obj.scale = (TONGS_ARM_HALF_W * 2, length, PROP_THICKNESS)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=True)
    obj.rotation_euler = (0.0, 0.0, math.radians(angle_deg))
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    return obj


def build_tongs():
    bpy.ops.mesh.primitive_cylinder_add(
        radius=TONGS_PIVOT_RADIUS, depth=PROP_THICKNESS,
        location=(0.0, 0.0, PROP_THICKNESS / 2), vertices=16,
    )
    pivot = bpy.context.active_object
    pivot.name = "tongs"

    arm1 = _add_arm(-TONGS_SPREAD_DEG)
    apply_boolean(pivot, arm1, 'UNION')
    arm2 = _add_arm(TONGS_SPREAD_DEG)
    apply_boolean(pivot, arm2, 'UNION')

    return pivot


# ============================================================
# MAIN
# ============================================================
def main():
    builders = {"hammer": build_hammer, "tongs": build_tongs}
    for name, builder in builders.items():
        clear_scene()
        obj = builder()
        print(f"{name}: volume={mesh_volume(obj):.1f}mm3, dims={tuple(round(d, 1) for d in obj.dimensions)}")
        if EXPORT_STL:
            export_stl(obj, f"{name}.stl")
        if RENDER_IMAGES:
            render_iso(name, obj)
    print("Done.")


if __name__ == "__main__":
    main()
