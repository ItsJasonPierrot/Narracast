"""F5-TTS generation and audio assembly."""

import json
import tempfile
import threading
import time
from pathlib import Path

import soundfile as sf
from pydub import AudioSegment

from .audio_polish import AudioPolishSettings, apply_polish
from .metadata import write_generation_metadata
from .output_files import make_output_filename
from .paths import OUTPUT_DIR
from .presets import DEFAULT_PRESET, format_duration, get_generation_preset
from .text_splitter import build_highlight_units, split_into_timeline_items
from .voices import get_voice_files, prepare_reference


tts = None
_tts_lock = threading.Lock()
_active_device: str = "cpu"  # updated by set_tts(); readable by the UI


def best_device() -> str:
    """Return the best available compute device for this machine."""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def set_tts(model, device: str = "cpu") -> None:
    global tts, _active_device
    tts = model
    _active_device = device


def active_device() -> str:
    """Which device the loaded model is running on."""
    return _active_device


def _infer_waveform(chunk, reference_audio, speed, nfe_step=32):
    if tts is None:
        raise RuntimeError("TTS model is not loaded yet.")
    reference = prepare_reference(reference_audio)
    with _tts_lock:
        wav, sr, _ = tts.infer(
            ref_file=reference_audio,
            ref_text=reference.ref_text,
            gen_text=chunk,
            speed=speed,
            nfe_step=nfe_step,
        )
    return wav, sr, reference.cache_hit


def _waveform_to_audio_segment(wav, sr) -> AudioSegment:
    """Convert model waveform output directly into an AudioSegment."""
    import numpy as np

    arr = np.asarray(wav)
    if arr.size == 0:
        return AudioSegment.empty()

    if arr.ndim == 1:
        channels = 1
    elif arr.ndim == 2:
        if arr.shape[0] <= 8 and arr.shape[1] > arr.shape[0]:
            arr = arr.T
        channels = arr.shape[1]
    else:
        arr = arr.reshape(-1)
        channels = 1

    if arr.dtype.kind == "f":
        arr = np.clip(arr, -1.0, 1.0)
        arr = (arr * 32767).astype(np.int16)
    elif arr.dtype != np.int16:
        arr = arr.astype(np.int16)

    return AudioSegment(
        arr.tobytes(),
        frame_rate=int(sr),
        sample_width=2,
        channels=channels,
    )


def infer_chunk_segment(chunk, reference_audio, speed, nfe_step=32) -> tuple[AudioSegment, dict[str, float]]:
    """Run inference and return an AudioSegment without a temp WAV round trip."""
    infer_start = time.perf_counter()
    wav, sr, cache_hit = _infer_waveform(chunk, reference_audio, speed, nfe_step)
    inference_s = time.perf_counter() - infer_start

    convert_start = time.perf_counter()
    segment = _waveform_to_audio_segment(wav, sr)
    convert_s = time.perf_counter() - convert_start

    return segment, {
        "inference_s": inference_s,
        "waveform_convert_s": convert_s,
        "temp_wav_write_s": 0.0,
        "wav_load_s": 0.0,
        "reference_cache_hits": 1.0 if cache_hit else 0.0,
        "reference_cache_misses": 0.0 if cache_hit else 1.0,
    }


def infer_chunk(chunk, reference_audio, speed, nfe_step=32):
    """Run inference and write a temporary WAV for direct playback previews."""
    wav, sr, _cache_hit = _infer_waveform(chunk, reference_audio, speed, nfe_step)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    sf.write(tmp.name, wav, sr)
    return tmp.name


def _write_id3_tags(audio_path: Path, *, title: str, part: str, voice: str) -> None:
    """Write ID3 tags to the generated MP3 so phones and players show clean metadata."""
    try:
        from mutagen.easyid3 import EasyID3
        from mutagen.id3 import ID3NoHeaderError
        try:
            tags = EasyID3(str(audio_path))
        except ID3NoHeaderError:
            tags = EasyID3()
            tags.filename = str(audio_path)
        if title:
            tags["title"] = f"{title}{' — ' + part if part else ''}"
            tags["album"] = title
        if part:
            tags["tracknumber"] = part
        tags["artist"] = voice or "Narracast"
        tags.save(str(audio_path))
    except Exception:
        pass  # Tags are a nicety — never let them break generation


def _export_generation_outputs(
    combined: AudioSegment,
    *,
    output_path: Path,
    bitrate: str,
    text: str,
    timeline: list[dict],
    highlight_units: list[dict],
    title: str,
    part: str,
    voice_name: str,
    speed: float,
    preset_name: str,
    preset: dict,
    paragraph_pause_ms: int,
    sentence_pause_ms: int,
    audio_polish: AudioPolishSettings | None,
    timings: dict[str, float],
    project_id: str = "",
    chapter_id: str = "",
) -> Path:
    """Write final MP3, ID3 tags, and metadata sidecar."""
    export_start = time.perf_counter()
    exported = combined.export(str(output_path), format="mp3", bitrate=bitrate)
    if hasattr(exported, "close"):
        exported.close()
    timings["mp3_export_s"] = time.perf_counter() - export_start

    id3_start = time.perf_counter()
    _write_id3_tags(output_path, title=title, part=part, voice=voice_name)
    timings["id3_s"] = time.perf_counter() - id3_start

    metadata_start = time.perf_counter()
    metadata_path = write_generation_metadata(
        output_path,
        source_text=text,
        timeline=timeline,
        highlight_units=highlight_units,
        title=title,
        part=part,
        voice=voice_name,
        speed=speed,
        preset=preset_name,
        preset_settings=preset,
        duration_ms=len(combined),
        paragraph_pause_ms=paragraph_pause_ms,
        sentence_pause_ms=sentence_pause_ms,
        generation_timings={k: round(v, 4) for k, v in timings.items() if not k.startswith("_")},
        audio_polish=audio_polish,
        project_id=project_id,
        chapter_id=chapter_id,
    )
    timings["metadata_write_s"] = time.perf_counter() - metadata_start
    timings["finalize_s"] = timings["mp3_export_s"] + timings["id3_s"] + timings["metadata_write_s"]
    timings["total_s"] = time.perf_counter() - timings.get("_total_start", time.perf_counter())
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        payload["generation_timings"] = {
            k: round(v, 4) for k, v in timings.items() if not k.startswith("_")
        }
        metadata_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass
    return metadata_path


