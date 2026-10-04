---
title: "Dice Tower & Tray Set — Mythos Edition"
date: 2026-09-22
draft: false
tags: ["3d-printing", "blender", "python", "multi-material"]
---

{{< lead >}}
Three pieces meant as one set — a plain tray, a tray with a raised lip, and a low castle-style tray — each getting the Mythos treatment: the sun/mountain/moon logo and wordmark recessed into both the top and the bottom, in a second color. This post covers the first one, the plain tray; the other two are still ahead.
{{< /lead >}}

{{< carousel images="gallery/*" aspectRatio="1-1" interval="3000" >}}

---

## Based on

Not built from scratch - starting from three existing MakerWorld designs and adding the Mythos branding on top:

- **[Dice Tray](https://makerworld.com/en/models/558989-dice-tray#profileId-491370)** by [Speedygold789](https://makerworld.com/en/@Speedygold789) - the plain tray this post covers. Licensed [CC BY-NC-SA](https://creativecommons.org/licenses/by-nc-sa/4.0/) - credit to Speedygold789 for the original design; the remixed files below carry the same license.
- **[Castle Style Dice Tray](https://makerworld.com/en/models/1521948-castle-style-dice-tray#profileId-1594982)** by [Hifisch360](https://makerworld.com/en/@Hifisch360) - the low-castle variant, still to come.
- **[Fantasy Tree Dice Tower](https://makerworld.com/en/models/2231739-fantasy-tree-dice-tower#profileId-2428507)** by [3DGEPRINTNL](https://makerworld.com/en/@3DGEPRINTNL) - the tower that feeds both trays, still to come.

The castle tray and the tree tower are both published under MakerWorld's Standard Digital File License, which - unlike the plain tray's CC BY-NC-SA - explicitly rules out sharing or hosting any derivative of the object elsewhere. So those two get printed and written up here same as any other build, credited and linked back to the originals, but no remixed STL of either gets published on this site.

## Mythos, top and bottom

Same recess + insert technique as the [combat-modifier tokens]({{< ref "/posts/combat-modifier-tokens" >}}) and the [measuring gauges]({{< ref "/posts/measuring-gauges" >}}) - a shallow pocket cut into the print, a matching insert dropped in for the second color - just aimed at someone else's mesh instead of one built from scratch here, and doubled up: one pocket cut into the top of the main basin floor, a second cut into the underside, with a 1mm solid membrane left between them in the 3mm floor. The base tray stays a complete, structurally sound single-color part on its own, before either insert goes in.

The bottom pocket's icon and wordmark are built from a **mirrored** contour - the same trick the tokens' two faces use - so the design un-mirrors and reads correct, not backwards, once you're looking at it from underneath rather than through it.

Each face got sized to what it actually has available, not the same fixed size twice:

- **Top** - the main basin is long and narrow (124 x 194mm), and the lockup (icon above the wordmark, both the same width) is short and wide - laid out straight, it's capped by the basin's short axis while most of the long axis goes unused. Rotating the whole lockup 90° swaps which axis constrains it, letting it run about 30% bigger before hitting the same margins. Ends up around 127mm wide, running along the basin's length.
- **Bottom** - the underside is one unbroken flat rectangle, no dividing wall in the way, so it runs close to the tray's full footprint unrotated - about 140mm wide.

Three parts in the end - base, top insert, bottom insert - meant as one combined multi-material print (the `_anycubic.3mf` carries per-part filament-slot metadata, same convention as the tokens), not glued-on inserts. Each pocket is only 1mm deep, so the color swap only has to happen across a handful of layers, not the whole floor thickness.

One thing worth naming rather than solving: a straight through-cut silhouette can only ever be read correctly from one side, mirror-flipped from the other - inherent to any single-thickness see-through design, the same reason a flag logo reads backwards from behind. Two independent shallow pockets, each with its own (un)mirrored contour, sidesteps that entirely - the actual reason this ended up as two 1mm pockets with a membrane between them, rather than one pocket cut clean through.

A real bug caught along the way, not just a design note: mirroring a multi-shell cutter (icon + wordmark, no shared geometry between them) by recalculating normals afterward silently inverted one shell relative to the other - both looked completely correct in a render, but the reported volume for each insert came out a fraction of what it should have been, the two shells' signed volumes mostly cancelling each other out despite every edge staying manifold. Fix was `reverse_faces` instead of `recalc_face_normals` for the mirrored case - deterministic, no heuristic to get confused by multiple disconnected shells in the same mesh. Caught by comparing volume before and after the mirror step (should be exactly equal, mirroring can't change volume) - a render alone wouldn't have shown it, both faces looked completely correct either way.

{{< include-code path="blender/dice-tower/build_dice_tray.py" lang="python" >}}

---

## Downloads

Plain tray only - the castle tray and tree tower aren't built yet, and even once they are, their license keeps any remix of them off this page (see above). CC BY-NC-SA 4.0, same as the source: share and remix freely, non-commercial, credit Speedygold789 for the original tray, keep the same license on anything built from these files.

**Base** (with both Mythos pockets cut in) - [STL](downloads/dice_tray_base.stl)

**Top insert** - [STL](downloads/dice_tray_top_insert.stl)

**Bottom insert** - [STL](downloads/dice_tray_bottom_insert.stl)

**Combined plate** - [Anycubic 3MF](downloads/dice_tray_anycubic.3mf) - carries Anycubic Slicer Next's per-part filament-slot metadata; check `BASE_EXTRUDER_SLOT`/`INLAY_EXTRUDER_SLOT` in the script match whatever's actually loaded if you're running a different multi-material setup.

**Script** - run headless in Blender 5.1.2 (`blender --background --python build_dice_tray.py`): [build_dice_tray.py](downloads/build_dice_tray.py)

## Status

Plain tray only, verified in Blender - all three parts manifold, sane volumes, both faces render correct. **Not yet printed** - a real multi-material test print is next, checking the two pockets actually hold their inserts flush and the color swap behaves the way the per-layer-depth math above assumes. Castle tray and tree tower are next after that.
