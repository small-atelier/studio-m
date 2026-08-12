"""
Arcane Obelisk generator (Blender bpy)

Target printer: Anycubic Photon Mono 2 (resin/MSLA)
Build volume:   143 x 89.5 x 165 mm (X x Y x Z)

Run: Blender -> Scripting workspace -> Open this file -> Alt+P
Modular kit, not matched sets: every shaft quarter shares SHAFT_HEIGHT, so
any 4 (from any seed) glue into one obelisk - mix and match. Per seed in
SHAFT_SEEDS: 4 quarters (shaft+spire unioned solid with a center bore,
rune+panel+diamond decorated, corner-cut into quarters). Plus a single
shared plinth (rune+panel decorated). No separate crystal cap, no
enclosed cavity anywhere - nothing to trap resin.
"""

import bpy
import bmesh
import math
import mathutils
import os
import random

# ============================================================
# CONFIG
# ============================================================

EXPORT_DIR = "/Users/mannil/Desktop/studio-m/TSONS/obelisks/output"

# Printer build volume (mm) - Anycubic Photon Mono 2. Each shaft quarter
# and the plinth/spire pieces are all comfortably smaller than this, so
# there's no print-bed-size splitting logic any more (that only existed
# for the old single-piece hollow shaft).
BED_X = 143.0
BED_Y = 89.5
BED_Z = 165.0

# Pillar geometry - tapers from BASE_WIDTH to TOP_WIDTH, then a separate
# low pyramidion cap (SPIRE_*) tapers the rest of the way to a point. Solid
# shaft with a simple center bore (see make_solid_shaft) for material
# savings - not a hollow shell. Shaft+spire get unioned into one solid,
# then corner-cut into 4 quarters for printing/gluing (see
# split_shaft_into_quarters) - no enclosed cavity anywhere at any point.
BASE_WIDTH = 28.0       # mm, footprint width at the base
TOP_WIDTH = 16.0        # mm, footprint width where the shaft meets the spire
BORE_WALL_MIN = 2.0     # mm, minimum wall thickness around the shaft's center bore -
                         # doesn't need to be precise, just avoid breaking through a wall.
                         # This is the binding constraint on bore size (it's sized off the
                         # narrowest point, at the top) - still a safe wall for resin at 2mm.
BORE_TOP_MARGIN = 5.0   # mm, how far short of the very top the bore stops

# Low pyramidion cap, not a tall spike - squat relative to its own base width.
# Unioned onto the shaft before the corner-cut (see build_and_export_variant),
# not a separate glued-on piece.
SPIRE_HEIGHT = 10.0
SPIRE_BLEED = 1.0  # embeds into the shaft's solid top for a clean union

# Stepped plinth the shaft stands on, part of this piece (not the separate
# foam-built ruins). Kept as its own separate piece (not merged into the
# shaft+spire before cutting) - shaft+spire alone already reaches ~152mm
# for the tallest variant; adding the plinth's ~22mm would exceed the
# printer's 165mm Z limit.
PLINTH_TIERS = [
    {"width": BASE_WIDTH + 16.0, "height": 16.0},
    {"width": BASE_WIDTH + 6.0, "height": 6.0},
]
PLINTH_BLEED = 1.5  # overlap between tiers for a clean union

# Socket recessed into the top, sized to the shaft's own footprint (plus a
# little clearance) so the assembled shaft seats into it for alignment/
# support rather than resting on a flat surface. The socket floor connects
# straight down into a box cavity reaching the bottom (a box removes more
# material than a cylindrical bore would - no solid "corners" left behind
# on a square plinth) - together they leave the plinth as a hollow ring
# rather than a solid block, same material-savings idea as the shaft's own
# bore.
PLINTH_SOCKET_DEPTH = 6.0
PLINTH_SOCKET_CLEARANCE = 0.5  # extra room around the shaft footprint so it seats easily
PLINTH_WALL_MIN = 5.0  # mm, minimum wall thickness around the plinth's hollow cavity -
                        # thicker than the shaft's own BORE_WALL_MIN since this is load-bearing
PLINTH_BEVEL_WIDTH = 0.4  # mm, softens the plinth's own outer edges (separate from
                           # the panel frame's own bevel, applied before the panels
                           # get unioned on)

# Raised border frame - the "laser-cut panel glued to the surface" look.
# Used two ways: small ones behind each shaft rune (standing proud less
# than the rune itself, so the rune still reads as the most prominent
# feature), and one plain wide one per face on the plinth's bottom tier
# (no rune inset - just the frame, sized to that tier's own width).
PANEL_W = 12.0
PANEL_H = 12.0
PANEL_BORDER = 1.2      # mm, frame bar width
PANEL_HEIGHT = 0.6      # mm, how proud the frame stands (< EMBOSS_HEIGHT)
PANEL_EMBED = 1.0       # mm, how far its base is buried into the wall
PANEL_BEVEL_WIDTH = 0.15  # mm, softens the frame's edges - stays well under
                           # half of PANEL_BORDER/PANEL_HEIGHT to avoid
                           # self-intersecting on such a thin shape
PLINTH_PANEL_MARGIN = 6.0  # mm, plinth panel width = tier width - this

