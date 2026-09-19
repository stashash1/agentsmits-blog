[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

$TaskName = 'agentsblog-analyze'
$Script   = 'C:\Users\Admin\dev\project\agentsmits-blog\scripts\cron_analyze.ps1'

Write-Host "=== ATTEMPT 1: schtasks /create with SYSTEM ==="
$argList = @(
    '/create'
    '/tn', $TaskName
    '/tr', "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$Script`""
    '/sc', 'hourly'
    '/mo', '1'
    '/ru', 'SYSTEM'
    '/rl', 'HIGHEST'
    '/f'  # force overwrite if exists
)
$out = & schtasks.exe @argList 2>&1
$ec = $LASTEXITCODE
Write-Host "exit_code=$ec"
Write-Host "output: $out"

Write-Host ''
Write-Host "=== VERIFY ==="
$verify = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($verify) {
    $info = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
    Write-Host ("  state=" + $verify.State + "  next=" + $info.NextRunTime)
} else {
    Write-Host '  task NOT registered'
}

Write-Host ''
Write-Host "=== ALL AGENTSBLOG TASKS ==="
Get-ScheduledTask -TaskPath '\' -ErrorAction SilentlyContinue |
    Where-Object { $_.TaskName -like '*agentsblog*' } |
    ForEach-Object {
        $info = Get-ScheduledTaskInfo -TaskName $_.TaskName -ErrorAction SilentlyContinue
        Write-Host (" - {0,-25} state={1,-10} next={2}" -f $_.TaskName, $_.State, $info.NextRunTime)
    }
