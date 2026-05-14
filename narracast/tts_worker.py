"""F5-TTS worker subprocess.

Launched via ``python -m narracast.tts_worker`` (or via the ``narracast``
package entry point).  Reads JSON-line commands from stdin, writes JSON-line
responses to stdout.  Stderr is left for library noise and is drained (and
discarded) by the GUI-side :class:`~narracast.tts_process.TTSProcess`.

Protocol
--------
**Commands** (GUI → worker, one JSON object per line on stdin):

``generate``
    Full generation pipeline.  Parameters mirror :func:`generate_core`.

``preview``
    Short single-chunk inference returning a WAV temp file path.  Used by the
    voice-reference page to audition a saved voice.

``benchmark_preset``
    Runs :data:`~narracast.benchmark.BENCHMARK_TEXT` through one preset inside
    the worker and returns a timing result dict.  Output is written to a
    temporary directory and cleaned up automatically.

``cancel``
    Set the cancellation flag.  The running generate job will abort at the next
    chunk boundary and emit a ``cancelled`` response.

``ping``
    Health check.  Worker responds immediately with ``pong``.

``shutdown``
    Exit cleanly after the current job (if any) finishes.

**Responses** (worker → GUI, one JSON object per line on stdout):

``ready``     ``{"type": "ready", "device": "mps"}``
``load_error``  ``{"type": "load_error", "message": "..."}``
``progress``  ``{"type": "progress", "job_id": "...", "frac": 0.5, "desc": "..."}``
``chunk``     ``{"type": "chunk", "job_id": "...", "chunk_idx": 0,
              "frame_rate": 24000, "channels": 1, "sample_width": 2,
              "pcm_b64": "<base64>"}``
``done``      ``{"type": "done", "job_id": "...", "output_path": "...", "summary": "..."}``
``cancelled`` ``{"type": "cancelled", "job_id": "..."}``
``error``     ``{"type": "error", "job_id": "...", "message": "..."}``
``preview_done`` ``{"type": "preview_done", "job_id": "...", "wav_path": "..."}``
``benchmark_preset_done`` ``{"type": "benchmark_preset_done", "job_id": "...", "result": {...}}``
``pong``      ``{"type": "pong"}``
"""

from __future__ import annotations

import base64
import json
import os
import queue
import sys
import tempfile
import threading
import time
from pathlib import Path

# Silence tokenizer / accelerate noise before heavy imports
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def _emit(obj: dict) -> None:
    """Write one JSON response line to stdout (binary channel)."""
    line = json.dumps(obj, ensure_ascii=False) + "\n"
    sys.stdout.buffer.write(line.encode("utf-8"))
    sys.stdout.buffer.flush()