# "Panels within the panel" on the plinth's main face panel, nested 3
# levels deep - main panel border -> small corner BRACKET
# (_build_corner_panel_bracket_mesh - a 2-sided open "L", not a closed
# ring) in each of its 4 corners -> an even smaller bracket of the same
# shape nested into THAT corner bracket's own far corner - plus a chain
# of 3 diamond-oriented panel-frames centered on the main panel. See
# emboss_plinth_panels for the placement math.
# Each bracket level is deliberately open on the 2 sides nearest its own
# parent's corner, positioned flush so those sides overlap/merge with the
# parent's own solid material - only the other 2 (inward) sides read as
# new/distinct detail, rather than a fully separate floating square (the
# ask this replaced: nesting a closed panel with clearance on every
# side). Reads as one complete panel per level because the parent
# supplies the other 2 sides, flush/coincident.
# CORNER_PANEL_W wider than CORNER_PANEL_H, matching the plinth panel's
# own wide/short aspect (ow/oh below) rather than a plain square - a
# square version was tried first and read as too squat/blocky against
# the panel's own long, low proportions.
# CORNER_PANEL_H must stay small enough that two corner panels of the
# same sign_x, stacked vertically (see emboss_plinth_panels), don't
# physically overlap each other - the main panel itself is short
# (PLINTH_TIERS[0]'s height, ~10mm), so CORNER_PANEL_H/2 must stay under
# the panel's own vertical corner offset (oh - CORNER_PANEL_H/2).
# Two manifold solids merely joined (not boolean-combined) but overlapping
# in volume is exactly the self-intersecting case that silently wipes out
# Blender's EXACT boolean solver result (this bit the first version of
# this feature: 4 overlapping corner panels joined onto the plinth emptied
# its entire mesh rather than erroring loudly).
CORNER_PANEL_W = 6.0
CORNER_PANEL_H = 3.0
CORNER_PANEL_BORDER = 0.8

# The next nesting level in from the corner bracket, nested INSIDE the
# corner bracket's own footprint, tucked toward its far corner - a plain
# CLOSED small panel frame (_build_panel_frame_mesh, not the open-bracket
# shape), positioned to overlap a comfortable, non-hairline chunk of the
# corner bracket's own kept border (see INNER_OVERLAP in
# emboss_plinth_panels) so the two merge into one continuous raised shape
# with no visible gap - the same "deep, resolved overlap" technique the
# center diamond chain already uses safely, not a hairline/tangent touch.
# Two earlier attempts got this wrong in opposite directions: an open
# bracket flushed hairline-exact against the corner bracket's internal
# border-inner edge produced a real near-tangent crossing (dense cluster
# of near-duplicate vertices at the seam, ~2x the usual duplicate-triangle
# count on STL reimport); an open bracket merely touching the corner
# bracket's outer edge (zero overlap) left a visible gap between the two
# shapes' actual material, since an open bracket's own border sits only
# at one end of its footprint - see the CORNER_PANEL_W comment above
# for why hairline/near-tangent touches are normally exactly where
# Blender's EXACT boolean solver is most fragile. A plain closed ring,
# genuinely overlapping (not just touching), sidesteps both problems.
# Same 2:1 wide/short proportion as the corner bracket (1/3 its size in
# each dimension) rather than a plain square, for the same reason -
# comfortably inside the corner bracket's own footprint so there's no
# risk of crossing the panel's vertical center.
INNER_PANEL_W = 2.0
INNER_PANEL_H = 1.0
INNER_PANEL_BORDER = 0.2
INNER_OVERLAP = 0.4  # mm, how deep into the corner bracket's own kept
                      # border (CORNER_PANEL_BORDER=0.8 thick) the inner
                      # panel's near edge reaches - comfortably mid-way,
                      # not grazing either boundary of that border.

# All decoration levels stand proud of the wall by the same amount as the
# main panel itself (PANEL_HEIGHT) - a uniform, flush-height look rather
# than the stepped-relief one this replaced. What actually keeps Blender's
# EXACT boolean solver happy with all these overlapping footprints isn't
# height staggering (turns out not to be required) - it's doing each
# decoration TYPE as its own join+union pass against the already-solid
# result of the previous pass (see the loop below), plus, for the one
# case with pieces that overlap EACH OTHER (the diamond chain), resolving
# that overlap into a single clean solid first (see the chain-building
# loop below) before it ever meets the plinth.
PLINTH_DECOR_HEIGHT = PANEL_HEIGHT

# Chain of 3 diamond-oriented panel-frames (45-degree rotated, via
# _build_panel_frame_mesh's rotate_deg) centered on the main panel, each
# overlapping the next like chain links - the center one is 30% bigger
# than the (equal-sized, and correspondingly shrunk to keep the chain's
# overall footprint from growing) two flanking it. Square (pre-rotation)
# so each diamond's bounding half-diagonal (= size/2 * sqrt(2)) stays
# comfortably inside the main panel's own half-height (oh) rather than
# poking out its top/bottom edge.
CENTER_PANEL_SIZE = 3.2
CENTER_PANEL_MID_SIZE = CENTER_PANEL_SIZE * 1.3
CENTER_PANEL_BORDER = 0.6
CENTER_CHAIN_SPACING = 3.3  # mm, center-to-center - a real, deep overlap (see emboss_plinth_panels
                             # for how that's made safe: resolved into one solid before touching the plinth)

# Small flat diamond studs, 2 vertical strips per face, inset from the
# edges rather than sitting on them - the shaft now gets cut through the
# corners, so anything on the edge would get sliced in half. Built and
# placed the same way as the rune stamps (same canonical local frame), but
# with their own much shallower proud/embed depth - reusing EMBOSS_HEIGHT
# (1.5mm) at this small scale made them 75% as deep as they are wide, which
# reads as a thin spike/peg rather than a flat stud. Asymmetric width/tall
# (narrower than it is tall) so it's unambiguously a diamond, not a square.
DIAMOND_WIDTH = 2.0
DIAMOND_TALL = 4.0
DIAMOND_HEIGHT = 0.4    # mm, how proud it stands
DIAMOND_EMBED = 0.4     # mm, how far its base is buried into the wall
DIAMOND_STRIP_INSET = 3.0  # mm, how far in from the face edge each strip sits
DIAMOND_SPACING = 10.0
DIAMOND_MARGIN_TOP = 15.0
DIAMOND_MARGIN_BOTTOM = 10.0

