"""AI Impact Scoring — keyword + source-tier based importance.

Pure function. Given (title, summary, source) → ImpactResult.
Composable: BASE + KEYWORD_BONUS + VERSION_BONUS - PENALTY, clamped to [1,5].

Replaces pipeline/impact_scoring.py with cleaner types + tests.
"""
from __future__ import annotations

import re
from typing import Iterable

from agentsblog.models import ImpactResult, SourceKind


# ── Tier keywords (fuzzy contains() match) ─────────────────────────

TIER1_KEYWORDS = (
    "anthropic", "openai", "google ai", "google deepmind", "deepmind",
    "microsoft ai", "microsoft research", "ms research",
    "deepseek", "xai", "x.ai", "mistral", "meta ai",
)

TIER2_KEYWORDS = (
    "cohere", "perplexity", "stability", "alibaba qwen", "qwen",
    "huggingface", "hugging face", "ai21", "inflection", "character ai",
    "reka", "01-ai", "moonshot", "zhipu", "kimi",
    "github copilot", "cursor", "claude code",
)

TIER3_KEYWORDS = (
    "arxiv", "stanford hai", "rbc", "vc.ru", "trends.rbc",
    "techcrunch", "the verge", "wired", "justai", "just-ai", "neural digest",
)

TIER_WEIGHTS = {1: 4, 2: 3, 3: 2}


def get_source_tier(source: str | None) -> int:
    """Map source name → tier (1/2/3). Unknown → 3."""
    s = (source or "").strip().lower()
    if not s:
        return 3
    for kw in TIER1_KEYWORDS:
        if kw in s:
            return 1
    for kw in TIER2_KEYWORDS:
        if kw in s:
            return 2
    return 3


# ── Known entities (used both for scoring + narrative clustering) ───

KNOWN_ENTITIES: set[str] = {
    # Companies
    "anthropic", "openai", "google", "deepmind", "microsoft", "meta",
    "deepseek", "xai", "x.ai", "mistral", "cohere", "perplexity",
    "huggingface", "hugging face", "nvidia", "apple", "amazon",
    "alibaba", "bytedance", "baidu", "ibm", "salesforce", "oracle",
    "tencent", "samsung", "tesla", "stability", "inflection",
    "01-ai", "moonshot", "zhipu", "kimi", "reka", "ai21",
    "character ai", "elevenlabs", "suno", "udio", "runway",
    # Products / models
    "gpt-5", "gpt-4", "gpt-3", "chatgpt", "claude", "sonnet", "opus",
    "haiku", "gemini", "llama", "grok", "mistral-large", "mixtral",
    "deepseek-r1", "deepseek-v3", "qwen", "phi", "copilot", "cursor",
    "claude code", "dall-e", "sora", "veo", "whisper", "embedding",
    # Researchers
    "altman", "amodei", "sutskever", "hinton", "lecun", "fei-fei li",
    "karpathy", "ilya", "musk", "andrej karpathy", "yann lecun",
    "geoffrey hinton", "sam altman", "dario amodei", "elon musk",
    # Tech concepts
    "agent", "agents", "agentic", "rag", "fine-tuning", "rlhf", "rlaif",
    "embedding", "transformer", "diffusion", "reasoning",
    "multimodal", "vision", "speech", "context window", "open source",
    "open-source", "open weights", "sota", "benchmark",
    "robot", "robotics", "embodied", "autonomous", "agi", "asi",
    "superintelligence", "alignment", "safety", "regulation", "policy",
    "chain-of-thought", "function calling", "tool use",
    # Business events
    "ipo", "acquisition", "funding", "valuation", "investment",
    "merger", "partnership", "revenue",
}


def extract_entities(text: str) -> list[str]:
    """Sorted unique entities from text (lowercase substring match)."""
    if not text:
        return []
    text_l = text.lower()
    return sorted(kw for kw in KNOWN_ENTITIES if kw in text_l)


def extract_entities_from_item(item) -> list[str]:
    """Extract from an Article-like model."""
    parts = [
        getattr(item, "title", "") or "",
        getattr(item, "summary", "") or "",
    ]
    analysis = getattr(item, "analysis", None) or {}
    if hasattr(analysis, "translated_title"):
        parts.append(analysis.translated_title or "")
        parts.append(analysis.summary or "")
        tags = analysis.tags or []
    else:
        # dict-style
        parts.append(analysis.get("translated_title", "") or "")
        parts.append(analysis.get("summary", "") or "")
        tags = analysis.get("tags", []) or []
    parts.extend(tags)
    return extract_entities(" ".join(parts))


