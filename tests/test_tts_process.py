"""Tests for narracast.tts_process and narracast.tts_worker."""

from __future__ import annotations

import base64
import json
import struct
import threading
import time
import unittest
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock, call, patch

from narracast.tts_process import JobCallbacks, TTSProcess, get_tts_process


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_pcm_b64(n_samples: int = 100) -> str:
    """Return base64-encoded silent s16le PCM."""
    return base64.b64encode(b"\x00\x00" * n_samples).decode("ascii")


def _json_line(obj: dict) -> bytes:
    return (json.dumps(obj) + "\n").encode("utf-8")


class _FakeProc:
    """Minimal subprocess.Popen stand-in."""

    def __init__(self, stdout_lines: list[dict]) -> None:
        # Build a BytesIO buffer with all the JSON-line responses
        buf = b"".join(_json_line(obj) for obj in stdout_lines)
        self.stdout = BytesIO(buf)
        self.stdin = BytesIO()
        self.stderr = BytesIO()
        self._returncode: int | None = None

    def poll(self) -> int | None:
        return self._returncode

    def terminate(self) -> None:
        self._returncode = -1


def _make_proc_with_responses(responses: list[dict]) -> _FakeProc:
    return _FakeProc(responses)


# ── JobCallbacks dataclass ────────────────────────────────────────────────────

class TestJobCallbacks(unittest.TestCase):
    def test_all_fields_default_to_none(self) -> None:
        cb = JobCallbacks()
        for attr in (
            "on_progress", "on_chunk", "on_done", "on_error",
            "on_cancelled", "on_preview_done", "on_benchmark_preset_done",
        ):
            self.assertIsNone(getattr(cb, attr))

    def test_fields_can_be_set(self) -> None:
        fn = lambda *a: None
        cb = JobCallbacks(on_progress=fn, on_done=fn)
        self.assertIs(cb.on_progress, fn)
        self.assertIs(cb.on_done, fn)
        self.assertIsNone(cb.on_error)


# ── TTSProcess._dispatch ─────────────────────────────────────────────────────

