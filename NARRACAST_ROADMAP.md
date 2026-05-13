# Narracast Roadmap

This roadmap turns the current Narracast app into a more complete offline audiobook and reading companion, with a special focus on people who process text more easily through listening, pacing, visual tracking, repetition, and reduced cognitive load.

Narracast can be framed as:

> An offline reading companion for people who want to read, but whose brain needs another route into the text.

This may be especially useful for dyslexia, ADHD, ASD, visual fatigue, chronic overwhelm, language learning, study, faith reading, and anyone who benefits from audio-supported reading.

Ratings use a 1-5 scale.

- **User Value:** How much this improves the app for real use.
- **Difficulty:** Estimated implementation complexity.
- **Risk:** Chance of introducing bugs, performance issues, or awkward UX.
- **Priority:** Suggested build order.

## Rating Guide

| Rating | User Value | Difficulty | Risk |
|---|---|---|---|
| 1 | Nice but minor | Tiny change | Very safe |
| 2 | Helpful polish | Small change | Low risk |
| 3 | Noticeable upgrade | Medium feature | Some edge cases |
| 4 | Major workflow improvement | Large feature | Needs careful design |
| 5 | Core product upgrade | Complex feature | High risk / needs testing |

---

## Recently Completed

| Item | Notes |
|---|---|
| Queue controls | Pending jobs can be cancelled, failed jobs can be retried, completed jobs can reveal output, and completed/error/cancelled jobs can be cleared. |
| Open output folder / reveal file | History has Reveal selected and Open output folder actions. Queue completed jobs can reveal their output too. |
| Generation speed presets | Added Best, Balanced, Fast, and Draft modes with different chunk sizes and F5-TTS `nfe_step` settings. |
| Larger default chunking | Balanced now uses 750-character chunks instead of the original 200-character chunks. |
| Brand icon | Added in-app, splash, and app-bundle icon assets with a properly scaled macOS `.icns`. |
| Better generation visibility | Progress includes preset name, chunk count, elapsed time, rolling average seconds per chunk, and ETA. |
| Module split | `app.py` is a small launcher; backend in `narracast/`; UI pages live in focused modules. |
| Persistent user settings | `narracast/settings.py` and `settings.json` persist voice, speed, preset, title, part, paragraph pause, theme, last page, and window geometry. |
| Settings validation hardening | Loaded settings are sanitized before UI use. |
| Comment and constants cleanup | Decorative comments removed, shared UI constants reused, unreachable Queue reveal call fixed. |
| Generation metadata sidecars | Every MP3 gets a `.json` sidecar with source text, title/part, voice, speed, preset, paragraph pause, chunk timeline, text offsets, and audio timings. |
| Chunk-level highlighting during playback | Read page opens any history file and highlights the current speech chunk in a scrolling Qt text view as the audio plays. |
| Resume playback and bookmarks | Last position saved per file; bookmarks with labels; back 10 s, forward 10 s, repeat current chunk. |
| Focus reading mode | Toggle between full-text scrolling view and a focused three-chunk layout (prev / current / next). S / M / L / XL font size controls included. |
| Paragraph pause slider | Slider from 0–2 s controls the silence inserted between paragraphs; stored in sidecar metadata. |
| Reader font size controls | Size buttons update the full scrolling text view and Focus Mode labels. Reader theme, spacing, font, and size now persist. |
| MP3 ID3 metadata tags | Title, album, track number, and artist written to every generated MP3 via `mutagen`. |
| Text cleanup panel | Five one-click buttons (Spaces / Hyphens / Page nos / URLs / All) using pure-regex helpers in `narracast/text_cleanup.py`. |
| PySide6 UI migration | Replaced the active Tkinter shell with a PySide6 `QMainWindow`, left sidebar navigation, `QStackedWidget` pages, dark/light stylesheet, and reusable Qt widgets. |
| PySide6 settings restore/save | Restores theme, window size, last page, title, part, voice, speed, preset, and paragraph pause; close saves all workflow settings instead of resetting to defaults. |
| PySide6 file drop support | Generate text editor accepts dropped `.txt` and `.pdf` files through the existing `load_file()` backend helper. |
| Preview signal wiring | Preview generation now updates the Last output card and enables Play/Reveal instead of completing silently. |
| PySide6 close lifecycle | Closing the window now saves workflow settings and persists the reader playback position before stopping audio. |
| Qt migration cleanup | Removed the legacy Tkinter UI modules and Tk-only asset helper; the active app is now PySide6-only. |
| PySide6 splash screen | A branded splash screen appears while local F5-TTS loading starts. Current source also has a timed fallback that opens the main window after 1.8 s while loading may continue. |
| App bundle launch logging | README documents `/Applications/Narracast.app` launch errors at `~/Library/Logs/Narracast.log`; the matching launcher wrapper source is stored at `scripts/Narracast.app-launcher.sh`. |
| Generation benchmark dialog | Generate page exposes a PySide6 benchmark dialog that runs all presets and reports chunks, generation time, audio duration, and real-time factor. |
| Reader spacing controls | Reader spacing dropdown now applies proportional line height and paragraph spacing to the full-text reader. |
| Reader highlight offset hardening | Full-text reader now uses metadata `text_start` / `text_end` offsets before falling back to text search, preventing duplicate-text mis-highlights. |
| Playback and reader tests | Added tests for last-position persistence, bookmark helpers, duplicate-text highlight offsets, and fallback highlight search. |
| Focus reader display sync | Focus Mode now follows reader theme, font, font size, spacing, and highlight colour settings. |
| Reader controls polish | Reader playback/bookmark/focus controls now stay disabled until a readable file is loaded. History disables Read mode for MP3s without Narracast sidecar metadata. |
| Preview wording polish | Preview UI now says “Preview first section,” matching the current first-500-character implementation. |
| Bundle launcher source | Added `scripts/Narracast.app-launcher.sh`, matching the installed `/Applications/Narracast.app` launcher wrapper. |
| Reference transcript support | Voice Reference can save an exact transcript to `reference.txt`; generation passes it into F5-TTS as `ref_text`. |
| Preview speed mode | Preview uses Draft settings, keeps paragraph pauses at zero, and caches repeated identical previews with reference audio/transcript invalidation. |
| Generation timing metadata | Sidecars now store timings for split, inference, waveform conversion, assembly, polish, MP3 export, ID3 tags, metadata write, finalization, total time, and reference cache hits/misses. |
| Audio polish controls | Generate page has Advanced controls for MP3 bitrate, peak normalization, fade in/out, and leading/trailing silence trim; immediate generation applies them, settings persist, and sidecars record them. Queue parity is still open. |
| Timing analysis dialog | Generate page now has Analyze timings, which summarizes recent sidecar timing data and recommends whether async finalization is worth prototyping. |
| Direct waveform conversion | Normal final MP3 generation now converts F5-TTS waveform output directly into `AudioSegment`, avoiding the per-chunk temp WAV write/reload round trip. |
| Voice Library | Named voice profiles can be saved under `voices/`, each with local `reference.wav`, `reference.txt`, metadata, notes, source clip details, rename/delete, preview, and Generate-page selection. |
| Voice reference cache | Reference transcript/signature metadata is cached by path/mtime/size/transcript fingerprint, invalidated on changes, and cache hits/misses are recorded in timing metadata. |
| PDF cleanup tools | PDF Clean removes repeated headers/footers conservatively, joins wrapped lines, and offers Raw/Cleaned comparison buttons. |
| Sentence-level highlight units | Metadata schema v2 stores `highlight_units`, and the reader uses sentence-level proportional timing units when available. |
| Professional icon migration | All emoji buttons replaced with qtawesome mdi6 Material Design icons via a central `narracast/ui/icons.py` registry with colour helpers (accent/muted/warn/danger). |
| Voice file browser | Voice Reference page has a Browse button to import any WAV/MP3/FLAC/M4A/OGG/AIFF directly, bypassing the Demucs pipeline. |
| Adjustable cognitive pacing | Auto-pause after paragraph gaps and Study mode (pause on each sentence advance, press Play to continue) are wired into the reading page. |
| Session-level reader launch | Projects page has a Read Session button that opens the first generated chapter in the reading companion and threads a Next chapter control through the rest of the session. |
| M4B audiobook export | `narracast/m4b_export.py` audits chapter readiness, builds FFmetadata chapter blocks, and runs ffmpeg concat + mux. `narracast/ui/m4b_export_dialog.py` provides a chapter audit table, output path picker, skip-missing toggle, and QThread progress. Export M4B button wired into Projects page. 16 backend tests. |

