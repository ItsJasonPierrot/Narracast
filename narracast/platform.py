"""Small platform helpers for desktop shell integration."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path


def _popen(command: list[str]) -> subprocess.Popen:
    return subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def play_audio(path: str | Path) -> subprocess.Popen:
    """Play an audio file with the host platform's simple local player."""
    audio_path = str(Path(path).expanduser())
    system = platform.system()
    if system == "Darwin":
        return _popen(["afplay", audio_path])
    if system == "Windows":
        escaped = audio_path.replace("'", "''")
        return _popen([
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Add-Type -AssemblyName presentationCore; "
                "$p = New-Object System.Windows.Media.MediaPlayer; "
                f"$p.Open('{escaped}'); "
                "$p.Play(); "
                "Start-Sleep -Seconds 3600"
            ),
        ])

    player = shutil.which("ffplay") or shutil.which("mpg123") or shutil.which("aplay")
    if not player:
        raise RuntimeError("No supported command-line audio player found.")
    if Path(player).name == "ffplay":
        return _popen([player, "-nodisp", "-autoexit", audio_path])
    return _popen([player, audio_path])


def reveal_path(path: str | Path) -> subprocess.Popen:
    """Reveal a file in the native file browser where supported."""
    target = str(Path(path).expanduser())
    system = platform.system()
    if system == "Darwin":
        return _popen(["open", "-R", target])
    if system == "Windows":
        return _popen(["explorer", f"/select,{target}"])
    folder = str(Path(target).parent)
    opener = shutil.which("xdg-open")
    if not opener:
        raise RuntimeError("xdg-open not found.")
    return _popen([opener, folder])


def open_folder(path: str | Path) -> subprocess.Popen:
    """Open a folder in the native file browser."""
    folder = str(Path(path).expanduser())
    system = platform.system()
    if system == "Darwin":
        return _popen(["open", folder])
    if system == "Windows":
        return _popen(["explorer", folder])
    opener = shutil.which("xdg-open")
    if not opener:
        raise RuntimeError("xdg-open not found.")
    return _popen([opener, folder])


def log_dir() -> Path:
    """Return the preferred platform log directory."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Logs"
    if system == "Windows":
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if root:
            return Path(root) / "Narracast" / "Logs"
    return Path.home() / ".local" / "state" / "narracast" / "logs"
