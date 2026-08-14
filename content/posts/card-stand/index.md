---
title: "A Business-Card Stand for the Neighbours"
date: 2026-08-12
draft: false
tags: ["3d-printing", "resin", "blender", "python"]
---

{{< lead >}}
A new store, [Mythos](https://mythos.nu/), opened up in the neighbourhood — wanted to make them something nice for the counter. Also, a good excuse to practice two techniques I hadn't done before: stamping a logo in from a raster image, and a genuinely zero-support resin print.
{{< /lead >}}

---

## What it is

A two-part stand for the counter: a holder with three upright slots for stacks of ~50 business cards each (65×65mm cards), and a backplate carrying the Mythos logo and wordmark in relief. Sized for the Anycubic Photon Mono 2's build volume, printed in resin.

{{< carousel images="gallery/*" aspectRatio="4-3" interval="3000" >}}

---

## Technique 1: stamping a logo in from a photo

The source was just a small JPG of the Mythos logo. Getting from that to a clean printable relief took two passes:

**First attempt — heightfield.** Threshold the image to pure black/white, blur it smooth, then displace the backplate's front face per-pixel from that mask as a continuous heightfield. Technically worked, but under raking light the fine linework (letter serifs, thin mountain lines) still read as fuzzy, slightly stair-stepped shading — the source JPG is only 183×127px, so there was never much real detail to work with, and upscaling can't add it back.

**Second attempt — vector contours.** Instead of a per-pixel heightmap, run marching squares over the same thresholded mask to get clean closed polygons, then extrude those as a flat plateau with sharp 90° walls. This needed handling letters with counters correctly — the hole inside an "O" has to be tagged as a hole, not read as its own separate shape.

Flat-plateau-with-sharp-edges turned out to be the better call anyway, independent of the resolution problem: a crisp edge is much easier to hand-paint up to than a soft gradient.

{{< include-code path="blender/card-stand/preprocess_logo.py" lang="python" >}}

{{< include-code path="blender/card-stand/extract_logo_contours_v5.py" lang="python" label="extract_logo_contours.py" >}}

---

## Technique 2: zero-support printing

Earlier versions stood the backplate on edge to fit the printer's bed, which meant supports under the overhanging relief. v5 instead prints it flat on its back — every raised feature (the logo, the wordmark, the decorative ridge) projects in the same direction, straight up off the plate, so nothing overhangs and nothing needs support material at all. The tradeoff is bed footprint: flat-on-back only works because the backplate was already narrow enough (70 × 138mm) to fit the Photon Mono 2's 89.6 × 143.4mm bed directly.

{{< include-code path="blender/card-stand/card_stand_v5_flat_sharp_logo.py" lang="python" label="backplate_and_holder.py" >}}

---

## How it went

The flat-on-back zero-support print worked, but the surface still needed sanding after support removal to look properly smooth — "no supports" isn't the same as "no finishing work."

The wordmark didn't survive first time round: real vector text grazing the flat face didn't have enough material behind thin letters like O and S to survive handling. First fix was a standalone glue-on plate with thicker, deeper-embedded letters (see gallery above) — glued on, it looked rough, so reprinted the whole backplate instead with the fix baked straight in.

{{< include-code path="blender/card-stand/text_plate_v1.py" lang="python" label="text_plate.py" >}}

---

## Downloads

The Mythos logo makes these specific to that store, but figured I'd host the files anyway in case the owner wants to reprint or tweak it themselves at some point:

- [Backplate](backplate.stl)
- [Card holder](card-holder.stl)
- [Text plate](text-plate.stl) — the bolder-lettered replacement, see above
- [Backplate + holder script](backplate_and_holder.py) — builds both STLs above
- [Text plate script](text_plate.py)
- [Logo preprocessing script](preprocess_logo.py)
- [Logo contour extraction script](extract_logo_contours.py)

---

Cards stand freely in the slots, no glue needed there — just the backplate-to-holder tenon joint. Handed over, hopefully useful for the counter.
