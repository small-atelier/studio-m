---
title: "Clear-PLA Terrain Footprint Templates for 11th Edition"
date: 2026-08-23
draft: false
tags: ["3d-printing", "blender", "python", "terrain", "40k"]
---

{{< lead >}}
Design note, not printed yet. 11th edition cares about a terrain feature's *footprint* more than its exact shape, so instead of building full ruins I'm printing thin, flat, clear outline templates that just mark the areas out on the table. Source files are free, but two of the five sizes are bigger than my printer's bed — this is the redesign that fixes that.
{{< /lead >}}

---

## What it is

[FREE 11th Edition Terrain Templates](https://www.myminifactory.com/object/3d-print-free-11th-edition-terrain-templates-791451) by **Tinker Junkie** (MyMiniFactory #791451) — flat 0.8mm outline plates in the standard matched-play terrain footprint sizes, made while test-fitting a foldable terrain set to check how ruins sit on the new footprint rules. Licensed [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) — credit to Tinker Junkie for the original design; the redesigned files below carry the same license.

The pack ships three style options (2-color, 1-color transparent, 1-color grid) — printing the plain **1-color** files only, in clear PLA, one material, no AMS/color-change needed.

## The standard set

A full 11th edition matched-play terrain set is 16 footprint pieces across 5 sizes:

| Qty | Size | Role | Pack file |
|---|---|---|---|
| 4 | 7" × 11.5" | Large rectangle | `7X11,5.stl` |
| 2 | 8" × 11.5" | Large right-angle triangle | `8X11,5.stl` |
| 4 | 6" × 4" | Medium rectangle | `4X8.stl` |
| 2 | 10" × 2.5" | Long line | `2,5X10.stl` |
| 4 | 6" × 2" | Short line | `2X8.stl` |

(The pack's own filenames for the medium/short pieces run a bit larger than the nominal rectangle — the rubble-edge outline overshoots the footprint box slightly, which is expected for a broken-edge template.)

## Why redesign the split

Printer is an Anycubic Kobra X, 260 × 260mm bed. Measured against that:

| File | Footprint | Fits as one print? |
|---|---|---|
| `2,5X10.stl` | 88 × 254mm | yes |
| `2X8.stl` | 72 × 152mm | yes |
| `4X8.stl` | 113 × 167mm | yes |
| `7X11,5.stl` | 292 × 193mm | **no** |
| `8X11,5.stl` | 305 × 203mm | **no** |

The two oversized ones ship with the designer's own pre-split `PT1`/`PT2` halves, but that's a plain edge-to-edge cut. At 0.8mm thick that's a razor-thin, low-area glue joint — fragile, and in clear PLA any glue bead along a butt seam shows as a visible line straight across the piece.

Redesigned the split as a **half-lap scarf splice** instead: over a 20mm band straddling the cut, one half keeps only the bottom 0.4mm and the other keeps only the top 0.4mm, so the two tongues nest back together into the original 0.8mm. Both faces stay flush and continuous right across the seam, and the glued area is a full 20mm-wide band instead of a thin line.

```
                     ┌──────────────── 0.8mm ───────────────┐
  Half A (full)      │████████████████████│                 │
                      └────────────────────┤· · · · · · · · ·│ 0.4mm tongue (bottom)
                                            │← 20mm overlap →│
  Half B (full)                            │· · · · · · · · ·├────────────────────┐
                       0.4mm tongue (top) →│                 │████████████████████│
                                            └─────────────────┴─────────────────────┘
  Assembled (glued):  │████████████████████│████████████████│████████████████████│
                                     flush 0.8mm the whole way across
```

One consequence: the half whose tongue sits in the *top* 0.4mm would print as an unsupported floating bridge if exported as-is — nothing underneath it for that band. That file is exported pre-flipped in Z (mirrored) so it prints flat with no supports, then gets turned back over by hand before gluing.

{{< include-code path="blender/terrain-templates/scarf_split_v1.py" lang="python" >}}

Verified in Blender (headless): 0 non-manifold edges, positive volume, on both output halves for both sizes. Resulting halves:

| Piece | Half A | Half B |
|---|---|---|
| 7×11.5 | 156 × 193mm | 156 × 190mm (flipped) |
| 8×11.5 | 163 × 203mm | 163 × 138mm (flipped) |

Both comfortably under the 260mm bed limit.

## Downloads

Self-hosted so these don't disappear if the original listing ever does. Original design: [FREE 11th Edition Terrain Templates](https://www.myminifactory.com/object/3d-print-free-11th-edition-terrain-templates-791451) by Tinker Junkie, [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) — the scarf-split files are a derivative of that work, shared under the same license.

**Print as-is (no rework needed):**

- [2.5×10](stl/2,5X10.stl)
- [2×8](stl/2X8.stl)
- [4×8](stl/4X8.stl)

**Scarf-split halves (redesigned, see above):**

| Piece | Half A | Half B (print flipped) |
|---|---|---|
| 7×11.5 | [STL](stl/7X11,5_SCARF_A.stl) | [STL](stl/7X11,5_SCARF_B_flip-to-print.stl) |
| 8×11.5 | [STL](stl/8X11,5_SCARF_A.stl) | [STL](stl/8X11,5_SCARF_B_flip-to-print.stl) |

- [Split script](scarf_split_v1.py)

## Print list

| Size | Qty | Split? | Prints needed |
|---|---|---|---|
| 7×11.5 | 4 | yes, scarf A+B | 8 |
| 8×11.5 | 2 | yes, scarf A+B | 4 |
| 4×8 | 4 | no | 4 |
| 2.5×10 | 2 | no | 2 |
| 2×8 | 4 | no | 4 |
| **Total** | **16 finished pieces** | | **22 prints** |

Board size not settled yet — this set covers the current 60" × 44" standard matched-play table; will revisit the exact layout once the first pieces are off the printer.

## Status

- Scarf-split geometry designed and verified (Blender, headless) — not yet printed
- 4×8, 2.5×10, 2×8 need no rework, print as-is from the pack's 1COLOR files
- Next: first test print of one 7×11.5 half-pair, check the glued seam before committing to the full run
