[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:AGENTSBLOG_ROOT = 'C:\Users\Admin\dev\project\agentsmits-blog'
$py = 'C:\Users\Admin\python312\python.exe'

Write-Host '=== STATE BEFORE PUBLISH ==='
& $py -c @"
import sqlite3
con = sqlite3.connect('data/blog.db')
con.row_factory = sqlite3.Row
pending = con.execute(\"SELECT COUNT(*) FROM articles WHERE status='pending'\").fetchone()[0]
ru_titles = con.execute(\"SELECT COUNT(*) FROM articles WHERE status='pending' AND translated_title != title AND translated_title != ''\").fetchone()[0]
en_titles = con.execute(\"SELECT COUNT(*) FROM articles WHERE status='pending' AND translated_title=title\").fetchone()[0]
print('pending=', pending, '  ru_titles=', ru_titles, '  en_titles=', en_titles)
print('--- top 5 by importance (whatever their title state) ---')
for r in con.execute(\"SELECT id, importance, source_id, substr(translated_title,1,55) AS tt, substr(agent_impact,1,50) AS ai FROM articles WHERE status='pending' ORDER BY importance DESC, date DESC LIMIT 5\"):
    print(f\"  imp={r['importance']:>4} {r['id'][:48]:<48} tt={r['tt']}\")
    print(f\"        ai: {r['ai']}\")
con.close()
"@

Write-Host ''
Write-Host '=== PUBLISH (--limit 5) ==='
$sw = [System.Diagnostics.Stopwatch]::StartNew()
& $py -m agentsblog publish --limit 5 2>&1 | ForEach-Object { Write-Host $_ }
$ec = $LASTEXITCODE
$sw.Stop()
Write-Host ("publish exit_code=" + $ec + " elapsed=" + [int]$sw.Elapsed.TotalSeconds + "s")

Write-Host ''
Write-Host '=== TELEGRAM AUDIT: last 5 entries ==='
if (Test-Path data\telegram_audit.log) {
    Get-Content data\telegram_audit.log -Tail 5 -ErrorAction SilentlyContinue |
        ForEach-Object { Write-Host $_ }
}

Write-Host ''
Write-Host '=== STATE AFTER PUBLISH ==='
& $py -c @"
import sqlite3
con = sqlite3.connect('data/blog.db')
con.row_factory = sqlite3.Row
pending = con.execute(\"SELECT COUNT(*) FROM articles WHERE status='pending'\").fetchone()[0]
sent = con.execute(\"SELECT COUNT(*) FROM articles WHERE status='sent'\").fetchone()[0]
error = con.execute(\"SELECT COUNT(*) FROM articles WHERE status='error'\").fetchone()[0]
print('pending=', pending, '  sent=', sent, '  error=', error)
print('--- last 5 sent (with telegram_msg_id) ---')
for r in con.execute(\"SELECT id, telegram_msg_id, datetime(updated_at) AS upd FROM articles WHERE status='sent' ORDER BY telegram_msg_id DESC LIMIT 5\"):
    print(f\"  msg={r['telegram_msg_id']} upd={r['upd']} {r['id'][:50]}\")
con.close()
"@
