"""PySide6 dialog for generation timing analysis."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from narracast.timing_analysis import analyze_generation_timings, format_timing_rows
from narracast.ui.widgets import MutedLabel


class TimingAnalysisDialog(QDialog):
    """Shows where recent generations spent time."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Generation Timing Analysis")
        self.resize(620, 420)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Generation Timing Analysis")
        title.setObjectName("h2")
        layout.addWidget(title)

        self.summary = MutedLabel("")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Stage", "Time", "Share"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, stretch=1)

        self.recommendation = MutedLabel("")
        self.recommendation.setWordWrap(True)
        layout.addWidget(self.recommendation)

        row = QHBoxLayout()
        row.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load)
        row.addWidget(refresh_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        row.addWidget(close_btn)
        layout.addLayout(row)

    def _load(self) -> None:
        report = analyze_generation_timings()
        self.table.setRowCount(0)

        if not report.has_data:
            self.summary.setText("No generation timing data found yet.")
            self.recommendation.setText(report.recommendation)
            return

        self.summary.setText(
            f"Analyzed {report.file_count} recent file(s). "
            f"Finalization took {report.finalize_time_s:.2f}s "
            f"({report.finalize_share * 100:.1f}% of measured time)."
        )

        for label, seconds, share in format_timing_rows(report):
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, value in enumerate((label, seconds, share)):
                self.table.setItem(row, col, QTableWidgetItem(value))

        self.recommendation.setText(report.recommendation)