---

## Current Status: 2026-05-13

The core feature set is complete: generation, reading companion, project mode with session tracking, session-level reader launch, and M4B audiobook export. The active UI is fully PySide6 with qtawesome mdi6 icons throughout. Every generated MP3 has a metadata sidecar, plays back with synchronized sentence-level text highlighting, supports bookmarks and resume, and has a focus reading mode. Generated files carry full ID3 tags and can be exported as chapter-marked `.m4b` audiobooks.

Latest verification pass:

- Recursive Python compile passed for app, backend, PySide6 UI, and tests.
- Test suite passed: `185` tests.
- PySide6 offscreen smoke test passed for splash construction, window construction, settings restore, page restore, reader display settings, disabled reader controls, preview wording, and file-drop path detection.
- `ffplay` is available on this machine, so seek/resume playback can use accurate offset playback.

The current UI structure is:

- `app.py`: PySide6 entry point and background F5-TTS model loader.
- `narracast/ui/main_window.py`: `QMainWindow`, sidebar, stacked page shell, settings restore/save.
- `narracast/ui/pages/`: Generate, Queue, Voice Reference, History, Read, Projects, and Help product areas.
- `narracast/ui/benchmark_dialog.py`: PySide6 generation benchmark dialog.
- `narracast/ui/m4b_export_dialog.py`: Chapter audit table, output path picker, QThread export with progress.

