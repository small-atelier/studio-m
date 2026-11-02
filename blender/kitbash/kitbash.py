"""
Kitbash assembler - snaps ball/cup-jointed parts onto a body from a TOML recipe, poses them,
reports part-to-part clashes, exports joined STLs and review renders.

Each recipe part gives its joint centre in its own file's coordinates (part_joint) and the
matching centre on the body (body_joint); the part is translated so the two coincide, plus an
optional rest offset (body-frame mm) where the fitted centre needs correcting by eye, and an
optional rest_rot {pitch, yaw, roll} where the exported orientation is off. Parts are
exported together as overlapping shells (no boolean) - the slicer fuses them.

Joint fill: a ball smaller than its cup, snapped centre to centre, leaves a gap and prints as a
loose part. fill_r = <mm> on a part adds a sphere of that radius at the joint centre, exported
with the model; make it bigger than joint_r so it runs into both the cup wall and the ball, and
check it in a close-up render - on an exposed joint it shows. A sphere at the pivot is the same
in every pose.

Posing: each part's rot = {pitch, yaw, roll} is a +- range in degrees about its joint centre,
body-frame axes (pitch about X, roll about Y, yaw about Z). The [pose] block sets count and
seed; variants are Latin-hypercube sampled over every angle so they spread out, and a variant
that clashes is redrawn uniformly at random (max_tries).

Data: the recipe's `data` folder (default: this folder) holds parts/<name>/, input/<name>/ and
out/<name>/ - meshes and results stay outside the code.

Prepped parts: a file with the same name in parts/<name>/ (the body with its glyph niches cut,
the grafted gun) is used instead of the source file. Glyphs: with a [glyphs] recipe section, each
variant gets a seeded set of line-glyph solids per carapace-plate niche (band.py), seeded from the
pose seed and the variant number, exported with the model.

Input parts: a cleaned-up part (slicer repair) in input/<name>/, named in the recipe's [input]
table (part name -> file, "body" for the body; the recipe file name when not listed), is used
instead of both. Slicers move parts onto the bed, so it is moved back onto the bounding-box centre
of the part it replaces (parts/ or source); a size mismatch over INPUT_TOL (rotated, or a
different part) stops the run.

Clash check: BVH triangle overlap between every pair of objects. Overlaps within a joint's
exempt radius are the joint itself (expected); remaining overlaps are clustered, and clusters of
fewer than clash_min_pairs triangle pairs count as incidental contact. The exempt radius is
joint_r + JOINT_MARGIN, or fill_r where the fill is bigger. joint_margin = <mm> on a part
sets it to joint_r + joint_margin instead, for a part pushed into its socket whose contact around
the socket has been inspected - it also hides real clashes within that radius.

Usage:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python kitbash.py -- --recipe recipes/lokhust.toml
  /Applications/Blender.app/Contents/MacOS/Blender --background --python kitbash.py -- --recipe recipes/lokhust.toml --pose --preview
  /Applications/Blender.app/Contents/MacOS/Blender --background --python kitbash.py -- --recipe recipes/lokhust.toml --pose
"""
import argparse
import math
import os
import random
import sys
import tomllib

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import band                                     # noqa: E402
JOINT_MARGIN = 0.6      # mm beyond joint_r still counted as joint contact
INPUT_TOL = 0.05        # mm an input/ part may differ in size from the part it replaces
DEBRIS_VERTS = 50       # shells smaller than this are stray fragments (a slicer repair drops them)
CLUSTER_MM = 1.5        # clash points closer than this are reported as one cluster
AXES = ("pitch", "yaw", "roll")
COLOURS = [(0.9, 0.2, 0.2, 1), (0.2, 0.4, 0.9, 1), (0.9, 0.8, 0.2, 1), (0.6, 0.3, 0.8, 1)]


def load_recipe(path):
    with open(path, "rb") as f:
        r = tomllib.load(f)
    r["source"] = os.path.expanduser(r["source"])
    r["data"] = os.path.expanduser(r.get("data", HERE))
    return r


def data_dir(recipe, kind):
    """<data>/<kind>/<name>: kind = parts (prepped), input (cleaned-up drop-ins) or out (results)."""
    return os.path.join(recipe["data"], kind, recipe["name"])


