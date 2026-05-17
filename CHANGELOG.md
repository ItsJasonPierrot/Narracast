# Changelog

All notable releases of Narracast are documented here.

---

## v1.5.0 — 2026-05-17

Major feature release. Live audio streaming during generation, isolated TTS subprocess, WiFi server for iPhone transfer, MP3 folder import, session reorder, session-level reader launch, and a full UX/accessibility pass.

### Streaming chunk playback

- Audio plays through your speakers after the very first synthesised chunk — you no longer wait for the whole file before hearing anything
- `ChunkStreamer` (`narracast/chunk_stream.py`) launches `ffplay` and pipes raw PCM over a streaming WAV-over-stdin header
- Falls back gracefully when `ffplay` is not installed — generation completes normally without streaming
- A "Streaming audio as it generates…" label appears in the Generate page job card during active streaming

### Local TTS backend process

- F5-TTS now runs in a persistent subprocess (`tts_worker.py`) rather than inside the GUI process — an inference crash can no longer freeze or kill the app window
- `TTSProcess` (`narracast/tts_process.py`) manages the worker: spawns it, reads its JSON-line responses in a daemon thread, and routes each message to the active job's `JobCallbacks`
- `JobCallbacks` is a dataclass with optional `on_progress`, `on_chunk`, `on_done`, `on_error`, `on_cancelled`, `on_preview_done`, and `on_benchmark_preset_done` hooks
- Cancellation fires between chunks via a `threading.Event` — no chunk is left half-generated
- Benchmark and voice preview are routed through the same worker, so there is only one model load

### WiFi Transfer Server

- New **Transfer** page in the sidebar starts a local HTTP server (`narracast/wifi_server.py`) over your LAN — no cables, no cloud, no iTunes
- Serve any MP3 and its sidecar JSON to your iPhone's Safari browser or the Narracast iOS companion app
- Endpoints: `GET /api/info`, `GET /api/files`, `GET /api/audio/<filename>` (with `Range` support for seeking), `GET /api/metadata/<filename>`
- Port 8765 with automatic fallback to 8766–8774 if already in use
- Path traversal rejected at the handler level before any filesystem access
- Server auto-starts when the Transfer page is shown; stops cleanly on app quit

### Projects improvements

- **Import MP3 folder** (`narracast/mp3_folder_import.py`) — import an existing folder of MP3s as a sidecar-aware project; files are sorted in natural order; files without sidecars get draft chapter stubs
- **Session reorder** — move sessions up or down with Up / Down buttons without changing chapter membership
- **Read Session** — opens all generated chapters in a session as a playback queue in the reading companion; **Next chapter** button advances without leaving the reader

### UX / accessibility

- 12 UI bugs fixed across all eight pages: invisible Reveal button, hardcoded dark-only colours, `text-transform` QSS workaround (uppercase in Python), Divider colour, light mode parity, delete confirmation dialogs, macOS-only Menlo font, waveform placeholder, Help page colours, sidebar, Generate right rail, and Reading page bars
- `QLabel#h3` and `QLabel#app_name` added to both dark and light QSS themes
- Transfer page status dot given `setAccessibleName` and `setToolTip`; status colours extracted to named `_DOT_COLOR` constants
- All icon-only interactive buttons confirmed to carry text labels; tooltip on the only icon-only button (Transfer refresh)

### Tests

- **365 backend tests** (up from 185 at v1.0.0)
- New test modules: `test_chunk_stream.py` (44 tests), `test_tts_process.py` (37 tests), `test_wifi_server.py` (32 tests), `test_platform.py`, `test_mp3_folder_import.py`, `test_timing_analysis.py`, `test_projects_page.py`, `test_ui_layout.py`

---

## v1.0.0 — 2026-05-13

First stable release. Core feature set complete and tagged.

### Generation
- Offline text-to-speech via F5-TTS — Best, Balanced, Fast, and Draft quality presets
- Voice cloning from any audio file; Browse… imports WAV / MP3 / FLAC / M4A / OGG / AIFF without Demucs
- Named voice library under `voices/` — save, rename, delete, preview, and select profiles per project
- Reference transcript caching keyed on audio path, mtime, size, and transcript hash
- Preview first section — Draft preset, zero pauses, in-memory cache invalidated on voice changes
- Paragraph pause slider (0–2 s generated silence between paragraphs)
- Sentence pause slider (default-off, generates silence between sentences for study pacing)
- Advanced audio polish — MP3 bitrate, peak normalization, fade in/out, leading/trailing silence trim
- Audio polish settings carried through queue jobs and retries
- Text cleanup toolbar — Spaces / Hyphens / Page nos / URLs / All / PDF clean / Raw–Cleaned preview
- File drop and Browse import for `.txt` and `.pdf` on the Generate page
- Background generation queue — cancel pending, retry failed, reveal output, clear finished
- Generation benchmark dialog — all presets, chunks, generation time, audio duration, real-time factor
- Timing analysis dialog — summarizes recent sidecar stage timings; flags if async finalization is worth prototyping

### Reading companion
- Sentence-level synchronized text highlighting; falls back to chunk timeline for older files
- Full-text scrolling view and Focus Mode (previous / current / next chunks)
- Bookmarks with labels, Jump, Delete; last playback position saved per file and restored on reopen
- –10 s / +10 s / Repeat current chunk controls
- Auto-pause after paragraph gaps; Study mode (pauses on each sentence advance)
- Display controls — font family, size (S / M / L / XL), theme, line and paragraph spacing; persisted in `settings.json`
- Reader controls disabled until a file is loaded

### Projects
- Project create / edit / delete; chapters with title, text, voice, speed, and status tracking
- Automatic chapter splitting from pasted text or imported file — heading detection, custom markers, single-chapter fallback
- Import source metadata stored per chapter; sessions rebuilt automatically after every import
- Reading sessions — estimated-duration splits, progress tracking, mark complete, rename, split, merge
- Session-level reader launch — Read Session opens all generated chapters as a playback queue with a Next chapter control
- M4B audiobook export — chapter audit table, skip-missing option, ffmpeg concat + FFmetadata chapter markers, background progress

### Infrastructure
- PySide6 `QMainWindow` with left sidebar, stacked pages, dark/light stylesheet
- qtawesome mdi6 icon system via `narracast/ui/icons.py` — no emoji in the interface
- Sidecar `.json` alongside every MP3 — source text, voice, speed, preset, pauses, chunk timeline, sentence highlight units, text offsets, audio and stage timings, polish settings, project/chapter IDs, last position, bookmarks
- ID3 tags (title, album, track, artist) written to every generated MP3
- Persistent `settings.json` — voice, speed, preset, title, part, pauses, theme, geometry, last page, all reader display options
- macOS app bundle with branded `.icns`, splash screen, background model loader, `~/Library/Logs/Narracast.log`
- 185 backend tests

---

## Post-v1 — Planned

See [NARRACAST_ROADMAP.md](NARRACAST_ROADMAP.md) for the prioritised post-v1 backlog.