# ── Keyword scoring ────────────────────────────────────────────────

HIGH_IMPACT_PATTERNS = [
    r"\bGPT-?\d(?:\.\d+)?(?:o\d?|o(?:pro|mini))?\b",
    r"\bClaude\s*(?:Opus|Sonnet|Haiku)?\s*\d(?:\.\d+)?\b",
    r"\bGemini\s*(?:\d(?:\.\d+)?|Ultra|Pro|Flash|Lite)\b",
    r"\bLlama\s*\d(?:\.\d+)?\b", r"\bGrok\s*\d(?:\.\d+)?\b",
    r"\bMixtral\b", r"\bMistral\s*(?:Large|Medium|Small|7B|Nemo|NeMo|Codestral)\b",
    r"\bDeepSeek\s*[RV]?\d*(?:\.\d+)?\b", r"\bQwen\s*\d(?:\.\d+)?\b",
    r"\bPhi\s*-?\d+\b",
    r"\bAGI\b", r"\bASI\b", r"\bsuperintelligence\b",
    r"\bagent(?:s|ic)?\s+(?:framework|sdk|platform|launch|release|protocol|standard)\b",
    r"\brelease(?:d|s)?\b", r"\blaunch(?:es|ed)?\b",
    r"\bannounce(?:s|d|ment)?\b", r"\bintroduce(?:s|d)?\b",
    r"\bunveil(?:s|ed)?\b", r"\bdebut(?:s|ed)?\b",
    r"\bnew\s+(?:model|api|feature|capability|tool|product)\b",
    r"\bIPO\b", r"\bvaluation\b", r"\bfunding\b", r"\braise(?:s|d)?\s+\$",
    r"\bacqui(?:r|si)(?:es?|red?|tion)\b", r"\bpartner(?:ship)?s?\b",
    r"\bM&A\b", r"\bmerger\b", r"\bbuyout\b",
    r"\bopen[- ]source\b", r"\bopen\s+weights\b",
    r"\bagent(?:s|ic)?\b", r"\bVLA\b", r"\bembodied\b", r"\bmanipulation\b",
    r"\brobot(?:s|ic)?\s+(?:agent|policy|learning|framework)\b",
    r"\bcontext\s+window\b", r"\btoken\s+(?:limit|window|capacity)\b",
    r"\bbenchmark\b", r"\bSOTA\b", r"\bstate[- ]of[- ]the[- ]art\b",
    r"\b(?:human[-\s]level|human[-\s]like|human[-\s]equivalent)\b",
]

MEDIUM_IMPACT_PATTERNS = [
    r"\bupdate(?:s|d)?\b", r"\bimprove(?:s|d|ment)?\b",
    r"\bupgrade(?:s|d)?\b", r"\bfaster\b", r"\bcheaper\b",
    r"\befficient(?:cy)?\b", r"\boptimi[sz](?:e|ed|ation)\b",
    r"\bbetter\s+than\b", r"\boutperforms?\b", r"\bbeats?\b",
    r"\bmodel\s+(?:card|weights|parameters)\b",
    r"\btraining\s+(?:data|cost|run)\b", r"\bfine[- ]tune(?:s|d)?\b",
    r"\bRLHF\b", r"\bRLAIF\b", r"\bconstitutional\s+AI\b",
    r"\bsafety\b", r"\balignment\b", r"\bguardrails?\b",
    r"\bmultimodal\b", r"\bvision\s+model\b", r"\btext[- ]to[- ](?:video|image|speech)\b",
    r"\bagent\b", r"\btool\s*use\b", r"\bfunction\s+calling\b",
    r"\breason(?:ing)?\b", r"\bchain[- ]of[- ]thought\b",
    r"\bmemory\b", r"\bcontext\s+engineering\b",
    r"\bRAG\b", r"\bretrieval\b",
]

