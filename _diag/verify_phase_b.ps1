[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$py = 'C:\Users\Admin\python312\python.exe'

Write-Host '=== STEP 1: verify _llm_analyze.py compiles with new --limit ==='
& $py -m py_compile 'scripts\_llm_analyze.py'
if ($LASTEXITCODE -eq 0) {
    Write-Host '  py_compile OK'
} else {
    Write-Host '  py_compile FAILED'
}

Write-Host ''
Write-Host '=== STEP 2: verify _llm_analyze.py --help ==='
& $py 'scripts\_llm_analyze.py' --help 2>&1
Write-Host ("exit_code=" + $LASTEXITCODE)

Write-Host ''
Write-Host '=== STEP 3: tiny analyze --limit 3 + publish --limit 3 end-to-end ==='
Write-Host '--- analyze ---'
& $py 'scripts\_llm_analyze.py' --limit 3 2>&1 | Select-Object -First 20 | ForEach-Object { Write-Host $_ }
$ae = $LASTEXITCODE
Write-Host ("analyze exit_code=" + $ae)

if ($ae -eq 0) {
    Write-Host ''
    Write-Host '--- publish ---'
    & $py -m agentsblog publish --limit 3 2>&1 | ForEach-Object { Write-Host $_ }
    Write-Host ("publish exit_code=" + $LASTEXITCODE)
}

Write-Host ''
Write-Host '=== STEP 4: pending count after ==='
& $py -c @"
import sqlite3
con = sqlite3.connect('data/blog.db')
for r in con.execute(\"SELECT status, COUNT(*) FROM articles GROUP BY status\"):
    print(f\"  {r[0]}: {r[1]}\")
ru_titles = con.execute(\"SELECT COUNT(*) FROM articles WHERE status='pending' AND translated_title != title AND translated_title != ''\").fetchone()[0]
en_titles = con.execute(\"SELECT COUNT(*) FROM articles WHERE status='pending' AND translated_title=title\").fetchone()[0]
print(f'  pending ru_title={ru_titles}  en_title={en_titles}')
con.close()
"@
