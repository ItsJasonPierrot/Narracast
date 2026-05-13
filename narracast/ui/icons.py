"""Centralised icon helpers — wraps qtawesome with app colour defaults."""
from __future__ import annotations

import qtawesome as qta
from PySide6.QtGui import QIcon

# Palette — matches theme.py
_TEXT = "#c8d8e8"
_MUTED = "#6b7f96"
_ACCENT = "#a3ff73"
_WARN = "#f0b429"
_DANGER = "#e05c5c"


def icon(name: str, color: str = _TEXT) -> QIcon:
    return qta.icon(name, color=color)


def accent(name: str) -> QIcon:
    return qta.icon(name, color=_ACCENT)


def warn(name: str) -> QIcon:
    return qta.icon(name, color=_WARN)


def danger(name: str) -> QIcon:
    return qta.icon(name, color=_DANGER)


def muted(name: str) -> QIcon:
    return qta.icon(name, color=_MUTED)


# ── Named constants so call sites don't hardcode mdi6 strings ──────────────

MICROPHONE       = "mdi6.microphone"
PLAY             = "mdi6.play"
PAUSE            = "mdi6.pause"
STOP             = "mdi6.stop"
REWIND_10        = "mdi6.rewind-10"
FAST_FORWARD_10  = "mdi6.fast-forward-10"
REPEAT           = "mdi6.repeat-once"
PLAYLIST_ADD     = "mdi6.playlist-plus"
BOOK_OPEN        = "mdi6.book-open-page-variant"
HEADPHONES       = "mdi6.headphones"
FOLDER_OPEN      = "mdi6.folder-open"
DELETE           = "mdi6.delete"
REFRESH          = "mdi6.refresh"
MOON             = "mdi6.weather-night"
SUN              = "mdi6.white-balance-sunny"
BOOKMARK_ADD     = "mdi6.bookmark-plus"
BOOKMARK_JUMP    = "mdi6.bookmark-check"
BOOKMARK_DEL     = "mdi6.bookmark-remove"
FOCUS            = "mdi6.fit-to-screen"
FULL_TEXT        = "mdi6.text-long"
SCISSORS         = "mdi6.scissors-cutting"
SAVE             = "mdi6.content-save"
SAVE_VOICE       = "mdi6.account-voice"
PREVIEW_BOX      = "mdi6.play-box-outline"
CHEVRON_RIGHT    = "mdi6.chevron-right"
CHEVRON_DOWN     = "mdi6.chevron-down"
COG              = "mdi6.cog"
UPLOAD_FILE      = "mdi6.file-upload-outline"
IMPORT_FILE      = "mdi6.file-import-outline"
RENAME           = "mdi6.pencil"
CLOSE            = "mdi6.close"
CHECK            = "mdi6.check"
ALERT            = "mdi6.alert"
REVEAL           = "mdi6.folder-search-outline"
