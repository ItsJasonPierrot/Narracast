"""Voice Reference page — extract and save a reference voice clip."""

from __future__ import annotations

import subprocess
import threading
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from narracast.audio_generation import infer_chunk
from narracast.paths import REFERENCE
from narracast.voices import (
    delete_voice_profile,
    extract_clip,
    get_voice_profile,
    get_voice_files,
    list_voice_profiles,
    load_reference_text,
    rename_voice_profile,
    save_clip,
    save_voice_profile,
    set_profile_as_reference,
)
from narracast.ui import icons
from narracast.ui.signals import get_signals
from narracast.ui.widgets import Card, Divider, MutedLabel, SectionLabel


class VoicePage(QWidget):
    """Voice Reference extraction screen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preview_path: Optional[str] = None
        self._preview_proc: Optional[subprocess.Popen] = None
        self._build_ui()
        self._connect_signals()
        self._populate_voices()
        self._refresh_library()

    # ── Build UI ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Header
        h2 = QLabel("Voice Reference")
        h2.setObjectName("h2")
        root.addWidget(h2)

        subtitle = MutedLabel(
            "Extract a short clip from a source audio file, then save it as the active reference or as a named voice."
        )
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        library_card = Card()
        library_layout = QVBoxLayout(library_card)
        library_layout.setContentsMargins(20, 18, 20, 18)
        library_layout.setSpacing(10)
        library_layout.addWidget(SectionLabel("Saved voices"))

        self.library_combo = QComboBox()
        self.library_combo.currentIndexChanged.connect(self._on_library_selection_changed)
        library_layout.addWidget(self.library_combo)

        self.library_detail_label = MutedLabel("No saved voices yet.")
        self.library_detail_label.setWordWrap(True)
        library_layout.addWidget(self.library_detail_label)

        edit_row = QHBoxLayout()
        edit_row.setSpacing(8)
        self.rename_profile_btn = QPushButton("Rename / update notes")
        self.rename_profile_btn.setIcon(icons.icon(icons.RENAME))
        self.rename_profile_btn.setFixedHeight(30)
        self.rename_profile_btn.setEnabled(False)
        self.rename_profile_btn.clicked.connect(self._rename_profile)
        edit_row.addWidget(self.rename_profile_btn)

        self.delete_profile_btn = QPushButton("Delete voice")
        self.delete_profile_btn.setIcon(icons.danger(icons.DELETE))
        self.delete_profile_btn.setObjectName("danger")
        self.delete_profile_btn.setFixedHeight(30)
        self.delete_profile_btn.setEnabled(False)
        self.delete_profile_btn.clicked.connect(self._delete_profile)
        edit_row.addWidget(self.delete_profile_btn)

        self.set_reference_btn = QPushButton("Set as active reference")
        self.set_reference_btn.setIcon(icons.accent(icons.CHECK))
        self.set_reference_btn.setObjectName("primary")
        self.set_reference_btn.setFixedHeight(30)
        self.set_reference_btn.setEnabled(False)
        self.set_reference_btn.clicked.connect(self._set_as_reference)
        edit_row.addWidget(self.set_reference_btn)
        library_layout.addLayout(edit_row)

        sample_row = QHBoxLayout()
        sample_row.setSpacing(8)
        self.sample_text_edit = QLineEdit()
        self.sample_text_edit.setPlaceholderText("Sample text for saved-voice preview")
        self.sample_text_edit.setText("Narracast turns anything worth reading into something worth hearing.")
        sample_row.addWidget(self.sample_text_edit, stretch=1)

        self.preview_profile_btn = QPushButton("Preview saved voice")
        self.preview_profile_btn.setIcon(icons.icon(icons.PREVIEW_BOX))
        self.preview_profile_btn.setFixedHeight(30)
        self.preview_profile_btn.setEnabled(False)
        self.preview_profile_btn.clicked.connect(self._preview_profile)
        sample_row.addWidget(self.preview_profile_btn)
        library_layout.addLayout(sample_row)
        root.addWidget(library_card)

        # Main card
        card = Card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(14)
        root.addWidget(card)

        # Source section
        card_layout.addWidget(SectionLabel("Source"))

        track_row = QHBoxLayout()
        track_row.addWidget(QLabel("Voice track:"))
        self.voice_combo = QComboBox()
        self.voice_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        track_row.addWidget(self.voice_combo, stretch=1)

        browse_btn = QPushButton("Browse…")
        browse_btn.setIcon(icons.icon(icons.FOLDER_OPEN))
        browse_btn.setFixedHeight(30)
        browse_btn.clicked.connect(self._browse_voice_file)
        track_row.addWidget(browse_btn)
        card_layout.addLayout(track_row)

        time_row = QHBoxLayout()
        time_row.setSpacing(16)

        start_col = QVBoxLayout()
        start_col.setSpacing(4)
        start_col.addWidget(SectionLabel("Start time (s)"))
        self.start_spin = QSpinBox()
        self.start_spin.setRange(0, 7200)
        self.start_spin.setValue(0)
        self.start_spin.setSuffix(" s")
        start_col.addWidget(self.start_spin)
        time_row.addLayout(start_col)

        dur_col = QVBoxLayout()
        dur_col.setSpacing(4)
        dur_col.addWidget(SectionLabel("Duration (s)"))
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 300)
        self.duration_spin.setValue(12)
        self.duration_spin.setSuffix(" s")
        dur_col.addWidget(self.duration_spin)
        time_row.addLayout(dur_col)
        time_row.addStretch()
        card_layout.addLayout(time_row)

        card_layout.addWidget(Divider())

        card_layout.addWidget(SectionLabel("Voice library"))
        profile_row = QHBoxLayout()
        profile_row.setSpacing(12)

        name_col = QVBoxLayout()
        name_col.setSpacing(4)
        name_col.addWidget(QLabel("Voice name"))
        self.profile_name_edit = QLineEdit()
        self.profile_name_edit.setPlaceholderText("e.g. Narrator warm tone")
        name_col.addWidget(self.profile_name_edit)
        profile_row.addLayout(name_col, stretch=1)

        notes_col = QVBoxLayout()
        notes_col.setSpacing(4)
        notes_col.addWidget(QLabel("Notes"))
        self.profile_notes_edit = QLineEdit()
        self.profile_notes_edit.setPlaceholderText("Optional source or tone notes")
        notes_col.addWidget(self.profile_notes_edit)
        profile_row.addLayout(notes_col, stretch=1)

        card_layout.addLayout(profile_row)

        card_layout.addWidget(Divider())

        card_layout.addWidget(SectionLabel("Reference transcript"))
        self.transcript_edit = QTextEdit()
        self.transcript_edit.setPlaceholderText(
            "Paste the exact words spoken in the saved reference clip. This can avoid repeated reference transcription work."
        )
        self.transcript_edit.setMinimumHeight(80)
        self.transcript_edit.setPlainText(load_reference_text(str(REFERENCE)))
        card_layout.addWidget(self.transcript_edit)

        card_layout.addWidget(Divider())

        # Waveform placeholder
        card_layout.addWidget(SectionLabel("Waveform preview"))

        wave_frame = QFrame()
        wave_frame.setFixedHeight(80)
        wave_frame.setFrameShape(QFrame.Shape.StyledPanel)
        wave_frame.setStyleSheet(
            "QFrame { border: 1px dashed #3b4d63; border-radius: 6px; background: #0a111b; }"
        )
        wave_inner = QVBoxLayout(wave_frame)
        wave_label = MutedLabel("Waveform preview")
        wave_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wave_inner.addWidget(wave_label)
        card_layout.addWidget(wave_frame)

        card_layout.addWidget(Divider())

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.extract_btn = QPushButton("Extract clip")
        self.extract_btn.setIcon(icons.icon(icons.SCISSORS))
        self.extract_btn.setFixedHeight(34)
        self.extract_btn.clicked.connect(self._extract)
        btn_row.addWidget(self.extract_btn)

        self.preview_btn = QPushButton("Preview clip")
        self.preview_btn.setIcon(icons.icon(icons.PLAY))
        self.preview_btn.setFixedHeight(34)
        self.preview_btn.setEnabled(False)
        self.preview_btn.clicked.connect(self._preview)
        btn_row.addWidget(self.preview_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setIcon(icons.icon(icons.STOP))
        self.stop_btn.setFixedHeight(34)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_preview)
        btn_row.addWidget(self.stop_btn)

        self.save_btn = QPushButton("Save as reference.wav")
        self.save_btn.setIcon(icons.accent(icons.SAVE))
        self.save_btn.setObjectName("primary")
        self.save_btn.setFixedHeight(34)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save)
        btn_row.addWidget(self.save_btn)

        self.save_profile_btn = QPushButton("Save named voice")
        self.save_profile_btn.setIcon(icons.accent(icons.SAVE_VOICE))
        self.save_profile_btn.setObjectName("secondary")
        self.save_profile_btn.setFixedHeight(34)
        self.save_profile_btn.setEnabled(False)
        self.save_profile_btn.clicked.connect(self._save_profile)
        btn_row.addWidget(self.save_profile_btn)

        btn_row.addStretch()
        card_layout.addLayout(btn_row)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            "color: #a3ff73; font-family: Menlo; font-size: 12px; background: transparent;"
        )
        self._status_label.setWordWrap(True)
        card_layout.addWidget(self._status_label)

        root.addStretch()

    def _connect_signals(self) -> None:
        sigs = get_signals()
        sigs.voice_preview_done.connect(self._on_voice_preview_done)
        sigs.voice_preview_error.connect(self._on_voice_preview_error)

    # ── Slots ─────────────────────────────────────────────────────────────

    def _populate_voices(self) -> None:
        self.voice_combo.clear()
        voices = get_voice_files()
        for name, path in voices.items():
            self.voice_combo.addItem(name, path)

    def _browse_voice_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select voice audio file",
            "",
            "Audio files (*.wav *.mp3 *.flac *.m4a *.ogg *.aiff)",
        )
        if not path:
            return
        from pathlib import Path
        name = Path(path).name
        existing_idx = self.voice_combo.findData(path)
        if existing_idx >= 0:
            self.voice_combo.setCurrentIndex(existing_idx)
        else:
            self.voice_combo.addItem(name, path)
            self.voice_combo.setCurrentIndex(self.voice_combo.count() - 1)

    def _refresh_library(self) -> None:
        current_id = self.library_combo.currentData()
        self.library_combo.blockSignals(True)
        self.library_combo.clear()
        profiles = list_voice_profiles()
        for profile in profiles:
            self.library_combo.addItem(profile.display_name, profile.id)
        self.library_combo.blockSignals(False)

        if current_id:
            idx = self.library_combo.findData(current_id)
            if idx >= 0:
                self.library_combo.setCurrentIndex(idx)
        self._on_library_selection_changed()

    def _on_library_selection_changed(self) -> None:
        profile_id = self.library_combo.currentData()
        profiles = {profile.id: profile for profile in list_voice_profiles()}
        profile = profiles.get(profile_id)
        if not profile:
            self.library_detail_label.setText("No saved voices yet.")
            self.rename_profile_btn.setEnabled(False)
            self.delete_profile_btn.setEnabled(False)
            self.set_reference_btn.setEnabled(False)
            self.preview_profile_btn.setEnabled(False)
            return

        self.profile_name_edit.setText(profile.display_name)
        self.profile_notes_edit.setText(profile.notes)
        self.rename_profile_btn.setEnabled(True)
        self.delete_profile_btn.setEnabled(True)
        self.set_reference_btn.setEnabled(True)
        self.preview_profile_btn.setEnabled(True)

        transcript = "transcript saved" if profile.ref_text else "no transcript"
        notes = f"\nNotes: {profile.notes}" if profile.notes else ""
        source = f"\nSource: {profile.source_file}" if profile.source_file else ""
        self.library_detail_label.setText(
            f"{profile.display_name} · {transcript} · "
            f"{profile.clip_duration_s:g}s from {profile.clip_start_s:g}s"
            f"{notes}{source}"
        )

    def _selected_profile(self):
        return get_voice_profile(str(self.library_combo.currentData() or ""))

    def _extract(self) -> None:
        voice_path = self.voice_combo.currentData()
        if not voice_path:
            self._status_label.setText("⚠️  Please select a voice track.")
            return
        start = self.start_spin.value()
        duration = self.duration_spin.value()
        path, msg = extract_clip(voice_path, start, duration)
        self._status_label.setText(msg)
        if path:
            self._preview_path = path
            self.preview_btn.setEnabled(True)
            self.save_btn.setEnabled(True)
            self.save_profile_btn.setEnabled(True)

    def _preview(self) -> None:
        if not self._preview_path:
            return
        self._stop_preview()
        self._preview_proc = subprocess.Popen(
            ["afplay", self._preview_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.stop_btn.setEnabled(True)

    def _stop_preview(self) -> None:
        if self._preview_proc and self._preview_proc.poll() is None:
            self._preview_proc.terminate()
        self._preview_proc = None
        self.stop_btn.setEnabled(False)

    def _save(self) -> None:
        if not self._preview_path:
            return
        msg = save_clip(self._preview_path, self.transcript_edit.toPlainText())
        self._status_label.setText(msg)
        get_signals().voice_library_changed.emit()

    def _save_profile(self) -> None:
        if not self._preview_path:
            return
        source_path = self.voice_combo.currentData() or ""
        try:
            profile = save_voice_profile(
                self._preview_path,
                self.profile_name_edit.text(),
                ref_text=self.transcript_edit.toPlainText(),
                notes=self.profile_notes_edit.text(),
                source_file=str(source_path),
                clip_start_s=float(self.start_spin.value()),
                clip_duration_s=float(self.duration_spin.value()),
            )
        except Exception as exc:
            self._status_label.setText(f"⚠️  {exc}")
            return

        self._status_label.setText(
            f"✅  Saved named voice: {profile.display_name}. It is now available in Generate."
        )
        self._refresh_library()
        get_signals().voice_library_changed.emit()

    def _rename_profile(self) -> None:
        profile = self._selected_profile()
        if not profile:
            return
        try:
            updated = rename_voice_profile(
                profile.id,
                self.profile_name_edit.text(),
                self.profile_notes_edit.text(),
            )
        except Exception as exc:
            self._status_label.setText(f"⚠️  {exc}")
            return

        self._status_label.setText(f"✅  Updated voice: {updated.display_name}.")
        self._refresh_library()
        get_signals().voice_library_changed.emit()

    def _delete_profile(self) -> None:
        profile = self._selected_profile()
        if not profile:
            return
        confirmed = QMessageBox.question(
            self,
            "Delete voice?",
            f"Delete saved voice “{profile.display_name}”?\n\nThis removes its local reference audio, transcript, and metadata.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return

        if delete_voice_profile(profile.id):
            self._status_label.setText(f"✅  Deleted voice: {profile.display_name}.")
        else:
            self._status_label.setText("⚠️  Voice profile was already missing.")
        self._refresh_library()
        get_signals().voice_library_changed.emit()

    def _set_as_reference(self) -> None:
        profile = self._selected_profile()
        if not profile:
            return
        try:
            set_profile_as_reference(profile.id)
        except Exception as exc:
            self._status_label.setText(f"⚠️  {exc}")
            return
        self._status_label.setText(
            f"✅  “{profile.display_name}” is now the active reference. New generations will use this voice."
        )
        get_signals().voice_library_changed.emit()

    def _preview_profile(self) -> None:
        profile = self._selected_profile()
        if not profile:
            return
        sample_text = self.sample_text_edit.text().strip()
        if not sample_text:
            self._status_label.setText("⚠️  Enter sample text first.")
            return

        self.preview_profile_btn.setEnabled(False)
        self._status_label.setText("Generating saved-voice preview…")

        def _worker() -> None:
            try:
                path = infer_chunk(sample_text[:300], profile.ref_audio, 1.0, nfe_step=16)
                get_signals().voice_preview_done.emit(path)
            except Exception as exc:
                get_signals().voice_preview_error.emit(str(exc))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_voice_preview_done(self, path: str) -> None:
        self._preview_path = path
        self._stop_preview()
        self._preview_proc = subprocess.Popen(
            ["afplay", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.stop_btn.setEnabled(True)
        self.preview_profile_btn.setEnabled(self.library_combo.count() > 0)
        self._status_label.setText("✅  Saved-voice preview ready.")

    def _on_voice_preview_error(self, err: str) -> None:
        self.preview_profile_btn.setEnabled(self.library_combo.count() > 0)
        self._status_label.setText(f"⚠️  Could not preview saved voice: {err}")
