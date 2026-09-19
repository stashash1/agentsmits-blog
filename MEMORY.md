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

- **2026-09-15:** Telegram-сеть вернулась сама (WinError 10065 → OK на 149.154.167.99:443). Не нужно было ничего чинить со стороны AmneziaVPN — daemon всё время был Running. Просто периодический сетевой блок, который сам рассосался.
- **2026-09-15:** Task Scheduler / schtasks с SYSTEM — оба требуют full admin elevation в shell, не хватает даже `elevated=on`. Fallback: встроить pre-step в существующий cron-wrapper (`cron_publish.ps1` теперь делает `analyze --limit 8` перед `publish --limit 5`).
- **2026-09-15:** qwen3:8b нестабилен на JSON output для длинных arxiv-саммари (~50% parse failures). В cron — лимит 8 (≈5-10 мин), не 50. Альтернатива — qwen3:14b (есть в Ollama), должна быть стабильнее. `_llm_analyze.py` теперь принимает `--limit`.
- **2026-09-15:** `heuristic_analyze` — критический fallback без LLM. Шаблонные RU impact + EN title, но `agent_impact != NULL` → publish не блокируется. Использовать как drain при недоступности Ollama.

- **2026-09-06:** Кодировка PowerShell-консоли CP866 — UTF-8 вывод openclaw выглядит как mojibake. Лечить через `$PROFILE` (`[Console]::OutputEncoding = UTF8; chcp 65001`). Параллельно три строки `identity.*` в `~/.openclaw/openclaw.json` прошли двойную `UTF-8↔CP1251` перекодировку → восстановлены по здоровым бэкапам (`last-good`, `migrated`, `bak-pre-tools-fix-*`).
- **2026-09-06:** Реальный проект живёт в `C:\dev\project\agentsmits-blog` (869 файлов, 39 МБ, .git, pipeline, public). Текущий OpenClaw workspace — пустой шаблон (`C:\Users\Admin\dev\project\agentsmits-blog`, 142 файла). Принято решение переключить workspace агента на реальный проект.
- **2026-09-14:** Publisher-блокер «no analysis» — это поле `agent_impact`, проверка `models.py:131-134`. Заполняется `_llm_analyze.py` через Ollama. Скрипт **не** входит в cron-cluster (`15 */6 * * *`) — это scan+cluster, без analyze. Исторически analyze запускался вручную или отдельной задачей, которая потерялась.
- **2026-09-14:** Telegram «404 / timeout» на этой машине — DNS+hosts ОК, демон `AmneziaVPN-service` жив (PID был 5252), но TCP до `149.154.167.99` не идёт. Лечить reconnect AmneziaVPN-клиента, не перезапуском демона. Не код.
- **2026-09-14:** `heuristic_analyze.py` — штатный fallback для drain'а очереди, шаблоны по 7 категориям (`model_release`, `agent_release`, `funding_business`, `research_paper`, `safety_policy`, `open_source`, `tutorial`). Использовать когда LLM/Ollama недоступен.
- **2026-09-14:** `python` в PowerShell PATH нет. Рабочий бинарь: `C:\Users\Admin\python312\python.exe` (второй дубль в `AppData\Local\Programs\Python\Python312\`). Запуск каждой команды: `[Console]::OutputEncoding=UTF8; chcp 65001; $env:PYTHONIOENCODING='utf-8'; & 'C:\Users\Admin\python312\python.exe' -m agentsblog ...`.

## Pending TODOs

- [ ] Переключить workspace агента `agentsmits-blog` в OpenClaw на этот путь
- [x] Возобновить cron: scan 30m, publish 5/35, rebuild 10/40 — **работает** (с 14.09 15:27)
- [x] Решить по stale pending items — **сделано** (heuristic drain 144→136, LLM upgrade)
- [x] Вернуть Telegram-доставку — **сделано** (сеть вернулась, 7 постов ушло msg_id 1617+)
- [ ] **Новое:** зарегистрировать `agentsblog-analyze` task из admin shell (workaround уже работает через cron_publish.ps1)
- [ ] **Новое:** удалить старую `agentsblog-daily-summary` task (exit 127 на удалённом `pipeline/daily_summary.py`)
- [ ] **Новое:** дать bot token + chat_id для daily-summary (см. `memory/2026-09-15-0944.md`)
- [ ] Закоммитить правки 15.09: `_llm_analyze.py` (+argparse), `cron_publish.ps1` (+analyze step), `cron_analyze.ps1` (новый)
- [ ] Разобраться с dreaming state (19 dream entries без details — у `graph-memory` нет эмбеддингов в новой среде?)
