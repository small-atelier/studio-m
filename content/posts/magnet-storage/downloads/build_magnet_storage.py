"""
Magnet storage bar - a solid bar with blind cylinder wells, all opening on
the top face, that hold the full magnet stock as stacks. Two rows back to
back: every well sits against one of the two long faces, and a full-height
slot runs from the well out through that face, so a finger (or a pin, for
the small sizes) can push the stack up from the side however low it runs.
Slot width is a fraction of the magnet diameter, so the magnets stay in.

The stock is split over COPIES identical bars (one STL, printed that many
times). Wells per size are derived from TARGET_DEPTH: how many discs fit
in one well at that depth, then enough wells for one bar's share. The
deepest planned stack (per_well x nominal thickness x STACK_TOLERANCE +
HEADROOM) sets the bar height, and every well runs that full depth, so
the sizes with shorter stacks get refill room. Hole diameter is nominal
+ HOLE_CLEARANCE for FDM.

Printed upright (wells vertical, no supports). Single material, STL only.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_magnet_storage.py
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_magnet_storage.py -- --no-render
"""

import bpy
import bmesh
import math
import mathutils
import os
import sys

# ============================================================
# CLI ARGS
# ============================================================
def _parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return "--no-render" not in argv


RENDER_IMAGES = _parse_args()

# ============================================================
# CONFIG (all mm)
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(SCRIPT_DIR, "output")
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1400, 1400)

HOLE_CLEARANCE  = 0.3    # on diameter, FDM slip fit
STACK_TOLERANCE = 1.05   # disc thickness is nominal; allow +5% over a long stack
HEADROOM        = 1.0    # above a full stack
CIRCLE_SEGMENTS = 96

TARGET_DEPTH  = 145.0    # max well depth; sets how many discs go in one well
COPIES        = 2        # identical bars printed; each holds count / COPIES

END_WALL    = 5.0        # first/last well edge to the bar's short ends
FACE_WALL   = 2.0        # well edge to its long face (the slot cuts through it)
CENTRE_WALL = 6.0        # between the two back-to-back rows
BASE        = 3.0        # solid under the deepest well
EMBED       = 0.5        # cutter overshoot past every outer face

SLOT_WIDTH_FRAC = 0.5    # slot width as a fraction of the magnet diameter
SLOT_LIP        = 1.0    # solid kept between the slot bottom and the well floor

# Magnet (diameter, thickness), stock count, and the wall between
# neighbouring wells of that size. Each side is laid out left to right
# in this order; big wells face small ones to keep the bar narrow.
# wells=N instead of a count: a fixed number of full-depth wells for
# odd sizes (thickness unknown, fill as many as fit).
# fill=True: after sizing, extra wells of that group are added until its
# side is as long as the other side.
FRONT = [
    dict(label="20x1", diam=20.0, thick=1.0, count=400, wall=6.0),
    dict(label="19",   diam=19.0, wells=1, wall=6.0),
    dict(label="16",   diam=16.0, wells=1, wall=6.0),
    dict(label="10x3", diam=10.0, thick=3.0, count=100, wall=4.0),
    dict(label="10",   diam=10.0, wells=1, wall=4.0),
]
BACK = [
    dict(label="5x3",  diam=5.0,  thick=3.0, count=400, wall=4.0, fill=True),
    dict(label="6x3",  diam=6.0,  thick=3.0, count=100, wall=4.0),
]

# ============================================================
# LAYOUT
# ============================================================
def hole_diam(g):
    return g["diam"] + HOLE_CLEARANCE


def plan_group(g):
    """Wells for one magnet size: (wells, per_well, depth). Fixed-count
    groups return per_well None and depth 0 - they never set the height."""
    if "wells" in g:
        return g["wells"], None, 0.0
    max_per_well = int((TARGET_DEPTH - HEADROOM) / (g["thick"] * STACK_TOLERANCE))
    count = math.ceil(g["count"] / COPIES)
    n = math.ceil(count / max_per_well)
    per_well = math.ceil(count / n)
    depth = per_well * g["thick"] * STACK_TOLERANCE + HEADROOM
    return n, per_well, depth


