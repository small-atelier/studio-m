"""
Prep - runs a recipe's [[prep]] ops in order on source parts, writes the results to parts/<name>/.

Each op works on a part by file name. The first op on a part loads it from the recipe's source
folder (never from parts/, so a rerun starts clean); later ops get the result of the earlier
ones. Every part touched or made is written at the end, with an open-edge / non-manifold count.

Ops:
  split  Cut a piece off a part without booleans. Each `cuts` plane {at, normal, reach} bisects
         only where the surface crosses it within `reach` mm of `at` - its outline must come out
         as one closed loop, or the run stops - and opens the cut. A `ball` {centre, r, tol}
         marks the faces on that sphere as a seam too: the piece takes the ball along, and
         wherever the ball met the rest is the second boundary. The piece is everything reachable
         from `seed` without crossing a cut or entering the ball, plus the ball; it is written as
         `out`. `part` keeps what is reachable from `rest_seed` the same way; anything reachable
         from neither (a member cut at both ends) is dropped. Holes close per loop: a loop on the
         ball, on the piece side, gets a fill pushed out onto the sphere (so the ball stays round
         where the rest joined it); every other loop a fan fill.
  sphere A sphere of radius r at `centre`, added to `part` as an overlapping shell (the slicer
         fuses it).
  rod    A cylinder of radius r from `start` to `end`, added the same way.
  strip  Delete a cylindrical member: the faces within radius r + tol of the line
         `point` + t*`dir`, t within `range` (end the range where the member meets the rest, or
         surface further along the line goes too), then whatever was connected to `seed` before
         and no longer is (other shells stay); the holes left where it met the rest get a fan
         fill.

Usage:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python tools/prep.py -- \
      --recipe recipes/heavy_lokhust_destroyer.toml
"""
import argparse
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import kitbash as kb    # noqa: E402

BISECT_DIST = 1e-5
FILL_REFINE = 2         # subdivide passes on a hole fill before shaping it
FILL_RELAX = 20         # smoothing iterations per pass on a fill that is not on the ball


def load(recipe, parts, filename):
    if filename not in parts:
        o = kb.import_stl(os.path.join(recipe["source"], filename), filename)
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bpy.data.objects.remove(o)
        parts[filename] = bm
    return parts[filename]


def boundary_loops(bm):
    """Open edges grouped into connected loops."""
    return edge_groups([e for e in bm.edges if len(e.link_faces) == 1])


def on_ball(v, ball):
    return abs((v.co - ball["c"]).length - ball["r"]) < ball["tol"]


