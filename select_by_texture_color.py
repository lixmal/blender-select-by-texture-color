"""Select faces by the color of the texture under them.

Install it as an add-on, or run it from the Text Editor (Run Script). In edit mode, Select > Select Similar > Texture Color
adds every face whose texture color matches one of the selected faces. The "Texture Color" panel in the 3D view's sidebar (N)
selects by a color you pick: Select, Add or Subtract, or Pick From Active Face to take the color under the active face.

A face's color is the texel of the active material's image texture at the centroid of the face's UVs. The match is
per channel: a texel matches when no channel differs from the picked color by more than the tolerance. Faces are
judged one by one, so a face is selected as a whole or not at all.

The eyedropper on the color swatch reads the shaded viewport, not the texture, so it will not match. Use Pick From Active Face.
"""

bl_info = {
    "name": "Select by Texture Color",
    "author": "Viktor Liu",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "category": "Mesh",
    "description": "Select faces whose texture color at their UV centroid matches a picked color",
}

import bmesh
import bpy
import numpy as np
from bpy.props import EnumProperty, FloatProperty, FloatVectorProperty, PointerProperty
from bpy.types import Operator, Panel, PropertyGroup


def image_of(material):
    if material is None or not material.use_nodes:
        return None
    for node in material.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image is not None:
            return node.image
    return None


def read_pixels(image):
    width, height = image.size
    flat = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(flat)
    return flat.reshape(height, width, 4)


def face_uv(face, uv_layer):
    return np.mean([loop[uv_layer].uv for loop in face.loops], axis=0)


def texel_rgb(pixels, uv):
    height, width = pixels.shape[:2]
    u, v = uv % 1.0
    x = min(int(u * width), width - 1)
    y = min(int(v * height), height - 1)
    return pixels[y, x, :3]


def face_matches(pixels, uv, color, tolerance):
    return bool(np.max(np.abs(texel_rgb(pixels, uv) - color)) <= tolerance)


def texels_at(pixels, uvs):
    height, width = pixels.shape[:2]
    uvs = np.mod(uvs, 1.0)
    x = np.minimum((uvs[:, 0] * width).astype(int), width - 1)
    y = np.minimum((uvs[:, 1] * height).astype(int), height - 1)
    return pixels[y, x, :3]


def similar_mask(texels, selected, tolerance):
    mask = np.zeros(len(texels), dtype=bool)
    for color in np.unique(texels[selected], axis=0):
        mask |= np.max(np.abs(texels - color), axis=1) <= tolerance
    return mask


class TextureColorPick(PropertyGroup):
    color: FloatVectorProperty(
        name="Color",
        subtype='COLOR_GAMMA',
        size=3,
        min=0.0,
        max=1.0,
        default=(0.5, 0.5, 0.5),
    )
    tolerance: FloatProperty(
        name="Tolerance",
        description="Largest per-channel difference that still counts as a match",
        min=0.0,
        max=1.0,
        default=0.02,
        precision=3,
    )


def edit_context_error(context):
    obj = context.object
    if obj is None or obj.type != 'MESH' or obj.mode != 'EDIT':
        return "Enter edit mode on a mesh"
    if bmesh.from_edit_mesh(obj.data).loops.layers.uv.active is None:
        return "The mesh has no active UV map"
    if image_of(obj.active_material) is None:
        return "The active material has no image texture"
    return None


class TEXCOLOR_OT_select_by_texture_color(Operator):
    bl_idname = "mesh.texcolor_select_by_texture_color"
    bl_label = "Select by Texture Color"
    bl_description = "Select the faces whose texture color matches the picked color"
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(
        name="Mode",
        items=[
            ('REPLACE', "Replace", "Select only the matching faces"),
            ('ADD', "Add", "Add the matching faces to the selection"),
            ('SUBTRACT', "Subtract", "Deselect the matching faces"),
        ],
        default='REPLACE',
    )

    @classmethod
    def poll(cls, context):
        return edit_context_error(context) is None

    def execute(self, context):
        error = edit_context_error(context)
        if error:
            self.report({'ERROR'}, error)
            return {'CANCELLED'}

        obj = context.object
        pick = context.scene.texcolor_texture_pick
        pixels = read_pixels(image_of(obj.active_material))
        color = np.array(pick.color)

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.active
        if self.mode == 'REPLACE':
            for face in bm.faces:
                face.select_set(False)

        count = 0
        for face in bm.faces:
            if not face_matches(pixels, face_uv(face, uv_layer), color, pick.tolerance):
                continue
            face.select_set(self.mode != 'SUBTRACT')
            count += 1

        bmesh.update_edit_mesh(obj.data)
        self.report({'INFO'}, f"{count} faces match")
        return {'FINISHED'}


