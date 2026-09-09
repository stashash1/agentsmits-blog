import sqlite3, json
from datetime import datetime, timezone, timedelta
from agentsblog.scoring.impact import get_source_tier

conn = sqlite3.connect("data/blog.db")
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT id, source_id, title, importance, date FROM articles "
    "WHERE status='pending' ORDER BY importance DESC, date DESC"
).fetchall()

# Check date spread
dates = [r["date"] for r in rows if r["date"]]
print("Date min/max:", min(dates) if dates else "n/a", max(dates) if dates else "n/a")

# Source-level breakdown
by_source = {}
for r in rows:
    by_source.setdefault(r["source_id"], []).append(dict(r))

# Check published count today
today_pubs = conn.execute(
    "SELECT COUNT(*) AS n FROM articles WHERE status='published' AND date(published_at) = date('now')"
).fetchone()["n"]
print(f"Published today: {today_pubs}")

# Check which claude_code / github_copilot strings actually match tier
for sid in by_source:
    t = get_source_tier(sid)
    print(f"get_source_tier({sid!r}) = {t}")

# Get the AGI counter state from metrics if possible
import os
met_path = "data/metrics.json"
if os.path.exists(met_path):
    with open(met_path) as f:
        m = json.load(f)
    print("AGI counter from metrics.json:", m.get("agi_counter"))
