#!/usr/bin/env python3
"""
Breakthrough detector — определяет, является ли статья технологическим
прорывом / новой архитектурой, заслуживающей отдельного формата поста.

Критерии прорывности (для канала про AI-агентов):
1. Новая архитектура (MoE, Mamba, SSM, JEPA, VLA, hybrid, diffusion transformer...)
2. Новая техника обучения / alignment (RLHF, DPO, process rewards, test-time compute)
3. Прорыв в рассуждениях / планировании (CoT, ToT, o1-style, extended thinking)
4. SOTA на ключевом бенчмарке (ARC-AGI, MMLU, MATH, HumanEval, GPQA, ...)
5. AGI/ASI milestone ("surpasses human", "first to", "human-level")
6. Open-source достигает frontier-capability ("first open-source to match GPT-4")
7. Safety / interpretability прорыв (mechanistic interp, scalable oversight)

Эвристика: набираем breakthrough_score на основе архитектурных/технических
маркеров + importance boost. НЕ учитываем как прорыв:
- продуктовый релиз без техники (новый тариф, новый API pricing)
- маркетинговые анонсы
- "improved" без тех.деталей

Использование:
    from breakthrough_detector import detect_breakthrough
    result = detect_breakthrough(item)
    if result['is_breakthrough']:
        # использовать расширенный формат поста
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable


# === Архитектуры / техники (HIGH signal — это прорывы) ===
ARCHITECTURE_PATTERNS = [
    # Transformer alternatives / новые парадигмы
    r"\bMamba\b", r"\bSSM\b", r"\bstate\s+space\s+model",
    r"\bRWKV\b", r"\bRetNet\b", r"\blinear\s+attention",
    r"\bmixture\s+of\s+experts\b", r"\bMoE\b", r"\bMixture[- ]of[- ]Experts",
    r"\bdiffusion\s+transformer\b", r"\bDiT\b",
    r"\bJEPA\b", r"\bV[- ]?JEPA\b", r"\bworld\s+model",
    r"\bhybrid\s+(?:model|architecture|intelligence|approach)\b",
    r"\bhypernetwork\b", r"\bhypernet\b",
    r"\bliquid\s+(?:network|model|neural)\b",
    r"\bneuro-symbolic\b", r"\bneurosymbolic\b",
    r"\bnovel\s+architecture\b", r"\bnew\s+architecture\b",
    r"\bmodel\s+architecture\b",
    r"\bfoundation\s+model\b",
    r"\btest[- ]time\s+compute\b", r"\binference[- ]time\s+scaling\b",
    r"\btest[- ]time\s+training\b", r"\bTTT\b",
    r"\bprocess\s+reward\s+model\b", r"\bPRM\b",
    r"\bself[- ]play\b", r"\bself[- ]improvement\b",
    r"\bconstitutional\s+AI\b", r"\bRLAIF\b", r"\bDPO\b", r"\bORPO\b",
    r"\bmechanistic\s+interpretability\b", r"\bscalable\s+oversight\b",
    r"\bchain[- ]of[- ]thought\b", r"\bCoT\b",
    r"\btree[- ]of[- ]thoughts?\b", r"\bToT\b",
    r"\bchain[- ]of[- ]agents?\b",
    r"\bagentic\s+(?:framework|workflow|reasoning|loop|system)\b",
    r"\bagentic\s+AI\b",
    r"\bmultimodal\s+(?:model|architecture|foundation)\b",
    r"\b(?:new|open|novel)\s+(?:framework|library|toolkit|method|approach|technique|protocol)\b",
    r"\b(?:reasoning|planning|tool[- ]use)\s+(?:model|capability|paradigm)\b",
    r"\bcontext\s+(?:engineering|window\s+extension)\b",
    r"\bmemory\s+(?:augmentation|mechanism|architecture)\b",
    r"\bRAG\b",
    # VLA / embodied / robotics
    r"\bvision[- ]language[- ]action\b", r"\bVLA\b",
    r"\bembodied\s+(?:AI|agent|intelligence)\b",
    r"\bhumanoid\b",
    r"\bmanipulation\s+(?:policy|learning|skill)\b",
    # Compute / hardware breakthroughs
    r"\bnew\s+(?:chip|accelerator|hardware|infrastructure)\b",
    # Научный прорыв / scientific computing frontier
    r"\bscientific\s+(?:computing|discovery|AI)\b",
    r"\bfuses?\s+\w+\s+with\s+\w+",  # гибридная архитектура
]

# === SOTA / milestone markers ===
SOTA_PATTERNS = [
    r"\bSOTA\b", r"\bstate[- ]of[- ]the[- ]art\b",
    r"\bfirst\s+to\b", r"\bmilestone\b",
    r"\b(?:surpasses?|beats?|outperforms?)\s+(?:human|expert|GPT[- ]?4|Claude|Gemini)\b",
    r"\bhuman[- ]level\b", r"\bhuman[- ]equivalent\b",
    r"\bsuperhuman\b",
    r"\b(?:achieves?|reaches?|hits?)\s+(?:AGI|ASI)\b",
    r"\bARC[- ]?AGI\b",
    r"\b(?:MMLU|MATH|HumanEval|GPQA|SWE[- ]?bench|FrontierMath|AIME)\b",
    r"\bnew\s+(?:record|high|score)\b",
    r"\btripled?\s+(?:our\s+)?score",  # конкретный прорыв на бенчмарке
]

# === Open-source frontier (когда open-source догоняет frontier) ===
OPEN_SOURCE_FRONTIER = [
    r"\bfirst\s+open[- ]source\s+(?:to\s+)?match",
    r"\bopen[- ]source\s+(?:frontier|state[- ]of[- ]the[- ]art|SOTA|equivalent|alternative|replacement)\b",
    r"\bopen[- ]weights?\s+(?:frontier|state[- ]of[- ]the[- ]art|matching|equivalent)\b",
]

# === АНТИ-паттерны (это НЕ прорыв — продуктовый/маркетинговый релиз) ===
NON_BREAKTHROUGH_PATTERNS = [
    r"\bpricing\b", r"\bprice\s+cut\b", r"\bnew\s+plan\b", r"\btier\b",
    r"\bAPI\s+(?:update|pricing|rate\s+limit)\b",
    r"\bdiscount\b", r"\bpromo(?:tion)?\b",
    r"\bcase\s+study\b", r"\bcustomer\s+story\b", r"\btestimonial\b",
    r"\binterview\b", r"\bopinion\b", r"\bthoughts?\s+on\b",
    r"\bhiring\b", r"\bjob\b", r"\brecruit",
    r"\bpartnership\s+announce(?:ment)?\b",
    r"\bbrand\b", r"\bmarketing\b", r"\bcampaign\b",
    r"\b(?:access|expansion|availability)\s+for\s+free\b",  # free tier rollout
    r"\bmonthly\s+(?:users|active)\b",  # метрики роста
    r"\bpower\s+(?:line|grid|outage)\b",  # инфраструктурные сбои, не прорыв
    r"\benergy\s+(?:crisis|supply|shortage|outage)\b",
    r"\bcustomer\s+story\b",  # уже есть, но добавлю явно
]

# === Веса паттернов ===
WEIGHT_ARCHITECTURE = 3
WEIGHT_SOTA = 2
WEIGHT_OPEN_SOURCE_FRONTIER = 3
WEIGHT_NON_BREAKTHROUGH = -2


@dataclass(frozen=True)
class BreakthroughResult:
    """Результат детекции прорыва."""
    is_breakthrough: bool
    score: int
    matched_architectures: tuple[str, ...]
    matched_sota: tuple[str, ...]
    matched_open_source: tuple[str, ...]
    matched_non_breakthrough: tuple[str, ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "is_breakthrough": self.is_breakthrough,
            "score": self.score,
            "matched_architectures": list(self.matched_architectures),
            "matched_sota": list(self.matched_sota),
            "matched_open_source": list(self.matched_open_source),
            "matched_non_breakthrough": list(self.matched_non_breakthrough),
            "reasons": list(self.reasons),
        }


def _match_patterns(text: str, patterns: Iterable[str], *, cap: int = 5) -> tuple[str, ...]:
    """Возвращает matched patterns (case-insensitive)."""
    if not text:
        return ()
    matches = []
    text_l = text.lower()
    for p in patterns:
        if re.search(p, text_l, flags=re.IGNORECASE):
            matches.append(p)
            if len(matches) >= cap:
                break
    return tuple(matches)


def _text_of_item(item: dict) -> str:
    """Собирает текст из всех доступных полей item."""
    parts = [
        item.get("title") or "",
        item.get("summary") or "",
    ]
    analysis = item.get("analysis") or {}
    parts.extend([
        analysis.get("translated_title") or "",
        analysis.get("summary") or "",
        analysis.get("agent_impact") or "",
        analysis.get("business_impact") or "",
        analysis.get("it_impact") or "",
    ])
    tags = analysis.get("tags") or []
    parts.extend(tags)
    return " ".join(p for p in parts if p)


def detect_breakthrough(item: dict) -> BreakthroughResult:
    """Главная функция — определить, является ли статья прорывом.

    Score-based подход:
    - architecture_match: +3 за каждый уникальный (cap=5)
    - sota_match: +2 за каждый (cap=3)
    - open_source_frontier: +3 если есть
    - non_breakthrough: -2 за каждый (cap=2)
    - importance boost: +2 для importance=5, +1 для importance=4

    is_breakthrough = score >= 3 AND (architecture OR sota OR open_source)
    (с importance boost — importance=5 может пройти с одним сигналом)
    """
    text = _text_of_item(item)
    if not text.strip():
        return BreakthroughResult(
            is_breakthrough=False, score=0,
            matched_architectures=(), matched_sota=(),
            matched_open_source=(), matched_non_breakthrough=(),
            reasons=("empty_text",),
        )

    archs = _match_patterns(text, ARCHITECTURE_PATTERNS, cap=5)
    sotas = _match_patterns(text, SOTA_PATTERNS, cap=3)
    os = _match_patterns(text, OPEN_SOURCE_FRONTIER, cap=2)
    non_break = _match_patterns(text, NON_BREAKTHROUGH_PATTERNS, cap=2)

    # Importance boost: топ-статьи чаще содержат прорыв
    importance = item.get("importance") or 0
    if importance >= 5:
        importance_boost = 2
    elif importance >= 4:
        importance_boost = 1
    else:
        importance_boost = 0

    score = (
        len(archs) * WEIGHT_ARCHITECTURE
        + len(sotas) * WEIGHT_SOTA
        + (WEIGHT_OPEN_SOURCE_FRONTIER if os else 0)
        + len(non_break) * WEIGHT_NON_BREAKTHROUGH
        + importance_boost
    )

    has_positive = bool(archs or sotas or os)
    is_breakthrough = has_positive and score >= 3

    reasons = []
    if archs:
        reasons.append(f"new_architecture_or_technique:{len(archs)}")
    if sotas:
        reasons.append(f"sota_or_milestone:{len(sotas)}")
    if os:
        reasons.append("open_source_frontier")
    if importance_boost:
        reasons.append(f"importance_boost:+{importance_boost}")
    if non_break:
        reasons.append(f"non_breakthrough_signal:{len(non_break)}")
    if not reasons:
        reasons.append("no_breakthrough_signals")

    return BreakthroughResult(
        is_breakthrough=is_breakthrough,
        score=score,
        matched_architectures=archs,
        matched_sota=sotas,
        matched_open_source=os,
        matched_non_breakthrough=non_break,
        reasons=tuple(reasons),
    )


# === CLI для диагностики ===
def main():
    import json
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from _config import PENDING_QUEUE

    with open(PENDING_QUEUE) as f:
        q = json.load(f)

    pending = q.get("pending", [])
    print(f"Scanning {len(pending)} pending items...")

    candidates = [p for p in pending if (p.get("importance") or 0) >= 3]

    breakthroughs = []
    for p in candidates:
        result = detect_breakthrough(p)
        if result.is_breakthrough:
            breakthroughs.append((p, result))

    print(f"\n🔥 BREAKTHROUGH CANDIDATES: {len(breakthroughs)}\n")
    for p, r in breakthroughs[:20]:
        print(f"  [{p.get('importance')}] {p.get('title', '?')[:80]}")
        print(f"      score={r.score} reasons={r.reasons}")
        print(f"      archs={[a[:30] for a in r.matched_architectures[:3]]}")
        print(f"      sota={[s[:30] for s in r.matched_sota[:2]]}")
        print()


if __name__ == "__main__":
    main()
