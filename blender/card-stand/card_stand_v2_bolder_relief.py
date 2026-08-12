"""
Store-counter business-card stand (Blender bpy) - standalone, NOT terrain.

Holds 3 piles of 65x65mm cards (~50/pile) in individually-sloped trays,
with a tall backplate carrying a bold "MYTHOS" logo relief behind them.

Print target: Anycubic Photon Mono 2 (~143.4 x 89.6 x 165mm build volume) -
too small for one continuous stand, so this is 4 separate prints that key
together and get glued:
  - tray_side.stl    x2  (plain, no joint)
  - tray_center.stl  x1  (2 socket cutouts in the back wall top - the joint)
  - backplate.stl    x1  (2 tenons on the bottom edge, logo relief on the
    front face) - print standing on edge (width along X) to fit the bed.

Boolean approach follows feedback_blender_boolean_fragility /
feedback_functional_parts_pipeline: the tray SHELL is one wedge profile
(flat bottom, sloped top - a single linear extrude, no boolean at all),
then just ONE rotated-box DIFFERENCE cuts the sloped pocket (the leftover
uncut wedge material at the front IS the retaining lip - no separate lip
cutter needed). No curves, no tangency, generous overlaps throughout.

The logo is a hand-modelled bold interpretation, not a raster trace of
the source JPG - fine traced linework would be exactly the thin/fragile
geometry those notes warn about, and unpaintable by hand at this scale.
Each decoration piece (mountain, sun, rays, moon, stars, text) is a
separate, non-overlapping-with-its-neighbors relief, unioned onto the
backplate one at a time (sequential, not joined into one cutter first -
see fragility note trigger 3).

Run: Blender -> Scripting workspace -> Open this file -> Alt+P
Or headless:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python card_stand_v1.py
"""

import bpy
import bmesh
import math
import mathutils
import os

# ============================================================
# CONFIG (all mm)
# ============================================================

EXPORT_DIR = "/Users/mannil/Desktop/studio-m/TSONS/card_stand/output_v2"
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

CIRCLE_STEPS = 40

# --- Card / pile ---
CARD_SIZE = 65.0
CARD_THICKNESS = 0.45                          # ~300gsm cardstock
CARDS_PER_PILE = 50
STACK_H = CARD_THICKNESS * CARDS_PER_PILE      # 22.5mm

# --- Tray (sloped pocket) ---
SLOT_CLEARANCE = 0.5                           # per side, cards slide freely
POCKET_W = CARD_SIZE + 2 * SLOT_CLEARANCE      # 66.0mm
POCKET_D = CARD_SIZE + 2 * SLOT_CLEARANCE      # 66.0mm, measured along the slope
TRAY_TILT_DEG = 18.0                           # incline from horizontal
SIDE_WALL_T = 2.5
BACK_WALL_THICK = 6.0                          # thicker than the sides - hosts the tenon sockets
FLOOR_T = 3.0                                  # pocket floor thickness (perpendicular to slope)
LIP_H = 8.0                                    # front retaining lip height above the pocket floor
POCKET_CUT_OVERSHOOT = 5.0                     # generous overshoot clearing the cut faces

TRAY_W = POCKET_W + 2 * SIDE_WALL_T            # 71.0mm
TRAY_D = POCKET_D + BACK_WALL_THICK            # 72.0mm

SHELL_H_FRONT = FLOOR_T + LIP_H                # 11.0mm - wedge height at the front
RISE = TRAY_D * math.tan(math.radians(TRAY_TILT_DEG))
SHELL_H_BACK = SHELL_H_FRONT + RISE            # wedge height at the back (~34mm)

POCKET_CUTTER_H = FLOOR_T + POCKET_CUT_OVERSHOOT   # local cutter height (before rotation)

TRAY_SPACING_X = TRAY_W                        # trays sit edge-to-edge, glued

# --- Alignment joint (center tray <-> backplate) ---
TENON_OFFSET_X = 17.0             # +-, within the center tray's back wall footprint
TENON_W = 10.0
TENON_D = BACK_WALL_THICK - 1.5   # stays inside the 6mm back wall with margin either side
TENON_SOCKET_DEPTH = 5.0
TENON_FIT_CLEARANCE = 0.25        # per side, snug press fit
TENON_EMBED = 1.0                 # extra overlap where the tenon unions onto the backplate

