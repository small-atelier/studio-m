"""
Objective Marker Tiles v1 - a thin paved-tile disc with a blind pocket for
a 40mm objective marker (2mm thick). Disc radius = marker radius + 3"
control range, measured from the marker's edge (192.4mm outer diameter).
Tiles are irregular wedge segments in concentric rings, staggered
ring-to-ring, built as plain mesh prisms (no per-tile booleans) and
joined into one object before a single boolean union onto the floor
plate - see feedback_blender_boolean_fragility memory.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python objective_markers_v1.py

Run with a different pattern seed / skip renders / add the Mythos logo
engraved on the underside (skip it on a copy meant to be glued down flat):
  /Applications/Blender.app/Contents/MacOS/Blender --background --python objective_markers_v1.py -- --seed 7 --no-render --logo

Override the outer diameter (inches) to match an objective ring printed on a
board instead of the 3" control range - e.g. the Spearhead boards' 5/6/7"
rings. Output names get a size suffix (objective_1_6in.stl):
  /Applications/Blender.app/Contents/MacOS/Blender --background --python objective_markers_v1.py -- --diameter 6

Cut the disc straight off at a board edge, N mm from the centre, for an
objective printed partly off the board (Spearhead Ghryan's side objectives).
Output names get an "_edge" suffix:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python objective_markers_v1.py -- --diameter 6 --edge-cut 21
"""

import bpy
import bmesh
import json
import math
import mathutils
import os
import sys
import random
import zipfile

# ============================================================
# CLI ARGS
# ============================================================
def _parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    seed, render, logo, diameter_in, edge_cut = 1, True, False, None, None
    i = 0
    while i < len(argv):
        if argv[i] == "--seed":
            seed = int(argv[i + 1]); i += 2
        elif argv[i] == "--no-render":
            render = False; i += 1
        elif argv[i] == "--logo":
            logo = True; i += 1
        elif argv[i] == "--diameter":
            diameter_in = float(argv[i + 1]); i += 2
        elif argv[i] == "--edge-cut":
            edge_cut = float(argv[i + 1]); i += 2
        else:
            i += 1
    return seed, render, logo, diameter_in, edge_cut


SEED, RENDER_IMAGES, ADD_LOGO, DIAMETER_IN, EDGE_CUT = _parse_args()

# ============================================================
# CONFIG (all mm)
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(SCRIPT_DIR, "output")
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1400, 1400)
EXPORT_STL = True
EXPORT_3MF = True   # Anycubic Slicer Next project file, alongside the STL

MARKER_DIAM      = 40.0
MARKER_THICKNESS = 2.0
POCKET_CLEARANCE = 0.2     # radial slip-fit clearance

CONTROL_RANGE_IN     = 3.0   # tile disc extends this far beyond the marker's edge (unless --diameter)
FLOOR_THICKNESS_POCKET = 1.0 # floor under the marker pocket - kept thin, small span
FLOOR_THICKNESS_RING   = 1.5 # floor under the paved ring - thicker, it's the big warp-risk span
TILE_HEIGHT          = 1.5   # tile height added on top of the ring floor - matches pocket top (see RECESS_MM)
EMBED                = 0.5   # overlap depth for every boolean union (tiles onto floor, floor step)

GROUT_GAP        = 0.8     # gap between tiles, both radial and angular (mm)
BEVEL_WIDTH      = 0.2     # softens each tile's top edge - worn-paver look
HEIGHT_JITTER    = 0.15    # per-tile random height offset - hand-laid look
BUMP_AMOUNT      = 0.15    # per-tile center dome/dish amplitude - worn stone surface

RING_WIDTH_MIN   = 10.0
RING_WIDTH_MAX   = 20.0
WEDGE_ANGLE_MIN  = 20.0    # degrees
WEDGE_ANGLE_MAX  = 40.0

