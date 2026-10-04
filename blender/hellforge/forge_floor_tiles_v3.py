#!/usr/bin/env python3
"""Portable Hellforge — forge floor, two-material print geometry, v11.

Blender/bpy script - paste into the Script Editor and run (Alt+P), or:
  blender --background --python forge_floor_tiles_v3.py

Every tile is TWO printed parts glued together, matching how individual
miniature bases are being built (FDM base for structure, resin topper for
detail):

  - FDM structural slab (thick, load-bearing): plain tile shape, a shallow
    rebate on the UNDERSIDE sized to the whole tile for a steel sheet to
    slot into, and a THROUGH-hole (full thickness) at every socket
    position. The steel sheet (slotted in from below, not printed) is what
    the miniature's own base magnets actually grip.
  - Resin detail skin (thin, glued on top of the FDM slab): carries ALL
    the fine surface detail - panel-seam grooves, the grate, rivets,
    paving, the smelting pool, the molten channels, hand-tool props, and
    (v11) the real Roaring Furnace body, fused in permanently. Also gets a
    hole at every socket position, cut LAST (after decoration), so the cut
    naturally removes any decoration material that happens to fall inside
    a hole's footprint.

The resin skin's socket plug isn't scrap: it's captured (via boolean
INTERSECT on a duplicate, before the hole is cut) and exported as a unique
base topper per model - literally a piece of the floor at that exact spot.
The Roaring Furnace is still one of these sockets (v11 re-added it after a
v10 detour that dropped it entirely) - its topper just happens to carry
the fused 3D furnace body along with it, since the union into the terrain
happens before stamping, not instead of it.

Socket holes are cut all the way through (SOCKET_GROWTH = +1mm over the
base diameter, loose enough to lift the model back out), not a blind
recess - the steel sheet under the FDM slab is what the hole actually
rests on.

Boolean approach follows [[feedback_blender_boolean_fragility]]: each
category (rebate, through-holes, grooves, grate, rivets, channels, paving)
is its own non-self-overlapping cutter object, one boolean pass each.

v11: floor/tile/socket/pool/channel/prop/paving DATA moved out to
forge_floor_data.py, a plain-Python (no bpy) module also used by
forge_floor_layout.py (the SVG planning renderer) - one master for both,
instead of forge_floor_layout.py keeping (and drifting from) its own copy,
which had happened 3 times already (v6, v7, v9/v10).
"""
import bpy
import bmesh
import math
import mathutils
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from forge_floor_data import (  # noqa: E402
    FDM_THICKNESS, RESIN_THICKNESS, STEEL_SHEET_THICKNESS, STEEL_REBATE_MARGIN,
    SOCKET_GROWTH, VERTICAL_SEAM_X, HORIZONTAL_SEAM_Y, GROOVE_WIDTH, GROOVE_DEPTH,
    GRATE_RECT, GRATE_SLOTS, GRATE_SLOT_WIDTH, GRATE_DEPTH,
    RIVET_DIAMETER, RIVET_HEIGHT, RIVET_EMBED,
    CHANNEL_WIDTH, CHANNEL_DEPTH, FLOW_WIDTH, FLOW_HEIGHT, FLOW_EMBED, MOLTEN_CHANNELS,
    FLOOR_W, FLOOR_D, WEDGE_CENTER, WEDGE_CUT_BL, WEDGE_CUT_BR, WEDGE_CUT_TOP,
    FURNACE_NAME, FURNACE_STL_PATH, FURNACE_HEIGHT,
    ALL_SOCKETS, TILE_NAMES, TILE_OUTLINES, GRATE_TILE, TILES, sockets_straddling_into,
    POOL_CENTER, POOL_INNER_RADIUS, POOL_MAX_RADIUS, POOL_CLEARANCE_MARGIN, POOL_SAMPLES,
    POOL_DEPTH, POOL_VEIN_COUNT, POOL_VEIN_WIDTH, POOL_VEIN_HEIGHT, POOL_VEIN_EMBED,
    POOL_VEIN_REACH_FRAC, pool_safe_radius, POOL_OUTLINE,
    TAB_BASE_HALF_WIDTH, TAB_TIP_HALF_WIDTH, TAB_REACH, TAB_EMBED, TAB_HOLE_CLEARANCE,
    WEDGE_JOINTS, cut_along_dir, perp_toward,
    PROP_PLACEMENTS,
    PAVING_CELL_SIZE, PAVING_CIRCLE_DIA, PAVING_LINE_WIDTH, PAVING_LINE_DEPTH, PAVING_CORNER_GAP,
    PAVING_PATTERNS, paving_pattern_for, PAVING_CELLS,
    RESIN_SPLIT, RESIN_QUADRANTS,
)

# ============================================================
# CONFIG local to this script (bpy export/render only - not shared with
# the SVG planner, which has no use for output paths or render settings)
# ============================================================
EXPORT_DIR = "/Users/mannil/studio-m/blender/hellforge/output_v3"
EXPORT_STL = True

