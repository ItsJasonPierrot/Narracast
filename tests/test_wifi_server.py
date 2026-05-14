"""Tests for narracast.wifi_server.

All tests spin up a real WifiServer against a temporary directory so they
exercise the actual HTTP logic without mocking the network.  No new
dependencies — stdlib urllib is used as the HTTP client.
"""

import json
import os
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from narracast.wifi_server import WifiServer, _get_local_ip, _find_free_port


# ── Helpers ───────────────────────────────────────────────────────────────────

def _start_server(output_dir: Path) -> WifiServer:
    """Start a WifiServer against *output_dir* and return it."""
    server = WifiServer(output_dir)
    server.start()
    # Give the background thread a moment to bind
    time.sleep(0.05)
    return server


def _get(url: str) -> tuple[int, bytes, str]:
    """Return (status_code, body_bytes, content_type)."""
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, resp.read(), resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), ""


def _get_with_range(url: str, start: int, end: int) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _make_mp3(output_dir: Path, name: str = "test.mp3") -> Path:
    """Write a minimal stub MP3 (just bytes, not valid audio)."""
    path = output_dir / name
    path.write_bytes(b"\xff\xfb" * 512)   # 1024 bytes of fake MP3 data
    return path


def _make_sidecar(output_dir: Path, mp3_name: str, **extra) -> Path:
    """Write a minimal sidecar JSON alongside *mp3_name*."""
    meta = {
        "schema_version": 2,
        "output_filename": mp3_name,
        "output_path": str(output_dir / mp3_name),  # should be stripped by /api/metadata
        "title": "Test Chapter",
        "part": "Part 1",
        "duration_ms": 120_000,
        "created_at": "2026-05-14T10:00:00",
        **extra,
    }
    path = output_dir / mp3_name.replace(".mp3", ".json")
    path.write_text(json.dumps(meta), encoding="utf-8")
    return path


# ── Test cases ────────────────────────────────────────────────────────────────

class TestHelpers(unittest.TestCase):
    def test_get_local_ip_returns_string(self):
        ip = _get_local_ip()
        self.assertIsInstance(ip, str)
        self.assertGreater(len(ip), 0)

    def test_find_free_port_returns_int(self):
        port = _find_free_port()
        self.assertIsInstance(port, int)
        self.assertGreaterEqual(port, 8765)

    def test_find_free_port_is_usable(self):
        import socket
        port = _find_free_port()
        # Should be able to bind to the returned port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("", port))
            except OSError:
                self.fail(f"Port {port} returned by _find_free_port is not bindable")