# Rune panels (raised emboss on each of the 4 faces). Stamps are pre-built
# by ../runes/build_stamp_library.py (mask smoothing + mesh generation
# happens there, once, at a resolution sized for these 8x8mm slots) - this
# script just imports the result and positions/unions it. Rebuilding from
# the source pixel art on every single run used to feed Blender's boolean
# solver several hundred thousand faces per obelisk; see that script's
# docstring for the full story.
RUNE_ROWS = 4
RUNE_MARGIN_TOP = 20.0         # keep clear of where the spire attaches
RUNE_MARGIN_BOTTOM = 15.0      # keep clear of the base
RUNE_SKIP_CHANCE = 0.15        # per-slot chance to leave a face bare (variation)

# How far the glyph stands proud of the wall surface / how far its base is
# buried into the wall for a clean union boundary. Must match the stamp
# library's build settings - it baked these dimensions into the geometry.
EMBOSS_HEIGHT = 1.5
EMBED_DEPTH = 1.0

STAMP_LIBRARY_DIR = "/Users/mannil/Desktop/studio-m/TSONS/runes/output/stamps"
RUNE_GLYPH_POOL = ["chaos", "void", "entropy", "sacred", "manifestation", "transcendence"]

# Modular kit: one fixed height so every shaft quarter is dimensionally
# interchangeable - print a pool of differently-decorated quarters (one set
# per seed below) and mix-and-match any 4 into an obelisk. Only one plinth
# and one spire design needed, not one per seed - the plinth's own
# decoration (see emboss_plinth_panels) doesn't vary, so it doesn't need a
# seed at all.
SHAFT_HEIGHT = 130.0
SHAFT_SEEDS = [1, 2, 3, 4]

FACE_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]  # +X, -X, +Y, -Y

# Rotation (about Z) that maps a glyph stamp's canonical local frame
# (X=width, Y=depth, Z=height) onto each face, so the stamp's depth axis
# points along that face's normal.
FACE_ROT_Z = {
    (1, 0): -math.pi / 2,
    (-1, 0): math.pi / 2,
    (0, 1): 0.0,
    (0, -1): math.pi,
}

EXPORT_STL = True

RENDER_IMAGES = True
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1600, 900)
RENDER_ANGLES = {
    "front": (0.0, -1.0, 0.15),
    "side": (1.0, -0.1, 0.15),
    "top": (0.001, -0.3, 1.0),
    "iso": (0.6, -1.0, 0.6),
}


# ============================================================
# SCENE HELPERS
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


def apply_bevel(obj, width, segments=2):
    mod = obj.modifiers.new("Bevel", 'BEVEL')
    mod.width = width
    mod.segments = segments
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def export_stl(obj, filename):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = os.path.join(EXPORT_DIR, filename)
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"Exported {path}")


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


# ============================================================
# GEOMETRY - tapered square prism
# ============================================================

