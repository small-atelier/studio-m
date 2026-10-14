---
title: "22×30 Spearhead Board"
date: 2026-09-22
draft: false
tags: ["terrain", "3d-printing", "resin", "spearhead"]
---

{{< lead >}}
Build plan for a dedicated 22" × 30" Spearhead board — Spearhead's quarter-of-a-standard-table footprint. Objectives and terrain are printed, the frame is built and capped with printed corner protectors; the foam surface is still to come.
{{< /lead >}}

{{< figure src="board_layers.png" alt="Exploded concept sketch of the board layers" caption="Concept sketch of the layer stack — double-sided hardboard core, carved foam, flush tile mosaic with objective discs." >}}

## Objectives

Resin-printed, 40mm coins. Seven variants from the **Spearhead Objective Markers (FDM-friendly)** set: simple, bigger simple, crane, snake, phoenix, dragon face, dragon side.

Each coin sits flush in an FDM-printed [objective marker tile]({{< ref "/printables/objective-marker-tiles" >}}) — a paved disc with a blind 40mm pocket, set into the board's tile mosaic at the same top height.

## Terrain (FDM)

Printed at 0.4mm nozzle, 1.2mm layer height.

[AOS 4 Skaventide Terrain Equivalent](https://www.thingiverse.com/thing:6724571) by ChickenFPV, CC BY-SA — `small_AOS_terrain.stl` + `big_AOS_terrain.stl`.

## The board

- Hardboard base, framed edge.
- Double-sided — a different terrain layout on each face.
- Foam glued on top: terrain detail (cracks, etc.) cut downward into the foam, separate foam tiles + objectives set on top, kept flush with the surrounding surface.

## Corner protectors

{{< figure src="board_corner.png" alt="Render of the corner protector: triangular cap with a plate border and rivet rings engraved on each side wall" caption="Corner protector — engraved plate border and rivet rings, tapered lip edges." >}}

FDM-printed caps glued onto the four frame corners. Each one wraps the corner on both side faces and laps 2mm over both board faces, so it works whichever side is up. The bottom lips double as feet, keeping the board off the table, and the corners stop it scratching the table or getting dinged in storage.

- Fits a 45mm board edge (0.4mm clearance in the pocket).
- 40mm along each frame edge; the lip reaches ~26mm in at the corner and tapers out toward the arm ends.
- Lip edges are tapered on the play side, so minis and terrain slide over the step instead of catching.
- All decoration is engraved, nothing stands proud on the play surface.

**Printing:** flat on a lip, as it sits on the table. The top lip needs supports inside the pocket: paint them under the lip only (not "build plate only" — they land on the bottom lip), ~0.2mm Z-gap. Support marks end up on the faces against the board, so sand them lightly if the fit is tight.

**Downloads:** [STL](downloads/board_corner_v2.stl) (print ×4, same part for every corner) · [script]({{< script "spearhead-board/board_corner_v2.py" >}}) (Blender, headless). Set `BOARD_THICKNESS` to your own board's edge thickness.

## Status

- Objective coins — printed (resin).
- Objective tiles — designed, not yet printed.
- Terrain — printed (FDM).
- Frame — built.
- Corner protectors — printed (FDM).
- Foam surface — not started.
