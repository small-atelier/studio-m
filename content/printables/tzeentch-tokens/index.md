---
title: "Disciples of Tzeentch Spearhead Tokens & Box"
date: 2026-10-19
draft: false
tags: ["3d-printing", "warhammer", "age-of-sigmar", "multi-material"]
---

{{< lead >}}
A token kit covering both Disciples of Tzeentch Spearheads, *Fluxblade Coven* and *Tzaangor Warflock*: hex tokens for regiment and enhancement picks and for lingering spell effects, damage trays, and a carry box with a Tzeentch flame lid and a rack for the Destiny Dice. The same kit exists for [Helsmiths of Hashut]({{< ref "/printables/hashut-game-tokens" >}}), [Blades of Khorne]({{< ref "/printables/khorne-tokens" >}}) and [Skaven]({{< ref "/printables/skaven-tokens" >}}).
{{< /lead >}}

{{< figure src="gallery/box_base_only.png" caption="Base: hex-token wells on the left, card slot up front, tray wells, the Destiny Dice rack and a spare dice well at the back" >}}

---

The two Tzeentch Spearheads:

- **[Fluxblade Coven]({{< ref "/spearhead/fluxblade-coven" >}}):** Magister on Disc, 3 Flamers, 3 Screamers, 2× 5 Tzaangors, 10 Kairic Acolytes
- **[Tzaangor Warflock]({{< ref "/spearhead/tzaangor-warflock" >}}):** Tzaangor Shaman, 10 Tzaangors, 3 Enlightened, 3 Skyfires

Fluxblade Coven's resource is **Masters of Destiny**: 9 dice rolled at the start of the first battle round and set aside. Casting, run, charge, hit, wound and save rolls can be replaced by a destiny die, which is then discarded. The pool needs a home where the values stay put and can't get mixed with rolling dice. Warflock has no pool of its own.

What gets forgotten mid-game is which regiment ability and enhancement were picked, whether a once-per-battle ability has been spent, and which unit a spell is still sitting on until the start of the next turn. The tokens cover those.

## What's in the kit

**Hex tokens** (33mm, pointy-top): the front shows the effect (Tzeentch flame, a big value and a short label). The back shows the ability's name. Once-per-battle abilities have the Chaos star on the back instead: flip the token when the ability is spent.

| Spearhead | Token | Kind | Front | Back |
|---|---|---|---|---|
| Fluxblade | Transient Forms | regiment | 4+ RETURN | TRANSIENT FORMS |
| Fluxblade | Eternal Conflagration | regiment | +1 REND | ETERNAL FIRE |
| Fluxblade | Shield of Fate | enhancement, lingering | 6+ WARD | SHIELD OF FATE |
| Fluxblade | Glimpse the Future | enhancement | +1 DESTINY | GLIMPSE |
| Fluxblade | Daemonheart | enhancement, once per battle | MW = ROUND | Chaos star |
| Fluxblade | Timeslip Pendant | enhancement, once per battle | LAST STRIKE | Chaos star |
| Warflock | Constant Flux | regiment | -1 REND | CONSTANT FLUX |
| Warflock | Arcane Ritualists | regiment | +1 CAST | ARCANE RITUAL |
| Warflock | Predicted Strike | enhancement, once per battle | D6" MOVE | Chaos star |
| Warflock | Fold Reality | enhancement | 6+ LEAP | FOLD REALITY |
| Warflock | Infernal Gateway | enhancement | 5+ MW | INFERNAL GATEWAY |
| Warflock | Mutagenic Sorcery | enhancement | D3 MW | MUTAGEN SORCERY |
| Warflock | Mutative Aura | Shaman spell, lingering | 1s MW | MUTATIVE AURA |

Before the game, pull the regiment token and the enhancement token for the chosen picks and put them beside the general.

The two lingering tokens go beside the unit they affect and come back at the start of your next turn:

- **Shield of Fate:** beside the friendly target. A unit that already has a ward (Flamers, Screamers) gets +1 to its ward rolls instead, so 6+ becomes 5+.
- **Mutative Aura:** beside the enemy target. Each unmodified hit roll of 1 in its combat attacks inflicts 1 mortal damage on it.

**Damage trays:** the arrow-shaped plate from the other kits, 22×40×6.5mm, with a pocket for one 16mm d6. The die shows the damage on the unit's currently wounded model, and the arrow points at the unit. No model in either force has more than 6 Health, so single trays cover everything.

