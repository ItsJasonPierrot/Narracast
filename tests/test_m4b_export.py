"""Tests for M4B audiobook export backend."""

import json
import tempfile
import unittest
from pathlib import Path

from narracast.m4b_export import (
    ChapterExportInfo,
    audit_project_chapters,
    build_ffmetadata,
)


def _fake_chapter(
    chapter_id="ch1",
    title="Chapter 1",
    output_path="",
    status="draft",
) -> dict:
    return {
        "id": chapter_id,
        "title": title,
        "output_path": output_path,
        "status": status,
        "text": "some text",
    }


class AuditProjectChaptersTests(unittest.TestCase):
    def test_ready_chapter_with_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = Path(tmp) / "ch1.mp3"
            mp3.write_bytes(b"fake audio")
            project = {
                "chapters": [
                    _fake_chapter(
                        output_path=str(mp3), status="generated"
                    )
                ]
            }
            result = audit_project_chapters(project)
            self.assertEqual(len(result), 1)
            self.assertTrue(result[0].ready)
            self.assertEqual(result[0].reason, "")
            self.assertEqual(result[0].output_path, str(mp3))

    def test_duration_read_from_sidecar_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = Path(tmp) / "ch1.mp3"
            mp3.write_bytes(b"fake audio")
            sidecar = Path(tmp) / "ch1.json"
            sidecar.write_text(
                json.dumps({"duration_ms": 123456}), encoding="utf-8"
            )
            project = {
                "chapters": [
                    _fake_chapter(output_path=str(mp3), status="generated")
                ]
            }
            result = audit_project_chapters(project)
            self.assertEqual(result[0].duration_ms, 123456)

    def test_not_ready_when_status_is_draft(self):
        project = {"chapters": [_fake_chapter(status="draft")]}
        result = audit_project_chapters(project)
        self.assertFalse(result[0].ready)
        self.assertIn("draft", result[0].reason.lower())

    def test_not_ready_when_output_path_empty(self):
        project = {
            "chapters": [_fake_chapter(status="generated", output_path="")]
        }
        result = audit_project_chapters(project)
        self.assertFalse(result[0].ready)
        self.assertIn("path", result[0].reason.lower())

    def test_not_ready_when_output_file_missing_on_disk(self):
        project = {
            "chapters": [
                _fake_chapter(
                    status="generated",
                    output_path="/nonexistent/audio.mp3",
                )
            ]
        }
        result = audit_project_chapters(project)
        self.assertFalse(result[0].ready)
        self.assertIn("not found", result[0].reason.lower())

    def test_empty_project_returns_empty_list(self):
        self.assertEqual(audit_project_chapters({"chapters": []}), [])

    def test_mixed_chapters(self):
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = Path(tmp) / "ok.mp3"
            mp3.write_bytes(b"audio")
            project = {
                "chapters": [
                    _fake_chapter(
                        chapter_id="ready",
                        status="generated",
                        output_path=str(mp3),
                    ),
                    _fake_chapter(chapter_id="draft", status="draft"),
                    _fake_chapter(
                        chapter_id="missing",
                        status="generated",
                        output_path="/gone.mp3",
                    ),
                ]
            }
            result = audit_project_chapters(project)
            self.assertEqual(len(result), 3)
            ready = [r for r in result if r.ready]
            not_ready = [r for r in result if not r.ready]
            self.assertEqual(len(ready), 1)
            self.assertEqual(len(not_ready), 2)
            self.assertEqual(ready[0].chapter_id, "ready")


class BuildFFMetadataTests(unittest.TestCase):
    def _make_chapter(self, chapter_id, title, duration_ms) -> ChapterExportInfo:
        return ChapterExportInfo(
            chapter_id=chapter_id,
            title=title,
            output_path="/fake/path.mp3",
            duration_ms=duration_ms,
            ready=True,
            reason="",
        )

    def test_starts_with_ffmetadata_header(self):
        project = {"title": "My Book", "author": "A. Author"}
        chapters = [self._make_chapter("ch1", "Chapter 1", 60_000)]
        result = build_ffmetadata(project, chapters)
        self.assertTrue(result.startswith(";FFMETADATA1"))

    def test_project_title_and_author_included(self):
        project = {"title": "Great Book", "author": "Jane Doe"}
        chapters = [self._make_chapter("ch1", "Chapter 1", 30_000)]
        result = build_ffmetadata(project, chapters)
        self.assertIn("title=Great Book", result)
        self.assertIn("artist=Jane Doe", result)

    def test_chapter_timestamps_accumulate_correctly(self):
        project = {"title": "Book"}
        chapters = [
            self._make_chapter("ch1", "Part One", 60_000),
            self._make_chapter("ch2", "Part Two", 90_000),
        ]
        result = build_ffmetadata(project, chapters)
        # Chapter 1: START=0, END=60000
        self.assertIn("START=0", result)
        self.assertIn("END=60000", result)
        # Chapter 2: START=60000, END=150000
        self.assertIn("START=60000", result)
        self.assertIn("END=150000", result)

    def test_chapter_title_in_metadata(self):
        project = {"title": "Book"}
        chapters = [self._make_chapter("ch1", "Genesis", 10_000)]
        result = build_ffmetadata(project, chapters)
        self.assertIn("title=Genesis", result)

    def test_equals_sign_in_chapter_title_is_escaped(self):
        project = {"title": "Book"}
        chapters = [self._make_chapter("ch1", "A=B", 10_000)]
        result = build_ffmetadata(project, chapters)
        self.assertIn(r"title=A\=B", result)

    def test_semicolon_in_chapter_title_is_escaped(self):
        project = {"title": "Book"}
        chapters = [self._make_chapter("ch1", "A;B", 10_000)]
        result = build_ffmetadata(project, chapters)
        self.assertIn(r"title=A\;B", result)

    def test_chapter_block_markers_present(self):
        project = {"title": "Book"}
        chapters = [self._make_chapter("ch1", "Ch", 5_000)]
        result = build_ffmetadata(project, chapters)
        self.assertIn("[CHAPTER]", result)
        self.assertIn("TIMEBASE=1/1000", result)


class ExportM4BValidationTests(unittest.TestCase):
    def test_raises_value_error_when_no_chapters_ready(self):
        from narracast.m4b_export import export_m4b

        project = {
            "title": "Empty",
            "chapters": [_fake_chapter(status="draft")],
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "out.m4b")
            with self.assertRaises(ValueError) as ctx:
                export_m4b(project, out)
            self.assertIn("No chapters", str(ctx.exception))

    def test_raises_value_error_when_skip_missing_false_and_partial(self):
        from narracast.m4b_export import export_m4b

        with tempfile.TemporaryDirectory() as tmp:
            mp3 = Path(tmp) / "ok.mp3"
            mp3.write_bytes(b"audio")
            project = {
                "title": "Book",
                "chapters": [
                    _fake_chapter(
                        chapter_id="ready",
                        status="generated",
                        output_path=str(mp3),
                    ),
                    _fake_chapter(
                        chapter_id="missing",
                        status="generated",
                        output_path="/nonexistent/file.mp3",
                    ),
                ],
            }
            out = str(Path(tmp) / "out.m4b")
            with self.assertRaises(ValueError) as ctx:
                export_m4b(project, out, skip_missing=False)
            self.assertIn("not ready", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
