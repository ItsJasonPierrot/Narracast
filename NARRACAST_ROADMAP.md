# Narracast Roadmap

An offline reading companion for people who want to read, but whose brain needs another route into the text — useful for dyslexia, ADHD, ASD, visual fatigue, chronic overwhelm, language learning, study, faith reading, and anyone who benefits from audio-supported reading.

> The app should make returning to text feel easy.

Ratings use a 1–5 scale: **User Value** (how much this improves real use), **Difficulty** (implementation complexity), **Risk** (chance of bugs or awkward UX).

---

## v1.5.0 — Shipped (2026-05-17)

Streaming chunk playback, isolated TTS subprocess, WiFi Transfer Server, MP3 folder import, session reorder, session-level Read Session, and a full UX/accessibility pass.
See [CHANGELOG.md](CHANGELOG.md) for the full v1.5.0 change list.

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
- 365 backend tests
- Cross-platform shell helpers (`platform.py`): play audio, reveal file, open folder, OS-aware button labels, unified log directory
- Import existing MP3 folder into project: sidecar-aware chapter creation, natural-sort order, draft stubs for sidecar-less files, session rebuild
- Streaming chunk playback: `ChunkStreamer` pipes raw PCM to ffplay via streaming WAV-over-stdin header; `generate_core()` `on_chunk` callback; graceful degradation when ffplay absent
- Local TTS backend process: F5-TTS in a persistent subprocess (`tts_worker.py`); JSON-lines IPC + base64 PCM chunks; `TTSProcess` GUI manager with per-job `JobCallbacks`; crash-isolated; cancellation between chunks; benchmark, queue, voice preview all routed through worker

---

## Current Baseline (v1.5.0)

All v1.5.0 features are working. The next developer can start from `app.py`, `narracast/ui/main_window.py`, and `narracast/ui/pages/`. The backend is split cleanly under `narracast/`. All icons come from `narracast/ui/icons.py` — never hardcode mdi6 strings in pages. Tests run with `venv/bin/python -m pytest tests/`; 365 tests, no GPU required.

Platform note: play/reveal/open-folder calls are centralized in `narracast/platform.py` with OS-aware error handling and button labels. Windows/Linux still need real-machine smoke tests before calling cross-platform runtime support complete.

See [docs/projectdirections.md](docs/projectdirections.md) for a file-by-file walkthrough aimed at developers new to the codebase.

---

## Post-v1 Open Work

Items are ordered by suggested build sequence. Difficulty and risk use the 1–5 scale from the header.

---

### ~~1 · Async MP3 Finalization~~ — Investigated and Closed

**Decision (2026-05-14): Do not build.**

**Benchmark on Apple Silicon macOS:**

| Step | Time for 30-min chapter |
|---|---|
| MP3 export (pydub) | 0.76 s |
| ID3 tags (mutagen) | 8.5 ms |
| Metadata write (JSON) | 0.5 ms |
| **Total finalization** | **~0.77 s** |

At realistic MPS inference speeds (5–15 min per chapter), finalization represents 0.09–0.26% of total time — two orders of magnitude below the 20% threshold that would make async worthwhile. The `finalize_time_s >= 10` guard in `timing_analysis.py` is physically unreachable with pydub + mutagen on any current hardware.

Adding thread pools, future tracking, error propagation across job boundaries, and cancellation race conditions for sub-1-second savings would be net negative. **Closed.**

---

### 2 · Project Import from Existing MP3 Folder — **Shipped**

Implemented in `narracast/mp3_folder_import.py`. See v1 shipped section.

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

### 4 · Streaming Chunk Playback — **Shipped**

Audio starts playing after the first synthesised chunk; ffplay receives raw PCM via a streaming WAV header on stdin while inference continues for the remaining chunks.  The final MP3 and sidecar are still written normally when all chunks complete.

**Implementation:**
- `narracast/chunk_stream.py` — `ChunkStreamer` class: launches `ffplay -i pipe:0 -nodisp -autoexit`, writes a 44-byte streaming WAV header with `0xFFFFFFFF` unknown-size fields, then accepts `AudioSegment` chunks via `feed()`.  Falls back gracefully when ffplay is not installed.
- `generate_core()` gained an `on_chunk` parameter.  After each `infer_chunk_segment()` call, the segment is handed to `on_chunk`; errors are silently swallowed so a streaming failure can never abort normal generation.
- `GeneratePage._start_generate()` creates a `ChunkStreamer`, calls `streamer.start()`, passes `streamer.feed` as `on_chunk`, calls `streamer.close()` on success and `streamer.stop()` on error.  A "Streaming audio as it generates…" label is shown in the job card while active.
- 44 backend tests cover the WAV header byte layout, ffplay availability caching, start/feed/stop/close lifecycle, format conversion, broken-pipe handling, thread safety, and `on_chunk` behaviour in `generate_core`.

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 5 | 4 | 4 |

---

### 5 · Local TTS Backend Process — **Shipped**

F5-TTS now lives in a persistent subprocess.  The GUI process has no model object; crashes in inference leave the GUI window running, and the next generation re-uses the already-loaded worker.  Cancellation fires between chunks via a threading.Event in the worker.

