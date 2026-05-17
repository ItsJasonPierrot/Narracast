"""WiFi Transfer page — browse and share generated audio files over local WiFi.

The page runs a small HTTP server (``narracast.wifi_server.WifiServer``) that
lets an iPhone companion app (or any browser on the same network) pull MP3s
and sidecar JSON without cables or cloud services.

The server starts automatically when the page is first shown, and stops
cleanly when :meth:`stop_server` is called (wired to the app's close event).
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from narracast.metadata import metadata_path_for_audio
from narracast.output_files import format_history_row, list_history_files
from narracast.paths import OUTPUT_DIR
from narracast.ui import icons
from narracast.ui.signals import get_signals
from narracast.ui.widgets import Card, Divider, MutedLabel
from narracast.wifi_server import WifiServer

# Semantic status-dot colors — intentionally not in QSS because they convey
# live server state (stopped / starting / running / error) independently of
# the app's dark/light theme.
_DOT_COLOR = {
    "stopped": "#6b7f96",   # muted grey
    "starting": "#f0b429",  # amber
    "running": "#a3ff73",   # green
    "error": "#e05c5c",     # red
}


class TransferPage(QWidget):
    """WiFi Transfer page: start/stop the local HTTP server and browse files."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._server = WifiServer(
            OUTPUT_DIR,
            on_started=self._on_server_started,
            on_error=self._on_server_error,
        )
        self._files: list[Path] = []
        self._build_ui()

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Header
        h2 = QLabel("Transfer to iPhone")
        h2.setObjectName("h2")
        root.addWidget(h2)

        root.addWidget(
            MutedLabel(
                "Open the URL below in Safari on your iPhone, or use the "
                "Narracast iOS app when available."
            )
        )

        # ── Server card ────────────────────────────────────────────────────
        server_card = Card()
        sc_layout = QVBoxLayout(server_card)
        sc_layout.setContentsMargins(16, 14, 16, 14)
        sc_layout.setSpacing(10)

        # Status row
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self._status_dot = QLabel("●")
        self._status_dot.setFixedWidth(14)
        self._status_dot.setAccessibleName("Server status indicator")
        self._status_dot.setToolTip("Server status")
        self._status_dot.setStyleSheet(f"color: {_DOT_COLOR['stopped']};")
        status_row.addWidget(self._status_dot)
        self._status_label = QLabel("Server stopped")
        status_row.addWidget(self._status_label, stretch=1)
        sc_layout.addLayout(status_row)

        # URL field
        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self._url_field = QLineEdit()
        self._url_field.setReadOnly(True)
        self._url_field.setPlaceholderText("Start the server to see its address")
        self._url_field.setMinimumWidth(280)
        url_row.addWidget(self._url_field, stretch=1)

        self._copy_btn = QPushButton("Copy")
        self._copy_btn.setObjectName("secondary")
        self._copy_btn.setFixedWidth(60)
        self._copy_btn.setEnabled(False)
        self._copy_btn.clicked.connect(self._copy_url)
        url_row.addWidget(self._copy_btn)
        sc_layout.addLayout(url_row)

        sc_layout.addWidget(
            MutedLabel("All files in your output folder are accessible once the server is running.")
        )

        # Toggle button
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()
        self._toggle_btn = QPushButton("Start server")
        self._toggle_btn.setObjectName("primary")
        self._toggle_btn.clicked.connect(self._toggle_server)
        btn_row.addWidget(self._toggle_btn)
        sc_layout.addLayout(btn_row)

        root.addWidget(server_card)

        # ── Files card ────────────────────────────────────────────────────
        files_card = Card()
        fc_layout = QVBoxLayout(files_card)
        fc_layout.setContentsMargins(16, 14, 16, 14)
        fc_layout.setSpacing(10)

        files_header = QHBoxLayout()
        files_lbl = QLabel("Available files")
        files_lbl.setObjectName("h3")
        files_header.addWidget(files_lbl, stretch=1)
        refresh_btn = QPushButton()
        refresh_btn.setIcon(icons.icon(icons.REFRESH))
        refresh_btn.setObjectName("secondary")
        refresh_btn.setFixedSize(30, 30)
        refresh_btn.setToolTip("Refresh file list")
        refresh_btn.clicked.connect(self._refresh_files)
        files_header.addWidget(refresh_btn)
        fc_layout.addLayout(files_header)

        self._count_label = MutedLabel("0 files")
        fc_layout.addWidget(self._count_label)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels(["Title", "Part", "Duration", "Size"])
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(False)
        fc_layout.addWidget(self._tree, stretch=1)

        root.addWidget(files_card, stretch=1)

        self._refresh_files()

    # ── Server control ────────────────────────────────────────────────────

    def showEvent(self, event) -> None:  # noqa: N802
        """Auto-start the server when the page becomes visible."""
        super().showEvent(event)
        if not self._server.is_running():
            self._start_server()

    def _toggle_server(self) -> None:
        if self._server.is_running():
            self._stop_server()
        else:
            self._start_server()

    def _start_server(self) -> None:
        self._toggle_btn.setEnabled(False)
        self._status_dot.setStyleSheet(f"color: {_DOT_COLOR['starting']};")
        self._status_label.setText("Starting…")
        try:
            self._server.start()
        except OSError as exc:
            self._on_server_error(str(exc))

    def _stop_server(self) -> None:
        self._server.stop()
        self._url_field.clear()
        self._copy_btn.setEnabled(False)
        self._toggle_btn.setText("Start server")
        self._toggle_btn.setEnabled(True)
        self._status_dot.setStyleSheet(f"color: {_DOT_COLOR['stopped']};")
        self._status_label.setText("Server stopped")
        get_signals().wifi_server_status.emit("stopped")

    def stop_server(self) -> None:
        """Public slot — called by MainWindow.closeEvent."""
        if self._server.is_running():
            self._server.stop()

    # ── Server callbacks (called from the daemon thread) ──────────────────

    def _on_server_started(self, url: str) -> None:
        """Invoked by WifiServer once it is listening."""
        # Use QTimer.singleShot to marshal back to the Qt main thread
        QTimer.singleShot(0, lambda: self._apply_running_state(url))

    def _on_server_error(self, message: str) -> None:
        QTimer.singleShot(0, lambda: self._apply_error_state(message))

    def _apply_running_state(self, url: str) -> None:
        self._url_field.setText(url)
        self._copy_btn.setEnabled(True)
        self._toggle_btn.setText("Stop server")
        self._toggle_btn.setEnabled(True)
        self._status_dot.setStyleSheet(f"color: {_DOT_COLOR['running']};")
        self._status_label.setText(f"Running on {url}")
        get_signals().wifi_server_status.emit(f"running:{url}")
        self._refresh_files()

    def _apply_error_state(self, message: str) -> None:
        self._url_field.clear()
        self._copy_btn.setEnabled(False)
        self._toggle_btn.setText("Start server")
        self._toggle_btn.setEnabled(True)
        self._status_dot.setStyleSheet(f"color: {_DOT_COLOR['error']};")
        self._status_label.setText(f"Error: {message}")
        get_signals().wifi_server_status.emit(f"error:{message}")

    # ── File list ─────────────────────────────────────────────────────────

    def _refresh_files(self) -> None:
        self._files = list_history_files()
        self._populate_tree()

    def _populate_tree(self) -> None:
        self._tree.clear()
        count = len(self._files)
        self._count_label.setText(f"{count} file{'s' if count != 1 else ''}")

        for mp3 in self._files:
            name, size, _mtime = format_history_row(mp3)
            title = name
            part = ""
            duration = ""

            sidecar = metadata_path_for_audio(mp3)
            if sidecar.exists():
                try:
                    meta = json.loads(sidecar.read_text(encoding="utf-8"))
                    if meta.get("title"):
                        title = str(meta["title"])
                    part = str(meta.get("part", ""))
                    ms = int(meta.get("duration_ms", 0))
                    if ms:
                        mins, secs = divmod(ms // 1000, 60)
                        duration = f"{mins}:{secs:02d}"
                except (OSError, json.JSONDecodeError, ValueError):
                    pass

            item = QTreeWidgetItem([title, part, duration, size])
            item.setToolTip(0, mp3.name)
            self._tree.addTopLevelItem(item)

    # ── Clipboard ─────────────────────────────────────────────────────────

    def _copy_url(self) -> None:
        url = self._url_field.text()
        if not url:
            return
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(url)
        self._copy_btn.setText("Copied!")
        QTimer.singleShot(1500, lambda: self._copy_btn.setText("Copy"))
