# Changelog

All notable releases of Narracast are documented here.

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