| Spearhead | Trays for | Count |
|---|---|---|
| Fluxblade | Magister, Flamers, Screamers, Tzaangors, Tzaangors | 5 |
| Warflock | Shaman, Enlightened, Skyfires, Tzaangors | 4 |

Print ×5. Kairic Acolytes have 1 Health and don't need one.

{{< carousel images="gallery/*" aspectRatio="1-1" interval="3000" >}}

## The box

The box has the same footprint as the other Spearhead boxes (165.5×131.2×24.5mm) and uses the same column layout. Every well is 22mm deep:

- **Left column:** 3 stacked hex wells, 7 tokens each: Fluxblade picks, Warflock picks, spares. Each well has a lift notch through the left wall.
- **Right column, front:** a 123×73mm slot for the warscroll cards, with a notch through the front wall. The floor carries a cards + die icon.
- **Right column, back:** 2 arrow-shaped wells holding 3 trays each, the Destiny Dice rack, and a closed dice well for 16mm spares. The rack has 9 fixed slots for 12mm d6, cut 6mm into the top face so each die sits half in, half out. At the table, with the lid off, put each rolled destiny die in a slot face up and take it out when it's spent.

The underside carries the Mythos logo, inlaid flush.

{{< figure src="gallery/box_base_underside.png" caption="Underside: Mythos logo" >}}

**Lid:** it slips over the base with a full-height skirt. The top carries the Tzeentch flame with the Chaos star in each corner. The inside face carries a dice icon: flip the lid over and it's a dice tray.

{{< figure src="gallery/box_lid_top_face.png" caption="Lid top: Tzeentch flame and Chaos star corners" >}}

{{< figure src="gallery/box_lid_as_dice_tray.png" caption="Lid flipped over as a dice tray" >}}

## Downloads