def plan_side(groups, extra=0):
    """One row along X starting at x=0; `extra` wells go to the fill group.
    Returns (wells as (x, d, depth, g), length, info)."""
    wells, info = [], []
    x = 0.0
    prev = None
    for g in groups:
        n, per_well, depth = plan_group(g)
        if g.get("fill") and extra:
            n += extra
            per_well = math.ceil(math.ceil(g["count"] / COPIES) / n)
        d = hole_diam(g)
        for _ in range(n):
            if prev is not None:
                x += hole_diam(prev) / 2 + max(prev["wall"], g["wall"]) + d / 2
            else:
                x = d / 2
            wells.append((x, d, depth, g))
            prev = g
        info.append((g["label"], n, per_well, depth))
    return wells, x + hole_diam(prev) / 2, info


def plan_filled_side(groups, target_len):
    """Plan a side, adding fill wells while it stays within target_len."""
    extra = 0
    side = plan_side(groups)
    if not any(g.get("fill") for g in groups):
        return side
    while True:
        more = plan_side(groups, extra + 1)
        if more[1] > target_len:
            return side
        extra, side = extra + 1, more


def plan_wells():
    """Front row against the -Y face, back row against +Y, both centred in X.
    Returns (wells as (x, y, d, depth, g, face_sign), size_x, size_y, info)."""
    front, front_len, front_info = plan_side(FRONT)
    back, back_len, back_info = plan_side(BACK)
    if back_len < front_len:
        back, back_len, back_info = plan_filled_side(BACK, front_len)
    else:
        front, front_len, front_info = plan_filled_side(FRONT, back_len)
    front_d = max(hole_diam(g) for g in FRONT)
    back_d = max(hole_diam(g) for g in BACK)
    size_x = max(front_len, back_len) + 2 * END_WALL
    size_y = 2 * FACE_WALL + front_d + CENTRE_WALL + back_d

    wells = []
    for row, row_len, sign in ((front, front_len, -1), (back, back_len, 1)):
        for x, d, depth, g in row:
            y = sign * (size_y / 2 - FACE_WALL - d / 2)
            wells.append((x - row_len / 2, y, d, depth, g, sign))
    return wells, size_x, size_y, front_info + back_info

# ============================================================
# UTILITIES
# ============================================================
def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for block_list in (bpy.data.meshes, bpy.data.cameras, bpy.data.lights):
        for block in list(block_list):
            if block.users == 0:
                block_list.remove(block)


def new_object_from_bmesh(bm, name):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def add_box(bm, cx, cy, z0, sx, sy, sz, angle=0.0):
    geom = bmesh.ops.create_cube(bm, size=1.0)
    verts = geom["verts"]
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=verts)
    bmesh.ops.rotate(bm, verts=verts, cent=(0, 0, 0), matrix=mathutils.Matrix.Rotation(angle, 3, 'Z'))
    bmesh.ops.translate(bm, vec=(cx, cy, z0 + sz / 2), verts=verts)


def add_cylinder(bm, cx, cy, z0, diam, height):
    geom = bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=CIRCLE_SEGMENTS,
        radius1=diam / 2, radius2=diam / 2, depth=height,
    )
    bmesh.ops.translate(bm, vec=(cx, cy, z0 + height / 2), verts=geom["verts"])


