# MEMORY.md — Long-Term Memory

_Agent Smith Blog's curated, long-term knowledge. Main-session only._

## Identity

- **Name:** Агент Смит Blog
- **Channel:** [@agentsSmits](https://t.me/agentsSmits) (Telegram)
- **Site:** https://stashash1.github.io/agentsmits-blog (GitHub Pages)
- **Sources:** 21 (Anthropic, OpenAI, DeepMind, HuggingFace, Mistral, Meta, MS, Cohere, Perplexity, Claude Code, Cursor, GitHub Copilot, xAI, DeepSeek, РБК Тренды, VC.ru, TechCrunch, arxiv cs.AI, JustAI, Neural Digest, Google AI Blog)
- **Stack:** Python stdlib only + OpenClaw (Telegram/cron) + GitHub Actions (deploy)
- **Workspace:** `C:\dev\project\agentsmits-blog` (this directory)

## Architecture (one-screen)

```
21 scanners → pending_queue.json → impact_scoring → breakthrough_detector
                                       ↓
                              narrative_store (clusters)
                                       ↓
                  publish_post (TG)  ⇄  publish_article (TG)
                                       ↓
                          generate_site.py → public/index.html
                                       ↓
                  sync_and_deploy.sh → git push → GitHub Pages
```

## Operational state

- **Last commit:** `7a4fbcf Auto-deploy: 2026-08-31 14:10` (~6 days stale)
- **Last pipeline run:** `cluster_narratives.log` 2026-09-06 03:24 (сегодня ночью)
- **Heartbeat:** disabled in OpenClaw agent config → cron сейчас не запускается
- **Pending queue:** 2.4 MB, от 31.08 — есть старый хвост, надо посмотреть актуальность
- **Narratives:** 978 KB JSON, свежий после сегодняшнего cluster run

## Conventions

- Importance scoring: tier source (1–3) × keyword boost (release/GPT-5/Claude 4…)
- Breakthrough = architecture/SOTA/agentic/VLA/TTT/JEPA/MoE patterns; importance boost, banner «🔥 ПРОРЫВ» на сайте
- Quiet hours: 23:00–08:00 МСК (настраивается через ENV)
- Anti-dupe тройной: (1) URL в `published[]`, (2) fingerprint в `recently_sent.json` за 24ч, (3) `publishing: true` лок
- Idempotent паблишер: `publish_post.py` можно гонять руками любое число раз

## Key files (to remember)

| Файл | Назначение |
|---|---|
| `pipeline/_config.py` | Единственное место с путями + ENV (override для новых машин) |
| `pipeline/impact_scoring.py` | importance-формула |
| `pipeline/breakthrough_detector.py` | SOTA/архитектурный детектор |
| `pipeline/narrative_store.py` | Кластеризация новостей в narratives |
| `generate_site.py` | Статический сайт (HTML + RSS) |
| `data/sources.md` | Карта 21 источника по тирам |
| `data/pending_queue.json` | Вход/выход сканеров |
| `data/narratives.json` | Кластеры narrative |
| `bootstrap.sh` | First-run (создаёт data/, проверяет зависимости) |
| `sync_and_deploy.sh` | Regen site + опц. push |

## Lessons learned

_(по мере накопления)_

- **2026-09-06:** Кодировка PowerShell-консоли CP866 — UTF-8 вывод openclaw выглядит как mojibake. Лечить через `$PROFILE` (`[Console]::OutputEncoding = UTF8; chcp 65001`). Параллельно три строки `identity.*` в `~/.openclaw/openclaw.json` прошли двойную `UTF-8↔CP1251` перекодировку → восстановлены по здоровым бэкапам (`last-good`, `migrated`, `bak-pre-tools-fix-*`).
- **2026-09-06:** Реальный проект живёт в `C:\dev\project\agentsmits-blog` (869 файлов, 39 МБ, .git, pipeline, public). Текущий OpenClaw workspace — пустой шаблон (`C:\Users\Admin\dev\project\agentsmits-blog`, 142 файла). Принято решение переключить workspace агента на реальный проект.

## Pending TODOs

- [ ] Переключить workspace агента `agentsmits-blog` в OpenClaw на этот путь
- [ ] Прогнать `pipeline/status.py` и решить по stale pending items
- [ ] Возобновить cron: scan 30m, publish 5/35, rebuild 10/40, daily 21:00 МСК
- [ ] Закоммитить накопившуюся незакоммиченную работу (49k вставок)
- [ ] Разобраться с dreaming state (19 dream entries без details — у `graph-memory` нет эмбеддингов в новой среде?)