def make_square_prism(name, base_hw, top_hw, height, z0=0.0):
    """4-sided prism, square cross-section, linearly tapered from base_hw to
    top_hw. top_hw=0.0 is a special case (a true point, e.g. for the spire
    cap) - a quad top cap would be degenerate (all 4 verts coincident), so
    it collapses to a single apex vertex and triangular side faces instead."""
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    b, t = base_hw, top_hw
    z_bot, z_top = z0, z0 + height
    v_bot = [
        bm.verts.new((-b, -b, z_bot)), bm.verts.new((b, -b, z_bot)),
        bm.verts.new((b, b, z_bot)), bm.verts.new((-b, b, z_bot)),
    ]
    # bottom cap needs the reverse winding of the natural vert order to face
    # outward (-Z) - verified via cross product, easy to get backwards by
    # "symmetry" intuition.
    bm.faces.new((v_bot[0], v_bot[3], v_bot[2], v_bot[1]))

    if t == 0.0:
        apex = bm.verts.new((0.0, 0.0, z_top))
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((v_bot[i], v_bot[j], apex))
    else:
        v_top = [
            bm.verts.new((-t, -t, z_top)), bm.verts.new((t, -t, z_top)),
            bm.verts.new((t, t, z_top)), bm.verts.new((-t, t, z_top)),
        ]
        # top cap uses the natural vert order to face outward (+Z)
        bm.faces.new((v_top[0], v_top[1], v_top[2], v_top[3]))
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((v_bot[i], v_bot[j], v_top[j], v_top[i]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    return obj


def outer_half_width(z, height):
    frac = max(0.0, min(1.0, z / height))
    return BASE_WIDTH / 2 + (TOP_WIDTH / 2 - BASE_WIDTH / 2) * frac


def make_solid_shaft(name, height):
    """Solid tapered shaft with a tapered bore down the center, matching
    the shaft's own taper - wider at the base, narrower at the top - so it
    removes much more material at the base than a constant-radius cylinder
    could (that was stuck being sized off the narrow top everywhere).
    Material savings without ever creating an enclosed cavity (the whole
    assembly gets corner-cut into 4 quarters later, see
    split_shaft_into_quarters, so there's nothing to seal shut and nothing
    to trap resin)."""
    shaft = make_square_prism(name, BASE_WIDTH / 2, TOP_WIDTH / 2, height)

    bleed = 2.0  # only needed at the bottom - the top end cuts into a
                 # continuous face, not right at an existing surface boundary
    z_bot, z_top = -bleed, height - BORE_TOP_MARGIN
    bottom_radius = BASE_WIDTH / 2 - BORE_WALL_MIN
    top_radius = outer_half_width(z_top, height) - BORE_WALL_MIN

    bpy.ops.mesh.primitive_cone_add(
        vertices=48, radius1=bottom_radius, radius2=top_radius, depth=z_top - z_bot,
    )
    bore = bpy.context.object
    bore.location = (0, 0, (z_bot + z_top) / 2)
    bpy.ops.object.transform_apply(location=False, scale=False, rotation=False)

    apply_boolean(shaft, bore, 'DIFFERENCE')
    shaft.name = name
    return shaft


def split_shaft_into_quarters(solid, z_min, z_max, base_name):
    """Two diagonal cuts through the corners (not the face midpoints) -
    each resulting piece is one full flat face with its rune/panel/diamond
    decoration intact, glue seams landing on the plain corner edges
    instead of running through the middle of a decorated face. Same box-
    intersect technique as before, just each cutting box is rotated 45
    degrees and pushed out along a face direction (FACE_DIRS) instead of a
    corner direction - that reorients its two active cutting planes onto
    the diagonals. z_min/z_max are the piece's true extents. No bleed/
    overlap between quarters: they butt-join flush when glued and are
    never boolean-combined with each other, so a shared cut plane isn't
    the coincident-face problem it would be if they were being unioned
    back together."""
    quarters = []
    big = BASE_WIDTH * 3
    # For a box rotated 45 degrees, its near face (the one meant to pass
    # exactly through the origin) sits at perpendicular distance big/2 from
    # the box's OWN center - but after rotation that face's normal points
    # along the diagonal, so the center must be pushed out by big/2 divided
    # by cos(45), i.e. big/sqrt(2), for that face to actually reach the
    # origin. Using big/2 here (a face-vs-center distance, not accounting
    # for the rotation) left the cut planes offset ~17mm short of center
    # at this box size - each "quarter" was keeping most of the shaft
    # instead of an actual quarter.
    offset = big / math.sqrt(2)
    z_mid = (z_min + z_max) / 2
    z_height = z_max - z_min
    for i, (dx, dy) in enumerate(FACE_DIRS):
        dup = solid.copy()
        dup.data = solid.data.copy()
        dup.name = f"{base_name}_q{i + 1}"
        bpy.context.collection.objects.link(dup)

        bpy.ops.mesh.primitive_cube_add(size=1)
        box = bpy.context.object
        box.scale = (big, big, z_height + 4.0)
        box.rotation_euler.z = math.radians(45)
        box.location = (dx * offset, dy * offset, z_mid)
        bpy.ops.object.transform_apply(scale=True, location=False, rotation=True)

        apply_boolean(dup, box, 'INTERSECT')
        quarters.append(dup)

    bpy.data.objects.remove(solid, do_unlink=True)
    return quarters


def make_spire(name, height):
    """Solid low pyramidion cap, sitting on the shaft's already-solid top.
    Starts SPIRE_BLEED below the shaft's top so the union boundary isn't
    flush/coincident with the shaft's own top face."""
    return make_square_prism(
        name, TOP_WIDTH / 2, 0.0, SPIRE_HEIGHT + SPIRE_BLEED, z0=height - SPIRE_BLEED,
    )


def make_plinth(name):
    """Stepped base the shaft stands on, built downward from z=0 so the
    shaft's own z=0-relative geometry (rune rows) doesn't need to change.
    Each tier's height is padded by PLINTH_BLEED at its top so it overlaps
    into whatever sits above (the next tier) rather than meeting it at an
    exact, coincident plane.

    Hollowed into a ring: a socket recessed into the top (sized to the
    shaft's own footprint, so the assembled shaft seats into it for
    alignment/support) connects straight down into a center bore reaching
    the bottom, via a small overlap so the two cavities merge cleanly
    rather than meeting at a coincident plane. The bore is sized off the
    narrower upper tier, which leaves it conservative (thick walls) within
    the wider base tier - a second, wider box cavity hollows that tier out
    properly too, since it doesn't share the bore's constraint. Finished
    with a bevel on the plain block before the panels get unioned on, so
    they keep their own separate bevel untouched."""
    total_height = sum(t["height"] for t in PLINTH_TIERS)
    z = -total_height
    pieces = []
    for i, tier in enumerate(PLINTH_TIERS):
        piece_height = tier["height"] + PLINTH_BLEED
        piece = make_square_prism(f"{name}_tier{i}", tier["width"] / 2, tier["width"] / 2, piece_height, z0=z)
        pieces.append(piece)
        z += tier["height"]

    base = pieces[0]
    for p in pieces[1:]:
        apply_boolean(base, p, 'UNION')

    bleed = 2.0
    socket_hw = BASE_WIDTH / 2 + PLINTH_SOCKET_CLEARANCE
    socket = make_square_prism(
        f"{name}_socket", socket_hw, socket_hw, PLINTH_SOCKET_DEPTH + bleed, z0=-PLINTH_SOCKET_DEPTH,
    )
    apply_boolean(base, socket, 'DIFFERENCE')

    overlap = 1.0  # bore's top reaches slightly past the socket floor so the two cavities merge
    narrowest_hw = min(t["width"] for t in PLINTH_TIERS) / 2
    bore_radius = narrowest_hw - PLINTH_WALL_MIN
    z_bot, z_top = -total_height - bleed, -PLINTH_SOCKET_DEPTH + overlap
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=bore_radius, depth=z_top - z_bot)
    bore = bpy.context.object
    bore.location = (0, 0, (z_bot + z_top) / 2)
    bpy.ops.object.transform_apply(location=False, scale=False, rotation=False)
    apply_boolean(base, bore, 'DIFFERENCE')

    # Second cavity: a box, almost as wide as the base tier itself, so that
    # tier isn't left with excess solid material just because the bore
    # above had to be sized conservatively for the narrower tier. Open at
    # the true bottom (bleeds past it), but stops PLINTH_WALL_MIN short of
    # the tier0/tier1 seam - not overlapping past it - leaving a solid lip
    # up there for tier1 (and everything glued on above it) to stand on.
    base_tier = PLINTH_TIERS[0]
    box_hw = base_tier["width"] / 2 - PLINTH_WALL_MIN
    box_z_bot = -total_height - bleed
    tier0_top = -total_height + base_tier["height"]
    box_z_top = tier0_top - PLINTH_WALL_MIN
    base_cavity = make_square_prism(
        f"{name}_basecavity", box_hw, box_hw, box_z_top - box_z_bot, z0=box_z_bot,
    )
    apply_boolean(base, base_cavity, 'DIFFERENCE')

    apply_bevel(base, PLINTH_BEVEL_WIDTH)

    base.name = name
    return base


# ============================================================
# RUNE PANELS - stamps pre-built by ../runes/build_stamp_library.py
# ============================================================

_glyph_mesh_cache = {}


def _build_glyph_stamp_mesh(glyph_name):
    """Import (once, cached) the pre-built stamp mesh for one glyph from the
    stamp library, in its canonical local frame: X=width, Y=depth (straddles
    0, spans -depth/2..+depth/2), Z=height. See build_stamp_library.py for
    why this is imported rather than rebuilt from the source pixel art here
    - short version: identical output every run for a given glyph name, so
    redoing the (expensive) mask smoothing + mesh generation on every single
    obelisk.py run was pure waste, and it was feeding Blender's boolean
    solver several hundred thousand faces per obelisk in the process."""
    if glyph_name in _glyph_mesh_cache:
        return _glyph_mesh_cache[glyph_name]

    path = os.path.join(STAMP_LIBRARY_DIR, f"{glyph_name}.stl")
    before = set(bpy.data.objects)
    bpy.ops.wm.stl_import(filepath=path)
    imported = [o for o in bpy.data.objects if o not in before]
    if not imported:
        raise RuntimeError(f"STL import produced no object for {path}")

    obj = imported[0]
    mesh = obj.data
    mesh.name = f"glyph_{glyph_name}"
    bpy.data.objects.remove(obj, do_unlink=True)  # keep the mesh datablock, drop the wrapper object

    _glyph_mesh_cache[glyph_name] = mesh
    return mesh


_panel_frame_mesh_cache = {}


def _build_panel_frame_mesh(w=PANEL_W, h=PANEL_H, border=PANEL_BORDER, rotate_deg=0.0, bevel=PANEL_BEVEL_WIDTH):
    """Cached (built once per w,h,border,rotate_deg,bevel combo) raised
    rectangular border frame - the "laser-cut panel glued to the wall"
    look. One ring face (outer rect minus inner rect), extruded the same
    way as the rune stamps, then beveled for a softer, more finished edge -
    a plain border shape can take a bevel without hurting paint-line
    legibility the way fine rune linework would. Used at the small
    PANEL_W/H size behind each shaft rune, at a wider size (spanning most
    of a face) on the plinth, and recursively nested at smaller
    size/border into that wide panel's own corners (see
    emboss_plinth_panels) - border is a separate parameter (rather than
    always PANEL_BORDER) so those smaller nested panels can use a
    proportionally thinner border and stay a valid ring rather than
    inverting when border would otherwise exceed the half-height. bevel
    defaults to PANEL_BEVEL_WIDTH but can be set to 0 for the smallest
    nested rings, where that fixed bevel width is no longer "well under
    half" of such a thin border and risks a self-intersecting bevel.
    rotate_deg spins the ring in its own build plane before extrusion (e.g.
    45 for a diamond-oriented center panel) - built directly into the
    vertex coordinates like every other rotated/mirrored shape in this
    file, rather than via a rotated object, so it unions in cleanly."""
    key = (w, h, border, rotate_deg, bevel)
    if key in _panel_frame_mesh_cache:
        return _panel_frame_mesh_cache[key]

    depth = PANEL_HEIGHT + PANEL_EMBED
    ow, oh = w / 2, h / 2
    iw, ih = ow - border, oh - border

    ang = math.radians(rotate_deg)
    cos_a, sin_a = math.cos(ang), math.sin(ang)

    def rot(x, z):
        return (x * cos_a - z * sin_a, x * sin_a + z * cos_a)

    def vert(x, z):
        rx, rz = rot(x, z)
        return bm.verts.new((rx, -depth / 2, rz))

    bm = bmesh.new()
    outer = [vert(-ow, -oh), vert(ow, -oh), vert(ow, oh), vert(-ow, oh)]
    inner = [vert(-iw, -ih), vert(iw, -ih), vert(iw, ih), vert(-iw, ih)]
    # ring of 4 trapezoids, wound to face -Y outward (matches the rune
    # stamp convention - verified via cross product)
    faces = [bm.faces.new((outer[i], outer[(i + 1) % 4], inner[(i + 1) % 4], inner[i])) for i in range(4)]

    extruded = bmesh.ops.extrude_face_region(bm, geom=faces)
    new_verts = [g for g in extruded['geom'] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=new_verts, vec=(0, depth, 0))

    if bevel > 0.0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=2)

    mesh = bpy.data.meshes.new(f"panel_frame_{w:.0f}x{h:.0f}_b{border:.1f}_r{rotate_deg:.0f}")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

    _panel_frame_mesh_cache[key] = mesh
    return mesh


