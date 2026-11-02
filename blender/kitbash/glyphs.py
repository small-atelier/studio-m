"""
Necron glyphs: procedural line glyphs (the look of the Heavy Destroyer's hull bands) plus the
older pixel-art library, and niche heightmaps.

Line glyphs: a thin baseline runs the length of the niche; each slot along it carries one glyph
built from a small vocabulary - rings, stacked double circles, stems ending in a small ring
("lollipops"), cross bars, C-arcs, ring-in-ring - all drawn at one stroke width. The baseline is
broken inside rings. line_glyphs() gives the primitives; glyph_solids() turns them into closed
solids with vertical walls (placed on the niche floor as separate overlapping shells), and
line_chain() into a signed distance field for 2D previews. niche_sdf() is the niche outline that
stamp.stamp() cuts into the body.

Pixel art: extract_units() splits the source image's glyph columns into single symbols, chain()
stacks them, heightmap() renders a chain at a fixed pixel size.

Pure numpy - load_mask() uses bpy when running inside Blender, PIL otherwise.
"""
import numpy as np

THRESH = 60             # green level counted as glyph
UNIT_ROWS = (5, 10)     # kept unit heights (source pixels): drops fragments and stacked doubles
RAIL_REPEAT = 0.5       # units whose most common row fills more than this share are connector rails
MAX_PIECES = 2          # units in more pieces than this (dots, broken bits) read poorly and print fragile
MIN_LIT = 16            # units with fewer lit pixels are too sparse


def load_mask(path):
    try:
        import bpy
        im = bpy.data.images.load(path)
        im.colorspace_settings.name = 'Non-Color'          # raw 0-255 levels, same as PIL
        w, h = im.size
        px = np.empty(w * h * 4, np.float32)
        im.pixels.foreach_get(px)
        g = px.reshape(h, w, 4)[::-1, :, 1] * 255      # Blender rows start at the bottom
    except ImportError:
        from PIL import Image
        g = np.array(Image.open(path).convert("RGB"))[..., 1].astype(float)
    return g > THRESH


def _runs(flags):
    runs, i = [], 0
    while i < len(flags):
        if flags[i]:
            s = i
            while i < len(flags) and flags[i]:
                i += 1
            runs.append((s, i))
        else:
            i += 1
    return runs


