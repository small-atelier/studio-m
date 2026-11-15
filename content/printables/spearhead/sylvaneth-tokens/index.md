---
title: "Spitewing Flight Spearhead Tokens & Box"
date: 2026-11-14
draft: true
tags: ["3d-printing", "warhammer", "age-of-sigmar", "multi-material"]
---

{{< lead >}}
A token kit for the Sylvaneth Spearhead, *Spitewing Flight*: ability tokens for the regiment and enhancement picks, effect markers for the quarry and the warscroll abilities, damage trays, a carry box with a chord roller for *Song of the Hunt*, and Sylvaneth-badged measuring gauges.
{{< /lead >}}

{{< figure src="gallery/box_base_only.png" caption="Box open: rect and hex wells on the left, card slot up front, two tray wells either side of the chord roller at the back" >}}

---

The Spitewing Flight: Arch-Revenant, 5 Gossamid Archers, 3 Spiterider Lancers, 3 Revenant Seekers.

The army hunts one enemy unit at a time. At the start of each battle round with no quarry on the battlefield, *Target of Vengeance* picks an enemy unit as the quarry for the rest of the battle. Every destroyed quarry adds a chord to *Song of the Hunt*, and the chords stack: 1 adds to run and charge rolls near the quarry, 2 to hit rolls, 3 or more to wound rolls.

What gets forgotten mid-game: which enemy unit is the quarry, how many chords the army has, which regiment ability and enhancement were picked, whether a once-per-battle ability has been spent, and which units carry a Hunting Horn or Deafening Drone effect.

## What's in the kit

**Ability tokens** (56×30mm): one per regiment ability and enhancement. Text only, in a condensed font that keeps letters open at small size.

- **Front:** the ability's name on the first two rows, a short version of the rule on the third. It prints on top.
- **Back:** who it applies to (ARMY or GENERAL), then when it's used.

Before the game, pull the regiment and enhancement tokens for the chosen picks and keep them with the warscroll cards. Flip a once-per-battle token when it's used.

Regiment abilities, back reads ARMY:

| Ability | Rule (front) | When (back) |
|---|---|---|
| Leaves on the Wind | RETREAT, NO MW | ONCE PER BATTLE · END OF ANY TURN |
| Lifebringers | HEAL D3 EACH UNIT | ONCE PER TURN · END OF ANY TURN |

Enhancements, back reads GENERAL:

| Enhancement | Rule (front) | When (back) |
|---|---|---|
| Head of the Hunt | +1 REND NEAR QUARRY | PASSIVE |
| Zephyrkin | 2D6" MOVE AFTER FIGHT | REACTION · AFTER CHARGE |
| Bold Spirit | +1 WOUND IN RANGE | ONCE PER BATTLE · ANY HERO PHASE |
| Cunning Pursuer | +1 CHARGE IF ENGAGED | PASSIVE |

*Head of the Hunt* works while the quarry is within 9" of the general and visible to them. *Cunning Pursuer* adds 1 to charge rolls for friendly units wholly within 12" while the general is in combat, 2 while the general is in combat with the quarry.

**Effect tokens** (33mm hex): the seed, a value and a label on the front, the source ability on the back. Each goes beside the unit it applies to.

| Token | Front | Back | Goes beside |
|---|---|---|---|
| Quarry | 9" · QUARRY | TARGET OF VENGEANCE | The enemy quarry, for the rest of the battle |
| Hunting Horn | +1 · CHORD | HUNTING HORN | The friendly unit the Arch-Revenant picked, until your next turn |
| Deafening Drone | -1 · ATTACKS | DEAFENING DRONE | The enemy unit the Revenant Seekers picked, for the rest of the turn |

The 9" on the quarry token is the range every *Song of the Hunt* effect is measured from.

**Generic tokens** (33mm hex, ×4): the seed on both faces, for anything else worth marking.

**Damage trays:** an arrow-shaped plate, 22×40×6.5mm, with a pocket for one 16mm d6. The die shows the damage on the unit's currently wounded model, and the arrow points at the unit. Print ×3: Arch-Revenant (6 Health), Spiterider Lancers and Revenant Seekers (5 each). Gossamid Archers have 2 Health and don't need one.

{{< carousel images="gallery/*" aspectRatio="1-1" interval="3000" >}}

## The box

The box has the same footprint as the other Spearhead boxes (165.5×131.2×24.5mm) and uses the same column layout. Every well is 22mm deep:

- **Left column:** a hex well at the back for the 3 effect and 4 generic tokens, a rect well at the front for the 6 ability tokens. Each has a lift notch through the left wall.
- **Right column, front:** a 123×73mm slot for the warscroll cards, with a notch through the front wall. The floor carries a cards + die icon.
- **Right column, back:** an arrow-shaped well on each side for the trays (2 + 1), and the chord roller in its trough between them. *SONG OF THE HUNT* runs across the strip in front.