# --- Backplate ---
BACKPLATE_W = 140.0                # <= Photon Mono 2's 143.4mm X, printed standing on edge
BACKPLATE_H = 120.0
BACKPLATE_T = 6.0
EMBOSS_H = 2.8                     # raised logo relief height - bold, paintable, casts real shadow
EMBOSS_EMBED = 1.0                 # extra embed into the backplate for a clean union
FINISH_BEVEL_W = 0.3                # global edge bevel, matches other props' finishing pass

# ============================================================
# SANITY CHECKS
# ============================================================
assert LIP_H < STACK_H, "front lip taller than the card stack - cards couldn't be grabbed"
assert SHELL_H_BACK > FLOOR_T + STACK_H, "back wall too short to stay behind a full stack"
assert TENON_OFFSET_X + TENON_W / 2 < TRAY_W / 2 - SIDE_WALL_T, \
    "tenon socket runs past the center tray's own side wall"
assert BACKPLATE_W <= 143.0, "backplate wider than the Photon Mono 2 bed (143.4mm, standing on edge)"
assert BACKPLATE_T <= 89.0, "backplate thicker than the Photon Mono 2 bed's other axis"
assert BACKPLATE_H <= 164.0, "backplate taller than the Photon Mono 2's 165mm Z"


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


def union_onto(base, piece):
    return apply_boolean(base, piece, 'UNION')


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


def _extrude_profile(points, plane, offset, thickness, name):
    """Build a flat face from a closed 2D point loop and extrude it into a
    solid prism. `plane` is 'XZ' (points are (x, z), extrude along Y) or
    'YZ' (points are (y, z), extrude along X). `offset` is the fixed
    coordinate of the starting face; extrusion runs +thickness from there.
    Same family as _spin_profile (brazier.py/columns.py) but linear
    instead of rotational - no booleans needed for a simple solid prism."""
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


def circle_points_xz(radius, cx=0.0, cz=0.0, steps=CIRCLE_STEPS):
    return [(cx + radius * math.cos(2 * math.pi * i / steps),
             cz + radius * math.sin(2 * math.pi * i / steps)) for i in range(steps)]


def rotate_points_2d(points, angle_rad, center=(0.0, 0.0)):
    ca, sa = math.cos(angle_rad), math.sin(angle_rad)
    out = []
    for (x, z) in points:
        dx, dz = x - center[0], z - center[1]
        out.append((center[0] + dx * ca - dz * sa, center[1] + dx * sa + dz * ca))
    return out


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

    # Raking key light: aimed with to_track_quat (direction the light
    # travels), not hand-picked euler angles - a near-head-on light gives a
    # flat relief almost zero shading contrast on its own top face (only
    # the short side walls catch anything), which is what a first attempt
    # at hand-derived euler angles produced here. Mostly-horizontal
    # traeval direction relative to the logo face's -Y normal is what
    # actually reveals a shallow raised plateau.
    # Direction the light TRAVELS. The logo face's outward normal is
    # roughly -Y, so illuminating it needs dir.y > 0 (light moving toward
    # +Y hits a -Y-facing surface) - a first attempt got this backwards
    # (dir.y < 0) and lit the *back* of everything, rendering pure black.
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


