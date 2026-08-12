"""
Prospero Brazier, WITH a modeled stone flame (Blender bpy) - standalone.

Variant of brazier.py with one addition: a cluster of stylized stone
flame "tongues" rising from the bowl, printed as part of the same solid
piece (a single-piece "lit brazier" statue) instead of leaving the flame
as a separate resin insert. Everything else - bowl, ring, glyph band,
feet - is identical to brazier.py; see that file for the rationale on
each part.

Run: Blender -> Scripting workspace -> Open this file -> Alt+P
Or headless: blender --background --python brazier_with_flame.py
"""

import bpy
import bmesh
import math
import mathutils
import os

# ============================================================
# CONFIG
# ============================================================

EXPORT_DIR = "/Users/mannil/Desktop/studio-m/TSONS/brazier/output_with_flame"
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

# Brazier assembly, in mm - 3 visually distinct parts stacked bottom to
# top, each its own primitive unioned together (not one continuous lathe
# profile): a flat solid base disc, a curved bowl body sitting on it, and
# a flat ring plate capping the rim. Feet hang below the base disc.
# Total finished height targets ~half a 28mm miniature (~32mm figure
# height), so ~14-16mm overall.
EMBED = 0.6  # overlap depth between unioned parts - avoids coincident-face
             # boolean degeneracy (see feedback_blender_boolean_fragility)

BASE_DISC_R = 6.0    # radius of the flat base disc
BASE_DISC_H = 1.0    # thickness of the flat base disc

BODY_R_BOTTOM = 5.2  # body's outer radius where it rises from the disc
BODY_R_SHOULDER = 8.0  # body's outer radius at the shoulder (top of the curve)
BODY_H = 5.0         # height of the curved body, disc top to shoulder
WALL_T = 1.3         # body wall thickness (outer - inner radius)
BOWL_PROFILE_STEPS = 10  # points along the curved body wall

LIP_R_IN = BODY_R_SHOULDER - WALL_T - 0.4  # ring's inner radius (laps onto the body's opening)
LIP_R_OUT = 8.6       # ring's outer radius - a modest overhang past the shoulder, not a big flat disc
LIP_H = 0.9           # thickness of the flat rim ring plate

BODY_STRAIGHT_H = 1.0  # short straight vertical collar at each end of the
                        # body wall, so the disc/ring overlap zones meet a
                        # constant-radius cylinder rather than the tangent
                        # (near-zero-slope) end of the eased curve - avoids
                        # coincident-ish faces that corrupt the EXACT solver

SPIN_STEPS = 128  # circle segment count for the lathed parts (disc, body,
                   # ring) - high enough that the curve prints smooth/round
                   # rather than visibly faceted at this small scale

# Feet: 4 short chunky carved-stone-block feet (tapered rectangular
# blocks, not turned pegs), diamond-oriented at the corners to match the
# reference art rather than cardinal N/S/E/W.
FOOT_COUNT = 4
FOOT_H = 2.0
FOOT_W_TOP = 2.6       # block width/depth where it meets the base disc
FOOT_W_BOTTOM = 2.0    # block width/depth at the ground (tapers inward)
FOOT_RADIAL_OFFSET = BASE_DISC_R - 1.2  # distance from center axis
FOOT_ANGLE_OFFSET_DEG = 45.0  # diamond orientation

# Stone flame cluster, rising from the bowl floor - 3 tapered "tongue"
# blades at different heights/rotations for a natural flicker look, all
# joined into one mesh before a single union (same pattern as feet/glyphs).
FLAME_TONGUES = [
    # (height, base_width, thickness, base_angle_deg, base_x_offset, base_y_offset)
    # Heights are measured from the disc floor (z=BASE_DISC_H). Dialed
    # back from an earlier too-tall/too-bulky 4x pass; each tongue is now
    # a twisted, tapered loft (see build_flame_tongue_object) rather than
    # a flat extruded blade, which is what was reading as "blocky".
    # width:thickness pushed to a more elongated, blade-like ratio so the
    # spiral twist actually reads visually (a near-circular cross-section
    # looks the same from every angle, so twisting it is invisible).
    # 2x scaled up per feedback.
    # Offsets pulled back in close: the cross-sections are wide through
    # the base/middle (large envelope) so nearby tongues genuinely fuse
    # there into one body, and only separate into distinct licks near the
    # tip where the envelope has shrunk small relative to the offset.
    # (height, width, thickness, base_angle_deg, ox, oy, curve_deg, curve_amount)
    # curve_deg/curve_amount bow the tongue's own axis out sideways in
    # the middle (peaking at half-height, anchored back to 0 at both the
    # base and the tip) rather than staying a straight vertical spike.
    # Scaled to 93% of the previous pass per feedback ("scale down ~7%").
    (44.64, 10.23, 2.42, 0.0, 0.0, 0.0, 15.0, 6.51),
    (37.20, 8.56, 2.05, 130.0, 1.67, -0.93, 160.0, 5.58),
    (31.62, 7.81, 2.05, 250.0, -1.40, 1.12, 290.0, 5.12),
]
FLAME_LEVELS = 32        # cross-section rings along the height (loft resolution) -
                          # bumped up so a bigger total twist still looks smooth