RENDER_IMAGES = True
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1600, 900)
RENDER_ANGLES = {"iso": (0.6, -1.0, 0.6)}

OVERSHOOT = 1.0

print(f"Paving: {len(PAVING_CELLS)} candidate cells kept (see forge_floor_data.py for the count checked)")


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


def add_cylinder(diameter, z_range, loc_xy, vertices=32):
    z0, z1 = z_range
    bpy.ops.mesh.primitive_cylinder_add(
        radius=diameter / 2, depth=z1 - z0,
        location=(loc_xy[0], loc_xy[1], (z0 + z1) / 2), vertices=vertices,
    )
    return bpy.context.active_object


def build_angled_box(p0, p1, width, z_range, pad=0.0):
    """A box running between two XY points at any angle, full width `width`,
    extruded over z_range - the general case of add_box_range for anything
    that isn't axis-aligned (paving diagonals, pool veins). `pad` extends
    the length past both ends (e.g. to bite into a neighbouring feature for
    a clean union)."""
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    length = (dx ** 2 + dy ** 2) ** 0.5 + pad
    ang = math.atan2(dy, dx)
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    mz = (z_range[0] + z_range[1]) / 2
    bpy.ops.mesh.primitive_cube_add(size=1, location=(mx, my, mz))
    obj = bpy.context.active_object
    obj.scale = (length, width, z_range[1] - z_range[0])
    obj.rotation_euler = (0.0, 0.0, ang)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def mesh_volume(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    volume = bm.calc_volume()
    bm.free()
    return volume


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
    """Renders ONLY `objs` - `bpy.ops.render.render()` renders every object
    currently in the scene regardless of what's passed here, so any stale
    object left over from an earlier build step (e.g. the 15 topper
    objects, kept around after export for their STL but never deleted)
    would otherwise silently show up layered into a later render. Caught
    exactly that way: the quadrant-split render showed the fused furnace
    body even though the exported quadrant STLs (checked by volume) never
    contained it - the furnace TOPPER object was still sitting in the
    scene at the same world position. Temporarily hides every other mesh
    object for render, restores afterward."""
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
    for angle_name, direction in RENDER_ANGLES.items():
        cam_obj.location = center + mathutils.Vector(direction).normalized() * size * 2.2
        scene.render.filepath = os.path.join(RENDER_DIR, f"{name}_{angle_name}.png")
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


def inset_rect(outline, margin):
    xs = [p[0] for p in outline]
    ys = [p[1] for p in outline]
    return (min(xs) + margin, max(xs) - margin, min(ys) + margin, max(ys) - margin)


def build_dovetail_tab(point, along_dir, perp_dir, base_half_w, tip_half_w, reach, back, name):
    """A trapezoid, extruded the full FDM slab thickness, in the XY plane -
    the tab's own edge IS part of the tile outline, not a separate
    perpendicular peg. `along_dir` is the direction the trapezoid's width
    runs (parallel to the cut); `perp_dir` is the direction it reaches
    (perpendicular to the cut, from the male tile into the female one).
    `back` is how far the trapezoid's base sits behind the seam line
    (embed for a tab's union, OVERSHOOT for a pocket's cut). Generalizes
    the old axis-aligned version (perp_dir=(1,0), along_dir=(0,1)) to any
    cut direction, since v7's 3 cuts aren't axis-aligned."""
    px, py = point
    ax, ay = along_dir
    nx, ny = perp_dir

    def _pt(perp_amt, along_amt):
        return (px + perp_amt * nx + along_amt * ax, py + perp_amt * ny + along_amt * ay)

    outline = [
        _pt(-back, -base_half_w),
        _pt(reach, -tip_half_w),
        _pt(reach, tip_half_w),
        _pt(-back, base_half_w),
    ]
    return build_slab(outline, 0.0, FDM_THICKNESS, name)


def build_seam_joint_tabs_for_tile(tile_name):
    tabs = []
    for jname, from_pt, to_pt, male, female, ts in WEDGE_JOINTS:
        if male != tile_name:
            continue
        along = cut_along_dir(from_pt, to_pt)
        perp = perp_toward(from_pt, along, female)  # reaches from male into female
        for t in ts:
            point = (from_pt[0] + t * (to_pt[0] - from_pt[0]), from_pt[1] + t * (to_pt[1] - from_pt[1]))
            tabs.append(build_dovetail_tab(point, along, perp, TAB_BASE_HALF_WIDTH, TAB_TIP_HALF_WIDTH,
                                            TAB_REACH, TAB_EMBED, f"tab_{jname}_{t:g}"))
    return join_objects(tabs, f"joint_tabs_{tile_name}") if tabs else None


def build_seam_joint_pockets_for_tile(tile_name):
    c = TAB_HOLE_CLEARANCE
    pockets = []
    for jname, from_pt, to_pt, male, female, ts in WEDGE_JOINTS:
        if female != tile_name:
            continue
        along = cut_along_dir(from_pt, to_pt)
        perp = perp_toward(from_pt, along, female)  # same direction as the tab - pocket also reaches into female
        for t in ts:
            point = (from_pt[0] + t * (to_pt[0] - from_pt[0]), from_pt[1] + t * (to_pt[1] - from_pt[1]))
            pockets.append(build_dovetail_tab(point, along, perp, TAB_BASE_HALF_WIDTH + c, TAB_TIP_HALF_WIDTH + c,
                                               TAB_REACH + c, OVERSHOOT, f"pocket_{jname}_{t:g}"))
    return join_objects(pockets, f"joint_pockets_{tile_name}") if pockets else None


# ============================================================
# FDM STRUCTURAL SLAB: plain tile + underside steel rebate + through-holes
# + seam joints (dovetail tabs where this tile is the "male" side of a cut,
# matching pockets where it's the "female" side - v7's 3 wedges mean a
# single tile can be male on one cut and female on another)
# ============================================================
def build_fdm_slab(tile_def):
    outline = tile_def["outline"]
    slab = build_slab(outline, 0.0, FDM_THICKNESS, tile_def["name"] + "_fdm")

    rx0, rx1, ry0, ry1 = inset_rect(outline, STEEL_REBATE_MARGIN)
    rebate = add_box_range((rx0, rx1), (ry0, ry1), (-OVERSHOOT, STEEL_SHEET_THICKNESS))
    apply_boolean(slab, rebate, 'DIFFERENCE')

    straddling = sockets_straddling_into(tile_def["name"])
    cut_sockets = tile_def["sockets"] + straddling
    if straddling:
        print(f"  {tile_def['name']}: +{len(straddling)} straddling socket(s) "
              f"cut here too: {[s[0] for s in straddling]}")
    if cut_sockets:
        cutters = [add_cylinder(d + SOCKET_GROWTH, (-OVERSHOOT, FDM_THICKNESS + OVERSHOOT), (cx, cy))
                   for _, cx, cy, d in cut_sockets]
        apply_boolean(slab, join_objects(cutters, "fdm_hole_cutters"), 'DIFFERENCE')

    tabs = build_seam_joint_tabs_for_tile(tile_def["name"])
    if tabs:
        apply_boolean(slab, tabs, 'UNION')
    pockets = build_seam_joint_pockets_for_tile(tile_def["name"])
    if pockets:
        apply_boolean(slab, pockets, 'DIFFERENCE')

    return slab


# ============================================================
# RESIN DETAIL SKIN: thin slab + grooves + grate + rivets, THEN topper
# capture, THEN through-holes cut last
# ============================================================
def build_vertical_groove_cutters(bbox):
    x0, x1, y0, y1 = bbox
    cutters = [add_box_range((gx - GROOVE_WIDTH / 2, gx + GROOVE_WIDTH / 2),
                              (y0 - OVERSHOOT, y1 + OVERSHOOT),
                              (RESIN_THICKNESS - GROOVE_DEPTH, RESIN_THICKNESS + OVERSHOOT))
               for gx in VERTICAL_SEAM_X if x0 < gx < x1]
    return join_objects(cutters, "vgroove_cutters") if cutters else None


def build_horizontal_groove_cutters(bbox):
    x0, x1, y0, y1 = bbox
    cutters = [add_box_range((x0 - OVERSHOOT, x1 + OVERSHOOT),
                              (gy - GROOVE_WIDTH / 2, gy + GROOVE_WIDTH / 2),
                              (RESIN_THICKNESS - GROOVE_DEPTH, RESIN_THICKNESS + OVERSHOOT))
               for gy in HORIZONTAL_SEAM_Y if y0 < gy < y1]
    return join_objects(cutters, "hgroove_cutters") if cutters else None


def build_grate_cutters(rect):
    x0, x1, y0, y1 = rect
    pitch = (x1 - x0) / GRATE_SLOTS
    cutters = [add_box_range((x0 + pitch * (i + 0.5) - GRATE_SLOT_WIDTH / 2,
                               x0 + pitch * (i + 0.5) + GRATE_SLOT_WIDTH / 2),
                              (y0, y1),
                              (RESIN_THICKNESS - GRATE_DEPTH, RESIN_THICKNESS + OVERSHOOT))
               for i in range(GRATE_SLOTS)]
    return join_objects(cutters, "grate_cutters")


def build_rivet_studs(bbox):
    x0, x1, y0, y1 = bbox
    studs = [add_cylinder(RIVET_DIAMETER, (RESIN_THICKNESS - RIVET_EMBED, RESIN_THICKNESS + RIVET_HEIGHT),
                           (gx, gy), vertices=12)
             for gx in VERTICAL_SEAM_X if x0 < gx < x1
             for gy in HORIZONTAL_SEAM_Y if y0 < gy < y1]
    return join_objects(studs, "rivets") if studs else None


def cut_channels(skin, bbox):
    """Each channel segment is its OWN separate DIFFERENCE pass, NOT
    combined into one cutter object first - several segments share an
    endpoint (an elbow), so their boxes overlap each other there. Joining
    overlapping shapes into one cutter before a single boolean is exactly
    the self-intersecting-cutter case from [[feedback_blender_boolean_
    fragility]] - it corrupted the whole skin down to ~2mm3 on first run,
    caught by the volume sanity print, not by eye. A short chain of
    separate passes (one per segment) is the safe fix."""
    x0b, x1b, y0b, y1b = bbox
    for cx0, cy0, cx1, cy1 in MOLTEN_CHANNELS:
        if not (x0b <= cx0 <= x1b and x0b <= cx1 <= x1b and y0b <= cy0 <= y1b and y0b <= cy1 <= y1b):
            continue
        if cx0 == cx1:   # vertical run
            cutter = add_box_range(
                (cx0 - CHANNEL_WIDTH / 2, cx0 + CHANNEL_WIDTH / 2), (min(cy0, cy1), max(cy0, cy1)),
                (RESIN_THICKNESS - CHANNEL_DEPTH, RESIN_THICKNESS + OVERSHOOT))
        else:             # horizontal run
            cutter = add_box_range(
                (min(cx0, cx1), max(cx0, cx1)), (cy0 - CHANNEL_WIDTH / 2, cy0 + CHANNEL_WIDTH / 2),
                (RESIN_THICKNESS - CHANNEL_DEPTH, RESIN_THICKNESS + OVERSHOOT))
        apply_boolean(skin, cutter, 'DIFFERENCE')


def add_channel_flow(skin, bbox):
    """A raised bead inside each already-cut trench - "something running in
    the channel". Must run AFTER cut_channels (the bead sits inside the
    trench, not under material that's about to be removed). Same elbow
    lesson applied proactively this time, not discovered again: each
    segment is its own separate UNION pass, never combined with the others
    first - several segments share an endpoint, and joining overlapping
    shapes into one cutter/union object before a single boolean is exactly
    what corrupted the trench cuts earlier in this session."""
    x0b, x1b, y0b, y1b = bbox
    trench_floor = RESIN_THICKNESS - CHANNEL_DEPTH
    z_range = (trench_floor - FLOW_EMBED, trench_floor + FLOW_HEIGHT)
    for cx0, cy0, cx1, cy1 in MOLTEN_CHANNELS:
        if not (x0b <= cx0 <= x1b and x0b <= cx1 <= x1b and y0b <= cy0 <= y1b and y0b <= cy1 <= y1b):
            continue
        if cx0 == cx1:   # vertical run
            bead = add_box_range(
                (cx0 - FLOW_WIDTH / 2, cx0 + FLOW_WIDTH / 2), (min(cy0, cy1), max(cy0, cy1)), z_range)
        else:             # horizontal run
            bead = add_box_range(
                (min(cx0, cx1), max(cx0, cx1)), (cy0 - FLOW_WIDTH / 2, cy0 + FLOW_WIDTH / 2), z_range)
        apply_boolean(skin, bead, 'UNION')


# ============================================================
# SMELTING POOL - a shallow basin around the Roaring Furnace socket (see
# POOL_OUTLINE above), with a few raised veins reading as molten metal
# creeping toward the channels. Cut BEFORE the channels/paving that share
# its footprint, same reasoning as the channel-elbow lesson: separate
# passes, nothing pre-joined.
# ============================================================
def build_pool_cutter():
    z_range = (RESIN_THICKNESS - POOL_DEPTH, RESIN_THICKNESS + OVERSHOOT)
    return build_slab(POOL_OUTLINE, z_range[0], z_range[1], "pool_cutter")


def build_pool_veins():
    trench_floor = RESIN_THICKNESS - POOL_DEPTH
    z_range = (trench_floor - POOL_VEIN_EMBED, trench_floor + POOL_VEIN_HEIGHT)
    px, py = POOL_CENTER
    veins = []
    for i in range(POOL_VEIN_COUNT):
        ang_deg = i * 360.0 / POOL_VEIN_COUNT + 20.0   # offset from the channel angles - no duplicate overlap
        ang = math.radians(ang_deg)
        ux, uy = math.cos(ang), math.sin(ang)
        outer_r = pool_safe_radius(ang_deg) * POOL_VEIN_REACH_FRAC
        p0 = (px + POOL_INNER_RADIUS * ux, py + POOL_INNER_RADIUS * uy)
        p1 = (px + outer_r * ux, py + outer_r * uy)
        veins.append(build_angled_box(p0, p1, POOL_VEIN_WIDTH, z_range, pad=POOL_VEIN_WIDTH))
    return veins


# ============================================================
# STONE-TILE PAVING - a square groove outline (4 separate edges, each
# stopped short of the corners so they never touch/overlap each other -
# same lesson as the channel elbow bug) plus an inset circle groove.
# ============================================================
def _shrink_segment(p0, p1, gap):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = (dx ** 2 + dy ** 2) ** 0.5
    t = gap / length
    return (p0[0] + dx * t, p0[1] + dy * t), (p1[0] - dx * t, p1[1] - dy * t)


def cut_paving_square_circle(skin, cx, cy):
    half = PAVING_CELL_SIZE / 2
    inner = half - PAVING_CORNER_GAP
    z_range = (RESIN_THICKNESS - PAVING_LINE_DEPTH, RESIN_THICKNESS + OVERSHOOT)
    # top and bottom edges (horizontal, stopped short of both corners)
    for ey in (cy - half, cy + half):
        cutter = add_box_range((cx - inner, cx + inner),
                                (ey - PAVING_LINE_WIDTH / 2, ey + PAVING_LINE_WIDTH / 2), z_range)
        apply_boolean(skin, cutter, 'DIFFERENCE')
    # left and right edges (vertical)
    for ex in (cx - half, cx + half):
        cutter = add_box_range((ex - PAVING_LINE_WIDTH / 2, ex + PAVING_LINE_WIDTH / 2),
                                (cy - inner, cy + inner), z_range)
        apply_boolean(skin, cutter, 'DIFFERENCE')
    apply_boolean(skin, add_cylinder(PAVING_CIRCLE_DIA, z_range, (cx, cy)), 'DIFFERENCE')


def cut_paving_diamond(skin, cx, cy):
    """Same square outline rotated 45 degrees (a diamond), plus the same
    inset circle - reads as a distinct flagstone variant next to the plain
    square-circle cells without needing a whole new motif."""
    half = PAVING_CELL_SIZE / 2
    z_range = (RESIN_THICKNESS - PAVING_LINE_DEPTH, RESIN_THICKNESS + OVERSHOOT)
    diamond_pts = [(cx, cy - half), (cx + half, cy), (cx, cy + half), (cx - half, cy)]
    for i in range(4):
        p0, p1 = _shrink_segment(diamond_pts[i], diamond_pts[(i + 1) % 4], PAVING_CORNER_GAP)
        apply_boolean(skin, build_angled_box(p0, p1, PAVING_LINE_WIDTH, z_range), 'DIFFERENCE')
    apply_boolean(skin, add_cylinder(PAVING_CIRCLE_DIA, z_range, (cx, cy)), 'DIFFERENCE')


def cut_paving_hatch(skin, cx, cy):
    """Plain X - the two diagonals cross at the cell center (a shared
    endpoint, same as the channel elbows), so each is its own separate
    DIFFERENCE pass rather than being joined into one cutter first."""
    half = PAVING_CELL_SIZE / 2 - PAVING_CORNER_GAP
    z_range = (RESIN_THICKNESS - PAVING_LINE_DEPTH, RESIN_THICKNESS + OVERSHOOT)
    for p0, p1 in [((cx - half, cy - half), (cx + half, cy + half)),
                   ((cx - half, cy + half), (cx + half, cy - half))]:
        apply_boolean(skin, build_angled_box(p0, p1, PAVING_LINE_WIDTH, z_range), 'DIFFERENCE')


PAVING_PATTERN_BUILDERS = {
    "square_circle": cut_paving_square_circle,
    "diamond": cut_paving_diamond,
    "hatch": cut_paving_hatch,
}
assert set(PAVING_PATTERN_BUILDERS) == set(PAVING_PATTERNS), \
    "PAVING_PATTERNS in forge_floor_data.py no longer matches the builders defined here"


def cut_paving(skin, bbox):
    x0b, x1b, y0b, y1b = bbox
    for cx, cy in PAVING_CELLS:
        if x0b <= cx <= x1b and y0b <= cy <= y1b:
            PAVING_PATTERN_BUILDERS[paving_pattern_for(cx, cy)](skin, cx, cy)


# ============================================================
# HAND-TOOL PROPS - built at local origin (hammer: handle base; tongs:
# pivot), then rotated and placed. Each one's own union chain stays short
# and each PROP is unioned onto the skin as its own separate pass.
# ============================================================
PROP_EMBED = 0.4       # how far the prop sinks into the skin, for a clean union
PROP_RELIEF = 1.2      # how far the prop stands proud of the skin's top face

HAMMER_HANDLE_LEN = 10.0
HAMMER_HANDLE_HALF_W = 0.75
HAMMER_HEAD_LEN = 4.0
HAMMER_HEAD_HALF_W = 2.5


def build_hammer_prop(cx, cy, rot_deg):
    hw, hhw = HAMMER_HANDLE_HALF_W, HAMMER_HEAD_HALF_W
    hl, hd = HAMMER_HANDLE_LEN, HAMMER_HEAD_LEN
    outline = [
        (-hw, 0.0), (hw, 0.0), (hw, hl),
        (hhw, hl), (hhw, hl + hd), (-hhw, hl + hd),
        (-hhw, hl), (-hw, hl),
    ]
    obj = build_slab(outline, 0.0, PROP_EMBED + PROP_RELIEF, "hammer_prop")
    obj.location = (cx, cy, RESIN_THICKNESS - PROP_EMBED)
    obj.rotation_euler = (0.0, 0.0, math.radians(rot_deg))
    return obj


TONGS_ARM_LEN = 9.0
TONGS_ARM_HALF_W = 0.6
TONGS_SPREAD_DEG = 16.0
TONGS_PIVOT_RADIUS = 1.3
TONGS_ARM_EMBED = 0.4   # each arm's own overlap into the pivot (unrelated to PROP_EMBED)


def _tongs_arm(angle_deg, z_thickness):
    length = TONGS_ARM_LEN + TONGS_ARM_EMBED
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.0, length / 2 - TONGS_ARM_EMBED, z_thickness / 2))
    obj = bpy.context.active_object
    obj.scale = (TONGS_ARM_HALF_W * 2, length, z_thickness)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=True)
    obj.rotation_euler = (0.0, 0.0, math.radians(angle_deg))
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    return obj


