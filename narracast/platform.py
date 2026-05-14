"""Small platform helpers for desktop shell integration."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import urllib.request
from pathlib import Path


def _popen(command: list[str]) -> subprocess.Popen:
    return subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _path_to_file_uri(path: str) -> str:
    """Convert an absolute filesystem path to a file:// URI."""
    # urllib.request.pathname2url returns a URL-encoded path component.
    # On Windows it produces '/C:/...' so we strip the leading slash.
    url_path = urllib.request.pathname2url(path)
    # Ensure we have exactly three slashes for an absolute file URI
    # (file:///...).  pathname2url may already start with '///' on Windows
    # when the path starts with a drive letter.
    if not url_path.startswith("///"):
        url_path = "/" + url_path.lstrip("/")
    return "file://" + url_path


def play_audio(path: str | Path) -> subprocess.Popen:
    """Play an audio file with the host platform's default local player.

    Returns a ``subprocess.Popen`` whose lifecycle the caller can track.
    The process exits naturally when playback finishes.

    Raises:
        RuntimeError: on Linux when no supported player is found.
    """
    audio_path = str(Path(path).expanduser())
    system = platform.system()

    if system == "Darwin":
        return _popen(["afplay", audio_path])

    if system == "Windows":
        # Pass the path as a file:// URI so MediaPlayer receives it correctly
        # regardless of spaces, non-ASCII characters, or backslashes.
        uri = _path_to_file_uri(audio_path)
        ps_script = (
            "Add-Type -AssemblyName presentationCore; "
            "$p = New-Object System.Windows.Media.MediaPlayer; "
            f"$p.Open([System.Uri]::new('{uri}')); "
            "$p.Play(); "
            "Start-Sleep -Seconds 3600"
        )
        return _popen(["powershell", "-NoProfile", "-Command", ps_script])

    # Linux / other POSIX: try common command-line players in order of preference
    player = shutil.which("ffplay") or shutil.which("mpg123") or shutil.which("aplay")
    if not player:
        raise RuntimeError(
            "No audio player found. Install ffmpeg (ffplay), mpg123, or alsa-utils (aplay)."
        )
    if Path(player).name == "ffplay":
        return _popen([player, "-nodisp", "-autoexit", audio_path])
    return _popen([player, audio_path])


def reveal_path(path: str | Path) -> subprocess.Popen:
    """Reveal a file in the native file browser.

    On macOS this opens Finder with the file selected.
    On Windows this opens Explorer with the file selected.
    On Linux this opens the parent folder in the default file manager.

    Raises:
        RuntimeError: on Linux when xdg-open is not found.
    """
    target = str(Path(path).expanduser())
    system = platform.system()
    if system == "Darwin":
        return _popen(["open", "-R", target])
    if system == "Windows":
        # /select highlights the file inside Explorer
        return _popen(["explorer", f"/select,{target}"])
    folder = str(Path(target).parent)
    opener = shutil.which("xdg-open")
    if not opener:
        raise RuntimeError("xdg-open not found. Install xdg-utils to reveal files.")
    return _popen([opener, folder])


def open_folder(path: str | Path) -> subprocess.Popen:
    """Open a folder in the native file browser.

    Raises:
        RuntimeError: on Linux when xdg-open is not found.
    """
    folder = str(Path(path).expanduser())
    system = platform.system()
    if system == "Darwin":
        return _popen(["open", folder])
    if system == "Windows":
        return _popen(["explorer", folder])
    opener = shutil.which("xdg-open")
    if not opener:
        raise RuntimeError("xdg-open not found. Install xdg-utils to open folders.")
    return _popen([opener, folder])


def reveal_label() -> str:
    """Return the OS-appropriate label for a 'reveal in file browser' action."""
    system = platform.system()
    if system == "Darwin":
        return "Reveal in Finder"
    if system == "Windows":
        return "Show in Explorer"
    return "Show in Files"


def log_dir() -> Path:
    """Return the preferred platform log directory.

    - macOS:   ~/Library/Logs
    - Windows: %LOCALAPPDATA%\\Narracast\\Logs  (falls back to %APPDATA%)
    - Linux:   ~/.local/state/narracast/logs   (XDG_STATE_HOME aware)
    """
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Logs"
    if system == "Windows":
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if root:
            return Path(root) / "Narracast" / "Logs"
        return Path.home() / "AppData" / "Local" / "Narracast" / "Logs"
    # Linux / other POSIX — respect XDG_STATE_HOME if set
    xdg_state = os.environ.get("XDG_STATE_HOME")
    root = Path(xdg_state).expanduser() if xdg_state else Path.home() / ".local" / "state"
    return root / "narracast" / "logs"
