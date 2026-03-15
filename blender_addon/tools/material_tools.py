"""Material creation and manipulation tools for Blender."""

import bpy
from uuid import uuid4
from .base import ToolsPackageBase


def _ensure_material(obj, material_name: str) -> bpy.types.Material:
    """Get or create a material by name and assign it to the object."""
    mat = bpy.data.materials.get(material_name)
    if not mat:
        mat = bpy.data.materials.new(name=material_name)
        mat.use_nodes = True
    if not obj.data.materials:
        obj.data.materials.append(mat)
    else:
        obj.data.materials[0] = mat
    return mat


def _get_principled_bsdf(mat):
    """Get or create a Principled BSDF node in the material."""
    if not mat.use_nodes:
        mat.use_nodes = True

    principled = mat.node_tree.nodes.get("Principled BSDF")
    if not principled:
        for node in mat.node_tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                principled = node
                break
    if not principled:
        principled = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        output = None
        for node in mat.node_tree.nodes:
            if node.type == "OUTPUT_MATERIAL":
                output = node
                break
        if not output:
            output = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
        mat.node_tree.links.new(principled.outputs[0], output.inputs[0])

    return principled


class MaterialTools(ToolsPackageBase):
    """Tools for creating and modifying materials on Blender objects."""

    def set_material(
        object_name: str,
        material_name: str = None,
        color: list[float] = None,
        metallic: float = None,
        roughness: float = None,
        emission_color: list[float] = None,
        emission_strength: float = None,
        alpha: float = None,
        subsurface: float = None,
        specular: float = None,
    ) -> dict:
        """
        Set or create a material on an object with PBR properties.

        Args:
        - object_name: Name of the object to apply the material to
        - material_name: Name of the material (auto-generated if omitted)
        - color: Base color [R, G, B] or [R, G, B, A] (0.0-1.0)
        - metallic: Metallic factor (0.0-1.0)
        - roughness: Roughness factor (0.0-1.0)
        - emission_color: Emission color [R, G, B, A] (0.0-1.0)
        - emission_strength: Emission intensity
        - alpha: Transparency (0.0 = transparent, 1.0 = opaque)
        - subsurface: Subsurface scattering weight (0.0-1.0)
        - specular: Specular reflection amount (0.0-1.0)
        """
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")
        if not hasattr(obj, "data") or not hasattr(obj.data, "materials"):
            raise ValueError(f"Object {object_name} cannot accept materials")

        material_name = material_name or f"{object_name}_mat_{uuid4().hex[:8]}"
        mat = _ensure_material(obj, material_name)
        principled = _get_principled_bsdf(mat)

        if color:
            rgba = color if len(color) == 4 else [*color, 1.0]
            principled.inputs["Base Color"].default_value = rgba
        if metallic is not None:
            principled.inputs["Metallic"].default_value = metallic
        if roughness is not None:
            principled.inputs["Roughness"].default_value = roughness
        if emission_color:
            rgba = emission_color if len(emission_color) == 4 else [*emission_color, 1.0]
            principled.inputs["Emission Color"].default_value = rgba
        if emission_strength is not None:
            principled.inputs["Emission Strength"].default_value = emission_strength
        if alpha is not None:
            principled.inputs["Alpha"].default_value = alpha
            if alpha < 1.0:
                mat.blend_method = "BLEND" if hasattr(mat, "blend_method") else None
        if subsurface is not None:
            principled.inputs["Subsurface Weight"].default_value = subsurface
        if specular is not None:
            principled.inputs["Specular IOR Level"].default_value = specular

        return {
            "object": object_name,
            "material": mat.name,
            "color": color,
        }

    def set_glass_material(
        object_name: str,
        color: list[float] = None,
        ior: float = 1.45,
        roughness: float = 0.0,
    ) -> dict:
        """
        Apply a glass/transparent material to an object.

        Args:
        - object_name: Name of the object
        - color: Tint color [R, G, B] (0.0-1.0)
        - ior: Index of refraction (1.0 = no refraction, 1.45 = glass, 1.33 = water)
        - roughness: Surface roughness (0.0 = smooth, 1.0 = frosted)
        """
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        mat_name = f"{object_name}_glass"
        mat = _ensure_material(obj, mat_name)
        principled = _get_principled_bsdf(mat)

        principled.inputs["Transmission Weight"].default_value = 1.0
        principled.inputs["IOR"].default_value = ior
        principled.inputs["Roughness"].default_value = roughness
        if color:
            rgba = color if len(color) == 4 else [*color, 1.0]
            principled.inputs["Base Color"].default_value = rgba

        return {"object": object_name, "material": mat_name, "ior": ior}
