import json
import tempfile
import unittest
from pathlib import Path

from narracast.timing_analysis import analyze_generation_timings, format_timing_rows


class TimingAnalysisTests(unittest.TestCase):
    def test_empty_output_dir_returns_no_data_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = analyze_generation_timings(Path(tmp))

        self.assertFalse(report.has_data)
        self.assertEqual(report.file_count, 0)
        self.assertIn("No generation timing data", report.recommendation)

    def test_analyzes_sidecar_timings(self):
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = Path(tmp) / "one.json"
            sidecar.write_text(
                json.dumps(
                    {
                        "generation_timings": {
                            "inference_s": 80,
                            "mp3_export_s": 10,
                            "id3_s": 1,
                            "metadata_write_s": 1,
                            "total_s": 100,
                        }
                    }
                ),
                encoding="utf-8",
            )

            report = analyze_generation_timings(Path(tmp))

        self.assertTrue(report.has_data)
        self.assertEqual(report.file_count, 1)
        self.assertEqual(report.finalize_time_s, 12)
        self.assertAlmostEqual(report.finalize_share, 0.12)
        self.assertIn("Model inference dominates", report.recommendation)

    def test_recommends_async_when_finalization_is_large(self):
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = Path(tmp) / "one.json"
            sidecar.write_text(
                json.dumps(
                    {
                        "generation_timings": {
                            "inference_s": 60,
                            "mp3_export_s": 25,
                            "id3_s": 2,
                            "metadata_write_s": 1,
                            "total_s": 100,
                        }
                    }
                ),
                encoding="utf-8",
            )

            report = analyze_generation_timings(Path(tmp))

        self.assertIn("worth prototyping", report.recommendation)

    def test_format_timing_rows_returns_display_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = Path(tmp) / "one.json"
            sidecar.write_text(
                json.dumps({"generation_timings": {"split_s": 1, "total_s": 10}}),
                encoding="utf-8",
            )
            report = analyze_generation_timings(Path(tmp))

        rows = format_timing_rows(report)
        self.assertIn(("Text split", "1.00s", "10.0%"), rows)


if __name__ == "__main__":
    unittest.main()
