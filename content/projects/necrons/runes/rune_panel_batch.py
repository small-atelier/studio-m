"""
Rune panel batch (Blender bpy) - standalone.

Cuts each glyph in GLYPH_POOL all the way through its own flat 3x20x30mm
box, laid out side by side, one STL exported per glyph. GLYPH_POOL is
deduped down to the 16 visually-unique glyphs out of the 40 named files in
GLYPH_DIR (many names share pixel-identical artwork).

Derived from the TSONS Prospero obelisk project's rune test script
(studio-m/TSONS/runes/rune_panel_test.py) - same pixel-mask -> single
connected mesh -> extrude -> boolean DIFFERENCE approach, just batched
across the whole glyph set instead of one at a time.

Run: Blender -> Scripting workspace -> Open this file -> Alt+P
"""

import bpy
import bmesh
import os

# ============================================================
# CONFIG
# ============================================================

GLYPH_DIR = "/Users/mannil/Desktop/studio-m/NECRONS/assets/rune_marks"
EXPORT_DIR = "/Users/mannil/Desktop/studio-m/NECRONS/runes/output"
EXPORT_STL = True

# The source set has 40 named files but only 16 are visually distinct - the
# rest are exact pixel-duplicates under a different thematic name (checked
# via pixel-hash comparison offline). One representative name per unique
# glyph, so we're not cutting 24 redundant duplicate shapes.
GLYPH_POOL = [
    "manifestation",  # dup: air, order
    "decay",          # dup: autumn, death
    "binding",        # dup: pact, winter
    "chaos",          # dup: sanguine, wrath
    "cycle",          # dup: sloth
    "void",           # dup: desecrated, envy
    "dominion",       # dup: pride
    "earth",          # dup: infusion, rational
    "entropy",        # dup: gluttony
    "fire",           # dup: force
    "flow",           # dup: water
    "will",           # dup: greed
    "life",           # dup: grove, spring
    "growth",         # dup: summer
    "transcendence",  # dup: lust
    "sacred",         # dup: mana, resonance
]

# Panel (X=width, Y=thickness, Z=height)
BOX_W = 20.0
BOX_D = 3.0
BOX_H = 30.0

# Glyph footprint on the panel face - smaller than the box so there's a
# visible border margin
RUNE_W = 14.0
RUNE_H = 20.0

RUNE_ALPHA_THRESHOLD = 0.15
RUNE_STROKE_DILATE = 1

# The cutter's nominal depth matches the box (3mm), but bleeds past each
# face internally so the cut boundary isn't coincident with the box's own
# faces - a flush cutter is exactly the degenerate case that fragments the
# boolean result.
CUT_BLEED = 1.0

PANEL_SPACING = 6.0  # gap between panels when laid out side by side


# ============================================================
# HELPERS
# ============================================================

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block)


def apply_boolean(target, cutter, operation):
    mod = target.modifiers.new("Bool", 'BOOLEAN')
    mod.object = cutter
    mod.operation = operation
    mod.solver = 'EXACT'
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def export_stl(obj, filename):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = os.path.join(EXPORT_DIR, filename)
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"Exported {path}")


def list_glyph_names():
    return list(GLYPH_POOL)


def load_glyph_mask(glyph_name):
    path = os.path.join(GLYPH_DIR, f"rune_{glyph_name}_mark.png")
    img = bpy.data.images.load(path, check_existing=True)
    w, h = img.size
    px = img.pixels[:]  # flat RGBA floats, row-major bottom-to-top
    bpy.data.images.remove(img)

    mask = [[px[(y * w + x) * 4 + 3] > RUNE_ALPHA_THRESHOLD for x in range(w)] for y in range(h)]

    for _ in range(RUNE_STROKE_DILATE):
        grown = [row[:] for row in mask]
        for y in range(h):
            for x in range(w):
                if mask[y][x]:
                    continue
                nbrs = [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]
                if any(0 <= nx < w and 0 <= ny < h and mask[ny][nx] for nx, ny in nbrs):
                    grown[y][x] = True
        mask = grown

    on_count = sum(sum(row) for row in mask)
    print(f"[{glyph_name}] mask {w}x{h}, {on_count} px on after dilate={RUNE_STROKE_DILATE}")
    return mask, w, h


def build_glyph_cutter_mesh(glyph_name):
    """Single connected mesh: one quad per "on" pixel, sharing vertices with
    its neighbors, extruded once via bmesh's own extrude operator."""
    mask, w, h = load_glyph_mask(glyph_name)
    depth = BOX_D + 2 * CUT_BLEED

    bm = bmesh.new()
    vert_grid = {}

    def get_vert(gx, gz):
        key = (gx, gz)
        if key not in vert_grid:
            lx = (gx / w - 0.5) * RUNE_W
            lz = (gz / h - 0.5) * RUNE_H
            vert_grid[key] = bm.verts.new((lx, -depth / 2, lz))
        return vert_grid[key]

    faces = []
    for y in range(h):
        for x in range(w):
            if not mask[y][x]:
                continue
            v0, v1, v2, v3 = get_vert(x, y), get_vert(x + 1, y), get_vert(x + 1, y + 1), get_vert(x, y + 1)
            faces.append(bm.faces.new((v0, v1, v2, v3)))

    if faces:
        extruded = bmesh.ops.extrude_face_region(bm, geom=faces)
        new_verts = [g for g in extruded['geom'] if isinstance(g, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, verts=new_verts, vec=(0, depth, 0))

    mesh = bpy.data.meshes.new(f"glyph_{glyph_name}_cutter")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(mesh.name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def build_and_export_panel(glyph_name, x_offset):
    bpy.ops.mesh.primitive_cube_add(size=1)
    box = bpy.context.object
    box.name = f"panel_{glyph_name}"
    box.scale = (BOX_W, BOX_D, BOX_H)
    bpy.ops.object.transform_apply(scale=True, location=False, rotation=False)

    cutter = build_glyph_cutter_mesh(glyph_name)
    apply_boolean(box, cutter, 'DIFFERENCE')

    box.location.x = x_offset

    if EXPORT_STL:
        export_stl(box, f"{box.name}.stl")


# ============================================================
# MAIN
# ============================================================

def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    clear_scene()

    names = list_glyph_names()
    print(f"Found {len(names)} glyphs in {GLYPH_DIR}")

    xoff = 0.0
    for name in names:
        build_and_export_panel(name, xoff)
        xoff += BOX_W + PANEL_SPACING

    print(f"Done. {len(names)} panel(s) exported to {EXPORT_DIR}")


if __name__ == "__main__":
    main()
