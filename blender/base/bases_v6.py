# Base Factory v6
# Generates plain hollow miniature bases — round, oval, square, rect, pill, and slotted.
# Paste into the Blender 5.1.2 Script Editor and run (Alt+P).
#
# Docs & article: https://small-atelier.github.io/studio-m/posts/blender-bases/

import bpy
import bmesh
import math
import os

# ----------------------------
# CONFIG
# ----------------------------
ROUND_SIZES = [25, 28.5, 32, 40, 50, 65, 80, 90, 100, 130, 160]

SQUARE_SIZES = [20, 25, 40, 50, 60, 100]   # GW square base standards

RECT_SIZES = [           # GW rectangular bases (width × depth)
    (25,  50),           # cavalry
    (40,  60),           # large cavalry / chariots
    (50,  75),           # monsters
    (50, 100),           # large monsters
]

PILL_SIZES = [           # GW pillbox bases (length × width)
    (70,  25),
    (95,  40),
]

OVAL_SIZES = [
    (60, 35),
    (75, 42),
    (90, 52),
    (105, 70),
    (120, 92),
    (150, 95),
    (170, 109)
]

HEIGHT           = 4.0
TOP_SHRINK       = 1.2   # taper amount
WALL             = 1.6   # wall thickness
BOTTOM_THICKNESS = 1.2   # solid floor at top (model platform)

MAGNET_CONFIGS = [
    {"diam": 5.2, "offset_deg":  0},   # 5x2mm — big
    {"diam": 3.2, "offset_deg": 60},   # 3x1mm — small
]
MAGNET_RING  = 0.55   # socket ring radius as fraction of base radius
SOCKET_WALL  = 0.8    # socket tube wall thickness

ADD_MAGNETS   = True

# Slotted bases — style: 'single' | 'double' (cavalry) | 'cross'
SLOT_WIDTH         = 2.0
SLOT_DEPTH         = 3.0    # from top surface downward
SLOT_SPACING       = 14.0   # centre-to-centre gap between double slots
SLOT_LENGTH_FACTOR = 0.60   # slot length as fraction of base dimension

SLOTTED_ROUND = [
    {"diam": 20, "style": "single"},
    {"diam": 25, "style": "single"},
]
SLOTTED_SQUARE = [
    {"size": 20, "style": "single"},
    {"size": 25, "style": "single"},
    {"size": 20, "style": "diagonal"},
    {"size": 25, "style": "diagonal"},
]
SLOTTED_RECT = [
    {"x": 20, "y": 40, "style": "double"},
    {"x": 25, "y": 50, "style": "double"},
]

EXPORT_STL    = True
EXPORT_ROUND  = True
EXPORT_OVAL   = True
EXPORT_SQUARE = True
EXPORT_RECT   = True
EXPORT_PILL   = True
EXPORT_SLOT   = True
EXPORT_DIR    = "/Users/mannil/Documents/STL_BASE"  # // = relative to .blend file; or use an absolute path

# ----------------------------
# LAYOUT (bin-pack onto 220 × 220 mm plates)
# ----------------------------
PLATE_W   = 220.0
PLATE_H   = 220.0
MARGIN    =   5.0
GAP       =   1.5
BATCH_SEP = 260.0