class TEXCOLOR_OT_select_similar_texture_color(Operator):
    bl_idname = "mesh.texcolor_select_similar_texture_color"
    bl_label = "Texture Color"
    bl_description = "Add the faces whose texture color matches a selected face"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return edit_context_error(context) is None

    def execute(self, context):
        error = edit_context_error(context)
        if error:
            self.report({'ERROR'}, error)
            return {'CANCELLED'}

        obj = context.object
        tolerance = context.scene.texcolor_texture_pick.tolerance
        pixels = read_pixels(image_of(obj.active_material))

        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.active
        faces = list(bm.faces)
        selected = np.array([face.select for face in faces], dtype=bool)
        if not selected.any():
            self.report({'ERROR'}, "Select a face first")
            return {'CANCELLED'}

        uvs = np.array([face_uv(face, uv_layer) for face in faces])
        mask = similar_mask(texels_at(pixels, uvs), selected, tolerance)
        mask &= np.array([not face.hide for face in faces], dtype=bool)
        for face, match in zip(faces, mask):
            if match:
                face.select_set(True)

        bmesh.update_edit_mesh(obj.data)
        self.report({'INFO'}, f"{int(mask.sum())} faces match")
        return {'FINISHED'}


class TEXCOLOR_OT_pick_texture_color_from_face(Operator):
    bl_idname = "mesh.texcolor_pick_texture_color_from_face"
    bl_label = "Pick From Active Face"
    bl_description = "Set the picked color to the texture color under the active face"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return edit_context_error(context) is None

    def execute(self, context):
        error = edit_context_error(context)
        if error:
            self.report({'ERROR'}, error)
            return {'CANCELLED'}

        obj = context.object
        bm = bmesh.from_edit_mesh(obj.data)
        face = bm.faces.active
        if face is None:
            self.report({'ERROR'}, "No active face")
            return {'CANCELLED'}

        pixels = read_pixels(image_of(obj.active_material))
        uv_layer = bm.loops.layers.uv.active
        context.scene.texcolor_texture_pick.color = texel_rgb(pixels, face_uv(face, uv_layer))
        return {'FINISHED'}


class TEXCOLOR_PT_select_by_texture_color(Panel):
    bl_label = "Select by Texture Color"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Texture Color"

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.mode == 'EDIT'

    def draw(self, context):
        layout = self.layout
        pick = context.scene.texcolor_texture_pick
        layout.prop(pick, "color")
        layout.prop(pick, "tolerance")
        layout.operator(TEXCOLOR_OT_pick_texture_color_from_face.bl_idname, icon='EYEDROPPER')
        row = layout.row(align=True)
        row.operator(TEXCOLOR_OT_select_by_texture_color.bl_idname, text="Select").mode = 'REPLACE'
        row.operator(TEXCOLOR_OT_select_by_texture_color.bl_idname, text="Add").mode = 'ADD'
        row.operator(TEXCOLOR_OT_select_by_texture_color.bl_idname, text="Subtract").mode = 'SUBTRACT'


classes = (
    TextureColorPick,
    TEXCOLOR_OT_select_by_texture_color,
    TEXCOLOR_OT_select_similar_texture_color,
    TEXCOLOR_OT_pick_texture_color_from_face,
    TEXCOLOR_PT_select_by_texture_color,
)


def draw_select_similar(self, context):
    self.layout.operator(TEXCOLOR_OT_select_similar_texture_color.bl_idname)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.texcolor_texture_pick = PointerProperty(type=TextureColorPick)
    bpy.types.VIEW3D_MT_edit_mesh_select_similar.append(draw_select_similar)


def unregister():
    bpy.types.VIEW3D_MT_edit_mesh_select_similar.remove(draw_select_similar)
    del bpy.types.Scene.texcolor_texture_pick
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
