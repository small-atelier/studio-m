---
title: "The Portable Hellforge"
date: 2026-08-23
draft: true
tags: ["3d-printing", "design", "python", "warhammer", "age-of-sigmar"]
---

{{< lead >}}
Design note for a themed transport/diorama box for the Helsmiths of Hashut Spearhead (Age of Sigmar, Chaos Dwarfs) — a wooden chest that carries the 14-model force and doubles as a one-piece forge-floor diorama when opened. Separate idea from the [modular magnetic storage box]({{< ref "/posts/modular-magnetic-storage-box" >}}) — no shared parts, just a shared corner-bracket mechanism worth reusing.
{{< /lead >}}

{{< figure src="gallery/box-exterior-sketch.png" caption="Exterior concept — stained wood, iron corner brackets, Hashut icon, HELFORGE HOST plate" >}}

{{< figure src="gallery/interior-sketch-v2.png" caption="Interior concept v2 — adds the Roaring Furnace as a standalone terrain structure and recessed base-socket callouts" >}}

{{< figure src="gallery/interior-sketch-v1.png" caption="Interior concept v1, kept for comparison — same composition, before the furnace and sockets were added" >}}

---

## The idea

A stained-wood chest with iron corner brackets, rivets, latches, and a Hashut icon embossed on the lid. Inside, the whole Spearhead sits on one continuous 3D-printed forge floor rather than 14 separate scenic bases — cracked stone, riveted plate, grates, and slag, printed in sections and joined at assembly. The box is the storage system and the diorama at the same time.

Composition is scattered, not ranked — the Dominator Engine (centerpiece) stands toward the back, the Tormentor Bombard sits off to one side, the War Despot holds front and center, and the Infernal Cohort works the floor in loose clusters rather than a parade-ground grid.

Don't have the Helforge Host box yet — this is pre-purchase planning, worked out against the real Citadel base sizes so the floor layout and box dimensions are usable once the models arrive rather than needing to be redone.

No electronics. Passive box, no lighting.

Separate project, same army: [Daemonic Power & Desolation Tokens]({{< ref "/posts/hashut-game-tokens" >}}) — the game-mechanic tokens this army spends the whole match shuffling around the table, not part of the box itself.

## Box contents (verified)

The Helforge Host Spearhead is 14 models on 5 base sizes:

| Unit | Count | Base size |
|---|---|---|
| Dominator Engine (with Immolation Cannons) | 1 | 100mm round |
| Tormentor Bombard | 1 | 80mm round |
| War Despot | 1 | 32mm round |
| Infernal Cohort | 10 | 28.5mm round |
| Hobgrot Gong-bearer | 1 | 25mm round |

Model heights aren't published anywhere I could find — box interior clearance is a placeholder until the models are in hand and can be measured directly.

## Forge-floor layout (v5) — packed tight, no floor growth

The 480×230mm floor from the previous pass was reversed — there was no real reason for it. Repacked tight back into the original **400×220mm**, by putting the two 100mm pieces (Dominator Engine, Roaring Furnace) diagonally opposite each other instead of side by side in the same row. That uses the floor's full diagonal instead of demanding two 100mm-wide clearances in one strip, and the box exterior stays within the original ~35–45cm target.

- **Dominator Engine** (100mm) — back-left
- **Roaring Furnace** (100mm, on a real base — see below) — front-right, diagonal from the Dominator
- **Tormentor Bombard** (80mm) — back-right
- **War Despot** (32mm) + **Hobgrot Gong-bearer** (25mm) — front and center
- **Infernal Cohort** (10× 28.5mm) — scattered through the remaining gaps

Tight packing came at a real cost: this repack needed 2 tiles, not 3 — a 3-way cut genuinely doesn't fit this density (see below), so both tiles ended up on the larger side (single straight seam at x=181, ~181mm and ~219mm wide, both still under the 220mm assumed bed).

`blender/hellforge/forge_floor_layout.py`'s seam-finder had two real bugs, both found by actually trying to cut this tighter layout into 3 tiles and both fixed rather than worked around:

1. **Seams weren't checked against each other**, only against the floor edges — a second seam could independently converge on the same gap as the first, pinching the middle tile to a sliver (or, worse, actually crossing the first seam in a different depth-band, which would have produced a self-intersecting tile boundary). Fixed by having each new seam search treat every already-placed seam as an exclusion zone too, with a minimum 25mm gap enforced **and** ordering enforced (seam 2 must stay to the right of seam 1 in every band, not just some minimum distance away in either direction).
2. Once that was fixed, 3 tiles genuinely failed outright for this composition — not a sliver, a real "no valid cut exists" result. Fell back to 2 tiles, which the (now-correct) checker confirmed clean. Documented as the actual tradeoff of packing tight: fewer, larger tiles, not a free lunch.

## Forge-floor layout (v6) — resized to a real found box

{{< figure src="gallery/forge-floor-layout.svg" caption="Forge floor, top-down, to scale — this diagram is regenerated as the layout changes, so it always shows the CURRENT state (currently v11: the FDM wedge cut, the resin quadrant split, the smelting pool and channels included), not a frozen v6 snapshot. See v11 further down for what changed most recently." >}}

