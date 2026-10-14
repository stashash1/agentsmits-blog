$f = 'C:\Users\Admin\dev\project\agentsmits-blog\data\pending_queue.json'
$content = [System.IO.File]::ReadAllText($f)
$utf8 = [System.Text.Encoding]::UTF8.GetString([System.Text.Encoding]::Convert([System.Text.Encoding]::UTF8, [System.Text.Encoding]::UTF8, [System.Text.Encoding]::UTF8.GetBytes($content)))
try {
    $j = $utf8 | ConvertFrom-Json
    Write-Host "pending_count=$($j.pending.Count)"
    Write-Host "published_count=$($j.published.Count)"
    Write-Host "sources_count=$($j.sources.Count)"
    Write-Host "agi=$($j.agi_counter | ConvertTo-Json -Compress)"
} catch {
    Write-Host "parse_error=$($_.Exception.Message)"
}
