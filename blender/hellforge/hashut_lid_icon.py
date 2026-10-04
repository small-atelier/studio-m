#!/usr/bin/env python3
"""Portable Hellforge — Hashut bull-skull icon, big flat lid appliqué, v1.

Blender/bpy script - paste into the Script Editor and run (Alt+P), or:
  blender --background --python hashut_lid_icon.py

Not a new icon design - reuses the bull skull already traced for the
Daemonic Power token project (blender/tokens/bull_contours.json, marching-
squares contours from blender/tokens/source/bull_hashut.png, see
extract_icon_contours.py there). Scaled way up and printed flat, 3mm
thick, as a multi-part appliqué glued onto the box lid - a completely
different physical object from the tokens, same source art.

ICON_W is a first-pass "big" guess (300mm) - bigger than a single FDM bed
side (260mm), which is the point: it forces the multi-piece cut this
script exists to work out. Adjust and rerun if the real lid ends up a
different size once the box is in hand.

Cut plan (verified against the icon's own real geometry, not assumed):
the bull's horns are the widest feature (full icon width, ~300mm) but sit
in a narrow band near the top; the head/face below is narrower (~188mm).
So: one horizontal cut separates the head from the horn band, then one
vertical cut splits the horn band in half (through the small diamond
gem between the horns - it's a decorative hole, not structural, so a
seam through it just leaves each piece with half a notch that completes
into the full gem shape once glued, same "holes can cross a seam" trick
already used on the forge floor). 3 pieces, each comfortably under the
260mm bed.

Boolean approach follows [[feedback_blender_boolean_fragility]]: outer
contours are unioned into one pass, hole contours differenced in their
own pass, pieces are split via INTERSECT (proven pattern from the resin
quadrant split) - never a chain of one-boolean-per-contour onto a single
growing target.
"""
import bpy
import bmesh
import json
import math
import mathutils
import os

# ============================================================
# CONFIG (all mm)
# ============================================================
CONTOURS_PATH = "/Users/mannil/studio-m/blender/tokens/bull_contours.json"
EXPORT_DIR = "/Users/mannil/studio-m/blender/hellforge/output_lid_icon"
EXPORT_STL = True

RENDER_IMAGES = True
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1600, 900)

OVERSHOOT = 1.0

ICON_W = 300.0          # "big" - a first-pass guess, bigger than one FDM bed side on purpose
THICKNESS = 3.0         # flat appliqué, glued onto the lid - not structural, no rebate/socket needed

BED_MARGIN_TARGET = 250.0   # each piece should land comfortably under this (260mm bed, ~10mm margin)


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
    return target


def join_objects(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    joined = bpy.context.active_object
    joined.name = name
    return joined


def duplicate_object(obj, name):
    new_obj = obj.copy()
    new_obj.data = obj.data.copy()
    new_obj.name = name
    bpy.context.collection.objects.link(new_obj)
    return new_obj


def add_box_range(x_range, y_range, z_range):
    x0, x1 = x_range
    y0, y1 = y_range
    z0, z1 = z_range
    size = (x1 - x0, y1 - y0, z1 - z0)
    center = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.active_object
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def build_slab(outline, z0, z1, name):
    bm = bmesh.new()
    bottom = [bm.verts.new((x, y, z0)) for x, y in outline]
    top = [bm.verts.new((x, y, z1)) for x, y in outline]
    bm.faces.new(reversed(bottom))
    bm.faces.new(top)
    n = len(outline)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def mesh_volume(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    volume = bm.calc_volume()
    bm.free()
    return volume


def mesh_bounds_xy(obj):
    xs = [(obj.matrix_world @ mathutils.Vector(c)).x for c in obj.bound_box]
    ys = [(obj.matrix_world @ mathutils.Vector(c)).y for c in obj.bound_box]
    return max(xs) - min(xs), max(ys) - min(ys)


def compute_scene_bounds(objs):
    xs, ys, zs = [], [], []
    for obj in objs:
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ mathutils.Vector(corner)
            xs.append(world_corner.x)
            ys.append(world_corner.y)
            zs.append(world_corner.z)
    center = mathutils.Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2))
    size = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    return center, size


