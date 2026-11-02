"""
Vent proof - thickens the hollow vent boxes of the prepped body (parts/<name>/<body file>) from
the inside and puts a criss-cross grate on each back wall. Settings come from the recipe's
[vents] section. Runs after tools/glyph_proof.py, which writes the prepped body from the source.

Per box: the opening plane is the biggest outward face of the box's convex hull. Inner faces are
the box faces facing a point 2mm inside the opening and visible from it; they group into walls by
normal, the one facing the opening is the back. Every inner face moves along its normal into the
box (wall or back mm) with even thickness - each vertex moves so that all its inner faces shift by
their full amount, and vertices on the rim stay in the rim plane. The outside is untouched. Steps
narrower than the offset fold over; the slicer's repair resolves those. Grate bars (+-45 deg) are
clipped to the outline of the moved back wall faces and exported as separate shells.

Idempotent: the first run saves the niche body as <body>_pre_vents.stl and works from that copy;
when glyph_proof has written a newer body since (newer than vents.json), that body is used.

  /Applications/Blender.app/Contents/MacOS/Blender --background --python tools/vent_proof.py
"""
import json
import math
import os
import shutil
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import kitbash                                  # noqa: E402

INSIDE = 2.0            # mm inside the opening for the visibility point
MIN_WALL_AREA = 1.0     # wall groups smaller than this (mm2) are slivers, left alone
GRATE_CLEAR = 0.05      # grate outline pulled in from the back wall's edge


def in_box(c, side, band, cfg):
    xr = side * (c[0] - cfg["midline"])
    return (cfg["out"][0] < xr < cfg["out"][1] and band[0] < c[1] < band[1]
            and cfg["z"][0] < c[2] < cfg["z"][1])


def opening(bm, side, band, cfg):
    """(normal, offset, centre) of the box opening: the biggest outward convex-hull face group."""
    pts = [v.co.copy() for v in bm.verts if in_box(v.co, side, band, cfg)]
    hb = bmesh.new()
    for p in pts:
        hb.verts.new(p)
    bmesh.ops.convex_hull(hb, input=hb.verts)
    hb.normal_update()
    centroid = np.mean([np.array(v.co) for v in hb.verts], axis=0)
    faces = []
    for f in hb.faces:
        n = np.array(f.normal)
        c = np.array(f.calc_center_median())
        if n @ (c - centroid) < 0:
            n = -n
        faces.append((n, n @ c, f.calc_area(), [np.array(v.co) for v in f.verts]))
    best = None
    for n, o, _, _ in faces:
        if n[0] * side <= 0.5:
            continue
        group = [g for g in faces if g[0] @ n > 0.995 and abs(g[1] - o) < 0.05]
        area = sum(g[2] for g in group)
        if best is None or area > best[0]:
            best = (area, n, o, group)
    hb.free()
    _, n, o, group = best
    corners = np.unique(np.round([p for g in group for p in g[3]], 4), axis=0)
    return n, o, corners.mean(0)


def clip(poly, a, b):
    """Sutherland-Hodgman: the part of 2D polygon poly with a . p <= b."""
    out = []
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        dp, dq = a @ p - b, a @ q - b
        if dp <= 0:
            out.append(p)
        if (dp <= 0) != (dq <= 0):
            out.append(p + (q - p) * (dp / (dp - dq)))
    return out


def hull2d(p):
    """Convex hull of 2D points, counter-clockwise (monotone chain)."""
    p = sorted(map(tuple, np.round(p, 6)))
    def half(pts):
        h = []
        for q in pts:
            while len(h) >= 2 and np.cross(np.subtract(h[-1], h[-2]), np.subtract(q, h[-2])) <= 0:
                h.pop()
            h.append(q)
        return h
    lo, hi = half(p), half(p[::-1])
    return [np.array(q) for q in lo[:-1] + hi[:-1]]


def grate(o, bn, back_pts, cfg):
    """Bar triangles on the back plane (point o, normal bn into the box), inside the outline of the
    moved back wall faces (back_pts), pulled in by GRATE_CLEAR."""
    u = np.cross(bn, [0, 1, 0])
    u /= np.linalg.norm(u)
    w = np.cross(bn, u)
    face = hull2d((np.array(back_pts) - o) @ np.c_[u, w])
    centre = np.mean(face, axis=0)
    face = [centre + (p - centre) * (1 - GRATE_CLEAR / np.linalg.norm(p - centre)) for p in face]
    tris = []
    for th in (math.pi / 4, -math.pi / 4):
        d = np.array([math.cos(th), math.sin(th)])
        e = np.array([-d[1], d[0]])
        for k in np.arange(-8, 8 + 1e-9, cfg["bar_pitch"]):
            bar = [k * e + s * d + t * e for s, t in
                   ((-8, -cfg["bar_w"] / 2), (8, -cfg["bar_w"] / 2), (8, cfg["bar_w"] / 2), (-8, cfg["bar_w"] / 2))]
            for i in range(len(face)):
                p, q = face[i], face[(i + 1) % len(face)]
                a = np.array([q[1] - p[1], -(q[0] - p[0])])
                if a @ (centre - p) > 0:
                    a = -a
                bar = clip(bar, a, a @ p)
                if len(bar) < 3:
                    break
            if len(bar) < 3:
                continue
            lo = [o + p[0] * u + p[1] * w - cfg["bar_sink"] * bn for p in bar]
            hi = [o + p[0] * u + p[1] * w + cfg["bar_h"] * bn for p in bar]
            for i in range(1, len(bar) - 1):
                tris += [[lo[0], lo[i + 1], lo[i]], [hi[0], hi[i], hi[i + 1]]]
            for i in range(len(bar)):
                j = (i + 1) % len(bar)
                tris += [[lo[i], lo[j], hi[j]], [lo[i], hi[j], hi[i]]]
    return tris, face


