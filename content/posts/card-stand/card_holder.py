"""
Standing-card holder - the second part of the v8 pairing (Blender bpy) -
standalone, NOT terrain.

Companion to card_stand_v8_holder_return.py (the backplate). Same comb
geometry as the original v5 holder (card_stand_v5_flat_sharp_logo.py's
build_holder()) - flat stepped-tread base, 4 upright fins forming 3
card slots, a diagonal wedge cut from the underside for resin savings -
copied verbatim since that shape itself was never the problem. Two real
changes, both from this session's print-failure debugging:

1. ROUND tenon sockets instead of the original rectangular ones - see
   card_stand_v8_holder_return.py's TENON_DIAMETER comment for the full
   reasoning. Short version: once this prints in the reoriented axis
   (below), the sockets are the one feature that breaks the shape's
   otherwise-constant cross-section, and a round hole with a horizontal
   axis self-supports (tapers to a point) where a rectangular hole's
   flat top edge doesn't (needs a support bridge).
2. BAKED-IN PRINT ORIENTATION. The original holder's wedge cavity is
   what caused the real failure: printed with HOLDER_W (X) horizontal
   and the comb standing up in Z, the wedge is a large diagonal
   overhang, and partial supports on it came out deformed and scarred.
   But the whole shape is a prismatic extrusion along X (see
   _extrude_profile's own call in build_holder) - the cross-section
   never changes along that axis. Printing with X VERTICAL instead means
   every layer is an identical copy of the same profile: no overhang
   anywhere except the two round sockets, which self-support per point
   1. Rather than rely on remembering to rotate 90 degrees in the
   slicer every time, that rotation is baked into the exported mesh
   here (rotate_for_print, applied right before the STL is written) -
   the file opens already in the correct orientation.

TENON_* values are copied EXACTLY from card_stand_v8_holder_return.py's
own constants (position, diameter, depth) - not just close, since the
physical fit depends on both sides agreeing precisely. If that script's
TENON_* ever change, update these to match.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python card_stand_v8_holder_piece.py
"""

import bpy
import bmesh
import math
import mathutils
import os

# ============================================================
# CONFIG (all mm)
# ============================================================

EXPORT_DIR = "/Users/mannil/pfn/projects/mjnet/studio-m/blender/card-stand/output_v8"
EXPORT_STL = True

RENDER_IMAGES = True
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1600, 1200)
RENDER_ANGLES = {
    "front": (0.0, -1.0, 0.35),
    "side": (1.0, -0.4, 0.35),
    "top": (0.05, -0.3, 1.0),
    "iso": (0.7, -1.0, 0.55),
}

# --- Card / pile - unchanged from v5 ---
CARD_SIZE = 65.0
CARD_THICKNESS = 0.45                          # ~300gsm cardstock
CARDS_PER_PILE = 50
STACK_H = CARD_THICKNESS * CARDS_PER_PILE      # 22.5mm

# --- Standing-card holder (comb: flat base + 4 upright fins = 3 slots) - unchanged from v5 ---
SLOT_CLEARANCE = 0.5                           # per side, cards slide freely
HOLDER_W = 70.0                                # matches the ORIGINAL 70mm backplate width - this
                                                # holder is being reused as-is rather than widened to
                                                # match the current (86mm) backplate, see
                                                # card_stand_v8_holder_return.py's own TENON_* comment
STANDING_SLOT_GAP = STACK_H + 2 * SLOT_CLEARANCE   # 23.5mm
FIN_THICK = 3.0
BACK_FIN_THICK = 6.0
BASE_THICK = 4.0
FIN_HEIGHT = 24.0
STEP_RISE = 7.0

FLOOR_HS = [BASE_THICK + i * STEP_RISE for i in range(3)]

# --- Alignment joint (backplate <-> holder's back fin) - TENON_* copied
# exactly from card_stand_v8_holder_return.py. DIAMETER here is the
# nominal (un-shrunk) size - the backplate's tenon is the one that gets
# TENON_FIT_CLEARANCE subtracted for the slip fit, not this socket. ---
TENON_OFFSET_X = 17.0
TENON_DIAMETER = 8.0
TENON_SOCKET_DEPTH = 4.0
TENON_Z_CENTER = 28.0

# --- Resin-saving wedge carved into the underside - unchanged from v5 ---
HOLLOW_SHELL_T = 2.0

FINISH_BEVEL_W = 0.3                # holder's edge bevel

# ============================================================
# SANITY CHECKS
# ============================================================
HOLDER_DEPTH = 3 * FIN_THICK + 3 * STANDING_SLOT_GAP + BACK_FIN_THICK
BACK_FIN_TOP_Z = FLOOR_HS[-1] + FIN_HEIGHT   # tallest point of the comb itself (old Z, pre-rotation)

