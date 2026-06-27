$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$api = Start-Process -FilePath "$root\.venv\Scripts\uvicorn.exe" `
    -ArgumentList "api.main:app", "--port", "8000", "--reload" `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -PassThru

try {
    Push-Location "$root\client"
    bun run dev
}
finally {
    Pop-Location
    if ($api -and -not $api.HasExited) {
        Stop-Process -Id $api.Id -Force
    }
}
