"""
Gun rework proof - cuts the barrel housing out of the cannon's gun shell, closes the gap with the
recipe's [part.section] members (tubes + rails), writes parts/<name>/cannon.stl in the cannon's own
file coordinates (arm, hand and ball joint untouched, so part_joint stays valid) and review renders
in the gun frame (gun_views.json carries the camera axes for grid overlays).

Checks: every member reaches into both collars; what members touch outside the gun shell; the
section's cross-section (area, solid pieces, thinnest bridge) at several stations along the gap.
[[part.graft]] entries with enabled = false are skipped.

  /Applications/Blender.app/Contents/MacOS/Blender --background --python tools/gun_proof.py -- [--variant flush|proud] [--quick]

--quick builds, exports and renders but skips the checks - for runs that only change the rear end.

flush: [[part.section.member]] as listed (rails flush inside the collar square), written as
cannon_flush.stl / *_flush renders. proud: the tubes plus [[part.section.proud]] rails lying on
the outside of the square, written as the active cannon.stl. Members with enabled = false are
skipped; girth = <factor> scales a member's cross-section about its long axis (length unchanged).
[part.extend] adds a mirrored copy of the rear box behind the butt (extend_box); the grafts are
seated after it, so a back-face graft lands on the new butt.
"""
import argparse
import json
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import graft                                    # noqa: E402
import kitbash                                  # noqa: E402

PART = "cannon"
VIEW_MM = 52
MASK_STEP = 0.05
TUBE_GREEN = (0.35, 0.8, 0.35, 1)
RAIL_ORANGE = (0.85, 0.55, 0.2, 1)


def thicken(o, long, girth, anchor):
    """Scale a member's cross-section by girth about its own long axis; length unchanged.
    The axis runs through the donor origin (anchor = "origin") or the bbox centre."""
    a = np.array(graft.AXES[long], float)
    v = graft.vertices(o.data)
    pivot = np.zeros(3) if anchor == "origin" else (v.min(0) + v.max(0)) / 2
    d = v - pivot
    along = np.outer(d @ a, a)
    o.data.vertices.foreach_set("co", (pivot + along + (d - along) * girth).astype(np.float32).ravel())
    o.data.update()


def tree_of(o):
    return BVHTree.FromPolygons([tuple(v) for v in graft.vertices(o.data)], [tuple(p.vertices) for p in o.data.polygons])


