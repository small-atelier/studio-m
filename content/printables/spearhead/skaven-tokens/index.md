---
title: "Skaven Spearhead Tokens & Box"
date: 2026-10-18
draft: false
tags: ["3d-printing", "warhammer", "age-of-sigmar", "multi-material"]
---

{{< lead >}}
A token kit covering both Skaven Spearheads, *Gnawfeast Clawpack* and *Warpspark Clawpack*: ability tokens for regiment and enhancement picks, damage trays (including a double tray for the Warp Lightning Cannon), a carry box with a Horned Rat lid, and Skaven-badged measuring gauges.
{{< /lead >}}

{{< figure src="gallery/box_assembled_open.png" caption="Box open: ability-token wells on the left, card slot up front, tray wells and the dice well at the back" >}}

---

The two Skaven Spearheads:

- **Gnawfeast Clawpack:** Clawlord on Gnaw-beast, Grey Seer, Warlock Engineer, 2× 10 Clanrats, 3 Rat Ogors
- **Warpspark Clawpack:** Grey Seer, 3 Stormfiends, Warp Lightning Cannon, 2× 10 Clanrats

Skaven have no token resource of their own, like the Blood Tithe or Daemonic Power. What gets forgotten mid-game is which regiment ability and enhancement were picked, and whether a once-per-battle ability has been spent. The tokens cover exactly that.

## What's in the kit

**Ability tokens** (56×30mm, the plate of the Hashut Desolation token): one per regiment ability and enhancement across both Spearheads, plus the Rat Ogors' *Unleashed Warp-Fury*. Text only, in a condensed font that keeps letters open at small size.

- **Front:** the ability's name on the first two rows, a short version of the rule on the third. It prints against the bed, where small text comes out crispest.
- **Back:** who it applies to (GENERAL, ARMY or RAT OGORS), then when it's used.

Before the game, pull the regiment and enhancement tokens for the chosen picks and keep them with the warscroll cards. The Warp-Fury token goes beside the Rat Ogors. Flip a once-per-battle token when it's used.

### Gnawfeast Clawpack

Regiment abilities, back reads ARMY:

| Ability | Rule (front) | When (back) |
|---|---|---|
| Warpstone-Laced Bullets | 1 GUN: CRIT (MORTAL) | ONCE PER BATTLE · SHOOTING PHASE |
| Too Quick to Hit-hit | RETREAT: NO MW | PASSIVE |

Enhancements, back reads GENERAL:

| Enhancement | Rule (front) | When (back) |
|---|---|---|
| Lead the Seething Horde | REINFORCE WITHIN 13" | REACTION · REINFORCEMENTS |
| Skryre Connections | PISTOL: 2D6 ATTACKS | PASSIVE |
| Warpstone Charm | -1 SAVE IN COMBAT | PASSIVE |
| Cloak of Stitched Victories | GENERAL: WARD 5+ | PASSIVE |

Rat Ogors warscroll, back reads RAT OGORS:

| Ability | Rule (front) | When (back) |
|---|---|---|
| Unleashed Warp-Fury | D3 MW SELF, +1 ATK | ONCE PER BATTLE · COMBAT PHASE |

### Warpspark Clawpack

Regiment abilities, back reads ARMY:

| Ability | Rule (front) | When (back) |
|---|---|---|
| Warpstone-Laced Armour | STORMFIENDS: WARD 5+ | ONCE PER BATTLE · REACTION |
| Endless Swarm of Rats | SEETHING SWARM: D6 | PASSIVE |

Enhancements, back reads GENERAL:

| Enhancement | Rule (front) | When (back) |
|---|---|---|
| Skilled Manipulator | WARD 4+ BY CLANRATS | PASSIVE |
| Skitterleap | CAST 6+: REDEPLOY >6" | HERO PHASE |
| Cage of Warp Lightning | 6": 2+ STRIKE-LAST | ONCE PER BATTLE · COMBAT PHASE |
| Scurry Away | 3+: RETREAT, NO MW | COMBAT PHASE |

### Damage trays

An arrow-shaped plate, 22×40×6.5mm, with a pocket for one 16mm d6. The die shows the damage on the unit's currently wounded model, and the arrow points at the unit. The Warp Lightning Cannon has 8 Health and can carry 7 damage, so it gets a **double tray** (41×40mm) with two die pockets side by side.

| Tray | Used by | Print |
|---|---|---|
| Single | Clawlord, Grey Seer, Warlock Engineer, Rat Ogors / Grey Seer, Stormfiends | ×4 |
| Double | Warp Lightning Cannon | ×1 |

A single tray also works for *Will of the Horned Rat*: set the die to the roll and park the tray beside the target unit until the start of your next turn.