# ----------------------------
# UTILITIES
# ----------------------------
def make_collection(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col

def move(obj, col):
    for c in obj.users_collection:
        c.objects.unlink(obj)
    col.objects.link(obj)

def socket_counts(radius):
    """Returns [big_count, small_count] scaled to base size."""
    d = radius * 2
    if d <= 28.5:   # 25, 28.5mm
        return [1, 2]
    elif d <= 40:   # 32, 40mm
        return [2, 2]
    else:           # 50mm+
        return [3, 3]

def ring_positions(r, offset_deg, count):
    """Evenly-spaced positions around a ring."""
    step = 360 / count
    return [
        (r * math.cos(math.radians(offset_deg + i * step)),
         r * math.sin(math.radians(offset_deg + i * step)))
        for i in range(count)
    ]

# ----------------------------
# GEOMETRY
# ----------------------------
def add_magnet_sockets(obj, radius):
    bpy.ops.object.mode_set(mode='OBJECT')

    r              = radius * MAGNET_RING
    floor_bottom_z = obj.location.z + HEIGHT / 2 - BOTTOM_THICKNESS
    depth          = HEIGHT - BOTTOM_THICKNESS - 1.0   # 1mm clearance above open rim
    cup_z          = floor_bottom_z - depth / 2

    counts = socket_counts(radius)

    for cfg, n in zip(MAGNET_CONFIGS, counts):
        outer_r   = cfg["diam"] / 2 + SOCKET_WALL
        inner_r   = cfg["diam"] / 2
        positions = ring_positions(r, cfg["offset_deg"], n)

        for x, y in positions:
            bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=outer_r, depth=depth)
            cup = bpy.context.object
            cup.location = (obj.location.x + x, obj.location.y + y, cup_z)

            bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=inner_r, depth=depth + 0.2)
            bore = bpy.context.object
            bore.location = (obj.location.x + x, obj.location.y + y, cup_z - 0.1)

            mod = cup.modifiers.new("Bore", 'BOOLEAN')
            mod.object = bore
            mod.operation = 'DIFFERENCE'
            bpy.context.view_layer.objects.active = cup
            bpy.ops.object.modifier_apply(modifier=mod.name)
            bpy.data.objects.remove(bore, do_unlink=True)

            mod = obj.modifiers.new("Socket", 'BOOLEAN')
            mod.object = cup
            mod.operation = 'UNION'
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=mod.name)
            bpy.data.objects.remove(cup, do_unlink=True)


def create_base_mesh(radius_x, radius_y=None):
    if radius_y is None:
        radius_y = radius_x

    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=1, depth=HEIGHT)
    obj = bpy.context.object
    obj.scale.x = radius_x
    obj.scale.y = radius_y
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.select_set(False)

    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    for v in bm.verts:
        if v.co.z > 0:
            v.co.x *= (1 - TOP_SHRINK / radius_x)
            v.co.y *= (1 - TOP_SHRINK / radius_y)
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')

    return obj


def add_recess(obj, radius_x, radius_y):
    inner_depth = HEIGHT - BOTTOM_THICKNESS + 0.1
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=1, depth=inner_depth)
    inner = bpy.context.object
    inner.scale.x = radius_x - WALL
    inner.scale.y = radius_y - WALL
    bpy.ops.object.transform_apply(scale=True)
    inner.location = (obj.location.x, obj.location.y, obj.location.z - BOTTOM_THICKNESS / 2)

    mod = obj.modifiers.new("Hollow", 'BOOLEAN')
    mod.object = inner
    mod.operation = 'DIFFERENCE'
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(inner, do_unlink=True)


def add_text(obj, text, radius_x, radius_y=None):
    if radius_y is None:
        radius_y = radius_x

    bpy.ops.object.text_add()
    t = bpy.context.object
    t.data.body    = text
    depth          = HEIGHT - BOTTOM_THICKNESS - 1.0
    t.data.extrude = depth
    scale          = max(4.5, radius_x * 0.18)   # floor at 50mm-base size
    t.scale        = (scale, scale, 1.0)
    t.rotation_euler = (0, math.pi, 0)

    ceiling_z  = obj.location.z + HEIGHT / 2 - BOTTOM_THICKNESS
    t.location = (
        obj.location.x + scale * len(text) * 0.3,
        obj.location.y - scale * 0.5,
        ceiling_z - depth / 2,
    )

    bpy.ops.object.convert(target='MESH')
    raised = bpy.context.object

    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=1, depth=HEIGHT)
    clip = bpy.context.object
    clip.scale.x = radius_x - WALL
    clip.scale.y = radius_y - WALL
    bpy.ops.object.transform_apply(scale=True)
    clip.location = (obj.location.x, obj.location.y, obj.location.z)

    mod = raised.modifiers.new("Clip", 'BOOLEAN')
    mod.object = clip
    mod.operation = 'INTERSECT'
    bpy.context.view_layer.objects.active = raised
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(clip, do_unlink=True)

    mod = obj.modifiers.new("TextRaise", 'BOOLEAN')
    mod.object = raised
    mod.operation = 'UNION'
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(raised, do_unlink=True)

# ----------------------------
# GENERATORS
# ----------------------------
def make_round(d, col, label=True):
    r   = d / 2
    obj = create_base_mesh(r)
    obj.name = f"round_{d}mm"
    add_recess(obj, r, r)
    if ADD_MAGNETS:
        add_magnet_sockets(obj, r)
    if label:
        add_text(obj, f"{d} mm", r)
    move(obj, col)
    return obj


