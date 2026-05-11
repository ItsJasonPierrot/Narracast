import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from .paths import CLEAN_VOICE, REFERENCE, REFERENCE_TEXT, VOICES_DIR


@dataclass(frozen=True)
class VoiceProfile:
    id: str
    display_name: str
    ref_audio: str
    ref_text: str = ""
    notes: str = ""
    source_file: str = ""
    clip_start_s: float = 0.0
    clip_duration_s: float = 0.0
    created_at: str = ""
    updated_at: str = ""

    @property
    def label(self) -> str:
        return f"🎙 {self.display_name}"

    @property
    def folder(self) -> Path:
        return VOICES_DIR / self.id


@dataclass(frozen=True)
class ReferenceInfo:
    audio_path: str
    text_path: str
    ref_text: str
    signature: str
    cache_hit: bool = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()
    return slug or "voice"


def _unique_voice_id(display_name: str) -> str:
    base = _slugify(display_name)
    candidate = base
    while (VOICES_DIR / candidate).exists():
        candidate = f"{base}-{uuid.uuid4().hex[:6]}"
    return candidate


_reference_cache: dict[str, tuple[tuple, ReferenceInfo]] = {}
_reference_cache_lock = threading.Lock()


def _profile_from_folder(folder: Path) -> VoiceProfile | None:
    meta_path = folder / "metadata.json"
    if not meta_path.exists():
        return None
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    audio_path = folder / "reference.wav"
    text_path = folder / "reference.txt"
    if not audio_path.exists():
        return None

    ref_text = ""
    if text_path.exists():
        ref_text = text_path.read_text(encoding="utf-8").strip()

    return VoiceProfile(
        id=str(payload.get("id") or folder.name),
        display_name=str(payload.get("display_name") or folder.name),
        ref_audio=str(audio_path),
        ref_text=ref_text,
        notes=str(payload.get("notes") or ""),
        source_file=str(payload.get("source_file") or ""),
        clip_start_s=float(payload.get("clip_start_s") or 0.0),
        clip_duration_s=float(payload.get("clip_duration_s") or 0.0),
        created_at=str(payload.get("created_at") or ""),
        updated_at=str(payload.get("updated_at") or ""),
    )


def list_voice_profiles() -> list[VoiceProfile]:
    profiles = []
    for folder in sorted(VOICES_DIR.iterdir()):
        if not folder.is_dir():
            continue
        profile = _profile_from_folder(folder)
        if profile:
            profiles.append(profile)
    return sorted(profiles, key=lambda p: p.display_name.lower())


def get_voice_profile(profile_id: str) -> VoiceProfile | None:
    if not profile_id:
        return None
    folder = VOICES_DIR / str(profile_id)
    if not folder.is_dir():
        return None
    return _profile_from_folder(folder)


def _write_profile_metadata(profile: VoiceProfile) -> None:
    payload = asdict(profile)
    payload.pop("ref_text", None)
    profile.folder.joinpath("metadata.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def save_voice_profile(
    preview_path: str,
    display_name: str,
    ref_text: str = "",
    notes: str = "",
    source_file: str = "",
    clip_start_s: float = 0.0,
    clip_duration_s: float = 0.0,
) -> VoiceProfile:
    if not preview_path:
        raise ValueError("Extract a clip first, then save a voice.")
    source = Path(preview_path)
    if not source.exists():
        raise FileNotFoundError(f"Reference clip not found: {preview_path}")

    name = str(display_name or "").strip()
    if not name:
        raise ValueError("Give this voice a name first.")

    voice_id = _unique_voice_id(name)
    folder = VOICES_DIR / voice_id
    folder.mkdir(parents=True, exist_ok=False)

    audio_path = folder / "reference.wav"
    text_path = folder / "reference.txt"
    meta_path = folder / "metadata.json"

    shutil.copy2(str(source), str(audio_path))
    clean_text = str(ref_text or "").strip()
    text_path.write_text(clean_text, encoding="utf-8")

    now = _now_iso()
    profile = VoiceProfile(
        id=voice_id,
        display_name=name,
        ref_audio=str(audio_path),
        ref_text=clean_text,
        notes=str(notes or "").strip(),
        source_file=str(source_file or ""),
        clip_start_s=float(clip_start_s or 0.0),
        clip_duration_s=float(clip_duration_s or 0.0),
        created_at=now,
        updated_at=now,
    )
    _write_profile_metadata(profile)
    clear_reference_cache()
    return profile


