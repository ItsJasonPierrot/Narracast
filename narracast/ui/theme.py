"""Narracast dark/light theme stylesheets."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication


# ---------------------------------------------------------------------------
# Dark stylesheet
# ---------------------------------------------------------------------------
DARK_QSS = """
/* ── Global ─────────────────────────────────────────────── */
QMainWindow, QDialog {
    background: #0f1724;
    color: #e9f1ff;
}

QWidget {
    background: #0f1724;
    color: #e9f1ff;
    font-family: "Arial";
    font-size: 13px;
}

/* ── Cards ───────────────────────────────────────────────── */
QFrame#card {
    background: #121e2d;
    border: 1px solid #2d3b4f;
    border-radius: 8px;
}

/* ── Buttons ──────────────────────────────────────────────── */
QPushButton {
    background: #1a2a3a;
    color: #e9f1ff;
    border: 1px solid #2d3b4f;
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 13px;
}
QPushButton:hover {
    background: #1e3248;
    border-color: #3b4d63;
}
QPushButton:pressed {
    background: #152030;
}
QPushButton:disabled {
    color: #3a4a5a;
    border-color: #1e2a3a;
    background: #111a26;
}

QPushButton#primary {
    background: #16a34a;
    color: #ffffff;
    border: 1px solid #16a34a;
    font-weight: 600;
}
QPushButton#primary:hover {
    background: #15803d;
    border-color: #15803d;
}
QPushButton#primary:pressed {
    background: #14532d;
}
QPushButton#primary:disabled {
    background: #0f2318;
    color: #3a5a3a;
    border-color: #1a3a1a;
}

QPushButton#secondary {
    background: #0f1724;
    color: #a3ff73;
    border: 1px solid #2d5a1a;
    border-radius: 6px;
}
QPushButton#secondary:hover {
    background: #0f2318;
    border-color: #3d7a2a;
}

QPushButton#nav {
    background: transparent;
    color: #7f90a8;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 9px 12px;
    text-align: left;
    font-size: 13px;
}
QPushButton#nav:hover {
    background: #131f2e;
    color: #e9f1ff;
    border-color: #2d3b4f;
}
QPushButton#nav[active="true"] {
    background: #0f2318;
    color: #eaffef;
    border: 1px solid #2d5a1a;
}

/* Small chip buttons */
QPushButton#chip {
    background: #0d1724;
    color: #7f90a8;
    border: 1px solid #3b4d63;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
}
QPushButton#chip:hover {
    background: #1a2a3a;
    color: #e9f1ff;
}

/* Danger / delete buttons */
QPushButton#danger {
    background: #3a0a0a;
    color: #f87171;
    border: 1px solid #7a1a1a;
}
QPushButton#danger:hover {
    background: #5a1010;
}

/* ── Inputs ─────────────────────────────────────────────── */
QLineEdit, QSpinBox, QDoubleSpinBox {
    background: #0d1724;
    color: #e9f1ff;
    border: 1px solid #3b4d63;
    border-radius: 5px;
    padding: 6px 10px;
    selection-background-color: #16a34a;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #16a34a;
}
QLineEdit:disabled {
    color: #3a4a5a;
    background: #0a111b;
}

QComboBox {
    background: #0d1724;
    color: #e9f1ff;
    border: 1px solid #3b4d63;
    border-radius: 5px;
    padding: 6px 10px;
    selection-background-color: #16a34a;
}
QComboBox:focus {
    border-color: #16a34a;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #7f90a8;
    width: 0;
    height: 0;
}
QComboBox QAbstractItemView {
    background: #121e2d;
    border: 1px solid #2d3b4f;
    color: #e9f1ff;
    selection-background-color: #0f2318;
    selection-color: #a3ff73;
}

QTextEdit, QPlainTextEdit {
    background: #0d1724;
    color: #e9f1ff;
    border: 1px solid #3b4d63;
    border-radius: 5px;
    padding: 8px;
    selection-background-color: #16a34a;
    font-family: "Arial";
}
QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #16a34a;
}

