#!/usr/bin/env python3
"""Spearhead board — corner protector, v1.

Blender/bpy script - paste into the Script Editor and run (Alt+P), or:
  blender --background --python board_corner_v1.py

Wraps one corner of the double-sided board: two side walls along the frame
edges plus a lip over each face, so it holds whichever face is up and the
bottom lips double as feet. In plan it's a right triangle (the walls are
the legs, the hypotenuse is open) with the board corner nested into a
pocket cut through its full height.

Construction: one bevelled triangular prism minus one pocket box. The
pocket box overshoots the hypotenuse and sits strictly inside the prism
vertically, so the single boolean has no coincident faces. The bevel is
applied to the prism before the cut, so the pocket stays sharp-cornered
and a square board corner seats fully.

Board convention: board corner at the origin, board occupies X>=0, Y>=0,
Z in [LIP, LIP + POCKET_HEIGHT].

Export orientation: on its side, the Y-wall's outer face on the bed. The
other wall and both lips stand vertical, the pocket floor is the bed
wall's inner face - no supports, no bridges. The part is symmetric across
the diagonal, so which outer face gets the bed finish is chosen per print.
"""
import bpy
import bmesh
import math
import mathutils
import os

# ============================================================
# CONFIG (all mm)
# ============================================================
BOARD_THICKNESS = 45.0   # hardboard + foam + frame, at the edge
FIT_CLEARANCE   = 0.4    # FDM slip fit on the thickness

WALL  = 3.0    # side wall thickness (outside the frame edge)
LIP   = 2.0    # lip thickness over each face (step at the play-area corner)
ARM   = 40.0   # how far the part runs along each frame edge from the corner

CORNER_SEGMENTS = 12  # outer vertical corner: radius WALL around the board corner
EDGE_BEVEL     = 1.0   # rounding on all outer edges
BEVEL_SEGMENTS = 3

EXPORT_DIR = "/Users/mannil/studio-m/blender/spearhead-board/output"
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1200, 900)

POCKET_HEIGHT = BOARD_THICKNESS + FIT_CLEARANCE
TOTAL_HEIGHT = POCKET_HEIGHT + 2 * LIP


# ============================================================
# GEOMETRY
# ============================================================
def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for item in list(block):
            block.remove(item)


def prism_from_polygon(name, pts, z0, z1):
    """Extrude a CCW XY polygon from z0 to z1 into a closed solid."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bottom = [bm.verts.new((x, y, z0)) for x, y in pts]
    top = [bm.verts.new((x, y, z1)) for x, y in pts]
    bm.faces.new(list(reversed(bottom)))
    bm.faces.new(top)
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def apply_modifiers(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    for mod in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=mod.name)


def build_corner():
    # Outer outline: right triangle with legs on x=-WALL / y=-WALL and the
    # hypotenuse ending ARM along each frame edge. The outer vertex is a
    # radius-WALL arc centred on the board corner, so the wall keeps full
    # thickness all the way round.
    w = WALL
    arc = [(w * math.cos(a), w * math.sin(a))
           for a in (math.radians(180 + 90 * i / CORNER_SEGMENTS)
                     for i in range(CORNER_SEGMENTS + 1))]
    outline = [(ARM, -w), (-w, ARM)] + arc
    body = prism_from_polygon("BoardCorner", outline, 0.0, TOTAL_HEIGHT)

    bevel = body.modifiers.new("Bevel", 'BEVEL')
    bevel.width = EDGE_BEVEL
    bevel.segments = BEVEL_SEGMENTS
    bevel.limit_method = 'ANGLE'
    bevel.angle_limit = math.radians(30)
    apply_modifiers(body)

    far = ARM * 3
    pocket_outline = [(0.0, 0.0), (far, 0.0), (far, far), (0.0, far)]
    pocket = prism_from_polygon("Pocket", pocket_outline, LIP, LIP + POCKET_HEIGHT)

    cut = body.modifiers.new("PocketCut", 'BOOLEAN')
    cut.operation = 'DIFFERENCE'
    cut.solver = 'EXACT'
    cut.object = pocket
    apply_modifiers(body)
    bpy.data.objects.remove(pocket, do_unlink=True)
    return body


def orient_for_print(obj):
    """Outer face of the Y-wall (normal -Y) down onto the bed at z=0."""
    rot = mathutils.Matrix.Rotation(math.radians(90), 4, 'X')
    obj.data.transform(rot)
    zs = [v.co.z for v in obj.data.vertices]
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    obj.data.transform(mathutils.Matrix.Translation((
        -(min(xs) + max(xs)) / 2, -(min(ys) + max(ys)) / 2, -min(zs))))
    obj.data.update()


def report(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
    volume = bm.calc_volume()
    bm.free()
    dims = obj.dimensions
    print(f"[{obj.name}] dims {dims.x:.1f} x {dims.y:.1f} x {dims.z:.1f} mm, "
          f"volume {volume / 1000:.2f} cm3, non-manifold edges: {non_manifold}")


# ============================================================
# RENDER / EXPORT
# ============================================================
def render_views(obj, prefix):
    os.makedirs(RENDER_DIR, exist_ok=True)
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = RENDER_RESOLUTION
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.5

    mat = bpy.data.materials.new("Preview")
    mat.diffuse_color = (0.55, 0.45, 0.35, 1.0)
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.45, 0.35, 1.0)
    obj.data.materials.clear()
    obj.data.materials.append(mat)

    corners = [obj.matrix_world @ mathutils.Vector(b) for b in obj.bound_box]
    center = sum(corners, mathutils.Vector()) / 8
    size = max(obj.dimensions)

    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam
    target = bpy.data.objects.new("Target", None)
    target.location = center
    bpy.context.collection.objects.link(target)
    track = cam.constraints.new('TRACK_TO')
    track.target = target
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'

    sun_data = bpy.data.lights.new("Sun", type='SUN')
    sun_data.energy = 3.0
    sun = bpy.data.objects.new("Sun", sun_data)
    sun.rotation_euler = (math.radians(50), 0, math.radians(30))
    bpy.context.collection.objects.link(sun)

    views = {
        "outer": (-1.0, -1.0, 0.8),   # outside of the corner
        "pocket": (1.0, 1.0, 1.4),    # looking into the pocket
    }
    for name, d in views.items():
        cam.location = center + mathutils.Vector(d).normalized() * size * 2.2
        scene.render.filepath = os.path.join(RENDER_DIR, f"{prefix}_{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"Rendered {scene.render.filepath}")

    for o in (cam, target, sun):
        bpy.data.objects.remove(o, do_unlink=True)


def export_stl(obj, filename):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = os.path.join(EXPORT_DIR, filename)
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"Exported {path}")


# ============================================================
# MAIN
# ============================================================
clear_scene()
corner = build_corner()
report(corner)
render_views(corner, "board_corner_v1")
orient_for_print(corner)
report(corner)
export_stl(corner, "board_corner_v1.stl")