def setup_camera_and_light(center):
    cam_data = bpy.data.cameras.new("RenderCam")
    cam_obj = bpy.data.objects.new("RenderCam", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    target = bpy.data.objects.new("RenderTarget", None)
    target.location = center
    bpy.context.collection.objects.link(target)
    track = cam_obj.constraints.new(type='TRACK_TO')
    track.target = target
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'
    light_data = bpy.data.lights.new("RenderSun", type='SUN')
    light_data.energy = 3.0
    light_obj = bpy.data.objects.new("RenderSun", light_data)
    light_obj.rotation_euler = (math.radians(55), 0.0, math.radians(35))
    bpy.context.collection.objects.link(light_obj)
    bpy.context.scene.camera = cam_obj
    return cam_obj


def render_iso(name, objs):
    """Renders ONLY `objs` - see the same fix in forge_floor_tiles_v3.py's
    render_iso for why this matters (a stale object left in the scene from
    an earlier build step otherwise silently shows up layered into later
    renders)."""
    os.makedirs(RENDER_DIR, exist_ok=True)
    others = [o for o in bpy.data.objects if o.type == 'MESH' and o not in objs]
    prev_hide = {o.name: o.hide_render for o in others}
    for o in others:
        o.hide_render = True
    center, size = compute_scene_bounds(objs)
    cam_obj = setup_camera_and_light(center)
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = RENDER_RESOLUTION[0]
    scene.render.resolution_y = RENDER_RESOLUTION[1]
    cam_obj.location = center + mathutils.Vector((0.0, 0.0, 1.0)) * max(size * 1.6, 20.0)
    scene.render.filepath = os.path.join(RENDER_DIR, f"{name}_top.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {scene.render.filepath}")
    for o in others:
        o.hide_render = prev_hide[o.name]


def export_stl(obj, filename):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = os.path.join(EXPORT_DIR, filename)
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"Exported {path}")


def dedupe_closed_loop(points, tol=1e-9):
    """Traced hole contours repeat their first point as their last (see
    extract_icon_contours.py / build_tokens.py's own note on this) - drop
    it, or bm.faces.new builds a degenerate ngon with a zero-length edge."""
    if len(points) > 1:
        x0, y0 = points[0]
        x1, y1 = points[-1]
        if abs(x0 - x1) < tol and abs(y0 - y1) < tol:
            return points[:-1]
    return points


def load_contours():
    with open(CONTOURS_PATH) as f:
        return json.load(f)


GAP_CONNECTOR_OVERLAP = 2.0   # how far the connector reaches past each real edge, for a real union overlap


def polygon_lower_edge_at_x(poly, x):
    """The polygon boundary's lowest y-crossing at a given x - i.e. where a
    vertical ray from y=-inf first hits the shape. NOT the same as the
    polygon's global min-y: the horn band curves/tapers, so its lower edge
    at any one x can sit well above its overall lowest point (confirmed
    numerically: at the right bridge's x, the horn's real local edge was
    ~2.5mm higher than the global min - using the global value undershot
    and left that connector not actually touching the horn, caught by an
    island-count check on the exported STL, not assumed to be fine)."""
    n = len(poly)
    ys = []
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (x0 <= x < x1) or (x1 <= x < x0):
            t = (x - x0) / (x1 - x0)
            ys.append(y0 + t * (y1 - y0))
    assert ys, f"vertical ray at x={x} never crosses the polygon - x is outside its span"
    return min(ys)


def build_gap_connector(bridge_pts, horn_pts, thickness, name):
    """The bridge contours don't actually touch the horn band's own outline
    - checked, not assumed: after a plain UNION, an island-count pass on
    the exported STL found 2 disjoint shells, not 1 (a real gap between
    the bridge's top edge and the horn's bottom edge in the traced art -
    invisible in a flat top-down render, since both still overlap in X,
    but the print would have been two loose unglued fragments, not one
    piece). Fixed by adding this small rectangular tab spanning the gap,
    positioned at the bridge's own X range, reaching up to the horn's
    LOCAL lower edge at that X (not its global lowest point - see
    polygon_lower_edge_at_x), overlapping real material on both ends
    rather than meeting it exactly flush."""
    bx = [p[0] for p in bridge_pts]
    by = [p[1] for p in bridge_pts]
    bridge_top = max(by)
    x0, x1 = min(bx), max(bx)
    horn_local_bottom = min(polygon_lower_edge_at_x(horn_pts, x0 + 1e-6),
                             polygon_lower_edge_at_x(horn_pts, x1 - 1e-6))
    assert horn_local_bottom > bridge_top, \
        f"{name}: expected a gap (horn's local bottom above the bridge top) - geometry assumption no longer holds"
    y0 = bridge_top - GAP_CONNECTOR_OVERLAP
    y1 = horn_local_bottom + GAP_CONNECTOR_OVERLAP
    outline = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return build_slab(outline, 0.0, thickness, name)


def build_outer_piece(outer_pts, all_hole_pts, thickness, name):
    """One natural outer contour, extruded, with every hole contour
    differenced against it - holes that don't actually overlap this piece
    are a harmless no-op cut, same principle as a socket hole straddling a
    seam on the forge floor: no need to know in advance which holes
    'belong' to which outer shape, the boolean just removes whatever
    overlaps."""
    solid = build_slab(outer_pts, 0.0, thickness, name)
    for i, hpts in enumerate(all_hole_pts):
        cutter = build_slab(hpts, -OVERSHOOT, thickness + OVERSHOOT, f"{name}_hole_{i}")
        apply_boolean(solid, cutter, 'DIFFERENCE')
    return solid


