---
title: "AoS Objective Markers"
date: 2026-10-14
draft: false
tags: ["3d-printing", "warhammer", "age-of-sigmar", "40k", "multi-material", "mythos"]
---

{{< lead >}}
Full-size objective markers for Age of Sigmar matched play: a paved-tile disc whose outer edge sits 3" beyond a 40mm marker, so the disc is the control zone. Plain, or with the Mythos logo set into the underside.
{{< /lead >}}

{{< carousel images="gallery/*" aspectRatio="1-1" interval="3000" >}}

---

## The idea

An objective is a 40mm marker with a control zone reaching 3" from it. A tile disc sized to exactly that radius beyond the marker's edge does double duty: decoration and a genuine ruler. 3" is the control range in 40K too, so the same disc works there.

## The set

The General's Handbook 2026-27 battleplans use six objectives, so a set is six discs. Board and objective rules are in the [battlefield reference]({{< ref "/notes/aos-battlefield-reference#objectives" >}}).

The disc design, the marker coin it's built around, and the script are on the [Objective Marker Tiles]({{< ref "/printables/objective-marker-tiles" >}}) page.

## Downloads

Own design, no external license to carry — share and remix freely.

**Plain** (no logo, single material) — [STL](downloads/objective_marker.stl)

**With Mythos logo** — [base](downloads/objective_marker_logo_base.stl) · [insert](downloads/objective_marker_logo_insert.stl) · [Anycubic 3MF](downloads/objective_marker_logo_anycubic.3mf)

The Anycubic 3MF carries Anycubic Slicer Next's own per-part filament-slot metadata (that slicer ignores the standard 3MF color hint entirely) — check `BASE_EXTRUDER_SLOT`/`LOGO_EXTRUDER_SLOT` in the script match whatever's actually loaded if you're running a different multi-material setup. The plain print is single-material, so it's STL only, no project file.

## Status

| Part                     | Needed | Designed | Printed |
|--------------------------|-------:|---------:|--------:|
| Disc with Mythos logo    | 6      | yes      | 0       |
| Mythos coin              | 6      | no       | 0       |