def recess(bm, o, a, s, u, mid, ext):
    """A rectangular pocket in each flat lower side wall of the copied box, with a criss-cross
    grate on its floor. The wall faces are cut along the rectangle's edges and the rectangle is
    extruded `depth` into the box. Returns the grate bar triangles (world coords, before the move)."""
    import bmesh
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import vent_proof
    r = ext["recess"]
    (al0, al1), (up0, up1), depth = r["along"], r["up"], r["depth"]
    bars = []
    for sgn in (1, -1):
        n = s * sgn                               # outward wall normal
        wall = lambda f: (f.normal.dot(n) > 0.95 and up0 - 0.3 < (f.calc_center_median() - o).dot(u) < up1 + 0.3
                          and al0 - 0.3 < (f.calc_center_median() - o).dot(a) < al1 + 0.3)
        for co, no in ((o + a * al0, a), (o + a * al1, a), (o + u * up0, u), (o + u * up1, u)):
            fs = [f for f in bm.faces if wall(f)]
            g = list({x for f in fs for x in list(f.verts) + list(f.edges)}) + fs
            bmesh.ops.bisect_plane(bm, geom=g, plane_co=co, plane_no=no)
        inside = [f for f in bm.faces if wall(f)
                  and al0 < (f.calc_center_median() - o).dot(a) < al1 and up0 < (f.calc_center_median() - o).dot(u) < up1]
        if not inside:
            print(f"RECESS side {sgn:+d}: no wall faces found")
            continue
        wall_d = np.median([(f.calc_center_median() - o).dot(n) for f in inside])
        ex = bmesh.ops.extrude_face_region(bm, geom=inside)
        moved = [g for g in ex["geom"] if isinstance(g, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, vec=-n * depth, verts=moved)
        bmesh.ops.delete(bm, geom=inside, context='FACES')
        floor_c = o + n * (wall_d - depth) + a * ((al0 + al1) / 2) + u * ((up0 + up1) / 2)
        corners = [np.array(o + n * (wall_d - depth) + a * x + u * y) for x in (al0, al1) for y in (up0, up1)]
        t, face = vent_proof.grate(np.array(floor_c), np.array(n), corners, r)
        bars += t
        print(f"RECESS side {sgn:+d}: wall at {wall_d:.2f} from the box centre, {len(inside)} faces, pocket "
              f"{al1 - al0:.2f} x {up1 - up0:.2f} x {depth:.2f}mm, grate {len(t)} tris")
    bm.normal_update()
    return bars


def extend_box(gun, frame, ext):
    """[part.extend]: a copy of the rear box behind the butt. The inner half of the box (side below
    the box's symmetry plane, clear of the hoses on the outer side) is cut out at the plane and the
    range ends, mirrored, welded at the plane, capped, and moved back by the box length less
    `overlap`; the two boxes' end bevels meet in a panel line. Returns the box length."""
    import bmesh
    o, a, s, u = (Vector(frame[k]) for k in ("origin", "along", "side", "up"))
    a0, a1 = ext["range"]
    mid = ext["mirror"]
    lo_up, hi_up = ext["up"]
    bm = bmesh.new()
    bm.from_mesh(gun.data)
    keep = set()
    for f in bm.faces:
        q = f.calc_center_median() - o
        if (a0 - 0.01 < q.dot(a) < a1 + 0.5 and lo_up < q.dot(u) < hi_up
                and q.dot(s) < mid + 1.0 and q.dot(s) > -ext["half"] - 0.2):
            keep.add(f)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f not in keep], context='FACES')
    geom = lambda: bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom(), plane_co=o + s * mid, plane_no=s, clear_outer=True)
    bmesh.ops.bisect_plane(bm, geom=geom(), plane_co=o + a * a1, plane_no=a, clear_outer=True)
    dup = bmesh.ops.duplicate(bm, geom=geom())
    for v in [g for g in dup["geom"] if isinstance(g, bmesh.types.BMVert)]:
        d = (v.co - o).dot(s) - mid
        v.co = v.co - s * (2 * d)
    bmesh.ops.reverse_faces(bm, faces=[g for g in dup["geom"] if isinstance(g, bmesh.types.BMFace)])
    seam = [v for v in bm.verts if abs((v.co - o).dot(s) - mid) < 1e-4]
    bmesh.ops.remove_doubles(bm, verts=seam, dist=1e-4)
    open_edges = [e for e in bm.edges if len(e.link_faces) == 1]
    bmesh.ops.holes_fill(bm, edges=open_edges, sides=0)
    bars = recess(bm, o, a, s, u, mid, ext) if ext.get("recess") else []
    length = a1 - a0
    bmesh.ops.translate(bm, vec=-a * (length - ext["overlap"]), verts=bm.verts)
    shift = -a * (length - ext["overlap"])
    for t in bars:                               # grate bars as their own shells, moved with the box
        vs = [bm.verts.new(Vector(p) + shift) for p in t]
        bm.faces.new(vs)
    left = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    copy = bpy.data.meshes.new("box_copy")
    bm.to_mesh(copy)
    bm.free()
    bm = bmesh.new()
    bm.from_mesh(gun.data)
    bm.from_mesh(copy)
    bm.to_mesh(gun.data)
    bm.free()
    gun.data.update()
    print(f"EXTEND box along {a0:+.2f}..{a1:+.2f} ({length:.2f}mm) mirrored at side {mid:+.2f}, "
          f"{len(open_edges)} open edges capped, {left} left; moved back {length - ext['overlap']:.2f}mm")
    return length


