"""
Vector-contour extraction (system python3 + skimage, NOT Blender) for the
Khorne token/box icons - same marching-squares-on-binary-mask approach as
card-stand/extract_logo_contours_v5.py (see that file's docstring for why:
clean closed polygons directly from a mask, holes handled by centroid-
containment rather than trusting find_contours' winding convention).

Traces the main icons:
  - khorn_icon.jpg -> the Khorne rune (lid top, Rend tokens, damage trays)
  - dice_roll.png  -> two tumbling dice (lid inside face - dice-tray hint)

Also traces the card-well floor labels (cards.png, one face cropped from
dice.png) - see SOURCES.

Output per icon is {"aspect": h/w, "polygons": [...]}, points normalized to
the icon's own bounding box (0..1, v flipped so it increases upward) - the
build scripts scale each into whatever footprint they need.
"""

import json
import os
import numpy as np
from PIL import Image, ImageFilter
from skimage import measure, morphology
from shapely.geometry import Polygon

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Per icon: source file, optional crop box (l, t, r, b) in source px, upscale factor (small
# sources trace too coarse - circles come out as polygons), ink growth in source px
# (dilates the dark ink before tracing - line-art strokes of ~2px land at ~0.3mm at print
# size, under a 0.4mm nozzle), and a min hole area in traced px (holes smaller than this are
# filled - drops the speckle left when growth closes up cards.png's crosshatch cells).
SOURCES = {
    "khorne": {"path": "khorn_icon.jpg"},
    "dice_roll": {"path": "dice_roll.png", "grow_px": 3},
    "cards": {"path": "cards.png", "upscale": 4, "grow_px": 2, "min_hole_px": 6400.0},
    "die_five": {"path": "dice.png", "crop": (118, 8, 217, 108), "upscale": 4, "grow_px": 2},
}
OUT_DIR = SCRIPT_DIR

BLUR_RADIUS = 0.5
SIMPLIFY_TOL = 0.6      # in source pixels - sub-pixel on the 1440px rune, keeps dice_roll's
                         # (447px) thin motion-line strokes from collapsing
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


def trace(src_path, crop=None, upscale=1, grow_px=0, min_hole_px=0.0):
    im = Image.open(src_path).convert("L")
    if crop:
        im = im.crop(crop)
    if upscale > 1:
        im = im.resize((im.width * upscale, im.height * upscale), Image.BICUBIC)
    gray = np.array(im)
    if grow_px:
        # grey erosion = grow the dark ink; round kernel, a square one turns pips octagonal
        gray = morphology.erosion(gray, morphology.disk(grow_px * upscale))
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

    kept = [(poly, is_hole) for poly, is_hole in tagged
            if not (is_hole and Polygon(poly).area < min_hole_px)]

    # Normalize to the icon's own bounding box, not the source canvas - khorn_icon.jpg has
    # ~23% whitespace margin per side, so canvas-normalized UVs would render the icon small
    # inside whatever footprint the build script asks for. Aspect (h/w) is stored alongside so
    # the build scripts don't need a hand-maintained ICON_ASPECT per source.
    xs = [x for poly, _ in kept for x, _ in poly]
    ys = [y for poly, _ in kept for _, y in poly]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    bw, bh = x1 - x0, y1 - y0

    polygons_out = []
    for poly, is_hole in kept:
        pts_uv = [[(x - x0) / bw, 1.0 - (y - y0) / bh] for (x, y) in poly]
        polygons_out.append({"points": pts_uv, "hole": is_hole})
    return {"aspect": bh / bw, "polygons": polygons_out}


def main():
    for name, cfg in SOURCES.items():
        contours = trace(os.path.join(SCRIPT_DIR, "source", cfg["path"]), cfg.get("crop"),
                         cfg.get("upscale", 1), cfg.get("grow_px", 0), cfg.get("min_hole_px", 0.0))
        out_path = os.path.join(OUT_DIR, f"{name}_contours.json")
        with open(out_path, "w") as f:
            json.dump(contours, f)
        n_holes = sum(1 for p in contours["polygons"] if p["hole"])
        print(f"{name}: saved {len(contours['polygons'])} contours ({n_holes} holes, "
              f"aspect h/w={contours['aspect']:.3f}) to {out_path}")


if __name__ == "__main__":
    main()
