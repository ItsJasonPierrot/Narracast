"""Local WiFi transfer server for Narracast.

Runs a small stdlib HTTP server so an iPhone companion app (or Safari) can
browse and download generated MP3s and their sidecar JSON over the local
network.  No new dependencies — stdlib only.

Usage
-----
::

    from narracast.wifi_server import WifiServer
    from narracast.paths import OUTPUT_DIR

    server = WifiServer(OUTPUT_DIR)
    server.start()          # blocks briefly; returns once listening
    print(server.url)       # "http://192.168.1.42:8765"
    ...
    server.stop()

Endpoints
---------
GET /api/info
    ``{"server": "narracast", "schema_version": 2}``

GET /api/files
    JSON array of file descriptors — one per MP3 in the output directory.

GET /api/audio/<filename>
    Serves the raw MP3.  Supports ``Range`` requests so iOS can seek.

GET /api/metadata/<filename>
    Serves the sidecar JSON, with ``output_path`` stripped (system path).

Security
--------
Every requested filename is validated against the output directory.  Any
path that would escape (``..``, absolute path, ``/`` inside the name) returns
HTTP 400 before touching the filesystem.
"""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urlparse


# ── Metadata schema version exposed in /api/info ──────────────────────────────

_SCHEMA_VERSION = 2

# ── Port range ────────────────────────────────────────────────────────────────

