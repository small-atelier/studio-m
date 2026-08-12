"""
Half-width module -> open-ended stick/wire organizer tube with 4
labeled compartments (Blender bpy, headless-runnable).

Does the +106mm length extension AND the organizer modifications (floor
removal, dividers, label lips) in ONE continuous pipeline starting from
the ORIGINAL "Half-width module.stl.stl" - not by loading the already-
extended/exported file. Doing it in two separate passes (extend, export,
reimport, modify) reopened small holes right at the old splice seam
(Z~73.85) when the new booleans touched that region again - real
1-face-boundary-edge gaps, not precision noise. Building it all in one
pass from the original avoids ever re-touching an already-resolved seam.

Steps:
  1. Extend +106mm (150mm -> 256mm), same technique/parameters as
     extend_parts.py: cut and splice a donor slice from a safe
     (vertex-free) zone, not a uniform scale. The extra 6mm (over the
     rest of the family's +100mm) pre-compensates for the floor-removal
     cut in step 2, which chops 6mm (FLOOR_CUT_Z) off the bottom - net
     result lands back at the family's 250mm total length.
  2. Remove the closed floor (a solid slab, Z 0-6mm) so both ends are
     open - a genuine tube.
  3. Add two crossing divider plates (a "+" in cross-section) splitting
     the 40x50mm cavity into a 2x2 grid of 4 compartments, ~18.5x23.5mm
     each. Dividers run the tube's full length and embed 2mm into the
     surrounding walls for a solid connection.
  4. Add a label lip (8mm protrusion, 3mm thick), flush with the tube's
     own top rim - not recessed - so the label rests across both the
     lip and the wall's own top edge as one continuous flat surface.
     2 lip boxes, each spanning the full cavity width and split into
     two ledges by the crossing X-divider automatically.
  5. Flip 180 degrees (a real rotation, not a mirror - keeps face
     winding/normals correct) so the lip end prints at the BOTTOM,
     right on the build plate - otherwise the lip is a flat shelf over
     open compartment space, a genuine unsupported overhang. Also
     recenters the part near the origin and sits it at Z=0, since the
     source STLs came in at an arbitrary far-from-origin position - the
     exported file is print-ready as-is, no manual reorientation needed
     in the slicer.

Run: blender --background --python make_stick_organizer.py
"""

import bpy
import bmesh
import os
import mathutils

SRC = "/Users/mannil/Desktop/studio-m/DRAWERS/Half-width module.stl.stl"
OUT_DIR = "/Users/mannil/Desktop/studio-m/DRAWERS/extended"
OUT_NAME = "Half-width stick organizer.stl"

EXTENSION = 106.0  # +6mm over the family's +100mm: floor removal below
                    # cuts FLOOR_CUT_Z (6mm) off the bottom, so extending
                    # by 106 here lands back at the family's 250mm total
EXT_CUT = 73.85
EXT_DONOR = (72.85, 74.85)
MARGIN = 50.0

# measured directly from the (pre-extension) source mesh
OUTER_X = (440.9, 490.9)
OUTER_Y = (95.0, 155.0)
CAVITY_X = (445.9, 485.9)
CAVITY_Y = (100.0, 150.0)
WALL_T = 5.0
Z_BOTTOM = 0.0
Z_TOP_ORIGINAL = 150.0
Z_TOP = Z_TOP_ORIGINAL + EXTENSION  # 250.0 after extension

FLOOR_CUT_Z = 6.0

DIVIDER_T = 3.0
# The front/back walls (OUTER_Y) carry a dovetail groove for connector.stl,
# centered at mid_x and running the full length, cut 4mm deep into the 5mm
# wall - only a 1mm membrane remains behind it. div_x lands exactly there,
# so its embed must stay under 1mm or it pokes into the (empty) groove
# channel and blocks the connector. 0.8mm leaves a small safety margin.
# The left/right walls (OUTER_X) have no groove, so div_y can use the full
# embed depth.
DIVIDER_EMBED_Y_WALLS = 0.8   # div_x embedding into front/back walls
DIVIDER_EMBED_X_WALLS = 2.0   # div_y embedding into left/right walls

LIP_PROTRUSION = 8.0        # bigger - was 4.0
LIP_EMBED = 1.5
LIP_THICKNESS = 3.0         # a bit thicker to support the larger protrusion
LIP_Z_TOP_MARGIN = 0.0      # flush with the tube's own top rim (was 5.0,
                             # recessed) - so the label rests across both
                             # the lip AND the wall's own top edge as one
                             # continuous flat surface, not a stepped-down shelf


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for b in list(bpy.data.meshes):
        bpy.data.meshes.remove(b)


def import_copy(path):
    bpy.ops.wm.stl_import(filepath=path)
    return bpy.context.selected_objects[0]


def apply_boolean(target, cutter, operation):
    mod = target.modifiers.new("Bool", 'BOOLEAN')
    mod.object = cutter
    mod.operation = operation
    mod.solver = 'EXACT'
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def make_box(xr, yr, zr, name):
    center = ((xr[0] + xr[1]) / 2, (yr[0] + yr[1]) / 2, (zr[0] + zr[1]) / 2)
    size = (xr[1] - xr[0], yr[1] - yr[0], zr[1] - zr[0])
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.scale = size
    return obj


def translate_apply(obj, offset):
    obj.location = tuple(offset)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=True)


