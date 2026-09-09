#!/usr/bin/env pwsh
# Daily-summary launcher for Windows Scheduled Task.
# Usage (manual test):
#   $env:AGENTSBLOG_BOT_TOKEN_FILE = 'C:\path\to\bot.token'
#   $env:AGENTSBLOG_TELEGRAM_CHAT_ID = '-1001234567890'
#   pwsh -File scripts/daily_summary.ps1
#
# Schedule (daily 21:00 MSK):
#   schtasks /Create /SC DAILY /TN "agentsblog-daily-summary" /TR "pwsh -File C:\path\to\scripts\daily_summary.ps1" /ST 21:00

$ErrorActionPreference = 'Stop'

# Project root = parent of scripts/
$Root = Split-Path -Parent $PSScriptRoot

# Sensible defaults (override via env or .env)
$env:AGENTSBLOG_ROOT = $Root
if (-not $env:AGENTSBLOG_BOT_TOKEN_FILE -and -not (Test-Path (Join-Path $Root '.env'))) {
    Write-Error "AGENTSBLOG_BOT_TOKEN_FILE not set and .env missing. See scripts/daily_summary.README.md"
    exit 2
}

# Find a working Python
$pyCandidates = @(
    "C:\Users\Admin\python312\python.exe",
    (Get-Command python -ErrorAction SilentlyContinue)?.Source,
    (Get-Command py -ErrorAction SilentlyContinue)?.Source,
)
$py = $null
foreach ($c in $pyCandidates) {
    if ($c -and (Test-Path $c)) { $py = $c; break }
}
if (-not $py) {
    Write-Error "Python not found. Set AGENTSBLOG_PYTHON explicitly."
    exit 3
}

# Run daily-summary for yesterday (default behavior)
& $py -m agentsblog daily-summary
exit $LASTEXITCODE
