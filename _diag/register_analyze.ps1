#!/usr/bin/env pwsh
# Register cron_analyze.ps1 in Windows Task Scheduler.
# Idempotent: deletes any existing 'agentsblog-analyze' task first.
$ErrorActionPreference = 'Continue'

$TaskName = 'agentsblog-analyze'
$Script   = 'C:\Users\Admin\dev\project\agentsmits-blog\scripts\cron_analyze.ps1'
$WorkDir  = 'C:\Users\Admin\dev\project\agentsmits-blog'
$Trigger  = 'Hourly'  # every hour, top of hour
$StartBoundary = '2026-09-15T11:00:00'  # first run after this turn

Write-Host "Registering scheduled task '$TaskName'..."

# Unregister if exists (clean slate)
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "  - existing task found, removing"
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Script`"" `
    -WorkingDirectory $WorkDir

$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(5) `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -RunLevel Highest `
    -LogonType S4U

try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description "LLM-analyze pending items via Ollama (qwen3:8b). Runs hourly." `
        -ErrorAction Stop | Out-Null
    Write-Host "  - registered OK"

    $verify = Get-ScheduledTask -TaskName $TaskName
    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host ("  - state=" + $verify.State + "  next=" + $info.NextRunTime)
} catch {
    Write-Host ("  - FAILED: " + $_.Exception.Message)
    Write-Host '  (probably needs elevated session; retry from admin shell if so)'
}
