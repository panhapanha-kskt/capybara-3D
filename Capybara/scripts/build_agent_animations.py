"""Build the capybara web-agent rig, face parts, props and the 7 state actions.

Re-runnable: everything this script creates is tagged ``agent_build`` and is
removed and rebuilt on every run. Existing objects only get vertex groups, an
Armature modifier, an outline Solidify modifier and extra outline material slots,
which are also cleaned up on re-run.

Run live (Blender MCP / Text editor):  exec(open(path).read())
Run headless:  blender --background capybara.blend --python build_agent_animations.py -- --save
"""
import bpy
import math
import sys
from mathutils import Vector, Quaternion

TAG = "agent_build"
COLL_NAME = "Agent_Build"
RIG_NAME = "Agent_Rig"
PARTS = {"body": "Cube", "head": "Cube.001", "arms": "Cube.002", "feet": "Cube.003"}
CENTER_Y = 0.07          # character symmetry plane (world Y)
HEAD_CENTER_Y = 0.085    # head mesh symmetry plane
OUTLINE_WORLD = 0.018    # inverted-hull outline thickness in metres
MOUTH_SCALE = 1.35       # mouth shapes are authored small; scale for widget readability

# Colours (linear) taken from the existing toon ramps / GP stroke material
DARK = (0.054, 0.007, 0.003, 1.0)
OUTLINE = (0.075, 0.012, 0.006, 1.0)
CREAM = (0.98, 0.90, 0.78, 1.0)
BLUSH = (0.85, 0.32, 0.38, 1.0)

# Character frame: faces -X, character's right is +Y (screen-left), up is +Z.
# Rotation helpers return (world_axis, degrees) tuples.
def P(d):  return ("Y", -d)   # pitch: bow forward (+) / look up (-)
def T(d):  return ("X", -d)   # tilt: top of the bone toward screen-left (+)
def Yw(d): return ("Z", d)    # yaw: turn toward screen-right (+)
def AIM(x, y, z): return ("AIM", (x, y, z))  # point a bone along a world direction


# --------------------------------------------------------------------------- cleanup
def cleanup():
    bone_names = {b[0] for b in BONES}
    for name in PARTS.values():
        ob = bpy.data.objects[name]
        if ob.parent and ob.parent.get(TAG):
            mw = ob.matrix_world.copy()
            ob.parent = None
            ob.matrix_world = mw
        for m in list(ob.modifiers):
            if m.name in ("Agent_Armature", "Agent_Outline"):
                ob.modifiers.remove(m)
        for vg in list(ob.vertex_groups):
            if vg.name in bone_names:
                ob.vertex_groups.remove(vg)
        mats = ob.data.materials
        for i in reversed(range(len(mats))):
            if mats[i] and mats[i].get(TAG):
                mats.pop(index=i)
    for ob in list(bpy.data.objects):
        if ob.get(TAG):
            bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.actions, bpy.data.meshes, bpy.data.armatures, bpy.data.materials,
                 bpy.data.cameras, bpy.data.images, bpy.data.curves):
        for d in list(coll):
            if d.get(TAG):
                coll.remove(d)


def tag(idblock):
    idblock[TAG] = True
    return idblock


def get_collection():
    coll = bpy.data.collections.get(COLL_NAME)
    if coll is None:
        coll = bpy.data.collections.new(COLL_NAME)
        bpy.context.scene.collection.children.link(coll)
    return coll