LOW_IMPACT_PATTERNS = [
    r"\bhow\s+to\b", r"\btutorial\b", r"\bguide\b",
    r"\bbest\s+practices?\b", r"\btips?\b", r"\btricks?\b",
    r"\bexplainer\b", r"\bintroduction\s+to\b", r"\bgetting\s+started\b",
    r"\binterview\b", r"\bopinion\b", r"\bprediction(?:s)?\b",
    r"\bI\s+think\b", r"\bwe\s+should\b",
    r"\breview(?:s|ed)?\b", r"\bcomparison\b",
]

# News category multi-label
NEWS_CATEGORIES: dict[str, list[str]] = {
    "model_release": [r"\brelease", r"\blaunch", r"\bannounce", r"\bunveil", r"\bnew\s+model"],
    "agent_release": [r"\bagent", r"\bclaude\s+code", r"\bchatgpt\s+agent", r"\bgemini\s+agent", r"\bcopilot"],
    "funding_business": [r"\bIPO\b", r"\bvaluation", r"\bfunding", r"\braise", r"\bacqui(?:r|si)(?:es?|red?|tion)\b", r"\bpartner"],
    "research_paper": [r"\bpaper", r"\barxiv", r"\bbenchmark", r"\bSOTA"],
    "safety_policy": [r"\bsafety", r"\balignment", r"\bregulat", r"\bguardrail"],
    "open_source": [r"\bopen[- ]source", r"\bopen\s+weights"],
    "tutorial": [r"\bhow\s+to", r"\btutorial", r"\bguide"],
}


# ── Main scoring function ──────────────────────────────────────────

_VERSION_RE = re.compile(
    r"\b(?:GPT|Claude|Gemini|Llama|Grok|Mixtral|Mistral|DeepSeek|Qwen|Phi|Sora)"
    r"[\s\-]*\d+(?:\.\d+)?\b",
    re.IGNORECASE,
)


def _count_matches(text: str, patterns: Iterable[str]) -> tuple[int, tuple[str, ...]]:
    matches: list[str] = []
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            matches.append(p)
    return len(matches), tuple(matches)


def _categorize(text: str) -> tuple[str, ...]:
    cats: list[str] = []
    for cat, patterns in NEWS_CATEGORIES.items():
        for p in patterns:
            if re.search(p, text, re.IGNORECASE):
                cats.append(cat)
                break
    return tuple(cats)


# Major-version pattern: same as _VERSION_RE but captures the actual number
# so we can distinguish "major" (whole-number bump) from patch (small bump).
_VERSION_MAJOR_RE = re.compile(
    r"\b(?:GPT|Claude|Gemini|Llama|Grok|Mistral|DeepSeek|Qwen|Phi|Sora)"
    r"[\s\-]*(?P<major>\d+)(?:\.(?P<minor>\d+))?\b",
    re.IGNORECASE,
)

# Speculation / soft-news markers — penalize hard.
SPECULATION_PATTERNS = [
    r"\brumor\b", r"\brumour\b", r"\breportedly\b",
    r"\bmight\b", r"\bmay\b", r"\bcould\b",
    r"\bleak\b", r"\bleaked\b", r"\bunconfirmed\b",
    r"\bspeculation\b", r"\bspeculates?\b", r"\banticipat\w+\b",
    r"\bpossibly\b", r"\bperhaps\b",
]

# Tier-1 source boost multipliers. Tier-1 (OpenAI, Anthropic, DeepMind,
# Google AI, DeepSeek, xAI, Mistral) gets full weight; tier-2 gets 1.0;
# tier-3 (aggregators, blogs) gets dampened.
TIER_MULTIPLIER = {1: 1.2, 2: 1.0, 3: 0.85}

# Boost for novelty language (vs incremental updates).
NOVELTY_BOOST_PATTERNS = [
    r"\bnew\b", r"\bintroduc\w+\b", r"\bdebut\b", r"\bunveil\w*\b",
    r"\bannounc\w+\b", r"\blaunch\w*\b", r"\brelease[ds]?\b",
    r"\bgroundbreaking\b", r"\brevolution\w*\b", r"\bparadigm\b",
    r"\bbreakthrough\b", r"\bmilestone\b",
]

