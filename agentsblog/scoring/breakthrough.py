"""Breakthrough detector — is this article a real tech breakthrough?

Pure function. Given an Article-like item → BreakthroughResult.
Uses score-based heuristics: architectures + SOTA + open-source frontier,
discounted by non-breakthrough signals (pricing, partnerships, etc.).
"""
from __future__ import annotations

import re
from typing import Iterable

from agentsblog.models import Article, BreakthroughResult


# ── Pattern groups ─────────────────────────────────────────────────

ARCHITECTURE_PATTERNS = [
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
    r"\bvision[- ]language[- ]action\b", r"\bVLA\b",
    r"\bembodied\s+(?:AI|agent|intelligence)\b",
    r"\bhumanoid\b",
    r"\bmanipulation\s+(?:policy|learning|skill)\b",
    r"\bnew\s+(?:chip|accelerator|hardware|infrastructure)\b",
    r"\bscientific\s+(?:computing|discovery|AI)\b",
    r"\bfuses?\s+\w+\s+with\s+\w+",
]

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
    r"\btripled?\s+(?:our\s+)?score",
]

OPEN_SOURCE_FRONTIER = [
    r"\bfirst\s+open[- ]source\s+(?:to\s+)?match",
    r"\bopen[- ]source\s+(?:frontier|state[- ]of[- ]the[- ]art|SOTA|equivalent|alternative|replacement)\b",
    r"\bopen[- ]weights?\s+(?:frontier|state[- ]of[- ]the[- ]art|matching|equivalent)\b",
]

NON_BREAKTHROUGH_PATTERNS = [
    r"\bpricing\b", r"\bprice\s+cut\b", r"\bnew\s+plan\b", r"\btier\b",
    r"\bAPI\s+(?:update|pricing|rate\s+limit)\b",
    r"\bdiscount\b", r"\bpromo(?:tion)?\b",
    r"\bcase\s+study\b", r"\bcustomer\s+story\b", r"\btestimonial\b",
    r"\binterview\b", r"\bopinion\b", r"\bthoughts?\s+on\b",
    r"\bhiring\b", r"\bjob\b", r"\brecruit",
    r"\bpartnership\s+announce(?:ment)?\b",
    r"\bbrand\b", r"\bmarketing\b", r"\bcampaign\b",
    r"\b(?:access|expansion|availability)\s+for\s+free\b",
    r"\bmonthly\s+(?:users|active)\b",
    r"\bpower\s+(?:line|grid|outage)\b",
    r"\benergy\s+(?:crisis|supply|shortage|outage)\b",
    r"\bcustomer\s+story\b",
]

WEIGHT_ARCHITECTURE = 3
WEIGHT_SOTA = 2
WEIGHT_OPEN_SOURCE_FRONTIER = 3
WEIGHT_NON_BREAKTHROUGH = -2


# ── Helpers ────────────────────────────────────────────────────────

def _match_patterns(text: str, patterns: Iterable[str], *, cap: int = 5) -> tuple[str, ...]:
    if not text:
        return ()
    text_l = text.lower()
    out: list[str] = []
    for p in patterns:
        if re.search(p, text_l, re.IGNORECASE):
            out.append(p)
            if len(out) >= cap:
                break
    return tuple(out)


def _text_of_item(item) -> str:
    """Concatenate every text field of an Article (or dict)."""
    parts: list[str] = []
    if isinstance(item, dict):
        parts.append(item.get("title", "") or "")
        parts.append(item.get("summary", "") or "")
        analysis = item.get("analysis") or {}
        parts.append(analysis.get("translated_title", "") or "")
        parts.append(analysis.get("summary", "") or "")
        parts.append(analysis.get("agent_impact", "") or "")
        parts.append(analysis.get("business_impact", "") or "")
        parts.append(analysis.get("it_impact", "") or "")
        parts.extend(analysis.get("tags", []) or [])
    else:
        parts.append(getattr(item, "title", "") or "")
        parts.append(getattr(item, "summary", "") or "")
        parts.append(getattr(item, "translated_title", "") or "")
        parts.append(getattr(item, "agent_impact", "") or "")
        parts.append(getattr(item, "business_impact", "") or "")
        parts.append(getattr(item, "it_impact", "") or "")
        parts.extend(getattr(item, "tags", []) or [])
    return " ".join(p for p in parts if p)


# ── Main detector ──────────────────────────────────────────────────

def detect_breakthrough(item) -> BreakthroughResult:
    """Determine if an article is a genuine breakthrough.

    is_breakthrough = score >= 3 AND (architecture OR sota OR open_source)
    """
    text = _text_of_item(item)
    if not text.strip():
        return BreakthroughResult(
            is_breakthrough=False, score=0,
            matched_architectures=(), matched_sota=(),
            matched_open_source=(), matched_non_breakthrough=(),
            reasons=("empty_text",),
        )

    archs = _match_patterns(text, ARCHITECTURE_PATTERNS)
    sotas = _match_patterns(text, SOTA_PATTERNS)
    os = _match_patterns(text, OPEN_SOURCE_FRONTIER)
    non_break = _match_patterns(text, NON_BREAKTHROUGH_PATTERNS)

    importance = getattr(item, "importance", 0) or 0
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

    reasons: list[str] = []
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