def make_oval(x, y, col, label=True):
    rx, ry = x / 2, y / 2
    obj    = create_base_mesh(rx, ry)
    obj.name = f"oval_{x}x{y}"
    add_recess(obj, rx, ry)
    if ADD_MAGNETS:
        add_magnet_sockets(obj, min(rx, ry))
    if label:
        add_text(obj, f"{x}x{y} mm", rx, ry)
    move(obj, col)
    return obj

# ----------------------------
# SQUARE / RECT GEOMETRY
# ----------------------------
def create_box_mesh(size_x, size_y):
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.object
    # size=1 gives vertices at ±0.5; scale so they sit at ±size/2
    obj.scale = (size_x, size_y, HEIGHT)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.select_set(False)

    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    for v in bm.verts:
        if v.co.z > 0:
            v.co.x *= (1 - TOP_SHRINK / (size_x / 2))
            v.co.y *= (1 - TOP_SHRINK / (size_y / 2))
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')

    return obj


def add_box_recess(obj, size_x, size_y):
    inner_depth = HEIGHT - BOTTOM_THICKNESS + 0.1
    bpy.ops.mesh.primitive_cube_add(size=1)
    inner = bpy.context.object
    inner.scale = (size_x - 2 * WALL, size_y - 2 * WALL, inner_depth)
    bpy.ops.object.transform_apply(scale=True)
    inner.location = (obj.location.x, obj.location.y, obj.location.z - BOTTOM_THICKNESS / 2)

    mod = obj.modifiers.new("Hollow", 'BOOLEAN')
    mod.object = inner
    mod.operation = 'DIFFERENCE'
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(inner, do_unlink=True)


def add_box_text(obj, text, size_x, size_y):
    bpy.ops.object.text_add()
    t = bpy.context.object
    t.data.body    = text
    depth          = HEIGHT - BOTTOM_THICKNESS - 1.0
    t.data.extrude = depth
    scale          = max(4.5, min(size_x, size_y) / 2 * 0.18)
    t.scale        = (scale, scale, 1.0)
    t.rotation_euler = (0, math.pi, 0)

    ceiling_z  = obj.location.z + HEIGHT / 2 - BOTTOM_THICKNESS
    t.location = (
        obj.location.x + scale * len(text) * 0.3,
        obj.location.y - scale * 0.5,
        ceiling_z - depth / 2,
    )

    bpy.ops.object.convert(target='MESH')
    raised = bpy.context.object

    bpy.ops.mesh.primitive_cube_add(size=1)
    clip = bpy.context.object
    clip.scale = (size_x - 2 * WALL, size_y - 2 * WALL, HEIGHT)
    bpy.ops.object.transform_apply(scale=True)
    clip.location = (obj.location.x, obj.location.y, obj.location.z)

    mod = raised.modifiers.new("Clip", 'BOOLEAN')
    mod.object = clip
    mod.operation = 'INTERSECT'
    bpy.context.view_layer.objects.active = raised
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(clip, do_unlink=True)

    mod = obj.modifiers.new("TextRaise", 'BOOLEAN')
    mod.object = raised
    mod.operation = 'UNION'
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(raised, do_unlink=True)


def make_square(s, col, label=True):
    r   = s / 2
    obj = create_box_mesh(s, s)
    obj.name = f"square_{s}mm"
    add_box_recess(obj, s, s)
    if ADD_MAGNETS:
        add_magnet_sockets(obj, r)
    if label:
        add_box_text(obj, f"{s}mm", s, s)
    move(obj, col)
    return obj


def make_rect(x, y, col, label=True):
    obj = create_box_mesh(x, y)
    obj.name = f"rect_{x}x{y}"
    add_box_recess(obj, x, y)
    if ADD_MAGNETS:
        add_magnet_sockets(obj, min(x, y) / 2)
    if label:
        add_box_text(obj, f"{x}x{y}", x, y)
    move(obj, col)
    return obj

# ----------------------------
# PILL GEOMETRY
# ----------------------------
def build_pill(length, width, depth, cx=0, cy=0, cz=0):
    """Union a rect + two semicircular end caps into one pill-shaped mesh."""
    r        = width / 2
    straight = length - width   # length of the straight midsection

    bpy.ops.mesh.primitive_cube_add(size=1)
    mid = bpy.context.object
    mid.scale = (straight, width, depth)
    bpy.ops.object.transform_apply(scale=True)
    mid.location = (cx, cy, cz)

    for sign in (1, -1):
        bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=r, depth=depth)
        cap = bpy.context.object
        cap.location = (cx + sign * straight / 2, cy, cz)
        mod = mid.modifiers.new("Cap", 'BOOLEAN')
        mod.object = cap
        mod.operation = 'UNION'
        bpy.context.view_layer.objects.active = mid
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cap, do_unlink=True)

    return mid