# --------------------------------------------------------------------------- materials
def emission_mat(name, color, cull=False, image=None, blend=False):
    m = tag(bpy.data.materials.new(name))
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = color
    em.inputs["Strength"].default_value = 1.0
    if image is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(em.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
    else:
        nt.links.new(em.outputs[0], out.inputs["Surface"])
    m.diffuse_color = color
    m.use_backface_culling = cull
    if blend:
        m.surface_render_method = "BLENDED"
    m["agent_color"] = list(color)
    return m


def blush_image():
    size = 64
    img = tag(bpy.data.images.new("Agent_BlushGradient", size, size, alpha=True))
    px = []
    for j in range(size):
        for i in range(size):
            dx = (i + 0.5) / size * 2 - 1
            dy = (j + 0.5) / size * 2 - 1
            r = min(1.0, math.hypot(dx, dy))
            a = (1 - r) ** 1.4
            a = a * a * (3 - 2 * a)
            px += [BLUSH[0], BLUSH[1], BLUSH[2], 0.75 * a]
    img.pixels[:] = px
    img.pack()
    return img


# --------------------------------------------------------------------------- rig
BONES = [
    # name, head, tail, parent
    ("root", (0.0, CENTER_Y, 0.0), (0.0, CENTER_Y, 0.25), None),
    ("body", (0.0, CENTER_Y, 0.08), (0.0, CENTER_Y, 0.9), "root"),
    ("head", (-0.15, HEAD_CENTER_Y, 1.0), (-0.15, HEAD_CENTER_Y, 1.6), "body"),
    ("ear.R", (-0.053, 0.611, 1.86), (-0.053, 0.64, 2.15), "head"),
    ("ear.L", (-0.053, -0.442, 1.86), (-0.053, -0.471, 2.15), "head"),
    ("arm.R", (-0.12, 0.55, 0.84), (-0.98, 0.393, 0.868), "body"),
    ("arm.L", (-0.12, -0.43, 0.84), (-0.98, -0.27, 0.868), "body"),
    ("foot.R", (0.156, 0.828, 0.29), (-0.738, 0.919, 0.187), "root"),
    ("foot.L", (0.156, -0.705, 0.29), (-0.738, -0.796, 0.187), "root"),
    ("prop_dots", (-0.45, HEAD_CENTER_Y, 2.32), (-0.45, HEAD_CENTER_Y, 2.42), "root"),
    ("dot.1", (-0.45, HEAD_CENTER_Y + 0.2, 2.42), (-0.45, HEAD_CENTER_Y + 0.2, 2.5), "prop_dots"),
    ("dot.2", (-0.45, HEAD_CENTER_Y, 2.42), (-0.45, HEAD_CENTER_Y, 2.5), "prop_dots"),
    ("dot.3", (-0.45, HEAD_CENTER_Y - 0.2, 2.42), (-0.45, HEAD_CENTER_Y - 0.2, 2.5), "prop_dots"),
    ("prop_question", (-0.45, -0.55, 2.2), (-0.45, -0.55, 2.3), "root"),
]
DEFORM = {"body", "head", "ear.R", "ear.L", "arm.R", "arm.L", "foot.R", "foot.L"}
PROP_BONES = {"dot.1", "dot.2", "dot.3", "prop_question"}


def build_rig(coll):
    arm = tag(bpy.data.armatures.new(RIG_NAME))
    rig = tag(bpy.data.objects.new(RIG_NAME, arm))
    coll.objects.link(rig)
    rig.show_in_front = True
    arm.display_type = "STICK"
    bpy.context.view_layer.objects.active = rig
    for o in bpy.context.selected_objects:
        o.select_set(False)
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = {}
    for name, h, t, parent in BONES:
        eb = arm.edit_bones.new(name)
        eb.head, eb.tail = Vector(h), Vector(t)
        eb.roll = 0.0
        eb.use_deform = name in DEFORM
        if parent:
            eb.parent = ebs[parent]
        ebs[name] = eb
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return rig


def add_armature_mod(ob, rig):
    mw = ob.matrix_world.copy()
    ob.parent = rig
    ob.matrix_parent_inverse = rig.matrix_world.inverted()
    ob.matrix_world = mw
    mod = ob.modifiers.new("Agent_Armature", "ARMATURE")
    mod.object = rig
    # Armature must evaluate before the outline Solidify
    ob.modifiers.move(ob.modifiers.find("Agent_Armature"), 0)
    return mod


def islands(me):
    adj = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        adj[a].append(b)
        adj[b].append(a)
    seen, out = set(), []
    for v in range(len(me.vertices)):
        if v in seen:
            continue
        stack, grp = [v], []
        seen.add(v)
        while stack:
            x = stack.pop()
            grp.append(x)
            for o in adj[x]:
                if o not in seen:
                    seen.add(o)
                    stack.append(o)
        out.append(grp)
    return out


def weight_parts(rig):
    """Rigid weights: one bone per part, 50/50 blend only on the ear seam."""
    body = bpy.data.objects[PARTS["body"]]
    g = body.vertex_groups.new(name="body")
    g.add(range(len(body.data.vertices)), 1.0, "REPLACE")

    head = bpy.data.objects[PARTS["head"]]
    mw = head.matrix_world
    ear_verts = {"R": set(), "L": set()}
    other = set()
    for p in head.data.polygons:
        if p.material_index == 0:
            side = "R" if (mw @ p.center).y > HEAD_CENTER_Y else "L"
            ear_verts[side].update(p.vertices)
        else:
            other.update(p.vertices)
    gh = head.vertex_groups.new(name="head")
    gr = head.vertex_groups.new(name="ear.R")
    gl = head.vertex_groups.new(name="ear.L")
    for v in range(len(head.data.vertices)):
        in_ear = v in ear_verts["R"] or v in ear_verts["L"]
        eg = gr if v in ear_verts["R"] else gl
        if in_ear and v in other:
            gh.add([v], 0.5, "REPLACE")
            eg.add([v], 0.5, "REPLACE")
        elif in_ear:
            eg.add([v], 1.0, "REPLACE")
        else:
            gh.add([v], 1.0, "REPLACE")

    for key, bone in (("arms", "arm"), ("feet", "foot")):
        ob = bpy.data.objects[PARTS[key]]
        gR = ob.vertex_groups.new(name=f"{bone}.R")
        gL = ob.vertex_groups.new(name=f"{bone}.L")
        for grp in islands(ob.data):
            cy = sum((ob.matrix_world @ ob.data.vertices[i].co).y for i in grp) / len(grp)
            (gR if cy > CENTER_Y else gL).add(grp, 1.0, "REPLACE")

    for name in PARTS.values():
        add_armature_mod(bpy.data.objects[name], rig)


# --------------------------------------------------------------------------- outline
def add_outline(ob, outline_mat, world_thickness=OUTLINE_WORLD, show_render=False):
    n = max(1, len(ob.data.materials))
    for _ in range(n):
        ob.data.materials.append(outline_mat)
    s = sum(abs(v) for v in ob.scale) / 3.0
    mod = ob.modifiers.new("Agent_Outline", "SOLIDIFY")
    mod.thickness = world_thickness / s
    mod.offset = 1.0
    mod.use_flip_normals = True
    mod.use_rim = False
    mod.use_even_offset = True
    mod.material_offset = n
    mod.show_render = show_render
    return mod


# --------------------------------------------------------------------------- face decals
def surface_point(head, y, z, offset):
    inv = head.matrix_world.inverted()
    o = inv @ Vector((-4.0, y, z))
    d = (inv.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()
    ok, loc, nor, _ = head.ray_cast(o, d)
    if not ok:
        return Vector((-0.9, y, z))
    wl = head.matrix_world @ loc
    wn = (head.matrix_world.inverted().transposed().to_3x3() @ nor).normalized()
    return wl + wn * offset


def strip(fn, M):
    pts = []
    for i in range(M + 1):
        u = -math.cos(math.pi * i / M)
        x, top, bot = fn(u)
        pts.append((x, top))
        pts.append((x, bot))
    return pts


def strip_faces(M, base):
    return [(base + 2 * i, base + 2 * i + 1, base + 2 * i + 3, base + 2 * i + 2) for i in range(M)]


def sq(u):
    return math.sqrt(max(0.0, 1 - u * u))


def build_decal(name, coll, rig, head, elements, shape_names, basis_name):
    """elements: list of dicts {center:(y,z), M, mat, offset, shapes:{name: fn(u)->(x,top,bot)}}.
    Shapes missing from an element fall back to that element's basis shape."""
    verts, faces, mats = [], [], []

    def element_points(el, shape):
        fn = el["shapes"].get(shape, el["shapes"][basis_name])
        cy, cz = el["center"]
        return [surface_point(head, cy - x, cz + v, el["offset"]) for x, v in strip(fn, el["M"])]

    for el in elements:
        base = len(verts)
        verts += element_points(el, basis_name)
        for f in strip_faces(el["M"], base):
            faces.append(f)
            mats.append(el["mat_index"])
    me = tag(bpy.data.meshes.new(name))
    me.from_pydata([tuple(v) for v in verts], [], faces)
    for i, p in enumerate(me.polygons):
        p.material_index = mats[i]
    ob = tag(bpy.data.objects.new(name, me))
    coll.objects.link(ob)
    ob.shape_key_add(name="Basis", from_mix=False)
    for sname in shape_names:
        kb = ob.shape_key_add(name=sname, from_mix=False)
        co = []
        for el in elements:
            co += element_points(el, sname)
        for i, v in enumerate(co):
            kb.data[i].co = v
    tag(me.shape_keys)
    g = ob.vertex_groups.new(name="head")
    g.add(range(len(me.vertices)), 1.0, "REPLACE")
    ob.parent = rig
    mod = ob.modifiers.new("Agent_Armature", "ARMATURE")
    mod.object = rig
    return ob


def eye_shapes(squint=False):
    W, H = 0.13, 0.17

    def open_(u):
        return (u * W / 2, H / 2 * sq(u), -H / 2 * sq(u))

    def wide(u):
        x, t, b = open_(u)
        return (x * 1.18, t * 1.18, b * 1.18)

    def closed(u):
        c = 0.012 * (1 - u * u) - 0.006
        th = 0.014 * sq(u) ** 0.35
        return (u * 0.075, c + th, c - th)

    def happy(u):
        c = 0.035 * (1 - abs(u) ** 1.4) - 0.01
        th = 0.012 * sq(u) ** 0.35
        return (u * 0.06, c + th, c - th)

    def shifted(dx, dy):
        return lambda u: (lambda x, t, b: (x + dx, t + dy, b + dy))(*open_(u))

    def sq_(u):
        return (u * 0.07, 0.014 * sq(u), -0.038 * sq(u))

    shapes = {"Open": open_, "Eyes_Closed": closed, "Eyes_Happy": happy, "Eyes_Wide": wide,
              "Look_Up": shifted(0, 0.032), "Look_Left": shifted(-0.032, 0), "Look_Right": shifted(0.032, 0)}
    if squint:
        shapes["Eye_Squint_R"] = sq_
    return shapes


def highlight_shapes(squint=False):
    r, hx, hy = 0.03, -0.026, 0.042

    def open_(u):
        return (hx + u * r, hy + r * sq(u), hy - r * sq(u))

    def hidden(u):
        return (hx, 0.0, 0.0)

    def wide(u):
        x, t, b = open_(u)
        return (x * 1.18, t * 1.18, b * 1.18)

    def shifted(dx, dy):
        return lambda u: (lambda x, t, b: (x + dx, t + dy, b + dy))(*open_(u))

    shapes = {"Open": open_, "Eyes_Closed": hidden, "Eyes_Happy": hidden, "Eyes_Wide": wide,
              "Look_Up": shifted(0, 0.032), "Look_Left": shifted(-0.032, 0), "Look_Right": shifted(0.032, 0)}
    if squint:
        shapes["Eye_Squint_R"] = hidden
    return shapes


EYE_KEYS = ["Eyes_Closed", "Eyes_Happy", "Eyes_Wide", "Look_Up", "Look_Left", "Look_Right", "Eye_Squint_R"]
MOUTH_KEYS = ["mouth_open", "Mouth_A", "Mouth_O", "Mouth_E", "Mouth_Smile", "Mouth_Wavy"]
BLUSH_KEYS = ["Blush_Strong"]


def mouth_shapes():
    def closed(u):
        return (u * 0.03, 0.002 * sq(u), -0.002 * sq(u))

    def open_(u):
        return (u * 0.045, 0.004 * sq(u), -0.06 * sq(u))

    def a(u):
        return (u * 0.06, 0.006 * sq(u), -0.075 * sq(u) ** 0.8)

    def o(u):
        return (u * 0.035, -0.035 + 0.04 * sq(u), -0.035 - 0.04 * sq(u))

    def e(u):
        return (u * 0.065, 0.004 * sq(u), -0.028 * sq(u))

    def smile(u):
        c = 0.03 * u * u - 0.012
        th = 0.008 * sq(u) ** 0.35
        return (u * 0.07, c + th, c - th)

    def wavy(u):
        c = -0.012 + 0.01 * math.sin(2 * math.pi * u)
        th = 0.007 * sq(u) ** 0.35
        return (u * 0.07, c + th, c - th)

    return {"Closed": closed, "mouth_open": open_, "Mouth_A": a, "Mouth_O": o, "Mouth_E": e,
            "Mouth_Smile": smile, "Mouth_Wavy": wavy}


def blush_shapes():
    def hidden(u):
        return (0.0, 0.0, 0.0)

    def strong(u):
        return (u * 0.085, 0.05 * sq(u), -0.05 * sq(u))

    return {"Hidden": hidden, "Blush_Strong": strong}


def blush_uvs(ob, M, n_elements):
    me = ob.data
    uv = me.uv_layers.new(name="UVMap")
    coords = []
    for _ in range(n_elements):
        for i in range(M + 1):
            u = -math.cos(math.pi * i / M)
            coords.append((0.5 + 0.5 * u, 0.5 + 0.5 * sq(u)))
            coords.append((0.5 + 0.5 * u, 0.5 - 0.5 * sq(u)))
    for loop in me.loops:
        uv.data[loop.index].uv = coords[loop.vertex_index]


def build_face(coll, rig):
    head = bpy.data.objects[PARTS["head"]]
    eye_dark = emission_mat("Agent_EyeDark", DARK)
    eye_hi = emission_mat("Agent_EyeHighlight", (1, 1, 1, 1))
    eyes_el = []
    # Character's right eye (screen-left) carries the squint key
    for (cy, cz), squint in (((0.41, 1.685), True), ((-0.21, 1.675), False)):
        eyes_el.append({"center": (cy, cz), "M": 20, "mat_index": 0, "offset": 0.006,
                        "shapes": eye_shapes(squint)})
        eyes_el.append({"center": (cy, cz), "M": 10, "mat_index": 1, "offset": 0.010,
                        "shapes": highlight_shapes(squint)})
    eyes = build_decal("Agent_Eyes", coll, rig, head, eyes_el, EYE_KEYS, "Open")
    eyes.data.materials.append(eye_dark)
    eyes.data.materials.append(eye_hi)

    mouth_mat = emission_mat("Agent_Mouth", DARK)
    big = {k: (lambda fn: lambda u: tuple(c * MOUTH_SCALE for c in fn(u)))(fn)
           for k, fn in mouth_shapes().items()}
    mouth = build_decal("Agent_Mouth", coll, rig, head,
                        [{"center": (0.089, 1.175), "M": 20, "mat_index": 0, "offset": 0.005,
                          "shapes": big}], MOUTH_KEYS, "Closed")
    mouth.data.materials.append(mouth_mat)

    img = blush_image()
    blush_mat = emission_mat("Agent_Blush", BLUSH, image=img, blend=True)
    bl_el = [{"center": c, "M": 12, "mat_index": 0, "offset": 0.004, "shapes": blush_shapes()}
             for c in ((0.66, 1.405), (-0.483, 1.405))]
    blush = build_decal("Agent_Blush", coll, rig, head, bl_el, BLUSH_KEYS, "Hidden")
    blush.data.materials.append(blush_mat)
    blush_uvs(blush, 12, 2)
    return eyes, mouth, blush


# --------------------------------------------------------------------------- props
def parent_to_bone(ob, rig, bone, world_matrix):
    ob.parent = rig
    ob.parent_type = "BONE"
    ob.parent_bone = bone
    bpy.context.view_layer.update()
    ob.matrix_world = world_matrix


def build_props(coll, rig, outline_mat):
    from mathutils import Matrix, Euler
    cream = emission_mat("Agent_PropFill", CREAM)
    for i in (1, 2, 3):
        me = tag(bpy.data.meshes.new(f"Agent_Dot.{i}"))
        import bmesh
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.065)
        bm.to_mesh(me)
        bm.free()
        for p in me.polygons:
            p.use_smooth = True
        ob = tag(bpy.data.objects.new(f"Agent_Dot.{i}", me))
        coll.objects.link(ob)
        me.materials.append(cream)
        add_outline(ob, outline_mat, 0.026, show_render=True)
        head = rig.data.bones[f"dot.{i}"].head_local
        parent_to_bone(ob, rig, f"dot.{i}",
                       Matrix.Translation(head) @ Matrix.Diagonal((0.6, 1, 1, 1)))

    cu = tag(bpy.data.curves.new("Agent_QuestionText", "FONT"))
    cu.body = "?"
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.size = 0.6
    cu.extrude = 0.025
    cu.bevel_depth = 0.006
    tmp = bpy.data.objects.new("tmp_q", cu)
    coll.objects.link(tmp)
    bpy.context.view_layer.update()
    me = tag(bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get())))
    me.name = "Agent_Question"
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.curves.remove(cu)
    ob = tag(bpy.data.objects.new("Agent_Question", me))
    coll.objects.link(ob)
    me.materials.clear()
    me.materials.append(cream)
    add_outline(ob, outline_mat, 0.024, show_render=True)
    head = rig.data.bones["prop_question"].head_local
    rot = Euler((math.radians(90), 0, math.radians(-90))).to_matrix().to_4x4()
    parent_to_bone(ob, rig, "prop_question", Matrix.Translation(head + Vector((0, 0, 0.08))) @ rot)