def import_stl(path, name):
    bpy.ops.wm.stl_import(filepath=path)
    o = bpy.context.selected_objects[0]
    o.name = name
    return o


def source_path(recipe, filename):
    """The prepped version in parts/<name>/ when there is one, else the source file."""
    prepped = os.path.join(data_dir(recipe, "parts"), filename)
    return prepped if os.path.exists(prepped) else os.path.join(recipe["source"], filename)


def bbox(o):
    """Bounding box over the shells of at least DEBRIS_VERTS vertices (stray fragments ignored)."""
    me = o.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    ev = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get("vertices", ev)
    parent = np.arange(len(co))                 # union-find over the edges

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, j in ev.reshape(-1, 2):
        ri, rj = root(i), root(j)
        if ri != rj:
            parent[ri] = rj
    roots = np.array([root(i) for i in range(len(co))])
    keep = np.bincount(roots, minlength=len(co))[roots] >= DEBRIS_VERTS
    pts = co[keep] if keep.any() else co
    return pts.min(0), pts.max(0)


def load_part(recipe, filename, name):
    """The input/<name>/ version (file named in the recipe's [input] table under the part name, or
    "body") moved back onto the part it replaces, else source_path's file."""
    ref_path = source_path(recipe, filename)
    inp = os.path.join(data_dir(recipe, "input"), recipe.get("input", {}).get(name, filename))
    if not os.path.exists(inp):
        return import_stl(ref_path, name)
    o = import_stl(inp, name)
    ref = import_stl(ref_path, "ref")
    (lo, hi), (rlo, rhi) = bbox(o), bbox(ref)
    bpy.data.objects.remove(ref)
    size_err = np.abs((hi - lo) - (rhi - rlo)).max()
    if size_err > INPUT_TOL:
        raise SystemExit(f"{inp}: size {np.round(hi - lo, 3)} vs {np.round(rhi - rlo, 3)} of {ref_path} "
                         f"(off {size_err:.3f}mm) - rotated, or not the same part")
    shift = (rlo + rhi) / 2 - (lo + hi) / 2
    o.data.transform(Matrix.Translation(Vector(shift)))
    o.data.update()
    print(f"INPUT {filename}: {inp} moved back by {np.round(shift, 3)} (size off {size_err:.3f}mm)")
    return o


def mesh_object(name, verts, faces, rgba):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    colour(o, rgba)
    return o


class Glyphs:
    """Per-variant glyph solids on the cut body's niches (needs parts/<name>/band.json)."""

    def __init__(self, recipe, body):
        self.cfg = recipe["glyphs"]
        path = os.path.join(data_dir(recipe, "parts"), "band.json")
        if not os.path.exists(path):
            raise SystemExit(f"{path} missing - cut the niches first: tools/glyph_proof.py")
        self.band = band.load(path)
        self.tree = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
        self.seed = recipe.get("pose", {}).get("seed", 0)
        self.objs = []

    def make(self, variant):
        self.clear()
        rng = random.Random(f"{self.seed}-{variant}")
        kinds = {}
        for side in band.SIDES:
            verts, faces, kinds[side] = band.place_glyphs(self.tree, self.band, side, self.cfg, rng)
            self.objs.append(mesh_object(f"glyphs{side:+d}", verts, faces, (0.85, 0.7, 0.35, 1)))
        return kinds

    def clear(self):
        for o in self.objs:
            bpy.data.objects.remove(o)
        self.objs = []


def colour(o, rgba):
    m = bpy.data.materials.new(o.name)
    m.diffuse_color = rgba
    o.data.materials.append(m)


class CollisionMesh:
    """Triangle soup of an object in its local space, re-treed under any world matrix."""

    def __init__(self, obj):
        me = obj.data
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        self.co = co.reshape(-1, 3).astype(np.float64)
        me.calc_loop_triangles()
        tris = np.empty(len(me.loop_triangles) * 3, np.int32)
        me.loop_triangles.foreach_get("vertices", tris)
        self.tris = tris.reshape(-1, 3)
        self.cent = self.co[self.tris].mean(1)
        self.tri_list = self.tris.tolist()

    def tree(self, M):
        R, t = np.array(M.to_3x3()), np.array(M.translation)
        return (BVHTree.FromPolygons((self.co @ R.T + t).tolist(), self.tri_list),
                self.cent @ R.T + t)