def boolean_difference(target, cutter):
    mod = target.modifiers.new("cut", 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    mod.object = cutter
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def nonmanifold_edges(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bad = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return bad

# ============================================================
# GEOMETRY
# ============================================================
def build_block():
    """The deepest planned stack sets the bar height; every well then runs
    the full depth down to BASE, so the shallower sizes get refill room."""
    wells, size_x, size_y, info = plan_wells()
    height = max(w[3] for w in wells) + BASE
    depth = height - BASE

    bm = bmesh.new()
    add_box(bm, 0, 0, 0, size_x, size_y, height)
    block = new_object_from_bmesh(bm, "magnet_storage")

    # wells: none overlap each other, so one joined cutter, one boolean
    bm = bmesh.new()
    for x, y, d, _, _, _ in wells:
        add_cylinder(bm, x, y, BASE, d, depth + EMBED)
    boolean_difference(block, new_object_from_bmesh(bm, "well_cutters"))

    # slots: separate pass - each overlaps its own well
    bm = bmesh.new()
    for x, y, d, _, g, sign in wells:
        _add_slot(bm, x, y, g, sign, BASE, height, size_y)
    boolean_difference(block, new_object_from_bmesh(bm, "slot_cutters"))

    print(f"Bar {size_x:.1f} x {size_y:.1f} x {height:.1f} mm, wells {depth:.1f} deep")
    groups = {g["label"]: g for g in FRONT + BACK}
    for label, n, per, _ in info:
        g = groups[label]
        if per is None:
            print(f"  {n:2d} x {label} well, fill as many as fit")
            continue
        full = int((depth - HEADROOM) / (g["thick"] * STACK_TOLERANCE) + 1e-6)
        print(f"  {n:2d} x {label} wells, {per}/well planned, {full}/well max")
    print(f"  non-manifold edges: {nonmanifold_edges(block)}")
    return block


def _add_slot(bm, x, y, g, sign, z_floor, z_top, size_y):
    """Full-height box from the well centre out through its long face. Starts
    SLOT_LIP above the well floor - keeps the bottom disc from sliding out and
    avoids a cutter face coplanar with the floor."""
    width = g["diam"] * SLOT_WIDTH_FRAC
    y_face = sign * (size_y / 2 + EMBED)
    z0 = z_floor + SLOT_LIP
    add_box(bm, x, (y + y_face) / 2, z0, width, abs(y_face - y), z_top + EMBED - z0)

# ============================================================
# RENDER
# ============================================================
def apply_color(obj, rgba):
    mat = bpy.data.materials.new("block")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = rgba
    obj.data.materials.append(mat)


def setup_render_engine():
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = RENDER_RESOLUTION


def _clear_cameras_and_lights():
    for o in [o for o in bpy.context.scene.objects if o.type in ('CAMERA', 'LIGHT')]:
        bpy.data.objects.remove(o, do_unlink=True)


def _shot(name, suffix, cam_offset, target, ortho_scale=None, light_offset=None):
    _clear_cameras_and_lights()
    cam_data = bpy.data.cameras.new("Cam")
    if ortho_scale:
        cam_data.type = 'ORTHO'
        cam_data.ortho_scale = ortho_scale
    else:
        cam_data.lens = 50
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = target + cam_offset
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam

    light_data = bpy.data.lights.new("Sun", type='SUN')
    light_data.energy = 3.0
    light = bpy.data.objects.new("Sun", light_data)
    bpy.context.collection.objects.link(light)
    light.location = target + (light_offset or cam_offset)
    light.rotation_euler = (target - light.location).to_track_quat('-Z', 'Y').to_euler()

    path = os.path.join(RENDER_DIR, f"{name}_{suffix}.png")
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {path}")


def render_object(obj):
    setup_render_engine()
    dims = obj.dimensions
    center = mathutils.Vector((0, 0, dims.z / 2))
    d = max(dims) * 3.2
    top = mathutils.Vector((0, 0, dims.z))
    _shot(obj.name, "front", mathutils.Vector((d * 0.3, -d * 0.45, d * 0.35)), center,
          light_offset=mathutils.Vector((d * 0.3, -d * 0.5, d * 0.9)))
    _shot(obj.name, "back", mathutils.Vector((-d * 0.3, d * 0.45, d * 0.35)), center,
          light_offset=mathutils.Vector((-d * 0.3, d * 0.5, d * 0.9)))
    plan = max(dims.x, dims.y) * 1.15
    _shot(obj.name, "top", mathutils.Vector((0, -0.001, d)), top, ortho_scale=plan,
          light_offset=mathutils.Vector((d * 0.3, -d * 0.4, d)))

# ============================================================
# EXPORT
# ============================================================
def export_stl(obj):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    path = os.path.join(EXPORT_DIR, f"{obj.name}.stl")
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"Exported {path}")

# ============================================================
# RUN
# ============================================================
def main():
    clear_scene()
    block = build_block()
    export_stl(block)
    if RENDER_IMAGES:
        os.makedirs(RENDER_DIR, exist_ok=True)
        apply_color(block, (0.55, 0.58, 0.62, 1.0))
        render_object(block)
    print("Done.")


main()