def render_closeup(obj, name, direction=(0.0, -1.0, 0.0)):
    """Tight, straight-on shot of a single object's own logo face - the
    non-manifold-fraction volume check catches CORRUPTION, not composition
    or legibility, so eyeball this before trusting the wide renders (see
    feedback_blender_boolean_fragility on close-crop verification)."""
    xs = [ (obj.matrix_world @ mathutils.Vector(c)) for c in obj.bound_box ]
    center = sum(xs, mathutils.Vector((0, 0, 0))) / 8.0
    size = max((max(v[i] for v in xs) - min(v[i] for v in xs)) for i in range(3))
    cam_obj = setup_camera_and_light(center)
    cam_obj.data.lens = 85.0
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = RENDER_RESOLUTION[0]
    scene.render.resolution_y = RENDER_RESOLUTION[1]
    distance = size * 1.6
    cam_obj.location = center + mathutils.Vector(direction).normalized() * distance
    scene.render.filepath = os.path.join(RENDER_DIR, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {scene.render.filepath}")


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
# TRAY
# ============================================================

def build_tray(is_center, name):
    """Wedge shell (flat bottom, sloped top, single linear extrude - no
    boolean) with ONE rotated-box pocket cut. The uncut wedge material
    left in front of the cutter IS the retaining lip - there's nothing
    else to cut there."""
    profile_yz = [
        (0.0, 0.0),                    # front-bottom
        (TRAY_D, 0.0),                 # back-bottom
        (TRAY_D, SHELL_H_BACK),        # back-top
        (0.0, SHELL_H_FRONT),          # front-top
    ]
    shell = _extrude_profile(profile_yz, 'YZ', -TRAY_W / 2, TRAY_W, name)

    theta = math.radians(TRAY_TILT_DEG)
    slope_dir = (math.cos(theta), math.sin(theta))
    normal_dir = (-math.sin(theta), math.cos(theta))
    front_top = (0.0, SHELL_H_FRONT)
    y0 = front_top[0] - normal_dir[0] * FLOOR_T
    z0 = front_top[1] - normal_dir[1] * FLOOR_T

    cutter = build_box(POCKET_W, POCKET_D, POCKET_CUTTER_H,
                        (0.0, POCKET_D / 2.0, POCKET_CUTTER_H / 2.0), "pocket_cutter")
    cutter.rotation_euler = (theta, 0.0, 0.0)
    cutter.location = (0.0, y0, z0)
    apply_transform(cutter)
    apply_boolean(shell, cutter, 'DIFFERENCE')

    if is_center:
        for sign in (-1, 1):
            socket = build_box(
                TENON_W, TENON_D, TENON_SOCKET_DEPTH + POCKET_CUT_OVERSHOOT,
                (sign * TENON_OFFSET_X,
                 POCKET_D + BACK_WALL_THICK / 2.0,
                 SHELL_H_BACK - TENON_SOCKET_DEPTH / 2.0 + POCKET_CUT_OVERSHOOT / 2.0),
                "tenon_socket")
            apply_boolean(shell, socket, 'DIFFERENCE')

    shell.name = name
    return shell


# ============================================================
# BACKPLATE + LOGO
# ============================================================

def build_mountain(base_x, base_z):
    """Bold two-peak silhouette - solid, no thin linework."""
    main_peak = [
        (base_x - 34.0, base_z), (base_x, base_z + 34.0), (base_x + 30.0, base_z),
    ]
    side_peak = [
        (base_x + 6.0, base_z), (base_x + 32.0, base_z + 20.0), (base_x + 50.0, base_z),
    ]
    m1 = _extrude_profile(main_peak, 'XZ', -EMBOSS_H, EMBOSS_H + EMBOSS_EMBED, "mountain_main")
    m2 = _extrude_profile(side_peak, 'XZ', -EMBOSS_H, EMBOSS_H + EMBOSS_EMBED, "mountain_side")
    return [m1, m2]


def build_sun(cx, cz, radius=13.0, ray_len=11.0, ray_w=5.0, n_rays=8):
    pieces = []
    disc = _extrude_profile(circle_points_xz(radius, cx, cz), 'XZ',
                             -EMBOSS_H, EMBOSS_H + EMBOSS_EMBED, "sun_disc")
    pieces.append(disc)
    ray_profile = [
        (-ray_w / 2.0, radius * 0.9), (ray_w / 2.0, radius * 0.9),
        (ray_w * 0.25, radius * 0.9 + ray_len), (-ray_w * 0.25, radius * 0.9 + ray_len),
    ]
    for i in range(n_rays):
        angle = 2 * math.pi * i / n_rays
        pts = rotate_points_2d(ray_profile, angle, center=(0.0, 0.0))
        pts = [(x + cx, z + cz) for (x, z) in pts]
        ray = _extrude_profile(pts, 'XZ', -EMBOSS_H, EMBOSS_H + EMBOSS_EMBED, f"sun_ray_{i}")
        pieces.append(ray)
    return pieces


def build_moon(cx, cz, radius=11.0, offset=6.0):
    outer_pts = circle_points_xz(radius, cx, cz)
    inner_pts = circle_points_xz(radius * 0.9, cx + offset, cz)
    outer = _extrude_profile(outer_pts, 'XZ', -EMBOSS_H, EMBOSS_H + EMBOSS_EMBED, "moon_outer")
    inner = _extrude_profile(inner_pts, 'XZ', -EMBOSS_H - 1.0, EMBOSS_H + EMBOSS_EMBED + 2.0, "moon_inner")
    apply_boolean(outer, inner, 'DIFFERENCE')
    return outer


def build_star(cx, cz, size=6.0):
    pts = [(cx, cz + size), (cx + size * 0.4, cz), (cx, cz - size), (cx - size * 0.4, cz)]
    return _extrude_profile(pts, 'XZ', -EMBOSS_H, EMBOSS_H + EMBOSS_EMBED, "star")


def build_text(text, size, location, name="logo_text"):
    curve_data = bpy.data.curves.new(name + "_curve", type='FONT')
    curve_data.body = text
    curve_data.size = size
    curve_data.extrude = (EMBOSS_H + EMBOSS_EMBED) / 2.0
    curve_data.align_x = 'CENTER'
    curve_data.align_y = 'CENTER'
    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(obj)

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')

    obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    obj.location = location
    apply_transform(obj)
    return obj


def build_backplate():
    shell = build_box(BACKPLATE_W, BACKPLATE_T, BACKPLATE_H,
                       (0.0, BACKPLATE_T / 2.0, BACKPLATE_H / 2.0), "backplate_shell")

    for sign in (-1, 1):
        tenon = build_box(
            TENON_W - 2 * TENON_FIT_CLEARANCE,
            TENON_D - 2 * TENON_FIT_CLEARANCE,
            TENON_SOCKET_DEPTH + TENON_EMBED,
            (sign * TENON_OFFSET_X, BACKPLATE_T / 2.0,
             -TENON_SOCKET_DEPTH / 2.0 + TENON_EMBED / 2.0),
            "tenon")
        union_onto(shell, tenon)

    # --- Logo layout (X-Z, front face at Y=0) ---
    icon_cz = BACKPLATE_H * 0.62
    for piece in build_mountain(0.0, icon_cz - 18.0):
        union_onto(shell, piece)
    for piece in build_sun(-8.0, icon_cz + 24.0):
        union_onto(shell, piece)
    union_onto(shell, build_moon(42.0, icon_cz + 14.0))
    for (sx, sz) in [(-48.0, icon_cz + 30.0), (48.0, icon_cz + 8.0), (30.0, icon_cz + 42.0)]:
        union_onto(shell, build_star(sx, sz))

    text_obj = build_text("MYTHOS", 22.0, (0.0, -EMBOSS_H, BACKPLATE_H * 0.18))
    union_onto(shell, text_obj)

    shell.name = "backplate"
    return shell


# ============================================================
# MAIN
# ============================================================

def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    clear_scene()

    side_a = build_tray(False, "tray_side_a")
    side_b = build_tray(False, "tray_side_b")
    center = build_tray(True, "tray_center")
    backplate = build_backplate()

    for obj in (side_a, side_b, center, backplate):
        apply_bevel(obj, FINISH_BEVEL_W)

    for obj in (side_a, side_b, center, backplate):
        vol = mesh_volume(obj)
        nm = nonmanifold_fraction(obj)
        print(f"{obj.name}: volume={vol:.1f}mm3  non-manifold edge fraction={nm:.4f}")
        assert vol > 0.0, f"{obj.name} has zero/negative volume - a boolean likely emptied it"

    if EXPORT_STL:
        export_stl(side_a, "tray_side.stl")
        export_stl(center, "tray_center.stl")
        export_stl(backplate, "backplate.stl")
        print("(tray_side.stl -> print x2)")

    # Position for an assembled preview render only (after STL export, so
    # the exported meshes stay at their own clean per-part origins).
    side_a.location = (-TRAY_SPACING_X, 0.0, 0.0)
    side_b.location = (TRAY_SPACING_X, 0.0, 0.0)
    backplate.location = (0.0, TRAY_D, SHELL_H_BACK)

    if RENDER_IMAGES:
        center_pt, size = compute_scene_bounds()
        render_angles(center_pt, size)
        render_closeup(backplate, "logo_closeup")

    print("Done.")


if __name__ == "__main__":
    main()