def build_tongs_prop(cx, cy, rot_deg):
    z_thickness = PROP_EMBED + PROP_RELIEF
    bpy.ops.mesh.primitive_cylinder_add(radius=TONGS_PIVOT_RADIUS, depth=z_thickness,
                                         location=(0.0, 0.0, z_thickness / 2), vertices=16)
    pivot = bpy.context.active_object
    pivot.name = "tongs_prop"
    apply_boolean(pivot, _tongs_arm(-TONGS_SPREAD_DEG, z_thickness), 'UNION')
    apply_boolean(pivot, _tongs_arm(TONGS_SPREAD_DEG, z_thickness), 'UNION')
    pivot.location = (cx, cy, RESIN_THICKNESS - PROP_EMBED)
    pivot.rotation_euler = (0.0, 0.0, math.radians(rot_deg))
    return pivot


ANVIL_BODY_HALF_W = 2.0
ANVIL_BODY_LEN = 7.0
ANVIL_HORN_LEN = 5.0
ANVIL_HORN_TIP_HALF_W = 0.5


def build_anvil_prop(cx, cy, rot_deg):
    bw, bl = ANVIL_BODY_HALF_W, ANVIL_BODY_LEN
    hl, htw = ANVIL_HORN_LEN, ANVIL_HORN_TIP_HALF_W
    outline = [
        (-bw, 0.0), (bw, 0.0), (bw, bl),
        (htw, bl + hl), (-htw, bl + hl), (-bw, bl),
    ]
    obj = build_slab(outline, 0.0, PROP_EMBED + PROP_RELIEF, "anvil_prop")
    obj.location = (cx, cy, RESIN_THICKNESS - PROP_EMBED)
    obj.rotation_euler = (0.0, 0.0, math.radians(rot_deg))
    return obj


