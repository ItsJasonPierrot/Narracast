"""Persistent local user settings."""

import json
import re
from pathlib import Path
from typing import Any

from .paths import APP_DIR
from .presets import DEFAULT_PRESET, GENERATION_PRESETS


SETTINGS_PATH = APP_DIR / "settings.json"


DEFAULT_SETTINGS: dict[str, Any] = {
    "voice": "",
    "speed": 1.0,
    "preset": DEFAULT_PRESET,
    "title": "",
    "part": "",
    "geometry": "980x720",
    "paragraph_pause_ms": 500,
    "sentence_pause_ms": 0,
    "app_theme": "Dark",
    "current_page": "generate",
    "reader_theme": "Night",
    "reader_spacing": "Normal",
    "reader_font": "Georgia",
    "reader_size": "M",
    "reader_auto_pause_paragraphs": False,
    "reader_study_mode": False,
    # Audio polish
    "polish_bitrate": "192k",
    "polish_normalize": False,
    "polish_fade_in_ms": 0,
    "polish_fade_out_ms": 0,
    "polish_trim_silence": False,
}

_GEOMETRY_RE = re.compile(r"^\d{3,4}x\d{3,4}$")


def _clean_settings(raw: dict[str, Any]) -> dict[str, Any]:
    settings = dict(DEFAULT_SETTINGS)

    for key in ("voice", "title", "part"):
        value = raw.get(key)
        if isinstance(value, str):
            settings[key] = value

    try:
        speed = float(raw.get("speed", DEFAULT_SETTINGS["speed"]))
    except (TypeError, ValueError):
        speed = DEFAULT_SETTINGS["speed"]
    settings["speed"] = min(2.0, max(0.5, speed))

    preset = raw.get("preset")
    if isinstance(preset, str) and preset in GENERATION_PRESETS:
        settings["preset"] = preset

    geometry = raw.get("geometry")
    if isinstance(geometry, str) and _GEOMETRY_RE.match(geometry):
        settings["geometry"] = geometry

    try:
        paragraph_pause_ms = int(
            raw.get("paragraph_pause_ms", DEFAULT_SETTINGS["paragraph_pause_ms"])
        )
    except (TypeError, ValueError):
        paragraph_pause_ms = DEFAULT_SETTINGS["paragraph_pause_ms"]
    settings["paragraph_pause_ms"] = min(2000, max(0, paragraph_pause_ms))

    try:
        sentence_pause_ms = int(
            raw.get("sentence_pause_ms", DEFAULT_SETTINGS["sentence_pause_ms"])
        )
    except (TypeError, ValueError):
        sentence_pause_ms = DEFAULT_SETTINGS["sentence_pause_ms"]
    settings["sentence_pause_ms"] = min(1000, max(0, sentence_pause_ms))

    app_theme = raw.get("app_theme")
    if app_theme in ("Dark", "Light"):
        settings["app_theme"] = app_theme

    current_page = raw.get("current_page")
    if current_page in ("generate", "queue", "voice", "history", "read", "help"):
        settings["current_page"] = current_page

    reader_theme = raw.get("reader_theme")
    if reader_theme in ("Warm", "High Contrast", "Night"):
        settings["reader_theme"] = reader_theme

    reader_spacing = raw.get("reader_spacing")
    if reader_spacing in ("Compact", "Normal", "Relaxed", "Spacious"):
        settings["reader_spacing"] = reader_spacing

    reader_font = raw.get("reader_font")
    if reader_font in ("Georgia", "Inter", "Courier New", "Times New Roman"):
        settings["reader_font"] = reader_font

    reader_size = raw.get("reader_size")
    if reader_size in ("S", "M", "L", "XL"):
        settings["reader_size"] = reader_size

    settings["reader_auto_pause_paragraphs"] = bool(
        raw.get("reader_auto_pause_paragraphs", False)
    )
    settings["reader_study_mode"] = bool(raw.get("reader_study_mode", False))

    # Audio polish
    from .audio_polish import VALID_BITRATES
    polish_bitrate = raw.get("polish_bitrate")
    if isinstance(polish_bitrate, str) and polish_bitrate in VALID_BITRATES:
        settings["polish_bitrate"] = polish_bitrate

    settings["polish_normalize"] = bool(raw.get("polish_normalize", False))
    settings["polish_trim_silence"] = bool(raw.get("polish_trim_silence", False))

    for fade_key in ("polish_fade_in_ms", "polish_fade_out_ms"):
        try:
            val = int(raw.get(fade_key, 0))
        except (TypeError, ValueError):
            val = 0
        settings[fade_key] = min(10_000, max(0, val))

    return settings


def load_settings(path: Path = SETTINGS_PATH) -> dict[str, Any]:
    """Load settings, recovering gracefully from missing or invalid JSON."""
    if not path.exists():
        return dict(DEFAULT_SETTINGS)
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_SETTINGS)
    if not isinstance(loaded, dict):
        return dict(DEFAULT_SETTINGS)

    return _clean_settings(loaded)


def save_settings(settings: dict[str, Any], path: Path = SETTINGS_PATH) -> None:
    """Save simple settings atomically enough for a local desktop app."""
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = _clean_settings(settings)

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(clean, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
