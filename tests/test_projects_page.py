import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from narracast import projects
from narracast.ui.pages import projects_page
from narracast.ui.pages.projects_page import ProjectsPage


def _qt_app():
    app = QApplication.instance()
    return app or QApplication([])


class ProjectsPageTests(unittest.TestCase):
    def _bind_project_storage(self, root: Path):
        original_create = projects_page.create_project
        original_load = projects_page.load_project
        original_list = projects_page.list_projects
        original_add_chapter = projects_page.add_chapter
        original_rebuild_sessions = projects_page.rebuild_sessions
        projects_page.create_project = lambda *args, **kwargs: projects.create_project(
            *args,
            **kwargs,
            root=root,
        )
        projects_page.load_project = lambda project_id: projects.load_project(project_id, root=root)
        projects_page.list_projects = lambda: projects.list_projects(root=root)
        projects_page.add_chapter = lambda project_id, title, text, **kwargs: projects.add_chapter(
            project_id,
            title,
            text,
            **kwargs,
            root=root,
        )
        projects_page.rebuild_sessions = lambda project_id: projects.rebuild_sessions(
            project_id,
            root=root,
        )
        self.addCleanup(setattr, projects_page, "create_project", original_create)
        self.addCleanup(setattr, projects_page, "load_project", original_load)
        self.addCleanup(setattr, projects_page, "list_projects", original_list)
        self.addCleanup(setattr, projects_page, "add_chapter", original_add_chapter)
        self.addCleanup(setattr, projects_page, "rebuild_sessions", original_rebuild_sessions)

    def test_import_text_as_chapters_creates_reviewable_drafts(self):
        _qt_app()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._bind_project_storage(root)
            project = projects.create_project("Book", root=root)
            page = ProjectsPage()
            page._load_project(project["id"])

            page._import_text_as_chapters(
                "Chapter 1\nFirst.\n\nChapter 2\nSecond.",
                fallback_title="Book",
            )

            loaded = projects.load_project(project["id"], root=root)
            self.assertEqual(
                [chapter["title"] for chapter in loaded["chapters"]],
                ["Chapter 1", "Chapter 2"],
            )
            self.assertEqual(len(loaded["sessions"]), 1)
            sources = [chapter["import_source"] for chapter in loaded["chapters"]]
            self.assertEqual({source["kind"] for source in sources}, {"paste"})
            self.assertEqual({source["split_method"] for source in sources}, {"heading"})
            self.assertEqual([source["chapter_index"] for source in sources], [1, 2])
            self.assertEqual({source["chapter_count"] for source in sources}, {2})
            self.assertIn("Imported 2 draft chapters", page.status_label.text())
            self.assertIn("Built 1 session", page.status_label.text())
            page.deleteLater()

    def test_import_text_as_chapters_falls_back_to_single_chapter(self):
        _qt_app()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._bind_project_storage(root)
            project = projects.create_project("Book", root=root)
            page = ProjectsPage()
            page._load_project(project["id"])

            page._import_text_as_chapters(
                "Plain text without headings.",
                fallback_title="Whole text",
            )

            loaded = projects.load_project(project["id"], root=root)
            self.assertEqual(len(loaded["chapters"]), 1)
            self.assertEqual(loaded["chapters"][0]["title"], "Whole text")
            self.assertEqual(loaded["chapters"][0]["text"], "Plain text without headings.")
            self.assertEqual(loaded["chapters"][0]["import_source"]["split_method"], "fallback")
            self.assertEqual(len(loaded["sessions"]), 1)
            page.deleteLater()


if __name__ == "__main__":
    unittest.main()
