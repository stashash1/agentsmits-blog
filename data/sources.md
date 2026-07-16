# AI News Sources

> **Управляется через AI Impact Scoring (`scripts/impact_scoring.py`).**
> Tier-1 источники по умолчанию важны; tier-3 — низкая важность.
> Keyword/категорийные бонусы переопределяют tier-base (см. `scripts/impact_scoring.py:TIER_WEIGHTS`).

## Tier 1 — Primary (always important, base importance = 4)

Стратегические AI-лаборатории, релизы моделей, ключевые продукты.

| Источник | URL | RSS/HTML | Статус |
|---|---|---|---|
| **Anthropic** | `https://www.anthropic.com/news/rss.xml` | RSS | ✅ работает |
| **OpenAI** | `https://openai.com/news/rss.xml` | RSS | ✅ работает |
| **Google DeepMind** | `https://deepmind.google/blog/rss.xml` | RSS | ✅ работает |
| **Microsoft AI Blog** | `https://blogs.microsoft.com/ai/feed/` | RSS | ✅ работает |
| **DeepSeek** | `https://deepseek.com/blog` | HTML | ⚠️ нужно проверить фид |
| **xAI (Grok)** | `https://x.ai/blog` | HTML | ⚠️ нужно проверить фид |
| **Mistral AI** | `https://mistral.ai/news/` | HTML | ⚠️ нужно проверить фид |
| **Meta AI** | `https://ai.meta.com/blog/` | HTML | ⚠️ нужно проверить фид |

## Tier 2 — LLM/Agent companies (base importance = 3)

Вторичные LLM-провайдеры и платформы агентов.

| Источник | URL | RSS/HTML | Статус |
|---|---|---|---|
| **Cohere** | `https://cohere.com/blog` | HTML | ⚠️ нужно проверить |
| **Perplexity AI** | `https://www.perplexity.ai/blog` | HTML | ⚠️ нужно проверить |
| **Claude Code** (changelog) | `https://docs.anthropic.com/en/release-notes/claude-code` | HTML | ✅ работает |
| **GitHub Copilot** (changelog) | `https://github.blog/changelog/label/copilot/` | HTML | ✅ работает |
| **Cursor** (changelog) | `https://cursor.com/changelog` | HTML | ✅ работает |
| HuggingFace | `https://huggingface.co/blog/rss.xml` | RSS | ✅ работает |

## Tier 3 — Research, digests, industry (base importance = 2)

Исследования и индустриальные дайджесты; фильтруются дополнительно.

| Источник | URL | Статус |
|---|---|---|
| **arXiv cs.AI** | `https://arxiv.org/rss/cs.AI` | ⚠️ фильтр по AI-impact keywords (см. `scan_sources.py:scan_arxiv_ai`) |
| TechCrunch AI | `https://techcrunch.com/category/artificial-intelligence/feed/` | ✅ работает |
| Google AI Blog | `https://blog.google/technology/ai/rss/` | ✅ работает |
| Stanford HAI | — | ❌ отключён (статический спам) |
| РБК Тренды | `https://trends.rbc.ru/trends/industry/69e87e5f9a7947ca488a8d90` | ❌ отключён (нет свежих статей) |
| Neural Digest | — | ❌ отключён (фид не работает) |
| JustAI | `https://www.just-ai.com/blog/` | ✅ работает |

## Russian-language

| Источник | URL | Статус |
|---|---|---|
| VC.ru AI | `https://vc.ru/search?q=AI+или+агенты` | ⚠️ поиск (нет RSS) |
| JustAI | `https://www.just-ai.com/blog/` | ✅ работает |

---

## Filtering rules

Реализовано в `scripts/impact_scoring.py`:

- **Tier 1**: base = 4, всегда публикуется (или повышается до 5 при release/version keywords)
- **Tier 2**: base = 3, повышается до 4-5 при release/IPO/acquisition keywords
- **Tier 3**: base = 2, **arXiv дополнительно фильтруется** — пропускаются только статьи с AI-impact keywords (модели, capabilities, архитектуры)
- **AI Impact Scoring** добавляет:
  - **+1..+3** за high-impact keywords (`release`, `launch`, `GPT-5`, `Claude 4`, `Gemini`, `IPO`, `acquisition`, `funding`, `agent framework` и т.д.)
  - **+1** за version bonus (явное упоминание `GPT-5.6`, `Claude 4.5`, `Gemini 3`, etc.)
  - **−1..−2** за low-impact keywords (`tutorial`, `how to`, `opinion`, `prediction`, `review`)
- **Итог**: clamp в [1, 5]

## Сканеры и регистрация

21 сканер зарегистрированы в `scripts/scan_sources.py:main()`:

```
Anthropic, OpenAI, DeepMind, HuggingFace, Mistral, Meta AI,
Microsoft AI, Stanford HAI, РБК, Google AI, TechCrunch AI,
JustAI, Neural Digest, arXiv cs.AI,
DeepSeek, xAI, Cohere, Perplexity AI,
Claude Code, GitHub Copilot, Cursor
```

## Dedup оптимизация

Реализована в `scripts/scan_sources.py:filter_already_seen()`:
- Каждый сканер фильтрует уже-опубликованные URL **перед** добавлением в `new_pending`
- Снижает `skipped_dup_count` с 99-115 до ~0 за запуск

## Backfill

`scripts/recompute_importance.py` — утилита для пересчёта importance всех pending items на основе нового AI Impact Scoring:

```bash
python3 scripts/recompute_importance.py --dry-run --verbose  # посмотреть изменения
python3 scripts/recompute_importance.py                       # применить (создаёт backup)
```

## История изменений

- **2026-07-13**: Добавлены AI Impact Scoring, новые источники (DeepSeek/xAI/Cohere/Perplexity/Claude Code/GitHub Copilot/Cursor), arXiv-фильтр, dedup-оптимизация. Отключены Stanford HAI (спам) и РБК (пусто).