INGOT_LEN = 3.0
INGOT_WIDE = 1.6
INGOT_HEIGHT = 1.0
INGOT_COUNT = 3
INGOT_STEP = 0.7   # each ingot in the stack sits slightly offset from the one below


def build_ingot_pile_prop(cx, cy, rot_deg):
    parts = []
    for i in range(INGOT_COUNT):
        z0 = i * INGOT_HEIGHT * 0.85
        offset = (i % 2) * INGOT_STEP
        obj = add_box_range((-INGOT_LEN / 2 + offset, INGOT_LEN / 2 + offset),
                             (-INGOT_WIDE / 2, INGOT_WIDE / 2), (z0, z0 + INGOT_HEIGHT))
        parts.append(obj)
    pile = join_objects(parts, "ingot_pile_prop")
    pile.location = (cx, cy, RESIN_THICKNESS - PROP_EMBED)
    pile.rotation_euler = (0.0, 0.0, math.radians(rot_deg))
    return pile


CHISEL_LEN = 8.0
CHISEL_HALF_W = 0.5
CHISEL_TIP_HALF_W = 0.9
CHISEL_TIP_LEN = 1.5


def build_chisel_prop(cx, cy, rot_deg):
    hw, tw, tl = CHISEL_HALF_W, CHISEL_TIP_HALF_W, CHISEL_TIP_LEN
    outline = [
        (-hw, 0.0), (hw, 0.0), (hw, CHISEL_LEN - tl),
        (tw, CHISEL_LEN), (-tw, CHISEL_LEN), (-hw, CHISEL_LEN - tl),
    ]
    obj = build_slab(outline, 0.0, PROP_EMBED + PROP_RELIEF, "chisel_prop")
    obj.location = (cx, cy, RESIN_THICKNESS - PROP_EMBED)
    obj.rotation_euler = (0.0, 0.0, math.radians(rot_deg))
    return obj


