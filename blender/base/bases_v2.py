import bpy
import bmesh
import math

# ----------------------------
# CONFIG
# ----------------------------
ROUND_SIZES = [25, 28.5, 32, 40, 50, 60, 80, 100]

OVAL_SIZES = [
    (60, 35),
    (75, 42),
    (90, 52),
    (105, 70),
    (170, 109)
]

HEIGHT = 4.0

TOP_SHRINK = 1.2         # taper amount
WALL = 1.6               # wall thickness
BOTTOM_THICKNESS = 1.2   # solid floor under hollow
MAGNET_DIAM = 5.2        # e.g. 5x2mm magnet with clearance
MAGNET_DEPTH = 2.2

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

def add_magnet_holes(obj, radius):
    bpy.ops.object.mode_set(mode='OBJECT')

    # magnet positions (triangle pattern)
    r = radius * 0.25

    positions = [
        ( r,  0, 0),
        (-r * 0.5,  r * 0.866, 0),
        (-r * 0.5, -r * 0.866, 0),
    ]

    cutters = []

    for x, y, z in positions:
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=32,
            radius=MAGNET_DIAM / 2,
            depth=MAGNET_DEPTH
        )

        cutter = bpy.context.object
        cutter.location = (
            obj.location.x + x,
            obj.location.y + y,
            obj.location.z - HEIGHT/2 + MAGNET_DEPTH/2
        )

        cutters.append(cutter)

    # apply booleans
    for cutter in cutters:
        mod = obj.modifiers.new(name="MagnetCut", type='BOOLEAN')
        mod.object = cutter
        mod.operation = 'DIFFERENCE'

        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)

        # delete cutter
        bpy.data.objects.remove(cutter, do_unlink=True)

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
def add_recess(obj):
    mod = obj.modifiers.new("Solidify", 'SOLIDIFY')
    mod.thickness = -WALL
    mod.offset = 1.0

    mod2 = obj.modifiers.new("BottomShell", 'SOLIDIFY')
    mod2.thickness = -BOTTOM_THICKNESS
    mod2.offset = -1.0

# ----------------------------
# MAIN GENERATORS
# ----------------------------
def make_round(d, col):
    obj = create_base_mesh(d/2)

    obj.name = f"Base_{d}mm"

    add_recess(obj)

    if ADD_MAGNETS:
        add_magnet_holes(obj, d/2)

    move(obj, col)
    return obj


def make_oval(x, y, col):
    obj = create_base_mesh(x/2, y/2)

    obj.name = f"Base_{x}x{y}"

    add_recess(obj)

    if ADD_MAGNETS:
        add_magnet_holes(obj, x/2)

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