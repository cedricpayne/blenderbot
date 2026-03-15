"""Main BlenderBot orchestrator - ties Claude and Blender together."""

from pathlib import Path

from .blender_client import BlenderClient, BlenderResponse
from .claude_bridge import ClaudeBridge


class BlenderBot:
    """High-level interface: takes user input, generates scripts via Claude, executes in Blender."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        blender_host: str = "127.0.0.1",
        blender_port: int = 9876,
    ):
        self.claude = ClaudeBridge(api_key=api_key, model=model)
        self.blender = BlenderClient(host=blender_host, port=blender_port)

    def is_blender_connected(self) -> bool:
        """Check if Blender is reachable."""
        return self.blender.ping()

    def text_to_render(
        self,
        prompt: str,
        render: bool = False,
        output_path: str = "/tmp/blenderbot_render.png",
        **render_kwargs,
    ) -> dict:
        """Generate a 3D scene from text and optionally render it.

        Args:
            prompt: Natural language description of the 3D scene.
            render: Whether to render the scene after creating it.
            output_path: Where to save the rendered image/animation.
            **render_kwargs: Additional render settings (resolution, samples, etc.)

        Returns:
            dict with 'script', 'execution' result, and optionally 'render' result.
        """
        script = self.claude.text_to_script(prompt)
        result = {"script": script}

        exec_result = self.blender.execute(script)
        result["execution"] = {
            "status": exec_result.status,
            "result": exec_result.result,
            "error": exec_result.error,
        }

        if render and exec_result.ok:
            render_result = self.blender.render(output_path=output_path, **render_kwargs)
            result["render"] = {
                "status": render_result.status,
                "output": output_path if render_result.ok else None,
                "error": render_result.error,
            }

        return result

    def image_to_render(
        self,
        image_path: str,
        prompt: str = "",
        render: bool = False,
        output_path: str = "/tmp/blenderbot_render.png",
        **render_kwargs,
    ) -> dict:
        """Recreate an image as a 3D scene and optionally render it.

        Args:
            image_path: Path to the reference image.
            prompt: Additional instructions for Claude.
            render: Whether to render the scene after creating it.
            output_path: Where to save the rendered image.
            **render_kwargs: Additional render settings.

        Returns:
            dict with 'script', 'execution' result, and optionally 'render' result.
        """
        script = self.claude.image_to_script(image_path, prompt)
        result = {"script": script}

        exec_result = self.blender.execute(script)
        result["execution"] = {
            "status": exec_result.status,
            "result": exec_result.result,
            "error": exec_result.error,
        }

        if render and exec_result.ok:
            render_result = self.blender.render(output_path=output_path, **render_kwargs)
            result["render"] = {
                "status": render_result.status,
                "output": output_path if render_result.ok else None,
                "error": render_result.error,
            }

        return result

    def video_to_render(
        self,
        video_path: str,
        prompt: str = "",
        render: bool = False,
        output_path: str = "/tmp/blenderbot_anim_",
        animation: bool = True,
        **render_kwargs,
    ) -> dict:
        """Recreate a video as a 3D animation and optionally render it.

        Args:
            video_path: Path to the reference video.
            prompt: Additional instructions for Claude.
            render: Whether to render the animation after creating it.
            output_path: Base path for rendered animation frames.
            animation: Render as animation (True) or single frame (False).
            **render_kwargs: Additional render settings.

        Returns:
            dict with 'script', 'execution' result, and optionally 'render' result.
        """
        script = self.claude.video_to_script(video_path, prompt)
        result = {"script": script}

        exec_result = self.blender.execute(script)
        result["execution"] = {
            "status": exec_result.status,
            "result": exec_result.result,
            "error": exec_result.error,
        }

        if render and exec_result.ok:
            render_result = self.blender.render(
                output_path=output_path,
                animation=animation,
                **render_kwargs,
            )
            result["render"] = {
                "status": render_result.status,
                "output": output_path if render_result.ok else None,
                "error": render_result.error,
            }

        return result

    def execute_raw(self, script: str) -> BlenderResponse:
        """Execute a raw Python script in Blender (bypass Claude)."""
        return self.blender.execute(script)

    def clear_scene(self) -> BlenderResponse:
        """Clear all objects from the Blender scene."""
        return self.blender.execute("""
import bpy
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
result = "Scene cleared"
""")

    def clear_history(self):
        """Clear conversation history with Claude."""
        self.claude.clear_history()
