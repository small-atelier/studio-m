---
title: "Magnet Storage Bar"
date: 2026-09-25
draft: false
tags: ["3d-printing", "blender", "python", "magnets", "storage"]
---

{{< lead >}}
A printed bar that stores the whole magnet stock as stacks. Every well sits against a long face, with a full-height slot, so a finger or a pin can push the stack up however low it runs. One design, printed twice, each copy holding half the stock.
{{< /lead >}}

{{< carousel images="gallery/*" aspectRatio="1-1" interval="3000" >}}

---

## The stock

| Magnet (Ø × thickness) | Count |
|---|---|
| 20 × 1 mm | 400 |
| 10 × 3 mm | 100 |
| 6 × 3 mm | 100 |
| 5 × 3 mm | 400 + extras |
| Ø19, Ø16, Ø10 (odd sizes) | a few each |

## Design

**Two bars, one STL.** The stock is split over `COPIES = 2` identical bars. Each bar is 149 × 37 × 130 mm and prints upright with no supports.

**Two rows, back to back.** The 20 mm and other large wells run along the front face, and the 5 × 3 and 6 × 3 wells along the back. Putting big wells opposite small ones keeps the bar narrow.

**Side slots.** Each well has a slot through its long face, running from the rim down to 1 mm above the floor. The slot is half the magnet diameter wide, so the stack stays in the well but can be pushed up from the side. It's a finger slot on the 20 mm wells and a pin or toothpick slot on the 5 mm ones. The 1 mm lip at the bottom keeps the last disc from sliding out.

**Well sizing from the stock count.** `TARGET_DEPTH` sets how many discs fit in one well, and that gives the number of wells needed per size. The deepest stack sets the bar height, and every well runs that full depth, so the sizes with shorter stacks have room for refills. After sizing, the shorter face is topped up with extra 5 × 3 wells until it matches the other.

**Per bar:**

| Face | Magnet | Wells | Max per well |
|---|---|---|---|
| front | 20 × 1 | 2 | 120 |
| front | Ø19 | 1 | full depth |
| front | Ø16 | 1 | full depth |
| front | 10 × 3 | 2 | 40 |
| front | Ø10 | 1 | full depth |
| back | 5 × 3 | 13 | 40 |
| back | 6 × 3 | 2 | 40 |

**Tolerances.** Hole diameter is the nominal magnet diameter + 0.3 mm, a slip fit for FDM. Stack depth allows +5 % over the nominal disc thickness: disc thickness is typically ±0.05 mm, which adds up over a 100-disc stack.

**Boolean-light.** The wells don't touch each other, so they're joined into one cutter and removed with a single boolean. The slots are joined into a second cutter and removed with a second pass. That's two boolean ops in total.

{{< include-code path="blender/magnet-storage/build_magnet_storage.py" lang="python" >}}

---

## Downloads

Own design, share and remix freely.

- [magnet_storage.stl](downloads/magnet_storage.stl) — print two
- [build_magnet_storage.py](downloads/build_magnet_storage.py)

Run headless in Blender 5.1.2:

```
blender --background --python build_magnet_storage.py
```

`--no-render` skips the preview renders. Stock counts, sizes, `COPIES` and `TARGET_DEPTH` are all in the config block at the top.

## Status

Verified in Blender: clean booleans, no non-manifold geometry. **Not yet printed.** The 0.3 mm hole clearance and the slot widths are informed guesses, not print-confirmed.