**Implementation:**
- `narracast/tts_worker.py` — Worker subprocess (`python -m narracast.tts_worker`): loads F5-TTS on startup, reads JSON-line commands from stdin, writes JSON-line responses to stdout, emits PCM chunks as base64 for streaming.  Supports: `generate`, `preview`, `benchmark_preset`, `cancel`, `shutdown`, `ping`.
- `narracast/tts_process.py` — `TTSProcess` GUI-side manager: spawns the worker, reads responses in a daemon thread, routes each message to the active job's `JobCallbacks`.  `get_tts_process()` returns the application singleton.
- `narracast/audio_generation.py` — `GenerationCancelled(BaseException)` added; `on_chunk` handling updated to re-raise it so cancellation propagates through `generate_core()`.
- `app.py` — Model loading replaced: `get_tts_process().start(on_ready=..., on_load_error=...)` spawns the worker; `on_ready` fires when the worker emits `{"type": "ready"}`.  No in-process torch/F5-TTS import.
- `narracast/queue_manager.py` — `_run_job()` submits via `get_tts_process().submit_job()` and blocks on a `threading.Event` until the job's `on_done` / `on_error` / `on_cancelled` callback fires.
- `narracast/ui/pages/generate_page.py` — `_start_generate()` and `_start_preview()` replaced: no more daemon threads; both use `submit_job()` with per-job `JobCallbacks`.  Streaming via `ChunkStreamer` is preserved.
- `narracast/ui/pages/voice_page.py` — `_preview_profile()` uses `submit_preview()` instead of calling `infer_chunk()` in a thread.
- `narracast/ui/benchmark_dialog.py` — `BenchmarkWorker` submits `benchmark_preset` commands one preset at a time via `submit_benchmark_preset()`, using a `threading.Event` per preset.  Dialog shows "not ready" if worker hasn't loaded yet.
- 37 backend tests: `JobCallbacks` dataclass, all `_dispatch()` message types, `_send()` safety, full end-to-end flow with fake subprocess, `is_alive()`, singleton, and `GenerationCancelled` propagation.

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 4 | 5 | 4 |

---

### 6 · WiFi Transfer Server — **Shipped**

The Mac app runs a local HTTP server so an iPhone can pull generated MP3s and sidecar JSON over the local network — no cables, no cloud, no iTunes.

**Implementation:**
- `narracast/wifi_server.py` — `WifiServer` class: `ThreadingHTTPServer` (stdlib) running in a daemon thread. Endpoints: `GET /api/info`, `/api/files` (JSON file list), `/api/audio/<filename>` (MP3 with `Accept-Ranges`/`Range` support for seeking), `/api/metadata/<filename>` (sidecar JSON, `output_path` stripped). Path traversal rejected at 400 before any filesystem access. Port 8765 with automatic fallback to 8766–8774.
- `narracast/ui/pages/transfer_page.py` — new sidebar page: server status dot, copyable URL field, start/stop toggle, live file list (reuses `list_history_files()` and `format_history_row()`). Server auto-starts on `showEvent`; `stop_server()` wired to `MainWindow.closeEvent`.
- `narracast/ui/icons.py` — `WIFI`, `CELLPHONE`, `QR_CODE` constants added.
- `narracast/ui/sidebar.py` — "Transfer" nav entry added.
- `narracast/ui/main_window.py` — `TransferPage` registered at index 6; `closeEvent` calls `stop_server()`.
- `narracast/ui/signals.py` — `wifi_server_status` signal added.
- 32 backend tests cover server lifecycle, all four endpoints, range requests, path traversal, and multi-file listing.

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 5 | 3 | 2 |

---

### 7 · iOS Companion App — Active

**Goal:** iPhone app that connects to the Mac's WiFi transfer server, plays generated MP3s, and follows along with synchronized sentence highlighting. Reading position and bookmarks sync back to the Mac sidecar.

**Scope (MVP):**
- Browse and download MP3 + sidecar from the Mac's `/api/files` and `/api/audio/<filename>` endpoints
- Native audio playback with –10 s / +10 s / repeat
- Full-text reading view with sentence-level highlight (sidecar `timeline` field drives it)
- Save last position back to Mac (new `POST /api/position` endpoint, to be added)
- No on-device generation

**Out of scope for MVP:** word-level highlighting, iCloud sync, Android.

---

## Possible Future

These items are not planned. They may be revisited if there is clear user demand.

- **Word-level highlighting** — per-word karaoke sync; blocked on a lightweight forced-aligner with an acceptable license. Sentence-level highlighting covers the accessibility need well enough for now.
- **Android companion** — separate platform, separate product. Revisit if iOS app proves the pattern.

---

## Product Notes

Narracast's strongest identity is accessibility-first, not productivity-first:

- It helps users read when visual reading is tiring, slippery, or overwhelming.
- It respects privacy by running entirely offline.
- It supports different processing speeds and attention patterns.
- It should stay calm, predictable, and low-stimulation by default.

Features should be judged not only by power but by whether they reduce friction for tired, distracted, overwhelmed, or dyslexic users.