Each piece comes as a base + inlay STL pair, an `_anycubic.3mf` (Anycubic Slicer Next's own per-part filament metadata) and a plain `.3mf`. Everything prints in two colours, base in slot 1 and inlay in slot 2. Set `BASE_EXTRUDER_SLOT`/`INLAY_EXTRUDER_SLOT` in the scripts to whatever's loaded.

**Tokens, Fluxblade Coven:**

- Transient Forms — [base](downloads/fluxblade_transient_forms_base.stl) · [inlay](downloads/fluxblade_transient_forms_inlay.stl) · [Anycubic 3MF](downloads/fluxblade_transient_forms_anycubic.3mf) · [plain 3MF](downloads/fluxblade_transient_forms.3mf)
- Eternal Conflagration — [base](downloads/fluxblade_conflagration_base.stl) · [inlay](downloads/fluxblade_conflagration_inlay.stl) · [Anycubic 3MF](downloads/fluxblade_conflagration_anycubic.3mf) · [plain 3MF](downloads/fluxblade_conflagration.3mf)
- Shield of Fate — [base](downloads/fluxblade_shield_of_fate_base.stl) · [inlay](downloads/fluxblade_shield_of_fate_inlay.stl) · [Anycubic 3MF](downloads/fluxblade_shield_of_fate_anycubic.3mf) · [plain 3MF](downloads/fluxblade_shield_of_fate.3mf)
- Glimpse the Future — [base](downloads/fluxblade_glimpse_base.stl) · [inlay](downloads/fluxblade_glimpse_inlay.stl) · [Anycubic 3MF](downloads/fluxblade_glimpse_anycubic.3mf) · [plain 3MF](downloads/fluxblade_glimpse.3mf)
- Daemonheart — [base](downloads/fluxblade_daemonheart_base.stl) · [inlay](downloads/fluxblade_daemonheart_inlay.stl) · [Anycubic 3MF](downloads/fluxblade_daemonheart_anycubic.3mf) · [plain 3MF](downloads/fluxblade_daemonheart.3mf)
- Timeslip Pendant — [base](downloads/fluxblade_timeslip_base.stl) · [inlay](downloads/fluxblade_timeslip_inlay.stl) · [Anycubic 3MF](downloads/fluxblade_timeslip_anycubic.3mf) · [plain 3MF](downloads/fluxblade_timeslip.3mf)

**Tokens, Tzaangor Warflock:**

- Constant Flux — [base](downloads/warflock_constant_flux_base.stl) · [inlay](downloads/warflock_constant_flux_inlay.stl) · [Anycubic 3MF](downloads/warflock_constant_flux_anycubic.3mf) · [plain 3MF](downloads/warflock_constant_flux.3mf)
- Arcane Ritualists — [base](downloads/warflock_ritualists_base.stl) · [inlay](downloads/warflock_ritualists_inlay.stl) · [Anycubic 3MF](downloads/warflock_ritualists_anycubic.3mf) · [plain 3MF](downloads/warflock_ritualists.3mf)
- Predicted Strike — [base](downloads/warflock_predicted_strike_base.stl) · [inlay](downloads/warflock_predicted_strike_inlay.stl) · [Anycubic 3MF](downloads/warflock_predicted_strike_anycubic.3mf) · [plain 3MF](downloads/warflock_predicted_strike.3mf)
- Fold Reality — [base](downloads/warflock_fold_reality_base.stl) · [inlay](downloads/warflock_fold_reality_inlay.stl) · [Anycubic 3MF](downloads/warflock_fold_reality_anycubic.3mf) · [plain 3MF](downloads/warflock_fold_reality.3mf)
- Infernal Gateway — [base](downloads/warflock_infernal_gateway_base.stl) · [inlay](downloads/warflock_infernal_gateway_inlay.stl) · [Anycubic 3MF](downloads/warflock_infernal_gateway_anycubic.3mf) · [plain 3MF](downloads/warflock_infernal_gateway.3mf)
- Mutagenic Sorcery — [base](downloads/warflock_mutagenic_base.stl) · [inlay](downloads/warflock_mutagenic_inlay.stl) · [Anycubic 3MF](downloads/warflock_mutagenic_anycubic.3mf) · [plain 3MF](downloads/warflock_mutagenic.3mf)
- Mutative Aura — [base](downloads/warflock_mutative_aura_base.stl) · [inlay](downloads/warflock_mutative_aura_inlay.stl) · [Anycubic 3MF](downloads/warflock_mutative_aura_anycubic.3mf) · [plain 3MF](downloads/warflock_mutative_aura.3mf)

**Generic token and tray:**

- Generic flame token — [base](downloads/tzeentch_token_base.stl) · [inlay](downloads/tzeentch_token_inlay.stl) · [Anycubic 3MF](downloads/tzeentch_token_anycubic.3mf) · [plain 3MF](downloads/tzeentch_token.3mf)
- Damage tray (×5) — [base](downloads/damage_tray_base.stl) · [inlay](downloads/damage_tray_inlay.stl) · [Anycubic 3MF](downloads/damage_tray_anycubic.3mf) · [plain 3MF](downloads/damage_tray.3mf)

**Box:**

- Base — [base](downloads/box_base_base.stl) · [inlay](downloads/box_base_inlay.stl) · [Anycubic 3MF](downloads/box_base_anycubic.3mf) · [plain 3MF](downloads/box_base.3mf)
- Lid — [base](downloads/box_lid_base.stl) · [inlay](downloads/box_lid_inlay.stl) · [Anycubic 3MF](downloads/box_lid_anycubic.3mf) · [plain 3MF](downloads/box_lid.3mf)

**Scripts** (Blender, headless) for adjusting sizes or counts: [build_tzeentch_tokens.py]({{< script "tzeentch-tokens/build_tzeentch_tokens.py" >}}) · [build_spearhead_box.py]({{< script "spearhead-box/build_spearhead_box.py" >}}) (`-- --force tzeentch`) · [extract_icon_contours.py]({{< script "icon-trace/extract_icon_contours.py" >}})

**Icon contours** (the scripts read them by relative path, so keep the folder layout from these URLs): [tzeentch_flame_contours.json]({{< script "assets/icons/tzeentch_flame_contours.json" >}}) · [chaos_star_contours.json]({{< script "assets/icons/chaos_star_contours.json" >}}) · [dice_roll_contours.json]({{< script "assets/icons/dice_roll_contours.json" >}}) · [cards_contours.json]({{< script "assets/icons/cards_contours.json" >}}) · [die_five_contours.json]({{< script "assets/icons/die_five_contours.json" >}}) · [logo_contours_v5.json]({{< script "card-stand/logo_contours_v5.json" >}})

## Rules

- [Spearhead: Fluxblade Coven (PDF)](https://assets.warhammer-community.com/eng_01-04_aos_spearhead_disciples_of_tzeentch_fluxblade_coven-maph6dtofo-iasdohuesc.pdf)
- [Spearhead: Tzaangor Warflock (PDF)](https://assets.warhammer-community.com/eng_04-02_aos_spearhead_disciples_of_tzeentch-4mldohmkit-qcunidsq7c.pdf)