def create_pill_mesh(length, width):
    obj = build_pill(length, width, HEIGHT)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    for v in bm.verts:
        if v.co.z > 0:
            v.co.x *= (1 - TOP_SHRINK / (length / 2))
            v.co.y *= (1 - TOP_SHRINK / (width  / 2))
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')

    return obj


def add_pill_recess(obj, length, width):
    inner_depth = HEIGHT - BOTTOM_THICKNESS + 0.1
    inner = build_pill(
        length - 2 * WALL, width - 2 * WALL, inner_depth,
        cx=obj.location.x, cy=obj.location.y,
        cz=obj.location.z - BOTTOM_THICKNESS / 2
    )
    mod = obj.modifiers.new("Hollow", 'BOOLEAN')
    mod.object = inner
    mod.operation = 'DIFFERENCE'
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(inner, do_unlink=True)


def make_pill(length, width, col):
    obj = create_pill_mesh(length, width)
    obj.name = f"pill_{length}x{width}"
    add_pill_recess(obj, length, width)
    if ADD_MAGNETS:
        add_magnet_sockets(obj, min(length, width) / 2)  # ring bounded by narrow side
    add_text(obj, f"{length}x{width}", width / 2)
    move(obj, col)
    return obj

# ----------------------------
# SLOTTED BASES
# ----------------------------
def add_slot(obj, slot_length, style='single'):
    """Cut slot(s) into the top face of a base."""
    slot_z = obj.location.z + HEIGHT / 2 - SLOT_DEPTH / 2

    def cut(cx, cy, rz=0.0, along_x=False):
        bpy.ops.mesh.primitive_cube_add(size=1)
        s = bpy.context.object
        s.scale = (slot_length if along_x else SLOT_WIDTH,
                   SLOT_WIDTH  if along_x else slot_length,
                   SLOT_DEPTH)
        bpy.ops.object.transform_apply(scale=True)
        s.location = (obj.location.x + cx, obj.location.y + cy, slot_z)
        if rz:
            s.rotation_euler.z = rz
        mod = obj.modifiers.new("Slot", 'BOOLEAN')
        mod.object = s
        mod.operation = 'DIFFERENCE'
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(s, do_unlink=True)

    if style == 'single':
        cut(0, 0)
    elif style == 'double':
        # two slots run along length (Y), offset side-by-side in X
        cut(-SLOT_SPACING / 2, 0)
        cut( SLOT_SPACING / 2, 0)
    elif style == 'cross':
        cut(0, 0)
        cut(0, 0, along_x=True)
    elif style == 'diagonal':
        cut(0, 0, rz=math.radians(45))


def make_slotted_round(d, style, col):
    obj = make_round(d, col, label=False)
    add_slot(obj, d * SLOT_LENGTH_FACTOR, style)
    obj.name = f"slot_round_{d}mm"
    return obj


def make_slotted_square(s, style, col):
    obj = make_square(s, col, label=False)
    if style == 'diagonal':
        slot_len = s * math.sqrt(2) * SLOT_LENGTH_FACTOR
        obj.name = f"slot_square_{s}mm_diag"
    else:
        slot_len = s * SLOT_LENGTH_FACTOR
        obj.name = f"slot_square_{s}mm"
    add_slot(obj, slot_len, style)
    return obj


def make_slotted_rect(x, y, style, col):
    obj = make_rect(x, y, col, label=False)
    dim = max(x, y)   # slots always run along the long axis
    add_slot(obj, dim * SLOT_LENGTH_FACTOR, style)
    obj.name = f"slot_rect_{x}x{y}"
    return obj

