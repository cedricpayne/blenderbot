"""Main BlenderBot orchestrator - ties Claude and Blender together.

Supports two modes:
- "tools" mode: Claude calls structured tools (create_object, set_material, etc.)
  which are executed via the addon's tool system. Safer and more predictable.
- "script" mode: Claude generates raw Python code. More flexible for complex scenes.
"""

import json
from .blender_client import BlenderClient, BlenderResponse
from .claude_bridge import ClaudeBridge


class BlenderBot:
    """High-level interface: takes user input, processes via Claude, executes in Blender."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        blender_host: str = "127.0.0.1",
        blender_port: int = 9876,
        mode: str = "tools",
    ):
        self.blender = BlenderClient(host=blender_host, port=blender_port)
        self.claude = ClaudeBridge(api_key=api_key, model=model, mode=mode)
        self.mode = mode
        self._tools_loaded = False

    def _ensure_tools_loaded(self):
        """Fetch tool definitions from Blender addon and pass to Claude."""
        if self._tools_loaded or self.mode != "tools":
            return

        try:
            tools = self.blender.get_tools()
            if tools:
                self.claude.set_tools(tools)
                self._tools_loaded = True
        except Exception:
            # Fall back to script mode if tools can't be loaded
            pass

    def is_blender_connected(self) -> bool:
        return self.blender.ping()

    def text_to_render(
        self,
        prompt: str,
        render: bool = False,
        output_path: str = "/tmp/blenderbot_render.png",
        **render_kwargs,
    ) -> dict:
        """Generate a 3D scene from text and optionally render it."""
        self._ensure_tools_loaded()

        result = {"prompt": prompt}
        commands = self.claude.text_to_commands(prompt)

        if self.mode == "tools" and isinstance(commands, list):
            result["tool_calls"] = self._execute_tool_calls(commands)
        else:
            exec_result = self.blender.execute(commands)
            result["execution"] = _response_to_dict(exec_result)

        if render:
            render_result = self.blender.render(output_path=output_path, **render_kwargs)
            result["render"] = _response_to_dict(render_result)

        return result

    def image_to_render(
        self,
        image_path: str,
        prompt: str = "",
        render: bool = False,
        output_path: str = "/tmp/blenderbot_render.png",
        **render_kwargs,
    ) -> dict:
        """Recreate an image as a 3D scene and optionally render it."""
        self._ensure_tools_loaded()

        result = {"image": image_path, "prompt": prompt}
        commands = self.claude.image_to_commands(image_path, prompt)

        if self.mode == "tools" and isinstance(commands, list):
            result["tool_calls"] = self._execute_tool_calls(commands)
        else:
            exec_result = self.blender.execute(commands)
            result["execution"] = _response_to_dict(exec_result)

        if render:
            render_result = self.blender.render(output_path=output_path, **render_kwargs)
            result["render"] = _response_to_dict(render_result)

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
        """Recreate a video as a 3D animation and optionally render it."""
        self._ensure_tools_loaded()

        result = {"video": video_path, "prompt": prompt}
        commands = self.claude.video_to_commands(video_path, prompt)

        if self.mode == "tools" and isinstance(commands, list):
            result["tool_calls"] = self._execute_tool_calls(commands)
        else:
            exec_result = self.blender.execute(commands)
            result["execution"] = _response_to_dict(exec_result)

        if render:
            render_result = self.blender.render(
                output_path=output_path, animation=animation, **render_kwargs,
            )
            result["render"] = _response_to_dict(render_result)

        return result

    def _execute_tool_calls(self, tool_calls: list[dict]) -> list[dict]:
        """Execute a list of tool calls against the Blender addon."""
        results = []
        for tc in tool_calls:
            tool_name = tc["tool"]
            tool_input = tc.get("input", {})
            response = self.blender.call_tool(tool_name, tool_input)
            results.append({
                "tool": tool_name,
                "input": tool_input,
                "status": response.status,
                "result": response.result,
                "error": response.error,
            })
            if not response.ok:
                print(f"Tool error [{tool_name}]: {response.error}")
        return results

    def execute_raw(self, script: str) -> BlenderResponse:
        return self.blender.execute(script)

    def call_tool(self, tool_name: str, **kwargs) -> BlenderResponse:
        """Call a specific tool directly."""
        return self.blender.call_tool(tool_name, kwargs)

    def clear_scene(self) -> BlenderResponse:
        if self.mode == "tools":
            return self.blender.call_tool("clear_scene", {})
        return self.blender.execute("""
import bpy
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
result = "Scene cleared"
""")

    def clear_history(self):
        self.claude.clear_history()


def _response_to_dict(resp: BlenderResponse) -> dict:
    return {
        "status": resp.status,
        "result": resp.result,
        "error": resp.error,
    }
