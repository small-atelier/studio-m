---
title: "Objective Marker Tiles"
date: 2026-09-22
draft: false
tags: ["3d-printing", "blender", "python", "warhammer", "age-of-sigmar", "40k", "multi-material"]
---

{{< lead >}}
A paved-tile disc for 40mm objective markers — the disc's outer edge sits 3" beyond the marker's own edge, so its footprint doubles as the actual control-range circle. Irregular wedge-tile paving, a flush pocket for the marker, and an optional Mythos logo on the underside only. Smaller variants match the objective rings printed on the four Spearhead boards, for gluing down.
{{< /lead >}}

{{< carousel images="gallery/*" aspectRatio="1-1" interval="3000" >}}

---

## The idea

40mm objective markers need something to visually mark their control range on the table, not just the marker itself. 3" happens to be the actual control-range distance in both 40k and AoS, so a tile disc sized to exactly that radius beyond the marker's edge does double duty — decoration and a genuine ruler.

## The marker

The pocket is sized for a set of free downloaded objective-marker coins — 40mm diameter, 2mm thick, five faction variants (dragon face, dragon side, phoenix, snake, crane). Not this project's own design, just the part it's built around; no download link here since the exact source/license wasn't tracked down, but any 40mm/2mm coin marker will drop straight in.

## Spearhead boards

The four Spearhead boards have their objectives printed on them as stone rings, and those rings aren't control-range circles: they come in 5", 6" and 7", all smaller than the 3" range around a 40mm marker. The Spearhead variants are sized to cover the printed ring exactly and get glued down onto the board, so each board needs its own full set:

{{< carousel images="boards/*" aspectRatio="4-3" interval="3000" >}}

| Board | Objectives | Pieces |
|---|---|---|
| Aqshy | 5 × 6" | 5 × 6" |
| Ghryan | 3 × 6" + 2 on the side edges | 3 × 6", 2 × 6" edge |
| Dolorum | 4 × 5" corners + 7" centre | 4 × 5", 1 × 7" |
| Ossia | 4 × 5" | 4 × 5" |
| **All four boards** | | **8 × 5", 8 × 6", 2 × 6" edge, 1 × 7"** |

Ghryan's two side objectives run off the board, with their centres about ¾" in from the edge. The edge piece is a 6" disc cut straight 21mm from its centre, just outside the marker pocket so the pocket wall stays closed; it sits ~2mm further in than the printed ring. The same piece rotated 180° covers the other side.

Control range is still measured from the marker, so these discs mark the objective, not the 3".

## Design

**Sizing** — outer radius = marker radius (20mm) + 3" (76.2mm) = 96.2mm, so 192.4mm across total. Still fits a single 220×220mm FDM plate. The Spearhead variants override the outer diameter (`--diameter`, in inches) and keep the same 40mm pocket; the edge piece adds one straight boolean cut (`--edge-cut`, mm from centre) after the tiles are on, which refuses to cut into the pocket.

**Stepped floor, not a uniform slab** — 1.0mm under the pocket (small span, doesn't need much rigidity) and 1.5mm under the paved ring (the big 192mm warp-risk span), built as two overlapping primitives unioned once rather than a single flush-thickness disc. Tile height is 1.5mm, chosen specifically so `ring floor + tile = 1.5+1.5` matches `pocket floor + marker = 1.0+2.0` — the marker ends up sitting exactly flush with the surrounding tile tops, not stepped up or recessed.

**Irregular wedge-tile paving** — concentric rings of wedge-shaped tiles, both the ring widths and the per-ring wedge angles are randomized and then *normalized* to sum exactly to their span (pocket→outer radius, and 360° per ring) rather than just clipped — otherwise the last ring or the last wedge in a pass is whatever's left over, usually a thin unprintable sliver. Wedge seams stagger between adjacent rings via a random per-ring rotation offset, so it reads as laid stone rather than a dartboard. Tiles run flush to both the pocket wall and the outer rim — no plain collar/lip on either edge.

**Restrained stone texture** — each tile gets a beveled top edge, a small random height offset (±0.15mm), and a poked-and-nudged center vertex for a subtle dome or dish (±0.15mm). Deliberately kept to what an FDM nozzle can actually resolve; finer surface noise would just get smoothed away in slicing.

**Mythos logo, underside only, as a real second material** — engraved as a genuine recess+insert pair (base on filament slot 1, insert on slot 2), the same multi-material technique as the [combat-modifier tokens]({{< ref "/posts/combat-modifier-tokens" >}}) and [dice tray]({{< ref "/posts/dice-tower" >}}), not a same-color engraving. Bottom-only and behind a `--logo` flag, for the full-size disc only — the Spearhead variants get glued down, so they never carry one. The icon+wordmark mirror (X-flip + `reverse_faces`, not `recalc_face_normals` — see the fragility notes below) so it reads correct viewed from underneath rather than backwards.

**Boolean-light by construction** — the whole plain print is two isolated boolean ops total: the floor's thickness-step union, and one union joining every tile (built as pure mesh prisms, no per-tile booleans) onto the floor. The logo variant adds exactly one more difference for the pocket cut. Every union that joins two parts together does it with real overlapping volume at the seam (the repo's `EMBED` pattern), never a flush/coincident face — see [[feedback_blender_boolean_fragility]] and the [combat-modifier tokens]({{< ref "/posts/combat-modifier-tokens" >}}) post for why that solver is fussy about long chains and touching faces.

{{< include-code path="blender/objective-markers/objective_markers_v1.py" lang="python" >}}

---

## Downloads

Own design, no external license to carry — share and remix freely.

**Plain** (no logo, single material) — [STL](downloads/objective_marker.stl)

**With Mythos logo** — [base](downloads/objective_marker_logo_base.stl) · [insert](downloads/objective_marker_logo_insert.stl) · [Anycubic 3MF](downloads/objective_marker_logo_anycubic.3mf)

**Spearhead boards** (single material, glue down) — [5"](downloads/objective_marker_spearhead_5in.stl) · [6"](downloads/objective_marker_spearhead_6in.stl) · [6" edge](downloads/objective_marker_spearhead_6in_edge.stl) · [7"](downloads/objective_marker_spearhead_7in.stl)

The Anycubic 3MF carries Anycubic Slicer Next's own per-part filament-slot metadata (that slicer ignores the standard 3MF color hint entirely) — check `BASE_EXTRUDER_SLOT`/`LOGO_EXTRUDER_SLOT` in the script match whatever's actually loaded if you're running a different multi-material setup. The plain print is single-material, so it's STL only, no project file.

**Script** — run headless in Blender 5.1.2:

```
blender --background --python objective_markers_v1.py -- --seed 7 --logo
```

`--seed N` picks a different irregular tile layout, `--logo` adds the underside logo (full-size disc only), `--diameter 6` sets the outer diameter in inches, `--edge-cut 21` cuts the disc straight at that many mm from the centre, `--no-render` skips the preview renders. A Ghryan edge piece:

```
blender --background --python objective_markers_v1.py -- --diameter 6 --edge-cut 21
```

- [objective_markers_v1.py](downloads/objective_markers_v1.py)

## Status

Verified in Blender — clean unions, no non-manifold geometry, marker sits flush per the flush-height invariant above. **Not yet printed** — floor thicknesses, bevel/jitter amounts, and the logo pocket depth are informed guesses, not print-confirmed.
