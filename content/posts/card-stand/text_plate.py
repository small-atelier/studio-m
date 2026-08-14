"""
Standalone "MYTHOS" text plate (Blender bpy) - a separate glue-on part,
not part of the backplate build anymore.

Why this exists: v5's wordmark was real vector text unioned straight
onto the backplate's front face (see build_logo_text in
card_stand_v5_flat_sharp_logo.py). After printing and support removal,
the O and S didn't survive - their stroke width at TEXT_SIZE=15 in
Baskerville is thin (moderate stroke contrast is part of that font's
design), and a thin stroke embossed onto a much bigger flat face is
exactly the kind of feature that's first to snap during sanding/support
cleanup. Plan: file the broken text off the existing printed backplate,
print this as its own small part, glue it on by eye afterward - so its
position doesn't need to match the backplate's coordinate system at all,
just its own footprint.

Two fixes versus v5's approach:
  1. Bolder strokes - curve_data.offset pushes the outline out on every
     edge (not just scaling the whole glyph up), so O's ring and S's
     curve both gain real wall thickness instead of getting
     proportionally thin-but-bigger.
  2. Real attachment - text is unioned onto a solid 2mm backing plate
     with a deep embed (not a thin graze against a big flat face like
     before), so the joint has actual volume behind it, and the whole
     plate is what gets glued down - no individual letter is depending
     on its own bond to survive alone.

Printed flat (plate on the bed, letters facing up) - same zero-support
logic as v5's backplate reorientation: the only raised feature all
projects the same direction, straight up.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python text_plate_v1.py
"""

import bpy
import bmesh
import math
import mathutils
import os

# ============================================================
# CONFIG (all mm)
# ============================================================

EXPORT_DIR = "/Users/mannil/pfn/projects/mjnet/studio-m/blender/card-stand/output_text_plate_v1"
EXPORT_STL = True

RENDER_IMAGES = True
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")
RENDER_RESOLUTION = (1600, 1200)

# --- Text ---
TEXT_FONT_PATH = "/System/Library/Fonts/Supplemental/Baskerville.ttc"
TEXT_STRING = "MYTHOS"
TEXT_SIZE = 18.0          # keep at 18 - dropping to 15 makes TEXT_BOLD_OFFSET proportionally too
                          # aggressive for the glyphs and collapses the union (verified: "MY" and
                          # part of the O disappeared, non-manifold fraction spiked to 12%). Shrink
                          # the plate via PLATE_MARGIN_X instead - doesn't touch text geometry.
TEXT_BOLD_OFFSET = 0.12  # curve outline offset - pushes every stroke edge out this much, the
                          # fix for O's ring / S's curve reading too thin. Tested 0.08-0.22: past
                          # ~0.13 the offset self-intersects O/S's tight inner curves and the
                          # union silently collapses most of the letterforms (volume drops from
                          # ~3000mm3 to ~200mm3, non-manifold fraction jumps to 12%) - 0.12 is
                          # comfortably inside the safe range (visibly bolder, volume ~3100mm3,
                          # non-manifold ~5%, every letter intact - verified by render).
TEXT_RAISE_H = 1.8        # how proud of the plate's top face the letters stand
TEXT_EMBED = 1.2          # how far into the plate the text volume also extends, for a real union
                           # with the plate rather than a shallow surface graze

# --- Backing plate ---
PLATE_T = 2.0             # requested: 2mm thick backing plate
PLATE_MARGIN_X = 1.5      # margin around the measured text bounding box - trimmed from 6.0 so the
                          # plate (was 73mm) fits inside the 70mm backplate it glues onto
PLATE_MARGIN_Z = 5.0
PLATE_BEVEL_W = 0.6

# ============================================================
# GENERIC HELPERS (same conventions as card_stand_v5_flat_sharp_logo.py)
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


def union_onto(base, piece):
    return apply_boolean(base, piece, 'UNION')