assert STEP_RISE < FIN_HEIGHT, \
    "a step taller than the fin itself would bury the divider - lower STEP_RISE or raise FIN_HEIGHT"
assert 0.0 < TENON_Z_CENTER < BACK_FIN_TOP_Z, "tenon socket falls outside the back fin's own height"
assert TENON_OFFSET_X + TENON_DIAMETER / 2 < HOLDER_W / 2 - 5.0, \
    "tenon socket runs past the back fin's own edge"
# Bed-fit check for the REORIENTED print (HOLDER_W vertical, HOLDER_DEPTH x
# BACK_FIN_TOP_Z as the bed-plane footprint) - different axes than the
# original v5 assert, which checked the old flat-on-comb orientation.
assert HOLDER_DEPTH <= 89.0, "holder deeper than the Photon Mono 2's 89.6mm bed axis (with margin)"
assert BACK_FIN_TOP_Z <= 143.0, \
    "holder taller (old Z) than the Photon Mono 2's 143.4mm bed axis"
# HOLDER_W (70mm) becomes the print's own build height in this orientation - comfortably within
# any resin printer's Z travel (this printer class is typically 155mm+), not asserted here since
# that figure isn't independently confirmed the way the XY bed size is.


# ============================================================
# GENERIC HELPERS (shared conventions - see pump_adapter.py, columns.py)
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