PROP_BUILDERS = {
    "hammer": build_hammer_prop,
    "tongs": build_tongs_prop,
    "anvil": build_anvil_prop,
    "ingot_pile": build_ingot_pile_prop,
    "chisel": build_chisel_prop,
}


def build_props(skin, bbox):
    x0b, x1b, y0b, y1b = bbox
    for name, cx, cy, rot_deg, _radius in PROP_PLACEMENTS:
        if x0b <= cx <= x1b and y0b <= cy <= y1b:
            prop_obj = PROP_BUILDERS[name](cx, cy, rot_deg)
            apply_boolean(skin, prop_obj, 'UNION')


def build_resin_terrain(outline, name, grate=None):
    """Stage 1 of the resin workflow: the fully-decorated skin (grooves,
    grate, channels + flow, paving, props) as ONE piece over `outline` -
    no socket holes cut yet, no toppers captured yet. Meant to be built,
    rendered, and reviewed BEFORE stamping anything out of it - the layout
    and terrain details are the thing to get right first; toppers/holes
    are a mechanical stamping step on top of an already-approved surface,
    not bundled into the same pass."""
    bbox = (min(p[0] for p in outline), max(p[0] for p in outline),
            min(p[1] for p in outline), max(p[1] for p in outline))

    skin = build_slab(outline, 0.0, RESIN_THICKNESS, name)

    vgrooves = build_vertical_groove_cutters(bbox)
    if vgrooves:
        apply_boolean(skin, vgrooves, 'DIFFERENCE')
    hgrooves = build_horizontal_groove_cutters(bbox)
    if hgrooves:
        apply_boolean(skin, hgrooves, 'DIFFERENCE')
    if grate:
        apply_boolean(skin, build_grate_cutters(grate), 'DIFFERENCE')
    apply_boolean(skin, build_pool_cutter(), 'DIFFERENCE')
    for vein in build_pool_veins():
        apply_boolean(skin, vein, 'UNION')
    cut_channels(skin, bbox)
    add_channel_flow(skin, bbox)
    cut_paving(skin, bbox)
    rivets = build_rivet_studs(bbox)
    if rivets:
        apply_boolean(skin, rivets, 'UNION')
    build_props(skin, bbox)

    fx, fy = POOL_CENTER
    if bbox[0] <= fx <= bbox[1] and bbox[2] <= fy <= bbox[3]:
        apply_boolean(skin, import_furnace_body(), 'UNION')

    return skin