def apply_transform(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def apply_bevel(obj, width, segments=2):
    mod = obj.modifiers.new("Bevel", 'BEVEL')
    mod.width = width
    mod.segments = segments
    mod.limit_method = 'ANGLE'
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
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


def build_box(sx, sy, sz, center, name):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    bmesh.ops.translate(bm, vec=center, verts=bm.verts)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
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


def setup_camera_and_light(center, plate_w, plate_h):
    # Straight-on front view (looking down -Y), not an angled iso shot -
    # more useful for judging a flat plaque than a 3D perspective would be.
    # ortho_scale fills the LARGER of the sensor's two axes; with a
    # landscape render, that's the horizontal one, so scale to whichever
    # of width or (height * render aspect) is bigger, plus margin.
    aspect = RENDER_RESOLUTION[0] / RENDER_RESOLUTION[1]
    scale = max(plate_w, plate_h * aspect) * 1.25

    cam_data = bpy.data.cameras.new("RenderCam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = scale
    cam = bpy.data.objects.new("RenderCam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = center + mathutils.Vector((0.0, -scale, 0.0))
    cam.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    bpy.context.scene.camera = cam

    light_data = bpy.data.lights.new("RenderLight", type='SUN')
    light_data.energy = 3.0
    light = bpy.data.objects.new("RenderLight", light_data)
    bpy.context.collection.objects.link(light)
    light.location = center + mathutils.Vector((scale * 0.3, -scale * 1.5, scale * 0.6))
    direction = center - light.location
    light.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()


def render_to(path):
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = RENDER_RESOLUTION
    scene.render.filepath = path
    scene.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {path}")


# ============================================================
# BUILD
# ============================================================

def build_text_mesh():
    """Real vector text, bolded via curve outline offset (not just a
    bigger font size) so O's ring and S's curve both gain real stroke
    width. Returns the converted mesh object, still at its own local
    origin (not yet measured/centered)."""
    font = bpy.data.fonts.load(TEXT_FONT_PATH)
    curve_data = bpy.data.curves.new("text_curve", type='FONT')
    curve_data.body = TEXT_STRING
    curve_data.font = font
    curve_data.size = TEXT_SIZE
    curve_data.align_x = 'CENTER'
    curve_data.align_y = 'CENTER'
    curve_data.offset = TEXT_BOLD_OFFSET
    curve_data.extrude = (TEXT_RAISE_H + TEXT_EMBED) / 2.0
    obj = bpy.data.objects.new("text", curve_data)
    bpy.context.collection.objects.link(obj)

    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='MESH')
    return obj


def build_plate():
    text_obj = build_text_mesh()

    # Measure the actual glyph ink extent (align_y='TOP' trusts the
    # font's ascender line, not the real cap-height - see v5's
    # build_logo_text for the same lesson) so the plate is sized to
    # what's really there, not a guessed font metric.
    xs = [v.co.x for v in text_obj.data.vertices]
    ys_ink = [v.co.y for v in text_obj.data.vertices]
    text_w = max(xs) - min(xs)
    text_h = max(ys_ink) - min(ys_ink)

    plate_w = text_w + 2 * PLATE_MARGIN_X
    plate_h = text_h + 2 * PLATE_MARGIN_Z

    plate = build_box(plate_w, PLATE_T, plate_h, (0.0, PLATE_T / 2.0, 0.0), "text_plate")
    apply_bevel(plate, PLATE_BEVEL_W)

    # Text curve extrudes along its own local Z, which after this
    # rotation becomes world Y (front-to-back through the plate) -
    # same convention as v5's build_logo_text.
    text_obj.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    text_obj.location = (0.0, TEXT_RAISE_H - (TEXT_RAISE_H + TEXT_EMBED) / 2.0, 0.0)
    apply_transform(text_obj)
    union_onto(plate, text_obj)

    return plate, plate_w, plate_h


# ============================================================
# MAIN
# ============================================================

def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    clear_scene()

    plate, plate_w, plate_h = build_plate()

    vol = mesh_volume(plate)
    nm = nonmanifold_fraction(plate)
    print(f"text_plate: {plate_w:.1f}x{PLATE_T:.1f}x{plate_h:.1f}mm  "
          f"volume={vol:.1f}mm3  non-manifold edge fraction={nm:.4f}")
    assert vol > 0.0, "text_plate has zero/negative volume - a boolean likely emptied it"

    if EXPORT_STL:
        export_stl(plate, "text_plate.stl")

    if RENDER_IMAGES:
        os.makedirs(RENDER_DIR, exist_ok=True)
        center, _ = compute_scene_bounds()
        setup_camera_and_light(center, plate_w, plate_h)
        render_to(os.path.join(RENDER_DIR, "text_plate_front.png"))

    print("Done.")


if __name__ == "__main__":
    main()
