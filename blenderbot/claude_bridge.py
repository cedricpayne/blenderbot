"""Bridge between Claude AI and Blender - processes text, image, and video inputs."""

import anthropic
import base64
import mimetypes
from pathlib import Path

SYSTEM_PROMPT = """\
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

Available Blender APIs you should use:
- bpy.ops.mesh.primitive_* for basic shapes
- bpy.ops.curve.* for curves and paths
- bpy.data.materials.new() for materials
- bpy.ops.object.modifier_add() for modifiers (subdivision, array, mirror, etc.)
- bpy.context.scene.frame_set() and obj.keyframe_insert() for animation
- bpy.ops.sculpt.* if sculpting is needed (enter sculpt mode first)

For complex organic shapes, prefer using metaballs, curves with bevel, or mesh \
primitives with subdivision surface and proportional editing via script.
"""


class ClaudeBridge:
    """Processes user inputs through Claude to generate Blender Python scripts."""

    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.conversation_history: list[dict] = []

    def text_to_script(self, prompt: str, keep_history: bool = True) -> str:
        """Generate a Blender script from a text description."""
        messages = self._build_messages(
            {"type": "text", "text": prompt},
            keep_history,
        )
        return self._call_claude(messages, keep_history, prompt)

    def image_to_script(self, image_path: str, prompt: str = "", keep_history: bool = True) -> str:
        """Generate a Blender script from an image (recreate what's in the image)."""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        mime_type = mimetypes.guess_type(str(path))[0] or "image/png"
        with open(path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        content = []
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime_type,
                "data": image_data,
            },
        })

        text = prompt or "Recreate this image as a 3D scene in Blender. Match the shapes, colors, and composition as closely as possible."
        content.append({"type": "text", "text": text})

        messages = self._build_messages(content, keep_history)
        return self._call_claude(messages, keep_history, f"[image: {path.name}] {text}")

    def video_to_script(self, video_path: str, prompt: str = "", keep_history: bool = True) -> str:
        """Generate a Blender animation script from a video file.

        Extracts key frames from the video, sends them to Claude, and generates
        an animation script.
        """
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
            content.append({
                "type": "text",
                "text": f"Frame {i + 1} of {len(frames)}",
            })

        text = prompt or (
            "Recreate this video as a 3D animation in Blender. "
            "Analyze the motion between frames and create keyframed animation "
            "that reproduces the movement. Match the objects, colors, and motion."
        )
        content.append({"type": "text", "text": text})

        messages = self._build_messages(content, keep_history)
        return self._call_claude(messages, keep_history, f"[video: {path.name}] {text}")

    def _build_messages(self, new_content, keep_history: bool) -> list[dict]:
        """Build the messages list, optionally including conversation history."""
        if keep_history:
            messages = list(self.conversation_history)
        else:
            messages = []

        # Normalize content to a list
        if isinstance(new_content, dict):
            new_content = [new_content]

        messages.append({"role": "user", "content": new_content})
        return messages

    def _call_claude(self, messages: list[dict], keep_history: bool, user_summary: str) -> str:
        """Call the Claude API and return the generated script."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=16384,
            system=SYSTEM_PROMPT,
            messages=messages,
        )

        script = response.content[0].text

        # Strip markdown code fences if Claude included them despite instructions
        if script.startswith("```"):
            lines = script.split("\n")
            # Remove first and last fence lines
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
        """Clear conversation history."""
        self.conversation_history.clear()

    def _extract_video_frames(self, video_path: str, num_frames: int = 8) -> list[str]:
        """Extract evenly-spaced frames from a video using ffmpeg.

        Returns a list of base64-encoded JPEG images.
        """
        import subprocess
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            # Get video duration
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
                        "-frames:v", "1",
                        "-q:v", "2",
                        output_file,
                    ],
                    capture_output=True,
                )
                if os.path.exists(output_file):
                    with open(output_file, "rb") as f:
                        frames.append(base64.standard_b64encode(f.read()).decode("utf-8"))

            return frames
