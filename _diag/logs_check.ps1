[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

Write-Host '=== data/cron-stdout.log: LAST 60 LINES ==='
Get-Content data\cron-stdout.log -Tail 60 -ErrorAction SilentlyContinue

Write-Host ''
Write-Host '=== data/cron-publish.log: LAST 30 LINES ==='
Get-Content data\cron-publish.log -Tail 30 -ErrorAction SilentlyContinue

Write-Host ''
Write-Host '=== data/cron-scan.log: LAST 20 LINES ==='
Get-Content data\cron-scan.log -Tail 20 -ErrorAction SilentlyContinue

Write-Host ''
Write-Host '=== data/cron-analyze.log: LAST 15 LINES ==='
Get-Content data\cron-analyze.log -Tail 15 -ErrorAction SilentlyContinue

Write-Host ''
Write-Host '=== data/telegram_audit.log: LAST 20 LINES ==='
Get-Content data\telegram_audit.log -Tail 20 -ErrorAction SilentlyContinue
