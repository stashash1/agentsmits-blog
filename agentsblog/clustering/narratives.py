"""Narrative clustering — group related articles via entity-overlap.

Pure functions over Narrative + Article models. Persistence layer
uses `agentsblog.db` (narratives + narrative_items tables).

Replaces pipeline/narrative_store.py — drops the global mutable counter
in favor of explicit DB queries.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Iterable

from agentsblog.models import Narrative, NarrativeItem
from agentsblog.scoring.impact import extract_entities_from_item


# Threshold chosen via spike 2026-08-10: gives real narratives (n>=2)
# without false merges.
JACCARD_THRESHOLD = 0.4

# Entities that are too generic to use for Jaccard clustering (appear in
# nearly every AI news piece). Still extracted for scoring, but excluded
# from overlap comparison.
_GENERIC_ENTITIES = frozenset({
    "agent", "agents", "agentic", "rag", "embedding", "transformer",
    "multimodal", "vision", "speech", "open source", "open-source",
    "benchmark", "sota", "robot", "robotics", "autonomous", "alignment",
    "regulation", "policy", "fine-tuning", "rlhf", "rlaif", "reasoning",
    "context window", "tool use", "function calling", "chain-of-thought",
    "retrieval", "memory",
})


def _filter_entities(entities: Iterable[str]) -> list[str]:
    """Drop generic entities that would cause false clustering."""
    return [e for e in entities if e not in _GENERIC_ENTITIES]


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def find_matching_narrative(
    entities: list[str],
    narratives: list[Narrative],
    *,
    threshold: float = JACCARD_THRESHOLD,
) -> Narrative | None:
    """Return the first narrative whose entity set overlaps ≥ threshold.

    Ties broken by recency (most recent `last_seen` first).
    """
    ent_set = set(_filter_entities(entities))
    if not ent_set:
        return None
    candidates: list[tuple[float, Narrative]] = []
    for n in narratives:
        if n.status == "dormant":
            continue
        n_ents = set(_filter_entities(n.entities))
        if not n_ents:
            continue
        sim = _jaccard(ent_set, n_ents)
        if sim >= threshold:
            candidates.append((sim, n))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1].last_seen), reverse=True)
    return candidates[0][1]


def create_narrative(
    article,
    *,
    narrative_id: str,
    entities: list[str] | None = None,
) -> Narrative:
    """Build a fresh Narrative from a single article (item becomes primary)."""
    now = datetime.now(timezone.utc)
    ents = entities if entities is not None else extract_entities_from_item(article)
    n = Narrative(
        id=narrative_id,
        title=getattr(article, "title", "(untitled)")[:120],
        status="active",
        first_seen=now,
        last_seen=now,
        entities=sorted(set(_filter_entities(ents))),
        items=[NarrativeItem(
            article_id=getattr(article, "id", ""),
            role="primary",
            attached_at=now,
        )],
        source="auto",
        importance_max=getattr(article, "importance", 0) or 0,
    )
    return n


def attach_to_narrative(
    narrative: Narrative, article,
    *,
    role: str = "followup",
) -> Narrative:
    """Attach an article to an existing narrative (mutates a copy)."""
    now = datetime.now(timezone.utc)
    new_items = list(narrative.items)
    if not any(it.article_id == getattr(article, "id", "") for it in new_items):
        new_items.append(NarrativeItem(
            article_id=getattr(article, "id", ""),
            role=role,
            attached_at=now,
        ))
    new_entities = sorted(set(narrative.entities) | set(_filter_entities(
        extract_entities_from_item(article)
    )))
    new_imp = max(narrative.importance_max, getattr(article, "importance", 0) or 0)
    return narrative.model_copy(update={
        "items": new_items,
        "entities": new_entities,
        "last_seen": now,
        "importance_max": new_imp,
    })


def top_entities(narratives: list[Narrative], *, k: int = 5) -> list[tuple[str, int]]:
    """Most common entities across all narratives — for diagnostics."""
    counter: Counter[str] = Counter()
    for n in narratives:
        for e in n.entities:
            counter[e] += 1
    return counter.most_common(k)