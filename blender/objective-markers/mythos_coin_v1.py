"""
Mythos Coin v1 - a 40mm x 2mm objective marker coin with the Mythos logo
icon raised in the centre. Coin profile copies the
downloaded Spearhead coins the objective-marker pocket is sized for: 1mm
base, 1mm raised rim from r=18 to r=20, art raised 1mm in the field - so it
sits in the same pocket at the same flush height. Single material, meant
for resin.

The coin body is built directly as a stepped mesh (no booleans); the logo
is the only boolean union onto it - see feedback_blender_boolean_fragility
memory.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python mythos_coin_v1.py

Skip renders:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python mythos_coin_v1.py -- --no-render
"""

import bpy
import bmesh
import json
import math
import mathutils
import os
import sys

# ============================================================
# CLI ARGS
# ============================================================
RENDER_IMAGES = "--no-render" not in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])

# ============================================================
# CONFIG (all mm)
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(SCRIPT_DIR, "output")
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1400, 1400)

COIN_DIAM      = 40.0
COIN_THICKNESS = 2.0
BASE_THICKNESS = 1.0   # field level - rim and logo rise from here to COIN_THICKNESS
RIM_WIDTH      = 2.0
SEGMENTS       = 256
EMBED          = 0.3   # logo prism starts this far below the field for a clean union

LOGO_MARGIN    = 1.5   # clearance between the logo's outermost point and the rim's inner wall

# same traced contours as the objective disc / dice tray / card-stand
MYTHOS_CONTOURS_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "card-stand", "logo_contours_v5.json"))
MYTHOS_ASPECT    = 376.0 / 720.0  # h/w, 720x720 source - width is the controlling dimension
NOMINAL_ICON_W   = 30.0   # built at this width, then scaled to fit the field

# ============================================================
# DERIVED
# ============================================================
COIN_RADIUS  = COIN_DIAM / 2
FIELD_RADIUS = COIN_RADIUS - RIM_WIDTH
LOGO_FIT_R   = FIELD_RADIUS - LOGO_MARGIN

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

# ============================================================
# COIN BODY
# ============================================================
def build_coin_body(name):
    """Stepped solid built straight as a mesh: bottom disc, outer wall,
    rim top, rim inner wall down to the field, field cap."""
    bm = bmesh.new()

    def ring(r, z):
        return [bm.verts.new((r * math.cos(2 * math.pi * i / SEGMENTS),
                              r * math.sin(2 * math.pi * i / SEGMENTS), z)) for i in range(SEGMENTS)]

    outer_bot = ring(COIN_RADIUS, 0.0)
    outer_top = ring(COIN_RADIUS, COIN_THICKNESS)
    inner_top = ring(FIELD_RADIUS, COIN_THICKNESS)
    inner_bot = ring(FIELD_RADIUS, BASE_THICKNESS)

    bm.faces.new(list(reversed(outer_bot)))
    for a, b in ((outer_bot, outer_top), (outer_top, inner_top), (inner_top, inner_bot)):
        for i in range(SEGMENTS):
            j = (i + 1) % SEGMENTS
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(inner_bot)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return new_object_from_bmesh(bm, name)

# ============================================================
# MYTHOS LOGO (raised on top) - same builders as objective_markers_v1.py,
# no mirror since it reads from above
# ============================================================
def dedupe_closed_loop(points, tol=1e-9):
    """Traced contours (skimage find_contours) can come back as closed rings
    with the first and last point identical - a degenerate zero-length edge
    that corrupts the extruded solid's topology if left in."""
    if len(points) > 1:
        x0, y0 = points[0]
        x1, y1 = points[-1]
        if abs(x0 - x1) < tol and abs(y0 - y1) < tol:
            return points[:-1]
    return points


def load_contours(path):
    with open(path) as f:
        return json.load(f)


