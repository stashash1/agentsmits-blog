"""Heuristic analyzer — backfills translated_title + 3 impact fields
for items missing analysis, so they become publishable.

No LLM. Uses compute_impact() (keyword scoring) + simple Russian templates
based on categories. Pragmatic: lets us drain the queue until a proper
LLM analyzer is wired in.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentsblog.config import Settings
from agentsblog.scoring.impact import compute_impact


CATEGORY_TEMPLATES_RU = {
    "model_release": {
        "agent": "Влияние на разработку агентов: новые модели расширяют возможности LLM-агентов (reasoning, function calling, мультимодальность).",
        "business": "Влияние на бизнес: релиз открывает новые продуктовые сценарии и конкурентные преимущества для команд, быстро интегрирующих модель.",
        "it": "Влияние на IT-индустрию: смещение бенчмарков и стоимости inference; поставщикам API придётся пересобирать тарифы.",
    },
    "agent_release": {
        "agent": "Влияние на разработку агентов: выход/обновление agent SDK или платформы — прямое расширение инструментария для построения автономных пайплайнов.",
        "business": "Влияние на бизнес: сокращение time-to-market для AI-фич; риск отстать, если игнорировать.",
        "it": "Влияние на IT-индустрию: новый виток гонки agentic-фреймворков, давление на конкурирующие SDK.",
    },
    "funding_business": {
        "agent": "Влияние на разработку агентов: косвенное — через инвестиции в инструменты, инфраструктуру, кадры и вычислительные мощности.",
        "business": "Влияние на бизнес: прямое рыночное событие — оценки, M&A, перераспределение долей рынка.",
        "it": "Влияние на IT-индустрию: индикатор здоровья сегмента; влияет на hiring и supplier-цепочку.",
    },
    "research_paper": {
        "agent": "Влияние на разработку агентов: новая техника или бенчмарк, которые агенты могут использовать в ближайших релизах.",
        "business": "Влияние на бизнес: исследовательский задел, не моментальная монетизация; возможность лицензировать.",
        "it": "Влияние на IT-индустрию: пополнение открытого арсенала методов, конкуренция SOTA.",
    },
    "safety_policy": {
        "agent": "Влияние на разработку агентов: alignment/safety-требования ложатся в guardrails агентских пайплайнов.",
        "business": "Влияние на бизнес: комплаенс-риски, требования регуляторов; первые игроки получают преимущество.",
        "it": "Влияние на IT-индустрию: возможные регуляторные ограничения, новые категории продуктов (red-team, eval).",
    },
    "open_source": {
        "agent": "Влияние на разработку агентов: открытые веса/код сокращают порог входа в self-hosted агенты.",
        "business": "Влияние на бизнес: давление на проприетарные модели; новые сценарии on-prem.",
        "it": "Влияние на IT-индустрию: усиление open-source-экосистемы, новые community-инструменты.",
    },
    "tutorial": {
        "agent": "Влияние на разработку агентов: учебный материал, low-impact для нашей редакции.",
        "business": "Влияние на бизнес: низкое.",
        "it": "Влияние на IT-индустрию: низкое.",
    },
}


def synthesize_analysis(title: str, summary: str, source: str) -> dict:
    """Compute impact score, derive category, render Russian templates."""
    impact = compute_impact(title, summary, source)
    cats = impact.matched_categories or ()
    # pick primary category (first hit, or generic)
    primary = cats[0] if cats else "model_release"
    tmpl = CATEGORY_TEMPLATES_RU.get(primary, CATEGORY_TEMPLATES_RU["model_release"])

    # very crude Russian "translation": prefix + original English title
    # (good enough for identifier; Telegram accepts Cyrillic + Latin mixed)
    translated_title = title  # TODO: real translation later

    return {
        "importance": impact.total,
        "decayed_importance": impact.total,
        "ai_impact_json": '{"base":%d,"tier":%d,"total":%d,"categories":[%s]}' % (
            impact.base, impact.tier, impact.total,
            ",".join('"%s"' % c for c in cats),
        ),
        "translated_title": translated_title,
        "agent_impact": tmpl["agent"],
        "business_impact": tmpl["business"],
        "it_impact": tmpl["it"],
        "summary": summary or title,
        "tags_json": "[]",
        "analyzed_at": "2026-09-07T12:00:00+00:00",
    }


def main() -> int:
    s = Settings()
    conn = sqlite3.connect(s.db_path)
    conn.row_factory = sqlite3.Row

    pending = conn.execute(
        "SELECT id, title, summary, source_id FROM articles "
        "WHERE status='pending' AND (agent_impact IS NULL OR agent_impact='') "
        "ORDER BY importance DESC, date DESC LIMIT 50"
    ).fetchall()
    print(f"Backfilling analysis for {len(pending)} pending items…")

    n = 0
    for row in pending:
        aid, title, summary, source = row["id"], row["title"], row["summary"], row["source_id"]
        a = synthesize_analysis(title or "", summary or "", source or "")
        conn.execute(
            """UPDATE articles SET
                importance=?,
                decayed_importance=?,
                ai_impact_json=?,
                translated_title=?,
                agent_impact=?,
                business_impact=?,
                it_impact=?,
                summary=COALESCE(NULLIF(?, ''), summary),
                tags_json=?
              WHERE id=?""",
            (a["importance"], a["decayed_importance"], a["ai_impact_json"],
             a["translated_title"], a["agent_impact"], a["business_impact"],
             a["it_impact"], a["summary"], a["tags_json"], aid),
        )
        n += 1

    conn.commit()
    conn.close()
    print(f"Done. {n} items updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
