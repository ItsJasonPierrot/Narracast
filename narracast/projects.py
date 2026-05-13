"""Project / Book Mode storage helpers."""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from .paths import PROJECTS_DIR


def _now() -> float:
    return time.time()


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


def _project_path(project_id: str, root: Path = PROJECTS_DIR) -> Path:
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", project_id)
    if not safe_id:
        raise ValueError("Project id is required.")
    return root / f"{safe_id}.json"


def _clean_str(value: Any) -> str:
    return str(value or "").strip()


def _clean_chapter(raw: dict[str, Any]) -> dict[str, Any]:
    created = float(raw.get("created_at") or _now())
    return {
        "id": _clean_str(raw.get("id")) or _new_id(),
        "title": _clean_str(raw.get("title")) or "Untitled chapter",
        "text": _clean_str(raw.get("text")),
        "status": _clean_str(raw.get("status")) or "draft",
        "output_path": _clean_str(raw.get("output_path")),
        "created_at": created,
        "updated_at": float(raw.get("updated_at") or created),
    }


def clean_project(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized project payload safe to write to disk."""
    created = float(raw.get("created_at") or _now())
    chapters = raw.get("chapters")
    if not isinstance(chapters, list):
        chapters = []
    sessions = raw.get("sessions")
    if not isinstance(sessions, list):
        sessions = []
    return {
        "schema_version": 1,
        "id": _clean_str(raw.get("id")) or _new_id(),
        "title": _clean_str(raw.get("title")) or "Untitled project",
        "author": _clean_str(raw.get("author")),
        "voice": _clean_str(raw.get("voice")),
        "speed": float(raw.get("speed") or 1.0),
        "notes": _clean_str(raw.get("notes")),
        "chapters": [
            _clean_chapter(chapter)
            for chapter in chapters
            if isinstance(chapter, dict)
        ],
        "sessions": [
            _clean_session(session)
            for session in sessions
            if isinstance(session, dict)
        ],
        "created_at": created,
        "updated_at": float(raw.get("updated_at") or created),
    }


def _clean_session(raw: dict[str, Any]) -> dict[str, Any]:
    created = float(raw.get("created_at") or _now())
    chapter_ids = raw.get("chapter_ids")
    if not isinstance(chapter_ids, list):
        chapter_ids = []
    return {
        "id": _clean_str(raw.get("id")) or _new_id(),
        "title": _clean_str(raw.get("title")) or "Session",
        "chapter_ids": [_clean_str(chapter_id) for chapter_id in chapter_ids if chapter_id],
        "status": _clean_str(raw.get("status")) or "open",
        "created_at": created,
        "updated_at": float(raw.get("updated_at") or created),
    }


def save_project(project: dict[str, Any], root: Path = PROJECTS_DIR) -> dict[str, Any]:
    """Persist *project* and return the cleaned payload."""
    root.mkdir(parents=True, exist_ok=True)
    payload = clean_project({**project, "updated_at": _now()})
    path = _project_path(payload["id"], root)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return payload


def create_project(
    title: str,
    *,
    author: str = "",
    voice: str = "",
    speed: float = 1.0,
    notes: str = "",
    root: Path = PROJECTS_DIR,
) -> dict[str, Any]:
    """Create and persist a new project."""
    return save_project(
        {
            "id": _new_id(),
            "title": title,
            "author": author,
            "voice": voice,
            "speed": speed,
            "notes": notes,
            "chapters": [],
            "sessions": [],
            "created_at": _now(),
        },
        root=root,
    )


def load_project(project_id: str, root: Path = PROJECTS_DIR) -> dict[str, Any] | None:
    """Load one project by id."""
    path = _project_path(project_id, root)
    try:
        return clean_project(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def list_projects(root: Path = PROJECTS_DIR) -> list[dict[str, Any]]:
    """Return all projects, newest updated first."""
    projects: list[dict[str, Any]] = []
    for path in root.glob("*.json"):
        try:
            project = clean_project(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
        projects.append(project)
    return sorted(projects, key=lambda p: p.get("updated_at", 0), reverse=True)


def delete_project(project_id: str, root: Path = PROJECTS_DIR) -> bool:
    """Delete a project JSON file."""
    path = _project_path(project_id, root)
    if not path.exists():
        return False
    path.unlink()
    return True


def update_project(
    project_id: str,
    *,
    title: str | None = None,
    author: str | None = None,
    voice: str | None = None,
    speed: float | None = None,
    notes: str | None = None,
    root: Path = PROJECTS_DIR,
) -> dict[str, Any] | None:
    """Update top-level project fields."""
    project = load_project(project_id, root)
    if project is None:
        return None
    for key, value in {
        "title": title,
        "author": author,
        "voice": voice,
        "notes": notes,
    }.items():
        if value is not None:
            project[key] = value
    if speed is not None:
        project["speed"] = speed
    return save_project(project, root=root)


def add_chapter(
    project_id: str,
    title: str,
    text: str,
    *,
    root: Path = PROJECTS_DIR,
) -> dict[str, Any] | None:
    """Append a chapter to a project."""
    project = load_project(project_id, root)
    if project is None:
        return None
    chapter = _clean_chapter(
        {
            "id": _new_id(),
            "title": title,
            "text": text,
            "status": "draft",
            "created_at": _now(),
        }
    )
    project["chapters"].append(chapter)
    project["sessions"] = []
    save_project(project, root=root)
    return chapter


def update_chapter(
    project_id: str,
    chapter_id: str,
    *,
    title: str | None = None,
    text: str | None = None,
    status: str | None = None,
    output_path: str | None = None,
    root: Path = PROJECTS_DIR,
) -> dict[str, Any] | None:
    """Update a chapter and return it."""
    project = load_project(project_id, root)
    if project is None:
        return None
    for chapter in project["chapters"]:
        if chapter["id"] != chapter_id:
            continue
        if title is not None:
            chapter["title"] = title
        if text is not None:
            chapter["text"] = text
        if status is not None:
            chapter["status"] = status
        if output_path is not None:
            chapter["output_path"] = output_path
        chapter["updated_at"] = _now()
        save_project(project, root=root)
        return chapter
    return None


def delete_chapter(project_id: str, chapter_id: str, root: Path = PROJECTS_DIR) -> bool:
    """Delete one chapter from a project."""
    project = load_project(project_id, root)
    if project is None:
        return False
    before = len(project["chapters"])
    project["chapters"] = [c for c in project["chapters"] if c["id"] != chapter_id]
    for session in project.get("sessions", []):
        session["chapter_ids"] = [
            existing_id for existing_id in session["chapter_ids"] if existing_id != chapter_id
        ]
    if len(project["chapters"]) == before:
        return False
    save_project(project, root=root)
    return True


def estimate_chapter_duration_s(chapter: dict[str, Any], words_per_minute: int = 150) -> int:
    """Estimate listening duration for a chapter by word count."""
    words = len(_clean_str(chapter.get("text")).split())
    if words == 0:
        return 0
    return max(1, int((words / max(1, words_per_minute)) * 60))


def rebuild_sessions(
    project_id: str,
    *,
    target_minutes: int = 20,
    root: Path = PROJECTS_DIR,
) -> list[dict[str, Any]]:
    """Create listening sessions by grouping chapters up to an estimated duration."""
    project = load_project(project_id, root)
    if project is None:
        return []

    target_s = max(1, target_minutes) * 60
    sessions: list[dict[str, Any]] = []
    current_ids: list[str] = []
    current_s = 0

    for chapter in project["chapters"]:
        duration_s = estimate_chapter_duration_s(chapter)
        if current_ids and current_s + duration_s > target_s:
            sessions.append(_session_payload(len(sessions) + 1, current_ids))
            current_ids = []
            current_s = 0
        current_ids.append(chapter["id"])
        current_s += duration_s

    if current_ids:
        sessions.append(_session_payload(len(sessions) + 1, current_ids))

    project["sessions"] = sessions
    save_project(project, root=root)
    return sessions


def _session_payload(index: int, chapter_ids: list[str]) -> dict[str, Any]:
    return _clean_session(
        {
            "id": _new_id(),
            "title": f"Session {index}",
            "chapter_ids": list(chapter_ids),
            "status": "open",
            "created_at": _now(),
        }
    )


def session_progress(project: dict[str, Any], session: dict[str, Any]) -> tuple[int, int]:
    """Return completed chapters and total chapters for a session."""
    chapters = {chapter["id"]: chapter for chapter in project.get("chapters", [])}
    total = len(session.get("chapter_ids", []))
    done = 0
    for chapter_id in session.get("chapter_ids", []):
        chapter = chapters.get(chapter_id)
        if chapter and chapter.get("status") == "generated":
            done += 1
    if session.get("status") == "complete":
        done = total
    return done, total


def mark_session_complete(
    project_id: str,
    session_id: str,
    *,
    root: Path = PROJECTS_DIR,
) -> dict[str, Any] | None:
    """Mark a reading/listening session complete."""
    project = load_project(project_id, root)
    if project is None:
        return None
    for session in project.get("sessions", []):
        if session["id"] == session_id:
            session["status"] = "complete"
            session["updated_at"] = _now()
            save_project(project, root=root)
            return session
    return None


def next_unfinished_session(project: dict[str, Any]) -> dict[str, Any] | None:
    """Return the first session that is not complete."""
    for session in project.get("sessions", []):
        done, total = session_progress(project, session)
        if total > 0 and done < total:
            return session
    return None


def update_session(
    project_id: str,
    session_id: str,
    *,
    title: str | None = None,
    status: str | None = None,
    chapter_ids: list[str] | None = None,
    root: Path = PROJECTS_DIR,
) -> dict[str, Any] | None:
    """Update a session title, status, or chapter membership."""
    project = load_project(project_id, root)
    if project is None:
        return None
    for session in project.get("sessions", []):
        if session["id"] != session_id:
            continue
        if title is not None:
            session["title"] = _clean_str(title) or session["title"]
        if status is not None:
            session["status"] = _clean_str(status) or session["status"]
        if chapter_ids is not None:
            known = {chapter["id"] for chapter in project.get("chapters", [])}
            session["chapter_ids"] = [
                chapter_id for chapter_id in chapter_ids if chapter_id in known
            ]
        session["updated_at"] = _now()
        save_project(project, root=root)
        return session
    return None


def split_session_after_chapter(
    project_id: str,
    session_id: str,
    chapter_id: str,
    *,
    root: Path = PROJECTS_DIR,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Split a session into two sessions after *chapter_id*."""
    project = load_project(project_id, root)
    if project is None:
        return None
    sessions = project.get("sessions", [])
    for index, session in enumerate(sessions):
        if session["id"] != session_id or chapter_id not in session["chapter_ids"]:
            continue
        split_at = session["chapter_ids"].index(chapter_id) + 1
        left_ids = session["chapter_ids"][:split_at]
        right_ids = session["chapter_ids"][split_at:]
        if not left_ids or not right_ids:
            return None
        session["chapter_ids"] = left_ids
        session["updated_at"] = _now()
        new_session = _session_payload(index + 2, right_ids)
        new_session["title"] = f"{session['title']} B"
        sessions.insert(index + 1, new_session)
        save_project(project, root=root)
        return session, new_session
    return None


def merge_session_with_next(
    project_id: str,
    session_id: str,
    *,
    root: Path = PROJECTS_DIR,
) -> dict[str, Any] | None:
    """Merge a session with the session immediately after it."""
    project = load_project(project_id, root)
    if project is None:
        return None
    sessions = project.get("sessions", [])
    for index, session in enumerate(sessions[:-1]):
        if session["id"] != session_id:
            continue
        next_session = sessions.pop(index + 1)
        session["chapter_ids"] = [
            *session.get("chapter_ids", []),
            *next_session.get("chapter_ids", []),
        ]
        session["status"] = "open"
        session["updated_at"] = _now()
        save_project(project, root=root)
        return session
    return None


def refresh_project_outputs(project_id: str, root: Path = PROJECTS_DIR) -> dict[str, Any] | None:
    """Refresh generated/missing status based on chapter output files."""
    project = load_project(project_id, root)
    if project is None:
        return None
    changed = False
    for chapter in project.get("chapters", []):
        output_path = chapter.get("output_path", "")
        if not output_path:
            continue
        exists = Path(output_path).exists()
        new_status = "generated" if exists else "missing"
        if chapter.get("status") != new_status:
            chapter["status"] = new_status
            chapter["updated_at"] = _now()
            changed = True
    return save_project(project, root=root) if changed else project


def mark_chapter_queued(project_id: str, chapter_id: str, root: Path = PROJECTS_DIR) -> None:
    update_chapter(project_id, chapter_id, status="queued", root=root)


def mark_chapter_generated(
    project_id: str,
    chapter_id: str,
    output_path: str,
    root: Path = PROJECTS_DIR,
) -> None:
    update_chapter(
        project_id,
        chapter_id,
        status="generated",
        output_path=output_path,
        root=root,
    )


def mark_chapter_error(project_id: str, chapter_id: str, root: Path = PROJECTS_DIR) -> None:
    update_chapter(project_id, chapter_id, status="error", root=root)
