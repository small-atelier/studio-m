---
title: "Helsmiths of Hashut Tokens & Box"
date: 2026-09-28
draft: false
tags: ["3d-printing", "warhammer", "age-of-sigmar", "multi-material"]
---

{{< lead >}}
Daemonic Power and Desolation tokens for the [Helforge Host]({{< ref "/projects/hashut/roster" >}}), plus a carry box that holds them alongside the warscroll cards. The same kit exists for [Blades of Khorne]({{< ref "/posts/khorne-tokens" >}}).
{{< /lead >}}

{{< figure src="gallery/box_assembled_open.png" caption="Box open: DPP wells on the left, card slot up front, two Desolation stacks at the back" >}}

---

## Why these exist

Helsmiths of Hashut (Age of Sigmar 4th Edition) runs on two linked resources instead of the usual command-point economy:

- **Desolation Tokens** sit on terrain and objectives. A unit of yours contesting one (not in combat) earns a token there each turn, or you can drop one directly with the *Leave the Realm in Ruin* command ability.
- **Daemonic Power Points (DPP)** sit on units. Each of your turns, *Harness Daemonic Power* converts every Desolation Token on the battlefield into DPP, which you then allocate onto friendly units. The cap is 3 per unit, and every warscroll except the Hobgrots gets meaningfully better with each one.

Nearly the whole gameplan runs through this loop, so both players read these tokens constantly, every turn. A set that's unambiguous from across the table beats a pile of generic glass gems.

Sources: [Bell of Lost Souls — Powered By Daemons](https://www.belloflostsouls.net/2025/09/age-of-sigmar-helsmiths-of-hashut-rules-powered-by-daemons.html), [Goonhammer — Helsmiths of Hashut Battletome Review](https://www.goonhammer.com/goonhammer-reviews-helsmiths-of-hashut-fourth-edition-battletome).

## The tokens

**DPP tokens** (33mm hex) show a unit's *current* power level: 1, 2 or 3. Instead of stacking counters on a base, there's one token per level. When a unit's DPP changes, swap in the token with the new number. There's no stack to knock over, and the level reads at a glance from either side.

**Desolation Tokens** (56×30mm) mark a contested terrain feature or objective until *Harness Daemonic Power* converts them. They're bigger than the DPP tokens so they stay visible sitting on terrain.

Both are double-sided, with the full design on each face, so a token that gets flipped never comes up blank. Both print in two colors: the icons and text are separate inlays, not paint.

{{< carousel images="gallery/*" aspectRatio="1-1" interval="3000" >}}

## How many to print

The roster has 4 DPP-eligible units (War Despot, Dominator Engine, Tormentor Bombard, Infernal Cohort; Hobgrots don't use DPP). Each is capped at 3, and at worst all four sit at the same level at once, so **2 of each level (6 DPP tokens)** is a comfortable set.

Desolation Tokens have no hard cap. Matched-play missions typically run 5–7 objectives, so **6–8 tokens** covers a normal game with spares for terrain outside the objective set.

## The box

One box for the whole army's game kit: 165.5×131.2×24.5mm, with all wells 22mm deep.

- **Left column:** 3 stacked hex wells, one per DPP level, up to 7 tokens each. Each well has a notch through the left wall so you can pinch a token out from the side.
- **Right column, front:** a slot for the 32 warscroll cards (a 120×70×20mm stack), with a notch through the front wall for lifting the stack out.
- **Right column, back:** 2 Desolation wells, up to 7 tokens each, notched through the back wall.

The lid slides over the full height of the base, with the bull skull in the centre and a Hashut rune in each corner.

## Downloads

Every two-color piece comes as a base + inlay STL pair, an `_anycubic.3mf` (Anycubic Slicer Next reads only its own per-part filament metadata) and a plain `.3mf`. The box base is single-color, so it's just one STL. Set `BASE_EXTRUDER_SLOT`/`INLAY_EXTRUDER_SLOT` in the scripts to whatever's loaded.

**DPP tokens** (33mm hex, print 2 of each):

- Level 1 — [base](downloads/dpp_token_level1_base.stl) · [inlay](downloads/dpp_token_level1_inlay.stl) · [Anycubic 3MF](downloads/dpp_token_level1_anycubic.3mf) · [plain 3MF](downloads/dpp_token_level1.3mf)
- Level 2 — [base](downloads/dpp_token_level2_base.stl) · [inlay](downloads/dpp_token_level2_inlay.stl) · [Anycubic 3MF](downloads/dpp_token_level2_anycubic.3mf) · [plain 3MF](downloads/dpp_token_level2.3mf)
- Level 3 — [base](downloads/dpp_token_level3_base.stl) · [inlay](downloads/dpp_token_level3_inlay.stl) · [Anycubic 3MF](downloads/dpp_token_level3_anycubic.3mf) · [plain 3MF](downloads/dpp_token_level3.3mf)

**Desolation Token** (56×30mm, print 6–8):

- [base](downloads/desolation_token_base.stl) · [inlay](downloads/desolation_token_inlay.stl) · [Anycubic 3MF](downloads/desolation_token_anycubic.3mf) · [plain 3MF](downloads/desolation_token.3mf)

**Box:**

- Base — [STL](downloads/box_base.stl)
- Lid — [base](downloads/box_lid_base.stl) · [inlay](downloads/box_lid_inlay.stl) · [Anycubic 3MF](downloads/box_lid_anycubic.3mf) · [plain 3MF](downloads/box_lid.3mf)

**Scripts** (Blender, headless) for adjusting sizes or counts: [build_tokens.py](downloads/build_tokens.py) · [build_token_card_box.py](downloads/build_token_card_box.py) · [extract_icon_contours.py](downloads/extract_icon_contours.py)
