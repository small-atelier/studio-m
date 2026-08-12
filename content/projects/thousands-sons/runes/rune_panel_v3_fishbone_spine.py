"""
Rune panel batch V3 (Blender bpy) - standalone.

Same pipeline as rune_panel_v2_ring_gems.py (mask -> smoothed grid -> extrude glyph,
flat direct-to-plate orientation, 18x27mm panel), plus:
  - glyph footprint shrunk 14x20 -> 10x15mm (RUNE_W/RUNE_H), to make room for
  - a more embellished border: v2's ring + diamond-stud motif is replaced
    with a "fishbone" - the same thin rule-line spine, but studded with
    pairs of thin ribs that cross it at +-45 deg at each repeat step,
    reading as a woven/mathematical lattice rather than discrete studs

Run: Blender -> Scripting workspace -> Open this file -> Alt+P
"""

import bpy
import bmesh
import math
import mathutils
import os

# ============================================================
# CONFIG
# ============================================================

GLYPH_DIR = "/Users/mannil/Desktop/studio-m/TSONS/assets/rune_marks"

# The 16 visually-unique glyphs left after deduping (matches the files
# actually present in GLYPH_DIR). A trailing blank (no rune, border only)
# is appended in main().
GLYPH_POOL = [
    "manifestation", "decay", "binding", "chaos", "cycle", "void",
    "dominion", "earth", "entropy", "fire", "flow", "will",
    "life", "growth", "transcendence", "sacred",
]
GRID_ROWS = 3
PANEL_SPACING_X = 6.0
PANEL_SPACING_Z = 10.0

EXPORT_DIR = "/Users/mannil/Desktop/studio-m/TSONS/runes/output/v3_fishbone_spine"
EXPORT_STL = True

RENDER_IMAGES = True
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1600, 900)
# name -> rough direction from the grid's center (unit-ish; gets normalized
# and scaled to distance). The camera is aimed via a Track To constraint at
# the grid's center, not by hand-deriving rotation.
RENDER_ANGLES = {
    "front": (0.0, -1.0, 0.15),
    "side": (1.0, -0.1, 0.15),
    "top": (0.001, -0.3, 1.0),
    "iso": (0.6, -1.0, 0.6),
}

# Panel (X=width, Y=thickness, Z=height, pre-flatten - see build_and_export_panel)
BOX_W = 18.0
BOX_D = 2.0
BOX_H = 27.0

# Glyph footprint on the panel face - smaller than the box so there's a
# visible border margin. Shrunk from v2's 14x20 to 10x15 to give the
# fishbone border (below) more room: margins are now 4mm (sides) / 6mm
# (top-bottom), vs v2's tight 2mm/3.5mm.
RUNE_W = 10.0
RUNE_H = 15.0

RUNE_ALPHA_THRESHOLD = 0.15
RUNE_STROKE_DILATE = 1

# The source is 32x32 pixel art - extruded literally, its stair-stepped
# edges read as "a bunch of blocks" rather than a symbol. This is pure
# embellishment (not a faithful trace), so: upscale the mask via nearest-
# neighbor, box-blur it, re-threshold at 0.5. Blur+rethreshold rounds off
# the steps without systematically growing/shrinking the shape the way
# dilation does - the two are solving different problems (dilate thickens
# thin strokes, this rounds corners) and are applied in that order.
#
# MASK_BLUR_RADIUS is in upscaled-grid cells, so it's roughly
# (MASK_BLUR_RADIUS / MASK_SUPERSAMPLE) original-pixel-widths of smoothing.
# This is the knob that turns "rounded pixels" into "flowing lines" - too
# small a radius just rounds each pixel block's own corners without
# blending it into its neighbors; it needs to be comparable to (or bigger
# than) MASK_SUPERSAMPLE to actually merge adjacent pixels into one curve.
# Resolution (MASK_SUPERSAMPLE) alone doesn't fix this - only radius does.
MASK_SUPERSAMPLE = 6
MASK_BLUR_RADIUS = 8

