"""Tests for narracast.audio_polish."""

import math
import struct
import unittest

from pydub import AudioSegment

from narracast.audio_polish import (
    VALID_BITRATES,
    AudioPolishSettings,
    _trim_surrounding_silence,
    apply_polish,
)


# ── Test helpers ──────────────────────────────────────────────────────────────

def _make_tone(duration_ms: int = 500, freq_hz: int = 440, amplitude: int = 16000) -> AudioSegment:
    """Create a mono 44100 Hz sine-wave segment."""
    samples_count = int(44100 * duration_ms / 1000)
    samples = [
        int(amplitude * math.sin(2 * math.pi * freq_hz * i / 44100))
        for i in range(samples_count)
    ]
    raw = struct.pack("<" + "h" * samples_count, *samples)
    return AudioSegment(raw, frame_rate=44100, sample_width=2, channels=1)


def _silent(duration_ms: int = 500) -> AudioSegment:
    return AudioSegment.silent(duration=duration_ms)


# ── AudioPolishSettings ───────────────────────────────────────────────────────

class TestAudioPolishSettingsDefaults(unittest.TestCase):
    def test_default_bitrate(self):
        s = AudioPolishSettings()
        self.assertEqual(s.bitrate, "192k")

    def test_default_no_processing(self):
        s = AudioPolishSettings()
        self.assertFalse(s.normalize)
        self.assertEqual(s.fade_in_ms, 0)
        self.assertEqual(s.fade_out_ms, 0)
        self.assertFalse(s.trim_silence)

    def test_is_default_true_for_fresh_instance(self):
        self.assertTrue(AudioPolishSettings().is_default())

    def test_is_default_false_when_normalize_on(self):
        self.assertFalse(AudioPolishSettings(normalize=True).is_default())

    def test_is_default_false_when_fade_in_set(self):
        self.assertFalse(AudioPolishSettings(fade_in_ms=500).is_default())

    def test_is_default_false_when_trim_silence_on(self):
        self.assertFalse(AudioPolishSettings(trim_silence=True).is_default())

    def test_is_default_true_non_default_bitrate_only(self):
        # Changing bitrate alone does not count as "active" processing
        self.assertTrue(AudioPolishSettings(bitrate="320k").is_default())

    def test_invalid_bitrate_falls_back_to_default(self):
        s = AudioPolishSettings(bitrate="999k")
        self.assertEqual(s.bitrate, "192k")

    def test_valid_bitrates_accepted(self):
        for br in VALID_BITRATES:
            s = AudioPolishSettings(bitrate=br)
            self.assertEqual(s.bitrate, br)

    def test_negative_fade_clamped_to_zero(self):
        s = AudioPolishSettings(fade_in_ms=-500, fade_out_ms=-1)
        self.assertEqual(s.fade_in_ms, 0)
        self.assertEqual(s.fade_out_ms, 0)

    def test_excessive_fade_clamped(self):
        s = AudioPolishSettings(fade_in_ms=99_999)
        self.assertEqual(s.fade_in_ms, 10_000)


class TestAudioPolishSettingsSerialization(unittest.TestCase):
    def test_to_dict_round_trip(self):
        original = AudioPolishSettings(
            bitrate="256k", normalize=True, fade_in_ms=200, fade_out_ms=300,
            trim_silence=True,
        )
        d = original.to_dict()
        restored = AudioPolishSettings.from_dict(d)
        self.assertEqual(restored.bitrate, "256k")
        self.assertTrue(restored.normalize)
        self.assertEqual(restored.fade_in_ms, 200)
        self.assertEqual(restored.fade_out_ms, 300)
        self.assertTrue(restored.trim_silence)

    def test_from_dict_with_missing_keys_uses_defaults(self):
        s = AudioPolishSettings.from_dict({})
        self.assertEqual(s.bitrate, "192k")
        self.assertFalse(s.normalize)

    def test_from_dict_ignores_extra_keys(self):
        s = AudioPolishSettings.from_dict({"unknown_key": "value", "bitrate": "128k"})
        self.assertEqual(s.bitrate, "128k")


# ── _trim_surrounding_silence ─────────────────────────────────────────────────

