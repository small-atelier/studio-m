#!/usr/bin/env python3
"""Spearhead board — corner protector, v2 (decorated).

Blender/bpy script - paste into the Script Editor and run (Alt+P), or:
  blender --background --python board_corner_v2.py

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

Decoration is engraved only - either outer wall can be the bed face, and
the lips sit on the play surface, so nothing may stand proud:
- a plate-border groove on each outer wall,
- engraved rivet rings inside each border's corners,
- a taper on each lip's play-side edge along the hypotenuse, so minis and
  terrain ride over the step instead of catching on it.
All decoration cutters are disjoint and joined into one mesh, cut in a
single boolean after the pocket.

Board convention: board corner at the origin, board occupies X>=0, Y>=0,
Z in [LIP, LIP + POCKET_HEIGHT].

Export orientation: as it sits on the table, flat on the bottom lip. Both
walls stand vertical with matching layer lines and the top lip's play face
prints last. The top lip overhangs the pocket and needs supports from the
bed inside the pocket; their scars land on the lip face against the board.
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

# Plate border on each outer wall
BORDER_INSET = 3.0   # groove's outer edge, from the wall's edges
BORDER_WIDTH = 1.0
BORDER_DEPTH = 0.7

# Rivet rings, one inside each corner of the border
RIVET_OUTER_D = 3.2
RIVET_INNER_D = 1.8
RIVET_DEPTH   = 0.5
RIVET_OFFSET  = 2.5   # ring centre, in from the border's inner edge
RIVET_SEGMENTS = 32

# Lip taper along the hypotenuse, on the play side
TAPER_RUN  = 3.0   # how far in from the hypotenuse the taper reaches
TAPER_RISE = 1.2   # height removed at the edge (leaves LIP - RISE)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(SCRIPT_DIR, "output")
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

    decor = build_decoration_cutters()
    cut = body.modifiers.new("DecorCut", 'BOOLEAN')
    cut.operation = 'DIFFERENCE'
    cut.solver = 'EXACT'
    cut.object = decor
    apply_modifiers(body)
    bpy.data.objects.remove(decor, do_unlink=True)
    return body


# ============================================================
# DECORATION CUTTERS
# ============================================================
def add_prism(bm, pts, z0, z1, matrix):
    """Closed prism from a CCW local-XY polygon, transformed by matrix."""
    bottom = [bm.verts.new(matrix @ mathutils.Vector((x, y, z0))) for x, y in pts]
    top = [bm.verts.new(matrix @ mathutils.Vector((x, y, z1))) for x, y in pts]
    faces = [bm.faces.new(list(reversed(bottom))), bm.faces.new(top)]
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((bottom[i], bottom[j], top[j], top[i])))
    return faces


def add_ring(bm, outer, inner, z0, z1, matrix):
    """Closed ring prism between two CCW local-XY loops of equal length."""
    def loop(pts, z):
        return [bm.verts.new(matrix @ mathutils.Vector((x, y, z))) for x, y in pts]
    ob, ot, ib, it = loop(outer, z0), loop(outer, z1), loop(inner, z0), loop(inner, z1)
    faces = []
    n = len(outer)
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((ot[i], ot[j], it[j], it[i])))
        faces.append(bm.faces.new((ob[j], ob[i], ib[i], ib[j])))
        faces.append(bm.faces.new((ob[i], ob[j], ot[j], ot[i])))
        faces.append(bm.faces.new((ib[j], ib[i], it[i], it[j])))
    return faces


def rect(u0, u1, v0, v1):
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


def circle(cu, cv, r):
    return [(cu + r * math.cos(2 * math.pi * i / RIVET_SEGMENTS),
             cv + r * math.sin(2 * math.pi * i / RIVET_SEGMENTS))
            for i in range(RIVET_SEGMENTS)]


def add_wall_decoration(bm, matrix):
    """Border groove + rivet rings in wall-local coords: u along the wall
    from the board corner, v up the board edge, local z out of the face."""
    u0, u1 = BORDER_INSET, ARM - BORDER_INSET
    v0, v1 = BORDER_INSET, TOTAL_HEIGHT - BORDER_INSET
    bw = BORDER_WIDTH
    faces = add_ring(bm, rect(u0, u1, v0, v1), rect(u0 + bw, u1 - bw, v0 + bw, v1 - bw),
                     -BORDER_DEPTH, 1.0, matrix)
    k = bw + RIVET_OFFSET
    for cu in (u0 + k, u1 - k):
        for cv in (v0 + k, v1 - k):
            faces += add_ring(bm, circle(cu, cv, RIVET_OUTER_D / 2),
                              circle(cu, cv, RIVET_INNER_D / 2),
                              -RIVET_DEPTH, 1.0, matrix)
    return faces


def build_decoration_cutters():
    bm = bmesh.new()

    # Wall on y=-WALL: local (u, v, z) -> world (u, -WALL - z, v)
    wall_a = (mathutils.Matrix.Translation((0.0, -WALL, 0.0))
              @ mathutils.Matrix.Rotation(math.radians(90), 4, 'X'))
    add_wall_decoration(bm, wall_a)

    # Wall on x=-WALL: mirror of wall A across the diagonal (flips winding)
    swap_xy = mathutils.Matrix(((0, 1, 0, 0), (1, 0, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)))
    bmesh.ops.reverse_faces(bm, faces=add_wall_decoration(bm, swap_xy @ wall_a))

    # Lip tapers: local x = s (inward from the hypotenuse), local y = world z,
    # local z runs along the hypotenuse.
    hyp = ARM - WALL                      # hypotenuse line: x + y = hyp
    r2 = math.sqrt(0.5)
    taper = mathutils.Matrix((
        (-r2, 0.0, -r2, hyp / 2),
        (-r2, 0.0,  r2, hyp / 2),
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    ))
    h, run, rise = TOTAL_HEIGHT, TAPER_RUN, TAPER_RISE
    slope = rise / run
    top = [(-1.0, h - rise - slope), (run + 1.0, h + slope), (-1.0, h + 3.0)]
    bottom = [(-1.0, rise + slope), (-1.0, -3.0), (run + 1.0, -slope)]
    half = ARM * 1.5
    add_prism(bm, top, -half, half, taper)
    add_prism(bm, bottom, -half, half, taper)

    bm.normal_update()
    mesh = bpy.data.meshes.new("DecorCutters")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("DecorCutters", mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def orient_for_print(obj):
    """Bottom lip on the bed at z=0, centred in XY."""
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
        "lip": (0.6, 0.6, 1.6),       # play-side lip taper
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
render_views(corner, "board_corner_v2")
orient_for_print(corner)
report(corner)
export_stl(corner, "board_corner_v2.stl")
