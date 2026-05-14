# Narracast User Guide

A complete walkthrough of the desktop app — from first launch to transferring audio to your iPhone.

---

## First launch

Open the app:

```bash
# From source
venv/bin/python app.py

# Or from the app bundle
open /Applications/Narracast.app
```

A splash screen appears while the app initialises. The main window opens immediately after — you can browse all pages straight away. The status bar at the bottom reads **"All systems offline"** while the F5-TTS model loads in the background. Once it shows **"Ready · Apple GPU (MPS)"**, generation and preview are unlocked.

If the bundle fails to open from Finder or the Dock, check the launch log:

```bash
cat ~/Library/Logs/Narracast.log
```

---

## Step 1 — Set up a voice

Every piece of generated audio uses a cloned voice. You need at least one voice reference before you can generate anything.

Navigate to **Voice** in the sidebar.

### Option A — Browse a file directly (recommended)

1. Click **Browse…** and pick any WAV, MP3, M4A, FLAC, OGG, or AIFF file.
2. The app loads the file without going through any external pipeline.
3. Paste the **exact words** spoken in the clip into the transcript box — F5-TTS uses this to avoid re-transcribing.
4. Click **Preview** to hear a short sample with the current settings.
5. Click **Save named voice**, give it a name, and it is stored permanently in your app-data folder.

### Option B — Extract from a longer file

1. Enter a **Start time** and **Duration** to isolate the section you want.
2. Paste the transcript for that section.
3. Save as above.

### Tips for a good reference clip

- 10–30 seconds of clean, uninterrupted speech works best.
- Background music, reverb, or compression artefacts reduce quality.
- The transcript must match the clip exactly — every word, every pause marker.

Saved voices appear in the voice selector on the Generate page immediately. You can rename, edit the transcript, preview, or delete them at any time from the Voice page.

---

## Step 2 — Generate audio

Navigate to **Generate** in the sidebar.

### Basic workflow

1. Paste your text into the main text area, or drag in a `.txt` or `.pdf` file.
2. Run the **Clean:** toolbar to strip common artefacts:
   - **Spaces** — collapses extra whitespace and blank lines
   - **Hyphens** — rejoins words split by a line-break hyphen (`some-\nthing` → `something`)
   - **Page nos** — removes standalone page-number lines
   - **URLs** — strips http/www addresses
   - **All** — applies all four at once
   - **PDF clean** — removes repeated headers/footers and joins wrapped lines
   - **Raw / Cleaned** toggle — compare before and after; press Cmd-Z to undo
3. Enter a **Title** and **Part** — used for the filename and MP3 ID3 tags.
4. Choose your saved voice and a **Speed** (1.0 is normal; 0.5 is half speed; 1.5 is 50% faster).
5. Pick a **Preset**:

   | Preset | Chunk size | F5 steps | Best for |
   |--------|----------:|:--------:|----------|
   | Best | 500 chars | 32 | Short or sensitive material |
   | Balanced | 750 chars | 32 | Default for books and articles |
   | Fast | 1000 chars | 24 | Chapters and longer articles |
   | Draft | 1200 chars | 16 | Quick rough copies and review |

6. Click **Generate MP3**.

Audio starts playing through your speakers after the first synthesised chunk — you do not wait for the full file. The progress bar, chunk count, elapsed time, and ETA update in real time. The final MP3 and a matching sidecar `.json` are saved to your output folder when all chunks complete.

### Paragraph and sentence pauses

- **Paragraph pause** (slider, 0–2 s) — silence inserted between paragraphs in the generated audio. Default 0.5 s.
- **Sentence pause** — when enabled, generates extra silence between each sentence. Off by default; useful for study or slow-paced listening.

### Queuing long jobs

For chapters or anything over a few minutes, use **Queue it** instead of Generate MP3. Jobs run one at a time in the background; you can keep adding more and come back when they are done. Monitor progress on the **Queue** page.

### Preview before generating

**Preview first section** generates the first section using Draft settings (fast, no pauses) and caches the result. Use it to audition a voice before committing to a full export.

### Benchmark and timing tools

- **Run benchmark** — tests all four presets against a short sample on your Mac and reports the real-time factor for each.
- **Analyze timings** — summarises recent generation stage timings from your sidecar files.

---

## Step 3 — Read along

Navigate to **History**, select a generated file, and click **Read + Play**.

The reader opens, starts playback, and highlights each sentence as it is spoken. Older files without sentence metadata fall back to chunk-level highlighting.

### Playback controls

| Control | Action |
|---------|--------|
| Play / Resume | Start or continue playback |
| Stop | Pause and save your position |
| –10 s | Jump back 10 seconds |
| +10 s | Jump forward 10 seconds |
| Repeat | Restart the current chunk |

Your position is saved automatically when you stop or close the app. Reopening the file resumes exactly where you left off.

### Bookmarks

1. Click **Add here** — a bookmark is saved at the current playback position.
2. Select a bookmark from the dropdown and click **Jump** to seek to it instantly.
3. Click **Delete** to remove a selected bookmark.