def close_holes(bm, ball=None):
    """Fill every open loop with a fan; loops on the ball get the fan projected onto it."""
    fill = bm.faces.layers.int.new("fill")
    for k, loop in enumerate(boundary_loops(bm), 1):
        verts = {v for e in loop for v in e.verts}
        sphere = ball is not None and all(on_ball(v, ball) for v in verts)
        faces = bmesh.ops.holes_fill(bm, edges=loop, sides=0)["faces"]
        # A fan from a centre vertex: a triangulation between the vertices of a non-planar loop
        # can reuse an edge the surface already has between them (non-manifold), a fan only adds
        # edges to the centre.
        faces = bmesh.ops.poke(bm, faces=faces)["faces"]
        print(f"  fill {len(verts)}-vert loop ({'on ball' if sphere else 'fan'})")
        for f in faces:
            f[fill] = k
        # Refine, then shape the inside of the fill: pushed onto the ball, or relaxed (boundary
        # pinned) so a fan over a non-planar loop doesn't spike from an off-surface centre.
        for i in range(FILL_REFINE + 1):
            region = [f for f in bm.faces if f[fill] == k]
            inside = [v for v in {v for f in region for v in f.verts} if v not in verts]
            if sphere:
                for v in inside:
                    d = v.co - ball["c"]
                    v.co = ball["c"] + d.normalized() * ball["r"]
            else:
                for _ in range(FILL_RELAX):
                    bmesh.ops.smooth_vert(bm, verts=inside, factor=0.5,
                                          use_axis_x=True, use_axis_y=True, use_axis_z=True)
            if i == FILL_REFINE:
                break
            inner = list({e for f in region for e in f.edges if all(g[fill] == k for g in e.link_faces)})
            bmesh.ops.subdivide_edges(bm, edges=inner, cuts=1, use_grid_fill=True)
            bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if f[fill] == k and len(f.verts) > 3])
    bm.faces.layers.int.remove(fill)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def cut_local(bm, c):
    """Bisect the surface within reach of c.at with its plane, check the outline closes, open it."""
    at, n, reach = Vector(c["at"]), Vector(c["normal"]).normalized(), c["reach"]
    faces = set()
    for e in bm.edges:                          # edges crossing the plane within reach of at
        a, b = ((v.co - at).dot(n) for v in e.verts)
        if a * b < 0:
            x = e.verts[0].co.lerp(e.verts[1].co, a / (a - b))
            if (x - at).length < reach:
                faces.update(e.link_faces)
    faces = list(faces)
    verts = list({v for f in faces for v in f.verts})
    edges = list({e for f in faces for e in f.edges})
    res = bmesh.ops.bisect_plane(bm, geom=verts + edges + faces, dist=BISECT_DIST, plane_co=at, plane_no=n)
    cut = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
    deg = {}
    for e in cut:
        for v in e.verts:
            deg[v] = deg.get(v, 0) + 1
    ends = [v for v, d in deg.items() if d != 2]
    if not cut or ends:
        raise SystemExit(f"cut '{c['name']}': outline does not close within reach {reach} "
                         f"({len(cut)} edges, loose ends at "
                         f"{[(tuple(round(x, 3) for x in v.co), deg[v]) for v in ends]})")
    loops = len(edge_groups(cut))
    if loops != 1:
        raise SystemExit(f"cut '{c['name']}': {loops} outlines within reach {reach} - it cuts more than one "
                         f"member, move it or shrink reach")
    bmesh.ops.split_edges(bm, edges=cut)
    print(f"  cut '{c['name']}': {len(cut)}-edge outline")


def edge_groups(edges):
    """Edges grouped into vertex-connected groups."""
    left, groups = set(edges), []
    while left:
        stack, group = [left.pop()], []
        while stack:
            e = stack.pop()
            group.append(e)
            for v in e.verts:
                for e2 in v.link_edges:
                    if e2 in left:
                        left.remove(e2)
                        stack.append(e2)
        groups.append(group)
    return groups


def flood(bm, seed, blocked):
    """Indices of the faces reachable from the face nearest seed without entering a blocked face."""
    start = min((f for f in bm.faces if not blocked[f.index]), key=lambda f: (f.calc_center_median() - seed).length)
    reached, stack = {start.index}, [start]
    while stack:
        f = stack.pop()
        for e in f.edges:
            for f2 in e.link_faces:
                if f2.index not in reached and not blocked[f2.index]:
                    reached.add(f2.index)
                    stack.append(f2)
    return reached


def op_split(recipe, parts, p):
    bm = load(recipe, parts, p["part"])
    ball = {"c": Vector(p["ball"]["centre"]), "r": p["ball"]["r"], "tol": p["ball"]["tol"]}
    for c in p["cuts"]:
        cut_local(bm, c)
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    is_ball = [all(on_ball(v, ball) for v in f.verts) for f in bm.faces]
    piece = flood(bm, Vector(p["seed"]), is_ball) | {i for i, b in enumerate(is_ball) if b}
    rest = flood(bm, Vector(p["rest_seed"]), is_ball)
    if rest & piece:
        raise SystemExit("split: piece and rest are still connected - a cut is missing")
    dropped = len(bm.faces) - len(piece) - len(rest)
    print(f"  piece {len(piece)}, rest {len(rest)}, dropped {dropped} of {len(bm.faces)} faces "
          f"({sum(is_ball)} on the ball)")
    out = bm.copy()
    out.faces.ensure_lookup_table()
    out.faces.index_update()
    bmesh.ops.delete(out, geom=[f for f in out.faces if f.index not in piece], context='FACES')
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in rest], context='FACES')
    print(f"  {p['out']}:")
    close_holes(out, ball)
    print(f"  {p['part']}:")
    close_holes(bm)
    parts[p["out"]] = out