def apply_transform(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def apply_bevel(obj, width, segments=2):
    mod = obj.modifiers.new("Bevel", 'BEVEL')
    mod.width = width
    mod.segments = segments
    mod.limit_method = 'ANGLE'
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def mesh_volume(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    volume = bm.calc_volume()
    bm.free()
    return volume


def nonmanifold_fraction(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bad = sum(1 for e in bm.edges if not e.is_manifold)
    total = len(bm.edges)
    bm.free()
    return bad / total if total else 0.0


def build_box(sx, sy, sz, center, name):
    """Box spanning [center - size/2, center + size/2] on each axis."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    bmesh.ops.translate(bm, vec=center, verts=bm.verts)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def build_cylinder(diameter, length, center, name, segments=24):
    """Cylinder of given diameter/length centered at `center`, axis along
    world Y (the tenon's own protrusion/socket direction) - matches
    card_stand_v8_holder_return.py's build_cylinder exactly; round holes
    with a horizontal axis self-support (taper to a point) instead of
    presenting a flat overhanging top edge like a box socket would."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                           radius1=diameter / 2.0, radius2=diameter / 2.0, depth=length)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0.0, 0.0, 0.0),
                      matrix=mathutils.Matrix.Rotation(math.radians(90.0), 3, 'X'))
    bmesh.ops.translate(bm, vec=center, verts=bm.verts)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def _extrude_profile(points, plane, offset, thickness, name):
    """Build a flat face from a closed 2D point loop and extrude it into a
    solid prism. `plane` is 'XZ' (points are (x, z), extrude along Y) or
    'YZ' (points are (y, z), extrude along X). `offset` is the fixed
    coordinate of the starting face; extrusion runs +thickness from there."""
    bm = bmesh.new()
    if plane == 'XZ':
        verts = [bm.verts.new((p[0], offset, p[1])) for p in points]
    else:
        verts = [bm.verts.new((offset, p[0], p[1])) for p in points]
    face = bm.faces.new(verts)
    result = bmesh.ops.extrude_face_region(bm, geom=[face])
    new_verts = [v for v in result['geom'] if isinstance(v, bmesh.types.BMVert)]
    vec = (0.0, thickness, 0.0) if plane == 'XZ' else (thickness, 0.0, 0.0)
    bmesh.ops.translate(bm, vec=vec, verts=new_verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


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

    key_dir = mathutils.Vector((0.6, 0.45, -0.6)).normalized()
    key_data = bpy.data.lights.new("RenderKey", type='SUN')
    key_data.energy = 3.0
    key_obj = bpy.data.objects.new("RenderKey", key_data)
    key_obj.rotation_euler = key_dir.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.collection.objects.link(key_obj)

    fill_dir = mathutils.Vector((-0.5, 0.35, 0.35)).normalized()
    fill_data = bpy.data.lights.new("RenderFill", type='SUN')
    fill_data.energy = 0.6
    fill_obj = bpy.data.objects.new("RenderFill", fill_data)
    fill_obj.rotation_euler = fill_dir.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.collection.objects.link(fill_obj)

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
    try:
        scene.eevee.use_gtao = True
    except AttributeError:
        pass
    scene.render.resolution_x = RENDER_RESOLUTION[0]
    scene.render.resolution_y = RENDER_RESOLUTION[1]

    distance = size * 3.0
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


# ============================================================
# STANDING-CARD HOLDER
# ============================================================

def build_stepped_comb_profile(fin_thicks, gaps, floor_hs, fin_height, back_drop_z=0.0):
    """Trace a stepped-base, N-upright-fin comb as ONE closed (y, z) loop -
    zero booleans (unchanged from v5 - see that file's own comment for
    the full reasoning)."""
    pts = [(0.0, 0.0)]
    y = 0.0
    front_floor = 0.0
    for i, ft in enumerate(fin_thicks):
        top = front_floor + fin_height
        pts.append((y, top))
        y += ft
        pts.append((y, top))
        if i < len(gaps):
            back_floor = floor_hs[i]
            pts.append((y, back_floor))
            y += gaps[i]
            pts.append((y, back_floor))
            front_floor = back_floor
        else:
            pts.append((y, back_drop_z))
    return pts, y


def build_holder():
    """Same stiletto-silhouette comb+wedge as v5 - see that file's own
    build_holder() for the full massing rationale. Only real change:
    round tenon sockets instead of rectangular, see TENON_DIAMETER's
    comment at the top of this file."""
    fin_thicks = [FIN_THICK, FIN_THICK, FIN_THICK, BACK_FIN_THICK]
    gaps = [STANDING_SLOT_GAP, STANDING_SLOT_GAP, STANDING_SLOT_GAP]

    y_fin1_end = FIN_THICK + STANDING_SLOT_GAP + FIN_THICK

    wedge_start_y = y_fin1_end
    peak_h = FLOOR_HS[1] - HOLLOW_SHELL_T

    zigzag, depth = build_stepped_comb_profile(fin_thicks, gaps, FLOOR_HS, FIN_HEIGHT,
                                                back_drop_z=peak_h)
    assert abs(depth - HOLDER_DEPTH) < 1e-6

    profile = zigzag + [(wedge_start_y, 0.0)]
    shell = _extrude_profile(profile, 'YZ', -HOLDER_W / 2.0, HOLDER_W, "card_holder")

    # Tenon sockets cut into the back fin from its BACK face, going
    # forward into the fin a few mm with overshoot for a clean cut -
    # round instead of v5's rectangular box, see TENON_DIAMETER's
    # comment at the top of this file for why.
    overshoot = 2.0
    for sign in (-1, 1):
        socket = build_cylinder(
            TENON_DIAMETER, TENON_SOCKET_DEPTH + overshoot,
            (sign * TENON_OFFSET_X,
             depth - TENON_SOCKET_DEPTH / 2.0 + overshoot / 2.0,
             TENON_Z_CENTER),
            "tenon_socket")
        apply_boolean(shell, socket, 'DIFFERENCE')

    return shell


def rotate_for_print(obj):
    """Bakes the reoriented-for-printing rotation into the exported mesh
    (see this file's own module docstring, point 2) - HOLDER_W (old X,
    70mm) becomes the vertical build axis, so every layer is an
    identical copy of the comb+wedge profile and nothing needs support
    except the two round sockets (which self-support on their own).
    Rotating -90deg around Y maps old X -> new Z (up) and leaves old Y
    (depth) as still-horizontal; old Z (comb height, symmetric-ish
    footprint) becomes the other horizontal axis. Applied AFTER all
    geometry (comb + sockets) is built, right before export, so every
    Z/Y reference throughout build_holder() stays in the same familiar
    coordinate convention as v5 until this one final step."""
    obj.rotation_euler = (0.0, math.radians(-90.0), 0.0)
    apply_transform(obj)
    return obj


# ============================================================
# MAIN
# ============================================================

def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    clear_scene()

    holder = build_holder()
    apply_bevel(holder, FINISH_BEVEL_W)
    rotate_for_print(holder)

    vol = mesh_volume(holder)
    nm = nonmanifold_fraction(holder)
    bbox = [holder.matrix_world @ mathutils.Vector(c) for c in holder.bound_box]
    xs = [v.x for v in bbox]
    ys = [v.y for v in bbox]
    zs = [v.z for v in bbox]
    print(f"holder: volume={vol:.1f}mm3  non-manifold edge fraction={nm:.4f}")
    print(f"post-rotation bounds: X={max(xs)-min(xs):.1f}mm  Y={max(ys)-min(ys):.1f}mm  "
          f"Z={max(zs)-min(zs):.1f}mm  (Z should be ~{HOLDER_W:.1f}mm, the new build height)")
    assert vol > 0.0, "holder has zero/negative volume - a boolean likely emptied it"

    if EXPORT_STL:
        export_stl(holder, "card_holder.stl")

    if RENDER_IMAGES:
        center_pt, size = compute_scene_bounds()
        render_angles(center_pt, size)

    print("Done.")


if __name__ == "__main__":
    main()