FLAME_RING_POINTS = 8    # points around each cross-section ring
FLAME_TWIST_DEG = 250    # total spiral twist from base to tip
FLAME_EMBED = 0.5  # how far the tongue base is buried into the disc floor -
                    # must stay well short of BASE_DISC_H (1.0mm) so the
                    # flame's bottom cap doesn't land coincident with the
                    # disc's own bottom face (a degenerate coplanar boolean)

# Rim glyph band: reuses the same pixel-mask emboss technique as
# runes/rune_panel_v1_plain.py, wrapped around the body's outer wall
# instead of stamped onto a flat panel. One glyph per GLYPH_POOL entry,
# evenly spaced around the full circle.
GLYPH_DIR = "/Users/mannil/Desktop/studio-m/TSONS/assets/rune_marks"
GLYPH_POOL = [
    "manifestation", "decay", "binding", "chaos", "cycle", "void",
    "dominion", "earth", "entropy", "fire", "flow", "will",
    "life", "growth", "transcendence", "sacred",
]

# Glyphs are cut (engraved) into the ring's flat TOP face, in the
# annulus between LIP_R_IN and LIP_R_OUT - not embossed on the body wall.
RIM_GLYPH_W = 2.0    # glyph footprint width (tangential direction), mm
RIM_GLYPH_H = 2.2    # glyph footprint height (radial direction), mm - must
                     # fit inside the ring's annulus width (LIP_R_OUT-LIP_R_IN)
RIM_GLYPH_CUT_DEPTH = 0.4     # how deep the engraving cuts into the ring
RIM_GLYPH_CUT_CLEARANCE = 0.3  # how far the cutter pokes above the top face

RUNE_ALPHA_THRESHOLD = 0.15
RUNE_STROKE_DILATE = 1
MASK_SUPERSAMPLE = 6
MASK_BLUR_RADIUS = 8
MESH_SMOOTH_ITERATIONS = 3
MESH_SMOOTH_FACTOR = 0.5


# ============================================================
# HELPERS (shared conventions - see runes/rune_panel_v1_plain.py)
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

    distance = size * 4.0
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


# ============================================================
# BOWL
# ============================================================

def _smoothstep(t):
    return t * t * (3 - 2 * t)


def _curved_wall_points(r_bottom, r_top, z_bottom, z_top, steps):
    """Sample points along a smoothstep-eased curve from (r_bottom,
    z_bottom) to (r_top, z_top) - an S-curve that starts and ends nearly
    vertical/horizontal, giving a rounded basin profile instead of a
    straight cone side."""
    pts = []
    for i in range(steps + 1):
        t = i / steps
        te = _smoothstep(t)
        r = r_bottom + (r_top - r_bottom) * te
        z = z_bottom + (z_top - z_bottom) * t
        pts.append((r, z))
    return pts


def _spin_profile(profile, name, steps=SPIN_STEPS):
    """Revolve a closed (r, z) profile loop 360 degrees around the Z axis
    into a solid/shell mesh object."""
    bm = bmesh.new()
    verts = [bm.verts.new((r, 0.0, z)) for r, z in profile]
    edges = [bm.edges.new((verts[i], verts[i + 1])) for i in range(len(verts) - 1)]
    bmesh.ops.spin(
        bm, geom=verts + edges, axis=(0, 0, 1), cent=(0, 0, 0),
        steps=steps, angle=math.radians(360), use_merge=True,
    )
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def build_base_disc():
    """Flat solid disc - the base plate the body sits on and the feet
    hang from. A plain filled cylinder, built via spin of a simple
    rectangular profile (center axis at bottom -> outer edge -> up ->
    back to center axis at top) so it comes out solid, not a shell."""
    profile = [
        (0.0, 0.0),
        (BASE_DISC_R, 0.0),
        (BASE_DISC_R, BASE_DISC_H),
        (0.0, BASE_DISC_H),
    ]
    return _spin_profile(profile, "base_disc")


