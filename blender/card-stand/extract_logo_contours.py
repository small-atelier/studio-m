"""
Vector-contour extraction (system python3 + skimage, NOT Blender) for the
flat/sharp-edge stamp: marching squares on the (lightly blurred) binary
mask gives clean closed polygons directly, instead of a per-pixel
heightmap - the right tool now that the design is "flat plateau, sharp
90-degree walls" rather than a continuous relief. Output feeds
card_stand_v4's build_logo_stamp.

Handles letters with counters (the "O" in MYTHOS) - each contour is
tagged as an outer shape or a hole by centroid-containment (odd number
of enclosing polygons = hole), not by trusting find_contours' winding
convention, which is easy to get backwards from memory.
"""

import json
import numpy as np
from PIL import Image, ImageFilter
from skimage import measure

SRC = "/Users/mannil/Downloads/mythos_liten logga_v3.jpg"
OUT = "/Users/mannil/Desktop/studio-m/TSONS/card_stand/logo_contours.json"
BLUR_RADIUS = 0.5      # same value that fixed the heightmap's fuzzy edges - smooths the
                        # marching-squares curves too, not just a heightmap gradient
SIMPLIFY_TOL = 1.2      # pixels, native (183px-wide) resolution
MIN_AREA_PX = 3.0       # drop degenerate slivers (thin decorative lines simplified to ~nothing)
ICON_ROW_FRAC_MAX = 0.70   # everything below this row fraction is the MYTHOS wordmark - excluded
                           # here and rebuilt as real vector text in a matching font instead of
                           # traced from 183x127px source pixels (see build_logo_text in Blender)


def otsu_threshold(gray):
    hist, _ = np.histogram(gray, bins=256, range=(0, 256))
    total = gray.size
    sum_all = np.dot(np.arange(256), hist)
    sum_bg, weight_bg, best_var, best_t = 0.0, 0, -1.0, 128
    for t in range(256):
        weight_bg += hist[t]
        if weight_bg == 0:
            continue
        weight_fg = total - weight_bg
        if weight_fg == 0:
            break
        sum_bg += t * hist[t]
        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_all - sum_bg) / weight_fg
        var_between = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if var_between > best_var:
            best_var, best_t = var_between, t
    return best_t


def point_in_polygon(px, py, poly):
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > py) != (yj > py):
            x_cross = (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi
            if px < x_cross:
                inside = not inside
        j = i
    return inside


def interior_probe_point(poly, epsilon=0.5):
    """A point guaranteed to be JUST inside poly, near its own boundary -
    NOT the naive vertex-average centroid, which for a ring shape (the
    outer edge of a letter like "O") lands in the middle of its own
    counter/hole rather than in the actual ink. That bug showed up as
    the O's outer boundary getting misclassified as a hole itself,
    because its centroid tested positive for "inside" the O's separate
    inner-counter contour."""
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        length = (dx ** 2 + dy ** 2) ** 0.5
        if length < 1e-9:
            continue
        mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        nx, ny = -dy / length, dx / length
        for sign in (1, -1):
            px, py = mx + sign * nx * epsilon, my + sign * ny * epsilon
            if point_in_polygon(px, py, poly):
                return px, py
    return (sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n)


def main():
    im = Image.open(SRC).convert("L")
    gray = np.array(im)
    t = otsu_threshold(gray)
    binary = np.where(gray < t, 255, 0).astype(np.uint8)  # ink=255 (foreground)

    bw = Image.fromarray(binary, mode="L")
    bw_blurred = bw.filter(ImageFilter.GaussianBlur(radius=BLUR_RADIUS))
    arr = np.array(bw_blurred).astype(np.float64)
    h, w = arr.shape

    raw_contours = measure.find_contours(arr, level=127.5)
    raw_polys = []
    for c in raw_contours:
        simplified = measure.approximate_polygon(c, tolerance=SIMPLIFY_TOL)
        if len(simplified) < 3:
            continue
        poly = [(col, row) for row, col in simplified]  # (x, y) pixel space
        area = 0.5 * abs(sum(
            poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
            for i in range(len(poly))
        ))
        if area < MIN_AREA_PX:
            continue  # degenerate sliver from simplifying a very thin decorative line
        if min(y for _, y in poly) / h > ICON_ROW_FRAC_MAX:
            continue  # the wordmark - rebuilt separately as real text
        raw_polys.append(poly)

    tagged = []
    for i, poly in enumerate(raw_polys):
        cx, cy = interior_probe_point(poly)
        contained_count = sum(
            1 for j, other in enumerate(raw_polys) if i != j and point_in_polygon(cx, cy, other)
        )
        tagged.append((poly, contained_count % 2 == 1))

    polygons_out = []
    for poly, is_hole in tagged:
        pts_uv = [[x / w, 1.0 - y / h] for (x, y) in poly]  # v flipped so it increases upward
        polygons_out.append({"points": pts_uv, "hole": is_hole})

    with open(OUT, "w") as f:
        json.dump(polygons_out, f)
    n_holes = sum(1 for p in polygons_out if p["hole"])
    print(f"Saved {len(polygons_out)} contours ({n_holes} holes) to {OUT}")


if __name__ == "__main__":
    main()
