"""
Detail grafts - crop pieces out of donor STLs and seat them on a part's flanks.

Gun frame: fitted from the part's largest shell (the gun body). PCA gives a seed axis; the
barrel is the run of cross-section slices with the modal (housing) width/height, and the frame
is a line fit through those slice centres. along points to the muzzle, up is world Z made
perpendicular, side = along x up. Faces: outer = +side, inner = -side, top = +up, bottom = -up.

Piece: a donor STL (optionally cropped to a box and scaled). Crops are cut one plane at a time
and each cut is capped, so pieces stay closed. The donor's `out` axis turns to face away from
the flank, `up` to the frame's up; along follows (up x out), so pieces are never mirrored.
The piece's back face (opposite `out`) is seated `overlap` mm into the flank surface, found by
raycasting across its footprint. Pieces are joined as overlapping shells - no boolean.
"""
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

AXES = {"+X": (1, 0, 0), "-X": (-1, 0, 0), "+Y": (0, 1, 0), "-Y": (0, -1, 0), "+Z": (0, 0, 1), "-Z": (0, 0, -1)}
SLICE_MM = 1.0
SLICE_HALF = 0.4
MODE_TOL = 0.6          # slices within this of the modal width/height count as barrel housing


def shells(mesh):
    """Shell id per vertex."""
    n = len(mesh.vertices)
    parent = np.arange(n)

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    e = np.empty(len(mesh.edges) * 2, np.int32)
    mesh.edges.foreach_get("vertices", e)
    for a, b in e.reshape(-1, 2):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    return np.array([find(i) for i in range(n)])


def vertices(mesh):
    co = np.empty(len(mesh.vertices) * 3, np.float32)
    mesh.vertices.foreach_get("co", co)
    return co.reshape(-1, 3).astype(np.float64)


def fit_frame(P):
    """Barrel frame from gun-shell vertices P: (origin, along, up, side, housing half-size)."""
    mu = P.mean(0)
    a = np.linalg.svd(P - mu, full_matrices=False)[2][0]
    a *= -np.sign(a[1])                                     # muzzle towards -Y
    up = np.array([0, 0, 1.0]) - a * a[2]
    up /= np.linalg.norm(up)
    s = np.cross(a, up)
    q = P - mu
    al = q @ a
    rows = []
    for x in np.arange(al.min() + 1, al.max() - 1, SLICE_MM):
        sl = q[np.abs(al - x) < SLICE_HALF]
        if len(sl) > 20:
            uu, ss = sl @ up, sl @ s
            rows.append((x, uu.min(), uu.max(), ss.min(), ss.max()))
    rows = np.array(rows)
    h, w = rows[:, 2] - rows[:, 1], rows[:, 4] - rows[:, 3]
    hm, wm = np.median(h), np.median(w)
    b = rows[(np.abs(h - hm) < MODE_TOL) & (np.abs(w - wm) < MODE_TOL)]
    cen = np.array([mu + a * r[0] + up * (r[1] + r[2]) / 2 + s * (r[3] + r[4]) / 2 for r in b])
    o = cen.mean(0)
    a = np.linalg.svd(cen - o)[2][0]
    a *= -np.sign(a[1])
    up = np.array([0, 0, 1.0]) - a * a[2]
    up /= np.linalg.norm(up)
    s = np.cross(a, up)
    span = ((cen - o) @ a).min(), ((cen - o) @ a).max()
    return {"origin": o, "along": a, "up": up, "side": s, "half": (wm / 2, hm / 2), "span": span}


def _hull(pts):
    pts = np.unique(np.round(pts, 5), axis=0)
    pts = pts[np.lexsort((pts[:, 1], pts[:, 0]))]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in pts[::-1]:
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return np.array(lo[:-1] + hi[:-1])


