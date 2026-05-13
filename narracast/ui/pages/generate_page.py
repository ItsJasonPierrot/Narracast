"""Generate Speech page — the main production UI."""

from __future__ import annotations

import subprocess
import threading
import hashlib
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from narracast.audio_generation import generate_core
from narracast.audio_polish import AudioPolishSettings, VALID_BITRATES
from narracast.output_files import load_file
from narracast.presets import DEFAULT_PRESET, GENERATION_PRESETS
from narracast.queue_manager import add_to_queue
from narracast.text_cleanup import (
    apply_all,
    clean_pdf_text,
    fix_hyphenated_line_breaks,
    normalize_whitespace,
    remove_page_numbers,
    strip_urls,
)
from narracast.voices import get_voice_files, reference_signature, reference_warning
from narracast.ui.benchmark_dialog import BenchmarkDialog
from narracast.ui.signals import get_signals
from narracast.ui.timing_dialog import TimingAnalysisDialog
from narracast.ui import icons
from narracast.ui.widgets import Card, ChipButton, MutedLabel, SectionLabel, StatusDot


class FileDropTextEdit(QTextEdit):
    """Text editor that accepts dropped .txt and .pdf files."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._has_supported_file(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if self._has_supported_file(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        path = self._first_supported_path(event.mimeData())
        if path:
            self.setPlainText(load_file(path))
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def _has_supported_file(self, mime_data) -> bool:
        return self._first_supported_path(mime_data) is not None

    def _first_supported_path(self, mime_data) -> str | None:
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.suffix.lower() in (".txt", ".pdf"):
                return str(path)
        return None


class GeneratePage(QWidget):
    """Main generate-speech page."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._play_proc: Optional[subprocess.Popen] = None
        self._last_output_path: Optional[str] = None
        self._benchmark_dialog: Optional[BenchmarkDialog] = None
        self._timing_dialog: Optional[TimingAnalysisDialog] = None
        self._preview_cache: dict[str, str] = {}
        self._raw_text_snapshot = ""
        self._cleaned_text_snapshot = ""
        self._model_ready = False
        self._build_ui()
        self._connect_signals()
        self._populate_voices()
        self._set_generation_buttons_enabled(False)

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Left scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(scroll.Shape.NoFrame)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(16, 18, 12, 18)
        left_layout.setSpacing(12)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(left_widget)
        root.addWidget(scroll, stretch=1)

        # Right rail
        right_widget = QWidget()
        right_widget.setMinimumWidth(220)
        right_widget.setMaximumWidth(280)
        right_widget.setStyleSheet("background: #0a111b; border-left: 1px solid #1a2a3a;")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(12, 20, 12, 20)
        right_layout.setSpacing(12)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        root.addWidget(right_widget)

        self._build_left(left_layout)
        self._build_right(right_layout)

    def _build_left(self, layout: QVBoxLayout) -> None:
        # ── Header ─────────────────────────────────────────────────────
        h2 = QLabel("Generate Speech")
        h2.setObjectName("h2")
        layout.addWidget(h2)

        subtitle = MutedLabel("Convert text to natural-sounding speech using F5-TTS.")
        layout.addWidget(subtitle)

        layout.addSpacing(4)

        # ── Text input card ─────────────────────────────────────────────
        text_card = Card()
        text_card_layout = QVBoxLayout(text_card)
        text_card_layout.setContentsMargins(16, 14, 16, 14)
        text_card_layout.setSpacing(8)

        text_card_layout.addWidget(SectionLabel("Your text"))

        self.text_edit = FileDropTextEdit()
        self.text_edit.setPlaceholderText("Enter or paste your text here…")
        self.text_edit.setMinimumHeight(180)
        self.text_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        text_card_layout.addWidget(self.text_edit)

        self._count_label = MutedLabel("0 characters  •  0 words  •  0 paragraphs")
        text_card_layout.addWidget(self._count_label)
        layout.addWidget(text_card)

        # ── Cleanup toolbar ─────────────────────────────────────────────
        cleanup_row = QHBoxLayout()
        cleanup_row.setSpacing(6)
        cleanup_row.addWidget(MutedLabel("Clean:"))
        for label, fn in [
            ("⎵ Spaces", lambda: self._apply_cleanup(normalize_whitespace)),
            ("⟐ Hyphens", lambda: self._apply_cleanup(fix_hyphenated_line_breaks)),
            ("# Page nos", lambda: self._apply_cleanup(remove_page_numbers)),
            ("🔗 URLs", lambda: self._apply_cleanup(strip_urls)),
            ("✨ All", lambda: self._apply_cleanup(apply_all)),
            ("📄 PDF clean", self._apply_pdf_cleanup),
        ]:
            btn = ChipButton(label)
            btn.clicked.connect(fn)
            cleanup_row.addWidget(btn)
        self.raw_text_btn = ChipButton("Raw")
        self.raw_text_btn.setEnabled(False)
        self.raw_text_btn.clicked.connect(self._show_raw_text)
        cleanup_row.addWidget(self.raw_text_btn)
        self.cleaned_text_btn = ChipButton("Cleaned")
        self.cleaned_text_btn.setEnabled(False)
        self.cleaned_text_btn.clicked.connect(self._show_cleaned_text)
        cleanup_row.addWidget(self.cleaned_text_btn)
        cleanup_row.addStretch()
        layout.addLayout(cleanup_row)

        # ── Metadata row ────────────────────────────────────────────────
        meta_card = Card()
        meta_layout = QFormLayout(meta_card)
        meta_layout.setContentsMargins(16, 12, 16, 12)
        meta_layout.setSpacing(8)
        meta_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("e.g. The Great Gatsby")
        meta_layout.addRow("Book title:", self.title_edit)

        self.part_edit = QLineEdit()
        self.part_edit.setPlaceholderText("e.g. Chapter 1")
        meta_layout.addRow("Part / chapter:", self.part_edit)
        layout.addWidget(meta_card)

        # ── Voice + Speed row ───────────────────────────────────────────
        vs_card = Card()
        vs_layout = QHBoxLayout(vs_card)
        vs_layout.setContentsMargins(16, 12, 16, 12)
        vs_layout.setSpacing(16)

        # Voice
        voice_col = QVBoxLayout()
        voice_col.setSpacing(4)
        voice_col.addWidget(SectionLabel("Voice"))
        self.voice_combo = QComboBox()
        self.voice_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        voice_col.addWidget(self.voice_combo)
        vs_layout.addLayout(voice_col, stretch=2)

        # Speed
        speed_col = QVBoxLayout()
        speed_col.setSpacing(4)
        speed_header = QHBoxLayout()
        speed_header.addWidget(SectionLabel("Speed"))
        self._speed_label = QLabel("1.0×")
        self._speed_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        speed_header.addWidget(self._speed_label)
        speed_col.addLayout(speed_header)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(500, 2000)
        self.speed_slider.setValue(1000)
        self.speed_slider.setTickInterval(100)
        speed_col.addWidget(self.speed_slider)
        vs_layout.addLayout(speed_col, stretch=1)
        layout.addWidget(vs_card)

        # ── Mode + Pause row ─────────────────────────────────────────────
        mp_card = Card()
        mp_layout = QHBoxLayout(mp_card)
        mp_layout.setContentsMargins(16, 12, 16, 12)
        mp_layout.setSpacing(16)

        mode_col = QVBoxLayout()
        mode_col.setSpacing(4)
        mode_col.addWidget(SectionLabel("Mode"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(list(GENERATION_PRESETS.keys()))
        idx = list(GENERATION_PRESETS.keys()).index(DEFAULT_PRESET)
        self.mode_combo.setCurrentIndex(idx)
        mode_col.addWidget(self.mode_combo)
        self._mode_desc = MutedLabel(GENERATION_PRESETS[DEFAULT_PRESET]["description"])
        mode_col.addWidget(self._mode_desc)
        mp_layout.addLayout(mode_col, stretch=2)

        pause_col = QVBoxLayout()
        pause_col.setSpacing(4)
        pause_header = QHBoxLayout()
        pause_header.addWidget(SectionLabel("Paragraph pause"))
        self._pause_label = QLabel("0.5s")
        self._pause_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        pause_header.addWidget(self._pause_label)
        pause_col.addLayout(pause_header)

        self.pause_slider = QSlider(Qt.Orientation.Horizontal)
        self.pause_slider.setRange(0, 2000)
        self.pause_slider.setValue(500)
        self.pause_slider.setTickInterval(100)
        pause_col.addWidget(self.pause_slider)
        mp_layout.addLayout(pause_col, stretch=1)

        sentence_pause_col = QVBoxLayout()
        sentence_pause_col.setSpacing(4)
        sentence_pause_header = QHBoxLayout()
        sentence_pause_header.addWidget(SectionLabel("Sentence pause"))
        self._sentence_pause_label = QLabel("0.0s")
        self._sentence_pause_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        sentence_pause_header.addWidget(self._sentence_pause_label)
        sentence_pause_col.addLayout(sentence_pause_header)

        self.sentence_pause_slider = QSlider(Qt.Orientation.Horizontal)
        self.sentence_pause_slider.setRange(0, 1000)
        self.sentence_pause_slider.setValue(0)
        self.sentence_pause_slider.setTickInterval(100)
        sentence_pause_col.addWidget(self.sentence_pause_slider)
        sentence_pause_col.addWidget(MutedLabel("Adds generated silence between sentences."))
        mp_layout.addLayout(sentence_pause_col, stretch=1)
        layout.addWidget(mp_card)

        # ── Advanced polish ──────────────────────────────────────────────
        self._build_advanced(layout)

        # ── Action buttons ───────────────────────────────────────────────
        self.gen_btn = QPushButton("Generate MP3")
        self.gen_btn.setIcon(icons.accent(icons.MICROPHONE))
        self.gen_btn.setObjectName("primary")
        self.gen_btn.setFixedHeight(40)
        self.gen_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.gen_btn)

        action_row = QHBoxLayout()
        self.preview_btn = QPushButton("Preview first section")
        self.preview_btn.setIcon(icons.icon(icons.PLAY))
        self.preview_btn.setFixedHeight(36)
        self.queue_btn = QPushButton("Queue it")
        self.queue_btn.setIcon(icons.icon(icons.PLAYLIST_ADD))
        self.queue_btn.setObjectName("secondary")
        self.queue_btn.setFixedHeight(36)
        action_row.addWidget(self.preview_btn, stretch=1)
        action_row.addWidget(self.queue_btn, stretch=1)
        layout.addLayout(action_row)

        layout.addStretch()

    def _build_advanced(self, layout: QVBoxLayout) -> None:
        """Collapsible Advanced audio-polish controls."""
        # Toggle button
        self._adv_toggle = QPushButton("Advanced")
        self._adv_toggle.setIcon(icons.muted(icons.COG))
        self._adv_toggle.setObjectName("chip")
        self._adv_toggle.setFixedHeight(28)
        self._adv_toggle.setCheckable(True)
        self._adv_toggle.setChecked(False)
        self._adv_toggle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(self._adv_toggle)

        # Container (hidden by default)
        self._adv_frame = QFrame()
        self._adv_frame.setFrameShape(QFrame.Shape.NoFrame)
        self._adv_frame.setVisible(False)
        adv_layout = QVBoxLayout(self._adv_frame)
        adv_layout.setContentsMargins(0, 4, 0, 0)
        adv_layout.setSpacing(10)

        adv_card = QFrame()
        adv_card.setObjectName("card")
        inner = QVBoxLayout(adv_card)
        inner.setContentsMargins(16, 14, 16, 14)
        inner.setSpacing(12)

        # Row 1 — Bitrate + Normalize
        row1 = QHBoxLayout()
        row1.setSpacing(16)

        bitrate_col = QVBoxLayout()
        bitrate_col.setSpacing(4)
        from narracast.ui.widgets import SectionLabel
        bitrate_col.addWidget(SectionLabel("MP3 bitrate"))
        self.bitrate_combo = QComboBox()
        self.bitrate_combo.addItems(list(VALID_BITRATES))
        self.bitrate_combo.setCurrentText("192k")
        bitrate_col.addWidget(self.bitrate_combo)
        row1.addLayout(bitrate_col, stretch=1)

        norm_col = QVBoxLayout()
        norm_col.setSpacing(4)
        norm_col.addWidget(SectionLabel("Volume"))
        self.normalize_check = QCheckBox("Normalize peak level")
        norm_col.addWidget(self.normalize_check)
        norm_col.addStretch()
        row1.addLayout(norm_col, stretch=2)
        inner.addLayout(row1)

        # Row 2 — Fade in
        fade_in_col = QVBoxLayout()
        fade_in_col.setSpacing(4)
        fade_in_header = QHBoxLayout()
        fade_in_header.addWidget(SectionLabel("Fade in"))
        self._fade_in_label = QLabel("0.0s")
        self._fade_in_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        fade_in_header.addWidget(self._fade_in_label)
        fade_in_col.addLayout(fade_in_header)
        self.fade_in_slider = QSlider(Qt.Orientation.Horizontal)
        self.fade_in_slider.setRange(0, 5000)
        self.fade_in_slider.setValue(0)
        self.fade_in_slider.setTickInterval(500)
        fade_in_col.addWidget(self.fade_in_slider)
        inner.addLayout(fade_in_col)

        # Row 3 — Fade out
        fade_out_col = QVBoxLayout()
        fade_out_col.setSpacing(4)
        fade_out_header = QHBoxLayout()
        fade_out_header.addWidget(SectionLabel("Fade out"))
        self._fade_out_label = QLabel("0.0s")
        self._fade_out_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        fade_out_header.addWidget(self._fade_out_label)
        fade_out_col.addLayout(fade_out_header)
        self.fade_out_slider = QSlider(Qt.Orientation.Horizontal)
        self.fade_out_slider.setRange(0, 5000)
        self.fade_out_slider.setValue(0)
        self.fade_out_slider.setTickInterval(500)
        fade_out_col.addWidget(self.fade_out_slider)
        inner.addLayout(fade_out_col)

        # Row 4 — Trim silence
        self.trim_silence_check = QCheckBox("Trim leading / trailing silence")
        inner.addWidget(self.trim_silence_check)

        adv_layout.addWidget(adv_card)
        layout.addWidget(self._adv_frame)

        # Connect
        self._adv_toggle.toggled.connect(self._on_adv_toggle)
        self.fade_in_slider.valueChanged.connect(
            lambda v: self._fade_in_label.setText(f"{v / 1000:.1f}s")
        )
        self.fade_out_slider.valueChanged.connect(
            lambda v: self._fade_out_label.setText(f"{v / 1000:.1f}s")
        )

    def _on_adv_toggle(self, checked: bool) -> None:
        from narracast.ui import icons
        self._adv_frame.setVisible(checked)
        self._adv_toggle.setText("Advanced")
        self._adv_toggle.setIcon(
            icons.muted(icons.CHEVRON_DOWN) if checked else icons.muted(icons.CHEVRON_RIGHT)
        )

    def _current_polish(self) -> AudioPolishSettings:
        """Read current Advanced panel values into an AudioPolishSettings."""
        return AudioPolishSettings(
            bitrate=self.bitrate_combo.currentText(),
            normalize=self.normalize_check.isChecked(),
            fade_in_ms=self.fade_in_slider.value(),
            fade_out_ms=self.fade_out_slider.value(),
            trim_silence=self.trim_silence_check.isChecked(),
        )

    def _build_right(self, layout: QVBoxLayout) -> None:
        # ── Last output card ─────────────────────────────────────────────
        out_card = Card()
        out_layout = QVBoxLayout(out_card)
        out_layout.setContentsMargins(12, 12, 12, 12)
        out_layout.setSpacing(6)

        out_layout.addWidget(SectionLabel("Last output"))

        self.last_file_label = MutedLabel("—")
        self.last_file_label.setWordWrap(True)
        out_layout.addWidget(self.last_file_label)

        play_row = QHBoxLayout()
        self._play_btn = QPushButton("Play")
        self._play_btn.setIcon(icons.icon(icons.PLAY))
        self._play_btn.setEnabled(False)
        self._play_btn.setFixedHeight(30)
        play_row.addWidget(self._play_btn, stretch=1)
        out_layout.addLayout(play_row)

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 100)
        self.seek_slider.setValue(0)
        self.seek_slider.setEnabled(False)
        out_layout.addWidget(self.seek_slider)

        self._time_label = MutedLabel("00:00 / 00:00")
        out_layout.addWidget(self._time_label)

        dl_row = QHBoxLayout()
        self._reveal_btn = QPushButton("Reveal")
        self._reveal_btn.setIcon(icons.icon(icons.REVEAL))
        self._reveal_btn.setEnabled(False)
        self._reveal_btn.setFixedHeight(28)
        dl_row.addWidget(self._reveal_btn)
        layout.addWidget(out_card)

        # ── Current job card ─────────────────────────────────────────────
        job_card = Card()
        job_layout = QVBoxLayout(job_card)
        job_layout.setContentsMargins(12, 12, 12, 12)
        job_layout.setSpacing(6)

        job_layout.addWidget(SectionLabel("Current job"))

        self.job_title_label = QLabel("Nothing in progress")
        self.job_title_label.setWordWrap(True)
        job_layout.addWidget(self.job_title_label)

        self.job_desc_label = MutedLabel("Loading local model. You can paste and prepare text now.")
        self.job_desc_label.setWordWrap(True)
        job_layout.addWidget(self.job_desc_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        job_layout.addWidget(self.progress_bar)

        self.job_eta_label = MutedLabel("")
        job_layout.addWidget(self.job_eta_label)
        layout.addWidget(job_card)

        # ── System card ──────────────────────────────────────────────────
        sys_card = Card()
        sys_layout = QVBoxLayout(sys_card)
        sys_layout.setContentsMargins(12, 12, 12, 12)
        sys_layout.setSpacing(6)

        sys_layout.addWidget(SectionLabel("System"))

        dot_row = QHBoxLayout()
        dot_row.setSpacing(6)
        self._sys_dot = StatusDot("#16a34a")
        dot_row.addWidget(self._sys_dot)
        self._sys_label = QLabel("Offline  •  CPU")
        dot_row.addWidget(self._sys_label)
        dot_row.addStretch()
        sys_layout.addLayout(dot_row)

        self._sys_desc = MutedLabel("Loading model…")
        sys_layout.addWidget(self._sys_desc)

        self.benchmark_btn = QPushButton("Run benchmark")
        self.benchmark_btn.setObjectName("secondary")
        self.benchmark_btn.setFixedHeight(28)
        self.benchmark_btn.setEnabled(False)
        sys_layout.addWidget(self.benchmark_btn)

        self.timing_btn = QPushButton("Analyze timings")
        self.timing_btn.setObjectName("secondary")
        self.timing_btn.setFixedHeight(28)
        sys_layout.addWidget(self.timing_btn)
        layout.addWidget(sys_card)

        layout.addStretch()

    # ── Signal connections ───────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        sigs = get_signals()
        sigs.generation_progress.connect(self._on_progress)
        sigs.generation_done.connect(self._on_done)
        sigs.generation_error.connect(self._on_error)
        sigs.preview_done.connect(self._on_preview_done)
        sigs.voice_library_changed.connect(self._populate_voices)

        self.text_edit.textChanged.connect(self._update_counts)
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        self.pause_slider.valueChanged.connect(self._on_pause_changed)
        self.sentence_pause_slider.valueChanged.connect(self._on_sentence_pause_changed)
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        self.voice_combo.currentTextChanged.connect(self._on_voice_changed)

        self.gen_btn.clicked.connect(self._start_generate)
        self.preview_btn.clicked.connect(self._start_preview)
        self.queue_btn.clicked.connect(self._queue_it)
        self._play_btn.clicked.connect(self._play_last)
        self._reveal_btn.clicked.connect(self._reveal_output)
        self.benchmark_btn.clicked.connect(self._open_benchmark)
        self.timing_btn.clicked.connect(self._open_timing_analysis)

    # ── Slot methods ─────────────────────────────────────────────────────────

    def _update_counts(self) -> None:
        text = self.text_edit.toPlainText()
        chars = len(text)
        words = len(text.split()) if text.strip() else 0
        paras = len([p for p in text.split("\n\n") if p.strip()]) if text.strip() else 0
        self._count_label.setText(
            f"{chars:,} characters  •  {words:,} words  •  {paras:,} paragraphs"
        )

    def _on_speed_changed(self, value: int) -> None:
        self._speed_label.setText(f"{value / 1000:.2f}×")

    def _on_pause_changed(self, value: int) -> None:
        self._pause_label.setText(f"{value / 1000:.1f}s")

    def _on_sentence_pause_changed(self, value: int) -> None:
        self._sentence_pause_label.setText(f"{value / 1000:.1f}s")

    def _on_mode_changed(self, name: str) -> None:
        desc = GENERATION_PRESETS.get(name, {}).get("description", "")
        self._mode_desc.setText(desc)

    def _apply_cleanup(self, fn) -> None:
        text = self.text_edit.toPlainText()
        cleaned = fn(text)
        self.text_edit.setPlainText(cleaned)

    def _apply_pdf_cleanup(self) -> None:
        raw = self.text_edit.toPlainText()
        cleaned = clean_pdf_text(raw)
        self._raw_text_snapshot = raw
        self._cleaned_text_snapshot = cleaned
        self.raw_text_btn.setEnabled(True)
        self.cleaned_text_btn.setEnabled(True)
        self.text_edit.setPlainText(cleaned)
        self.job_desc_label.setText(
            "PDF cleanup applied. Use Raw / Cleaned to compare before generating."
        )

    def _show_raw_text(self) -> None:
        if self._raw_text_snapshot:
            self.text_edit.setPlainText(self._raw_text_snapshot)
            self.job_desc_label.setText("Showing raw imported text.")

    def _show_cleaned_text(self) -> None:
        if self._cleaned_text_snapshot:
            self.text_edit.setPlainText(self._cleaned_text_snapshot)
            self.job_desc_label.setText("Showing cleaned text.")

    def _populate_voices(self) -> None:
        current = self.voice_combo.currentText()
        self.voice_combo.clear()
        voices = get_voice_files()
        for name in voices:
            self.voice_combo.addItem(name)
        if current:
            idx = self.voice_combo.findText(current)
            if idx >= 0:
                self.voice_combo.setCurrentIndex(idx)
        self._on_voice_changed(self.voice_combo.currentText())

    def _current_voice_path(self) -> str:
        voices = get_voice_files()
        return voices.get(self.voice_combo.currentText(), "")

    def _on_voice_changed(self, _name: str) -> None:
        warning = reference_warning(self._current_voice_path())
        if warning:
            self._sys_desc.setText(warning)
        elif self._model_ready:
            self._sys_desc.setText("Model loaded and ready.")
        else:
            self._sys_desc.setText("Loading local model. You can paste and prepare text now.")

    def _start_generate(self) -> None:
        text = self.text_edit.toPlainText().strip()
        if not text:
            self.job_desc_label.setText("Please enter some text first.")
            return
        voices = get_voice_files()
        voice = self.voice_combo.currentText()
        if not voice or voice not in voices:
            self.job_desc_label.setText("Please select a reference voice.")
            return

        speed = self.speed_slider.value() / 1000.0
        title = self.title_edit.text().strip()
        part = self.part_edit.text().strip()
        preset = self.mode_combo.currentText()
        pause_ms = self.pause_slider.value()
        sentence_pause_ms = self.sentence_pause_slider.value()
        polish = self._current_polish()

        _job_title = f'"{title}"' if title else "Generating…"
        self.job_title_label.setText(_job_title)
        warning = reference_warning(voices[voice])
        self.job_desc_label.setText(f"Starting… {warning}" if warning else "Starting…")
        self.progress_bar.setValue(0)
        self._set_generation_buttons_enabled(False)

        def _worker():
            try:
                path, msg = generate_core(
                    text, voice, speed, title, part,
                    on_progress=lambda f, d: get_signals().generation_progress.emit(f, d),
                    preset_name=preset,
                    paragraph_pause_ms=pause_ms,
                    sentence_pause_ms=sentence_pause_ms,
                    audio_polish=polish,
                )
                get_signals().generation_done.emit(path, msg)
            except Exception as e:
                get_signals().generation_error.emit(str(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _start_preview(self) -> None:
        text = self.text_edit.toPlainText().strip()
        if not text:
            return
        voices = get_voice_files()
        voice = self.voice_combo.currentText()
        if not voice or voice not in voices:
            return

        speed = self.speed_slider.value() / 1000.0
        preset = "Draft"

        preview_text = text[:500]
        voice_path = voices[voice]
        cache_key = self._preview_cache_key(preview_text, voice, voice_path, speed, preset)
        cached_path = self._preview_cache.get(cache_key)
        if cached_path and Path(cached_path).exists():
            self.job_desc_label.setText("Using cached preview.")
            get_signals().preview_done.emit(cached_path)
            return

        def _worker():
            try:
                path, _ = generate_core(
                    preview_text, voice, speed, "", "",
                    on_progress=lambda f, d: get_signals().generation_progress.emit(f, d),
                    preset_name=preset,
                    paragraph_pause_ms=0,
                )
                self._preview_cache[cache_key] = path
                get_signals().preview_done.emit(path)
            except Exception as e:
                get_signals().generation_error.emit(str(e))

        threading.Thread(target=_worker, daemon=True).start()
        warning = reference_warning(voice_path)
        self.job_desc_label.setText(
            f"Generating preview from the first section… {warning}"
            if warning
            else "Generating preview from the first section…"
        )
        self.progress_bar.setValue(0)
        self._set_generation_buttons_enabled(False)

    def _preview_cache_key(
        self, text: str, voice: str, voice_path: str, speed: float, preset: str
    ) -> str:
        payload = f"{voice}\0{reference_signature(voice_path)}\0{speed:.2f}\0{preset}\0{text}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _queue_it(self) -> None:
        text = self.text_edit.toPlainText().strip()
        if not text:
            self.job_desc_label.setText("Please enter some text first.")
            return
        voice = self.voice_combo.currentText()
        speed = self.speed_slider.value() / 1000.0
        title = self.title_edit.text().strip()
        part = self.part_edit.text().strip()
        preset = self.mode_combo.currentText()
        pause_ms = self.pause_slider.value()
        sentence_pause_ms = self.sentence_pause_slider.value()
        polish = self._current_polish()
        msg = add_to_queue(
            text,
            voice,
            speed,
            title,
            part,
            preset,
            pause_ms,
            sentence_pause_ms,
            audio_polish=polish,
        )
        self.job_desc_label.setText(msg)

    def _play_last(self) -> None:
        if not self._last_output_path:
            return
        if self._play_proc and self._play_proc.poll() is None:
            self._play_proc.terminate()
        self._play_proc = subprocess.Popen(
            ["afplay", self._last_output_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _reveal_output(self) -> None:
        if not self._last_output_path:
            return
        subprocess.Popen(["open", "-R", self._last_output_path])

    def _open_benchmark(self) -> None:
        voices = get_voice_files()
        voice = self.voice_combo.currentText()
        voice_path = voices.get(voice)
        if not voice_path:
            self.job_desc_label.setText("Please select a reference voice first.")
            return
        self._benchmark_dialog = BenchmarkDialog(voice, voice_path, self)
        self._benchmark_dialog.show()

    def _open_timing_analysis(self) -> None:
        self._timing_dialog = TimingAnalysisDialog(self)
        self._timing_dialog.show()

    # ── Signal handlers ──────────────────────────────────────────────────────

    def _on_progress(self, fraction: float, desc: str) -> None:
        self.progress_bar.setValue(int(fraction * 100))
        self.job_desc_label.setText(desc)

    def _on_done(self, output_path: str, message: str) -> None:
        self._last_output_path = output_path
        filename = Path(output_path).name
        self.last_file_label.setText(filename)
        self.last_file_label.setStyleSheet("color: #e9f1ff;")
        self.job_title_label.setText("Done!")
        self.job_desc_label.setText(message)
        self.progress_bar.setValue(100)
        self._play_btn.setEnabled(True)
        self._reveal_btn.setEnabled(True)
        self._set_generation_buttons_enabled(True)

    def _on_preview_done(self, output_path: str) -> None:
        self._last_output_path = output_path
        filename = Path(output_path).name
        self.last_file_label.setText(filename)
        self.last_file_label.setStyleSheet("color: #e9f1ff;")
        self.job_title_label.setText("Preview ready")
        self.job_desc_label.setText("First-section preview generated. Press Play to listen.")
        self.progress_bar.setValue(100)
        self._play_btn.setEnabled(True)
        self._reveal_btn.setEnabled(True)
        self._set_generation_buttons_enabled(True)

    def _on_error(self, err: str) -> None:
        self.job_title_label.setText("Generation failed")
        self.job_desc_label.setText(f"{err}")
        self.progress_bar.setValue(0)
        self._set_generation_buttons_enabled(True)

    # ── Public API ───────────────────────────────────────────────────────────

    def on_model_ready(self) -> None:
        """Called by MainWindow when the AI model has finished loading."""
        self._model_ready = True
        self._sys_desc.setText("Model loaded and ready.")
        self._populate_voices()
        self._on_voice_changed(self.voice_combo.currentText())
        self._set_generation_buttons_enabled(True)
        self.benchmark_btn.setEnabled(True)

    def apply_settings(self, settings: dict) -> None:
        self.title_edit.setText(str(settings.get("title") or ""))
        self.part_edit.setText(str(settings.get("part") or ""))

        voice = str(settings.get("voice") or "")
        if voice:
            idx = self.voice_combo.findText(voice)
            if idx >= 0:
                self.voice_combo.setCurrentIndex(idx)

        try:
            speed = float(settings.get("speed", 1.0))
        except (TypeError, ValueError):
            speed = 1.0
        self.speed_slider.setValue(int(min(2.0, max(0.5, speed)) * 1000))

        preset = str(settings.get("preset") or DEFAULT_PRESET)
        idx = self.mode_combo.findText(preset)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)

        try:
            pause_ms = int(settings.get("paragraph_pause_ms", 500))
        except (TypeError, ValueError):
            pause_ms = 500
        self.pause_slider.setValue(min(2000, max(0, pause_ms)))

        try:
            sentence_pause_ms = int(settings.get("sentence_pause_ms", 0))
        except (TypeError, ValueError):
            sentence_pause_ms = 0
        self.sentence_pause_slider.setValue(min(1000, max(0, sentence_pause_ms)))

        # Audio polish
        bitrate = str(settings.get("polish_bitrate") or "192k")
        if bitrate in VALID_BITRATES:
            self.bitrate_combo.setCurrentText(bitrate)
        self.normalize_check.setChecked(bool(settings.get("polish_normalize", False)))
        self.trim_silence_check.setChecked(bool(settings.get("polish_trim_silence", False)))
        try:
            fade_in = int(settings.get("polish_fade_in_ms", 0))
        except (TypeError, ValueError):
            fade_in = 0
        self.fade_in_slider.setValue(min(5000, max(0, fade_in)))
        try:
            fade_out = int(settings.get("polish_fade_out_ms", 0))
        except (TypeError, ValueError):
            fade_out = 0
        self.fade_out_slider.setValue(min(5000, max(0, fade_out)))

    def current_settings(self) -> dict:
        return {
            "voice": self.voice_combo.currentText(),
            "speed": round(self.speed_slider.value() / 1000.0, 2),
            "preset": self.mode_combo.currentText(),
            "title": self.title_edit.text().strip(),
            "part": self.part_edit.text().strip(),
            "paragraph_pause_ms": self.pause_slider.value(),
            "sentence_pause_ms": self.sentence_pause_slider.value(),
            "polish_bitrate": self.bitrate_combo.currentText(),
            "polish_normalize": self.normalize_check.isChecked(),
            "polish_fade_in_ms": self.fade_in_slider.value(),
            "polish_fade_out_ms": self.fade_out_slider.value(),
            "polish_trim_silence": self.trim_silence_check.isChecked(),
        }

    def _set_generation_buttons_enabled(self, enabled: bool) -> None:
        self.gen_btn.setEnabled(enabled and self._model_ready)
        self.preview_btn.setEnabled(enabled and self._model_ready)
        self.queue_btn.setEnabled(enabled)