_corner_bracket_mesh_cache = {}


def _build_corner_panel_bracket_mesh(sign_x, sign_z, w=CORNER_PANEL_W, h=CORNER_PANEL_H,
                                      border=CORNER_PANEL_BORDER, bevel=PANEL_BEVEL_WIDTH):
    """2-sided open "L" bracket - the same ring shape as
    _build_panel_frame_mesh but keeping only its local -Z and -X side
    trapezoids (the two facing the panel's center), built directly at
    whichever of the 4 corners sign_x/sign_z picks (signed vertex
    coordinates, same mirroring trick as elsewhere in this file).
    Positioned (see emboss_plinth_panels) so the two OMITTED sides (local
    +Z and +X - the two nearest the plinth's true corner) sit flush,
    overlapping, with the main panel's own border on both edges at once -
    they merge into shared edges there, so only the 2 remaining (inward)
    sides read as new/distinct detail rather than a fully separate
    floating rectangle. Dropping whole faces (rather than trimming them)
    also means extrude_face_region caps the new cut edges the same way it
    already caps the ring's outer/inner boundary, so the result stays a
    valid manifold solid with no extra bookkeeping."""
    key = (sign_x, sign_z, w, h, border, bevel)
    if key in _corner_bracket_mesh_cache:
        return _corner_bracket_mesh_cache[key]

    depth = PANEL_HEIGHT + PANEL_EMBED
    ow, oh = w / 2, h / 2
    iw, ih = ow - border, oh - border

    def vert(x, z):
        return bm.verts.new((x * sign_x, -depth / 2, z * sign_z))

    bm = bmesh.new()
    o_bl, o_br, o_tr, o_tl = vert(-ow, -oh), vert(ow, -oh), vert(ow, oh), vert(-ow, oh)
    i_bl, i_br, i_tr, i_tl = vert(-iw, -ih), vert(iw, -ih), vert(iw, ih), vert(-iw, ih)
    faces = [
        bm.faces.new((o_bl, o_br, i_br, i_bl)),  # bottom (local -Z, faces the panel's center)
        bm.faces.new((o_tl, o_bl, i_bl, i_tl)),  # left (local -X, faces the panel's center)
        # right (local +X) and top (local +Z) omitted - the two sides
        # nearest the plinth's true corner, which overlap/merge with the
        # main panel's own border, see docstring
    ]

    extruded = bmesh.ops.extrude_face_region(bm, geom=faces)
    new_verts = [g for g in extruded['geom'] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=new_verts, vec=(0, depth, 0))

    if bevel > 0.0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=2)

    mesh = bpy.data.meshes.new(f"corner_bracket_{sign_x}_{sign_z}")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

    _corner_bracket_mesh_cache[key] = mesh
    return mesh