# Mythos logo, engraved into the underside only (--logo) - same traced
# contours + font as the dice tray/combat-modifier/card-stand pieces, no
# re-tracing. Bottom-only because a glued-down copy shouldn't carry one.
MYTHOS_CONTOURS_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "card-stand", "logo_contours_v5.json"))
MYTHOS_ASPECT    = 376.0 / 720.0  # h/w, 720x720 source - width is the controlling dimension
MYTHOS_FONT_PATH = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "card-stand", "BaskervilleBold.ttf"))
LOGO_TEXT        = "MYTHOS"
TEXT_SPACING     = 1.1     # see feedback_blender_boolean_fragility memory - touching glyphs at
                            # small sizes corrupt the EXACT solver on FONT-curve conversion
GAP_FRAC         = 0.15    # gap between icon and text, as a fraction of the icon's own height
LOGO_ICON_W      = 110.0   # icon width in mm - text below is sized to the same width
ENGRAVE_DEPTH    = 0.4     # shallow - stays well inside the 1.0mm pocket floor, the thinnest span
CUT_POKE         = 0.3     # cutter overshoot below z=0 for a clean boolean cut
BASE_EXTRUDER_SLOT = 1     # material slots for the .3mf - same convention as the
LOGO_EXTRUDER_SLOT = 2     # dice tray/combat-modifier/token multi-material pieces
BASE_COLOR = (1.0, 1.0, 1.0, 1.0)     # preview-only colors so a flush insert is
LOGO_COLOR = (0.06, 0.45, 0.12, 1.0)  # actually visible in the render, not just the print

# ============================================================
# DERIVED
# ============================================================
def inches_to_mm(v):
    return v * 25.4

MARKER_RADIUS = MARKER_DIAM / 2
POCKET_RADIUS = MARKER_RADIUS + POCKET_CLEARANCE
CONTROL_RANGE_RADIUS = MARKER_RADIUS + inches_to_mm(CONTROL_RANGE_IN)
OUTER_RADIUS  = inches_to_mm(DIAMETER_IN) / 2 if DIAMETER_IN else CONTROL_RANGE_RADIUS
SIZE_SUFFIX   = (f"_{DIAMETER_IN:g}in".replace(".", "_") if DIAMETER_IN else "") + ("_edge" if EDGE_CUT else "")

# board-sized pieces get glued down onto the board, so the underside logo is
# for the free-standing control-range disc only
if ADD_LOGO and (DIAMETER_IN or EDGE_CUT):
    raise SystemExit("--logo is for the control-range disc only, not with --diameter/--edge-cut")
RING_TOP_Z    = FLOOR_THICKNESS_RING + TILE_HEIGHT           # top of the paved area
POCKET_TOP_Z  = FLOOR_THICKNESS_POCKET + MARKER_THICKNESS    # top of the marker once seated
RECESS_MM     = RING_TOP_Z - POCKET_TOP_Z                    # how far the marker sits below the tile tops

# ============================================================
# UTILITIES
# ============================================================
def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for block_list in (bpy.data.meshes, bpy.data.cameras, bpy.data.lights):
        for block in list(block_list):
            if block.users == 0:
                block_list.remove(block)


