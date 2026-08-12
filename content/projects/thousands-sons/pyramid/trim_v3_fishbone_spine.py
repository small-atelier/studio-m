"""
Pyramid trim strip V3 - "fishbone spine" (Blender bpy) - standalone.

Same two edge rails as trim_v1_plain.py, plus a third spine down
the strip's own centerline with a repeating pair of +-45deg ribs crossing
it at each step - each rib is centered on its spine point and, since the
spine sits at the channel's center this time (not near one edge, like
runes/rune_panel_v3_fishbone_spine.py's border), a single rib already
reaches from one rail's inner edge to the other's. Two ribs per point (one
each diagonal) read as a small woven "X" - repeated down the spine it's a
fern/wheat-stalk motif, distinct from the alternating chevron braid in
_v4/_v5.

One of a family of border motifs for the same strip footprint - see
_v1_plain.py, _v2_studs.py, _v4_braid_2strand.py, and _v5_braid_3strand.py
for the others.

Cut to length/mitred by hand after printing - a generic straight trim
strip, not tied to any specific piece or angle, reusable across the
board's various straight trim runs wherever this border motif fits.

Sized to the Anycubic Photon Mono 2's 143 x 89mm plate: strip length
140mm (down the plate's long axis, ~3mm margin off the true 143mm edge),
strip width 16mm (well inside the 89mm short axis). Direct-to-plate, no
supports - same shallow emboss-on-flat-back logic as the rune panels.

Run: Blender -> Scripting workspace -> Open this file -> Alt+P
"""

import bpy
import bmesh
import math
import mathutils
import os

# ============================================================
# CONFIG
# ============================================================

EXPORT_DIR = "/Users/mannil/Desktop/studio-m/TSONS/pyramid/trim/output/v3_fishbone_spine"
EXPORT_STL = True

RENDER_IMAGES = True
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1600, 900)
RENDER_ANGLES = {
    "front": (0.0, -1.0, 0.15),
    "side": (1.0, -0.1, 0.15),
    "top": (0.001, -0.3, 1.0),
    "iso": (0.6, -1.0, 0.6),
}

# Strip (X=length, Y=thickness, Z=width, pre-flatten - see
# build_and_export_strip). X is the length axis to match build_border_solid,
# which builds along local X (length) / local Z (width) - the same
# (cx, cz)=(X, Z) convention add_box uses throughout.
STRIP_W = 16.0
STRIP_D = 2.0
STRIP_L = 140.0

# Border: one straight rail down each long edge (RAIL_OUTER_INSET=1.0mm in
# from the true edge, same as the other variants), plus a spine down the
# strip's own centerline (z=0) carrying a repeating X-cross of ribs.
RAIL_OUTER_INSET = 1.0
RAIL_WIDTH = 0.6

# FISHBONE_RIB_LENGTH=17.5 reaches (L/2)*sin(45) = 6.19mm out from the
# spine on each side - short of the rail's own centerline at
# STRIP_W/2 - RAIL_OUTER_INSET = 7.0mm by ~0.8mm, avoiding an
# exact-coincidence union boundary (the same class of degenerate boolean
# input flagged throughout this pipeline) while still visually reaching
# right up to the rail. FISHBONE_RIB_SPACING=7.0 divides STRIP_L=140mm into
# exactly 20 rib-pair steps with no remainder.
FISHBONE_SPINE_WIDTH = 0.6
FISHBONE_RIB_LENGTH = 17.5
FISHBONE_RIB_WIDTH = 0.5
FISHBONE_RIB_SPACING = 7.0
BORDER_EMBOSS_HEIGHT = 0.8
BORDER_EMBED_DEPTH = 0.6

# Chamfer on all 12 slab edges - same reasoning as the rune panels: softens
# the raw-slab look, and once laid flat for printing gives a scraper
# something to wedge under on the bottom perimeter. Must stay clear of
# where the rail starts (RAIL_OUTER_INSET - RAIL_WIDTH/2 = 0.7mm from the
# true edge) so the bevel doesn't eat into the flat area the rail unions
# onto.
BOX_BEVEL_WIDTH = 0.4
BOX_BEVEL_SEGMENTS = 3


