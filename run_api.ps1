# Start the DSE Scraper API (FastAPI) on http://localhost:8000
# Swagger docs: http://localhost:8000/docs
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
& ".\.venv\Scripts\uvicorn.exe" api.main:app --host 127.0.0.1 --port 8000 --reload
