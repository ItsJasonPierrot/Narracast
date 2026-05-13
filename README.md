# Narracast

Narracast turns anything worth reading into something worth hearing — right on your device.

A fully offline native macOS desktop app built with Python and PySide6, powered by F5-TTS.

---

## Development approach

Narracast is an experiment in **multi-AI-agent software development** — building a real, shippable app by orchestrating several specialised AI agents in parallel, each owning a distinct role.

| Role | Agent | Responsibility |
|---|---|---|
| Project lead & orchestrator | **Jason Pierrot** (human) | Overall direction, decision-making, bash scripting, initial voice pipeline setup |
| Tech Lead / Reviewer | Codex agent | Roadmap ownership, architecture decisions, code review |
| Dev agent | Codex | Backend implementation and feature development |
| Dev agent | Claude Code (Anthropic) | Backend implementation and feature development |
| Senior UX Designer | OpenAI agent | Wireframing, UX/UI decisions, visual direction |

Jason set up the project, wrote the initial bash scripts for voice extraction and Demucs processing, and managed every agent — deciding what to build next, reviewing outputs, and keeping the agents aligned on a single coherent product.

The v1.0.0 release was built entirely through this workflow. No single agent owned the whole codebase; the human orchestrator was the only constant thread.

---

## Branding

Narracast uses a green app icon with a stylized **N** mark. The icon appears in:

- the macOS app launcher: `/Applications/Narracast.app`
- the startup loading screen
- the top navigation bar inside the app

```text
assets/Narracast_Icon.png        # in-app header icon
assets/Narracast_Splash_Icon.png # startup loading screen icon
assets/Narracast_App_Icon.png    # source image for the macOS app bundle
```

The macOS launcher uses an `.icns` file generated from the app bundle PNG:

```text
/Applications/Narracast.app/Contents/Resources/Narracast.icns
```

If the Dock or Finder shows an old icon, remove Narracast from the Dock and add it again. macOS caches app icons aggressively.

---

## What it does

Paste any text — a book chapter, article, scripture, notes — and the app generates a spoken MP3 using a cloned voice. Everything runs locally on your Mac. No internet connection needed after setup, no API keys, no subscriptions.

---

## How to launch

Double-click the desktop app:

```bash
/Applications/Narracast.app
```

Or run it from Terminal:

```bash
cd /path/to/Narracast
venv/bin/python3 app.py
```

A native desktop window opens automatically. On startup, Narracast shows a short loading screen, then opens the main window while the F5-TTS model continues loading in the background. Generate and Preview become available once the model is ready.

If the app bundle does not appear when launched from Finder or the Dock, check:

```bash
~/Library/Logs/Narracast.log
```

The launcher writes startup errors there because macOS app bundles do not show a Terminal window.

---

## Setup

Clone the repo and set up a Python 3.11 virtual environment:

```bash
git clone https://github.com/your-username/Narracast.git
cd Narracast
python3.11 -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -e .
```

You will also need `ffmpeg` installed on your system:

```bash
brew install ffmpeg
```

Then launch the app:

```bash
venv/bin/python app.py
# or
venv/bin/python -m narracast
```

---

## Project layout

Narracast uses a standard flat Python application layout:

```text
app.py          # PySide6 entry point
narracast/      # importable application package
narracast/ui/   # PySide6 interface layer
tests/          # unittest suite
scripts/        # release and app-bundle helper scripts
docs/           # developer/release documentation
assets/         # app icons and bundled UI images
pyproject.toml  # package metadata and build configuration
```

This keeps importable code inside the `narracast` package, tests in a dedicated
top-level `tests/` directory, and build/release helpers outside the runtime
package.

---

## Release bundles

Release bundles are built with PyInstaller on each target operating system.
PyInstaller is not a cross-compiler, so build macOS bundles on macOS, Windows
bundles on Windows, and Linux bundles on Linux.

Install build dependencies:

```bash
venv/bin/python -m pip install -e ".[build]"
```

Build the bundle for the current OS:

```bash
venv/bin/python scripts/build_bundle.py
```

See [docs/RELEASE_BUILDS.md](docs/RELEASE_BUILDS.md) for macOS, Windows, and
Linux release steps.

---

## Sections

### Generate Speech

The main production page. Paste your text, set a book title and part number for the filename, choose a voice and speed, then generate.

