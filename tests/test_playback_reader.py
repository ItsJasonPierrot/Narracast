import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from narracast.playback import (
    delete_bookmark,
    load_bookmarks,
    load_last_position,
    save_bookmark,
    save_last_position,
)
from narracast import voices
from narracast.ui.pages.generate_page import GeneratePage
from narracast.ui.pages.reading_page import ReadingPage, highlight_span_for_timeline_item


def _qt_app():
    app = QApplication.instance()
    return app or QApplication([])


class _FakeSession:
    def __init__(self, position=0):
        self.position = position
        self.paused = False

    def is_playing(self):
        return not self.paused

    def pause_and_get_position(self):
        self.paused = True
        return self.position


class PlaybackReaderTests(unittest.TestCase):
    def test_last_position_preserves_existing_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audio.json"
            path.write_text(
                json.dumps({"title": "Book", "last_position_ms": 100}),
                encoding="utf-8",
            )

            save_last_position(path, 2500)
            payload = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(payload["title"], "Book")
            self.assertEqual(load_last_position(path), 2500)

    def test_bookmark_helpers_add_load_and_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audio.json"
            path.write_text(json.dumps({"title": "Book"}), encoding="utf-8")

            save_bookmark(path, "Start", 0)
            save_bookmark(path, "Chapter 2", 12000)
            self.assertEqual(
                load_bookmarks(path),
                [
                    {"label": "Start", "position_ms": 0},
                    {"label": "Chapter 2", "position_ms": 12000},
                ],
            )

            delete_bookmark(path, 0)
            self.assertEqual(load_bookmarks(path), [{"label": "Chapter 2", "position_ms": 12000}])

    def test_highlight_span_prefers_offsets_for_duplicate_text(self):
        source = "Repeat this. Different sentence. Repeat this."
        item = {
            "text": "Repeat this.",
            "text_start": 33,
            "text_end": 45,
        }

        self.assertEqual(highlight_span_for_timeline_item(source, item), (33, 45))

    def test_highlight_span_falls_back_to_search_when_offsets_missing(self):
        source = "First chunk. Second chunk."
        item = {"text": "Second chunk."}

        self.assertEqual(highlight_span_for_timeline_item(source, item), (13, 26))

    def test_highlight_span_accepts_normalized_offset_text(self):
        source = "First sentence.\nSecond sentence."
        item = {"text": "First sentence. Second sentence.", "text_start": 0, "text_end": len(source)}

        self.assertEqual(highlight_span_for_timeline_item(source, item), (0, len(source)))

    def test_reader_display_settings_sync_focus_mode(self):
        _qt_app()
        page = ReadingPage()

        page.apply_settings(
            {
                "reader_theme": "Warm",
                "reader_spacing": "Spacious",
                "reader_font": "Courier New",
                "reader_size": "XL",
                "reader_auto_pause_paragraphs": True,
                "reader_study_mode": True,
            }
        )

        self.assertEqual(page._theme_key, "Warm")
        self.assertEqual(page._spacing_key, "Spacious")
        self.assertEqual(page._font_name, "Courier New")
        self.assertEqual(page._current_font_size, 26)
        self.assertTrue(page._auto_pause_paragraphs)
        self.assertTrue(page._study_mode)
        self.assertEqual(page._current_chunk_label.font().family(), "Courier New")
        self.assertIn("#3a2a10", page._current_frame.styleSheet())
        page.deleteLater()

    def test_reader_pacing_settings_round_trip(self):
        _qt_app()
        page = ReadingPage()

        page._auto_pause_check.setChecked(True)
        page._study_mode_check.setChecked(True)
        settings = page.current_settings()

        self.assertTrue(settings["reader_auto_pause_paragraphs"])
        self.assertTrue(settings["reader_study_mode"])
        page.deleteLater()

    def test_reader_auto_pause_paragraph_pauses_inside_paragraph_gap(self):
        _qt_app()
        page = ReadingPage()
        page._duration_ms = 3000
        page._auto_pause_paragraphs = True
        page._timeline = [
            {"type": "speech", "audio_start_ms": 0, "audio_end_ms": 1000},
            {"type": "pause", "audio_start_ms": 1000, "audio_end_ms": 1500},
            {"type": "speech", "audio_start_ms": 1500, "audio_end_ms": 3000},
        ]
        session = _FakeSession(position=1100)
        page._session = session

        self.assertTrue(page._maybe_auto_pause_paragraph(1100))
        self.assertTrue(session.paused)
        page.deleteLater()

    def test_reader_study_mode_pauses_on_sentence_transition(self):
        _qt_app()
        page = ReadingPage()
        page._duration_ms = 3000
        page._study_mode = True
        page._last_highlight_key = "sentence:0:0"
        session = _FakeSession(position=1200)
        page._session = session

        page._maybe_study_pause(
            {"type": "sentence", "unit_index": 1, "audio_start_ms": 1000}
        )

        self.assertTrue(session.paused)
        page.deleteLater()

    def test_reader_controls_start_disabled(self):
        _qt_app()
        page = ReadingPage()

        self.assertFalse(page._play_btn.isEnabled())
        self.assertFalse(page._stop_btn.isEnabled())
        self.assertFalse(page._back_btn.isEnabled())
        self.assertFalse(page._forward_btn.isEnabled())
        self.assertFalse(page._repeat_btn.isEnabled())
        self.assertFalse(page._bm_add_btn.isEnabled())
        self.assertFalse(page._focus_btn.isEnabled())
        page.deleteLater()

    def test_preview_cache_key_changes_with_reference_signature(self):
        _qt_app()
        page = GeneratePage()
        original_reference = voices.REFERENCE
        original_reference_text = voices.REFERENCE_TEXT
        with tempfile.TemporaryDirectory() as tmp:
            voices.REFERENCE = Path(tmp) / "reference.wav"
            voices.REFERENCE.write_bytes(b"first wav")
            voices.REFERENCE_TEXT = Path(tmp) / "reference.txt"
            try:
                voices.save_reference_text("first transcript")
                first = page._preview_cache_key(
                    "hello", "reference", str(voices.REFERENCE), 1.0, "Draft"
                )
                voices.save_reference_text("changed transcript")
                second = page._preview_cache_key(
                    "hello", "reference", str(voices.REFERENCE), 1.0, "Draft"
                )
                self.assertNotEqual(first, second)
            finally:
                voices.REFERENCE = original_reference
                voices.REFERENCE_TEXT = original_reference_text
                page.deleteLater()

    def test_generate_page_persists_sentence_pause_setting(self):
        _qt_app()
        page = GeneratePage()

        page.apply_settings({"sentence_pause_ms": 450})

        self.assertEqual(page.current_settings()["sentence_pause_ms"], 450)
        page.deleteLater()


if __name__ == "__main__":
    unittest.main()
