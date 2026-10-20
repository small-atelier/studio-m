# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Studio M is a Hugo static site for documenting tabletop miniature painting and model building. It uses the [Blowfish v2](https://github.com/nunocoracao/blowfish) theme (managed as a Go module) and deploys to GitHub Pages at `https://small-atelier.github.io/studio-m/`.

All Hugo commands run inside Docker — do not call `hugo` directly.

## Common Commands

```bash
make serve               # Dev server at http://localhost:1313 (includes drafts & future posts)
make build               # Build minified static site to public/
make modules             # Download/sync theme and modules (run after cloning)
make update-modules      # Upgrade Blowfish theme to latest version
make clean               # Remove public/ and resources/
```

**Create content:**
```bash
make new-army name=my-army             # New army section (creates _index.md + gallery folder)
make new-printable name=my-printable   # New printable bundle
```

Projects, spearhead forces, notes, and inventory items are written directly (no scaffolding command) —
copy an existing page's frontmatter shape as a starting point.

## Architecture

**Content** lives entirely in `content/` as Markdown with TOML/YAML frontmatter. Hugo builds it into a static site — no code compilation.

**Content types and their locations:**
- `content/armies/[name]/_index.md` — Armies (40K and AoS): roster, army lists, unit pages, paint
- `content/spearhead/[name]/` — Spearhead forces: list, rules PDFs, links to their printables
- `content/projects/[name]/` — Multi-session physical builds (boards, terrain sets, workshop gear), each with a Status list
- `content/printables/[name]/index.md` — Single downloadable designs (STL + Blender/Python script).
  Game-specific army kits (tokens + carry box) go in a per-game section: `printables/aos/`,
  `printables/spearhead/`, `printables/40k/` (created with its first kit). Anything usable
  across games, or not game-related, stays in `printables/` itself.
- `content/inventory/[category]/[name].md` — Paint, resin, FDM printer stock tracking
- `content/notes/` — Quick reference notes (hidden from the menu until one is published)

**Images** live in the page bundle (`gallery/` for carousels, alongside `index.md` otherwise).

**Theme** is Blowfish v2, loaded as a Go module (not a git submodule). Theme layouts are not overridden — `layouts/` is empty. Theme shortcodes used in content include `{{< carousel >}}`, `{{< lead >}}`, and `{{< figure >}}`.

**Deployment** is automatic: pushing to `main` triggers `.github/workflows/build.yml`, which runs `hugo --minify` and deploys to GitHub Pages.

**Archetypes** in `archetypes/` define frontmatter templates for each content type. Reference these when adding new frontmatter fields to understand the expected structure.