# ----------------------------
# BIN PACKING
# ----------------------------
def pack_batches(items):
    usable_w = PLATE_W - 2 * MARGIN
    usable_h = PLATE_H - 2 * MARGIN
    ordered  = sorted(items, key=lambda i: max(i[1], i[2]), reverse=True)

    def new_plate():
        return {"shelves": [{"x": 0.0, "y": 0.0, "h": 0.0}], "items": []}

    plates = []
    plate  = new_plate()

    for obj, w, h in ordered:
        placed = False
        for shelf in plate["shelves"]:
            if shelf["x"] + w <= usable_w:
                plate["items"].append((obj, MARGIN + shelf["x"] + w / 2, MARGIN + shelf["y"] + h / 2))
                shelf["h"]  = max(shelf["h"], h)
                shelf["x"] += w + GAP
                placed = True
                break

        if not placed:
            last  = plate["shelves"][-1]
            new_y = last["y"] + last["h"] + GAP
            if new_y + h <= usable_h:
                plate["shelves"].append({"x": 0.0, "y": new_y, "h": h})
                plate["items"].append((obj, MARGIN + w / 2, MARGIN + new_y + h / 2))
                plate["shelves"][-1]["x"] = w + GAP
            else:
                plates.append(plate["items"])
                plate = new_plate()
                plate["items"].append((obj, MARGIN + w / 2, MARGIN + h / 2))
                plate["shelves"][0]["h"] = h
                plate["shelves"][0]["x"] = w + GAP

    if plate["items"]:
        plates.append(plate["items"])

    return plates

# ----------------------------
# EXPORT
# ----------------------------
_TYPE_FLAGS = {
    "round_":      lambda: EXPORT_ROUND,
    "oval_":       lambda: EXPORT_OVAL,
    "square_":     lambda: EXPORT_SQUARE,
    "rect_":       lambda: EXPORT_RECT,
    "pill_":       lambda: EXPORT_PILL,
    "slot_round_": lambda: EXPORT_SLOT,
    "slot_square_":lambda: EXPORT_SLOT,
    "slot_rect_":  lambda: EXPORT_SLOT,
}

def export_stl(obj):
    for prefix, flag in _TYPE_FLAGS.items():
        if obj.name.startswith(prefix) and not flag():
            return
    out  = bpy.path.abspath(EXPORT_DIR)
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, f"{obj.name}.stl")
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    print(f"  exported {obj.name} → {path}")

# ----------------------------
# BUILD
# ----------------------------
col_round  = make_collection("Round Bases")
col_oval   = make_collection("Oval Bases")
col_square = make_collection("Square Bases")
col_rect   = make_collection("Rect Bases")
col_pill   = make_collection("Pill Bases")
col_slot   = make_collection("Slotted Bases")

items = []
for d in ROUND_SIZES:
    obj = make_round(d, col_round)
    items.append((obj, float(d), float(d)))

for x, y in OVAL_SIZES:
    obj = make_oval(x, y, col_oval)
    items.append((obj, float(x), float(y)))

for s in SQUARE_SIZES:
    obj = make_square(s, col_square)
    items.append((obj, float(s), float(s)))

for x, y in RECT_SIZES:
    obj = make_rect(x, y, col_rect)
    items.append((obj, float(x), float(y)))

for length, width in PILL_SIZES:
    obj = make_pill(length, width, col_pill)
    items.append((obj, float(length), float(width)))

for cfg in SLOTTED_ROUND:
    obj = make_slotted_round(cfg["diam"], cfg["style"], col_slot)
    items.append((obj, float(cfg["diam"]), float(cfg["diam"])))

for cfg in SLOTTED_SQUARE:
    obj = make_slotted_square(cfg["size"], cfg["style"], col_slot)
    items.append((obj, float(cfg["size"]), float(cfg["size"])))

for cfg in SLOTTED_RECT:
    obj = make_slotted_rect(cfg["x"], cfg["y"], cfg["style"], col_slot)
    items.append((obj, float(cfg["x"]), float(cfg["y"])))

batches = pack_batches(items)

for b_idx, batch in enumerate(batches):
    y_base = b_idx * BATCH_SEP
    for obj, px, py in batch:
        obj.rotation_euler.x = math.pi
        obj.location.x =  px - PLATE_W / 2
        obj.location.y = (py - PLATE_H / 2) + y_base
        obj.location.z =  HEIGHT / 2

print(f"Base Factory v6 — {len(batches)} batch(es), {len(items)} bases")
for i, batch in enumerate(batches):
    print(f"  Batch {i + 1} ({len(batch)}): {', '.join(o.name for o, _, _ in batch)}")

if EXPORT_STL:
    print(f"\nExporting individual STLs to {bpy.path.abspath(EXPORT_DIR)} ...")
    for obj, _, _ in [item for batch in batches for item in batch]:
        export_stl(obj)
    print("Done.")