def new_object_from_bmesh(bm, name):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def mesh_volume(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    volume = bm.calc_volume()
    bm.free()
    return volume


def nonmanifold_fraction(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bad = sum(1 for e in bm.edges if not e.is_manifold)
    total = len(bm.edges)
    bm.free()
    return bad / total if total else 0.0

# ============================================================
# GEOMETRY
# ============================================================
def make_wedge_tile(r_in, r_out, a_start_deg, a_end_deg, z_base, height, name, bump=0.0):
    """A single paving tile: a ring-sector prism built directly as a mesh
    (fan of verts along the outer arc, back along the inner arc, extruded
    up) - no booleans, so it can never corrupt or chain. `bump` pokes the
    top face and nudges the new center vertex up/down for a worn-stone
    dome/dish - the perimeter (and the later bevel) stays untouched since
    poke never splits the boundary edges, only fans new ones off it."""
    span = a_end_deg - a_start_deg
    segments = max(2, int(span / 8) + 1)
    angles = [math.radians(a_start_deg + span * i / segments) for i in range(segments + 1)]

    outer_pts = [(r_out * math.cos(a), r_out * math.sin(a)) for a in angles]
    inner_pts = [(r_in * math.cos(a), r_in * math.sin(a)) for a in reversed(angles)]
    loop = outer_pts + inner_pts

    bm = bmesh.new()
    verts = [bm.verts.new((x, y, z_base)) for x, y in loop]
    bm.verts.ensure_lookup_table()
    face = bm.faces.new(verts)
    face.normal_update()
    if face.normal.z > 0:
        face.normal_flip()

    ret = bmesh.ops.extrude_face_region(bm, geom=[face])
    new_verts = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=new_verts, vec=(0, 0, height))

    top_z = z_base + height
    top_face = next(
        g for g in ret["geom"]
        if isinstance(g, bmesh.types.BMFace) and all(abs(v.co.z - top_z) < 1e-6 for v in g.verts)
    )
    boundary_edges = list(top_face.edges)

    if bump:
        poke = bmesh.ops.poke(bm, faces=[top_face])
        poke["verts"][0].co.z += bump

    bmesh.ops.bevel(bm, geom=boundary_edges, offset=BEVEL_WIDTH,
                     offset_type='OFFSET', segments=2, profile=0.5, affect='EDGES')

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return new_object_from_bmesh(bm, name)

# ============================================================
# MYTHOS LOGO (bottom only) - ported from blender/dice-tower/build_dice_tray.py,
# same traced-contour + font technique, ONE engraved pocket instead of that
# project's two multi-material ones - this is a single-material print.
# ============================================================
def dedupe_closed_loop(points, tol=1e-9):
    """Traced contours (skimage find_contours) can come back as closed rings
    with the first and last point identical - a degenerate zero-length edge
    that corrupts the extruded solid's topology if left in."""
    if len(points) > 1:
        x0, y0 = points[0]
        x1, y1 = points[-1]
        if abs(x0 - x1) < tol and abs(y0 - y1) < tol:
            return points[:-1]
    return points


def load_contours(path):
    with open(path) as f:
        return json.load(f)


def _extrude_profile_xy(points, z0, thickness, name):
    bm = bmesh.new()
    verts = [bm.verts.new((p[0], p[1], z0)) for p in points]
    face = bm.faces.new(verts)
    ret = bmesh.ops.extrude_face_region(bm, geom=[face])
    new_verts = [v for v in ret["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0.0, 0.0, thickness), verts=new_verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    return new_object_from_bmesh(bm, name)


def build_mythos_prism(contours, icon_w, icon_h, local_y, z0, thickness, name_prefix):
    """Built at local X=0, local Y=local_y - mirror/placement happens later,
    once icon and text are both built, so they stay in registration."""
    outer_pts, hole_pts = [], []
    for c in contours:
        pts = [(u * icon_w - icon_w / 2.0, v * icon_h - icon_h / 2.0 + local_y) for u, v in c["points"]]
        pts = dedupe_closed_loop(pts)
        (hole_pts if c["hole"] else outer_pts).append(pts)

    solid = _extrude_profile_xy(outer_pts[0], z0, thickness, f"{name_prefix}_0")
    for i, pts in enumerate(outer_pts[1:], start=1):
        piece = _extrude_profile_xy(pts, z0, thickness, f"{name_prefix}_{i}")
        mod = solid.modifiers.new("Union", 'BOOLEAN')
        mod.object = piece
        mod.operation = 'UNION'
        bpy.context.view_layer.objects.active = solid
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(piece, do_unlink=True)
    for i, pts in enumerate(hole_pts):
        cutter = _extrude_profile_xy(pts, z0 - 1.0, thickness + 2.0, f"{name_prefix}_hole_{i}")
        mod = solid.modifiers.new("Hole", 'BOOLEAN')
        mod.object = cutter
        mod.operation = 'DIFFERENCE'
        bpy.context.view_layer.objects.active = solid
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cutter, do_unlink=True)

    return solid


def measure_text_aspect(text, font_path):
    """Height/width ratio of the text at some nominal size - queried once so
    the caller can compute a target height from a target width."""
    font = bpy.data.fonts.load(font_path)
    curve_data = bpy.data.curves.new("measure_text_curve", type='FONT')
    curve_data.body = text
    curve_data.font = font
    curve_data.size = 10.0
    curve_data.align_x = 'CENTER'
    curve_data.align_y = 'CENTER'
    curve_data.space_character = TEXT_SPACING
    obj = bpy.data.objects.new("measure_text", curve_data)
    bpy.context.scene.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    mesh = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.meshes.remove(mesh, do_unlink=True)
    return h / w


def build_text_prism(text, target_width, local_y, z0, thickness, name, font_path=MYTHOS_FONT_PATH):
    font = bpy.data.fonts.load(font_path)
    curve_data = bpy.data.curves.new(f"{name}_curve", type='FONT')
    curve_data.body = text
    curve_data.font = font
    curve_data.size = 10.0
    curve_data.align_x = 'CENTER'
    curve_data.align_y = 'CENTER'
    curve_data.space_character = TEXT_SPACING
    curve_data.extrude = thickness / 2.0
    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.scene.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-3)

    xs = [v.co.x for v in bm.verts]
    scale = target_width / (max(xs) - min(xs))
    for v in bm.verts:
        v.co.x *= scale
        v.co.y *= scale
        v.co.y += local_y
        v.co.z += z0 + thickness / 2.0  # curve's own extrude is centered on local z=0

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def build_logo_cutter(contours, icon_w, text_aspect, z0, thickness, name_prefix):
    """Icon above the wordmark, same width, gap proportional to icon
    height - built local-origin-centered, then mirrored in place (X-flip
    + reverse_faces) so it reads correct engraved into the underside."""
    icon_h = icon_w * MYTHOS_ASPECT
    text_h = icon_w * text_aspect
    gap = GAP_FRAC * icon_h
    icon_local_y = (text_h + gap) / 2.0
    text_local_y = -(icon_h + gap) / 2.0

    icon = build_mythos_prism(contours, icon_w, icon_h, icon_local_y, z0, thickness, f"{name_prefix}_icon")
    text = build_text_prism(LOGO_TEXT, icon_w, text_local_y, z0, thickness, f"{name_prefix}_text")

    bpy.ops.object.select_all(action='DESELECT')
    icon.select_set(True)
    text.select_set(True)
    bpy.context.view_layer.objects.active = icon
    bpy.ops.object.join()
    cutter = bpy.context.object
    cutter.name = name_prefix

    # mirror (determinant -1) so text/icon read correct viewed from
    # underneath - reverse_faces fixes winding, recalc_face_normals alone
    # can invert one shell relative to the other on a multi-shell mesh
    # like this (see feedback_blender_text_mesh_gotchas memory)
    bm = bmesh.new()
    bm.from_mesh(cutter.data)
    for v in bm.verts:
        v.co.x = -v.co.x
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(cutter.data)
    bm.free()
    return cutter


def build_bottom_logo(floor):
    """Cuts a shallow pocket for the logo into the base (material 1) and
    builds the matching insert (material 2) that fills it flush - same
    recess+insert multi-material technique as the dice tray/combat-modifier/
    token pieces, not a same-color engraving."""
    contours = load_contours(MYTHOS_CONTOURS_PATH)
    text_aspect = measure_text_aspect(LOGO_TEXT, MYTHOS_FONT_PATH)

    cutter = build_logo_cutter(
        contours, LOGO_ICON_W, text_aspect,
        -CUT_POKE, ENGRAVE_DEPTH + CUT_POKE, "bottom_logo_cutter",
    )
    vol_before = mesh_volume(floor)
    mod = floor.modifiers.new("Logo", 'BOOLEAN')
    mod.object = cutter
    mod.operation = 'DIFFERENCE'
    bpy.context.view_layer.objects.active = floor
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)

    vol_after = mesh_volume(floor)
    nm = nonmanifold_fraction(floor)
    print(f"  bottom logo pocket cut: {vol_before:.0f}mm3 -> {vol_after:.0f}mm3 (non-manifold {nm:.4f})")
    if not (0.0 < vol_after < vol_before) or nm > 0.01:
        print(f"  !! WARNING: logo cut looks corrupted")

    insert = build_logo_cutter(
        contours, LOGO_ICON_W, text_aspect,
        0.0, ENGRAVE_DEPTH, "bottom_logo_insert",
    )
    insert_vol = mesh_volume(insert)
    insert_nm = nonmanifold_fraction(insert)
    print(f"  bottom logo insert: {insert_vol:.0f}mm3 (non-manifold {insert_nm:.4f})")
    if insert_vol <= 0.0 or insert_nm > 0.01:
        print(f"  !! WARNING: logo insert looks corrupted")

    return insert

