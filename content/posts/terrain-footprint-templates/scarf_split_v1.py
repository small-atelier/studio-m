"""
Re-split the two oversized 11th Edition terrain footprint templates (source:
Tinker Junkie, "FREE 11th Edition Terrain Templates", MyMiniFactory #791451)
into halves that fit an Anycubic Kobra X's 260x260mm bed - standalone Blender
bpy script, headless-runnable, NOT a from-scratch part (edits found STLs),
same "STL surgery" conventions as blender/drawers/extend_parts.py.

Why re-split instead of using the designer's own PT1/PT2 files: those are a
plain straight/organic cut, glued edge-to-edge. At this pack's 0.8mm plate
thickness that's a razor-thin, low-surface-area glue joint - fragile, and in
clear PLA any glue bead at a butt seam shows as a visible line. This script
replaces that with a half-lap SCARF SPLICE: over an OVERLAP-wide band
straddling the cut, one half keeps only the bottom 0.4mm and the other keeps
only the top 0.4mm, so the two tongues nest together back to the original
0.8mm - both outer faces stay flush and continuous right across the seam,
and the glued area is (overlap width x seam length) instead of a thin edge
line.

Print-orientation consequence: the half that keeps the TOP tongue in the
overlap band would print as an unsupported floating bridge if exported
as-is (nothing underneath it for that band). That half is mirrored in Z
before export so its tongue faces down onto the bed instead - same trick as
card_stand_v8_holder_return.py's baked-in print orientation. Glue the two
halves the same way up shown in the piece names (A = bottom-tongue half,
printed normal side down; B = top-tongue half, printed pre-flipped) and it
sits flat with no supports.

Only the two pieces that don't fit the 260mm bed as a single print need
this (7X11,5 and 8X11,5) - 2,5X10, 2X8 and 4X8 print whole, untouched.

Run: /Applications/Blender.app/Contents/MacOS/Blender --background --python scarf_split_v1.py
"""

import bpy
import bmesh
import os

SRC_DIR = "/Users/mannil/studio-m/input/11TH AREA FREE TINKERJUNKIE [2COLOR] + [GRID]/1COLOR"
OUT_DIR = "/Users/mannil/studio-m/blender/terrain-templates/output"

OVERLAP = 20.0   # mm, width of the scarf splice band, centered on the cut
MARGIN = 50.0    # generous safety margin for box sides not doing the cutting

# (filename, out_stem) - split perpendicular to the piece's own long (X) axis,
# centered on its own bounding box midpoint
PIECES = [
    ("7X11,5.stl", "7X11,5"),
    ("8X11,5.stl", "8X11,5"),
]


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for b in list(bpy.data.meshes):
        bpy.data.meshes.remove(b)


def import_copy(path):
    bpy.ops.wm.stl_import(filepath=path)
    return bpy.context.selected_objects[0]


def world_bounds(obj):
    xs, ys, zs = [], [], []
    for c in obj.bound_box:
        wc = obj.matrix_world @ __import__("mathutils").Vector(c)
        xs.append(wc.x); ys.append(wc.y); zs.append(wc.z)
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def apply_boolean(target, cutter, operation):
    mod = target.modifiers.new("Bool", 'BOOLEAN')
    mod.object = cutter
    mod.operation = operation
    mod.solver = 'EXACT'
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def make_box(xr, yr, zr, name):
    """Box spanning the given (lo, hi) ranges on each axis - explicit
    ranges, not a fixed size centered at the origin (these STLs sit far
    from world origin, e.g. x~1450-1750)."""
    center = ((xr[0] + xr[1]) / 2, (yr[0] + yr[1]) / 2, (zr[0] + zr[1]) / 2)
    size = (xr[1] - xr[0], yr[1] - yr[0], zr[1] - zr[0])
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.scale = size
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=True)
    return obj


