"""M4B audiobook export dialog.

Shows a chapter audit table, lets the user pick the output path,
and runs ffmpeg export on a background QThread with live progress.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from narracast.m4b_export import ChapterExportInfo, audit_project_chapters, export_m4b
from narracast.ui import icons


# ── Background worker ───────────────────────────────────────────────────────


class _ExportWorker(QThread):
    """Runs export_m4b on a worker thread."""

    progress = Signal(str)
    finished = Signal(str)   # output path on success
    errored = Signal(str)    # error message on failure

    def __init__(
        self,
        project: dict,
        output_path: str,
        skip_missing: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._project = project
        self._output_path = output_path
        self._skip_missing = skip_missing

    def run(self) -> None:
        try:
            result = export_m4b(
                self._project,
                self._output_path,
                skip_missing=self._skip_missing,
                on_progress=self.progress.emit,
            )
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.errored.emit(str(exc))


# ── Dialog ──────────────────────────────────────────────────────────────────


class M4BExportDialog(QDialog):
    """Modal dialog for exporting a project as an M4B audiobook."""

    def __init__(self, project: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project = project
        self._audit: list[ChapterExportInfo] = []
        self._worker: _ExportWorker | None = None

        self.setWindowTitle("Export M4B Audiobook")
        self.setMinimumWidth(640)
        self.setMinimumHeight(480)

        self._build_ui()
        self._run_audit()

    # ── UI construction ─────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title_lbl = QLabel("Export M4B Audiobook")
        title_lbl.setObjectName("h2")
        layout.addWidget(title_lbl)

        desc = QLabel(
            "Review chapter readiness below, choose an output file, then click Export."
        )
        desc.setObjectName("muted")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Audit table
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Chapter", "Status", "Duration", "Reason"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table, stretch=1)

        # Audit summary
        self._audit_label = QLabel("")
        self._audit_label.setObjectName("muted")
        layout.addWidget(self._audit_label)

        # Skip missing option
        self._skip_check = QCheckBox("Skip chapters that are not ready")
        self._skip_check.setChecked(True)
        layout.addWidget(self._skip_check)

        # Output path
        out_row = QHBoxLayout()
        out_lbl = QLabel("Output file:")
        out_row.addWidget(out_lbl)
        self._out_edit = QLineEdit()
        default_title = (self._project.get("title") or "audiobook").replace(" ", "_")
        self._out_edit.setText(str(Path.home() / "Desktop" / f"{default_title}.m4b"))
        self._out_edit.setPlaceholderText("Path to output .m4b file")
        out_row.addWidget(self._out_edit, stretch=1)
        browse_btn = QPushButton()
        browse_btn.setIcon(icons.icon(icons.FOLDER_OPEN))
        browse_btn.setToolTip("Choose output file…")
        browse_btn.clicked.connect(self._browse_output)
        out_row.addWidget(browse_btn)
        layout.addLayout(out_row)

        # Progress bar + status
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("muted")
        self._status_lbl.setWordWrap(True)
        layout.addWidget(self._status_lbl)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)
        self._export_btn = QPushButton("Export")
        self._export_btn.setObjectName("primary")
        self._export_btn.setIcon(icons.icon(icons.SAVE))
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._start_export)
        btn_row.addWidget(self._export_btn)
        layout.addLayout(btn_row)

    # ── Audit ───────────────────────────────────────────────────────────────

    def _run_audit(self) -> None:
        self._audit = audit_project_chapters(self._project)
        self._populate_table()
        self._update_export_button()

    def _populate_table(self) -> None:
        self._table.setRowCount(0)
        for info in self._audit:
            row = self._table.rowCount()
            self._table.insertRow(row)

            title_item = QTableWidgetItem(info.title)
            if info.ready:
                title_item.setForeground(Qt.GlobalColor.green)
            else:
                title_item.setForeground(Qt.GlobalColor.red)
            self._table.setItem(row, 0, title_item)

            status_text = "Ready" if info.ready else "Not ready"
            self._table.setItem(row, 1, QTableWidgetItem(status_text))

            dur_text = self._format_duration(info.duration_ms) if info.ready else "—"
            self._table.setItem(row, 2, QTableWidgetItem(dur_text))

            self._table.setItem(row, 3, QTableWidgetItem(info.reason))

        ready = sum(1 for a in self._audit if a.ready)
        total = len(self._audit)
        self._audit_label.setText(
            f"{ready} of {total} chapter{'s' if total != 1 else ''} ready to export."
        )

    def _update_export_button(self) -> None:
        ready = sum(1 for a in self._audit if a.ready)
        self._export_btn.setEnabled(ready > 0)

    # ── Export ──────────────────────────────────────────────────────────────

    def _browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save M4B audiobook",
            self._out_edit.text(),
            "M4B Audiobook (*.m4b)",
        )
        if path:
            if not path.endswith(".m4b"):
                path += ".m4b"
            self._out_edit.setText(path)

    def _start_export(self) -> None:
        output_path = self._out_edit.text().strip()
        if not output_path:
            self._status_lbl.setText("Please choose an output file path.")
            return

        self._set_busy(True)
        self._worker = _ExportWorker(
            project=self._project,
            output_path=output_path,
            skip_missing=self._skip_check.isChecked(),
            parent=self,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.errored.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, msg: str) -> None:
        self._status_lbl.setText(msg)

    def _on_finished(self, output_path: str) -> None:
        self._set_busy(False)
        self._status_lbl.setText(f"Exported to: {output_path}")
        self._export_btn.setText("Done")
        self._export_btn.setEnabled(False)
        self._cancel_btn.setText("Close")

    def _on_error(self, msg: str) -> None:
        self._set_busy(False)
        self._status_lbl.setText(f"Export failed: {msg}")

    def _set_busy(self, busy: bool) -> None:
        self._export_btn.setEnabled(not busy)
        self._cancel_btn.setEnabled(not busy)
        self._skip_check.setEnabled(not busy)
        self._out_edit.setEnabled(not busy)
        self._progress.setVisible(busy)

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _format_duration(ms: int) -> str:
        if ms <= 0:
            return "—"
        total_s = ms // 1000
        minutes, seconds = divmod(total_s, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h {minutes:02d}m {seconds:02d}s"
        if minutes:
            return f"{minutes}m {seconds:02d}s"
        return f"{seconds}s"