# ============================================================
# RING / WEDGE PLANNING
# ============================================================
def plan_rings(rng):
    """Irregular ring widths spanning pocket -> outer radius, normalized so
    they sum exactly to the span (same trick as plan_wedges) - otherwise
    the last ring is whatever's left over, often a thin sliver."""
    span = OUTER_RADIUS - POCKET_RADIUS
    widths = []
    total = 0.0
    while total < span:
        w = rng.uniform(RING_WIDTH_MIN, RING_WIDTH_MAX)
        widths.append(w)
        total += w
    scale = span / total
    widths = [w * scale for w in widths]

    rings = []
    r = POCKET_RADIUS
    for w in widths:
        rings.append((r, r + w))
        r += w
    return rings


def plan_wedges(rng):
    """Irregular angular widths covering 360 degrees, normalized, with a
    random rotational offset so seams stagger between rings."""
    angles = []
    total = 0.0
    while total < 360.0:
        a = rng.uniform(WEDGE_ANGLE_MIN, WEDGE_ANGLE_MAX)
        angles.append(a)
        total += a
    scale = 360.0 / total
    angles = [a * scale for a in angles]

    offset = rng.uniform(0, 360)
    bounds = [offset]
    for a in angles:
        bounds.append(bounds[-1] + a)
    return [(bounds[i], bounds[i + 1]) for i in range(len(angles))]