_DEFAULT_PORT = 8765
_PORT_RETRIES = 10


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_local_ip() -> str:
    """Return the LAN IP address used for outbound connections.

    Connects a UDP socket to a public address (no data is sent) and reads
    which local interface would be selected.  Falls back to ``127.0.0.1``
    if no network is available.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _find_free_port(start: int = _DEFAULT_PORT, retries: int = _PORT_RETRIES) -> int:
    """Find the first free TCP port starting at *start*."""
    for port in range(start, start + retries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("", port))
                return port
            except OSError:
                continue
    raise OSError(
        f"Could not find a free port in range {start}–{start + retries - 1}."
    )


# ── Request handler ───────────────────────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    """HTTP request handler for the Narracast WiFi transfer server."""

    # ── Routing ──────────────────────────────────────────────────────────────

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/api/info":
            self._serve_info()
        elif path == "/api/files":
            self._serve_files()
        elif path.startswith("/api/audio/"):
            filename = unquote(path[len("/api/audio/"):])
            self._serve_audio(filename)
        elif path.startswith("/api/metadata/"):
            filename = unquote(path[len("/api/metadata/"):])
            self._serve_metadata(filename)
        else:
            self._send_error(404, "Not found")

    # ── Endpoint implementations ──────────────────────────────────────────────

    def _serve_info(self) -> None:
        self._send_json({"server": "narracast", "schema_version": _SCHEMA_VERSION})

    def _serve_files(self) -> None:
        output_dir: Path = self.server.output_dir  # type: ignore[attr-defined]
        result = []
        for mp3 in sorted(output_dir.glob("*.mp3"),
                          key=lambda f: f.stat().st_mtime, reverse=True):
            try:
                stat = mp3.stat()
            except OSError:
                continue

            descriptor: dict = {
                "filename": mp3.name,
                "size_bytes": stat.st_size,
                "has_metadata": False,
                "title": "",
                "part": "",
                "duration_ms": 0,
                "created_at": "",
            }

            sidecar = mp3.with_suffix(".json")
            if sidecar.exists():
                try:
                    meta = json.loads(sidecar.read_text(encoding="utf-8"))
                    descriptor["has_metadata"] = True
                    descriptor["title"] = str(meta.get("title", ""))
                    descriptor["part"] = str(meta.get("part", ""))
                    descriptor["duration_ms"] = int(meta.get("duration_ms", 0))
                    descriptor["created_at"] = str(meta.get("created_at", ""))
                except (OSError, json.JSONDecodeError, ValueError):
                    pass

            result.append(descriptor)

        self._send_json(result)

    def _serve_audio(self, filename: str) -> None:
        path = self._validate_filename(filename)
        if path is None:
            self._send_error(400, "Invalid filename")
            return
        if not path.exists():
            self._send_error(404, "Not found")
            return

        file_size = path.stat().st_size
        range_header = self.headers.get("Range")

        try:
            if range_header:
                start, end = self._parse_range(range_header, file_size)
                length = end - start + 1
                self.send_response(206)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(length))
                self.send_header("Content-Range",
                                 f"bytes {start}-{end}/{file_size}")
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                with open(path, "rb") as f:
                    f.seek(start)
                    remaining = length
                    chunk = 65536
                    while remaining > 0:
                        data = f.read(min(chunk, remaining))
                        if not data:
                            break
                        self.wfile.write(data)
                        remaining -= len(data)
            else:
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(file_size))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                with open(path, "rb") as f:
                    while True:
                        data = f.read(65536)
                        if not data:
                            break
                        self.wfile.write(data)
        except (OSError, BrokenPipeError):
            pass  # client disconnected mid-stream

    def _serve_metadata(self, filename: str) -> None:
        # Accept "<name>.mp3" or "<name>.json" — always resolve to the sidecar
        if filename.endswith(".mp3"):
            base = filename[:-4]
        elif filename.endswith(".json"):
            base = filename[:-5]
        else:
            base = filename

        sidecar_name = base + ".json"
        path = self._validate_filename(sidecar_name)
        if path is None:
            self._send_error(400, "Invalid filename")
            return
        if not path.exists():
            self._send_error(404, "Not found")
            return

        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._send_error(500, "Could not read metadata")
            return

        # Strip the local system path — not useful on mobile
        meta.pop("output_path", None)

        self._send_json(meta)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _validate_filename(self, filename: str) -> Path | None:
        """Return a safe resolved Path, or None if the filename is rejected.

        Rejects: empty, containing ``/`` or ``\\``, starting with ``.``,
        or resolving outside ``output_dir``.
        """
        if not filename:
            return None
        # Reject path separators or leading dots inside the component
        if "/" in filename or "\\" in filename or filename.startswith("."):
            return None
        output_dir: Path = self.server.output_dir  # type: ignore[attr-defined]
        try:
            resolved = (output_dir / filename).resolve()
        except (OSError, ValueError):
            return None
        if resolved.parent != output_dir.resolve():
            return None
        return resolved

    def _parse_range(self, header: str, total: int) -> tuple[int, int]:
        """Parse a ``Range: bytes=start-end`` header."""
        try:
            unit, ranges = header.split("=", 1)
            if unit.strip() != "bytes":
                return 0, total - 1
            start_str, _, end_str = ranges.partition("-")
            start = int(start_str) if start_str.strip() else 0
            end = int(end_str) if end_str.strip() else total - 1
            start = max(0, min(start, total - 1))
            end = max(start, min(end, total - 1))
            return start, end
        except (ValueError, AttributeError):
            return 0, total - 1

    def _send_json(self, data) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str) -> None:
        body = json.dumps({"error": message}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args) -> None:  # noqa: A002
        pass  # suppress per-request log noise


# ── WifiServer ────────────────────────────────────────────────────────────────

class WifiServer:
    """Manages a single local HTTP server instance.

    Start with :meth:`start`; stop with :meth:`stop`.  The server runs in a
    daemon thread so it does not prevent the application from exiting.

    Attributes
    ----------
    local_ip : str | None
        LAN IP address once the server is running.
    port : int | None
        Bound port once the server is running.
    """

    def __init__(
        self,
        output_dir: Path,
        on_started: Callable[[str], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self._output_dir = output_dir
        self._on_started = on_started
        self._on_error = on_error
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.local_ip: str | None = None
        self.port: int | None = None

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def url(self) -> str | None:
        """Full base URL, e.g. ``http://192.168.1.42:8765``, or None."""
        if self.local_ip and self.port:
            return f"http://{self.local_ip}:{self.port}"
        return None

    def is_running(self) -> bool:
        """True if the server thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Bind and start the server in a background daemon thread.

        Raises :exc:`OSError` if no free port is found.  Calls
        ``on_started(url)`` once the server is listening.
        """
        if self.is_running():
            return

        try:
            self.port = _find_free_port()
            self.local_ip = _get_local_ip()
        except OSError as exc:
            if self._on_error:
                self._on_error(str(exc))
            raise

        # Attach output_dir to the server instance so _Handler can access it
        httpd = ThreadingHTTPServer(("0.0.0.0", self.port), _Handler)
        httpd.output_dir = self._output_dir  # type: ignore[attr-defined]
        self._httpd = httpd

        self._thread = threading.Thread(
            target=httpd.serve_forever,
            daemon=True,
            name="narracast-wifi",
        )
        self._thread.start()

        if self._on_started and self.url:
            self._on_started(self.url)

    def stop(self) -> None:
        """Shut down the server and wait for the thread to exit."""
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None
        self.port = None
        self.local_ip = None