# --------------------------------------------------------------------------- camera
def build_square_camera(coll):
    src = bpy.data.objects["Camera"]
    cam = tag(bpy.data.cameras.new("AgentCam_Square"))
    cam.lens = src.data.lens
    cam.sensor_width = src.data.sensor_width
    ob = tag(bpy.data.objects.new("AgentCam_Square", cam))
    coll.objects.link(ob)
    ob.rotation_euler = src.rotation_euler.copy()
    ob.location = (-5.7, CENTER_Y, 1.28)
    return ob


# --------------------------------------------------------------------------- animation
class Anim:
    """Collects keys per channel. Rotations are given as world-axis (axis, deg) lists
    and converted to bone-local quaternions; locations as world offsets."""

    def __init__(self, name, end, loop):
        self.name, self.end, self.loop = name, end, loop
        self.ch = {}  # (kind, target, index) -> {frame: value}

    def _set(self, key, f, v):
        self.ch.setdefault(key, {})[f] = v

    def pose(self, f, bone, rot=None, loc=None, scl=None):
        if rot is not None:
            self._set(("rot", bone), f, list(rot))
        if loc is not None:
            self._set(("loc", bone), f, Vector(loc))
        if scl is not None:
            if not hasattr(scl, "__len__"):
                scl = (scl, scl, scl)
            self._set(("scl", bone), f, tuple(scl))

    def shape(self, f, key, value):
        self._set(("shape", key), f, float(value))

    def shapes(self, f, **kw):
        for k, v in kw.items():
            self.shape(f, k, v)

    def blink(self, f, base=0.0, key="Eyes_Closed"):
        self.shape(f, key, base)
        self.shape(f + 2, key, 1.0)
        self.shape(f + 3, key, 1.0)
        self.shape(f + 7, key, base)


