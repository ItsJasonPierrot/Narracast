"""Tests for narracast.mp3_folder_import."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from narracast.mp3_folder_import import (
    FolderScanItem,
    _chapter_title_from_sidecar,
    _natural_key,
    _title_from_filename,
    import_mp3_folder,
    scan_mp3_folder,
)
from narracast.projects import create_project, load_project


def _make_mp3(folder: Path, name: str) -> Path:
    """Write a tiny fake MP3 and return its path."""
    p = folder / name
    p.write_bytes(b"ID3" + b"\x00" * 100)
    return p


def _make_sidecar(mp3_path: Path, **fields) -> Path:
    """Write a minimal sidecar JSON next to *mp3_path*."""
    defaults = {
        "schema_version": 2,
        "source_text": "Hello world.",
        "title": "My Book",
        "part": "Chapter 1",
        "voice": "warm",
        "speed": 1.0,
        "duration_ms": 3000,
        "timeline": [],
    }
    defaults.update(fields)
    p = mp3_path.with_suffix(".json")
    p.write_text(json.dumps(defaults), encoding="utf-8")
    return p


# ── Unit tests for helpers ────────────────────────────────────────────────────

class TestNaturalKey(unittest.TestCase):
    def test_numbers_sort_numerically(self) -> None:
        paths = [Path(f"chapter{n}.mp3") for n in [10, 2, 1]]
        self.assertEqual(
            sorted(paths, key=_natural_key),
            [Path("chapter1.mp3"), Path("chapter2.mp3"), Path("chapter10.mp3")],
        )

    def test_mixed_text_and_numbers(self) -> None:
        paths = [Path("Part 10.mp3"), Path("Part 2.mp3"), Path("Part 1.mp3")]
        self.assertEqual(
            sorted(paths, key=_natural_key),
            [Path("Part 1.mp3"), Path("Part 2.mp3"), Path("Part 10.mp3")],
        )


class TestTitleFromFilename(unittest.TestCase):
    def test_underscores_become_spaces(self) -> None:
        self.assertEqual(_title_from_filename("chapter_one"), "Chapter One")

    def test_hyphens_become_spaces(self) -> None:
        self.assertEqual(_title_from_filename("my-book-part-1"), "My Book Part 1")

    def test_leading_date_stripped(self) -> None:
        result = _title_from_filename("2024-01-15 chapter one")
        self.assertNotIn("2024", result)

    def test_empty_stem_returns_stem(self) -> None:
        self.assertEqual(_title_from_filename(""), "")


class TestChapterTitleFromSidecar(unittest.TestCase):
    def test_both_title_and_part(self) -> None:
        self.assertEqual(
            _chapter_title_from_sidecar({"title": "My Book", "part": "Chapter 1"}, "fallback"),
            "My Book — Chapter 1",
        )

    def test_only_title(self) -> None:
        self.assertEqual(
            _chapter_title_from_sidecar({"title": "My Book", "part": ""}, "fallback"),
            "My Book",
        )

    def test_only_part(self) -> None:
        self.assertEqual(
            _chapter_title_from_sidecar({"title": "", "part": "Chapter 1"}, "fallback"),
            "Chapter 1",
        )

    def test_neither_uses_fallback(self) -> None:
        self.assertEqual(
            _chapter_title_from_sidecar({}, "fallback"),
            "fallback",
        )


# ── scan_mp3_folder ───────────────────────────────────────────────────────────

class TestScanMp3Folder(unittest.TestCase):
    def test_empty_folder_returns_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            items = scan_mp3_folder(tmp)
        self.assertEqual(items, [])

    def test_non_directory_raises_value_error(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
            with self.assertRaises(ValueError):
                scan_mp3_folder(f.name)

    def test_non_mp3_files_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "notes.txt").write_text("ignored")
            Path(tmp, "cover.jpg").write_bytes(b"\xff\xd8")
            items = scan_mp3_folder(tmp)
        self.assertEqual(items, [])

    def test_mp3_without_sidecar_is_stub(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _make_mp3(Path(tmp), "chapter01.mp3")
            items = scan_mp3_folder(tmp)
        self.assertEqual(len(items), 1)
        self.assertFalse(items[0].has_sidecar)
        self.assertEqual(items[0].source_text, "")

    def test_mp3_with_sidecar_has_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = _make_mp3(Path(tmp), "chapter01.mp3")
            _make_sidecar(mp3, source_text="The quick brown fox.", title="Book", part="Ch 1")
            items = scan_mp3_folder(tmp)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertTrue(item.has_sidecar)
        self.assertEqual(item.source_text, "The quick brown fox.")
        self.assertEqual(item.title, "Book — Ch 1")
        self.assertEqual(item.voice, "warm")

    def test_corrupt_sidecar_treated_as_no_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = _make_mp3(Path(tmp), "chapter01.mp3")
            mp3.with_suffix(".json").write_text("not valid json!!!", encoding="utf-8")
            items = scan_mp3_folder(tmp)
        self.assertFalse(items[0].has_sidecar)

    def test_files_returned_in_natural_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for n in [10, 2, 1, 5]:
                _make_mp3(Path(tmp), f"ch{n:02d}.mp3")
            items = scan_mp3_folder(tmp)
        names = [item.mp3_path.name for item in items]
        self.assertEqual(names, ["ch01.mp3", "ch02.mp3", "ch05.mp3", "ch10.mp3"])

    def test_mixed_sidecar_and_no_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mp3a = _make_mp3(Path(tmp), "ch01.mp3")
            mp3b = _make_mp3(Path(tmp), "ch02.mp3")
            _make_sidecar(mp3a, source_text="Chapter one text.")
            items = scan_mp3_folder(tmp)
        self.assertTrue(items[0].has_sidecar)
        self.assertFalse(items[1].has_sidecar)

    def test_title_derived_from_filename_when_no_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _make_mp3(Path(tmp), "my_book_chapter_one.mp3")
            items = scan_mp3_folder(tmp)
        self.assertEqual(items[0].title, "My Book Chapter One")

    def test_subdirectories_not_traversed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sub = Path(tmp) / "subdir"
            sub.mkdir()
            _make_mp3(sub, "chapter01.mp3")  # inside subdir — should be ignored
            _make_mp3(Path(tmp), "main.mp3")
            items = scan_mp3_folder(tmp)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].mp3_path.name, "main.mp3")


# ── import_mp3_folder ─────────────────────────────────────────────────────────

class TestImportMp3Folder(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self._proj_dir = Path(self._tmp) / "projects"
        self._proj_dir.mkdir()
        self._mp3_dir = Path(self._tmp) / "audio"
        self._mp3_dir.mkdir()
        self._project = create_project("Test Book", root=self._proj_dir)
        self._project_id = self._project["id"]

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_empty_folder_returns_zero_total(self) -> None:
        summary, project = import_mp3_folder(
            self._project_id, self._mp3_dir, root=self._proj_dir
        )
        self.assertEqual(summary.total, 0)
        self.assertIsNotNone(project)
        self.assertEqual(len(project["chapters"]), 0)

    def test_nonexistent_project_returns_none(self) -> None:
        summary, project = import_mp3_folder(
            "doesnotexist", self._mp3_dir, root=self._proj_dir
        )
        self.assertIsNone(project)
        self.assertEqual(summary.total, 0)

    def test_invalid_folder_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            import_mp3_folder(
                self._project_id,
                "/this/does/not/exist",
                root=self._proj_dir,
            )

    def test_mp3s_with_sidecars_create_generated_chapters(self) -> None:
        for i in range(1, 4):
            mp3 = _make_mp3(self._mp3_dir, f"ch{i:02d}.mp3")
            _make_sidecar(mp3, title="My Book", part=f"Chapter {i}", source_text=f"Text {i}.")

        summary, project = import_mp3_folder(
            self._project_id, self._mp3_dir, root=self._proj_dir
        )

        self.assertEqual(summary.total, 3)
        self.assertEqual(summary.imported_with_sidecar, 3)
        self.assertEqual(summary.imported_as_stub, 0)
        chapters = project["chapters"]
        self.assertEqual(len(chapters), 3)
        for chapter in chapters:
            self.assertEqual(chapter["status"], "generated")
            self.assertTrue(chapter["output_path"].endswith(".mp3"))
            self.assertTrue(chapter["text"].startswith("Text "))

    def test_mp3s_without_sidecars_create_draft_stubs(self) -> None:
        for i in range(1, 3):
            _make_mp3(self._mp3_dir, f"ch{i:02d}.mp3")

        summary, project = import_mp3_folder(
            self._project_id, self._mp3_dir, root=self._proj_dir
        )

        self.assertEqual(summary.total, 2)
        self.assertEqual(summary.imported_as_stub, 2)
        self.assertEqual(summary.imported_with_sidecar, 0)
        for chapter in project["chapters"]:
            self.assertEqual(chapter["status"], "draft")
            self.assertEqual(chapter["text"], "")
            self.assertTrue(chapter["output_path"].endswith(".mp3"))

    def test_mixed_creates_both_generated_and_stubs(self) -> None:
        mp3a = _make_mp3(self._mp3_dir, "ch01.mp3")
        _make_sidecar(mp3a, source_text="With sidecar.")
        _make_mp3(self._mp3_dir, "ch02.mp3")

        summary, project = import_mp3_folder(
            self._project_id, self._mp3_dir, root=self._proj_dir
        )

        statuses = [c["status"] for c in project["chapters"]]
        self.assertIn("generated", statuses)
        self.assertIn("draft", statuses)
        self.assertEqual(summary.imported_with_sidecar, 1)
        self.assertEqual(summary.imported_as_stub, 1)

    def test_chapters_appended_in_natural_order(self) -> None:
        for n in [10, 2, 1]:
            _make_mp3(self._mp3_dir, f"chapter{n}.mp3")

        _, project = import_mp3_folder(
            self._project_id, self._mp3_dir, root=self._proj_dir
        )

        titles = [c["title"] for c in project["chapters"]]
        # Natural order: 1, 2, 10
        self.assertIn("1", titles[0])
        self.assertIn("10", titles[-1])

    def test_sessions_are_rebuilt_after_import(self) -> None:
        for i in range(1, 6):
            mp3 = _make_mp3(self._mp3_dir, f"ch{i:02d}.mp3")
            _make_sidecar(mp3, source_text="Long text " * 200, title="Book", part=f"Ch{i}")

        summary, project = import_mp3_folder(
            self._project_id, self._mp3_dir, root=self._proj_dir
        )

        self.assertGreater(summary.sessions_built, 0)
        self.assertGreater(len(project.get("sessions", [])), 0)

    def test_existing_chapters_preserved(self) -> None:
        from narracast.projects import add_chapter
        add_chapter(self._project_id, "Pre-existing", "Old text.", root=self._proj_dir)

        _make_mp3(self._mp3_dir, "ch01.mp3")
        _, project = import_mp3_folder(
            self._project_id, self._mp3_dir, root=self._proj_dir
        )

        titles = [c["title"] for c in project["chapters"]]
        self.assertIn("Pre-existing", titles)
        self.assertEqual(len(titles), 2)

    def test_import_source_is_recorded_on_chapter(self) -> None:
        _make_mp3(self._mp3_dir, "track.mp3")

        _, project = import_mp3_folder(
            self._project_id, self._mp3_dir, root=self._proj_dir
        )

        src = project["chapters"][0].get("import_source", {})
        self.assertEqual(src.get("kind"), "mp3_folder")
        self.assertIn("import_id", src)
        self.assertEqual(src.get("chapter_index"), 1)
        self.assertEqual(src.get("chapter_count"), 1)

    def test_all_chapters_share_same_import_id(self) -> None:
        for i in range(1, 4):
            _make_mp3(self._mp3_dir, f"ch{i:02d}.mp3")

        _, project = import_mp3_folder(
            self._project_id, self._mp3_dir, root=self._proj_dir
        )

        import_ids = {c["import_source"]["import_id"] for c in project["chapters"]}
        self.assertEqual(len(import_ids), 1)

    def test_chapter_title_from_sidecar_preferred_over_filename(self) -> None:
        mp3 = _make_mp3(self._mp3_dir, "some_ugly_filename_001.mp3")
        _make_sidecar(mp3, title="Beautiful Title", part="Part I", source_text="text")

        _, project = import_mp3_folder(
            self._project_id, self._mp3_dir, root=self._proj_dir
        )

        self.assertEqual(project["chapters"][0]["title"], "Beautiful Title — Part I")

    def test_chapter_output_path_is_absolute(self) -> None:
        _make_mp3(self._mp3_dir, "ch01.mp3")

        _, project = import_mp3_folder(
            self._project_id, self._mp3_dir, root=self._proj_dir
        )

        output_path = project["chapters"][0]["output_path"]
        self.assertTrue(Path(output_path).is_absolute())

    def test_project_persisted_to_disk(self) -> None:
        _make_mp3(self._mp3_dir, "ch01.mp3")

        import_mp3_folder(self._project_id, self._mp3_dir, root=self._proj_dir)

        reloaded = load_project(self._project_id, self._proj_dir)
        self.assertIsNotNone(reloaded)
        self.assertEqual(len(reloaded["chapters"]), 1)

    def test_speed_defaults_to_1_when_no_sidecar(self) -> None:
        _make_mp3(self._mp3_dir, "ch01.mp3")
        items = scan_mp3_folder(self._mp3_dir)
        self.assertEqual(items[0].speed, 1.0)

    def test_speed_read_from_sidecar(self) -> None:
        mp3 = _make_mp3(self._mp3_dir, "ch01.mp3")
        _make_sidecar(mp3, speed=1.25)
        items = scan_mp3_folder(self._mp3_dir)
        self.assertAlmostEqual(items[0].speed, 1.25)


if __name__ == "__main__":
    unittest.main()
