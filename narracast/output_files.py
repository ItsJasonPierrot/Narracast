"""Output filename, history, and file-loading helpers."""

import re
from datetime import datetime
from pathlib import Path

from .paths import OUTPUT_DIR

MAX_IMPORT_BYTES = 25 * 1024 * 1024

SUPPORTED_AUDIO_SUFFIXES = {".mp3", ".m4b", ".wav", ".aac", ".m4a"}


def make_output_filename(text, title="", part=""):
    date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if title.strip():
        title_slug = re.sub(r"[^\w\s]", "", title.strip()).replace(" ", "-")
        part_slug = (
            re.sub(r"[^\w\s]", "", part.strip()).replace(" ", "-")
            if part.strip()
            else ""
        )
        name = title_slug + ("_" + part_slug if part_slug else "")
    else:
        words = re.sub(r"[^\w\s]", "", text.strip()).split()[:5]
        name = "-".join(words)
    return f"{name}_{date}.mp3"


def load_file(filepath):
    if filepath is None:
        return ""
    path = Path(filepath)
    try:
        if path.stat().st_size > MAX_IMPORT_BYTES:
            limit_mb = MAX_IMPORT_BYTES // (1024 * 1024)
            return f"File is too large to import safely. Limit: {limit_mb} MB."
    except OSError as e:
        return f"Could not read file: {e}"

    if path.suffix.lower() == ".pdf":
        try:
            from pdfminer.high_level import extract_text

            return extract_text(str(path))
        except ImportError:
            return "PDF support not installed. Run: pip install pdfminer.six"
        except Exception as e:
            return f"Could not read PDF: {e}"
    elif path.suffix.lower() == ".txt":
        return path.read_text(encoding="utf-8", errors="replace")
    return "Only .txt and .pdf files are supported."


def is_supported_audio_path(path: str | Path | None) -> bool:
    """Return True when *path* points to an existing supported audio file."""
    if path is None:
        return False
    try:
        audio_path = Path(path).expanduser()
    except (TypeError, ValueError):
        return False
    if "\n" in str(audio_path) or "\r" in str(audio_path):
        return False
    return audio_path.exists() and audio_path.suffix.lower() in SUPPORTED_AUDIO_SUFFIXES


def list_history_files():
    """Return generated MP3 files newest first."""
    return sorted(OUTPUT_DIR.glob("*.mp3"), key=lambda f: f.stat().st_mtime, reverse=True)


def format_history_row(path: Path):
    """Format an MP3 path for the history table."""
    size_kb = path.stat().st_size // 1024
    mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d  %H:%M")
    return path.name, f"{size_kb} KB", mtime


def get_history_choices():
    choices = []
    for f in list_history_files():
        name, size, _mtime = format_history_row(f)
        choices.append((name, size, f))
    return choices


def clear_history(confirmed):
    if not confirmed:
        return "Tick the checkbox first to confirm deletion."
    count = delete_all_history()
    return f"Deleted {count} file(s)."


def delete_all_history() -> int:
    """Delete all generated MP3 files and return the number removed."""
    files = list(OUTPUT_DIR.glob("*.mp3"))
    for f in files:
        f.with_suffix(".json").unlink(missing_ok=True)
        f.unlink()
    return len(files)
