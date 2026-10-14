#!/usr/bin/env pwsh
# Daily rebuild + deploy launcher.
# Replaces: agentsmits-blog-daily automation (fc26f97f) which used `sh -lc ...`.
# Calls Windows-native PowerShell, not POSIX sh (which is not on PATH).
#
# Schedule (daily 21:00 Europe/Moscow):
#   openclaw automations edit fc26f97f-00c0-4b37-9c23-ab2dbe7d3c9e \
#       --command-argv '["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File","C:\\Users\\Admin\\dev\\project\\agentsmits-blog\\scripts\\daily_rebuild_deploy.ps1"]'
#
# What it does:
#   1. Rebuild static site from blog.db
#   2. Stage all changes, commit, push to origin main (only if there are changes)
#
# Requirements:
#   - python at C:\Users\Admin\python312\python.exe (already installed)
#   - git on PATH (already installed, 2.55.0.5)
#   - GITHUB_DEPLOY_TOKEN configured (env or .env)

$ErrorActionPreference = 'Stop'
$Root = 'C:\Users\Admin\dev\project\agentsmits-blog'
$LogFile = Join-Path $Root 'data\cron-daily.log'

$env:AGENTSBLOG_ROOT  = $Root
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8       = '1'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

function Log {
    param([string]$Msg)
    $entry = "[{0}] [daily] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Msg
    Add-Content -Path $LogFile -Value $entry -Encoding UTF8
    Write-Host $entry
}

Log "start: pid=$PID user=$env:USERNAME cwd=$PWD"

# 1. rebuild static site
try {
    Log "step: build-site"
    & 'C:\Users\Admin\python312\python.exe' -m agentsblog build-site 2>&1 | ForEach-Object { Log "[build] $_" }
    Log "build-site exit_code=$LASTEXITCODE"
} catch {
    Log "build-site ERROR: $_"
    exit 1
}

# 2. git add/commit/push (only if there are changes)
Push-Location $Root
try {
    Log "step: git status"
    $status = git status --porcelain
    if (-not $status) {
        Log "no changes to commit, skipping push"
        exit 0
    }
    Log "step: git add -A"
    git add -A 2>&1 | ForEach-Object { Log "[git] $_" }
    $date = Get-Date -Format 'yyyy-MM-dd'
    $msg = "daily rebuild $date"
    Log "step: git commit -m '$msg' --allow-empty"
    git commit -m $msg --allow-empty 2>&1 | ForEach-Object { Log "[git] $_" }
    Log "step: git push origin main"
    git push origin main 2>&1 | ForEach-Object { Log "[git] $_" }
    Log "git push exit_code=$LASTEXITCODE"
    exit $LASTEXITCODE
} catch {
    Log "git ERROR: $_"
    exit 2
} finally {
    Pop-Location
}