The remaining open work falls into two bands:
- **Small/safe** — Queue audio-polish parity is the main open item. Manual session reorder and project import flow are next.
- **Larger / deferred** — Streaming chunk playback, async MP3 finalization (data-gated on timing reports), word-level highlighting, local TTS backend process.

Current review notes:

- All UI buttons use qtawesome mdi6 icons via `narracast/ui/icons.py`. No emoji in button labels.
- Voice Reference Browse button accepts WAV/MP3/FLAC/M4A/OGG/AIFF directly, bypassing Demucs.
- Auto-pause after paragraph and Study mode (sentence-by-sentence with Play to advance) are wired in the reading page.
- Projects page: Read Session opens session chapters in the reader with a Next chapter queue; Export M4B opens the audit dialog and runs ffmpeg export on a background thread.
- Benchmark backend and active PySide6 dialog are wired from the Generate page.
- Speed work already completed: the F5-TTS model is loaded once at app startup, generation runs away from the Qt UI thread, presets tune chunk size and `nfe_step`, final exports avoid per-chunk temp WAV round trips, and the benchmark/timing dialogs report real performance data.
- Audio polish controls are wired into immediate generation: bitrate, normalization, fade in/out, and silence trim are available from the Generate page and recorded in sidecars. Queued jobs currently do not carry these settings yet.
- Reference transcript support is now in place for the active `reference.wav` and named voice profiles. Saved profile transcripts are passed into `tts.infer(ref_text=...)`.
- Reference metadata/transcript caching is in place at the Narracast layer. It does not cache F5-TTS internal tensors or mel features because the public API does not expose a stable hook for that yet.
- Preview caching is implemented in-memory by text/voice/speed/preset plus reference audio path/mtime/size and transcript hash, so voice/reference changes invalidate stale previews.
- Reading display options now include font size, font family, display themes, and spacing. Focus Mode follows the same reader display settings.
- Chunk highlighting now prefers saved `text_start` / `text_end` offsets, and new metadata includes sentence-level `highlight_units` with proportional timing estimates.
- PDF cleanup now has a conservative PDF-specific pipeline and Raw/Cleaned comparison controls in the Generate page.
- Startup splash exists and the 1.8 s fallback is intentional: the main window opens quickly while model loading continues in the background; Generate/Preview stay disabled until ready.
- App bundle logging is documented in README and the matching launcher wrapper source is now stored at `scripts/Narracast.app-launcher.sh`.
- Legacy Tk files have been removed. Active app path is PySide6.

---

## Next Developer Handoff

This is the recommended takeover context for the next developer.

### Stable Baseline

- The active app is PySide6-only. Start at `app.py`, `narracast/ui/main_window.py`, and `narracast/ui/pages/`.
- The backend split is in place: generation, playback, metadata, text cleanup, text splitting, voices, settings, queueing, benchmark, project management, chapter splitting, and M4B export helpers live under `narracast/`.
- The full feature set is working: MP3 generation, sidecar metadata, Read + Play with sentence-aware highlighting, bookmarks, resume, focus mode, auto-pause, study mode, display controls, history, queue, voice reference extraction, named voice profiles, voice file browser, preview, benchmark/timing dialogs, projects, automatic chapter splitting, reading sessions with session-level reader launch, M4B audiobook export, and app-bundle launcher source.
- All UI buttons use qtawesome mdi6 icons via `narracast/ui/icons.py`.
- Current verification: recursive compile passes and `185` tests pass.

### Recommended Next Order

1. **Queue Audio Polish Parity** — small correctness task. Carry `AudioPolishSettings` through `Job`, `add_to_queue()`, retry, and `generate_core(...)`.
2. **Voice Library Polish** — saved voices exist; next polish is editing transcripts directly, persistent preview files, and better empty-state UX.
3. **Async MP3 Finalization** — data-gated. Run real long chapters, open Timing Analysis, check `finalization_s / total_generation_s`. Only proceed if finalization is a meaningful share.
4. **Manual Session Reorder** — drag sessions into a different order; small self-contained UI feature.
5. **Streaming Chunk Playback** — start listening after the first generated chunk; requires chunk-ready event from the generation pipeline.

### Caution Notes

- Raw discovered `clean_voice/**/vocals.wav` entries still do not have transcript metadata unless saved as named voice profiles.
- Preview cache is in memory only. It now includes reference audio/transcript signature, but it is not a persistent disk cache.
- Queue cancellation only cancels pending jobs. Active generation is serialized behind `_tts_lock` and is not interruptible mid-chunk.
- Queued jobs currently preserve text, voice, speed, title, part, preset, and paragraph pause, but not Advanced audio polish settings.
- Normal final MP3 generation no longer writes/reloads temp WAVs per chunk. `infer_chunk()` still writes a temp WAV for direct preview-style uses.
- Tests emit a small Qt font warning about missing `"Sans Serif"`; it does not fail tests, but future UI polish can remove that alias lookup.

