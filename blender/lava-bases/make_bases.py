"""Organic kidney/blob base outlines: true-size SVG cut files + a dimensioned preview SVG per shape.

Usage: python3 make_bases.py <cut-file dir> <preview dir>
"""
import math, sys, os

OUT, PREVIEW = sys.argv[1], sys.argv[2]
N = 360  # outline samples

# name, width, height (mm), harmonics [(k, amp, phase)], bites [(angle_deg, depth, width_rad)]
SHAPES = [
    ("large-a", 220, 160, [(2, .06, .4), (3, .05, 1.9), (4, .025, .7)], [(80, .62, .52)]),
    ("large-b", 220, 160, [(2, .05, 2.1), (3, .06, .3), (5, .02, 1.2)], [(250, .58, .50), (20, .10, .35)]),
    ("small-a", 140, 100, [(2, .05, 1.1), (3, .05, 2.6), (4, .02, .2)], [(200, .60, .52)]),
    ("small-b", 140, 100, [(2, .06, 2.9), (3, .04, 1.4), (5, .02, .5)], [(300, .55, .50)]),
]

def outline(w, h, harm, bites):
    pts = []
    for i in range(N):
        t = 2 * math.pi * i / N
        # superellipse base (rounder-cornered than an ellipse)
        c, s = math.cos(t), math.sin(t)
        n = 2.6
        r = (abs(c) ** n + abs(s) ** n) ** (-1 / n)
        r *= 1 + sum(a * math.cos(k * t + p) for k, a, p in harm)
        for ang, depth, wid in bites:
            d = math.atan2(math.sin(t - math.radians(ang)), math.cos(t - math.radians(ang)))
            r *= 1 - depth * math.exp(-(d / wid) ** 2)
        pts.append((r * c, r * s))
    # circular moving average rounds the bottom of each bite (no sharp tips to cut)
    k = 14
    pts = [(sum(pts[(i + j) % N][0] for j in range(-k, k + 1)) / (2 * k + 1),
            sum(pts[(i + j) % N][1] for j in range(-k, k + 1)) / (2 * k + 1)) for i in range(N)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    return [((x - x0) / (x1 - x0) * w, (y - y0) / (y1 - y0) * h) for x, y in pts]

def path_d(pts, ox=0, oy=0):
    return "M" + " L".join(f"{x+ox:.2f},{y+oy:.2f}" for x, y in pts) + " Z"

shapes = [(n, w, h, outline(w, h, hm, b)) for n, w, h, hm, b in SHAPES]

# true-size cut files: 0.1mm red hairline, mm units
for n, w, h, pts in shapes:
    with open(os.path.join(OUT, f"base-{n}.svg"), "w") as f:
        f.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}">\n'
                f'  <path d="{path_d(pts)}" fill="none" stroke="#ff0000" stroke-width="0.1"/>\n</svg>\n')

# previews: mid-grey strokes and text read on both light and dark themes, width arrow below, height arrow left
M = 22
for n, w, h, pts in shapes:
    W, H = w + 2 * M, h + 2 * M
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W*3}" height="{H*3}" viewBox="0 0 {W} {H}" font-family="sans-serif">',
           '<defs><marker id="a" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">'
           '<path d="M0,0 L10,5 L0,10 z" fill="#9ca3af"/></marker></defs>',
           f'<path d="{path_d(pts, M, M)}" fill="#b7895a" fill-opacity="0.55" stroke="#8b929c" stroke-width="1.2"/>',
           f'<line x1="{M}" y1="{M+h+7}" x2="{M+w}" y2="{M+h+7}" stroke="#9ca3af" stroke-width="0.8" marker-start="url(#a)" marker-end="url(#a)"/>',
           f'<text x="{M+w/2}" y="{M+h+18}" fill="#8b929c" font-size="9" text-anchor="middle">{w} mm</text>',
           f'<line x1="{M-7}" y1="{M}" x2="{M-7}" y2="{M+h}" stroke="#9ca3af" stroke-width="0.8" marker-start="url(#a)" marker-end="url(#a)"/>',
           f'<text x="{M-11}" y="{M+h/2}" fill="#8b929c" font-size="9" text-anchor="middle" transform="rotate(-90 {M-11} {M+h/2})">{h} mm</text>',
           '</svg>']
    open(os.path.join(PREVIEW, f"base-{n}.svg"), "w").write("\n".join(out))
