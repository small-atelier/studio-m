"""
Pyramid trim strip V2 - "studs" (Blender bpy) - standalone.

Same rails as trim_v1_plain.py, plus a row of diamond "rivet"
studs running just inside each rail - a riveted-girder look rather than a
braid filling the whole channel (the channel's middle stays flat). Same
diamond-stud language as runes/rune_panel_v2_ring_gems.py's border gems,
reinterpreted here as two rivet rows instead of one ring hugging all 4
edges of a rectangle.

One of a family of border motifs for the same strip footprint - see
_v1_plain.py, _v3_fishbone_spine.py, _v4_braid_2strand.py, and
_v5_braid_3strand.py for the others.

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

EXPORT_DIR = "/Users/mannil/Desktop/studio-m/TSONS/pyramid/trim/output/v2_studs"
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

# Border: one straight rail down each long edge, RAIL_OUTER_INSET (1.0mm,
# same as the rune panel borders) in from the true edge, plus a row of
# diamond studs just inside each rail (STUD_RAIL_GAP further in from the
# rail's own centerline). STUD_SPACING=10mm gives 14 studs per row across
# STRIP_L=140mm with no remainder.
RAIL_OUTER_INSET = 1.0
RAIL_WIDTH = 0.6
STUD_RAIL_GAP = 1.8
STUD_SIZE = 2.0
STUD_SPACING = 10.0
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
    Y=0). angle_deg=45 with w==h turns the box into a diamond - used for
    the studs below."""
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
    one watertight solid via real booleans. Kept as its own short chain per
    stud row (14 pieces) rather than folded into one giant union with the
    rails - see rune_panel_v6_fishbone_3strand.py's build_border_solid for
    why long boolean-union chains are unreliable with the EXACT solver."""
    solid = make_box_object(*parts[0], depth, f"{base_name}_solid")
    for cx, cz, w, h, angle in parts[1:]:
        piece = make_box_object(cx, cz, w, h, angle, depth, f"{base_name}_piece")
        apply_boolean(solid, piece, 'UNION')
    return solid


def build_stud_row(strip_l, stud_z, spacing, size):
    n_studs = max(1, round(strip_l / spacing))
    step = strip_l / n_studs
    return [
        (-strip_l / 2 + (i + 0.5) * step, stud_z, size, size, 45.0)
        for i in range(n_studs)
    ]


def build_border_solid(strip_w, strip_l, depth):
    """Border: two straight rails plus a row of diamond studs just inside
    each one (mirrored top/bottom), spaced evenly along the length."""
    rail_z = strip_w / 2 - RAIL_OUTER_INSET
    rail_parts = [
        (0.0, rail_z, strip_l, RAIL_WIDTH, 0.0),
        (0.0, -rail_z, strip_l, RAIL_WIDTH, 0.0),
    ]

    stud_z = rail_z - STUD_RAIL_GAP
    studs_a = build_stud_row(strip_l, stud_z, STUD_SPACING, STUD_SIZE)
    studs_b = build_stud_row(strip_l, -stud_z, STUD_SPACING, STUD_SIZE)

    rails_solid = merge_pieces_into_solid(rail_parts, depth, "rails")
    studs_a_solid = merge_pieces_into_solid(studs_a, depth, "studs_a")
    studs_b_solid = merge_pieces_into_solid(studs_b, depth, "studs_b")

    apply_boolean(rails_solid, studs_a_solid, 'UNION')
    apply_boolean(rails_solid, studs_b_solid, 'UNION')
    return rails_solid


def build_and_export_strip():
    bpy.ops.mesh.primitive_cube_add(size=1)
    box = bpy.context.object
    box.name = "trim_studs"
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
