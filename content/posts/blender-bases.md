---
title: "Generating Miniature Bases with Blender"
date: 2026-05-31
draft: true
tags: ["blender", "fdm", "3d-printing", "bases"]
---

A Blender Python script that generates a full set of plain round and oval bases — hollow, print-ready, with optional magnet sockets. Good for when you want a clean blank base quickly without hunting for a file on Printables.

{{< lead >}}
Built and tested in Blender 5.1.2. No plugins required — paste into the Script Editor and run.
{{< /lead >}}

---

## What it generates

- **Round bases:** 25 · 28.5 · 32 · 40 · 50 · 65 · 80 · 90 · 100 · 130 · 160 mm
- **Oval bases:** 60×35 · 75×42 · 90×52 · 105×70 · 120×92 · 150×95 · 170×109 mm
- Hollow interior — stands on the outer rim, open at the bottom
- GW-style taper on the top edge
- Size label raised on the inside ceiling (readable from below)
- Optional magnet sockets — two sizes, interleaved triangles (5×2 mm and 3×1 mm)

Bases are laid out in print batches to fit a 220 × 220 mm bed (Anycubic Kobra X), flipped so the flat top face sits on the bed.

---

## How to run it

1. Open Blender
2. Switch to the **Scripting** workspace
3. Click **New** to open a blank script
4. Paste the script below (or open the `.py` file directly with **Open**)
5. Click **Run Script** (▶) or press `Alt + P`

The script builds everything into two collections — *Round Bases* and *Oval Bases* — and prints a batch summary to the console.

---

## Key config options

All knobs are at the top of the file under `# CONFIG`.

| Variable | Default | What it controls |
|---|---|---|
| `ROUND_SIZES` | list of diameters | which round bases to generate |
| `OVAL_SIZES` | list of (x, y) pairs | which oval bases to generate |
| `HEIGHT` | `4.0` | total base height in mm |
| `WALL` | `1.6` | side wall thickness |
| `BOTTOM_THICKNESS` | `1.2` | top floor thickness (model platform) |
| `ADD_MAGNETS` | `True` | include magnet sockets |
| `MAGNET_RING` | `0.55` | socket ring position as fraction of radius |
| `EXPORT_STL` | `False` | export individual STLs after building |
| `EXPORT_DIR` | `//stl_output` | output folder (`//` = next to the .blend file) |

---

## Exporting STLs

Set `EXPORT_STL = True` and optionally change `EXPORT_DIR` to an absolute path, then run the script. Each base is exported as its own file named after the object (`Base_25mm.stl`, `Base_60x35.stl`, etc.).

---

## Print orientation

Bases are placed **flat top face down** — the top surface (where the model stands) goes on the bed, the open cavity faces up. This avoids any bridging over the hollow interior and gives a clean top surface straight off the print.

---

## The script

{{< include-code path="blender/base/bases_v5.py" lang="python" >}}