def import_furnace_body():
    """The Roaring Furnace's real body - v11: fused into the resin terrain
    (UNION) same as v10, but the correction this round is that it's STILL
    one of the 15 sockets (back in ALL_SOCKETS, moved near the wedge apex
    so it spans all 3 FDM tiles). It gets a real FDM hole, a real resin
    hole, and a real topper - stamp_toppers_and_holes() just uses a TALLER
    cutter at this one socket's position, so the topper captures the whole
    fused kettle body (not a shaved-off 1.2mm disc) and the hole removes
    all of it from the master, not just its base. Tested the union in
    isolation first (178k triangles is a lot to trust blind, per
    [[feedback_blender_boolean_fragility]]): a plain slab+furnace union ran
    in <1s, volume landed exactly on slab+furnace with no corruption, only
    a handful of non-manifold verts (typical for a complex third-party
    mesh, not a sign of a failed boolean). CC BY-NC, 'ecaroth' on
    Thingiverse (https://www.thingiverse.com/thing:2860871).

    NOTE the physical consequence: the captured topper (decoration + a
    62.7mm-tall body) can't print flat/no-supports like the other toppers
    - it needs to go in upright, supported, same as any tall mini. That's
    a real tradeoff of fusing it in, not an oversight."""
    bpy.ops.wm.stl_import(filepath=FURNACE_STL_PATH)
    obj = bpy.context.selected_objects[-1]
    obj.name = "furnace_body"
    # the STL's own local origin isn't centered on its footprint - recenter
    # first, or a plain translate to the socket lands the wrong point
    xs = [c[0] for c in obj.bound_box]
    ys = [c[1] for c in obj.bound_box]
    local_cx = (min(xs) + max(xs)) / 2
    local_cy = (min(ys) + max(ys)) / 2
    fx, fy = POOL_CENTER
    obj.location = (fx - local_cx, fy - local_cy, RESIN_THICKNESS)
    return obj