def fit_roll(P, frame, along_range):
    """Roll of a square collar about the gun axis: the minimum-area rectangle (rotating calipers
    over the convex hull) of the vertices P in along_range, in (side, up) coordinates.
    Returns roll in degrees folded to (-45, 45], the (side, up) centre, side lengths, corners."""
    q = P - frame["origin"]
    al = q @ frame["along"]
    pts = np.c_[q @ frame["side"], q @ frame["up"]][(al > along_range[0]) & (al < along_range[1])]
    H = _hull(pts)
    best = None
    for i in range(len(H)):
        e = H[(i + 1) % len(H)] - H[i]
        th = np.arctan2(e[1], e[0])
        R = np.array([[np.cos(th), np.sin(th)], [-np.sin(th), np.cos(th)]])
        r = H @ R.T
        lo, hi = r.min(0), r.max(0)
        if best is None or np.prod(hi - lo) < best[0]:
            best = (np.prod(hi - lo), th, lo, hi, R)
    _, th, lo, hi, R = best
    corners = np.array([[lo[0], lo[1]], [hi[0], lo[1]], [hi[0], hi[1]], [lo[0], hi[1]]]) @ R
    return {"roll": (np.degrees(th) + 45) % 90 - 45, "centre": ((lo + hi) / 2) @ R,
            "sides": hi - lo, "corners": corners}


def roll_frame(frame, roll_deg, centre):
    """Frame rolled about along by roll_deg (side turns towards up), recentred on centre (side, up)."""
    f = dict(frame)
    c, s = np.cos(np.radians(roll_deg)), np.sin(np.radians(roll_deg))
    f["side"] = c * frame["side"] + s * frame["up"]
    f["up"] = -s * frame["side"] + c * frame["up"]
    f["origin"] = frame["origin"] + frame["side"] * centre[0] + frame["up"] * centre[1]
    return f


def crop(bm, lo, hi):
    """Keep the inside of box lo..hi, capping each cut. Every cut runs through the whole remaining
    surface (no pre-trim), so its outline is a closed loop and the cap closes it; the next cut trims
    the earlier caps with the rest."""
    lo, hi = Vector(lo), Vector(hi)
    for i in range(3):
        for co, sign in ((lo, -1), (hi, 1)):
            n = Vector((0, 0, 0))
            n[i] = sign
            geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=n, clear_outer=True)
            cut = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge) and len(e.link_faces) == 1]
            if cut:
                filled = bmesh.ops.holes_fill(bm, edges=cut, sides=0)
                tris = bmesh.ops.triangulate(bm, faces=filled["faces"])["faces"]
                flip = [f for f in tris if f.normal.dot(n) < 0]          # caps face the removed side
                if flip:
                    bmesh.ops.reverse_faces(bm, faces=flip)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')


_DONORS = {}


def load_piece(path, crop_box=None, scale=1.0, name="piece"):
    """New object holding the (cropped, scaled) donor; each donor file is imported once."""
    path = os.path.expanduser(path)
    if path not in _DONORS:
        bpy.ops.wm.stl_import(filepath=path)
        src = bpy.context.selected_objects[0]
        _DONORS[path] = src.data
        bpy.data.objects.remove(src)
    o = bpy.data.objects.new(name, _DONORS[path].copy())
    bpy.context.scene.collection.objects.link(o)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    if crop_box:
        crop(bm, crop_box["min"], crop_box["max"])
    bm.transform(Matrix.Scale(scale, 4))
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
    return o


def face_axes(frame, face):
    """(outward normal, in-plane second axis) of a frame face. The first in-plane axis is
    second x normal: along on the flanks and top/bottom, side on the back (butt) face."""
    s, u, a = frame["side"], frame["up"], frame["along"]
    return {"outer": (s, u), "inner": (-s, u), "top": (u, s), "bottom": (-u, s), "back": (-a, u)}[face]


