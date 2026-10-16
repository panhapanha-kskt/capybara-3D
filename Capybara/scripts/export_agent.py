"""Export the capybara web agent: GLB (all actions + shape keys) and transparent renders.

Never saves the .blend: material swaps and render overrides only live in this session.

  blender --background capybara.blend --python export_agent.py -- --glb
  blender --background capybara.blend --python export_agent.py -- --render [--only Talking_Loop]
  blender --background capybara.blend --python export_agent.py -- --verify
"""
import bpy
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXPORT_DIR = os.path.join(ROOT, "export")
GLB_PATH = os.path.join(EXPORT_DIR, "capybara_agent.glb")
RENDER_DIR = os.path.join(EXPORT_DIR, "renders")

RIG = "Agent_Rig"
FACE = ("Agent_Eyes", "Agent_Mouth", "Agent_Blush")
STATES = ["Greeting_Sampeah", "Listening_Loop", "Thinking_Loop", "Talking_Loop",
          "Confused", "WakeUp", "Goodbye"]
LOOPS = {"Listening_Loop", "Thinking_Loop", "Talking_Loop"}

# Flat colours of the original toon ramps (linear), for the export-only unlit materials
TOON_COLORS = {"Skin": (0.631, 0.347, 0.195, 1.0), "Material": (0.258, 0.127, 0.084, 1.0)}
FACE_TEXTURE_MATERIAL = "Material.002"


# --------------------------------------------------------------------------- helpers
def use_action(name):
    # Face shape keys are driven from the rig, so only the armature needs the action.
    act = bpy.data.actions[name]
    bpy.data.objects[RIG].animation_data.action = act
    return act


def export_objects():
    rig = bpy.data.objects[RIG]
    return [rig] + [o for o in bpy.data.objects if o.parent == rig]


def find_image(mat):
    for n in mat.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image:
            return n.image
    return None


def make_unlit(mat, color=None, image=None, use_image_alpha=False):
    """Rebuild a material as the node pattern the glTF exporter writes as KHR_materials_unlit:
    Emission -> Mix(LightPath.IsCameraRay) [-> Mix with Transparent by alpha] -> Output."""
    cull = mat.use_backface_culling
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    lp = nt.nodes.new("ShaderNodeLightPath")
    tr0 = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix_cam = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix_cam.inputs["Fac"])
    nt.links.new(tr0.outputs[0], mix_cam.inputs[1])
    nt.links.new(em.outputs[0], mix_cam.inputs[2])
    tex = None
    if image is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image
        nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    else:
        em.inputs["Color"].default_value = color
    if use_image_alpha and tex is not None:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix_a = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(tex.outputs["Alpha"], mix_a.inputs["Fac"])
        nt.links.new(tr.outputs[0], mix_a.inputs[1])
        nt.links.new(mix_cam.outputs[0], mix_a.inputs[2])
        nt.links.new(mix_a.outputs[0], out.inputs["Surface"])
        mat.surface_render_method = "BLENDED"
    else:
        nt.links.new(mix_cam.outputs[0], out.inputs["Surface"])
    mat.use_backface_culling = cull


def convert_materials(objs):
    done = set()
    for ob in objs:
        if ob.type != "MESH":
            continue
        for slot in ob.material_slots:
            m = slot.material
            if m is None or m.name in done:
                continue
            done.add(m.name)
            if m.name in TOON_COLORS:
                make_unlit(m, color=TOON_COLORS[m.name])
            elif m.name == FACE_TEXTURE_MATERIAL:
                make_unlit(m, image=find_image(m))
            elif "agent_color" in m:
                img = find_image(m)
                if img is not None:
                    make_unlit(m, image=img, use_image_alpha=True)
                else:
                    make_unlit(m, color=tuple(m["agent_color"]))
            else:
                print("WARN: material left as-is:", m.name)
    return sorted(done)


# --------------------------------------------------------------------------- GLB
def export_glb():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    objs = export_objects()
    mats = convert_materials(objs)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    rig = bpy.data.objects[RIG]
    bpy.context.view_layer.objects.active = rig
    # Export from the rest pose: prop bones are keyed to scale 0 in most clips, and
    # bone-parented props would otherwise get a degenerate (zero-scale) local matrix.
    rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.scale = (1, 1, 1)
    for k in [k for k in rig.pose.bones["root"].keys() if not k.startswith("_")]:
        rig.pose.bones["root"][k] = 0.0
    bpy.context.scene.frame_set(1)
    bpy.ops.export_scene.gltf(
        filepath=GLB_PATH,
        export_format="GLB",
        use_selection=True,
        export_apply=True,              # bakes the Solidify outline hull into the mesh
        export_animations=True,
        export_animation_mode="ACTIONS",
        export_force_sampling=True,
        export_frame_range=False,
        export_anim_slide_to_zero=True,
        export_morph=True,
        export_morph_animation=True,
        export_morph_normal=False,
        export_skins=True,
        export_def_bones=False,
        export_yup=True,
        export_cameras=False,
        export_lights=False,
        export_extras=False,
    )
    print("EXPORTED", GLB_PATH, os.path.getsize(GLB_PATH), "bytes; materials:", mats)


def read_glb_json(path):
    with open(path, "rb") as f:
        data = f.read()
    magic, _, _ = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF"
    clen, ctype = struct.unpack_from("<I4s", data, 12)
    return json.loads(data[20:20 + clen].decode("utf-8"))


