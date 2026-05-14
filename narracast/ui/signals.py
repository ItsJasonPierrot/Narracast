"""Qt signals bridge — application-wide event bus."""

from PySide6.QtCore import QObject, Signal


class AppSignals(QObject):
    generation_progress = Signal(float, str)   # fraction 0-1, description
    generation_done = Signal(str, str)          # output_path, summary message
    generation_error = Signal(str)
    preview_done = Signal(str)                  # output_path
    status_update = Signal(str)
    queue_refresh = Signal()
    model_ready = Signal(str)                   # device name
    reading_position = Signal(int)              # ms
    voice_library_changed = Signal()
    voice_preview_done = Signal(str)
    voice_preview_error = Signal(str)
    wifi_server_status = Signal(str)  # "running:http://...:PORT" | "stopped" | "error:..."


_signals = AppSignals()


def get_signals() -> AppSignals:
    return _signals