FACE_BONE = "root"


def add_face_drivers(rig, face_objs):
    """Each shape key reads a same-named float property on the root pose bone.
    The glTF exporter bakes driven shape keys of armature children into every
    armature action, so each clip gets its own morph-weight channels."""
    pb = rig.pose.bones[FACE_BONE]
    for ob in face_objs:
        for kb in ob.data.shape_keys.key_blocks[1:]:
            pb[kb.name] = 0.0
            ui = pb.id_properties_ui(kb.name)
            ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0)
            fc = kb.driver_add("value")
            drv = fc.driver
            drv.type = "AVERAGE"
            var = drv.variables.new()
            var.name = "v"
            var.type = "SINGLE_PROP"
            var.targets[0].id_type = "OBJECT"
            var.targets[0].id = rig
            var.targets[0].data_path = f'pose.bones["{FACE_BONE}"]["{kb.name}"]'


def world_rot_to_local(rig, bone, rot):
    q = Quaternion()
    b = rig.data.bones[bone]
    for axis, val in rot:
        if axis == "AIM":  # point the bone along a world direction
            rest_dir = (b.tail_local - b.head_local).normalized()
            q = rest_dir.rotation_difference(Vector(val).normalized()) @ q
            continue
        ax = {"X": Vector((1, 0, 0)), "Y": Vector((0, 1, 0)), "Z": Vector((0, 0, 1))}[axis]
        q = Quaternion(ax, math.radians(val)) @ q
    rest = rig.data.bones[bone].matrix_local.to_quaternion()
    return rest.inverted() @ q @ rest


