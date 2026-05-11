"""PySide6 benchmark dialog for generation speed presets."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from narracast.benchmark import run_all_presets
from narracast.ui.widgets import MutedLabel


class BenchmarkWorker(QThread):
    """Runs preset benchmarks off the UI thread."""

    preset_started = Signal(str)
    preset_done = Signal(dict)
    finished_ok = Signal(list)
    failed = Signal(str)

    def __init__(self, voice_name: str, voice_path: str) -> None:
        super().__init__()
        self.voice_name = voice_name
        self.voice_path = voice_path

    def run(self) -> None:
        try:
            results = run_all_presets(
                self.voice_name,
                self.voice_path,
                on_preset_start=self.preset_started.emit,
                on_preset_done=self.preset_done.emit,
            )
            self.finished_ok.emit(results)
        except Exception as exc:
            self.failed.emit(str(exc))


class BenchmarkDialog(QDialog):
    """Shows generation speed results for the active voice."""

    def __init__(self, voice_name: str, voice_path: str, parent=None) -> None:
        super().__init__(parent)
        self.voice_name = voice_name
        self.voice_path = voice_path
        self._worker: BenchmarkWorker | None = None

        self.setWindowTitle("Generation Benchmark")
        self.resize(680, 420)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Generation Benchmark")
        title.setObjectName("h2")
        layout.addWidget(title)

        layout.addWidget(
            MutedLabel(
                "Runs the same short sample through each preset to estimate speed on this Mac."
            )
        )

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Preset", "Chunks", "Generation", "Audio", "Real-time factor"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, stretch=1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 4)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        self.status = MutedLabel("Ready to run benchmark.")
        layout.addWidget(self.status)

        row = QHBoxLayout()
        row.addStretch()
        self.run_btn = QPushButton("Run benchmark")
        self.run_btn.setObjectName("primary")
        self.run_btn.clicked.connect(self._start)
        row.addWidget(self.run_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        row.addWidget(close_btn)
        layout.addLayout(row)

    def _start(self) -> None:
        self.table.setRowCount(0)
        self.progress.setValue(0)
        self.status.setText("Starting benchmark…")
        self.run_btn.setEnabled(False)

        self._worker = BenchmarkWorker(self.voice_name, self.voice_path)
        self._worker.preset_started.connect(self._on_preset_started)
        self._worker.preset_done.connect(self._on_preset_done)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_preset_started(self, preset: str) -> None:
        self.status.setText(f"Running {preset} preset…")

    def _on_preset_done(self, result: dict) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        values = [
            result.get("preset", ""),
            str(result.get("chunks", "")),
            f"{result.get('gen_time_s', 0):.1f}s",
            f"{result.get('audio_duration_s', 0):.1f}s",
            f"{result.get('rtf', 0):.2f}×",
        ]
        for col, value in enumerate(values):
            self.table.setItem(row, col, QTableWidgetItem(value))
        self.progress.setValue(row + 1)

    def _on_finished(self, _results: list) -> None:
        self.status.setText("Benchmark complete.")
        self.run_btn.setEnabled(True)

    def _on_failed(self, error: str) -> None:
        self.status.setText(f"Benchmark failed: {error}")
        self.run_btn.setEnabled(True)