class TestWifiServerLifecycle(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.output_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_not_running_before_start(self):
        server = WifiServer(self.output_dir)
        self.assertFalse(server.is_running())
        self.assertIsNone(server.url)

    def test_running_after_start(self):
        server = _start_server(self.output_dir)
        try:
            self.assertTrue(server.is_running())
            self.assertIsNotNone(server.url)
            self.assertIn("http://", server.url)
        finally:
            server.stop()

    def test_url_format(self):
        server = _start_server(self.output_dir)
        try:
            url = server.url
            self.assertRegex(url, r"http://[\d.]+:\d+")
        finally:
            server.stop()

    def test_stopped_after_stop(self):
        server = _start_server(self.output_dir)
        server.stop()
        self.assertFalse(server.is_running())
        self.assertIsNone(server.url)

    def test_start_twice_is_noop(self):
        server = _start_server(self.output_dir)
        try:
            first_url = server.url
            server.start()  # second start should be a no-op
            self.assertEqual(first_url, server.url)
        finally:
            server.stop()

    def test_on_started_callback(self):
        called_with = []
        server = WifiServer(self.output_dir, on_started=called_with.append)
        server.start()
        time.sleep(0.05)
        try:
            self.assertEqual(len(called_with), 1)
            self.assertIn("http://", called_with[0])
        finally:
            server.stop()

    def test_on_error_callback_on_bad_port_range(self):
        errors = []

        def mock_find_free_port(*a, **kw):
            raise OSError("no free port")

        server = WifiServer(self.output_dir, on_error=errors.append)
        with patch("narracast.wifi_server._find_free_port", mock_find_free_port):
            try:
                server.start()
            except OSError:
                pass
        self.assertEqual(len(errors), 1)


class TestInfoEndpoint(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._server = _start_server(Path(self._tmp.name))
        self._base = self._server.url

    def tearDown(self):
        self._server.stop()
        self._tmp.cleanup()

    def test_info_returns_200(self):
        status, _, _ = _get(f"{self._base}/api/info")
        self.assertEqual(status, 200)

    def test_info_content_type(self):
        _, _, ct = _get(f"{self._base}/api/info")
        self.assertIn("application/json", ct)

    def test_info_shape(self):
        _, body, _ = _get(f"{self._base}/api/info")
        data = json.loads(body)
        self.assertEqual(data["server"], "narracast")
        self.assertEqual(data["schema_version"], 2)

    def test_unknown_path_returns_404(self):
        status, _, _ = _get(f"{self._base}/no/such/route")
        self.assertEqual(status, 404)


class TestFilesEndpoint(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._output = Path(self._tmp.name)
        self._server = _start_server(self._output)
        self._base = self._server.url

    def tearDown(self):
        self._server.stop()
        self._tmp.cleanup()

    def test_empty_output_returns_empty_list(self):
        status, body, _ = _get(f"{self._base}/api/files")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), [])

    def test_files_with_mp3_returns_descriptor(self):
        mp3 = _make_mp3(self._output, "chapter.mp3")
        _make_sidecar(self._output, "chapter.mp3")
        time.sleep(0.05)  # let mtime settle

        _, body, _ = _get(f"{self._base}/api/files")
        data = json.loads(body)
        self.assertEqual(len(data), 1)
        desc = data[0]
        self.assertEqual(desc["filename"], "chapter.mp3")
        self.assertTrue(desc["has_metadata"])
        self.assertEqual(desc["title"], "Test Chapter")
        self.assertEqual(desc["part"], "Part 1")
        self.assertEqual(desc["duration_ms"], 120_000)

    def test_files_without_sidecar_returns_has_metadata_false(self):
        _make_mp3(self._output, "nosidecar.mp3")
        _, body, _ = _get(f"{self._base}/api/files")
        data = json.loads(body)
        self.assertEqual(len(data), 1)
        self.assertFalse(data[0]["has_metadata"])

    def test_files_descriptor_has_required_keys(self):
        _make_mp3(self._output, "x.mp3")
        _, body, _ = _get(f"{self._base}/api/files")
        desc = json.loads(body)[0]
        for key in ("filename", "size_bytes", "has_metadata", "title",
                    "part", "duration_ms", "created_at"):
            self.assertIn(key, desc, msg=f"Missing key: {key}")

    def test_multiple_files_returned(self):
        for i in range(3):
            _make_mp3(self._output, f"ch{i}.mp3")
        _, body, _ = _get(f"{self._base}/api/files")
        self.assertEqual(len(json.loads(body)), 3)


class TestAudioEndpoint(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._output = Path(self._tmp.name)
        self._server = _start_server(self._output)
        self._base = self._server.url

    def tearDown(self):
        self._server.stop()
        self._tmp.cleanup()

    def test_existing_file_returns_200(self):
        _make_mp3(self._output, "track.mp3")
        status, _, ct = _get(f"{self._base}/api/audio/track.mp3")
        self.assertEqual(status, 200)
        self.assertEqual(ct, "audio/mpeg")

    def test_file_content_matches_disk(self):
        mp3 = _make_mp3(self._output, "track.mp3")
        _, body, _ = _get(f"{self._base}/api/audio/track.mp3")
        self.assertEqual(body, mp3.read_bytes())

    def test_missing_file_returns_404(self):
        status, _, _ = _get(f"{self._base}/api/audio/nosuchfile.mp3")
        self.assertEqual(status, 404)

    def test_path_traversal_returns_400(self):
        status, _, _ = _get(f"{self._base}/api/audio/../secret.txt")
        # urllib follows the URL as-is; server should reject the traversal attempt
        self.assertIn(status, (400, 404))

    def test_path_traversal_with_literal_dots_returns_400(self):
        status, _, _ = _get(f"{self._base}/api/audio/..%2Fsecret.txt")
        self.assertIn(status, (400, 404))

    def test_range_request_returns_206(self):
        _make_mp3(self._output, "track.mp3")
        status, body = _get_with_range(f"{self._base}/api/audio/track.mp3", 0, 99)
        self.assertEqual(status, 206)
        self.assertEqual(len(body), 100)

    def test_range_request_returns_correct_slice(self):
        mp3 = _make_mp3(self._output, "track.mp3")
        expected = mp3.read_bytes()[10:20]
        _, body = _get_with_range(f"{self._base}/api/audio/track.mp3", 10, 19)
        self.assertEqual(body, expected)

    def test_accept_ranges_header_present(self):
        _make_mp3(self._output, "track.mp3")
        req = urllib.request.Request(f"{self._base}/api/audio/track.mp3")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.headers.get("Accept-Ranges"), "bytes")


class TestMetadataEndpoint(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._output = Path(self._tmp.name)
        self._server = _start_server(self._output)
        self._base = self._server.url

    def tearDown(self):
        self._server.stop()
        self._tmp.cleanup()

    def test_existing_sidecar_returns_200(self):
        _make_mp3(self._output, "ch.mp3")
        _make_sidecar(self._output, "ch.mp3")
        status, _, ct = _get(f"{self._base}/api/metadata/ch.mp3")
        self.assertEqual(status, 200)
        self.assertIn("application/json", ct)

    def test_output_path_is_stripped(self):
        _make_mp3(self._output, "ch.mp3")
        _make_sidecar(self._output, "ch.mp3")
        _, body, _ = _get(f"{self._base}/api/metadata/ch.mp3")
        data = json.loads(body)
        self.assertNotIn("output_path", data)

    def test_json_extension_also_works(self):
        _make_mp3(self._output, "ch.mp3")
        _make_sidecar(self._output, "ch.mp3")
        status, body, _ = _get(f"{self._base}/api/metadata/ch.json")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["title"], "Test Chapter")

    def test_missing_sidecar_returns_404(self):
        _make_mp3(self._output, "ch.mp3")  # no sidecar
        status, _, _ = _get(f"{self._base}/api/metadata/ch.mp3")
        self.assertEqual(status, 404)

    def test_metadata_content_matches_sidecar(self):
        _make_mp3(self._output, "ch.mp3")
        _make_sidecar(self._output, "ch.mp3", source_text="Hello world")
        _, body, _ = _get(f"{self._base}/api/metadata/ch.mp3")
        data = json.loads(body)
        self.assertEqual(data["source_text"], "Hello world")
        self.assertEqual(data["title"], "Test Chapter")


if __name__ == "__main__":
    unittest.main()