def _place_decor(stamps, mesh, name, dx, dy, z, hw, stand_off, embed, tangent_offset=0.0):
    """Position/rotate one instance of `mesh` onto face (dx,dy) at height z,
    appended to `stamps` for the caller to join+union in one batch.
    FACE_ROT_Z aligns the piece's local Y (depth) axis with the face's
    outward normal (dx,dy) - after rotation, the extruded/duplicated cap
    (local Y=+depth/2) ends up pointing outward and the originally-built
    cap (local Y=-depth/2) points inward, so the two are embedded/proud the
    opposite way round from the flat test panel, where the object isn't
    rotated at all. Solves for the radial offset r0 such that:
        r0 + depth/2 = hw + stand_off   (outward tip proud of the surface)
        r0 - depth/2 = hw - embed       (inward tip buried in the wall)
    which both give r0 = hw + (stand_off - embed) / 2.

    tangent_offset shifts the piece sideways along the face (e.g. two
    diamond strips left/right of center) rather than centered. The same
    FACE_ROT_Z rotation maps local X (width/tangent) onto world direction
    (dy, -dx) - a 90-degree rotation of the face normal - so that's the
    tangent world direction to offset along."""
    r0 = hw + (stand_off - embed) / 2
    tx, ty = dy, -dx
    # .copy() is required: bpy.ops.object.join() later mutates the active
    # object's mesh datablock IN PLACE (it doesn't create a new one), so an
    # instance that shared a cached mesh directly would permanently bloat
    # that cache entry with every other instance's geometry - compounding
    # across every slot, then every obelisk in the same run.
    inst = bpy.data.objects.new(name, mesh.copy())
    bpy.context.collection.objects.link(inst)
    inst.rotation_euler.z = FACE_ROT_Z[(dx, dy)]
    inst.location = (dx * r0 + tx * tangent_offset, dy * r0 + ty * tangent_offset, z)
    stamps.append(inst)


def _add_decor_slot(stamps, dx, dy, z, hw, rng):
    """One rune glyph + its (small) panel frame, both positioned onto face
    (dx,dy) at height z. The rune and its panel use different
    stand_off/embed values, so they end up at slightly different radii -
    the rune sits proud of the panel, by design."""
    glyph_name = rng.choice(RUNE_GLYPH_POOL)
    _place_decor(
        stamps, _build_glyph_stamp_mesh(glyph_name), f"rune_{glyph_name}_{dx}_{dy}_{z:.1f}",
        dx, dy, z, hw, EMBOSS_HEIGHT, EMBED_DEPTH,
    )
    _place_decor(
        stamps, _build_panel_frame_mesh(), f"panel_{dx}_{dy}_{z:.1f}",
        dx, dy, z, hw, PANEL_HEIGHT, PANEL_EMBED,
    )


def _union_decor(obj, stamps):
    if not stamps:
        return obj

    bpy.ops.object.select_all(action='DESELECT')
    for s in stamps:
        s.select_set(True)
    bpy.context.view_layer.objects.active = stamps[0]
    bpy.ops.object.join()
    stamp_union = bpy.context.active_object

    apply_boolean(obj, stamp_union, 'UNION')
    return obj


