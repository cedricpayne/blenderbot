"""Scene information and management tools for Blender."""

import bpy
from .base import ToolsPackageBase


class SceneTools(ToolsPackageBase):
    """Tools for querying and managing the Blender scene."""

    def get_scene_info() -> dict:
        """Get information about the current Blender scene including all objects."""
        scene = bpy.context.scene
        objects = []
        for obj in scene.objects:
            objects.append({
                "name": obj.name,
                "type": obj.type,
                "location": list(obj.location),
            })

        return {
            "scene_name": scene.name,
            "object_count": len(scene.objects),
            "objects": objects,
            "materials_count": len(bpy.data.materials),
            "frame_current": scene.frame_current,
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
            "render_engine": scene.render.engine,
            "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        }

    def clear_scene(keep_camera: bool = False, keep_lights: bool = False) -> dict:
        """
        Remove all objects from the scene.

        Args:
        - keep_camera: Keep camera objects
        - keep_lights: Keep light objects
        """
        deleted = []
        for obj in list(bpy.data.objects):
            if keep_camera and obj.type == "CAMERA":
                continue
            if keep_lights and obj.type == "LIGHT":
                continue
            deleted.append(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)

        return {"deleted": deleted, "remaining": len(bpy.data.objects)}

    def set_render_settings(
        engine: str = None,
        resolution_x: int = None,
        resolution_y: int = None,
        samples: int = None,
        output_path: str = None,
        film_transparent: bool = None,
    ) -> dict:
        """
        Configure render settings.

        Args:
        - engine: Render engine (CYCLES, BLENDER_EEVEE_NEXT)
        - resolution_x: Horizontal resolution in pixels
        - resolution_y: Vertical resolution in pixels
        - samples: Number of render samples
        - output_path: File path for rendered output
        - film_transparent: Make background transparent
        """
        scene = bpy.context.scene
        if engine:
            scene.render.engine = engine
        if resolution_x:
            scene.render.resolution_x = resolution_x
        if resolution_y:
            scene.render.resolution_y = resolution_y
        if samples and scene.render.engine == "CYCLES":
            scene.cycles.samples = samples
        if output_path:
            scene.render.filepath = output_path
        if film_transparent is not None:
            scene.render.film_transparent = film_transparent

        return {
            "engine": scene.render.engine,
            "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        }

    def set_timeline(
        frame_start: int = None,
        frame_end: int = None,
        frame_current: int = None,
        fps: int = None,
    ) -> dict:
        """
        Configure animation timeline settings.

        Args:
        - frame_start: First frame of the animation
        - frame_end: Last frame of the animation
        - frame_current: Current frame
        - fps: Frames per second
        """
        scene = bpy.context.scene
        if frame_start is not None:
            scene.frame_start = frame_start
        if frame_end is not None:
            scene.frame_end = frame_end
        if frame_current is not None:
            scene.frame_set(frame_current)
        if fps is not None:
            scene.render.fps = fps

        return {
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
            "frame_current": scene.frame_current,
            "fps": scene.render.fps,
        }

    def render_scene(
        output_path: str = "/tmp/blenderbot_render.png",
        animation: bool = False,
    ) -> dict:
        """
        Render the current scene to an image or animation.

        Args:
        - output_path: File path for the rendered output
        - animation: If True, render full animation; if False, render single frame
        """
        scene = bpy.context.scene
        scene.render.filepath = output_path

        if animation:
            bpy.ops.render.render(animation=True)
        else:
            bpy.ops.render.render(write_still=True)

        return {
            "output_path": output_path,
            "animation": animation,
            "engine": scene.render.engine,
        }

    def set_world_color(color: list[float] = None, strength: float = 1.0) -> dict:
        """
        Set the world background color.

        Args:
        - color: Background color [R, G, B, A] (0.0-1.0)
        - strength: Background strength/intensity
        """
        world = bpy.context.scene.world
        if not world:
            world = bpy.data.worlds.new("World")
            bpy.context.scene.world = world

        world.use_nodes = True
        bg = None
        for node in world.node_tree.nodes:
            if node.type == "BACKGROUND":
                bg = node
                break
        if not bg:
            bg = world.node_tree.nodes.new("ShaderNodeBackground")

        if color:
            rgba = color if len(color) == 4 else [*color, 1.0]
            bg.inputs["Color"].default_value = rgba
        bg.inputs["Strength"].default_value = strength

        return {"color": color, "strength": strength}

    def execute_blender_code(code: str) -> dict:
        """
        Execute arbitrary Blender Python code. Use this as a fallback when no specific tool exists for an operation.

        Args:
        - code: The Python code to execute (must be valid bpy code)
        """
        namespace = {"bpy": bpy}
        exec(code, namespace)
        result = namespace.get("result", "Code executed successfully")
        return {"executed": True, "result": str(result)}
