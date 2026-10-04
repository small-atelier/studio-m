---
title: "Shape-Coded Combat Modifier Tokens"
date: 2026-09-08
draft: false
tags: ["3d-printing", "blender", "python", "warhammer", "age-of-sigmar", "40k", "multi-material"]
---

{{< lead >}}
Generic combat-modifier tokens for 40k or AoS — not tied to any army, unlike the [Hashut DPP/Desolation tokens]({{< ref "/posts/hashut-game-tokens" >}}) that share their build pipeline. Each stat gets its own token *shape*, not just a label, so they're sortable by touch in a dice bag, not only by reading them.
{{< /lead >}}

{{< carousel images="gallery/*" aspectRatio="1-1" interval="3000" >}}

---

## Why shape, not just text

A modifier token only earns its keep if picking the right one is faster than doing the math in your head. Nine differently-labelled squares in a pile doesn't clear that bar — you're still reading every one. Give each stat its own silhouette instead, and the shape does the sorting before you've even read the text:

| Stat | Shape |
|---|---|
| To Hit | Round |
| To Save | Shield |
| To Wound | Drop/teardrop |
| Battle Shock | Skull |
| Strike Order | Arrow |
| Rend | Square |
| Attacks | Hexagon |
| Damage | Sword |

Every numeric one is a **flip token** — front and back show opposite states of the same stat ("+1"/"−1"), one physical piece instead of a pile of loose counters. Full sentence on every face, matching how the rules actually word it: "**TO HIT**", "**TO WOUND**", "**TO SAVE**" for roll modifiers (the rules say "+1 to Hit"), plain "**REND**", "**ATTACKS**", "**DAMAGE**" for characteristic modifiers (the rules say "Rend −1", not "Rend to −1"). Battle Shock and Strike Order aren't ±1 pairs, so they flip between the two actual states instead: **BATTLE SHOCK TEST** ↔ **BATTLE SHOCKED**, **STRIKE FIRST** ↔ **STRIKE LAST** — the arrow even reverses direction when you flip it, which wasn't planned but reads perfectly regardless.

## Bonus: a Mythos token

Thrown in for free — the sun/mountain/moon relief from the [Mythos business-card stand]({{< ref "/posts/card-stand" >}}), re-cut as a square token with the same border treatment as the rest of the set. Reused the already-traced icon contours directly rather than re-tracing from the source image.

## Design

Same recess + insert multi-material build as the Hashut tokens: every icon and line of text is a shallow (0.6mm) flush pocket, and a second "inlay" part — everything recessed, joined into one piece — drops in exactly flush. Print the plate in one filament and the inlay in another and the result is genuinely two-color, no painting. Border ring included on every token this time, in the same inlay color.

Three build details worth remembering for the next project like this:

- **Booleaning a border ring and a text/icon pocket into one combined cutter can corrupt the model**, even when each is clean on its own — found it on the skull's concave notch. Fix: cut the border and the content as two separate sequential differences, not one joined cutter.
- **A uniform scaled-copy "border" isn't a real constant-width offset** — fine on regular shapes (circle, square, hexagon) and gentle curves (shield, drop), but on the sword and arrow it visibly stopped hugging the outline right at the crossguard/shaft step. Fixed by computing a genuine polygon offset instead ([shapely](https://shapely.readthedocs.io/)'s `buffer()`, round joins so concave corners like a crossguard's inner step don't spike into a point) and baking the result in as fixed coordinates. The sword needed a noticeably *thinner* ring than the arrow for this to work — a uniform mm offset eats the same amount off every edge, and the sword's short axis can't afford to lose as much as its long axis can.
- **The first test print's text looked weak** — same lesson as the [score tracker]({{< ref "/posts/score-tracker" >}}) before it: a thin serif at small recessed size just doesn't resolve on an FDM nozzle, no matter how big the nominal curve size is. Swapped the label font from BaskervilleBold to Arial Black — uniform heavy strokes, no fine detail to lose — and it prints crisp. The Mythos wordmark keeps BaskervilleBold on purpose, for brand consistency with the card-stand piece it's borrowed from; everything meant to be *read fast at a glance* gets the bold sans instead.

Full build script below — one file, no separate contour-extraction step needed since the only traced icon (Mythos) reuses contours already produced for the card-stand project. Same technique again in the [measuring gauges]({{< ref "/posts/measuring-gauges" >}}), including the Arial Black lesson above.

{{< include-code path="blender/combat-modifiers/build_modifier_tokens.py" lang="python" >}}

---

## Downloads

Same workflow as the Hashut set: STL pairs work with any multi-material setup that lets you assign a filament per imported part. The `_anycubic.3mf` files carry Anycubic Slicer Next's own per-part filament-slot metadata (that slicer ignores the standard 3MF color hint entirely) — import that one if that's what you're running, and check `BASE_EXTRUDER_SLOT`/`INLAY_EXTRUDER_SLOT` in the script match whatever's actually loaded.

**Round** — [base](downloads/to_hit_base.stl) · [inlay](downloads/to_hit_inlay.stl) · [Anycubic 3MF](downloads/to_hit_anycubic.3mf)

**Shield** — [base](downloads/to_save_base.stl) · [inlay](downloads/to_save_inlay.stl) · [Anycubic 3MF](downloads/to_save_anycubic.3mf)

**Drop** — [base](downloads/to_wound_base.stl) · [inlay](downloads/to_wound_inlay.stl) · [Anycubic 3MF](downloads/to_wound_anycubic.3mf)

**Skull** — [base](downloads/battle_shock_base.stl) · [inlay](downloads/battle_shock_inlay.stl) · [Anycubic 3MF](downloads/battle_shock_anycubic.3mf)

**Arrow** — [base](downloads/strike_order_base.stl) · [inlay](downloads/strike_order_inlay.stl) · [Anycubic 3MF](downloads/strike_order_anycubic.3mf)

**Square** — [base](downloads/rend_base.stl) · [inlay](downloads/rend_inlay.stl) · [Anycubic 3MF](downloads/rend_anycubic.3mf)

**Hexagon** — [base](downloads/attacks_base.stl) · [inlay](downloads/attacks_inlay.stl) · [Anycubic 3MF](downloads/attacks_anycubic.3mf)

**Sword** — [base](downloads/damage_base.stl) · [inlay](downloads/damage_inlay.stl) · [Anycubic 3MF](downloads/damage_anycubic.3mf)

**Mythos (bonus)** — [base](downloads/mythos_base.stl) · [inlay](downloads/mythos_inlay.stl) · [Anycubic 3MF](downloads/mythos_anycubic.3mf)

**Script** — run headless in Blender 5.1.2 (`blender --background --python build_modifier_tokens.py`), no extra Python packages needed:

- [build_modifier_tokens.py](downloads/build_modifier_tokens.py)