| Button | What it does |
|---|---|
| **Generate MP3** | Generates immediately — progress bar, elapsed time, chunk count, and ETA update as it works |
| **Queue it** | Adds to the background queue — you can keep adding more while it works |
| **Preview first section** | Generates the first section with Draft settings so you can check the voice before a full export |

You can also upload a `.txt` or `.pdf` file and the text is extracted automatically.

#### Text cleanup toolbar

Raw copied text often contains artefacts from PDFs and e-books. The **Clean:** toolbar sits right below the text area and fixes the most common ones before you generate:

| Button | What it fixes |
|---|---|
| **Spaces** | Collapses extra spaces, tabs, and excessive blank lines |
| **Hyphens** | Rejoins words split by a line-break hyphen (e.g. "some-\nthing" → "something") |
| **Page nos** | Removes standalone page-number lines ("42", "Page 12", "— 12 —") |
| **URLs** | Strips http/www URLs |
| **All** | Applies all four steps at once |
| **PDF clean** | Conservatively removes repeated PDF headers/footers and joins wrapped lines |
| **Raw / Cleaned** | Toggles between the last raw text and cleaned preview |

Each button is non-destructive to the undo history — press Cmd-Z to undo if the result isn't right.

PDF cleanup only removes repeated headers/footers when page breaks are present and the same short line appears across several pages. It is deliberately cautious so book content is not deleted by accident.

#### Paragraph pause

Use the **Paragraph pause** slider to control the length of the silence inserted between paragraphs. Default is 0.5 s. Slide to 0 for no gap, up to 2 s for a longer breathing space between sections. The chosen value is stored in the sidecar `.json` so it can be referenced later.

Use **Sentence pause** when you want extra generated silence between sentences. It is off by default because it creates smaller sentence-level generation units, which can be slower, but it gives more deliberate pacing for study or tired listening.

For full chapters or long essays, use **Queue it**. It runs in the background and keeps the app responsive.

### Generation modes

| Mode | Chunk size | F5 steps | Best for |
|---|---:|---:|---|
| Best | 500 | 32 | Highest quality, shorter or sensitive material |
| Balanced | 750 | 32 | Default long-form generation |
| Fast | 1000 | 24 | Chapters and longer articles |
| Draft | 1200 | 16 | Quick rough copies and review |

Larger chunks reduce the number of F5-TTS calls. Lower F5 steps reduce model work. Both can speed up generation, with some possible quality tradeoff.

Use **Run benchmark** in the Generate page's System card to test all presets on your Mac. The benchmark reports chunk count, generation time, generated audio duration, and real-time factor.

Use **Analyze timings** after a few real exports to inspect recent sidecar timing data and see where time is being spent across inference, assembly, and export stages.

Preview generation intentionally uses Draft settings and caches repeated identical previews by text, voice, speed, and preset so repeated checks do not redo the same work.

### Progress feedback

- **Startup** — a short loading screen appears, then the main window opens while the F5-TTS model finishes loading. Generate and Preview unlock when ready.
- **Generation** — the Generate page shows a progress bar, current chunk, elapsed time, and estimated time remaining.
- **Queue jobs** — the Queue page updates every 2 seconds with each job's status and progress.

### MP3 tags

Every generated file is tagged automatically with ID3 metadata:

- **Title** — book title and part (e.g. "The Conquest of Bread — Part 1")
- **Album** — book title
- **Track number** — part/chapter number
- **Artist** — the voice name used for cloning

### Metadata sidecars

Every generated MP3 also gets a matching `.json` file beside it. The sidecar stores the original text, title, part, voice, speed, generation preset, paragraph pause, generation chunk timeline, sentence-level highlight units, text offsets, audio timings, generation-stage timings, last playback position, and bookmarks.

```text
Conquest-of-Bread_Part-1_2026-05-08_14-32-01.mp3
Conquest-of-Bread_Part-1_2026-05-08_14-32-01.json
```

### Read (reading companion)

Select any generated file in History and click **Read + Play** to open it in the reading view. Narracast will start playing the audio and highlight each sentence as it is spoken. Older files without sentence highlight metadata fall back to chunk-level highlighting.

#### Playback controls

| Button | What it does |
|---|---|
| **Play / Resume** | Start playback, or resume from where you stopped |
| **Stop** | Stop and save your position — the app remembers where you left off |
| **-10s** | Jump back 10 seconds |
| **+10s** | Jump forward 10 seconds |
| **Repeat** | Restart the current chunk from the beginning |

The last playback position is automatically saved when you stop or close the app.

