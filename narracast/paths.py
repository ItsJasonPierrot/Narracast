"""Filesystem paths for Narracast.

Application assets live in the repository/app bundle. User-generated data lives
in the platform app-data folder so transcripts, projects, and generated audio do
not get mixed into source control checkouts.
"""

from __future__ import annotations

import os
import platform
import shutil
import tempfile
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
ICON_PATH = APP_DIR / "assets" / "Narracast_Icon.png"
SPLASH_ICON_PATH = APP_DIR / "assets" / "Narracast_Splash_Icon.png"


def _default_data_dir() -> Path:
    override = os.environ.get("NARRACAST_DATA_DIR")
    if override:
        return Path(override).expanduser()

    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Narracast"
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        root = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return root / "Narracast"

    xdg_data = os.environ.get("XDG_DATA_HOME")
    root = Path(xdg_data).expanduser() if xdg_data else Path.home() / ".local" / "share"
    return root / "narracast"


def _writable_data_dir() -> Path:
    candidate = _default_data_dir()
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate
    except OSError:
        if os.environ.get("NARRACAST_DATA_DIR"):
            raise
        fallback = Path(tempfile.gettempdir()) / "Narracast"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


DATA_DIR = _writable_data_dir()
LOG_DIR = (
    Path.home() / "Library" / "Logs"
    if platform.system() == "Darwin"
    else DATA_DIR / "logs"
)

LEGACY_CLEAN_VOICE = APP_DIR / "clean_voice"
LEGACY_VOICES_DIR = APP_DIR / "voices"
LEGACY_PROJECTS_DIR = APP_DIR / "projects"
LEGACY_REFERENCE = APP_DIR / "reference.wav"
LEGACY_REFERENCE_TEXT = APP_DIR / "reference.txt"
LEGACY_OUTPUT_DIR = APP_DIR / "output"
LEGACY_SETTINGS = APP_DIR / "settings.json"

CLEAN_VOICE = DATA_DIR / "clean_voice"
VOICES_DIR = DATA_DIR / "voices"
PROJECTS_DIR = DATA_DIR / "projects"
REFERENCE = DATA_DIR / "reference.wav"
REFERENCE_TEXT = DATA_DIR / "reference.txt"
OUTPUT_DIR = DATA_DIR / "output"
SETTINGS_PATH = DATA_DIR / "settings.json"


def _copy_file_once(source: Path, destination: Path) -> None:
    if not source.exists() or destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _copy_dir_once(source: Path, destination: Path) -> None:
    if not source.exists() or not source.is_dir():
        return
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        if child.name == ".gitkeep":
            continue
        target = destination / child.name
        if target.exists():
            continue
        if child.is_dir():
            shutil.copytree(child, target)
        else:
            shutil.copy2(child, target)


def migrate_legacy_user_data() -> None:
    """Copy old repo-root runtime data into the app-data folder once.

    The migration is intentionally non-destructive: legacy files are left in
    place so users can inspect or remove them at their own pace.
    """
    if DATA_DIR.resolve() == APP_DIR.resolve():
        return

    for source, destination in (
        (LEGACY_PROJECTS_DIR, PROJECTS_DIR),
        (LEGACY_VOICES_DIR, VOICES_DIR),
        (LEGACY_CLEAN_VOICE, CLEAN_VOICE),
        (LEGACY_OUTPUT_DIR, OUTPUT_DIR),
    ):
        _copy_dir_once(source, destination)

    for source, destination in (
        (LEGACY_SETTINGS, SETTINGS_PATH),
        (LEGACY_REFERENCE, REFERENCE),
        (LEGACY_REFERENCE_TEXT, REFERENCE_TEXT),
    ):
        _copy_file_once(source, destination)


migrate_legacy_user_data()
for directory in (OUTPUT_DIR, VOICES_DIR, PROJECTS_DIR, CLEAN_VOICE, LOG_DIR):
    directory.mkdir(parents=True, exist_ok=True)
