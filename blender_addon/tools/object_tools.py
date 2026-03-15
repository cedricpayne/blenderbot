"""Object creation, modification, and deletion tools for Blender."""

import bpy
from mathutils import Vector
from .base import ToolsPackageBase


class ObjectTools(ToolsPackageBase):
    """Tools for creating and manipulating objects in the Blender scene."""

    def create_object(
        entity_type: str = "CUBE",
        name: str = "New Object",
        location: list[float] = (0, 0, 0),
        rotation: list[float] = (0, 0, 0),
        scale: list[float] = (1, 1, 1),
        major_segments: int = 48,
        minor_segments: int = 12,
        major_radius: float = 1.0,
        minor_radius: float = 0.25,
    ) -> dict:
        """
        Create a new object in the Blender scene.

        Args:
        - entity_type: Type to create (CUBE, SPHERE, CYLINDER, PLANE, CONE, TORUS, EMPTY, CAMERA, LIGHT, MONKEY, CIRCLE, GRID, METABALL)
        - name: Name for the object
        - location: [x, y, z] location coordinates
        - rotation: [x, y, z] rotation in radians
        - scale: [x, y, z] scale factors
        - major_segments: Segments for torus main ring
        - minor_segments: Segments for torus cross-section
        - major_radius: Torus main radius
        - minor_radius: Torus cross-section radius
        """
        old_objects = set(bpy.data.objects)
        bpy.ops.object.select_all(action="DESELECT")

        creators = {
            "CUBE": lambda: bpy.ops.mesh.primitive_cube_add(location=location, rotation=rotation, scale=scale),
            "SPHERE": lambda: bpy.ops.mesh.primitive_uv_sphere_add(location=location, rotation=rotation, scale=scale),
            "CYLINDER": lambda: bpy.ops.mesh.primitive_cylinder_add(location=location, rotation=rotation, scale=scale),
            "PLANE": lambda: bpy.ops.mesh.primitive_plane_add(location=location, rotation=rotation, scale=scale),
            "CONE": lambda: bpy.ops.mesh.primitive_cone_add(location=location, rotation=rotation, scale=scale),
            "TORUS": lambda: bpy.ops.mesh.primitive_torus_add(
                location=location, rotation=rotation,
                major_segments=major_segments, minor_segments=minor_segments,
                major_radius=major_radius, minor_radius=minor_radius,
            ),
            "MONKEY": lambda: bpy.ops.mesh.primitive_monkey_add(location=location, rotation=rotation, scale=scale),
            "CIRCLE": lambda: bpy.ops.mesh.primitive_circle_add(location=location, rotation=rotation, scale=scale),
            "GRID": lambda: bpy.ops.mesh.primitive_grid_add(location=location, rotation=rotation, scale=scale),
            "EMPTY": lambda: bpy.ops.object.empty_add(location=location, rotation=rotation, scale=scale),
            "CAMERA": lambda: bpy.ops.object.camera_add(location=location, rotation=rotation),
            "LIGHT": lambda: bpy.ops.object.light_add(type="POINT", location=location, rotation=rotation, scale=scale),
            "METABALL": lambda: bpy.ops.object.metaball_add(location=location, rotation=rotation, scale=scale),
        }

        creator = creators.get(entity_type.upper())
        if not creator:
            raise ValueError(f"Unsupported entity type: {entity_type}. Supported: {', '.join(creators.keys())}")

        creator()
        new_objects = set(bpy.data.objects) - old_objects
        if not new_objects:
            raise RuntimeError(f"Failed to create {entity_type}")

        obj = list(new_objects)[0]
        if name:
            obj.name = name

        return {
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "rotation": list(obj.rotation_euler),
            "scale": list(obj.scale),
        }

    def modify_object(
        name: str,
        location: list[float] = None,
        rotation: list[float] = None,
        scale: list[float] = None,
        visible: bool = None,
    ) -> dict:
        """
        Modify an existing object's transform or visibility.

        Args:
        - name: Name of the object to modify
        - location: New [x, y, z] location
        - rotation: New [x, y, z] rotation in radians
        - scale: New [x, y, z] scale
        - visible: Set visibility
        """
        obj = bpy.data.objects.get(name)
        if not obj:
            raise ValueError(f"Object not found: {name}")

        if location is not None:
            obj.location = location
        if rotation is not None:
            obj.rotation_euler = rotation
        if scale is not None:
            obj.scale = scale
        if visible is not None:
            obj.hide_viewport = not visible
            obj.hide_render = not visible

        return {
            "name": obj.name,
            "location": list(obj.location),
            "rotation": list(obj.rotation_euler),
            "scale": list(obj.scale),
            "visible": obj.visible_get(),
        }

    def delete_object(object_name: str) -> dict:
        """
        Delete an object from the scene.

        Args:
        - object_name: Name of the object to delete
        """
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")
        with bpy.context.temp_override(selected_objects=[obj]):
            bpy.ops.object.delete()
        return {"deleted": object_name}

    def duplicate_object(object_name: str, new_name: str = None, offset: list[float] = None) -> dict:
        """
        Duplicate an existing object.

        Args:
        - object_name: Name of the object to duplicate
        - new_name: Name for the duplicate
        - offset: [x, y, z] offset from original position
        """
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        new_obj = obj.copy()
        if obj.data:
            new_obj.data = obj.data.copy()
        bpy.context.collection.objects.link(new_obj)

        if new_name:
            new_obj.name = new_name
        if offset:
            new_obj.location = (
                obj.location.x + offset[0],
                obj.location.y + offset[1],
                obj.location.z + offset[2],
            )

        return {
            "name": new_obj.name,
            "location": list(new_obj.location),
        }

    def get_object_info(object_name: str) -> dict:
        """
        Get detailed information about a specific object.

        Args:
        - object_name: Name of the object
        """
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        info = {
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "rotation": list(obj.rotation_euler),
            "scale": list(obj.scale),
            "visible": obj.visible_get(),
            "materials": [slot.material.name for slot in obj.material_slots if slot.material],
        }

        if obj.type == "MESH" and obj.data:
            mesh = obj.data
            info["mesh"] = {
                "vertices": len(mesh.vertices),
                "edges": len(mesh.edges),
                "polygons": len(mesh.polygons),
            }

        if obj.type == "CAMERA" and obj.data:
            cam = obj.data
            info["camera"] = {
                "type": cam.type,
                "focal_length": cam.lens,
            }

        if obj.type == "LIGHT" and obj.data:
            light = obj.data
            info["light"] = {
                "type": light.type,
                "energy": light.energy,
                "color": list(light.color),
            }

        return info

    def set_keyframe(
        object_name: str,
        frame: int,
        data_path: str = "location",
        value: list[float] = None,
    ) -> dict:
        """
        Set a keyframe on an object property for animation.

        Args:
        - object_name: Name of the object
        - frame: Frame number
        - data_path: Property to keyframe (location, rotation_euler, scale)
        - value: Value to set before keyframing
        """
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        bpy.context.scene.frame_set(frame)

        if value is not None:
            setattr(obj, data_path, value)

        obj.keyframe_insert(data_path=data_path, frame=frame)

        return {
            "object": object_name,
            "frame": frame,
            "data_path": data_path,
            "value": list(getattr(obj, data_path)),
        }

    def set_light_properties(
        object_name: str,
        light_type: str = None,
        energy: float = None,
        color: list[float] = None,
        size: float = None,
    ) -> dict:
        """
        Set properties on a light object.

        Args:
        - object_name: Name of the light object
        - light_type: Light type (POINT, SUN, SPOT, AREA)
        - energy: Light intensity/power in watts
        - color: [R, G, B] color (0.0-1.0)
        - size: Size of the light source
        """
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "LIGHT":
            raise ValueError(f"Light not found: {object_name}")

        light = obj.data
        if light_type:
            light.type = light_type
        if energy is not None:
            light.energy = energy
        if color:
            light.color = color[:3]
        if size is not None:
            if hasattr(light, "shadow_soft_size"):
                light.shadow_soft_size = size

        return {
            "name": object_name,
            "type": light.type,
            "energy": light.energy,
            "color": list(light.color),
        }

    def set_camera_properties(
        object_name: str,
        focal_length: float = None,
        sensor_width: float = None,
        clip_start: float = None,
        clip_end: float = None,
        dof_focus_object: str = None,
    ) -> dict:
        """
        Set properties on a camera object.

        Args:
        - object_name: Name of the camera object
        - focal_length: Lens focal length in mm
        - sensor_width: Sensor width in mm
        - clip_start: Near clipping distance
        - clip_end: Far clipping distance
        - dof_focus_object: Name of object to focus on for depth of field
        """
        obj = bpy.data.objects.get(object_name)
        if not obj or obj.type != "CAMERA":
            raise ValueError(f"Camera not found: {object_name}")

        cam = obj.data
        if focal_length is not None:
            cam.lens = focal_length
        if sensor_width is not None:
            cam.sensor_width = sensor_width
        if clip_start is not None:
            cam.clip_start = clip_start
        if clip_end is not None:
            cam.clip_end = clip_end
        if dof_focus_object:
            focus_obj = bpy.data.objects.get(dof_focus_object)
            if focus_obj:
                cam.dof.use_dof = True
                cam.dof.focus_object = focus_obj

        return {
            "name": object_name,
            "focal_length": cam.lens,
            "sensor_width": cam.sensor_width,
        }
