---
title: "A Modular Magnetic Miniature Storage System"
date: 2026-08-22
draft: true
tags: ["3d-printing", "design", "blender", "python", "storage"]
---

{{< lead >}}
Design note, not a build yet. A stackable, modular tray system for transporting painted miniatures: small 3D-printed corner posts and stacking connectors holding cheap flat panels (plywood or acrylic) and a thin steel floor that magnetic miniature bases stick to.
{{< /lead >}}

{{< figure src="gallery/exploded-tray-sketch.png" caption="Concept sketch, one tray exploded — steel floor, corner brackets, side panels, stacking pin/socket" >}}

{{< figure src="gallery/corner-bracket-low.png" caption="corner_bracket_v1_low.stl — low-profile tier, generated and rendered in Blender" >}}
{{< figure src="gallery/corner-bracket-tall.png" caption="corner_bracket_v1_tall.stl — tall tier, same part, taller post" >}}

---

## The idea

Each tray is a shallow removable box with a thin ferromagnetic steel plate as its floor. Miniatures with small magnets in their bases attach directly to the steel, holding them in place during transport and lifting off easily when needed.

Only the corner posts, rails, and stacking connectors are printed — side panels are cut from cheap flat sheet material (plywood, acrylic) rather than printing the whole box. Keeps print time and material low while the case's overall footprint stays easy to customize.

Every tray has the same stacking interface: a locating pin on top, a matching socket on the bottom. Trays stack into a tower and stay put, but each tray also lifts off individually and works as its own transport tray or is usable directly on the table.

Different tray heights reuse the same corner-post part — a low-profile tier for infantry, a taller tier for cavalry, monsters, vehicles, or raised scenic bases.

## Design assumptions (unvalidated)

- **Footprint:** not yet pinned down. No existing case standard checked against.
- **Tray height tiers:** ~28mm interior (low, infantry-scale) and ~48mm interior (tall, monster/vehicle-scale) — same corner bracket, different post height.
- **Panel material:** 3mm plywood or acrylic.
- **Floor:** ~1mm ferromagnetic steel sheet.
- **Fastening:** slot friction-fit for v1. Screws/heat-set inserts are a likely v2 addition once the slot fit is validated on a real print — not designed yet.

## What exists so far

- `blender/portable-storage/corner_bracket_v1.py` — Blender/Python script for the corner post: panel slots on two faces, a narrower floor-retaining slot at the base, and the pin/socket stacking interface, in both height tiers. Working directory renamed from an earlier "olle-storage" codename to something that actually describes the project. Geometry is now verified — ran clean in Blender 5.1.2 (headless, both tiers, clean booleans, sane volumes) and exported real STLs (above), rather than sitting as untested code.
- `corner_bracket_v1_low.stl` / `corner_bracket_v1_tall.stl` in this post's `stl/` folder.
- One concept sketch (above), generated via the Gemini illustration pipeline (`illustrations/generate_illustration.py`, sketch style).

## Open questions

- The panel slot's far wall reads as a thin standing fin in the render (confirmed real geometry via a top-down cross-section check, not a boolean artifact) — worth watching on the first physical print. A thin tall rib can be geometrically sound and still warp or snap in FDM.
- Real footprint / case-standard decision.
- Steel floor weight across a full stack — steel in every tray, or an optional insert only for trays used loose on the table.
- Assembly order for sliding the floor and panels into the corner-post slots.
- Whether snap-fit alone holds up to repeated assembly/disassembly, or corners need screws from the start.

## Possible components

* Standard magnetic miniature tray
* Low-profile infantry tray
* Tall miniature/monster tray
* Vehicle tray
* Removable steel floor
* Plywood or acrylic side panels
* 3D-printed corner brackets
* 3D-printed stacking connectors
* Carrying handle
* Removable or hinged lid
* Magnetic or mechanical latches
* Optional dividers
* Optional foam or padded protective inserts
* Optional label holders for identifying the contents of each tray

Most of this list is v2+. The near-term goal is just: tray + steel floor + corner bracket + stacking interface, proven to hold and stack.