def world_vec_to_local(rig, bone, v):
    return rig.data.bones[bone].matrix_local.to_3x3().inverted() @ v


def fcurves_of(action):
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    yield fc


def bake_anim(anim, rig, face_objs):
    act = tag(bpy.data.actions.new(anim.name))
    act.use_fake_user = True
    act.use_frame_range = True
    act.frame_start, act.frame_end = 1, anim.end
    act.use_cyclic = anim.loop

    rig.animation_data_create()
    rig.animation_data.action = act
    # Shape keys are animated through custom properties on the root pose bone
    # (see add_face_drivers), so one armature action carries the whole state.
    key_owner = [kb.name for ob in face_objs for kb in ob.data.shape_keys.key_blocks[1:]]

    # Every channel is keyed at the first and last frame so clips fully define the pose.
    bones = [b.name for b in rig.data.bones if b.name != "root"]
    defaults = {}
    for b in bones:
        defaults[("rot", b)] = []
        defaults[("loc", b)] = Vector((0, 0, 0))
        defaults[("scl", b)] = (0.0, 0.0, 0.0) if b in PROP_BONES else (1.0, 1.0, 1.0)
    for name in key_owner:
        defaults[("shape", name)] = 0.0
    for key, dflt in defaults.items():
        d = anim.ch.setdefault(key, {})
        if 1 not in d:
            first = min(d) if d else None
            d[1] = d[first] if first is not None else dflt
        if anim.end not in d:
            d[anim.end] = d[1] if anim.loop else (d[max(d)] if d else dflt)
        if anim.loop:
            d[anim.end] = d[1]

    for key, frames in anim.ch.items():
        kind, target = key
        if kind == "shape":
            fc = act.fcurve_ensure_for_datablock(rig, f'pose.bones["{FACE_BONE}"]["{target}"]',
                                                 group_name="face")
            for f, v in sorted(frames.items()):
                fc.keyframe_points.insert(f, v, options={"FAST"})
            continue
        path = {"rot": "rotation_quaternion", "loc": "location", "scl": "scale"}[kind]
        n = 4 if kind == "rot" else 3
        fcs = [act.fcurve_ensure_for_datablock(rig, f'pose.bones["{target}"].{path}', index=i, group_name=target)
               for i in range(n)]
        prev = None
        for f, v in sorted(frames.items()):
            if kind == "rot":
                q = world_rot_to_local(rig, target, v)
                if prev is not None and prev.dot(q) < 0:
                    q.negate()
                prev = q
                vals = list(q)
            elif kind == "loc":
                vals = list(world_vec_to_local(rig, target, v))
            else:
                vals = list(v)
            for i in range(n):
                fcs[i].keyframe_points.insert(f, vals[i], options={"FAST"})

    for fc in fcurves_of(act):
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
        if anim.loop:
            fc.modifiers.new("CYCLES")
        fc.update()
    return act