A real candidate box turned up: **280×260mm interior**. Not a simple scale-down — the miniature bases are fixed real-world sizes (a 100mm Dominator base is 100mm regardless of what the floor is sized to), so shrinking the whole composition uniformly was never on the table. This is a genuine repack into a smaller, much more *square* footprint (280×260, aspect ~1.08:1) than the old 400×220 (aspect ~1.82:1), not a rescale.

**It fits.** Repacked with the same diagonal-corner trick as v5 (the two 100mm pieces — Dominator, Furnace — opposite corners), reworked for the squarer shape: Bombard moved up next to the Dominator along the back edge, Despot/Hobgrot stay front-and-center, the 10 Infernal Cohort redistributed through the resulting gaps. Checked with the same overlap checker as always, not eyeballed — took 3 rounds of real, flagged conflicts (infantry-vs-infantry, infantry-vs-Furnace) before landing clean. Tile seam needs one small jog (132mm back band, 119mm front band) — both tiles land comfortably under the 260mm bed either way.

One thing this surfaced: the SVG's legend text started getting clipped once the floor got narrower (the canvas scales with `FLOOR_W`, the legend string doesn't) — gave the canvas width a floor of its own (`max(..., 700)`) so it stops happening at any floor size, not just this one.

**Done — the print geometry is rebuilt for the new footprint.** `forge_floor_tiles_v3.py`'s sockets, paving grid, molten channels, props, and tile outlines all moved to the 280×260 layout and reran clean in Blender, first real attempt after fixing 4 flagged position conflicts (2 tab-clearance, 2 channel/prop clearance) before ever touching Blender:

- **Tile outlines are jogged polygons again**, not plain rectangles — the v6 seam steps at y=130 (132mm back band, 119mm front band), same shape as the layout SVG. `_seam_x_at(y)` picks the right seam x for any given y; used everywhere something needs to know which tile it's on or where the seam sits — socket assignment, dovetail tabs, paving cells.
- **Dovetail tabs moved and now respect the jog** — 3 positions (y=55, 145, 245), each looked up against its own band's seam x rather than a single shared value. The old fixed positions (y=40/105/160) didn't automatically carry over; 2 of the first 3 candidates I tried failed the clearance check against Cohort 6, Despot, and Hobgrot before landing on ones that actually clear everything.
- **Channels no longer cross the seam.** The old design had one pair of segments meeting at the seam to read as continuous once glued; the new front band is tight enough (Despot and Hobgrot sit close to where a crossing channel would have to pass) that forcing a crossing wasn't worth it. The Furnace's channels (up toward Bombard, down toward the front, one stub toward Despot) now all stay within tile_b.
- **Grate and all 4 props got new positions**, checked with the same `_clearance_ok()` helper as before, not carried over from the old layout (the old spots don't exist in the new geometry — different floor, different gaps).
- **Paving regenerated automatically** — 30 of 156 candidate cells survived at the smaller floor size, no manual work needed there.

`tile_a_fdm.stl` / `tile_a_resin.stl` / `tile_b_fdm.stl` / `tile_b_resin.stl` and all 15 toppers were the 280×260 version at this point — since superseded by the v7 rework below, which changes the FDM tiling entirely.

## v7 — the first real print failed, and why

Tried printing the FDM base plates. Failed — a stringy mess. The likely cause: every tile spanned the *full* 260mm bed depth (the seam only ever cut left-right), so both pieces were printed edge-to-edge with **zero margin**. The outer few mm of most beds run cooler and less consistently than the center, so a part that size is much more prone to a corner lifting mid-print — and once a corner lifts, the nozzle catches it, drags the loosened part around, and keeps extruding into open air. That presents as "stringy mess" even though the root cause is edge adhesion, not retraction settings.

Considered a straight 4-tile grid (cut once more at y=130, already a natural boundary in the composition) — simpler, but 3 pizza/Y-style wedges radiating from a center point won round margins better and needs one fewer seam. Two things worth recording about getting there:

**Checked before trusting it, twice.** A naive "3 even radial slices" of a *rectangle* (not an actual circular pizza) generically leaves at least one wedge spanning a full edge — by pigeonhole, 4 corners split among 3 wedges. Verified this by computing real wedge bounding boxes for several rotations before picking a cut, rather than assuming pizza-shaped intuition carries over to a rectangle. The specific cut used routes 2 of the 3 cuts through corners deliberately (center → each bottom corner, center → top-edge midpoint) to control which wedge is bounded by which edge. Then caught a second mistake in my own verification: the first bounding-box check used a *triangle* for the LEFT/RIGHT wedges, which is wrong — they're actually quadrilaterals (each includes the rectangle's own top corner). The wrong shape said 191×191mm at 45°; the corrected shape says **236×236mm** — still comfortably under the 260mm bed, just not as roomy as the wrong number implied. Caught before it became a second bad print, not after.

**Sockets are allowed to cross a seam.** Original assumption was that a socket hole couldn't straddle two tiles. It can — each tile gets a "bite" out of its edge, and gluing the two tiles together at the dovetail joint completes the hole, same as ordinary modular terrain. Only the *dovetail tab points themselves* need real clearance from anything, not the whole cut line. That one relaxation meant only **2 pieces** (of 6 originally flagged as conflicting) actually needed to move — the 100mm Roaring Furnace sits almost exactly *on* one of the cuts for most of its length and didn't need to move at all once its hole was allowed to cross it.