**Chord roller:** a 20×20×68mm square bar with one chord count per face: *0*, *1 SIMPLE*, *2 TUNEFUL*, *3 MELODIC*. The face on top is the army's current chord count. Pinch it between the front scoop and the back-wall notch, lift it, turn it a quarter and drop it back in. Rolling it backwards, top face away from you, steps up one chord.

The roller is a brown core with a shallow recess on each long face and four flat-printed tiles glued into them. Each recess and tile has one chamfered corner, so a tile only fits text-upright. The core prints standing on one end. Glue the tiles in order 0 → 1 → 2 → 3, each on the face that comes up as you roll it backwards.

The underside carries the Mythos logo, inlaid flush.

{{< figure src="gallery/box_base_underside.png" caption="Underside: Mythos logo" >}}

**Lid:** it slips over the base with a full-height skirt. The top carries the Sylvaneth faction glyph, with the Ironbark, Oakenbrow, Gnarlroot and Winterleaf glade glyphs in the corners. The inside face carries a dice icon: flip the lid over and it's a dice tray.

{{< figure src="gallery/box_lid_top_face.png" caption="Lid top: faction glyph and glade glyphs" >}}

{{< figure src="gallery/box_lid_as_dice_tray.png" caption="Lid flipped over as a dice tray" >}}

## Measuring gauges

The Small (½", 1", 2", 3") and Medium (1", 3", 6", 9") gauges from the [Measuring Gauges]({{< ref "/printables/measuring-gauges" >}}) set. The Small carries the seed as its front badge, the Medium the faction glyph. The back keeps the Mythos badge.

{{< figure src="gallery/small_sylvaneth_front.png" caption="Small, seed front" >}}

{{< figure src="gallery/medium_sylvaneth_front.png" caption="Medium, faction glyph front" >}}

## Downloads