#### Bookmarks

Save any position while the audio is playing:

1. Click **Add here** — a bookmark is saved at the current position.
2. The bookmark appears in the dropdown next to the button.
3. Select a bookmark and click **Jump** to seek to it instantly.
4. Click **Delete** to remove a selected bookmark.

Bookmarks are saved in the sidecar `.json` file and persist between sessions.

#### Focus Mode

Click **Focus Mode** to switch from the full-text scrolling view to a focused three-chunk layout:

- The **previous chunk** appears above in muted grey.
- The **current chunk** is shown large, front-and-centre, with a green highlight.
- The **next chunk** appears below in muted grey.

Use the **S / M / L / XL** size buttons to adjust the text size to whatever feels comfortable.

The reader also includes display controls for theme, font, and spacing. These apply to both full-text reading and Focus Mode, and persist in `settings.json`.

#### Cognitive pacing

- **Pause after paragraph** pauses when playback reaches a paragraph gap, so you can breathe before continuing.
- **Study mode** pauses when the reader advances to the next sentence; press Play to continue sentence by sentence.

These playback controls do not modify the MP3. Sentence pause on the Generate page is the generated-audio pacing option.

### Queue

Shows all queued and in-progress jobs. Refreshes every 2 seconds automatically. Jobs run one at a time in the background — add as many as you like and come back when they're done.

### Voice Reference

Swap the voice the app clones. Pick a source audio file, set a start time and duration, paste the exact transcript spoken in the clip, then preview it.

You can **Browse…** to import any WAV, MP3, FLAC, M4A, OGG, or AIFF file directly — you do not need to go through the Demucs pipeline first.

You can save the clip two ways:

- **Save as reference.wav** — updates the active reference voice immediately.
- **Save named voice** — stores a reusable voice profile under `voices/` with its own `reference.wav`, `reference.txt`, and `metadata.json`.

Saved voices appear in the Generate voice selector immediately. Each saved transcript is passed into F5-TTS as `ref_text`, so generation can avoid unnecessary reference-text guessing.

The saved voice library also lets you:

- rename a saved voice and update its notes
- delete a saved voice profile
- set a saved voice as the active reference
- generate a short sample preview from saved profile audio and transcript

### History

Lists all generated MP3s, newest first, with file sizes. Select any file to **Play (audio only)** for simple playback, or click **Read + Play** to open it in the full reading view with highlighting, bookmarks, and focus mode.

### Projects

Organise long texts into projects. Each project holds a list of chapters, each with its own text, voice, and status (draft, queued, generated, or error). Queue one chapter or all drafts at once. Projects also support:

- **Automatic chapter splitting** — paste a long text and let the app detect headings and split into draft chapters for review before queueing.
- **Reading sessions** — break chapters into manageable estimated-duration sessions with progress tracking.
- **Read Session** — open the first generated chapter in a session directly in the reading companion; a Next chapter button advances through the rest of the session without leaving the reader.
- **Export M4B** — combine all generated chapters into a single `.m4b` audiobook file with native chapter markers, ready for any audiobook player. A chapter audit table shows readiness before export; chapters without audio can be skipped or blocked depending on your choice.

### Help

Quick reference guide built into the app.

---

## What's Next

The core feature set — generation, reading companion, project mode, session tracking, and M4B export — is complete. Active development is focused on:

### Near-term polish
- **Queue audio polish parity** — carry Advanced audio polish settings (bitrate, normalization, fade, trim) through queued jobs, not just immediate generation
- **Manual session reorder** — drag sessions into a different order within a project
- **Project import flow** — import an existing folder of MP3s as a project

### Larger features
- **Streaming chunk playback** — start listening after the first generated chunk instead of waiting for the full export
- **Async MP3 finalization** — data-gated: run real long-chapter generations and check the Timing Analysis dialog; only worth building if finalization is a meaningful share of total time

### Deferred / research
- **Word-level highlighting** — per-word karaoke-style sync using forced speech alignment
- **Local TTS backend process** — move the model into a persistent worker process for cleaner cancellation and future streaming
- **Mobile companion** — iPhone/Android app for listening, syncing, and bookmarks

---

## File naming

Files are saved to the `output/` folder and named automatically:

```
Conquest-of-Bread_Part-1_2026-05-08_14-32-01.mp3
```

If you leave the title fields blank, the first five words of the text are used instead.

---

## Folder structure