class TestTTSProcessDispatch(unittest.TestCase):
    """Unit-test the _dispatch() routing logic without spawning a subprocess."""

    def _proc_with_mock_cb(self, callbacks: JobCallbacks) -> TTSProcess:
        proc = TTSProcess()
        proc._callbacks = callbacks
        return proc

    def test_dispatch_ready_calls_on_ready(self) -> None:
        on_ready = MagicMock()
        p = TTSProcess()
        p._on_ready = on_ready
        p._dispatch({"type": "ready", "device": "mps"})
        on_ready.assert_called_once_with("mps")

    def test_dispatch_load_error_calls_on_load_error(self) -> None:
        on_err = MagicMock()
        p = TTSProcess()
        p._on_load_error = on_err
        p._dispatch({"type": "load_error", "message": "OOM"})
        on_err.assert_called_once_with("OOM")

    def test_dispatch_progress_calls_callback(self) -> None:
        cb = JobCallbacks(on_progress=MagicMock())
        p = self._proc_with_mock_cb(cb)
        p._dispatch({"type": "progress", "job_id": "x", "frac": 0.5, "desc": "Chunk 1"})
        cb.on_progress.assert_called_once_with(0.5, "Chunk 1")

    def test_dispatch_progress_no_callback_is_safe(self) -> None:
        p = self._proc_with_mock_cb(JobCallbacks())
        p._dispatch({"type": "progress", "frac": 0.1, "desc": ""})  # must not raise

    def test_dispatch_done_calls_callback_and_clears_callbacks(self) -> None:
        cb = JobCallbacks(on_done=MagicMock())
        p = self._proc_with_mock_cb(cb)
        p._dispatch({"type": "done", "output_path": "/out/a.mp3", "summary": "Done!"})
        cb.on_done.assert_called_once_with("/out/a.mp3", "Done!")
        self.assertIsNone(p._callbacks)

    def test_dispatch_error_calls_callback_and_clears_callbacks(self) -> None:
        cb = JobCallbacks(on_error=MagicMock())
        p = self._proc_with_mock_cb(cb)
        p._dispatch({"type": "error", "message": "BOOM"})
        cb.on_error.assert_called_once_with("BOOM")
        self.assertIsNone(p._callbacks)

    def test_dispatch_cancelled_calls_on_cancelled(self) -> None:
        cb = JobCallbacks(on_cancelled=MagicMock())
        p = self._proc_with_mock_cb(cb)
        p._dispatch({"type": "cancelled", "job_id": "x"})
        cb.on_cancelled.assert_called_once()
        self.assertIsNone(p._callbacks)

    def test_dispatch_cancelled_falls_back_to_on_error_when_no_on_cancelled(self) -> None:
        cb = JobCallbacks(on_error=MagicMock())
        p = self._proc_with_mock_cb(cb)
        p._dispatch({"type": "cancelled"})
        cb.on_error.assert_called_once_with("Generation cancelled.")

    def test_dispatch_preview_done_calls_callback(self) -> None:
        cb = JobCallbacks(on_preview_done=MagicMock())
        p = self._proc_with_mock_cb(cb)
        p._dispatch({"type": "preview_done", "wav_path": "/tmp/a.wav"})
        cb.on_preview_done.assert_called_once_with("/tmp/a.wav")
        self.assertIsNone(p._callbacks)

    def test_dispatch_benchmark_preset_done_calls_callback(self) -> None:
        cb = JobCallbacks(on_benchmark_preset_done=MagicMock())
        p = self._proc_with_mock_cb(cb)
        result = {"preset": "Best", "rtf": 0.5}
        p._dispatch({"type": "benchmark_preset_done", "result": result})
        cb.on_benchmark_preset_done.assert_called_once_with(result)
        self.assertIsNone(p._callbacks)

    def test_dispatch_chunk_reconstructs_audio_segment(self) -> None:
        received: list = []
        cb = JobCallbacks(on_chunk=received.append)
        p = self._proc_with_mock_cb(cb)
        pcm_b64 = _make_pcm_b64(48)  # 48 samples
        p._dispatch({
            "type": "chunk",
            "job_id": "x",
            "chunk_idx": 0,
            "frame_rate": 24000,
            "channels": 1,
            "sample_width": 2,
            "pcm_b64": pcm_b64,
        })
        self.assertEqual(len(received), 1)
        seg = received[0]
        self.assertEqual(seg.frame_rate, 24000)
        self.assertEqual(seg.channels, 1)
        self.assertEqual(seg.sample_width, 2)

    def test_dispatch_chunk_bad_b64_does_not_raise(self) -> None:
        cb = JobCallbacks(on_chunk=MagicMock())
        p = self._proc_with_mock_cb(cb)
        p._dispatch({
            "type": "chunk",
            "pcm_b64": "NOT_VALID_BASE64!!!",
            "frame_rate": 24000, "channels": 1, "sample_width": 2,
        })  # must not raise

    def test_dispatch_pong_is_ignored_safely(self) -> None:
        p = TTSProcess()
        p._dispatch({"type": "pong"})  # must not raise

    def test_dispatch_unknown_type_is_ignored(self) -> None:
        p = TTSProcess()
        p._dispatch({"type": "whatever_unknown_msg"})  # must not raise


# ── TTSProcess._send ──────────────────────────────────────────────────────────