{{< carousel images="gallery/*" aspectRatio="1-1" interval="3000" >}}

## The box

The box has the same footprint as the Hashut and Khorne boxes (165.5×131.2×24.5mm) and uses the same column layout. Every well is 22mm deep:

- **Left column:** 2 ability-token wells, long side front to back, 7 tokens each: one per Spearhead. Each well has a lift notch through the left wall.
- **Right column, front:** a 123×73mm slot for the warscroll cards, with a notch through the front wall. The floor carries a cards + die icon.
- **Right column, back:** 2 arrow-shaped wells holding 3 single trays each, a double-tray well, and a closed dice well (24×51mm, 3 spare d6 in a row). The tray wells are notched through the back wall.

The underside carries the Mythos logo, inlaid flush.

{{< figure src="gallery/box_base_underside.png" caption="Underside: Mythos logo" >}}

**Lid:** it slips over the base with a full-height skirt. The top carries the Horned Rat head with the rune in each corner. The inside face carries a dice icon: flip the lid over and it's a dice tray.

{{< figure src="gallery/box_lid_top_face.png" caption="Lid top: Horned Rat head and corner runes" >}}

{{< figure src="gallery/box_lid_as_dice_tray.png" caption="Lid flipped over as a dice tray" >}}

## Measuring gauges

The Small (½", 1", 2", 3") and Medium (1", 3", 6", 9") gauges from the [Measuring Gauges]({{< ref "/printables/measuring-gauges" >}}) set, with the Horned Rat rune as the front badge. The back keeps the Mythos badge.

{{< figure src="gallery/small_skaven_front.png" caption="Small, Skaven front" >}}

{{< figure src="gallery/medium_skaven_front.png" caption="Medium, Skaven front" >}}

## Downloads

