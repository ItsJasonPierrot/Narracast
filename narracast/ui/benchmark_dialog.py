"""PySide6 benchmark dialog for generation speed presets."""

from __future__ import annotations

import threading
import uuid

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

from narracast.presets import GENERATION_PRESETS
from narracast.tts_process import JobCallbacks, get_tts_process
from narracast.ui.widgets import MutedLabel


class BenchmarkWorker(QThread):
    """Runs preset benchmarks off the UI thread via the TTS worker process."""

    preset_started = Signal(str)
    preset_done = Signal(dict)
    finished_ok = Signal(list)
    failed = Signal(str)

    def __init__(self, voice_name: str, voice_path: str) -> None:
        super().__init__()
        self.voice_name = voice_name
        self.voice_path = voice_path  # kept for API compatibility; worker resolves internally

    def run(self) -> None:
        proc = get_tts_process()
        results: list[dict] = []

        for preset_name in GENERATION_PRESETS:
            self.preset_started.emit(preset_name)

            done_event = threading.Event()
            result_holder: list[dict] = []
            error_holder: list[str] = []

            def _on_result(result: dict, _ev=done_event, _r=result_holder) -> None:
                _r.append(result)
                _ev.set()

            def _on_error(err: str, _ev=done_event, _e=error_holder) -> None:
                _e.append(err)
                _ev.set()

            callbacks = JobCallbacks(
                on_benchmark_preset_done=_on_result,
                on_error=_on_error,
            )
            proc.submit_benchmark_preset(
                {
                    "job_id": uuid.uuid4().hex[:8],
                    "voice_name": self.voice_name,
                    "preset_name": preset_name,
                },
                callbacks,
            )

            timed_out = not done_event.wait(timeout=600.0)  # 10-minute safety timeout
            if timed_out:
                self.failed.emit(f"Timeout waiting for benchmark preset '{preset_name}'.")
                return
            if error_holder:
                self.failed.emit(error_holder[0])
                return

            result = result_holder[0]
            results.append(result)
            self.preset_done.emit(result)

        self.finished_ok.emit(results)


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
        if not get_tts_process().is_alive():
            self.status.setText("TTS worker not ready. Wait for model to finish loading.")
            return

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