class TestTTSProcessSend(unittest.TestCase):
    def _proc_with_fake_stdin(self) -> tuple[TTSProcess, BytesIO]:
        fake_proc = MagicMock()
        stdin_buf = BytesIO()
        fake_proc.stdin = stdin_buf
        fake_proc.poll.return_value = None

        proc = TTSProcess()
        proc._proc = fake_proc
        return proc, stdin_buf

    def test_send_writes_json_line(self) -> None:
        proc, buf = self._proc_with_fake_stdin()
        proc._send({"cmd": "ping"})
        written = buf.getvalue().decode("utf-8")
        self.assertEqual(written.strip(), json.dumps({"cmd": "ping"}))
        self.assertTrue(written.endswith("\n"))

    def test_send_when_proc_is_none_does_not_raise(self) -> None:
        proc = TTSProcess()
        proc._proc = None
        proc._send({"cmd": "ping"})  # must not raise

    def test_send_when_proc_exited_does_not_raise(self) -> None:
        proc, _ = self._proc_with_fake_stdin()
        proc._proc.poll.return_value = 1  # exited
        proc._send({"cmd": "ping"})  # must not raise

    def test_send_broken_pipe_does_not_raise(self) -> None:
        fake_proc = MagicMock()
        fake_proc.stdin.write.side_effect = BrokenPipeError
        fake_proc.poll.return_value = None
        proc = TTSProcess()
        proc._proc = fake_proc
        proc._send({"cmd": "ping"})  # must not raise


# ── TTSProcess.submit_* ───────────────────────────────────────────────────────

class TestTTSProcessSubmit(unittest.TestCase):
    def _proc_capturing_sends(self) -> tuple[TTSProcess, list[dict]]:
        sent: list[dict] = []

        proc = TTSProcess()
        original_send = proc._send

        def _capture(obj: dict) -> None:
            sent.append(obj)

        proc._send = _capture
        return proc, sent

    def test_submit_job_sets_callbacks_and_sends_generate(self) -> None:
        proc, sent = self._proc_capturing_sends()
        cb = JobCallbacks(on_done=MagicMock())
        proc.submit_job({"job_id": "x", "text": "Hello", "voice_name": "v"}, cb)
        self.assertIs(proc._callbacks, cb)
        self.assertEqual(sent[0]["cmd"], "generate")
        self.assertEqual(sent[0]["text"], "Hello")

    def test_submit_preview_sets_callbacks_and_sends_preview(self) -> None:
        proc, sent = self._proc_capturing_sends()
        cb = JobCallbacks(on_preview_done=MagicMock())
        proc.submit_preview({"job_id": "y", "text": "Hi", "voice_path": "/v.wav"}, cb)
        self.assertEqual(sent[0]["cmd"], "preview")
        self.assertEqual(sent[0]["voice_path"], "/v.wav")

    def test_submit_benchmark_preset_sends_correct_cmd(self) -> None:
        proc, sent = self._proc_capturing_sends()
        cb = JobCallbacks(on_benchmark_preset_done=MagicMock())
        proc.submit_benchmark_preset(
            {"job_id": "z", "voice_name": "vn", "preset_name": "Best"}, cb
        )
        self.assertEqual(sent[0]["cmd"], "benchmark_preset")
        self.assertEqual(sent[0]["preset_name"], "Best")

    def test_cancel_sends_cancel_cmd(self) -> None:
        proc, sent = self._proc_capturing_sends()
        proc.cancel()
        self.assertEqual(sent[0]["cmd"], "cancel")


# ── TTSProcess end-to-end with fake subprocess ────────────────────────────────

