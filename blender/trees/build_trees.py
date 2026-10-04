"""
Organic terrain trees (Blender bpy) - exploratory first pass, not yet a
final print-ready set.

Trunk+branches are built as a chain of metaball elements, not curves/
booleans - metaballs blend into each other smoothly on their own, which
sidesteps the EXACT-solver fragility on organic/near-degenerate geometry
seen on other projects here (see feedback_blender_boolean_fragility
memory) entirely for the trunk shape itself.

Canopy is a separate "mushroom cap" piece - an icosphere pushed through
a Displace modifier (cloud/voronoi noise) for a lumpy foliage-clump look,
then flattened on the underside so it prints flat-side-down with no
supports and seats on top of the trunk.

This pass has NO peg/socket joinery yet - trunk and canopy are each just
flattened solids on their own. Assembled preview renders just butt the
two together visually to check proportions; once a trunk shape + canopy
style is picked, a peg/socket pair (same pattern as the token/box
projects) can be added as a follow-up.

Run everything:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python build_trees.py

Run one group only:
  ... --python build_trees.py -- --only trunks
  ... --python build_trees.py -- --only canopies
  ... --python build_trees.py -- --only assemblies
"""

import bpy
import bmesh
import math
import mathutils
import os
import random
import sys

# ============================================================
# CLI ARGS
# ============================================================


def _parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only, render = None, True
    i = 0
    while i < len(argv):
        if argv[i] == "--only":
            only = argv[i + 1]; i += 2
        elif argv[i] == "--no-render":
            render = False; i += 1
        else:
            i += 1
    return only, render


ONLY, RENDER_IMAGES = _parse_args()

# ============================================================
# CONFIG (all mm)
# ============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(SCRIPT_DIR, "output")
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1200, 1200)

TRUNK_COLOR = (0.32, 0.21, 0.12, 1.0)
CANOPY_COLOR = (0.22, 0.40, 0.15, 1.0)

# ============================================================
# GENERIC HELPERS (ported from blender/combat-modifiers/build_modifier_tokens.py)
# ============================================================


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block)
    for block in list(bpy.data.metaballs):
        bpy.data.metaballs.remove(block)


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


def convert_to_mesh(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')
    return bpy.context.view_layer.objects.active


def recalc_normals(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def mesh_volume(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    volume = bm.calc_volume()
    bm.free()
    return volume


def flatten_bottom(obj, z_plane, span):
    """Cut everything below z_plane with a big cube - gives a flat,
    print-bed-ready underside on an otherwise round/organic solid."""
    bpy.ops.mesh.primitive_cube_add(size=span, location=(0, 0, z_plane - span / 2.0))
    cutter = bpy.context.active_object
    apply_boolean(obj, cutter, 'DIFFERENCE')
    return obj


def export_stl(obj, filename):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = os.path.join(EXPORT_DIR, filename)
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"Exported {path}")


def apply_color(obj, name, rgba):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = rgba
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def compute_scene_bounds():
    xs, ys, zs = [], [], []
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ mathutils.Vector(corner)
            xs.append(world_corner.x); ys.append(world_corner.y); zs.append(world_corner.z)
    if not xs:
        return mathutils.Vector((0.0, 0.0, 0.0)), 10.0
    center = mathutils.Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2))
    size = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    return center, size


