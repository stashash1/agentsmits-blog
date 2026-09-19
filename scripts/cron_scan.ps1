#!/usr/bin/env pwsh
# Cron entry: scan all enabled sources.
# Called by Windows Scheduled Task "agentsblog-scan".

$ErrorActionPreference = 'Continue'
$Root    = 'C:\Users\Admin\dev\project\agentsmits-blog'
$LogFile = Join-Path $Root 'data\cron-stdout.log'

$env:AGENTSBLOG_ROOT  = $Root
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8       = '1'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

function Log {
    param([string]$Msg)
    $entry = "[{0}] [scan] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Msg
    Add-Content -Path $LogFile -Value $entry -Encoding UTF8
}

Log "start: pid=$PID user=$env:USERNAME cwd=$PWD"

try {
    & 'C:\Users\Admin\python312\python.exe' -m agentsblog scan 2>&1 |
        ForEach-Object { Log $_; $_ }
    $ec = $LASTEXITCODE
    Log "exit_code=$ec"
    exit $ec
}
catch {
    Log "ERROR: $_"
    exit 1
}
