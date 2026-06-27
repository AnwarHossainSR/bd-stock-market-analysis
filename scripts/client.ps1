param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("dev", "build", "test", "test:watch")]
    [string]$Script
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location "$root\client"
try {
    bun run $Script
}
finally {
    Pop-Location
}