def rename_voice_profile(profile_id: str, display_name: str, notes: str | None = None) -> VoiceProfile:
    profile = get_voice_profile(profile_id)
    if not profile:
        raise FileNotFoundError("Voice profile not found.")

    name = str(display_name or "").strip()
    if not name:
        raise ValueError("Voice name cannot be empty.")

    updated = VoiceProfile(
        id=profile.id,
        display_name=name,
        ref_audio=profile.ref_audio,
        ref_text=profile.ref_text,
        notes=profile.notes if notes is None else str(notes or "").strip(),
        source_file=profile.source_file,
        clip_start_s=profile.clip_start_s,
        clip_duration_s=profile.clip_duration_s,
        created_at=profile.created_at,
        updated_at=_now_iso(),
    )
    _write_profile_metadata(updated)
    clear_reference_cache()
    return updated


def delete_voice_profile(profile_id: str) -> bool:
    profile = get_voice_profile(profile_id)
    if not profile:
        return False
    shutil.rmtree(profile.folder)
    clear_reference_cache()
    return True


def get_voice_files():
    result = {}
    if REFERENCE.exists():
        result["📌 reference.wav (recommended)"] = str(REFERENCE)
    for profile in list_voice_profiles():
        result[profile.label] = profile.ref_audio
    for f in sorted(CLEAN_VOICE.rglob("vocals.wav")):
        result[f.parent.name] = str(f)
    return result


def get_clean_voice_choices():
    files = sorted(CLEAN_VOICE.rglob("vocals.wav"))
    return [(f.parent.name, str(f)) for f in files]


def extract_clip(voice_path, start_time, duration):
    if not voice_path:
        return None, "⚠️  Please select a voice file."
    try:
        start_time = float(start_time)
        duration = float(duration)
    except (ValueError, TypeError):
        return None, "⚠️  Start time and duration must be numbers."
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            voice_path,
            "-ss",
            str(start_time),
            "-t",
            str(duration),
            "-acodec",
            "pcm_s16le",
            tmp.name,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None, f"⚠️  ffmpeg error: {result.stderr[:300]}"
    return tmp.name, f"✅  Extracted {duration}s starting at {start_time}s."


def reference_text_path_for_audio(audio_path):
    path = str(audio_path)
    if not path:
        return None
    if path == str(REFERENCE):
        return REFERENCE_TEXT
    maybe_profile_text = Path(path).with_name("reference.txt")
    try:
        if maybe_profile_text.exists() and VOICES_DIR in maybe_profile_text.parents:
            return maybe_profile_text
    except OSError:
        pass
    return None


def _stat_parts(path: Path | None) -> tuple[int, int]:
    if not path:
        return 0, 0
    try:
        stat = path.stat()
    except OSError:
        return 0, 0
    return stat.st_mtime_ns, stat.st_size


def _reference_fingerprint(audio_path: str) -> tuple:
    audio = str(audio_path or "")
    audio_path_obj = Path(audio) if audio else None
    text_path = reference_text_path_for_audio(audio)
    audio_mtime, audio_size = _stat_parts(audio_path_obj)
    text_mtime, text_size = _stat_parts(text_path)
    return (audio, audio_mtime, audio_size, str(text_path or ""), text_mtime, text_size)


def clear_reference_cache() -> None:
    with _reference_cache_lock:
        _reference_cache.clear()


def prepare_reference(audio_path) -> ReferenceInfo:
    """Return cached reference metadata/transcript for a reference audio path."""
    audio = str(audio_path or "")
    fingerprint = _reference_fingerprint(audio)

    with _reference_cache_lock:
        cached = _reference_cache.get(audio)
        if cached and cached[0] == fingerprint:
            return replace(cached[1], cache_hit=True)

    text_path = reference_text_path_for_audio(audio)
    ref_text = ""
    if text_path and text_path.exists():
        ref_text = text_path.read_text(encoding="utf-8").strip()

    text_hash = hashlib.sha256(ref_text.encode("utf-8")).hexdigest()
    audio_mtime = fingerprint[1]
    audio_size = fingerprint[2]
    signature = f"{audio}|{audio_mtime}|{audio_size}|{text_hash}"
    info = ReferenceInfo(
        audio_path=audio,
        text_path=str(text_path or ""),
        ref_text=ref_text,
        signature=signature,
        cache_hit=False,
    )

    with _reference_cache_lock:
        _reference_cache[audio] = (fingerprint, info)

    return info


def load_reference_text(audio_path):
    return prepare_reference(audio_path).ref_text


def reference_signature(audio_path):
    return prepare_reference(audio_path).signature


def reference_warning(audio_path):
    text_path = reference_text_path_for_audio(audio_path)
    if text_path and not load_reference_text(audio_path):
        return "Reference transcript missing. Generation may spend extra time preparing the voice."
    return ""


def save_reference_text(text):
    REFERENCE_TEXT.write_text(str(text or "").strip(), encoding="utf-8")
    clear_reference_cache()


def save_clip(preview_path, ref_text=""):
    if not preview_path:
        return "⚠️  Extract a clip first, then save."
    shutil.copy2(preview_path, str(REFERENCE))
    save_reference_text(ref_text)
    clear_reference_cache()
    return "✅  reference.wav updated — new generations will use this voice."
