# Editorial analysis: full source, evidence, review, persistent retry state.
# Model and batch size are configured through AGENTSBLOG_EDITORIAL_* settings.
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
    $entry = "[{0}] [analyze] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Msg
    Add-Content -Path $LogFile -Value $entry -Encoding UTF8
}

Log "start: pid=$PID user=$env:USERNAME editorial=settings cwd=$PWD"

try {
    & 'C:\Users\Admin\python312\python.exe' "$Root\scripts\_llm_analyze.py" 2>&1 |
        ForEach-Object { Log $_; $_ }
    $ec = $LASTEXITCODE
    Log "exit_code=$ec"
    exit $ec
}
catch {
    Log "ERROR: $_"
    exit 1
}