def emboss_rune_panels(obj, height, seed):
    """RUNE_ROWS rows of rune+panel decoration per face, up the shaft."""
    rng = random.Random(seed)
    usable_top = height - RUNE_MARGIN_TOP
    usable_bottom = RUNE_MARGIN_BOTTOM
    span = usable_top - usable_bottom
    if span <= 0:
        return obj
    row_spacing = span / RUNE_ROWS

    stamps = []
    for dx, dy in FACE_DIRS:
        for row in range(RUNE_ROWS):
            if rng.random() < RUNE_SKIP_CHANCE:
                continue
            z = usable_bottom + row_spacing * (row + 0.5)
            hw = outer_half_width(z, height)
            _add_decor_slot(stamps, dx, dy, z, hw, rng)

    return _union_decor(obj, stamps)


def emboss_plinth_panels(obj):
    """"Panels within the panel" on the plinth's widest (bottom) tier - the
    "ornament" on the base:
      - one wide panel frame per face (_build_panel_frame_mesh, as before)
      - a small wide/short 2-sided open bracket (_build_corner_panel_bracket_mesh)
        nested into each of its 4 corners, flush/overlapping the main
        panel's own border on its 2 open sides - reads as one complete
        panel per corner since the main panel's border supplies the
        other 2 sides
      - an even smaller closed panel frame (_build_panel_frame_mesh, not
        the open-bracket shape), nested INSIDE each of THOSE corner
        brackets' own footprint, overlapping a comfortable chunk of its
        kept border so the two merge into one continuous shape with no
        visible gap
      - a chain of 3 diamond-oriented panel frames (45-degree rotated)
        centered on the main panel, each overlapping the next, with the
        center one 30% bigger than the two (correspondingly shrunk) flanking it
    No rune glyph - just frames, sized to the tier's own dimensions (minus
    PLINTH_PANEL_MARGIN) rather than the small shaft-rune panel size."""
    tier = PLINTH_TIERS[0]
    hw = tier["width"] / 2
    z = -sum(t["height"] for t in PLINTH_TIERS) + tier["height"] / 2
    panel_w = tier["width"] - PLINTH_PANEL_MARGIN
    panel_h = tier["height"] - PLINTH_PANEL_MARGIN
    mesh = _build_panel_frame_mesh(panel_w, panel_h)
    ow, oh = panel_w / 2, panel_h / 2

    cw, ch = CORNER_PANEL_W / 2, CORNER_PANEL_H / 2
    corner_x = ow - cw  # flush with the main panel's own outer edge (open sides overlap/merge with its border)
    corner_z = oh - ch  # flush with the main panel's own outer edge (open sides overlap/merge with its border)

    inner_iw, inner_ih = INNER_PANEL_W / 2, INNER_PANEL_H / 2
    # Nested INSIDE the corner bracket's own footprint, positioned so the
    # inner panel's near edge reaches INNER_OVERLAP deep into the corner
    # bracket's own kept border (which spans corner_x-cw to corner_x-cw+
    # CORNER_PANEL_BORDER) - a genuine, comfortable overlap rather than a
    # hairline touch, see INNER_OVERLAP's comment for why.
    inner_x = (corner_x - cw + INNER_OVERLAP) + inner_iw
    inner_z = (corner_z - ch + INNER_OVERLAP) + inner_ih
    inner_mesh = _build_panel_frame_mesh(INNER_PANEL_W, INNER_PANEL_H, INNER_PANEL_BORDER, bevel=0.0)

    side_mesh = _build_panel_frame_mesh(CENTER_PANEL_SIZE, CENTER_PANEL_SIZE, CENTER_PANEL_BORDER, rotate_deg=45.0)
    mid_mesh = _build_panel_frame_mesh(CENTER_PANEL_MID_SIZE, CENTER_PANEL_MID_SIZE, CENTER_PANEL_BORDER, rotate_deg=45.0)

    # Each decoration level gets its own join+union pass against the
    # (already-solid) result of the previous pass, rather than joining all
    # the pieces into one giant cutter for a single union - joining that
    # many overlapping-by-design pieces at once reliably made Blender's
    # EXACT solver drop the base plinth entirely and keep only stray
    # decoration fragments, even once every individual pairwise overlap
    # was made safe. Smaller, same-type batches per pass is far more
    # robust.
    main_stamps = []
    center_stamps = []
    corner_stamps = []
    inner_stamps = []
    for dx, dy in FACE_DIRS:
        _place_decor(main_stamps, mesh, f"panel_{dx}_{dy}", dx, dy, z, hw, PANEL_HEIGHT, PANEL_EMBED)
        # Chain of 3 diamonds along the face's tangent axis, center one
        # bigger, each overlapping its neighbor by design (see
        # CENTER_CHAIN_SPACING). Resolved into ONE clean solid via
        # sequential pairwise booleans here, rather than joining all 3
        # raw (mutually overlapping, not boolean-combined) objects
        # straight into center_stamps: that plain join produces a
        # self-intersecting mesh which, fed into the final union pass
        # against the (by then already complex) plinth base, reliably
        # unioned to something non-empty but with the diamonds
        # themselves missing from the visible result - a partial,
        # silent corruption rather than an outright failure. Resolving
        # the chain's own internal overlaps first, while it's still
        # simple, sidesteps that.
        mid_stamp = []
        _place_decor(mid_stamp, mid_mesh, f"centerpanel_{dx}_{dy}_mid", dx, dy, z, hw, PLINTH_DECOR_HEIGHT, PANEL_EMBED)
        chain = mid_stamp[0]
        for side in (-1, 1):
            side_stamp = []
            _place_decor(
                side_stamp, side_mesh, f"centerpanel_{dx}_{dy}_{side}", dx, dy, z, hw,
                PLINTH_DECOR_HEIGHT, PANEL_EMBED, tangent_offset=side * CENTER_CHAIN_SPACING,
            )
            apply_boolean(chain, side_stamp[0], 'UNION')
        center_stamps.append(chain)
        for sign_x in (-1, 1):
            for sign_z in (-1, 1):
                bracket = _build_corner_panel_bracket_mesh(sign_x, sign_z)
                _place_decor(
                    corner_stamps, bracket, f"cornerpanel_{dx}_{dy}_{sign_x}_{sign_z}",
                    dx, dy, z + sign_z * corner_z, hw, PLINTH_DECOR_HEIGHT, PANEL_EMBED,
                    tangent_offset=sign_x * corner_x,
                )
                _place_decor(
                    inner_stamps, inner_mesh, f"innerpanel_{dx}_{dy}_{sign_x}_{sign_z}",
                    dx, dy, z + sign_z * inner_z, hw, PLINTH_DECOR_HEIGHT, PANEL_EMBED,
                    tangent_offset=sign_x * inner_x,
                )

    for stamps in (main_stamps, corner_stamps, inner_stamps, center_stamps):
        _union_decor(obj, stamps)
    return obj


