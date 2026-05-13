import json
import tempfile
import unittest
from pathlib import Path

from narracast import metadata, output_files, paths, presets, text_splitter, voices


class BackendHelperTests(unittest.TestCase):
    # ── output_files helpers ──────────────────────────────────────────────────


    def test_app_paths_are_relative_to_project_root(self):
        self.assertEqual(paths.APP_DIR, Path(__file__).resolve().parents[1])
        self.assertEqual(paths.OUTPUT_DIR, paths.APP_DIR / "output")
        self.assertEqual(paths.CLEAN_VOICE, paths.APP_DIR / "clean_voice")
        self.assertEqual(paths.VOICES_DIR, paths.APP_DIR / "voices")
        self.assertEqual(paths.PROJECTS_DIR, paths.APP_DIR / "projects")
        self.assertEqual(paths.REFERENCE, paths.APP_DIR / "reference.wav")
        self.assertEqual(paths.REFERENCE_TEXT, paths.APP_DIR / "reference.txt")

    def test_make_output_filename_uses_title_and_part(self):
        name = output_files.make_output_filename("ignored text", "Conquest of Bread", "Part 1")

        self.assertRegex(
            name,
            r"^Conquest-of-Bread_Part-1_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.mp3$",
        )

    def test_make_output_filename_falls_back_to_text(self):
        name = output_files.make_output_filename("Cut the chord to this idea.", "", "")

        self.assertTrue(name.startswith("Cut-the-chord-to-this_"))
        self.assertTrue(name.endswith(".mp3"))

    def test_split_into_items_preserves_paragraph_break_marker(self):
        items = text_splitter.split_into_items("First sentence.\n\nSecond sentence.")

        self.assertEqual(items, ["First sentence.", None, "Second sentence."])

    def test_split_into_timeline_items_tracks_offsets_and_pauses(self):
        text = "First sentence.\n\nSecond sentence."
        items = text_splitter.split_into_timeline_items(text, max_chars=750)

        self.assertEqual([item["type"] for item in items], ["speech", "pause", "speech"])
        self.assertEqual(items[0]["text"], "First sentence.")
        self.assertEqual(text[items[0]["text_start"] : items[0]["text_end"]], "First sentence.")
        self.assertEqual(items[1]["duration_ms"], 500)
        self.assertEqual(items[2]["text"], "Second sentence.")

    def test_generation_presets_control_chunk_size_and_steps(self):
        self.assertEqual(presets.get_generation_preset("Best")["chunk_size"], 500)
        self.assertEqual(presets.get_generation_preset("Fast")["nfe_step"], 24)
        self.assertEqual(
            presets.get_generation_preset("Not a real mode"),
            presets.GENERATION_PRESETS[presets.DEFAULT_PRESET],
        )

    def test_format_duration(self):
        self.assertEqual(presets.format_duration(9), "9s")
        self.assertEqual(presets.format_duration(75), "1m 15s")
        self.assertEqual(presets.format_duration(3661), "1h 01m")

    def test_chunk_text_splits_on_sentence_boundaries(self):
        chunks = text_splitter.chunk_text("One sentence. Two sentence. Three sentence.", max_chars=25)

        self.assertEqual(chunks, ["One sentence.", "Two sentence.", "Three sentence."])

    def test_make_output_filename_sanitises_special_chars(self):
        name = output_files.make_output_filename("ignored", "Book: A Story!", "Ch. 1")
        # Colons, exclamation marks, periods should not appear raw
        self.assertNotIn(":", name)
        self.assertNotIn("!", name)
        self.assertTrue(name.endswith(".mp3"))

    def test_make_output_filename_empty_text_falls_back_gracefully(self):
        name = output_files.make_output_filename("", "", "")
        self.assertTrue(name.endswith(".mp3"))
        # Should not raise and should return a non-empty filename
        self.assertTrue(len(name) > 4)

    def test_load_file_reads_txt(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as f:
            f.write("hello from a text file")
            path = f.name

        try:
            self.assertEqual(output_files.load_file(path), "hello from a text file")
        finally:
            Path(path).unlink(missing_ok=True)

    def test_load_file_warns_on_unsupported_extension(self):
        with tempfile.NamedTemporaryFile("w", suffix=".docx", delete=False) as f:
            f.write("ignored")
            path = f.name
        try:
            result = output_files.load_file(path)
            # Returns a user-facing warning string rather than raising
            self.assertIn("⚠️", result)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_reference_text_helpers_round_trip_for_active_reference(self):
        original_reference = voices.REFERENCE
        original_reference_text = voices.REFERENCE_TEXT
        with tempfile.TemporaryDirectory() as tmp:
            voices.REFERENCE = Path(tmp) / "reference.wav"
            voices.REFERENCE.write_bytes(b"fake wav")
            voices.REFERENCE_TEXT = Path(tmp) / "reference.txt"
            try:
                voices.save_reference_text("  exact transcript  ")
                self.assertEqual(
                    voices.load_reference_text(str(voices.REFERENCE)),
                    "exact transcript",
                )
                self.assertEqual(voices.load_reference_text("/tmp/other.wav"), "")
            finally:
                voices.REFERENCE = original_reference
                voices.REFERENCE_TEXT = original_reference_text

    def test_reference_signature_changes_when_audio_or_transcript_changes(self):
        original_reference = voices.REFERENCE
        original_reference_text = voices.REFERENCE_TEXT
        with tempfile.TemporaryDirectory() as tmp:
            voices.REFERENCE = Path(tmp) / "reference.wav"
            voices.REFERENCE.write_bytes(b"first wav")
            voices.REFERENCE_TEXT = Path(tmp) / "reference.txt"
            try:
                voices.save_reference_text("first transcript")
                first = voices.reference_signature(str(voices.REFERENCE))

                voices.save_reference_text("second transcript")
                second = voices.reference_signature(str(voices.REFERENCE))
                self.assertNotEqual(first, second)

                voices.REFERENCE.write_bytes(b"changed wav")
                third = voices.reference_signature(str(voices.REFERENCE))
                self.assertNotEqual(second, third)
            finally:
                voices.REFERENCE = original_reference
                voices.REFERENCE_TEXT = original_reference_text
                voices.clear_reference_cache()

    def test_prepare_reference_uses_cache_until_reference_changes(self):
        original_reference = voices.REFERENCE
        original_reference_text = voices.REFERENCE_TEXT
        with tempfile.TemporaryDirectory() as tmp:
            voices.REFERENCE = Path(tmp) / "reference.wav"
            voices.REFERENCE.write_bytes(b"fake wav")
            voices.REFERENCE_TEXT = Path(tmp) / "reference.txt"
            try:
                voices.clear_reference_cache()
                voices.save_reference_text("first transcript")

                first = voices.prepare_reference(str(voices.REFERENCE))
                second = voices.prepare_reference(str(voices.REFERENCE))
                self.assertFalse(first.cache_hit)
                self.assertTrue(second.cache_hit)

                voices.save_reference_text("second transcript")
                third = voices.prepare_reference(str(voices.REFERENCE))
                self.assertFalse(third.cache_hit)
                self.assertEqual(third.ref_text, "second transcript")
            finally:
                voices.REFERENCE = original_reference
                voices.REFERENCE_TEXT = original_reference_text
                voices.clear_reference_cache()

    def test_reference_warning_only_for_active_reference_without_transcript(self):
        original_reference = voices.REFERENCE
        original_reference_text = voices.REFERENCE_TEXT
        with tempfile.TemporaryDirectory() as tmp:
            voices.REFERENCE = Path(tmp) / "reference.wav"
            voices.REFERENCE.write_bytes(b"fake wav")
            voices.REFERENCE_TEXT = Path(tmp) / "reference.txt"
            try:
                self.assertIn("transcript missing", voices.reference_warning(str(voices.REFERENCE)))
                voices.save_reference_text("spoken words")
                self.assertEqual(voices.reference_warning(str(voices.REFERENCE)), "")
                self.assertEqual(voices.reference_warning("/tmp/other.wav"), "")
            finally:
                voices.REFERENCE = original_reference
                voices.REFERENCE_TEXT = original_reference_text
                voices.clear_reference_cache()

    def test_save_voice_profile_creates_library_files(self):
        original_voices_dir = voices.VOICES_DIR
        with tempfile.TemporaryDirectory() as tmp:
            voices.VOICES_DIR = Path(tmp) / "voices"
            voices.VOICES_DIR.mkdir()
            clip = Path(tmp) / "clip.wav"
            clip.write_bytes(b"fake wav")
            try:
                profile = voices.save_voice_profile(
                    str(clip),
                    "Warm Narrator",
                    ref_text="spoken words",
                    notes="gentle tone",
                    source_file="/source/audio.wav",
                    clip_start_s=30,
                    clip_duration_s=12,
                )

                folder = voices.VOICES_DIR / profile.id
                self.assertTrue((folder / "reference.wav").exists())
                self.assertEqual((folder / "reference.txt").read_text(), "spoken words")
                payload = json.loads((folder / "metadata.json").read_text())
                self.assertEqual(payload["display_name"], "Warm Narrator")
                self.assertEqual(payload["notes"], "gentle tone")
                self.assertEqual(payload["clip_start_s"], 30.0)
                self.assertEqual(payload["clip_duration_s"], 12.0)
            finally:
                voices.VOICES_DIR = original_voices_dir
                voices.clear_reference_cache()

    def test_voice_profile_appears_in_voice_files_and_loads_transcript(self):
        original_voices_dir = voices.VOICES_DIR
        original_reference = voices.REFERENCE
        with tempfile.TemporaryDirectory() as tmp:
            voices.VOICES_DIR = Path(tmp) / "voices"
            voices.VOICES_DIR.mkdir()
            voices.REFERENCE = Path(tmp) / "missing-reference.wav"
            clip = Path(tmp) / "clip.wav"
            clip.write_bytes(b"fake wav")
            try:
                profile = voices.save_voice_profile(
                    str(clip),
                    "Library Voice",
                    ref_text="profile transcript",
                )

                voice_files = voices.get_voice_files()
                self.assertIn(profile.label, voice_files)
                self.assertEqual(voice_files[profile.label], profile.ref_audio)
                self.assertEqual(
                    voices.load_reference_text(profile.ref_audio),
                    "profile transcript",
                )
            finally:
                voices.VOICES_DIR = original_voices_dir
                voices.REFERENCE = original_reference
                voices.clear_reference_cache()

    def test_profile_reference_signature_changes_when_transcript_changes(self):
        original_voices_dir = voices.VOICES_DIR
        with tempfile.TemporaryDirectory() as tmp:
            voices.VOICES_DIR = Path(tmp) / "voices"
            voices.VOICES_DIR.mkdir()
            clip = Path(tmp) / "clip.wav"
            clip.write_bytes(b"fake wav")
            try:
                profile = voices.save_voice_profile(str(clip), "Cache Voice", "first")
                first = voices.reference_signature(profile.ref_audio)

                Path(profile.ref_audio).with_name("reference.txt").write_text(
                    "second",
                    encoding="utf-8",
                )
                second = voices.reference_signature(profile.ref_audio)

                self.assertNotEqual(first, second)
            finally:
                voices.VOICES_DIR = original_voices_dir
                voices.clear_reference_cache()

    def test_rename_voice_profile_updates_metadata_but_keeps_id(self):
        original_voices_dir = voices.VOICES_DIR
        with tempfile.TemporaryDirectory() as tmp:
            voices.VOICES_DIR = Path(tmp) / "voices"
            voices.VOICES_DIR.mkdir()
            clip = Path(tmp) / "clip.wav"
            clip.write_bytes(b"fake wav")
            try:
                profile = voices.save_voice_profile(str(clip), "Old Name", notes="old")
                updated = voices.rename_voice_profile(profile.id, "New Name", "new notes")

                self.assertEqual(updated.id, profile.id)
                self.assertEqual(updated.display_name, "New Name")
                self.assertEqual(updated.notes, "new notes")

                reloaded = voices.get_voice_profile(profile.id)
                self.assertIsNotNone(reloaded)
                self.assertEqual(reloaded.display_name, "New Name")
                self.assertEqual(reloaded.ref_text, profile.ref_text)
            finally:
                voices.VOICES_DIR = original_voices_dir
                voices.clear_reference_cache()

    def test_delete_voice_profile_removes_profile_folder(self):
        original_voices_dir = voices.VOICES_DIR
        with tempfile.TemporaryDirectory() as tmp:
            voices.VOICES_DIR = Path(tmp) / "voices"
            voices.VOICES_DIR.mkdir()
            clip = Path(tmp) / "clip.wav"
            clip.write_bytes(b"fake wav")
            try:
                profile = voices.save_voice_profile(str(clip), "Delete Me")
                folder = voices.VOICES_DIR / profile.id
                self.assertTrue(folder.exists())

                self.assertTrue(voices.delete_voice_profile(profile.id))
                self.assertFalse(folder.exists())
                self.assertFalse(voices.delete_voice_profile(profile.id))
            finally:
                voices.VOICES_DIR = original_voices_dir
                voices.clear_reference_cache()

    def test_chunk_text_handles_single_long_sentence(self):
        # A sentence longer than max_chars must still be returned (not dropped)
        long = "a" * 800
        chunks = text_splitter.chunk_text(long, max_chars=500)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], long)

    def test_split_into_timeline_items_custom_pause_ms(self):
        text = "Hello.\n\nWorld."
        items = text_splitter.split_into_timeline_items(text, max_chars=750, paragraph_pause_ms=1200)
        pause = next(i for i in items if i["type"] == "pause")
        self.assertEqual(pause["duration_ms"], 1200)

    def test_split_into_timeline_items_zero_pause(self):
        text = "Hello.\n\nWorld."
        items = text_splitter.split_into_timeline_items(text, max_chars=750, paragraph_pause_ms=0)
        pause = next(i for i in items if i["type"] == "pause")
        self.assertEqual(pause["duration_ms"], 0)

    def test_split_into_timeline_items_sentence_pause(self):
        text = "First sentence. Second sentence.\n\nNext paragraph."
        items = text_splitter.split_into_timeline_items(
            text,
            max_chars=750,
            paragraph_pause_ms=500,
            sentence_pause_ms=300,
        )

        self.assertEqual(
            [item["type"] for item in items],
            ["speech", "sentence_pause", "speech", "pause", "speech"],
        )
        sentence_pause = next(i for i in items if i["type"] == "sentence_pause")
        self.assertEqual(sentence_pause["duration_ms"], 300)

    def test_split_into_timeline_items_offsets_match_source(self):
        text = "First sentence.\n\nSecond sentence."
        items = text_splitter.split_into_timeline_items(text, max_chars=750)
        for item in (i for i in items if i["type"] == "speech"):
            self.assertGreaterEqual(item["text_start"], 0)
            self.assertLessEqual(item["text_end"], len(text))
            self.assertEqual(text[item["text_start"]:item["text_end"]], item["text"])

    def test_build_highlight_units_splits_sentences_inside_chunk(self):
        text = "First sentence. Second sentence."
        timeline = [
            {
                "type": "speech",
                "text": text,
                "chunk_index": 0,
                "text_start": 0,
                "text_end": len(text),
                "audio_start_ms": 0,
                "audio_end_ms": 3000,
            }
        ]

        units = text_splitter.build_highlight_units(timeline, text)

        self.assertEqual([unit["text"] for unit in units], ["First sentence.", "Second sentence."])
        self.assertEqual(units[0]["audio_start_ms"], 0)
        self.assertLess(units[0]["audio_end_ms"], 3000)
        self.assertEqual(units[1]["audio_end_ms"], 3000)
        self.assertEqual(units[0]["timing_estimate"], "proportional_by_characters")

    # ── metadata sidecar ──────────────────────────────────────────────────────

    def test_write_generation_metadata_creates_sidecar_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "Book_Part-1.mp3"
            audio_path.write_bytes(b"fake mp3")

            meta_path = metadata.write_generation_metadata(
                audio_path,
                source_text="Hello.",
                timeline=[
                    {
                        "type": "speech",
                        "text": "Hello.",
                        "text_start": 0,
                        "text_end": 6,
                        "audio_start_ms": 0,
                        "audio_end_ms": 1000,
                    }
                ],
                title="Book",
                part="Part 1",
                voice="Voice",
                speed=1.0,
                preset="Balanced",
                preset_settings={"chunk_size": 750, "nfe_step": 32},
                duration_ms=1000,
            )

            payload = json.loads(meta_path.read_text(encoding="utf-8"))

            self.assertEqual(meta_path, audio_path.with_suffix(".json"))
            self.assertEqual(payload["schema_version"], metadata.SCHEMA_VERSION)
            self.assertEqual(payload["output_filename"], "Book_Part-1.mp3")
            self.assertEqual(payload["source_text"], "Hello.")
            self.assertEqual(payload["timeline"][0]["audio_end_ms"], 1000)

    def test_write_generation_metadata_stores_pacing_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "Book.mp3"
            audio_path.write_bytes(b"fake mp3")

            meta_path = metadata.write_generation_metadata(
                audio_path,
                source_text="Hello.",
                timeline=[],
                title="Book",
                part="",
                voice="Voice",
                speed=1.0,
                preset="Balanced",
                preset_settings={"chunk_size": 750, "nfe_step": 32},
                duration_ms=0,
                paragraph_pause_ms=1200,
                sentence_pause_ms=300,
            )

            payload = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["paragraph_pause_ms"], 1200)
            self.assertEqual(payload["sentence_pause_ms"], 300)

    def test_write_generation_metadata_stores_project_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "Book.mp3"
            audio_path.write_bytes(b"fake mp3")

            meta_path = metadata.write_generation_metadata(
                audio_path,
                source_text="Hello.",
                timeline=[],
                title="Book",
                part="Chapter 1",
                voice="Voice",
                speed=1.0,
                preset="Balanced",
                preset_settings={"chunk_size": 750, "nfe_step": 32},
                duration_ms=0,
                project_id="project-1",
                chapter_id="chapter-1",
            )

            payload = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(
                payload["project"],
                {"project_id": "project-1", "chapter_id": "chapter-1"},
            )

    def test_metadata_path_for_audio_returns_json_sibling(self):
        self.assertEqual(
            metadata.metadata_path_for_audio("/some/path/Book.mp3"),
            Path("/some/path/Book.json"),
        )


if __name__ == "__main__":
    unittest.main()
