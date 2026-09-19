[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:AGENTSBLOG_ROOT = 'C:\Users\Admin\dev\project\agentsmits-blog'
$py = 'C:\Users\Admin\python312\python.exe'

Write-Host '=== STEP 1: LLM analyze (qwen3:8b, top 50 by importance) ==='
$sw = [System.Diagnostics.Stopwatch]::StartNew()
& $py 'scripts\_llm_analyze.py' 2>&1 | ForEach-Object { Write-Host $_ }
$ec = $LASTEXITCODE
$sw.Stop()
Write-Host ("exit_code=" + $ec + " elapsed=" + [int]$sw.Elapsed.TotalSeconds + "s")

Write-Host ''
Write-Host '=== STEP 2: DB snapshot after LLM analyze ==='
& $py -c @"
import sqlite3
con = sqlite3.connect('data/blog.db')
con.row_factory = sqlite3.Row
total = con.execute('SELECT COUNT(*) FROM articles').fetchone()[0]
pending = con.execute(\"SELECT COUNT(*) FROM articles WHERE status='pending'\").fetchone()[0]
no_an = con.execute(\"SELECT COUNT(*) FROM articles WHERE status='pending' AND (agent_impact IS NULL OR agent_impact='')\").fetchone()[0]
std_pending = con.execute(\"SELECT COUNT(*) FROM articles WHERE status='pending' AND COALESCE(translated_title,'') = '' \").fetchone()[0]
en_title = con.execute(\"SELECT COUNT(*) FROM articles WHERE status='pending' AND translated_title=title\").fetchone()[0]
ru_title = con.execute(\"SELECT COUNT(*) FROM articles WHERE status='pending' AND translated_title != title AND translated_title != ''\").fetchone()[0]
print('total=', total)
print('pending=', pending)
print('  no agent_impact=', no_an)
print('  empty translated_title=', std_pending)
print('  en title (== title)=', en_title)
print('  ru title (proper)=', ru_title)
print('--- top 8 ru-title pending ---')
for r in con.execute(\"SELECT id, importance, source_id, substr(translated_title,1,60) AS tt FROM articles WHERE status='pending' AND translated_title != title AND translated_title != '' ORDER BY importance DESC, date DESC LIMIT 8\"):
    print(f\"  imp={r['importance']:>4} {r['id'][:50]:<50} tt={r['tt']}\")
con.close()
"@

Write-Host ''
Write-Host '=== STEP 3: publish --limit 5 (Telegram test) ==='
& $py -m agentsblog publish --limit 5 2>&1 | ForEach-Object { Write-Host $_ }
$ec2 = $LASTEXITCODE
Write-Host ("publish exit_code=" + $ec2)
