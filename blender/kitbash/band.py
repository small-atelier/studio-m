"""
Glyph bands on the Lokhust carapace plates: a niche cut once into the body, line-glyph solids
placed into it per variant.

Band: each plate's outer edge is traced from above (where the plate is at least min_thick),
smoothed and offset inwards to a centre line, from edge_clear behind the plate front to where
the band no longer fits inside the plate. Only area usable on BOTH plates counts (the right plate
mirrored about the midline), so the two bands are exact mirrors. Points map to (u = distance
across, + outwards; v = distance along) that line.

cut_niches() stamps the rounded-rectangle niche into the body (stamp.stamp, no boolean) and
returns the band data; place_glyphs() builds a seeded set of line-glyph solids for one plate and
seats them on the niche floor: each vertex goes to its (u, v) on the band, is dropped straight
down onto the cut body and offset along the plate's `up` by its height. Glyph solids run from
sink below the floor to depth - glyph_top above it and are separate shells overlapping the body.

cfg = the recipe's [glyphs] table: midline, plate_y, min_thick, edge_clear, width, corner_r, depth,
glyph_top, stroke, margin, n_glyphs, max_edge, line_step. save() / load() keep the band data
next to the cut body in parts/.
"""
import json

import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import glyphs
import stamp

SIDES = (1, -1)         # +1 = model's left plate (+X), -1 = right (-X)


def plate_rows(tree, side, cfg):
    """{y: (x_min, x_max)} of thick top surface on one side's plate, 0.25mm rows."""
    rows = {}
    for y in np.arange(*cfg["plate_y"], 0.25):
        xs = []
        for x in np.arange(cfg["midline"] + side * 2, cfg["midline"] + side * 17, side * 0.1):
            hit = tree.ray_cast(Vector((x, y, 30)), Vector((0, 0, -1)))
            if hit[0] is None or hit[0].z > 3.5:
                continue
            back = tree.ray_cast(hit[0] + Vector((0, 0, -0.01)), Vector((0, 0, -1)))
            if back[0] is not None and hit[0].z - back[0].z >= cfg["min_thick"]:
                xs.append(x)
        if xs:
            rows[round(float(y), 2)] = (min(xs), max(xs))
    return rows


def symmetric_rows(tree, cfg):
    """Plate rows usable on both sides, in +X coordinates (right plate mirrored about the midline)."""
    m = cfg["midline"]
    left, right = plate_rows(tree, 1, cfg), plate_rows(tree, -1, cfg)
    rows = {}
    for y in left.keys() & right.keys():
        lo = max(left[y][0], 2 * m - right[y][1])
        hi = min(left[y][1], 2 * m - right[y][0])
        if hi > lo:
            rows[y] = (lo, hi)
    return rows


def _lookup(rows, y):
    ys = np.array(sorted(rows))
    return rows[float(ys[np.argmin(np.abs(ys - y))])]


