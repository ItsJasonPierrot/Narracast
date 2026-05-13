"""History page — browse, play, and manage generated audio files."""

from __future__ import annotations

import subprocess
import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from narracast.output_files import (
    delete_all_history,
    format_history_row,
    list_history_files,
)
from narracast.metadata import metadata_path_for_audio
from narracast.ui import icons
from narracast.paths import OUTPUT_DIR
from narracast.ui.widgets import Card, Divider, MutedLabel


class HistoryPage(QWidget):
    """Generated audio file browser."""

    open_in_reader: Signal = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._files: list[Path] = []
        self._selected_path: Optional[Path] = None
        self._selected_has_metadata = False
        self._build_ui()
        self._refresh()

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Header
        h2 = QLabel("History")
        h2.setObjectName("h2")
        root.addWidget(h2)

        subtitle = MutedLabel("All generated MP3 files, newest first.")
        root.addWidget(subtitle)

        # Card
        card = Card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(10)
        root.addWidget(card, stretch=1)

        # Search + refresh row
        top_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search by filename…")
        self._search.textChanged.connect(self._on_search)
        top_row.addWidget(self._search, stretch=1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setIcon(icons.icon(icons.REFRESH))
        refresh_btn.setFixedHeight(32)
        refresh_btn.clicked.connect(self._refresh)
        top_row.addWidget(refresh_btn)
        card_layout.addLayout(top_row)

        # Tree
        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Title / Filename", "Date", "Duration", "Size"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().resizeSection(1, 140)
        self.tree.header().resizeSection(2, 80)
        self.tree.header().resizeSection(3, 80)
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tree.setMinimumHeight(240)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        card_layout.addWidget(self.tree)

        # Primary actions
        action_row = QHBoxLayout()
        self.read_btn = QPushButton("Read + Play")
        self.read_btn.setIcon(icons.accent(icons.BOOK_OPEN))
        self.read_btn.setObjectName("primary")
        self.read_btn.setFixedHeight(36)
        self.read_btn.setEnabled(False)
        self.read_btn.clicked.connect(self._open_in_reader)
        action_row.addWidget(self.read_btn)

        self.play_btn = QPushButton("Play (audio only)")
        self.play_btn.setIcon(icons.icon(icons.HEADPHONES))
        self.play_btn.setObjectName("secondary")
        self.play_btn.setFixedHeight(36)
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self._play_audio)
        action_row.addWidget(self.play_btn)

        self.reveal_btn = QPushButton("Reveal")
        self.reveal_btn.setIcon(icons.icon(icons.REVEAL))
        self.reveal_btn.setFixedHeight(36)
        self.reveal_btn.setEnabled(False)
        self.reveal_btn.clicked.connect(self._reveal_selected)
        action_row.addWidget(self.reveal_btn)

        self.open_folder_btn = QPushButton("Open output folder")
        self.open_folder_btn.setFixedHeight(36)
        self.open_folder_btn.clicked.connect(self._open_output_folder)
        action_row.addWidget(self.open_folder_btn)
        action_row.addStretch()
        card_layout.addLayout(action_row)

        card_layout.addWidget(Divider())

        # Danger zone
        danger_row = QHBoxLayout()
        danger_row.addWidget(MutedLabel("Danger zone:"))

        self.delete_btn = QPushButton("Delete file")
        self.delete_btn.setIcon(icons.danger(icons.DELETE))
        self.delete_btn.setObjectName("danger")
        self.delete_btn.setFixedHeight(30)
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._delete_selected)
        danger_row.addWidget(self.delete_btn)

        self.clear_btn = QPushButton("Clear history")
        self.clear_btn.setObjectName("danger")
        self.clear_btn.setFixedHeight(30)
        self.clear_btn.clicked.connect(self._clear_history)
        danger_row.addWidget(self.clear_btn)
        danger_row.addStretch()
        card_layout.addLayout(danger_row)

        root.addStretch()

    # ── Refresh / populate ────────────────────────────────────────────────

    def _refresh(self) -> None:
        self._files = list_history_files()
        self._populate_tree(self._files)

    def _populate_tree(self, files: list[Path]) -> None:
        self.tree.clear()
        for f in files:
            name, size, mtime = format_history_row(f)
            duration_str = "—"
            has_reader_metadata = False
            try:
                meta_path = metadata_path_for_audio(f)
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    ms = meta.get("duration_ms", 0)
                    m, s = divmod(ms // 1000, 60)
                    duration_str = f"{m}:{s:02d}"
                    has_reader_metadata = bool(meta.get("source_text") and meta.get("timeline"))
            except Exception:
                pass
            item = QTreeWidgetItem([name, mtime, duration_str, size])
            item.setData(0, Qt.ItemDataRole.UserRole, str(f))
            item.setData(1, Qt.ItemDataRole.UserRole, has_reader_metadata)
            if not has_reader_metadata:
                item.setToolTip(0, "Audio-only file: no Narracast sidecar metadata found.")
            self.tree.addTopLevelItem(item)

    def _on_search(self, text: str) -> None:
        query = text.lower()
        filtered = [f for f in self._files if query in f.name.lower()]
        self._populate_tree(filtered)

    def _on_selection_changed(self) -> None:
        items = self.tree.selectedItems()
        has_sel = bool(items)
        path = Path(items[0].data(0, Qt.ItemDataRole.UserRole)) if has_sel else None
        has_metadata = bool(items[0].data(1, Qt.ItemDataRole.UserRole)) if has_sel else False
        self._selected_path = path
        self._selected_has_metadata = has_metadata
        self.read_btn.setEnabled(has_sel and has_metadata)
        self.read_btn.setToolTip(
            "" if has_metadata else "Read mode needs Narracast sidecar metadata. Use Play (audio only)."
        )
        self.play_btn.setEnabled(has_sel)
        self.reveal_btn.setEnabled(has_sel)
        self.delete_btn.setEnabled(has_sel)

    def _on_double_click(self, item: QTreeWidgetItem, _col: int) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        has_metadata = bool(item.data(1, Qt.ItemDataRole.UserRole))
        if path and has_metadata:
            self.open_in_reader.emit(path)

    # ── Actions ───────────────────────────────────────────────────────────

    def _open_in_reader(self) -> None:
        if self._selected_path and self._selected_has_metadata:
            self.open_in_reader.emit(str(self._selected_path))

    def _play_audio(self) -> None:
        if self._selected_path:
            subprocess.Popen(
                ["afplay", str(self._selected_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def _reveal_selected(self) -> None:
        if self._selected_path:
            subprocess.Popen(["open", "-R", str(self._selected_path)])

    def _open_output_folder(self) -> None:
        subprocess.Popen(["open", str(OUTPUT_DIR)])

    def _delete_selected(self) -> None:
        if not self._selected_path:
            return
        confirmed = QMessageBox.question(
            self,
            "Delete file?",
            f"Delete \"{self._selected_path.name}\" and its sidecar?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        meta = metadata_path_for_audio(self._selected_path)
        meta.unlink(missing_ok=True)
        self._selected_path.unlink(missing_ok=True)
        self._selected_path = None
        self._refresh()

    def _clear_history(self) -> None:
        n = len(self._files)
        if n == 0:
            return
        confirmed = QMessageBox.question(
            self,
            "Clear all history?",
            f"Permanently delete all {n} generated file{'s' if n != 1 else ''} and their sidecars?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        delete_all_history()
        self._refresh()
