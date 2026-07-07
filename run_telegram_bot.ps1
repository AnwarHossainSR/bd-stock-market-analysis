$ErrorActionPreference = "Stop"

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Error "Created .env. Fill TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_CHAT_IDS, then run again."
}

.\.venv\Scripts\python tools\telegram_bot.py