def thicken_box(bm, side, band, cfg):
    n_o, o_o, oc = opening(bm, side, band, cfg)
    C = oc - INSIDE * n_o
    tree = BVHTree.FromBMesh(bm)
    inner = []
    for f in bm.faces:
        c = np.array(f.calc_center_median())
        if not in_box(c, side, band, cfg):
            continue
        to_c = C - c
        if np.array(f.normal) @ to_c <= 0:
            continue
        d = np.linalg.norm(to_c)
        if tree.ray_cast(Vector(C), Vector(-to_c / d), d + 0.01)[2] == f.index:
            inner.append(f)
    groups = []
    for f in sorted(inner, key=lambda f: -f.calc_area()):
        nf = np.array(f.normal)
        for g in groups:
            if g[0] @ nf > 0.9:
                g[1].append(f)
                break
        else:
            groups.append([nf, [f]])
    walls = []
    for _, fs in groups:
        a = np.array([f.calc_area() for f in fs])
        if a.sum() < MIN_WALL_AREA:
            continue
        nn = (np.array([f.normal for f in fs]) * a[:, None]).sum(0)
        nn /= np.linalg.norm(nn)
        walls.append(["back" if nn @ n_o > 0.7 else "wall", fs])
    target = {f.index: cfg["back"] if kind == "back" else cfg["wall"] for kind, fs in walls for f in fs}
    before = {fi: np.array(bm.faces[fi].normal) for fi in target}
    disp = {}
    for fi in target:
        for v in bm.faces[fi].verts:
            if v.index in disp:
                continue
            cons = []
            for lf in v.link_faces:
                nf = np.array(lf.normal)
                if lf.index in target:
                    t = target[lf.index]
                elif nf @ n_o > 0.9:
                    t = 0.0                     # rim face: stay in the rim plane
                else:
                    continue
                if all(abs(nf @ c[0]) < 0.999 for c in cons):
                    cons.append((nf, t))
            A = np.array([c[0] for c in cons])
            t = np.array([c[1] for c in cons])
            U, S, Vt = np.linalg.svd(A, full_matrices=False)
            k = S > 0.05
            disp[v.index] = Vt[k].T @ ((U[:, k].T @ t) / S[k])
    for vi, d in disp.items():
        bm.verts[vi].co = Vector(np.array(bm.verts[vi].co) + d)
    bm.normal_update()
    folded = sum(1 for fi in target if np.array(bm.faces[fi].normal) @ before[fi] < 0.5)
    planes = []
    for kind, fs in walls:
        a = np.array([f.calc_area() for f in fs])
        nn = (np.array([f.normal for f in fs]) * a[:, None]).sum(0)
        nn /= np.linalg.norm(nn)
        planes.append((kind, nn, float(np.median([np.array(f.calc_center_median()) @ nn for f in fs]))))
    _, bn, bo = next(p for p in planes if p[0] == "back")
    o = oc - (oc @ bn - bo) * bn
    back_pts = [np.array(v.co) for kind, fs in walls if kind == "back" for f in fs for v in f.verts]
    tris, face = grate(o, bn, back_pts, cfg)
    depth = o_o - o @ n_o
    print(f"VENT {side:+d} y {band[0]:5.1f}..{band[1]:5.1f}: {len(inner)} inner faces, {len(walls) - 1} walls + back, "
          f"{len(disp)} verts moved (max {max(np.linalg.norm(d) for d in disp.values()):.2f}mm), {folded} folded; "
          f"grate {np.ptp([p[0] for p in face]):.1f} x {np.ptp([p[1] for p in face]):.1f}mm at {depth:.2f}mm deep")
    return tris


def main():
    recipe = kitbash.load_recipe(os.path.join(ROOT, "recipes", "lokhust.toml"))
    cfg = recipe["vents"]
    parts_dir = kitbash.data_dir(recipe, "parts")
    body_stl = os.path.join(parts_dir, recipe["body"])
    stem, ext = os.path.splitext(body_stl)
    pre = f"{stem}_pre_vents{ext}"
    marker = os.path.join(parts_dir, "vents.json")
    if not os.path.exists(pre) or (os.path.exists(marker) and os.path.getmtime(body_stl) > os.path.getmtime(marker)):
        shutil.copy2(body_stl, pre)
        print(f"SAVED {pre}")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    body = kitbash.import_stl(pre, "body")
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bars = []
    for side in (+1, -1):
        for band in cfg["bands"]:
            bars += thicken_box(bm, side, band, cfg)
    bm.to_mesh(body.data)
    bm.free()
    grates = kitbash.mesh_object("grates", [tuple(p) for t in bars for p in t],
                                 [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(bars))], (1, 0, 1, 1))
    kitbash.export_stl([body, grates], body_stl)
    with open(marker, "w") as f:
        json.dump({k: cfg[k] for k in ("wall", "back", "bar_w", "bar_pitch", "bar_h", "bar_sink")}, f, indent=1)
    print(f"EXPORT {body_stl}")


if __name__ == "__main__":
    main()
