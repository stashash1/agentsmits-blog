[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

Write-Host '=== telegram_audit.log: size + last entries (UTF-8) ==='
if (Test-Path data\telegram_audit.log) {
    $fi = Get-Item data\telegram_audit.log
    Write-Host ("size=" + $fi.Length + " bytes  mtime=" + $fi.LastWriteTime)
    Write-Host '--- last 6 lines (UTF-8) ---'
    [System.IO.File]::ReadAllLines($fi.FullName, [System.Text.Encoding]::UTF8) |
        Select-Object -Last 6 | ForEach-Object { Write-Host $_ }
} else {
    Write-Host 'audit log not found'
}

Write-Host ''
Write-Host '=== data/cron-stdout.log: last 15 lines (UTF-8) ==='
if (Test-Path data\cron-stdout.log) {
    $fi = Get-Item data\cron-stdout.log
    Write-Host ("size=" + $fi.Length + " bytes  mtime=" + $fi.LastWriteTime)
    Write-Host '--- last 15 lines (UTF-8) ---'
    [System.IO.File]::ReadAllLines($fi.FullName, [System.Text.Encoding]::UTF8) |
        Select-Object -Last 15 | ForEach-Object { Write-Host $_ }
}

Write-Host ''
Write-Host '=== SCHEDULED TASKS ==='
Get-ScheduledTask -TaskPath '\' -ErrorAction SilentlyContinue |
    Where-Object { $_.TaskName -like '*agentsblog*' } |
    ForEach-Object {
        $info = Get-ScheduledTaskInfo -TaskName $_.TaskName -ErrorAction SilentlyContinue
        $next = if ($info) { $info.NextRunTime } else { 'n/a' }
        Write-Host (" - {0,-25} state={1,-10} next={2}" -f $_.TaskName, $_.State, $next)
    }
