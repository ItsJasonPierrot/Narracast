"""Generation presets and formatting helpers."""

DEFAULT_PRESET = "Balanced"

GENERATION_PRESETS = {
    "Best": {
        "chunk_size": 500,
        "nfe_step": 32,
        "description": "Highest quality, slower generation",
    },
    "Balanced": {
        "chunk_size": 750,
        "nfe_step": 32,
        "description": "Default quality/speed balance",
    },
    "Fast": {
        "chunk_size": 1000,
        "nfe_step": 24,
        "description": "Faster long-form generation",
    },
    "Draft": {
        "chunk_size": 1200,
        "nfe_step": 16,
        "description": "Quick rough listening copy",
    },
}


def get_generation_preset(name: str):
    return GENERATION_PRESETS.get(name, GENERATION_PRESETS[DEFAULT_PRESET])


def format_duration(seconds: float | int) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    mins, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {mins:02d}m"
    if mins:
        return f"{mins}m {secs:02d}s"
    return f"{secs}s"

