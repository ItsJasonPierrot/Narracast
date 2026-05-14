"""Streaming chunk playback — pipes raw PCM to ffplay via a streaming WAV header.

Audio arrives chunk by chunk from ``generate_core()`` while inference is still
running.  Each chunk's raw PCM is written to ffplay's stdin.  ffplay treats the
stream as a WAV file with unknown length (RIFF size = 0xFFFFFFFF) and plays it
continuously until stdin is closed or the process is terminated.

Usage
-----
::

    streamer = ChunkStreamer()
    if streamer.start():
        for segment in my_chunks:
            if not streamer.feed(segment):
                break   # ffplay died — generation still continues
        streamer.close()   # let ffplay drain the remaining buffered audio

Graceful degradation
--------------------
If ffplay is not installed, :meth:`ChunkStreamer.start` returns ``False`` and
all subsequent :meth:`ChunkStreamer.feed` calls are no-ops.  The rest of the
generation pipeline is completely unaffected.

Audio format
------------
The WAV header is written once with the parameters supplied to
:class:`ChunkStreamer` (default: 24 000 Hz, mono, 16-bit — the F5-TTS output
format).  :meth:`feed` will resample/convert the incoming :class:`AudioSegment`
if it does not match those parameters, so passing segments with a different
frame rate is safe even though it should not happen in practice.
"""

from __future__ import annotations

import struct
import subprocess
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydub import AudioSegment


_FFPLAY_AVAILABLE: bool | None = None  # cached after first check


