"""
Extend the modular drawer/housing STLs along their length axis (Blender
bpy, headless-runnable) - NOT a from-scratch part, this edits found
STLs in place.

Technique: cut and splice, not a uniform scale. For each part:
  1. "bottom" = everything up to a cut plane, kept as-is.
  2. "top" = everything from the cut plane onward, translated by
     +EXTENSION so it moves away from bottom by exactly that much.
  3. "donor" = a thin slice extracted from a genuinely constant-
     cross-section region of the ORIGINAL mesh (no vertices strictly
     inside it - see find_safe_zones below), then SCALED along the
     length axis to fill the gap left between bottom and top's new
     position. Since the donor's cross-section is constant by
     construction, stretching it doesn't distort anything - it's the
     same wall thickness, rail slots, everything, just longer.
  4. Union bottom + donor + top, then a final dissolve_degenerate pass
     to clean up any leftover EXACT-solver seam artifacts.

This keeps every actual feature (rounded corners, rail/interlock slots,
the drawer's finger-pull notch) at original size - only the boring
middle grows.

Confirmed with the user: module's 150mm axis is where the drawer's
144mm axis slides in (~6mm clearance) - the module's own STL is
oriented upright (open-top) in the file, meant to lie on its side once
installed. Same +EXTENSION delta must be applied to both the module
family and the drawer family to keep that clearance constant.

Pitfalls hit getting this reliable (see feedback_stl_surgery_pitfalls
memory for the full writeup):
  - These STLs are NOT centered near the world origin (e.g. one
    drawer's X range was 436-524mm) - a clipping box sized/centered
    around (0,0,0) silently clipped real geometry. Fixed by deriving
    box bounds from the actual per-file world bounding box (+MARGIN),
    not an assumed fixed size.
  - Landing the cut/donor planes exactly ON a safe zone's boundary
    (even by 0.5mm) was still fragile for 2 of 7 files - centering them
    in the MIDDLE of the widest available safe zone was what actually
    made every file clean.
  - A small deliberate overlap (donor slightly bigger than the gap)
    made things WORSE here, not better - unlike the general "always
    overlap generously" rule, the overlap region's cross-section didn't
    exactly match its neighbor once it crossed out of the safe zone.
    Exact-touch (zero overlap, matching the same cut value) worked
    better - the fix that mattered was picking a good cut LOCATION so
    the solver wasn't handling ambiguous/coincident geometry there.

Run: blender --background --python extend_parts.py
"""

import bpy
import bmesh
import os
import mathutils

SRC_DIR = "/Users/mannil/Desktop/studio-m/DRAWERS"
OUT_DIR = "/Users/mannil/Desktop/studio-m/DRAWERS/extended"
EXTENSION = 100.0   # mm added to every part's length axis
MARGIN = 50.0       # generous safety margin beyond each object's own bounds,
                     # for the box sides NOT doing the cutting

# (filename, axis[0=X,1=Y,2=Z], cut, donor_lo, donor_hi) - cut/donor
# centered in the widest available vertex-free zone for each file, not
# at its edges (see find_safe_zones.py-style scan in the memory note
# for how these were found)
PARTS = [
    ("Full-width module.stl.stl",              2, 66.9,   65.9,   67.9),
    ("Half-width module.stl.stl",               2, 73.85,  72.85,  74.85),
    ("Full-width container_dual_shelf.stl.stl", 2, 66.6,   65.6,   67.6),
    ("Full-width Open storage bin.stl.stl",     2, 65.6,   64.6,   66.6),
    ("Half-width Open storage bin.stl.stl",     2, 74.4,   73.4,   75.4),
    ("drawer 140x36x46.stl.stl",                1, -192.8, -193.3, -192.3),
    ("drawer140x84x46.stl.stl",                 1, -192.8, -193.3, -192.3),
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
        wc = obj.matrix_world @ mathutils.Vector(c)
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


def make_box(lo, hi, axis, bounds3, name):
    """A box spanning [lo, hi] along `axis`, and the object's own
    (margin-padded) extent on the other two axes - NOT a fixed size
    centered at the origin, since these STLs sit far from it."""
    if lo > hi:
        lo, hi = hi, lo
    size = [b[1] - b[0] for b in bounds3]
    center = [(b[0] + b[1]) / 2 for b in bounds3]
    size[axis] = hi - lo
    center[axis] = (lo + hi) / 2
    bpy.ops.mesh.primitive_cube_add(size=1, location=tuple(center))
    obj = bpy.context.object
    obj.name = name
    obj.scale = tuple(size)
    return obj


def translate_apply(obj, offset):
    obj.location = tuple(offset)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=True)


def extend_part(fname, axis, cut, donor_lo, donor_hi, extension):
    path = os.path.join(SRC_DIR, fname)
    clear_scene()

    probe = import_copy(path)
    bx, by, bz = world_bounds(probe)
    bounds3 = ((bx[0] - MARGIN, bx[1] + MARGIN),
               (by[0] - MARGIN, by[1] + MARGIN),
               (bz[0] - MARGIN, bz[1] + MARGIN))
    bpy.data.objects.remove(probe, do_unlink=True)

    bottom = import_copy(path)
    apply_boolean(bottom, make_box(bounds3[axis][0] - 10, cut, axis, bounds3, "box_bottom"), 'INTERSECT')

    top = import_copy(path)
    apply_boolean(top, make_box(cut, bounds3[axis][1] + 10, axis, bounds3, "box_top"), 'INTERSECT')
    off = [0.0, 0.0, 0.0]
    off[axis] = extension
    translate_apply(top, off)

    donor = import_copy(path)
    apply_boolean(donor, make_box(donor_lo, donor_hi, axis, bounds3, "box_donor"), 'INTERSECT')
    lo = min(donor_lo, donor_hi)
    thickness = abs(donor_hi - donor_lo)
    factor = extension / thickness
    bm = bmesh.new()
    bm.from_mesh(donor.data)
    for v in bm.verts:
        v.co[axis] = lo + (v.co[axis] - lo) * factor
    bm.to_mesh(donor.data)
    bm.free()
    donor.data.update()
    shift = [0.0, 0.0, 0.0]
    shift[axis] = cut - lo
    translate_apply(donor, shift)

    apply_boolean(bottom, donor, 'UNION')
    apply_boolean(bottom, top, 'UNION')

    bm = bmesh.new()
    bm.from_mesh(bottom.data)
    bmesh.ops.dissolve_degenerate(bm, dist=0.01, edges=bm.edges)
    bm.to_mesh(bottom.data)
    bottom.data.update()
    nm_count = len([e for e in bm.edges if not e.is_manifold])
    bm.free()

    out_name = os.path.splitext(os.path.splitext(fname)[0])[0] + "_extended.stl"
    out_path = os.path.join(OUT_DIR, out_name)
    bpy.ops.object.select_all(action='DESELECT')
    bottom.select_set(True)
    bpy.context.view_layer.objects.active = bottom
    bpy.ops.wm.stl_export(filepath=out_path, export_selected_objects=True)
    print(f"OK {fname:45s} -> {out_name:45s} "
          f"dims={tuple(round(d,1) for d in bottom.dimensions)} nonmanifold={nm_count}")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for args in PARTS:
        extend_part(*args, EXTENSION)


if __name__ == "__main__":
    main()
