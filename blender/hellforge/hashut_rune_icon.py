#!/usr/bin/env python3
"""Portable Hellforge — Hashut rune icon, single-print flat lid appliqué, v1.

Blender/bpy script - paste into the Script Editor and run (Alt+P), or:
  blender --background --python hashut_rune_icon.py

Same idea as hashut_lid_icon.py (the bull skull) but the OTHER Hashut icon
from the token project - the V/E rune (blender/tokens/rune_contours.json,
traced from blender/tokens/source/rune_hashut.jpeg). Much simpler shape:
one contour, no holes, nearly perfectly square (aspect 1.00002) - so
unlike the bull, sized to print in ONE piece, no cutting/splitting logic
needed at all. RUNE_W just has to stay under the bed margin on both axes,
which a square shape makes trivial to guarantee.

ICON size is picked to land under BED_MARGIN_TARGET (same 250mm real
margin under the 260mm bed used throughout this project) - adjust and
rerun if the actual lid target size turns out different once the box is
in hand.
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
CONTOURS_PATH = "/Users/mannil/studio-m/blender/tokens/rune_contours.json"
EXPORT_DIR = "/Users/mannil/studio-m/blender/hellforge/output_lid_icon"
EXPORT_STL = True

RENDER_IMAGES = True
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1200, 1200)

OVERSHOOT = 1.0

TARGET_REAL_W = 245.0   # the actual real-world printed width wanted, comfortably under BED_MARGIN_TARGET
THICKNESS = 3.0         # flat appliqué, glued onto the lid - matches the bull icon's own thickness

BED_MARGIN_TARGET = 250.0   # same real margin under the 260mm bed used for the bull icon


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


def render_iso(name, objs):
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
    cam_obj.location = center + mathutils.Vector((0.0, 0.0, 1.0)) * max(size * 1.6, 20.0)
    scene.render.filepath = os.path.join(RENDER_DIR, f"{name}_top.png")
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


def main():
    clear_scene()
    with open(CONTOURS_PATH) as f:
        contours = json.load(f)
    outer = [c for c in contours if not c["hole"]]
    assert len(outer) == 1 and not any(c["hole"] for c in contours), \
        "rune_contours.json is no longer a single holeless contour - this script assumed that, re-check"

    xs = [p[0] for p in outer[0]["points"]]
    ys = [p[1] for p in outer[0]["points"]]
    bbox_w_frac = max(xs) - min(xs)
    bbox_h_frac = max(ys) - min(ys)
    # the traced outline doesn't fill its own 0..1 UV unit square (real
    # padding around the ink, bbox_w_frac=0.802 not 1.0) - scaling by a
    # flat "mm per UV unit" would undershoot the real printed size by that
    # same ~20% (caught by comparing the exported mesh's actual bounds
    # against the intended target, not assumed to match). Scale by the
    # real ink bbox fraction instead, so TARGET_REAL_W is what actually
    # comes out of the printer, not what goes into the UV math.
    scale = TARGET_REAL_W / bbox_w_frac
    rune_h = bbox_h_frac * scale
    print(f"Rune: target {TARGET_REAL_W:.1f}mm real width -> scale={scale:.1f}mm/UV-unit, "
          f"ink bbox {bbox_w_frac:.3f}x{bbox_h_frac:.3f} of the unit square, real size {TARGET_REAL_W:.1f}x{rune_h:.1f}mm")

    pts = dedupe_closed_loop([(u * scale, v * scale) for u, v in outer[0]["points"]])
    solid = build_slab(pts, 0.0, THICKNESS, "hashut_rune")

    w, h = mesh_bounds_xy(solid)
    fits = w <= BED_MARGIN_TARGET and h <= BED_MARGIN_TARGET
    print(f"rune piece: {w:.1f}x{h:.1f}mm volume={mesh_volume(solid):.0f}mm3 "
          f"{'OK, one print' if fits else 'TOO BIG for one print - lower RUNE_W'}")
    assert fits, "rune doesn't fit BED_MARGIN_TARGET - lower RUNE_W and rerun"

    if EXPORT_STL:
        export_stl(solid, "hashut_rune.stl")
    if RENDER_IMAGES:
        render_iso("hashut_rune", [solid])

    print("Done. 1 piece total.")


if __name__ == "__main__":
    main()
