"""Audio post-processing polish controls.

Applied to the fully assembled AudioSegment after all chunks are joined,
before MP3 export. Operations run in a fixed order:

    trim silence → normalize → fade in → fade out

This ordering means normalization targets the intended content (not silence),
and fades frame the already-normalised audio cleanly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from pydub import AudioSegment
from pydub.silence import detect_leading_silence


VALID_BITRATES: tuple[str, ...] = ("128k", "192k", "256k", "320k")

_DEFAULT_BITRATE = "192k"
_DEFAULT_SILENCE_THRESHOLD_DB: float = -50.0
_DEFAULT_SILENCE_MIN_LEN_MS: int = 200
_MAX_FADE_MS: int = 10_000


@dataclass
class AudioPolishSettings:
    """Controls applied to the assembled audio before MP3 export."""

    bitrate: str = _DEFAULT_BITRATE
    normalize: bool = False
    fade_in_ms: int = 0
    fade_out_ms: int = 0
    trim_silence: bool = False
    silence_threshold_db: float = _DEFAULT_SILENCE_THRESHOLD_DB
    silence_min_len_ms: int = _DEFAULT_SILENCE_MIN_LEN_MS

    def __post_init__(self) -> None:
        if self.bitrate not in VALID_BITRATES:
            self.bitrate = _DEFAULT_BITRATE
        self.fade_in_ms = max(0, min(_MAX_FADE_MS, int(self.fade_in_ms)))
        self.fade_out_ms = max(0, min(_MAX_FADE_MS, int(self.fade_out_ms)))
        self.silence_threshold_db = float(self.silence_threshold_db)
        self.silence_min_len_ms = max(0, int(self.silence_min_len_ms))

    # ── Serialization ─────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AudioPolishSettings":
        """Create from a dict, ignoring unknown keys and using defaults for missing ones."""
        return cls(
            bitrate=str(d.get("bitrate", _DEFAULT_BITRATE)),
            normalize=bool(d.get("normalize", False)),
            fade_in_ms=int(d.get("fade_in_ms", 0)),
            fade_out_ms=int(d.get("fade_out_ms", 0)),
            trim_silence=bool(d.get("trim_silence", False)),
            silence_threshold_db=float(d.get("silence_threshold_db", _DEFAULT_SILENCE_THRESHOLD_DB)),
            silence_min_len_ms=int(d.get("silence_min_len_ms", _DEFAULT_SILENCE_MIN_LEN_MS)),
        )

    def is_default(self) -> bool:
        """True when no post-processing is active (only bitrate may differ)."""
        return (
            not self.normalize
            and self.fade_in_ms == 0
            and self.fade_out_ms == 0
            and not self.trim_silence
        )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _trim_surrounding_silence(
    segment: AudioSegment,
    silence_threshold_db: float = _DEFAULT_SILENCE_THRESHOLD_DB,
    chunk_size_ms: int = 10,
) -> AudioSegment:
    """Strip leading and trailing silence from a segment.

    Returns the original segment unchanged if it is entirely silent or empty,
    to avoid producing a zero-length segment.
    """
    if len(segment) == 0:
        return segment

    start_trim = detect_leading_silence(
        segment,
        silence_threshold=silence_threshold_db,
        chunk_size=chunk_size_ms,
    )
    end_trim = detect_leading_silence(
        segment.reverse(),
        silence_threshold=silence_threshold_db,
        chunk_size=chunk_size_ms,
    )

    trimmed_end = len(segment) - end_trim
    if start_trim >= trimmed_end:
        # Entirely silent — return as-is rather than an empty segment
        return segment

    return segment[start_trim:trimmed_end]


# ── Public API ────────────────────────────────────────────────────────────────

def apply_polish(
    segment: AudioSegment,
    settings: AudioPolishSettings,
) -> AudioSegment:
    """Apply audio post-processing described by *settings* to *segment*.

    Operations run in this fixed order:
    1. Trim surrounding silence
    2. Normalize peak level
    3. Fade in
    4. Fade out

    Returns the original segment unchanged if it is empty or all defaults.
    """
    if len(segment) == 0:
        return segment

    if settings.trim_silence:
        segment = _trim_surrounding_silence(
            segment,
            silence_threshold_db=settings.silence_threshold_db,
        )

    if settings.normalize:
        segment = segment.normalize()

    if settings.fade_in_ms > 0:
        # Never fade longer than the segment itself
        segment = segment.fade_in(min(settings.fade_in_ms, len(segment)))

    if settings.fade_out_ms > 0:
        segment = segment.fade_out(min(settings.fade_out_ms, len(segment)))

    return segment