# ============================================================
# BUILD
# ============================================================
def build_stepped_floor(seed):
    """Two-thickness floor: thin under the pocket (small span, doesn't need
    the rigidity), thicker under the paved ring (the big warp-risk span).
    Built as two independent primitives with real overlapping volume at the
    step (EMBED), then ONE boolean union - not a coincident/flush seam."""
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=POCKET_RADIUS + EMBED, depth=FLOOR_THICKNESS_POCKET)
    pocket_floor = bpy.context.object
    pocket_floor.location.z = FLOOR_THICKNESS_POCKET / 2

    bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=OUTER_RADIUS, depth=FLOOR_THICKNESS_RING)
    ring_outer = bpy.context.object
    ring_outer.location.z = FLOOR_THICKNESS_RING / 2

    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=POCKET_RADIUS, depth=FLOOR_THICKNESS_RING + 0.4)
    ring_inner = bpy.context.object
    ring_inner.location.z = FLOOR_THICKNESS_RING / 2
    mod = ring_outer.modifiers.new("Bore", 'BOOLEAN')
    mod.object = ring_inner
    mod.operation = 'DIFFERENCE'
    bpy.context.view_layer.objects.active = ring_outer
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(ring_inner, do_unlink=True)

    mod = pocket_floor.modifiers.new("Step", 'BOOLEAN')
    mod.object = ring_outer
    mod.operation = 'UNION'
    bpy.context.view_layer.objects.active = pocket_floor
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(ring_outer, do_unlink=True)

    pocket_floor.name = f"objective_{seed}{SIZE_SUFFIX}"
    return pocket_floor


