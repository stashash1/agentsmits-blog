"""Tests for scoring — impact + breakthrough + entity extraction."""
from __future__ import annotations

from agentsblog.clustering.narratives import (
    attach_to_narrative,
    create_narrative,
    find_matching_narrative,
)
from agentsblog.models import Article
from agentsblog.scoring.breakthrough import detect_breakthrough
from agentsblog.scoring.impact import (
    compute_impact,
    extract_entities,
    extract_entities_from_item,
    get_source_tier,
)


# ── Tier detection ─────────────────────────────────────────────────

def test_get_source_tier_anthropic_is_1():
    assert get_source_tier("Anthropic News") == 1


def test_get_source_tier_huggingface_is_2():
    assert get_source_tier("HuggingFace Blog") == 2


def test_get_source_tier_techcrunch_is_3():
    assert get_source_tier("TechCrunch AI") == 3


def test_get_source_tier_unknown_is_3():
    assert get_source_tier("Random Blog") == 3


def test_get_source_tier_empty():
    assert get_source_tier("") == 3
    assert get_source_tier(None) == 3  # type: ignore[arg-type]


# ── Entity extraction ──────────────────────────────────────────────

def test_extract_entities_finds_models():
    ents = extract_entities("OpenAI releases GPT-5 with reasoning")
    assert "openai" in ents
    assert "gpt-5" in ents
    assert "reasoning" in ents


def test_extract_entities_sorted_unique():
    ents = extract_entities("Anthropic Claude Claude Claude 4")
    assert ents == sorted(set(ents))


def test_extract_entities_empty():
    assert extract_entities("") == []
    assert extract_entities("no entities here at all") == []


def test_extract_entities_from_article():
    a = Article(
        id="x", source_id="openai",
        title="GPT-5 release", url="https://e.com",
        date="2026-09-06",
        summary="Anthropic also announces Claude 4",
    )
    ents = extract_entities_from_item(a)
    # Entities come from title/summary text only (not source_id)
    assert "gpt-5" in ents
    assert "anthropic" in ents
    assert "claude" in ents


# ── Impact scoring ─────────────────────────────────────────────────

def test_compute_impact_anthropic_release():
    result = compute_impact(
        title="Anthropic releases Claude 4 with agentic capabilities",
        summary="New release with breakthrough agent framework",
        source="Anthropic News",
    )
    assert result.tier == 1
    assert result.base == 4
    # version bonus + keyword bonus should push it up
    assert result.total >= 4
    assert result.version_bonus >= 1


def test_compute_impact_techcrunch_tutorial_penalized():
    result = compute_impact(
        title="How to use GPT-4: a tutorial for beginners",
        summary="This is a guide for getting started with AI",
        source="TechCrunch AI",
    )
    assert result.tier == 3
    # Should be penalized for "how to" + "tutorial" + "guide"
    assert result.penalty >= 1
    assert result.total <= 3


def test_compute_impact_clamped_to_max_5():
    """Even with every keyword, importance cannot exceed 5."""
    result = compute_impact(
        title="GPT-5 Claude 4 Gemini 3 release launch announce",
        summary="AGI ASI superintelligence breakthrough SOTA",
        source="Anthropic",
    )
    assert result.total == 5


def test_compute_impact_clamped_to_min_1():
    result = compute_impact(
        title="Generic blog post about something",
        summary="How to tutorial guide tips tricks review comparison",
        source="Random Blog",
    )
    assert result.total >= 1


def test_compute_impact_explicit_base_override():
    result = compute_impact("Title", source="Anthropic", explicit_base=5)
    assert result.base == 5


def test_compute_impact_categories():
    result = compute_impact(
        title="OpenAI announces IPO at $1B valuation",
        summary="Massive funding round",
        source="OpenAI",
    )
    assert "funding_business" in result.matched_categories
    assert "model_release" in result.matched_categories


# ── Breakthrough detection ─────────────────────────────────────────

def test_detect_breakthrough_architecture_is_breakthrough():
    a = Article(
        id="x", source_id="openai", title="Mamba architecture breakthrough",
        url="https://e.com", date="",
        summary="New MoE with diffusion transformer and VLA capabilities",
    )
    r = detect_breakthrough(a)
    assert r.is_breakthrough is True
    assert len(r.matched_architectures) >= 1


def test_detect_breakthrough_sota_is_breakthrough():
    a = Article(
        id="x", source_id="openai", title="GPT-5 achieves AGI on MMLU",
        url="https://e.com", date="",
        summary="First to surpass human-expert level on SWE-bench",
    )
    r = detect_breakthrough(a)
    assert r.is_breakthrough is True
    assert len(r.matched_sota) >= 1


