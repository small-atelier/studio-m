---
title: "Attacker & Defender Score Tracker"
date: 2026-09-08
draft: false
tags: ["3d-printing", "blender", "python", "warhammer", "age-of-sigmar", "40k", "multi-material"]
---

{{< lead >}}
One board, sat between both players, with a thumb-spun dial for everything you'd otherwise be scribbling on a scrap of paper or juggling in loose dice: Command Points and Victory Points for the Attacker and the Defender, plus the battle round. Nine wheels, one peg each, dial to the number and walk away.
{{< /lead >}}

{{< carousel images="gallery/*" aspectRatio="1-1" interval="3000" >}}

---

## Why this exists

Every game has the same four running totals — Attacker CP, Attacker VP, Defender CP, Defender VP — plus the round number, and every game they end up tracked differently: a die on the table that gets bumped, a phone notes app nobody remembers to update, a scorepad that only one player can see. None of it survives a full table reach, and none of it is readable from across the board at a glance.

This is a single physical answer to all five numbers at once. Spin a wheel, the number shows in its window, done — no resetting a stack of tokens, no "wait, was that CP already spent this turn," no re-adding a column of scribbles to check who's ahead.

## How it works

Each of the nine wheels — Round up top, then Attacker CP/VP and Defender CP/VP stacked below it — sits on its own peg between a front and back plate, with a knurled rim you spin with a fingertip through a cutout at the wheel's edge. The digit lined up with the square window on the front is the current value. Command Points and Victory Points both run two wheels deep (00–99), so a long game never runs out of road.

A little branding along the way: the [Mythos]({{< ref "/posts/card-stand" >}}) sun/mountain/moon mark sits at the top of the board, and a plain divider line splits the Attacker half from the Defender half so it reads at a glance which column is whose.

## Design

Two-color print throughout — white base, black recessed digits and labels, no painting needed. The wheels have a cog-textured rim for grip and drop into a recessed pocket on the back plate, peg through the center, with the front plate capping it all in place. Back plate's backside is a single clean flat surface once assembled — nothing printing proud of it, nothing to catch on a case or a table edge.

One assembly note: the wheels print digit-face-down for the cleanest finish, so the digit ring is deliberately pre-mirrored in the model — flip each wheel over once when you install it and the numbers read correctly. Print it flat and skip the flip and they'll come out backwards.

The front plate also comes in two badge variants — swap the Mythos mark for a big **40K** or **AOS** wordmark in the same frame, same board, same wheels. Everything else about the build is identical.

## Downloads

STL pairs (base + inlay) work with any multi-material setup that lets you assign a filament per imported part. The `_anycubic.3mf` files carry Anycubic Slicer Next's own per-part filament-slot metadata — import that one if that's what you're running.

**Round wheel** — [base](downloads/wheel_round_base.stl) · [inlay](downloads/wheel_round_inlay.stl) · [3MF](downloads/wheel_round.3mf) · [Anycubic 3MF](downloads/wheel_round_anycubic.3mf)

**Tens wheel** (print ×4 — one per CP/VP counter) — [base](downloads/wheel_tens_base.stl) · [inlay](downloads/wheel_tens_inlay.stl) · [3MF](downloads/wheel_tens.3mf) · [Anycubic 3MF](downloads/wheel_tens_anycubic.3mf)

**Ones wheel** (print ×4) — [base](downloads/wheel_ones_base.stl) · [inlay](downloads/wheel_ones_inlay.stl) · [3MF](downloads/wheel_ones.3mf) · [Anycubic 3MF](downloads/wheel_ones_anycubic.3mf)

**Front plate** (Mythos badge) — [base](downloads/front_plate_base.stl) · [inlay](downloads/front_plate_inlay.stl) · [3MF](downloads/front_plate.3mf) · [Anycubic 3MF](downloads/front_plate_anycubic.3mf)

**Front plate** (40K badge) — [base](downloads/front_plate_40k_base.stl) · [inlay](downloads/front_plate_40k_inlay.stl) · [3MF](downloads/front_plate_40k.3mf) · [Anycubic 3MF](downloads/front_plate_40k_anycubic.3mf)

**Front plate** (AOS badge) — [base](downloads/front_plate_aos_base.stl) · [inlay](downloads/front_plate_aos_inlay.stl) · [3MF](downloads/front_plate_aos.3mf) · [Anycubic 3MF](downloads/front_plate_aos_anycubic.3mf)

**Back plate** (single color) — [STL](downloads/back_plate.stl)

**Script** — run headless in Blender 5.1.2 (`blender --background --python build_score_tracker.py`), no extra Python packages needed. Needs the bundled Arial Black font alongside it (used for the digits and labels — chosen over a serif font specifically because its thick, uniform strokes hold up at small print scale):

- [build_score_tracker.py](downloads/build_score_tracker.py) · [ArialBlack.ttf](downloads/ArialBlack.ttf)
