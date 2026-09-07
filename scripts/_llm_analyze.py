"""LLM analyzer — backfills Russian translated_title + 3 impact fields
for items missing analysis.

Uses local Ollama (qwen3:14b by default). Stdlib only (urllib + json).
Re-runnable: only touches items with empty agent_impact.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentsblog.config import Settings
from agentsblog.scoring.impact import compute_impact


OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")


SYSTEM_PROMPT = """Ты — редактор русскоязычного AI-новостного канала «Агенты Смита». \
Преврати англоязычную новость в короткий пост для Telegram.

Правила:
- Язык: ТОЛЬКО русский. Английский — только в именах собственных и неизменяемых терминах (API, LLM, GPU).
- Заголовок: 1 строка, до 110 символов, по-русски, без кавычек и эмодзи.
- Поля влияния: по 1-2 предложения каждое, конкретно, по-русски.
- Не выдумывай факты — переводи и обобщай то, что в исходнике.
- Верни СТРОГО JSON без markdown-обёрток и комментариев.

Формат:
{"translated_title": "...", "summary": "...", \
"agent_impact": "...", "business_impact": "...", "it_impact": "...", "tags": ["...", "..."]}
"""


def _check_ollama(timeout: float = 5.0) -> bool:
    """Quick health check on the Ollama server."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=timeout) as r:
            r.read(2048)
        return True
    except Exception as e:
        sys.stderr.write(f"[ollama] health check failed at {OLLAMA_URL}: {e}\n")
        return False


def _call_ollama(prompt_user: str, *, timeout: float = 120.0) -> dict | None:
    """Call Ollama /api/generate. Parses JSON from free-form response.

    qwen3 models sometimes return `{}` when format=json is forced; we
    instead prompt-engineer for JSON and extract the first {...} block.
    """
    payload = {
        "model": OLLAMA_MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": prompt_user,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_ctx": 4096,
            "num_predict": 800,
        },
    }
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"[ollama] HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}\n")
        return None
    except Exception as e:
        sys.stderr.write(f"[ollama] error: {e}\n")
        return None

    text = body.get("response", "")
    # Extract first balanced {...} block from the response
    start = text.find("{")
    if start < 0:
        sys.stderr.write(f"[ollama] no JSON in response: {text[:200]}\n")
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    else:
        sys.stderr.write(f"[ollama] unbalanced JSON: {text[:200]}\n")
        return None
    blob = text[start:end]
    try:
        return json.loads(blob)
    except Exception as e:
        sys.stderr.write(f"[ollama] json parse error: {e}; blob={blob[:200]}\n")
        return None


def analyze_one(title: str, summary: str, source: str) -> dict | None:
    user = f"""Новость (источник: {source}):

Заголовок: {title}
Краткое содержание: {summary or '(нет)'}

Сделай русскоязычный пост."""
    return _call_ollama(user)


def main() -> int:
    s = Settings()
    conn = sqlite3.connect(s.db_path)
    conn.row_factory = sqlite3.Row

    if not _check_ollama():
        sys.stderr.write(f"FATAL: Ollama недоступен на {OLLAMA_URL}. "
                         "Запусти `ollama serve` и проверь `ollama list`.\n")
        return 2
    sys.stderr.write(f"[setup] Ollama OK at {OLLAMA_URL}, model={OLLAMA_MODEL}\n")

    pending = conn.execute(
        "SELECT id, title, summary, source_id FROM articles "
        "WHERE status='pending' "
        "  AND (agent_impact IS NULL OR agent_impact='' "
        "       OR translated_title='' OR translated_title=title) "
        "ORDER BY importance DESC, date DESC LIMIT 50"
    ).fetchall()
    sys.stderr.write(f"[run] {len(pending)} items to analyze\n")

    n = 0
    t0 = time.monotonic()
    for i, row in enumerate(pending, 1):
        a = analyze_one(row["title"] or "", row["summary"] or "", row["source_id"] or "")
        if not a:
            sys.stderr.write(f"  [{i}/{len(pending)}] {row['id'][:50]} -> FAILED, skip\n")
            continue
        impact = compute_impact(row["title"] or "", row["summary"] or "", row["source_id"] or "")
        ai_json = json.dumps({
            "base": impact.base, "tier": impact.tier, "total": impact.total,
            "categories": list(impact.matched_categories),
            "llm": f"ollama:{OLLAMA_MODEL}",
        }, ensure_ascii=False)
        tags_json = json.dumps(a.get("tags") or [], ensure_ascii=False)
        conn.execute(
            """UPDATE articles SET
                importance=?, decayed_importance=?, ai_impact_json=?,
                translated_title=?, summary=?, agent_impact=?,
                business_impact=?, it_impact=?, tags_json=?,
                updated_at=?
              WHERE id=?""",
            (impact.total, impact.total, ai_json,
             a.get("translated_title", row["title"] or "")[:200],
             a.get("summary", row["summary"] or "")[:500],
             a.get("agent_impact", "")[:500],
             a.get("business_impact", "")[:500],
             a.get("it_impact", "")[:500],
             tags_json,
             time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
             row["id"]),
        )
        n += 1
        sys.stderr.write(
            f"  [{i}/{len(pending)}] imp={impact.total} | "
            f"{a.get('translated_title','')[:80]}\n"
        )
        # Commit per-item so progress survives interrupts / timeouts
        if n % 3 == 0:
            conn.commit()

    conn.commit()
    conn.close()
    dt = time.monotonic() - t0
    sys.stderr.write(f"[done] {n}/{len(pending)} items updated in {dt:.1f}s "
                     f"({dt/max(n,1):.1f}s/item)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
