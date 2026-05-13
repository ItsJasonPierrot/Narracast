import tempfile
import unittest
from pathlib import Path

from narracast import projects


class ProjectStorageTests(unittest.TestCase):
    def test_create_list_load_and_delete_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            project = projects.create_project(
                "Romans",
                author="Paul",
                voice="Narrator",
                speed=1.1,
                notes="Study reading",
                root=root,
            )

            self.assertEqual(project["title"], "Romans")
            self.assertEqual(project["author"], "Paul")
            self.assertEqual(project["voice"], "Narrator")
            self.assertEqual(project["speed"], 1.1)
            self.assertTrue((root / f"{project['id']}.json").exists())

            listed = projects.list_projects(root)
            self.assertEqual([p["id"] for p in listed], [project["id"]])
            self.assertEqual(projects.load_project(project["id"], root)["title"], "Romans")

            self.assertTrue(projects.delete_project(project["id"], root))
            self.assertIsNone(projects.load_project(project["id"], root))

    def test_add_update_mark_and_delete_chapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = projects.create_project("Book", root=root)

            chapter = projects.add_chapter(
                project["id"],
                "Chapter 1",
                "In the beginning.",
                import_source={
                    "import_id": "import-1",
                    "kind": "file",
                    "name": "book.txt",
                    "path": "/tmp/book.txt",
                    "split_method": "heading",
                    "split_marker": "",
                    "chapter_index": "1",
                    "chapter_count": 2,
                    "imported_at": 123.45,
                    "ignored": "nope",
                },
                root=root,
            )

            self.assertIsNotNone(chapter)
            loaded = projects.load_project(project["id"], root)
            self.assertEqual(len(loaded["chapters"]), 1)
            self.assertEqual(loaded["chapters"][0]["status"], "draft")
            self.assertEqual(
                loaded["chapters"][0]["import_source"],
                {
                    "import_id": "import-1",
                    "kind": "file",
                    "name": "book.txt",
                    "path": "/tmp/book.txt",
                    "split_method": "heading",
                    "chapter_index": 1,
                    "chapter_count": 2,
                    "imported_at": 123.45,
                },
            )

            updated = projects.update_chapter(
                project["id"],
                chapter["id"],
                title="Chapter One",
                text="Updated text.",
                root=root,
            )
            self.assertEqual(updated["title"], "Chapter One")
            self.assertEqual(updated["text"], "Updated text.")

            projects.mark_chapter_queued(project["id"], chapter["id"], root=root)
            self.assertEqual(
                projects.load_project(project["id"], root)["chapters"][0]["status"],
                "queued",
            )

            projects.mark_chapter_generated(
                project["id"],
                chapter["id"],
                "/tmp/chapter.mp3",
                root=root,
            )
            generated = projects.load_project(project["id"], root)["chapters"][0]
            self.assertEqual(generated["status"], "generated")
            self.assertEqual(generated["output_path"], "/tmp/chapter.mp3")

            self.assertTrue(projects.delete_chapter(project["id"], chapter["id"], root=root))
            self.assertEqual(projects.load_project(project["id"], root)["chapters"], [])

    def test_clean_project_recovers_from_malformed_chapters(self):
        clean = projects.clean_project(
            {
                "title": "",
                "speed": "1.25",
                "chapters": [
                    {
                        "title": "",
                        "text": "body",
                        "import_source": {
                            "kind": "paste",
                            "chapter_index": "bad",
                            "imported_at": "bad",
                        },
                    },
                    "bad",
                ],
            }
        )

        self.assertEqual(clean["title"], "Untitled project")
        self.assertEqual(clean["speed"], 1.25)
        self.assertEqual(len(clean["chapters"]), 1)
        self.assertEqual(clean["chapters"][0]["title"], "Untitled chapter")
        self.assertEqual(clean["chapters"][0]["import_source"], {"kind": "paste"})

    def test_rebuild_sessions_groups_chapters_and_tracks_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = projects.create_project("Book", root=root)
            first = projects.add_chapter(project["id"], "One", "word " * 100, root=root)
            second = projects.add_chapter(project["id"], "Two", "word " * 100, root=root)

            sessions = projects.rebuild_sessions(project["id"], target_minutes=1, root=root)

            self.assertEqual(len(sessions), 2)
            loaded = projects.load_project(project["id"], root)
            self.assertEqual(len(loaded["sessions"]), 2)
            self.assertEqual(projects.session_progress(loaded, loaded["sessions"][0]), (0, 1))

            projects.mark_chapter_generated(
                project["id"],
                first["id"],
                "/tmp/one.mp3",
                root=root,
            )
            loaded = projects.load_project(project["id"], root)
            self.assertIsNotNone(projects.next_unfinished_session(loaded))
            self.assertEqual(projects.session_progress(loaded, loaded["sessions"][0]), (1, 1))

            projects.mark_session_complete(project["id"], loaded["sessions"][1]["id"], root=root)
            loaded = projects.load_project(project["id"], root)
            self.assertEqual(projects.session_progress(loaded, loaded["sessions"][1]), (1, 1))
            self.assertIsNone(projects.next_unfinished_session(loaded))

    def test_update_split_and_merge_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = projects.create_project("Book", root=root)
            first = projects.add_chapter(project["id"], "One", "word " * 10, root=root)
            second = projects.add_chapter(project["id"], "Two", "word " * 10, root=root)
            third = projects.add_chapter(project["id"], "Three", "word " * 10, root=root)
            sessions = projects.rebuild_sessions(project["id"], target_minutes=20, root=root)
            session_id = sessions[0]["id"]

            renamed = projects.update_session(
                project["id"],
                session_id,
                title="Morning reading",
                root=root,
            )
            self.assertEqual(renamed["title"], "Morning reading")

            split = projects.split_session_after_chapter(
                project["id"],
                session_id,
                first["id"],
                root=root,
            )
            self.assertIsNotNone(split)
            loaded = projects.load_project(project["id"], root)
            self.assertEqual(len(loaded["sessions"]), 2)
            self.assertEqual(loaded["sessions"][0]["chapter_ids"], [first["id"]])
            self.assertEqual(
                loaded["sessions"][1]["chapter_ids"],
                [second["id"], third["id"]],
            )

            merged = projects.merge_session_with_next(project["id"], session_id, root=root)
            self.assertIsNotNone(merged)
            loaded = projects.load_project(project["id"], root)
            self.assertEqual(len(loaded["sessions"]), 1)
            self.assertEqual(
                loaded["sessions"][0]["chapter_ids"],
                [first["id"], second["id"], third["id"]],
            )

    def test_refresh_project_outputs_marks_missing_and_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = Path(tmp) / "chapter.mp3"
            output.write_bytes(b"fake mp3")
            project = projects.create_project("Book", root=root)
            first = projects.add_chapter(project["id"], "One", "text", root=root)
            second = projects.add_chapter(project["id"], "Two", "text", root=root)
            projects.update_chapter(
                project["id"],
                first["id"],
                status="queued",
                output_path=str(output),
                root=root,
            )
            projects.update_chapter(
                project["id"],
                second["id"],
                status="generated",
                output_path=str(Path(tmp) / "missing.mp3"),
                root=root,
            )

            refreshed = projects.refresh_project_outputs(project["id"], root=root)
            chapters = {chapter["id"]: chapter for chapter in refreshed["chapters"]}

            self.assertEqual(chapters[first["id"]]["status"], "generated")
            self.assertEqual(chapters[second["id"]]["status"], "missing")


