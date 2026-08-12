"""
Prospero Columns (Blender bpy) - standalone.

Ruin-scale fluted columns for the "filler" ruins terrain (see
ruins/ruins.md - "fallen columns" is one of its listed features). One
shared plinth/shaft/capital builder produces a kit of standing parts
rather than pre-arranged rubble piles - print a batch of each and
arrange/combine them by hand on the board:

  - column_whole   - intact standing column (plinth + fluted tapered
                      shaft + capital), one STL
  - column_base    - plinth + a broken-off shaft stub, jagged fracture
                      at the top
  - column_middle  - a generic mid-shaft segment, jagged fractures on
                      both ends - print several, mix lengths of "missing"
                      column by how many you stack/scatter
  - column_top     - a broken-off shaft stub + capital, jagged fracture
                      at the bottom

All fracture surfaces are irregular (a jittered grid, not a flat plane
cut) so they read as broken stone rather than a clean saw cut.

Flutes are carved directly into the shaft's cross-section as a ring loft
(bridge_edge_loops), not cut via boolean grooves - there's no boolean
involved in the flute geometry at all. Fracture cuts are DIFFERENCE
booleans against a jagged-faced cutter; column_middle needs two (one per
end) on the same duplicate - still a short chain, kept to 2 ops, and
verified by volume like every other part here (see
feedback_blender_boolean_fragility: long chains are what corrupts
geometry).

Run: Blender -> Scripting workspace -> Open this file -> Alt+P
Or headless: blender --background --python columns.py
"""

import bpy
import bmesh
import math
import mathutils
import os
import random

# ============================================================
# CONFIG
# ============================================================

EXPORT_DIR = "/Users/mannil/Desktop/studio-m/TSONS/columns/output"
EXPORT_STL = True

RENDER_IMAGES = True
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1600, 900)
RENDER_ANGLES = {
    "front": (0.0, -1.0, 0.3),
    "side": (1.0, -0.1, 0.3),
    "top": (0.001, -0.3, 1.0),
    "iso": (0.7, -1.0, 0.5),
}

EMBED = 0.6  # overlap depth between unioned parts - avoids coincident-face
             # boolean degeneracy (see feedback_blender_boolean_fragility)

# Plinth: low round stepped base the shaft stands on.
PLINTH_R = 6.5
PLINTH_H = 3.0

# Fluted tapered shaft, in mm.
SHAFT_R_BOTTOM = 5.0
SHAFT_R_TOP = 4.2
SHAFT_H = 72.0
FLUTE_COUNT = 20
FLUTE_DEPTH = 0.45
SHAFT_RING_STEPS = 24     # vertical loft resolution
SHAFT_ANGULAR_STEPS = 96  # angular resolution (must be a clean multiple
                           # of FLUTE_COUNT for even flutes)

# Capital: round echinus flare (transitions from the round shaft) topped
# by a square abacus block - matches the blocky square cap on the fallen
# column in ruins/illustrations/v1_ruins.png, rather than a fully round
# capital.
CAPITAL_ECHINUS_H = 4.0
CAPITAL_ECHINUS_R_OUT = 6.0
CAPITAL_ABACUS_SIZE = 12.0  # square abacus width/depth (full span, not radius)
CAPITAL_ABACUS_H = 2.5

SPIN_STEPS = 48

TOTAL_WHOLE_HEIGHT = PLINTH_H + SHAFT_H + CAPITAL_ECHINUS_H + CAPITAL_ABACUS_H

# Broken parts: how much shaft stays attached to the base/top stubs, and
# the nominal length of a free-standing middle segment. All measured as
# shaft length from the nominal (pre-jitter) fracture boundary.
BASE_STUB_H = 24.0
TOP_STUB_H = 24.0
MIDDLE_H = 30.0

# Fracture surfaces: a jittered grid instead of a flat plane, so the
# break reads as irregular broken stone rather than a clean cut.
JAGGED_JITTER_AMP = 1.4   # max +/- deviation from the nominal cut height, mm
JAGGED_GRID_N = 14        # grid subdivisions across the cutter footprint
JAGGED_CUTTER_MARGIN = 3.0  # cutter footprint radius = shaft radius + this,
                             # so it's comfortably wider than the shaft


