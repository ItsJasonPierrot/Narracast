import json
import tempfile
import unittest
from pathlib import Path

from pydub import AudioSegment

from narracast import audio_generation


class GenerationMetadataTests(unittest.TestCase):
    def test_waveform_to_audio_segment_converts_float_samples(self):
        segment = audio_generation._waveform_to_audio_segment([0.0, 0.25, -0.25, 0.0], 44100)

        self.assertIsInstance(segment, AudioSegment)
        self.assertEqual(segment.channels, 1)
        self.assertEqual(segment.frame_rate, 44100)
        self.assertGreaterEqual(len(segment), 0)

    def test_generate_core_writes_metadata_sidecar(self):
        original_output_dir = audio_generation.OUTPUT_DIR
        original_get_voice_files = audio_generation.get_voice_files
        original_infer_chunk_segment = audio_generation.infer_chunk_segment

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_path = tmp_path / "reference.wav"
            ref_path.write_bytes(b"fake reference")

            def fake_infer_chunk_segment(_chunk, _reference_audio, _speed, _nfe_step=32):
                return AudioSegment.silent(duration=100), {
                    "inference_s": 0.01,
                    "waveform_convert_s": 0.001,
                    "temp_wav_write_s": 0.0,
                    "wav_load_s": 0.0,
                }

            audio_generation.OUTPUT_DIR = tmp_path
            audio_generation.get_voice_files = lambda: {"Test Voice": str(ref_path)}
            audio_generation.infer_chunk_segment = fake_infer_chunk_segment

            try:
                output_path, _message = audio_generation.generate_core(
                    "First sentence.\n\nSecond sentence.",
                    "Test Voice",
                    1.0,
                    "Book",
                    "Part 1",
                    preset_name="Balanced",
                )
            finally:
                audio_generation.OUTPUT_DIR = original_output_dir
                audio_generation.get_voice_files = original_get_voice_files
                audio_generation.infer_chunk_segment = original_infer_chunk_segment

            metadata_path = Path(output_path).with_suffix(".json")
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))

            self.assertTrue(Path(output_path).exists())
            self.assertEqual(payload["output_filename"], Path(output_path).name)
            self.assertEqual(payload["source_text"], "First sentence.\n\nSecond sentence.")
            self.assertEqual(
                [item["type"] for item in payload["timeline"]],
                ["speech", "pause", "speech"],
            )
            self.assertEqual(payload["timeline"][1]["duration_ms"], 500)
            self.assertEqual(
                [unit["text"] for unit in payload["highlight_units"]],
                ["First sentence.", "Second sentence."],
            )
            self.assertEqual(payload["highlight_units"][0]["type"], "sentence")
            self.assertEqual(
                payload["highlight_units"][0]["timing_estimate"],
                "proportional_by_characters",
            )
            self.assertEqual(payload["paragraph_pause_ms"], 500)
            timings = payload["generation_timings"]
            self.assertIn("split_s", timings)
            self.assertIn("inference_s", timings)
            self.assertIn("waveform_convert_s", timings)
            self.assertIn("temp_wav_write_s", timings)
            self.assertIn("wav_load_s", timings)
            self.assertIn("assembly_s", timings)
            self.assertIn("mp3_export_s", timings)
            self.assertIn("metadata_write_s", timings)
            self.assertIn("finalize_s", timings)
            self.assertIn("total_s", timings)
            self.assertIn("total_before_metadata_s", timings)

    def test_generate_core_respects_custom_paragraph_pause(self):
        original_output_dir = audio_generation.OUTPUT_DIR
        original_get_voice_files = audio_generation.get_voice_files
        original_infer_chunk_segment = audio_generation.infer_chunk_segment

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_path = tmp_path / "reference.wav"
            ref_path.write_bytes(b"fake reference")

            def fake_infer_chunk_segment(_chunk, _reference_audio, _speed, _nfe_step=32):
                return AudioSegment.silent(duration=100), {
                    "inference_s": 0.01,
                    "waveform_convert_s": 0.001,
                    "temp_wav_write_s": 0.0,
                    "wav_load_s": 0.0,
                }

            audio_generation.OUTPUT_DIR = tmp_path
            audio_generation.get_voice_files = lambda: {"Test Voice": str(ref_path)}
            audio_generation.infer_chunk_segment = fake_infer_chunk_segment

            try:
                output_path, _ = audio_generation.generate_core(
                    "Hello.\n\nWorld.",
                    "Test Voice",
                    1.0,
                    "Book",
                    "Part 1",
                    preset_name="Balanced",
                    paragraph_pause_ms=1500,
                )
            finally:
                audio_generation.OUTPUT_DIR = original_output_dir
                audio_generation.get_voice_files = original_get_voice_files
                audio_generation.infer_chunk_segment = original_infer_chunk_segment

            payload = json.loads(Path(output_path).with_suffix(".json").read_text(encoding="utf-8"))

            self.assertEqual(payload["paragraph_pause_ms"], 1500)
            pause = next(i for i in payload["timeline"] if i["type"] == "pause")
            self.assertEqual(pause["duration_ms"], 1500)

    def test_generate_core_respects_custom_sentence_pause(self):
        original_output_dir = audio_generation.OUTPUT_DIR
        original_get_voice_files = audio_generation.get_voice_files
        original_infer_chunk_segment = audio_generation.infer_chunk_segment

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ref_path = tmp_path / "reference.wav"
            ref_path.write_bytes(b"fake reference")

            def fake_infer_chunk_segment(_chunk, _reference_audio, _speed, _nfe_step=32):
                return AudioSegment.silent(duration=100), {
                    "inference_s": 0.01,
                    "waveform_convert_s": 0.001,
                    "temp_wav_write_s": 0.0,
                    "wav_load_s": 0.0,
                }

            audio_generation.OUTPUT_DIR = tmp_path
            audio_generation.get_voice_files = lambda: {"Test Voice": str(ref_path)}
            audio_generation.infer_chunk_segment = fake_infer_chunk_segment

            try:
                output_path, _ = audio_generation.generate_core(
                    "Hello. World.",
                    "Test Voice",
                    1.0,
                    "Book",
                    "Part 1",
                    preset_name="Balanced",
                    sentence_pause_ms=250,
                )
            finally:
                audio_generation.OUTPUT_DIR = original_output_dir
                audio_generation.get_voice_files = original_get_voice_files
                audio_generation.infer_chunk_segment = original_infer_chunk_segment

            payload = json.loads(Path(output_path).with_suffix(".json").read_text(encoding="utf-8"))

            self.assertEqual(payload["sentence_pause_ms"], 250)
            self.assertEqual(
                [item["type"] for item in payload["timeline"]],
                ["speech", "sentence_pause", "speech"],
            )
            pause = next(i for i in payload["timeline"] if i["type"] == "sentence_pause")
            self.assertEqual(pause["duration_ms"], 250)


if __name__ == "__main__":
    unittest.main()