def seat(obj, frame, tree, at, face, out, up, overlap, samples=5):
    """Rotate/translate obj (local donor coords) so its back face sits `overlap` into the face.

    out -> face normal, up -> the face's second axis, along follows (never mirrored).
    at = [first in-plane axis, second] offsets from the frame axis."""
    n, t2 = face_axes(frame, face)
    out_d, up_d = Vector(AXES[out]), Vector(AXES[up])
    along_d = up_d.cross(out_d)
    along_g = Vector(np.cross(t2, n))
    R = Matrix((along_g, Vector(t2), Vector(n))).transposed() @ Matrix((along_d, up_d, out_d))
    co = vertices(obj.data)
    loc = co @ np.array(R).T
    a_ax, u_ax, n_ax = np.array(along_g), np.array(t2), np.array(n)
    la, lu, ln = loc @ a_ax, loc @ u_ax, loc @ n_ax
    centre = np.array([(la.min() + la.max()) / 2, (lu.min() + lu.max()) / 2, ln.min()])   # back-face centre
    base = frame["origin"] + a_ax * at[0] + u_ax * at[1]
    depths = []
    for fa in np.linspace(-0.4, 0.4, samples):
        for fu in np.linspace(-0.4, 0.4, samples):
            p = base + a_ax * fa * (la.max() - la.min()) + u_ax * fu * (lu.max() - lu.min())
            hit = tree.ray_cast(Vector(p + n_ax * 40), Vector(-n_ax))
            if hit[0] is not None:
                depths.append((np.array(hit[0]) - frame["origin"]) @ n_ax)
    if not depths:
        raise ValueError(f"{obj.name}: no flank surface under {at}")
    surf = float(np.median(depths))
    target = base + n_ax * (surf - overlap)               # base lies on the frame's centre line
    t = target - (a_ax * centre[0] + u_ax * centre[1] + n_ax * centre[2])
    obj.data.transform(Matrix.Translation(Vector(t)) @ R.to_4x4())
    obj.data.update()
    return surf, (la.max() - la.min(), lu.max() - lu.min(), ln.max() - ln.min())


def subset_object(src, keep, name):
    """New object with the vertices of src where keep is True (src untouched)."""
    bm = bmesh.new()
    bm.from_mesh(src.data)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not keep[v.index]], context='VERTS')
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return o


def cut_gap(obj, frame, a0, a1, shift):
    """Remove obj's geometry between along a0..a1, cap both cuts, move the front part back by shift.

    Returns the number of cap faces made at each plane."""
    o, a = Vector(frame["origin"]), Vector(frame["along"])
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for x in (a0, a1):
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=o + a * x, plane_no=a)

    def along(p):
        return (p - o).dot(a)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if a0 < along(f.calc_center_median()) < a1], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    caps = []
    for x in (a0, a1):
        edges = [e for e in bm.edges if len(e.link_faces) == 1
                 and all(abs(along(v.co) - x) < 1e-4 for v in e.verts)]
        filled = bmesh.ops.holes_fill(bm, edges=edges, sides=0)
        bmesh.ops.triangulate(bm, faces=filled["faces"])
        caps.append(len(filled["faces"]))
    front = [v for v in bm.verts if along(v.co) >= a1 - 1e-4]
    bmesh.ops.translate(bm, verts=front, vec=-a * shift)
    open_edges = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return caps, open_edges


def trim_front(obj, frame, x):
    """Cut obj flush at along = x, keep the part behind (along < x), cap the cut.
    Returns (vertices before, vertices after)."""
    o, a = Vector(frame["origin"]), Vector(frame["along"])
    n0 = len(obj.data.vertices)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                                 plane_co=o + a * x, plane_no=a, clear_outer=True)
    cut = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge) and len(e.link_faces) == 1]
    if cut:
        filled = bmesh.ops.holes_fill(bm, edges=cut, sides=0)
        bmesh.ops.triangulate(bm, faces=filled["faces"])
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return n0, len(obj.data.vertices)


DIRS = {"+up": ("up", 1), "-up": ("up", -1), "+side": ("side", 1), "-side": ("side", -1)}