# Laplacian relax pass on the mesh's own vertices, on top of the mask blur -
# fixes the residual staircase that "one quad per grid cell" always leaves
# no matter how smooth the mask is. Push iterations/factor up for a rounder
# look, but too much will visibly shrink/thin the strokes.
MESH_SMOOTH_ITERATIONS = 3
MESH_SMOOTH_FACTOR = 0.5

# How far the glyph stands proud of the box's front face
EMBOSS_HEIGHT = 1.5
# How far the glyph's base is buried into the box, so the union boundary
# isn't flush/coincident with the box's own front face - the same class of
# degenerate boolean input that fragmented the cut-through version. At the
# BOX_D=2.0 this lands the base exactly on the panel's center plane (still
# short of the back face) - checked, doesn't breach through.
EMBED_DEPTH = 1.0

# ------------------------------------------------------------
# Ornamental border v3: a "fishbone" motif - the same thin rule-line spine
# as v2's ring, but instead of diamond studs, each repeat step along it gets
# a pair of thin ribs crossing the spine at +-45 deg to its local tangent
# (tangent is 0 on the horizontal top/bottom runs, 90 on the vertical
# left/right runs - see edge_tangent_deg). Both ribs are centered on the
# same spine point, so they read as a small woven "X" rather than two
# separate marks; repeated along the whole perimeter it reads as a
# mathematical lattice/braid rather than discrete studs.
#
# FISHBONE_RIB_LENGTH=2.4 reaches ~0.85mm past the spine on each side
# (length/2 * sin(45)) - comfortably inside both the panel edge (spine is
# inset 1.5mm from it) and the glyph's margin (4mm/6mm, see RUNE_W/RUNE_H
# above). Revisit if BOX_W/BOX_H, FISHBONE_INSET, or RUNE_W/RUNE_H change.
# ------------------------------------------------------------
FISHBONE_INSET = 1.5
FISHBONE_SPINE_WIDTH = 0.6
FISHBONE_RIB_LENGTH = 2.4
FISHBONE_RIB_WIDTH = 0.5
FISHBONE_RIB_SPACING = 4.0
FISHBONE_RIB_ANGLE = 45.0
FISHBONE_EMBOSS_HEIGHT = 0.8
FISHBONE_EMBED_DEPTH = 0.6

# Chamfer on all 12 box edges - softens the raw slab look and gives 3D
# printing/resin casting less of a knife-edge to chip, and (once the panel
# is laid flat for printing) gives a scraper something to wedge under on
# the bottom perimeter to pop it off the build plate. Must stay under
# FISHBONE_INSET (1.5mm) so the bevel doesn't eat into the flat area the
# spine is unioned onto.
BOX_BEVEL_WIDTH = 0.4
BOX_BEVEL_SEGMENTS = 3


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


def frame_and_angle_view():
    """Point the 3D viewport at a 3/4 angle on everything in the scene and
    zoom to fit. A dead flat front-on view of an emboss looks like nothing -
    there's no foreshortening or shading to reveal the raised surface, so
    straight-on is close to the worst angle to inspect it from. Only selects
    mesh objects - not the render camera/light/target added afterward,
    which would otherwise drag the "zoom to fit" way out."""
    bpy.ops.object.select_all(action='DESELECT')
    mesh_objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    for obj in mesh_objects:
        obj.select_set(True)
    if mesh_objects:
        bpy.context.view_layer.objects.active = mesh_objects[0]

    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
            if region is None:
                continue
            with bpy.context.temp_override(window=window, area=area, region=region):
                bpy.ops.view3d.view_axis(type='FRONT')
                bpy.ops.view3d.view_orbit(angle=math.radians(-35), type='ORBITLEFT')
                bpy.ops.view3d.view_orbit(angle=math.radians(20), type='ORBITUP')
                bpy.ops.view3d.view_selected()
            return


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
    if not xs:
        return mathutils.Vector((0.0, 0.0, 0.0)), 10.0
    center = mathutils.Vector((
        (min(xs) + max(xs)) / 2,
        (min(ys) + max(ys)) / 2,
        (min(zs) + max(zs)) / 2,
    ))
    size = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    return center, size


