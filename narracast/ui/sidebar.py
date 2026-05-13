"""Left navigation sidebar."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from narracast.paths import APP_DIR
from narracast.ui import icons
from narracast.ui.widgets import Divider, MutedLabel, StatusDot

_ICON_PATH = APP_DIR / "assets" / "Narracast_Icon.png"

_NAV_ITEMS = [
    ("generate",  "Generate",       "mdi6.microphone"),
    ("projects",  "Projects",       "mdi6.book-multiple"),
    ("queue",     "Queue",          "mdi6.playlist-music"),
    ("voice",     "Voice",          "mdi6.account-voice"),
    ("history",   "History",        "mdi6.history"),
    ("read",      "Read",           "mdi6.book-open-page-variant"),
    ("help",      "Help",           "mdi6.help-circle-outline"),
]


class Sidebar(QWidget):
    """Fixed-width left sidebar with navigation and status."""

    page_requested: Signal = Signal(str)
    theme_toggle_requested: Signal = Signal()

    def __init__(self, dark: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dark = dark
        self._active_key: str = "generate"
        self._nav_buttons: dict[str, QPushButton] = {}
        self._device_label: MutedLabel | None = None

        self.setMinimumWidth(172)
        self.setMaximumWidth(220)
        self.setObjectName("sidebar")

        self._build()

    def _build(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 16, 12, 16)
        root_layout.setSpacing(0)

        # ── App icon + name ────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(8)

        icon_label = QLabel()
        if _ICON_PATH.exists():
            pix = QPixmap(str(_ICON_PATH)).scaled(
                36, 36, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            icon_label.setPixmap(pix)
        icon_label.setFixedSize(36, 36)
        icon_label.setObjectName("app_icon")
        header.addWidget(icon_label)

        app_name = QLabel("Narracast")
        app_name.setStyleSheet("background: transparent; font-weight: 700; font-size: 16px;")
        header.addWidget(app_name)
        header.addStretch()
        root_layout.addLayout(header)

        root_layout.addSpacing(20)
        root_layout.addWidget(Divider())
        root_layout.addSpacing(12)

        # ── Nav buttons ────────────────────────────────────────────────
        for key, label, icon_name in _NAV_ITEMS:
            btn = QPushButton(label)
            btn.setIcon(icons.muted(icon_name))
            btn.setObjectName("nav")
            btn.setProperty("active", "false")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(38)
            btn.clicked.connect(lambda checked=False, k=key: self._on_nav_click(k))
            self._nav_buttons[key] = btn
            root_layout.addWidget(btn)
            root_layout.addSpacing(2)

        root_layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )

        # ── Status section ─────────────────────────────────────────────
        root_layout.addWidget(Divider())
        root_layout.addSpacing(10)

        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self._status_dot = StatusDot("#16a34a")
        status_row.addWidget(self._status_dot)
        self._device_label = MutedLabel("CPU  •  Offline")
        status_row.addWidget(self._device_label)
        status_row.addStretch()
        root_layout.addLayout(status_row)

        root_layout.addSpacing(8)

        # ── Theme toggle ───────────────────────────────────────────────
        _tm = icons.MOON if not self._dark else icons.SUN
        theme_btn = QPushButton("Dark mode" if not self._dark else "Light mode")
        theme_btn.setIcon(icons.muted(_tm))
        theme_btn.setObjectName("secondary")
        theme_btn.setFixedHeight(30)
        theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        theme_btn.clicked.connect(self._on_theme_toggle)
        self._theme_btn = theme_btn
        root_layout.addWidget(theme_btn)

        # Set the default active page
        self.set_active("generate")

    def _on_nav_click(self, key: str) -> None:
        self.page_requested.emit(key)

    def _on_theme_toggle(self) -> None:
        self._dark = not self._dark
        self._theme_btn.setText("Light mode" if self._dark else "Dark mode")
        self._theme_btn.setIcon(icons.muted(icons.SUN if self._dark else icons.MOON))
        self.theme_toggle_requested.emit()

    def set_active(self, key: str) -> None:
        """Mark a nav button as active and clear the others."""
        self._active_key = key
        for k, btn in self._nav_buttons.items():
            is_active = k == key
            btn.setProperty("active", "true" if is_active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_device(self, device: str) -> None:
        """Update the device label in the status area."""
        label = {"cuda": "NVIDIA GPU", "mps": "Apple GPU", "cpu": "CPU"}.get(device, device)
        if self._device_label is not None:
            self._device_label.setText(f"{label}  •  Offline")

    def set_dark(self, dark: bool) -> None:
        """Sync the theme button text after an external theme change."""
        self._dark = dark
        self._theme_btn.setText("Light mode" if dark else "Dark mode")
        self._theme_btn.setIcon(icons.muted(icons.SUN if dark else icons.MOON))