### Files To Read First

- `narracast/audio_generation.py` — F5-TTS inference, chunk loop, timing metadata, MP3 export.
- `narracast/voices.py` — voice discovery, named voice profiles, active reference transcript, reference cache/signature.
- `narracast/ui/pages/generate_page.py` — generation UI, preview cache, benchmark and timing-analysis launch.
- `narracast/ui/pages/voice_page.py` — reference clip extraction, transcript entry, saved voice profiles.
- `narracast/ui/pages/reading_page.py` — reader playback controls, highlight offsets, display settings.
- `narracast/metadata.py` — sidecar schema.
- `narracast/timing_analysis.py` — generation timing summaries and async-export recommendations.
- `tests/` — current safety net; add focused tests with every feature.

---

## Open Tasks — Ordered by Difficulty (Lowest → Highest)

---

### Difficulty 2

---

#### Expand Test Coverage

**Status:** Baseline complete; continue adding focused tests with each new feature.

**Description:** Add tests for helper logic, queue behavior, metadata generation, text splitting, and cleanup functions.

**Why it matters:** More tests make future feature work safer and catch regressions early.

**Requirements:**

- Done: Test filename creation edge cases.
- Done: Test chunk splitting for long sentences.
- Done: Test paragraph break behavior.
- Done: Test queue job state changes.
- Done: Test metadata timeline generation.
- Done: Test text cleanup functions.
- Done: Test file loading errors.
- Done: Add tests for playback persistence helpers.
- Done: Add tests for reader highlight selection using duplicate text.
- Done: Add a light PySide6 smoke check for splash/window construction, settings restore, page restore, reader spacing, and file-drop path detection.
- Done: Add tests for reader focus-mode display sync.
- Done: Add tests for voice profile create/load/signature/rename/delete.
- Done: Add tests for reference cache hit/miss behaviour.
- Done: Add tests for PDF cleanup helpers.
- Done: Add tests for sentence-level highlight-unit generation.
- Done: Add tests for timing-analysis recommendations.

**Implementation Notes:**

- Keep UI tests minimal unless needed.
- Focus first on pure functions and backend helpers.
- Add tests as each new feature lands.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 3 | 2 | 1 |

---

#### Generation Benchmark Tool

**Status:** Done.

**Description:** Add a small benchmark button that measures conversion speed for the current Mac and selected voice.

**Why it matters:** TTS performance varies heavily by hardware, model settings, and chunk size. Benchmarking makes speed decisions less guessy and helps users choose the right preset.

**Requirements:**

- Done: Generate a fixed sample text with each preset in `narracast/benchmark.py`.
- Done: Record total time, generated audio duration, real-time factor, average seconds per chunk, and chunk count.
- Done: Show results in a PySide6 dialog launched from the Generate page.
- Do not overwrite normal output history unless the user saves the benchmark audio.

**Implementation Notes:**

- Real-time factor: `generation_time / audio_duration`.
- Example: 10 minutes to generate 5 minutes of audio = 2.0× real time.
- This can guide the default preset on a user's machine.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 4 | 2 | 2 |

---

#### Dyslexia-Friendly Display Options

**Status:** Done for the current scope. Themes, fonts, font size, and spacing now apply to both full-text reading and Focus Mode, and reader display settings persist.

**Description:** Add visual settings that make text easier to track and less tiring to read.

**Why it matters:** Audio helps, but many users still want to follow the text visually. Display control can extend how long that is comfortable.

**Requirements:**

- Done: Line/paragraph spacing controls affect the full-text reader layout.
- Done: High contrast mode.
- Done: Warm background / reduced glare option.
- Done: Font family selection applies to Focus Mode labels.
- Done: Font size selection scales Focus Mode current/previous/next labels.
- Done: Display theme selection applies to Focus Mode background, foreground, muted text, and highlight colours.
- Done: Reader display settings persist in `settings.json`.

**Implementation Notes:**

- Do not hardcode a special font as the only option.
- Store preferences in settings.
- Keep controls simple: Small / Medium / Large / Extra Large may be better than many sliders.
- Full-text font size is already wired; this task should finish focus-mode sync, spacing, and colour persistence.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 5 | 2 | 2 |

---

#### Reader Control and Preview Polish

**Status:** Done.

**Description:** Tighten the PySide6 reader/generator UI now that the migration is active-path complete.

**Why it matters:** The main workflows are in place; this pass removes small inconsistencies that can confuse users, especially when they are tired or context-switching.

**Requirements:**

- Done: Store the reader Stop / Back / Forward / Repeat / Bookmark buttons as instance attributes and disable them until a readable file is loaded.
- Done: Disable `Read + Play` for MP3s without Narracast sidecar metadata and explain that audio-only playback is available.
- Done: Rename preview to "Preview first section".
- Done: Replace dynamic `__import__("PySide6.QtGui", ...)` calls with direct imports.

**Implementation Notes:**

