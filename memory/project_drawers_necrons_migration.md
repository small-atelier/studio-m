---
name: drawers necrons migration
description: Raw material moved from ~/Desktop/studio-m/ into this site — DRAWERS as a new project, NECRONS runes into the existing necrons project. Not committed, not written up.
type: project
---

Moved 2026-08-02 from `/Users/mannil/Desktop/studio-m/` (a staging folder, not a repo) — working tree only, nothing committed or pushed.

**Drawers, resolved 2026-08-12** — moved out of `content/projects/drawers/` into `content/inventory/misc/drawers/` (page bundle), since it's a desk/storage item, not a miniature build. Page rewritten short-and-concise, no iteration narrative: intro + `{{< carousel >}}` gallery + a Downloads section linking the final STLs directly (they're plain bundle resources, so page-relative markdown links like `(full-width-module.stl)` just work — Hugo copies them next to `index.html`). `draft: false`, linked from `content/inventory/_index.md` under Misc.

Final STLs offered (renamed, no spaces/double-extensions): `full-width-module.stl`, `half-width-module.stl`, `full-width-storage-bin.stl`, `half-width-storage-bin.stl`, `full-width-dual-shelf.stl`, `drawer-140x36x46.stl`, `drawer-140x84x46.stl`, `connector-85mm.stl`/`-129mm`/`-220mm`, and `half-width-stick-organizer.stl` (organizer for the sticks/wire used to mount models for painting; extended + modified from the half-width module).

Raw material (the three `.py` scripts, pre-resize source STLs, unused preview renders) moved to `blender/drawers/` at repo root — following the same convention as `blender/bases/` for the bases post: outside `content/`, so Hugo doesn't publish it, kept for provenance only. Not linked from the page.

**Layout standardization, 2026-08-12:** the three hobby-tech pages (bases, drawers, card-stand) were reviewed together and made consistent — see the update in [[tsons migration]] for the full pass (bases converted flat-file→leaf-bundle with real STL downloads, `blender/base/`→`blender/bases/` rename, drawers' unreferenced leftover `_preview/` folders deleted, raw drawer STL filenames cleaned up to `*-original.stl`, card-stand got downloads added too).

**Open item, flagged not guessed:** the original found STL family's source (where it was downloaded from) isn't recorded anywhere and wasn't in the migrated material — no attribution/credit link on the page. Worth adding if the user still has the source.

Notable technique worth pulling into prose if this ever gets a real writeup: `make_connector_lengths.py` rescales the dovetail connector's length with a pure STL vertex remap along one axis (no Blender) — the bar is a constant-cross-section prism, so no triangle normal has a component along the scaled axis and nothing gets distorted.

**Addition to existing project: `content/projects/necrons/runes.md`** (`draft: true`) + `content/projects/necrons/runes/`. Rune panel generation — note this one was partly done with **Gemini**, not Claude (reference images), which is worth keeping visible if picking this up later since the workflow/tooling differs.

**Also skipped in this pass, still sitting in `~/Desktop/studio-m/`:**
- `TSONS/` — has its own `CLAUDE.md`/`.claude/`, appears to already be mid-migration in a separate session (matches uncommitted `content/projects/thousands-sons/{brazier,columns,crystals,forest,obelisks,pyramid,ruins,runes}` in this repo). Left untouched.
- `Mythos/` — empty, nothing to move.
- Loose top-level files (`favicon_io/`, `favicon.ico`, a stray screenshot PNG) — unclear target, not migrated, flagged for the user to decide on directly.

**TODO:** drawers is done (see above). Necrons runes still needs: proper writeup, photos, final slug/title, flip `draft: true` → `false`.