def _extrude_profile_xy(points, z0, thickness, name):
    bm = bmesh.new()
    verts = [bm.verts.new((p[0], p[1], z0)) for p in points]
    face = bm.faces.new(verts)
    ret = bmesh.ops.extrude_face_region(bm, geom=[face])
    new_verts = [v for v in ret["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0.0, 0.0, thickness), verts=new_verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    return new_object_from_bmesh(bm, name)


def build_mythos_prism(contours, icon_w, icon_h, local_y, z0, thickness, name_prefix):
    """Built at local X=0, local Y=local_y - mirror/placement happens later,
    once icon and text are both built, so they stay in registration."""
    outer_pts, hole_pts = [], []
    for c in contours:
        pts = [(u * icon_w - icon_w / 2.0, v * icon_h - icon_h / 2.0 + local_y) for u, v in c["points"]]
        pts = dedupe_closed_loop(pts)
        (hole_pts if c["hole"] else outer_pts).append(pts)

    solid = _extrude_profile_xy(outer_pts[0], z0, thickness, f"{name_prefix}_0")
    for i, pts in enumerate(outer_pts[1:], start=1):
        piece = _extrude_profile_xy(pts, z0, thickness, f"{name_prefix}_{i}")
        mod = solid.modifiers.new("Union", 'BOOLEAN')
        mod.object = piece
        mod.operation = 'UNION'
        bpy.context.view_layer.objects.active = solid
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(piece, do_unlink=True)
    for i, pts in enumerate(hole_pts):
        cutter = _extrude_profile_xy(pts, z0 - 1.0, thickness + 2.0, f"{name_prefix}_hole_{i}")
        mod = solid.modifiers.new("Hole", 'BOOLEAN')
        mod.object = cutter
        mod.operation = 'DIFFERENCE'
        bpy.context.view_layer.objects.active = solid
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cutter, do_unlink=True)

    return solid



def build_logo(contours, z0, thickness, name):
    """Mythos icon, scaled in XY so its outermost point lands exactly on
    LOGO_FIT_R - fits the round field by actual shape, not bounding box."""
    icon_w = NOMINAL_ICON_W
    logo = build_mythos_prism(contours, icon_w, icon_w * MYTHOS_ASPECT, 0.0, z0, thickness, name)

    # traced contours don't sit centred in their source frame - centre the
    # icon's own bounding box on the coin before fitting
    xs = [v.co.x for v in logo.data.vertices]
    ys = [v.co.y for v in logo.data.vertices]
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    for v in logo.data.vertices:
        v.co.x -= cx
        v.co.y -= cy

    max_r = max(math.hypot(v.co.x, v.co.y) for v in logo.data.vertices)
    scale = LOGO_FIT_R / max_r
    for v in logo.data.vertices:
        v.co.x *= scale
        v.co.y *= scale
    logo.data.update()
    xs = [v.co.x for v in logo.data.vertices]
    ys = [v.co.y for v in logo.data.vertices]
    print(f"  logo: {max(xs) - min(xs):.1f} x {max(ys) - min(ys):.1f}mm")
    return logo


def build_coin():
    coin = build_coin_body("mythos_coin")
    contours = load_contours(MYTHOS_CONTOURS_PATH)
    logo = build_logo(contours, BASE_THICKNESS - EMBED,
                      COIN_THICKNESS - BASE_THICKNESS + EMBED, "mythos_coin_logo")

    vol_before = mesh_volume(coin)
    logo_vol = mesh_volume(logo)
    mod = coin.modifiers.new("Logo", 'BOOLEAN')
    mod.object = logo
    mod.operation = 'UNION'
    bpy.context.view_layer.objects.active = coin
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(logo, do_unlink=True)

    vol_after = mesh_volume(coin)
    nm = nonmanifold_fraction(coin)
    print(f"  coin={vol_before:.0f}mm3 logo={logo_vol:.0f}mm3 -> merged={vol_after:.0f}mm3 (non-manifold {nm:.4f})")
    if not (vol_before < vol_after < vol_before + logo_vol) or nm > 0.01:
        print("  !! WARNING: logo union looks corrupted")
    return coin

# ============================================================
# RENDER
# ============================================================
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
    center = mathutils.Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2))
    size = max(max(xs) - min(xs), max(ys) - min(ys))
    return center, size


def setup_render_engine():
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = RENDER_RESOLUTION


def add_light(target, distance):
    light_data = bpy.data.lights.new("RenderLight", type='SUN')
    light_data.energy = 3.0
    light = bpy.data.objects.new("RenderLight", light_data)
    bpy.context.collection.objects.link(light)
    light.location = target + mathutils.Vector((distance * 0.4, -distance * 0.5, distance * 0.9))
    direction = target - light.location
    light.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()


def render_hero(name, center, size):
    """Angled 3/4 perspective shot to show the tile relief and pocket."""
    distance = size * 1.1
    cam_data = bpy.data.cameras.new("HeroCam")
    cam_data.type = 'PERSP'
    cam_data.lens = 50
    cam = bpy.data.objects.new("HeroCam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = center + mathutils.Vector((0.0, -distance * 0.85, distance * 0.9))
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam

    add_light(center, distance)
    bpy.context.scene.render.filepath = os.path.join(RENDER_DIR, f"{name}_hero.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {bpy.context.scene.render.filepath}")


def render_top(name, center, size):
    """Straight top-down orthographic shot for a plan-view scale reference."""
    cam_data = bpy.data.cameras.new("TopCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = size * 1.05
    cam = bpy.data.objects.new("TopCam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = center + mathutils.Vector((0.0, 0.0, size))
    cam.rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.scene.camera = cam

    add_light(center, size)
    bpy.context.scene.render.filepath = os.path.join(RENDER_DIR, f"{name}_top.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {bpy.context.scene.render.filepath}")


def _clear_cameras_and_lights():
    for cam in [o for o in bpy.context.scene.objects if o.type == 'CAMERA']:
        bpy.data.objects.remove(cam, do_unlink=True)
    for light in [o for o in bpy.context.scene.objects if o.type == 'LIGHT']:
        bpy.data.objects.remove(light, do_unlink=True)


def render_object(obj):
    setup_render_engine()
    center, size = compute_scene_bounds()
    render_hero(obj.name, center, size)
    _clear_cameras_and_lights()
    render_top(obj.name, center, size)

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
    coin = build_coin()
    print(f"Mythos coin v1 - {COIN_DIAM:.0f}mm x {COIN_THICKNESS:.0f}mm, field r={FIELD_RADIUS:.0f}mm, "
          f"logo fit r={LOGO_FIT_R:.1f}mm")
    export_stl(coin)
    if RENDER_IMAGES:
        os.makedirs(RENDER_DIR, exist_ok=True)
        render_object(coin)
    print("Done.")


main()