def cut_at_board_edge(obj):
    """Straight cut along +X at EDGE_CUT from the centre - ONE boolean after
    the tiles are on, so it slices floor and tiles together. A cut inside
    the pocket radius would open the pocket wall, so that's refused."""
    if EDGE_CUT <= POCKET_RADIUS:
        raise SystemExit(f"--edge-cut {EDGE_CUT}mm cuts into the {POCKET_RADIUS:.1f}mm pocket radius")
    size = OUTER_RADIUS * 2 + 10.0
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    cutter = bpy.context.object
    cutter.scale = (size, size, RING_TOP_Z + 10.0)
    cutter.location = (EDGE_CUT + size / 2, 0.0, RING_TOP_Z / 2)

    vol_before = mesh_volume(obj)
    mod = obj.modifiers.new("EdgeCut", 'BOOLEAN')
    mod.object = cutter
    mod.operation = 'DIFFERENCE'
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)

    vol_after = mesh_volume(obj)
    nm = nonmanifold_fraction(obj)
    print(f"  edge cut at {EDGE_CUT:.1f}mm (pocket wall {EDGE_CUT - POCKET_RADIUS:.1f}mm): "
          f"{vol_before:.0f}mm3 -> {vol_after:.0f}mm3 (non-manifold {nm:.4f})")
    if not (0.0 < vol_after < vol_before) or nm > 0.01:
        print(f"  !! WARNING: edge cut looks corrupted")


def build_objective_marker(seed):
    rng = random.Random(seed)

    floor = build_stepped_floor(seed)

    tile_z = FLOOR_THICKNESS_RING - EMBED
    tile_h = TILE_HEIGHT + EMBED

    ring_plan = plan_rings(rng)
    tiles = []
    for ring_idx, (r_in, r_out) in enumerate(ring_plan):
        gap_deg = math.degrees(GROUT_GAP / ((r_in + r_out) / 2))
        # every seam gets its usual grout gap except the outermost edge,
        # which runs flush to OUTER_RADIUS - no gap right at the rim
        tile_r_out = r_out if ring_idx == len(ring_plan) - 1 else r_out - GROUT_GAP / 2
        for a_start, a_end in plan_wedges(rng):
            jitter = rng.uniform(-HEIGHT_JITTER, HEIGHT_JITTER)
            bump   = rng.uniform(-BUMP_AMOUNT, BUMP_AMOUNT)
            t = make_wedge_tile(
                r_in  + GROUT_GAP / 2,
                tile_r_out,
                a_start + gap_deg / 2,
                a_end   - gap_deg / 2,
                tile_z + jitter, tile_h,
                name=f"tile_{seed}_{r_in:.0f}_{a_start:.0f}",
                bump=bump,
            )
            tiles.append(t)

    # combine all tiles (non-overlapping with each other) into one object,
    # then a single boolean union onto the floor - per the repo's boolean
    # fragility lesson: no per-tile booleans, no long chains.
    bpy.ops.object.select_all(action='DESELECT')
    for t in tiles:
        t.select_set(True)
    bpy.context.view_layer.objects.active = tiles[0]
    bpy.ops.object.join()
    tile_set = bpy.context.object

    floor_vol_before = mesh_volume(floor)
    tile_vol = mesh_volume(tile_set)

    mod = floor.modifiers.new("Tiles", 'BOOLEAN')
    mod.object = tile_set
    mod.operation = 'UNION'
    bpy.context.view_layer.objects.active = floor
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(tile_set, do_unlink=True)

    merged_vol = mesh_volume(floor)
    nm = nonmanifold_fraction(floor)
    expected_min = max(floor_vol_before, tile_vol)
    print(f"{floor.name}: floor={floor_vol_before:.0f}mm3 tiles={tile_vol:.0f}mm3 "
          f"-> merged={merged_vol:.0f}mm3 (non-manifold {nm:.4f})")
    if merged_vol < expected_min * 0.9 or nm > 0.01:
        print(f"  !! WARNING: union looks corrupted (expected >= {expected_min:.0f}mm3)")

    if EDGE_CUT:
        cut_at_board_edge(floor)

    insert = None
    if ADD_LOGO:
        floor.name = f"objective_{seed}{SIZE_SUFFIX}_logo"
        insert = build_bottom_logo(floor)
        insert.name = f"objective_{seed}{SIZE_SUFFIX}_logo_insert"
        apply_color(floor, "base_white", BASE_COLOR)
        apply_color(insert, "logo_green", LOGO_COLOR)

    return floor, insert

