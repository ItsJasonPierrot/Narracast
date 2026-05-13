"""M4B audiobook export backend.

Handles chapter auditing, FFmetadata generation, and ffmpeg-based .m4b export.
Timestamps use milliseconds throughout (ffmpeg chapter timebase 1/1000).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


# ── Data model ─────────────────────────────────────────────────────────────


@dataclass
class ChapterExportInfo:
    """Audit result for a single chapter."""

    chapter_id: str
    title: str
    output_path: str
    duration_ms: int = 0
    ready: bool = False
    reason: str = ""  # empty string when ready


# ── Chapter audit ───────────────────────────────────────────────────────────


def audit_project_chapters(project: dict) -> list[ChapterExportInfo]:
    """Return one :class:`ChapterExportInfo` per chapter in *project*.

    A chapter is *ready* when:

    - Its ``status`` is ``"generated"``
    - Its ``output_path`` is non-empty
    - The file at ``output_path`` exists on disk

    Duration is loaded from a sidecar ``<stem>.json`` if present and the
    JSON contains ``"duration_ms"``.
    """
    results: list[ChapterExportInfo] = []

    for chapter in project.get("chapters", []):
        chapter_id = chapter.get("id", "")
        title = chapter.get("title", "")
        output_path = chapter.get("output_path", "")
        status = chapter.get("status", "")

        info = ChapterExportInfo(
            chapter_id=chapter_id,
            title=title,
            output_path=output_path,
        )

        if status != "generated":
            info.ready = False
            info.reason = f"Status is '{status}' (must be 'generated')"
            results.append(info)
            continue

        if not output_path:
            info.ready = False
            info.reason = "No output path set for this chapter"
            results.append(info)
            continue

        audio_file = Path(output_path)
        if not audio_file.exists():
            info.ready = False
            info.reason = f"Audio file not found on disk: {output_path}"
            results.append(info)
            continue

        # All checks passed — chapter is ready.
        info.ready = True
        info.reason = ""

        # Try to read duration from sidecar JSON.
        sidecar = audio_file.with_suffix(".json")
        if sidecar.exists():
            try:
                data = json.loads(sidecar.read_text(encoding="utf-8"))
                info.duration_ms = int(data.get("duration_ms", 0))
            except (json.JSONDecodeError, ValueError, OSError):
                pass

        results.append(info)

    return results


# ── FFmetadata builder ──────────────────────────────────────────────────────

_ESCAPE_CHARS = {"=", ";", "#", "\\", "\n"}


def _escape_ffmeta_value(value: str) -> str:
    """Escape special characters in an FFmetadata value field."""
    out: list[str] = []
    for ch in value:
        if ch in _ESCAPE_CHARS:
            out.append("\\")
        out.append(ch)
    return "".join(out)


def build_ffmetadata(project: dict, chapters: list[ChapterExportInfo]) -> str:
    """Build an FFmetadata string for *chapters* within *project*.

    The returned string can be written to a file and passed to ffmpeg via
    ``-i <file> -map_metadata 0``.

    Timestamps are in milliseconds (``TIMEBASE=1/1000``).
    """
    lines: list[str] = [";FFMETADATA1"]

    title = project.get("title", "")
    author = project.get("author", "")

    if title:
        lines.append(f"title={_escape_ffmeta_value(title)}")
    if author:
        lines.append(f"artist={_escape_ffmeta_value(author)}")

    cursor_ms = 0
    for chapter in chapters:
        start = cursor_ms
        end = cursor_ms + max(chapter.duration_ms, 0)
        cursor_ms = end

        lines.append("")
        lines.append("[CHAPTER]")
        lines.append("TIMEBASE=1/1000")
        lines.append(f"START={start}")
        lines.append(f"END={end}")
        lines.append(f"title={_escape_ffmeta_value(chapter.title)}")

    return "\n".join(lines)


# ── Main export function ────────────────────────────────────────────────────


def export_m4b(
    project: dict,
    output_path: str,
    *,
    skip_missing: bool = True,
    on_progress: Callable[[str], None] | None = None,
) -> str:
    """Export *project* as a single .m4b audiobook file.

    Parameters
    ----------
    project:
        Project dict containing ``title``, ``author``, ``chapters``.
    output_path:
        Destination path for the ``.m4b`` file.
    skip_missing:
        When *True* (default) chapters that are not ready are silently
        skipped.  When *False* a :exc:`ValueError` is raised if any
        chapter is not ready.
    on_progress:
        Optional callback invoked with status strings during export.

    Returns
    -------
    str
        Absolute path to the written ``.m4b`` file.

    Raises
    ------
    ValueError
        If no chapters are ready, or if *skip_missing* is *False* and
        any chapter is not ready.
    RuntimeError
        If ffmpeg is not on ``$PATH`` or the ffmpeg invocation fails.
    """
    audit = audit_project_chapters(project)

    not_ready = [a for a in audit if not a.ready]
    if not skip_missing and not_ready:
        reasons = "; ".join(f"{a.chapter_id}: {a.reason}" for a in not_ready)
        raise ValueError(f"Some chapters are not ready: {reasons}")

    ready = [a for a in audit if a.ready]
    if not ready:
        raise ValueError(
            "No chapters are ready to export. "
            "Generate audio for at least one chapter first."
        )

    output = Path(output_path).expanduser()
    if output.suffix.lower() != ".m4b":
        raise ValueError("M4B export path must end with .m4b")
    output.parent.mkdir(parents=True, exist_ok=True)

    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "ffmpeg not found on PATH. Install ffmpeg to export M4B files."
        )

    _notify(on_progress, f"Audited {len(ready)} chapter(s) — starting export…")

    with tempfile.TemporaryDirectory(prefix="narracast_m4b_") as tmp:
        tmp_path = Path(tmp)

        # 1. Write concat list.
        concat_file = tmp_path / "concat.txt"
        concat_lines = [
            f"file '{_escape_concat_path(chapter.output_path)}'" for chapter in ready
        ]
        concat_file.write_text("\n".join(concat_lines), encoding="utf-8")

        # 2. Write FFmetadata.
        meta_file = tmp_path / "ffmeta.txt"
        meta_content = build_ffmetadata(project, ready)
        meta_file.write_text(meta_content, encoding="utf-8")

        # 3. Concatenate audio files into a single AAC stream.
        merged_aac = tmp_path / "merged.aac"
        _notify(on_progress, "Concatenating audio…")
        _run_ffmpeg(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_file),
                "-vn", "-acodec", "aac", "-b:a", "128k",
                str(merged_aac),
            ]
        )

        # 4. Mux with chapter metadata into .m4b.
        _notify(on_progress, "Muxing chapter metadata…")
        _run_ffmpeg(
            [
                "ffmpeg", "-y",
                "-i", str(merged_aac),
                "-i", str(meta_file),
                "-map_metadata", "1",
                "-c", "copy",
                "-movflags", "+faststart",
                str(output),
            ]
        )

    _notify(on_progress, f"Export complete → {output}")
    return str(output.resolve())


# ── Helpers ─────────────────────────────────────────────────────────────────


def _notify(cb: Callable[[str], None] | None, msg: str) -> None:
    if cb is not None:
        cb(msg)


def _escape_concat_path(path: str) -> str:
    """Escape a path for ffmpeg concat-demuxer single-quoted file entries."""
    if "\n" in path or "\r" in path:
        raise ValueError("Audio paths cannot contain newline characters")
    return path.replace("\\", "\\\\").replace("'", "\\'")


def _run_ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit {result.returncode}):\n{result.stderr}"
        )
