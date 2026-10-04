#!/usr/bin/env python3
"""Portable Hellforge — box corner trim, wraps the actual 3D corner, v2.

Blender/bpy script - paste into the Script Editor and run (Alt+P), or:
  blender --background --python box_corner_trim.py

v1 (corner_trim.py) was a flat 2D L-bracket glued onto one face only -
rivets and a chain loop, but no real wrap. Feedback: drop the rivets/loop
(not selling the look), keep the rune, and make it actually wrap the
corner like the exterior concept sketch shows (a metal cap folding from
the lid's top face down onto the adjacent side face).

Rather than re-deriving that from scratch, adapted directly from
content/projects/thousands-sons/pyramid/trim_corner_v1_plain.py - a
proven 3-panel (TOP/FRONT/RIGHT) box-corner cap from the Prospero terrain
project. Its own docstring documents exactly the failure mode worth
avoiding here: an earlier "V-fold arms" version had TOP and RIGHT each
touching FRONT, but never touching EACH OTHER - no real 3-sided pocket,
however the decoration was arranged, because 2 of the 3 panel pairs never
shared a genuine edge. Fixed there (and reused as-is here) with a hub-
and-arms construction: each panel is a small hub at the vertex plus two
long arms continuing out along its two shared edges, with a real
EDGE_OVERLAP (not a knife-edge touch) at every seam - the same "overlap,
don't just touch" lesson as this project's own gap-connector fix on the
bull icon's horn/bridge pieces, just already solved once before.

Box convention (vertex at world origin, carried over unchanged from the
source script - it was verified there with an actual boolean-collision
test against a stand-in box, not hand-derived, so reusing the convention
inherits that verification rather than re-risking the same mistake):
box interior occupies X<=0, Y>=0, Z<=0. TOP panel sits proud in +Z (glued
to the box's top face), FRONT proud in -Y, RIGHT proud in +X.

Only 2 changes from the source pattern: PANEL_THICKNESS/reach values
retuned for this box's scale (not a terrain piece), and the rail
decoration is replaced with an engraved rune (reuses rune_contours.json,
same as hashut_rune_icon.py / corner_trim.py v1) on the TOP panel only,
near the hub. Engraved, not raised - a proud detail there would be a
snag/wear point, scraping other surfaces and getting worn/dented itself.
"""
import bpy
import bmesh
import json
import math
import mathutils
import os
import zipfile

# ============================================================
# CONFIG (all mm)
# ============================================================
RUNE_CONTOURS_PATH = "/Users/mannil/studio-m/blender/tokens/rune_contours.json"
EXPORT_DIR = "/Users/mannil/studio-m/blender/hellforge/output_corner_trim"
EXPORT_STL = True
EXPORT_3MF = True

# Multi-color print, same technique as blender/tokens/build_tokens.py
# (which already worked this out for the Anycubic printer): CAP_COLOR is
# a render-preview-only placeholder for whatever the bracket's own
# filament actually is; INSERT_COLOR is the rune's contrasting color -
# green, matching the tokens project's own established color for every
# icon/text inlay across the whole army-accessory line, not just picked
# fresh here. Swap to black by flipping the comment if that's preferred.
CAP_COLOR = (0.15, 0.15, 0.17, 1.0)     # dark gunmetal placeholder - not a real material choice
INSERT_COLOR = (0.06, 0.45, 0.12, 1.0)  # green - same value as build_tokens.py's INLAY_COLOR
# INSERT_COLOR = (0.02, 0.02, 0.02, 1.0)  # black, if preferred over green

# Anycubic Slicer Next ignores the standard 3MF color hint entirely and
# only reads its own project-3mf `extruder` metadata per part - same
# finding as build_tokens.py's own export_project_3mf docstring. Edit
# these to match your ACE Gen2/AMS loadout on the day you slice.
CAP_EXTRUDER_SLOT = 1
INSERT_EXTRUDER_SLOT = 2

RENDER_IMAGES = True
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1600, 900)
RENDER_ANGLES = {"iso_a": (0.8, -0.9, 0.6), "iso_b": (-0.8, 0.9, -0.6)}

CORNER_REACH = 18.0       # hub half-size where all 3 panels actually meet and cover the vertex
ARM_REACH_TOP = 70.0      # how far the TOP panel's own arms (and FRONT/RIGHT's horizontal arms) reach
                          # along the top face - not limited by lid thickness, so left as-is
ARM_REACH_DOWN = 25.4     # 1 inch - the lid's actual wall thickness, so this is a hard max, not a
                          # guess: FRONT/RIGHT's vertical (Z) arms can't wrap further down than the
                          # lid itself is tall before they'd run onto the box's lower half