# Penalty for incremental chatter that isn't a release.
INCREMENTAL_PATTERNS = [
    r"\bupdate(?:s|d)?\b", r"\bpatch\b", r"\bbug[\s-]?fix\b",
    r"\bhotfix\b", r"\bminor\s+(?:update|release|change)\b",
    r"\bweekly\s+digest\b", r"\bchangelog\b",
]


def _is_release(text: str) -> bool:
    """Heuristic: text looks like a versioned release / changelog."""
    t = text.lower()
    if _VERSION_RE.search(t):
        return True
    if re.search(r"\bchangelog\b", t):
        return True
    if re.search(r"\bv?\d+\.\d+(\.\d+)?\s*(?:release|update)\b", t):
        return True
    return False


def _major_bump(text: str) -> bool:
    """True if a version is mentioned and it's a whole-number major release."""
    m = _VERSION_MAJOR_RE.search(text)
    if not m:
        return False
    return m.group("minor") is None


def compute_impact(
    title: str,
    summary: str = "",
    source: str = "",
    *,
    explicit_base: int | None = None,
    tier_override: int | None = None,
) -> ImpactResult:
    """Compute AI impact score in [1, 5] (refined v2).

    Improvements over v1:
      - Source tier multiplier (tier-1 sources weighted up)
      - Speculation penalty (rumor/might/could → -1)
      - Major-version bump bonus (+1 for GPT-6, Claude 4, etc.)
      - Incremental chatter penalty (-1 for "patch", "weekly digest")
      - Novelty boost (+1 for "new"/"introduces"/"unveils")
    """
    text = f"{title} {summary}".strip()
    tier = tier_override if tier_override is not None else get_source_tier(source)
    base = explicit_base if explicit_base is not None else TIER_WEIGHTS[tier]

    high_n, high_matches = _count_matches(text, HIGH_IMPACT_PATTERNS)
    med_n, _ = _count_matches(text, MEDIUM_IMPACT_PATTERNS)
    low_n, low_matches = _count_matches(text, LOW_IMPACT_PATTERNS)
    spec_n, spec_matches = _count_matches(text, SPECULATION_PATTERNS)
    incr_n, incr_matches = _count_matches(text, INCREMENTAL_PATTERNS)
    nov_n, nov_matches = _count_matches(text, NOVELTY_BOOST_PATTERNS)

    adjusted_base = base * TIER_MULTIPLIER.get(tier, 1.0)

    keyword_bonus = min(high_n, 3) + (1 if med_n >= 2 else 0)
    version_bonus = 1 if _VERSION_RE.search(text) else 0
    major_bonus = 1 if _major_bump(text) else 0
    novelty_bonus = 1 if nov_n >= 1 else 0
    penalty = min(low_n, 2) + min(spec_n, 2) + min(incr_n, 2)

    # Floor (not round) so tier-1 base 4 with 1.2 multiplier doesn't
    # immediately clamp to 5 — leaves room for legitimate bonuses.
    floored_base = int(adjusted_base) if adjusted_base == int(adjusted_base) else int(adjusted_base)

    raw = floored_base + keyword_bonus + version_bonus + major_bonus + novelty_bonus - penalty

    # Hard cap: pure how-to/tutorial/interview without release keywords => 1.
    # Don't publish "How to use Claude Code" at importance 4.
    is_pure_howto = (
        low_n >= 1 and high_n == 0 and med_n == 0
        and not _VERSION_RE.search(text)
    )
    if is_pure_howto:
        raw = min(raw, 1)

    total = max(1, min(5, int(round(raw))))

    matched_keywords = (
        high_matches[:5]
        + tuple(f"+{p}" for p in nov_matches[:2])
        + tuple(f"-{p}" for p in (low_matches + spec_matches + incr_matches)[:4])
    )
    if _is_release(text):
        matched_keywords = matched_keywords + ("release:1",)

    return ImpactResult(
        base=base,
        tier=tier,
        keyword_bonus=keyword_bonus,
        version_bonus=version_bonus,
        penalty=penalty,
        total=total,
        matched_keywords=matched_keywords,
        matched_categories=_categorize(text),
    )


def is_release_item(article) -> bool:
    """True if article's title/summary look like a versioned release.

    Used by publisher to group multiple releases from the same source.
    """
    text = f"{getattr(article, 'title', '')} {getattr(article, 'summary', '')}"
    return _is_release(text)
