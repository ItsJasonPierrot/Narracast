"""Help Center page — FAQ and usage documentation."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from narracast.ui import icons
from narracast.ui.widgets import Card, MutedLabel, SectionLabel


# (icon_constant, title, answer)
_FAQ = [
    (
        icons.MICROPHONE,
        "How to generate",
        "Paste your text into the Generate tab, choose a voice reference, "
        "set the speed and quality mode, then click Generate MP3. "
        "The audio file will be saved to the output/ folder when done.",
    ),
    (
        icons.PLAYLIST_PLAY,
        "Why use Queue?",
        "The queue lets you line up multiple generation jobs so they run "
        "automatically one after another. This is useful for long books where "
        "you want to generate several chapters overnight without supervision.",
    ),
    (
        icons.TIMER_PAUSE,
        "Paragraph pauses",
        "The Paragraph pause slider in the Generate tab controls how long a "
        "silence is inserted between paragraphs. A value of 0.5s is comfortable "
        "for most listening. Increase it for audiobook-style pacing.",
    ),
    (
        icons.FILE_MUSIC,
        "Generated files",
        "All output MP3 files are saved in output/ at the project root. "
        "Each MP3 has a matching .json sidecar file that stores the source "
        "text, timeline, bookmarks, and last playback position so the reader "
        "can resume where you left off.",
    ),
    (
        icons.SAVE_VOICE,
        "Voice reference",
        "F5-TTS clones speech from a short reference clip. For best results "
        "use a clean 10–15 second recording with no background noise. "
        "Use the Voice Reference tab to extract and save a clip as reference.wav.",
    ),
    (
        icons.BOOK_OPEN,
        "Reading and Focus mode",
        "The Read tab syncs the text display to the audio position. "
        "Switch to Focus Mode to see only the current sentence in large text, "
        "with the previous and next lines shown dimly for context.",
    ),
    (
        icons.TUNE,
        "Quality modes",
        "Best (NFE=32, 500 chars/chunk): highest quality, slowest.\n"
        "Balanced (NFE=32, 750 chars/chunk): default, good trade-off.\n"
        "Fast (NFE=24, 1000 chars/chunk): faster for long texts.\n"
        "Draft (NFE=16, 1200 chars/chunk): rough listening copy.",
    ),
    (
        icons.CLOCK,
        "Why is it slow?",
        "F5-TTS runs on your local machine. On Apple Silicon (MPS) a typical "
        "chapter takes 5–15 minutes. On CPU it can be several times longer. "
        "Use a lower quality mode or the Queue tab to generate overnight.",
    ),
]


class HelpPage(QWidget):
    """Static FAQ / help center."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)

        h2 = QLabel("Help Center")
        h2.setObjectName("h2")
        root.addWidget(h2)

        root.addWidget(MutedLabel(
            "Quick reference for using Narracast — offline audiobook generator."
        ))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 8, 0)
        scroll_layout.setSpacing(12)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(scroll_widget)
        root.addWidget(scroll, stretch=1)

        for icon_name, question, answer in _FAQ:
            card = Card()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 14, 16, 14)
            card_layout.setSpacing(6)

            # Icon + title row
            header_row = QHBoxLayout()
            header_row.setSpacing(8)
            header_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

            icon_label = QLabel()
            icon_label.setPixmap(icons.muted(icon_name).pixmap(18, 18))
            icon_label.setFixedSize(20, 20)
            header_row.addWidget(icon_label)

            q_label = QLabel(question)
            q_label.setStyleSheet("background: transparent; font-size: 14px; font-weight: 600;")
            header_row.addWidget(q_label, stretch=1)
            card_layout.addLayout(header_row)

            a_label = QLabel(answer)
            a_label.setObjectName("muted")
            a_label.setWordWrap(True)
            a_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            card_layout.addWidget(a_label)

            scroll_layout.addWidget(card)

        scroll_layout.addStretch()