Bookmarks are stored in the sidecar `.json` and persist between sessions.

### Display settings

| Setting | Options |
|---------|---------|
| Theme | Dark · Light · High contrast · Warm |
| Font family | System default or serif |
| Font size | S · M · L · XL |
| Line spacing | Slider |
| Paragraph spacing | Slider |

All display settings apply to both the full-text view and Focus Mode, and persist in `settings.json`.

### Focus Mode

Click **Focus Mode** to switch to a three-line centred layout:

- **Previous chunk** — muted, above
- **Current chunk** — large, highlighted in green
- **Next chunk** — muted, below

### Cognitive pacing modes

- **Pause after paragraph** — playback pauses at each paragraph gap so you can breathe before continuing.
- **Study mode** — playback pauses after every sentence advance. Press Play to move to the next sentence. Useful for dense material or language learning.

---

## Step 4 — Projects (books and multi-chapter texts)

Use **Projects** when you have more than one chapter, or when you want to manage a long text as a structured book.

### Create a project

1. Click **Projects** → **New project** and give it a name.
2. Open the project and paste your full text into the import panel, or import a file.
3. Click **Split into chapters** — the app detects headings and creates draft chapters automatically. Review and edit them before queueing.

### Generate chapters

- **Queue all drafts** — adds every draft chapter to the background queue at once.
- Individual chapters can be queued, re-queued, or cancelled from the chapter list.

### Reading sessions

Once chapters are generated, break them into sessions:

1. Click **Split into sessions** and set an estimated duration per session (e.g. 30 minutes).
2. Sessions appear in a list with progress tracking and a **Mark complete** button.
3. Drag sessions up or down to reorder them — chapter membership is unchanged.
4. Click **Read Session** to open all chapters in a session as a queue in the reader. The **Next chapter** button advances without leaving the reader.

### M4B audiobook export

When all chapters are generated:

1. Click **Export M4B**.
2. A chapter audit table shows readiness. Toggle **Skip missing** if you want to export with gaps, or block the export until all chapters are present.
3. Click **Export** — ffmpeg concatenates the chapters and writes a `.m4b` file with native chapter markers, ready for any audiobook player.

### Import existing MP3 folder

If you have audio already generated outside the app:

1. Click **Import MP3 folder** and select the folder.
2. Files are imported in natural sort order. Sidecar-aware files are linked automatically; files without sidecars get draft stubs.

---

## Step 5 — Transfer to iPhone

Navigate to **Transfer** in the sidebar.

The server starts automatically when you open the page. It shows a URL like:

```
http://192.168.1.42:8765
```

Your Mac and iPhone must be on the same WiFi network.

### Using Safari on iPhone (available now)

1. Copy the URL and open it in Safari on your iPhone.
2. Navigate to `/api/files` to see a JSON list of all available files.
3. Open `/api/audio/filename.mp3` to stream or download an MP3.
4. Open `/api/metadata/filename.mp3` to download the sidecar JSON (text, timeline, bookmarks).

### Using the Narracast iOS app (coming soon)

The iOS companion app will connect to this server automatically, list your files, play audio with synchronized text highlighting, and sync reading position and bookmarks back to the Mac.

### API reference (for developers)

| Endpoint | Response |
|----------|----------|
| `GET /api/info` | `{"server": "narracast", "schema_version": 2}` |
| `GET /api/files` | JSON array of file descriptors |
| `GET /api/audio/<filename>` | MP3 binary; supports `Range` for seeking |
| `GET /api/metadata/<filename>` | Sidecar JSON (accepts `.mp3` or `.json` extension) |

The server stops when you quit Narracast.

---

## Local data

All runtime data is kept separate from the app source code:

```
~/Library/Application Support/Narracast/
├── output/          — generated MP3s and sidecar .json files
├── voices/          — saved voice profiles (reference audio, transcript, metadata)
├── projects/        — project and chapter data
└── settings.json    — display preferences, last page, window geometry
```

Set `NARRACAST_DATA_DIR=/path/to/data` to override this location (useful for development or portable installs).

Sidecar `.json` files may contain the source text, timing data, bookmarks, and reading position. Everything stays on your machine — nothing is sent anywhere.

---

## Keyboard shortcuts and tips

- **Cmd-Z** — undo text cleanup on the Generate page.
- **Stop** in the reader saves your position — you do not need to do anything special before closing the app.
- The preview cache is keyed on text + voice + settings — running the same preview twice is instant.
- If the TTS worker crashes mid-generation, the app window stays open. Click Generate again to reload the model and retry.
- Generated filenames include a timestamp so nothing is ever overwritten:
  ```
  Conquest-of-Bread_Part-1_2026-05-08_14-32-01.mp3
  ```

---

## Getting help

The **Help** page in the sidebar has a quick reference guide built into the app.

For launch errors when using the app bundle, check:

```bash
cat ~/Library/Logs/Narracast.log
```
