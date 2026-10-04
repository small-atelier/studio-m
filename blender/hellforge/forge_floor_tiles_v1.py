#!/usr/bin/env python3
"""Portable Hellforge — forge floor, actual print geometry, v2.

Blender/bpy script (not runnable outside Blender's own Python) - paste into
the Script Editor and run (Alt+P), or run headless:
  blender --background --python forge_floor_tiles_v1.py

v2 change from v1: floor grew to 480x230mm (from 400x220) once the Roaring
Furnace moved onto a real 100mm Citadel-size base instead of a bespoke
40mm terrain footprint - see forge_floor_layout.py's v4 note. 3 tiles now,
not 2, with a plain straight seam each (no jog needed this time - the wider
floor left real open corridors). Socket depth also simplified: previously
two separate cuts (socket recess + magnet through-hole); now ONE recess
sized for the base (bases.py HEIGHT=4.0mm) plus a thin steel disc
(0.5mm) - the magnets live in the miniature's own base (bases.py
MAGNET_CONFIGS) and stick to this steel disc, not the other way round.

Turns the forge_floor_layout.py plan into 3 printable tile STLs (tile_a,
tile_b, tile_c). Each tile is:
  - one clean slab, extruded directly from its outline - no boolean needed
    for the basic shape, see [[feedback_functional_parts_pipeline]]
  - a recessed socket (base + steel disc, one cut) per miniature/terrain
    base assigned to that tile
  - a couple of panel-seam grooves, dividing the slab into "plates"
  - a small drain-style grate (tile_a only)
  - rivet studs at the groove intersections

Boolean approach follows [[feedback_blender_boolean_fragility]]: each
decorative/functional CATEGORY (all socket recesses, all vertical grooves,
all horizontal grooves, all grate slots, all rivets) is built as its own
object combining only mutually non-overlapping cutters, then applied as ONE
boolean pass per category - never a long chain, never a cutter built from
already-overlapping shapes.

Positions/detail sizing are first-pass and approximate - correct once the
actual models, base thickness, and steel stock are in hand.
"""
import bpy
import bmesh
import math
import mathutils
import os

# ============================================================
# CONFIG (all mm)
# ============================================================
EXPORT_DIR = "/Users/mannil/studio-m/blender/hellforge/output"
EXPORT_STL = True

RENDER_IMAGES = True
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1600, 900)
RENDER_ANGLES = {
    "top": (0.001, -0.3, 1.0),
    "iso": (0.6, -1.0, 0.6),
}

TILE_THICKNESS = 7.0
OVERSHOOT = 1.0   # generic cutter overshoot past a surface, for clean booleans

SOCKET_CLEARANCE = 0.3
BASE_THICKNESS = 4.0          # from blender/bases/bases.py HEIGHT
STEEL_DISC_THICKNESS = 0.5    # ASSUMPTION - thin steel shim, correct once stock is picked
SOCKET_DEPTH = BASE_THICKNESS + STEEL_DISC_THICKNESS

VERTICAL_SEAM_X = [56.0, 232.0, 300.0, 416.0]    # global X, panel-seam grooves
HORIZONTAL_SEAM_Y = [75.0, 150.0]                # global Y, panel-seam grooves
GROOVE_WIDTH = 1.2
GROOVE_DEPTH = 0.6

GRATE_RECT = (10.0, 40.0, 55.0, 85.0)   # x0, x1, y0, y1 - tile_a only, open floor near the back-left
GRATE_SLOTS = 5
GRATE_SLOT_WIDTH = 2.2
GRATE_DEPTH = 1.5

RIVET_DIAMETER = 1.6
RIVET_HEIGHT = 0.8
RIVET_EMBED = 0.3   # rivet base sunk slightly into the slab before the union, avoids a flush/coincident seam

# ----------------------------
# Sockets - same data/positions as forge_floor_layout.py v4 (miniature
# bases + the Roaring Furnace, now on its own real 100mm base)
# ----------------------------
FLOOR_W = 480.0
FLOOR_D = 230.0
SEAM_X = [112.0, 353.0]   # straight seams this time - no jog needed