def extend_length(path):
    """Same cut-and-splice technique as extend_parts.py, axis=2 (Z)."""
    axis = 2
    bounds3 = ((OUTER_X[0]-MARGIN, OUTER_X[1]+MARGIN),
               (OUTER_Y[0]-MARGIN, OUTER_Y[1]+MARGIN),
               (Z_BOTTOM-MARGIN, Z_TOP_ORIGINAL+MARGIN))

    bottom = import_copy(path)
    apply_boolean(bottom, make_box(
        (bounds3[0][0], bounds3[0][1]), (bounds3[1][0], bounds3[1][1]),
        (bounds3[2][0]-10, EXT_CUT), "box_bottom"), 'INTERSECT')

    top = import_copy(path)
    apply_boolean(top, make_box(
        (bounds3[0][0], bounds3[0][1]), (bounds3[1][0], bounds3[1][1]),
        (EXT_CUT, bounds3[2][1]+10), "box_top"), 'INTERSECT')
    translate_apply(top, (0, 0, EXTENSION))

    donor = import_copy(path)
    apply_boolean(donor, make_box(
        (bounds3[0][0], bounds3[0][1]), (bounds3[1][0], bounds3[1][1]),
        EXT_DONOR, "box_donor"), 'INTERSECT')
    lo = min(EXT_DONOR)
    thickness = abs(EXT_DONOR[1] - EXT_DONOR[0])
    factor = EXTENSION / thickness
    bm = bmesh.new()
    bm.from_mesh(donor.data)
    for v in bm.verts:
        v.co[axis] = lo + (v.co[axis] - lo) * factor
    bm.to_mesh(donor.data)
    bm.free()
    donor.data.update()
    translate_apply(donor, (0, 0, EXT_CUT - lo))

    apply_boolean(bottom, donor, 'UNION')
    apply_boolean(bottom, top, 'UNION')
    return bottom


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    clear_scene()

    body = extend_length(SRC)

    # remove the floor
    apply_boolean(
        body,
        make_box((OUTER_X[0]-10, OUTER_X[1]+10), (OUTER_Y[0]-10, OUTER_Y[1]+10),
                  (FLOOR_CUT_Z, Z_TOP+10), "box_open"),
        'INTERSECT',
    )

    mid_x = (CAVITY_X[0] + CAVITY_X[1]) / 2
    mid_y = (CAVITY_Y[0] + CAVITY_Y[1]) / 2

    div_x = make_box(
        (mid_x - DIVIDER_T/2, mid_x + DIVIDER_T/2),
        (OUTER_Y[0] + WALL_T - DIVIDER_EMBED_Y_WALLS, OUTER_Y[1] - WALL_T + DIVIDER_EMBED_Y_WALLS),
        (FLOOR_CUT_Z, Z_TOP),
        "divider_x",
    )
    apply_boolean(body, div_x, 'UNION')

    div_y = make_box(
        (OUTER_X[0] + WALL_T - DIVIDER_EMBED_X_WALLS, OUTER_X[1] - WALL_T + DIVIDER_EMBED_X_WALLS),
        (mid_y - DIVIDER_T/2, mid_y + DIVIDER_T/2),
        (FLOOR_CUT_Z, Z_TOP),
        "divider_y",
    )
    apply_boolean(body, div_y, 'UNION')

    lip_z = (Z_TOP - LIP_Z_TOP_MARGIN - LIP_THICKNESS, Z_TOP - LIP_Z_TOP_MARGIN)

    lip_front = make_box(
        CAVITY_X,
        (CAVITY_Y[0] - LIP_EMBED, CAVITY_Y[0] + LIP_PROTRUSION),
        lip_z, "lip_front",
    )
    apply_boolean(body, lip_front, 'UNION')

    div_y_back_face = mid_y + DIVIDER_T / 2
    lip_back = make_box(
        CAVITY_X,
        (div_y_back_face - LIP_EMBED, div_y_back_face + LIP_PROTRUSION),
        lip_z, "lip_back",
    )
    apply_boolean(body, lip_back, 'UNION')

    bm = bmesh.new()
    bm.from_mesh(body.data)
    bmesh.ops.dissolve_degenerate(bm, dist=0.01, edges=bm.edges)
    boundary_edges = [e for e in bm.edges if len(e.link_faces) == 1]
    if boundary_edges:
        bmesh.ops.holes_fill(bm, edges=boundary_edges, sides=0)

    # Flip for print: the label lips are a flat shelf with nothing under
    # them - printed as originally oriented (lips near the top), that's
    # a true unsupported overhang the whole way across each compartment.
    # A proper 180-degree rotation about X (not a mirror - preserves
    # face winding/normals, no flip needed) puts the lip end at the
    # BOTTOM of the print instead, right on the build plate, so it needs
    # no support at all. Then recenter so it sits print-ready (Z from 0
    # up, X/Y centered near the origin) instead of the arbitrary far-
    # from-origin position these found STLs came in at.
    bm.verts.ensure_lookup_table()
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    cy, cz = (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2
    for v in bm.verts:
        v.co.y = 2 * cy - v.co.y
        v.co.z = 2 * cz - v.co.z
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    dx, dy, dz = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, min(zs)
    for v in bm.verts:
        v.co.x -= dx
        v.co.y -= dy
        v.co.z -= dz

    bm.to_mesh(body.data)
    body.data.update()
    nm_count = len([e for e in bm.edges if not e.is_manifold])
    vol = bm.calc_volume(signed=True)
    bm.free()

    out_path = os.path.join(OUT_DIR, OUT_NAME)
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.wm.stl_export(filepath=out_path, export_selected_objects=True)
    print(f"OK -> {out_path} dims={tuple(round(d,1) for d in body.dimensions)} "
          f"nonmanifold={nm_count} vol={vol:.1f}")


if __name__ == "__main__":
    main()
