"""Narracast main application window."""

from __future__ import annotations

import re

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from narracast.settings import save_settings
from narracast.ui.sidebar import Sidebar
from narracast.ui.signals import get_signals
from narracast.ui.theme import apply_theme
from narracast.ui.pages.generate_page import GeneratePage
from narracast.ui.pages.projects_page import ProjectsPage
from narracast.ui.pages.queue_page import QueuePage
from narracast.ui.pages.voice_page import VoicePage
from narracast.ui.pages.history_page import HistoryPage
from narracast.ui.pages.reading_page import ReadingPage
from narracast.ui.pages.help_page import HelpPage


PAGE_INDEX = {
    "generate": 0,
    "projects": 1,
    "queue": 2,
    "voice": 3,
    "history": 4,
    "read": 5,
    "help": 6,
}


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(
        self,
        settings: dict | None = None,
        dark: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings or {}
        self._dark = dark
        self._device = "CPU"
        self._current_page = "generate"

        self.setWindowTitle("Narracast")
        self.resize(1100, 760)

        self._build_ui()
        self._connect_signals()
        self._apply_settings()

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar(dark=self._dark)
        self.sidebar.page_requested.connect(self._switch_page)
        self.sidebar.theme_toggle_requested.connect(self._toggle_theme)
        layout.addWidget(self.sidebar)

        # Page stack
        self.stack = QStackedWidget()
        self.generate_page = GeneratePage()
        self.projects_page = ProjectsPage()
        self.queue_page = QueuePage()
        self.voice_page = VoicePage()
        self.history_page = HistoryPage()
        self.reading_page = ReadingPage()
        self.help_page = HelpPage()

        for page in [
            self.generate_page,
            self.projects_page,
            self.queue_page,
            self.voice_page,
            self.history_page,
            self.reading_page,
            self.help_page,
        ]:
            self.stack.addWidget(page)

        layout.addWidget(self.stack)

        # Status bar
        self._status_bar = self.statusBar()
        self._status_label = QLabel("●  Ready  •  CPU  •  All systems offline")
        self._status_label.setObjectName("muted")
        self._status_bar.addWidget(self._status_label)

    # ── Signal connections ────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        sigs = get_signals()
        sigs.model_ready.connect(self._on_model_ready_signal)
        sigs.status_update.connect(self._status_label.setText)

        # History / Projects → Reading bridge
        self.history_page.open_in_reader.connect(self._open_in_reader)
        self.projects_page.open_in_reader.connect(self._open_in_reader)
        self.projects_page.open_session_in_reader.connect(self._open_session_in_reader)

    # ── Page navigation ───────────────────────────────────────────────────

    def _switch_page(self, key: str) -> None:
        self._current_page = key if key in PAGE_INDEX else "generate"
        self.stack.setCurrentIndex(PAGE_INDEX.get(key, 0))
        self.sidebar.set_active(key)

    # ── Theme ─────────────────────────────────────────────────────────────

    def _toggle_theme(self) -> None:
        self._dark = not self._dark
        from PySide6.QtWidgets import QApplication
        apply_theme(QApplication.instance(), dark=self._dark)
        self.sidebar.set_dark(self._dark)

    # ── Reader bridge ─────────────────────────────────────────────────────

    def _open_in_reader(self, path: str) -> None:
        self.reading_page.load_file(path)
        self._switch_page("read")

    def _open_session_in_reader(self, paths: object) -> None:
        """Open a session's chapters as a queue in the reading page."""
        path_list = list(paths) if paths else []
        if not path_list:
            return
        self.reading_page.load_session(path_list)
        self._switch_page("read")

    # ── Model lifecycle ───────────────────────────────────────────────────

    def on_model_ready(self, device: str) -> None:
        """Called by app.py when model loading succeeds."""
        self._device = device
        label = {"cuda": "NVIDIA GPU (CUDA)", "mps": "Apple GPU (MPS)", "cpu": "CPU"}.get(
            device.lower(), device
        )
        self._status_label.setText(f"●  Ready  •  {label}  •  All systems offline")
        self.sidebar.set_device(device)
        self.generate_page.on_model_ready()

    def on_model_error(self, err: str) -> None:
        """Called by app.py when model loading fails."""
        self._status_label.setText(f"⚠  Model failed: {err}")

    def _on_model_ready_signal(self, device: str) -> None:
        """Handles the model_ready signal (redundant path for signal bus use)."""
        self.on_model_ready(device)

    # ── Settings ──────────────────────────────────────────────────────────

    def _apply_settings(self) -> None:
        geometry = str(self._settings.get("geometry") or "")
        match = re.match(r"^(\d{3,4})x(\d{3,4})$", geometry)
        if match:
            self.resize(int(match.group(1)), int(match.group(2)))

        self.generate_page.apply_settings(self._settings)
        self.reading_page.apply_settings(self._settings)

        page = str(self._settings.get("current_page") or "generate")
        if page in PAGE_INDEX:
            self._switch_page(page)

    def closeEvent(self, event) -> None:  # noqa: N802
        settings = {
            **self.generate_page.current_settings(),
            **self.reading_page.current_settings(),
            "geometry": f"{self.width()}x{self.height()}",
            "app_theme": "Dark" if self._dark else "Light",
            "current_page": self._current_page,
        }
        save_settings(settings)
        self.reading_page.shutdown()
        event.accept()