PANEL_THICKNESS = 5.0     # was 2.5mm (matched the thin icon appliques) - this piece needs real
                          # structural presence as a corner guard, not just a cosmetic plaque
EDGE_OVERLAP = 1.5        # real structural overlap at every panel-to-panel seam - proven value, reused as-is
OVERSHOOT = 1.0           # generic cutter overshoot, so a DIFFERENCE cut always clears the real surface

BOX_BEVEL_WIDTH = 2.0    # was 0.8mm (a thin chamfer, read as a stepped "lip" not a round) - a forged
                         # smith piece wants a true round-over, not a flat angled facet
BOX_BEVEL_SEGMENTS = 6   # was 2 (a hard 2-facet chamfer) - more segments approximates a smooth
                         # quarter-round rather than a visible facet line

RUNE_TARGET_W = 13.0
# 2-color print: the rune is a SEPARATE insert (its own STL, printed in a
# different color/material - black/green per the request) glued into a
# socket cut into the main bracket, not a shallow surface engrave. Same
# proven insert/pocket technique as build_tokens.py (INSERT_DEPTH/
# POCKET_POKE values reused as-is from there) - flush with the surface
# either way, so it still can't scrape/dent anything once glued in.
RUNE_INSERT_DEPTH = 0.6   # flush insert thickness
RUNE_POCKET_POKE = 0.4    # how much deeper the socket cutter reaches past the insert's own depth,
                          # so the insert seats fully without bottoming out on a tight boolean seam
# centered inside the TOP hub's own footprint (x in [-CORNER_REACH,0], y
# in [0,CORNER_REACH]) - inset so the rune doesn't hang off either edge
RUNE_CENTER_XY = (-CORNER_REACH * 0.55, CORNER_REACH * 0.55)


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


def make_panel(x_range, y_range, z_range, name):
    """Box spanning the given [min,max] ranges on each axis - same helper
    as trim_corner_v1_plain.py's, unchanged."""
    cx, cy, cz = (x_range[0] + x_range[1]) / 2, (y_range[0] + y_range[1]) / 2, (z_range[0] + z_range[1]) / 2
    sx, sy, sz = x_range[1] - x_range[0], y_range[1] - y_range[0], z_range[1] - z_range[0]
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True, location=False, rotation=False)
    obj.location = (cx, cy, cz)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    return obj


def bevel_box_edges(obj, width, segments):
    """Modifier-based bevel with an ANGLE limit_method, not the raw bmesh
    operator the source TSONS script used (that version beveled EVERY
    edge, geom=bm.edges[:] - switched away from it first, see git history
    of this file, but that alone turned out not to be the actual fix).

    use_clamp_overlap=False matters just as much: even with ANGLE limiting
    the SELECTED edges to the real outer silhouette, Blender's clamp logic
    still checks the wider local neighborhood - including the internal
    hub/arm union seams (near-flat, ~180 degrees, but geometrically short
    since EDGE_OVERLAP is only 1.5mm) - and clamped the outer bevel's
    width down to avoid touching them, even though they were never
    selected for beveling themselves. Silent: no error, `modifier_apply`
    returns FINISHED either way. Caught by isolating the two flags on a
    FRESH copy of the pristine mesh and comparing volumes directly - width
    2.0mm/segments 6 with clamp on produced a ~0.07mm3 change (i.e.
    nothing); the exact same call with clamp off produced a real
    ~630mm3 change. Re-verify shell count/non-manifold edges after this
    change too - clamp_overlap exists to prevent self-intersecting bevels,
    so turning it off needs checking, not just trusting the volume moved."""
    mod = obj.modifiers.new("Bevel", 'BEVEL')
    mod.width = width
    mod.segments = segments
    mod.use_clamp_overlap = False
    mod.limit_method = 'ANGLE'
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def dedupe_closed_loop(points, tol=1e-9):
    if len(points) > 1:
        x0, y0 = points[0]
        x1, y1 = points[-1]
        if abs(x0 - x1) < tol and abs(y0 - y1) < tol:
            return points[:-1]
    return points


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


