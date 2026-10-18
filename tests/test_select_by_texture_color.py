"""Checks select_by_texture_color.py on a .blend file with an image-textured, UV-mapped mesh.

    blender -b --factory-startup --python tests/test_select_by_texture_color.py -- MODEL.blend OBJECT SCRATCH_DIR

OBJECT is the mesh object's name, and its active material needs an image texture. SCRATCH_DIR receives the pixel array
the add-on read (blender-pixels.npy) and, for a packed image, the image file, so the reads can be compared with the file
decoded by another library (see the README).
"""

import os
import sys

import bmesh
import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
blend_path, object_name, scratch = argv[0], argv[1], argv[2]
addon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "select_by_texture_color.py")

bpy.ops.wm.open_mainfile(filepath=blend_path)

namespace = {"__name__": "select_by_texture_color"}
exec(open(addon_path).read(), namespace)

obj = bpy.data.objects[object_name]
image = namespace["image_of"](obj.active_material)
assert image is not None, "active material has no image"

pixels = namespace["read_pixels"](image)
height, width = pixels.shape[:2]
print("IMAGE", image.name, width, height)

if image.packed_file is not None:
    with open(os.path.join(scratch, "packed-image" + os.path.splitext(image.name)[1]), "wb") as out:
        out.write(image.packed_file.data)
np.save(os.path.join(scratch, "blender-pixels.npy"), pixels[:, :, :3])

bm = bmesh.new()
bm.from_mesh(obj.data)
uv_layer = bm.loops.layers.uv.active
faces = list(bm.faces)

picked = namespace["face_uv"](faces[0], uv_layer)
color = namespace["texel_rgb"](pixels, picked)
tolerance = 0.02
matches = [i for i, f in enumerate(faces)
           if namespace["face_matches"](pixels, namespace["face_uv"](f, uv_layer), color, tolerance)]
print("PICKED", color.tolist(), "FACES", len(faces), "MATCHES", len(matches))
assert 0 in matches, "the picked face does not match itself"

for i in matches:
    texel = namespace["texel_rgb"](pixels, namespace["face_uv"](faces[i], uv_layer))
    assert np.max(np.abs(texel - color)) <= tolerance, f"face {i} is outside the tolerance"

selected = np.zeros(len(faces), dtype=bool)
selected[0] = True
texels = namespace["texels_at"](pixels, np.array([namespace["face_uv"](f, uv_layer) for f in faces]))
similar = namespace["similar_mask"](texels, selected, tolerance)
print("SIMILAR", int(similar.sum()))
assert similar[0], "the selected face is not similar to itself"
assert similar.sum() == len(matches), "similar_mask disagrees with the per-face match"
print("OK")
bm.free()