class TestTrimSurroundingSilence(unittest.TestCase):
    def test_trims_leading_silence(self):
        segment = _silent(500) + _make_tone(500)
        trimmed = _trim_surrounding_silence(segment)
        # Leading 500 ms of silence should be removed
        self.assertLess(len(trimmed), len(segment))

    def test_trims_trailing_silence(self):
        segment = _make_tone(500) + _silent(500)
        trimmed = _trim_surrounding_silence(segment)
        self.assertLess(len(trimmed), len(segment))

    def test_trims_both_ends(self):
        segment = _silent(200) + _make_tone(500) + _silent(200)
        trimmed = _trim_surrounding_silence(segment)
        self.assertLess(len(trimmed), len(segment))

    def test_all_silent_returns_original_unchanged(self):
        segment = _silent(500)
        trimmed = _trim_surrounding_silence(segment)
        # Should not produce a zero-length segment
        self.assertGreater(len(trimmed), 0)

    def test_empty_segment_returned_unchanged(self):
        empty = AudioSegment.empty()
        result = _trim_surrounding_silence(empty)
        self.assertEqual(len(result), 0)

    def test_no_silence_unchanged(self):
        tone = _make_tone(500)
        trimmed = _trim_surrounding_silence(tone)
        # Duration should be very close to the original (within one chunk size = 10 ms)
        self.assertAlmostEqual(len(trimmed), len(tone), delta=20)


# ── apply_polish ──────────────────────────────────────────────────────────────

class TestApplyPolish(unittest.TestCase):
    def test_noop_settings_returns_audio_segment(self):
        tone = _make_tone(500)
        result = apply_polish(tone, AudioPolishSettings())
        self.assertIsInstance(result, AudioSegment)

    def test_noop_preserves_duration(self):
        tone = _make_tone(500)
        result = apply_polish(tone, AudioPolishSettings())
        self.assertEqual(len(result), len(tone))

    def test_empty_segment_returned_immediately(self):
        result = apply_polish(AudioSegment.empty(), AudioPolishSettings(normalize=True))
        self.assertEqual(len(result), 0)

    def test_normalize_returns_audio_segment(self):
        tone = _make_tone(500, amplitude=4000)
        result = apply_polish(tone, AudioPolishSettings(normalize=True))
        self.assertIsInstance(result, AudioSegment)

    def test_normalize_raises_peak_level(self):
        tone = _make_tone(500, amplitude=2000)  # quiet
        result = apply_polish(tone, AudioPolishSettings(normalize=True))
        # After normalization, the peak should be higher
        self.assertGreaterEqual(result.max, tone.max)

    def test_fade_in_preserves_duration(self):
        tone = _make_tone(1000)
        result = apply_polish(tone, AudioPolishSettings(fade_in_ms=200))
        self.assertEqual(len(result), len(tone))

    def test_fade_out_preserves_duration(self):
        tone = _make_tone(1000)
        result = apply_polish(tone, AudioPolishSettings(fade_out_ms=200))
        self.assertEqual(len(result), len(tone))

    def test_fade_longer_than_segment_clamped(self):
        tone = _make_tone(300)
        # fade_in_ms > segment length — should not raise
        result = apply_polish(tone, AudioPolishSettings(fade_in_ms=5000))
        self.assertIsInstance(result, AudioSegment)

    def test_trim_silence_removes_padding(self):
        padded = _silent(400) + _make_tone(500) + _silent(400)
        result = apply_polish(padded, AudioPolishSettings(trim_silence=True))
        self.assertLess(len(result), len(padded))

    def test_combined_operations_return_audio_segment(self):
        segment = _silent(200) + _make_tone(1000) + _silent(200)
        settings = AudioPolishSettings(
            normalize=True,
            fade_in_ms=100,
            fade_out_ms=100,
            trim_silence=True,
        )
        result = apply_polish(segment, settings)
        self.assertIsInstance(result, AudioSegment)
        self.assertGreater(len(result), 0)

    def test_bitrate_field_not_applied_by_apply_polish(self):
        # bitrate is used at export time, not inside apply_polish — verify no error
        tone = _make_tone(200)
        result = apply_polish(tone, AudioPolishSettings(bitrate="320k"))
        self.assertIsInstance(result, AudioSegment)


if __name__ == "__main__":
    unittest.main()
