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
                root=root,
            )

            self.assertIsNotNone(chapter)
            loaded = projects.load_project(project["id"], root)
            self.assertEqual(len(loaded["chapters"]), 1)
            self.assertEqual(loaded["chapters"][0]["status"], "draft")

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
                "chapters": [{"title": "", "text": "body"}, "bad"],
            }
        )

        self.assertEqual(clean["title"], "Untitled project")
        self.assertEqual(clean["speed"], 1.25)
        self.assertEqual(len(clean["chapters"]), 1)
        self.assertEqual(clean["chapters"][0]["title"], "Untitled chapter")

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


if __name__ == "__main__":
    unittest.main()
