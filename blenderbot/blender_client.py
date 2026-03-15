"""Client for communicating with the BlenderBot addon running inside Blender."""

import json
import socket
from dataclasses import dataclass


@dataclass
class BlenderResponse:
    status: str
    result: str | None = None
    error: str | None = None
    traceback: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"


class BlenderClient:
    """Sends commands to the BlenderBot addon running inside Blender."""

    def __init__(self, host: str = "127.0.0.1", port: int = 9876):
        self.host = host
        self.port = port

    def ping(self) -> bool:
        """Check if the Blender addon server is reachable."""
        try:
            resp = self._send({"type": "ping"})
            return resp.ok
        except (ConnectionRefusedError, OSError):
            return False

    def execute(self, script: str, timeout: int = 120) -> BlenderResponse:
        """Execute a Python script inside Blender."""
        return self._send({
            "type": "execute",
            "script": script,
            "timeout": timeout,
        })

    def render(
        self,
        output_path: str = "/tmp/blenderbot_render.png",
        resolution: tuple[int, int] = (1920, 1080),
        engine: str = "CYCLES",
        samples: int = 128,
        animation: bool = False,
        frame_start: int = 1,
        frame_end: int = 250,
        timeout: int = 300,
    ) -> BlenderResponse:
        """Trigger a render in Blender."""
        return self._send({
            "type": "render",
            "settings": {
                "output_path": output_path,
                "resolution_x": resolution[0],
                "resolution_y": resolution[1],
                "engine": engine,
                "samples": samples,
                "animation": animation,
                "frame_start": frame_start,
                "frame_end": frame_end,
            },
            "timeout": timeout,
        })

    def _send(self, request: dict) -> BlenderResponse:
        """Send a request to the Blender addon and return the response."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(request.get("timeout", 120) + 10)
        try:
            sock.connect((self.host, self.port))
            data = json.dumps(request).encode("utf-8")
            sock.sendall(len(data).to_bytes(4, "big") + data)

            # Read response
            header = b""
            while len(header) < 4:
                chunk = sock.recv(4 - len(header))
                if not chunk:
                    raise ConnectionError("Connection closed while reading header")
                header += chunk

            msg_len = int.from_bytes(header, "big")
            body = b""
            while len(body) < msg_len:
                chunk = sock.recv(min(msg_len - len(body), 65536))
                if not chunk:
                    raise ConnectionError("Connection closed while reading body")
                body += chunk

            resp_data = json.loads(body.decode("utf-8"))
            return BlenderResponse(**resp_data)
        finally:
            sock.close()
