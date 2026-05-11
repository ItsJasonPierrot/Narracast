# Narracast

Narracast turns anything worth reading into something worth hearing — right on your device.

A fully offline native macOS desktop app built with Python and PySide6, powered by F5-TTS.

---

## Branding

Narracast uses a green app icon with a stylized **N** mark. The icon appears in:

- the macOS app launcher: `/Applications/Narracast.app`
- the startup loading screen
- the top navigation/header bar inside the app

Narracast keeps separate icon assets for each use:

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

Paste any text — a book chapter, article, scripture, notes — and the app generates a spoken MP3 using a cloned voice (David Suchet reading the NIV Bible). Everything runs locally on your Mac. No internet connection needed after setup, no API keys, no subscriptions.

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
venv/bin/pip install -r requirements.txt
```

You will also need `ffmpeg` installed on your system:

```bash
brew install ffmpeg
```

Then launch the app:

```bash
venv/bin/python3 app.py
```

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
| **⎵ Spaces** | Collapses extra spaces, tabs, and excessive blank lines |
| **⟐ Hyphens** | Rejoins words split by a line-break hyphen (e.g. "some-\nthing" → "something") |
| **# Page nos** | Removes standalone page-number lines ("42", "Page 12", "— 12 —") |
| **🔗 URLs** | Strips http/www URLs |
| **✨ All** | Applies all four steps at once |
| **📄 PDF clean** | Conservatively removes repeated PDF headers/footers and joins wrapped lines |
| **Raw / Cleaned** | Toggles between the last raw text and cleaned preview |

Each button is non-destructive to the undo history — press Ctrl-Z / Cmd-Z to undo if the result isn't right.

PDF cleanup only removes repeated headers/footers when page breaks are present and the same short line appears across several pages. It is deliberately cautious so book content is not deleted by accident.

#### Paragraph pause

Use the **Paragraph pause** slider to control the length of the silence inserted between paragraphs. Default is 0.5 s. Slide to 0 for no gap, up to 2 s for a longer breathing space between sections. The chosen value is stored in the sidecar `.json` so it can be referenced later.

Use **Sentence pause** when you want extra generated silence between sentences. It is off by default because it creates smaller sentence-level generation units, which can be slower, but it gives more deliberate pacing for study or tired listening.

For full chapters or long essays, use **Queue it**. It runs in the background and keeps the app responsive.

### Generation modes
Generation mode controls the speed/quality tradeoff.

| Mode | Chunk size | F5 steps | Best for |
|---|---:|---:|---|
| Best | 500 | 32 | Highest quality, shorter or sensitive material |
| Balanced | 750 | 32 | Default long-form generation |
| Fast | 1000 | 24 | Chapters and longer articles |
| Draft | 1200 | 16 | Quick rough copies and review |

Larger chunks reduce the number of F5-TTS calls. Lower F5 steps reduce model work. Both can speed up generation, with some possible quality tradeoff.

Use **Run benchmark** in the Generate page's System card to test all presets on your Mac. The benchmark reports chunk count, generation time, generated audio duration, and real-time factor so you can choose the best speed/quality mode without guessing.

Use **Analyze timings** after a few real exports to inspect recent sidecar timing data. It shows how much time was spent in inference, waveform conversion, assembly, MP3 export, ID3 tagging, and metadata writing, then recommends whether async finalization is worth prototyping.

Preview generation intentionally uses Draft settings and caches repeated identical previews by text, voice, speed, and preset so repeated checks do not redo the same work.

### Progress feedback
Narracast gives feedback at two slow points:

- **Startup** — a short loading screen appears, then the main window opens while the F5-TTS model finishes loading. Generate and Preview unlock when ready.
- **Generation** — the Generate page shows a progress bar, current chunk, elapsed time, and estimated time remaining.
- **Queue jobs** — the Queue page updates every 2 seconds with each job's status and progress.

### MP3 tags
Every generated file is tagged automatically with ID3 metadata so it appears correctly in music apps, podcast players, and on your phone:

- **Title** — book title and part (e.g. "The Conquest of Bread — Part 1")
- **Album** — book title
- **Track number** — part/chapter number
- **Artist** — the voice name used for cloning

### Metadata sidecars
Every generated MP3 also gets a matching `.json` file beside it. The sidecar stores the original text, title, part, voice, speed, generation preset, paragraph pause, generation chunk timeline, sentence-level highlight units, text offsets, audio timings, generation-stage timings, last playback position, and bookmarks.

Generation chunks stay large for F5-TTS quality and speed. Reading highlights use smaller sentence-level units estimated proportionally inside each generated chunk, so the reader can track text more precisely without slowing generation down.

Generation timings include model inference, waveform conversion, assembly, audio polish, MP3 export, ID3 tags, metadata write, finalize time, reference cache hits/misses, and total time. Normal generation converts F5-TTS waveform output directly into audio segments, so per-chunk temporary WAV writing is avoided for final MP3 exports.

```text
Conquest-of-Bread_Part-1_2026-05-08_14-32-01.mp3
Conquest-of-Bread_Part-1_2026-05-08_14-32-01.json
```

### 📖 Read (reading companion)

Select any generated file in History and click **📖 Read + Play** to open it in the reading view. Narracast will start playing the audio and highlight each sentence as it's spoken. Older files without sentence highlight metadata fall back to chunk-level highlighting.

#### Playback controls

| Button | What it does |
|---|---|
| **▶ Play / Resume** | Start playback, or resume from where you stopped |
| **■ Stop** | Stop and save your position — the app remembers where you left off |
| **◀ –10s** | Jump back 10 seconds |
| **▶ +10s** | Jump forward 10 seconds |
| **↺ Repeat** | Restart the current chunk from the beginning |

The last playback position is automatically saved when you stop or close the app, so **Resume** picks up exactly where you left off.

#### Bookmarks

Save any position with a name while the audio is playing:

1. Click **🔖 Add here** and type a short label (e.g. "Chapter 2 start").
2. The bookmark appears in the dropdown next to the button.
3. Select a bookmark and click **⤶ Jump** to seek to it instantly.
4. Click **✕ Delete** to remove a selected bookmark.

Bookmarks are saved in the sidecar `.json` file and persist between sessions.

#### Focus Mode

Click **🔍 Focus Mode** to switch from the full-text scrolling view to a focused three-chunk layout:

- The **previous chunk** appears above in muted grey.
- The **current chunk** is shown large, front-and-centre, with a green highlight.
- The **next chunk** appears below in muted grey.

Use the **S / M / L / XL** size buttons to adjust the text size of the current chunk to whatever feels comfortable. Click **📄 Full Text** to switch back to the scrolling view at any time.

The reader also includes display controls for theme, font, and spacing. These settings apply to both full-text reading and Focus Mode, and spacing changes the full-text reader's line height and paragraph breathing room.

#### Cognitive pacing

The Read page has playback-only pacing controls:

- **Pause after paragraph** pauses when playback reaches a paragraph gap, so you can breathe before continuing.
- **Study mode** pauses when the reader advances to the next sentence; press Play to continue sentence by sentence.

These playback controls do not modify the MP3. Sentence pause on the Generate page is the generated-audio pacing option.

### Queue
Shows all queued and in-progress jobs. Refreshes every 2 seconds automatically.
Jobs run one at a time in the background — add as many as you like and come back when they're done.

### Voice Reference
Swap the voice the app clones. Pick a cleaned audio track from your `clean_voice` folder, set a start time and duration, paste the exact transcript spoken in the clip, then preview it.

You can save the clip two ways:

- **Save as reference.wav** updates the active backward-compatible reference voice.
- **Save named voice** stores a reusable voice profile under `voices/` with its own `reference.wav`, `reference.txt`, and `metadata.json`.

Saved voices appear in the Generate voice selector immediately. Each saved transcript is passed into F5-TTS as `ref_text`, so generation can avoid unnecessary reference-text guessing.

Narracast caches reference metadata and transcripts by audio/transcript file state, so repeated chunks using the same saved voice do not keep rereading the same reference text from disk. If the reference audio or transcript changes, the cache invalidates automatically.

The saved voice library also lets you:

- rename a saved voice and update its notes
- delete a saved voice profile
- generate a short sample preview from saved profile audio and transcript

### History
Lists all generated MP3s, newest first, with file sizes. Select any file to **▶ Play (audio only)** for simple playback, or click **📖 Read + Play** to open it in the full reading view with highlighting, bookmarks, and focus mode. Use the Clear History button (with confirmation) to delete everything in the output folder.

### Help
Quick reference guide built into the app.

---

## What's Next

Narracast is under active development. Planned features, roughly in order of priority:

### Near-term
- **Queue audio polish parity** — advanced audio settings (bitrate, normalization, fade, silence trim) carried through queued and retried jobs, not just immediate generation
- **Voice Library polish** — edit saved voice transcripts in place, set a saved voice as the active reference, and persistent sample previews per profile

### Medium-term
- **Automatic chapter splitting** — detect chapter headings, section markers, or Markdown headings in pasted or imported text and split them into separate generation jobs automatically, with a review step before queueing
- **Reading sessions** — break long material into manageable listening sessions with estimated durations and progress tracking, reducing executive-function friction for long books

### Larger features
- **Project / Book mode** — a library of projects, each with chapters or parts, batch generation, and per-project settings (voice, speed, notes)
- **Streaming chunk playback** — start listening after the first generated chunk instead of waiting for the full export
- **M4B audiobook export** — combine chapters into a single `.m4b` file with native chapter markers for audiobook players

### Deferred / research
- **Word-level highlighting** — per-word karaoke-style sync using forced speech alignment
- **Mobile companion** — iPhone/Android app for listening, syncing, and bookmarks

---

## File naming

Files are saved to the `output/` folder inside the project directory and named automatically:

```
Conquest-of-Bread_Part-1_2026-05-08_14-32-01.mp3
```

If you leave the title fields blank, the first five words of the text are used instead.

---

## Folder structure

```
Narracast/
├── assets/
│   ├── Narracast_Icon.png — in-app header icon
│   ├── Narracast_Splash_Icon.png — splash screen icon
│   ├── Narracast_App_Icon.png — app bundle icon source
│   └── Narracast.icns — generated macOS app icon
├── app.py              — PySide6 launcher and background model loader
├── reference.txt       — transcript for the active reference voice clip
├── voices/             — named voice profiles, each with audio, transcript, and metadata
├── narracast/          — backend package
│   ├── paths.py        — project-relative paths
│   ├── presets.py      — generation speed/quality presets
│   ├── text_splitter.py — chunking and paragraph break handling
│   ├── audio_generation.py — F5-TTS inference and MP3 assembly
│   ├── text_cleanup.py — regex-based text pre-processing helpers
│   ├── metadata.py     — JSON sidecar files for generated MP3s
│   ├── queue_manager.py — background queue and job state
│   ├── voices.py       — voice/reference file helpers
│   ├── output_files.py — filenames, history, and file loading
│   ├── settings.py     — local user preferences
│   ├── playback.py     — audio playback, position tracking, bookmarks
│   ├── benchmark.py    — local preset speed benchmark helper
│   └── ui/
│       ├── main_window.py — QMainWindow shell, sidebar, stacked pages
│       ├── benchmark_dialog.py — PySide6 benchmark results dialog
│       ├── sidebar.py — left navigation and system status
│       ├── theme.py — PySide6 dark/light app stylesheet
│       ├── widgets.py — reusable card, label, chip, and status widgets
│       ├── signals.py — Qt signal bus for background work
│       └── pages/
│           ├── generate_page.py — Generate Speech production page
│           ├── queue_page.py — background queue monitor
│           ├── voice_page.py — Voice Reference extraction page
│           ├── history_page.py — generated audio library
│           ├── reading_page.py — Read mode with highlighting/focus
│           └── help_page.py — Help Center
├── reference.wav       — the 12-second voice clip used for cloning
├── README.md           — this file
├── requirements.txt    — Python package list
├── tests/              — lightweight backend helper tests
├── scripts/
│   └── Narracast.app-launcher.sh — source copy of the macOS app bundle launcher
├── venv/               — Python 3.11 virtual environment
├── raw_audio/          — original downloaded audio files
├── clean_voice/        — Demucs-separated narrator vocals (.wav files)
└── output/             — generated MP3s saved here
```

The app finds `clean_voice/`, `voices/`, `reference.wav`, and `output/` relative to `app.py`, so the project folder can be moved without editing hardcoded paths.

Narracast also writes a local `settings.json` file beside the app. It remembers small workflow preferences like voice, speed, generation mode, title, part, paragraph pause, app theme, last page, reader display settings, and window size. It does **not** save the pasted text.

---

## Tech stack

| Tool | Role |
|---|---|
| Python 3.11 | Language |
| F5-TTS | Voice cloning and speech synthesis |
| PyTorch (MPS) | AI inference backend (Apple Silicon) |
| PySide6 / Qt | Native desktop UI, sidebar navigation, stacked pages |
| pydub | Joining and exporting audio chunks |
| soundfile | Writing intermediate .wav files |
| pdfminer.six | Extracting text from PDF uploads |
| mutagen | Writing ID3 tags to generated MP3 files |
| ffmpeg | Extracting voice reference clips |

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

- **AirDrop** — open Finder, navigate to the `output/` folder inside the project, right-click a file → Share → AirDrop
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
