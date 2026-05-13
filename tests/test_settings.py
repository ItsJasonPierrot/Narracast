import json
import tempfile
import unittest
from pathlib import Path

from narracast.settings import DEFAULT_SETTINGS, load_settings, save_settings


class SettingsTests(unittest.TestCase):
    def test_missing_settings_returns_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"

            self.assertEqual(load_settings(path), DEFAULT_SETTINGS)

    def test_invalid_json_returns_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text("{ nope", encoding="utf-8")

            self.assertEqual(load_settings(path), DEFAULT_SETTINGS)

    def test_load_settings_filters_unknown_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text(
                json.dumps({"speed": 1.5, "preset": "Fast", "text": "do not keep me"}),
                encoding="utf-8",
            )

            settings = load_settings(path)

            self.assertEqual(settings["speed"], 1.5)
            self.assertEqual(settings["preset"], "Fast")
            self.assertNotIn("text", settings)

    def test_load_settings_sanitizes_malformed_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text(
                json.dumps(
                    {
                        "speed": "very fast",
                        "preset": "Turbo",
                        "geometry": "bad",
                        "voice": 123,
                        "paragraph_pause_ms": "forever",
                        "sentence_pause_ms": "too much",
                        "app_theme": "Sepia",
                        "current_page": "made-up-page",
                        "reader_theme": "Solarized",
                        "reader_spacing": "Huge",
                        "reader_font": "Papyrus",
                        "reader_size": "XXL",
                    }
                ),
                encoding="utf-8",
            )

            settings = load_settings(path)

            self.assertEqual(settings["speed"], DEFAULT_SETTINGS["speed"])
            self.assertEqual(settings["preset"], DEFAULT_SETTINGS["preset"])
            self.assertEqual(settings["geometry"], DEFAULT_SETTINGS["geometry"])
            self.assertEqual(settings["voice"], DEFAULT_SETTINGS["voice"])
            self.assertEqual(
                settings["paragraph_pause_ms"],
                DEFAULT_SETTINGS["paragraph_pause_ms"],
            )
            self.assertEqual(settings["sentence_pause_ms"], DEFAULT_SETTINGS["sentence_pause_ms"])
            self.assertEqual(settings["app_theme"], DEFAULT_SETTINGS["app_theme"])
            self.assertEqual(settings["current_page"], DEFAULT_SETTINGS["current_page"])
            self.assertEqual(settings["reader_theme"], DEFAULT_SETTINGS["reader_theme"])
            self.assertEqual(settings["reader_spacing"], DEFAULT_SETTINGS["reader_spacing"])
            self.assertEqual(settings["reader_font"], DEFAULT_SETTINGS["reader_font"])
            self.assertEqual(settings["reader_size"], DEFAULT_SETTINGS["reader_size"])

    def test_load_settings_clamps_speed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text(json.dumps({"speed": 9}), encoding="utf-8")

            settings = load_settings(path)

            self.assertEqual(settings["speed"], 2.0)

    def test_load_settings_clamps_paragraph_pause(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text(json.dumps({"paragraph_pause_ms": 9000}), encoding="utf-8")

            settings = load_settings(path)

            self.assertEqual(settings["paragraph_pause_ms"], 2000)

    def test_load_settings_clamps_sentence_pause(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text(json.dumps({"sentence_pause_ms": 9000}), encoding="utf-8")

            settings = load_settings(path)

            self.assertEqual(settings["sentence_pause_ms"], 1000)

    def test_save_and_load_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            save_settings(
                {
                    "voice": "reference",
                    "speed": 1.2,
                    "preset": "Draft",
                    "title": "Book",
                    "part": "Part 1",
                    "geometry": "980x720",
                    "paragraph_pause_ms": 1200,
                    "sentence_pause_ms": 300,
                    "app_theme": "Light",
                    "current_page": "projects",
                    "reader_theme": "Warm",
                    "reader_spacing": "Relaxed",
                    "reader_font": "Courier New",
                    "reader_size": "L",
                    "reader_auto_pause_paragraphs": True,
                    "reader_study_mode": True,
                    "text": "large pasted text should not be stored",
                },
                path,
            )

            settings = load_settings(path)

            self.assertEqual(settings["voice"], "reference")
            self.assertEqual(settings["speed"], 1.2)
            self.assertEqual(settings["preset"], "Draft")
            self.assertEqual(settings["title"], "Book")
            self.assertEqual(settings["part"], "Part 1")
            self.assertEqual(settings["paragraph_pause_ms"], 1200)
            self.assertEqual(settings["sentence_pause_ms"], 300)
            self.assertEqual(settings["app_theme"], "Light")
            self.assertEqual(settings["current_page"], "projects")
            self.assertEqual(settings["reader_theme"], "Warm")
            self.assertEqual(settings["reader_spacing"], "Relaxed")
            self.assertEqual(settings["reader_font"], "Courier New")
            self.assertEqual(settings["reader_size"], "L")
            self.assertTrue(settings["reader_auto_pause_paragraphs"])
            self.assertTrue(settings["reader_study_mode"])
            self.assertNotIn("text", settings)


if __name__ == "__main__":
    unittest.main()
