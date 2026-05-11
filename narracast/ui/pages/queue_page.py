"""Queue page — monitor and manage background generation jobs."""

from __future__ import annotations

import subprocess

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from narracast.queue_manager import (
    Job,
    cancel_job,
    clear_finished_jobs,
    list_jobs,
    retry_job,
)
from narracast.ui.widgets import Card, MutedLabel, SectionLabel


_STATUS_COLORS = {
    "pending": "#7f90a8",
    "generating": "#60a5fa",
    "done": "#16a34a",
    "error": "#f87171",
    "cancelled": "#7f90a8",
}


class QueuePage(QWidget):
    """Background job queue monitor."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._jobs: list[Job] = []
        self._build_ui()
        self._start_refresh_timer()

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Header
        h2 = QLabel("Queue")
        h2.setObjectName("h2")
        root.addWidget(h2)

        subtitle = MutedLabel("Jobs run one at a time in the background.")
        root.addWidget(subtitle)

        # Main card
        card = Card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(10)
        root.addWidget(card)

        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(["#", "Job", "Status", "Progress", "Added"])
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.tree.header().resizeSection(0, 40)
        self.tree.header().resizeSection(2, 90)
        self.tree.header().resizeSection(3, 120)
        self.tree.header().resizeSection(4, 130)
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tree.setMinimumHeight(280)
        card_layout.addWidget(self.tree)

        # Footer row
        footer = QHBoxLayout()
        self._count_label = MutedLabel("0 jobs  •  0 processing")
        footer.addWidget(self._count_label)
        footer.addStretch()
        self._autostart_check = QCheckBox("Auto-start")
        self._autostart_check.setChecked(True)
        footer.addWidget(self._autostart_check)
        card_layout.addLayout(footer)

        # Action buttons
        btn_row = QHBoxLayout()
        self._cancel_btn = QPushButton("Cancel pending")
        self._cancel_btn.setFixedHeight(32)
        self._cancel_btn.clicked.connect(self._cancel_pending)

        self._retry_btn = QPushButton("Retry failed")
        self._retry_btn.setFixedHeight(32)
        self._retry_btn.clicked.connect(self._retry_failed)

        self._reveal_btn = QPushButton("Reveal output")
        self._reveal_btn.setFixedHeight(32)
        self._reveal_btn.clicked.connect(self._reveal_selected)

        self._clear_btn = QPushButton("Clear completed")
        self._clear_btn.setObjectName("secondary")
        self._clear_btn.setFixedHeight(32)
        self._clear_btn.clicked.connect(self._clear_completed)

        for btn in [self._cancel_btn, self._retry_btn, self._reveal_btn, self._clear_btn]:
            btn_row.addWidget(btn)
        btn_row.addStretch()
        card_layout.addLayout(btn_row)

        root.addStretch()

    # ── Refresh logic ─────────────────────────────────────────────────────

    def _start_refresh_timer(self) -> None:
        QTimer.singleShot(2000, self._refresh_queue)

    def _refresh_queue(self) -> None:
        self._jobs = list_jobs(reverse=False)
        self._populate_tree()
        QTimer.singleShot(2000, self._refresh_queue)

    def _populate_tree(self) -> None:
        self.tree.clear()
        processing = 0

        for i, job in enumerate(self._jobs):
            if job.status == "generating":
                processing += 1

            title = job.title or job.text[:40] + "…" if len(job.text) > 40 else job.text
            from datetime import datetime
            added = datetime.fromtimestamp(job.created_at).strftime("%Y-%m-%d %H:%M")

            item = QTreeWidgetItem([
                str(i + 1),
                title,
                job.status.capitalize(),
                "",  # progress column — will be handled below
                added,
            ])

            color = _STATUS_COLORS.get(job.status, "#e9f1ff")
            item.setForeground(2, QColor(color))
            item.setData(0, Qt.ItemDataRole.UserRole, job.id)

            self.tree.addTopLevelItem(item)

            # Inline progress bar for generating jobs
            if job.status == "generating":
                try:
                    pct_str = job.progress.split("%")[0] if "%" in job.progress else "0"
                    pct = int(pct_str.strip())
                except (ValueError, IndexError):
                    pct = 0
                bar = QProgressBar()
                bar.setRange(0, 100)
                bar.setValue(pct)
                bar.setTextVisible(False)
                bar.setFixedHeight(10)
                bar.setStyleSheet(
                    "QProgressBar { background: #0a111b; border: 1px solid #2d3b4f; border-radius: 3px; }"
                    "QProgressBar::chunk { background: #60a5fa; border-radius: 2px; }"
                )
                self.tree.setItemWidget(item, 3, bar)
            else:
                item.setText(3, job.progress)

        n = len(self._jobs)
        self._count_label.setText(f"{n} job{'s' if n != 1 else ''}  •  {processing} processing")

    # ── Button actions ────────────────────────────────────────────────────

    def _selected_job(self) -> Job | None:
        items = self.tree.selectedItems()
        if not items:
            return None
        job_id = items[0].data(0, Qt.ItemDataRole.UserRole)
        return next((j for j in self._jobs if j.id == job_id), None)

    def _cancel_pending(self) -> None:
        job = self._selected_job()
        if job:
            cancel_job(job.id)
        else:
            for j in self._jobs:
                if j.status == "pending":
                    cancel_job(j.id)
        self._refresh_queue()

    def _retry_failed(self) -> None:
        job = self._selected_job()
        if job and job.status == "error":
            retry_job(job.id)
        else:
            for j in self._jobs:
                if j.status == "error":
                    retry_job(j.id)
        self._refresh_queue()

    def _reveal_selected(self) -> None:
        job = self._selected_job()
        if job and job.output_path:
            subprocess.Popen(["open", "-R", job.output_path])

    def _clear_completed(self) -> None:
        clear_finished_jobs()
        self._refresh_queue()