# ---- the 7 states (24 fps) -------------------------------------------------------
def greeting():
    a = Anim("Greeting_Sampeah", 84, False)
    a.shapes(1, Eyes_Closed=1)
    a.shapes(5, Eyes_Closed=1)
    a.shapes(9, Eyes_Closed=0, Eyes_Wide=0.45)
    a.shapes(15, Eyes_Wide=0)
    # anticipation squash, then a little stretch as it wakes into the greeting
    a.pose(1, "body", scl=1)
    a.pose(6, "body", scl=(1.03, 0.96, 1.03))
    a.pose(12, "body", scl=(0.98, 1.03, 0.98))
    a.pose(17, "body", scl=1)
    # palms come together at chest level (peer-level sampeah)
    a.pose(8, "arm.R", rot=[], loc=(0, 0, 0))
    a.pose(8, "arm.L", rot=[], loc=(0, 0, 0))
    for f in (21, 50):
        # palms meet in front of the chin: arms slide forward a little as they rise
        a.pose(f, "arm.R", rot=[Yw(15), ("Y", 14)], loc=(-0.16, 0, 0.02))
        a.pose(f, "arm.L", rot=[Yw(-15), ("Y", 14)], loc=(-0.16, 0, 0.02))
    a.pose(60, "arm.R", rot=[Yw(-7), ("Y", 5)], loc=(-0.03, 0, 0))
    a.pose(60, "arm.L", rot=[Yw(7), ("Y", 5)], loc=(-0.03, 0, 0))
    a.pose(74, "arm.R", rot=[])
    a.pose(74, "arm.L", rot=[])
    # bow of body and head, eyes softly closed while bowing
    for f, d in ((22, 0), (32, 12), (42, 12), (52, -2), (58, 0)):
        a.pose(f, "body", rot=[P(d)])
    for f, d in ((24, 0), (34, 4), (44, 4), (54, -4), (62, 0)):
        a.pose(f, "head", rot=[P(d)])
    a.shapes(28, Eyes_Closed=0)
    a.shapes(33, Eyes_Closed=0.9)
    a.shapes(42, Eyes_Closed=0.9)
    a.shapes(47, Eyes_Closed=0)
    # happy return
    a.shapes(49, Eyes_Happy=0, Mouth_Smile=0, Blush_Strong=0)
    a.shapes(55, Eyes_Happy=1, Mouth_Smile=1, Blush_Strong=0.7)
    a.shapes(70, Eyes_Happy=1, Mouth_Smile=1, Blush_Strong=0.7)
    a.shapes(80, Eyes_Happy=0, Mouth_Smile=0, Blush_Strong=0)
    for ear, s in (("ear.R", 1), ("ear.L", -1)):
        a.pose(48, ear, rot=[])
        a.pose(54, ear, rot=[P(12)])
        a.pose(59, ear, rot=[P(-4)])
        a.pose(65, ear, rot=[])
    a.pose(54, "head", rot=[P(-4), T(6)])
    a.pose(72, "head", rot=[T(3)])
    a.pose(84, "head", rot=[])
    a.pose(52, "body", loc=(0, 0, 0))
    a.pose(56, "body", loc=(0, 0, 0.03))
    a.pose(61, "body", loc=(0, 0, 0))
    return a


def listening():
    a = Anim("Listening_Loop", 97, True)
    for f, t, p in ((1, 6, -3), (30, 8, -2), (60, 7, -4), (97, 6, -3)):
        a.pose(f, "head", rot=[P(p), T(t)])
    for f, s in ((1, 1.0), (24, 1.022), (48, 1.0), (72, 1.022), (97, 1.0)):
        a.pose(f, "body", scl=(1 + (s - 1) * 0.5, s, 1 + (s - 1) * 0.5))
    for ear, off in (("ear.R", 0), ("ear.L", 10)):
        for f, d in ((1, 10), (24 + off, 13), (52 + off, 9), (78, 12), (97, 10)):
            a.pose(f, ear, rot=[P(d)])
    a.blink(28)
    a.blink(74)
    a.blink(83)
    a.shapes(40, Look_Left=0)
    a.shapes(42, Look_Left=0.35)
    a.shapes(58, Look_Left=0.35)
    a.shapes(60, Look_Left=0, Look_Right=0)
    a.shapes(62, Look_Right=0.3)
    a.shapes(70, Look_Right=0.3)
    a.shapes(72, Look_Right=0)
    a.shapes(1, Mouth_Smile=0.3)
    return a