def _rune_points(compensate_deg=0.0):
    """compensate_deg rotates the rune IN PLACE around its own pivot
    (RUNE_CENTER_XY), before the surrounding bracket's own whole-piece
    Z-rotation is applied later. Needed because the rune's ABSOLUTE
    orientation is meant to stay the same on all 4 corners (confirmed:
    not "consistent relative to its own corner" - that reads as identical
    rune shapes rotating right along with each differently-rotated
    bracket, which is what pure whole-piece rotation alone gives you, and
    isn't what was wanted). Pre-rotating the rune by -z_deg here, before
    the corner's own +z_deg gets applied to the whole assembled piece,
    cancels out to a fixed final absolute angle regardless of which
    corner. This is why the rune has to be rebuilt (the pocket re-cut)
    per corner, not just rigidly transformed after the fact like the rest
    of the piece - it's baked into the cap's own geometry, not a separate
    rigid attachment."""
    with open(RUNE_CONTOURS_PATH) as f:
        contours = json.load(f)
    outer = [c for c in contours if not c["hole"]]
    xs = [p[0] for p in outer[0]["points"]]
    ys = [p[1] for p in outer[0]["points"]]
    bbox_w, bbox_h = max(xs) - min(xs), max(ys) - min(ys)
    bbox_cx, bbox_cy = (max(xs) + min(xs)) / 2.0, (max(ys) + min(ys)) / 2.0
    scale = RUNE_TARGET_W / bbox_w
    rune_h = bbox_h * scale
    ox = RUNE_CENTER_XY[0] - bbox_cx * scale
    oy = RUNE_CENTER_XY[1] - bbox_cy * scale
    pts = dedupe_closed_loop([(u * scale + ox, v * scale + oy) for u, v in outer[0]["points"]])
    if compensate_deg:
        pcx, pcy = RUNE_CENTER_XY
        deg = compensate_deg % 360
        if deg % 90 == 0:
            # all 4 corners use exact multiples of 90 - do this as a plain
            # coordinate swap/negate instead of cos/sin. The trig version
            # left a ~1e-14 residue at 90/180 (not 0/270, direction-of-
            # rounding dependent) that was just large enough to make the
            # rune pocket cutter's OVERSHOOT wall not fully coincide with
            # itself across the EXACT boolean, leaving a real 1mm-tall
            # leftover rim/wall baked into the shell at the rune's footprint
            # (found via zmin/extreme-vertex inspection - not a separate
            # island, so remove_small_islands never caught it). Exact
            # 90-degree steps need zero numerical residue to cancel
            # perfectly, so skip trig entirely for this case.
            k = int(deg // 90)
            pts = [(x, y) for x, y in pts]
            for _ in range(k):
                pts = [(pcx - (y - pcy), pcy + (x - pcx)) for x, y in pts]
        else:
            ang = math.radians(compensate_deg)
            ca, sa = math.cos(ang), math.sin(ang)
            pts = [(pcx + (x - pcx) * ca - (y - pcy) * sa,
                    pcy + (x - pcx) * sa + (y - pcy) * ca) for x, y in pts]
    return pts, rune_h


def build_rune_insert(compensate_deg=0.0):
    """The rune as its own separate flush plug - printed in a different
    color/material (black/green) and glued into the socket
    build_rune_pocket_cutter() cuts. Flush with the surface either way
    (not proud, not recessed once glued) - see RUNE_INSERT_DEPTH."""
    pts, rune_h = _rune_points(compensate_deg)
    z0 = PANEL_THICKNESS - RUNE_INSERT_DEPTH
    insert = build_slab(pts, z0, PANEL_THICKNESS, "rune_insert")
    return insert, rune_h


def build_rune_pocket_cutter(compensate_deg=0.0):
    """Same footprint as the insert, but reaches RUNE_POCKET_POKE deeper
    (so the insert seats fully rather than bottoming out on a tight
    boolean seam) and pokes OVERSHOOT above the surface for a clean
    DIFFERENCE cut."""
    pts, _ = _rune_points(compensate_deg)
    z0 = PANEL_THICKNESS - RUNE_INSERT_DEPTH - RUNE_POCKET_POKE
    cutter = build_slab(pts, z0, PANEL_THICKNESS + OVERSHOOT, "rune_pocket_cutter")
    return cutter


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


def render_angles(objs, prefix=""):
    """prefix distinguishes multiple render_angles() calls in one run -
    without it every call overwrites the same iso_a.png/iso_b.png (caught
    by only ever finding the LAST of 3 calls' output on disk, not
    assumed)."""
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
    for name, direction in RENDER_ANGLES.items():
        cam_obj.location = center + mathutils.Vector(direction).normalized() * max(size * 1.8, 20.0)
        scene.render.filepath = os.path.join(RENDER_DIR, f"{prefix}{name}.png")
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


def apply_color(obj, name, rgba):
    """Viewport/render-only material so preview renders show the intended
    two-color look - has no bearing on the exported geometry. Reused
    verbatim from build_tokens.py's own apply_color."""
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


def export_3mf(parts, path):
    """Portable 3MF with a standard <colorgroup> color hint - reused
    verbatim from build_tokens.py's own export_3mf (itself adapted from
    ~/best/site's scout-name-tags project). Keeps both parts in one
    coordinate space so their relative alignment survives import (a
    slicer auto-centers independently-imported STLs, which would break
    the cap/insert fit). `parts` is a list of (obj, (r,g,b,a), name)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    colors, color_index = [], {}

    def color_id(rgba):
        key = tuple(round(c, 4) for c in rgba)
        if key not in color_index:
            color_index[key] = len(colors)
            colors.append(key)
        return color_index[key]

    objects_xml, build_items = [], []
    next_id = 2
    for obj, rgba, name in parts:
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
        obj_id = next_id
        next_id += 1
        objects_xml.append(
            f'<object id="{obj_id}" name="{name}" type="model" pid="1" pindex="{color_id(rgba)}">'
            f'<mesh><vertices>{verts_xml}</vertices>'
            f'<triangles>{tris_xml}</triangles></mesh></object>'
        )
        build_items.append(f'<item objectid="{obj_id}"/>')

    colors_xml = "".join(
        f'<m:color color="#{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}{int(a*255):02X}"/>'
        for (r, g, b, a) in colors
    )
    model_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
        'xmlns:m="http://schemas.microsoft.com/3dmanufacturing/material/2015/02">'
        f'<resources><m:colorgroup id="1">{colors_xml}</m:colorgroup>'
        f'{"".join(objects_xml)}</resources>'
        f'<build>{"".join(build_items)}</build></model>'
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
        '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        '</Relationships>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("3D/3dmodel.model", model_xml)
    print(f"Exported {path}")


def export_project_3mf(parts, path):
    """Anycubic Slicer Next's own project-3mf flavor (Bambu Studio/
    OrcaSlicer lineage: Metadata/model_settings.config) - reused verbatim
    from build_tokens.py's own export_project_3mf. That slicer ignores the
    standard 3MF color hint entirely (both <basematerials> and
    <colorgroup> came back flat/same-color on import there) and only
    reads its own `extruder` metadata per part, referencing whatever
    filament is physically loaded in that numbered slot - see
    CAP_EXTRUDER_SLOT/INSERT_EXTRUDER_SLOT. This is the file that
    actually works on that printer; the plain export_3mf above is kept
    for other slicers/portability. `parts` is (obj, name, extruder_slot)."""
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


def export_project_3mf_grouped(groups, path):
    """Like export_project_3mf, but for multiple INDEPENDENT assemblies in
    one plate (e.g. 4 corners). export_project_3mf wraps every part passed
    to it as components of a single parent object with one <item> in
    <build> - correct for one corner's own cap+insert (which should move
    together) but wrong for 4 corners at once, since the slicer then sees
    one giant fused group instead of 4 independently-movable pieces. This
    builds one parent object per group, each with its own <item>, so each
    corner stays independently movable while its own cap+insert stay
    glued together. `groups` is [(group_name, [(obj, name, slot), ...]), ...]."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    leaf_objects_xml, parent_objects_xml, build_items_xml, object_configs_xml = [], [], [], []
    next_id = 1
    for group_name, parts in groups:
        components_xml, group_parts_xml = [], []
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
            group_parts_xml.append(
                f'<part id="{leaf_id}" subtype="normal_part">'
                f'<metadata key="name" value="{name}.stl"/>'
                f'<metadata key="extruder" value="{slot}"/></part>'
            )

        parent_id = next_id
        next_id += 1
        parent_objects_xml.append(
            f'<object id="{parent_id}" type="model">'
            f'<components>{"".join(components_xml)}</components></object>'
        )
        build_items_xml.append(f'<item objectid="{parent_id}"/>')
        # mirrors export_project_3mf's own <object id="parent"><metadata
        # name/><part .../>...</object> shape exactly, just repeated once
        # per group instead of once globally - the earlier version of this
        # function dumped every <part> flat under <config> with no <object>
        # wrapper at all (and even emitted a bogus top-level <part> for the
        # parent itself), which is why the slicer failed to load the file.
        object_configs_xml.append(
            f'<object id="{parent_id}">'
            f'<metadata key="name" value="{group_name}"/>'
            f'{"".join(group_parts_xml)}</object>'
        )

    model_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        f'<resources>{"".join(leaf_objects_xml)}{"".join(parent_objects_xml)}</resources>'
        f'<build>{"".join(build_items_xml)}</build></model>'
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
        f'{"".join(object_configs_xml)}'
        '</config>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("3D/3dmodel.model", model_xml)
        zf.writestr("Metadata/model_settings.config", model_settings)
    print(f"Exported {path}")