_diamond_mesh_cache = None


def _build_diamond_mesh():
    """Cached (built once) small flat diamond/rhombus. Hand-built with
    explicit vertex positions - primitive_cone_add(vertices=4)'s default
    rotation didn't give the expected orientation (still read as square),
    and rather than guess again at what Blender's default actually is,
    placing the 4 corners directly removes that ambiguity entirely.
    Asymmetric DIAMOND_WIDTH/TALL also makes the result unambiguously a
    diamond rather than a square regardless of viewing angle. Same
    canonical local frame as everything else (front cap at local
    Y=-depth/2, extruded to Y=+depth/2)."""
    global _diamond_mesh_cache
    if _diamond_mesh_cache is not None:
        return _diamond_mesh_cache

    depth = DIAMOND_HEIGHT + DIAMOND_EMBED
    hw, hh = DIAMOND_WIDTH / 2, DIAMOND_TALL / 2

    bm = bmesh.new()
    top = bm.verts.new((0.0, -depth / 2, hh))
    right = bm.verts.new((hw, -depth / 2, 0.0))
    bottom = bm.verts.new((0.0, -depth / 2, -hh))
    left = bm.verts.new((-hw, -depth / 2, 0.0))
    face = bm.faces.new((top, right, bottom, left))

    extruded = bmesh.ops.extrude_face_region(bm, geom=[face])
    new_verts = [g for g in extruded['geom'] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=new_verts, vec=(0, depth, 0))

    mesh = bpy.data.meshes.new("diamond")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

    _diamond_mesh_cache = mesh
    return mesh


def emboss_face_diamonds(obj, height):
    """2 vertical strips of small flat diamonds per face, inset
    DIAMOND_STRIP_INSET from the edges rather than sitting on them - the
    shaft gets cut through the corners, so anything on the edge would get
    sliced in half. Placed via the same tangent_offset mechanism as
    everything else, but with their own shallow DIAMOND_HEIGHT/EMBED
    rather than the rune's - see DIAMOND_HEIGHT comment for why."""
    mesh = _build_diamond_mesh()

    stamps = []
    z = DIAMOND_MARGIN_BOTTOM
    top_z = height - DIAMOND_MARGIN_TOP
    while z <= top_z:
        for dx, dy in FACE_DIRS:
            hw = outer_half_width(z, height)
            strip_offset = hw - DIAMOND_STRIP_INSET
            for side in (-1, 1):
                _place_decor(
                    stamps, mesh, f"diamond_{dx}_{dy}_{side}_{z:.1f}",
                    dx, dy, z, hw, DIAMOND_HEIGHT, DIAMOND_EMBED,
                    tangent_offset=side * strip_offset,
                )
        z += DIAMOND_SPACING

    return _union_decor(obj, stamps)


# ============================================================
# BUILD + EXPORT
# ============================================================

def build_and_export_shaft_set(seed, x_offset):
    """Shaft + spire: decorate the shaft, union the spire on (no more "leave
    a cap for it to sit on" bookkeeping needed once they're just going to be
    cut together), then corner-cut the combined solid into 4 quarters. All
    seeds share SHAFT_HEIGHT, so any quarter from any seed's set is
    dimensionally interchangeable with any other - the "kit" is a pool of
    these to mix and match, not matched sets."""
    name = f"side_seed{seed}"
    shaft = make_solid_shaft(f"{name}_body", SHAFT_HEIGHT)
    emboss_rune_panels(shaft, SHAFT_HEIGHT, seed)
    emboss_face_diamonds(shaft, SHAFT_HEIGHT)

    spire = make_spire(f"{name}_spire", SHAFT_HEIGHT)
    apply_boolean(shaft, spire, 'UNION')

    quarters = split_shaft_into_quarters(shaft, 0.0, SHAFT_HEIGHT + SPIRE_HEIGHT, f"{name}_body")

    for obj in quarters:
        obj.location.x += x_offset

    if EXPORT_STL:
        for obj in quarters:
            export_stl(obj, f"{obj.name}.stl")

    return quarters


def build_and_export_plinth(x_offset):
    """Just one - every shaft quarter from any seed fits the same plinth,
    so there's no need for a matched plinth per shaft set any more."""
    plinth = make_plinth("plinth")
    emboss_plinth_panels(plinth)
    plinth.location.x += x_offset

    if EXPORT_STL:
        export_stl(plinth, f"{plinth.name}.stl")

    return plinth


def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    clear_scene()

    xoff = 0.0
    spacing = BASE_WIDTH * 2 + 20.0
    for seed in SHAFT_SEEDS:
        build_and_export_shaft_set(seed, xoff)
        xoff += spacing

    build_and_export_plinth(xoff)

    if RENDER_IMAGES:
        center, size = compute_scene_bounds()
        render_angles(center, size)

    print(f"Done. {len(SHAFT_SEEDS)} shaft set(s) + 1 plinth exported to {EXPORT_DIR}")


if __name__ == "__main__":
    main()
