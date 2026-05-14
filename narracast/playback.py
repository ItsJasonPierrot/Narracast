"""Audio playback engine with wall-clock position tracking.

Uses ffplay (part of ffmpeg) for seeking to an offset when available;
falls back to the platform audio helper from the beginning if ffplay is not
installed.

Position updates are fired to `on_position(ms: int)` every POLL_MS
milliseconds from a background thread.  Callers must schedule any UI
work through `root.after()` themselves.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from .platform import play_audio


POLL_MS = 250  # position-update interval


class PlaybackSession:
    """Manages audio playback and reports the current position."""

    def __init__(
        self,
        file_path: str,
        duration_ms: int,
        on_position: Callable[[int], None],
        on_done: Callable[[], None],
    ):
        self.file_path = file_path
        self.duration_ms = duration_ms
        self.on_position = on_position
        self.on_done = on_done

        self._proc: Optional[subprocess.Popen] = None
        self._wall_start: Optional[float] = None
        self._offset_ms: int = 0
        self._running = False
        self._lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def position_ms(self) -> int:
        """Current playback position in milliseconds."""
        if self._wall_start is None:
            return self._offset_ms
        elapsed = int((time.time() - self._wall_start) * 1000)
        return min(self._offset_ms + elapsed, self.duration_ms)

    def play(self, from_ms: int = 0) -> None:
        """Start (or restart) playback from `from_ms`."""
        self.stop()
        self._offset_ms = max(0, from_ms)
        self._running = True
        self._wall_start = time.time()
        self._proc = _launch(self.file_path, self._offset_ms)
        threading.Thread(target=self._monitor, daemon=True).start()

    def stop(self) -> None:
        """Stop playback.  The current position is remembered in `_offset_ms`."""
        self._running = False
        self._wall_start = None
        with self._lock:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
            self._proc = None

    def pause_and_get_position(self) -> int:
        """Stop playback and return the position so the caller can resume later."""
        pos = self.position_ms
        self.stop()
        self._offset_ms = pos
        return pos

    def seek(self, ms: int) -> None:
        """Seek to `ms` and resume playback."""
        self.play(from_ms=max(0, ms))

    def back(self, secs: int = 10) -> None:
        """Step back `secs` seconds."""
        self.seek(max(0, self.position_ms - secs * 1000))

    def forward(self, secs: int = 10) -> None:
        """Step forward `secs` seconds."""
        self.seek(min(self.duration_ms, self.position_ms + secs * 1000))

    def repeat_chunk(self, timeline: list[dict]) -> None:
        """Restart playback from the beginning of the current chunk."""
        pos = self.position_ms
        start = 0
        for item in timeline:
            if item.get("type") in ("speech", "sentence"):
                if item["audio_start_ms"] <= pos < item["audio_end_ms"]:
                    start = item["audio_start_ms"]
                    break
        self.seek(start)

    def is_playing(self) -> bool:
        return self._running

    # ── Internal ──────────────────────────────────────────────────────────────

    def _monitor(self) -> None:
        while self._running:
            time.sleep(POLL_MS / 1000)
            if not self._running:
                break
            self.on_position(self.position_ms)
            with self._lock:
                if self._proc and self._proc.poll() is not None:
                    if self._running:
                        self._running = False
                        self.on_done()
                    break


# ── Player launch helpers ─────────────────────────────────────────────────────

_FFPLAY_AVAILABLE: Optional[bool] = None  # cached after first check


def _ffplay_available() -> bool:
    global _FFPLAY_AVAILABLE
    if _FFPLAY_AVAILABLE is None:
        try:
            subprocess.run(
                ["ffplay", "-version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
            )
            _FFPLAY_AVAILABLE = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            _FFPLAY_AVAILABLE = False
    return _FFPLAY_AVAILABLE


def _launch(file_path: str, offset_ms: int) -> subprocess.Popen:
    """Start audio playback, seeking to ``offset_ms`` when possible.

    Seeking requires ffplay (part of ffmpeg).  When ffplay is not available the
    file plays from the beginning regardless of ``offset_ms``; this is a known
    limitation on systems without ffmpeg installed.
    """
    if offset_ms > 500 and _ffplay_available():
        return subprocess.Popen(
            [
                "ffplay",
                "-nodisp",
                "-autoexit",
                "-loglevel", "quiet",
                "-ss", f"{offset_ms / 1000:.3f}",
                file_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    # ffplay not available or offset within tolerance — fall back to the
    # platform player from position 0.  On Windows this is the PowerShell
    # MediaPlayer approach; on Linux this requires ffplay, mpg123, or aplay.
    return play_audio(file_path)


# ── Position persistence ──────────────────────────────────────────────────────

# ── Bookmark persistence ──────────────────────────────────────────────────────

def load_bookmarks(metadata_path: str | Path) -> list[dict]:
    """Return the list of saved bookmarks, or [] if none."""
    try:
        data = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
        return list(data.get("bookmarks", []))
    except Exception:
        return []


def save_bookmark(metadata_path: str | Path, label: str, position_ms: int) -> None:
    """Append a bookmark to the sidecar JSON."""
    path = Path(metadata_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    bookmarks = list(data.get("bookmarks", []))
    bookmarks.append({"label": label, "position_ms": position_ms})
    data["bookmarks"] = bookmarks
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def delete_bookmark(metadata_path: str | Path, index: int) -> None:
    """Remove the bookmark at `index` from the sidecar JSON."""
    path = Path(metadata_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    bookmarks = list(data.get("bookmarks", []))
    if 0 <= index < len(bookmarks):
        bookmarks.pop(index)
    data["bookmarks"] = bookmarks
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Position persistence ──────────────────────────────────────────────────────

def load_last_position(metadata_path: str | Path) -> int:
    """Return the saved playback position in ms, or 0 if none."""
    try:
        data = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
        return int(data.get("last_position_ms", 0))
    except Exception:
        return 0


def save_last_position(metadata_path: str | Path, position_ms: int) -> None:
    """Write `position_ms` into the sidecar JSON without losing other fields."""
    path = Path(metadata_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    data["last_position_ms"] = position_ms
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