Each piece comes as a base + inlay STL pair and an `_anycubic.3mf` (Anycubic Slicer Next's own per-part filament metadata); tokens, trays and box also have a plain `.3mf`. Everything prints in two colours, base in slot 1 and inlay in slot 2. Set `BASE_EXTRUDER_SLOT`/`INLAY_EXTRUDER_SLOT` in the scripts to whatever's loaded.

**Tokens, Gnawfeast:**

- Unleashed Warp-Fury — [base](downloads/gnawfeast_warp_fury_base.stl) · [inlay](downloads/gnawfeast_warp_fury_inlay.stl) · [Anycubic 3MF](downloads/gnawfeast_warp_fury_anycubic.3mf) · [plain 3MF](downloads/gnawfeast_warp_fury.3mf)
- Warpstone-Laced Bullets — [base](downloads/gnawfeast_bullets_base.stl) · [inlay](downloads/gnawfeast_bullets_inlay.stl) · [Anycubic 3MF](downloads/gnawfeast_bullets_anycubic.3mf) · [plain 3MF](downloads/gnawfeast_bullets.3mf)
- Too Quick to Hit-hit — [base](downloads/gnawfeast_too_quick_base.stl) · [inlay](downloads/gnawfeast_too_quick_inlay.stl) · [Anycubic 3MF](downloads/gnawfeast_too_quick_anycubic.3mf) · [plain 3MF](downloads/gnawfeast_too_quick.3mf)
- Lead the Seething Horde — [base](downloads/gnawfeast_seething_horde_base.stl) · [inlay](downloads/gnawfeast_seething_horde_inlay.stl) · [Anycubic 3MF](downloads/gnawfeast_seething_horde_anycubic.3mf) · [plain 3MF](downloads/gnawfeast_seething_horde.3mf)
- Skryre Connections — [base](downloads/gnawfeast_skryre_base.stl) · [inlay](downloads/gnawfeast_skryre_inlay.stl) · [Anycubic 3MF](downloads/gnawfeast_skryre_anycubic.3mf) · [plain 3MF](downloads/gnawfeast_skryre.3mf)
- Warpstone Charm — [base](downloads/gnawfeast_warp_charm_base.stl) · [inlay](downloads/gnawfeast_warp_charm_inlay.stl) · [Anycubic 3MF](downloads/gnawfeast_warp_charm_anycubic.3mf) · [plain 3MF](downloads/gnawfeast_warp_charm.3mf)
- Cloak of Stitched Victories — [base](downloads/gnawfeast_cloak_base.stl) · [inlay](downloads/gnawfeast_cloak_inlay.stl) · [Anycubic 3MF](downloads/gnawfeast_cloak_anycubic.3mf) · [plain 3MF](downloads/gnawfeast_cloak.3mf)

**Tokens, Warpspark:**

- Warpstone-Laced Armour — [base](downloads/warpspark_armour_base.stl) · [inlay](downloads/warpspark_armour_inlay.stl) · [Anycubic 3MF](downloads/warpspark_armour_anycubic.3mf) · [plain 3MF](downloads/warpspark_armour.3mf)
- Endless Swarm of Rats — [base](downloads/warpspark_endless_swarm_base.stl) · [inlay](downloads/warpspark_endless_swarm_inlay.stl) · [Anycubic 3MF](downloads/warpspark_endless_swarm_anycubic.3mf) · [plain 3MF](downloads/warpspark_endless_swarm.3mf)
- Skilled Manipulator — [base](downloads/warpspark_manipulator_base.stl) · [inlay](downloads/warpspark_manipulator_inlay.stl) · [Anycubic 3MF](downloads/warpspark_manipulator_anycubic.3mf) · [plain 3MF](downloads/warpspark_manipulator.3mf)
- Skitterleap — [base](downloads/warpspark_skitterleap_base.stl) · [inlay](downloads/warpspark_skitterleap_inlay.stl) · [Anycubic 3MF](downloads/warpspark_skitterleap_anycubic.3mf) · [plain 3MF](downloads/warpspark_skitterleap.3mf)
- Cage of Warp Lightning — [base](downloads/warpspark_cage_base.stl) · [inlay](downloads/warpspark_cage_inlay.stl) · [Anycubic 3MF](downloads/warpspark_cage_anycubic.3mf) · [plain 3MF](downloads/warpspark_cage.3mf)
- Scurry Away — [base](downloads/warpspark_scurry_away_base.stl) · [inlay](downloads/warpspark_scurry_away_inlay.stl) · [Anycubic 3MF](downloads/warpspark_scurry_away_anycubic.3mf) · [plain 3MF](downloads/warpspark_scurry_away.3mf)

**Generic token and trays:**

- Generic hex rune token (spare, no ability) — [base](downloads/skaven_token_base.stl) · [inlay](downloads/skaven_token_inlay.stl) · [Anycubic 3MF](downloads/skaven_token_anycubic.3mf) · [plain 3MF](downloads/skaven_token.3mf)
- Damage tray (×4) — [base](downloads/damage_tray_base.stl) · [inlay](downloads/damage_tray_inlay.stl) · [Anycubic 3MF](downloads/damage_tray_anycubic.3mf) · [plain 3MF](downloads/damage_tray.3mf)
- Double damage tray (×1) — [base](downloads/damage_tray_double_base.stl) · [inlay](downloads/damage_tray_double_inlay.stl) · [Anycubic 3MF](downloads/damage_tray_double_anycubic.3mf) · [plain 3MF](downloads/damage_tray_double.3mf)

**Box:**

- Base — [base](downloads/box_base_base.stl) · [inlay](downloads/box_base_inlay.stl) · [Anycubic 3MF](downloads/box_base_anycubic.3mf) · [plain 3MF](downloads/box_base.3mf)
- Lid — [base](downloads/box_lid_base.stl) · [inlay](downloads/box_lid_inlay.stl) · [Anycubic 3MF](downloads/box_lid_anycubic.3mf) · [plain 3MF](downloads/box_lid.3mf)

**Measuring gauges:**

- Small — [base](downloads/small_skaven_base.stl) · [inlay](downloads/small_skaven_inlay.stl) · [Anycubic 3MF](downloads/small_skaven_anycubic.3mf)
- Medium — [base](downloads/medium_skaven_base.stl) · [inlay](downloads/medium_skaven_inlay.stl) · [Anycubic 3MF](downloads/medium_skaven_anycubic.3mf)

The gauge script lives with the [Measuring Gauges]({{< ref "/printables/measuring-gauges" >}}) post.

**Scripts** (Blender, headless) for adjusting sizes or counts: [build_skaven_tokens.py]({{< script "skaven-tokens/build_skaven_tokens.py" >}}) · [build_spearhead_box.py]({{< script "spearhead-box/build_spearhead_box.py" >}}) (`-- --force skaven`) · [extract_icon_contours.py]({{< script "icon-trace/extract_icon_contours.py" >}})

**Icon contours** (the scripts read them by relative path, so keep the folder layout from these URLs): [rat_rune_contours.json]({{< script "assets/icons/rat_rune_contours.json" >}}) · [rat_head_contours.json]({{< script "assets/icons/rat_head_contours.json" >}}) · [dice_roll_contours.json]({{< script "assets/icons/dice_roll_contours.json" >}}) · [cards_contours.json]({{< script "assets/icons/cards_contours.json" >}}) · [die_five_contours.json]({{< script "assets/icons/die_five_contours.json" >}}) · [logo_contours_v5.json]({{< script "card-stand/logo_contours_v5.json" >}})