def thinking():
    a = Anim("Thinking_Loop", 97, True)
    chin = [Yw(17), ("Y", 13)]
    tap = [Yw(17), ("Y", 9)]
    for f in (1, 22, 30, 60, 68, 97):
        a.pose(f, "arm.R", rot=chin)
    for f in (25, 28):
        a.pose(f, "arm.R", rot=tap if f == 25 else chin)
    for f in (63, 66):
        a.pose(f, "arm.R", rot=tap if f == 63 else chin)
    a.pose(26, "arm.R", rot=chin)
    a.pose(64, "arm.R", rot=chin)
    for f, t in ((1, -5), (48, 5), (97, -5)):
        a.pose(f, "head", rot=[P(-5), T(t)])
        a.pose(f, "body", rot=[T(-t * 0.35)])
    a.shapes(1, Look_Up=0.85, Look_Left=0.55, Look_Right=0)
    a.shapes(40, Look_Up=0.85, Look_Left=0.55, Look_Right=0)
    a.shapes(46, Look_Up=0.75, Look_Left=0, Look_Right=0.5)
    a.shapes(88, Look_Up=0.75, Look_Left=0, Look_Right=0.5)
    a.shapes(94, Look_Up=0.85, Look_Left=0.55, Look_Right=0)
    a.blink(56)
    a.shapes(1, Mouth_Wavy=0.25)
    for i in (1, 2, 3):
        bone = f"dot.{i}"
        for k in range(0, 12):
            f = 1 + k * 8
            z = 0.05 * math.sin(2 * math.pi * (k * 8) / 32 - i * 1.1)
            a.pose(f, bone, loc=(0, 0, z), scl=1)
    for ear, s in (("ear.R", 1), ("ear.L", -1)):
        for f, d in ((1, 4), (48, 8), (97, 4)):
            a.pose(f, ear, rot=[P(d if ear == "ear.R" else 12 - d)])
    return a


def talking():
    a = Anim("Talking_Loop", 73, True)
    seq = [(1, None, 0), (4, "Mouth_A", 0.9), (8, "Mouth_O", 0.8), (11, "Mouth_E", 0.75), (14, None, 0),
           (17, "Mouth_A", 1.0), (21, "Mouth_E", 0.7), (23, None, 0), (27, "Mouth_O", 0.9),
           (32, "Mouth_A", 0.8), (36, None, 0), (40, "Mouth_E", 0.85), (43, "Mouth_A", 0.95),
           (47, "Mouth_O", 0.7), (50, None, 0), (55, "Mouth_A", 0.85), (58, "Mouth_E", 0.8),
           (62, "Mouth_O", 0.85), (66, None, 0), (73, None, 0)]
    for f, k, v in seq:
        for name in ("Mouth_A", "Mouth_O", "Mouth_E"):
            a.shape(f, name, v if name == k else 0.0)
    a.shapes(1, Mouth_Smile=0.15)
    for f, p, t in ((1, 0, 2), (9, 2, 1.5), (17, -1, 0), (27, 2.5, -1), (37, 0, -2),
                    (47, 2, -1), (58, -1, 1), (73, 0, 2)):
        a.pose(f, "head", rot=[P(p), T(t)])
    for f, s in ((1, 1.0), (36, 1.015), (73, 1.0)):
        a.pose(f, "body", scl=(1, s, 1))
    a.blink(19)
    a.blink(57)
    for ear, off in (("ear.R", 0), ("ear.L", 6)):
        for f, d in ((1, 6), (20 + off, 9), (44 + off, 5), (73, 6)):
            a.pose(f, ear, rot=[P(d)])
    return a


def confused():
    a = Anim("Confused", 60, False)
    a.pose(1, "head", rot=[])
    a.pose(6, "head", rot=[T(3)])
    a.pose(14, "head", rot=[T(-15), P(-3)])
    a.pose(46, "head", rot=[T(-14), P(-2)])
    a.pose(58, "head", rot=[])
    a.pose(10, "ear.L", rot=[])
    a.pose(18, "ear.L", rot=[("X", 38)])
    a.pose(46, "ear.L", rot=[("X", 35)])
    a.pose(57, "ear.L", rot=[])
    a.shapes(10, Eye_Squint_R=0, Mouth_Wavy=0)
    a.shapes(16, Eye_Squint_R=0.85, Mouth_Wavy=1)
    a.shapes(44, Eye_Squint_R=0.85, Mouth_Wavy=1)
    a.shapes(54, Eye_Squint_R=0, Mouth_Wavy=0)
    # "?" pops with squash & stretch, then shrinks away
    for f, s in ((8, 0.0), (13, (0.8, 1.35, 0.8)), (16, (1.15, 0.85, 1.15)), (19, 1.0),
                 (46, 1.0), (50, 1.15), (56, 0.0)):
        a.pose(f, "prop_question", scl=s)
    for f, z in ((8, -0.1), (14, 0.04), (19, 0.0), (32, 0.03), (46, 0.0)):
        a.pose(f, "prop_question", loc=(0, 0, z))
    # shrug
    for arm, s in (("arm.R", 1), ("arm.L", -1)):
        a.pose(24, arm, rot=[])
        a.pose(29, arm, rot=[Yw(-13 * s), ("Y", 11)])
        a.pose(36, arm, rot=[Yw(-13 * s), ("Y", 11)])
        a.pose(43, arm, rot=[Yw(2 * s), ("Y", -2)])
        a.pose(48, arm, rot=[])
    a.pose(24, "body", loc=(0, 0, 0), scl=1)
    a.pose(29, "body", loc=(0, 0, 0.04), scl=(0.98, 1.03, 0.98))
    a.pose(36, "body", loc=(0, 0, 0.04), scl=1)
    a.pose(42, "body", loc=(0, 0, 0), scl=(1.025, 0.965, 1.025))
    a.pose(48, "body", loc=(0, 0, 0), scl=1)
    return a


