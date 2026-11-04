"""
Close-up render sheet for review - orthographic Workbench shots of one or more STLs around a
centre point, from named views or direction vectors, tiled into one contact sheet.

  /Applications/Blender.app/Contents/MacOS/Blender --background --python tools/render.py -- \
      --stl Body.stl --centre 1.4 10.7 42.9 --scale 14 --view front --view right --view=-0.6,0.8,0.8 \
      --out out/head.png

  --stl          one or more meshes; the first is grey, the rest get kitbash's part colours
  --centre       look-at point, mm
  --scale        ortho width of each shot, mm
  --view         repeatable; a kitbash.Camera view name (box front right left top) or a direction
                 vector "x,y,z" from the centre to the camera (--view=-1,0,0 when it starts with -)
                 default: front right left top box
  --open-edges   magenta markers on boundary edges (cuts that did not cap, non-manifold repairs)
  --cols         contact sheet columns (default 3)

Views are in the file's coordinates; the camera's up is +Z (+Y when looking straight down).
Single shots go next to the sheet as <out stem>_<n>.png.
"""
import argparse
import os
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import kitbash as kb    # noqa: E402

MARK_R = 0.08           # open-edge marker size, mm


def open_edge_markers(objs):
    """One magenta octahedron per boundary edge midpoint, over all objects."""
    pts = []
    for o in objs:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        pts += [o.matrix_world @ ((e.verts[0].co + e.verts[1].co) / 2)
                for e in bm.edges if len(e.link_faces) == 1]
        bm.free()
    print(f"OPEN EDGES {len(pts)}")
    if not pts:
        return
    axes = [Vector(v) * MARK_R for v in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
    tris = ((0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5))
    verts, faces = [], []
    for p in pts:
        b = len(verts)
        verts += [p + a for a in axes]
        faces += [(b + i, b + j, b + k) for i, j, k in tris]
    kb.mesh_object("open_edges", verts, faces, (1, 0, 1, 1))


def view_dir(v):
    if v in kb.Camera.VIEWS:
        return v
    d = tuple(float(c) for c in v.split(","))
    if len(d) != 3:
        raise SystemExit(f"view {v!r}: not a view name ({' '.join(kb.Camera.VIEWS)}) or 'x,y,z'")
    kb.Camera.VIEWS[v] = d
    return v


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="render.py")
    ap.add_argument("--stl", nargs="+", required=True)
    ap.add_argument("--centre", nargs=3, type=float, required=True)
    ap.add_argument("--scale", type=float, required=True)
    ap.add_argument("--view", action="append", dest="views")
    ap.add_argument("--open-edges", action="store_true")
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--res", type=int, default=700)
    ap.add_argument("--out", required=True, help="contact sheet PNG")
    args = ap.parse_args(argv)
    args.views = args.views or ["front", "right", "left", "top", "box"]

    bpy.ops.wm.read_factory_settings(use_empty=True)
    objs = []
    for i, path in enumerate(args.stl):
        o = kb.import_stl(os.path.expanduser(path), f"m{i}")
        kb.colour(o, (0.75, 0.75, 0.75, 1) if i == 0 else kb.COLOURS[(i - 1) % len(kb.COLOURS)])
        objs.append(o)
    if args.open_edges:
        open_edge_markers(objs)

    out = os.path.abspath(os.path.expanduser(args.out))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    stem = os.path.splitext(out)[0]
    cam = kb.Camera(args.res)
    centre = Vector(args.centre)
    files = [cam.shoot(f"{stem}_{n}.png", view_dir(v), centre, args.scale, v)
             for n, v in enumerate(args.views, 1)]
    kb.contact_sheet(files, out, args.cols)
    print(f"SHEET {out}")


main()