def generate_core(
    text, voice_name, speed, title, part, on_progress=None,
    preset_name=DEFAULT_PRESET, paragraph_pause_ms: int = 500,
    sentence_pause_ms: int = 0,
    audio_polish: AudioPolishSettings | None = None,
    project_id: str = "",
    chapter_id: str = "",
):
    """Core generation — progress-callback agnostic."""
    total_start = time.perf_counter()
    timings: dict[str, float] = {}
    timings["_total_start"] = total_start

    split_start = time.perf_counter()
    preset = get_generation_preset(preset_name)
    voice_map = get_voice_files()
    reference_audio = voice_map[voice_name]
    items = split_into_timeline_items(
        text, max_chars=preset["chunk_size"],
        paragraph_pause_ms=paragraph_pause_ms,
        sentence_pause_ms=sentence_pause_ms,
    )
    timings["split_s"] = time.perf_counter() - split_start

    chunks = [x for x in items if x["type"] == "speech"]
    total = len(chunks)
    if total == 0:
        raise ValueError("No speakable text found.")

    combined = AudioSegment.empty()
    chunk_idx = 0
    chunk_times: list[float] = []
    timeline: list[dict] = []
    t_start = time.time()
    timings["inference_s"] = 0.0
    timings["waveform_convert_s"] = 0.0
    timings["temp_wav_write_s"] = 0.0
    timings["wav_load_s"] = 0.0
    timings["reference_cache_hits"] = 0.0
    timings["reference_cache_misses"] = 0.0
    timings["assembly_s"] = 0.0

    for item in items:
        audio_start_ms = len(combined)
        if item["type"] in ("pause", "sentence_pause"):
            assembly_start = time.perf_counter()
            silence = AudioSegment.silent(duration=item["duration_ms"])
            combined += silence
            timings["assembly_s"] += time.perf_counter() - assembly_start
            timeline.append(
                {
                    **item,
                    "audio_start_ms": audio_start_ms,
                    "audio_end_ms": len(combined),
                }
            )
        else:
            if on_progress:
                elapsed = time.time() - t_start
                recent_times = chunk_times[-5:]
                avg = (sum(recent_times) / len(recent_times)) if recent_times else None
                remaining = total - chunk_idx
                eta_str = (
                    f"~{format_duration(avg * remaining)} left"
                    if avg
                    else "estimating…"
                )
                avg_str = f"{avg:.1f}s/chunk" if avg else "avg estimating…"
                on_progress(
                    chunk_idx / total,
                    desc=(
                        f"{preset_name} · Chunk {chunk_idx + 1} / {total}"
                        f"  ·  {format_duration(elapsed)} elapsed"
                        f"  ·  {avg_str}  ·  {eta_str}"
                    ),
                )
            t_chunk = time.time()
            segment, chunk_timing = infer_chunk_segment(
                item["text"],
                reference_audio,
                speed,
                preset["nfe_step"],
            )
            inference_elapsed = time.time() - t_chunk
            chunk_times.append(inference_elapsed)
            for key, value in chunk_timing.items():
                timings[key] = timings.get(key, 0.0) + value
            assembly_start = time.perf_counter()
            combined += segment
            timings["assembly_s"] += time.perf_counter() - assembly_start
            timeline.append(
                {
                    **item,
                    "chunk_index": chunk_idx,
                    "audio_start_ms": audio_start_ms,
                    "audio_end_ms": len(combined),
                    "duration_ms": len(segment),
                }
            )
            chunk_idx += 1

    # ── Audio polish ──────────────────────────────────────────────────────
    polish_start = time.perf_counter()
    if audio_polish and not audio_polish.is_default():
        combined = apply_polish(combined, audio_polish)
    timings["polish_s"] = round(time.perf_counter() - polish_start, 4)

    bitrate = audio_polish.bitrate if audio_polish else "192k"

    if on_progress:
        if chunk_times:
            avg = sum(chunk_times) / len(chunk_times)
            on_progress(0.95, desc=f"Saving MP3… avg {avg:.1f}s/chunk")
        else:
            on_progress(0.95, desc="Saving MP3…")
    filename = make_output_filename(text, title, part)
    output_path = OUTPUT_DIR / filename
    timings["total_before_metadata_s"] = time.perf_counter() - total_start
    metadata_path = _export_generation_outputs(
        combined,
        output_path=output_path,
        bitrate=bitrate,
        text=text,
        timeline=timeline,
        highlight_units=build_highlight_units(timeline, text),
        title=title,
        part=part,
        voice_name=voice_name,
        speed=speed,
        preset_name=preset_name,
        preset=preset,
        paragraph_pause_ms=paragraph_pause_ms,
        sentence_pause_ms=sentence_pause_ms,
        audio_polish=audio_polish,
        timings=timings,
        project_id=project_id,
        chapter_id=chapter_id,
    )

    mins = int(len(combined) / 60000)
    secs = int((len(combined) % 60000) / 1000)
    return (
        str(output_path),
        (
            f"Done! {total} parts → {mins}m {secs}s\n"
            f"Saved as: {filename}\n"
            f"Metadata: {Path(metadata_path).name}"
        ),
    )
