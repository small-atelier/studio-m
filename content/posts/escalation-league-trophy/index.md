---
title: "A #1 Trophy for the Escalation League"
date: 2026-08-14
draft: false
tags: ["3d-printing", "resin", "blender", "python"]
---

{{< lead >}}
Mythos runs its own 40K escalation league, so this was a good excuse to fork the [card-stand backplate](../card-stand/) into something new: a standalone trophy plaque, printed in resin.
{{< /lead >}}

---

## What it is

A single plaque — the Mythos icon, the wordmark, a big "#1", and a small "40K Escalation League / Season 2" line underneath. The panel is dished in from the front so a raised frame runs all the way around it, with the relief inside sitting flush against that frame rather than looking sunken.

{{< carousel images="gallery/*" aspectRatio="4-3" interval="3000" >}}

---

## Technique: a frame that's actually flush

The dish is cut from the front, not the back, so the recessed panel is genuinely visible as a frame rather than just a thickness saving — cutting from the back would leave it floating with nothing under it once printed flat. 

The depth of that dish is matched to how proud the relief sits, so the raised icon/text tips land level with the frame's own face instead of sitting noticeably behind it.

MYTHOS and the "#1" are set in a real Bold weight, and the subtitle underneath in Bold Italic — genuinely drawn bold strokes rather than a synthetically thickened outline, and the italic gives the subtitle a bit of visual hierarchy under the two bigger elements above it. 

Both are extracted straight out of Baskerville's own font-collection file, which bundles Regular/Bold/Italic/Bold Italic together as separate faces, rather than a separate font download.

{{< include-code path="blender/card-stand/card_stand_v7_trophy.py" lang="python" label="mythos_trophy.py" >}}

---

## Downloads

- [Trophy plaque](mythos_trophy.stl)
- [Build script](mythos_trophy.py)

---

Took a couple of print passes to get the relief surviving cleanly, but it's holding up now — off to the store to award to whoever tops the league table.
