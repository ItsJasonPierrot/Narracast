"""Reusable PySide6 widgets for Narracast."""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QPainter, QBrush
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QWidget,
)


class Card(QFrame):
    """A styled card container widget."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setFrameShape(QFrame.Shape.StyledPanel)


class SectionLabel(QLabel):
    """Small uppercase section heading label."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("section")


class MutedLabel(QLabel):
    """Muted / secondary text label."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("muted")


class ChipButton(QPushButton):
    """Compact chip-style action button."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("chip")
        self.setFixedHeight(24)


class StatusDot(QWidget):
    """Paints a small filled circle indicator."""

    def __init__(
        self,
        color: str = "#16a34a",
        size: int = 8,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self._dot_size = size
        self.setFixedSize(QSize(size + 4, size + 4))

    @property
    def color(self) -> str:
        return self._color.name()

    @color.setter
    def color(self, value: str) -> None:
        self._color = QColor(value)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(self._color))
        painter.setPen(Qt.PenStyle.NoPen)
        offset = (self.width() - self._dot_size) // 2
        painter.drawEllipse(offset, offset, self._dot_size, self._dot_size)


class Divider(QFrame):
    """Thin horizontal line divider."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        self.setStyleSheet("background: #1a2a3a; border: none; max-height: 1px; margin: 4px 0;")
