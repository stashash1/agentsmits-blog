# Analyze at most four candidates, then publish through the editorial and delivery gates.
# AGENTSBLOG_SKIP_ANALYZE=1 skips analysis; it does not bypass quality gates.
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
    $entry = "[{0}] [publish] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Msg
    Add-Content -Path $LogFile -Value $entry -Encoding UTF8
}

Log "start: pid=$PID user=$env:USERNAME editorial=settings cwd=$PWD"

# Pre-step: source-grounded editorial analysis
$AnalyzeLimit = if ($env:AGENTSBLOG_ANALYZE_LIMIT) { [int]$env:AGENTSBLOG_ANALYZE_LIMIT } else { 4 }
if (-not $env:AGENTSBLOG_SKIP_ANALYZE) {
    Log "pre-step: LLM analyze (limit=$AnalyzeLimit, editorial=settings)"
    try {
        & 'C:\Users\Admin\python312\python.exe' "$Root\scripts\_llm_analyze.py" --limit $AnalyzeLimit 2>&1 |
            ForEach-Object { Log "[analyze] $_" }
        Log "analyze exit_code=$LASTEXITCODE"
    } catch {
        Log "analyze ERROR: $_"
    }
} else {
    Log "pre-step: LLM analyze SKIPPED (env AGENTSBLOG_SKIP_ANALYZE=1)"
}

try {
    & 'C:\Users\Admin\python312\python.exe' -m agentsblog publish --limit 3 2>&1 |
        ForEach-Object { Log $_; $_ }
    $ec = $LASTEXITCODE
    Log "exit_code=$ec"
    exit $ec
}
catch {
    Log "ERROR: $_"
    exit 1
}