def build_body():
    """Curved bowl-body shell: a thin tube wall (outer curve up, thin cap
    across the top, inner curve back down, thin cap across the bottom) -
    a closed ring cross-section revolved, so it comes out as a proper
    hollow tube not touching the axis. Bottom overlaps EMBED into the
    base disc; top is the shoulder where the rim ring sits - both ends
    have a short straight (constant-radius) collar so the overlap zone
    meets a plain cylinder, not the tangent end of the eased curve."""
    z_bot = BASE_DISC_H - EMBED
    z_top = BASE_DISC_H + BODY_H
    z_curve_start = z_bot + BODY_STRAIGHT_H
    z_curve_end = z_top - BODY_STRAIGHT_H

    r_out_bot = BODY_R_BOTTOM
    r_out_top = BODY_R_SHOULDER
    r_in_bot = r_out_bot - WALL_T
    r_in_top = r_out_top - WALL_T

    outer = [(r_out_bot, z_bot), (r_out_bot, z_curve_start)]
    outer += _curved_wall_points(r_out_bot, r_out_top, z_curve_start, z_curve_end, BOWL_PROFILE_STEPS)[1:]
    outer += [(r_out_top, z_top)]

    inner = [(r_in_bot, z_bot), (r_in_bot, z_curve_start)]
    inner += _curved_wall_points(r_in_bot, r_in_top, z_curve_start, z_curve_end, BOWL_PROFILE_STEPS)[1:]
    inner += [(r_in_top, z_top)]

    profile = outer + list(reversed(inner))
    profile.append(profile[0])  # close the loop back to the outer-bottom start
    return _spin_profile(profile, "body")


def build_rim_ring():
    """Flat ring plate (a washer): rectangular cross-section, flat top
    and bottom, revolved - sits capping the body's opening. Its bottom
    overlaps EMBED into the body's shoulder."""
    z_bot = BASE_DISC_H + BODY_H - EMBED
    z_top = z_bot + EMBED + LIP_H
    profile = [
        (LIP_R_IN, z_bot),
        (LIP_R_OUT, z_bot),
        (LIP_R_OUT, z_top),
        (LIP_R_IN, z_top),
        (LIP_R_IN, z_bot),
    ]
    return _spin_profile(profile, "rim_ring")


def _add_foot_to_bmesh(bm, cx, cy):
    """Add one chunky tapered rectangular block (truncated pyramid) to an
    existing bmesh, centered at (cx, cy) - reads as a distinct
    carved-stone foot rather than a turned peg. Top face sits at z=EMBED
    (overlapping up into the base disc); it hangs down to the ground at
    z=EMBED-FOOT_H."""
    top_z = EMBED
    bot_z = EMBED - FOOT_H
    ht, hb = FOOT_W_TOP / 2, FOOT_W_BOTTOM / 2

    top_verts = [
        bm.verts.new((cx - ht, cy - ht, top_z)), bm.verts.new((cx + ht, cy - ht, top_z)),
        bm.verts.new((cx + ht, cy + ht, top_z)), bm.verts.new((cx - ht, cy + ht, top_z)),
    ]
    bot_verts = [
        bm.verts.new((cx - hb, cy - hb, bot_z)), bm.verts.new((cx + hb, cy - hb, bot_z)),
        bm.verts.new((cx + hb, cy + hb, bot_z)), bm.verts.new((cx - hb, cy + hb, bot_z)),
    ]

    bm.faces.new(top_verts)
    bm.faces.new(reversed(bot_verts))
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((top_verts[i], top_verts[j], bot_verts[j], bot_verts[i]))


def build_all_feet():
    """All 4 feet combined into ONE mesh/object (built directly in one
    bmesh, not joined via separate boolean unions per foot) - so the
    brazier only needs a single feet-union boolean instead of 4 chained
    ones, which is what was corrupting one foot's geometry (see
    feedback_blender_boolean_fragility: long boolean chains are fragile)."""
    bm = bmesh.new()
    for i in range(FOOT_COUNT):
        angle = math.radians(FOOT_ANGLE_OFFSET_DEG + i * (360.0 / FOOT_COUNT))
        x = FOOT_RADIAL_OFFSET * math.cos(angle)
        y = FOOT_RADIAL_OFFSET * math.sin(angle)
        _add_foot_to_bmesh(bm, x, y)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("feet")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("feet", mesh)
    bpy.context.collection.objects.link(obj)
    return obj