def band_line(rows, cfg):
    """Centre line (M x 2, xy, +X plate) at line_step spacing."""
    clear, half_w = cfg["edge_clear"], cfg["width"] / 2
    ys = np.array(sorted(rows))
    xo = np.array([rows[float(y)][1] for y in ys])
    k = 7
    xo = np.convolve(np.pad(xo, k // 2, mode="edge"), np.ones(k) / k, "valid")      # smooth the traced edge
    edge = np.c_[xo, ys]
    t = np.gradient(edge, axis=0)
    t /= np.linalg.norm(t, axis=1)[:, None]
    inward = np.c_[-t[:, 1], t[:, 0]]                     # left of +Y travel = towards -X
    line = edge + inward * (clear + half_w)
    ok = []
    for c, nrm in zip(line, inward):
        inner = c + nrm * (half_w + clear)
        lo, hi = _lookup(rows, inner[1])
        ok.append(lo <= inner[0] <= hi and c[1] >= ys[0] + clear)
    best, run = (0, 0), None                              # longest contiguous run that fits
    for i, good in enumerate(ok + [False]):
        if good and run is None:
            run = i
        elif not good and run is not None:
            if i - run > best[1] - best[0]:
                best = (run, i)
            run = None
    line = line[best[0]:best[1]]
    s_cum = np.r_[0, np.cumsum(np.linalg.norm(np.diff(line, axis=0), axis=1))]
    s_new = np.arange(0, s_cum[-1], cfg["line_step"])
    return np.c_[np.interp(s_new, s_cum, line[:, 0]), np.interp(s_new, s_cum, line[:, 1])]


def band_uv(line, midline, mirror):
    """uv_fn (world points -> u across, v along) for a band along `line`; mirror maps the -X plate."""
    a, b = line[:-1], line[1:]
    d = b - a
    seg_len = np.linalg.norm(d, axis=1)
    s0 = np.r_[0, np.cumsum(seg_len)][:-1]

    def uv(p):
        xy = p[:, :2].copy()
        if mirror:
            xy[:, 0] = 2 * midline - xy[:, 0]
        out_u, out_v = np.empty(len(xy)), np.empty(len(xy))
        for i in range(0, len(xy), 20000):
            q = xy[i:i + 20000, None, :]
            t = np.clip(((q - a) * d).sum(2) / seg_len ** 2, 0, 1)
            dist = np.linalg.norm(q - (a + t[..., None] * d), axis=2)
            j = np.argmin(dist, axis=1)
            r = np.arange(len(j))
            qq = q[r, 0]
            # past either end, extend the end segment straight instead of wrapping round the end point
            t_raw = ((qq - a[j]) * d[j]).sum(1) / seg_len[j] ** 2
            tj = np.where((j == 0) & (t_raw < 0) | (j == len(a) - 1) & (t_raw > 1), t_raw, t[r, j])
            cross = d[j, 0] * (qq[:, 1] - a[j, 1]) - d[j, 1] * (qq[:, 0] - a[j, 0])
            out_u[i:i + 20000] = -cross / seg_len[j]                  # signed perpendicular, + = outwards
            out_v[i:i + 20000] = s0[j] + tj * seg_len[j]
        return out_u, out_v
    return uv


def band_xy(line, midline, mirror, u, v, step):
    """Inverse of band_uv: band coordinates -> world xy."""
    t = np.gradient(line, axis=0)
    t /= np.linalg.norm(t, axis=1)[:, None]
    outward = np.c_[t[:, 1], -t[:, 0]]
    k = np.clip(v / step, 0, len(line) - 1)
    i0 = np.floor(k).astype(int)
    i1 = np.minimum(i0 + 1, len(line) - 1)
    f = (k - i0)[:, None]
    c = line[i0] * (1 - f) + line[i1] * f
    o = outward[i0] * (1 - f) + outward[i1] * f
    o /= np.linalg.norm(o, axis=1)[:, None]
    xy = c + o * u[:, None]
    if mirror:
        xy[:, 0] = 2 * midline - xy[:, 0]
    return xy


def cut_niches(body, cfg, depsgraph):
    """Cut both plates' niches into `body` in place; returns the band data for place_glyphs."""
    tree = BVHTree.FromObject(body, depsgraph)
    line = band_line(symmetric_rows(tree, cfg), cfg)
    L = len(line) * cfg["line_step"]
    niche = glyphs.niche_sdf(cfg["width"], L, cfg["corner_r"])
    band = {"line": line.tolist(), "length": L, "up": {}}
    for side in SIDES:
        mid = line[len(line) // 2]
        mid_x = mid[0] if side > 0 else 2 * cfg["midline"] - mid[0]
        up = tree.ray_cast(Vector((mid_x, mid[1], 30)), Vector((0, 0, -1)))[1]
        band["up"][side] = list(up)
        stamp.stamp(body, [(niche, -cfg["depth"])], 0.02, band_uv(line, cfg["midline"], side < 0), up,
                    max_edge=cfg["max_edge"])
        tree = BVHTree.FromObject(body, depsgraph)
    return band


def save(band, path):
    with open(path, "w") as f:
        json.dump({"line": band["line"], "length": band["length"],
                   "up": {str(k): v for k, v in band["up"].items()}}, f)


def load(path):
    with open(path) as f:
        band = json.load(f)
    band["up"] = {int(k): v for k, v in band["up"].items()}
    return band


def place_glyphs(tree, band, side, cfg, rng, sink=0.1):
    """Line-glyph solids for one plate, seated on the cut niche floor (tree = BVH of the cut body).
    Returns (world verts N x 3, faces, glyph kinds)."""
    line = np.array(band["line"])
    prims, kinds = glyphs.line_glyphs(cfg["n_glyphs"], cfg["width"], band["length"], cfg["margin"],
                                      cfg["stroke"], rng)
    uvh, faces = glyphs.glyph_solids(prims, cfg["stroke"], -sink, cfg["depth"] - cfg["glyph_top"])
    xy = band_xy(line, cfg["midline"], side < 0, uvh[:, 0], uvh[:, 1], cfg["line_step"])
    up = np.array(band["up"][side])
    out = np.empty((len(uvh), 3))
    for i, ((x, y), h) in enumerate(zip(xy, uvh[:, 2])):
        floor = tree.ray_cast(Vector((x, y, 30)), Vector((0, 0, -1)))[0]
        out[i] = np.array(floor) + up * h
    return out, faces, kinds
