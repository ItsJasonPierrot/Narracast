"""TTS generation benchmark — measures speed per preset."""

import tempfile
import time
from pathlib import Path
from typing import Callable, Optional

from .audio_generation import generate_core
from .presets import GENERATION_PRESETS

# ~600-character fixed sample — long enough for 1–2 chunks across all presets,
# but short enough to finish quickly even on CPU.
BENCHMARK_TEXT = (
    "The art of reading slowly is not laziness. It is the deliberate act of letting "
    "words settle before moving on, of allowing meaning to build rather than blur. "
    "In an age designed to consume attention, choosing to read carefully is itself a "
    "form of resistance — a quiet insistence that some things are worth the time they "
    "take. The mind that reads in this way is not slower. It is more present. It notices "
    "what the hurried reader skips. It returns to a sentence not because it failed, but "
    "because something there was worth revisiting. This is how good books become companions "
    "rather than events."
)


def run_benchmark(
    voice_name: str,
    voice_path: str,
    preset_name: str,
    on_progress: Optional[Callable] = None,
) -> dict:
    """Run a single-preset benchmark and return a result dict.

    Parameters
    ----------
    voice_name:
        Name of the reference voice (used to look up the voice file).
    voice_path:
        Absolute path to the reference WAV file.
    preset_name:
        One of the keys in GENERATION_PRESETS.
    on_progress:
        Optional ``(fraction, desc)`` callback forwarded to generate_core.

    Returns
    -------
    dict with keys:
        preset, chunks, gen_time_s, audio_duration_s, rtf, avg_s_per_chunk,
        output_path (temp file, caller may delete it).
    """
    from . import audio_generation as _ag  # local import to allow monkey-patching in tests

    original_output_dir = _ag.OUTPUT_DIR
    original_get_voice_files = _ag.get_voice_files

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _ag.OUTPUT_DIR = tmp_path
        _ag.get_voice_files = lambda: {voice_name: voice_path}

        chunk_count = 0

        def _counting_progress(frac, desc=""):
            nonlocal chunk_count
            # Count unique "Chunk N / total" calls to determine number of chunks
            if "Chunk" in desc:
                try:
                    part = desc.split("Chunk")[1].strip().split("/")[0].strip()
                    chunk_count = max(chunk_count, int(part))
                except (ValueError, IndexError):
                    pass
            if on_progress:
                on_progress(frac, desc)

        try:
            t0 = time.time()
            output_path, _ = generate_core(
                BENCHMARK_TEXT,
                voice_name,
                speed=1.0,
                title="__benchmark__",
                part="",
                on_progress=_counting_progress,
                preset_name=preset_name,
            )
            gen_time = time.time() - t0
        finally:
            _ag.OUTPUT_DIR = original_output_dir
            _ag.get_voice_files = original_get_voice_files

        # Read audio duration from the metadata sidecar
        import json
        meta_path = Path(output_path).with_suffix(".json")
        audio_duration_ms = json.loads(meta_path.read_text(encoding="utf-8"))["duration_ms"]
        audio_duration_s = audio_duration_ms / 1000

        rtf = gen_time / audio_duration_s if audio_duration_s > 0 else 0
        avg_s = gen_time / chunk_count if chunk_count > 0 else gen_time

        return {
            "preset": preset_name,
            "chunks": chunk_count,
            "gen_time_s": gen_time,
            "audio_duration_s": audio_duration_s,
            "rtf": rtf,
            "avg_s_per_chunk": avg_s,
        }


def run_all_presets(
    voice_name: str,
    voice_path: str,
    on_preset_start: Optional[Callable[[str], None]] = None,
    on_progress: Optional[Callable] = None,
    on_preset_done: Optional[Callable[[dict], None]] = None,
) -> list[dict]:
    """Run the benchmark for every preset in sequence and return all results."""
    results = []
    for preset_name in GENERATION_PRESETS:
        if on_preset_start:
            on_preset_start(preset_name)
        result = run_benchmark(voice_name, voice_path, preset_name, on_progress)
        results.append(result)
        if on_preset_done:
            on_preset_done(result)
    return results
