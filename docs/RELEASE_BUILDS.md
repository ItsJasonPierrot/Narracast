# Release Builds

Narracast uses PyInstaller to create native desktop bundles. Build each operating
system on that operating system: macOS on macOS, Windows on Windows, and Linux on
Linux. PyInstaller packages the local Python environment and is not a
cross-compiler.

## Common Setup

Use Python 3.11, then install the runtime and build dependencies:

```bash
python3.11 -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -e ".[build]"
```

On Windows PowerShell, use:

```powershell
py -3.11 -m venv venv
.\venv\Scripts\python -m pip install --upgrade pip
.\venv\Scripts\python -m pip install -e ".[build]"
```

Narracast also needs `ffmpeg` available on `PATH` for audio export and M4B work.

## macOS

```bash
venv/bin/python scripts/build_bundle.py
```

Output:

```text
dist/Narracast-macos.zip
dist/Narracast-macos.zip.sha256
```

The archive contains `Narracast.app`.

## Windows

Run from a Windows checkout:

```powershell
.\venv\Scripts\python scripts\build_bundle.py
```

Output:

```text
dist\Narracast-windows.zip
dist\Narracast-windows.zip.sha256
```

The archive contains the PyInstaller `Narracast` app directory. If you add a
Windows `.ico` file at `assets/Narracast.ico`, the build script will use it.

## Linux

Run from a Linux checkout:

```bash
venv/bin/python scripts/build_bundle.py
```

Output:

```text
dist/Narracast-linux.zip
dist/Narracast-linux.zip.sha256
```

The archive contains the PyInstaller `Narracast` app directory.

## Notes

- Use `--onefile` only for small smoke builds. The default app-directory output
  starts faster and is easier to inspect.
- Use `--no-archive` if you want the raw PyInstaller output left in `dist/`.
- User data folders such as `output/`, `projects/`, and `voices/` live in the
  platform app-data folder at runtime and are not bundled into releases.
- Large local assets such as `reference.wav`, `raw_audio/`, and generated MP3s are
  not release inputs.
- `requirements.lock` records the current resolved development environment. Use it
  for reproducible rebuilds after validating it on the target OS.
- Release archives get a sibling `.sha256` file. Publish both files together.