def _pieces(u):
    """8-connected component count of a small bool array."""
    seen = np.zeros_like(u)
    n = 0
    for y, x in zip(*np.nonzero(u)):
        if seen[y, x]:
            continue
        n += 1
        stack = [(y, x)]
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < u.shape[0] and 0 <= nx < u.shape[1] and u[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
    return n


def extract_units(mask):
    """Unique single symbols, each a bool array trimmed to its rows (column width kept)."""
    units, seen = [], set()
    for x0, x1 in _runs(mask.any(0)):
        col = mask[:, x0:x1]
        c = (x1 - x0 - 1) / 2
        off_centre = np.abs(np.arange(x1 - x0) - c) > 1
        body = (col & off_centre).any(1)             # stem rows light only the centre columns
        for y0, y1 in _runs(body):
            if y0 == 0 or y1 == len(body):          # cut off by the image edge
                continue
            if not UNIT_ROWS[0] <= y1 - y0 <= UNIT_ROWS[1]:
                continue
            u = col[y0:y1]
            _, counts = np.unique(u, axis=0, return_counts=True)
            if counts.max() > RAIL_REPEAT * len(u):
                continue
            if u.sum() < MIN_LIT or _pieces(u) > MAX_PIECES:
                continue
            key = u.tobytes() + bytes(u.shape)
            if key not in seen:
                seen.add(key)
                units.append(u)
    return units


def chain(units, order, stem_rows=2, width=12):
    """Stack units[order] top to bottom, centred in `width` columns, joined by 1px stems."""
    rows = []
    stem = np.zeros((stem_rows, width), bool)
    stem[:, width // 2] = True
    for i, k in enumerate(order):
        u = units[k]
        pad = width - u.shape[1]
        rows.append(np.pad(u, ((0, 0), (pad // 2, pad - pad // 2))))
        if i < len(order) - 1:
            rows.append(stem)
    return np.vstack(rows)


def _blur(a, sigma_px):
    r = max(1, int(3 * sigma_px))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma_px) ** 2)
    k /= k.sum()
    a = np.apply_along_axis(lambda v: np.convolve(np.pad(v, r, mode="edge"), k, "valid"), 0, a)
    return np.apply_along_axis(lambda v: np.convolve(np.pad(v, r, mode="edge"), k, "valid"), 1, a)


def chain_fits(glyph, px_mm, niche_w, niche_l, margin_mm):
    gh, gw = glyph.shape
    return gh * px_mm + 2 * margin_mm <= niche_l and gw * px_mm + 2 * margin_mm <= niche_w


def heightmap(glyph, px_mm, niche_w, niche_l, corner_r, margin_mm, niche_depth, glyph_top,
              res_mm=0.02, smooth_px=0.5):
    """Relief for one niche: 0 outside, -niche_depth on the niche floor, -glyph_top on glyph strokes.

    The niche is a fixed niche_w x niche_l rectangle with corner_r rounded corners; the chain is
    drawn at a fixed px_mm per source pixel, centred, so stroke weight is the same in every niche
    (check chain_fits first). Stroke rounding is smooth_px source pixels.
    Returns a height array [v, u], row 0 = niche top.
    """
    if not chain_fits(glyph, px_mm, niche_w, niche_l, margin_mm):
        raise ValueError(f"chain {glyph.shape} does not fit {niche_w:.2f}x{niche_l:.2f}mm at {px_mm}mm/px")
    up = max(1, int(round(px_mm / res_mm)))
    g = np.kron(glyph.astype(float), np.ones((up, up)))
    g = (_blur(np.pad(g, up), smooth_px * px_mm / res_mm) > 0.5).astype(float)[up:-up, up:-up]
    W, H = int(round(niche_w / res_mm)), int(round(niche_l / res_mm))
    canvas = np.zeros((H, W))
    y0, x0 = (H - g.shape[0]) // 2, (W - g.shape[1]) // 2
    canvas[y0:y0 + g.shape[0], x0:x0 + g.shape[1]] = g
    v, u = np.mgrid[0:H, 0:W].astype(float) + 0.5
    r = corner_r / res_mm
    cu = np.clip(u, r, W - r)                                   # nearest point of the inner rectangle
    cv = np.clip(v, r, H - r)
    niche = (u - cu) ** 2 + (v - cv) ** 2 <= r ** 2
    h = np.where(niche, -niche_depth, 0.0)
    h = np.where(niche & (canvas > 0), -glyph_top, h)
    return _blur(h, 0.04 / res_mm)


GLYPH_KINDS = ("ring", "double", "lollipops", "bar_ring", "c_bar", "ring_ring", "double_bar")


def _glyph_prims(kind, c, S, Hh, rng):
    """Primitives for one glyph centred at slot centre c (along) on the baseline (across = 0).
    S = slot length, Hh = half the usable band height. Returns [('circle', cv, cu, r) |
    ('seg', v0, u0, v1, u1) | ('arc', cv, cu, r, facing)], plus ring interiors that break the baseline."""
    flip = rng.choice((-1, 1))
    if kind == "ring":
        r = 0.40 * S
        return [("circle", c, 0, r)], [(c, 0, r)]
    if kind == "double":
        r = min(0.22 * S, 0.45 * Hh)
        return [("circle", c, r, r), ("circle", c, -r, r)], []
    if kind == "lollipops":
        r = 0.16 * S
        reach = 0.95 * Hh - 2 * r          # stem end; its ring's outer edge lands at 0.95 Hh
        d = 0.18 * S
        return [("seg", c - d, 0, c - d, flip * reach), ("circle", c - d, flip * (reach + r), r),
                ("seg", c + d, 0, c + d, -flip * reach), ("circle", c + d, -flip * (reach + r), r)], []
    if kind == "bar_ring":
        r = 0.24 * S
        return [("seg", c - 0.22 * S, -0.9 * Hh, c - 0.22 * S, 0.9 * Hh), ("circle", c + 0.16 * S, 0, r)], \
               [(c + 0.16 * S, 0, r)]
    if kind == "c_bar":
        r = 0.30 * S
        return [("arc", c - 0.05 * S, 0, r, flip), ("seg", c + flip * 0.32 * S, -0.7 * Hh,
                                                         c + flip * 0.32 * S, 0.7 * Hh)], []
    if kind == "ring_ring":
        r = 0.40 * S
        return [("circle", c, 0, r), ("circle", c, 0, 0.45 * r)], [(c, 0, r)]
    if kind == "double_bar":
        r = min(0.18 * S, 0.4 * Hh)
        return [("circle", c - 0.15 * S, r, r), ("circle", c - 0.15 * S, -r, r),
                ("seg", c + 0.25 * S, -0.8 * Hh, c + 0.25 * S, 0.8 * Hh)], []
    raise ValueError(kind)


def line_glyphs(n, niche_w, niche_l, margin_mm, stroke_mm, rng):
    """Primitives of n line glyphs on a baseline, in niche coordinates (v along from the niche
    top, u across from its centre line), and the glyph kinds used. The baseline comes out as
    segments, broken inside rings."""
    S = (niche_l - 2 * margin_mm) / n
    Hh = niche_w / 2 - margin_mm - stroke_mm / 2
    prims, holes, kinds = [], [], []
    for i in range(n):
        kind = rng.choice([k for k in GLYPH_KINDS if not kinds or k != kinds[-1]])
        kinds.append(kind)
        p, rings = _glyph_prims(kind, margin_mm + (i + 0.5) * S, S, Hh, rng)
        prims += p
        holes += rings
    start = margin_mm
    for cv, _, r in sorted(holes):
        if cv - r > start:
            prims.append(("seg", start, 0.0, cv - r, 0.0))
        start = max(start, cv + r)
    if niche_l - margin_mm > start:
        prims.append(("seg", start, 0.0, niche_l - margin_mm, 0.0))
    return prims, kinds


def line_chain(prims, niche_w, niche_l, stroke_mm, res_mm=0.02):
    """Signed distance (mm) to the stroke edges of `prims`, sampled [v, u] over niche_l x niche_w
    at res_mm (negative = on a stroke) - for 2D previews."""
    W, H = int(round(niche_w / res_mm)), int(round(niche_l / res_mm))
    v, u = (np.mgrid[0:H, 0:W].astype(float) + 0.5) * res_mm
    u = u - niche_w / 2
    dist = np.full(v.shape, np.inf)
    for p in prims:
        if p[0] == "circle":
            _, cv, cu, r = p
            d = np.abs(np.hypot(v - cv, u - cu) - r)
        elif p[0] == "arc":
            _, cv, cu, r, facing = p
            d = np.abs(np.hypot(v - cv, u - cu) - r)
            d = np.where((v - cv) * facing <= 0, d, np.inf)           # half circle opening along +-v
        else:
            _, v0, u0, v1, u1 = p
            dv, du = v1 - v0, u1 - u0
            t = np.clip(((v - v0) * dv + (u - u0) * du) / max(dv * dv + du * du, 1e-12), 0, 1)
            d = np.hypot(v - (v0 + t * dv), u - (u0 + t * du))
        dist = np.minimum(dist, d)
    return dist - stroke_mm / 2


def _ring_band(cv, cu, r_in, r_out, a0, a1, closed, h0, h1, seg_mm):
    """Closed solid of an annulus sector (u, v, h) - full washer when `closed`."""
    n = max(8, int(np.ceil((a1 - a0) * r_out / seg_mm)))
    a = np.linspace(a0, a1, n, endpoint=not closed)
    ring = lambda r, h: [(cu + r * np.sin(t), cv + r * np.cos(t), h) for t in a]
    verts = ring(r_out, h0) + ring(r_out, h1) + ring(r_in, h0) + ring(r_in, h1)
    ob, ot, ib, it = (k * n for k in range(4))
    faces = []
    m = n if closed else n - 1
    for i in range(m):
        j = (i + 1) % n
        faces += [(ob + i, ob + j, ot + j, ot + i), (ib + j, ib + i, it + i, it + j),   # outer / inner wall
                  (ot + i, ot + j, it + j, it + i), (ob + j, ob + i, ib + i, ib + j)]   # top / bottom
    if not closed:
        faces += [(ob, ot, it, ib), (ob + n - 1, ib + n - 1, it + n - 1, ot + n - 1)]  # flat ends
    return verts, faces


def _stadium(v0, u0, v1, u1, half_w, h0, h1, seg_mm):
    """Closed solid of a segment with round ends, half_w wide each side (u, v, h)."""
    ang = np.arctan2(u1 - u0, v1 - v0)
    k = max(4, int(np.ceil(np.pi * half_w / seg_mm)))
    outline = []
    for (cv, cu), base in (((v1, u1), ang - np.pi / 2), ((v0, u0), ang + np.pi / 2)):
        for t in np.linspace(base, base + np.pi, k):
            outline.append((cu + half_w * np.sin(t), cv + half_w * np.cos(t)))
    n = len(outline)
    verts = [(x, y, h0) for x, y in outline] + [(x, y, h1) for x, y in outline]
    faces = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return verts, faces


def glyph_solids(prims, stroke_mm, h0, h1, seg_mm=0.04):
    """Closed solids for every primitive, as one (verts [(u, v, h)], faces) soup of separate shells
    (they overlap, like any multi-part print - the slicer unions them). Walls are vertical in u/v/h."""
    verts, faces = [], []
    w = stroke_mm / 2
    for p in prims:
        if p[0] == "circle":
            _, cv, cu, r = p
            vs, fs = _ring_band(cv, cu, max(r - w, 0.0), r + w, 0, 2 * np.pi, True, h0, h1, seg_mm)
        elif p[0] == "arc":
            _, cv, cu, r, facing = p
            a0 = np.pi / 2 if facing > 0 else -np.pi / 2               # the half with (v - cv) * facing <= 0
            vs, fs = _ring_band(cv, cu, r - w, r + w, a0, a0 + np.pi, False, h0, h1, seg_mm)
        else:
            _, v0, u0, v1, u1 = p
            vs, fs = _stadium(v0, u0, v1, u1, w, h0, h1, seg_mm)
        base = len(verts)
        verts += vs
        faces += [tuple(base + i for i in f) for f in fs]
    return np.array(verts), faces


def niche_sdf(niche_w, niche_l, corner_r, res_mm=0.02):
    """Signed distance (mm) to the edge of a niche_w x niche_l rectangle with corner_r rounded
    corners, sampled [v, u] like line_chain (negative = inside)."""
    W, H = int(round(niche_w / res_mm)), int(round(niche_l / res_mm))
    v, u = (np.mgrid[0:H, 0:W].astype(float) + 0.5) * res_mm
    qu = np.abs(u - niche_w / 2) - (niche_w / 2 - corner_r)
    qv = np.abs(v - niche_l / 2) - (niche_l / 2 - corner_r)
    outside = np.hypot(np.maximum(qu, 0), np.maximum(qv, 0))
    inside = np.minimum(np.maximum(qu, qv), 0)
    return outside + inside - corner_r


if __name__ == "__main__":
    import sys
    from PIL import Image
    src, out = sys.argv[1], sys.argv[2]
    units = extract_units(load_mask(src))
    print(f"{len(units)} units, heights {sorted({u.shape[0] for u in units})}")
    cell = 14
    cols = 10
    rows = (len(units) + cols - 1) // cols
    sheet = np.zeros((rows * cell, cols * cell), np.uint8)
    for i, u in enumerate(units):
        y, x = (i // cols) * cell + 1, (i % cols) * cell + 1
        sheet[y:y + u.shape[0], x:x + u.shape[1]] = u * 255
    Image.fromarray(sheet).resize((cols * cell * 6, rows * cell * 6), Image.NEAREST).save(out)
