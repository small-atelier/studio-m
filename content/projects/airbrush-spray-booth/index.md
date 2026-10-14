---
title: "Airbrush Spray Booth"
date: 2026-08-30
draft: true
tags: ["build", "airbrush", "workshop"]
---

{{< lead >}}
Design note, not a build yet. A spray booth for airbrush work — two alternatives aimed at two different locations, not two competing designs for the same spot. Plexi + plywood construction either way, with extraction, cleaning-waste handling, and lighting as shared concerns.
{{< /lead >}}

{{< figure src="gallery/floor-ducted-sketch.png" caption="Concept sketch, Alternative A — two-bay shop booth: plexi divider, plexi roof + LED, S-baffle, shared compressor with Y-split to two regulated lines, per-bay cleaning catchers" >}}

{{< figure src="gallery/bench-sketch.png" caption="Concept sketch, Alternative B — benchtop, single station, same system scaled down with its own dedicated compressor" >}}

---

## The idea

Two builds, two locations — not a bench-vs-floor tradeoff to pick one winner from. Both share the same underlying system: an enclosure with extraction, air supply for the airbrush kept fully separate from the extraction fan, an overspray baffle ahead of the fan, a wet catcher for cleaning waste (unrelated to the air path), and shadow-free lighting to judge color while spraying.

## Alternative A — floor-standing, ducted, two bays

One floor cabinet, two working spaces side by side, split by a removable plexiglass divider — lets both bays run independently or opens up into one wide space for bigger pieces. Plexiglass panel across the top for visibility, with integrated lighting built into the roof structure. Extraction pickups from both bays feed a shared plenum at the back with an S-shaped baffle — the airflow has to change direction sharply, which knocks heavier overspray out of the airstream by inertia before it reaches the fan. From there, a flexible hose connects the booth to a fixed duct in the wall, out to the exterior.

**Air supply** is one shop compressor with a tank, sized for two airbrushes potentially drawing at once. Single trunk line → moisture trap → Y-split into two branches, each with its own pressure regulator + gauge, down to each bay's airbrush. Regulators live at the Y/branch point rather than back at the compressor, so each person dials in their own pressure independently.

**Cleaning station per bay:** a PET bottle with a cyclone lid, mounted at each station — not part of the extraction airflow at all, just a contained rinse-waste catcher for flushing the airbrush between colors. Splash/mist stays in the bottle instead of going everywhere.

## Alternative B — benchtop

Smaller plexi + plywood box, sitting on a workbench, single station. Same core system as Alternative A scaled down to one bay: plexiglass top panel with integrated LED lighting, a mini version of the S-shaped overspray baffle ahead of the fan, and a flexible hose run to a nearby window instead of fixed wall ducting. Lower footprint and no wall penetration needed — the tradeoff is it's sized for single-mini work and is a worse fit for solvent-heavy paints if the flex run is short or leaky.

**Air supply:** its own dedicated small compressor (not tapped off A's shop compressor) — self-contained regardless of where the bench ends up relative to the shop model. Same chain otherwise: compressor → moisture trap → regulator + gauge → airbrush, just no Y-split since it's one station.

**Cleaning station:** same PET bottle + cyclone-lid catcher as each bay in Alternative A — one build to document instead of two different waste-catcher designs.

## Shared components

- **Extraction fan:** sized for static pressure through the duct run, not just open-air CFM.
- **Overspray catcher:** an S-shaped baffle forcing a sharp airflow direction change, so heavier overspray drops out by inertia before the air reaches the fan/duct. One per booth — shared across both bays in A, single (mini) version in B. Not one per bay/station.
- **Air supply (separate system from extraction):** compressor(+tank) → moisture trap → regulator + gauge close to each airbrush (not just at the compressor, to avoid pressure drop over hose length) → braided hose → quick-disconnect → airbrush. A splits this after the moisture trap via a Y into two independently-regulated branches; B has its own dedicated compressor and skips the Y entirely.
- **Cleaning-waste catcher:** PET bottle with a cyclone lid, used for airbrush rinse waste — a wet/liquid catcher for cleaning, not part of the air extraction path. Same design at every station in both builds.
- **Plexi top + lighting:** both builds get a plexiglass top panel with integrated LED lighting built in, high-CRI (90+), angled down/back to avoid glare off wet paint and mounted clear of the direct overspray path so it doesn't film over.

## Design assumptions (unvalidated)

- **Location for Alternative A:** not yet decided — needs a wall with a viable duct run (already assumed to exist as a fixed wall duct, per the shop-model description — location for that duct not confirmed).
- **Location for Alternative B:** near an existing window, short flex run.
- **Cabinet/booth dimensions:** not pinned down for either. A also needs a real per-bay width once actual airbrush/piece working space is decided.
- **Fan sizing (CFM/static pressure):** not calculated for either build. A's fan has to move air from two bays through an S-baffle and a hose run to the wall duct — more restrictive than a straight duct, so needs its own sizing pass rather than reusing a generic number.
- **Compressor (A):** shop compressor with tank, sized to feed two airbrushes at once without pressure sag — model/CFM not chosen yet.
- **Compressor (B):** own dedicated small compressor, separate from A's — model/CFM not chosen yet.
- **Divider construction (A):** "removable" plexi divider between bays — mounting/slide mechanism not designed.
- **S-baffle sizing (B):** scaled down from A's version but not dimensioned — how small it can go before it stops doing anything useful at low CFM is unknown.

## Open questions

- Does Alternative A get built first, or does the cheaper/faster Alternative B come first as a stopgap while A's location (wall duct, two-bay footprint) gets sorted?
- Exterior vent detail for A — where does the wall duct actually terminate outside?
- S-baffle geometry — how sharp/long the direction change needs to be to actually knock down overspray without killing static pressure too badly, for both the full-size (A) and mini (B) versions.
- Real dimensions for both: A driven by per-bay working space × 2, B driven by largest single piece sprayed on the bench.

## Possible components

* Plywood carcass (A: two-bay cabinet + legs, B: small box)
* Plexiglass top panel (both) + removable plexiglass divider (A, between bays)
* Inline centrifugal duct fan (both, sized differently)
* S-shaped overspray baffle (both, full-size in A / mini in B)
* Fixed wall duct + flexible hose connector (A) / flexible hose to window (B)
* Shop air compressor + tank (A, shared between bays) / dedicated small compressor (B)
* Inline moisture trap
* Y-split to two branches (A only)
* Pressure regulator + gauge per airbrush
* Braided air hose + quick-disconnect
* PET bottle + cyclone lid cleaning-waste catcher (per station, both builds)
* High-CRI integrated LED lighting (both, built into the plexi top)
* Airbrush holder/stand

Near-term goal: pin down real dimensions and fan sizing for at least one of the two, and decide which gets built first.