def cluster(points):
    groups = []
    for p in points:
        for g in groups:
            if np.linalg.norm(g["c"] - p) < CLUSTER_MM:
                g["pts"].append(p)
                g["c"] = np.mean(g["pts"], axis=0)
                break
        else:
            groups.append({"c": p.copy(), "pts": [p]})
    return groups


def check_clashes(trees, joints, min_pairs):
    """trees: {name: (BVHTree, centroids)}; joints: [(centre, exempt radius)].
    Returns [(a, b, clusters)] where clusters have >= min_pairs triangle pairs."""
    names = list(trees)
    jc = np.array([c for c, _ in joints])
    jr = np.array([r for _, r in joints])
    report = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            (ta, ca), (tb, cb) = trees[a], trees[b]
            pairs = ta.overlap(tb)
            if not pairs:
                report.append((a, b, []))
                continue
            ij = np.array(pairs)
            p = (ca[ij[:, 0]] + cb[ij[:, 1]]) / 2
            near_joint = (np.linalg.norm(p[:, None, :] - jc[None], axis=2) < jr).any(1)
            groups = [g for g in cluster(p[~near_joint]) if len(g["pts"]) >= min_pairs]
            report.append((a, b, groups))
    return report


class Camera:
    VIEWS = {"box": (-0.9, -1, 0.45), "front": (0, -1, 0), "right": (-1, 0, 0),
             "left": (1, 0, 0), "top": (0, 0, 1)}

    def __init__(self, res):
        sc = bpy.context.scene
        sc.render.engine = 'BLENDER_WORKBENCH'
        sc.display.shading.color_type = 'MATERIAL'
        sc.render.resolution_x = sc.render.resolution_y = res
        self.cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
        sc.collection.objects.link(self.cam)
        sc.camera = self.cam
        self.cam.data.type = 'ORTHO'
        bpy.ops.object.text_add()
        self.label = bpy.context.object
        colour(self.label, (1, 1, 1, 1))
        self.label.parent = self.cam

    def shoot(self, path, view, centre, scale, label=""):
        d = Vector(self.VIEWS[view]).normalized()
        up = Vector((0, 1, 0)) if view == "top" else Vector((0, 0, 1))
        x = up.cross(d).normalized()
        self.cam.matrix_world = (Matrix.Translation(centre + d * 200)
                                 @ Matrix((x, d.cross(x), d)).transposed().to_4x4())
        self.cam.data.ortho_scale = scale
        self.label.data.body = label
        self.label.scale = (scale * 0.06,) * 3
        self.label.location = (-scale * 0.47, scale * 0.42, -10)
        bpy.context.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        return path


def contact_sheet(files, path, cols):
    imgs = [bpy.data.images.load(f) for f in files]
    w, h = imgs[0].size
    rows = (len(imgs) + cols - 1) // cols
    sheet = np.zeros((rows * h, cols * w, 4), np.float32)
    sheet[..., 3] = 1
    for i, im in enumerate(imgs):
        px = np.empty(w * h * 4, np.float32)
        im.pixels.foreach_get(px)
        px = px.reshape(h, w, 4)
        px[..., :3] = px[..., :3] * px[..., 3:] + (1 - px[..., 3:])     # onto white
        r = rows - 1 - i // cols            # image rows start at the bottom
        c = i % cols
        sheet[r * h:(r + 1) * h, c * w:(c + 1) * w, :3] = px[..., :3]
    out = bpy.data.images.new("sheet", cols * w, rows * h)
    out.pixels.foreach_set(sheet.ravel())
    out.filepath_raw = path
    out.file_format = 'PNG'
    out.save()


def export_stl(objs, path):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, apply_modifiers=True)


def rotation(angles):
    """Body-frame rotation from {pitch, yaw, roll} degrees: yaw, then pitch, then roll."""
    a = {k: math.radians(angles.get(k, 0.0)) for k in AXES}
    return (Matrix.Rotation(a["yaw"], 4, 'Z') @ Matrix.Rotation(a["pitch"], 4, 'X')
            @ Matrix.Rotation(a["roll"], 4, 'Y'))