- Keep this as a cleanup pass rather than a redesign.
- This pairs well with the display-options task because both touch `narracast/ui/pages/reading_page.py`.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 3 | 2 | 1 |

---

#### Startup and Bundle Verification Polish

**Status:** Done for current startup policy.

**Description:** Tighten startup behaviour and make the packaged-app diagnostics verifiable from the project tree.

**Why it matters:** Startup is the first trust moment. If the model takes a long time to load, the app should make it clear whether the user can already work or should wait.

**Requirements:**

- Done: Keep the 1.8 s fallback so the main window opens quickly while model loading continues.
- Done: Generate page shows a model-loading state and keeps Generate/Preview disabled until ready.
- Done: Splash status text describes local model loading and first-launch delay.
- Done: Add the app bundle launcher script source to `scripts/Narracast.app-launcher.sh`.

**Implementation Notes:**

- `app.py` already uses a background loader thread and queue polling; this task is mostly UX policy and packaging visibility.
- Keep the fallback if it prevents the app feeling frozen, but make the loading state obvious.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 3 | 2 | 2 |

---

#### F5-TTS Reference Text and Timing Pass

**Status:** Done for active `reference.wav` and saved voice profiles.

**Description:** Remove avoidable F5-TTS overhead by storing exact reference transcripts and adding clearer timing around generation stages.

**Why it matters:** Passing a real reference transcript avoids extra reference-text guessing/transcription work. This is now done for active `reference.wav` and saved voice profiles.

**Requirements:**

- Done: Add `ref_text` to the active voice/reference workflow.
- Done: Store the transcript alongside the active `reference.wav` as `reference.txt`.
- Done: Pass the saved transcript into `tts.infer(ref_text=...)` instead of an empty string.
- Done: Store per-profile `reference.txt` files for saved voices.
- Done: Add timing around chunk split, inference, waveform conversion, assembly, polish, MP3 export, ID3 tags, metadata write, finalization, reference cache hits/misses, and total time.

**Implementation Notes:**

- Raw `clean_voice/**/vocals.wav` entries still have no transcript until saved as named voice profiles.
- This keeps backwards-compatible `reference.wav` support while making saved voices first-class.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 5 | 2 | 2 |

---

#### Preview Speed Mode

**Status:** Done.

**Description:** Make previews intentionally fast rather than a small full-quality export.

**Why it matters:** Preview is where the app should feel instant. It can trade quality for speed without affecting final MP3 export quality.

**Requirements:**

- Done: Rename the current preview to "Preview first section".
- Done: Force preview generation to use the Draft preset regardless of the selected export preset.
- Done: Keep preview paragraph pauses at zero.
- Done: Cache previews by text/voice/speed/preset/reference signature hash so repeated clicks do not regenerate identical audio.
- Done: Include reference audio path/mtime/size and `reference.txt` contents in the preview cache key.
- Consider pre-generating a short voice sample for each voice once the Voice Library exists.

**Implementation Notes:**

- This is a UX speed feature as much as a raw performance feature.
- Keep final export presets separate from preview presets.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 4 | 2 | 2 |

---

#### Reader Highlight Offset Hardening

**Status:** Done.

**Description:** Use metadata `text_start` / `text_end` offsets for full-text highlighting instead of searching for the chunk text.

**Why it matters:** Text search can highlight the wrong occurrence if a chunk appears more than once. The metadata already contains offsets, so the reader should use them.

**Requirements:**

- Done: Use timeline `text_start` and `text_end` to create the highlight cursor.
- Done: Fall back to text search only if offsets are missing or invalid.
- Done: Add a regression test for duplicate text.

**Implementation Notes:**

- This is a correctness hardening task for the already-shipped chunk highlighting feature.
- It should be done before sentence-level highlighting.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 4 | 2 | 2 |

---

#### Queue Audio Polish Parity

**Status:** Open.

**Description:** Make queued generation use the same Advanced audio polish settings as immediate Generate.

**Why it matters:** Users should be able to queue long jobs without losing chosen bitrate, normalization, fade, or trim-silence settings.

**Requirements:**

- Add an `audio_polish` field to `queue_manager.Job`.
- Pass `GeneratePage._current_polish()` into `add_to_queue(...)`.
- Preserve polish settings when retrying failed jobs.
- Pass queued polish settings into `generate_core(..., audio_polish=...)`.
- Add tests proving queued jobs and retried jobs preserve polish settings.

**Implementation Notes:**

- Store an `AudioPolishSettings` instance or plain dict; if using a dict, reconstruct with `AudioPolishSettings.from_dict(...)` before calling `generate_core`.
- Keep the default queue behaviour unchanged when no advanced options are selected.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 3 | 2 | 2 |

---

### Difficulty 3

---

#### Audio Polish Controls

**Status:** Done for immediate generation; queue parity is tracked separately above.

**Description:** Add controls for bitrate, volume normalization, fade in/out, and optional silence trimming.

**Why it matters:** Users generating long-form audio will care about listenability and consistency across files.