def _ffplay_available() -> bool:
    """Return True if ``ffplay`` (part of ffmpeg) is installed and responsive."""
    global _FFPLAY_AVAILABLE
    if _FFPLAY_AVAILABLE is None:
        try:
            subprocess.run(
                ["ffplay", "-version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
            )
            _FFPLAY_AVAILABLE = True
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            _FFPLAY_AVAILABLE = False
    return _FFPLAY_AVAILABLE


def _reset_ffplay_cache() -> None:
    """Reset the ffplay availability cache (test helper only)."""
    global _FFPLAY_AVAILABLE
    _FFPLAY_AVAILABLE = None


def write_streaming_wav_header(
    f,
    *,
    sample_rate: int,
    channels: int,
    bits: int,
) -> None:
    """Write a streaming WAV header with unknown-length RIFF and data chunks.

    Using ``0xFFFFFFFF`` for both the RIFF chunk size and the data chunk size
    signals to decoders that the stream length is not known in advance.  ffplay
    accepts this and plays continuously until stdin is closed or EOF is reached.
    The ``Ignoring maximum wav data size`` warning ffplay emits is harmless.

    Parameters
    ----------
    f:
        A writable binary file-like object (e.g. ``proc.stdin``).
    sample_rate:
        Audio sample rate in Hz.
    channels:
        Number of channels (1 = mono).
    bits:
        Bits per sample (16 for signed 16-bit little-endian PCM).
    """
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    f.write(b"RIFF")
    f.write(struct.pack("<I", 0xFFFFFFFF))  # unknown total RIFF size
    f.write(b"WAVE")
    f.write(b"fmt ")
    f.write(struct.pack("<I", 16))          # PCM fmt chunk is always 16 bytes
    f.write(struct.pack("<H", 1))           # audio format: PCM = 1
    f.write(struct.pack("<H", channels))
    f.write(struct.pack("<I", sample_rate))
    f.write(struct.pack("<I", byte_rate))
    f.write(struct.pack("<H", block_align))
    f.write(struct.pack("<H", bits))
    f.write(b"data")
    f.write(struct.pack("<I", 0xFFFFFFFF))  # unknown data chunk size


class ChunkStreamer:
    """Stream audio chunks to ffplay via a WAV-over-stdin pipe.

    The streamer is single-use: start it once, feed chunks, then close or stop
    it.  To play a second generation, create a new instance.

    Parameters
    ----------
    sample_rate:
        Audio sample rate in Hz.  Must match the segments that will be passed
        to :meth:`feed`.  Defaults to 24 000 Hz (F5-TTS output rate).
    channels:
        Number of audio channels (1 = mono).
    bits:
        Bits per sample (16 for s16le).
    """

    def __init__(
        self,
        *,
        sample_rate: int = 24_000,
        channels: int = 1,
        bits: int = 16,
    ) -> None:
        self._sample_rate = sample_rate
        self._channels = channels
        self._bits = bits
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._active = False

    # ── Public API ────────────────────────────────────────────────────────────

    @staticmethod
    def is_available() -> bool:
        """Return True if ffplay is installed and usable on this machine."""
        return _ffplay_available()

    def start(self) -> bool:
        """Launch ffplay and write the streaming WAV header.

        Returns
        -------
        bool
            ``True`` if ffplay started successfully and is ready to accept PCM
            data.  ``False`` if ffplay is not installed, could not be launched,
            or the header write failed — all subsequent :meth:`feed` calls will
            be no-ops.
        """
        if not _ffplay_available():
            return False
        try:
            self._proc = subprocess.Popen(
                [
                    "ffplay",
                    "-i", "pipe:0",
                    "-nodisp",
                    "-autoexit",
                    "-loglevel", "quiet",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (FileNotFoundError, OSError):
            self._proc = None
            return False

        try:
            assert self._proc.stdin is not None
            write_streaming_wav_header(
                self._proc.stdin,
                sample_rate=self._sample_rate,
                channels=self._channels,
                bits=self._bits,
            )
        except (BrokenPipeError, OSError):
            # ffplay died before we could write the header
            try:
                self._proc.terminate()
            except OSError:
                pass
            self._proc = None
            return False

        self._active = True
        return True

    def feed(self, segment: "AudioSegment") -> bool:
        """Write one audio chunk's PCM bytes to ffplay's stdin.

        If the segment's audio format does not match the parameters given at
        construction, it is resampled/converted automatically.

        Parameters
        ----------
        segment:
            An :class:`~pydub.AudioSegment` produced by
            ``infer_chunk_segment()``.

        Returns
        -------
        bool
            ``True`` if the write succeeded.  ``False`` if ffplay has already
            exited or the pipe is broken.  A ``False`` return does **not**
            mean generation should be aborted — the caller should stop feeding
            but continue producing the final MP3.
        """
        if not self._active:
            return False

        # Convert to the format the WAV header advertises, if necessary
        try:
            if segment.frame_rate != self._sample_rate:
                segment = segment.set_frame_rate(self._sample_rate)
            if segment.channels != self._channels:
                segment = segment.set_channels(self._channels)
            if segment.sample_width != self._bits // 8:
                segment = segment.set_sample_width(self._bits // 8)
        except Exception:
            return False  # conversion failed — skip chunk but stay alive

        with self._lock:
            if self._proc is None or self._proc.stdin is None:
                self._active = False
                return False
            if self._proc.poll() is not None:
                # ffplay exited unexpectedly
                self._active = False
                return False
            try:
                self._proc.stdin.write(segment.raw_data)
                self._proc.stdin.flush()
                return True
            except (BrokenPipeError, OSError):
                self._active = False
                return False

    def stop(self) -> None:
        """Terminate ffplay immediately, cutting off any buffered audio.

        Safe to call from any thread, even if :meth:`start` was never called
        or returned ``False``.
        """
        self._active = False
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                try:
                    self._proc.terminate()
                except OSError:
                    pass
            self._proc = None

    def close(self) -> None:
        """Close stdin and let ffplay drain the remaining buffered audio.

        This is the graceful end-of-stream signal.  ffplay will finish playing
        whatever has been written and then exit on its own.  Non-blocking — this
        method returns immediately without waiting for ffplay to exit.
        """
        self._active = False
        with self._lock:
            if self._proc is not None and self._proc.stdin is not None:
                try:
                    self._proc.stdin.close()
                except OSError:
                    pass

    @property
    def is_running(self) -> bool:
        """True if ffplay was started successfully and has not yet exited."""
        if not self._active:
            return False
        with self._lock:
            if self._proc is None:
                return False
            return self._proc.poll() is None
