"""
Vector-contour extraction (system python3 + skimage, NOT Blender) for the
Hashut token icons - same marching-squares-on-binary-mask approach as
card-stand/extract_logo_contours_v5.py (see that file's docstring for why:
clean closed polygons directly from a mask, holes handled by centroid-
containment rather than trusting find_contours' winding convention).

Traces both source icons in one pass:
  - rune_hashut.jpeg -> the V/E glyph (Desolation Token icon)
  - bull_hashut.png  -> the bull skull (Daemonic Power Point icon)

Output is normalized UV points (0..1, v flipped so it increases upward) -
build_tokens.py scales each into whatever footprint it needs.
"""

import json
import os
import numpy as np
from PIL import Image, ImageFilter
from skimage import measure
from shapely.geometry import Polygon

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES = {
    "rune": os.path.join(SCRIPT_DIR, "source", "rune_hashut.jpeg"),
    "bull": os.path.join(SCRIPT_DIR, "source", "bull_hashut.png"),
}
OUT_DIR = SCRIPT_DIR

BLUR_RADIUS = 0.5
SIMPLIFY_TOL = 0.6      # source icons are small (192-215px) - a touch looser than v5's 0.4
                         # (traced from a much bigger 720px source) so noise doesn't survive
MIN_AREA_PX = 3.0


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


def trace(src_path):
    im = Image.open(src_path).convert("L")
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
        poly = [(col, row) for row, col in simplified]

        # Marching-squares + Douglas-Peucker simplification can (rarely) leave a
        # self-intersecting "bowtie" ring - confirmed via shapely on bull_hashut.png's
        # main head contour (crossing at ~(0.96, 0.66) in UV). Fatal downstream: the
        # EXACT boolean solver silently corrupts geometry when unioning/differencing a
        # self-intersecting piece (see feedback_blender_boolean_fragility memory) -
        # repair with a zero-width buffer, which for this kind of self-touching ring
        # just splits it into its non-overlapping lobes.
        shp = Polygon(poly)
        if not shp.is_valid:
            shp = shp.buffer(0)
        if shp.is_empty:
            continue
        repaired_rings = ([list(shp.exterior.coords)[:-1]] if shp.geom_type == "Polygon"
                           else [list(g.exterior.coords)[:-1] for g in shp.geoms])

        for ring in repaired_rings:
            area = 0.5 * abs(sum(
                ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1]
                for i in range(len(ring))
            ))
            if area < MIN_AREA_PX:
                continue
            raw_polys.append(ring)

    tagged = []
    for i, poly in enumerate(raw_polys):
        cx, cy = interior_probe_point(poly)
        contained_count = sum(
            1 for j, other in enumerate(raw_polys) if i != j and point_in_polygon(cx, cy, other)
        )
        tagged.append((poly, contained_count % 2 == 1))

    polygons_out = []
    for poly, is_hole in tagged:
        pts_uv = [[x / w, 1.0 - y / h] for (x, y) in poly]
        polygons_out.append({"points": pts_uv, "hole": is_hole})
    return polygons_out


def main():
    for name, src in SOURCES.items():
        contours = trace(src)
        out_path = os.path.join(OUT_DIR, f"{name}_contours.json")
        with open(out_path, "w") as f:
            json.dump(contours, f)
        n_holes = sum(1 for p in contours if p["hole"])
        print(f"{name}: saved {len(contours)} contours ({n_holes} holes) to {out_path}")


if __name__ == "__main__":
    main()
