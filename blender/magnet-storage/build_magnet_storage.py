"""
Magnet storage ring - a square block with blind cylinder wells around all
four outer faces and an open storage basin in the middle. Every well sits
against an outer face, and a full-height slot runs from the well out
through that face, so a finger (or a pin, for the small sizes) can push the
stack up from the side however low it runs. Slot width is a fraction of the
magnet diameter, so the magnets stay in.

Pinwheel layout: side k runs from its own start corner to the inner edge of
side k+1, so every corner belongs to exactly one side. Each side is only as
thick as its largest well needs (FACE_WALL + hole + INNER_WALL); whatever
is left in the middle becomes the basin, floored at BASE like the wells.

Wells per size are derived from TARGET_DEPTH: how many discs fit in one
well at that depth, then enough wells for the planned count (count / COPIES
per piece). The deepest planned stack (per_well x nominal thickness x
STACK_TOLERANCE + HEADROOM) sets the height, and every well runs that full
depth, so the sizes with shorter stacks get refill room. Sides holding a
fill group get extra wells of it until they reach the square's size. Hole
diameter is nominal + HOLE_CLEARANCE for FDM.

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

TARGET_DEPTH  = 70.0     # max well depth; sets how many discs go in one well
COPIES        = 1        # identical pieces printed; each holds count / COPIES

END_WALL    = 3.0        # first/last well edge to the end of its side's run
FACE_WALL   = 2.0        # well edge to its outer face (the slot cuts through it)
INNER_WALL  = 2.5        # well edge to the basin
MIN_BASIN   = 20.0       # smallest basin opening allowed, either direction
BASE        = 3.0        # floor under the wells and the basin
EMBED       = 0.5        # cutter overshoot past every outer face

SLOT_WIDTH_FRAC = 0.5    # slot width as a fraction of the magnet diameter
SLOT_LIP        = 1.0    # solid kept between the slot bottom and the well floor

# Magnet (diameter, thickness), planned count, and the wall between
# neighbouring wells of that size. Planned counts are what the piece needs
# to hold, not the full stock (20x1 and 5x3: half of the 400 each).
# wells=N instead of a count: a fixed number of full-depth wells for
# odd sizes (thickness unknown, fill as many as fit).
# fill=True: extra wells of that group are added until its side reaches
# the square's size.
# Sides go counter-clockwise from the front (-Y) face; each side is laid
# out left to right as seen from outside.
SIDES = [
    [   # front
        dict(label="20x1", diam=20.0, thick=1.0, count=200, wall=6.0),
        dict(label="10",   diam=10.0, wells=1, wall=4.0),
    ],
    [   # right
        dict(label="19",   diam=19.0, wells=1, wall=6.0),
        dict(label="16",   diam=16.0, wells=1, wall=6.0),
        dict(label="10x3", diam=10.0, thick=3.0, count=100, wall=4.0),
    ],
    [   # back
        dict(label="6x3",  diam=6.0,  thick=3.0, count=100, wall=4.0),
        dict(label="5x3",  diam=5.0,  thick=3.0, count=100, wall=4.0, fill=True),
    ],
    [   # left
        dict(label="5x3",  diam=5.0,  thick=3.0, count=100, wall=4.0, fill=True),
    ],
]

# ============================================================
# LAYOUT
# ============================================================
def hole_diam(g):
    return g["diam"] + HOLE_CLEARANCE


def plan_group(g):
    """Wells for one group: (wells, per_well, depth). Fixed-count groups
    return per_well None and depth 0 - they never set the height."""
    if "wells" in g:
        return g["wells"], None, 0.0
    max_per_well = int((TARGET_DEPTH - HEADROOM) / (g["thick"] * STACK_TOLERANCE))
    count = math.ceil(g["count"] / COPIES)
    n = math.ceil(count / max_per_well)
    per_well = math.ceil(count / n)
    depth = per_well * g["thick"] * STACK_TOLERANCE + HEADROOM
    return n, per_well, depth


def side_thickness(groups):
    return FACE_WALL + max(hole_diam(g) for g in groups) + INNER_WALL


def plan_run(groups, extra=0):
    """One side's wells along local X from x=0. `extra` wells go to the
    fill group. Returns (wells as (x, d, depth, g), run length, info)."""
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


def plan_ring():
    """Square size, per-side runs (fill applied), and per-side thickness.
    Side k's run spans local x in [-S/2, S/2 - T[k+1]]."""
    T = [side_thickness(groups) for groups in SIDES]
    runs = [plan_run(groups) for groups in SIDES]

    def needed(k, run_len):
        return run_len + 2 * END_WALL + T[(k + 1) % 4]

    size = max(needed(k, runs[k][1]) for k in range(4))
    size = max(size, T[0] + T[2] + MIN_BASIN, T[1] + T[3] + MIN_BASIN)

    for k, groups in enumerate(SIDES):
        if not any(g.get("fill") for g in groups):
            continue
        extra = 0
        while True:
            more = plan_run(groups, extra + 1)
            if needed(k, more[1]) > size:
                break
            extra, runs[k] = extra + 1, more
    return size, runs, T


