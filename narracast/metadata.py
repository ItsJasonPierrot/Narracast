"""Generation metadata sidecar files."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2


def metadata_path_for_audio(audio_path: str | Path) -> Path:
    return Path(audio_path).with_suffix(".json")


def write_generation_metadata(
    audio_path: str | Path,
    *,
    source_text: str,
    timeline: list[dict[str, Any]],
    highlight_units: list[dict[str, Any]] | None = None,
    title: str,
    part: str,
    voice: str,
    speed: float,
    preset: str,
    preset_settings: dict[str, Any],
    duration_ms: int,
    paragraph_pause_ms: int = 500,
    sentence_pause_ms: int = 0,
    generation_timings: dict[str, float] | None = None,
    audio_polish: Any = None,
) -> Path:
    audio_path = Path(audio_path)
    metadata_path = metadata_path_for_audio(audio_path)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "output_filename": audio_path.name,
        "output_path": str(audio_path),
        "duration_ms": duration_ms,
        "title": title,
        "part": part,
        "voice": voice,
        "speed": speed,
        "preset": preset,
        "paragraph_pause_ms": paragraph_pause_ms,
        "sentence_pause_ms": sentence_pause_ms,
        "preset_settings": dict(preset_settings),
        "source_text": source_text,
        "timeline": timeline,
        "highlight_units": list(highlight_units or []),
    }
    if generation_timings:
        payload["generation_timings"] = dict(generation_timings)
    if audio_polish is not None:
        # Accept either an AudioPolishSettings instance or a plain dict
        payload["audio_polish"] = (
            audio_polish.to_dict()
            if hasattr(audio_polish, "to_dict")
            else dict(audio_polish)
        )
    metadata_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return metadata_path
