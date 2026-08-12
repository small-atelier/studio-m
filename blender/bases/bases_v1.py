import bpy
import bmesh
import math

# ----------------------------
# PARAMETERS
# ----------------------------
round_sizes = [25, 28.5, 32, 40, 50, 60, 80, 100]

oval_sizes = [
    (60, 35),
    (75, 42),
    (90, 52),
    (105, 70),
    (170, 109)
]

HEIGHT = 4.0
TOP_SHRINK = 1.2        # taper amount
WALL = 1.6              # hollow wall thickness
TEXT_DEPTH = 0.4

# ----------------------------
# UTILS
# ----------------------------
def make_collection(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col

def move_to_collection(obj, col):
    for c in obj.users_collection:
        c.objects.unlink(obj)
    col.objects.link(obj)

# ----------------------------
# BASE CREATION
# ----------------------------
def create_round_base(d, col):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=d/2, depth=HEIGHT)
    obj = bpy.context.object
    obj.name = f"Base_{d}mm"

    # Taper top
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)

    top_verts = [v for v in bm.verts if v.co.z > 0]
    for v in top_verts:
        v.co.x *= (1 - TOP_SHRINK / d)
        v.co.y *= (1 - TOP_SHRINK / d)

    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')

    # Hollow underside
    solid = obj.modifiers.new("Solidify", 'SOLIDIFY')
    solid.thickness = -WALL

    # Label text
    bpy.ops.object.text_add()
    txt = bpy.context.object
    txt.data.body = f"{d}mm"
    txt.scale = (1.5, 1.5, 1.5)
    txt.location = (0, 0, -HEIGHT/2 + 0.2)

    # Convert text to mesh
    bpy.ops.object.convert(target='MESH')

    # Boolean engrave
    bool_mod = obj.modifiers.new("TextCut", 'BOOLEAN')
    bool_mod.object = txt
    bool_mod.operation = 'DIFFERENCE'

    move_to_collection(obj, col)
    move_to_collection(txt, col)

    return obj

def create_oval_base(x, y, col):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=1, depth=HEIGHT)
    obj = bpy.context.object
    obj.scale.x = x / 2
    obj.scale.y = y / 2
    obj.name = f"Base_{x}x{y}"

    # Apply scale
    bpy.ops.object.transform_apply(scale=True)

    # Taper
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)

    top_verts = [v for v in bm.verts if v.co.z > 0]
    for v in top_verts:
        v.co.x *= (1 - TOP_SHRINK / x)
        v.co.y *= (1 - TOP_SHRINK / y)

    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')

    # Hollow underside
    solid = obj.modifiers.new("Solidify", 'SOLIDIFY')
    solid.thickness = -WALL

    move_to_collection(obj, col)
    return obj

# ----------------------------
# MAIN
# ----------------------------
col_round = make_collection("Round Bases")
col_oval = make_collection("Oval Bases")

# Round bases
x_offset = 0
for d in round_sizes:
    obj = create_round_base(d, col_round)
    obj.location.x = x_offset
    x_offset += d + 10

# Oval bases
y_offset = -80
for x, y in oval_sizes:
    obj = create_oval_base(x, y, col_oval)
    obj.location.x = x_offset
    obj.location.y = y_offset
    y_offset += y + 10

print("Bases generated!")