def setup_camera_and_light(center, distance, ortho_scale):
    cam_data = bpy.data.cameras.new("RenderCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = ortho_scale
    cam = bpy.data.objects.new("RenderCam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = center + mathutils.Vector((distance * 0.6, -distance, distance * 0.35))
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam

    light_data = bpy.data.lights.new("RenderLight", type='SUN')
    light_data.energy = 3.0
    light = bpy.data.objects.new("RenderLight", light_data)
    bpy.context.collection.objects.link(light)
    light.location = center + mathutils.Vector((distance * 0.3, -distance * 1.5, distance * 0.9))
    light.rotation_euler = (center - light.location).to_track_quat('-Z', 'Y').to_euler()
    return cam


def render_object(name):
    center, size = compute_scene_bounds()
    distance = size * 1.4
    setup_camera_and_light(center, distance, size * 1.2)
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = RENDER_RESOLUTION
    scene.render.filepath = os.path.join(RENDER_DIR, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {scene.render.filepath}")


# ============================================================
# TRUNK - a chain of metaball elements from base to tip (plus a few
# shorter branch chains), converted to one mesh. Metaballs blend into
# each other automatically, so trunk+branches come out as a single
# smooth organic solid with no boolean union step at all.
# ============================================================


def _path_points(height, lean, wobble, n, rng):
    """Base-to-tip point chain. Wander is a couple of low-frequency sine
    waves, NOT independent per-point jitter - IID jitter's magnitude
    (up to +-wobble, a couple mm) swamped the tight point spacing needed
    near the thin tip (down to ~0.3x the tip radius, well under a
    millimeter there), knocking neighboring metaballs too far apart to
    fuse and producing a beaded chain instead of a smooth taper. A smooth
    low-frequency wander keeps immediately-adjacent points close together
    while still bending the trunk's overall line."""
    lean_dir = math.radians(rng.uniform(0, 360))
    wx = [(rng.uniform(0.6, 1.3), rng.uniform(0, 2 * math.pi)) for _ in range(2)]
    wy = [(rng.uniform(0.6, 1.3), rng.uniform(0, 2 * math.pi)) for _ in range(2)]

    def wander(t, params):
        return sum(math.sin(f * t * math.pi * 2 + p) for f, p in params) / len(params)

    pts = []
    for i in range(n):
        t = i / (n - 1)
        lean_amount = math.sin(t * math.pi / 2) * lean
        jx = wander(t, wx) * wobble * t
        jy = wander(t, wy) * wobble * t
        pts.append(mathutils.Vector((
            lean_amount * math.cos(lean_dir) + jx,
            lean_amount * math.sin(lean_dir) + jy,
            t * height,
        )))
    return pts


def _add_ball_chain(mb_data, pts, radii):
    for p, r in zip(pts, radii):
        e = mb_data.elements.new()
        e.co = p
        e.radius = r
        e.stiffness = 2.0


def build_trunk(seed, height, base_r, tip_r, n_branches):
    rng = random.Random(seed)
    mb_data = bpy.data.metaballs.new(f"trunk_{seed}_mb")
    mb_data.resolution = 0.3
    mb_data.render_resolution = 0.3
    # default threshold (0.6) - element.radius only means "rendered ball
    # radius" at this threshold; raising it (tried 1.2 first) makes
    # neighboring balls need MORE overlap to blend, not less, which is
    # why the first pass came out as a sparse bead chain instead of a
    # solid trunk. The real fix is point spacing: it has to shrink along
    # with the taper (see n below), not stay uniform.
    mb_obj = bpy.data.objects.new(f"trunk_{seed}", mb_data)
    bpy.context.collection.objects.link(mb_obj)

    # spacing must scale with the SMALLEST radius on the chain (the tip) or
    # the thin end never gets enough ball-to-ball overlap to fuse into a
    # continuous surface. 0.75x radius spacing still left a visibly beaded
    # (non-fused) chain at the thin tip - confirmed by test render, and NOT
    # a marching-cubes resolution artifact (volume barely moved when
    # resolution was tightened 0.5->0.3mm) - the field itself wasn't
    # overlapping enough. 0.3x is what actually fused cleanly.
    n = min(160, max(20, int(height / (tip_r * 0.3)) + 1))
    pts = _path_points(height, lean=rng.uniform(2.0, 10.0), wobble=rng.uniform(0.8, 2.5), n=n, rng=rng)
    # taper eases faster near the top (power curve) rather than linear -
    # reads more like a real trunk than a uniform cone
    radii = [base_r + (tip_r - base_r) * (i / (n - 1)) ** 0.7 for i in range(n)]
    _add_ball_chain(mb_data, pts, radii)

    for _ in range(n_branches):
        i0 = rng.randint(int(n * 0.45), int(n * 0.75))
        start, r0 = pts[i0], radii[i0] * rng.uniform(0.55, 0.75)
        blen = height * rng.uniform(0.25, 0.4)
        branch_tip_r = 1.0
        bn = min(80, max(10, int(blen / (branch_tip_r * 0.3)) + 1))
        bdir = math.radians(rng.uniform(0, 360))
        up_frac = rng.uniform(0.5, 0.8)
        bpts, brs = [], []
        for j in range(bn):
            t = j / (bn - 1)
            bpts.append(start + mathutils.Vector((
                math.cos(bdir) * blen * t * (1 - up_frac),
                math.sin(bdir) * blen * t * (1 - up_frac),
                blen * t * up_frac,
            )))
            brs.append(max(r0 * (1 - t) ** 0.8, branch_tip_r))
        _add_ball_chain(mb_data, bpts, brs)

    mesh_obj = convert_to_mesh(mb_obj)
    mesh_obj.name = f"trunk_{seed}"
    recalc_normals(mesh_obj)
    flatten_bottom(mesh_obj, z_plane=0.0, span=max(base_r * 8.0, 60.0))
    recalc_normals(mesh_obj)
    return mesh_obj, pts[-1]


TRUNK_VARIANTS = [
    dict(name="sapling_straight", seed=1, height=85.0, base_r=6.5, tip_r=2.0, n_branches=0),
    dict(name="leaning_branched", seed=2, height=95.0, base_r=8.0, tip_r=2.5, n_branches=2),
    dict(name="gnarled_multibranch", seed=3, height=100.0, base_r=9.0, tip_r=2.8, n_branches=3),
]

# ============================================================
# CANOPY - "mushroom cap" foliage clump: icosphere, noise-displaced for
# a lumpy clump silhouette, flattened underside so it prints flat with
# no supports.
# ============================================================

CANOPY_STYLES = {
    "smooth_dome": dict(subdiv=5, disp_strength=3.0, noise_scale=18.0, z_scale=0.85, flatten_frac=0.15),
    "lumpy_clump": dict(subdiv=5, disp_strength=7.0, noise_scale=9.0, z_scale=0.80, flatten_frac=0.20),
    "flat_mushroom": dict(subdiv=5, disp_strength=5.0, noise_scale=13.0, z_scale=0.55, flatten_frac=0.35),
}


def build_canopy(seed, style, radius):
    cfg = CANOPY_STYLES[style]
    rng = random.Random(seed)

    bpy.ops.mesh.primitive_ico_sphere_add(radius=radius, subdivisions=cfg["subdiv"], location=(0, 0, 0))
    obj = bpy.context.active_object
    obj.name = f"canopy_{style}"
    obj.scale.z = cfg["z_scale"]
    apply_transform(obj)

    tex = bpy.data.textures.new(f"canopy_tex_{seed}", type='CLOUDS')
    tex.noise_scale = cfg["noise_scale"]
    tex.noise_basis = rng.choice(['BLENDER_ORIGINAL', 'ORIGINAL_PERLIN', 'VORONOI_F1'])

    mod = obj.modifiers.new("Displace", 'DISPLACE')
    mod.texture = tex
    mod.strength = cfg["disp_strength"]
    mod.mid_level = 0.5
    mod.texture_coords = 'GLOBAL'
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)

    half_h = radius * cfg["z_scale"]
    flat_z = -half_h + cfg["flatten_frac"] * 2.0 * half_h
    flatten_bottom(obj, z_plane=flat_z, span=radius * 4.0)
    recalc_normals(obj)
    return obj, flat_z


CANOPY_RADIUS = 42.0

# ============================================================
# ASSEMBLIES - visual-only pairing of one trunk + one canopy, to check
# proportions. No boolean join, no peg/socket yet (see module docstring)
# - canopy is just translated to rest on the trunk's top point.
# ============================================================

ASSEMBLY_PAIRS = [
    ("sapling_straight", "smooth_dome"),
    ("leaning_branched", "lumpy_clump"),
    ("gnarled_multibranch", "flat_mushroom"),
]


def build_assembly(trunk_spec, canopy_style):
    trunk, top_pt = build_trunk(trunk_spec["seed"], trunk_spec["height"], trunk_spec["base_r"],
                                 trunk_spec["tip_r"], trunk_spec["n_branches"])
    canopy, flat_z = build_canopy(hash(canopy_style) % 1000, canopy_style, CANOPY_RADIUS)
    # sit the canopy's flat underside a bit into the trunk tip so it
    # reads as joined rather than floating
    canopy.location = (top_pt.x, top_pt.y, top_pt.z - flat_z - 4.0)
    apply_transform(canopy)
    return trunk, canopy


# ============================================================
# MAIN
# ============================================================


def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    if RENDER_IMAGES:
        os.makedirs(RENDER_DIR, exist_ok=True)

    if ONLY in (None, "trunks"):
        for spec in TRUNK_VARIANTS:
            clear_scene()
            trunk, _ = build_trunk(spec["seed"], spec["height"], spec["base_r"], spec["tip_r"], spec["n_branches"])
            vol = mesh_volume(trunk)
            print(f"{spec['name']}: volume={vol:.1f}mm3")
            assert vol > 0.0, f"{spec['name']}: zero/negative volume"
            apply_color(trunk, "bark", TRUNK_COLOR)
            if RENDER_IMAGES:
                render_object(f"trunk_{spec['name']}")
            export_stl(trunk, f"trunk_{spec['name']}.stl")

    if ONLY in (None, "canopies"):
        for style in CANOPY_STYLES:
            clear_scene()
            canopy, _ = build_canopy(hash(style) % 1000, style, CANOPY_RADIUS)
            vol = mesh_volume(canopy)
            print(f"canopy_{style}: volume={vol:.1f}mm3")
            assert vol > 0.0, f"canopy_{style}: zero/negative volume"
            apply_color(canopy, "foliage", CANOPY_COLOR)
            if RENDER_IMAGES:
                render_object(f"canopy_{style}")
            export_stl(canopy, f"canopy_{style}.stl")

    if ONLY in (None, "assemblies"):
        specs_by_name = {s["name"]: s for s in TRUNK_VARIANTS}
        for trunk_name, canopy_style in ASSEMBLY_PAIRS:
            clear_scene()
            trunk, canopy = build_assembly(specs_by_name[trunk_name], canopy_style)
            apply_color(trunk, "bark", TRUNK_COLOR)
            apply_color(canopy, "foliage", CANOPY_COLOR)
            if RENDER_IMAGES:
                render_object(f"assembly_{trunk_name}__{canopy_style}")

    print("Done.")


if __name__ == "__main__":
    main()
