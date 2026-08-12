"""
Prospero Brazier - flame only (Blender bpy) - standalone.

Just the stone flame cluster from brazier_with_flame.py, printed as its
own separate piece: a small glue peg ("nob") at the bottom to attach it
into the bowl after painting, with a 1.8mm hole drilled up into the peg
from below to hold a toothpick while painting. See brazier_with_flame.py
for the flame geometry's own rationale (twisted/tapered/bowed loft).

Run: Blender -> Scripting workspace -> Open this file -> Alt+P
Or headless: blender --background --python flame_only.py
"""

import bpy
import bmesh
import math
import mathutils
import os

# ============================================================
# CONFIG
# ============================================================

EXPORT_DIR = "/Users/mannil/Desktop/studio-m/TSONS/brazier/output_flame_only"
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

# Glue peg the flame sits on - kept slim (small radius) so it stays
# subtle, but tall enough that the ENTIRE toothpick hole fits inside it
# without ever touching the flame. Letting the hole reach into the
# flame's base (earlier passes) visibly notched/cracked the thin twisted
# geometry there - see the junction_close.png render - and was also the
# root cause of two separate catastrophic boolean failures. Keeping hole
# and flame from ever meeting sidesteps both problems at once.
NOB_RADIUS = 1.2
NOB_HEIGHT = 4.0
NOB_STEPS = 32

# Toothpick hole, drilled up from the peg's bottom face - lets you hold
# the piece on a toothpick while priming/painting. Confined entirely to
# the peg (HOLE_DEPTH stays comfortably below FLAME_EMBED's anchor point)
# rather than reaching into the flame - see the note on NOB_HEIGHT above.
HOLE_DIAMETER = 1.2  # radius 0.6mm
HOLE_DEPTH = 1.0      # shortened to stay clear of the new, higher flame
                      # anchor (NOB_HEIGHT-FLAME_EMBED=1.5) now that most
                      # of the peg is buried up inside the flame - see
                      # FLAME_EMBED below
HOLE_CLEARANCE = 0.6  # cutter pokes below the peg's bottom by this much for a clean through-cut

# Stone flame cluster - identical tuning to brazier_with_flame.py's final
# pass (twisted, tapered, bowed tongues fused into one body).
FLAME_TONGUES = [
    # (height, width, thickness, base_angle_deg, ox, oy, curve_deg, curve_amount)
    (44.64, 10.23, 2.42, 0.0, 0.0, 0.0, 15.0, 6.51),
    (37.20, 8.56, 2.05, 130.0, 1.67, -0.93, 160.0, 5.58),
    (31.62, 7.81, 2.05, 250.0, -1.40, 1.12, 290.0, 5.12),
]
FLAME_LEVELS = 32
FLAME_RING_POINTS = 8
FLAME_TWIST_DEG = 250
FLAME_EMBED = 2.5  # how far the tongue base is buried into the peg -
                    # raised from 0.5 so most of the 4mm peg is hidden up
                    # inside the flame's own base and only ~1.5mm shows
                    # below it. Safe to raise now because HOLE_DEPTH (above)
                    # was shortened to stay clear of the new anchor point -
                    # it's specifically the hole crossing the flame's
                    # paper-thin (t=0) base cap that's fragile (an earlier
                    # attempt at FLAME_EMBED=0.9 with the old deeper hole
                    # blew up the boolean, volume dropped to ~1mm3); the
                    # peg-flame overlap itself was never the problem.


# ============================================================
# HELPERS (shared conventions - see runes/rune_panel_v1_plain.py)
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

    distance = size * 4.0
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
# NOB (glue peg) + TOOTHPICK HOLE
# ============================================================

