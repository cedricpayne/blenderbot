"""Bridge between Claude AI and Blender - processes text, image, and video inputs.

Supports two modes:
1. Tool-calling mode (default): Claude calls structured tools (create_object, set_material, etc.)
   that execute safely on Blender's main thread. Inspired by GenesisCore's MCP approach.
2. Script mode: Claude generates raw bpy Python code for maximum flexibility.
"""

import anthropic
import base64
import json
import mimetypes
from pathlib import Path

SYSTEM_PROMPT_TOOLS = """\
You are BlenderBot, an AI assistant that creates 3D scenes, sculptures, and animations \
in Blender by calling tools. You have access to tools for creating objects, setting materials, \
adding modifiers, managing the scene, searching Polyhaven for assets, and executing custom code.

Strategy:
1. Analyze the user's request and break it into steps.
2. Use the structured tools (create_object, set_material, add_modifier, etc.) when possible.
3. For complex operations not covered by tools, use execute_blender_code as a fallback.
4. When the user references real-world objects, search Polyhaven first for ready-made models.
5. Set up appropriate lighting and camera for the scene.
6. For animations, use set_keyframe to create keyframed motion.
7. Think step by step but keep explanations brief.
"""

SYSTEM_PROMPT_SCRIPT = """\
You are BlenderBot, an expert Blender Python (bpy) scripter. You generate Python code \
that runs inside Blender 4.x to create 3D scenes, animations, and sculptures.

Rules:
1. Output ONLY valid Python code - no markdown fences, no explanations.
2. Always import bpy at the top.
3. Clear the default scene objects at the start unless the user says to keep them.
4. Use descriptive variable names.
5. Set up proper materials with colors/textures as described.
6. Position the camera and lighting appropriately for the scene.
7. If creating an animation, set keyframes and configure the timeline.
8. At the end, set a variable called `result` with a short description of what was created.
"""