def setup_camera_and_light(center):
    cam_data = bpy.data.cameras.new("RenderCam")
    cam_obj = bpy.data.objects.new("RenderCam", cam_data)
    bpy.context.collection.objects.link(cam_obj)

    # Empty at the grid's center - the camera tracks this via constraint
    # instead of us hand-computing a look-at rotation.
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


def render_angles(center, size):
    os.makedirs(RENDER_DIR, exist_ok=True)
    cam_obj = setup_camera_and_light(center)

    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = RENDER_RESOLUTION[0]
    scene.render.resolution_y = RENDER_RESOLUTION[1]

    distance = size * 1.8
    for name, direction in RENDER_ANGLES.items():
        cam_obj.location = center + mathutils.Vector(direction).normalized() * distance
        scene.render.filepath = os.path.join(RENDER_DIR, f"{name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"Rendered {scene.render.filepath}")


def export_stl(obj, filename):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = os.path.join(EXPORT_DIR, filename)
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

    on_count = sum(sum(row) for row in mask)
    print(f"[{glyph_name}] mask {w}x{h}, {on_count} px on after dilate={RUNE_STROKE_DILATE}")

    mask, w, h = upscale_and_smooth_mask(mask, w, h, MASK_SUPERSAMPLE, MASK_BLUR_RADIUS)
    on_count = sum(sum(row) for row in mask)
    print(f"[{glyph_name}] smoothed to {w}x{h}, {on_count} px on")

    return mask, w, h


def upscale_and_smooth_mask(mask, w, h, factor, radius):
    """Nearest-neighbor upscale, then box-blur via a summed-area table so an
    arbitrarily large radius costs the same as a small one (O(1) per cell
    instead of O(radius^2)), then re-threshold at 0.5."""
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


def build_glyph_stamp_mesh(glyph_name, depth):
    """Build a single connected mesh: one quad per "on" pixel, sharing
    vertices with its neighbors (a proper grid, not separate boxes), then
    extrude the whole connected surface once via bmesh's own extrude
    operator. This avoids ever hand-deriving face winding - Blender's
    extrude gets that right - and avoids feeding the boolean solver a pile
    of separately-overlapping shells, which is what fragmented/ate the
    result in the boxes-per-pixel-run version.

    Builds symmetric around local Y=0 (spans -depth/2..+depth/2); the caller
    positions/orients the resulting object for whatever it's cutting or
    embossing onto."""
    mask, w, h = load_glyph_mask(glyph_name)

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
            # order gives normal -Y (outward, since this starts as the back
            # face of the extrusion, at y=-depth/2)
            v0, v1, v2, v3 = get_vert(x, y), get_vert(x + 1, y), get_vert(x + 1, y + 1), get_vert(x, y + 1)
            faces.append(bm.faces.new((v0, v1, v2, v3)))

    # The mesh still snaps to grid-cell edges no matter how smooth the mask
    # is - that's what "one quad per cell" always produces, a staircase
    # that just gets finer at higher resolution rather than actually
    # curving. Relaxing the vertices themselves (Laplacian smoothing) fixes
    # that at the root. Flat interior verts barely move (symmetric
    # neighbors); it's mainly the silhouette boundary that relaxes.
    for _ in range(MESH_SMOOTH_ITERATIONS):
        bmesh.ops.smooth_vert(
            bm, verts=list(vert_grid.values()), factor=MESH_SMOOTH_FACTOR,
            use_axis_x=True, use_axis_y=False, use_axis_z=True,
        )

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


def point_on_rect_perimeter(s, w, h):
    """s is arc-length along a w x h rectangle's perimeter, starting at the
    top-left corner and going clockwise (right along top, down the right
    side, left along the bottom, up the left side). Returns a local (x, z)
    point, centered on the rectangle."""
    half_w, half_h = w / 2, h / 2
    if s < w:
        return (-half_w + s, half_h)
    s -= w
    if s < h:
        return (half_w, half_h - s)
    s -= h
    if s < w:
        return (half_w - s, -half_h)
    s -= w
    return (-half_w, -half_h + s)


def edge_tangent_deg(s, w, h):
    """Companion to point_on_rect_perimeter: which way the perimeter is
    running at arc-length s, expressed as a box rotation angle (0 = long
    axis along local X, matching the top/bottom spine bars' un-rotated
    orientation; 90 = long axis along local Z, matching the left/right
    bars). A rectangle's 180 deg symmetry means only two values are ever
    needed - same branch structure as point_on_rect_perimeter."""
    if s < w:
        return 0.0
    s -= w
    if s < h:
        return 90.0
    s -= h
    if s < w:
        return 0.0
    return 90.0


def add_box(bm, cx, cz, w, h, depth, angle_deg=0.0):
    """Appends a single axis-aligned (or Y-rotated, for the fishbone ribs)
    box into the given bmesh - width/height in local X/Z, `depth` in local Y
    (straddling Y=0, same convention build_glyph_stamp_mesh uses)."""
    mat = (mathutils.Matrix.Translation((cx, 0.0, cz))
           @ mathutils.Matrix.Rotation(math.radians(angle_deg), 4, 'Y')
           @ mathutils.Matrix.Diagonal(mathutils.Vector((w, depth, h, 1.0))))
    bmesh.ops.create_cube(bm, size=1.0, matrix=mat)


def bevel_box_edges(obj, width, segments):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.bevel(
        bm, geom=bm.edges[:], offset=width, offset_type='OFFSET',
        segments=segments, affect='EDGES', clamp_overlap=True,
    )
    bm.to_mesh(obj.data)
    bm.free()


def make_box_object(cx, cz, w, h, angle_deg, depth, name):
    bm = bmesh.new()
    add_box(bm, cx, cz, w, h, depth, angle_deg)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def build_fishbone_border_solid(panel_w, panel_h, depth):
    """v3's border: the same thin rule-line spine as v2's ring, but instead
    of diamond studs, each repeat step gets a pair of thin ribs crossing the
    spine at +-45 deg to its local tangent (both centered on the same spine
    point, so they read as one woven "X" rather than two separate marks).

    Every piece is unioned into one watertight solid up front via real
    sequential booleans, same as v2 - it's what's safe to reuse as a single
    cutter against every panel (see build_glyph_stamp_mesh's docstring for
    why: booleans against a pile of separately-overlapping shells as a
    single cutter is what fragmented an earlier version of this pipeline)."""
    parts = []  # (cx, cz, w, h, angle_deg)

    spine_w = panel_w - 2 * FISHBONE_INSET
    spine_h = panel_h - 2 * FISHBONE_INSET
    half_t = FISHBONE_SPINE_WIDTH / 2
    parts.append((0.0, spine_h / 2 - half_t, spine_w, FISHBONE_SPINE_WIDTH, 0.0))
    parts.append((0.0, -(spine_h / 2 - half_t), spine_w, FISHBONE_SPINE_WIDTH, 0.0))
    parts.append((spine_w / 2 - half_t, 0.0, FISHBONE_SPINE_WIDTH, spine_h, 0.0))
    parts.append((-(spine_w / 2 - half_t), 0.0, FISHBONE_SPINE_WIDTH, spine_h, 0.0))

    perimeter = 2 * (spine_w + spine_h)
    n_ribs = max(4, round(perimeter / FISHBONE_RIB_SPACING))
    for i in range(n_ribs):
        s = (i / n_ribs) * perimeter
        x, z = point_on_rect_perimeter(s, spine_w, spine_h)
        tangent = edge_tangent_deg(s, spine_w, spine_h)
        # Every rib pair is centered exactly on the spine line as placed
        # above - an exact-coincidence degenerate boolean input (same class
        # as the flush-boundary issue EMBED_DEPTH avoids elsewhere), which a
        # volume-consistency check (check_panel_volumes.py) caught: the
        # blank panel's border came out ~90% short of every other panel's,
        # because with no glyph stamp union to perturb the mesh first,
        # nothing broke the coincidence. Nudge the touch point a hair off
        # the spine, perpendicular to it, to break it - imperceptible at
        # this scale.
        rad_t = math.radians(tangent)
        nudge_x, nudge_z = -math.sin(rad_t) * 0.1, -math.cos(rad_t) * 0.1
        x, z = x + nudge_x, z + nudge_z
        parts.append((x, z, FISHBONE_RIB_LENGTH, FISHBONE_RIB_WIDTH, tangent + FISHBONE_RIB_ANGLE))
        parts.append((x, z, FISHBONE_RIB_LENGTH, FISHBONE_RIB_WIDTH, tangent - FISHBONE_RIB_ANGLE))

    solid = make_box_object(*parts[0], depth, "fishbone_solid")
    for cx, cz, w, h, angle in parts[1:]:
        piece = make_box_object(cx, cz, w, h, angle, depth, "fishbone_piece")
        apply_boolean(solid, piece, 'UNION')
    return solid


def build_and_export_panel(glyph_name, x_offset, z_offset, border_mesh):
    bpy.ops.mesh.primitive_cube_add(size=1)
    box = bpy.context.object
    box.name = f"panel_{glyph_name or 'blank'}"
    box.scale = (BOX_W, BOX_D, BOX_H)
    bpy.ops.object.transform_apply(scale=True, location=False, rotation=False)
    bevel_box_edges(box, BOX_BEVEL_WIDTH, BOX_BEVEL_SEGMENTS)

    # Box front face is at y=-BOX_D/2 (outward normal -Y). Each stamp is
    # built symmetric around its own local origin, so shift it in -Y until
    # its far edge sticks out past the front face by its emboss height and
    # its near edge is buried its embed depth past the surface.
    if glyph_name is not None:
        depth = EMBOSS_HEIGHT + EMBED_DEPTH
        stamp = build_glyph_stamp_mesh(glyph_name, depth)
        stamp.location.y = -BOX_D / 2 + (EMBED_DEPTH - EMBOSS_HEIGHT) / 2
        apply_boolean(box, stamp, 'UNION')

    border = bpy.data.objects.new("border_cutter", border_mesh)
    bpy.context.collection.objects.link(border)
    border.location.y = -BOX_D / 2 + (FISHBONE_EMBED_DEPTH - FISHBONE_EMBOSS_HEIGHT) / 2
    apply_boolean(box, border, 'UNION')

    # Lie flat for direct-to-plate resin printing: the relief (rune + border
    # + ribs) is a shallow, undercut-free emboss standing proud of a flat
    # plain back, so built plain-face-down it needs no supports. Rotating
    # -90 deg about local X sends the plain back (local +Y) to world -Z
    # (down, on the plate) and the emboss face (local -Y) to world +Z (up);
    # local Z (BOX_H, the panel's long axis) becomes world Y. All 12 edges
    # are already beveled above, including what's now the bottom perimeter -
    # that's what gives a scraper something to wedge under once the plate
    # comes off the printer.
    box.rotation_euler.x = math.radians(-90)
    bpy.ops.object.select_all(action='DESELECT')
    box.select_set(True)
    bpy.context.view_layer.objects.active = box
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

    box.location.x = x_offset
    box.location.y = z_offset

    if EXPORT_STL:
        export_stl(box, f"{box.name}.stl")


# ============================================================
# MAIN
# ============================================================

def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    clear_scene()

    panels = GLYPH_POOL + [None]  # trailing None = blank panel, border only

    border_depth = FISHBONE_EMBOSS_HEIGHT + FISHBONE_EMBED_DEPTH
    border_solid = build_fishbone_border_solid(BOX_W, BOX_H, border_depth)
    border_mesh = border_solid.data
    bpy.data.objects.remove(border_solid, do_unlink=True)

    cols = math.ceil(len(panels) / GRID_ROWS)

    for i, name in enumerate(panels):
        row = i // cols
        col = i % cols
        x = col * (BOX_W + PANEL_SPACING_X)
        z = -row * (BOX_H + PANEL_SPACING_Z)
        build_and_export_panel(name, x, z, border_mesh)

    if RENDER_IMAGES:
        center, size = compute_scene_bounds()
        render_angles(center, size)

    frame_and_angle_view()

    print(f"Done. {len(panels)} panel(s) exported to {EXPORT_DIR}")


if __name__ == "__main__":
    main()
