---
title: "Generating Miniature Bases with Blender"
date: 2026-05-31
draft: false
tags: ["blender", "fdm", "3d-printing", "bases"]
---

A Blender Python script that generates a complete set of plain bases across all standard GW shapes and sizes — hollow, print-ready, with optional magnet sockets. Good for when you want a clean blank base quickly without hunting for a file on Printables.

{{< lead >}}
Built and tested in Blender 5.1.2. No plugins required — paste into the Script Editor and run.
{{< /lead >}}

{{< figure src="gallery/IMG_1509.webp" caption="Printed set — magnet sockets and size labels visible on the underside" >}}

---

## What it generates

**Round** — 25 · 28.5 · 32 · 40 · 50 · 65 · 80 · 90 · 100 · 130 · 160 mm

**Oval** — 60×35 · 75×42 · 90×52 · 105×70 · 120×92 · 150×95 · 170×109 mm

**Square** — 20 · 25 · 40 · 50 · 60 · 100 mm

**Rectangular** — 25×50 · 40×60 · 50×75 · 50×100 mm

**Pill** (stadium — rect with semicircular ends) — 70×25 · 95×40 mm

**Slotted round** — 20 · 25 mm — single straight slot

**Slotted square** — 20 · 25 mm — single straight slot + corner-to-corner diagonal slot (separate files for each)

**Slotted rect (cavalry)** — 20×40 · 25×50 mm — two parallel slots running along the long axis, side by side across the width

All bases are:
- Hollow interior, standing on the outer rim
- GW-style taper on the top edge
- Size label raised on the inside ceiling (readable from below)
- Optional magnet sockets — two sizes, interleaved triangles (5×2 mm and 3×1 mm), count scaled to base size. Oval bases use an elliptical ring so sockets stay inside the wall at all angles and clear of the centre label
- Slotted bases omit the label (the slot cutter would intersect it)

Bases are bin-packed to fit a 220 × 220 mm print bed (Anycubic Kobra X), flipped flat-top-down for printing.

---

## Downloads

Pre-generated STLs for everything above, if you just want the files rather than running the script yourself.

**Round** — [25](round_25mm.stl) · [28.5](round_28.5mm.stl) · [32](round_32mm.stl) · [40](round_40mm.stl) · [50](round_50mm.stl) · [65](round_65mm.stl) · [80](round_80mm.stl) · [90](round_90mm.stl) · [100](round_100mm.stl) · [130](round_130mm.stl) · [160](round_160mm.stl) mm

**Oval** — [60×35](oval_60x35.stl) · [75×42](oval_75x42.stl) · [90×52](oval_90x52.stl) · [105×70](oval_105x70.stl) · [120×92](oval_120x92.stl) · [150×95](oval_150x95.stl) · [170×109](oval_170x109.stl) mm

**Square** — [20](square_20mm.stl) · [25](square_25mm.stl) · [40](square_40mm.stl) · [50](square_50mm.stl) · [60](square_60mm.stl) · [100](square_100mm.stl) mm

**Rectangular** — [25×50](rect_25x50.stl) · [40×60](rect_40x60.stl) · [50×75](rect_50x75.stl) · [50×100](rect_50x100.stl) mm

**Pill** — [70×25](pill_70x25.stl) · [95×40](pill_95x40.stl) mm

**Slotted round** — [20](slot_round_20mm.stl) · [25](slot_round_25mm.stl) mm

**Slotted square** — [20](slot_square_20mm.stl) · [20 diagonal](slot_square_20mm_diag.stl) · [25](slot_square_25mm.stl) · [25 diagonal](slot_square_25mm_diag.stl) mm

**Slotted rect (cavalry)** — [20×40](slot_rect_20x40.stl) · [25×50](slot_rect_25x50.stl) mm

---

## How to run it

1. Open Blender
2. Switch to the **Scripting** workspace
3. Click **New** to open a blank script
4. Paste the script below (or open the `.py` file directly with **Open**)
5. Click **Run Script** (▶) or press `Alt + P`

The script builds everything into collections — *Round Bases*, *Oval Bases*, *Square Bases*, *Rect Bases*, *Pill Bases*, *Slotted Bases* — and prints a batch summary to the console.

---

## Key config options

All knobs are at the top of the file under `# CONFIG`.

### Shape sizes

| Variable | What it controls |
|---|---|
| `ROUND_SIZES` | list of round diameters |
| `OVAL_SIZES` | list of `(x, y)` oval pairs |
| `SQUARE_SIZES` | list of square side lengths |
| `RECT_SIZES` | list of `(width, depth)` rect pairs |
| `PILL_SIZES` | list of `(length, width)` pill pairs |
| `SLOTTED_ROUND` | list of `{"diam", "style"}` dicts |
| `SLOTTED_SQUARE` | list of `{"size", "style"}` dicts |
| `SLOTTED_RECT` | list of `{"x", "y", "style"}` dicts |

### Slot styles

| Style | Description | Used for |
|---|---|---|
| `"single"` | one slot along Y axis | infantry round & square |
| `"double"` | two parallel slots along length, side by side in X | cavalry rect |
| `"diagonal"` | corner-to-corner slot at 45° | square bases |
| `"cross"` | perpendicular crossed slots | larger bases |

### Geometry

| Variable | Default | What it controls |
|---|---|---|
| `HEIGHT` | `4.0` | total base height mm |
| `WALL` | `1.6` | side wall thickness |
| `BOTTOM_THICKNESS` | `1.2` | top floor thickness (model platform) |
| `ADD_MAGNETS` | `True` | include magnet sockets |
| `MAGNET_RING` | `0.55` | socket ring as fraction of radius |
| `SLOT_WIDTH` | `2.0` | slot width mm |
| `SLOT_DEPTH` | `3.0` | slot depth from top surface mm |
| `SLOT_SPACING` | `14.0` | front-to-back spacing between cavalry slots mm |
| `SLOT_LENGTH_FACTOR` | `0.60` | slot length as fraction of base dimension |

### Export

| Variable | Default | What it controls |
|---|---|---|
| `EXPORT_STL` | `False` | master export switch |
| `EXPORT_ROUND` | `True` | include round bases |
| `EXPORT_OVAL` | `True` | include oval bases |
| `EXPORT_SQUARE` | `True` | include square bases |
| `EXPORT_RECT` | `True` | include rect bases |
| `EXPORT_PILL` | `True` | include pill bases |
| `EXPORT_SLOT` | `True` | include all slotted bases |
| `EXPORT_DIR` | `//stl_output` | output folder (`//` = next to .blend file) |

---

## Exporting STLs

Set `EXPORT_STL = True` and optionally change `EXPORT_DIR` to an absolute path, then run. Each base exports as its own file named by type and size:

```
stl_output/
  round_25mm.stl
  oval_60x35.stl
  square_25mm.stl
  rect_25x50.stl
  pill_95x40.stl
  slot_round_25mm.stl
  slot_square_25mm.stl
  slot_square_25mm_diag.stl
  slot_rect_25x50.stl
  ...
```

Toggle individual type flags (`EXPORT_ROUND`, `EXPORT_OVAL`, etc.) to export only what you need.

---

## Print orientation

Bases are placed **flat top face down** — the model platform goes on the bed, the open cavity faces up. No bridging over the hollow interior, clean top surface straight off the print.

---

## The script

{{< include-code path="blender/bases/bases.py" lang="python" >}}