def op_sphere(recipe, parts, p):
    bm = load(recipe, parts, p["part"])
    bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=32, radius=p["r"],
                              matrix=Matrix.Translation(Vector(p["centre"])))
    print(f"  sphere r{p['r']} at {p['centre']}")


def op_rod(recipe, parts, p):
    bm = load(recipe, parts, p["part"])
    a, b = Vector(p["start"]), Vector(p["end"])
    axis = b - a
    m = Matrix.Translation((a + b) / 2) @ axis.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=48, radius1=p["r"], radius2=p["r"],
                          depth=axis.length, matrix=m)
    print(f"  rod '{p['name']}' r{p['r']} x {axis.length:.2f}mm")


def op_strip(recipe, parts, p):
    """Delete a cylindrical member, close where it met the rest."""
    bm = load(recipe, parts, p["part"])
    a, d = Vector(p["point"]), Vector(p["dir"]).normalized()
    lo, hi = p["range"]

    def in_cyl(v):
        t = (v.co - a).dot(d)
        return lo <= t <= hi and (v.co - a - d * t).length < p["r"] + p["tol"]
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    seed = Vector(p["seed"])
    main = {bm.faces[i] for i in flood(bm, seed, [False] * len(bm.faces))}   # other shells stay
    gone = [f for f in bm.faces if all(in_cyl(v) for v in f.verts)]
    bmesh.ops.delete(bm, geom=gone, context='FACES')
    slivers = 0
    while True:                                 # faces left hanging on the edge of the hole
        ears = [f for f in bm.faces if sum(len(e.link_faces) == 1 for e in f.edges) >= 2]
        if not ears:
            break
        slivers += len(ears)
        bmesh.ops.delete(bm, geom=ears, context='FACES')
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    keep = flood(bm, seed, [False] * len(bm.faces))
    loose = [f for f in bm.faces if f in main and f.index not in keep]
    bmesh.ops.delete(bm, geom=loose, context='FACES')
    print(f"  strip '{p['name']}': {len(gone)} faces in the cylinder, {slivers} slivers, {len(loose)} loose "
          f"faces removed")
    close_holes(bm)


OPS = {"split": op_split, "sphere": op_sphere, "rod": op_rod, "strip": op_strip}


def report(name, bm):
    open_e = sum(len(e.link_faces) == 1 for e in bm.edges)
    nm = sum(len(e.link_faces) > 2 for e in bm.edges)
    lo = [min(v.co[i] for v in bm.verts) for i in range(3)]
    hi = [max(v.co[i] for v in bm.verts) for i in range(3)]
    print(f"OUT {name}: {len(bm.faces)} faces, open edges {open_e}, non-manifold {nm}, "
          f"bbox {[round(x, 2) for x in lo]} .. {[round(x, 2) for x in hi]}")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", required=True)
    args = ap.parse_args(argv)
    recipe = kb.load_recipe(args.recipe)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    parts = {}
    for p in recipe.get("prep", []):
        print(f"PREP {p['op']} {p['part']}")
        OPS[p["op"]](recipe, parts, p)
    out_dir = kb.data_dir(recipe, "parts")
    os.makedirs(out_dir, exist_ok=True)
    for name, bm in parts.items():
        report(name, bm)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        o = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(o)
        kb.export_stl([o], os.path.join(out_dir, name))


if __name__ == "__main__":
    main()
