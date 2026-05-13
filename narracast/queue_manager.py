"""Background generation queue."""

import queue as _q
import threading
import time
import uuid
from dataclasses import dataclass, field, replace
from typing import Optional, Any

from .audio_polish import AudioPolishSettings
from .audio_generation import generate_core
from .presets import DEFAULT_PRESET
from .voices import get_voice_files


@dataclass
class Job:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    text: str = ""
    title: str = ""
    part: str = ""
    voice: str = ""
    speed: float = 1.0
    preset: str = DEFAULT_PRESET
    paragraph_pause_ms: int = 500
    sentence_pause_ms: int = 0
    audio_polish: Optional[dict[str, Any]] = None
    project_id: str = ""
    chapter_id: str = ""
    status: str = "pending"
    progress: str = ""
    output_path: Optional[str] = None
    error_msg: Optional[str] = None
    cancel_requested: bool = False
    created_at: float = field(default_factory=time.time)


_work_q: _q.Queue = _q.Queue()
_jobs: list[Job] = []
_jobs_lock: threading.Lock = threading.Lock()
_worker_thread: Optional[threading.Thread] = None


def list_jobs(reverse=False) -> list[Job]:
    """Return a snapshot of jobs without exposing mutable queue state."""
    with _jobs_lock:
        jobs = list(_jobs)
    if reverse:
        jobs.reverse()
    return [replace(job) for job in jobs]


def get_job(job_id: str) -> Optional[Job]:
    """Return a snapshot of a job by id."""
    with _jobs_lock:
        job = next((j for j in _jobs if j.id == job_id), None)
        return replace(job) if job else None


def clear_finished_jobs() -> int:
    """Remove done, error, and cancelled jobs. Return the number removed."""
    with _jobs_lock:
        before = len(_jobs)
        _jobs[:] = [j for j in _jobs if j.status not in ("done", "error", "cancelled")]
        return before - len(_jobs)


def cancel_job(job_id: str) -> str:
    """Request cancellation for a pending job and return a user-facing result code."""
    with _jobs_lock:
        job = next((j for j in _jobs if j.id == job_id), None)
        if job is None:
            return "missing"
        if job.status == "pending":
            job.cancel_requested = True
            job.progress = "Cancelling…"
            return "cancelled"
        if job.status == "generating":
            return "active"
        return "not_pending"


def retry_job(job_id: str) -> tuple[str, Optional[Job]]:
    """Queue a fresh copy of a failed job."""
    with _jobs_lock:
        job = next((j for j in _jobs if j.id == job_id), None)
        if job is None:
            return "missing", None
        if job.status != "error":
            return "not_error", replace(job)
        retry = Job(
            text=job.text,
            title=job.title,
            part=job.part,
            voice=job.voice,
            speed=job.speed,
            preset=job.preset,
            paragraph_pause_ms=job.paragraph_pause_ms,
            sentence_pause_ms=job.sentence_pause_ms,
            audio_polish=dict(job.audio_polish) if job.audio_polish else None,
            project_id=job.project_id,
            chapter_id=job.chapter_id,
        )
        _jobs.append(retry)
    _work_q.put(retry.id)
    return "queued", replace(retry)


def _worker():
    while True:
        job_id = _work_q.get()
        with _jobs_lock:
            job = next((j for j in _jobs if j.id == job_id), None)
        if job is None:
            _work_q.task_done()
            continue
        if job.cancel_requested:
            job.status = "cancelled"
            job.progress = "Cancelled"
            _work_q.task_done()
            continue
        job.status = "generating"
        job.progress = "Starting…"

        def on_progress(frac, desc="", _job=job):
            _job.progress = f"{int(frac * 100)}%  {desc}"

        try:
            path, _ = generate_core(
                job.text,
                job.voice,
                job.speed,
                job.title,
                job.part,
                on_progress,
                job.preset,
                paragraph_pause_ms=job.paragraph_pause_ms,
                sentence_pause_ms=job.sentence_pause_ms,
                audio_polish=(
                    AudioPolishSettings.from_dict(job.audio_polish)
                    if job.audio_polish
                    else None
                ),
                project_id=job.project_id,
                chapter_id=job.chapter_id,
            )
            job.status = "done"
            job.output_path = path
            job.progress = "Complete"
            if job.project_id and job.chapter_id:
                from .projects import mark_chapter_generated

                mark_chapter_generated(job.project_id, job.chapter_id, path)
        except Exception as e:
            job.status = "error"
            job.error_msg = str(e)[:200]
            if job.project_id and job.chapter_id:
                from .projects import mark_chapter_error

                mark_chapter_error(job.project_id, job.chapter_id)
        finally:
            _work_q.task_done()


def start_queue_worker():
    """Start the background queue worker once."""
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _worker_thread = threading.Thread(target=_worker, daemon=True)
    _worker_thread.start()


def add_to_queue(
    text, voice_name, speed, title, part,
    preset_name=DEFAULT_PRESET, paragraph_pause_ms: int = 500,
    sentence_pause_ms: int = 0,
    audio_polish: AudioPolishSettings | dict[str, Any] | None = None,
    project_id: str = "",
    chapter_id: str = "",
):
    if not text.strip():
        return "Please paste some text first."
    voice_map = get_voice_files()
    if not voice_name or voice_name not in voice_map:
        return "Please select a reference voice."
    job = Job(
        text=text,
        title=title,
        part=part,
        voice=voice_name,
        speed=speed,
        preset=preset_name,
        paragraph_pause_ms=paragraph_pause_ms,
        sentence_pause_ms=sentence_pause_ms,
        audio_polish=(
            audio_polish.to_dict()
            if hasattr(audio_polish, "to_dict")
            else dict(audio_polish)
            if audio_polish
            else None
        ),
        project_id=project_id,
        chapter_id=chapter_id,
    )
    with _jobs_lock:
        jobs_ahead = sum(1 for j in _jobs if j.status in ("pending", "generating"))
        _jobs.append(job)
    _work_q.put(job.id)
    if project_id and chapter_id:
        from .projects import mark_chapter_queued

        mark_chapter_queued(project_id, chapter_id)
    label = f'"{title}"' if title else f'"{text[:40]}…"'
    msg = f"Queued: {label}"
    if jobs_ahead:
        msg += f"\n{jobs_ahead} job(s) ahead of it."
    else:
        msg += "\nGenerating now — check the Queue tab for progress."
    return msg
