"""Re-score all pending items using the latest impact v2 formula.

Useful when scoring logic is updated and we want to re-rank the backlog.
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentsblog.config import Settings
from agentsblog.scoring.impact import compute_impact


def main() -> int:
    s = Settings()
    conn = sqlite3.connect(s.db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT id, title, summary, source_id, importance "
        "FROM articles WHERE status='pending'"
    ).fetchall()

    print(f"Rescoring {len(rows)} pending items...")
    n_changed = 0
    for row in rows:
        impact = compute_impact(
            row["title"] or "", row["summary"] or "", row["source_id"] or ""
        )
        if impact.total != row["importance"]:
            n_changed += 1
        conn.execute(
            "UPDATE articles SET importance=?, decayed_importance=? WHERE id=?",
            (impact.total, impact.total, row["id"]),
        )

    conn.commit()
    conn.close()

    print(f"Done. {n_changed}/{len(rows)} items had importance changed.")
    print()
    print("Distribution after rescore:")
    print("  imp=5:", sum(1 for r in rows if compute_impact(r["title"] or "", r["summary"] or "", r["source_id"] or "").total == 5))
    print("  imp=4:", sum(1 for r in rows if compute_impact(r["title"] or "", r["summary"] or "", r["source_id"] or "").total == 4))
    print("  imp=3:", sum(1 for r in rows if compute_impact(r["title"] or "", r["summary"] or "", r["source_id"] or "").total == 3))
    print("  imp=2:", sum(1 for r in rows if compute_impact(r["title"] or "", r["summary"] or "", r["source_id"] or "").total == 2))
    print("  imp=1:", sum(1 for r in rows if compute_impact(r["title"] or "", r["summary"] or "", r["source_id"] or "").total == 1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
