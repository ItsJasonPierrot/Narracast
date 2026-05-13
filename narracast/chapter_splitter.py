"""Detect chapter boundaries in long pasted/imported text."""

from __future__ import annotations

import re
from dataclasses import dataclass


_CHAPTER_RE = re.compile(
    r"^\s*(?:#{1,3}\s+)?("
    r"(?:chapter|part|section)\s+[\divxlcdm]+"
    r"|[1-3]?\s?[A-Z][A-Za-z]+\s+\d{1,3}"
    r")\b[^\n]*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ChapterDraft:
    title: str
    text: str


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 100:
        return False
    if re.match(r"^\s*#{1,3}\s+\S+", line):
        return True
    return bool(_CHAPTER_RE.match(stripped))


def _heading_title(line: str) -> str:
    return re.sub(r"^\s*#{1,3}\s+", "", line.strip()).strip()


def split_chapters(text: str, custom_marker: str = "") -> list[ChapterDraft]:
    """Split text into chapter drafts using a custom marker or common headings."""
    source = text.strip()
    if not source:
        return []

    marker = custom_marker.strip()
    if marker:
        return _split_by_marker(source, marker)

    chapters: list[ChapterDraft] = []
    current_title = ""
    current_lines: list[str] = []

    for line in source.splitlines():
        if _is_heading(line):
            if current_title or any(part.strip() for part in current_lines):
                chapters.append(
                    ChapterDraft(
                        title=current_title or f"Part {len(chapters) + 1}",
                        text="\n".join(current_lines).strip(),
                    )
                )
            current_title = _heading_title(line)
            current_lines = []
            continue
        current_lines.append(line)

    if current_title:
        chapters.append(
            ChapterDraft(
                title=current_title,
                text="\n".join(current_lines).strip(),
            )
        )

    return [chapter for chapter in chapters if chapter.text.strip()]


def _split_by_marker(text: str, marker: str) -> list[ChapterDraft]:
    parts = [part.strip() for part in text.split(marker)]
    chapters: list[ChapterDraft] = []
    for part in parts:
        if not part:
            continue
        lines = part.splitlines()
        first = lines[0].strip() if lines else ""
        title = first if first and len(first) <= 100 else f"Part {len(chapters) + 1}"
        body = "\n".join(lines[1:]).strip() if first == title else part
        chapters.append(ChapterDraft(title=title, text=body or part))
    return chapters