```
Narracast/
├── assets/
│   ├── Narracast_Icon.png           — in-app header icon
│   ├── Narracast_Splash_Icon.png    — splash screen icon
│   ├── Narracast_App_Icon.png       — app bundle icon source
│   └── Narracast.icns               — generated macOS app icon
├── app.py                           — PySide6 launcher and background model loader
├── reference.txt                    — transcript for the active reference voice clip
├── voices/                          — named voice profiles (audio, transcript, metadata)
├── projects/                        — project JSON files
├── narracast/                       — backend package
│   ├── paths.py                     — project-relative paths
│   ├── presets.py                   — generation speed/quality presets
│   ├── text_splitter.py             — chunking and paragraph break handling
│   ├── audio_generation.py          — F5-TTS inference and MP3 assembly
│   ├── text_cleanup.py              — regex-based text pre-processing helpers
│   ├── metadata.py                  — JSON sidecar files for generated MP3s
│   ├── queue_manager.py             — background queue and job state
│   ├── voices.py                    — voice/reference file helpers
│   ├── projects.py                  — project and chapter management
│   ├── chapter_splitter.py          — automatic chapter detection and splitting
│   ├── output_files.py              — filenames, history, and file loading
│   ├── settings.py                  — local user preferences
│   ├── playback.py                  — audio playback, position tracking, bookmarks
│   ├── benchmark.py                 — local preset speed benchmark helper
│   ├── m4b_export.py                — chapter audit, FFmetadata builder, ffmpeg M4B export
│   └── ui/
│       ├── main_window.py           — QMainWindow shell, sidebar, stacked pages
│       ├── benchmark_dialog.py      — PySide6 benchmark results dialog
│       ├── m4b_export_dialog.py     — M4B export dialog with audit table and progress
│       ├── sidebar.py               — left navigation and system status
│       ├── theme.py                 — PySide6 dark/light app stylesheet
│       ├── icons.py                 — centralised qtawesome/mdi6 icon registry
│       ├── widgets.py               — reusable card, label, chip, and status widgets
│       ├── signals.py               — Qt signal bus for background work
│       └── pages/
│           ├── generate_page.py     — Generate Speech production page
│           ├── queue_page.py        — background queue monitor
│           ├── voice_page.py        — Voice Reference extraction page
│           ├── history_page.py      — generated audio library
│           ├── reading_page.py      — Read mode with highlighting and focus
│           ├── projects_page.py     — Project / Book mode
│           └── help_page.py         — Help Center
├── reference.wav                    — the active voice clip used for cloning
├── README.md                        — this file
├── requirements.txt                 — Python package list
├── tests/                           — lightweight backend helper tests
├── scripts/
│   └── Narracast.app-launcher.sh    — source copy of the macOS app bundle launcher
├── venv/                            — Python 3.11 virtual environment
├── raw_audio/                       — original downloaded audio files
├── clean_voice/                     — Demucs-separated narrator vocals
└── output/                          — generated MP3s saved here
```

---

## Tech stack

| Tool | Role |
|---|---|
| Python 3.11 | Language |
| F5-TTS | Voice cloning and speech synthesis |
| PyTorch (MPS) | AI inference backend (Apple Silicon) |
| PySide6 / Qt | Native desktop UI, sidebar navigation, stacked pages |
| qtawesome | Material Design icon library (mdi6) for all UI buttons |
| pydub | Joining and exporting audio chunks |
| soundfile | Writing intermediate WAV files |
| pdfminer.six | Extracting text from PDF uploads |
| mutagen | Writing ID3 tags to generated MP3 files |
| ffmpeg | Voice reference clip extraction and M4B audiobook export |

---

## Speed setting

| Value | Effect |
|---|---|
| 0.5 | Half speed — very slow, good for study |
| 1.0 | Normal (default) |
| 1.5 | 50% faster — good for familiar material |
| 2.0 | Double speed |

---

## Transferring MP3s to your phone

- **AirDrop** — open Finder, navigate to the `output/` folder, right-click a file → Share → AirDrop
- **USB** — connect your phone and drag files across in Finder

---

## Requirements

- macOS (Apple Silicon recommended — uses MPS for fast inference)
- Python 3.11
- ffmpeg (`brew install ffmpeg`)
- All Python packages listed in `requirements.txt`

Install Python packages with:

```bash
venv/bin/pip install -r requirements.txt
```

Run the lightweight helper tests with:

```bash
venv/bin/python3 -m unittest discover -s tests
```