class ClaudeBridge:
    """Processes user inputs through Claude to generate Blender commands.

    In tool-calling mode, returns a list of tool calls for the BlenderBot
    orchestrator to execute. In script mode, returns raw Python code.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        mode: str = "tools",
    ):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.mode = mode  # "tools" or "script"
        self.conversation_history: list[dict] = []
        self._tools: list[dict] | None = None

    def set_tools(self, tool_definitions: list[dict]):
        """Set the available tool definitions for tool-calling mode."""
        self._tools = tool_definitions

    def text_to_commands(self, prompt: str, keep_history: bool = True):
        """Generate Blender commands from a text description."""
        messages = self._build_messages(
            {"type": "text", "text": prompt},
            keep_history,
        )
        return self._call_claude(messages, keep_history, prompt)

    def image_to_commands(self, image_path: str, prompt: str = "", keep_history: bool = True):
        """Generate Blender commands from an image reference."""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        mime_type = mimetypes.guess_type(str(path))[0] or "image/png"
        with open(path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": image_data,
                },
            },
            {
                "type": "text",
                "text": prompt or "Recreate this image as a 3D scene in Blender. Match the shapes, colors, and composition as closely as possible.",
            },
        ]

        messages = self._build_messages(content, keep_history)
        return self._call_claude(messages, keep_history, f"[image: {path.name}] {prompt}")

    def video_to_commands(self, video_path: str, prompt: str = "", keep_history: bool = True):
        """Generate Blender animation commands from a video reference."""
        path = Path(video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        frames = self._extract_video_frames(str(path))
        if not frames:
            raise RuntimeError("Failed to extract frames from video. Ensure ffmpeg is installed.")

        content = []
        for i, frame_data in enumerate(frames):
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": frame_data,
                },
            })
            content.append({"type": "text", "text": f"Frame {i + 1} of {len(frames)}"})

        text = prompt or (
            "Recreate this video as a 3D animation in Blender. "
            "Analyze the motion between frames and create keyframed animation "
            "that reproduces the movement."
        )
        content.append({"type": "text", "text": text})

        messages = self._build_messages(content, keep_history)
        return self._call_claude(messages, keep_history, f"[video: {path.name}] {text}")

    def _build_messages(self, new_content, keep_history: bool) -> list[dict]:
        if keep_history:
            messages = list(self.conversation_history)
        else:
            messages = []

        if isinstance(new_content, dict):
            new_content = [new_content]

        messages.append({"role": "user", "content": new_content})
        return messages

    def _call_claude(self, messages: list[dict], keep_history: bool, user_summary: str):
        """Call Claude API. Returns tool calls in tools mode, or a script string in script mode."""
        if self.mode == "tools" and self._tools:
            return self._call_claude_tools(messages, keep_history, user_summary)
        else:
            return self._call_claude_script(messages, keep_history, user_summary)

    def _call_claude_tools(self, messages: list[dict], keep_history: bool, user_summary: str) -> list[dict]:
        """Call Claude with tool_use, executing a tool-calling loop until done."""
        all_tool_calls = []
        current_messages = list(messages)

        while True:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=16384,
                system=SYSTEM_PROMPT_TOOLS,
                tools=self._tools,
                messages=current_messages,
            )

            # Collect tool calls and text from this response
            assistant_content = response.content
            tool_uses = [block for block in assistant_content if block.type == "tool_use"]
            text_blocks = [block for block in assistant_content if block.type == "text"]

            if not tool_uses:
                # No more tool calls - Claude is done
                break

            # Record each tool call
            for tool_use in tool_uses:
                all_tool_calls.append({
                    "tool": tool_use.name,
                    "input": tool_use.input,
                    "id": tool_use.id,
                })

            # Add assistant message and placeholder tool results to continue the loop
            current_messages.append({"role": "assistant", "content": assistant_content})

            # Add tool result placeholders (actual execution happens in the orchestrator)
            tool_results = []
            for tool_use in tool_uses:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps({"status": "queued", "message": "Tool call recorded for execution"}),
                })
            current_messages.append({"role": "user", "content": tool_results})

            # If Claude stopped for tool use, continue the loop
            if response.stop_reason != "tool_use":
                break

        # Update history
        if keep_history:
            self.conversation_history.append(
                {"role": "user", "content": [{"type": "text", "text": user_summary}]}
            )
            summary = f"Executed {len(all_tool_calls)} tool calls: {', '.join(tc['tool'] for tc in all_tool_calls)}"
            if text_blocks:
                summary = text_blocks[-1].text
            self.conversation_history.append(
                {"role": "assistant", "content": [{"type": "text", "text": summary}]}
            )

        return all_tool_calls

    def _call_claude_script(self, messages: list[dict], keep_history: bool, user_summary: str) -> str:
        """Call Claude to generate a raw Python script."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=16384,
            system=SYSTEM_PROMPT_SCRIPT,
            messages=messages,
        )

        script = response.content[0].text

        # Strip markdown code fences
        if script.startswith("```"):
            lines = script.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            script = "\n".join(lines)

        if keep_history:
            self.conversation_history.append(
                {"role": "user", "content": [{"type": "text", "text": user_summary}]}
            )
            self.conversation_history.append(
                {"role": "assistant", "content": [{"type": "text", "text": script}]}
            )

        return script

    def clear_history(self):
        self.conversation_history.clear()

    def _extract_video_frames(self, video_path: str, num_frames: int = 8) -> list[str]:
        """Extract evenly-spaced frames from a video using ffmpeg."""
        import subprocess
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            probe = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    video_path,
                ],
                capture_output=True, text=True,
            )
            if probe.returncode != 0:
                return []

            duration = float(probe.stdout.strip())
            interval = duration / (num_frames + 1)

            frames = []
            for i in range(1, num_frames + 1):
                timestamp = interval * i
                output_file = os.path.join(tmpdir, f"frame_{i:03d}.jpg")
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-ss", str(timestamp),
                        "-i", video_path,
                        "-frames:v", "1", "-q:v", "2",
                        output_file,
                    ],
                    capture_output=True,
                )
                if os.path.exists(output_file):
                    with open(output_file, "rb") as f:
                        frames.append(base64.standard_b64encode(f.read()).decode("utf-8"))

            return frames
