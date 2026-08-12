import bpy
import bmesh
import math
import os

# ----------------------------
# CONFIG
# ----------------------------
ROUND_SIZES = [25, 28.5, 32, 40, 50, 65, 80, 90, 100, 130, 160]

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
    {"diam": 5.2, "depth": 2.2, "offset_deg":  0},   # 5x2mm — triangle at 0/120/240
    {"diam": 3.2, "depth": 1.2, "offset_deg": 60},   # 3x1mm — triangle at 60/180/300
]
MAGNET_RING  = 0.55   # socket ring radius as fraction of base radius
SOCKET_WALL  = 0.8    # socket tube wall thickness

ADD_MAGNETS  = True

EXPORT_STL   = True
EXPORT_DIR   = "/Users/mannil/Documents/STL_BASE"   # relative to the .blend file; change to an absolute path if needed

# ----------------------------
# LAYOUT (bin-pack onto 220 × 220 mm plates)
# ----------------------------
PLATE_W   = 220.0
PLATE_H   = 220.0
MARGIN    =   5.0   # keep-out from each edge
GAP       =   1.5   # gap between bases
BATCH_SEP = 260.0   # scene Y offset between batches

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

# ----------------------------
# GEOMETRY
# ----------------------------
def add_magnet_sockets(obj, radius):
    bpy.ops.object.mode_set(mode='OBJECT')

    r              = radius * MAGNET_RING
    floor_bottom_z = obj.location.z + HEIGHT / 2 - BOTTOM_THICKNESS
    depth          = HEIGHT - BOTTOM_THICKNESS - 1.0   # 1mm clearance above open rim

    for cfg in MAGNET_CONFIGS:
        off       = math.radians(cfg["offset_deg"])
        positions = [
            (r * math.cos(off + math.radians(a)),
             r * math.sin(off + math.radians(a)))
            for a in (0, 120, 240)
        ]
        outer_r = cfg["diam"] / 2 + SOCKET_WALL
        inner_r = cfg["diam"] / 2
        cup_z   = floor_bottom_z - depth / 2

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
    scale          = max(2.5, radius_x * 0.18)
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
def make_round(d, col):
    r   = d / 2
    obj = create_base_mesh(r)
    obj.name = f"Base_{d}mm"
    add_recess(obj, r, r)
    if ADD_MAGNETS:
        add_magnet_sockets(obj, r)
    add_text(obj, f"{d} mm", r)
    move(obj, col)
    return obj


def make_oval(x, y, col):
    rx, ry = x / 2, y / 2
    obj    = create_base_mesh(rx, ry)
    obj.name = f"Base_{x}x{y}"
    add_recess(obj, rx, ry)
    if ADD_MAGNETS:
        add_magnet_sockets(obj, rx)
    add_text(obj, f"{x}x{y} mm", rx, ry)
    move(obj, col)
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
def export_stl(obj):
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
col_round = make_collection("Round Bases")
col_oval  = make_collection("Oval Bases")

items = []
for d in ROUND_SIZES:
    obj = make_round(d, col_round)
    items.append((obj, float(d), float(d)))

for x, y in OVAL_SIZES:
    obj = make_oval(x, y, col_oval)
    items.append((obj, float(x), float(y)))

batches = pack_batches(items)

for b_idx, batch in enumerate(batches):
    y_base = b_idx * BATCH_SEP
    for obj, px, py in batch:
        obj.rotation_euler.x = math.pi
        obj.location.x =  px - PLATE_W / 2
        obj.location.y = (py - PLATE_H / 2) + y_base
        obj.location.z =  HEIGHT / 2

print(f"Base Factory v5 — {len(batches)} batch(es), {len(items)} bases")
for i, batch in enumerate(batches):
    print(f"  Batch {i + 1} ({len(batch)}): {', '.join(o.name for o, _, _ in batch)}")

if EXPORT_STL:
    print(f"\nExporting individual STLs to {bpy.path.abspath(EXPORT_DIR)} ...")
    for obj, _, _ in [item for batch in batches for item in batch]:
        export_stl(obj)
    print("Done.")
