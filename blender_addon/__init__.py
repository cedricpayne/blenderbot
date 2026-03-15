"""
BlenderBot Addon - AI-powered 3D content generation.

Receives commands from the BlenderBot client and executes them in Blender
using structured MCP-style tools (object creation, materials, modifiers, etc.)
or raw Python scripts.

Install: Edit > Preferences > Add-ons > Install, select this folder.
"""

bl_info = {
    "name": "BlenderBot",
    "author": "BlenderBot",
    "version": (2, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > BlenderBot",
    "description": "AI-powered 3D content generation with Claude and structured tools",
    "category": "AI",
}

import bpy
import json
import socket
import threading
import traceback
import queue
from pathlib import Path

from .timer import Timer

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9876

# Thread-safe queues for communication between socket threads and main thread
_command_queue = queue.Queue()
_result_queue = queue.Queue()


class BlenderBotServer:
    """Socket server that listens for commands from the BlenderBot client."""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self._server_socket = None
        self._thread = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass
        self._server_socket = None

    def _run(self):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.settimeout(1.0)
        try:
            self._server_socket.bind((self.host, self.port))
            self._server_socket.listen(5)
            print(f"[BlenderBot] Server listening on {self.host}:{self.port}")
        except OSError as e:
            print(f"[BlenderBot] Failed to bind: {e}")
            self._running = False
            return

        while self._running:
            try:
                client, addr = self._server_socket.accept()
                threading.Thread(
                    target=self._handle_client, args=(client,), daemon=True
                ).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_client(self, client_socket):
        try:
            client_socket.settimeout(300)
            data = _recv_all(client_socket)
            if not data:
                return

            request = json.loads(data.decode("utf-8"))
            command_type = request.get("type", "execute")
            timeout = request.get("timeout", 120)

            if command_type == "ping":
                response = {"status": "ok", "message": "pong"}
            elif command_type == "execute":
                _command_queue.put(("execute", request.get("script", "")))
                try:
                    response = _result_queue.get(timeout=timeout)
                except queue.Empty:
                    response = {"status": "error", "error": "Execution timed out"}
            elif command_type == "tool_call":
                # MCP-style tool call
                tool_name = request.get("tool")
                tool_input = request.get("input", {})
                _command_queue.put(("tool_call", tool_name, tool_input))
                try:
                    response = _result_queue.get(timeout=timeout)
                except queue.Empty:
                    response = {"status": "error", "error": "Tool call timed out"}
            elif command_type == "get_tools":
                # Return available tool definitions
                from .tools import get_all_tool_definitions
                response = {"status": "ok", "tools": get_all_tool_definitions()}
            elif command_type == "render":
                render_settings = request.get("settings", {})
                script = _build_render_script(render_settings)
                _command_queue.put(("execute", script))
                try:
                    response = _result_queue.get(timeout=request.get("timeout", 300))
                except queue.Empty:
                    response = {"status": "error", "error": "Render timed out"}
            else:
                response = {"status": "error", "error": f"Unknown command: {command_type}"}

            response_data = json.dumps(response, default=str).encode("utf-8")
            client_socket.sendall(len(response_data).to_bytes(4, "big") + response_data)

        except Exception as e:
            try:
                err = json.dumps({"status": "error", "error": str(e)}).encode("utf-8")
                client_socket.sendall(len(err).to_bytes(4, "big") + err)
            except Exception:
                pass
        finally:
            client_socket.close()


def _recv_all(sock):
    """Receive a length-prefixed message."""
    header = b""
    while len(header) < 4:
        chunk = sock.recv(4 - len(header))
        if not chunk:
            return None
        header += chunk
    msg_len = int.from_bytes(header, "big")
    data = b""
    while len(data) < msg_len:
        chunk = sock.recv(min(msg_len - len(data), 65536))
        if not chunk:
            return None
        data += chunk
    return data


def _build_render_script(settings):
    output_path = settings.get("output_path", "/tmp/blenderbot_render.png")
    resolution_x = settings.get("resolution_x", 1920)
    resolution_y = settings.get("resolution_y", 1080)
    samples = settings.get("samples", 128)
    engine = settings.get("engine", "CYCLES")
    animation = settings.get("animation", False)
    frame_start = settings.get("frame_start", 1)
    frame_end = settings.get("frame_end", 250)

    return f"""
import bpy
scene = bpy.context.scene
scene.render.engine = '{engine}'
scene.render.resolution_x = {resolution_x}
scene.render.resolution_y = {resolution_y}
scene.render.filepath = '{output_path}'
if scene.render.engine == 'CYCLES':
    scene.cycles.samples = {samples}
if {animation}:
    scene.frame_start = {frame_start}
    scene.frame_end = {frame_end}
    bpy.ops.render.render(animation=True)
else:
    bpy.ops.render.render(write_still=True)
result = '{output_path}'
"""


def _process_command_queue():
    """Timer callback - processes commands on the main thread (bpy-safe)."""
    global _server
    if not _server or not _server._running:
        return None

    try:
        command = _command_queue.get_nowait()
    except queue.Empty:
        return 0.05

    if command[0] == "execute":
        script = command[1]
        result = _execute_script(script)
    elif command[0] == "tool_call":
        tool_name = command[1]
        tool_input = command[2]
        result = _execute_tool(tool_name, tool_input)
    else:
        result = {"status": "error", "error": f"Unknown command type: {command[0]}"}

    _result_queue.put(result)
    return 0.05


def _execute_script(script):
    """Execute a Python script in the Blender context."""
    namespace = {"__name__": "__blenderbot__", "bpy": bpy}
    try:
        exec(compile(script, "<blenderbot>", "exec"), namespace)
        script_result = namespace.get("result", None)
        return {
            "status": "ok",
            "result": str(script_result) if script_result is not None else None,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


def _execute_tool(tool_name, tool_input):
    """Execute a named tool with the given input on the main thread."""
    from .tools import get_tool_executor

    func = get_tool_executor(tool_name)
    if not func:
        return {"status": "error", "error": f"Unknown tool: {tool_name}"}

    try:
        result = func(**tool_input)
        return {"status": "ok", "result": result}
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


# Global server instance
_server = None


class BLENDERBOT_OT_start_server(bpy.types.Operator):
    """Start the BlenderBot server"""
    bl_idname = "blenderbot.start_server"
    bl_label = "Start Server"

    def execute(self, context):
        global _server
        prefs = context.preferences.addons[__name__].preferences
        if _server and _server._running:
            self.report({"WARNING"}, "Server already running")
            return {"CANCELLED"}
        _server = BlenderBotServer(host=prefs.host, port=prefs.port)
        _server.start()
        context.scene.blenderbot_running = True
        self.report({"INFO"}, f"BlenderBot started on {prefs.host}:{prefs.port}")
        bpy.app.timers.register(_process_command_queue, first_interval=0.1)
        return {"FINISHED"}


class BLENDERBOT_OT_stop_server(bpy.types.Operator):
    """Stop the BlenderBot server"""
    bl_idname = "blenderbot.stop_server"
    bl_label = "Stop Server"

    def execute(self, context):
        global _server
        if _server:
            _server.stop()
            _server = None
        context.scene.blenderbot_running = False
        self.report({"INFO"}, "BlenderBot stopped")
        return {"FINISHED"}


class BLENDERBOT_PT_panel(bpy.types.Panel):
    """BlenderBot main panel"""
    bl_label = "BlenderBot"
    bl_idname = "BLENDERBOT_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BlenderBot"

    def draw(self, context):
        layout = self.layout
        prefs = context.preferences.addons[__name__].preferences
        running = getattr(context.scene, "blenderbot_running", False)

        # Server controls
        box = layout.box()
        box.label(text="Server", icon="WORLD")
        row = box.row()
        row.label(text=f"{prefs.host}:{prefs.port}")

        if running:
            row = box.row()
            row.scale_y = 1.5
            row.operator("blenderbot.stop_server", icon="PAUSE")
            box.label(text="Status: Running", icon="CHECKMARK")
        else:
            row = box.row()
            row.scale_y = 1.5
            row.operator("blenderbot.start_server", icon="PLAY")
            box.label(text="Status: Stopped", icon="X")

        # Tool modules info
        box = layout.box()
        box.label(text="Available Tools", icon="TOOL_SETTINGS")
        from .tools import get_all_tool_definitions
        tools = get_all_tool_definitions()
        box.label(text=f"{len(tools)} tools loaded")

        # Group by package
        from .tools.base import ToolsPackageBase
        for pkg in ToolsPackageBase.get_all_packages():
            pkg_tools = pkg.get_all_tools()
            if pkg_tools:
                row = box.row()
                row.label(text=f"  {pkg.__name__}: {len(pkg_tools)} tools", icon="DOT")


class BlenderBotPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    host: bpy.props.StringProperty(
        name="Host", default=DEFAULT_HOST,
        description="Server host address",
    )
    port: bpy.props.IntProperty(
        name="Port", default=DEFAULT_PORT,
        min=1024, max=65535,
        description="Server port",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "host")
        layout.prop(self, "port")


_classes = (
    BlenderBotPreferences,
    BLENDERBOT_OT_start_server,
    BLENDERBOT_OT_stop_server,
    BLENDERBOT_PT_panel,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.blenderbot_running = bpy.props.BoolProperty(default=False)
    Timer.register()


def unregister():
    global _server
    if _server:
        _server.stop()
        _server = None
    Timer.unregister()
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
    if hasattr(bpy.types.Scene, "blenderbot_running"):
        del bpy.types.Scene.blenderbot_running
