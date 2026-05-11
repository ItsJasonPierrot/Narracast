#!/bin/bash
unset PYTHONHASHSEED
export PYTHONUNBUFFERED=1
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "$HOME/Documents/code/python/Narracast" || exit 1
exec "$HOME/Documents/code/python/Narracast/venv/bin/python3" "$HOME/Documents/code/python/Narracast/app.py" >> "$HOME/Library/Logs/Narracast.log" 2>&1