def to_world(k, x, y):
    a = k * math.pi / 2
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)

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
    """The deepest planned stack sets the height; every well runs the full
    depth down to BASE, so the shallower sizes get refill room."""
    size, runs, T = plan_ring()
    depth = max(w[2] for run in runs for w in run[0])
    height = depth + BASE
    half = size / 2

    bm = bmesh.new()
    add_box(bm, 0, 0, 0, size, size, height)
    block = new_object_from_bmesh(bm, "magnet_storage")

    # wells + basin: none overlap each other, so one joined cutter, one boolean
    bm = bmesh.new()
    for k, (wells, run_len, _) in enumerate(runs):
        run_start = -half + END_WALL
        # centre the run within this side's span
        span = size - T[(k + 1) % 4] - 2 * END_WALL
        offset = run_start + (span - run_len) / 2
        for x, d, _, g in wells:
            ly = -half + FACE_WALL + d / 2
            wx, wy = to_world(k, offset + x, ly)
            add_cylinder(bm, wx, wy, BASE, d, depth + EMBED)
    x0, x1 = -half + T[3], half - T[1]
    y0, y1 = -half + T[0], half - T[2]
    add_box(bm, (x0 + x1) / 2, (y0 + y1) / 2, BASE, x1 - x0, y1 - y0, depth + EMBED)
    boolean_difference(block, new_object_from_bmesh(bm, "well_cutters"))

    # slots: separate pass - each overlaps its own well
    bm = bmesh.new()
    for k, (wells, run_len, _) in enumerate(runs):
        span = size - T[(k + 1) % 4] - 2 * END_WALL
        offset = -half + END_WALL + (span - run_len) / 2
        for x, d, _, g in wells:
            ly = -half + FACE_WALL + d / 2
            _add_slot(bm, k, offset + x, ly, g, height, half)
    boolean_difference(block, new_object_from_bmesh(bm, "slot_cutters"))

    print(f"Ring {size:.1f} x {size:.1f} x {height:.1f} mm, wells {depth:.1f} deep, "
          f"basin {x1 - x0:.1f} x {y1 - y0:.1f}")
    for k, (_, _, info) in enumerate(runs):
        for label, n, per, _ in info:
            g = next(g for g in SIDES[k] if g["label"] == label)
            if per is None:
                print(f"  side {k}: {n:2d} x {label} well, fill as many as fit")
                continue
            full = int((depth - HEADROOM) / (g["thick"] * STACK_TOLERANCE) + 1e-6)
            print(f"  side {k}: {n:2d} x {label} wells, {per}/well planned, {full}/well max")
    print(f"  non-manifold edges: {nonmanifold_edges(block)}")
    return block


def _add_slot(bm, k, lx, ly, g, z_top, half):
    """Full-height box from the well centre out through its outer face.
    Starts SLOT_LIP above the well floor - keeps the bottom disc from
    sliding out and avoids a cutter face coplanar with the floor."""
    width = g["diam"] * SLOT_WIDTH_FRAC
    y_face = -half - EMBED
    z0 = BASE + SLOT_LIP
    wx, wy = to_world(k, lx, (ly + y_face) / 2)
    add_box(bm, wx, wy, z0, width, ly - y_face, z_top + EMBED - z0, k * math.pi / 2)

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