{{< figure src="gallery/tile-left-render.png" caption="tile_left_fdm.stl — quadrilateral wedge, 3 sockets (Dominator + 2 Cohort), tabs on both cut edges" >}}
{{< figure src="gallery/tile-right-render.png" caption="tile_right_fdm.stl — 9 sockets (Bombard, Furnace, 7 Cohort), tabs on one edge, pockets on the other" >}}
{{< figure src="gallery/tile-bottom-render.png" caption="tile_bottom_fdm.stl — true triangle, 3 sockets (Despot, Hobgrot, 1 Cohort), pockets on both edges" >}}

**The joints needed real rework, not just new positions.** The 3 cuts aren't axis-aligned (two run at odd corner-to-center angles, one runs straight up), so the dovetail tab code had to generalize from a fixed x-offset trapezoid to one built from an arbitrary along/perpendicular direction pair — and since a single tile can be the "male" (tab) side of one cut and the "female" (pocket) side of another (`tile_right` is both), the male/female assignment is now per-cut, not per-tile. The perpendicular direction for each tab — which way it reaches, from which tile into which — is resolved by actually probing which wedge a test point lands in (`_which_wedge()`), not derived by hand: getting a reach direction backwards by hand is exactly the kind of mistake this session already made twice with the wedge shapes.

Verified against sockets, not assumed: sampled 101 points along each cut and kept only ones with real clearance margin, same tool-driven approach as the whole layout. `BL` and `TOP` cuts got 3 tabs each; `BR` only 2, since the Furnace's exclusion zone covers most of its middle.

**Ran clean in Blender on the first real attempt** after the position/tab math was verified — 3 wedge shapes, 15 sockets split 3/9/3, dovetail tabs and pockets visible exactly where the male/female assignment says they should be, confirmed by render, not just trusted from the numbers.

**Scoped to the FDM slab only this pass.** The resin detail skin needs its own approach — it's headed for an Anycubic Photon Mono 2, whose build plate (~143×89mm) is much smaller than this floor. The socket positions (`ALL_SOCKETS`) are the stable, shared reference for both layers — the only positions that moved this round are the 2 flagged above, and there's no plan to move anything else. See v8 below for how resin is actually being approached.

## v8 — resin doesn't need tiling at all, and a two-stage workflow

Reconsidered the resin problem entirely rather than designing a second multi-piece cut scheme. The FDM slab needs tiling because it's one continuous *structural* piece that has to physically hold together — the resin layer doesn't have that constraint. Each base topper is captured as its own small independent STL already; even the largest (100mm, matching the Dominator/Furnace) fits the Photon Mono 2's bed once rotated diagonally in the slicer (same rotate-to-fit idea as the FDM wedges). So: no resin tile grid, no resin seams, no resin dovetail joints. Just print each topper on its own.

That reframes the whole resin pipeline into two explicit stages, matching how it should actually be worked:

1. **Terrain review** — build the *entire* 280×260 floor's decoration (panel-seam grooves, the grate, molten channels + flow, paving, hand-tool props) as ONE continuous piece, with no socket holes cut and no toppers captured yet. The surface is the thing to get right first; look at it before committing to anything downstream.
2. **Stamping** — only after the terrain above is reviewed and approved: cut every socket hole (base diameter + `SOCKET_GROWTH` margin — the exact same value and the exact same `ALL_SOCKETS` data the FDM slab's holes use, so the two layers line up by construction, not by coincidence) and capture each hole's plug as its own topper STL.

{{< figure src="gallery/master-resin-terrain.png" caption="Stage 1 — full-floor terrain, no holes cut yet. Paving runs continuously through where every socket will eventually go." >}}

Built and rendered stage 1 (`RESIN_STAGE = "review"` in the script) — ran clean, one continuous 84,314mm³ piece, all the existing decoration code (grooves/grate/channels/paving/props) reused as-is since none of it needed to change for the current socket layout, just applied to the whole floor instead of per-wedge. **This is a checkpoint, not a finished pass** — stage 2 (stamping 15 topper STLs + cutting the matching FDM-aligned holes) is written (`stamp_toppers_and_holes()`) but deliberately not run yet, waiting on this render actually being looked at first.

## v9 — smelting pool, the real furnace body, paving variety, and the actual stamp + split

The v8 review render checked out, so this pass went straight through the rest of the pipeline: more terrain detail, then stamp toppers/holes, then cut the holed master into print-sized pieces.

**Smelting pool.** A shallow basin around the Furnace's position that the 3 molten channels now visibly spill out of, rather than just starting mid-slab. Not a plain circle — the Furnace sits close enough to 3 Infernal Cohort sockets (as tight as ~55mm clear in some directions) that one fixed radius would either collide with a neighbor or, kept safe everywhere, shrink to a barely-there ~2mm rim. Computed the safe radius **per angle** instead: cast a ray from the Furnace's own center point in each of 48 directions, find where it first comes within a real margin of any other socket's hole or the floor edge, and use that as the basin's edge in that direction — checked numerically (line-circle intersection, same approach as the earlier tab-clearance searches), not assumed. Result ranges from 52.5mm (tight directions toward Cohort 4/5/9) out to 85mm on the open side toward the Despot. A handful of raised veins (6, offset from the channel angles so they don't duplicate them) run from the basin's inner edge outward, reading as metal creeping toward the rim.

**Paving got real variety and got denser.** One motif (square groove + inset circle) covering the whole floor started reading monotonous once there was this much of it. Two more patterns now: a diamond (the same square rotated 45°, still with the inset circle) and a plain hatch (an X, no circle). Assigned deterministically by grid position (`(col + row) % 3`), not randomly, so the layout is stable across re-runs. Pitch dropped from 20mm to 16mm for tighter coverage — 61 of 272 candidate cells survived the clearance checks (up from 39 of 156 at the coarser pitch, even with the new pool and 2 more props also claiming floor space now).

**Two more props** — an ingot pile (3 stacked rectangular blocks, slightly offset) and a chisel (same silhouette-extrusion approach as the hammer/anvil) — 6 props total now. The tongs had to move off its old spot at (270,150): that position turned out to sit inside the pool's open lobe once the pool existed, so it's now at (120,235), re-checked against everything the same way every other placement is.

**Stamped for real, not just staged.** `RESIN_STAGE = "stamp"` — all 14 socket holes cut (base diameter + `SOCKET_GROWTH` = +1mm, unchanged, the same value and the same `ALL_SOCKETS` data the FDM slab's holes already use, so the two layers match by construction) and all 14 toppers captured as their own STLs. Only 14 now, not 15 — see the furnace correction directly below; it's no longer one of the removable pieces.

**Then cut into 4 quadrants for the actual resin printer** (165×143×89mm bed, printed flat, no supports — corrected spec from the earlier "Photon Mono 2, ~143×89mm" placeholder). The now-holed master terrain is still one big 280×260mm connected sheet — too big for that bed — but unlike the FDM slab it's thin decoration glued onto a continuous structural layer underneath, so it doesn't need its own dovetail joints for strength. A plain 4-way split at the floor's center point (INTERSECT against 4 quadrant boxes, the same capture technique already used for toppers), each piece 140×130mm, comfortably inside the bed with real margin, butt-glued once seated on the FDM slab below.

## v10 — the furnace is fused into the terrain, not a removable piece

Got corrected on this one: the furnace was meant to be a permanent part of the terrain from the start, not a 15th removable model with its own socket and topper. Reworked accordingly:

- **`ALL_SOCKETS` dropped to 14 entries** — the 14 actual army models. The Furnace was always coded as "14 models + 1 terrain feature," and now it's *only* a terrain feature: no socket, no FDM hole, no resin hole, no topper STL.
- **The real kettle mesh is unioned directly into the resin skin** (`import_furnace_body()` + a plain `UNION` at the end of `build_resin_terrain`), positioned the same place the socket used to be. Tested this in isolation first before trusting it on the real pipeline — 178,212 triangles is a lot of untouched third-party geometry to boolean blind, exactly the scenario [[feedback_blender_boolean_fragility]] warns about. A plain slab+furnace union in a throwaway scene ran in 0.49s and landed on a volume that's *exactly* slab-volume + furnace-volume (no corruption, no runaway/collapsed result like the earlier channel-elbow bug produced) — just 10 non-manifold verts, typical for a complex hobby STL and not a sign of a failed boolean. Safe to wire in for real.
- **Caught a real bug this surfaced before it shipped**: the quadrant-split boolean (`split_into_quadrants`) INTERSECTs each quadrant against a box capped at `RESIN_THICKNESS + OVERSHOOT` (~2.2mm) — sized for a thin decorative skin. The furnace is 62.7mm tall. Left as-is, splitting into quadrants would have silently decapitated it to a 2mm stub. Fixed by capping the box at `RESIN_THICKNESS + FURNACE_HEIGHT + OVERSHOOT` instead, high enough to clear anything fused into the skin, not just the skin itself.
- **Real physical consequence, not just a code change**: fusing a 62.7mm-tall body into a 1.2mm sheet means the SE quadrant (the one the furnace landed in) can no longer be printed flat/no-supports like the other 3 — it needs to go in upright, supported, same as any tall mini. That's the actual tradeoff of "part of the terrain," not an oversight to fix later.

{{< figure src="gallery/furnace-pool-reference.png" caption="The furnace fused into the SE resin quadrant — genuinely one piece with the floor, not glued on after the fact" >}}

{{< figure src="gallery/resin-quadrant-sw-holes.png" caption="Straight-down check on the SW quadrant, lit to make the through-holes read as dark gaps — confirms real full-diameter holes, not partial cuts, and the paving/pattern grid tiling cleanly around them" >}}

Also worth recording: the same straddling-socket gap [[feedback_blender_boolean_fragility]]-adjacent bug the FDM slab had — a socket owned by one tile but cut only there, even where its circle pokes into a neighbor — doesn't apply to the resin quadrants. They're cut from the *already-holed* master via INTERSECT, so every hole is already a complete circle before the split ever happens; there's no equivalent "which tile cuts this socket" decision to get wrong.

## v11 — furnace corrected again, one shared master, and a real center

v10 went the wrong direction: dropping the Furnace's socket entirely wasn't actually what was wanted. Corrected: the Furnace stays on a 100mm base conceptually (same socket, same hole, same topper as every other model) — it's just that the topper capture happens *after* the real kettle body is already fused onto the terrain, so what gets stamped out is one piece: decoration + the real furnace, not a separate print to glue on by hand. And it should sit close to the true center of the composition, close enough to the FDM wedge cut's apex that it actually spans all 3 tiles, not just 2.

**One shared master, finally.** Split every piece of pure layout data (floor size, `ALL_SOCKETS`, the wedge cut, the pool math, molten channels, props, paving, the resin quadrant split) out of `forge_floor_tiles_v3.py` into a new `forge_floor_data.py` — plain Python, no `bpy`, importable by both the real Blender script and `forge_floor_layout.py` (the SVG planner). The SVG script had its own independent copy of the socket list before this, and it drifted out of sync 3 separate times (v6, v7, v9/v10) as things moved in the real script without anyone remembering to also update the planning diagram. Now there's exactly one place any of this can be wrong, and `python3 forge_floor_data.py` runs every layout assertion standalone in well under a second — no need to wait on a full Blender run just to check whether a position change is geometrically valid.

**Moving the Furnace to the center crowded out 4 other pieces.** Being within the furnace's own radius (50.5mm) of the wedge-cut apex is what actually guarantees the circle spans all 3 tiles — the 3 cuts radiate outward from that exact point, so any circle containing it gets sliced into 3 arcs automatically. But the exact apex collides with the Dominator Engine, and the best nearby spot still collided with War Despot, Hobgrot Gong-bearer, and Infernal Cohort 4 by 15-17mm each (checked numerically, a grid search over candidate centers, not eyeballed) — real conflicts, not a small nudge. Asked which way to handle it rather than silently deciding to shove 4 models around; the call was to move them. Final furnace center: **(148.5, 174)**, 44.5mm from the apex (a real 6mm safety margin inside the 50.5mm radius, not a knife-edge fit). Despot moved 19mm, Hobgrot 33mm, Cohort 4 16mm; Cohort 3 — already sitting almost exactly at the old wedge center from the v7 rework — turned out to already clear the new position and didn't need to move again.

**That one move cascaded into everything else near the center**, each caught and fixed the same way (search for real clearance, not guess, then verify with `forge_floor_data.py`'s own assertions):
- The dovetail tab positions on all 3 FDM cuts, not just BR — the furnace now crowds out near-center tab spots on every cut, not just one. Re-searched clear ranges per cut and picked new t-fractions with real margin.
- 3 of the 6 props (anvil, tongs, chisel) needed new spots — the bigger, closer smelting pool and the relocated models reached into their old positions.
- The molten channels needed rerouting from the furnace's new position entirely — recomputed safe cardinal-direction lengths the same way as the smelting pool's per-angle radius (line-circle intersection against every socket), then trimmed back from the safe maximum so they still read as "stops short" rather than edge-to-edge.

**A real render bug, caught by a volume check disagreeing with what the picture showed.** The first combined render of the split quadrants appeared to still show the fused furnace body sitting in the SE piece — alarming, since the whole point of re-stamping it as a topper was to remove it from the background master. But the exported quadrant STLs' volumes were normal-sized (~12,000mm³, not the ~70,000mm³+ a fused furnace would add), so the *files* were right and the *picture* was lying. Root cause: `bpy.ops.render.render()` renders every object currently in the scene, not just whatever list gets passed to `render_iso()` — and the 15 topper objects (kept around after each was exported to its own STL, never deleted) were still sitting at their original world positions, layered invisibly into every render from that point on. Fixed by having `render_iso()` temporarily hide every mesh object *not* in its own argument list before rendering, restoring visibility after — a render now actually shows only what it claims to.

**Verified the fix worked, not just assumed it.** Re-rendered the quadrant split: 4 pieces, clean circular holes (including one large one where the furnace was), no residual geometry. Rendered the furnace's own topper STL standalone: a 101×101×63.9mm piece — matches exactly (100mm base + 1mm growth, 1.2mm resin skin + 62.7mm furnace) — one continuous print with the full kettle body sitting on a round decorated base, not two parts to align and glue.

{{< figure src="gallery/furnace-pool-reference.png" caption="The furnace's own topper, rendered standalone — one piece, decorated base plus the full kettle body, captured together by a taller-than-usual cutter" >}}

{{< figure src="gallery/resin-quadrant-sw-holes.png" caption="The 4 resin quadrants after the render-isolation fix — clean holes only, no leftover furnace geometry from a stale scene object" >}}

{{< figure src="gallery/forge-floor-layout.svg" caption="The planning SVG, now generated from the same forge_floor_data.py the real print geometry uses - FDM wedge cut in red, resin quadrant split in blue, the smelting pool and molten channels drawn in for the first time" >}}

## Two-material print stack: FDM structure + resin detail (current as of v11)

Every miniature base in this project is being built the same way — a plain FDM base for structure (`blender/bases/bases.py`, magnets already in the base), with a thin resin topper glued on for detail, since resin holds fine surface detail FDM can't. The floor tiles now follow the identical split, "to match in thickness":

- **FDM structural slab** (4mm, matches `bases.py`'s own base `HEIGHT`) — the tile's basic shape, a shallow rebate on the *underside* sized to the whole tile for a steel sheet to slot into, and a **through-hole** at every socket position (not a blind recess — the model drops all the way through and rests on the steel sheet beneath).
- **Resin detail skin** (1.2mm, glued on top of the FDM slab) — carries all the fine surface detail: panel-seam grooves, the grate, rivets. Gets its own hole at every socket position too, cut **last**, after all the decoration.

Socket holes are base diameter **+1mm** (loose enough to lift the model back out, not a snug press fit) — that's what "+1mm for the base size" turned into: `SOCKET_GROWTH = 1.0` in the script.

The two FDM slabs join along the seam with 3 dovetail tabs — jigsaw-style, cut into the tile's own outline (in-plane, full slab thickness) rather than a separate perpendicular peg. First pass used plain round dowel pins; those were swapped out because a smooth round peg can just slide straight back out along its own axis — no actual lock. A dovetail (wider at the tip than at its base on the seam line) can't separate by a straight sideways pull, only by sliding along the seam or lifting apart before glue sets — the same principle as a real puzzle piece's mushroom-shaped tab, just built as a straight-sided trapezoid instead of a curved bulb, which is much simpler to extrude and boolean cleanly. Tabs on tile_a's edge, matching pockets on tile_b's, spaced to clear every socket by at least 2mm (checked with an assertion in the script). Permanent glued joint, not a repeatable connector like the storage-box's stacking pins — this floor lives fixed inside the box. The resin skin doesn't need its own joint; it just sits on top once the two FDM halves are glued. (Tile dimensions below reflect the current 280×260 layout — see the v6 section further down; both tiles still fit comfortably on the 260×260mm bed.)

Cutting the resin skin's holes last (after grooves/grate/rivets are already in place) turned out to double as the fix for last session's floating-rivet bug — a much better fix than the manual "exclude rivets near sockets" filter that pass used. If a rivet happens to land inside a hole's footprint, the hole-cutting pass just removes it along with everything else there, decoration or plain slab. No special-casing needed.

## Base toppers, for free

The resin skin's socket plug isn't scrap. Before each hole is actually cut, the script duplicates the (already decorated) skin and boolean-**intersects** the duplicate with that socket's cylinder — capturing the plug, whatever decoration happens to overlap it, as its own STL: a unique **base topper**, meant to be glued onto that same model's own separate FDM base for standalone tabletop use outside the box. 15 toppers came out of this run — one per army model, genuinely unique since each is cut from wherever that piece actually sits on the floor, plus the Roaring Furnace's own topper, which is special: its cutter is tall enough (63.9mm, not the usual 1.2mm) to capture the real fused kettle body along with the decorated base, not just a shaved-off disc. Confirmed one by inspection: the Dominator's topper picked up part of a rivet that happened to fall inside its socket footprint, captured correctly as part of that topper rather than orphaned.

No riser/spacer needed for height-matching — the topper (1.2mm) glues straight onto a standard 4mm FDM base, same as any other resin-topped base in the project.

## Roaring Furnace — adapted, not built from scratch

Found a genuinely good fit sitting in `input/spearhead/`: **[Boil Kettle & Tun System — Dwarven AleWorks](https://www.thingiverse.com/thing:2860871)** by ecaroth on Thingiverse (CC BY-NC — free for this non-commercial build, credit required, not for resale). It's a riveted copper/iron boiler vessel piped into a second smaller tank, mounted on a rough-hewn stone plinth, with — per the maker's own description — "a small furnace built-in below." Built for a dwarven brewery, but the aesthetic (dark riveted metal, exposed piping, industrial) reads as Chaos Dwarf foundry equipment with zero changes needed. Checked its actual geometry: 67×41mm footprint, 62.7mm tall.

**Fused into its own topper, still a socket** — after a v10 detour that dropped it as a socket entirely, v11 settled on the actual intent: it's still on a 100mm base, still gets an FDM hole, a resin hole, and its own topper, exactly like every other model. The difference from a normal model is just that the real kettle mesh is boolean-unioned onto the terrain *before* that topper gets stamped out, so what comes off the floor is one piece - the decorated base and the full furnace body together, not two parts to align and glue by hand. See v10 for the isolated boolean test (178k triangles, tested blind-trust before the real pipeline) and v11 for the correction and the taller-cutter fix that makes the topper actually capture the whole thing.

## Molten-metal channels

Added a network of rectilinear trenches (3mm wide, 0.4mm deep, cut into the resin skin) radiating from the Furnace's position — up toward the Bombard emplacement, down toward the front, and toward the Despot, stopping short rather than forcing a crossing through the tight front band where the Despot and Hobgrot sit. Manhattan-routed (right angles only) rather than curved — reads as dwarven pipework, not a lava flow, and was far simpler to get right. All 3 still start at the Furnace's own center point, which as of v9 is inside the smelting pool's footprint — the pool cut runs first, so the first stretch of each channel is a no-op cut into already-recessed material, and the visible channel effectively starts right at the pool's rim. As of v10 that same center point is also where the real furnace body gets unioned in, so the channels visually run straight up to its base. See above.

It also produced the session's second real boolean-fragility bug, this time caught by the volume sanity check rather than a render: several channel segments share an elbow, so their cutter boxes overlap each other there — and I'd combined all of them into one cutter object before a single DIFFERENCE pass, exactly the self-intersecting-cutter case the fragility notes warn about. It corrupted the resin skin down to ~2mm³ (should be ~34,000mm³) — not subtle, but only visible in the printed volume, not the render. Fixed by applying each channel segment as its own separate DIFFERENCE pass instead of combining them — a short chain of simple cuts, not one cut from a self-overlapping cutter.

**Something running in the channels** — a raised bead (1.2mm wide, 0.15mm proud) sitting inside each already-cut trench, narrower and shorter than the trench itself so it reads as molten metal partially filling the channel once painted, rather than an empty groove. Applied the elbow lesson from above *proactively* this time: each bead segment is its own separate UNION pass, same as the trench cuts, never combined first. The bead's own bottom face also can't sit exactly flush with the trench floor it's unioned onto — that's a coincident-face union, the other fragility trigger — so it's embedded 0.15mm below the trench floor for real overlap. Confirmed with a close-up render: a distinct raised strip visible running down the center of the trench, not just an empty channel.

## Hand-tool props — integrated, not standalone, now four of them

First pass built the hammer and tongs as standalone loose STLs to glue on by hand. Reversed that: parts this small (10–14mm long, next to a 400×220mm floor) are genuinely fiddly to align and glue precisely, so they're **unioned directly into the resin skin** at build time instead — permanent, no hand-placement needed. `tools_props.py`'s original geometry logic moved into `forge_floor_tiles_v3.py` itself, each prop embedded 0.4mm into the skin and standing 1.2mm proud of it, for a clean union rather than a flush/coincident face. Now four props for variety, not just one of each:

- **Hammer** (×2) — one T-shaped silhouette polygon, extruded once, no boolean beyond the final union.
- **Tongs** — pivot cylinder + two arm boxes (each only overlapping the pivot, never each other), unioned into one shape, then that whole shape unioned onto the skin. Moved in v9 to clear the pool's old open lobe, then nudged again in v11 (a 1mm tweak, not a real conflict - the furnace's move changed the pool's shape enough to make the v9 spot a knife-edge fit) - currently (269, 150), almost back to its original spot.
- **Anvil** — a second silhouette-only prop: a body block with a tapering horn, one polygon, same zero-boolean approach as the hammer. Moved again in v11 (36.5mm) - the bigger, closer-to-center smelting pool reached into its v9 spot.
- **Ingot pile** (v9) — 3 stacked rectangular blocks, slightly offset, `join_objects` into one shape before the final union onto the skin.
- **Chisel** (v9) — same silhouette-extrusion approach as the hammer, just a narrower outline. Nudged 2mm in v11 for the same reason as the tongs.

The tongs had come out wrong on the very first standalone render — a symmetric bowtie/X instead of an open pair of arms. Real bug, not a boolean-fragility one: a plain transform-order mistake (an offset set via `.location` got overwritten before it was ever baked into the mesh, so both arms stayed centered on the pivot and just mirrored on rotation). Fixed before integration, by baking the offset into the mesh data *before* rotating rather than after. Caught by looking at the render, not the volume check — a reminder that volume alone only catches missing/extra material, not wrong shape.

All 6 placements are checked in code against every socket, the grate, every molten channel, the smelting pool, the floor edge, and each other — a `clearance_ok()` helper (in `forge_floor_data.py` as of v11) shared with the paving grid below, not hand-picked spots hoped to be clear.

## Stone-tile paving — the whole floor, with real pattern variety

First pass placed 4 hand-picked paving cells, then one auto-generated pattern (square groove + inset circle) across the whole floor. As of v9, three patterns rotate through the grid, assigned deterministically by cell position so the layout is stable across re-runs, not random:

- **Square + circle** — the original motif: 4 groove edges plus an inset circle.
- **Diamond + circle** (new) — the same square rotated 45°, still with the inset circle.
- **Hatch** (new) — a plain X, no circle, the simplest of the three.

A full grid is generated across the *entire* floor at 16mm pitch (272 candidate cells, denser than the 20mm pitch this replaced) and every candidate is checked against every socket, the grate, every channel, the smelting pool, and every prop — only cells that actually clear everything get cut. **61 of 272 survived and got paved.** Adjacent surviving cells still tile edge-to-edge correctly since they all sit on the same master grid; the gaps are simply wherever the machinery (or now the pool) actually is, decided by the checker, not by hand.

Each pattern is built from several separate DIFFERENCE passes (never one cutter joined from overlapping shapes first) — the channel-elbow lesson, applied consistently across square edges, diamond edges, and the hatch's own crossing diagonals.

## Print geometry — current state

Both layers are real now, run and verified in Blender, not just designed. FDM: the 3 v7 wedge tiles (renders above), each including the straddling-socket fix so a hole that crosses a seam gets its bite cut into *both* (or, for the Furnace as of v11, all *three*) tiles, not just the one that "owns" it by center point. Resin: the v11 master terrain (pool, real paving variety, channels, 6 props, the real furnace body fused into its own socket's spot), stamped (all 15 sockets cut, all 15 toppers captured, the Furnace's topper carrying the fused kettle body along with it), then split into 4 print-sized quadrants. The two-material stack, base toppers, molten channels, hand-tool props, and stone-tile paving sections below describe this current geometry, not a pending design.

## What exists so far

- `blender/hellforge/forge_floor_data.py` — the shared master: floor dimensions, all 15 sockets, the wedge cut, the smelting pool, molten channels, props, paving, the resin quadrant split. Plain Python, no `bpy` - runs its own assertions standalone in well under a second. Both scripts below import from it; neither keeps its own copy anymore.
- `blender/hellforge/forge_floor_layout.py` — the SVG planning diagram, now generated from `forge_floor_data.py` directly (v11) instead of a hand-maintained duplicate that had drifted out of sync 3 times. Draws the FDM wedge cut and the resin quadrant split in different colors, plus the pool and channels for the first time.
- `blender/hellforge/forge_floor_tiles_v3.py` — the actual print geometry for both layers, run and verified in Blender 5.1.2. `BUILD_RESIN = True`, `RESIN_STAGE = "stamp"`.
- `tile_left_fdm.stl` / `tile_right_fdm.stl` / `tile_bottom_fdm.stl` — the 3 FDM wedges, current (straddling-socket fix included, furnace repositioned to span all 3).
- `forge_floor_master_resin.stl` — full-detail reference piece, undecorated by holes (the "look at the whole surface" checkpoint from v8).
- `forge_floor_resin_nw.stl` / `_ne.stl` / `_sw.stl` / `_se.stl` — the 4 print-ready resin quadrants, holes already cut (the furnace's hole included - it's fully captured into its own topper by this point, no tall geometry left to clip), each within the 165×143mm bed.
- `topper_*.stl` × 15 — one per army model, captured before the master's holes were cut, plus `topper_roaring_furnace.stl` (101×101×63.9mm - the real fused kettle body, not a flat disc).
- `blender/hellforge/forge_floor_tiles_v1.py` — superseded single-material version, kept for comparison, not deleted.
- `blender/hellforge/tools_props.py` — original standalone hammer/tongs script; superseded by integrating the same geometry directly into `forge_floor_tiles_v3.py`, kept for comparison, not deleted.
- Exterior and interior concept sketches, via the Gemini illustration pipeline (`illustrations/generate_illustration.py`, sketch style). Interior v2 was generated by editing v1 in place (`edit` mode) to add the furnace and base sockets rather than re-describing the whole scene.
- Original brainstorm dump at `input/spearhead/dwarfs.md` (raw source, unedited).
- Roaring Furnace body: adapted third-party asset, `input/spearhead/Boil Kettle & Tun System - Dwarven AleWorks - 28mm - 2860871/` (CC BY-NC, ecaroth on Thingiverse) — imported into the pipeline and fused into its own topper, see v11 above.

## Open questions

- **Nothing has actually been printed yet** — FDM wedges or resin pieces. This rework fixes the diagnosed cause of the first FDM failure (edge-to-edge zero margin) and everything is verified in Blender (geometry, volumes, straight-down hole checks), but the real test is a physical print of both layers, glued together, checking the holes actually line up in hand and not just in the model.
- **The Spigot.stl piece** (part of the same third-party furnace asset) isn't positioned anywhere — its local coordinate space doesn't share an origin with the main kettle body, and there's no reference for the correct offset between them. Left out of the fused body entirely; likely a by-eye glue placement onto the printed terrain rather than something worth reverse-engineering from two mismatched STLs.
- **The furnace's own topper can't print flat/no-supports** like the other 14 — it's 63.9mm tall (base + fused kettle), so it needs to go into the printer upright and supported, same as any tall mini. Not designed yet: a specific support strategy in the slicer for that one piece. (Resolved as of v11: this is no longer a problem for the 4 background quadrants themselves — the furnace is fully captured into its own topper before the quadrant split happens, so all 4 quadrants print flat with no supports same as before.)
- The smelting pool reads fairly subtly in the wide iso renders (the recess is shallow, and the veins are thin) — worth a closer look once it's actually printed and painted, since the "molten metal" read likely comes more from paint (bright orange in the recess, contrasting with the surrounding stone/metal floor) than from the print geometry alone.
- Real footprint / case-standard decision for the storage-box project aside, this floor's own composition has now had 5 models nudged across v7/v9/v11 for geometric reasons (seam clearance, pool clearance, furnace repositioning) - worth a pass at some point checking the *whole* layout still reads as the intended "scattered workers" composition, not just that each individual move was locally justified.
- Real model heights, for box interior/lid clearance.
- Resin skin thickness (1.2mm) and steel sheet thickness (0.5mm) — both placeholders, not confirmed against real prints/stock.
- Corner-bracket/stacking mechanism for the floor tiles — worth checking whether the pin/socket design from the storage-box corner bracket transfers directly, rather than designing a second one from scratch.
- Hero bases for v1: Dominator Engine + Bombard emplacement. Infantry bases stay simple/repeatable — no need for 10 unique stories.
- The straight-seam finder (`find_clear_seams`) has the same "not checked against each other" gap the stepped one had — never actually hit in practice since this layout only ever needed 1 straight seam, but not fixed either.