def split_into_quadrants(skin):
    """Cut the finished, already-holed master terrain into 4 rectangular
    quadrants via INTERSECT (same proven pattern as topper capture) - the
    resin skin is thin decoration glued onto a continuous FDM slab below,
    so unlike the FDM tiles it needs no structural dovetail joints of its
    own; a plain butt seam is enough once it's glued down. Each quadrant is
    140x130mm, comfortably inside the 165x143mm resin bed printed flat.
    (The furnace itself never reaches this step - see stamp_toppers_and_
    holes - it's fully captured into its own topper before the master gets
    split, so there's no tall geometry left for a quadrant box to clip.)"""
    z_top = RESIN_THICKNESS + FURNACE_HEIGHT + OVERSHOOT   # margin of safety, not load-bearing here anymore
    pieces = []
    for name, xr, yr in RESIN_QUADRANTS:
        dup = duplicate_object(skin, f"resin_{name}")
        box = add_box_range((xr[0] - OVERSHOOT, xr[1] + OVERSHOOT),
                             (yr[0] - OVERSHOOT, yr[1] + OVERSHOOT),
                             (-OVERSHOOT, z_top))
        apply_boolean(dup, box, 'INTERSECT')
        pieces.append((name, dup))
    return pieces


def _topper_cutter_z_range(socket_name):
    """Every socket's topper/hole cutter is a short cylinder matching the
    resin skin's own thickness - except the Furnace, which has the real
    62.7mm-tall body fused onto it. A short cutter there would only grab
    the flat base of the fusion (a shaved-off disc) for the topper, and
    only remove that same shallow disc from the master - leaving the tall
    body still fused onto the master's hole rim. Caught by reasoning about
    it before running, not by a bad export - same lesson as the quadrant
    -split Z-clipping bug this round."""
    if socket_name == FURNACE_NAME:
        return (-OVERSHOOT, RESIN_THICKNESS + FURNACE_HEIGHT + OVERSHOOT)
    return (-OVERSHOOT, RESIN_THICKNESS + OVERSHOOT)