def test_detect_breakthrough_pricing_is_not():
    a = Article(
        id="x", source_id="openai", title="OpenAI announces new pricing plan",
        url="https://e.com", date="",
        summary="Discount on API rate limit",
        importance=5,
    )
    r = detect_breakthrough(a)
    assert r.is_breakthrough is False
    assert "non_breakthrough_signal" in " ".join(r.reasons)


def test_detect_breakthrough_empty_text():
    r = detect_breakthrough({"title": "", "summary": ""})
    assert r.is_breakthrough is False
    assert "empty_text" in r.reasons


def test_detect_breakthrough_importance_boost():
    """importance=4 boosts score by +1 — can swing borderline items."""
    a = Article(
        id="x", source_id="openai",
        title="GPT-5 launches",
        url="https://e.com", date="",
        summary="Just a release",
        importance=4,
    )
    r = detect_breakthrough(a)
    # GPT-5 doesn't match architecture patterns, but version_bonus isn't here
    # either. With importance_boost +1 and SOTA markers (none here), still false.
    # But the score went up by 1 — verify.
    assert "importance_boost:+1" in r.reasons


def test_detect_breakthrough_open_source_frontier():
    a = Article(
        id="x", source_id="meta",
        title="Llama 4 is first open-source to match GPT-5",
        url="https://e.com", date="",
        summary="Open-source frontier SOTA",
    )
    r = detect_breakthrough(a)
    assert r.is_breakthrough is True
    assert "open_source_frontier" in r.reasons


# ── Narrative clustering ───────────────────────────────────────────

def test_create_narrative_basic():
    a = Article(
        id="x", source_id="openai",
        title="GPT-5 release", url="https://e.com", date="",
        summary="OpenAI announces new model",
    )
    n = create_narrative(a, narrative_id="n-001",
                         entities=["gpt-5", "openai"])
    assert n.id == "n-001"
    assert n.title == "GPT-5 release"
    assert len(n.items) == 1
    assert n.items[0].role == "primary"
    assert "gpt-5" in n.entities


def test_find_matching_narrative_jaccard_match():
    a1 = Article(id="x1", source_id="openai", title="GPT-5",
                 url="https://e.com", date="",
                 summary="OpenAI GPT-5 release")
    n = create_narrative(a1, narrative_id="n-1",
                         entities=["gpt-5", "openai"])

    a2 = Article(id="x2", source_id="openai", title="GPT-5 capabilities",
                 url="https://e.com/2", date="",
                 summary="OpenAI GPT-5 update")
    ents = extract_entities_from_item(a2)
    match = find_matching_narrative(ents, [n])
    assert match is not None
    assert match.id == "n-1"


def test_find_matching_narrative_no_match_below_threshold():
    n = create_narrative(
        Article(id="x", source_id="openai", title="GPT-5", url="https://e.com", date=""),
        narrative_id="n-1",
        entities=["gpt-5", "openai"],
    )
    ents = ["cohere", "rag", "transformer"]  # generic only
    match = find_matching_narrative(ents, [n])
    # generic-only entities filter out, no match
    assert match is None


def test_attach_to_narrative_extends_entities():
    a1 = Article(id="x1", source_id="openai", title="GPT-5",
                 url="https://e.com", date="",
                 summary="OpenAI release", importance=5)
    n = create_narrative(a1, narrative_id="n-1", entities=["gpt-5", "openai"])

    # Use specific (non-generic) entities: sonnet, opus are model names
    a2 = Article(id="x2", source_id="anthropic",
                 title="Anthropic partners with OpenAI on GPT-5 Sonnet",
                 url="https://e.com/2", date="",
                 summary="Claude Sonnet and Opus integrate with OpenAI",
                 importance=4)
    n2 = attach_to_narrative(n, a2)
    assert len(n2.items) == 2
    # New specific entities should be merged in
    assert "anthropic" in n2.entities
    assert "sonnet" in n2.entities or "opus" in n2.entities
    assert n2.importance_max == 5


def test_attach_to_narrative_dedup():
    a1 = Article(id="x1", source_id="openai", title="GPT-5",
                 url="https://e.com", date="")
    n = create_narrative(a1, narrative_id="n-1", entities=["gpt-5"])

    # Attach same article twice
    n2 = attach_to_narrative(n, a1)
    n3 = attach_to_narrative(n2, a1)
    assert len(n3.items) == 1  # deduped