def build_nob():
    """Solid cylinder from z=0 (ground) to z=NOB_HEIGHT - the small glue
    peg the flame stands on."""
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=NOB_STEPS,
        radius1=NOB_RADIUS, radius2=NOB_RADIUS, depth=NOB_HEIGHT,
    )
    for v in bm.verts:
        v.co.z += NOB_HEIGHT / 2  # create_cone is Z-centered; shift base to z=0

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("nob")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("nob", mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def build_hole_cutter():
    """Thin cylinder cutter for the toothpick hole, drilled up from the
    peg's bottom face - extends slightly past z=0 (HOLE_CLEARANCE) for a
    clean through-cut, up to HOLE_DEPTH."""
    bm = bmesh.new()
    total_h = HOLE_DEPTH + HOLE_CLEARANCE
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=24,
        radius1=HOLE_DIAMETER / 2, radius2=HOLE_DIAMETER / 2, depth=total_h,
    )
    for v in bm.verts:
        v.co.z += total_h / 2 - HOLE_CLEARANCE  # base at z=-HOLE_CLEARANCE, top at z=HOLE_DEPTH

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("hole_cutter")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("hole_cutter", mesh)
    bpy.context.collection.objects.link(obj)
    return obj


# ============================================================
# FLAME (stone flame cluster - see brazier_with_flame.py for rationale)
# ============================================================

def _flame_envelope(t):
    if t <= 0.15:
        return 0.15 + (0.9 - 0.15) * (t / 0.15)
    u = (t - 0.15) / 0.85
    return max(0.05, 0.9 * (1 - u) ** 1.3)


def build_flame_tongue_object(height, width, thickness, angle_deg, ox, oy, curve_deg, curve_amount):
    bm = bmesh.new()
    rings = []
    curve_dir = math.radians(curve_deg)
    curve_cos, curve_sin = math.cos(curve_dir), math.sin(curve_dir)
    for i in range(FLAME_LEVELS + 1):
        t = i / FLAME_LEVELS
        z = t * height
        env = _flame_envelope(t)
        hw = (width / 2) * env
        ht = (thickness / 2) * env
        twist = math.radians(angle_deg + FLAME_TWIST_DEG * t)
        cos_tw, sin_tw = math.cos(twist), math.sin(twist)

        bow = curve_amount * math.sin(math.pi * t)
        cx = ox + bow * curve_cos
        cy = oy + bow * curve_sin

        ring = []
        for j in range(FLAME_RING_POINTS):
            phi = 2 * math.pi * j / FLAME_RING_POINTS
            lx, ly = hw * math.cos(phi), ht * math.sin(phi)
            rx = lx * cos_tw - ly * sin_tw
            ry = lx * sin_tw + ly * cos_tw
            ring.append(bm.verts.new((rx + cx, ry + cy, z + NOB_HEIGHT - FLAME_EMBED)))
        rings.append(ring)

    for i in range(FLAME_LEVELS):
        r0, r1 = rings[i], rings[i + 1]
        for j in range(FLAME_RING_POINTS):
            a, b = r0[j], r0[(j + 1) % FLAME_RING_POINTS]
            c, d = r1[j], r1[(j + 1) % FLAME_RING_POINTS]
            bm.faces.new((a, b, d, c))

    bm.faces.new(rings[0])
    bm.faces.new(list(reversed(rings[-1])))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("flame_tongue")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(mesh.name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def build_flame():
    tongues = [build_flame_tongue_object(*t) for t in FLAME_TONGUES]
    flame = tongues[0]
    for other in tongues[1:]:
        apply_boolean(flame, other, 'UNION')
    flame.name = "flame"
    return flame


def build_flame_piece():
    nob = build_nob()

    flame = build_flame()
    apply_boolean(nob, flame, 'UNION')

    hole = build_hole_cutter()
    apply_boolean(nob, hole, 'DIFFERENCE')

    nob.name = "flame_only"
    return nob


# ============================================================
# MAIN
# ============================================================

def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    clear_scene()

    piece = build_flame_piece()

    print(f"Flame-only piece built: nob {NOB_RADIUS*2}mm dia x {NOB_HEIGHT}mm tall, "
          f"toothpick hole {HOLE_DIAMETER}mm dia x {HOLE_DEPTH}mm deep")

    if EXPORT_STL:
        export_stl(piece, "flame_only.stl")

    if RENDER_IMAGES:
        center, size = compute_scene_bounds()
        render_angles(center, size)

    print("Done.")


if __name__ == "__main__":
    main()
