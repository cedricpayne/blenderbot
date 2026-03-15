"""Modifier tools for Blender objects."""

import bpy
from .base import ToolsPackageBase


class ModifierTools(ToolsPackageBase):
    """Tools for adding and configuring modifiers on Blender objects."""

    def add_modifier(
        object_name: str,
        modifier_type: str,
        modifier_name: str = None,
        properties: dict = None,
    ) -> dict:
        """
        Add a modifier to an object.

        Args:
        - object_name: Name of the object
        - modifier_type: Modifier type (SUBSURF, ARRAY, MIRROR, SOLIDIFY, BEVEL, BOOLEAN, CURVE, DISPLACE, WAVE, SMOOTH, WIREFRAME, DECIMATE, REMESH, SKIN, SCREW)
        - modifier_name: Display name for the modifier
        - properties: Dict of modifier properties to set (e.g. {"levels": 3, "render_levels": 4})
        """
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        mod = obj.modifiers.new(
            name=modifier_name or modifier_type.title(),
            type=modifier_type,
        )

        if properties:
            for key, value in properties.items():
                if hasattr(mod, key):
                    setattr(mod, key, value)

        return {
            "object": object_name,
            "modifier": mod.name,
            "type": mod.type,
        }

    def apply_modifier(object_name: str, modifier_name: str) -> dict:
        """
        Apply a modifier to an object (makes it permanent).

        Args:
        - object_name: Name of the object
        - modifier_name: Name of the modifier to apply
        """
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=modifier_name)

        return {"object": object_name, "applied": modifier_name}

    def add_subdivision_surface(
        object_name: str,
        levels: int = 2,
        render_levels: int = 3,
    ) -> dict:
        """
        Add a Subdivision Surface modifier for smooth geometry.

        Args:
        - object_name: Name of the object
        - levels: Viewport subdivision levels
        - render_levels: Render subdivision levels
        """
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        mod = obj.modifiers.new(name="Subdivision", type="SUBSURF")
        mod.levels = levels
        mod.render_levels = render_levels

        return {"object": object_name, "modifier": mod.name, "levels": levels}

    def add_array_modifier(
        object_name: str,
        count: int = 2,
        relative_offset: list[float] = None,
        constant_offset: list[float] = None,
    ) -> dict:
        """
        Add an Array modifier to duplicate an object in a pattern.

        Args:
        - object_name: Name of the object
        - count: Number of copies
        - relative_offset: Relative offset [x, y, z] (multiplied by object dimensions)
        - constant_offset: Constant offset [x, y, z] in Blender units
        """
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        mod = obj.modifiers.new(name="Array", type="ARRAY")
        mod.count = count

        if relative_offset:
            mod.use_relative_offset = True
            mod.relative_offset_displace = relative_offset
        if constant_offset:
            mod.use_constant_offset = True
            mod.constant_offset_displace = constant_offset

        return {"object": object_name, "modifier": mod.name, "count": count}

    def add_mirror_modifier(
        object_name: str,
        axis_x: bool = True,
        axis_y: bool = False,
        axis_z: bool = False,
        use_clip: bool = True,
    ) -> dict:
        """
        Add a Mirror modifier to mirror geometry along axes.

        Args:
        - object_name: Name of the object
        - axis_x: Mirror along X axis
        - axis_y: Mirror along Y axis
        - axis_z: Mirror along Z axis
        - use_clip: Prevent vertices from crossing the mirror plane
        """
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        mod = obj.modifiers.new(name="Mirror", type="MIRROR")
        mod.use_axis[0] = axis_x
        mod.use_axis[1] = axis_y
        mod.use_axis[2] = axis_z
        mod.use_clip = use_clip

        return {"object": object_name, "modifier": mod.name}
