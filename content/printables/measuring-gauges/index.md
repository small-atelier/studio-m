---
title: "Measuring Gauges"
date: 2026-09-09
draft: false
tags: ["3d-printing", "blender", "python", "warhammer", "40k", "multi-material"]
---

{{< lead >}}
Mythos-branded printed measuring tools for a 40k or AoS table - for the checks that come up constantly, the edge itself is the answer, faster than sliding a tape measure around.
{{< /lead >}}

---

## The need

Most mid-game distance checks are really yes/no questions - "is this ≤1 inch," "did this land more than 9 inches out" - not "how far apart are these exactly." Sliding a tape measure around to answer a yes/no question is the slow way to do it. A charge roll is the one case that genuinely *is* a scale, since it's a random 2-12" you then have to measure out - and there's the odd long-range check where a tape measure is still the right call.

So what actually gets checked, and how often, differs a bit by game:

| Distance | 40k | AoS |
|---|---|---|
| ½" | - | Engagement Range **and** coherency |
| 1" | Engagement Range | common weapon range |
| 2" | Unit coherency | common melee weapon range |
| 3" | Pile-In / Consolidation | Pile-In |
| 6" | common Move / abilities | common Move / abilities |
| 9" | Deep Strike / Reinforcements | Reinforcements |
| 12"-48" | weapon ranges, short to very long | weapon ranges, short to very long |

The two games mostly agree - ½, 1, 3, 6, and 9 all mean roughly the same thing in both. Where they genuinely differ: 40k has a dedicated 2" coherency check that AoS doesn't (AoS folds coherency into the same ½" as engagement), and AoS's short weapon brackets (1"/2") sit at values 40k doesn't really use the same way. Past 12" both games just have a long ladder of weapon ranges (12"/18"/24"/36"/48") - too many distinct values to print a gauge for each, and once you're checking something that far out a tape measure is genuinely fine again. 24" is the exception worth a dedicated piece - it's the single most common troop-weapon range in both games (lasgun, bolter, plasma gun in 40k, AoS's skybolt bow all sit there), everything past it stays a tape-measure job.

Four kinds of piece cover the checks worth a dedicated tool: two fixed-edge gauges for the short-to-mid checks, a charge stick for the 2D6 roll, and a longer stick for that one common 24" check.

## Small & Medium: the gauge family

**Small** packs four references onto one piece - ½", 1", 2", 3" - the checks that come up constantly: Engagement Range (1"), base-to-base, Pile-In (3"), and most of the short ability ranges in either game.

**Medium** stretches the same idea out - 1", 3", 6", 9" - covering the longer, still-frequent checks: 9" for Deep Strike (a unit has to land more than 9" from every enemy model), 6" for common Move characteristics and aura ranges.

Between the two, every edge you actually reach for - ½, 1, 2, 3, 6, 9 - is a real straight edge you lay flat against the check, not a position read off a scale.

{{< figure src="gallery/small_back.png" caption="Small" >}}

{{< figure src="gallery/medium_back.png" caption="Medium" >}}

## Charge

A charge roll is 2D6 (2-12") - a plain graduated ruler, not a fixed edge. The useful length isn't just "12 inches plus a bit of margin" though: after a charge you also need to check you've actually made it into engagement, and that follow-up distance differs per game -

- **AoS** - charge-connect is ½", so **12.5"** covers the full roll plus that check.
- **40k** - Engagement Range is 1", so **13"** covers the full roll plus that check.

Beyond 13" isn't worth printing - a tape measure is the more practical tool past that. Same triangular build as the shooting stick below - self-orienting (reads correctly from any of its 3 faces) and stiffer than a flat plate over this length.

{{< figure src="gallery/charge_tri_12_5in_straighton.png" caption="Charge - 12.5\" (AoS)" >}}

{{< figure src="gallery/charge_tri_13in_straighton.png" caption="Charge - 13\" (40k)" >}}

## Shooting: the 24" experiment

A tape measure is still the right call for most of the table, but it gets floppy and hard to hold straight at range, and it doesn't tell you anything at a glance the way a fixed edge does. This is an experiment in a stiffer alternative for the occasional long check: a rigid **24" triangular stick**, assembled from two 12" segments glued at a tenon/socket joint (the print bed isn't big enough for 24" in one piece).

24" isn't arbitrary - it's the single most common troop-rifle range in both games (lasgun, bolter, plasma gun in 40k, AoS's skybolt bow, all sit at 24"). Full-width unlabeled lines mark the distances that matter along the way - 3"/6"/9" (mirroring the gauge family), 12" (the short/specialist weapon range, and Rapid Fire's half-range line), 18" (the stock tape measure's own length, and a common AoS spell-range bracket) - everything else gets a normal numbered tick. Nothing printed at 24" itself - that's simply the far end of the assembled stick.

Still fresh off the printer - the open question is whether the glued joint holds up to real handling over time, not just whether it prints cleanly. Tape measure stays the fallback either way.

{{< figure src="gallery/shooting_straighton.png" caption="Shooting" >}}

## How it's built

Genuine multi-material technique every number and marking prints in its own color, not painted on - two filaments, one print, nothing to touch up afterward. One script builds the whole family.

{{< include-code path="blender/measuring-gauges/build_measuring_gauges.py" lang="python" >}}

---

## Downloads

STL pairs (base + inlay) work with any multi-material setup that lets you assign a filament per imported part. The `_anycubic.3mf` files carry Anycubic Slicer Next's own per-part filament-slot metadata - import those if that's what you're running, and check `BASE_EXTRUDER_SLOT`/`INLAY_EXTRUDER_SLOT` in the script match whatever's actually loaded.

### Gauges

**Small (3")** — [base](downloads/small_base.stl) · [inlay](downloads/small_inlay.stl) · [Anycubic 3MF](downloads/small_anycubic.3mf)

**Medium (9")** — [base](downloads/medium_base.stl) · [inlay](downloads/medium_inlay.stl) · [Anycubic 3MF](downloads/medium_anycubic.3mf)

### Charge sticks

**13" (40k)** — [base](downloads/charge_tri_13in_base.stl) · [inlay](downloads/charge_tri_13in_inlay.stl) · [Anycubic 3MF](downloads/charge_tri_13in_anycubic.3mf)

**12.5" (AoS)** — [base](downloads/charge_tri_12_5in_base.stl) · [inlay](downloads/charge_tri_12_5in_inlay.stl) · [Anycubic 3MF](downloads/charge_tri_12_5in_anycubic.3mf)

### Shooting stick (24", experimental)

Two segments, glue together at the tenon/socket joint before use.

**Segment A** — [base](downloads/shooting_segment_a_base.stl) · [inlay](downloads/shooting_segment_a_inlay.stl) · [Anycubic 3MF](downloads/shooting_segment_a_anycubic.3mf)

**Segment B** — [base](downloads/shooting_segment_b_base.stl) · [inlay](downloads/shooting_segment_b_inlay.stl) · [Anycubic 3MF](downloads/shooting_segment_b_anycubic.3mf)

### Script

Run headless in Blender 5.1.2 (`blender --background --python build_measuring_gauges.py`) builds the whole family in one pass, no extra Python packages needed. Needs the bundled Arial Black font alongside it (every numeral and the wordmark); the Mythos badge's own icon data lives in a `mythos-logo` folder alongside this project's own, referenced by relative path:

- [build_measuring_gauges.py](downloads/build_measuring_gauges.py) · [ArialBlack.ttf](downloads/ArialBlack.ttf)