# ============================================================
# RENDER
# ============================================================
def compute_scene_bounds():
    xs, ys, zs = [], [], []
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ mathutils.Vector(corner)
            xs.append(world_corner.x)
            ys.append(world_corner.y)
            zs.append(world_corner.z)
    center = mathutils.Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2))
    size = max(max(xs) - min(xs), max(ys) - min(ys))
    return center, size


def setup_render_engine():
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = RENDER_RESOLUTION


def add_light(target, distance):
    light_data = bpy.data.lights.new("RenderLight", type='SUN')
    light_data.energy = 3.0
    light = bpy.data.objects.new("RenderLight", light_data)
    bpy.context.collection.objects.link(light)
    light.location = target + mathutils.Vector((distance * 0.4, -distance * 0.5, distance * 0.9))
    direction = target - light.location
    light.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()


def render_hero(name, center, size):
    """Angled 3/4 perspective shot to show the tile relief and pocket."""
    distance = size * 1.1
    cam_data = bpy.data.cameras.new("HeroCam")
    cam_data.type = 'PERSP'
    cam_data.lens = 50
    cam = bpy.data.objects.new("HeroCam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = center + mathutils.Vector((0.0, -distance * 0.85, distance * 0.9))
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam

    add_light(center, distance)
    bpy.context.scene.render.filepath = os.path.join(RENDER_DIR, f"{name}_hero.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {bpy.context.scene.render.filepath}")


def render_top(name, center, size):
    """Straight top-down orthographic shot for a plan-view scale reference."""
    cam_data = bpy.data.cameras.new("TopCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = size * 1.05
    cam = bpy.data.objects.new("TopCam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = center + mathutils.Vector((0.0, 0.0, size))
    cam.rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.scene.camera = cam

    add_light(center, size)
    bpy.context.scene.render.filepath = os.path.join(RENDER_DIR, f"{name}_top.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {bpy.context.scene.render.filepath}")


def render_bottom(name, center, size):
    """Straight bottom-up orthographic shot - the only view that shows the
    engraved logo, which sits on the underside."""
    cam_data = bpy.data.cameras.new("BottomCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = size * 1.05
    cam = bpy.data.objects.new("BottomCam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = center - mathutils.Vector((0.0, 0.0, size))
    cam.rotation_euler = (0.0, math.pi, 0.0)
    bpy.context.scene.camera = cam

    add_light(center, -size)
    bpy.context.scene.render.filepath = os.path.join(RENDER_DIR, f"{name}_bottom.png")
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {bpy.context.scene.render.filepath}")


def _clear_cameras_and_lights():
    for cam in [o for o in bpy.context.scene.objects if o.type == 'CAMERA']:
        bpy.data.objects.remove(cam, do_unlink=True)
    for light in [o for o in bpy.context.scene.objects if o.type == 'LIGHT']:
        bpy.data.objects.remove(light, do_unlink=True)


def render_object(obj):
    setup_render_engine()
    center, size = compute_scene_bounds()
    render_hero(obj.name, center, size)
    _clear_cameras_and_lights()
    render_top(obj.name, center, size)
    if ADD_LOGO:
        _clear_cameras_and_lights()
        render_bottom(obj.name, center, size)

def apply_color(obj, name, rgba):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = rgba
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

# ============================================================
# EXPORT
# ============================================================
def export_stl(obj):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    path = os.path.join(EXPORT_DIR, f"{obj.name}.stl")
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"Exported {path}")


def export_project_3mf(parts, path):
    """Anycubic Slicer Next's project-3mf flavor - same writer as
    blender/combat-modifiers/build_modifier_tokens.py and
    blender/dice-tower/build_dice_tray.py (that slicer ignores the
    standard 3MF color hint entirely, hence the per-part extruder
    metadata instead). `parts` is a list of (obj, name, extruder_slot) -
    single-material here, so everything sits on slot 0."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

    leaf_objects_xml, components_xml, parts_config_xml = [], [], []
    next_id = 1

    for obj, name, slot in parts:
        mesh = obj.data
        mesh.calc_loop_triangles()
        mw = obj.matrix_world
        verts_xml = "".join(
            f'<vertex x="{co.x:.5f}" y="{co.y:.5f}" z="{co.z:.5f}"/>'
            for co in (mw @ v.co for v in mesh.vertices)
        )
        tris_xml = "".join(
            f'<triangle v1="{t.vertices[0]}" v2="{t.vertices[1]}" v3="{t.vertices[2]}"/>'
            for t in mesh.loop_triangles
        )
        leaf_id = next_id
        next_id += 1
        leaf_objects_xml.append(
            f'<object id="{leaf_id}" type="model">'
            f'<mesh><vertices>{verts_xml}</vertices>'
            f'<triangles>{tris_xml}</triangles></mesh></object>'
        )
        components_xml.append(f'<component objectid="{leaf_id}"/>')
        parts_config_xml.append(
            f'<part id="{leaf_id}" subtype="normal_part">'
            f'<metadata key="name" value="{name}.stl"/>'
            f'<metadata key="extruder" value="{slot}"/></part>'
        )

    parent_id = next_id
    model_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        f'<resources>{"".join(leaf_objects_xml)}'
        f'<object id="{parent_id}" type="model">'
        f'<components>{"".join(components_xml)}</components></object>'
        f'</resources>'
        f'<build><item objectid="{parent_id}"/></build></model>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
        '</Types>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Target="/3D/3dmodel.model" Id="rel-1" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        '</Relationships>'
    )
    model_settings = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<config>'
        f'<object id="{parent_id}">'
        '<metadata key="name" value="plate"/>'
        f'{"".join(parts_config_xml)}'
        '</object></config>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("3D/3dmodel.model", model_xml)
        zf.writestr("Metadata/model_settings.config", model_settings)
    print(f"Exported {path}")

# ============================================================
# RUN
# ============================================================
def main():
    clear_scene()
    obj, insert = build_objective_marker(SEED)

    print(f"Objective marker v1 (seed {SEED}, logo={ADD_LOGO}) - outer diam {OUTER_RADIUS * 2:.1f}mm, "
          f"pocket diam {POCKET_RADIUS * 2:.1f}mm")
    print(f"  ring: {FLOOR_THICKNESS_RING:.1f}mm floor + {TILE_HEIGHT:.1f}mm tiles = {RING_TOP_Z:.1f}mm total")
    print(f"  pocket: {FLOOR_THICKNESS_POCKET:.1f}mm floor + {MARKER_THICKNESS:.1f}mm marker = {POCKET_TOP_Z:.1f}mm "
          f"-> marker sits {RECESS_MM:.1f}mm below the tile tops")

    if EXPORT_STL:
        os.makedirs(EXPORT_DIR, exist_ok=True)
        export_stl(obj)
        if insert is not None:
            export_stl(insert)

    # single-material plain print doesn't need a project file - just the STL.
    # the logo variant is a real two-material recess+insert, same convention
    # as the dice tray/combat-modifier/token pieces.
    if EXPORT_3MF and insert is not None:
        export_project_3mf(
            [(obj, obj.name, BASE_EXTRUDER_SLOT), (insert, insert.name, LOGO_EXTRUDER_SLOT)],
            os.path.join(EXPORT_DIR, f"{obj.name}.3mf"),
        )

    if RENDER_IMAGES:
        os.makedirs(RENDER_DIR, exist_ok=True)
        render_object(obj)

    print("Done.")


main()
