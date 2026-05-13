# Narracast Roadmap

An offline reading companion for people who want to read, but whose brain needs another route into the text — useful for dyslexia, ADHD, ASD, visual fatigue, chronic overwhelm, language learning, study, faith reading, and anyone who benefits from audio-supported reading.

> The app should make returning to text feel easy.

Ratings use a 1–5 scale: **User Value** (how much this improves real use), **Difficulty** (implementation complexity), **Risk** (chance of bugs or awkward UX).

---

## v1.0.0 — Shipped (2026-05-13)

Everything below describes the current completed baseline. The original `v1.0.0`
tag predates a few post-v1 hardening and packaging notes called out under
Infrastructure.

**Generation**
- F5-TTS offline speech synthesis — Best / Balanced / Fast / Draft presets
- Voice cloning from any audio file; Browse… skips Demucs entirely
- Named voice library in the Narracast app-data folder with reference audio, transcript, metadata, preview, rename, delete
- Reference transcript caching (path / mtime / transcript hash); cache hits recorded in sidecars
- Preview first section — Draft preset, zero pauses, in-memory cache keyed on text + voice + reference signature
- Paragraph pause slider (0–2 s) and Sentence pause slider (default-off, generates silence between sentences)
- Advanced audio polish: bitrate, peak normalization, fade in/out, leading/trailing silence trim
- Audio polish carried through queue, retry, and `generate_core()`
- Text cleanup toolbar: Spaces / Hyphens / Page nos / URLs / All / PDF clean / Raw–Cleaned toggle
- File drop and Browse import for `.txt` and `.pdf` on the Generate page
- Background queue with cancel, retry, clear finished; queue worker updates project chapter status
- Generation benchmark dialog (all presets, real-time factor)
- Timing analysis dialog (summarizes recent sidecar stage timings; recommends async finalization if warranted)

**Reading companion**
- Sentence-level synchronized highlighting (proportional timing within chunks); falls back to chunk timeline for older files
- Full-text scrolling view and Focus Mode (prev / current / next chunks)
- Bookmarks with labels, Jump, Delete; last position saved per file; resume on reopen
- –10 s / +10 s / Repeat current chunk controls
- Auto-pause after paragraph gaps; Study mode (pauses on each sentence advance, Play to continue)
- Display controls: font family, size (S / M / L / XL), theme (dark / light / high-contrast / warm), line and paragraph spacing — all apply to full-text and Focus Mode, persist in app-data `settings.json`
- Reader controls disabled until a file is loaded; Read + Play disabled for files without sidecar metadata

**Projects**
- Project create / edit / delete; chapters with title, text, voice, speed, status
- Automatic chapter splitting from pasted text or imported file (heading detection, custom markers, single-chapter fallback)
- Import source metadata stored per chapter; sessions rebuilt automatically after import
- Reading sessions: estimated-duration splits, progress tracking, mark complete, rename, split after chapter, merge with next
- Manual session reorder: Up / Down controls persist session order without changing chapter membership
- Session-level reader launch: Read Session opens all generated chapters as a queue; Next chapter advances without leaving the reader
- M4B audiobook export: chapter audit table, skip-missing toggle, ffmpeg concat + FFmetadata mux, QThread progress, Export M4B button in Projects

**Infrastructure**
- PySide6 `QMainWindow` with left sidebar, stacked pages, dark/light stylesheet
- qtawesome mdi6 icon system (`narracast/ui/icons.py`) — no emoji in the interface
- Sidecar `.json` for every MP3: source text, title/part, voice, speed, preset, pauses, chunk timeline, highlight units, text offsets, audio timings, stage timings, polish settings, project/chapter link, last position, bookmarks
- ID3 tags (title, album, track, artist) on every generated MP3
- Persistent app-data `settings.json`: voice, speed, preset, title, part, pauses, theme, geometry, last page, all reader display options
- User data separated from the repo/app bundle: projects, voices, reference files, generated output, and settings live under the platform app-data folder with non-destructive legacy migration
- Text/PDF import size guard, audio-path validation for reader/reveal actions, escaped ffmpeg concat paths for M4B export, and in-app privacy note for sidecar contents
- Platform shell helper for play audio, reveal file, open folder, and log directory behavior across macOS / Windows / Linux
- macOS app bundle with branded `.icns`, splash screen, background model loader, `~/Library/Logs/Narracast.log` for launch errors
- Cross-platform release packaging helper, release build notes for macOS / Windows / Linux, generated SHA-256 archive checksums, and `requirements.lock`
- 193 backend tests

---

## Current Baseline (post-v1)

All v1 features are working. The next developer can start from `app.py`, `narracast/ui/main_window.py`, and `narracast/ui/pages/`. The backend is split cleanly under `narracast/`. All icons come from `narracast/ui/icons.py` — never hardcode mdi6 strings in pages. Tests run with `venv/bin/python -m unittest discover -s tests`; `pytest` is optional if installed.

