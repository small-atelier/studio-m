"""
Sylvaneth seed icon (system python3 + Pillow, NOT Blender) - a generated source image for the
tracer, not a trace of existing art. A teardrop, tip up, with a stylized swirl cut out of it: one
open spiral filling the drop's round bottom, its outer end sweeping up into a tail that tapers
toward the tip. Printed as an inlay, the drop is the inlay colour and the swirl shows the base
colour through it.

Bold enough for small inlays, unlike the traced glade glyphs: at 12mm tall, under 0.5% of the
drop's ink and of the swirl's gap is thinner than 0.6mm; 9.5mm is the floor (~8% of the drop's ink
between the spiral turns drops under 0.6mm there).

Drawn at 2x and downsampled - a pure black/white image gives the tracer's Otsu threshold nothing
between its two levels, the anti-aliased edges do.

Run (writes the source, then trace it with the rest):
  python3 draw_sylvaneth_seed.py
  python3 extract_icon_contours.py ../assets/icons
"""
import math
import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "icons", "source",
                   "sylvaneth_seed.png")
N = 2400                # canvas px, before the 2x downsample
DROP_W = 0.95           # drop width factor (max width ~0.66 of the height)
M = 1.4                 # teardrop sharpness
STROKE = 0.085          # swirl stroke, in drop heights (~0.8mm at a 9.5mm icon)
TAIL_END = 0.75         # tail stroke at the tip end, as a fraction of STROKE
TURNS = 1.1
R_OUT, R_IN = 0.21, 0.03
CENTER = (0.0, -0.13)   # spiral center, in the drop's round bottom


def drop(t):
    """Teardrop outline point, t in 0..2pi, tip at t=0 -> top; unit height, centered."""
    return 0.5 * DROP_W * math.sin(t) * math.sin(t / 2) ** M, 0.5 * math.cos(t)


def bezier(p0, p1, p2, p3, n=80):
    out = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        out.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return out


def main():
    outline = [drop(2 * math.pi * i / 400) for i in range(400)]
    # spiral from the inside out, counter-clockwise, ending on the right side heading up
    th_max = 2 * math.pi * TURNS
    spiral = []
    for i in range(241):
        r = R_IN + (R_OUT - R_IN) * i / 240
        a = th_max * i / 240 - th_max      # end angle 0 = right side
        spiral.append((CENTER[0] + r * math.cos(a), CENTER[1] + r * math.sin(a)))
    end = spiral[-1]
    # tail: from the spiral's outer end, sweeping up to just under the tip
    tail = bezier(end, (end[0], end[1] + 0.16), (0.06, 0.22), (0.0, 0.34))

    k = N * 0.92                           # unit height -> px

    def xf(p):
        return N / 2 + p[0] * k, N / 2 - p[1] * k

    im = Image.new("L", (N, N), 255)
    d = ImageDraw.Draw(im)
    d.polygon([xf(p) for p in outline], fill=0)

    def brush(path, w0, w1):
        """Round brush along the path, stroke tapering linearly from w0 to w1."""
        for i, p in enumerate(path):
            rw = (w0 + (w1 - w0) * i / (len(path) - 1)) * k / 2
            x, y = xf(p)
            d.ellipse((x - rw, y - rw, x + rw, y + rw), fill=255)

    brush(spiral, STROKE, STROKE)
    brush(tail, STROKE, STROKE * TAIL_END)
    im.resize((N // 2, N // 2), Image.LANCZOS).save(OUT)
    print(f"wrote {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
