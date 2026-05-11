"""Text splitting helpers for generation."""

import re
from typing import Any


def chunk_text(text, max_chars=750):
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks, current = [], ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_chars:
            current = (current + " " + sentence).strip()
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def split_into_items(text, max_chars=750):
    """Split text into chunks, inserting None as a paragraph-break marker."""
    paragraphs = re.split(r"\n\n+", text)
    items = []
    for i, para in enumerate(paragraphs):
        para = para.strip()
        if not para:
            continue
        for chunk in chunk_text(para, max_chars):
            items.append(chunk)
        if i < len(paragraphs) - 1:
            items.append(None)
    return items


def split_into_timeline_items(
    text: str,
    max_chars: int = 750,
    paragraph_pause_ms: int = 500,
    sentence_pause_ms: int = 0,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    paragraph_matches = list(re.finditer(r"\S(?:.*?)(?=\n\n+|\Z)", text, re.S))

    for idx, match in enumerate(paragraph_matches):
        para_text = match.group(0)
        para_start = match.start()
        sentence_matches = list(
            re.finditer(r"\S(?:.*?)(?:(?<=[.!?])(?=\s+)|\Z)", para_text, re.S)
        )
        normalized_sentences: list[tuple[str, int, int]] = []

        for sentence in sentence_matches:
            sentence_text = re.sub(r"\s+", " ", sentence.group(0).strip())
            if not sentence_text:
                continue
            normalized_sentences.append(
                (sentence_text, para_start + sentence.start(), para_start + sentence.end())
            )

        if sentence_pause_ms > 0:
            for sentence_idx, (sentence_text, start, end) in enumerate(normalized_sentences):
                items.append(
                    {
                        "type": "speech",
                        "text": sentence_text,
                        "text_start": start,
                        "text_end": end,
                    }
                )
                if sentence_idx < len(normalized_sentences) - 1:
                    items.append(
                        {
                            "type": "sentence_pause",
                            "text": "",
                            "text_start": end,
                            "text_end": normalized_sentences[sentence_idx + 1][1],
                            "duration_ms": sentence_pause_ms,
                        }
                    )
        else:
            current_text = ""
            current_start: int | None = None
            current_end: int | None = None

            for sentence_text, start, end in normalized_sentences:
                next_text = (
                    f"{current_text} {sentence_text}".strip()
                    if current_text
                    else sentence_text
                )
                if current_text and len(next_text) > max_chars:
                    items.append(
                        {
                            "type": "speech",
                            "text": current_text,
                            "text_start": current_start,
                            "text_end": current_end,
                        }
                    )
                    current_text = sentence_text
                    current_start = start
                    current_end = end
                else:
                    current_text = next_text
                    if current_start is None:
                        current_start = start
                    current_end = end

            if current_text:
                items.append(
                    {
                        "type": "speech",
                        "text": current_text,
                        "text_start": current_start,
                        "text_end": current_end,
                    }
                )

        if idx < len(paragraph_matches) - 1:
            items.append(
                {
                    "type": "pause",
                    "text": "",
                    "text_start": match.end(),
                    "text_end": paragraph_matches[idx + 1].start(),
                    "duration_ms": paragraph_pause_ms,
                }
            )

    return items


def build_highlight_units(timeline: list[dict[str, Any]], source_text: str) -> list[dict[str, Any]]:
    """Create sentence-level highlight units inside generated speech chunks.

    Generation chunks stay large for TTS speed/quality. Highlight units are
    smaller display ranges with estimated timings inside each generated chunk.
    """
    units: list[dict[str, Any]] = []
    unit_index = 0

    for chunk in timeline:
        if chunk.get("type") != "speech":
            continue

        try:
            chunk_start = int(chunk["text_start"])
            chunk_end = int(chunk["text_end"])
            audio_start = int(chunk["audio_start_ms"])
            audio_end = int(chunk["audio_end_ms"])
        except (KeyError, TypeError, ValueError):
            continue

        if not (0 <= chunk_start < chunk_end <= len(source_text)):
            continue

        source_span = source_text[chunk_start:chunk_end]
        sentence_matches = [
            match for match in re.finditer(r"\S(?:.*?)(?:(?<=[.!?])(?=\s+)|\Z)", source_span, re.S)
            if match.group(0).strip()
        ]
        if not sentence_matches:
            sentence_matches = [re.match(r"(?s).*", source_span)]

        normalized_sentences = [
            re.sub(r"\s+", " ", match.group(0).strip()) for match in sentence_matches if match
        ]
        weights = [max(1, len(sentence)) for sentence in normalized_sentences]
        total_weight = sum(weights) or 1
        chunk_duration = max(0, audio_end - audio_start)

        current_audio_start = audio_start
        for idx, match in enumerate(sentence_matches):
            if not match:
                continue
            text = re.sub(r"\s+", " ", match.group(0).strip())
            if not text:
                continue
            text_start = chunk_start + match.start()
            text_end = chunk_start + match.end()
            if idx == len(sentence_matches) - 1:
                current_audio_end = audio_end
            else:
                current_audio_end = audio_start + round(
                    chunk_duration * (sum(weights[: idx + 1]) / total_weight)
                )

            units.append(
                {
                    "type": "sentence",
                    "unit_index": unit_index,
                    "chunk_index": chunk.get("chunk_index"),
                    "text": text,
                    "text_start": text_start,
                    "text_end": text_end,
                    "audio_start_ms": current_audio_start,
                    "audio_end_ms": current_audio_end,
                    "timing_estimate": "proportional_by_characters",
                }
            )
            unit_index += 1
            current_audio_start = current_audio_end

    return units