**Requirements:**

- Done: MP3 bitrate selector.
- Done: Optional peak normalization.
- Done: Optional fade in/out.
- Done: Optional trim leading/trailing silence.
- Done: Persist polish settings in `settings.json`.
- Done: Store polish settings in sidecar metadata.
- Done: Add backend tests for polish settings, trim, normalization, fade, and combined operations.

**Implementation Notes:**

- `pydub` can handle silence, fades, and gain changes.
- Keep defaults simple.
- Place controls in an Advanced section rather than cluttering the main Generate page.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 4 | 3 | 2 |

---

#### Voice Reference Cache

**Status:** Done for metadata/transcript caching; deeper F5-TTS tensor or mel caching is deferred until the F5-TTS API exposes a stable hook.

**Description:** Cache reusable voice/reference preparation so repeated generations with the same voice do less repeated work.

**Why it matters:** Narracast users will usually reuse the same voice. Reference audio loading, trimming, normalization, transcript/token prep, and any F5-TTS-side reference processing should be paid once where possible.

**Requirements:**

- Done: Introduce a `VoiceProfile` object for saved voices.
- Done: Cache reference metadata by path, audio mtime/size, transcript path, and transcript mtime/size.
- Done: Reuse cached reference text/signature through `prepare_reference(...)`.
- Done: Invalidate cache when the reference WAV or transcript changes.
- Done: Store reference cache hits/misses in generation timing metadata.
- Deferred: Cache tensors or mel features only if F5-TTS exposes a stable and safe hook.

**Implementation Notes:**

- This is intentionally conservative: it avoids inventing private F5-TTS internals.
- Timing data will show whether deeper reference processing is still meaningful.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 4 | 3 | 3 |

---

#### Generation Pipeline and Async Export

**Status:** Partial. Direct waveform conversion and timing analysis are done; async finalization remains open and should be guided by real timing reports.

**Description:** Reduce idle time around generation by overlapping CPU-side work with audio writing/export where it is safe.

**Why it matters:** GPU/model inference should stay serialized, but text cleanup, chunk planning, temporary file handling, audio loading, concatenation, metadata writing, and MP3 export can be profiled and improved.

**Requirements:**

- Keep one F5-TTS inference at a time unless benchmarking proves batching is safe.
- Done: Sidecars include timing for chunk split, inference, waveform conversion, assembly, polish, MP3 export, ID3 tags, metadata write, finalization, reference cache hits/misses, and total time.
- Done: Avoid per-chunk temp WAV write/read loops for normal final MP3 exports.
- Done: Add a PySide6 timing-analysis dialog that summarizes recent sidecars and recommends whether async finalization is worth prototyping.
- Consider writing preview audio as WAV while final exports remain MP3.
- Move final MP3 export/ID3 writing to an async step if it blocks starting the next queued job.

**Implementation Notes:**

- Current final-export flow converts waveform output directly into `AudioSegment`, concatenates, optionally polishes, then exports MP3.
- `infer_chunk()` still writes a temp WAV for direct preview-style uses.
- Do not build async export unless timing reports show finalization is a meaningful share of total time.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 4 | 3 | 3 |

---

#### PDF Cleanup Tools

**Status:** Done for current conservative scope.

**Description:** Improve imported PDF text before generation by removing repeated headers, footers, and broken line wraps beyond what the text cleanup toolbar already handles.

**Why it matters:** Raw PDF extraction often sounds bad when read aloud. The current cleanup panel handles common cases; this adds smarter, PDF-aware passes.

**Requirements:**

- Done: Detect and remove repeated page headers/footers when page breaks are present.
- Done: Join wrapped PDF lines conservatively.
- Done: Add PDF Clean button in the Generate cleanup toolbar.
- Done: Add Raw / Cleaned comparison buttons after cleanup.
- Done: Add tests for repeated headers, line wraps, and combined PDF cleanup.

**Implementation Notes:**

- Keep this conservative. Repeated-line removal intentionally requires page breaks and repeated short lines.
- Future polish could add a modal preview/diff, but the current Raw/Cleaned toggle covers the safe first pass.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 4 | 3 | 3 |

---

#### Sentence-Level Timeline

**Status:** Done for proportional sentence-level estimates.

**Description:** Improve highlighting granularity by tracking sentence-level units inside each TTS chunk.

**Why it matters:** Sentence highlighting feels closer to a Bible app or karaoke-style reading experience than chunk highlighting.

**Requirements:**

- Done: Preserve existing chunk size limits for TTS quality.
- Done: Track sentence offsets inside chunks.
- Done: Estimate sentence timings proportionally within a chunk.
- Done: Store sentence units in sidecar metadata as `highlight_units`.
- Done: Reader uses `highlight_units` when present and falls back to speech chunks for older sidecars.
- Avoid word-level alignment for now.

**Implementation Notes:**

- Current approach: proportional timing based on sentence character length.
- Better future approach: forced alignment using a speech alignment library.
- Keep this optional because useful timing beats perfect timing.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 4 | 3 | 3 |

