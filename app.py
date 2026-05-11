#!/usr/bin/env python3
"""Narracast — offline audiobook generator. PySide6 entry point."""
import sys
import os
import queue
import threading

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QProgressBar, QVBoxLayout

from narracast.audio_generation import best_device, set_tts
from narracast.paths import SPLASH_ICON_PATH
from narracast.queue_manager import start_queue_worker
from narracast.settings import load_settings
from narracast.ui.signals import get_signals
from narracast.ui.theme import apply_theme


class SplashWindow(QDialog):
    """Small startup window shown while the local F5-TTS model loads."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Narracast")
        self.setFixedSize(420, 300)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel()
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if SPLASH_ICON_PATH.exists():
            icon.setPixmap(
                QPixmap(str(SPLASH_ICON_PATH)).scaled(
                    96,
                    96,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(icon)

        title = QLabel("Narracast")
        title.setObjectName("h1")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        blurb = QLabel(
            "Narracast turns anything worth reading into something worth hearing — right on your device."
        )
        blurb.setObjectName("muted")
        blurb.setWordWrap(True)
        blurb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(blurb)

        self.status = QLabel("Loading local voice model…")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(8)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

    def set_status(self, text: str) -> None:
        self.status.setText(text)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Narracast")
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
    font.setPointSize(13)
    app.setFont(font)

    settings = load_settings()
    dark = settings.get("app_theme", "Dark") == "Dark"
    apply_theme(app, dark=dark)

    from narracast.ui.main_window import MainWindow
    splash = SplashWindow()
    splash.show()
    app.processEvents()

    window = MainWindow(settings=settings, dark=dark)

    app._narracast_splash = splash

    state = {"ticks": 0, "main_shown": False}

    def _show_main_window() -> None:
        if state["main_shown"]:
            return
        state["main_shown"] = True
        splash.close()
        window.show()

    def _on_ready(device: str) -> None:
        splash.set_status("Ready.")
        _show_main_window()
        get_signals().model_ready.emit(device)

    def _on_error(err: str) -> None:
        _show_main_window()
        window.on_model_error(err)

    load_events: queue.Queue[tuple[str, str]] = queue.Queue()

    def _load_model_worker() -> None:
        try:
            device = best_device()

            from f5_tts.api import F5TTS

            model = F5TTS(device=device)
            set_tts(model, device=device)
            load_events.put(("ready", device))
        except Exception as exc:
            load_events.put(("error", str(exc)))

    def _poll_model_load() -> None:
        state["ticks"] += 1
        if state["ticks"] == 1:
            splash.set_status("Loading local voice model…")
        elif state["ticks"] == 40:
            splash.set_status("Still loading local model. First launch can take a few minutes…")

        try:
            kind, payload = load_events.get_nowait()
        except queue.Empty:
            QTimer.singleShot(250, _poll_model_load)
            return

        if kind == "ready":
            start_queue_worker()
            _on_ready(payload)
        else:
            _on_error(payload)

    app._narracast_loader_thread = threading.Thread(target=_load_model_worker, daemon=True)
    app._narracast_loader_thread.start()
    QTimer.singleShot(1800, _show_main_window)
    QTimer.singleShot(100, _poll_model_load)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