Each piece comes as a base + inlay STL pair and an `_anycubic.3mf` (Anycubic Slicer Next's own per-part filament metadata); tokens, trays and box also have a plain `.3mf`. Everything prints in two colours, black base in slot 1 and orange inlay in slot 2, except the roller core, which is a single brown part. Set `BASE_EXTRUDER_SLOT`/`INLAY_EXTRUDER_SLOT` in the scripts to whatever's loaded.

**Ability tokens:**

- Leaves on the Wind — [base](downloads/leaves_on_the_wind_base.stl) · [inlay](downloads/leaves_on_the_wind_inlay.stl) · [Anycubic 3MF](downloads/leaves_on_the_wind_anycubic.3mf) · [plain 3MF](downloads/leaves_on_the_wind.3mf)
- Lifebringers — [base](downloads/lifebringers_base.stl) · [inlay](downloads/lifebringers_inlay.stl) · [Anycubic 3MF](downloads/lifebringers_anycubic.3mf) · [plain 3MF](downloads/lifebringers.3mf)
- Head of the Hunt — [base](downloads/head_of_the_hunt_base.stl) · [inlay](downloads/head_of_the_hunt_inlay.stl) · [Anycubic 3MF](downloads/head_of_the_hunt_anycubic.3mf) · [plain 3MF](downloads/head_of_the_hunt.3mf)
- Zephyrkin — [base](downloads/zephyrkin_base.stl) · [inlay](downloads/zephyrkin_inlay.stl) · [Anycubic 3MF](downloads/zephyrkin_anycubic.3mf) · [plain 3MF](downloads/zephyrkin.3mf)
- Bold Spirit — [base](downloads/bold_spirit_base.stl) · [inlay](downloads/bold_spirit_inlay.stl) · [Anycubic 3MF](downloads/bold_spirit_anycubic.3mf) · [plain 3MF](downloads/bold_spirit.3mf)
- Cunning Pursuer — [base](downloads/cunning_pursuer_base.stl) · [inlay](downloads/cunning_pursuer_inlay.stl) · [Anycubic 3MF](downloads/cunning_pursuer_anycubic.3mf) · [plain 3MF](downloads/cunning_pursuer.3mf)

**Effect and generic tokens:**

- Quarry — [base](downloads/quarry_base.stl) · [inlay](downloads/quarry_inlay.stl) · [Anycubic 3MF](downloads/quarry_anycubic.3mf) · [plain 3MF](downloads/quarry.3mf)
- Hunting Horn — [base](downloads/hunting_horn_base.stl) · [inlay](downloads/hunting_horn_inlay.stl) · [Anycubic 3MF](downloads/hunting_horn_anycubic.3mf) · [plain 3MF](downloads/hunting_horn.3mf)
- Deafening Drone — [base](downloads/deafening_drone_base.stl) · [inlay](downloads/deafening_drone_inlay.stl) · [Anycubic 3MF](downloads/deafening_drone_anycubic.3mf) · [plain 3MF](downloads/deafening_drone.3mf)
- Generic (×4) — [base](downloads/sylvaneth_token_base.stl) · [inlay](downloads/sylvaneth_token_inlay.stl) · [Anycubic 3MF](downloads/sylvaneth_token_anycubic.3mf) · [plain 3MF](downloads/sylvaneth_token.3mf)

**Trays:**

- Damage tray (×3) — [base](downloads/damage_tray_base.stl) · [inlay](downloads/damage_tray_inlay.stl) · [Anycubic 3MF](downloads/damage_tray_anycubic.3mf) · [plain 3MF](downloads/damage_tray.3mf)
- Plain damage tray, single colour — [STL](downloads/damage_tray_plain.stl)

**Box:**

- Base — [base](downloads/box_base_base.stl) · [inlay](downloads/box_base_inlay.stl) · [Anycubic 3MF](downloads/box_base_anycubic.3mf) · [plain 3MF](downloads/box_base.3mf)
- Lid — [base](downloads/box_lid_base.stl) · [inlay](downloads/box_lid_inlay.stl) · [Anycubic 3MF](downloads/box_lid_anycubic.3mf) · [plain 3MF](downloads/box_lid.3mf)
- Roller core, brown — [STL](downloads/roller_core.stl) · [3MF](downloads/roller_core.3mf)
- Roller tile 0 — [base](downloads/roller_tile_0_base.stl) · [inlay](downloads/roller_tile_0_inlay.stl) · [Anycubic 3MF](downloads/roller_tile_0_anycubic.3mf) · [plain 3MF](downloads/roller_tile_0.3mf)
- Roller tile 1 SIMPLE — [base](downloads/roller_tile_1_base.stl) · [inlay](downloads/roller_tile_1_inlay.stl) · [Anycubic 3MF](downloads/roller_tile_1_anycubic.3mf) · [plain 3MF](downloads/roller_tile_1.3mf)
- Roller tile 2 TUNEFUL — [base](downloads/roller_tile_2_base.stl) · [inlay](downloads/roller_tile_2_inlay.stl) · [Anycubic 3MF](downloads/roller_tile_2_anycubic.3mf) · [plain 3MF](downloads/roller_tile_2.3mf)
- Roller tile 3 MELODIC — [base](downloads/roller_tile_3_base.stl) · [inlay](downloads/roller_tile_3_inlay.stl) · [Anycubic 3MF](downloads/roller_tile_3_anycubic.3mf) · [plain 3MF](downloads/roller_tile_3.3mf)

**Measuring gauges:**

- Small — [base](downloads/small_sylvaneth_base.stl) · [inlay](downloads/small_sylvaneth_inlay.stl) · [Anycubic 3MF](downloads/small_sylvaneth_anycubic.3mf)
- Medium — [base](downloads/medium_sylvaneth_base.stl) · [inlay](downloads/medium_sylvaneth_inlay.stl) · [Anycubic 3MF](downloads/medium_sylvaneth_anycubic.3mf)

The gauge script lives with the [Measuring Gauges]({{< ref "/printables/measuring-gauges" >}}) post.

**Scripts** (Blender, headless) for adjusting sizes or counts: [build_sylvaneth_tokens.py]({{< script "sylvaneth-tokens/build_sylvaneth_tokens.py" >}}) · [build_spearhead_box.py]({{< script "spearhead-box/build_spearhead_box.py" >}}) (`-- --force sylvaneth`) · [extract_icon_contours.py]({{< script "icon-trace/extract_icon_contours.py" >}}) · [draw_sylvaneth_seed.py]({{< script "icon-trace/draw_sylvaneth_seed.py" >}}) (the seed icon's source image)

**Icon contours** (the scripts read them by relative path, so keep the folder layout from these URLs): [sylvaneth_seed_contours.json]({{< script "assets/icons/sylvaneth_seed_contours.json" >}}) · [sylvaneth_faction_contours.json]({{< script "assets/icons/sylvaneth_faction_contours.json" >}}) · [sylvaneth_ironbark_contours.json]({{< script "assets/icons/sylvaneth_ironbark_contours.json" >}}) · [sylvaneth_oakenbrow_contours.json]({{< script "assets/icons/sylvaneth_oakenbrow_contours.json" >}}) · [sylvaneth_gnarlroot_contours.json]({{< script "assets/icons/sylvaneth_gnarlroot_contours.json" >}}) · [sylvaneth_winterleaf_contours.json]({{< script "assets/icons/sylvaneth_winterleaf_contours.json" >}}) · [dice_roll_contours.json]({{< script "assets/icons/dice_roll_contours.json" >}}) · [cards_contours.json]({{< script "assets/icons/cards_contours.json" >}}) · [die_five_contours.json]({{< script "assets/icons/die_five_contours.json" >}}) · [logo_contours_v5.json]({{< script "card-stand/logo_contours_v5.json" >}})

## Rules

- [Spearhead: Spitewing Flight (PDF)](https://assets.warhammer-community.com/eng_25-03_aos_spearhead_spitewing_flight_sylvaneth-rtiguzvyhx-f7di7yhcim.pdf)
