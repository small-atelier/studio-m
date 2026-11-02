"""
Glyph band proof: cuts both carapace-plate niches into the baseline body once (saved as the shared
prepped body parts/<name>/<body file> + band.json), then seats one seeded set of line-glyph
solids per plate in them; renders + a review STL of body and glyphs together. Settings come from
the recipe's [glyphs] section.

  /Applications/Blender.app/Contents/MacOS/Blender --background --python tools/glyph_proof.py
"""
import os
import random
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import band                                     # noqa: E402
import kitbash                                  # noqa: E402

SEED = 1


def main():
    recipe = kitbash.load_recipe(os.path.join(ROOT, "recipes", "lokhust.toml"))
    out_dir = kitbash.data_dir(recipe, "out")
    parts_dir = kitbash.data_dir(recipe, "parts")
    os.makedirs(parts_dir, exist_ok=True)
    cfg = recipe["glyphs"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    body = kitbash.import_stl(os.path.join(recipe["source"], recipe["body"]), "body")
    kitbash.colour(body, (0.75, 0.75, 0.75, 1))
    dg = bpy.context.evaluated_depsgraph_get()

    data = band.cut_niches(body, cfg, dg)
    print(f"BAND L={data['length']:.2f}  W={cfg['width']}  body now {len(body.data.polygons)} faces")
    body_stl = os.path.join(parts_dir, recipe["body"])
    kitbash.export_stl([body], body_stl)
    band.save(data, os.path.join(parts_dir, "band.json"))
    print(f"EXPORT {body_stl} + band.json")

    tree = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())
    rng = random.Random(SEED)
    pieces, centres = [], []
    for side in band.SIDES:
        verts, faces, kinds = band.place_glyphs(tree, data, side, cfg, rng)
        pieces.append(kitbash.mesh_object(f"glyphs{side:+d}", verts, faces, (0.85, 0.7, 0.35, 1)))
        centres.append(Vector(verts.mean(0)))
        print(f"GLYPHS side {side:+d}: {kinds}  {len(verts)} verts")

    sc = bpy.context.scene
    sc.display.shading.show_cavity = True
    cam = kitbash.Camera(900)
    files = [cam.shoot(os.path.join(out_dir, "glyph_proof_top.png"), "top", (centres[0] + centres[1]) / 2, 34)]
    for side, c in zip(band.SIDES, centres):
        up = Vector(data["up"][side])
        kitbash.Camera.VIEWS[f"rake{side}"] = tuple(up * 0.45 + Vector((side * 0.9, 0.35, 0)))   # low, from outboard
        files.append(cam.shoot(os.path.join(out_dir, f"glyph_proof_rake{side:+d}.png"), f"rake{side}",
                               c, data["length"] * 1.3))
    kitbash.Camera.VIEWS["wide"] = (0.6, 1.0, 0.9)
    files.append(cam.shoot(os.path.join(out_dir, "glyph_proof_wide.png"), "wide", Vector((0.86, 18, -6)), 50))
    kitbash.contact_sheet(files, os.path.join(out_dir, "glyph_proof_sheet.png"), 4)

    stl = os.path.join(out_dir, "glyph_proof_body.stl")
    kitbash.export_stl([body] + pieces, stl)
    print(f"EXPORT {stl}")


main()