def split_in_half(piece, name):
    """Cuts one piece into 2 via INTERSECT (proven technique from the
    forge floor's resin quadrant split), along whichever axis it's
    actually oversized on - not a fixed direction, so this works whichever
    natural piece turns out too big, not just the horn band."""
    w, h = mesh_bounds_xy(piece)
    xs = [(piece.matrix_world @ mathutils.Vector(c)).x for c in piece.bound_box]
    ys = [(piece.matrix_world @ mathutils.Vector(c)).y for c in piece.bound_box]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    vertical_cut = w >= h   # wider than tall -> cut with a vertical line (split left/right)
    halves = []
    for half_name, xr, yr in ([(f"{name}_l", (x0, (x0 + x1) / 2), (y0, y1)),
                                (f"{name}_r", ((x0 + x1) / 2, x1), (y0, y1))]
                               if vertical_cut else
                               [(f"{name}_b", (x0, x1), (y0, (y0 + y1) / 2)),
                                (f"{name}_t", (x0, x1), ((y0 + y1) / 2, y1))]):
        dup = duplicate_object(piece, half_name)
        box = add_box_range((xr[0] - OVERSHOOT, xr[1] + OVERSHOOT),
                             (yr[0] - OVERSHOOT, yr[1] + OVERSHOOT),
                             (-OVERSHOOT, THICKNESS + OVERSHOOT))
        apply_boolean(dup, box, 'INTERSECT')
        halves.append(dup)
    bpy.data.objects.remove(piece, do_unlink=True)
    return halves


def fit_to_bed(piece, name, depth=0):
    """Recursively halves a piece until every result fits BED_MARGIN_TARGET
    on both axes - in practice only the horn band needs this (one split),
    but written generally rather than hardcoded to that one case."""
    w, h = mesh_bounds_xy(piece)
    if w <= BED_MARGIN_TARGET and h <= BED_MARGIN_TARGET:
        return [(name, piece)]
    assert depth < 4, f"{name}: still too big after {depth} splits - bed target may be unreachable for this shape"
    halves = split_in_half(piece, name)
    result = []
    for h_obj in halves:
        result.extend(fit_to_bed(h_obj, h_obj.name, depth + 1))
    return result


def main():
    clear_scene()
    contours = load_contours()
    outer = [c for c in contours if not c["hole"]]
    xs = [p[0] for c in outer for p in c["points"]]
    ys = [p[1] for c in outer for p in c["points"]]
    aspect = (max(xs) - min(xs)) / (max(ys) - min(ys))
    icon_h = ICON_W / aspect
    print(f"Icon: {ICON_W:.1f}x{icon_h:.1f}mm (aspect {aspect:.4f} from the traced outline)")

    real_outer, real_holes = [], []
    for c in contours:
        pts = dedupe_closed_loop([(u * ICON_W, v * icon_h) for u, v in c["points"]])
        (real_holes if c["hole"] else real_outer).append(pts)

    # Indices confirmed by inspecting the real bboxes (not assumed): 0 is
    # the horn band, 1 and 3 are the two tiny bridge slivers where each
    # horn curls down to meet the head at the outer edges, 2 is the head.
    # Folded into the horn band BEFORE the bed-fit split (not after) - each
    # bridge sits right at the horn band's own left/right edge, so once
    # the merged shape is split in half, each bridge lands in the correct
    # (nearest) horn half automatically, no special-casing needed.
    HORN_IDX, BRIDGE_IDXS, HEAD_IDX = 0, (1, 3), 2
    assert set(range(len(real_outer))) == {HORN_IDX, *BRIDGE_IDXS, HEAD_IDX}, \
        "natural contour count/order changed - re-check which index is which before trusting this merge"

    built = [build_outer_piece(pts, real_holes, THICKNESS, f"icon_part_{i}")
             for i, pts in enumerate(real_outer)]
    horn = built[HORN_IDX]
    for bi in BRIDGE_IDXS:
        connector = build_gap_connector(real_outer[bi], real_outer[HORN_IDX], THICKNESS, f"icon_connector_{bi}")
        apply_boolean(horn, connector, 'UNION')
        apply_boolean(horn, built[bi], 'UNION')
    w, h = mesh_bounds_xy(horn)
    print(f"horn band + 2 bridges (with gap connectors) merged: {w:.1f}x{h:.1f}mm before bed-fit split")

    all_pieces = []
    all_pieces.extend(fit_to_bed(horn, "icon_horn"))
    all_pieces.extend(fit_to_bed(built[HEAD_IDX], "icon_head"))

    for name, piece in all_pieces:
        w, h = mesh_bounds_xy(piece)
        print(f"piece {name}: {w:.1f}x{h:.1f}mm volume={mesh_volume(piece):.0f}mm3 (fits the bed)")
        if EXPORT_STL:
            export_stl(piece, f"hashut_{name}.stl")
    if RENDER_IMAGES:
        render_iso("hashut_icon_pieces", [p for _, p in all_pieces])

    print(f"Done. {len(all_pieces)} pieces total.")


if __name__ == "__main__":
    main()
