#!/usr/bin/env python3
"""Clear Telegram webhook so polling via telegram_bot.py can use getUpdates."""
from __future__ import annotations

import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()
token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
if not token:
    raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env first.")

resp = requests.post(f"https://api.telegram.org/bot{token}/deleteWebhook", data={"drop_pending_updates": False}, timeout=30)
resp.raise_for_status()
print(resp.json())