ALL_SOCKETS = [
    ("Dominator Engine", 170.0, 65.0, 100.0),
    ("Roaring Furnace", 300.0, 60.0, 100.0),
    ("Tormentor Bombard", 410.0, 140.0, 80.0),
    ("War Despot", 195.0, 175.0, 32.0),
    ("Hobgrot Gong-bearer", 235.0, 185.0, 25.0),
    ("Infernal Cohort 1", 60.0, 100.0, 28.5),
    ("Infernal Cohort 2", 90.0, 155.0, 28.5),
    ("Infernal Cohort 3", 140.0, 130.0, 28.5),
    ("Infernal Cohort 4", 55.0, 190.0, 28.5),
    ("Infernal Cohort 5", 130.0, 205.0, 28.5),
    ("Infernal Cohort 6", 260.0, 150.0, 28.5),
    ("Infernal Cohort 7", 300.0, 190.0, 28.5),
    ("Infernal Cohort 8", 380.0, 190.0, 28.5),
    ("Infernal Cohort 9", 440.0, 90.0, 28.5),
    ("Infernal Cohort 10", 420.0, 60.0, 28.5),
]
assert len(ALL_SOCKETS) == 15, "expected 14 models + 1 terrain feature"


def _tile_index(cx):
    if cx < SEAM_X[0]:
        return 0
    if cx < SEAM_X[1]:
        return 1
    return 2


TILE_BOUNDS = [(0.0, SEAM_X[0]), (SEAM_X[0], SEAM_X[1]), (SEAM_X[1], FLOOR_W)]
TILE_NAMES = ["tile_a", "tile_b", "tile_c"]

TILES = []
for i, name in enumerate(TILE_NAMES):
    x0, x1 = TILE_BOUNDS[i]
    TILES.append({
        "name": name,
        "outline": [(x0, 0.0), (x1, 0.0), (x1, FLOOR_D), (x0, FLOOR_D)],
        "sockets": [s for s in ALL_SOCKETS if _tile_index(s[1]) == i],
        "grate": GRATE_RECT if name == "tile_a" else None,
    })

assert sum(len(t["sockets"]) for t in TILES) == len(ALL_SOCKETS)


# ============================================================
# HELPERS (shared convention - see card_stand_v8_holder_piece.py,
# brazier_with_flame.py)
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


def join_objects(objs, name):
    """Combine several mutually NON-OVERLAPPING objects into one, for a
    single boolean pass - see [[feedback_blender_boolean_fragility]]. Don't
    use this to combine shapes that overlap each other."""
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    joined = bpy.context.active_object
    joined.name = name
    return joined


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


def add_cylinder(diameter, z_range, loc_xy, vertices=32):
    z0, z1 = z_range
    bpy.ops.mesh.primitive_cylinder_add(
        radius=diameter / 2, depth=z1 - z0,
        location=(loc_xy[0], loc_xy[1], (z0 + z1) / 2), vertices=vertices,
    )
    return bpy.context.active_object


