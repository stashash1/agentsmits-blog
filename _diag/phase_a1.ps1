[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:AGENTSBLOG_ROOT = 'C:\Users\Admin\dev\project\agentsmits-blog'
$py = 'C:\Users\Admin\python312\python.exe'

Write-Host '=== STEP 1: DB snapshot before analyze ==='
$before = & $py -c @"
import sqlite3
con = sqlite3.connect('data/blog.db')
con.row_factory = sqlite3.Row
total = con.execute('SELECT COUNT(*) FROM articles').fetchone()[0]
pending = con.execute(\"SELECT COUNT(*) FROM articles WHERE status='pending'\").fetchone()[0]
no_an = con.execute(\"SELECT COUNT(*) FROM articles WHERE status='pending' AND (agent_impact IS NULL OR agent_impact='')\").fetchone()[0]
publishable = con.execute(\"SELECT COUNT(*) FROM articles WHERE status='pending' AND agent_impact IS NOT NULL AND agent_impact != ''\").fetchone()[0]
print(f'total={total} pending={pending} pending_no_an={no_an} publishable={publishable}')
con.close()
"@
Write-Host $before

Write-Host ''
Write-Host '=== STEP 2: run _heuristic_analyze.py ==='
& $py 'scripts\_heuristic_analyze.py' 2>&1
$ec = $LASTEXITCODE
Write-Host "exit_code=$ec"

Write-Host ''
Write-Host '=== STEP 3: DB snapshot after analyze ==='
$after = & $py -c @"
import sqlite3
con = sqlite3.connect('data/blog.db')
con.row_factory = sqlite3.Row
total = con.execute('SELECT COUNT(*) FROM articles').fetchone()[0]
pending = con.execute(\"SELECT COUNT(*) FROM articles WHERE status='pending'\").fetchone()[0]
no_an = con.execute(\"SELECT COUNT(*) FROM articles WHERE status='pending' AND (agent_impact IS NULL OR agent_impact='')\").fetchone()[0]
publishable = con.execute(\"SELECT COUNT(*) FROM articles WHERE status='pending' AND agent_impact IS NOT NULL AND agent_impact != ''\").fetchone()[0]
print(f'total={total} pending={pending} pending_no_an={no_an} publishable={publishable}')
print('--- top 5 publishable (now with analysis) ---')
for r in con.execute(\"SELECT id, importance, source_id, substr(translated_title,1,60) AS tt FROM articles WHERE status='pending' AND agent_impact IS NOT NULL AND agent_impact != '' ORDER BY importance DESC LIMIT 5\"):
    print(f\"  imp={r['importance']:>4} src={r['source_id']:<15} {r['id'][:50]}\")
    print(f\"        tt: {r['tt']}\")
con.close()
"@
Write-Host $after