def place_member(obj, frame, along_c, at, long, face, toward, anchor="bbox"):
    """Lay a section member along the gun axis: donor `long` axis -> along, donor `face` axis ->
    `toward` (+up/-up/+side/-side, or [up, side] components, e.g. [1, 1] for a corner diagonal).
    The anchor (bbox centre, or donor origin) goes to along_c and at = [up, side] in the frame.
    Returns the member's (along, up, side) extents."""
    a = np.array(frame["along"])
    if isinstance(toward, str):
        k, sgn = DIRS[toward]
        t = np.array(frame[k]) * sgn
    else:
        t = np.array(frame["up"]) * toward[0] + np.array(frame["side"]) * toward[1]
        t /= np.linalg.norm(t)
    L_d, F_d = Vector(AXES[long]), Vector(AXES[face])
    R = Matrix((Vector(a), Vector(t), Vector(np.cross(a, t)))).transposed() @ Matrix((L_d, F_d, L_d.cross(F_d)))
    co = vertices(obj.data) @ np.array(R).T
    p = (co.min(0) + co.max(0)) / 2 if anchor == "bbox" else np.zeros(3)
    target = frame["origin"] + a * along_c + np.array(frame["up"]) * at[0] + np.array(frame["side"]) * at[1]
    obj.data.transform(Matrix.Translation(Vector(target - p)) @ R.to_4x4())
    if anchor == "bbox":       # recentre on frame-axis extents: a crop that doesn't fill its box biases the world bbox
        q = vertices(obj.data) - frame["origin"]
        fix = sum(np.array(frame[k]) * (want - ((q @ np.array(frame[k])).min() + (q @ np.array(frame[k])).max()) / 2)
                  for k, want in (("along", along_c), ("up", at[0]), ("side", at[1])))
        obj.data.transform(Matrix.Translation(Vector(fix)))
    obj.data.update()
    q = vertices(obj.data) - frame["origin"]
    return [(float((q @ np.array(frame[k])).min()), float((q @ np.array(frame[k])).max()))
            for k in ("along", "up", "side")]


def section_mask(objs, frame, along_x, up_range, side_range, step=0.05):
    """Inside/outside mask of the union of closed meshes on the plane along = along_x. A point is
    inside a shell when the nearest surface faces away from it; tested per shell, since
    overlapping shells (bumps on a tube) confuse both parity and nearest-face tests on the whole
    mesh. Rows = up, cols = side."""
    trees = []
    for o in objs:
        co = [tuple(v) for v in vertices(o.data)]
        sid = shells(o.data)
        polys = {}
        for p in o.data.polygons:
            polys.setdefault(sid[p.vertices[0]], []).append(tuple(p.vertices))
        trees += [BVHTree.FromPolygons(co, ps) for ps in polys.values()]
    a, u, s = (Vector(frame[k]) for k in ("along", "up", "side"))
    base = Vector(frame["origin"]) + a * along_x
    us = np.arange(up_range[0], up_range[1] + 1e-9, step)
    ss = np.arange(side_range[0], side_range[1] + 1e-9, step)
    mask = np.zeros((len(us), len(ss)), bool)
    for i, uu in enumerate(us):
        for j, sv in enumerate(ss):
            p = base + u * uu + s * sv
            for t in trees:
                hit = t.find_nearest(p, 3.0)
                if hit[0] is not None and (hit[0] - p).dot(hit[1]) > 0:
                    mask[i, j] = True
                    break
    return mask, us, ss


def overlaps(obj_a, obj_b):
    ta = BVHTree.FromPolygons([tuple(v) for v in vertices(obj_a.data)], [tuple(p.vertices) for p in obj_a.data.polygons])
    tb = BVHTree.FromPolygons([tuple(v) for v in vertices(obj_b.data)], [tuple(p.vertices) for p in obj_b.data.polygons])
    return len(ta.overlap(tb))