def stamp_toppers_and_holes(skin, sockets):
    """Stage 2: run ONLY after the terrain skin from build_resin_terrain has
    been reviewed and approved. Captures each socket's plug as its own
    topper STL (base diameter + SOCKET_GROWTH margin, matching the FDM
    slab's hole size exactly - same ALL_SOCKETS data drives both, so the
    two layers' holes line up by construction, not by coincidence), then
    cuts the real holes into the skin."""
    toppers = []
    for socket_name, cx, cy, d in sockets:
        dup = duplicate_object(skin, "topper_tmp")
        cutter = add_cylinder(d + SOCKET_GROWTH, _topper_cutter_z_range(socket_name), (cx, cy))
        apply_boolean(dup, cutter, 'INTERSECT')
        dup.name = f"topper_{socket_name}"
        toppers.append((socket_name, dup))

    if sockets:
        hole_cutters = [add_cylinder(d + SOCKET_GROWTH, _topper_cutter_z_range(name), (cx, cy))
                        for name, cx, cy, d in sockets]
        apply_boolean(skin, join_objects(hole_cutters, "resin_hole_cutters"), 'DIFFERENCE')

    return toppers


# ============================================================
# MAIN
# ============================================================
def safe_filename(name):
    return name.lower().replace(" ", "_")


# v9 workflow: resin is no longer tiled/wedge-cut at all. Each base topper
# ends up as its own small independent STL (even the 100mm ones fit the
# resin bed rotated diagonally), so there's no need to cut a large
# connected resin sheet into printable pieces the way the FDM slab needs -
# except the "background" master terrain itself (everything minus the
# toppers) is still one big connected sheet once the holes are cut, and
# that one DOES need splitting: 280x260mm is far bigger than the resin
# bed. Explicit stages, matching the requested "review before stamping"
# workflow:
#   "review" - build the WHOLE floor's terrain (grooves, grate, pool,
#              channels, paving, props) as ONE piece, render it, export it,
#              STOP. No socket holes cut, no toppers captured yet - the
#              surface is the thing to get right and approve first.
#   "stamp"  - re-run the same terrain build, cut every socket hole,
#              capture every topper as its own STL, THEN split the
#              now-holed master into 4 quadrants (each within the resin
#              bed) for printing.
BUILD_RESIN = True
RESIN_STAGE = "stamp"   # "review" | "stamp"

MASTER_OUTLINE = [(0.0, 0.0), (FLOOR_W, 0.0), (FLOOR_W, FLOOR_D), (0.0, FLOOR_D)]


def build_fdm_tiles():
    for tile_def in TILES:
        clear_scene()
        fdm = build_fdm_slab(tile_def)
        print(f"{tile_def['name']}: fdm volume={mesh_volume(fdm):.0f}mm3, {len(tile_def['sockets'])} sockets")
        if EXPORT_STL:
            export_stl(fdm, f"{tile_def['name']}_fdm.stl")
        if RENDER_IMAGES:
            render_iso(tile_def["name"], [fdm])


def build_resin_master():
    clear_scene()
    skin = build_resin_terrain(MASTER_OUTLINE, "forge_floor_master_resin", grate=GRATE_RECT)
    print(f"master resin terrain: volume={mesh_volume(skin):.0f}mm3 "
          f"({RESIN_STAGE} stage - {len(ALL_SOCKETS)} sockets not yet cut, furnace body already fused in)")
    if EXPORT_STL:
        export_stl(skin, "forge_floor_master_resin.stl")
    if RENDER_IMAGES:
        render_iso("forge_floor_master_resin", [skin])
    return skin


def main():
    build_fdm_tiles()

    if BUILD_RESIN:
        skin = build_resin_master()
        if RESIN_STAGE == "stamp":
            toppers = stamp_toppers_and_holes(skin, ALL_SOCKETS)
            print(f"stamped {len(toppers)} toppers, cut holes into the master skin")
            if EXPORT_STL:
                for socket_name, topper in toppers:
                    export_stl(topper, f"topper_{safe_filename(socket_name)}.stl")

            quadrants = split_into_quadrants(skin)
            for name, piece in quadrants:
                print(f"resin quadrant {name}: volume={mesh_volume(piece):.0f}mm3")
                if EXPORT_STL:
                    export_stl(piece, f"forge_floor_resin_{name}.stl")
            if RENDER_IMAGES:
                render_iso("forge_floor_resin_quadrants", [p for _, p in quadrants])

    print("Done.")


if __name__ == "__main__":
    main()
