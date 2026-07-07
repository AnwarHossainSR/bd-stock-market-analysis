#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f ".env" ]]; then
  cp ".env.example" ".env"
  echo "Created .env. Fill TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_CHAT_IDS, then run again." >&2
  exit 1
fi

if [[ -x ".venv/Scripts/python.exe" ]]; then
  ".venv/Scripts/python.exe" tools/telegram_bot.py
elif [[ -x ".venv/bin/python" ]]; then
  ".venv/bin/python" tools/telegram_bot.py
else
  python tools/telegram_bot.py
fi