def mesh_volume(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    volume = bm.calc_volume()
    bm.free()
    return volume


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
        (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2,
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


def render_angles(tile_name, center, size):
    os.makedirs(RENDER_DIR, exist_ok=True)
    cam_obj = setup_camera_and_light(center)

    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = RENDER_RESOLUTION[0]
    scene.render.resolution_y = RENDER_RESOLUTION[1]

    distance = size * 2.2
    for name, direction in RENDER_ANGLES.items():
        cam_obj.location = center + mathutils.Vector(direction).normalized() * distance
        scene.render.filepath = os.path.join(RENDER_DIR, f"{tile_name}_{name}.png")
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
# TILE SLAB (single clean extrusion, no boolean - see
# [[feedback_functional_parts_pipeline]])
# ============================================================
def build_tile_slab(outline, thickness, name):
    """Extrude a flat polygon straight up by `thickness`. `outline` must be
    wound counter-clockwise as seen from +Z."""
    bm = bmesh.new()
    bottom = [bm.verts.new((x, y, 0.0)) for x, y in outline]
    top = [bm.verts.new((x, y, thickness)) for x, y in outline]
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


# ============================================================
# SOCKETS - one cut per piece: base recess + steel disc, combined into a
# single depth (SOCKET_DEPTH) since the disc sits directly under the base
# with no air gap. One category, one boolean pass.
# ============================================================
def build_socket_cutters(sockets):
    cutters = []
    for name, cx, cy, d in sockets:
        dia = d + SOCKET_CLEARANCE * 2
        z_range = (TILE_THICKNESS - SOCKET_DEPTH, TILE_THICKNESS + OVERSHOOT)
        cutters.append(add_cylinder(dia, z_range, (cx, cy)))
    return join_objects(cutters, "socket_cutters")


# ============================================================
# PANEL-SEAM GROOVES (vertical and horizontal kept as separate passes, so a
# grid crossing never joins two shapes into one self-overlapping cutter)
# ============================================================
def build_vertical_groove_cutters(bbox):
    x0, x1, y0, y1 = bbox
    cutters = []
    for gx in VERTICAL_SEAM_X:
        if not (x0 < gx < x1):
            continue
        cutters.append(add_box_range(
            (gx - GROOVE_WIDTH / 2, gx + GROOVE_WIDTH / 2),
            (y0 - OVERSHOOT, y1 + OVERSHOOT),
            (TILE_THICKNESS - GROOVE_DEPTH, TILE_THICKNESS + OVERSHOOT),
        ))
    return join_objects(cutters, "vgroove_cutters") if cutters else None


def build_horizontal_groove_cutters(bbox):
    x0, x1, y0, y1 = bbox
    cutters = []
    for gy in HORIZONTAL_SEAM_Y:
        if not (y0 < gy < y1):
            continue
        cutters.append(add_box_range(
            (x0 - OVERSHOOT, x1 + OVERSHOOT),
            (gy - GROOVE_WIDTH / 2, gy + GROOVE_WIDTH / 2),
            (TILE_THICKNESS - GROOVE_DEPTH, TILE_THICKNESS + OVERSHOOT),
        ))
    return join_objects(cutters, "hgroove_cutters") if cutters else None


# ============================================================
# GRATE (parallel slots, drain-cover style - bars are just the material
# left standing between cutters, not modeled separately)
# ============================================================
def build_grate_cutters(rect):
    x0, x1, y0, y1 = rect
    pitch = (x1 - x0) / GRATE_SLOTS
    cutters = []
    for i in range(GRATE_SLOTS):
        cx = x0 + pitch * (i + 0.5)
        cutters.append(add_box_range(
            (cx - GRATE_SLOT_WIDTH / 2, cx + GRATE_SLOT_WIDTH / 2),
            (y0, y1),
            (TILE_THICKNESS - GRATE_DEPTH, TILE_THICKNESS + OVERSHOOT),
        ))
    return join_objects(cutters, "grate_cutters")


# ============================================================
# RIVETS (at groove-grid intersections that fall inside this tile, and
# outside every socket - a rivet centered over a socket's void has no
# material to bond to and unions in as a disconnected floating fragment)
# ============================================================
def build_rivet_studs(bbox, sockets):
    x0, x1, y0, y1 = bbox
    studs = []
    for gx in VERTICAL_SEAM_X:
        if not (x0 < gx < x1):
            continue
        for gy in HORIZONTAL_SEAM_Y:
            if not (y0 < gy < y1):
                continue
            in_socket = any(
                ((gx - scx) ** 2 + (gy - scy) ** 2) ** 0.5 < (sd / 2 + SOCKET_CLEARANCE + RIVET_DIAMETER)
                for _, scx, scy, sd in sockets
            )
            if in_socket:
                continue
            z_range = (TILE_THICKNESS - RIVET_EMBED, TILE_THICKNESS + RIVET_HEIGHT)
            studs.append(add_cylinder(RIVET_DIAMETER, z_range, (gx, gy), vertices=12))
    return join_objects(studs, "rivets") if studs else None


# ============================================================
# ASSEMBLE ONE TILE
# ============================================================
def build_tile(tile_def):
    outline = tile_def["outline"]
    bbox = (
        min(p[0] for p in outline), max(p[0] for p in outline),
        min(p[1] for p in outline), max(p[1] for p in outline),
    )

    slab = build_tile_slab(outline, TILE_THICKNESS, tile_def["name"])

    if tile_def["sockets"]:
        apply_boolean(slab, build_socket_cutters(tile_def["sockets"]), 'DIFFERENCE')

    vgrooves = build_vertical_groove_cutters(bbox)
    if vgrooves:
        apply_boolean(slab, vgrooves, 'DIFFERENCE')
    hgrooves = build_horizontal_groove_cutters(bbox)
    if hgrooves:
        apply_boolean(slab, hgrooves, 'DIFFERENCE')

    if tile_def.get("grate"):
        apply_boolean(slab, build_grate_cutters(tile_def["grate"]), 'DIFFERENCE')

    rivets = build_rivet_studs(bbox, tile_def["sockets"])
    if rivets:
        apply_boolean(slab, rivets, 'UNION')

    slab.name = tile_def["name"]
    return slab


# ============================================================
# MAIN
# ============================================================
def main():
    for tile_def in TILES:
        clear_scene()
        tile = build_tile(tile_def)
        print(f"{tile_def['name']}: {len(tile_def['sockets'])} sockets, "
              f"volume={mesh_volume(tile):.0f}mm3 (sanity check only)")
        if EXPORT_STL:
            export_stl(tile, f"{tile_def['name']}.stl")
        if RENDER_IMAGES:
            center, size = compute_scene_bounds()
            render_angles(tile_def["name"], center, size)
    print("Done.")


if __name__ == "__main__":
    main()