---

#### Separate Generation Chunks From Highlighting Units

**Status:** Done for sentence-level highlight units.

**Description:** Decouple TTS chunk size from the visual highlighting unit size.

**Why it matters:** Highlighting wants small units, but fast generation wants larger chunks. Tying them together forces a tradeoff that harms both.

**Requirements:**

- Done: Use larger chunks for F5-TTS generation.
- Done: Track smaller sentence ranges for display in `highlight_units`.
- Done: Estimate sentence timing within each generated chunk.
- Done: Metadata schema v2 stores generation timeline and display highlight units separately.
- Future: Allow forced alignment to improve accuracy without replacing the reader model.

**Implementation Notes:**

- Generation chunks remain 500–1200 characters depending on preset.
- Highlighting units are sentence-level.
- Timing is proportional by character count inside each generated chunk.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 5 | 3 | 3 |

---

#### Adjustable Cognitive Pacing

**Status:** Done.

**Description:** Add reading controls that change not just speed, but the rhythm of the listening experience.

**Why it matters:** Neurodivergent users may need slower speech, longer pauses, or repeated sections depending on energy, attention, and processing load.

**Requirements:**

- Done: Sentence pause slider (pause between sentences during generation).
- Done: Auto-pause after each paragraph gap during playback.
- Done: Study mode — pauses when the reader advances to the next sentence; press Play to continue sentence by sentence.

**Implementation Notes:**

- Paragraph pause (generation-time silence) and playback-time auto-pause are kept separate.
- Study mode operates at the reading page level without modifying the generated MP3.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 5 | 3 | 3 |

---

#### Reading Sessions

**Status:** Done.

**Description:** Let users break long material into manageable listening sessions with progress tracking.

**Why it matters:** Long texts can feel impossible as one giant task. Sessions create a clear stopping point and reduce executive-function friction.

**Requirements:**

- Done: Split chapters into estimated-duration sessions automatically when text is imported.
- Done: Show session progress (chapters done / total).
- Done: Mark sessions complete.
- Done: Resume next unfinished session.
- Done: Read Session — open all generated chapters in a session as a queue in the reading companion, advancing automatically with a Next chapter button.
- Future polish: manual session reorder (drag to change session sequence).

**Implementation Notes:**

- Sessions are built per project from chapter word counts and a configurable target duration.
- The reader queue (`load_session`) and `_advance_session` pattern decouples session navigation from file loading.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 4 | 3 | 3 |

---

#### Automatic Chapter Splitting

**Status:** Done.

**Description:** Detect chapters, headings, or custom markers and split pasted/imported text into multiple generation jobs automatically.

**Why it matters:** Long PDFs and books become much easier to convert when the app can divide them for you.

**Requirements:**

- Done: Detect common chapter headings (`Chapter 1`, `CHAPTER I`, `Genesis 1`, Markdown `# headings`).
- Done: Fall back to a single draft chapter when no headings are detected.
- Done: Support custom split markers via the Projects page split-marker field.
- Done: Chapters created as drafts for review before queueing; sessions are rebuilt automatically on import.
- Done: Import from file (`.txt` / `.pdf`) or pasted text.

**Implementation Notes:**

- `narracast/chapter_splitter.py` handles detection; Projects page runs import and rebuilds sessions automatically.
- Review happens inline in the chapter tree before any queueing.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 5 | 3 | 3 |

---

#### Voice Library

**Status:** Done for the core saved-voice workflow; polish remains.

**Description:** Replace the single active `reference.wav` workflow with a proper library of named voices.

**Why it matters:** Users can experiment with different narration voices without overwriting the current reference.

**Requirements:**

- Done: Save named voices.
- Done: Store reference file path, display name, notes, source file, start time, and duration.
- Done: Store exact `ref_text` transcript for each voice so F5-TTS does not need to auto-transcribe reference audio.
- Done: Preview each voice with sample text.
- Done: Select saved voices directly during generation.
- Done: Rename/update notes and delete saved voices.
- Future polish: edit saved transcripts directly, set saved voice as active `reference.wav`, and add persistent preview files.

**Implementation Notes:**

- Uses a `voices/` folder with one subfolder per saved voice.
- Stores `reference.wav`, `reference.txt`, and `metadata.json` per profile.
- Keeps `reference.wav` support for backwards compatibility.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 4 | 3 | 3 |

---

### Difficulty 4

---

#### Project / Book Mode

**Status:** Done.

**Description:** Add a library of projects where each project represents a book, scripture collection, article series, study set, or audiobook.

**Why it matters:** Users working with long texts need organization beyond one-off MP3 files.

**Requirements:**

- Done: Create, edit, and delete projects.
- Done: Store project title, author/source, voice, speed, and notes.
- Done: Add chapters or parts to a project.
- Done: Generate one chapter at a time or queue all drafts at once.
- Done: Show generated status per chapter (draft, queued, generated, error).
- Done: Automatic chapter splitting from pasted text or imported file.
- Done: Reading sessions with progress tracking, complete, resume, and split/merge.
- Done: Read Session — launch session chapters in the reading companion.
- Done: Export M4B — export all generated chapters as a chapter-marked `.m4b` audiobook.

