"""Projects page — organize books, chapters, and queued generation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from narracast.chapter_splitter import split_chapters
from narracast.projects import (
    add_chapter,
    create_project,
    delete_chapter,
    delete_project,
    list_projects,
    load_project,
    mark_session_complete,
    next_unfinished_session,
    rebuild_sessions,
    session_progress,
    update_chapter,
    update_project,
)
from narracast.queue_manager import add_to_queue
from narracast.voices import get_voice_files
from narracast.ui.widgets import Card, MutedLabel, SectionLabel


class ProjectsPage(QWidget):
    """Project / Book Mode management page."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._projects: list[dict] = []
        self._current_project: dict | None = None
        self._current_chapter_id = ""
        self._build_ui()
        self.refresh()

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        h2 = QLabel("Projects")
        h2.setObjectName("h2")
        root.addWidget(h2)
        root.addWidget(MutedLabel("Organize long books, chapters, and queued generation."))

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, stretch=1)

        # Left: project list
        left = Card()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(10)
        left_layout.addWidget(SectionLabel("Library"))

        self.project_tree = QTreeWidget()
        self.project_tree.setColumnCount(3)
        self.project_tree.setHeaderLabels(["Project", "Chapters", "Updated"])
        self.project_tree.setRootIsDecorated(False)
        self.project_tree.setMinimumWidth(320)
        self.project_tree.itemSelectionChanged.connect(self._on_project_selection)
        left_layout.addWidget(self.project_tree, stretch=1)

        project_btns = QHBoxLayout()
        self.new_project_btn = QPushButton("New")
        self.new_project_btn.clicked.connect(self._new_project)
        self.delete_project_btn = QPushButton("Delete")
        self.delete_project_btn.setObjectName("danger")
        self.delete_project_btn.clicked.connect(self._delete_project)
        project_btns.addWidget(self.new_project_btn)
        project_btns.addWidget(self.delete_project_btn)
        left_layout.addLayout(project_btns)
        splitter.addWidget(left)

        # Right: project details + chapters
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 0, 0, 0)
        right_layout.setSpacing(12)

        details = Card()
        details_layout = QFormLayout(details)
        details_layout.setContentsMargins(16, 14, 16, 14)
        details_layout.setSpacing(8)
        details_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Project title")
        details_layout.addRow("Title:", self.title_edit)

        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText("Author / source")
        details_layout.addRow("Author:", self.author_edit)

        self.voice_combo = QComboBox()
        details_layout.addRow("Voice:", self.voice_combo)

        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.75", "0.90", "1.00", "1.10", "1.25", "1.50"])
        self.speed_combo.setCurrentText("1.00")
        details_layout.addRow("Speed:", self.speed_combo)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Notes")
        self.notes_edit.setMaximumHeight(72)
        details_layout.addRow("Notes:", self.notes_edit)

        save_row = QHBoxLayout()
        self.save_project_btn = QPushButton("Save project")
        self.save_project_btn.setObjectName("primary")
        self.save_project_btn.clicked.connect(self._save_project)
        save_row.addStretch()
        save_row.addWidget(self.save_project_btn)
        details_layout.addRow("", save_row)
        right_layout.addWidget(details)

        chapter_card = Card()
        chapter_layout = QVBoxLayout(chapter_card)
        chapter_layout.setContentsMargins(16, 16, 16, 16)
        chapter_layout.setSpacing(10)
        chapter_layout.addWidget(SectionLabel("Chapters"))

        self.chapter_tree = QTreeWidget()
        self.chapter_tree.setColumnCount(4)
        self.chapter_tree.setHeaderLabels(["Chapter", "Status", "Words", "Output"])
        self.chapter_tree.header().resizeSection(1, 90)
        self.chapter_tree.header().resizeSection(2, 70)
        self.chapter_tree.header().resizeSection(3, 90)
        self.chapter_tree.setRootIsDecorated(False)
        self.chapter_tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.chapter_tree.itemSelectionChanged.connect(self._on_chapter_selection)
        chapter_layout.addWidget(self.chapter_tree, stretch=1)

        self.chapter_title_edit = QLineEdit()
        self.chapter_title_edit.setPlaceholderText("Chapter title")
        chapter_layout.addWidget(self.chapter_title_edit)

        self.chapter_text_edit = QTextEdit()
        self.chapter_text_edit.setPlaceholderText("Chapter text")
        self.chapter_text_edit.setMinimumHeight(160)
        chapter_layout.addWidget(self.chapter_text_edit, stretch=1)

        split_row = QHBoxLayout()
        self.split_marker_edit = QLineEdit()
        self.split_marker_edit.setPlaceholderText("Optional custom split marker")
        split_row.addWidget(self.split_marker_edit, stretch=1)
        self.split_chapters_btn = QPushButton("Split pasted text")
        self.split_chapters_btn.clicked.connect(self._split_pasted_text)
        split_row.addWidget(self.split_chapters_btn)
        chapter_layout.addLayout(split_row)

        chapter_btns = QHBoxLayout()
        self.add_chapter_btn = QPushButton("Add chapter")
        self.add_chapter_btn.clicked.connect(self._add_chapter)
        self.update_chapter_btn = QPushButton("Update chapter")
        self.update_chapter_btn.clicked.connect(self._update_chapter)
        self.delete_chapter_btn = QPushButton("Delete chapter")
        self.delete_chapter_btn.setObjectName("danger")
        self.delete_chapter_btn.clicked.connect(self._delete_chapter)
        self.queue_chapter_btn = QPushButton("Queue chapter")
        self.queue_chapter_btn.setObjectName("primary")
        self.queue_chapter_btn.clicked.connect(self._queue_selected_chapter)
        self.queue_all_btn = QPushButton("Queue all drafts")
        self.queue_all_btn.clicked.connect(self._queue_all_drafts)
        for btn in [
            self.add_chapter_btn,
            self.update_chapter_btn,
            self.delete_chapter_btn,
            self.queue_chapter_btn,
            self.queue_all_btn,
        ]:
            chapter_btns.addWidget(btn)
        chapter_btns.addStretch()
        chapter_layout.addLayout(chapter_btns)

        chapter_layout.addWidget(SectionLabel("Reading sessions"))
        self.session_tree = QTreeWidget()
        self.session_tree.setColumnCount(3)
        self.session_tree.setHeaderLabels(["Session", "Progress", "Status"])
        self.session_tree.setRootIsDecorated(False)
        self.session_tree.setMaximumHeight(120)
        chapter_layout.addWidget(self.session_tree)

        session_btns = QHBoxLayout()
        self.build_sessions_btn = QPushButton("Build sessions")
        self.build_sessions_btn.clicked.connect(self._build_sessions)
        self.complete_session_btn = QPushButton("Mark complete")
        self.complete_session_btn.clicked.connect(self._mark_session_complete)
        self.resume_session_btn = QPushButton("Resume next")
        self.resume_session_btn.setObjectName("primary")
        self.resume_session_btn.clicked.connect(self._resume_next_session)
        for btn in [self.build_sessions_btn, self.complete_session_btn, self.resume_session_btn]:
            session_btns.addWidget(btn)
        session_btns.addStretch()
        chapter_layout.addLayout(session_btns)

        self.status_label = MutedLabel("")
        chapter_layout.addWidget(self.status_label)
        right_layout.addWidget(chapter_card, stretch=1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        self._set_detail_enabled(False)

    # ── Refresh / selection ───────────────────────────────────────────────

    def refresh(self) -> None:
        self._populate_voices()
        self._projects = list_projects()
        self.project_tree.clear()
        for project in self._projects:
            item = QTreeWidgetItem(
                [
                    project["title"],
                    str(len(project["chapters"])),
                    self._format_time(project.get("updated_at")),
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, project["id"])
            self.project_tree.addTopLevelItem(item)

    def _populate_voices(self) -> None:
        current = self.voice_combo.currentText() if hasattr(self, "voice_combo") else ""
        self.voice_combo.clear()
        self.voice_combo.addItems(list(get_voice_files().keys()))
        if current:
            idx = self.voice_combo.findText(current)
            if idx >= 0:
                self.voice_combo.setCurrentIndex(idx)

    def _on_project_selection(self) -> None:
        items = self.project_tree.selectedItems()
        if not items:
            self._current_project = None
            self._set_detail_enabled(False)
            return
        project_id = items[0].data(0, Qt.ItemDataRole.UserRole)
        self._load_project(project_id)

    def _load_project(self, project_id: str) -> None:
        self._current_project = load_project(project_id)
        self._current_chapter_id = ""
        if self._current_project is None:
            self._set_detail_enabled(False)
            return
        self._set_detail_enabled(True)
        self.title_edit.setText(self._current_project["title"])
        self.author_edit.setText(self._current_project["author"])
        self.notes_edit.setPlainText(self._current_project["notes"])
        voice = self._current_project.get("voice", "")
        idx = self.voice_combo.findText(voice)
        if idx >= 0:
            self.voice_combo.setCurrentIndex(idx)
        self.speed_combo.setCurrentText(f"{float(self._current_project.get('speed', 1.0)):.2f}")
        self._populate_chapters()
        self._populate_sessions()

    def _populate_chapters(self) -> None:
        self.chapter_tree.clear()
        if not self._current_project:
            return
        for chapter in self._current_project["chapters"]:
            words = len(chapter.get("text", "").split())
            output = "yes" if chapter.get("output_path") else ""
            item = QTreeWidgetItem(
                [chapter["title"], chapter["status"], str(words), output]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, chapter["id"])
            self.chapter_tree.addTopLevelItem(item)

    def _populate_sessions(self) -> None:
        self.session_tree.clear()
        if not self._current_project:
            return
        for session in self._current_project.get("sessions", []):
            done, total = session_progress(self._current_project, session)
            item = QTreeWidgetItem(
                [session["title"], f"{done}/{total}", session["status"]]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, session["id"])
            self.session_tree.addTopLevelItem(item)

    def _on_chapter_selection(self) -> None:
        chapter = self._selected_chapter()
        if not chapter:
            self._current_chapter_id = ""
            return
        self._current_chapter_id = chapter["id"]
        self.chapter_title_edit.setText(chapter["title"])
        self.chapter_text_edit.setPlainText(chapter["text"])

    # ── Project actions ───────────────────────────────────────────────────

    def _new_project(self) -> None:
        project = create_project("Untitled project")
        self.status_label.setText("Project created.")
        self.refresh()
        self._select_project(project["id"])

    def _save_project(self) -> None:
        if not self._current_project:
            return
        speed = float(self.speed_combo.currentText() or 1.0)
        project = update_project(
            self._current_project["id"],
            title=self.title_edit.text(),
            author=self.author_edit.text(),
            voice=self.voice_combo.currentText(),
            speed=speed,
            notes=self.notes_edit.toPlainText(),
        )
        if project:
            self.status_label.setText("Project saved.")
            self.refresh()
            self._select_project(project["id"])

    def _delete_project(self) -> None:
        if not self._current_project:
            return
        delete_project(self._current_project["id"])
        self._current_project = None
        self.status_label.setText("Project deleted.")
        self.refresh()
        self._set_detail_enabled(False)

    # ── Chapter actions ───────────────────────────────────────────────────

    def _add_chapter(self) -> None:
        if not self._current_project:
            return
        title = self.chapter_title_edit.text().strip() or "Untitled chapter"
        text = self.chapter_text_edit.toPlainText().strip()
        chapter = add_chapter(self._current_project["id"], title, text)
        if chapter:
            self.status_label.setText("Chapter added.")
            self._load_project(self._current_project["id"])
            self._select_chapter(chapter["id"])

    def _update_chapter(self) -> None:
        if not self._current_project or not self._current_chapter_id:
            return
        update_chapter(
            self._current_project["id"],
            self._current_chapter_id,
            title=self.chapter_title_edit.text(),
            text=self.chapter_text_edit.toPlainText(),
            status="draft",
        )
        self.status_label.setText("Chapter updated.")
        project_id = self._current_project["id"]
        chapter_id = self._current_chapter_id
        self._load_project(project_id)
        self._select_chapter(chapter_id)

    def _delete_chapter(self) -> None:
        if not self._current_project or not self._current_chapter_id:
            return
        delete_chapter(self._current_project["id"], self._current_chapter_id)
        self.status_label.setText("Chapter deleted.")
        self._load_project(self._current_project["id"])

    def _queue_selected_chapter(self) -> None:
        chapter = self._selected_chapter()
        if chapter:
            self._queue_chapter(chapter)

    def _split_pasted_text(self) -> None:
        if not self._current_project:
            return
        drafts = split_chapters(
            self.chapter_text_edit.toPlainText(),
            custom_marker=self.split_marker_edit.text(),
        )
        if not drafts:
            self.status_label.setText("No chapter headings or split markers found.")
            return
        project_id = self._current_project["id"]
        for draft in drafts:
            add_chapter(project_id, draft.title, draft.text)
        self.status_label.setText(
            f"Added {len(drafts)} chapter{'s' if len(drafts) != 1 else ''} for review."
        )
        self.chapter_title_edit.clear()
        self.chapter_text_edit.clear()
        self._load_project(project_id)

    def _queue_all_drafts(self) -> None:
        if not self._current_project:
            return
        count = 0
        for chapter in self._current_project["chapters"]:
            if chapter.get("status") in ("draft", "error") and chapter.get("text", "").strip():
                self._queue_chapter(chapter, quiet=True)
                count += 1
        self.status_label.setText(f"Queued {count} chapter{'s' if count != 1 else ''}.")
        self._load_project(self._current_project["id"])

    def _queue_chapter(self, chapter: dict, quiet: bool = False) -> None:
        if not self._current_project:
            return
        voice = self._current_project.get("voice") or self.voice_combo.currentText()
        msg = add_to_queue(
            chapter["text"],
            voice,
            float(self._current_project.get("speed") or 1.0),
            self._current_project["title"],
            chapter["title"],
            project_id=self._current_project["id"],
            chapter_id=chapter["id"],
        )
        if not quiet:
            self.status_label.setText(msg)
        self._load_project(self._current_project["id"])

    def _build_sessions(self) -> None:
        if not self._current_project:
            return
        sessions = rebuild_sessions(self._current_project["id"])
        self.status_label.setText(
            f"Built {len(sessions)} session{'s' if len(sessions) != 1 else ''}."
        )
        self._load_project(self._current_project["id"])

    def _mark_session_complete(self) -> None:
        if not self._current_project:
            return
        items = self.session_tree.selectedItems()
        if not items:
            return
        session_id = items[0].data(0, Qt.ItemDataRole.UserRole)
        mark_session_complete(self._current_project["id"], session_id)
        self.status_label.setText("Session marked complete.")
        self._load_project(self._current_project["id"])

    def _resume_next_session(self) -> None:
        if not self._current_project:
            return
        session = next_unfinished_session(self._current_project)
        if not session or not session.get("chapter_ids"):
            self.status_label.setText("No unfinished sessions.")
            return
        self._select_chapter(session["chapter_ids"][0])
        self.status_label.setText(f"Selected {session['title']}.")

    # ── Helpers ───────────────────────────────────────────────────────────

    def _selected_chapter(self) -> dict | None:
        if not self._current_project:
            return None
        items = self.chapter_tree.selectedItems()
        if not items:
            return None
        chapter_id = items[0].data(0, Qt.ItemDataRole.UserRole)
        return next((c for c in self._current_project["chapters"] if c["id"] == chapter_id), None)

    def _select_project(self, project_id: str) -> None:
        for i in range(self.project_tree.topLevelItemCount()):
            item = self.project_tree.topLevelItem(i)
            if item.data(0, Qt.ItemDataRole.UserRole) == project_id:
                self.project_tree.setCurrentItem(item)
                return

    def _select_chapter(self, chapter_id: str) -> None:
        for i in range(self.chapter_tree.topLevelItemCount()):
            item = self.chapter_tree.topLevelItem(i)
            if item.data(0, Qt.ItemDataRole.UserRole) == chapter_id:
                self.chapter_tree.setCurrentItem(item)
                return

    def _set_detail_enabled(self, enabled: bool) -> None:
        for widget in [
            self.title_edit,
            self.author_edit,
            self.voice_combo,
            self.speed_combo,
            self.notes_edit,
            self.save_project_btn,
            self.chapter_tree,
            self.chapter_title_edit,
            self.chapter_text_edit,
            self.split_marker_edit,
            self.split_chapters_btn,
            self.add_chapter_btn,
            self.update_chapter_btn,
            self.delete_chapter_btn,
            self.queue_chapter_btn,
            self.queue_all_btn,
            self.session_tree,
            self.build_sessions_btn,
            self.complete_session_btn,
            self.resume_session_btn,
        ]:
            widget.setEnabled(enabled)

    def _format_time(self, value) -> str:
        try:
            from datetime import datetime

            return datetime.fromtimestamp(float(value)).strftime("%Y-%m-%d")
        except Exception:
            return ""