# ============================================================
# HELPERS
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


def frame_and_angle_view():
    """Point the 3D viewport at a 3/4 angle on everything in the scene and
    zoom to fit - a dead flat front-on view of an emboss shows no
    foreshortening/shading, so straight-on is close to the worst angle to
    inspect it from."""
    bpy.ops.object.select_all(action='DESELECT')
    mesh_objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    for obj in mesh_objects:
        obj.select_set(True)
    if mesh_objects:
        bpy.context.view_layer.objects.active = mesh_objects[0]

    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
            if region is None:
                continue
            with bpy.context.temp_override(window=window, area=area, region=region):
                bpy.ops.view3d.view_axis(type='FRONT')
                bpy.ops.view3d.view_orbit(angle=math.radians(-35), type='ORBITLEFT')
                bpy.ops.view3d.view_orbit(angle=math.radians(20), type='ORBITUP')
                bpy.ops.view3d.view_selected()
            return


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


def render_angles(center, size):
    os.makedirs(RENDER_DIR, exist_ok=True)
    cam_obj = setup_camera_and_light(center)

    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = RENDER_RESOLUTION[0]
    scene.render.resolution_y = RENDER_RESOLUTION[1]

    distance = size * 1.8
    for name, direction in RENDER_ANGLES.items():
        cam_obj.location = center + mathutils.Vector(direction).normalized() * distance
        scene.render.filepath = os.path.join(RENDER_DIR, f"{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"Rendered {scene.render.filepath}")


def export_stl(obj, filename):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = os.path.join(EXPORT_DIR, filename)
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"Exported {path}")


def add_box(bm, cx, cz, w, h, depth, angle_deg=0.0):
    """Appends a single axis-aligned (or Y-rotated) box into the given
    bmesh - width/height in local X/Z, `depth` in local Y (straddling
    Y=0)."""
    mat = (mathutils.Matrix.Translation((cx, 0.0, cz))
           @ mathutils.Matrix.Rotation(math.radians(angle_deg), 4, 'Y')
           @ mathutils.Matrix.Diagonal(mathutils.Vector((w, depth, h, 1.0))))
    bmesh.ops.create_cube(bm, size=1.0, matrix=mat)


def bevel_box_edges(obj, width, segments):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.bevel(
        bm, geom=bm.edges[:], offset=width, offset_type='OFFSET',
        segments=segments, affect='EDGES', clamp_overlap=True,
    )
    bm.to_mesh(obj.data)
    bm.free()


def make_box_object(cx, cz, w, h, angle_deg, depth, name):
    bm = bmesh.new()
    add_box(bm, cx, cz, w, h, depth, angle_deg)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def merge_pieces_into_solid(parts, depth, base_name):
    """Sequentially unions a list of (cx, cz, w, h, angle_deg) pieces into
    one watertight solid via real booleans. Kept as its own short chain
    (the ribs' 40 pieces, separate from the rails/spine) rather than folded
    into one giant union - see rune_panel_v6_fishbone_3strand.py's
    build_border_solid for why long boolean-union chains are unreliable
    with the EXACT solver."""
    solid = make_box_object(*parts[0], depth, f"{base_name}_solid")
    for cx, cz, w, h, angle in parts[1:]:
        piece = make_box_object(cx, cz, w, h, angle, depth, f"{base_name}_piece")
        apply_boolean(solid, piece, 'UNION')
    return solid


def build_fishbone_ribs(strip_l, rib_length, rib_width, spacing):
    """Builds the spine's rib pairs: at each step along x, two ribs at
    +-45deg, both centered on the same (x, 0) spine point so they cross as
    a small "X". Each rib already spans from -z to +z on its own (it's
    centered on the spine, not offset like the zigzag legs), reaching
    toward both rails at once. Returns a list of (cx, cz, w, h, angle_deg)."""
    n_steps = max(1, round(strip_l / spacing))
    step = strip_l / n_steps
    parts = []
    for i in range(n_steps):
        x = -strip_l / 2 + (i + 0.5) * step
        parts.append((x, 0.0, rib_length, rib_width, 45.0))
        parts.append((x, 0.0, rib_length, rib_width, -45.0))
    return parts