# ============================================================
# HELPERS (shared conventions - see brazier/brazier.py, runes/rune_panel_v1_plain.py)
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


def apply_transform(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


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


def render_variant(name, objects):
    """Render one variant (a group of one or more objects) to its own
    renders/<name>/ subfolder, then clean up the camera/light/target so
    the next variant's render starts fresh."""
    out_dir = os.path.join(RENDER_DIR, name)
    os.makedirs(out_dir, exist_ok=True)

    center, size = compute_scene_bounds()
    cam_obj = setup_camera_and_light(center)

    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = RENDER_RESOLUTION[0]
    scene.render.resolution_y = RENDER_RESOLUTION[1]

    distance = size * 3.0
    for angle_name, direction in RENDER_ANGLES.items():
        cam_obj.location = center + mathutils.Vector(direction).normalized() * distance
        scene.render.filepath = os.path.join(out_dir, f"{angle_name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"Rendered {scene.render.filepath}")

    bpy.data.objects.remove(cam_obj, do_unlink=True)
    for obj in list(bpy.context.scene.objects):
        if obj.type in {'LIGHT', 'EMPTY'}:
            bpy.data.objects.remove(obj, do_unlink=True)


def export_stl(obj, filename):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = os.path.join(EXPORT_DIR, filename)
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"Exported {path}")


def mesh_volume(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    volume = bm.calc_volume()
    bm.free()
    return volume


# ============================================================
# SHARED PARTS
# ============================================================

def _spin_profile(profile, name, steps=SPIN_STEPS):
    """Revolve a closed (r, z) profile loop 360 degrees around the Z axis
    into a solid mesh object."""
    bm = bmesh.new()
    verts = [bm.verts.new((r, 0.0, z)) for r, z in profile]
    edges = [bm.edges.new((verts[i], verts[i + 1])) for i in range(len(verts) - 1)]
    bmesh.ops.spin(
        bm, geom=verts + edges, axis=(0, 0, 1), cent=(0, 0, 0),
        steps=steps, angle=math.radians(360), use_merge=True,
    )
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def build_plinth():
    """Low round stepped base: a wide flat foot plus a slightly narrower
    upper step the shaft's EMBED overlap sinks into."""
    step_r = PLINTH_R - 1.2
    step_h = PLINTH_H * 0.4
    profile = [
        (0.0, 0.0),
        (PLINTH_R, 0.0),
        (PLINTH_R, step_h),
        (step_r, step_h),
        (step_r, PLINTH_H),
        (0.0, PLINTH_H),
    ]
    return _spin_profile(profile, "plinth")


def build_square_block(size, height, z0, name):
    """Solid square block, size x size footprint, spanning z in
    [z0, z0+height] - the square abacus cap. Box-building approach shared
    with build_slab_cutter: create_cube gives a unit cube (half-extent
    0.5 per axis), so scaling by the full desired span gives the correct
    post-scale half-extent directly, no extra /2 needed."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(size, size, height), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(0.0, 0.0, z0 + height / 2.0), verts=bm.verts)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def build_capital():
    """Round echinus flare (narrow at bottom where it meets the shaft,
    flares out going up) topped by a square abacus block - the echinus is
    spun, the abacus is a square box, unioned together."""
    ech = [
        (0.0, 0.0),
        (SHAFT_R_TOP, 0.0),
        (CAPITAL_ECHINUS_R_OUT, CAPITAL_ECHINUS_H),
        (0.0, CAPITAL_ECHINUS_H),
    ]
    echinus = _spin_profile(ech, "capital_echinus")

    z_bot = CAPITAL_ECHINUS_H - EMBED
    abacus = build_square_block(CAPITAL_ABACUS_SIZE, EMBED + CAPITAL_ABACUS_H, z_bot, "capital_abacus")

    apply_boolean(echinus, abacus, 'UNION')
    echinus.name = "capital"
    return echinus


def build_fluted_shaft(height=SHAFT_H, r_bottom=SHAFT_R_BOTTOM, r_top=SHAFT_R_TOP,
                        name="shaft", ring_steps=SHAFT_RING_STEPS,
                        angular_steps=SHAFT_ANGULAR_STEPS):
    """Tapered cylinder with vertical flutes carved directly into the
    cross-section (a ring loft via bridge_edge_loops-equivalent manual
    face building), capped top and bottom. No boolean ops at all - the
    grooves are just radius modulation per angle, so there's nothing here
    for the EXACT solver to corrupt."""
    bm = bmesh.new()
    rings = []
    for i in range(ring_steps + 1):
        t = i / ring_steps
        z = t * height
        r_base = r_bottom + (r_top - r_bottom) * t
        ring_verts = []
        for j in range(angular_steps):
            theta = 2 * math.pi * j / angular_steps
            groove = 0.5 + 0.5 * math.cos(theta * FLUTE_COUNT)  # 0..1
            r = r_base - FLUTE_DEPTH * groove
            x = r * math.cos(theta)
            y = r * math.sin(theta)
            ring_verts.append(bm.verts.new((x, y, z)))
        rings.append(ring_verts)

    for i in range(ring_steps):
        ring_a, ring_b = rings[i], rings[i + 1]
        for j in range(angular_steps):
            j2 = (j + 1) % angular_steps
            bm.faces.new((ring_a[j], ring_a[j2], ring_b[j2], ring_b[j]))

    bm.faces.new(reversed(rings[0]))
    bm.faces.new(rings[-1])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def build_jagged_cutter(z_cut, direction, radius, name, seed,
                         jitter_amp=JAGGED_JITTER_AMP, grid_n=JAGGED_GRID_N):
    """A solid whose near face is an irregular jittered grid centered at
    z_cut (instead of a flat plane) and whose far side extends a long way
    up ('above') or down ('below') - used as a DIFFERENCE cutter so the
    surface it leaves behind on the target reads as broken stone, not a
    clean saw cut. Built by extruding the jagged grid straight down/up:
    the extrude operator generates the side walls and the far flat cap
    for us, so there's no separate cap-stitching to get wrong."""
    rng = random.Random(seed)
    bm = bmesh.new()
    verts = {}
    for i in range(grid_n + 1):
        for j in range(grid_n + 1):
            x = -radius + (2 * radius) * i / grid_n
            y = -radius + (2 * radius) * j / grid_n
            z = z_cut + rng.uniform(-jitter_amp, jitter_amp)
            verts[(i, j)] = bm.verts.new((x, y, z))

    faces = []
    for i in range(grid_n):
        for j in range(grid_n):
            v00, v10 = verts[(i, j)], verts[(i + 1, j)]
            v11, v01 = verts[(i + 1, j + 1)], verts[(i, j + 1)]
            faces.append(bm.faces.new((v00, v10, v11, v01)))

    far = 1000.0
    offset = far if direction == 'above' else -far
    extruded = bmesh.ops.extrude_face_region(bm, geom=faces)
    ex_verts = [v for v in extruded['geom'] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0.0, 0.0, offset), verts=ex_verts)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


# ============================================================
# WHOLE COLUMN
# ============================================================

def build_whole_column():
    base = build_plinth()

    shaft = build_fluted_shaft()
    shaft.location.z = PLINTH_H - EMBED
    apply_transform(shaft)
    apply_boolean(base, shaft, 'UNION')

    capital = build_capital()
    capital.location.z = PLINTH_H + SHAFT_H - EMBED
    apply_transform(capital)
    apply_boolean(base, capital, 'UNION')

    base.name = "column_whole"
    return base


# ============================================================
# BROKEN PARTS (base / middle / top - standing, kit-of-parts)
# ============================================================

def build_base_part():
    """Plinth + shaft, broken off jagged at BASE_STUB_H above the
    plinth top - a "just the foot survives" ruin piece."""
    plinth = build_plinth()

    shaft = build_fluted_shaft(name="base_shaft")
    shaft.location.z = PLINTH_H - EMBED
    apply_transform(shaft)
    apply_boolean(plinth, shaft, 'UNION')

    cutter = build_jagged_cutter(
        z_cut=PLINTH_H + BASE_STUB_H, direction='above',
        radius=SHAFT_R_BOTTOM + JAGGED_CUTTER_MARGIN,
        name="base_break_cutter", seed=11)
    apply_boolean(plinth, cutter, 'DIFFERENCE')

    plinth.name = "column_base"
    return plinth


def build_top_part():
    """Shaft stub + capital, broken off jagged at TOP_STUB_H below the
    capital's echinus base - a "just the head survives" ruin piece."""
    shaft = build_fluted_shaft(name="top_shaft")

    cutter = build_jagged_cutter(
        z_cut=SHAFT_H - TOP_STUB_H, direction='below',
        radius=SHAFT_R_BOTTOM + JAGGED_CUTTER_MARGIN,
        name="top_break_cutter", seed=22)
    apply_boolean(shaft, cutter, 'DIFFERENCE')

    capital = build_capital()
    capital.location.z = SHAFT_H - EMBED
    apply_transform(capital)
    apply_boolean(shaft, capital, 'UNION')

    shaft.name = "column_top"
    return shaft


def build_middle_part():
    """A generic mid-shaft drum, jagged fractures on both ends, no
    plinth or capital - print several and mix into any broken
    arrangement. Two DIFFERENCE ops on one duplicate (upper cut, then
    lower cut) - a short chain, kept to 2 and volume-checked like the
    rest of this file."""
    shaft = build_fluted_shaft(name="middle_shaft")

    z0 = (SHAFT_H - MIDDLE_H) / 2.0
    z1 = z0 + MIDDLE_H

    upper_cutter = build_jagged_cutter(
        z_cut=z1, direction='above',
        radius=SHAFT_R_BOTTOM + JAGGED_CUTTER_MARGIN,
        name="middle_break_cutter_upper", seed=33)
    apply_boolean(shaft, upper_cutter, 'DIFFERENCE')

    lower_cutter = build_jagged_cutter(
        z_cut=z0, direction='below',
        radius=SHAFT_R_BOTTOM + JAGGED_CUTTER_MARGIN,
        name="middle_break_cutter_lower", seed=44)
    apply_boolean(shaft, lower_cutter, 'DIFFERENCE')

    shaft.name = "column_middle"
    return shaft


# ============================================================
# MAIN
# ============================================================

def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)

    print(f"Whole column: plinth H={PLINTH_H}mm + shaft H={SHAFT_H}mm + "
          f"capital H={CAPITAL_ECHINUS_H + CAPITAL_ABACUS_H}mm "
          f"= {TOTAL_WHOLE_HEIGHT}mm total, shaft dia {SHAFT_R_BOTTOM * 2}-{SHAFT_R_TOP * 2}mm")

    # --- whole column ---
    clear_scene()
    whole = build_whole_column()
    vol = mesh_volume(whole)
    print(f"column_whole volume = {vol:.1f} mm^3")
    if EXPORT_STL:
        export_stl(whole, "column_whole.stl")
    if RENDER_IMAGES:
        render_variant("column_whole", [whole])

    # --- base part (plinth + broken stub) ---
    clear_scene()
    base = build_base_part()
    print(f"column_base volume = {mesh_volume(base):.1f} mm^3")
    if EXPORT_STL:
        export_stl(base, "column_base.stl")
    if RENDER_IMAGES:
        render_variant("column_base", [base])

    # --- middle part (generic drum, both ends broken) ---
    clear_scene()
    middle = build_middle_part()
    print(f"column_middle volume = {mesh_volume(middle):.1f} mm^3")
    if EXPORT_STL:
        export_stl(middle, "column_middle.stl")
    if RENDER_IMAGES:
        render_variant("column_middle", [middle])

    # --- top part (broken stub + capital) ---
    clear_scene()
    top = build_top_part()
    print(f"column_top volume = {mesh_volume(top):.1f} mm^3")
    if EXPORT_STL:
        export_stl(top, "column_top.stl")
    if RENDER_IMAGES:
        render_variant("column_top", [top])

    print("Done.")


if __name__ == "__main__":
    main()