# ============================================================
# RIM GLYPH BAND (pixel-mask emboss, adapted from
# runes/rune_panel_v1_plain.py for a small curved band instead of a flat
# panel - see that file for the technique's full rationale)
# ============================================================

def load_glyph_mask(glyph_name):
    path = os.path.join(GLYPH_DIR, f"rune_{glyph_name}_mark.png")
    img = bpy.data.images.load(path, check_existing=True)
    w, h = img.size
    px = img.pixels[:]
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
    return mask, w, h


def upscale_and_smooth_mask(mask, w, h, factor, radius):
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


def build_glyph_stamp_mesh(glyph_name, depth, glyph_w, glyph_h):
    """Build one glyph's emboss bump, symmetric around local Y=0 (spans
    -depth/2..+depth/2), centered on its own local origin in X/Z - same
    construction as runes/rune_panel_v1_plain.py's version, parameterized
    by footprint size instead of the fixed RUNE_W/RUNE_H there."""
    mask, w, h = load_glyph_mask(glyph_name)

    bm = bmesh.new()
    vert_grid = {}

    def get_vert(gx, gz):
        key = (gx, gz)
        if key not in vert_grid:
            lx = (gx / w - 0.5) * glyph_w
            lz = (gz / h - 0.5) * glyph_h
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

    mesh = bpy.data.meshes.new(f"glyph_{glyph_name}")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(mesh.name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def build_rim_glyph_band():
    """One glyph cutter per GLYPH_POOL entry, engraved into the ring's
    flat TOP face around the annulus between LIP_R_IN and LIP_R_OUT (not
    embossed on the body wall). Each stamp's local axes are remapped via
    an explicit rotation matrix - local X (glyph width) -> tangential,
    local Z (glyph height) -> radially outward, local Y (depth) -> world
    -Z (so it cuts down into the top face) - rather than composing
    euler rotations, which only works for rotation about a single shared
    axis. All stamps are joined into ONE object before a single boolean
    DIFFERENCE against the base (same "combine before union" fix used
    for the feet)."""
    z_top = BASE_DISC_H + BODY_H + LIP_H  # ring's flat top surface
    radius = (LIP_R_IN + LIP_R_OUT) / 2

    depth = RIM_GLYPH_CUT_DEPTH + RIM_GLYPH_CUT_CLEARANCE
    # local Y=0 (the stamp's own mid-plane) should sit at world Z so the
    # cut extends CUT_CLEARANCE above the surface and CUT_DEPTH below it.
    z_center = z_top + (RIM_GLYPH_CUT_CLEARANCE - RIM_GLYPH_CUT_DEPTH) / 2

    count = len(GLYPH_POOL)
    stamps = []
    for i, glyph_name in enumerate(GLYPH_POOL):
        angle = math.radians(i * (360.0 / count))
        tangent = mathutils.Vector((-math.sin(angle), math.cos(angle), 0.0))
        outward = mathutils.Vector((math.cos(angle), math.sin(angle), 0.0))
        down = mathutils.Vector((0.0, 0.0, -1.0))

        stamp = build_glyph_stamp_mesh(glyph_name, depth, RIM_GLYPH_W, RIM_GLYPH_H)
        rot = mathutils.Matrix((
            (tangent.x, down.x, outward.x),
            (tangent.y, down.y, outward.y),
            (tangent.z, down.z, outward.z),
        )).to_4x4()
        loc = mathutils.Vector((radius * math.cos(angle), radius * math.sin(angle), z_center))
        stamp.matrix_world = mathutils.Matrix.Translation(loc) @ rot

        bpy.context.view_layer.objects.active = stamp
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=False)
        stamps.append(stamp)

    bpy.ops.object.select_all(action='DESELECT')
    for s in stamps:
        s.select_set(True)
    bpy.context.view_layer.objects.active = stamps[0]
    bpy.ops.object.join()
    return stamps[0]


# ============================================================
# FLAME (stone flame cluster)
# ============================================================

def _flame_envelope(t):
    """Width/thickness scale factor (0..1) along the flame's height
    fraction t: starts at a small-but-nonzero base radius (never a true
    zero-radius ring, which would give a degenerate loft face), rises to
    a modest peak low down, then tapers off steadily toward the tip - a
    slender flame-lick profile, not a fat bulge in the middle."""
    if t <= 0.15:
        return 0.15 + (0.9 - 0.15) * (t / 0.15)
    u = (t - 0.15) / 0.85
    return max(0.05, 0.9 * (1 - u) ** 1.3)


