# Select by Texture Color

A Blender add-on that selects faces by the color of the image texture under them. Blender's own tools can select by
material or vertex color, but not by what is painted on the texture.

A face's color is the texel of the active material's image texture at the centroid of the face's UVs. A texel matches when
no channel differs from the target color by more than the tolerance.

## Install

Blender 4.0 or newer. Edit > Preferences > Add-ons > Install from Disk, pick `select_by_texture_color.py`, and enable it.
Or open the file in the Text Editor and press Run Script.

## Use

In edit mode, select one or more faces, then Select > Select Similar > Texture Color. Every visible face whose texture
color matches a selected face is added to the selection. Hidden faces are skipped.

The "Texture Color" tab in the 3D view sidebar (N) has:

- Tolerance: the largest per-channel difference (0 to 1) that still counts as a match. Default 0.02.
- Pick From Active Face: sets the color to the texture color under the active face.
- Select, Add, Subtract: select by that color.

The eyedropper on the color swatch reads the shaded viewport, not the texture, so its colors will not match. Use Pick From
Active Face.

Requirements: the mesh needs an active UV map, and the active material needs an image texture node.

## Test

```sh
blender -b --factory-startup --python tests/test_select_by_texture_color.py -- MODEL.blend OBJECT SCRATCH_DIR
```

It runs the selection on the named object of a `.blend` file and checks the matches against the image. It also writes the
pixels the add-on read to `SCRATCH_DIR/blender-pixels.npy`. To check them against the image file, decode the file with
another library, flip it vertically (Blender's row 0 is the bottom), and compare with `numpy.abs`.