def verify_glb():
    g = read_glb_json(GLB_PATH)
    report = {"size_bytes": os.path.getsize(GLB_PATH), "animations": {}, "morph_targets": {},
              "materials": [], "nodes": len(g.get("nodes", [])), "triangles": 0}
    for m in g.get("materials", []):
        report["materials"].append((m.get("name"), "unlit" if "KHR_materials_unlit" in m.get("extensions", {}) else "pbr",
                                    m.get("doubleSided", False), m.get("alphaMode", "OPAQUE")))
    for mesh in g.get("meshes", []):
        names = mesh.get("extras", {}).get("targetNames")
        if names:
            report["morph_targets"][mesh["name"]] = names
        for prim in mesh["primitives"]:
            if "indices" in prim:
                report["triangles"] += g["accessors"][prim["indices"]]["count"] // 3
    for a in g.get("animations", []):
        paths = {}
        for ch in a["channels"]:
            p = ch["target"]["path"]
            paths[p] = paths.get(p, 0) + 1
        times = [g["accessors"][s["input"]].get("max", [0])[0] for s in a["samplers"]]
        report["animations"][a["name"]] = {"channels": paths, "duration_s": round(max(times), 3)}
    missing = [s for s in STATES if s not in report["animations"]]
    report["missing_actions"] = missing
    no_morph = [n for n, v in report["animations"].items() if "weights" not in v["channels"]]
    report["actions_without_morph_channels"] = no_morph
    print("VERIFY", json.dumps(report, indent=1))
    with open(os.path.join(EXPORT_DIR, "verify_report.json"), "w") as f:
        json.dump(report, f, indent=1)

    # Re-import into an empty scene as a second check
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=GLB_PATH)
    acts = sorted(a.name for a in bpy.data.actions)
    keys = {o.name: [k.name for k in o.data.shape_keys.key_blocks]
            for o in bpy.data.objects if o.type == "MESH" and o.data.shape_keys}
    print("REIMPORT actions:", acts)
    print("REIMPORT shape keys:", json.dumps(keys))
    return report


# --------------------------------------------------------------------------- renders
def setup_render():
    sc = bpy.context.scene
    sc.camera = bpy.data.objects["AgentCam_Square"]
    r = sc.render
    r.resolution_x = r.resolution_y = 512
    r.resolution_percentage = 100
    r.fps = 24
    r.film_transparent = True
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    r.image_settings.color_depth = "8"
    plane = bpy.data.objects.get("Plane")
    if plane:
        plane.hide_render = True
        plane.lineart.usage = "EXCLUDE"   # no floor line from Line Art
    return sc


def render_state(sc, name):
    act = use_action(name)
    end = int(act.frame_end) - (1 if name in LOOPS else 0)  # loops: skip duplicate seam frame
    sc.frame_start, sc.frame_end = 1, end
    folder = os.path.join(RENDER_DIR, name)
    os.makedirs(folder, exist_ok=True)
    done = [f for f in os.listdir(folder) if f.endswith(".png")]
    if len(done) == end and "--rerender" not in sys.argv:
        print("SKIP (already rendered)", name)
        return folder, end
    sc.render.filepath = os.path.join(folder, "frame_")
    bpy.ops.render.render(animation=True)
    return folder, end


def encode_webm(name, folder, nframes):
    """Pack the PNG sequence into a VP9 WebM with alpha using the sequencer (no ffmpeg CLI needed)."""
    enc = bpy.data.scenes.new(f"encode_{name}")
    enc.render.resolution_x = enc.render.resolution_y = 512
    enc.render.resolution_percentage = 100
    enc.render.fps = 24
    enc.frame_start, enc.frame_end = 1, nframes
    enc.sequence_editor_create()
    files = sorted(f for f in os.listdir(folder) if f.endswith(".png"))
    strips = enc.sequence_editor.strips if hasattr(enc.sequence_editor, "strips") else enc.sequence_editor.sequences
    st = strips.new_image("seq", os.path.join(folder, files[0]), channel=1, frame_start=1)
    for f in files[1:]:
        st.elements.append(f)
    enc.render.film_transparent = True
    im = enc.render.image_settings
    im.media_type = "VIDEO"   # Blender 5: pick the video media type before FFMPEG
    im.file_format = "FFMPEG"
    enc.render.ffmpeg.format = "WEBM"
    enc.render.ffmpeg.codec = "WEBM"
    im.color_mode = "RGBA"
    enc.render.ffmpeg.constant_rate_factor = "HIGH"
    enc.render.filepath = os.path.join(RENDER_DIR, f"{name}.webm")
    enc.render.use_file_extension = False
    bpy.ops.render.render(animation=True, scene=enc.name)
    bpy.data.scenes.remove(enc)
    return os.path.join(RENDER_DIR, f"{name}.webm")


def render_all(only=None):
    sc = setup_render()
    for name in STATES:
        if only and name not in only:
            continue
        folder, n = render_state(sc, name)
        path = encode_webm(name, folder, n)
        print("RENDERED", name, n, "frames ->", path)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
    if "--glb" in argv:
        export_glb()
    if "--verify" in argv:
        verify_glb()
    if "--render" in argv:
        render_all(only)
