"""GUI-side manager for the F5-TTS worker subprocess.

:class:`TTSProcess` spawns ``python -m narracast.tts_worker``, forwards jobs
to it via a JSON-lines protocol over stdin/stdout, and routes responses to
per-job :class:`JobCallbacks`.

Usage
-----
::

    proc = get_tts_process()
    proc.start(on_ready=lambda device: ..., on_load_error=lambda err: ...)

    callbacks = JobCallbacks(
        on_progress=lambda frac, desc: ...,
        on_chunk=lambda seg: streamer.feed(seg),
        on_done=lambda path, msg: ...,
        on_error=lambda err: ...,
    )
    proc.submit_job(
        {"job_id": "abc", "text": "...", "voice_name": "..."},
        callbacks,
    )

Crash isolation
---------------
If the worker process crashes, :meth:`TTSProcess.is_alive` returns ``False``
and the outstanding job's ``on_error`` callback is called with a crash message.
Call :meth:`TTSProcess.restart` to spawn a fresh worker.

Thread safety
-------------
:meth:`submit_job`, :meth:`submit_preview`, :meth:`cancel`, :meth:`stop` and
:meth:`restart` are safe to call from any thread.  Callbacks are invoked from
the reader thread — callers that need to update Qt widgets should emit a Qt
signal from the callback rather than touching widgets directly.
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Callable, Any


# ── Per-job callback bag ──────────────────────────────────────────────────────

@dataclass
class JobCallbacks:
    """Callbacks for a single job submitted to :class:`TTSProcess`.

    All fields are optional.  Callbacks are invoked from the reader thread, so
    Qt UI updates must be marshalled to the main thread (e.g. by emitting a
    Qt signal).
    """

    #: Called repeatedly during generation: ``(fraction 0–1, description)``.
    on_progress: Callable[[float, str], None] | None = None

    #: Called for each synthesised audio chunk: ``(AudioSegment,)``.
    #: Connect to :meth:`ChunkStreamer.feed` for live playback.
    on_chunk: Callable[[Any], None] | None = None

    #: Called when generation completes: ``(output_path, summary_message)``.
    on_done: Callable[[str, str], None] | None = None

    #: Called on generation failure: ``(error_message,)``.
    on_error: Callable[[str], None] | None = None

    #: Called when a job is cancelled between chunks.
    on_cancelled: Callable[[], None] | None = None

    #: Called when a ``preview`` job completes: ``(wav_path,)``.
    on_preview_done: Callable[[str], None] | None = None

    #: Called when a ``benchmark_preset`` job completes: ``(result_dict,)``.
    on_benchmark_preset_done: Callable[[dict], None] | None = None


# ── TTSProcess ────────────────────────────────────────────────────────────────

class TTSProcess:
    """Manages a single long-lived F5-TTS worker subprocess.

    The worker owns the model object.  The GUI sends generation/preview jobs
    via a JSON-lines protocol and receives responses the same way.  Audio
    chunks are base64-encoded inside the JSON to avoid a separate binary
    channel.
    """

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self._send_lock = threading.Lock()
        self._cb_lock = threading.Lock()
        self._callbacks: JobCallbacks | None = None
        self._on_ready: Callable[[str], None] | None = None
        self._on_load_error: Callable[[str], None] | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(
        self,
        on_ready: Callable[[str], None] | None = None,
        on_load_error: Callable[[str], None] | None = None,
    ) -> None:
        """Spawn the worker subprocess and start the response reader thread.

        Parameters
        ----------
        on_ready:
            Called once when the model is loaded: ``(device_string,)``.
        on_load_error:
            Called if the model fails to load: ``(error_message,)``.
        """
        self._on_ready = on_ready
        self._on_load_error = on_load_error

        self._proc = subprocess.Popen(
            [sys.executable, "-m", "narracast.tts_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,  # binary mode — we encode/decode ourselves
        )

        self._reader = threading.Thread(
            target=self._read_loop,
            daemon=True,
            name="tts-reader",
        )
        self._reader.start()

        # Drain stderr silently so the OS pipe buffer never fills up
        threading.Thread(
            target=self._drain_stderr,
            daemon=True,
            name="tts-stderr",
        ).start()

    def stop(self) -> None:
        """Terminate the worker process immediately."""
        if self._proc and self._proc.poll() is None:
            try:
                self._send({"cmd": "shutdown"})
            except OSError:
                pass
            try:
                self._proc.terminate()
            except OSError:
                pass
        self._proc = None

    def restart(
        self,
        on_ready: Callable[[str], None] | None = None,
        on_load_error: Callable[[str], None] | None = None,
    ) -> None:
        """Stop the current worker (if alive) and spawn a new one."""
        self.stop()
        self.start(
            on_ready=on_ready or self._on_ready,
            on_load_error=on_load_error or self._on_load_error,
        )

    def is_alive(self) -> bool:
        """True if the worker subprocess is running."""
        return self._proc is not None and self._proc.poll() is None

    # ── Job submission ────────────────────────────────────────────────────────

    def submit_job(self, params: dict, callbacks: JobCallbacks) -> None:
        """Send a ``generate`` command to the worker.

        Parameters
        ----------
        params:
            Dict with keys matching :func:`generate_core` parameters plus
            ``job_id``.  Required keys: ``text``, ``voice_name``.
        callbacks:
            Handlers for progress / chunk / done / error events.
        """
        with self._cb_lock:
            self._callbacks = callbacks
        self._send({"cmd": "generate", **params})

    def submit_preview(self, params: dict, callbacks: JobCallbacks) -> None:
        """Send a ``preview`` command to the worker.

        Parameters
        ----------
        params:
            Dict with keys: ``job_id``, ``text``, ``voice_path``,
            ``speed`` (default 1.0), ``nfe_step`` (default 16).
        callbacks:
            At minimum, provide ``on_preview_done`` and ``on_error``.
        """
        with self._cb_lock:
            self._callbacks = callbacks
        self._send({"cmd": "preview", **params})

    def submit_benchmark_preset(self, params: dict, callbacks: JobCallbacks) -> None:
        """Send a ``benchmark_preset`` command to the worker.

        Parameters
        ----------
        params:
            Dict with keys: ``job_id``, ``voice_name``, ``preset_name``.
        callbacks:
            At minimum, provide ``on_benchmark_preset_done`` and ``on_error``.
        """
        with self._cb_lock:
            self._callbacks = callbacks
        self._send({"cmd": "benchmark_preset", **params})

    def cancel(self) -> None:
        """Ask the worker to cancel the current job between chunks."""
        self._send({"cmd": "cancel"})

    def ping(self) -> None:
        """Send a health-check ping (worker responds with ``pong``)."""
        self._send({"cmd": "ping"})

    # ── Internal: sending ─────────────────────────────────────────────────────

    def _send(self, obj: dict) -> None:
        with self._send_lock:
            if self._proc and self._proc.stdin and self._proc.poll() is None:
                try:
                    line = json.dumps(obj, ensure_ascii=False) + "\n"
                    self._proc.stdin.write(line.encode("utf-8"))
                    self._proc.stdin.flush()
                except (OSError, BrokenPipeError):
                    pass

    # ── Internal: reading ─────────────────────────────────────────────────────

    def _read_loop(self) -> None:
        if self._proc is None or self._proc.stdout is None:
            return
        try:
            for raw_line in self._proc.stdout:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self._dispatch(msg)
        except (OSError, ValueError):
            pass

        # Worker process exited — notify the outstanding job if any
        with self._cb_lock:
            cb = self._callbacks
            self._callbacks = None
        if cb and cb.on_error:
            cb.on_error("TTS worker process exited unexpectedly.")

    def _drain_stderr(self) -> None:
        if self._proc is None or self._proc.stderr is None:
            return
        try:
            for _ in self._proc.stderr:
                pass  # discard library noise
        except (OSError, ValueError):
            pass

    def _dispatch(self, msg: dict) -> None:
        """Route one response message to the appropriate callback."""
        t = msg.get("type")
        with self._cb_lock:
            cb = self._callbacks

        if t == "ready":
            device = str(msg.get("device", "cpu"))
            if self._on_ready:
                self._on_ready(device)

        elif t == "load_error":
            err = str(msg.get("message", "Model failed to load."))
            if self._on_load_error:
                self._on_load_error(err)

        elif t == "progress":
            if cb and cb.on_progress:
                cb.on_progress(
                    float(msg.get("frac", 0.0)),
                    str(msg.get("desc", "")),
                )

        elif t == "chunk":
            if cb and cb.on_chunk:
                try:
                    from pydub import AudioSegment  # noqa: PLC0415
                    pcm = base64.b64decode(msg["pcm_b64"])
                    seg = AudioSegment(
                        pcm,
                        frame_rate=int(msg["frame_rate"]),
                        sample_width=int(msg["sample_width"]),
                        channels=int(msg["channels"]),
                    )
                    cb.on_chunk(seg)
                except Exception:  # noqa: BLE001
                    pass  # chunk reconstruction failure is best-effort

        elif t == "done":
            if cb and cb.on_done:
                with self._cb_lock:
                    self._callbacks = None
                cb.on_done(
                    str(msg.get("output_path", "")),
                    str(msg.get("summary", "")),
                )

        elif t == "error":
            err = str(msg.get("message", "Unknown error"))
            if cb and cb.on_error:
                with self._cb_lock:
                    self._callbacks = None
                cb.on_error(err)

        elif t == "cancelled":
            if cb and cb.on_cancelled:
                with self._cb_lock:
                    self._callbacks = None
                cb.on_cancelled()
            elif cb and cb.on_error:
                # Callers that don't handle cancellation see it as an error
                with self._cb_lock:
                    self._callbacks = None
                cb.on_error("Generation cancelled.")

        elif t == "preview_done":
            if cb and cb.on_preview_done:
                with self._cb_lock:
                    self._callbacks = None
                cb.on_preview_done(str(msg.get("wav_path", "")))

        elif t == "benchmark_preset_done":
            if cb and cb.on_benchmark_preset_done:
                with self._cb_lock:
                    self._callbacks = None
                cb.on_benchmark_preset_done(dict(msg.get("result", {})))

        elif t == "pong":
            pass  # health check — no callback needed


# ── Module-level singleton ────────────────────────────────────────────────────

_tts_process: TTSProcess | None = None


def get_tts_process() -> TTSProcess:
    """Return the application-wide :class:`TTSProcess` instance (created lazily)."""
    global _tts_process
    if _tts_process is None:
        _tts_process = TTSProcess()
    return _tts_process
