"""
Relief stamping onto a mesh surface - no booleans.

The faces under the stamp footprint are subdivided down to max_edge, the faces a feature outline
runs through again down to edge_edge, then every vertex is pushed to its level along a smoothed
surface normal (see _smooth_normals). Only vertices move, so the mesh stays as watertight (or not) as it
was; non-manifold geometry elsewhere is irrelevant.

Features are nested layers [(sdf, height)], outermost first (niche, then strokes inside it):
sdf is a signed distance grid in mm (negative inside) over the footprint, sampled [v, u] at res;
a vertex gets the height of the deepest layer it is inside of, stopping at the first layer it is
outside of. Vertices never move sideways, so no triangle can flip; the outline's step along the
edge_edge triangles (0.02mm) is below a resin printer's pixel.

Footprint mapping: uv_fn maps world points (N x 3) to footprint coordinates in mm - u across
(0 = grid centre column), v along (0 = first row). linear_uv() gives a flat frame; a curved band
supplies its own. Faces are stamped only if they face `up` (dot > FACING) and lie on the outermost
surface along it (no other surface within OUTER_TOL above them) - so undersides and buried
shells sharing the same (u, v) are left alone.
"""
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

FACING = 0.3
OUTER_TOL = 0.05
NORMAL_GRID = 0.3       # displacement-normal sample spacing (mm)
NORMAL_RADIUS = 1.0     # normals averaged over this radius (mm)
NORMAL_K = 6            # samples blended per vertex


def linear_uv(origin, u_axis, v_axis):
    o, ua, va = (np.array(a, float) for a in (origin, u_axis, v_axis))
    return lambda p: ((p - o) @ ua, (p - o) @ va)


def _sample(grid, res, u, v, fill):
    """Bilinear grid lookup; u/v in mm from the grid's top-centre, `fill` outside."""
    H, W = grid.shape
    x = np.clip(u / res + W / 2 - 0.5, -1, W)
    y = np.clip(v / res - 0.5, -1, H)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    out = np.zeros(len(u))
    for dy, wy in ((0, 1 - fy), (1, fy)):
        for dx, wx in ((0, 1 - fx), (1, fx)):
            yy, xx = y0 + dy, x0 + dx
            ok = (yy >= 0) & (yy < H) & (xx >= 0) & (xx < W)
            val = np.full(len(u), fill, float)
            val[ok] = grid[yy[ok], xx[ok]]
            out += val * wx * wy
    return out


def _smooth_normals(co, tree):
    """Displacement directions that vary smoothly over the surface. The surface's own normals jump
    at every facet edge of a low-poly sculpt, and neighbouring vertices pushed apart along them
    fold the fine triangles over. Normals are sampled on a NORMAL_GRID voxel subset, averaged over
    NORMAL_RADIUS, and blended per vertex from the nearest NORMAL_K samples by inverse distance."""
    keys = np.floor(co / NORMAL_GRID).astype(np.int64)
    _, first = np.unique(keys, axis=0, return_index=True)
    samples = co[first]
    raw = np.array([tree.find_nearest(Vector(p))[1] for p in samples])
    kd = KDTree(len(samples))
    for i, p in enumerate(samples):
        kd.insert(p, i)
    kd.balance()
    smooth = np.array([raw[[i for _, i, _ in kd.find_range(p, NORMAL_RADIUS)]].sum(0) for p in samples])
    smooth /= np.linalg.norm(smooth, axis=1)[:, None]
    out = np.empty_like(co)
    for k, p in enumerate(co):
        near = kd.find_n(p, NORMAL_K)
        w = np.array([1.0 / (d + 1e-3) for _, _, d in near])
        n = (smooth[[i for _, i, _ in near]] * w[:, None]).sum(0)
        out[k] = n / np.linalg.norm(n)
    return out


def _split(bm, faces, cuts):
    """Split every edge of `faces` into cuts + 1 and re-triangulate whatever turned into ngons."""
    edges = list({e for f in faces for e in f.edges})
    res_geom = bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts, use_grid_fill=True)
    new_verts = {g for g in res_geom["geom"] if isinstance(g, bmesh.types.BMVert)}
    bmesh.ops.triangulate(bm, faces=list({f for vv in new_verts for f in vv.link_faces if len(f.verts) > 3}))


def stamp(obj, layers, res, uv_fn, up, max_edge=0.08, edge_edge=0.02):
    up = Vector(up).normalized()
    H, W = layers[0][0].shape
    half_u, len_v = W * res / 2 + 0.2, H * res + 0.2

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    tree = BVHTree.FromBMesh(bm)
    bm.faces.ensure_lookup_table()

    # every face that touches the footprint at all: a big face with only a corner inside it would
    # otherwise stay coarse and get that corner pushed down into a long slanted sliver
    bm.verts.ensure_lookup_table()
    vu, vv_ = uv_fn(np.array([vt.co for vt in bm.verts]))
    vin = (np.abs(vu) <= half_u) & (vv_ > -0.2) & (vv_ < len_v)
    candidates = [i for i, f in enumerate(bm.faces) if any(vin[vt.index] for vt in f.verts)]

    def outer(f):
        if f.normal.dot(up) < FACING:
            return False
        c = f.calc_center_median()
        hit = tree.ray_cast(c + up * 30, -up)
        return hit[0] is not None and (hit[0] - c).dot(up) < OUTER_TOL

    # Tag the stamped surface once; split faces inherit the tag. Its edges are split in a single
    # native call with enough cuts that the longest one ends up under max_edge; neighbouring
    # faces pick up the split verts as ngons and are triangulated.
    tag = bm.faces.layers.int.new("stamp")
    region = [bm.faces[i] for i in candidates if outer(bm.faces[i])]
    if not region:
        raise ValueError("stamp footprint hits no outward-facing surface")
    for f in region:
        f[tag] = 1
    longest = max(e.calc_length() for f in region for e in f.edges)
    _split(bm, region, int(np.ceil(longest / max_edge)) - 1)

    # second pass: refine just the faces an outline runs through
    region = [f for f in bm.faces if f[tag]]
    fverts = list({vv for f in region for vv in f.verts})
    fco = np.array([vv.co for vv in fverts])
    fu, fv = uv_fn(fco)
    side = {}
    for grid, _ in layers:
        s_in = _sample(grid, res, fu, fv, 1e3) < 0
        for vv, flag in zip(fverts, s_in):
            side.setdefault(vv, []).append(flag)
    straddle = [f for f in region if any(len({side[vv][k] for vv in f.verts}) > 1 for k in range(len(layers)))]
    if straddle:
        _split(bm, straddle, int(np.ceil(max_edge / edge_edge)) - 1)

    region = [f for f in bm.faces if f[tag]]
    verts = list({vv for f in region for vv in f.verts})
    co = np.array([vv.co for vv in verts])
    h = np.zeros(len(co))
    inside = np.ones(len(co), bool)
    u, v = uv_fn(co)
    for grid, height in layers:
        inside &= _sample(grid, res, u, v, 1e3) < 0
        h = np.where(inside, height, h)
    normals = _smooth_normals(co, tree)
    for vv, c, n, dh in zip(verts, co, normals, h):
        if dh:
            vv.co = Vector(c + n * dh)
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    return len(region)
