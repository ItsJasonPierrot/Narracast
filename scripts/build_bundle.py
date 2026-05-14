#!/usr/bin/env python3
"""Build a native Narracast app bundle for the current operating system."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"


def _platform_name() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        return "linux"
    return system or "unknown"


def _asset_arg(source: Path, destination: str) -> str:
    separator = ";" if platform.system() == "Windows" else ":"
    return f"{source}{separator}{destination}"


def _require_pyinstaller() -> None:
    if importlib.util.find_spec("PyInstaller") is not None:
        return
    raise SystemExit(
        "PyInstaller is not installed. Run: "
        f"{sys.executable} -m pip install -e .[build]"
    )


def _base_command(onefile: bool) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "Narracast",
        "--clean",
        "--noconfirm",
        "--windowed",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR / "pyinstaller"),
        "--specpath",
        str(BUILD_DIR),
        "--add-data",
        _asset_arg(ROOT / "assets", "assets"),
        "--add-data",
        _asset_arg(ROOT / "voices" / ".gitkeep", "voices"),
        "--add-data",
        _asset_arg(ROOT / "projects" / ".gitkeep", "projects"),
    ]
    if onefile:
        command.append("--onefile")
    if platform.system() == "Darwin":
        icon = ROOT / "assets" / "Narracast.icns"
        if icon.exists():
            command.extend(["--icon", str(icon)])
    elif platform.system() == "Windows":
        icon = ROOT / "assets" / "Narracast.ico"
        if icon.exists():
            command.extend(["--icon", str(icon)])
    command.append(str(ROOT / "app.py"))
    return command


def build(onefile: bool) -> Path:
    _require_pyinstaller()
    DIST_DIR.mkdir(exist_ok=True)
    command = _base_command(onefile)
    subprocess.run(command, cwd=ROOT, check=True)
    return DIST_DIR / f"Narracast-{_platform_name()}"


def package_output(target: Path) -> Path:
    target.parent.mkdir(exist_ok=True)
    source = DIST_DIR / "Narracast"
    if platform.system() == "Darwin":
        source = DIST_DIR / "Narracast.app"
    archive = shutil.make_archive(str(target), "zip", root_dir=source.parent, base_dir=source.name)
    return Path(archive)


def write_checksum(path: Path) -> Path:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    checksum_path = path.with_suffix(path.suffix + ".sha256")
    checksum_path.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return checksum_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="Build a single executable instead of an app directory.",
    )
    parser.add_argument(
        "--no-archive",
        action="store_true",
        help="Leave the PyInstaller output unpacked in dist/.",
    )
    args = parser.parse_args()

    target = build(onefile=args.onefile)
    if args.no_archive:
        print(f"Built Narracast in {DIST_DIR}")
        return
    archive = package_output(target)
    checksum = write_checksum(archive)
    print(f"Created {archive}")
    print(f"Created {checksum}")


if __name__ == "__main__":
    main()
