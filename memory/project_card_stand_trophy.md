---
name: project-card-stand-trophy
description: Mythos card-stand backplate forked into a standalone "#1" escalation-league trophy plaque (v7), status and key design/print lessons
metadata:
  type: project
---

The Mythos business-card-stand project (`content/posts/card-stand/`, Blender scripts in
`blender/card-stand/`) got forked into a second, unrelated piece: a "#1" trophy plaque for
Mythos's own 40K Escalation League, Season 2. Built as `blender/card-stand/card_stand_v7_trophy.py`
(v6 `card_stand_v6_backplate_solo.py` is the holder-less Mythos backplate only, v7 forks off that
and adds the trophy content).

**Status as of 2026-08-14:** first v7 print (design as of 2026-08-13) failed - all raised text and
some logo detail delaminated mid-print, stuck to the vat's FEP film rather than the plate. Root
cause was mid-print peel-force delamination (thin isolated proud relief losing the tug-of-war
against the FEP peel each layer), not a post-print handling snap like the original wordmark break.
Iterated since: `EMBOSS_H` roughly halved, offsets/sizes re-tuned, plate widened for room to grow
icon/wordmark/#1. As of today the user manually trimmed values further and confirmed the STL looks
clean in the slicer (AnycubicSlicerNext/PhotonWorkshop) - about to test-print again, result not
yet known.

**Why the trophy exists:** wanted to reuse the Mythos backplate's box/ridge/emboss techniques for a
one-off trophy rather than starting fresh, and to practice a dished/framed cross-section and a
print-release chamfer neither had been done before on this site.

**Plate content (top to bottom):** Mythos icon (large), "MYTHOS" wordmark, big "#1", small subtitle
(wording iterated - settled somewhere around "Warhammer 40k / Escalation League / Season 2").

**Key lessons from this iteration, in case this gets revisited:**
- The dished center panel must be cut from the FRONT, not the back - cutting the back leaves the
  center floating above the build plate with nothing under it during a flat-on-back print (caught
  before the first slice).
- Thickening the whole plate does NOT help mid-print peel-force delamination - peel force acts on
  each raised feature's own cross-section at each layer height, independent of how much material
  sits underneath. Wasted a round finding this out; should have reasoned about it before touching
  `BACKPLATE_T`.
- The real levers against peel-force failure: shorter `EMBOSS_H` (fewer risky unsupported layers to
  climb through) and thicker strokes via `curve_data.offset` bold-offset (more cross-section
  resisting the peel) - but offset has its own failure mode, see below.
- **Bold-offset self-intersection is letter-specific and size-dependent, not just a single safe
  threshold.** `text_plate_v1.py`'s original tuning found ~0.13 as the danger line for O/S at
  TEXT_SIZE=18 - but at smaller sizes (the subtitle, ~6.5-8mm) even much lower offsets (down to
  0.0) still dropped different individual letters (0, n, a, l, K all failed at various points) with
  no clean monotonic relationship to the offset value. Whole-piece volume/non-manifold stats did
  NOT reliably catch these - a single collapsed character among many barely moves the aggregate
  number. Bumping curve `resolution_u` to fix suspected under-tessellation made things drastically
  worse (final boolean union volume collapsed from ~48800mm3 to ~368mm3) - do not touch that again.
- **Blender's own EEVEE render preview is not trustworthy for verifying fine embossed text at this
  scale.** Raking-light renders made letters look dropped/malformed that were actually fine, and
  conversely some real drops only showed up in the sliced STL, not the Blender render, even at high
  resolution and with shadows flattened. The user's slicer is the actual ground truth for this
  project - always confirm fine text there before trusting a Blender render.
- Growing `LOGO_W`/`TEXT_SIZE` bigger eats vertical budget fast (icon height is aspect-locked to
  width) - upsizing the top elements repeatedly pushed the subtitle off the bottom margin; the gap
  constants (`TEXT_GAP_BELOW_ICON`, `TROPHY_GAP_BELOW_TEXT`, `SUBTITLE_GAP_BELOW_TROPHY`) need
  retrimming any time the elements above grow.
- Icon and wordmark ended up with separate side-margin constants (`LOGO_SIDE_MARGIN` vs
  `TEXT_SIDE_MARGIN`) after growing the icon aggressively started squeezing the wordmark's own
  safe margin - don't collapse these back into one shared constant.

Next step when this resumes: hear back on the second test print.
