"""Analyze generation timing metadata from completed Narracast sidecars."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import OUTPUT_DIR


TIMING_LABELS: dict[str, str] = {
    "split_s": "Text split",
    "inference_s": "Model inference",
    "waveform_convert_s": "Waveform conversion",
    "temp_wav_write_s": "Temp WAV write",
    "wav_load_s": "WAV load",
    "assembly_s": "Audio assembly",
    "polish_s": "Audio polish",
    "mp3_export_s": "MP3 export",
    "id3_s": "ID3 tags",
    "metadata_write_s": "Metadata write",
    "finalize_s": "Finalization",
}

FINALIZE_KEYS = ("mp3_export_s", "id3_s", "metadata_write_s")


@dataclass(frozen=True)
class TimingReport:
    sidecar_count: int
    file_count: int
    totals: dict[str, float]
    total_time_s: float
    finalize_time_s: float
    finalize_share: float
    recommendation: str

    @property
    def has_data(self) -> bool:
        return self.file_count > 0 and self.total_time_s > 0


def _load_timings(path: Path) -> dict[str, float]:
    try:
        payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    timings = payload.get("generation_timings")
    if not isinstance(timings, dict):
        return {}

    clean: dict[str, float] = {}
    for key, value in timings.items():
        try:
            clean[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return clean


def analyze_generation_timings(output_dir: Path = OUTPUT_DIR, limit: int = 20) -> TimingReport:
    """Summarize recent sidecar generation timings."""
    sidecars = sorted(
        output_dir.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[: max(1, limit)]

    totals: dict[str, float] = {}
    file_count = 0
    for sidecar in sidecars:
        timings = _load_timings(sidecar)
        if not timings:
            continue
        file_count += 1
        for key, value in timings.items():
            totals[key] = totals.get(key, 0.0) + value

    total_time_s = totals.get("total_s") or sum(
        totals.get(k, 0.0)
        for k in (
            "split_s",
            "inference_s",
            "waveform_convert_s",
            "wav_load_s",
            "assembly_s",
            "polish_s",
            "mp3_export_s",
            "id3_s",
            "metadata_write_s",
        )
    )
    finalize_time_s = totals.get("finalize_s") or sum(totals.get(k, 0.0) for k in FINALIZE_KEYS)
    finalize_share = finalize_time_s / total_time_s if total_time_s > 0 else 0.0

    if file_count == 0 and sidecars:
        recommendation = (
            f"Found {len(sidecars)} sidecar file(s), but none include generation_timings. "
            "Generate a new MP3 with the current version, then run this again."
        )
    elif file_count == 0:
        recommendation = "No generation timing data found yet. Generate an MP3, then run this again."
    elif finalize_share >= 0.20 and finalize_time_s >= 10:
        recommendation = (
            "Finalization is a meaningful share of total time. Async export/tag/metadata "
            "is worth prototyping."
        )
    elif totals.get("inference_s", 0.0) / total_time_s >= 0.70:
        recommendation = (
            "Model inference dominates. Async export would not change total generation much; "
            "focus on presets, reference caching, or model/runtime speed."
        )
    else:
        recommendation = (
            "Finalization is not dominant yet. Keep measuring before adding async complexity."
        )

    return TimingReport(
        sidecar_count=len(sidecars),
        file_count=file_count,
        totals={k: round(v, 4) for k, v in sorted(totals.items())},
        total_time_s=round(total_time_s, 4),
        finalize_time_s=round(finalize_time_s, 4),
        finalize_share=round(finalize_share, 4),
        recommendation=recommendation,
    )


def format_timing_rows(report: TimingReport) -> list[tuple[str, str, str]]:
    """Return display rows: label, seconds, share."""
    if not report.has_data:
        return []
    rows = []
    for key, label in TIMING_LABELS.items():
        seconds = report.totals.get(key, 0.0)
        if seconds <= 0:
            continue
        share = seconds / report.total_time_s if report.total_time_s else 0.0
        rows.append((label, f"{seconds:.2f}s", f"{share * 100:.1f}%"))
    return rows