def build_border_solid(strip_w, strip_l, depth):
    """Border: two straight rails plus a center spine carrying a repeating
    X-cross of ribs reaching toward both rails."""
    rail_z = strip_w / 2 - RAIL_OUTER_INSET
    rail_parts = [
        (0.0, rail_z, strip_l, RAIL_WIDTH, 0.0),
        (0.0, -rail_z, strip_l, RAIL_WIDTH, 0.0),
    ]
    spine_parts = [(0.0, 0.0, strip_l, FISHBONE_SPINE_WIDTH, 0.0)]
    rib_parts = build_fishbone_ribs(strip_l, FISHBONE_RIB_LENGTH, FISHBONE_RIB_WIDTH, FISHBONE_RIB_SPACING)

    rails_solid = merge_pieces_into_solid(rail_parts, depth, "rails")
    spine_solid = merge_pieces_into_solid(spine_parts, depth, "spine")
    ribs_solid = merge_pieces_into_solid(rib_parts, depth, "ribs")

    apply_boolean(rails_solid, spine_solid, 'UNION')
    apply_boolean(rails_solid, ribs_solid, 'UNION')

    # Each rib is centered on its own spine point and, near the two ends of
    # the strip, its far tip can land past x=+-strip_l/2 (the ribs don't
    # know where the strip's own cut ends are) - left unclipped this pokes
    # thin unsupported spurs out past the flat slab's own footprint at both
    # ends. Clip to the strip's footprint, same fix as
    # rune_panel_v5_fishbone_2strand.py's build_border_solid uses for its
    # zigzag corners spilling past the outer rail.
    clip = make_box_object(0.0, 0.0, strip_l, strip_w, 0.0, depth * 4, "border_clip")
    apply_boolean(rails_solid, clip, 'INTERSECT')
    return rails_solid


def build_and_export_strip():
    bpy.ops.mesh.primitive_cube_add(size=1)
    box = bpy.context.object
    box.name = "trim_fishbone_spine"
    box.scale = (STRIP_L, STRIP_D, STRIP_W)
    bpy.ops.object.transform_apply(scale=True, location=False, rotation=False)
    bevel_box_edges(box, BOX_BEVEL_WIDTH, BOX_BEVEL_SEGMENTS)

    border_depth = BORDER_EMBOSS_HEIGHT + BORDER_EMBED_DEPTH
    border = build_border_solid(STRIP_W, STRIP_L, border_depth)
    # Box front face is at y=-STRIP_D/2 (outward normal -Y). The border
    # solid is built symmetric around its own local Y=0, so shift it in -Y
    # until its far edge stands proud past the front face by
    # BORDER_EMBOSS_HEIGHT and its near edge is buried BORDER_EMBED_DEPTH
    # past the surface (avoids a flush/coincident union boundary).
    border.location.y = -STRIP_D / 2 + (BORDER_EMBED_DEPTH - BORDER_EMBOSS_HEIGHT) / 2
    apply_boolean(box, border, 'UNION')

    # Lie flat for direct-to-plate resin printing: local Y (thickness) ->
    # world -Z (down, on the plate), local Z (STRIP_W, the strip's width)
    # -> world Y; local X (STRIP_L, the strip's long axis) stays world X.
    box.rotation_euler.x = math.radians(-90)
    bpy.ops.object.select_all(action='DESELECT')
    box.select_set(True)
    bpy.context.view_layer.objects.active = box
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

    if EXPORT_STL:
        export_stl(box, f"{box.name}.stl")

    return box


# ============================================================
# MAIN
# ============================================================

def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    clear_scene()

    build_and_export_strip()

    if RENDER_IMAGES:
        center, size = compute_scene_bounds()
        render_angles(center, size)

    frame_and_angle_view()

    print(f"Done. Strip exported to {EXPORT_DIR}")


if __name__ == "__main__":
    main()
