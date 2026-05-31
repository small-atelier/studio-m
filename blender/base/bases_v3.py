import bpy
import bmesh
import math

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

HEIGHT = 4.0

TOP_SHRINK = 1.2         # taper amount
WALL = 1.6               # wall thickness
BOTTOM_THICKNESS = 1.2   # solid floor under hollow
MAGNET_CONFIGS = [
    {"diam": 5.2, "depth": 2.2, "offset_deg": 0},    # 5x2mm — triangle at 0/120/240
    {"diam": 3.2, "depth": 1.2, "offset_deg": 60},   # 3x1mm — triangle at 60/180/300
]
MAGNET_RING = 0.55       # ring radius as fraction of base radius

ADD_MAGNETS = True

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

SOCKET_WALL = 0.8  # wall thickness around each magnet socket

def add_magnet_sockets(obj, radius):
    bpy.ops.object.mode_set(mode='OBJECT')

    r = radius * MAGNET_RING
    floor_bottom_z = obj.location.z + HEIGHT / 2 - BOTTOM_THICKNESS
    depth = HEIGHT - BOTTOM_THICKNESS - 1.0  # always reaches to 1mm above the open bottom

    for cfg in MAGNET_CONFIGS:
        off = math.radians(cfg["offset_deg"])
        positions = [
            (r * math.cos(off + math.radians(a)),
             r * math.sin(off + math.radians(a)))
            for a in (0, 120, 240)
        ]

        outer_r = cfg["diam"] / 2 + SOCKET_WALL
        inner_r = cfg["diam"] / 2
        cup_z    = floor_bottom_z - depth / 2  # hangs down, closed end at floor

        for x, y in positions:
            # outer shell of socket
            bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=outer_r, depth=depth)
            cup = bpy.context.object
            cup.location = (obj.location.x + x, obj.location.y + y, cup_z)

            # bore out the inner pocket (open at bottom, closed at top by floor)
            bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=inner_r, depth=depth + 0.2)
            bore = bpy.context.object
            bore.location = (obj.location.x + x, obj.location.y + y, cup_z - 0.1)

            mod = cup.modifiers.new("Bore", 'BOOLEAN')
            mod.object = bore
            mod.operation = 'DIFFERENCE'
            bpy.context.view_layer.objects.active = cup
            bpy.ops.object.modifier_apply(modifier=mod.name)
            bpy.data.objects.remove(bore, do_unlink=True)

            # union socket into base
            mod = obj.modifiers.new("Socket", 'BOOLEAN')
            mod.object = cup
            mod.operation = 'UNION'
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=mod.name)
            bpy.data.objects.remove(cup, do_unlink=True)

# ----------------------------
# BASE CORE SHAPE
# ----------------------------
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

    # taper top
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)

    top = [v for v in bm.verts if v.co.z > 0]
    for v in top:
        v.co.x *= (1 - TOP_SHRINK / radius_x)
        v.co.y *= (1 - TOP_SHRINK / radius_y)

    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')

    return obj

# ----------------------------
# UNDERCUT / LIP (GW-style underside)
# ----------------------------
def add_recess(obj, radius_x, radius_y):
    # Boolean hollow: open bottom, thin top floor, WALL-thick sides
    inner_depth = HEIGHT - BOTTOM_THICKNESS + 0.1  # 0.1 bleed through the bottom face
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=1, depth=inner_depth)
    inner = bpy.context.object
    inner.scale.x = radius_x - WALL
    inner.scale.y = radius_y - WALL
    bpy.ops.object.transform_apply(scale=True)
    # center the cutter so it bleeds out the bottom but stops BOTTOM_THICKNESS from the top
    inner.location = (
        obj.location.x,
        obj.location.y,
        obj.location.z - BOTTOM_THICKNESS / 2,
    )

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

    t.data.body = text
    depth = HEIGHT - BOTTOM_THICKNESS - 1.0  # hangs to 1mm above open bottom
    t.data.extrude = depth  # Z scale = 1, so this is literal world depth

    scale = max(2.5, radius_x * 0.18)
    t.scale = (scale, scale, 1.0)

    # rotate so text faces down, readable from below
    t.rotation_euler = (0, math.pi, 0)

    # shift down by depth/2 so the back face sits exactly at the ceiling (not above it)
    ceiling_z = obj.location.z + HEIGHT / 2 - BOTTOM_THICKNESS
    t.location = (
        obj.location.x + scale * len(text) * 0.3,
        obj.location.y - scale * 0.5,
        ceiling_z - depth / 2,
    )

    bpy.ops.object.convert(target='MESH')
    raised = bpy.context.object

    # clip text to inner cavity so it can't spill outside the base walls
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
# MAIN GENERATORS
# ----------------------------
def make_round(d, col):
    r = d / 2
    obj = create_base_mesh(r)
    obj.name = f"Base_{d}mm"

    add_recess(obj, r, r)

    if ADD_MAGNETS:
        add_magnet_sockets(obj, r)

    add_text(obj, f"{d}mm", r)

    move(obj, col)
    return obj


def make_oval(x, y, col):
    rx, ry = x / 2, y / 2
    obj = create_base_mesh(rx, ry)
    obj.name = f"Base_{x}x{y}"

    add_recess(obj, rx, ry)

    if ADD_MAGNETS:
        add_magnet_sockets(obj, rx)

    add_text(obj, f"{x}x{y}", rx, ry)

    move(obj, col)
    return obj

# ----------------------------
# BUILD
# ----------------------------
col_round = make_collection("Round Bases")
col_oval = make_collection("Oval Bases")

xoff = 0
for d in ROUND_SIZES:
    obj = make_round(d, col_round)
    obj.location.x = xoff
    xoff += d + 8

yoff = -90
for x, y in OVAL_SIZES:
    obj = make_oval(x, y, col_oval)
    obj.location.x = xoff
    obj.location.y = yoff
    yoff += y + 8

print("Base Factory v2 complete")