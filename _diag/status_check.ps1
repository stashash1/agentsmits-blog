[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$ErrorActionPreference = 'Continue'

Write-Host '=== DATA DIRECTORY ==='
if (Test-Path data) {
    Get-ChildItem data -Force | Select-Object Mode, LastWriteTime, Length, Name | Format-Table -AutoSize
} else { Write-Host 'data/ not found' }

Write-Host ''
Write-Host '=== RECENT LOG FILES (last 10 modified) ==='
$logs = Get-ChildItem -Path data -Recurse -File -Filter '*.log' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 10
foreach ($l in $logs) {
    $rel = $l.FullName.Substring((Get-Location).Path.Length + 1)
    Write-Host ("{0:yyyy-MM-dd HH:mm:ss}  {1,8}  {2}" -f $l.LastWriteTime, $l.Length, $rel)
}

Write-Host ''
Write-Host '=== FILES MODIFIED IN LAST 24h (top 40) ==='
$recent = Get-ChildItem -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -gt (Get-Date).AddDays(-1) } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 40
foreach ($f in $recent) {
    $rel = $f.FullName.Substring((Get-Location).Path.Length + 1)
    Write-Host ("{0:HH:mm:ss}  {1,8}  {2}" -f $f.LastWriteTime, $f.Length, $rel)
}
