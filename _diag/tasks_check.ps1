[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

Write-Host '=== WINDOWS TASK SCHEDULER: agentsblog tasks ==='
try {
    $tasks = Get-ScheduledTask -TaskPath '\' -ErrorAction Stop |
        Where-Object { $_.TaskName -like '*agentsblog*' -or $_.TaskName -like '*agentsmits*' }
    if ($tasks) {
        foreach ($t in $tasks) {
            $info = Get-ScheduledTaskInfo -TaskName $t.TaskName -ErrorAction SilentlyContinue
            $last = if ($info) { $info.LastRunTime } else { 'never' }
            $next = if ($info) { $info.NextRunTime } else { 'n/a' }
            $state = $t.State
            Write-Host (" - {0,-30} state={1,-12} last={2} next={3}" -f $t.TaskName, $state, $last, $next)
        }
    } else {
        Write-Host 'no tasks matching *agentsblog* / *agentsmits*'
    }
} catch {
    Write-Host ("Get-ScheduledTask failed: " + $_.Exception.Message)
}

Write-Host ''
Write-Host '=== ALSO check user-context scheduled tasks ==='
try {
    $tasks2 = Get-ScheduledTask -TaskPath '\' -ErrorAction Stop |
        Where-Object { $_.TaskName -match 'cron|cron_' }
    foreach ($t in $tasks2) {
        Write-Host (" - cron-like: {0}" -f $t.TaskName)
    }
} catch {}

Write-Host ''
Write-Host '=== check schtasks.exe listing (broader) ==='
& schtasks.exe /query /fo LIST 2>&1 | Select-String -Pattern 'agentsblog|agentsmits' -SimpleMatch |
    ForEach-Object { Write-Host ("schtasks: " + $_) }
