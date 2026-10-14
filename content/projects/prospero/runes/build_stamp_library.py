"""
Rune stamp library builder (Blender bpy) - standalone.

Builds each glyph's embossed stamp mesh (mask smooth -> grid extrude ->
Laplacian relax, same technique as rune_panel_v1_plain.py) sized for
obelisk-scale use (8x8mm slots, matching ../obelisks/obelisk.py), and
exports each as its own STL - no backing box, just the raised glyph
geometry, ready to be imported and boolean-unioned onto a target surface.

Why this exists: obelisk.py used to rebuild + smooth every glyph's mesh
from the source pixel art on every single run, even though the result is
identical every time for a given glyph name - expensive and wasted. Worse,
it was reusing the flat 14x20mm test panel's MASK_SUPERSAMPLE=6, which is
massive overkill at 8x8mm and was feeding Blender's boolean solver
~100k+ faces per obelisk. This builds the stamps once, at a resolution
actually appropriate for their size, and obelisk.py just imports them.

RUNE_W/RUNE_H/EMBOSS_HEIGHT/EMBED_DEPTH here must match obelisk.py's - the
positioning math there assumes stamps built with these exact dimensions.

Run: Blender -> Scripting workspace -> Open this file -> Alt+P
"""

import bpy
import bmesh
import math
import os

# ============================================================
# CONFIG - keep in sync with obelisks/obelisk.py's rune settings
# ============================================================

GLYPH_DIR = "/Users/mannil/Desktop/studio-m/TSONS/assets/rune_marks"
STAMP_DIR = "/Users/mannil/Desktop/studio-m/TSONS/runes/output/stamps"

# The 16 visually-unique glyphs (see assets/rune_marks - already deduped)
GLYPH_POOL = [
    "manifestation", "decay", "binding", "chaos", "cycle", "void",
    "dominion", "earth", "entropy", "fire", "flow", "will",
    "life", "growth", "transcendence", "sacred",
]

# Stamp footprint - must match obelisk.py's RUNE_W/RUNE_H
RUNE_W = 8.0
RUNE_H = 8.0

# Must match obelisk.py's EMBOSS_HEIGHT/EMBED_DEPTH
EMBOSS_HEIGHT = 1.5
EMBED_DEPTH = 1.0

RUNE_ALPHA_THRESHOLD = 0.15
RUNE_STROKE_DILATE = 1

# Lower than the flat test panel's supersample=6 - these stamps are 8x8mm,
# under half that panel's physical size, so the same resolution ratio gives
# plenty of smoothness at a fraction of the face count. This - not the
# import step - is what actually fixes the boolean-solver slowness.
MASK_SUPERSAMPLE = 3
MASK_BLUR_RADIUS = 4

MESH_SMOOTH_ITERATIONS = 3
MESH_SMOOTH_FACTOR = 0.5

# After smoothing, the flat front/back cap faces are almost entirely
# coplanar (perfectly flat except right at the boundary) - thousands of
# tiny grid quads that merge into a handful of large polygons with zero
# shape change. This is the main lever that keeps the boolean solver fast
# once these stamps get unioned onto the pillar - resolution alone (above)
# only gets partway there.
DISSOLVE_ANGLE_LIMIT = math.radians(2.0)


# ============================================================
# HELPERS
# ============================================================

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block)


def export_stl(obj, filename):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = os.path.join(STAMP_DIR, filename)
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"Exported {path}")


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

    mask, w, h = upscale_and_smooth_mask(mask, w, h, MASK_SUPERSAMPLE, MASK_BLUR_RADIUS)

    on_count = sum(sum(row) for row in mask)
    print(f"[{glyph_name}] {w}x{h}, {on_count} px on")
    return mask, w, h


def upscale_and_smooth_mask(mask, w, h, factor, radius):
    """Nearest-neighbor upscale, then box-blur via a summed-area table so an
    arbitrarily large radius costs the same as a small one, then
    re-threshold at 0.5."""
    nw, nh = w * factor, h * factor
    grid = [[1.0 if mask[y // factor][x // factor] else 0.0 for x in range(nw)] for y in range(nh)]

    sat = [[0.0] * (nw + 1) for _ in range(nh + 1)]
    for y in range(nh):
        row_sum = 0.0
        for x in range(nw):
            row_sum += grid[y][x]
            sat[y + 1][x + 1] = sat[y][x + 1] + row_sum

    def box_avg(x, y):
        x0, x1 = max(x - radius, 0), min(x + radius, nw - 1)
        y0, y1 = max(y - radius, 0), min(y + radius, nh - 1)
        total = sat[y1 + 1][x1 + 1] - sat[y0][x1 + 1] - sat[y1 + 1][x0] + sat[y0][x0]
        area = (x1 - x0 + 1) * (y1 - y0 + 1)
        return total / area

    smoothed = [[box_avg(x, y) > 0.5 for x in range(nw)] for y in range(nh)]
    return smoothed, nw, nh


def build_glyph_stamp_mesh(glyph_name):
    """Canonical local frame: X=width, Y=depth (straddles 0, spans
    -depth/2..+depth/2), Z=height. Same frame obelisk.py's
    emboss_rune_panels expects when it imports and positions this."""
    mask, w, h = load_glyph_mask(glyph_name)
    depth = EMBOSS_HEIGHT + EMBED_DEPTH

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

    for _ in range(MESH_SMOOTH_ITERATIONS):
        bmesh.ops.smooth_vert(
            bm, verts=list(vert_grid.values()), factor=MESH_SMOOTH_FACTOR,
            use_axis_x=True, use_axis_y=False, use_axis_z=True,
        )

    if faces:
        extruded = bmesh.ops.extrude_face_region(bm, geom=faces)
        new_verts = [g for g in extruded['geom'] if isinstance(g, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, verts=new_verts, vec=(0, depth, 0))

    bmesh.ops.dissolve_limit(
        bm, angle_limit=DISSOLVE_ANGLE_LIMIT, use_dissolve_boundaries=False,
        verts=bm.verts[:], edges=bm.edges[:],
    )

    mesh = bpy.data.meshes.new(f"glyph_{glyph_name}")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(mesh.name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


# ============================================================
# MAIN
# ============================================================

def main():
    os.makedirs(STAMP_DIR, exist_ok=True)
    clear_scene()

    # Export while each stamp is still at local origin - STL export writes
    # world-space coordinates, and these get re-imported elsewhere (see
    # obelisks/obelisk.py) expecting to be centered at local origin. The
    # viewport-layout offset below must happen AFTER export, or it gets
    # baked into the file and silently corrupts every downstream use.
    xoff = 0.0
    for name in GLYPH_POOL:
        obj = build_glyph_stamp_mesh(name)
        obj.name = f"stamp_{name}"
        export_stl(obj, f"{name}.stl")
        obj.location.x = xoff
        xoff += RUNE_W + 4.0

    print(f"Done. {len(GLYPH_POOL)} stamp(s) exported to {STAMP_DIR}")


if __name__ == "__main__":
    main()
