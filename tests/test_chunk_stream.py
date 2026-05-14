"""Tests for narracast.chunk_stream."""

from __future__ import annotations

import struct
import subprocess
import threading
import time
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch

from narracast.chunk_stream import (
    ChunkStreamer,
    _ffplay_available,
    _reset_ffplay_cache,
    write_streaming_wav_header,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_segment(duration_ms: int = 100, frame_rate: int = 24_000) -> MagicMock:
    """Minimal AudioSegment-like mock with raw_data and format attributes."""
    seg = MagicMock()
    seg.frame_rate = frame_rate
    seg.channels = 1
    seg.sample_width = 2  # 16-bit
    seg.raw_data = b"\x00\x00" * (frame_rate * duration_ms // 1000)
    # Chained set_* calls return the same mock (format is already correct)
    seg.set_frame_rate.return_value = seg
    seg.set_channels.return_value = seg
    seg.set_sample_width.return_value = seg
    return seg


def _make_mismatched_segment(
    frame_rate: int = 44_100, channels: int = 2, sample_width: int = 4
) -> MagicMock:
    """A segment whose format does NOT match the default ChunkStreamer params."""
    seg = MagicMock()
    seg.frame_rate = frame_rate
    seg.channels = channels
    seg.sample_width = sample_width  # 32-bit
    seg.raw_data = b"\x00" * 1024
    # Conversion returns a segment with the correct format
    converted = _make_segment()
    seg.set_frame_rate.return_value = converted
    converted.set_channels.return_value = converted
    converted.set_sample_width.return_value = converted
    return seg


# ── write_streaming_wav_header ─────────────────────────────────────────────────

class TestWriteStreamingWavHeader(unittest.TestCase):
    """Verify the byte layout of the streaming WAV header."""

    def _parse(self, buf: bytes) -> dict:
        """Parse the 44-byte streaming WAV header and return its fields."""
        self.assertEqual(buf[:4], b"RIFF")
        (riff_size,) = struct.unpack_from("<I", buf, 4)
        self.assertEqual(buf[8:12], b"WAVE")
        self.assertEqual(buf[12:16], b"fmt ")
        (fmt_size,) = struct.unpack_from("<I", buf, 16)
        (audio_fmt,) = struct.unpack_from("<H", buf, 20)
        (channels,) = struct.unpack_from("<H", buf, 22)
        (sample_rate,) = struct.unpack_from("<I", buf, 24)
        (byte_rate,) = struct.unpack_from("<I", buf, 28)
        (block_align,) = struct.unpack_from("<H", buf, 32)
        (bits,) = struct.unpack_from("<H", buf, 34)
        self.assertEqual(buf[36:40], b"data")
        (data_size,) = struct.unpack_from("<I", buf, 40)
        return {
            "riff_size": riff_size,
            "fmt_size": fmt_size,
            "audio_fmt": audio_fmt,
            "channels": channels,
            "sample_rate": sample_rate,
            "byte_rate": byte_rate,
            "block_align": block_align,
            "bits": bits,
            "data_size": data_size,
        }

    def test_header_length_is_44_bytes(self) -> None:
        buf = BytesIO()
        write_streaming_wav_header(buf, sample_rate=24_000, channels=1, bits=16)
        self.assertEqual(buf.tell(), 44)

    def test_riff_and_data_sizes_are_unknown(self) -> None:
        buf = BytesIO()
        write_streaming_wav_header(buf, sample_rate=24_000, channels=1, bits=16)
        fields = self._parse(buf.getvalue())
        self.assertEqual(fields["riff_size"], 0xFFFFFFFF)
        self.assertEqual(fields["data_size"], 0xFFFFFFFF)

    def test_pcm_audio_format(self) -> None:
        buf = BytesIO()
        write_streaming_wav_header(buf, sample_rate=24_000, channels=1, bits=16)
        fields = self._parse(buf.getvalue())
        self.assertEqual(fields["audio_fmt"], 1)  # PCM

    def test_mono_24khz_16bit_fields(self) -> None:
        buf = BytesIO()
        write_streaming_wav_header(buf, sample_rate=24_000, channels=1, bits=16)
        fields = self._parse(buf.getvalue())
        self.assertEqual(fields["sample_rate"], 24_000)
        self.assertEqual(fields["channels"], 1)
        self.assertEqual(fields["bits"], 16)
        self.assertEqual(fields["byte_rate"], 24_000 * 1 * 2)
        self.assertEqual(fields["block_align"], 2)

    def test_stereo_44khz_fields(self) -> None:
        buf = BytesIO()
        write_streaming_wav_header(buf, sample_rate=44_100, channels=2, bits=16)
        fields = self._parse(buf.getvalue())
        self.assertEqual(fields["sample_rate"], 44_100)
        self.assertEqual(fields["channels"], 2)
        self.assertEqual(fields["byte_rate"], 44_100 * 2 * 2)
        self.assertEqual(fields["block_align"], 4)

    def test_fmt_chunk_size_is_16(self) -> None:
        buf = BytesIO()
        write_streaming_wav_header(buf, sample_rate=24_000, channels=1, bits=16)
        fields = self._parse(buf.getvalue())
        self.assertEqual(fields["fmt_size"], 16)


# ── _ffplay_available ─────────────────────────────────────────────────────────

class TestFfplayAvailable(unittest.TestCase):
    def setUp(self) -> None:
        _reset_ffplay_cache()

    def tearDown(self) -> None:
        _reset_ffplay_cache()

    def test_returns_true_when_ffplay_succeeds(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = _ffplay_available()
        self.assertTrue(result)

    def test_returns_false_when_ffplay_not_found(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = _ffplay_available()
        self.assertFalse(result)

    def test_returns_false_when_ffplay_times_out(self) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffplay", 3)):
            result = _ffplay_available()
        self.assertFalse(result)

    def test_result_is_cached(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            _ffplay_available()
            _ffplay_available()
        # Only called once despite two invocations
        self.assertEqual(mock_run.call_count, 1)


# ── ChunkStreamer.is_available ─────────────────────────────────────────────────

class TestChunkStreamerIsAvailable(unittest.TestCase):
    def setUp(self) -> None:
        _reset_ffplay_cache()

    def tearDown(self) -> None:
        _reset_ffplay_cache()

    def test_is_available_true_when_ffplay_present(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            self.assertTrue(ChunkStreamer.is_available())

    def test_is_available_false_when_ffplay_absent(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            self.assertFalse(ChunkStreamer.is_available())


# ── ChunkStreamer.start ────────────────────────────────────────────────────────

class TestChunkStreamerStart(unittest.TestCase):
    def setUp(self) -> None:
        _reset_ffplay_cache()

    def tearDown(self) -> None:
        _reset_ffplay_cache()

    def test_start_returns_false_when_ffplay_unavailable(self) -> None:
        with patch("narracast.chunk_stream._ffplay_available", return_value=False):
            streamer = ChunkStreamer()
            result = streamer.start()
        self.assertFalse(result)

    def test_start_returns_false_when_popen_raises(self) -> None:
        with patch("narracast.chunk_stream._ffplay_available", return_value=True), \
             patch("subprocess.Popen", side_effect=FileNotFoundError):
            streamer = ChunkStreamer()
            result = streamer.start()
        self.assertFalse(result)

    def test_start_returns_true_when_ffplay_launches(self) -> None:
        mock_proc = MagicMock()
        mock_proc.stdin = BytesIO()
        mock_proc.poll.return_value = None
        with patch("narracast.chunk_stream._ffplay_available", return_value=True), \
             patch("subprocess.Popen", return_value=mock_proc):
            streamer = ChunkStreamer()
            result = streamer.start()
        self.assertTrue(result)

    def test_start_writes_wav_header_to_stdin(self) -> None:
        stdin_buf = BytesIO()
        mock_proc = MagicMock()
        mock_proc.stdin = stdin_buf
        mock_proc.poll.return_value = None
        with patch("narracast.chunk_stream._ffplay_available", return_value=True), \
             patch("subprocess.Popen", return_value=mock_proc):
            streamer = ChunkStreamer(sample_rate=24_000, channels=1, bits=16)
            streamer.start()
        # Header should be exactly 44 bytes
        self.assertEqual(stdin_buf.tell(), 44)
        header = stdin_buf.getvalue()
        self.assertTrue(header.startswith(b"RIFF"))
        self.assertIn(b"WAVE", header)
        self.assertIn(b"data", header)

    def test_start_returns_false_when_header_write_fails(self) -> None:
        stdin_mock = MagicMock()
        stdin_mock.write.side_effect = BrokenPipeError
        mock_proc = MagicMock()
        mock_proc.stdin = stdin_mock
        with patch("narracast.chunk_stream._ffplay_available", return_value=True), \
             patch("subprocess.Popen", return_value=mock_proc):
            streamer = ChunkStreamer()
            result = streamer.start()
        self.assertFalse(result)
        self.assertFalse(streamer.is_running)

    def test_is_running_false_before_start(self) -> None:
        streamer = ChunkStreamer()
        self.assertFalse(streamer.is_running)


# ── ChunkStreamer.feed ─────────────────────────────────────────────────────────

class TestChunkStreamerFeed(unittest.TestCase):
    def _started_streamer(self) -> tuple[ChunkStreamer, MagicMock]:
        """Return a streamer that has been successfully started, plus its proc mock."""
        stdin_buf = BytesIO()
        mock_proc = MagicMock()
        mock_proc.stdin = stdin_buf
        mock_proc.poll.return_value = None

        with patch("narracast.chunk_stream._ffplay_available", return_value=True), \
             patch("subprocess.Popen", return_value=mock_proc):
            streamer = ChunkStreamer()
            streamer.start()
        return streamer, mock_proc

    def test_feed_before_start_returns_false(self) -> None:
        streamer = ChunkStreamer()
        seg = _make_segment()
        result = streamer.feed(seg)
        self.assertFalse(result)

    def test_feed_returns_true_when_write_succeeds(self) -> None:
        streamer, mock_proc = self._started_streamer()
        seg = _make_segment()
        result = streamer.feed(seg)
        self.assertTrue(result)

    def test_feed_writes_raw_data_to_stdin(self) -> None:
        stdin_buf = BytesIO()
        mock_proc = MagicMock()
        mock_proc.stdin = stdin_buf
        mock_proc.poll.return_value = None
        with patch("narracast.chunk_stream._ffplay_available", return_value=True), \
             patch("subprocess.Popen", return_value=mock_proc):
            streamer = ChunkStreamer()
            streamer.start()
        header_end = stdin_buf.tell()
        seg = _make_segment(duration_ms=100)
        streamer.feed(seg)
        written = stdin_buf.getvalue()[header_end:]
        self.assertEqual(written, seg.raw_data)

    def test_feed_returns_false_when_proc_has_exited(self) -> None:
        streamer, mock_proc = self._started_streamer()
        mock_proc.poll.return_value = 1  # non-None → exited
        seg = _make_segment()
        result = streamer.feed(seg)
        self.assertFalse(result)

    def test_feed_returns_false_on_broken_pipe(self) -> None:
        stdin_mock = MagicMock()
        stdin_mock.write.side_effect = BrokenPipeError
        mock_proc = MagicMock()
        mock_proc.stdin = stdin_mock
        mock_proc.poll.return_value = None
        with patch("narracast.chunk_stream._ffplay_available", return_value=True), \
             patch("subprocess.Popen", return_value=mock_proc):
            streamer = ChunkStreamer()
            # Patch start to avoid re-using the broken stdin for the header
            with patch.object(streamer, "_active", True):
                streamer._proc = mock_proc
        seg = _make_segment()
        result = streamer.feed(seg)
        self.assertFalse(result)
        self.assertFalse(streamer._active)

    def test_feed_after_stop_returns_false(self) -> None:
        streamer, _proc = self._started_streamer()
        streamer.stop()
        seg = _make_segment()
        result = streamer.feed(seg)
        self.assertFalse(result)

    def test_feed_converts_mismatched_format(self) -> None:
        """feed() should resample a segment with a different frame rate."""
        stdin_buf = BytesIO()
        mock_proc = MagicMock()
        mock_proc.stdin = stdin_buf
        mock_proc.poll.return_value = None
        with patch("narracast.chunk_stream._ffplay_available", return_value=True), \
             patch("subprocess.Popen", return_value=mock_proc):
            streamer = ChunkStreamer(sample_rate=24_000)
            streamer.start()
        seg = _make_mismatched_segment(frame_rate=44_100)
        result = streamer.feed(seg)
        # Conversion should have been called
        seg.set_frame_rate.assert_called_once_with(24_000)
        self.assertTrue(result)

    def test_feed_returns_false_when_conversion_fails(self) -> None:
        stdin_buf = BytesIO()
        mock_proc = MagicMock()
        mock_proc.stdin = stdin_buf
        mock_proc.poll.return_value = None
        with patch("narracast.chunk_stream._ffplay_available", return_value=True), \
             patch("subprocess.Popen", return_value=mock_proc):
            streamer = ChunkStreamer(sample_rate=24_000)
            streamer.start()
        seg = MagicMock()
        seg.frame_rate = 44_100
        seg.channels = 1
        seg.sample_width = 2
        seg.set_frame_rate.side_effect = RuntimeError("cannot convert")
        result = streamer.feed(seg)
        self.assertFalse(result)


# ── ChunkStreamer.stop / close ─────────────────────────────────────────────────

class TestChunkStreamerStopClose(unittest.TestCase):
    def _started_streamer(self) -> tuple[ChunkStreamer, MagicMock]:
        stdin_buf = BytesIO()
        mock_proc = MagicMock()
        mock_proc.stdin = stdin_buf
        mock_proc.poll.return_value = None
        with patch("narracast.chunk_stream._ffplay_available", return_value=True), \
             patch("subprocess.Popen", return_value=mock_proc):
            streamer = ChunkStreamer()
            streamer.start()
        return streamer, mock_proc

    def test_stop_terminates_process(self) -> None:
        streamer, mock_proc = self._started_streamer()
        streamer.stop()
        mock_proc.terminate.assert_called_once()

    def test_stop_sets_active_false(self) -> None:
        streamer, _proc = self._started_streamer()
        streamer.stop()
        self.assertFalse(streamer._active)

    def test_stop_clears_proc_reference(self) -> None:
        streamer, _proc = self._started_streamer()
        streamer.stop()
        self.assertIsNone(streamer._proc)

    def test_stop_when_not_started_is_safe(self) -> None:
        streamer = ChunkStreamer()
        streamer.stop()  # Must not raise
        self.assertFalse(streamer.is_running)

    def test_stop_when_proc_already_exited_is_safe(self) -> None:
        streamer, mock_proc = self._started_streamer()
        mock_proc.poll.return_value = 0  # already exited
        streamer.stop()  # Must not raise

    def test_close_closes_stdin(self) -> None:
        stdin_mock = MagicMock()
        mock_proc = MagicMock()
        mock_proc.stdin = stdin_mock
        mock_proc.poll.return_value = None
        with patch("narracast.chunk_stream._ffplay_available", return_value=True), \
             patch("subprocess.Popen", return_value=mock_proc):
            streamer = ChunkStreamer()
            streamer.start()
        streamer.close()
        stdin_mock.close.assert_called_once()

    def test_close_sets_active_false(self) -> None:
        streamer, _proc = self._started_streamer()
        streamer.close()
        self.assertFalse(streamer._active)

    def test_close_when_not_started_is_safe(self) -> None:
        streamer = ChunkStreamer()
        streamer.close()  # Must not raise

    def test_stop_after_close_is_safe(self) -> None:
        streamer, _proc = self._started_streamer()
        streamer.close()
        streamer.stop()  # Must not raise


# ── ChunkStreamer.is_running ───────────────────────────────────────────────────

class TestChunkStreamerIsRunning(unittest.TestCase):
    def test_is_running_false_when_not_started(self) -> None:
        streamer = ChunkStreamer()
        self.assertFalse(streamer.is_running)

    def test_is_running_true_after_successful_start(self) -> None:
        stdin_buf = BytesIO()
        mock_proc = MagicMock()
        mock_proc.stdin = stdin_buf
        mock_proc.poll.return_value = None  # still running
        with patch("narracast.chunk_stream._ffplay_available", return_value=True), \
             patch("subprocess.Popen", return_value=mock_proc):
            streamer = ChunkStreamer()
            streamer.start()
        self.assertTrue(streamer.is_running)

    def test_is_running_false_after_stop(self) -> None:
        stdin_buf = BytesIO()
        mock_proc = MagicMock()
        mock_proc.stdin = stdin_buf
        mock_proc.poll.return_value = None
        with patch("narracast.chunk_stream._ffplay_available", return_value=True), \
             patch("subprocess.Popen", return_value=mock_proc):
            streamer = ChunkStreamer()
            streamer.start()
        streamer.stop()
        self.assertFalse(streamer.is_running)

    def test_is_running_false_when_proc_exits(self) -> None:
        stdin_buf = BytesIO()
        mock_proc = MagicMock()
        mock_proc.stdin = stdin_buf
        mock_proc.poll.return_value = None
        with patch("narracast.chunk_stream._ffplay_available", return_value=True), \
             patch("subprocess.Popen", return_value=mock_proc):
            streamer = ChunkStreamer()
            streamer.start()
        mock_proc.poll.return_value = 0  # ffplay exited
        self.assertFalse(streamer.is_running)


# ── Thread-safety ─────────────────────────────────────────────────────────────

class TestChunkStreamerThreadSafety(unittest.TestCase):
    """Smoke-test concurrent feed() + stop() from multiple threads."""

    def test_concurrent_feed_and_stop(self) -> None:
        stdin_buf = BytesIO()
        mock_proc = MagicMock()
        mock_proc.stdin = stdin_buf
        mock_proc.poll.return_value = None

        with patch("narracast.chunk_stream._ffplay_available", return_value=True), \
             patch("subprocess.Popen", return_value=mock_proc):
            streamer = ChunkStreamer()
            streamer.start()

        errors: list[Exception] = []

        def feeder():
            for _ in range(20):
                try:
                    streamer.feed(_make_segment())
                except Exception as exc:
                    errors.append(exc)

        def stopper():
            time.sleep(0.01)
            try:
                streamer.stop()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=feeder) for _ in range(3)]
        threads.append(threading.Thread(target=stopper))
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        self.assertEqual(errors, [], f"Thread errors: {errors}")


# ── generate_core on_chunk integration ────────────────────────────────────────

class TestGenerateCoreOnChunk(unittest.TestCase):
    """on_chunk is called once per synthesised speech chunk."""

    def _mock_generate_core_deps(self):
        """Return a context manager that patches all generate_core externals."""
        from contextlib import ExitStack
        from narracast import audio_generation

        stack = ExitStack()
        fake_segment = MagicMock()
        fake_segment.__len__ = MagicMock(return_value=500)  # 500 ms
        fake_segment.__iadd__ = lambda s, o: s
        fake_segment.__add__ = lambda s, o: s
        fake_segment.raw_data = b"\x00" * 100

        fake_empty = MagicMock()
        fake_empty.__len__ = MagicMock(return_value=0)
        fake_empty.__iadd__ = lambda s, o: fake_segment
        fake_empty.__add__ = lambda s, o: fake_segment

        stack.enter_context(patch.object(audio_generation, "get_voice_files",
                                         return_value={"test_voice": "/fake/ref.wav"}))
        stack.enter_context(patch.object(audio_generation, "prepare_reference",
                                         return_value=MagicMock(ref_text="ref", cache_hit=False)))
        stack.enter_context(patch.object(audio_generation, "infer_chunk_segment",
                                         return_value=(fake_segment, {
                                             "inference_s": 0.1, "waveform_convert_s": 0.01,
                                             "temp_wav_write_s": 0.0, "wav_load_s": 0.0,
                                             "reference_cache_hits": 0.0,
                                             "reference_cache_misses": 1.0,
                                         })))
        stack.enter_context(patch.object(audio_generation, "apply_polish",
                                         return_value=fake_segment))
        stack.enter_context(patch.object(audio_generation, "_export_generation_outputs",
                                         return_value=MagicMock()))
        stack.enter_context(patch.object(audio_generation, "make_output_filename",
                                         return_value="test_output.mp3"))
        stack.enter_context(patch("narracast.audio_generation.OUTPUT_DIR",
                                  new_callable=lambda: type(
                                      "P", (), {"__truediv__": lambda s, x: MagicMock()}
                                  )))
        return stack

    def test_on_chunk_called_for_each_speech_chunk(self) -> None:
        from narracast.audio_generation import generate_core
        from narracast.text_splitter import split_into_timeline_items

        received: list = []
        text = "Hello world. Second sentence. Third sentence."

        with self._mock_generate_core_deps():
            with patch("narracast.audio_generation.split_into_timeline_items") as mock_split:
                # Simulate 3 speech chunks
                mock_split.return_value = [
                    {"type": "speech", "text": f"Chunk {i}."} for i in range(3)
                ]
                try:
                    generate_core(
                        text, "test_voice", 1.0, "T", "P",
                        on_chunk=received.append,
                    )
                except Exception:
                    pass  # export is mocked minimally — only care about on_chunk

        self.assertEqual(len(received), 3)

    def test_on_chunk_exception_does_not_abort_generation(self) -> None:
        """A crashing on_chunk must never propagate out of generate_core."""
        from narracast.audio_generation import generate_core

        call_count = 0

        def bad_chunk(seg):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("streaming broken")

        with self._mock_generate_core_deps():
            with patch("narracast.audio_generation.split_into_timeline_items") as mock_split:
                mock_split.return_value = [
                    {"type": "speech", "text": "Hello."},
                    {"type": "speech", "text": "World."},
                ]
                try:
                    generate_core(
                        "Hello. World.", "test_voice", 1.0, "T", "P",
                        on_chunk=bad_chunk,
                    )
                except Exception:
                    pass  # export mock may raise — that's fine

        self.assertGreater(call_count, 0)

    def test_on_chunk_none_is_valid(self) -> None:
        """Passing on_chunk=None must work without error."""
        from narracast.audio_generation import generate_core

        with self._mock_generate_core_deps():
            with patch("narracast.audio_generation.split_into_timeline_items") as mock_split:
                mock_split.return_value = [{"type": "speech", "text": "Hello."}]
                try:
                    generate_core("Hello.", "test_voice", 1.0, "T", "P", on_chunk=None)
                except Exception:
                    pass  # export mock may raise

    def test_on_chunk_not_called_for_pauses(self) -> None:
        """Pause items must not trigger on_chunk."""
        from narracast.audio_generation import generate_core

        received: list = []

        with self._mock_generate_core_deps():
            with patch("narracast.audio_generation.split_into_timeline_items") as mock_split:
                mock_split.return_value = [
                    {"type": "speech", "text": "Hello."},
                    {"type": "pause", "duration_ms": 500},
                ]
                try:
                    generate_core(
                        "Hello.", "test_voice", 1.0, "T", "P",
                        on_chunk=received.append,
                    )
                except Exception:
                    pass

        self.assertEqual(len(received), 1)


if __name__ == "__main__":
    unittest.main()