class ProjectSummaryTests(unittest.TestCase):
    def test_empty_project_has_zero_totals(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = projects.create_project("Empty", root=Path(tmp))
            summary = projects.project_summary(project)
            self.assertEqual(summary["total"], 0)
            self.assertEqual(summary["counts"], {})
            self.assertEqual(summary["estimated_remaining_s"], 0)

    def test_counts_chapters_by_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = projects.create_project("Book", root=root)
            ch1 = projects.add_chapter(project["id"], "One", "word " * 50, root=root)
            ch2 = projects.add_chapter(project["id"], "Two", "word " * 50, root=root)
            ch3 = projects.add_chapter(project["id"], "Three", "word " * 50, root=root)
            projects.update_chapter(project["id"], ch3["id"], status="generated", root=root)
            projects.update_chapter(project["id"], ch2["id"], status="queued", root=root)
            loaded = projects.load_project(project["id"], root)
            summary = projects.project_summary(loaded)
            self.assertEqual(summary["total"], 3)
            self.assertEqual(summary["counts"]["draft"], 1)
            self.assertEqual(summary["counts"]["queued"], 1)
            self.assertEqual(summary["counts"]["generated"], 1)

    def test_estimated_remaining_excludes_generated_and_queued(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = projects.create_project("Book", root=root)
            ch1 = projects.add_chapter(project["id"], "Draft", "word " * 300, root=root)
            ch2 = projects.add_chapter(project["id"], "Done", "word " * 300, root=root)
            projects.update_chapter(project["id"], ch2["id"], status="generated", root=root)
            loaded = projects.load_project(project["id"], root)
            summary = projects.project_summary(loaded)
            # Only the draft chapter contributes to remaining estimate
            draft_only = projects.estimate_chapter_duration_s(
                next(c for c in loaded["chapters"] if c["id"] == ch1["id"])
            )
            self.assertEqual(summary["estimated_remaining_s"], draft_only)

    def test_next_action_when_all_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = projects.create_project("Book", root=root)
            ch = projects.add_chapter(project["id"], "One", "text", root=root)
            projects.update_chapter(project["id"], ch["id"], status="generated", root=root)
            loaded = projects.load_project(project["id"], root)
            summary = projects.project_summary(loaded)
            self.assertIn("generated", summary["next_action"].lower())

    def test_next_action_suggests_queue_when_drafts_remain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = projects.create_project("Book", root=root)
            projects.add_chapter(project["id"], "One", "text", root=root)
            loaded = projects.load_project(project["id"], root)
            summary = projects.project_summary(loaded)
            self.assertIn("queue", summary["next_action"].lower())


class SessionReadableChaptersTests(unittest.TestCase):
    def test_returns_existing_paths_in_session_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            p1 = Path(tmp) / "ch1.mp3"
            p2 = Path(tmp) / "ch2.mp3"
            p1.write_bytes(b"fake")
            p2.write_bytes(b"fake")
            project = {
                "chapters": [
                    {"id": "ch1", "status": "generated", "output_path": str(p1)},
                    {"id": "ch2", "status": "generated", "output_path": str(p2)},
                    {"id": "ch3", "status": "draft", "output_path": ""},
                ],
                "sessions": [],
            }
            session = {"id": "s1", "chapter_ids": ["ch1", "ch2", "ch3"]}
            result = projects.session_readable_chapters(project, session)
            self.assertEqual(result, [str(p1), str(p2)])

    def test_skips_chapters_with_missing_output_files(self):
        project = {
            "chapters": [
                {
                    "id": "ch1",
                    "status": "generated",
                    "output_path": "/nonexistent/path.mp3",
                }
            ],
            "sessions": [],
        }
        session = {"id": "s1", "chapter_ids": ["ch1"]}
        result = projects.session_readable_chapters(project, session)
        self.assertEqual(result, [])

    def test_respects_session_chapter_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            p1 = Path(tmp) / "first.mp3"
            p2 = Path(tmp) / "second.mp3"
            p1.write_bytes(b"fake")
            p2.write_bytes(b"fake")
            project = {
                "chapters": [
                    {"id": "ch2", "status": "generated", "output_path": str(p2)},
                    {"id": "ch1", "status": "generated", "output_path": str(p1)},
                ],
                "sessions": [],
            }
            # session lists ch1 before ch2
            session = {"id": "s1", "chapter_ids": ["ch1", "ch2"]}
            result = projects.session_readable_chapters(project, session)
            self.assertEqual(result, [str(p1), str(p2)])

    def test_returns_empty_for_empty_session(self):
        project = {"chapters": [], "sessions": []}
        session = {"id": "s1", "chapter_ids": []}
        result = projects.session_readable_chapters(project, session)
        self.assertEqual(result, [])

    def test_skips_chapters_not_in_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            p1 = Path(tmp) / "ch1.mp3"
            p1.write_bytes(b"fake")
            project = {
                "chapters": [
                    {"id": "ch1", "status": "generated", "output_path": str(p1)}
                ],
                "sessions": [],
            }
            # session references a chapter that doesn't exist in the project
            session = {"id": "s1", "chapter_ids": ["ch1", "ghost_id"]}
            result = projects.session_readable_chapters(project, session)
            self.assertEqual(result, [str(p1)])


if __name__ == "__main__":
    unittest.main()
