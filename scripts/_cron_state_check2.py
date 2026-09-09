import sqlite3
conn = sqlite3.connect('data/blog.db')
cur = conn.cursor()

print('=== claude_code pending ===')
cur.execute("SELECT id, title, date, importance, added_at FROM articles WHERE status='pending' AND source_id='claude_code' ORDER BY date")
for row in cur.fetchall():
    print(row)

print('=== github_copilot pending ===')
cur.execute("SELECT id, title, date, importance, added_at FROM articles WHERE status='pending' AND source_id='github_copilot' ORDER BY date")
for row in cur.fetchall():
    print(row)

print('=== cursor pending ===')
cur.execute("SELECT id, title, date, importance, added_at FROM articles WHERE status='pending' AND source_id='cursor' ORDER BY date")
for row in cur.fetchall():
    print(row)

print('=== techcrunch pending imp=2 ===')
cur.execute("SELECT id, title, date, importance, added_at FROM articles WHERE status='pending' AND source_id='techcrunch' AND importance=2 ORDER BY date DESC")
for row in cur.fetchall():
    print(row)

print('=== google_ai pending imp=2 ===')
cur.execute("SELECT id, title, date, importance, added_at FROM articles WHERE status='pending' AND source_id='google_ai' AND importance>=2 ORDER BY date DESC")
for row in cur.fetchall():
    print(row)

print('=== arxiv pending imp=2 ===')
cur.execute("SELECT id, title, date, importance, added_at, summary FROM articles WHERE status='pending' AND source_id='arxiv' AND importance=2 ORDER BY date DESC")
for row in cur.fetchall():
    print(row)

# Show importance distribution by source
print('=== importance distribution by source ===')
cur.execute("SELECT source_id, importance, COUNT(*) FROM articles WHERE status='pending' GROUP BY source_id, importance ORDER BY source_id, importance DESC")
for row in cur.fetchall():
    print(row)

# source tier
print('=== sources table ===')
cur.execute("SELECT id, name, tier, weight FROM sources ORDER BY id")
for row in cur.fetchall():
    print(row)

conn.close()