def mesh_volume(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    volume = bm.calc_volume()
    bm.free()
    return volume


def remove_small_islands(obj, min_faces):
    """Deletes any disconnected face-island under min_faces - the (now-
    replaced) raised-rune UNION onto the ALREADY-BEVELED shape (a much
    denser mesh than the plain pre-bevel one) left a tiny stray 2-face
    sliver behind, a
    classic EXACT-solver artifact on a complex target, not present when
    beveling alone or when the rune was unioned onto the simple pre-bevel
    shape - confirmed by an island-count check before/after each step, not
    assumed. The real geometry (everything but that sliver) checked out
    clean, so removing the stray island is the right fix here, not
    redesigning the union order again."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    visited = set()
    islands = []
    for f in bm.faces:
        if f.index in visited:
            continue
        stack, island = [f], set()
        while stack:
            cur = stack.pop()
            if cur.index in island:
                continue
            island.add(cur.index)
            for e in cur.edges:
                for lf in e.link_faces:
                    if lf.index not in island:
                        stack.append(lf)
        visited |= island
        islands.append(island)

    to_delete = [bm.faces[i] for island in islands if len(island) < min_faces for i in island]
    removed = len(to_delete)
    if to_delete:
        bmesh.ops.delete(bm, geom=to_delete, context='FACES')
    bm.to_mesh(obj.data)
    bm.free()
    if removed:
        print(f"  removed {removed} stray face(s) from small disconnected island(s)")
    return obj


def weld_mesh(obj, dist=0.05):
    """Merge-by-distance + recalc normals, run once on the finished cap
    right before export. The long boolean/bevel/snap chain that builds
    this mesh leaves vertices that are SUPPOSED to be coincident (e.g. a
    bevel ring meeting a flat face) sitting a tiny float-precision amount
    apart - invisible in-memory (Blender's own edge/face adjacency still
    treats them as shared, since they came from the same operator pass)
    but STL is a triangle soup with no shared-vertex concept, so those
    near-but-not-exact duplicates survive the export/reimport round-trip
    as real separate vertices - a slicer re-checking manifoldness on the
    reimported file then reports non-manifold edges that were never
    visible on the in-memory mesh (confirmed: a fresh STL round-trip
    reimport found 4 naked + 11 non-manifold edges on EVERY corner,
    including the two that were never touched by the rune-wall fix -
    this is a general property of the mesh, not something introduced by
    that fix). Welding within a tight, well-under-print-tolerance distance
    forces those to true single vertices before they ever hit the STL
    triangle-soup format."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bm.normal_update()
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return obj


# ============================================================
# BUILD - hub + 2 arms per panel, same construction as
# trim_corner_v1_plain.py's build_and_export_cap(), rails dropped, an
# engraved rune added to TOP only.
# ============================================================
def build_cap(rune_compensate_deg=0.0):
    r, t, o = CORNER_REACH, PANEL_THICKNESS, EDGE_OVERLAP
    a_top, a_down = ARM_REACH_TOP, ARM_REACH_DOWN
    assert a_down > r, f"ARM_REACH_DOWN ({a_down}) must clear the hub ({r}) - lid is too thin for this hub size"

    # TOP: proud in +Z. Hub reaches -X/+Y; X-arm continues further in -X
    # (pairs with FRONT's own X-arm along the TOP-FRONT edge), Y-arm
    # continues further in +Y (pairs with RIGHT's Y-arm along TOP-RIGHT).
    # Both TOP arms and the two horizontal-edge arms below run along the
    # top face, not down the lid wall, so they use a_top, not the 1-inch
    # lid-thickness cap.
    # TOP_HUB itself stays at the small `o` (edge-overlap) reach into
    # RIGHT's/FRONT's territory - widening it too (an earlier attempt)
    # fixed the TOP/FRONT height-step but introduced a NEW, worse step
    # where the widened hub's own footprint no longer matched the arm's
    # width right where they meet, visible a few cm out along the arm,
    # not just at the vertex. Reverted; the real fix only needed to widen
    # FRONT_HUB/RIGHT_HUB's own Z-reach (below) - see that note for why
    # that's sufficient on its own for a flush outer surface.
    top_hub = make_panel((-r, o), (-o, r), (0, t), "cap_top_hub")
    top_x_arm = make_panel((-a_top, -r + o), (-o, r), (0, t), "cap_top_xarm")
    top_y_arm = make_panel((-r, o), (r - o, a_top), (0, t), "cap_top_yarm")
    apply_boolean(top_hub, top_x_arm, 'UNION')
    apply_boolean(top_hub, top_y_arm, 'UNION')
    top = top_hub

    # FRONT: proud in -Y. Hub reaches -X/-Z; X-arm continues in -X (pairs
    # with TOP's X-arm, horizontal, a_top) - Z-arm continues in -Z (pairs
    # with RIGHT's Z-arm, this is the actual down-the-lid-wall reach, so
    # it's capped at a_down, the lid's real 1-inch thickness).
    #
    # front_x_arm's Z-reach into TOP's territory is `t` (full panel
    # thickness), not `o` - same fix as front_hub's, and for the same
    # reason: this arm runs the ENTIRE 70mm top-front edge, so an
    # o=1.5mm-short reach was a step running that whole length, not just
    # a defect at the vertex. Caught by re-rendering after the hub-only
    # fix and finding the same notch still there, partway along the arm,
    # not assumed fixed once the hub alone was corrected.
    # front_z_arm's X-reach into RIGHT's territory is also `t`, not `o` -
    # same bug, other axis: this leg meets right_z_arm at the bottom tip
    # (the vertical box edge, not the top edge), and the same o-vs-t
    # mismatch there left a small step/notch at the tip - reported after
    # the top-edge fix, correctly guessed as "same thing, other axis".
    front_hub = make_panel((-r, t), (-t, 0), (-r, t), "cap_front_hub")
    front_x_arm = make_panel((-a_top, -r + o), (-t, 0), (-r, t), "cap_front_xarm")
    front_z_arm = make_panel((-r, t), (-t, 0), (-a_down, -r + o), "cap_front_zarm")
    apply_boolean(front_hub, front_x_arm, 'UNION')
    apply_boolean(front_hub, front_z_arm, 'UNION')
    front = front_hub

    # RIGHT: proud in +X. Hub reaches +Y/-Z; Y-arm continues in +Y (pairs
    # with TOP's Y-arm, horizontal, a_top) - Z-arm continues in -Z (pairs
    # with FRONT's Z-arm, capped at a_down for the same reason).
    # right_y_arm gets the same `t`-reach fix as front_x_arm, same reason;
    # right_z_arm gets the same `t`-reach fix as front_z_arm (its Y into
    # FRONT's territory), for the tip seam.
    right_hub = make_panel((0, t), (-t, r), (-r, t), "cap_right_hub")
    right_y_arm = make_panel((0, t), (r - o, a_top), (-r, t), "cap_right_yarm")
    right_z_arm = make_panel((0, t), (-t, r), (-a_down, -r + o), "cap_right_zarm")
    apply_boolean(right_hub, right_y_arm, 'UNION')
    apply_boolean(right_hub, right_z_arm, 'UNION')
    right = right_hub

    apply_boolean(top, front, 'UNION')
    apply_boolean(top, right, 'UNION')

    # Bevel the PLAIN assembled shape first, rune socket cut after - not
    # the other way round. Beveling with the rune's fine detail already
    # unioned in gave the round-over a second, much-shorter set of nearby
    # edges to worry about, and even with use_clamp_overlap=False it came
    # out visibly shredded right at the rune (an actual defect, not a
    # rendering artifact - checked by rendering a close-up, not assumed).
    # This ordering is the same lesson the sibling TSONS script already
    # documented for its own rails: "bevel the plain slab, then union the
    # border on top" - reused here rather than rediscovered from scratch.
    bevel_box_edges(top, BOX_BEVEL_WIDTH, BOX_BEVEL_SEGMENTS)

    pocket_cutter = build_rune_pocket_cutter(rune_compensate_deg)
    apply_boolean(top, pocket_cutter, 'DIFFERENCE')
    # a UNION here (the old raised-emboss version) left a tiny stray
    # disconnected sliver against the denser beveled mesh (an EXACT-solver
    # artifact, checked via an island-count pass) - a DIFFERENCE cut
    # shouldn't produce the same failure mode (nothing new is being added
    # that could end up disconnected), but the cleanup stays as a cheap,
    # harmless safety net rather than trusting that by reasoning alone.
    remove_small_islands(top, min_faces=20)

    # At rune_compensate_deg of -90/-180 specifically (not 0/-270) the
    # DIFFERENCE above can leave a ~1mm-tall leftover rim/roof standing at
    # z=PANEL_THICKNESS+OVERSHOOT right over the rune's footprint - the
    # EXACT solver failing to fully consume part of the pocket cutter's own
    # OVERSHOOT geometry at those orientations. Found by inspecting
    # extreme-Z vertices on the exported STL (not visible in the isometric
    # renders used earlier) - this is what read as a "floating rune" once
    # printed/viewed in the slicer: a phantom rune-shaped cap hovering
    # above the real, correctly-cut pocket. It's a single connected wall,
    # not a separate island, so remove_small_islands doesn't catch it.
    # Tried making the rotation bit-exact via coordinate swaps instead of
    # cos/sin first (no change - not floating-point residue in the
    # cutter's points) and tried clipping it off with one more boolean
    # (INTERSECT and DIFFERENCE both immediately zeroed the whole mesh -
    # this mesh already carries 2 pre-existing non-manifold edges from the
    # long upstream boolean chain, confirmed via a link_faces!=2 scan, and
    # EXACT chokes on one more CSG op stacked on that). Snapping the stray
    # vertices back down directly is plain mesh surgery, not another CSG
    # op, so it can't retrigger that failure mode. Nothing legitimate on
    # this panel should ever exceed PANEL_THICKNESS (confirmed: the clean
    # 0deg/270deg corners cap out at exactly 5.0).
    clip_z = PANEL_THICKNESS + 0.02
    stray = [v for v in top.data.vertices if v.co.z > clip_z]
    if stray:
        for v in stray:
            v.co.z = PANEL_THICKNESS
        top.data.update()
        # snapping collapses the wall's former side/roof faces flat onto
        # the true surface already there at PANEL_THICKNESS, leaving ~47
        # edges shared by 4-6 faces instead of 2 (redundant overlapping
        # footprints, not zero-area - remove_doubles/dissolve_degenerate
        # don't touch them, and an explicit dedupe-by-vertex-set found none
        # either, since the collapsed faces aren't literal vertex-for-
        # vertex duplicates of the ones below). Tried deleting the wall
        # faces outright instead and filling the resulting hole: that
        # exposed 3 genuinely naked edges holes_fill couldn't close
        # cleanly plus its own tangle of non-manifold edges - an actual gap
        # in the shell, strictly worse for slicing than this. Checked what
        # actually matters for printing: every non-manifold edge here has
        # link_faces>=4 (never 0 or 1), i.e. no gap anywhere, just
        # redundant coincident surface - slicers ray-cast through the
        # shell and tolerate that fine, so leaving it as-is rather than
        # risking a real hole chasing perfect manifoldness.
        print(f"  snapped {len(stray)} stray vert(s) above {clip_z:.2f}mm back to {PANEL_THICKNESS:.1f}mm")

    weld_mesh(top)

    cap = top
    cap.name = "box_corner_trim_v2"

    insert, rune_h = build_rune_insert(rune_compensate_deg)
    insert.name = "box_corner_trim_v2_rune_insert"
    print(f"rune insert real size: {RUNE_TARGET_W:.1f}x{rune_h:.1f}mm, centered at {RUNE_CENTER_XY}, "
          f"{RUNE_INSERT_DEPTH}mm thick - separate STL, print in a contrasting color")

    print(f"corner cap: volume={mesh_volume(cap):.0f}mm3")
    apply_color(cap, "cap_color", CAP_COLOR)
    apply_color(insert, "insert_color", INSERT_COLOR)
    return cap, insert


# ============================================================
# 4 CORNERS + PRINT ORIENTATION
#
# One box has 4 top corners, and a rectangle's 4 corners are related to
# each other by pure 90-degree rotations around the vertical (Z) axis -
# not reflections - so the BRACKET shape (hub+arms) for each corner is
# just the base geometry rotated another 90 degrees. That part was never
# the bug: a rotation can't introduce mirroring, verified and still true.
#
# The RUNE is different on purpose (confirmed after a first attempt
# printed wrong): it's meant to read the same ABSOLUTE way on all 4
# corners (e.g. always upright from one fixed viewing direction), not
# rotate along with its own bracket the way real repeating hardware
# would. Since a plain whole-piece rotation rotates the rune right along
# with everything else, keeping it absolute means pre-rotating the rune's
# OWN pocket/insert by -z_deg (see build_cap's rune_compensate_deg) before
# the bracket's own +z_deg gets applied - the two cancel out to a fixed
# final angle. That's why each corner rebuilds the cap from scratch (the
# pocket is cut fresh per corner) rather than just rigidly transforming
# one shared base like the bracket geometry does.
#
# PRINT_FLIP (180 degrees around X) is a separate, unrelated transform -
# it only controls how the piece sits in the SLICER for support-free
# printing (see the earlier overhang analysis: this flip takes
# unsupported overhang from ~21% down to ~3%). It has no bearing on the
# rune's final readability once the piece is removed from the print bed
# and mounted normally - only the rune's own compensating rotation (baked
# into the geometry) and the corner's z_deg affect that.
# ============================================================
PRINT_FLIP = True   # top panel down, short leg up - see the overhang analysis in conversation

# (name, degrees around Z) - the geometry was built for one specific
# corner by construction (FRONT proud -Y, RIGHT proud +X); each other
# corner is just that same shape rotated another 90 degrees around the
# vertex. The rune's own compensating rotation is -z_deg, computed from
# this same list, not a second independent value to keep in sync by hand.
CORNERS = [
    ("corner_0deg", 0.0),
    ("corner_90deg", 90.0),
    ("corner_180deg", 180.0),
    ("corner_270deg", 270.0),
]


def duplicate_and_transform(obj, name, z_deg, flip):
    """Duplicates obj and applies a fresh world transform: Z-rotation
    (corner selection) first, then the print-flip (if any) - matrix
    composition, not Euler angles, so there's no rotation-order ambiguity
    to get backwards."""
    dup = obj.copy()
    dup.data = obj.data.copy()
    dup.name = name
    bpy.context.collection.objects.link(dup)
    m = mathutils.Matrix.Rotation(math.radians(z_deg), 4, 'Z')
    if flip:
        m = mathutils.Matrix.Rotation(math.radians(180), 4, 'X') @ m
    dup.matrix_world = m
    return dup


def export_corner(cap, insert, corner_name, z_deg):
    cap_dup = duplicate_and_transform(cap, f"box_corner_trim_v2_{corner_name}", z_deg, PRINT_FLIP)
    insert_dup = duplicate_and_transform(
        insert, f"box_corner_trim_v2_{corner_name}_rune_insert", z_deg, PRINT_FLIP)
    apply_color(cap_dup, "cap_color", CAP_COLOR)
    apply_color(insert_dup, "insert_color", INSERT_COLOR)

    if EXPORT_STL:
        export_stl(cap_dup, f"{cap_dup.name}.stl")
        export_stl(insert_dup, f"{insert_dup.name}.stl")
    if EXPORT_3MF:
        export_3mf([(cap_dup, CAP_COLOR, "cap"), (insert_dup, INSERT_COLOR, "insert")],
                   os.path.join(EXPORT_DIR, f"box_corner_trim_v2_{corner_name}.3mf"))
        export_project_3mf(
            [(cap_dup, "cap", CAP_EXTRUDER_SLOT), (insert_dup, "insert", INSERT_EXTRUDER_SLOT)],
            os.path.join(EXPORT_DIR, f"box_corner_trim_v2_{corner_name}_anycubic.3mf"))
    return cap_dup, insert_dup


def main():
    clear_scene()

    exported = []
    for corner_name, z_deg in CORNERS:
        # fresh build per corner - the rune's pocket/insert are cut at a
        # compensating -z_deg angle each time (see build_cap's own note),
        # so they can't just be a rigid duplicate of one shared base the
        # way the surrounding bracket geometry is.
        cap, insert = build_cap(rune_compensate_deg=-z_deg)
        exported.append(export_corner(cap, insert, corner_name, z_deg))

    if EXPORT_3MF:
        # one combined plate with all 4 corners (8 objects: 4 caps + 4
        # inserts), laid out so they don't overlap - requested instead of
        # importing 4 separate files one at a time. Same print-flipped
        # objects export_corner already built, reused rather than
        # rebuilt - laying them out is just a translation, no new booleans.
        pitch = 100.0
        combined_parts, combined_groups_proj = [], []
        for i, ((corner_name, _), (cap_dup, insert_dup)) in enumerate(zip(CORNERS, exported)):
            cap_dup.location = (i * pitch, 0.0, 0.0)
            insert_dup.location = (i * pitch, 0.0, 0.0)
            combined_parts.append((cap_dup, CAP_COLOR, f"cap_{corner_name}"))
            combined_parts.append((insert_dup, INSERT_COLOR, f"insert_{corner_name}"))
            # each corner is its own group here (own parent/<item>) so the
            # slicer can move/arrange the 4 corners independently, while
            # each corner's own cap+insert stay glued together as one
            # component set - see export_project_3mf_grouped's own note.
            combined_groups_proj.append((corner_name, [
                (cap_dup, f"cap_{corner_name}", CAP_EXTRUDER_SLOT),
                (insert_dup, f"insert_{corner_name}", INSERT_EXTRUDER_SLOT),
            ]))
        export_3mf(combined_parts, os.path.join(EXPORT_DIR, "box_corner_trim_v2_all4corners.3mf"))
        export_project_3mf_grouped(combined_groups_proj,
                                    os.path.join(EXPORT_DIR, "box_corner_trim_v2_all4corners_anycubic.3mf"))

    if RENDER_IMAGES:
        # the base corner, print-flipped (confirms what lands in the slicer)
        render_angles([exported[0][0], exported[0][1]], prefix="printflip_")
        # all 4 corners together, laid out (already offset above) - shown
        # print-flipped since that's what's currently in the scene; the
        # UNFLIPPED absolute-rune-orientation check is done separately
        # (see verify_4corners_mounted.py in conversation) since it needs
        # the print-flip undone first, which isn't how these are exported
        render_angles([obj for pair in exported for obj in pair], prefix="all4corners_")

    print("Done.")


if __name__ == "__main__":
    main()
