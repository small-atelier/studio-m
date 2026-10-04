#!/usr/bin/env python3
"""Portable Hellforge — forge-floor layout plan, v11.

Not a Blender script (no bpy) - plain Python, generates a dimensioned
top-down SVG of the forge floor: every socket, the smelting pool, the
molten channels, hand-tool props, and BOTH cuts - the FDM wedge cut (3
tiles) and the resin quadrant split (4 pieces) - in two different colors,
since the two layers are cut completely differently and that's easy to
lose track of looking at one diagram.

v11 change: this script no longer has its own copy of the socket list,
floor dimensions, or cut geometry - it imports all of it from
forge_floor_data.py, the same module forge_floor_tiles_v3.py (the actual
Blender print geometry) uses. Previously this file kept an independent
duplicate that fell out of sync 3 separate times (v6, v7, v9/v10) as
things moved in the real script. There is now exactly one place any of
this data can be wrong.

Run: python3 blender/hellforge/forge_floor_layout.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from forge_floor_data import (
    ALL_SOCKETS, FURNACE_NAME, SOCKET_GROWTH, FLOOR_W, FLOOR_D,
    WEDGE_CENTER, WEDGE_CUT_BL, WEDGE_CUT_BR, WEDGE_CUT_TOP,
    POOL_OUTLINE, MOLTEN_CHANNELS, PROP_PLACEMENTS, GRATE_RECT,
    RESIN_SPLIT,
)

OUTPUT_PATH = "/Users/mannil/studio-m/blender/hellforge/output/forge_floor_layout.svg"

STEEL_DISC_DIAMETER = 6.0  # SVG annotation only - the real steel disc is sized to the socket in forge_floor_tiles_v3.py

FDM_COLOR = "#b33"     # the 3-wedge cut - structural, load-bearing
RESIN_COLOR = "#2a6fb3"  # the 4-quadrant split - thin decorative skin, no joints needed

SVG_SCALE = 1.5
MARGIN = 60


def render_svg():
    w = max(FLOOR_W * SVG_SCALE + MARGIN * 2, 760)
    h = FLOOR_D * SVG_SCALE + MARGIN * 2 + 100

    def X(x):
        return x * SVG_SCALE + MARGIN

    def Y(y):
        return y * SVG_SCALE + MARGIN

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
             f'viewBox="0 0 {w:.0f} {h:.0f}" font-family="monospace">']
    parts.append(f'<rect width="{w:.0f}" height="{h:.0f}" fill="#faf6ec"/>')

    parts.append(f'<rect x="{X(0):.1f}" y="{Y(0):.1f}" width="{FLOOR_W * SVG_SCALE:.1f}" '
                 f'height="{FLOOR_D * SVG_SCALE:.1f}" fill="none" stroke="#222" stroke-width="2"/>')
    parts.append(f'<text x="{X(10):.1f}" y="{Y(0) - 6:.1f}" font-size="10" fill="#888">BACK</text>')
    parts.append(f'<text x="{X(10):.1f}" y="{Y(FLOOR_D) + 16:.1f}" font-size="10" fill="#888">FRONT (latch side)</text>')

    # --- FDM wedge cut: 3 lines radiating from WEDGE_CENTER ---
    for to_pt, label in [(WEDGE_CUT_BL, "BL"), (WEDGE_CUT_BR, "BR"), (WEDGE_CUT_TOP, "TOP")]:
        parts.append(f'<line x1="{X(WEDGE_CENTER[0]):.1f}" y1="{Y(WEDGE_CENTER[1]):.1f}" '
                     f'x2="{X(to_pt[0]):.1f}" y2="{Y(to_pt[1]):.1f}" '
                     f'stroke="{FDM_COLOR}" stroke-width="2" stroke-dasharray="7,4"/>')
        mx, my = (WEDGE_CENTER[0] + to_pt[0]) / 2, (WEDGE_CENTER[1] + to_pt[1]) / 2
        parts.append(f'<text x="{X(mx)+5:.1f}" y="{Y(my):.1f}" font-size="9" fill="{FDM_COLOR}">FDM {label}</text>')

    # --- resin quadrant split: a plain cross at the floor's center ---
    sx, sy = RESIN_SPLIT
    parts.append(f'<line x1="{X(sx):.1f}" y1="{Y(0):.1f}" x2="{X(sx):.1f}" y2="{Y(FLOOR_D):.1f}" '
                 f'stroke="{RESIN_COLOR}" stroke-width="1.5" stroke-dasharray="3,3"/>')
    parts.append(f'<line x1="{X(0):.1f}" y1="{Y(sy):.1f}" x2="{X(FLOOR_W):.1f}" y2="{Y(sy):.1f}" '
                 f'stroke="{RESIN_COLOR}" stroke-width="1.5" stroke-dasharray="3,3"/>')
    parts.append(f'<text x="{X(sx)+5:.1f}" y="{Y(12):.1f}" font-size="9" fill="{RESIN_COLOR}">RESIN split</text>')

    # --- smelting pool ---
    pool_pts = " ".join(f"{X(px):.1f},{Y(py):.1f}" for px, py in POOL_OUTLINE)
    parts.append(f'<polygon points="{pool_pts}" fill="#f0c896" fill-opacity="0.5" '
                 f'stroke="#c07830" stroke-width="1"/>')

    # --- molten channels ---
    for cx0, cy0, cx1, cy1 in MOLTEN_CHANNELS:
        parts.append(f'<line x1="{X(cx0):.1f}" y1="{Y(cy0):.1f}" x2="{X(cx1):.1f}" y2="{Y(cy1):.1f}" '
                     f'stroke="#c04010" stroke-width="2"/>')

    # --- grate ---
    gx0, gx1, gy0, gy1 = GRATE_RECT
    parts.append(f'<rect x="{X(gx0):.1f}" y="{Y(gy0):.1f}" width="{(gx1-gx0)*SVG_SCALE:.1f}" '
                 f'height="{(gy1-gy0)*SVG_SCALE:.1f}" fill="#888" fill-opacity="0.4" stroke="#444"/>')

    # --- sockets (Furnace drawn distinctly - it's fused, not a plain plug-in model) ---
    for name, cx, cy, d in ALL_SOCKETS:
        r = (d + SOCKET_GROWTH) / 2
        fill = "#e0895a" if name == FURNACE_NAME else "#d8cdb0"
        parts.append(f'<circle cx="{X(cx):.1f}" cy="{Y(cy):.1f}" r="{r * SVG_SCALE:.1f}" '
                     f'fill="{fill}" stroke="#222" stroke-width="1"/>')
        parts.append(f'<circle cx="{X(cx):.1f}" cy="{Y(cy):.1f}" r="{STEEL_DISC_DIAMETER / 2 * SVG_SCALE:.1f}" '
                     f'fill="#555" stroke="none"/>')

    # --- props ---
    for name, px, py, _rot, _rad in PROP_PLACEMENTS:
        parts.append(f'<circle cx="{X(px):.1f}" cy="{Y(py):.1f}" r="3" fill="#3a7d3a"/>')

    LABEL_BELOW = {FURNACE_NAME}
    for name, cx, cy, d in ALL_SOCKETS:
        if name.startswith("Infernal Cohort"):
            continue
        if name in LABEL_BELOW:
            y = Y(cy) + (d / 2) * SVG_SCALE + 16
        else:
            y = Y(cy) - (d / 2) * SVG_SCALE - 6
        parts.append(f'<text x="{X(cx):.1f}" y="{y:.1f}" '
                     f'text-anchor="middle" font-size="11" fill="#222">{name} ({d:g}mm)</text>')

    legend_y = FLOOR_D + 40
    parts.append(f'<text x="{X(20):.1f}" y="{Y(legend_y):.1f}" font-size="11" fill="#222">'
                 f'&#9679; 10x Infernal Cohort (28.5mm), scattered</text>')
    parts.append(f'<text x="{X(20):.1f}" y="{Y(legend_y+16):.1f}" font-size="11" fill="#222">'
                 f'tan = miniature socket, orange = Roaring Furnace (fused, still socketed - see the post)</text>')
    parts.append(f'<text x="{X(20):.1f}" y="{Y(legend_y+32):.1f}" font-size="11" fill="{FDM_COLOR}">'
                 f'&#9472;&#9472; FDM wedge cut (3 structural tiles, dovetail-jointed)</text>')
    parts.append(f'<text x="{X(20):.1f}" y="{Y(legend_y+48):.1f}" font-size="11" fill="{RESIN_COLOR}">'
                 f'&#9472;&#9472; resin quadrant split (4 decorative pieces, plain butt seam)</text>')

    dim_y = FLOOR_D + 55
    parts.append(f'<line x1="{X(0):.1f}" y1="{Y(dim_y):.1f}" x2="{X(FLOOR_W):.1f}" y2="{Y(dim_y):.1f}" '
                 f'stroke="#222" stroke-width="1"/>')
    parts.append(f'<text x="{X(FLOOR_W / 2):.1f}" y="{Y(dim_y) + 16:.1f}" text-anchor="middle" '
                 f'font-size="13" fill="#222">{FLOOR_W:.0f}mm overall</text>')

    parts.append('</svg>')
    return "\n".join(parts)


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(render_svg())
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
