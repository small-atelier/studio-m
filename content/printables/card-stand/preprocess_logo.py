"""
One-off preprocessing (system python3 + PIL/numpy, NOT run inside Blender):
grayscale the source Mythos logo JPG, threshold it to pure black/white
(Otsu) to strip JPEG grey-halo noise around the linework, blur the clean
binary result, then upscale with a smoothing resize. Output feeds
card_stand's image-stamp version as a heightmap.

The blur step matters: the source JPG is only 183x127px, so fine detail
(letter serifs, thin mountain lines) is only 1-2 native pixels wide.
LANCZOS upscaling smooths the RESIZE but can't add real resolution, so a
plain threshold+upscale still reads as small stairsteps once it's a 3D
relief under raking light - showing up as fuzzy/pixelated shadows right
where the detail is finest. Since this gets hand-painted afterward
anyway, a real blur (trading a little fidelity for genuinely smooth
edges) is the right call over chasing more source resolution.
"""

import numpy as np
from PIL import Image, ImageFilter

SRC = "/Users/mannil/Downloads/mythos_liten logga_v3.jpg"
OUT = "/Users/mannil/Desktop/studio-m/TSONS/card_stand/logo_mask.png"
UPSCALE_W = 720  # keeps the ~183:127 aspect ratio
BLUR_RADIUS = 0.5  # at native (183px-wide) resolution, before upscaling


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


def main():
    im = Image.open(SRC).convert("L")
    gray = np.array(im)

    t = otsu_threshold(gray)
    print(f"Otsu threshold: {t}")
    binary = np.where(gray < t, 0, 255).astype(np.uint8)  # ink=0 (dark), bg=255

    bw = Image.fromarray(binary, mode="L")
    bw_blurred = bw.filter(ImageFilter.GaussianBlur(radius=BLUR_RADIUS))
    h = int(UPSCALE_W * bw.height / bw.width)
    bw_smooth = bw_blurred.resize((UPSCALE_W, h), Image.LANCZOS)
    bw_smooth.save(OUT)
    print(f"Saved {OUT} ({bw_smooth.size[0]}x{bw_smooth.size[1]})")


if __name__ == "__main__":
    main()