Platform note: release packaging docs exist for all three desktop OSes, and play/reveal/open-folder calls are centralized in `narracast/platform.py`. Windows/Linux still need real-machine smoke tests before calling cross-platform runtime support complete.

---

## Post-v1 Open Work

Items are ordered by suggested build sequence. Difficulty and risk use the 1–5 scale from the header.

---

### 1 · Async MP3 Finalization

**Status:** Data-gated. Do not start until timing data exists.

**Why:** If MP3 export + ID3 + metadata write is a meaningful share of total generation time, moving it off the critical path lets the next queued job start sooner.

**How to decide:** Generate 3–5 real chapters of 2 000+ words. Open Generate → Analyze timings. If the dialog recommends async, proceed. If `finalization_s / total_s` is under ~10–15%, leave it.

**When you do build it:**
- Group final MP3 / ID3 / metadata write behind a `ThreadPoolExecutor` step that runs after the last chunk but before `generate_core()` returns.
- The queue worker must wait for the future before marking the job done.
- Do not start the next job until the previous finalization future completes, to avoid concurrent disk writes on the same output directory.

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 3 | 3 | 3 |

---

### 2 · Project Import from Existing MP3 Folder

**Why:** Users who already have generated MP3s outside Narracast can't bring them into a project without re-generating.

**Scope:**
- "Import folder" action on Projects page.
- Scan for `.mp3` + sibling `.json` pairs; create chapters marked `generated` with correct `output_path`.
- Chapters without a sidecar are created as `draft` stubs with empty text.
- Rebuild sessions after import.

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 4 | 3 | 2 |

---

### 3 · Security / Privacy Hardening Follow-up

**Status:** Mostly complete. Keep this as a release checklist item.

**Done:**
- Runtime data moved to platform app-data storage with non-destructive migration from legacy repo-root folders.
- Text/PDF imports reject unexpectedly large files before parsing.
- Project reader/reveal actions require existing supported audio files.
- M4B concat files escape quotes/backslashes and reject newline-bearing paths.
- Source launcher no longer hardcodes a personal repository path.
- Help page documents that sidecars can store source text, timing data, bookmarks, and reader position.
- Release archives get SHA-256 checksum files from `scripts/build_bundle.py`.
- `requirements.lock` captures the current resolved dependency set for reproducible local builds.
- `narracast/platform.py` centralizes OS-specific play/reveal/open-folder commands.

**Remaining before public distribution:**
- Add signed/notarized macOS builds and Windows signing if distributing outside local/dev machines.
- Smoke test Windows/Linux bundles on the target machines.

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 4 | 2 | 2 |

---

### 4 · Streaming Chunk Playback

**Why:** Long chapters take minutes to generate. Streaming lets the user start listening after the first chunk instead of waiting for the full MP3.

**Scope:**
- Emit a `chunk_ready(path, index)` signal from `generate_core()` as each chunk WAV is finalized.
- Reading page (or a lightweight inline player) queues and plays chunks in order while generation continues.
- Final full MP3 and sidecar are still written when all chunks complete.
- Cancellation must clean up partial chunk files.

**Caution:** This touches the generation pipeline and the reader simultaneously. Build after async finalization (item 1) so the stage boundaries are clear.

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 5 | 4 | 4 |

---

### 5 · Local TTS Backend Process

**Why:** Moving F5-TTS into a persistent worker process isolates crashes, simplifies cancellation, and enables streaming in a cleaner way.

**Scope:**
- Worker process owns the model, device, and voice cache.
- GUI sends jobs via `multiprocessing.Queue` or local socket; worker emits progress events back.
- GUI process stays responsive even if inference blocks.

**Caution:** Do not start this before streaming chunk playback is done. Streaming will reveal what the IPC interface actually needs.

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 4 | 5 | 4 |

---

### 6 · Word-Level Highlighting — Deferred

**Why deferred:** F5-TTS produces no word timestamps. Forced alignment (e.g., `whisperx`, `montreal-forced-aligner`) requires a full second-pass over the generated audio and adds a heavy dependency. Sentence-level highlighting already covers most of the user value at a fraction of the complexity.

**Revisit when:** A lightweight forced-alignment library with an acceptable license and install size becomes available, or when sentence highlighting is demonstrably insufficient for a user group.

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 4 | 5 | 5 |

---

### 7 · Mobile Companion App — Deferred

This is a separate product. Revisit after the desktop app has a stable release history and a clear sync story.

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 5 | 5 | 5 |

---

## Product Notes

Narracast's strongest identity is accessibility-first, not productivity-first:

- It helps users read when visual reading is tiring, slippery, or overwhelming.
- It respects privacy by running entirely offline.
- It supports different processing speeds and attention patterns.
- It should stay calm, predictable, and low-stimulation by default.

Features should be judged not only by power but by whether they reduce friction for tired, distracted, overwhelmed, or dyslexic users.