def latin_hypercube(n, dims, rng):
    """n samples in [-1, 1]^dims, one per stratum along every dimension."""
    cols = []
    for _ in range(dims):
        strata = list(range(n))
        rng.shuffle(strata)
        cols.append([(s + rng.random()) / n * 2 - 1 for s in strata])
    return [list(row) for row in zip(*cols)]


def build_scene(recipe):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    body = load_part(recipe, recipe["body"], "body")
    colour(body, (0.75, 0.75, 0.75, 1))
    parts, joints = [], []
    for i, p in enumerate(recipe["part"]):
        o = load_part(recipe, p["file"], p["name"])
        colour(o, COLOURS[i % len(COLOURS)])
        centre = Vector(p["body_joint"]) + Vector(p.get("offset", (0, 0, 0)))
        snap = Matrix.Translation(centre - Vector(p["part_joint"]))
        c = Matrix.Translation(centre)
        snap = c @ rotation(p.get("rest_rot", {})) @ c.inverted() @ snap
        fill, fill_r = None, p.get("fill_r", 0.0)
        if fill_r:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=fill_r, location=centre,
                                                 segments=64, ring_count=32)
            fill = bpy.context.object
            fill.name = f"{p['name']}_fill"
            colour(fill, COLOURS[i % len(COLOURS)])
        parts.append({"name": p["name"], "obj": o, "centre": centre, "snap": snap,
                      "rot": p.get("rot", {}), "fill": fill})
        if "joint_margin" in p:
            exempt = p["joint_r"] + p["joint_margin"]
        else:
            exempt = max(fill_r, p["joint_r"] + JOINT_MARGIN)
        joints.append((np.array(centre), exempt))
    return body, parts, joints


def place(parts, angles):
    """angles: {part name: {pitch, yaw, roll}}; rotates each part about its joint centre."""
    for p in parts:
        c = Matrix.Translation(p["centre"])
        p["obj"].matrix_world = c @ rotation(angles.get(p["name"], {})) @ c.inverted() @ p["snap"]


def bounds(objs):
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def fmt_angles(angles):
    return "  ".join(f"{n}:" + "/".join(f"{angles[n].get(k, 0):+5.1f}" for k in AXES) for n in angles)


def run_baseline(recipe, out_dir):
    body, parts, joints = build_scene(recipe)
    place(parts, {})
    min_pairs = recipe.get("pose", {}).get("clash_min_pairs", 1)
    meshes = {"body": CollisionMesh(body), **{p["name"]: CollisionMesh(p["obj"]) for p in parts}}
    trees = {"body": meshes["body"].tree(body.matrix_world),
             **{p["name"]: meshes[p["name"]].tree(p["obj"].matrix_world) for p in parts}}
    clash_pts = []
    for a, b, groups in check_clashes(trees, joints, min_pairs):
        print(f"CLASH {a:>8s} x {b:<8s} " + ("ok" if not groups else f"{len(groups)} clash cluster(s)"))
        for g in groups:
            c = g["c"]
            print(f"        at ({c[0]:6.2f},{c[1]:6.2f},{c[2]:6.2f})  {len(g['pts'])} tri pairs")
            clash_pts.append(Vector(c))

    objs = [body] + [p["obj"] for p in parts] + [p["fill"] for p in parts if p["fill"]]
    if "glyphs" in recipe:
        glyphs = Glyphs(recipe, body)
        print(f"GLYPHS {glyphs.make(0)}")
        objs += glyphs.objs
    lo, hi = bounds(objs)
    size = hi - lo
    print(f"SIZE {size.x:.1f} x {size.y:.1f} x {size.z:.1f} mm")

    markers = []
    for c in clash_pts:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.6, location=c)
        colour(bpy.context.object, (1, 0, 1, 1))
        markers.append(bpy.context.object)
    cam = Camera(800)
    files = [cam.shoot(os.path.join(out_dir, f"baseline_{v}.png"), v, (lo + hi) / 2, max(size) * 1.15)
             for v in Camera.VIEWS]
    contact_sheet(files, os.path.join(out_dir, "baseline_sheet.png"), len(files))
    for m in markers:
        bpy.data.objects.remove(m)

    stl = os.path.join(out_dir, f"{recipe['name']}_baseline.stl")
    export_stl(objs, stl)
    print(f"EXPORT {stl}")