**Implementation Notes:**

- Projects stored as JSON under `projects/`; each has a stable UUID and a list of chapter records.
- Generated files link back to project/chapter IDs in their sidecar metadata.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 5 | 4 | 4 |

---

#### Local TTS Backend Process

**Description:** Move F5-TTS ownership into a persistent local worker process or lightweight localhost service.

**Why it matters:** A separate long-lived backend keeps the GUI simpler, isolates crashes, makes cancellation/queueing cleaner, and creates a path for streaming chunks or future optimized backends.

**Requirements:**

- GUI process sends synthesize jobs to a local worker via multiprocessing queue, local HTTP, or another small IPC layer.
- Worker loads F5-TTS once and owns the model/device.
- Worker owns voice cache and generation queue.
- Support cancellation and progress events.
- Return final file paths and, later, chunk-ready events.

**Implementation Notes:**

- Do not do this before the simpler speed wins unless profiling shows the GUI process is becoming hard to manage.
- Keep the API small enough that the backend can later swap from PyTorch to a faster serving path.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 4 | 4 | 4 |

---

#### Streaming Chunk Playback

**Description:** Start playback after the first generated chunk instead of waiting for the full MP3 export.

**Why it matters:** This may not reduce total conversion time, but it makes long chapters feel much faster because the user can begin listening immediately.

**Requirements:**

- Emit a chunk-ready event as soon as each chunk audio is available.
- Add a playback queue that can play generated chunks in order.
- Continue generating later chunks while earlier chunks are playing.
- Preserve final MP3/sidecar export after all chunks complete.
- Handle cancellation and partial-output cleanup.

**Implementation Notes:**

- Best built after the generation pipeline has clearer stage timings.
- Works especially well with sentence/chunk metadata already stored in sidecars.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 5 | 4 | 4 |

---

#### M4B Audiobook Export

**Status:** Done.

**Description:** Export projects as `.m4b` audiobooks with chapter markers.

**Why it matters:** M4B is better than MP3 for long-form listening because it supports chapters and bookmarking natively in audiobook players.

**Requirements:**

- Done: Audit every chapter for readiness (status, output_path, file existence).
- Done: Read chapter duration from sidecar JSON when available.
- Done: Build FFmetadata string with `[CHAPTER]` blocks and millisecond timestamps.
- Done: Escape `=`, `;`, `\`, and newlines in chapter titles per FFmetadata spec.
- Done: Run ffmpeg concat demuxer to join chapter audio, then mux with chapter metadata into `.m4b`.
- Done: Raise `ValueError` when no chapters are ready, or when `skip_missing=False` and any chapter is not ready.
- Done: `M4BExportDialog` — chapter audit table, output path picker, skip-missing toggle, QThread export with indeterminate progress bar.
- Done: Export M4B button wired in Projects page; enabled when at least one chapter has generated audio.
- Done: 16 backend tests covering audit, FFmetadata generation, timestamp accumulation, escaping, and validation errors.

**Implementation Notes:**

- `narracast/m4b_export.py`: `ChapterExportInfo` dataclass, `audit_project_chapters()`, `build_ffmetadata()`, `export_m4b()`.
- `narracast/ui/m4b_export_dialog.py`: `_ExportWorker(QThread)` + `M4BExportDialog`.
- Individual MP3 files are preserved; the `.m4b` is a new file written to the user-chosen path.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 5 | 4 | 4 |

---

### Difficulty 5 — Deferred

---

#### Word-Level Highlighting

**Description:** Highlight each word exactly as it is spoken.

**Why it is deferred:** F5-TTS does not provide word timestamps directly. This requires forced alignment or speech-to-text alignment after generation.

**Requirements:**

- Generate audio.
- Align generated audio to original text using a forced-alignment library.
- Store word-level timestamps in the sidecar.
- Build smooth UI highlighting without flicker.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 4 | 5 | 5 |

---

#### Mobile Companion App

**Description:** Create an iPhone/Android companion for listening, syncing, and highlighting.

**Why it is deferred:** This is a separate product, not just a feature.

**Ratings:**

| User Value | Difficulty | Risk |
|---:|---:|---:|
| 5 | 5 | 5 |

---

## Product Notes

Narracast should avoid presenting itself only as a productivity app. Its strongest identity may be accessibility-first:

- It helps users read when visual reading is tiring, slippery, or overwhelming.
- It respects privacy by running offline.
- It supports different processing speeds and attention patterns.
- It lets users convert difficult text into something easier to enter through listening.
- It should stay calm, predictable, and low-stimulation by default.

Design principle:

> The app should make returning to text feel easy.

That means future features should be judged not only by power, but by whether they reduce friction for tired, distracted, overwhelmed, or dyslexic users.