def build_flame_tongue_object(height, width, thickness, angle_deg, ox, oy, curve_deg, curve_amount):
    """Build one solid flame-tongue as its own bpy object: a stack of
    small elliptical cross-section rings, each scaled down by
    _flame_envelope and rotated a bit further than the last (a spiral
    twist from base to tip), bridged into a loft. This is what actually
    breaks up the flat, blocky look of a simple extruded blade - a
    single constant cross-section extrusion reads as a slab no matter
    how much its silhouette is smoothed or tapered; a twisting, shrinking
    stack of rings reads as an organic, flickering flame shape.

    Each ring's center is also bowed sideways by curve_amount*sin(pi*t) -
    zero at the base and tip, peaking at half-height - so the tongue's
    own axis curves in the middle instead of running dead straight."""
    bm = bmesh.new()
    rings = []
    curve_dir = math.radians(curve_deg)
    curve_cos, curve_sin = math.cos(curve_dir), math.sin(curve_dir)
    for i in range(FLAME_LEVELS + 1):
        t = i / FLAME_LEVELS
        z = t * height
        env = _flame_envelope(t)
        hw = (width / 2) * env
        ht = (thickness / 2) * env
        twist = math.radians(angle_deg + FLAME_TWIST_DEG * t)
        cos_tw, sin_tw = math.cos(twist), math.sin(twist)

        bow = curve_amount * math.sin(math.pi * t)
        cx = ox + bow * curve_cos
        cy = oy + bow * curve_sin

        ring = []
        for j in range(FLAME_RING_POINTS):
            phi = 2 * math.pi * j / FLAME_RING_POINTS
            lx, ly = hw * math.cos(phi), ht * math.sin(phi)
            rx = lx * cos_tw - ly * sin_tw
            ry = lx * sin_tw + ly * cos_tw
            ring.append(bm.verts.new((rx + cx, ry + cy, z + BASE_DISC_H - FLAME_EMBED)))
        rings.append(ring)

    for i in range(FLAME_LEVELS):
        r0, r1 = rings[i], rings[i + 1]
        for j in range(FLAME_RING_POINTS):
            a, b = r0[j], r0[(j + 1) % FLAME_RING_POINTS]
            c, d = r1[j], r1[(j + 1) % FLAME_RING_POINTS]
            bm.faces.new((a, b, d, c))

    bm.faces.new(rings[0])              # base cap
    bm.faces.new(list(reversed(rings[-1])))  # tip cap (tiny - reads as a point)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("flame_tongue")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(mesh.name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def build_flame():
    """The 3 flame tongues genuinely overlap near their base (that's the
    intended clustered-flicker look), so they can't just be concatenated
    into one mesh like the feet/glyphs (which never touch each other) -
    a self-intersecting, multi-shell cutter is exactly the "multi-piece
    cutter" case that corrupts the EXACT solver (see
    feedback_blender_boolean_fragility). Instead, union them into each
    other for real (only 2 operations, low risk) so the result is one
    clean, non-self-intersecting solid before the final union onto the
    base."""
    tongues = [build_flame_tongue_object(*t) for t in FLAME_TONGUES]
    flame = tongues[0]
    for other in tongues[1:]:
        apply_boolean(flame, other, 'UNION')
    flame.name = "flame"
    return flame


def build_brazier():
    base = build_base_disc()

    body = build_body()
    apply_boolean(base, body, 'UNION')

    rim = build_rim_ring()
    apply_boolean(base, rim, 'UNION')

    feet = build_all_feet()
    apply_boolean(base, feet, 'UNION')

    glyph_band = build_rim_glyph_band()
    apply_boolean(base, glyph_band, 'DIFFERENCE')

    flame = build_flame()
    apply_boolean(base, flame, 'UNION')

    base.name = "brazier"
    return base


# ============================================================
# MAIN
# ============================================================

def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    clear_scene()

    bowl = build_brazier()

    total_h = BASE_DISC_H + BODY_H + LIP_H
    print(f"Brazier built: disc H={BASE_DISC_H}mm + body H={BODY_H}mm + lip H={LIP_H}mm "
          f"= {total_h}mm above ground, plus {FOOT_H}mm feet, rim outer dia={LIP_R_OUT * 2}mm")

    if EXPORT_STL:
        export_stl(bowl, "brazier.stl")

    if RENDER_IMAGES:
        center, size = compute_scene_bounds()
        render_angles(center, size)

    print("Done.")


if __name__ == "__main__":
    main()