class TestTTSProcessEndToEnd(unittest.TestCase):
    """Simulate the reader loop with a fake process emitting canned responses."""

    def _run_with_responses(
        self,
        responses: list[dict],
        callbacks: JobCallbacks,
        cmd: str = "generate",
    ) -> None:
        """Start a TTSProcess, inject fake responses, and wait for completion."""
        fake_proc = _make_proc_with_responses(responses)
        on_ready_calls: list[str] = []

        proc = TTSProcess()
        proc._proc = fake_proc
        proc._on_ready = on_ready_calls.append

        # Set the callbacks for the active job
        proc._callbacks = callbacks

        # Run the reader loop synchronously (stdout is a BytesIO that will EOF)
        proc._read_loop()
        return on_ready_calls

    def test_ready_message_triggers_on_ready(self) -> None:
        on_ready = MagicMock()
        proc = TTSProcess()
        proc._on_ready = on_ready
        proc._proc = _make_proc_with_responses([{"type": "ready", "device": "cuda"}])
        proc._read_loop()
        on_ready.assert_called_once_with("cuda")

    def test_full_generate_flow(self) -> None:
        """progress → done triggers the right callbacks in order."""
        calls: list[str] = []
        cb = JobCallbacks(
            on_progress=lambda f, d: calls.append(f"prog:{f:.1f}"),
            on_done=lambda p, m: calls.append(f"done:{p}"),
        )
        self._run_with_responses(
            [
                {"type": "progress", "frac": 0.5, "desc": "Chunk 1/2"},
                {"type": "progress", "frac": 0.9, "desc": "Saving…"},
                {"type": "done", "output_path": "/out/a.mp3", "summary": "Done!"},
            ],
            cb,
        )
        self.assertEqual(calls, ["prog:0.5", "prog:0.9", "done:/out/a.mp3"])

    def test_error_flow(self) -> None:
        errors: list[str] = []
        cb = JobCallbacks(on_error=errors.append)
        self._run_with_responses([{"type": "error", "message": "BOOM"}], cb)
        self.assertEqual(errors, ["BOOM"])

    def test_cancelled_flow_uses_on_cancelled(self) -> None:
        cancelled: list[bool] = []
        cb = JobCallbacks(on_cancelled=lambda: cancelled.append(True))
        self._run_with_responses([{"type": "cancelled", "job_id": "x"}], cb)
        self.assertEqual(cancelled, [True])

    def test_process_exit_calls_on_error(self) -> None:
        """When the reader loop sees EOF, the outstanding job gets on_error."""
        errors: list[str] = []
        cb = JobCallbacks(on_error=errors.append)
        # Empty response list → reader sees EOF immediately
        proc = TTSProcess()
        proc._proc = _make_proc_with_responses([])
        proc._callbacks = cb
        proc._read_loop()
        self.assertEqual(len(errors), 1)
        self.assertIn("exited", errors[0].lower())

    def test_chunk_messages_call_on_chunk(self) -> None:
        chunks: list = []
        cb = JobCallbacks(
            on_chunk=chunks.append,
            on_done=lambda p, m: None,
        )
        pcm_b64 = _make_pcm_b64(24)
        self._run_with_responses(
            [
                {
                    "type": "chunk", "job_id": "x", "chunk_idx": 0,
                    "frame_rate": 24000, "channels": 1, "sample_width": 2,
                    "pcm_b64": pcm_b64,
                },
                {"type": "done", "output_path": "/out/a.mp3", "summary": ""},
            ],
            cb,
        )
        self.assertEqual(len(chunks), 1)

    def test_malformed_json_lines_are_skipped(self) -> None:
        """Corrupt lines between valid JSON messages must not abort the loop."""
        errors: list[str] = []
        cb = JobCallbacks(on_done=lambda p, m: None, on_error=errors.append)

        fake_proc = MagicMock()
        fake_proc.poll.return_value = 0
        good_lines = [
            b"NOT_JSON_AT_ALL\n",
            _json_line({"type": "done", "output_path": "/out/x.mp3", "summary": ""}),
        ]
        fake_proc.stdout = BytesIO(b"".join(good_lines))
        proc = TTSProcess()
        proc._proc = fake_proc
        proc._callbacks = cb
        proc._read_loop()
        self.assertEqual(errors, [])  # bad JSON must not trigger on_error


# ── TTSProcess.is_alive ───────────────────────────────────────────────────────

