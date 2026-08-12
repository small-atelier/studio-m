---
title: "A Business-Card Stand for the Neighbours"
date: 2026-08-12
draft: false
tags: ["3d-printing", "resin", "blender", "python"]
---

{{< lead >}}
A new store, [Mythos](https://mythos.nu/), opened up in the neighbourhood — wanted to make them something nice for the counter. Also a good excuse to practice two techniques I hadn't done before: stamping a logo in from a raster image, and a genuinely zero-support resin print.
{{< /lead >}}

---

## What it is

A two-part stand for the counter: a holder with three upright slots for stacks of ~50 business cards each (65×65mm cards), and a backplate carrying the Mythos logo and wordmark in relief. Sized for the Anycubic Photon Mono 2's build volume, printed in resin.

{{< carousel images="gallery/*" aspectRatio="4-3" interval="3000" >}}

---

## Technique 1: stamping a logo in from a photo

The source was just a small JPG of the Mythos logo. Getting from that to a clean printable relief took two passes:

**Attempt 1 (v3) — heightfield.** Threshold the image to pure black/white, blur it smooth, then displace the backplate's front face per-pixel from that mask as a continuous heightfield. Technically worked, but under raking light the fine linework (letter serifs, thin mountain lines) still read as fuzzy, slightly stair-stepped shading — the source JPG is only 183×127px, so there was never much real detail to work with, and upscaling can't add it back.

**Attempt 2 (v4/v5) — vector contours.** Instead of a per-pixel heightmap, run marching squares over the same thresholded mask to get clean closed polygons, then extrude those as a flat plateau with sharp 90° walls. This needed handling letters with counters correctly (the hole inside an "O" has to be tagged as a hole, not another shape) — done by testing containment from a point just inside each contour's own boundary, not a naive centroid, which was misreading the ring shape of an "O" as a hole in itself.

Flat-plateau-with-sharp-edges turned out to be the better call anyway, independent of the resolution problem: a crisp edge is much easier to hand-paint up to than a soft gradient.

{{< include-code path="blender/card-stand/preprocess_logo.py" lang="python" >}}

{{< include-code path="blender/card-stand/extract_logo_contours_v5.py" lang="python" >}}

---

## Technique 2: zero-support printing

Earlier versions stood the backplate on edge to fit the printer's bed, which meant supports under the overhanging relief. v5 instead prints it flat on its back — every raised feature (the logo, the wordmark, the decorative ridge) projects in the same direction, straight up off the plate, so nothing overhangs and nothing needs support material at all. The tradeoff is bed footprint: flat-on-back only works because the backplate was already narrow enough (70 × 138mm) to fit the Photon Mono 2's 89.6 × 143.4mm bed directly.

---

## Iteration history

| Version | Change |
|---|---|
| v1 | Hand-modelled bold logo relief (not traced from the source image), 3-wide sloped card trays, split into 4 separate prints to fit the bed |
| v2 | Bolder revision of v1's hand-modelled relief |
| v3 | Switched to image-stamp: real logo traced in as a per-pixel heightfield relief instead of hand-modelled |
| v4 | Redesigned holder — cards stand upright in a 3-slot "comb" instead of sloped trays, one print instead of four; logo relief switched from heightfield to flat vector-contour plateau with sharp edges |
| v5 | Backplate reoriented to print flat on its back — zero supports; logo mask re-cropped and cleaned, finer contour simplification for smoother curves |

---

## Lessons from printing

The flat-on-back zero-support print worked, but the surface still needed sanding after support removal to look properly smooth — "no supports" isn't the same as "no finishing work."

The wordmark didn't survive: it was real vector text unioned straight onto the backplate's flat face, and the O and S both broke off during support removal/sanding. Baskerville's stroke width at that size just wasn't enough material to survive being handled, especially on those two letters' thin curves.

{{< figure src="text-plate.png" caption="Standalone replacement plate — thicker letters, deep-embedded into a proper 2mm backing rather than grazing a flat face" >}}

Fix: pull the wordmark off the backplate entirely and make it its own small glued-on part — a 2mm backing plate with the letters raised 1.8mm and embedded 1.2mm into the plate itself, a real union with volume behind it rather than a thin surface graze. Letters also needed to be genuinely thicker, not just bigger — done with Blender's curve outline offset, which pushes every stroke edge outward (so O's ring and S's curve both gain real wall thickness) rather than scaling the whole glyph up proportionally thin-but-bigger. That offset has a ceiling, though: past ~0.13mm it self-intersects on O and S's tight curves and the boolean union silently collapses most of the letterforms — caught by checking the mesh volume before and after (it drops from ~3000mm³ to ~200mm³ once it happens). 0.12mm landed comfortably inside the safe range.

Plan is to file the broken text off the existing backplate print and glue this plate on in whatever spot looks right, rather than reprinting the whole backplate.

---

## Downloads

The Mythos logo makes these specific to that store, but figured I'd host the files anyway in case the owner wants to reprint or tweak it themselves at some point:

- [Backplate](backplate.stl)
- [Card holder](card-holder.stl)
- [Text plate](text-plate.stl) — the bolder-lettered replacement, see above

---

Cards stand freely in the slots, no glue needed there — just the backplate-to-holder tenon joint. Handed over, hopefully useful for the counter.
