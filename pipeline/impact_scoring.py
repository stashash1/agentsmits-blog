"""
AI Impact Scoring — keyword-based + source-tier scoring для новостей.

Используется scan_sources.py для пересчёта importance каждой статьи.

Композиция:
- BASE_IMPORTANCE (от источника)
- SOURCE_TIER_BOOST (по уровню источника)
- KEYWORD_BONUS (по контенту)
- RELEASE_VERSION_BONUS (по упоминанию модели/версии)
- PENALTIES (за нерелевантный контент)
- ФИНАЛЬНЫЙ clamp в [1, 5]
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Iterable

# === Tier-1 источники (всегда важны по умолчанию) ===
# Fuzzy-matching: contains() используется вместо exact match,
# поэтому "Anthropic News", "OpenAI Blog", "Microsoft AI Blog" тоже попадают.
TIER1_KEYWORDS = (
    "anthropic", "openai", "google ai", "google deepmind", "deepmind",
    "microsoft ai", "microsoft research", "ms research",
    "deepseek", "xai", "x.ai", "mistral", "meta ai",
)

# === Tier-2 (компании выпускающие LLM/агентов, но вторичные) ===
TIER2_KEYWORDS = (
    "cohere", "perplexity", "stability", "alibaba qwen", "qwen",
    "huggingface", "hugging face",
    "ai21", "inflection", "character ai",
    "reka", "01-ai", "moonshot", "zhipu", "kimi",
    "github copilot", "cursor", "claude code",
)

# === Tier-3 (исследования, дайджесты — низкая важность) ===
TIER3_KEYWORDS = (
    "arxiv", "stanford hai", "rbc", "vc.ru", "trends.rbc",
    "techcrunch", "the verge", "wired", "justai", "just-ai", "neural digest",
)

# === Tier weights ===
TIER_WEIGHTS = {
    1: 4,  # base 4 (high importance)
    2: 3,  # base 3
    3: 2,  # base 2
}

# === AI Impact keywords (каждый матч +N к importance) ===
HIGH_IMPACT_KEYWORDS = [
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
    # Агентские фичи — критичны для канала про агентов
    r"\bagent(?:s|ic)?\b", r"\bVLA\b", r"\bembodied\b", r"\bmanipulation\b",
    r"\brobot(?:s|ic)?\s+(?:agent|policy|learning|framework)\b",
    r"\bcontext\s+window\b", r"\btoken\s+(?:limit|window|capacity)\b",
    r"\bbenchmark\b", r"\bSOTA\b", r"\bstate[- ]of[- ]the[- ]art\b",
    r"\b(?:human[-\s]level|human[-\s]like|human[-\s]equivalent)\b",
]

MEDIUM_IMPACT_KEYWORDS = [
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

# Negative — обучающие, маркетинговые, мнения
LOW_IMPACT_KEYWORDS = [
    r"\bhow\s+to\b", r"\btutorial\b", r"\bguide\b",
    r"\bbest\s+practices?\b", r"\btips?\b", r"\btricks?\b",
    r"\bexplainer\b", r"\bintroduction\s+to\b", r"\bgetting\s+started\b",
    r"\binterview\b", r"\bopinion\b", r"\bprediction(?:s)?\b",
    r"\bI\s+think\b", r"\bwe\s+should\b",
    r"\breview(?:s|ed)?\b", r"\bcomparison\b",
]

# === News categories (multi-label) ===
NEWS_CATEGORIES = {
    "model_release": [r"\brelease", r"\blaunch", r"\bannounce", r"\bunveil", r"\bnew\s+model"],
    "agent_release": [r"\bagent", r"\bclaude\s+code", r"\bchatgpt\s+agent", r"\bgemini\s+agent", r"\bcopilot"],
    "funding_business": [r"\bIPO\b", r"\bvaluation", r"\bfunding", r"\braise", r"\bacqui(?:r|si)(?:es?|red?|tion)\b", r"\bpartner"],
    "research_paper": [r"\bpaper", r"\barxiv", r"\bbenchmark", r"\bSOTA"],
    "safety_policy": [r"\bsafety", r"\balignment", r"\bregulat", r"\bguardrail"],
    "open_source": [r"\bopen[- ]source", r"\bopen\s+weights"],
    "tutorial": [r"\bhow\s+to", r"\btutorial", r"\bguide"],
}


@dataclass(frozen=True)
class ImpactResult:
    """Результат оценки AI Impact."""
    base: int           # tier weight (2-4)
    tier: int           # 1/2/3
    keyword_bonus: int  # сумма от keywords
    version_bonus: int  # бонус за версию модели
    penalty: int        # штраф
    total: int          # финальный importance (1..5)
    matched_keywords: tuple[str, ...] = field(default_factory=tuple)
    matched_categories: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "base": self.base,
            "tier": self.tier,
            "keyword_bonus": self.keyword_bonus,
            "version_bonus": self.version_bonus,
            "penalty": self.penalty,
            "total": self.total,
            "matched_keywords": list(self.matched_keywords),
            "matched_categories": list(self.matched_categories),
        }


def _normalize_source(source: str) -> str:
    return (source or "").strip().lower()


def get_source_tier(source: str) -> int:
    """Определяет tier источника через fuzzy keyword match. 1 — топ, 2 — вторичный, 3 — остальные."""
    s = _normalize_source(source)
    if not s:
        return 3
    for kw in TIER1_KEYWORDS:
        if kw in s:
            return 1
    for kw in TIER2_KEYWORDS:
        if kw in s:
            return 2
    return 3


def _count_keyword_matches(text: str, patterns: Iterable[str]) -> tuple[int, tuple[str, ...]]:
    """Считает количество уникальных matched patterns в тексте."""
    matches: list[str] = []
    for p in patterns:
        if re.search(p, text, flags=re.IGNORECASE):
            matches.append(p)
    return len(matches), tuple(matches)


def _categorize(text: str) -> tuple[str, ...]:
    """Возвращает список подходящих категорий новости."""
    cats = []
    for cat, patterns in NEWS_CATEGORIES.items():
        for p in patterns:
            if re.search(p, text, flags=re.IGNORECASE):
                cats.append(cat)
                break
    return tuple(cats)


def compute_impact(
    title: str,
    summary: str = "",
    source: str = "",
    *,
    explicit_base: int | None = None,
    tier_override: int | None = None,
) -> ImpactResult:
    """Главная функция — вычислить AI impact importance.

    Args:
        title: заголовок статьи
        summary: саммари/описание (опционально)
        source: источник (например "OpenAI News")
        explicit_base: если задан, переопределяет tier-base (для обратной совместимости)

    Returns:
        ImpactResult с детальной разбивкой скоринга
    """
    text = f"{title} {summary}".strip()

    # Tier
    tier = tier_override if tier_override is not None else get_source_tier(source)
    base = explicit_base if explicit_base is not None else TIER_WEIGHTS[tier]

    # Keywords
    high_count, high_matches = _count_keyword_matches(text, HIGH_IMPACT_KEYWORDS)
    med_count, _ = _count_keyword_matches(text, MEDIUM_IMPACT_KEYWORDS)
    low_count, low_matches = _count_keyword_matches(text, LOW_IMPACT_KEYWORDS)

    keyword_bonus = min(high_count, 3) + (1 if med_count >= 2 else 0)
    penalty = min(low_count, 2)

    # Version bonus: явное упоминание модели с номером версии
    version_pattern = (
        r"\b(?:GPT|Claude|Gemini|Llama|Grok|Mixtral|Mistral|DeepSeek|Qwen|Phi|Sora)"
        r"[\s\-]*\d+(?:\.\d+)?\b"
    )
    version_bonus = 1 if re.search(version_pattern, text, flags=re.IGNORECASE) else 0

    # Итог
    total = base + keyword_bonus + version_bonus - penalty
    total = max(1, min(5, total))

    # Categories
    matched_keywords = high_matches[:5] + tuple(f"-{p}" for p in low_matches[:3])
    matched_categories = _categorize(text)

    return ImpactResult(
        base=base,
        tier=tier,
        keyword_bonus=keyword_bonus,
        version_bonus=version_bonus,
        penalty=penalty,
        total=total,
        matched_keywords=matched_keywords,
        matched_categories=matched_categories,
    )