class Worker:
    """Single-threaded TTS worker.  Owns the F5-TTS model object."""

    def __init__(self) -> None:
        self._cancel_event = threading.Event()
        self._cmd_queue: queue.Queue[dict] = queue.Queue()
        self._shutdown = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Main entry point.  Blocks until a ``shutdown`` command is received."""
        # Start stdin reader in background so cancel/shutdown can interrupt
        reader = threading.Thread(target=self._read_stdin, daemon=True, name="worker-stdin")
        reader.start()

        # Load model before accepting generation jobs
        try:
            device = self._load_model()
            _emit({"type": "ready", "device": device})
        except Exception as exc:  # noqa: BLE001
            _emit({"type": "load_error", "message": str(exc)})
            return

        # Command loop
        while not self._shutdown:
            try:
                cmd = self._cmd_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            action = cmd.get("cmd")
            if action == "shutdown":
                self._shutdown = True
                break
            elif action == "ping":
                _emit({"type": "pong"})
            elif action == "generate":
                self._run_generate(cmd)
            elif action == "preview":
                self._run_preview(cmd)
            elif action == "benchmark_preset":
                self._run_benchmark_preset(cmd)

    # ── Model loading ─────────────────────────────────────────────────────────

    def _load_model(self) -> str:
        """Import and load F5-TTS.  Returns the compute device string."""
        from narracast.audio_generation import best_device, set_tts  # noqa: PLC0415
        from f5_tts.api import F5TTS  # noqa: PLC0415

        device = best_device()
        model = F5TTS(device=device)
        set_tts(model, device=device)
        return device

    # ── Stdin reader ──────────────────────────────────────────────────────────

    def _read_stdin(self) -> None:
        """Background thread: read JSON-line commands from stdin."""
        for raw_line in sys.stdin.buffer:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                cmd = json.loads(line)
            except json.JSONDecodeError:
                continue

            action = cmd.get("cmd")
            if action == "cancel":
                # Cancel is handled immediately — no queue needed
                self._cancel_event.set()
            elif action == "shutdown":
                # Put shutdown in queue so the main loop sees it after finishing
                self._shutdown = True
                self._cmd_queue.put(cmd)
            else:
                self._cmd_queue.put(cmd)

    # ── Generation ────────────────────────────────────────────────────────────

    def _run_generate(self, cmd: dict) -> None:
        """Execute a full generation job and stream chunks back."""
        from narracast.audio_generation import GenerationCancelled, generate_core  # noqa: PLC0415
        from narracast.audio_polish import AudioPolishSettings  # noqa: PLC0415
        from narracast.presets import DEFAULT_PRESET  # noqa: PLC0415

        job_id = str(cmd.get("job_id", ""))
        self._cancel_event.clear()
        chunk_idx = 0

        def on_progress(frac: float, desc: str = "") -> None:
            _emit({"type": "progress", "job_id": job_id, "frac": frac, "desc": desc})

        def on_chunk(segment) -> None:
            nonlocal chunk_idx
            if self._cancel_event.is_set():
                raise GenerationCancelled()
            pcm_b64 = base64.b64encode(segment.raw_data).decode("ascii")
            _emit({
                "type": "chunk",
                "job_id": job_id,
                "chunk_idx": chunk_idx,
                "frame_rate": segment.frame_rate,
                "channels": segment.channels,
                "sample_width": segment.sample_width,
                "pcm_b64": pcm_b64,
            })
            chunk_idx += 1

        try:
            polish_dict = cmd.get("audio_polish")
            audio_polish = (
                AudioPolishSettings.from_dict(polish_dict)
                if polish_dict
                else None
            )
            path, summary = generate_core(
                str(cmd["text"]),
                str(cmd["voice_name"]),
                float(cmd.get("speed", 1.0)),
                str(cmd.get("title", "")),
                str(cmd.get("part", "")),
                on_progress=on_progress,
                preset_name=str(cmd.get("preset_name", DEFAULT_PRESET)),
                paragraph_pause_ms=int(cmd.get("paragraph_pause_ms", 500)),
                sentence_pause_ms=int(cmd.get("sentence_pause_ms", 0)),
                audio_polish=audio_polish,
                project_id=str(cmd.get("project_id", "")),
                chapter_id=str(cmd.get("chapter_id", "")),
                on_chunk=on_chunk,
            )
            _emit({"type": "done", "job_id": job_id,
                   "output_path": path, "summary": summary})
        except GenerationCancelled:
            _emit({"type": "cancelled", "job_id": job_id})
        except Exception as exc:  # noqa: BLE001
            _emit({"type": "error", "job_id": job_id, "message": str(exc)})

    # ── Voice preview ─────────────────────────────────────────────────────────

    def _run_preview(self, cmd: dict) -> None:
        """Run a short single-chunk inference and return a WAV temp path."""
        from narracast.audio_generation import infer_chunk  # noqa: PLC0415

        job_id = str(cmd.get("job_id", ""))
        try:
            wav_path = infer_chunk(
                str(cmd["text"]),
                str(cmd["voice_path"]),
                float(cmd.get("speed", 1.0)),
                int(cmd.get("nfe_step", 16)),
            )
            _emit({"type": "preview_done", "job_id": job_id, "wav_path": wav_path})
        except Exception as exc:  # noqa: BLE001
            _emit({"type": "error", "job_id": job_id, "message": str(exc)})

    # ── Benchmark ─────────────────────────────────────────────────────────────

    def _run_benchmark_preset(self, cmd: dict) -> None:
        """Run BENCHMARK_TEXT through one preset and return timing stats."""
        from narracast.benchmark import BENCHMARK_TEXT  # noqa: PLC0415
        from narracast.presets import DEFAULT_PRESET  # noqa: PLC0415
        import narracast.audio_generation as ag  # noqa: PLC0415

        job_id = str(cmd.get("job_id", ""))
        preset_name = str(cmd.get("preset_name", DEFAULT_PRESET))
        voice_name = str(cmd.get("voice_name", ""))

        with tempfile.TemporaryDirectory() as tmp_dir:
            original_output_dir = ag.OUTPUT_DIR
            ag.OUTPUT_DIR = Path(tmp_dir)
            chunk_count = 0

            def _count_progress(frac: float, desc: str = "") -> None:
                nonlocal chunk_count
                if "Chunk" in desc:
                    try:
                        part = desc.split("Chunk")[1].strip().split("/")[0].strip()
                        chunk_count = max(chunk_count, int(part))
                    except (ValueError, IndexError):
                        pass

            try:
                t0 = time.time()
                output_path, _ = ag.generate_core(
                    BENCHMARK_TEXT,
                    voice_name,
                    1.0,
                    "__benchmark__",
                    "",
                    on_progress=_count_progress,
                    preset_name=preset_name,
                )
                gen_time = time.time() - t0

                meta_path = Path(output_path).with_suffix(".json")
                audio_duration_ms = json.loads(
                    meta_path.read_text(encoding="utf-8")
                )["duration_ms"]
                audio_duration_s = audio_duration_ms / 1000
                rtf = gen_time / audio_duration_s if audio_duration_s > 0 else 0
                avg_s = gen_time / chunk_count if chunk_count > 0 else gen_time

                result = {
                    "preset": preset_name,
                    "chunks": chunk_count,
                    "gen_time_s": gen_time,
                    "audio_duration_s": audio_duration_s,
                    "rtf": rtf,
                    "avg_s_per_chunk": avg_s,
                }
                _emit({"type": "benchmark_preset_done", "job_id": job_id,
                       "result": result})
            except Exception as exc:  # noqa: BLE001
                _emit({"type": "error", "job_id": job_id, "message": str(exc)})
            finally:
                ag.OUTPUT_DIR = original_output_dir


def main() -> None:
    """Entry point for ``python -m narracast.tts_worker``."""
    Worker().run()


if __name__ == "__main__":
    main()