def wake_up():
    a = Anim("WakeUp", 84, False)
    sleep_head = [P(9)]
    a.pose(1, "head", rot=sleep_head)
    a.pose(16, "head", rot=sleep_head)
    a.pose(1, "body", rot=[P(3)], scl=1)
    a.pose(9, "body", scl=(1.015, 1.03, 1.015))
    a.pose(17, "body", rot=[P(3)], scl=1)
    a.pose(1, "ear.R", rot=[("X", -8)])
    a.pose(18, "ear.R", rot=[("X", -8)])
    a.pose(1, "ear.L", rot=[("X", 8)])
    a.pose(18, "ear.L", rot=[("X", 8)])
    a.shapes(1, Eyes_Closed=1)
    a.shapes(22, Eyes_Closed=1, Eyes_Wide=0)
    # anticipation dip, then startle
    a.pose(22, "body", rot=[P(5)], scl=(1.045, 0.93, 1.045), loc=(0, 0, 0))
    a.pose(22, "head", rot=[P(12)])
    a.pose(26, "body", rot=[P(-3)], scl=(0.96, 1.07, 0.96), loc=(0, 0, 0.05))
    a.pose(26, "head", rot=[P(-7)])
    a.shapes(25, Eyes_Closed=0, Eyes_Wide=1)
    a.pose(31, "body", rot=[], scl=(1.02, 0.98, 1.02), loc=(0, 0, 0))
    a.pose(35, "body", scl=1)
    a.pose(36, "head", rot=[P(-2)])
    for ear, s in (("ear.R", 1), ("ear.L", -1)):
        a.pose(25, ear, rot=[])
        a.pose(28, ear, rot=[P(16)])
        a.pose(32, ear, rot=[P(-6)])
        a.pose(37, ear, rot=[P(2)])
    a.shapes(40, Eyes_Wide=0.6)
    a.blink(38, 0.0)
    a.blink(45, 0.0)
    a.blink(53, 0.0)
    a.shapes(60, Eyes_Wide=0)
    # little full-body shake, head and ears lagging behind (overlap)
    shake = [(56, 0), (58, 6), (60, -6), (62, 5), (64, -4), (66, 2.5), (68, -1), (70, 0)]
    for f, d in shake:
        a.pose(f, "body", rot=[Yw(d)])
        a.pose(f + 1, "head", rot=[P(-2), Yw(d * 1.3)])
        a.pose(f + 2, "ear.R", rot=[("X", -d * 2.2)])
        a.pose(f + 2, "ear.L", rot=[("X", -d * 2.2)])
    a.pose(78, "head", rot=[])
    a.pose(84, "head", rot=[])
    return a


def goodbye():
    a = Anim("Goodbye", 72, False)
    a.pose(1, "arm.L", rot=[])
    a.pose(6, "arm.L", rot=[("Y", -4)])
    raised = AIM(-0.38, -0.5, 0.78)   # paw up beside the head (screen-right)
    for f, roll in ((12, 8), (17, -14), (22, 14), (27, -14), (32, 12), (36, 0)):
        a.pose(f, "arm.L", rot=[raised, ("X", roll)])
    a.pose(42, "arm.L", rot=[("Y", -6)])
    a.pose(46, "arm.L", rot=[("Y", 3)])
    a.pose(50, "arm.L", rot=[])
    a.pose(4, "head", rot=[])
    a.pose(12, "head", rot=[T(-6)])
    a.pose(36, "head", rot=[T(-6)])
    for f, d in ((44, 0), (52, 12), (58, 12), (64, -1), (68, 0)):
        a.pose(f, "body", rot=[P(d)])
    for f, d in ((46, 0), (54, 8), (60, 8), (66, -2), (72, 0)):
        a.pose(f, "head", rot=[P(d)])
    a.shapes(1, Mouth_Smile=0, Blush_Strong=0, Eyes_Happy=0)
    a.shapes(8, Mouth_Smile=1, Blush_Strong=0.6)
    a.shapes(72, Mouth_Smile=1, Blush_Strong=0.6)
    a.blink(24)
    a.shapes(50, Eyes_Happy=0)
    a.shapes(55, Eyes_Happy=1)
    a.shapes(72, Eyes_Happy=1)
    for ear in ("ear.R", "ear.L"):
        a.pose(10, ear, rot=[])
        a.pose(16, ear, rot=[P(8)])
        a.pose(40, ear, rot=[P(8)])
        a.pose(50, ear, rot=[])
    return a


STATES = [greeting, listening, thinking, talking, confused, wake_up, goodbye]


# --------------------------------------------------------------------------- main
def main(save=False):
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    cleanup()
    coll = get_collection()
    tag(coll)
    gp = bpy.data.objects.get("EYE")
    if gp:
        for layer in gp.data.layers:
            if layer.name == "LINE":
                layer.hide = True

    outline_mat = emission_mat("Outline_Brown", OUTLINE, cull=True)
    rig = build_rig(coll)
    weight_parts(rig)
    for name in PARTS.values():
        add_outline(bpy.data.objects[name], outline_mat, show_render=False)
    eyes, mouth, blush = build_face(coll, rig)
    build_props(coll, rig, outline_mat)
    build_square_camera(coll)

    face = [eyes, mouth, blush]
    add_face_drivers(rig, face)
    actions = [bake_anim(fn(), rig, face) for fn in STATES]
    # Leave the file showing Listening; every action stays available via fake user.
    rig.animation_data.action = bpy.data.actions["Listening_Loop"]
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, 96  # Listening cycle (frame 97 == frame 1)
    sc.frame_set(1)
    if save:
        bpy.ops.wm.save_mainfile()
    return {"actions": [(a.name, int(a.frame_start), int(a.frame_end)) for a in actions],
            "bones": len(rig.data.bones),
            "eye_keys": [k.name for k in eyes.data.shape_keys.key_blocks],
            "mouth_keys": [k.name for k in mouth.data.shape_keys.key_blocks]}


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    print(main(save="--save" in argv))
