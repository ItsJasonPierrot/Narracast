#!/bin/bash
unset PYTHONHASHSEED
export PYTHONUNBUFFERED=1
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_ROOT="${NARRACAST_APP_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
PYTHON_BIN="${NARRACAST_PYTHON:-$APP_ROOT/venv/bin/python3}"
LOG_DIR="${HOME}/Library/Logs"

mkdir -p "$LOG_DIR"
cd "$APP_ROOT" || exit 1
exec "$PYTHON_BIN" "$APP_ROOT/app.py" >> "$LOG_DIR/Narracast.log" 2>&1
