"""
BlenderBot Addon - Receives commands from the BlenderBot server and executes them in Blender.

Install: Edit > Preferences > Add-ons > Install, select this folder.
"""

bl_info = {
    "name": "BlenderBot Remote",
    "author": "BlenderBot",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > BlenderBot",
    "description": "Receive and execute commands from the BlenderBot AI assistant",
    "category": "Interface",
}

import bpy
import json
import socket
import threading
import traceback
import queue
from pathlib import Path


# Thread-safe queue for commands received from the server
_command_queue = queue.Queue()
# Thread-safe queue for results to send back
_result_queue = queue.Queue()

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9876


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
        """Handle a single client connection."""
        try:
            client_socket.settimeout(300)  # 5 min timeout for long renders
            data = self._recv_all(client_socket)
            if not data:
                return

            request = json.loads(data.decode("utf-8"))
            command_type = request.get("type", "execute")

            if command_type == "ping":
                response = {"status": "ok", "message": "pong"}
            elif command_type == "execute":
                # Queue the script for execution on the main thread
                script = request.get("script", "")
                _command_queue.put(script)
                # Wait for result (blocks this handler thread, not the main thread)
                try:
                    result = _result_queue.get(timeout=request.get("timeout", 120))
                    response = result
                except queue.Empty:
                    response = {"status": "error", "error": "Execution timed out"}
            elif command_type == "render":
                # Queue a render command
                render_settings = request.get("settings", {})
                script = _build_render_script(render_settings)
                _command_queue.put(script)
                try:
                    result = _result_queue.get(timeout=request.get("timeout", 300))
                    response = result
                except queue.Empty:
                    response = {"status": "error", "error": "Render timed out"}
            else:
                response = {"status": "error", "error": f"Unknown command type: {command_type}"}

            response_data = json.dumps(response).encode("utf-8")
            length_header = len(response_data).to_bytes(4, "big")
            client_socket.sendall(length_header + response_data)

        except Exception as e:
            try:
                err = json.dumps({"status": "error", "error": str(e)}).encode("utf-8")
                client_socket.sendall(len(err).to_bytes(4, "big") + err)
            except Exception:
                pass
        finally:
            client_socket.close()

    def _recv_all(self, sock):
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
    """Build a Blender Python script to configure and execute a render."""
    output_path = settings.get("output_path", "/tmp/blenderbot_render.png")
    resolution_x = settings.get("resolution_x", 1920)
    resolution_y = settings.get("resolution_y", 1080)
    samples = settings.get("samples", 128)
    engine = settings.get("engine", "CYCLES")
    animation = settings.get("animation", False)
    frame_start = settings.get("frame_start", 1)
    frame_end = settings.get("frame_end", 250)

    script = f"""
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
    result = '{output_path}'
else:
    bpy.ops.render.render(write_still=True)
    result = '{output_path}'
"""
    return script


# Global server instance
_server = None


class BLENDERBOT_OT_start_server(bpy.types.Operator):
    """Start the BlenderBot server"""
    bl_idname = "blenderbot.start_server"
    bl_label = "Start BlenderBot Server"

    def execute(self, context):
        global _server
        prefs = context.preferences.addons[__name__].preferences
        if _server and _server._running:
            self.report({"WARNING"}, "Server already running")
            return {"CANCELLED"}
        _server = BlenderBotServer(host=prefs.host, port=prefs.port)
        _server.start()
        context.scene.blenderbot_running = True
        self.report({"INFO"}, f"BlenderBot server started on {prefs.host}:{prefs.port}")
        # Start the timer that processes queued commands
        bpy.app.timers.register(_process_command_queue, first_interval=0.1)
        return {"FINISHED"}


class BLENDERBOT_OT_stop_server(bpy.types.Operator):
    """Stop the BlenderBot server"""
    bl_idname = "blenderbot.stop_server"
    bl_label = "Stop BlenderBot Server"

    def execute(self, context):
        global _server
        if _server:
            _server.stop()
            _server = None
        context.scene.blenderbot_running = False
        self.report({"INFO"}, "BlenderBot server stopped")
        return {"FINISHED"}


class BLENDERBOT_PT_panel(bpy.types.Panel):
    """BlenderBot control panel in the 3D viewport sidebar"""
    bl_label = "BlenderBot"
    bl_idname = "BLENDERBOT_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BlenderBot"

    def draw(self, context):
        layout = self.layout
        prefs = context.preferences.addons[__name__].preferences
        running = getattr(context.scene, "blenderbot_running", False)

        layout.label(text=f"Host: {prefs.host}:{prefs.port}")

        if running:
            layout.operator("blenderbot.stop_server", icon="PAUSE")
            layout.label(text="Status: Running", icon="CHECKMARK")
        else:
            layout.operator("blenderbot.start_server", icon="PLAY")
            layout.label(text="Status: Stopped", icon="X")


class BlenderBotPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    host: bpy.props.StringProperty(
        name="Host",
        default=DEFAULT_HOST,
        description="Server host address",
    )
    port: bpy.props.IntProperty(
        name="Port",
        default=DEFAULT_PORT,
        min=1024,
        max=65535,
        description="Server port",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "host")
        layout.prop(self, "port")


def _process_command_queue():
    """Timer callback that runs on the main thread to execute queued scripts."""
    global _server
    if not _server or not _server._running:
        return None  # Unregister timer

    try:
        script = _command_queue.get_nowait()
    except queue.Empty:
        return 0.1  # Check again in 100ms

    # Execute the script on the main thread
    result = _execute_script(script)
    _result_queue.put(result)

    return 0.1  # Continue checking


def _execute_script(script):
    """Execute a Python script in the Blender context and return the result."""
    namespace = {"__name__": "__blenderbot__", "bpy": bpy}
    try:
        exec(compile(script, "<blenderbot>", "exec"), namespace)
        # Check if the script set a 'result' variable
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


def unregister():
    global _server
    if _server:
        _server.stop()
        _server = None
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
    if hasattr(bpy.types.Scene, "blenderbot_running"):
        del bpy.types.Scene.blenderbot_running
