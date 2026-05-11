"""Reading page — immersive audiobook reader with synchronized text highlighting."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QTextBlockFormat, QTextCharFormat, QTextCursor, QTextOption
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from narracast.metadata import metadata_path_for_audio
from narracast.playback import (
    PlaybackSession,
    load_bookmarks,
    load_last_position,
    save_bookmark,
    save_last_position,
    delete_bookmark,
)
from narracast.ui.signals import get_signals
from narracast.ui.widgets import Divider, MutedLabel


def _ms_to_time(ms: int) -> str:
    s = ms // 1000
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


_DISPLAY_THEMES = {
    "Warm": {"bg": "#1a1510", "fg": "#e8dcc8", "muted": "#8f7f68", "hl": "#3a2a10"},
    "High Contrast": {"bg": "#000000", "fg": "#ffffff", "muted": "#a8a8a8", "hl": "#1a3a1a"},
    "Night": {"bg": "#0a0f14", "fg": "#8fb0c8", "muted": "#4a6070", "hl": "#0a1f2a"},
}

_SPACING_VALS = {"Compact": 1.2, "Normal": 1.6, "Relaxed": 2.0, "Spacious": 2.6}

_FONT_SIZES = {"S": 13, "M": 16, "L": 20, "XL": 26}


def highlight_span_for_timeline_item(source_text: str, item: dict) -> tuple[int, int] | None:
    """Return the safest text span for a timeline speech item."""
    text = str(item.get("text") or "")
    if not text:
        return None

    try:
        start = int(item.get("text_start"))
        end = int(item.get("text_end"))
    except (TypeError, ValueError):
        start = -1
        end = -1

    if (
        0 <= start < end <= len(source_text)
        and re.sub(r"\s+", " ", source_text[start:end].strip()) == text
    ):
        return start, end

    found = source_text.find(text)
    if found >= 0:
        return found, found + len(text)
    return None


class ReadingPage(QWidget):
    """Immersive audiobook reader."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session: Optional[PlaybackSession] = None
        self._metadata: dict = {}
        self._timeline: list[dict] = []
        self._highlight_units: list[dict] = []
        self._bookmarks: list[dict] = []
        self._meta_path: Optional[Path] = None
        self._duration_ms: int = 0
        self._current_font_size: int = 16
        self._font_name: str = "Georgia"
        self._focus_mode: bool = False
        self._theme_key: str = "Night"
        self._spacing_key: str = "Normal"
        self._auto_pause_paragraphs = False
        self._study_mode = False
        self._last_highlight_key: str | None = None
        self._pacing_paused_keys: set[str] = set()
        self._build_ui()
        self._connect_signals()

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar ─────────────────────────────────────────────────────
        top_bar = QWidget()
        top_bar.setFixedHeight(52)
        top_bar.setStyleSheet("background: #101a27; border-bottom: 1px solid #1a2a3a;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 0, 12, 0)
        top_layout.setSpacing(8)

        self._control_buttons: list[QPushButton] = []
        controls = [
            ("▶ Play", "_play"),
            ("■ Stop", "_stop"),
            ("◀ -10s", "_back"),
            ("+10s ▶", "_forward"),
            ("↺ Repeat", "_repeat"),
        ]
        for label, fn_name in controls:
            btn = QPushButton(label)
            btn.setFixedHeight(32)
            btn.setFixedWidth(80 if len(label) < 7 else 90)
            btn.clicked.connect(getattr(self, fn_name))
            top_layout.addWidget(btn)
            self._control_buttons.append(btn)
            if fn_name == "_play":
                self._play_btn = btn
            elif fn_name == "_stop":
                self._stop_btn = btn
            elif fn_name == "_back":
                self._back_btn = btn
            elif fn_name == "_forward":
                self._forward_btn = btn
            elif fn_name == "_repeat":
                self._repeat_btn = btn

        top_layout.addStretch()

        # Focus mode toggle
        self._focus_btn = QPushButton("Focus Mode")
        self._focus_btn.setObjectName("secondary")
        self._focus_btn.setFixedHeight(32)
        self._focus_btn.setCheckable(True)
        self._focus_btn.toggled.connect(self._toggle_focus_mode)
        top_layout.addWidget(self._focus_btn)

        top_layout.addStretch()

        # Font size buttons
        self._size_btns: dict[str, QPushButton] = {}
        for size in ["S", "M", "L", "XL"]:
            btn = QPushButton(size)
            btn.setFixedSize(32, 32)
            btn.clicked.connect(lambda checked=False, s=size: self._set_font_size(s))
            top_layout.addWidget(btn)
            self._size_btns[size] = btn
        root.addWidget(top_bar)

        # ── Bookmark bar ─────────────────────────────────────────────────
        bm_bar = QWidget()
        bm_bar.setFixedHeight(42)
        bm_bar.setStyleSheet("background: #0a111b; border-bottom: 1px solid #1a2a3a;")
        bm_layout = QHBoxLayout(bm_bar)
        bm_layout.setContentsMargins(12, 0, 12, 0)
        bm_layout.setSpacing(8)

        self._bm_add_btn = QPushButton("🔖 Add here")
        self._bm_add_btn.setFixedHeight(28)
        self._bm_add_btn.clicked.connect(self._add_bookmark)
        bm_layout.addWidget(self._bm_add_btn)

        self._bm_combo = QComboBox()
        self._bm_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._bm_combo.setFixedHeight(28)
        bm_layout.addWidget(self._bm_combo, stretch=1)

        self._bm_jump_btn = QPushButton("⤶ Jump")
        self._bm_jump_btn.setFixedHeight(28)
        self._bm_jump_btn.clicked.connect(self._jump_bookmark)
        bm_layout.addWidget(self._bm_jump_btn)

        self._bm_del_btn = QPushButton("✕ Delete")
        self._bm_del_btn.setFixedHeight(28)
        self._bm_del_btn.clicked.connect(self._delete_bookmark)
        bm_layout.addWidget(self._bm_del_btn)
        root.addWidget(bm_bar)

        # ── Display bar ───────────────────────────────────────────────────
        disp_bar = QWidget()
        disp_bar.setFixedHeight(40)
        disp_bar.setStyleSheet("background: #0f1724; border-bottom: 1px solid #1a2a3a;")
        disp_layout = QHBoxLayout(disp_bar)
        disp_layout.setContentsMargins(12, 0, 12, 0)
        disp_layout.setSpacing(12)

        disp_layout.addWidget(MutedLabel("Theme"))
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(list(_DISPLAY_THEMES.keys()))
        self._theme_combo.setCurrentText("Night")
        self._theme_combo.setFixedHeight(28)
        self._theme_combo.currentTextChanged.connect(self._apply_display_theme)
        disp_layout.addWidget(self._theme_combo)

        disp_layout.addWidget(MutedLabel("Spacing"))
        self._spacing_combo = QComboBox()
        self._spacing_combo.addItems(list(_SPACING_VALS.keys()))
        self._spacing_combo.setCurrentText("Normal")
        self._spacing_combo.setFixedHeight(28)
        self._spacing_combo.currentTextChanged.connect(self._apply_text_spacing)
        disp_layout.addWidget(self._spacing_combo)

        disp_layout.addWidget(MutedLabel("Font"))
        self._font_combo = QComboBox()
        self._font_combo.addItems(["Georgia", "Inter", "Courier New", "Times New Roman"])
        self._font_combo.setCurrentText("Georgia")
        self._font_combo.setFixedHeight(28)
        self._font_combo.currentTextChanged.connect(self._apply_display_font)
        disp_layout.addWidget(self._font_combo)

        self._auto_pause_check = QCheckBox("Pause after paragraph")
        self._auto_pause_check.toggled.connect(self._set_auto_pause_paragraphs)
        disp_layout.addWidget(self._auto_pause_check)

        self._study_mode_check = QCheckBox("Study mode")
        self._study_mode_check.toggled.connect(self._set_study_mode)
        disp_layout.addWidget(self._study_mode_check)

        disp_layout.addStretch()
        root.addWidget(disp_bar)

        # ── Main content area ──────────────────────────────────────────────
        self._content_stack = QStackedWidget()
        root.addWidget(self._content_stack, stretch=1)

        # Page 0: Full text view
        full_widget = QWidget()
        full_layout = QVBoxLayout(full_widget)
        full_layout.setContentsMargins(0, 0, 0, 0)
        self.text_view = QTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        self.text_view.setFont(QFont("Georgia", 16))
        self.text_view.setStyleSheet(
            "QTextEdit { background: #0a0f14; color: #8fb0c8; border: none; padding: 32px 60px; }"
        )
        full_layout.addWidget(self.text_view)
        self._content_stack.addWidget(full_widget)

        # Page 1: Focus view
        self._focus_widget = QWidget()
        self._focus_widget.setStyleSheet("background: #0a0f14;")
        self._focus_layout = QVBoxLayout(self._focus_widget)
        self._focus_layout.setContentsMargins(60, 40, 60, 40)
        self._focus_layout.setSpacing(16)

        self._prev_chunk_label = QLabel("")
        self._prev_chunk_label.setWordWrap(True)
        self._prev_chunk_label.setStyleSheet(
            "color: #4a6070; font-size: 14px; font-style: italic; background: transparent;"
        )
        self._prev_chunk_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._focus_layout.addWidget(self._prev_chunk_label)

        self._focus_layout.addWidget(Divider())

        self._current_frame = QFrame()
        self._current_frame.setStyleSheet(
            "QFrame { background: #0a1f14; border-radius: 8px; border: 1px solid #1a3a1a; }"
        )
        current_inner = QVBoxLayout(self._current_frame)
        current_inner.setContentsMargins(20, 16, 20, 16)
        self._current_chunk_label = QLabel("")
        self._current_chunk_label.setWordWrap(True)
        self._current_chunk_label.setStyleSheet(
            "color: #a3ff73; font-size: 20px; font-weight: 500; background: transparent;"
        )
        self._current_chunk_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        current_inner.addWidget(self._current_chunk_label)
        self._focus_layout.addWidget(self._current_frame)

        self._focus_layout.addWidget(Divider())

        self._next_chunk_label = QLabel("")
        self._next_chunk_label.setWordWrap(True)
        self._next_chunk_label.setStyleSheet(
            "color: #4a6070; font-size: 14px; background: transparent;"
        )
        self._next_chunk_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._focus_layout.addWidget(self._next_chunk_label)
        self._focus_layout.addStretch()
        self._content_stack.addWidget(self._focus_widget)

        # ── Bottom bar ────────────────────────────────────────────────────
        bottom_bar = QWidget()
        bottom_bar.setFixedHeight(52)
        bottom_bar.setStyleSheet("background: #101a27; border-top: 1px solid #1a2a3a;")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(12, 0, 12, 0)
        bottom_layout.setSpacing(10)

        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setRange(0, 1000)
        self._seek_slider.setValue(0)
        self._seek_slider.sliderReleased.connect(self._on_seek)
        bottom_layout.addWidget(self._seek_slider, stretch=1)

        self._time_label = QLabel("00:00 / 00:00")
        self._time_label.setStyleSheet("color: #7f90a8; font-size: 11px; background: transparent;")
        self._time_label.setFixedWidth(110)
        bottom_layout.addWidget(self._time_label)
        root.addWidget(bottom_bar)

        self._set_controls_enabled(False)

    # ── Signal connections ───────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        get_signals().reading_position.connect(self._on_position_update)

    # ── Control state ─────────────────────────────────────────────────────────

    def _set_controls_enabled(self, enabled: bool) -> None:
        for button in self._control_buttons:
            button.setEnabled(enabled)
        for widget in [self._bm_add_btn, self._bm_jump_btn, self._bm_del_btn, self._bm_combo]:
            widget.setEnabled(enabled)
        self._focus_btn.setEnabled(enabled)
        self._seek_slider.setEnabled(enabled)

    # ── Public API ───────────────────────────────────────────────────────────

    def load_file(self, path: str) -> None:
        """Load an audio file and its metadata into the reader."""
        audio_path = Path(path)
        if not audio_path.exists():
            return

        # Stop any current session
        if self._session:
            self._session.stop()
            self._session = None

        # Load metadata
        self._meta_path = metadata_path_for_audio(audio_path)
        try:
            self._metadata = json.loads(self._meta_path.read_text(encoding="utf-8"))
        except Exception:
            self._metadata = {}

        self._timeline = self._metadata.get("timeline", [])
        self._highlight_units = self._metadata.get("highlight_units") or [
            item for item in self._timeline if item.get("type") == "speech"
        ]
        self._last_highlight_key = None
        self._pacing_paused_keys.clear()
        source_text = self._metadata.get("source_text", "")
        self._duration_ms = self._metadata.get("duration_ms", 0)
        if not source_text or not self._timeline:
            source_text = "This MP3 does not have Narracast reading metadata. Use Play (audio only) from History."
            self._duration_ms = self._duration_ms or 0

        # Populate text view
        self.text_view.setPlainText(source_text)
        self._apply_text_spacing(self._spacing_key)

        # Load bookmarks and last position
        self._bookmarks = load_bookmarks(str(self._meta_path))
        self._refresh_bookmark_combo()
        last_pos = load_last_position(str(self._meta_path))

        # Update time label
        total_str = _ms_to_time(self._duration_ms)
        pos_str = _ms_to_time(last_pos)
        self._time_label.setText(f"{pos_str} / {total_str}")

        # Create playback session
        self._session = PlaybackSession(
            file_path=str(audio_path),
            duration_ms=self._duration_ms,
            on_position=lambda ms: get_signals().reading_position.emit(ms),
            on_done=self._on_playback_done,
        )
        if last_pos > 0:
            self._session._offset_ms = last_pos

        self._set_controls_enabled(True)

    def shutdown(self) -> None:
        """Stop playback and persist the current reader position."""
        self._stop()

    # ── Playback actions ──────────────────────────────────────────────────────

    def _play(self) -> None:
        if not self._session:
            return
        if self._session.is_playing():
            self._session.pause_and_get_position()
            self._play_btn.setText("▶ Play")
        else:
            self._session.play(from_ms=self._session._offset_ms)
            self._play_btn.setText("⏸ Pause")
            if self._study_mode:
                self._time_label.setText(
                    f"{_ms_to_time(self._session._offset_ms)} / {_ms_to_time(self._duration_ms)}"
                )

    def _stop(self) -> None:
        if self._session:
            pos = self._session.pause_and_get_position()
            if self._meta_path:
                save_last_position(str(self._meta_path), pos)
        self._play_btn.setText("▶ Play")

    def _back(self) -> None:
        if self._session:
            self._session.back(10)

    def _forward(self) -> None:
        if self._session:
            self._session.forward(10)

    def _repeat(self) -> None:
        if self._session:
            self._session.repeat_chunk(self._highlight_units or self._timeline)

    def _on_playback_done(self) -> None:
        self._play_btn.setText("▶ Play")

    # ── Position update ───────────────────────────────────────────────────────

    def _on_position_update(self, ms: int) -> None:
        if self._duration_ms > 0:
            frac = ms / self._duration_ms
            self._seek_slider.blockSignals(True)
            self._seek_slider.setValue(int(frac * 1000))
            self._seek_slider.blockSignals(False)

        total_str = _ms_to_time(self._duration_ms)
        pos_str = _ms_to_time(ms)
        self._time_label.setText(f"{pos_str} / {total_str}")

        if self._maybe_auto_pause_paragraph(ms):
            self._highlight_current_chunk(ms)
            return

        self._highlight_current_chunk(ms)

    def _on_seek(self) -> None:
        if not self._session or self._duration_ms == 0:
            return
        frac = self._seek_slider.value() / 1000.0
        target_ms = int(frac * self._duration_ms)
        self._session.seek(target_ms)

    # ── Text highlighting ─────────────────────────────────────────────────────

    def _highlight_current_chunk(self, position_ms: int) -> None:
        """Highlight the current speech chunk in the full text view."""
        # Find current item in timeline
        current_item = None
        prev_item = None
        next_item = None
        speech_items = self._highlight_units or [
            x for x in self._timeline if x.get("type") == "speech"
        ]

        for i, item in enumerate(speech_items):
            if item["audio_start_ms"] <= position_ms < item["audio_end_ms"]:
                current_item = item
                prev_item = speech_items[i - 1] if i > 0 else None
                next_item = speech_items[i + 1] if i < len(speech_items) - 1 else None
                break

        if current_item is None:
            return

        chunk_text = current_item.get("text", "")
        source_text = self._metadata.get("source_text", self.text_view.toPlainText())
        self._maybe_study_pause(current_item)

        # Update focus view
        self._prev_chunk_label.setText(prev_item.get("text", "") if prev_item else "")
        self._current_chunk_label.setText(chunk_text)
        self._next_chunk_label.setText(next_item.get("text", "") if next_item else "")

        # Highlight in full text view
        doc = self.text_view.document()
        cursor = QTextCursor(doc)
        cursor.select(QTextCursor.SelectionType.Document)

        # Clear all highlights first
        fmt_clear = QTextCharFormat()
        fmt_clear.setBackground(QColor("transparent"))
        cursor.mergeCharFormat(fmt_clear)

        span = highlight_span_for_timeline_item(source_text, current_item)
        if span:
            start, end = span
            search_cursor = QTextCursor(doc)
            search_cursor.setPosition(start)
            search_cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            fmt_hl = QTextCharFormat()
            fmt_hl.setBackground(QColor("#1a3a1a"))
            fmt_hl.setForeground(QColor("#a3ff73"))
            search_cursor.mergeCharFormat(fmt_hl)
            self.text_view.setTextCursor(search_cursor)
            self.text_view.ensureCursorVisible()

    # ── Bookmarks ─────────────────────────────────────────────────────────────

    def _refresh_bookmark_combo(self) -> None:
        self._bm_combo.clear()
        for bm in self._bookmarks:
            label = bm.get("label", "")
            pos = bm.get("position_ms", 0)
            self._bm_combo.addItem(f"{label}  [{_ms_to_time(pos)}]", pos)

    def _add_bookmark(self) -> None:
        if not self._session or not self._meta_path:
            return
        pos = self._session.position_ms
        label = f"Bookmark {len(self._bookmarks) + 1}"
        save_bookmark(str(self._meta_path), label, pos)
        self._bookmarks = load_bookmarks(str(self._meta_path))
        self._refresh_bookmark_combo()

    def _jump_bookmark(self) -> None:
        if not self._session:
            return
        pos = self._bm_combo.currentData()
        if pos is not None:
            self._session.seek(pos)

    def _delete_bookmark(self) -> None:
        if not self._meta_path:
            return
        idx = self._bm_combo.currentIndex()
        if idx >= 0:
            delete_bookmark(str(self._meta_path), idx)
            self._bookmarks = load_bookmarks(str(self._meta_path))
            self._refresh_bookmark_combo()

    # ── Focus mode ────────────────────────────────────────────────────────────

    def _toggle_focus_mode(self, enabled: bool) -> None:
        self._focus_mode = enabled
        self._content_stack.setCurrentIndex(1 if enabled else 0)
        self._focus_btn.setText("Exit Focus" if enabled else "Focus Mode")

    def _set_auto_pause_paragraphs(self, enabled: bool) -> None:
        self._auto_pause_paragraphs = enabled

    def _set_study_mode(self, enabled: bool) -> None:
        self._study_mode = enabled
        if not enabled:
            self._last_highlight_key = None

    def _maybe_auto_pause_paragraph(self, position_ms: int) -> bool:
        if not self._auto_pause_paragraphs or not self._session or not self._session.is_playing():
            return False
        for idx, item in enumerate(self._timeline):
            if item.get("type") != "pause":
                continue
            start = int(item.get("audio_start_ms", -1))
            end = int(item.get("audio_end_ms", -1))
            key = f"paragraph:{idx}:{start}"
            if start <= position_ms < end and key not in self._pacing_paused_keys:
                self._pacing_paused_keys.add(key)
                self._pause_for_pacing("Paused after paragraph. Press Play when ready.")
                return True
        return False

    def _maybe_study_pause(self, current_item: dict) -> None:
        key = self._pacing_key(current_item)
        if key is None:
            return
        should_pause = (
            self._study_mode
            and self._session is not None
            and self._session.is_playing()
            and self._last_highlight_key is not None
            and key != self._last_highlight_key
            and key not in self._pacing_paused_keys
        )
        self._last_highlight_key = key
        if should_pause:
            self._pacing_paused_keys.add(key)
            self._pause_for_pacing("Study pause. Press Play for the next sentence.")

    def _pause_for_pacing(self, message: str) -> None:
        if not self._session:
            return
        pos = self._session.pause_and_get_position()
        if self._meta_path:
            save_last_position(str(self._meta_path), pos)
        self._play_btn.setText("▶ Play")
        self._time_label.setText(f"{_ms_to_time(pos)} / {_ms_to_time(self._duration_ms)}  •  {message}")

    def _pacing_key(self, item: dict) -> str | None:
        try:
            start = int(item.get("audio_start_ms"))
        except (TypeError, ValueError):
            return None
        unit = item.get("unit_index", item.get("chunk_index", item.get("text_start", "")))
        return f"{item.get('type')}:{unit}:{start}"

    # ── Display theme / font ──────────────────────────────────────────────────

    def _apply_display_theme(self, theme_name: str) -> None:
        self._theme_key = theme_name
        self._apply_reader_display()

    def _apply_display_font(self, font_name: str) -> None:
        self._font_name = font_name
        self._apply_reader_display()

    def _apply_text_spacing(self, spacing_name: str) -> None:
        self._spacing_key = spacing_name
        self._apply_reader_display()

    def _apply_reader_display(self) -> None:
        theme = _DISPLAY_THEMES.get(self._theme_key, _DISPLAY_THEMES["Night"])
        self.text_view.setStyleSheet(
            f"QTextEdit {{ background: {theme['bg']}; color: {theme['fg']}; "
            f"border: none; padding: 32px 60px; }}"
        )
        self.text_view.setFont(QFont(self._font_name, self._current_font_size))

        multiplier = _SPACING_VALS.get(self._spacing_key, _SPACING_VALS["Normal"])
        block_fmt = QTextBlockFormat()
        block_fmt.setLineHeight(int(multiplier * 100), QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        block_fmt.setBottomMargin(max(0, (multiplier - 1.0) * 8))

        cursor = QTextCursor(self.text_view.document())
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.mergeBlockFormat(block_fmt)

        prev_next_size = max(12, int(self._current_font_size * 0.85))
        self._focus_widget.setStyleSheet(f"background: {theme['bg']};")
        self._focus_layout.setSpacing(int(10 * multiplier))
        self._prev_chunk_label.setFont(QFont(self._font_name, prev_next_size))
        self._current_chunk_label.setFont(QFont(self._font_name, self._current_font_size + 4))
        self._next_chunk_label.setFont(QFont(self._font_name, prev_next_size))
        self._prev_chunk_label.setStyleSheet(
            f"color: {theme['muted']}; font-style: italic; background: transparent;"
        )
        self._current_chunk_label.setStyleSheet(
            f"color: {theme['fg']}; font-weight: 600; background: transparent;"
        )
        self._next_chunk_label.setStyleSheet(
            f"color: {theme['muted']}; background: transparent;"
        )
        self._current_frame.setStyleSheet(
            f"QFrame {{ background: {theme['hl']}; border-radius: 8px; border: 1px solid #16a34a; }}"
        )

    def _set_font_size(self, size_key: str) -> None:
        self._current_font_size = _FONT_SIZES.get(size_key, 16)
        self._apply_reader_display()

    def apply_settings(self, settings: dict) -> None:
        theme = str(settings.get("reader_theme") or self._theme_key)
        if theme in _DISPLAY_THEMES:
            self._theme_combo.setCurrentText(theme)

        spacing = str(settings.get("reader_spacing") or self._spacing_key)
        if spacing in _SPACING_VALS:
            self._spacing_combo.setCurrentText(spacing)

        font = str(settings.get("reader_font") or self._font_name)
        idx = self._font_combo.findText(font)
        if idx >= 0:
            self._font_combo.setCurrentIndex(idx)

        size = str(settings.get("reader_size") or "M")
        if size in _FONT_SIZES:
            self._set_font_size(size)
        else:
            self._apply_reader_display()

        self._auto_pause_check.setChecked(bool(settings.get("reader_auto_pause_paragraphs", False)))
        self._study_mode_check.setChecked(bool(settings.get("reader_study_mode", False)))

    def current_settings(self) -> dict:
        size_key = next(
            (key for key, value in _FONT_SIZES.items() if value == self._current_font_size),
            "M",
        )
        return {
            "reader_theme": self._theme_key,
            "reader_spacing": self._spacing_key,
            "reader_font": self._font_name,
            "reader_size": size_key,
            "reader_auto_pause_paragraphs": self._auto_pause_paragraphs,
            "reader_study_mode": self._study_mode,
        }