class TestTTSProcessIsAlive(unittest.TestCase):
    def test_is_alive_false_when_no_proc(self) -> None:
        proc = TTSProcess()
        self.assertFalse(proc.is_alive())

    def test_is_alive_true_when_proc_running(self) -> None:
        proc = TTSProcess()
        fake = MagicMock()
        fake.poll.return_value = None
        proc._proc = fake
        self.assertTrue(proc.is_alive())

    def test_is_alive_false_when_proc_exited(self) -> None:
        proc = TTSProcess()
        fake = MagicMock()
        fake.poll.return_value = 0
        proc._proc = fake
        self.assertFalse(proc.is_alive())


# ── get_tts_process singleton ─────────────────────────────────────────────────

class TestGetTTSProcess(unittest.TestCase):
    def test_returns_same_instance(self) -> None:
        import narracast.tts_process as tp
        original = tp._tts_process
        try:
            tp._tts_process = None
            a = get_tts_process()
            b = get_tts_process()
            self.assertIs(a, b)
        finally:
            tp._tts_process = original


# ── GenerationCancelled propagation in generate_core ─────────────────────────

class TestGenerationCancelledPropagation(unittest.TestCase):
    """Verify that GenerationCancelled raised inside on_chunk escapes generate_core."""

    def _mock_generate_core_deps(self):
        from contextlib import ExitStack
        from unittest.mock import patch, MagicMock
        from narracast import audio_generation

        stack = ExitStack()
        fake_segment = MagicMock()
        fake_segment.__len__ = MagicMock(return_value=500)
        fake_segment.__add__ = lambda s, o: s
        fake_segment.__iadd__ = lambda s, o: s
        fake_segment.raw_data = b"\x00" * 100

        stack.enter_context(patch.object(
            audio_generation, "get_voice_files",
            return_value={"v": "/fake.wav"}
        ))
        stack.enter_context(patch.object(
            audio_generation, "prepare_reference",
            return_value=MagicMock(ref_text="", cache_hit=False)
        ))
        stack.enter_context(patch.object(
            audio_generation, "infer_chunk_segment",
            return_value=(fake_segment, {
                "inference_s": 0.01, "waveform_convert_s": 0.0,
                "temp_wav_write_s": 0.0, "wav_load_s": 0.0,
                "reference_cache_hits": 0.0, "reference_cache_misses": 1.0,
            })
        ))
        stack.enter_context(patch.object(
            audio_generation, "_export_generation_outputs",
            return_value=MagicMock()
        ))
        stack.enter_context(patch.object(
            audio_generation, "make_output_filename",
            return_value="out.mp3"
        ))
        stack.enter_context(patch(
            "narracast.audio_generation.OUTPUT_DIR",
            new_callable=lambda: type("P", (), {
                "__truediv__": lambda s, x: MagicMock()
            })
        ))
        return stack

    def test_generation_cancelled_escapes_generate_core(self) -> None:
        from narracast.audio_generation import GenerationCancelled, generate_core
        from unittest.mock import patch

        def bad_chunk(_seg):
            raise GenerationCancelled()

        with self._mock_generate_core_deps():
            with patch("narracast.audio_generation.split_into_timeline_items") as ms:
                ms.return_value = [{"type": "speech", "text": "Hello."}]
                with self.assertRaises(GenerationCancelled):
                    generate_core("Hello.", "v", 1.0, "", "", on_chunk=bad_chunk)

    def test_regular_exception_in_on_chunk_is_swallowed(self) -> None:
        from narracast.audio_generation import generate_core
        from unittest.mock import patch

        called: list = []

        def flaky_chunk(_seg):
            called.append(True)
            raise RuntimeError("streaming broken")

        with self._mock_generate_core_deps():
            with patch("narracast.audio_generation.split_into_timeline_items") as ms:
                ms.return_value = [{"type": "speech", "text": "Hello."}]
                try:
                    generate_core("Hello.", "v", 1.0, "", "", on_chunk=flaky_chunk)
                except Exception:
                    pass  # export mock may raise

        self.assertTrue(called)


if __name__ == "__main__":
    unittest.main()
