"""Filesystem paths for Narracast."""

from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
ICON_PATH = APP_DIR / "assets" / "Narracast_Icon.png"
SPLASH_ICON_PATH = APP_DIR / "assets" / "Narracast_Splash_Icon.png"
CLEAN_VOICE = APP_DIR / "clean_voice"
VOICES_DIR = APP_DIR / "voices"
REFERENCE = APP_DIR / "reference.wav"
REFERENCE_TEXT = APP_DIR / "reference.txt"
OUTPUT_DIR = APP_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
VOICES_DIR.mkdir(parents=True, exist_ok=True)