def components(mask):
    """4-connected components of a bool mask: list of (cell count, thickness in cells)."""
    lab = np.zeros(mask.shape, int)
    out = []
    for start in zip(*np.nonzero(mask)):
        if lab[start]:
            continue
        n = len(out) + 1
        stack, cells = [start], []
        lab[start] = n
        while stack:
            i, j = stack.pop()
            cells.append((i, j))
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                k = (i + di, j + dj)
                if 0 <= k[0] < mask.shape[0] and 0 <= k[1] < mask.shape[1] and mask[k] and not lab[k]:
                    lab[k] = n
                    stack.append(k)
        comp = lab == n
        erosions = 0                                         # thickness = 2 x erosions to vanish
        while comp.any():
            c = comp.copy()
            c[1:] &= comp[:-1]
            c[:-1] &= comp[1:]
            c[:, 1:] &= comp[:, :-1]
            c[:, :-1] &= comp[:, 1:]
            comp = c
            erosions += 1
        out.append((len(cells), 2 * erosions))
    return out


def slice_mask(objs, frame, along_x, up_range, side_range, step):
    """Union cross-section of objs on the plane along = along_x: each object is sliced with a plane
    and its outline filled even-odd in 2D (independent of face orientation). Returns (mask, per-object mm2)."""
    import bmesh
    a, u, s = (np.array(frame[k]) for k in ("along", "up", "side"))
    us = np.arange(up_range[0], up_range[1] + 1e-9, step)
    ss = np.arange(side_range[0], side_range[1] + 1e-9, step)
    gu, gs = np.meshgrid(us, ss, indexing="ij")
    pts = np.c_[gs.ravel(), gu.ravel()]
    mask = np.zeros(len(pts), bool)
    areas = []
    for o in objs:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                                     plane_co=Vector(frame["origin"] + a * along_x), plane_no=Vector(a))
        seg = np.array([[(np.array(e.verts[i].co) - frame["origin"]) @ s, (np.array(e.verts[i].co) - frame["origin"]) @ u]
                        for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge) for i in (0, 1)]).reshape(-1, 2, 2)
        bm.free()
        if not len(seg):
            areas.append(0.0)
            continue
        (x0, y0), (x1, y1) = seg[:, 0].T, seg[:, 1].T
        py = pts[:, 1:2]
        crosses = ((y0 > py) != (y1 > py))
        xi = x0 + (py - y0) * (x1 - x0) / np.where(y1 == y0, 1e-12, y1 - y0)
        inside = ((crosses & (pts[:, 0:1] < xi)).sum(1) % 2).astype(bool)
        areas.append(inside.sum() * step * step)
        mask |= inside
    return mask.reshape(gu.shape), areas


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=("flush", "proud"), default="proud")
    ap.add_argument("--quick", action="store_true",
                    help="build, export and render only: skip the contact, clearance, section and graft-clearance checks")
    args = ap.parse_args(argv)
    variant, quick = args.variant, args.quick
    sfx = "_flush" if variant == "flush" else ""
    recipe = kitbash.load_recipe(os.path.join(ROOT, "recipes", "lokhust.toml"))
    part = next(p for p in recipe["part"] if p["name"] == PART)
    sec = part["section"]
    out_dir = kitbash.data_dir(recipe, "out")
    parts_dir = kitbash.data_dir(recipe, "parts")
    os.makedirs(parts_dir, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    host = kitbash.import_stl(os.path.join(recipe["source"], part["file"]), PART)
    kitbash.colour(host, (0.75, 0.75, 0.75, 1))
    sid = graft.shells(host.data)
    P = graft.vertices(host.data)
    gun_id = max(np.unique(sid), key=lambda i: np.ptp(P[sid == i], axis=0).max())
    frame = graft.fit_frame(P[sid == gun_id])
    a = frame["along"]
    print(f"FRAME origin={np.round(frame['origin'], 3)} along={np.round(a, 4)} "
          f"yaw={np.degrees(np.arctan2(a[0], -a[1])):.1f} pitch={np.degrees(np.arcsin(a[2])):.1f}")
    if "roll_fit" in part["frame"]:
        sq = graft.fit_roll(P[sid == gun_id], frame, part["frame"]["roll_fit"])
        frame = graft.roll_frame(frame, sq["roll"], sq["centre"])
        corners = graft.fit_roll(P[sid == gun_id], frame, part["frame"]["roll_fit"])["corners"]
        print(f"ROLL {sq['roll']:+.2f}deg  square {sq['sides'][0]:.2f} x {sq['sides'][1]:.2f}mm  "
              f"centre (side,up) {np.round(sq['centre'], 3)}  corners in rolled frame (side,up) "
              + " ".join(f"({c[0]:+.2f},{c[1]:+.2f})" for c in corners))
    old_len = np.ptp((P[sid == gun_id] - frame["origin"]) @ a)

    gun = graft.subset_object(host, sid == gun_id, "gun")
    rest = graft.subset_object(host, sid != gun_id, "arm_hand")
    for o in (gun, rest):
        kitbash.colour(o, (0.75, 0.75, 0.75, 1))

    members = []
    chosen = sec["member"] if variant == "flush" else \
        [m for m in sec["member"] if not m["name"].startswith("rail")] + sec["proud"]
    chosen = [m for m in chosen if m.get("enabled", True)]
    for m in chosen:
        o = graft.load_piece(m["donor"], m.get("crop"), m["scale"], m["name"])
        if m.get("girth", 1.0) != 1.0:
            thicken(o, m["long"], m["girth"], m.get("anchor", "bbox"))
        length = np.ptp(graft.vertices(o.data) @ np.array(graft.AXES[m["long"]]))
        members.append((m, o, length))
    c0, c1 = sec["cut"]
    gap = min(L for _, _, L in members) - 2 * sec["overlap"]
    shift = (c1 - c0) - gap
    caps, open_edges = graft.cut_gap(gun, frame, c0, c1, shift)
    print(f"CUT along {c0:+.2f}..{c1:+.2f} ({c1 - c0:.2f}mm removed), cap faces {caps}, open edges left {open_edges}; "
          f"new gap {gap:.2f}mm, muzzle piece moved back {shift:.2f}mm")
    if sec.get("trim"):
        rq = (graft.vertices(rest.data) - frame["origin"]) @ a
        behind = np.sort(rq[rq < c0 - 0.01])
        n0, n1 = graft.trim_front(rest, frame, c0)
        rq2 = (graft.vertices(rest.data) - frame["origin"]) @ a
        intact = np.array_equal(behind, np.sort(rq2[rq2 < c0 - 0.01]))
        print(f"TRIM other shells at along {c0:+.2f}: removed along {c0:+.2f}..{rq.max():+.2f}, "
              f"vertices {n0} -> {n1}; everything behind the plane identical: {intact}")
    ball = np.array(part["part_joint"])
    print(f"BALL nearest arm/hand vertex {np.linalg.norm(graft.vertices(rest.data) - ball, axis=1).min():.3f}mm "
          f"from part_joint (ball r 1.19, along {(ball - frame['origin']) @ a:+.2f})")
    centre = c0 + gap / 2
    for m, o, L in members:
        ext = graft.place_member(o, frame, centre + m.get("along_shift", 0.0), m["at"], m["long"], m["face"], m["toward"], m.get("anchor", "bbox"))
        kitbash.colour(o, TUBE_GREEN if "tube" in m["name"] else RAIL_ORANGE)
        print(f"MEMBER {m['name']:18s} along {ext[0][0]:+6.2f}..{ext[0][1]:+6.2f} up {ext[1][0]:+5.2f}..{ext[1][1]:+5.2f} "
              f"side {ext[2][0]:+5.2f}..{ext[2][1]:+5.2f} (len {L:.2f}, past the gap ends {c0 - ext[0][0]:.2f} / {ext[0][1] - (c0 + gap):.2f})")

    objs = [o for _, o, _ in members]
    if not quick:
        gun_tree, rest_tree = tree_of(gun), tree_of(rest)
        gun_cent = np.array([p.center for p in gun.data.polygons])
        for m, o, _ in members:
            t = tree_of(o)
            pairs = t.overlap(gun_tree)
            al = (gun_cent[[j for _, j in pairs]] - frame["origin"]) @ a if pairs else np.array([])
            rear, front = (al < c0 + 0.5).any(), (al > c0 + gap - 0.5).any()
            print(f"CONTACT {m['name']:18s} rear collar {'yes' if rear else 'NO'}  front collar {'yes' if front else 'NO'}  "
                  f"arm/hand-shell tri pairs {len(t.overlap(rest_tree))}")
        new_len = np.ptp((graft.vertices(gun.data) - frame["origin"]) @ a)
        print(f"LENGTH gun shell {old_len:.2f} -> {new_len:.2f}mm ({old_len - new_len:.2f} shorter)")

        gq0 = graft.vertices(gun.data) - frame["origin"]
        hose_pts = gq0[((gq0 @ a) > -17) & ((gq0 @ a) < c0) & ((gq0 @ frame["up"]) < -3.7)]     # hose loop under the rear block
        trees = {o.name: tree_of(o) for o in objs}
        half = 3.5
        for i, (mi, oi, _) in enumerate(members):
            q = graft.vertices(oi.data) - frame["origin"]
            inside = q[((q @ a) > c0 + 0.2) & ((q @ a) < c0 + gap - 0.2)]           # the free span, clear of the collars
            sq_gap = half - np.abs(np.c_[inside @ frame["side"], inside @ frame["up"]]).max()
            others = []
            for mj, oj, _ in members[i + 1:]:
                d = min(trees[oj.name].find_nearest(v)[3] for v in frame["origin"] + inside)
                others.append(f"{mj['name']} {d:.2f}")
            arm = min(rest_tree.find_nearest(v)[3] for v in frame["origin"] + q)
            hose = np.linalg.norm(q[:, None, :][::3] - hose_pts[None, ::3], axis=2).min() if len(hose_pts) else np.inf
            print(f"CLEAR {mi['name']:18s} to square face {sq_gap:+.2f}  arm/hand {arm:.2f}  hose loop {hose:.2f}  " + "  ".join(others))
        for x in (c0 + 1.0, centre + 0.37, c0 + gap - 1.0):           # mid station off the tubes' centre vertex ring
            mask, areas = slice_mask(objs, frame, x, (-5.0, 5.0), (-5.0, 5.0), MASK_STEP)
            comps = [c for c in components(mask) if c[0] * MASK_STEP ** 2 > 0.05]
            desc = ", ".join(f"{n * MASK_STEP ** 2:.2f}mm2 (thick {t * MASK_STEP:.2f})" for n, t in sorted(comps, reverse=True))
            each = "  ".join(f"{o.name} {ar:.2f}" for o, ar in zip(objs, areas))
            print(f"SECTION along {x:+6.2f}: area {mask.sum() * MASK_STEP ** 2:.2f}mm2 in {len(comps)} piece(s): {desc}\n        per member: {each}")

    if part.get("extend"):
        extend_box(gun, frame, part["extend"])
    gun_tree = tree_of(gun)
    gq = graft.vertices(gun.data) - frame["origin"]
    back_along = (gq @ a).min()
    butt = gq[(gq @ a) < back_along + 0.3]
    bs, bu = butt @ frame["side"], butt @ frame["up"]
    butt_c = [(bs.min() + bs.max()) / 2, (bu.min() + bu.max()) / 2]
    print(f"BACK face at along {back_along:+.2f}: side {bs.min():+.2f}..{bs.max():+.2f} up {bu.min():+.2f}..{bu.max():+.2f}")
    grafts = []
    for g in part.get("graft", []):
        if not g.get("enabled", True):
            continue
        o = graft.load_piece(g["donor"], g.get("crop"), g["scale"], g["name"])
        at = butt_c if g["at"] == "centre" else g["at"]
        surf, size = graft.seat(o, frame, gun_tree, at, g["face"], g["out"], g["up"], g["overlap"])
        kitbash.colour(o, RAIL_ORANGE)
        q = graft.vertices(o.data) - frame["origin"]
        print(f"GRAFT {g['name']:18s} {g['face']} at (side,up)=({at[0]:+.2f},{at[1]:+.2f}) surface={surf:+.2f} "
              f"size {size[0]:.2f}x{size[1]:.2f}x{size[2]:.2f}  along {(q @ a).min():+.2f}..{(q @ a).max():+.2f}")
        if not quick:
            print(f"GRAFT {g['name']:18s} arm/hand tri pairs {len(tree_of(o).overlap(tree_of(rest)))}  "
                  f"nearest arm/hand {min(tree_of(rest).find_nearest(v)[3] for v in frame['origin'] + q):.2f}mm")
        if g["face"] == "back" and not quick:    # measured clearance to gun geometry behind the butt face (hose loop)
            proud = q[(q @ a) < back_along - 0.3]
            d, near = min(((gun_tree.find_nearest(v)[3], tuple(v)) for v in frame["origin"] + proud), key=lambda t: t[0])
            nq = np.array(gun_tree.find_nearest(near)[0]) - frame["origin"]
            hose = np.linalg.norm(q[:, None, :] - hose_pts[None], axis=2).min() if len(hose_pts) else np.inf
            print(f"GRAFT {g['name']:18s} hose loop {hose:.2f}mm; proud part vs nearest gun-shell surface {d:.2f}mm at "
                  f"(along,side,up)=({nq @ a:+.2f},{nq @ frame['side']:+.2f},{nq @ frame['up']:+.2f})")
        grafts.append(o)

    stl = os.path.join(parts_dir, f"{PART}{sfx}.stl")
    kitbash.export_stl([gun, rest] + objs + grafts, stl)
    print(f"EXPORT {stl}")

    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.color_type = 'MATERIAL'
    sc.display.shading.show_cavity = True
    sc.render.resolution_x = sc.render.resolution_y = 900
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = 'ORTHO'
    o, u, s = frame["origin"], frame["up"], frame["side"]
    view_c = o + a * -7
    views = {"outer": (s, u), "inner": (-s, u), "top": (u, s), "iso": (s + u * 0.6 - a * 0.5, u)}
    meta = {"frame": {k: np.asarray(v).tolist() for k, v in frame.items()}, "centre_along": -7,
            "view_mm": VIEW_MM, "res": 900, "views": {}}
    after = [gun, rest] + objs + grafts
    views["back"] = (-a, u)
    for tag, shown in (("after", after), ("before", [host])):
        for ob in [host] + after:
            ob.hide_render = ob not in shown
        for name, (d, up) in views.items():
            if tag == "before" and name == "inner":
                continue
            d = Vector(d).normalized()
            x = Vector(up).cross(d).normalized()
            y = d.cross(x)
            c, mm = (o + a * back_along, 22) if name == "back" else (view_c, VIEW_MM)
            cam.matrix_world = Matrix.Translation(Vector(c) + d * 200) @ Matrix((x, y, d)).transposed().to_4x4()
            cam.data.ortho_scale = mm
            cam.data.clip_start = 0.1
            sc.render.filepath = os.path.join(out_dir, f"gun_{tag}_{name}{sfx}.png")
            bpy.ops.render.render(write_still=True)
            meta["views"][f"{tag}_{name}"] = {"right": list(x), "up": list(y)}
            if name == "back":
                meta["views"][f"{tag}_{name}"].update({"view_mm": mm, "centre_along": float(back_along)})
    # down the barrel: camera ahead of the section looking back, near plane clipped at mid-gap
    for ob in [host] + after:
        ob.hide_render = ob not in after
    d = Vector(a)
    x = Vector(u).cross(d).normalized()
    y = d.cross(x)
    cam.matrix_world = Matrix.Translation(Vector(o + a * centre) + d * 60) @ Matrix((x, y, d)).transposed().to_4x4()
    cam.data.ortho_scale = 14
    cam.data.clip_start = 60
    sc.render.filepath = os.path.join(out_dir, f"gun_after_xsection{sfx}.png")
    bpy.ops.render.render(write_still=True)
    meta["views"]["after_xsection"] = {"right": list(x), "up": list(y), "view_mm": 14, "centre_along": centre}
    with open(os.path.join(out_dir, f"gun_views{sfx}.json"), "w") as f:
        json.dump(meta, f, indent=1)


main()