def run_pose(recipe, out_dir, preview):
    cfg = recipe["pose"]
    n, min_pairs, max_tries = cfg["count"], cfg["clash_min_pairs"], cfg["max_tries"]
    rng = random.Random(cfg["seed"])
    body, parts, joints = build_scene(recipe)
    dims = [(p["name"], k, p["rot"][k]) for p in parts for k in AXES if p["rot"].get(k)]

    def to_angles(u):
        angles = {p["name"]: {} for p in parts}
        for (name, k, rng_deg), x in zip(dims, u):
            angles[name][k] = round(x * rng_deg, 1)
        return angles

    meshes = {p["name"]: CollisionMesh(p["obj"]) for p in parts}
    body_tree = CollisionMesh(body).tree(body.matrix_world)

    def clashes(angles):
        place(parts, angles)
        trees = {"body": body_tree,
                 **{p["name"]: meshes[p["name"]].tree(p["obj"].matrix_world) for p in parts}}
        return [(a, b, len(g)) for a, b, g in check_clashes(trees, joints, min_pairs) if g]

    poses, log = [], []
    for i, u in enumerate(latin_hypercube(n, len(dims), rng), 1):
        angles = to_angles(u)
        for attempt in range(max_tries):
            hits = clashes(angles)
            if not hits:
                break
            angles = to_angles([rng.uniform(-1, 1) for _ in dims])
        else:
            raise SystemExit(f"variant {i:02d}: still clashing after {max_tries} tries: {hits}")
        line = f"{recipe['name']}_{i:02d}  redraws={attempt}  {fmt_angles(angles)}"
        print("POSE", line)
        log.append(line)
        poses.append(angles)

    glyphs = Glyphs(recipe, body) if "glyphs" in recipe else None
    objs = [body] + [p["obj"] for p in parts] + [p["fill"] for p in parts if p["fill"]]
    place(parts, {})
    lo, hi = bounds(objs)
    centre, scale = (lo + hi) / 2, max(hi - lo) * 1.05
    cam = Camera(400)
    files = []
    for i, angles in enumerate(poses, 1):
        place(parts, angles)
        if glyphs:
            kinds = glyphs.make(i)
            log[i - 1] += "  glyphs L:" + ",".join(kinds[1]) + " R:" + ",".join(kinds[-1])
        for view in ("box", "right"):
            files.append(cam.shoot(os.path.join(out_dir, f"pose_{i:02d}_{view}.png"), view, centre, scale,
                                   f"{i:02d}" if view == "box" else ""))
        if not preview:
            stl = os.path.join(out_dir, f"{recipe['name']}_{i:02d}.stl")
            export_stl(objs + (glyphs.objs if glyphs else []), stl)
            print(f"EXPORT {stl}")
    with open(os.path.join(out_dir, "poses.txt"), "w") as f:
        f.write(f"# seed={cfg['seed']}  angles per part as pitch/yaw/roll degrees\n" + "\n".join(log) + "\n")
    contact_sheet(files, os.path.join(out_dir, "pose_sheet.png"), 6)     # 3 variants per row, box + side each
    print(f"SHEET {os.path.join(out_dir, 'pose_sheet.png')}")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", required=True)
    ap.add_argument("--pose", action="store_true", help="generate the [pose] variants instead of the baseline")
    ap.add_argument("--preview", action="store_true", help="with --pose: contact sheet + poses.txt only, no STLs")
    args = ap.parse_args(argv)

    recipe = load_recipe(args.recipe if os.path.isabs(args.recipe) else os.path.join(HERE, args.recipe))
    out_dir = data_dir(recipe, "out")
    os.makedirs(out_dir, exist_ok=True)
    if args.pose:
        run_pose(recipe, out_dir, args.preview)
    else:
        run_baseline(recipe, out_dir)


if __name__ == "__main__":
    main()
