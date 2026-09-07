import sqlite3
c = sqlite3.connect('data/blog.db')
print('---articles by status---')
for row in c.execute("SELECT status, COUNT(*) FROM articles GROUP BY status"):
    print(' ', row[0], '=', row[1])
print()
print('---pending articles---')
sql = (
    "SELECT id, importance, date, source, substr(title,1,60) "
    "FROM articles WHERE status='pending' "
    "ORDER BY importance DESC, date"
)
for row in c.execute(sql):
    print(' ', row[1], '|', row[2], '|', row[3], '|', row[4], '|', row[0][:50])
print()
print('---recent events---')
for row in c.execute("SELECT ts, event, details FROM events ORDER BY ts DESC LIMIT 5"):
    print(' ', row[0][:19], '|', row[1], '|', (row[2] or '')[:120])
