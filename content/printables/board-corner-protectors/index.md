---
title: "Board Corner Protectors"
date: 2026-10-14
draft: false
tags: ["3d-printing", "blender", "python", "terrain", "spearhead"]
---

{{< lead >}}
FDM-printed caps for the corners of a double-sided gaming board: they wrap both faces, double as feet, and keep the corners from getting dinged in storage.
{{< /lead >}}

{{< figure src="board_corner.png" alt="Render of the corner protector: triangular cap with a plate border and rivet rings engraved on each side wall" caption="Corner protector — engraved plate border and rivet rings, tapered lip edges." >}}

Glued onto the four frame corners. Each one wraps the corner on both side faces and laps 2mm over both board faces, so it works whichever side is up. The bottom lips double as feet, keeping the board off the table. Made for the [22×30 Spearhead Board]({{< ref "/projects/spearhead-board" >}}).

- Fits a 45mm board edge (0.4mm clearance in the pocket).
- 40mm along each frame edge; the lip reaches ~26mm in at the corner and tapers out toward the arm ends.
- Lip edges are tapered on the play side, so minis and terrain slide over the step instead of catching.
- All decoration is engraved, nothing stands proud on the play surface.

## Printing

Flat on a lip, as it sits on the table. The top lip needs supports inside the pocket: paint them under the lip only (not "build plate only" — they land on the bottom lip), ~0.2mm Z-gap. Support marks end up on the faces against the board, so sand them lightly if the fit is tight.

## Downloads

[STL](downloads/board_corner_v2.stl) (print ×4, same part for every corner) · [script]({{< script "spearhead-board/board_corner_v2.py" >}}) (Blender, headless). Set `BOARD_THICKNESS` to your own board's edge thickness.