/* ── Progress bar ────────────────────────────────────────── */
QProgressBar {
    background: #0a111b;
    border: 1px solid #2d3b4f;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background: #16a34a;
    border-radius: 3px;
}

/* ── Scrollbars ─────────────────────────────────────────── */
QScrollBar:vertical {
    background: #0a111b;
    width: 8px;
    border: none;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #2d3b4f;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #3b4d63;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

QScrollBar:horizontal {
    background: #0a111b;
    height: 8px;
    border: none;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #2d3b4f;
    border-radius: 4px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover {
    background: #3b4d63;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Tree/List widgets ──────────────────────────────────── */
QTreeWidget, QListWidget {
    background: #0d1724;
    color: #e9f1ff;
    border: 1px solid #2d3b4f;
    border-radius: 5px;
    alternate-background-color: #121e2d;
    outline: none;
}
QTreeWidget::item, QListWidget::item {
    padding: 4px 8px;
    border-bottom: 1px solid #1a2a3a;
}
QTreeWidget::item:selected, QListWidget::item:selected {
    background: #0f2318;
    color: #a3ff73;
}
QTreeWidget::item:hover, QListWidget::item:hover {
    background: #131f2e;
}
QHeaderView::section {
    background: #0a111b;
    color: #7f90a8;
    border: none;
    border-bottom: 1px solid #2d3b4f;
    padding: 6px 8px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ── Slider ─────────────────────────────────────────────── */
QSlider::groove:horizontal {
    background: #1a2a3a;
    height: 4px;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #16a34a;
    width: 14px;
    height: 14px;
    border-radius: 7px;
    margin: -5px 0;
}
QSlider::sub-page:horizontal {
    background: #16a34a;
    border-radius: 2px;
}

/* ── Labels ─────────────────────────────────────────────── */
QLabel {
    background: transparent;
    color: #e9f1ff;
}
QLabel#muted {
    color: #7f90a8;
    font-size: 12px;
}
QLabel#section {
    color: #7f90a8;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    font-weight: 600;
}
QLabel#h2 {
    font-size: 20px;
    font-weight: 700;
    color: #e9f1ff;
}

/* ── Status bar ─────────────────────────────────────────── */
QStatusBar {
    background: #101a27;
    color: #7f90a8;
    border-top: 1px solid #1a2a3a;
    font-size: 11px;
}
QStatusBar::item { border: none; }

/* ── Check boxes ─────────────────────────────────────────── */
QCheckBox {
    color: #e9f1ff;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #3b4d63;
    border-radius: 3px;
    background: #0d1724;
}
QCheckBox::indicator:checked {
    background: #16a34a;
    border-color: #16a34a;
}

/* ── Splitter ─────────────────────────────────────────────── */
QSplitter::handle { background: #1a2a3a; width: 1px; }

/* ── Tool tip ────────────────────────────────────────────── */
QToolTip {
    background: #121e2d;
    color: #e9f1ff;
    border: 1px solid #2d3b4f;
    padding: 4px 8px;
    border-radius: 4px;
}
"""


# ---------------------------------------------------------------------------
# Light stylesheet
# ---------------------------------------------------------------------------
LIGHT_QSS = """
QMainWindow, QDialog { background: #f0f4f8; color: #1a2a3a; }
QWidget {
    background: #f0f4f8;
    color: #1a2a3a;
    font-family: "Arial";
    font-size: 13px;
}
QFrame#card {
    background: #ffffff;
    border: 1px solid #d0d8e4;
    border-radius: 8px;
}
QPushButton {
    background: #e8eef5;
    color: #1a2a3a;
    border: 1px solid #c0ccd8;
    border-radius: 6px;
    padding: 7px 16px;
}
QPushButton:hover { background: #d8e4f0; }
QPushButton#primary {
    background: #16a34a;
    color: #ffffff;
    border: 1px solid #16a34a;
    font-weight: 600;
}
QPushButton#primary:hover { background: #15803d; }
QPushButton#secondary {
    background: #f0fff4;
    color: #16a34a;
    border: 1px solid #a3e0b4;
}
QPushButton#nav {
    background: transparent;
    color: #4a6a8a;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 9px 12px;
    text-align: left;
}
QPushButton#nav:hover { background: #e0eaf5; }
QPushButton#nav[active="true"] {
    background: #dcfce7;
    color: #15803d;
    border: 1px solid #86efac;
}
QPushButton#chip {
    background: #e8eef5;
    color: #4a6a8a;
    border: 1px solid #c0ccd8;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
}
QPushButton#danger { background: #fee2e2; color: #dc2626; border: 1px solid #fca5a5; }
QLineEdit, QSpinBox, QDoubleSpinBox {
    background: #ffffff;
    color: #1a2a3a;
    border: 1px solid #c0ccd8;
    border-radius: 5px;
    padding: 6px 10px;
}
QLineEdit:focus, QSpinBox:focus { border-color: #16a34a; }
QComboBox {
    background: #ffffff;
    color: #1a2a3a;
    border: 1px solid #c0ccd8;
    border-radius: 5px;
    padding: 6px 10px;
}
QComboBox QAbstractItemView { background: #ffffff; color: #1a2a3a; border: 1px solid #c0ccd8; }
QTextEdit, QPlainTextEdit {
    background: #ffffff;
    color: #1a2a3a;
    border: 1px solid #c0ccd8;
    border-radius: 5px;
    padding: 8px;
}
QProgressBar {
    background: #e8eef5;
    border: 1px solid #c0ccd8;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk { background: #16a34a; border-radius: 3px; }
QScrollBar:vertical { background: #e8eef5; width: 8px; border: none; border-radius: 4px; }
QScrollBar::handle:vertical { background: #a0b0c0; border-radius: 4px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: #e8eef5; height: 8px; border: none; }
QScrollBar::handle:horizontal { background: #a0b0c0; border-radius: 4px; min-width: 24px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QTreeWidget, QListWidget {
    background: #ffffff;
    color: #1a2a3a;
    border: 1px solid #c0ccd8;
    border-radius: 5px;
}
QTreeWidget::item:selected, QListWidget::item:selected { background: #dcfce7; color: #15803d; }
QHeaderView::section { background: #e8eef5; color: #4a6a8a; border: none; border-bottom: 1px solid #c0ccd8; padding: 6px 8px; }
QSlider::groove:horizontal { background: #d0d8e4; height: 4px; border-radius: 2px; }
QSlider::handle:horizontal { background: #16a34a; width: 14px; height: 14px; border-radius: 7px; margin: -5px 0; }
QSlider::sub-page:horizontal { background: #16a34a; border-radius: 2px; }
QLabel { background: transparent; color: #1a2a3a; }
QLabel#muted { color: #4a6a8a; font-size: 12px; }
QLabel#section { color: #6a8aaa; font-size: 10px; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 600; }
QLabel#h2 { font-size: 20px; font-weight: 700; color: #1a2a3a; }
QStatusBar { background: #e8eef5; color: #4a6a8a; border-top: 1px solid #c0ccd8; font-size: 11px; }
QStatusBar::item { border: none; }
QCheckBox { color: #1a2a3a; spacing: 6px; }
QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #c0ccd8; border-radius: 3px; background: #ffffff; }
QCheckBox::indicator:checked { background: #16a34a; border-color: #16a34a; }
QToolTip { background: #ffffff; color: #1a2a3a; border: 1px solid #c0ccd8; padding: 4px 8px; border-radius: 4px; }
"""


def apply_theme(app: QApplication, dark: bool = True) -> None:
    """Apply the dark or light stylesheet to the application."""
    app.setStyleSheet(DARK_QSS if dark else LIGHT_QSS)