def flip_180_apply(obj, y_center, z_center):
    """Physically flip obj over (in place) about an axis running along X,
    through (y_center, z_center) - used to bake in the print orientation
    for the top-tongue half so its scarf tongue faces the bed instead of
    floating unsupported.

    Deliberately NOT a pure Z-mirror (X/Y unchanged, only Z negated) -
    that's an improper reflection, and for an asymmetric footprint (this
    pack's rubble-edge outlines are not Y-symmetric) it produces a mirror
    image that can never be reproduced by physically turning a printed
    part over, only by printing its mirror twin. A real hand-flip is a
    180 degree ROTATION about an in-plane axis, which flips Z together
    with whichever in-plane axis is perpendicular to that axis (here Y) -
    that's what this reproduces, so flipping the printed piece back over
    by hand exactly undoes it. Since it's a proper rotation (det=+1, X
    unchanged, Y and Z both negated), face winding/normals stay correct
    automatically - no flip_normals() needed."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for v in bm.verts:
        v.co.y = 2 * y_center - v.co.y
        v.co.z = 2 * z_center - v.co.z
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def mesh_diagnostics(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    volume = bm.calc_volume()
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    total = len(bm.edges)
    bm.free()
    return volume, nm, total


def split_piece(fname, stem):
    path = os.path.join(SRC_DIR, fname)
    clear_scene()

    probe = import_copy(path)
    (xmin, xmax), (ymin, ymax), (zmin, zmax) = world_bounds(probe)
    bpy.data.objects.remove(probe, do_unlink=True)

    split_x = (xmin + xmax) / 2
    band_lo = split_x - OVERLAP / 2
    band_hi = split_x + OVERLAP / 2
    z_mid = (zmin + zmax) / 2

    y_full = (ymin - MARGIN, ymax + MARGIN)
    z_full = (zmin - MARGIN, zmax + MARGIN)

    print(f"\n=== {stem} ===")
    print(f"bounds x[{xmin:.2f},{xmax:.2f}] y[{ymin:.2f},{ymax:.2f}] "
          f"z[{zmin:.2f},{zmax:.2f}]  split_x={split_x:.2f} "
          f"band=[{band_lo:.2f},{band_hi:.2f}]")

    # --- Half A: everything up to band_hi, bottom-half tongue in the band ---
    a = import_copy(path)
    apply_boolean(
        a, make_box((xmin - MARGIN, band_hi), y_full, z_full, "boxA_keep"),
        'INTERSECT')
    apply_boolean(
        a, make_box((band_lo, band_hi), y_full, (z_mid, zmax + MARGIN), "boxA_relief"),
        'DIFFERENCE')
    vol_a, nm_a, tot_a = mesh_diagnostics(a)
    print(f"A: dims={tuple(round(d,2) for d in a.dimensions)} "
          f"volume={vol_a:.1f} nonmanifold={nm_a}/{tot_a}")
    assert vol_a > 0.0, f"{stem} half A has zero/negative volume - boolean likely emptied it"
    a.name = f"{stem}_A"
    out_a = os.path.join(OUT_DIR, f"{stem}_SCARF_A.stl")
    bpy.ops.object.select_all(action='DESELECT')
    a.select_set(True)
    bpy.context.view_layer.objects.active = a
    bpy.ops.wm.stl_export(filepath=out_a, export_selected_objects=True)

    # --- Half B: everything from band_lo onward, top-half tongue in the band,
    #     then physically flipped so that tongue prints bed-side-down ---
    b = import_copy(path)
    apply_boolean(
        b, make_box((band_lo, xmax + MARGIN), y_full, z_full, "boxB_keep"),
        'INTERSECT')
    apply_boolean(
        b, make_box((band_lo, band_hi), y_full, (zmin - MARGIN, z_mid), "boxB_relief"),
        'DIFFERENCE')
    vol_b, nm_b, tot_b = mesh_diagnostics(b)
    print(f"B (pre-flip): dims={tuple(round(d,2) for d in b.dimensions)} "
          f"volume={vol_b:.1f} nonmanifold={nm_b}/{tot_b}")
    assert vol_b > 0.0, f"{stem} half B has zero/negative volume - boolean likely emptied it"

    flip_180_apply(b, (ymin + ymax) / 2, z_mid)
    vol_b2, nm_b2, tot_b2 = mesh_diagnostics(b)
    print(f"B (flipped): volume={vol_b2:.1f} nonmanifold={nm_b2}/{tot_b2}")
    assert vol_b2 > 0.0, f"{stem} half B lost its volume sign after the Z-flip"

    b.name = f"{stem}_B"
    out_b = os.path.join(OUT_DIR, f"{stem}_SCARF_B_flip-to-print.stl")
    bpy.ops.object.select_all(action='DESELECT')
    b.select_set(True)
    bpy.context.view_layer.objects.active = b
    bpy.ops.wm.stl_export(filepath=out_b, export_selected_objects=True)

    print(f"OK {stem}: A width={a.dimensions.x:.1f}mm  B width={b.dimensions.x:.1f}mm "
          f"(bed limit 260mm)")
    assert a.dimensions.x <= 260.0 and a.dimensions.x <= 260.0, f"{stem} half A too wide for the bed"
    assert b.dimensions.x <= 260.0, f"{stem} half B too wide for the bed"
    assert a.dimensions.y <= 260.0 and b.dimensions.y <= 260.0, f"{stem} halves too deep for the bed"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for fname, stem in PIECES:
        split_piece(fname, stem)


if __name__ == "__main__":
    main()
