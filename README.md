# agentsmits-blog 🤖

Автоматический блог + Telegram-канал про ИИ-агентов и автономные системы.  
Коробочное решение: `git clone` → один скрипт → полный пайплайн работает.

```
[ news-collector ] ──> [ pending_queue.json ] ──> [ telegram-publisher ] ──> @agentsSmits
                                                  └─> [ generate_site.py ]   ──> github-pages blog
```

## Что внутри

| | |
|---|---|
| **Канал:** | [@agentsSmits](https://t.me/agentsSmits) |
| **Сайт:** | https://stashash1.github.io/agentsmits-blog |
| **Бот:** | [@AgentsSmits_bot](https://t.me/AgentsSmits_bot) (Telegram Bot API через OpenClaw) |
| **Источники:** | 21 источник: Anthropic, OpenAI, DeepMind, HuggingFace, Mistral, Meta, Microsoft, Cohere, Perplexity, Claude Code, Cursor, GitHub Copilot, xAI, DeepSeek, РБК Тренды, VC.ru, TechCrunch, arxiv cs.AI, JustAI, Neural Digest, Google AI Blog |

## Деплой за 3 шага

### 1. Подготовка

```bash
git clone https://github.com/stashash1/agentsmits-blog.git
cd agentsmits-blog

# Требуется: Python 3.10+ (только stdlib) и OpenClaw (для отправки в Telegram)
python3 --version            # должно быть 3.10+
openclaw --version           # ≥ 2026.7
openclaw channels status     # убедись, что telegram подключён
```

Если `openclaw` нет — Telegram-рассылка работать не будет (сайт и сборщик — будут).

### 2. Bootstrap (только на свежей машине)

```bash
./bootstrap.sh
```

Создаёт `data/` со всеми очередями и сайтовым хранилищем, проверяет зависимости.

### 3. Подключи GitHub Pages (опционально, для сайта)

```bash
git remote add origin git@github.com:stashash1/agentsmits-blog.git
git push -u origin main

# В GitHub UI: Settings → Pages → Source → GitHub Actions
```

CI workflow в `.github/workflows/deploy.yml` пересобирает сайт при изменении `public/`.

## Использование (CLI)

```bash
# Однократный скан всех 21 источников
python3 pipeline/scan_sources.py

# Что в очереди?
python3 pipeline/status.py

# Опубликовать одно сообщение в Telegram (подчиняется quiet hours)
python3 pipeline/publish_post.py

# Опубликовать статью (с развёрнутым анализом)
python3 pipeline/publish_article.py

# Пересобрать сайт
python3 generate_site.py

# Пересчитать importance для всех pending items
python3 pipeline/recompute_importance.py --dry-run --verbose

# Сгенерировать article-черновик через LLM (нужен MCP/LLM)
python3 pipeline/analyze_pending.py
```

## Cron / scheduled tasks

Проект **не запускается сам по себе** — нужно настроить расписание. Готовые рецепты:

### Вариант A: OpenClaw cron (рекомендуется)

```bash
# Сбор новостей — каждые 30 минут
openclaw cron add "scan-sources" \
    --every 30m \
    --command "python3 /path/to/agentsmits-blog/pipeline/scan_sources.py"

# Публикация в Telegram — каждый час в :05 и :35
openclaw cron add "publish-posts" \
    --cron "5,35 * * * *" \
    --command "python3 /path/to/agentsmits-blog/pipeline/publish_post.py"

# Пересборка сайта + (опционально) push — каждый час в :10
openclaw cron add "rebuild-site" \
    --cron "10,40 * * * *" \
    --command "PUSH=1 /path/to/agentsmits-blog/sync_and_deploy.sh"

# Дневной саммари — 21:00 МСК
openclaw cron add "daily-summary" \
    --cron "0 21 * * *" \
    --command "python3 /path/to/agentsmits-blog/pipeline/daily_summary.py"
```

### Вариант B: системный cron

```bash
# /etc/cron.d/agentsmits-blog
*/30 * * * *  stas  cd /home/stas/dev/project/agentsmits-blog && python3 pipeline/scan_sources.py >> data/events.log 2>&1
5,35 * * * *  stas  cd /home/stas/dev/project/agentsmits-blog && python3 pipeline/publish_post.py >> data/events.log 2>&1
10,40 * * * * stas  cd /home/stas/dev/project/agentsmits-blog && PUSH=1 ./sync_and_deploy.sh >> data/events.log 2>&1
0 21 * * *   stas  cd /home/stas/dev/project/agentsmits-blog && python3 pipeline/daily_summary.py >> data/events.log 2>&1
```

## Конфигурация через ENV

| ENV | Default | Что делает |
|---|---|---|
| `AGENTSBLOG_TELEGRAM_ACCOUNT` | `agentsmits` | OpenClaw Telegram account id |
| `AGENTSBLOG_TELEGRAM_TARGET`  | `@agentsSmits` | Telegram target (channel) |
| `AGENTSBLOG_TELEGRAM_CHANNEL` | `telegram` | OpenClaw channel name |
| `AGENTSBLOG_QUIET_HOURS_START` | `23` | С какой МСК-час не публиковать |
| `AGENTSBLOG_QUIET_HOURS_END`   | `8`  | С какого часа снова публиковать |
| `AGENTSBLOG_TZ_OFFSET`         | `3`  | UTC offset для quiet-hours tz (МСК = 3) |
| `AGENTSBLOG_DATA_DIR`          | `<project>/data` | Override пути к данным |
| `AGENTSBLOG_ROOT`              | auto-detect | Полностью override project root |

## Структура

```
agentsmits-blog/
├── data/                           # всё мутабельное состояние (queues + logs)
│   ├── pending_queue.json          # вход/выход сканера
│   ├── selection_queue.json        # importance=5 → ручной разбор
│   ├── articles_queue.json         # готовые articles (дайджесты)
│   ├── current.json                # посты этой недели (для сайта)
│   ├── archive.json                # посты старше 7 дней (для сайта)
│   ├── recently_sent.json          # anti-dupe для Telegram
│   ├── sent_messages.json          # история отправок
│   ├── metrics.json                # централизованные метрики
│   ├── events.log                  # полный event log (JSON Lines)
│   ├── telegram_audit.log          # каждое отправленное сообщение
│   ├── daily_summaries.json
│   ├── sync_status.json
│   └── sources.md                  # описание источников и тиров
│
├── pipeline/                       # Python-пайплайн (только stdlib)
│   ├── _config.py                  # пути + ENV-конфиг
│   ├── scan_sources.py             # 21 сканер (Anthropic, OpenAI, DeepMind, ...)
│   ├── publish_post.py             # TG-паблишер кратких постов
│   ├── publish_article.py          # TG-паблишер статей
│   ├── analyze_pending.py          # LLM-классификация importance
│   ├── recompute_importance.py     # backfill importance через impact_scoring
│   ├── daily_summary.py            # дневной итог в канал
│   ├── generate_weekly_digest.py   # еженедельный digest
│   ├── impact_scoring.py           # модуль importance
│   ├── metrics.py                  # централизованный логгер
│   ├── status.py                   # отчёт о состоянии очередей
│   ├── dedup_audit.py              # проверка дедупликации
│   ├── validate_sync.py            # валидатор согласованности
│   └── fix_ids.py                  # утилита для fix ID-truncation
│
├── public/                         # сгенерированный сайт
│   ├── index.html                  # лента
│   ├── articles.html               # статьи
│   └── rss.xml                     # RSS (для Яндекс Дзен)
│
├── scripts/                        # deployment glue (сейчас пусто, для будущих утилит)
│
├── skills/                         # OpenClaw skills (опциональные, для LLM-агента)
│   ├── channel-publisher/SKILL.md  # спека паблишера
│   ├── post-illustrator/SKILL.md   # генерация иллюстраций с пасхалками
│   └── spell-check/SKILL.md        # проверка орфографии
│
├── tests/                          # юнит-тесты (заглушка)
│
├── generate_site.py                # генератор статического сайта
├── bootstrap.sh                    # deploy fresh
├── sync_and_deploy.sh              # regen site + (опц.) push
├── sync-to-repo.sh                 # legacy hourly sync
├── requirements.txt                # пусто (только stdlib)
├── .github/workflows/deploy.yml    # GitHub Pages CI
└── README.md                       # ← ты здесь
```

## Как настроить новые источники

Открой `data/sources.md` — там карта 21 источника по 3 тирам. Сканеры в `pipeline/scan_sources.py`:

```python
sources = [
    ('Anthropic', scan_anthropic),
    ('OpenAI', scan_openai),
    ...
]
```

Чтобы добавить новый:

1. Написать функцию `scan_my_site(queue)` рядом с другими
2. Добавить в список `sources = [...]` в `main()`
3. Заполнить entry в `sources.md`

## Архитектурные заметки

- **`pipeline/_config.py` — единственное место, где живут пути.** Все скрипты импортируют `PENDING_QUEUE`, `DATA_DIR`, `TELEGRAM_ACCOUNT`. Если нужно развернуть на новой машине — переопредели через ENV.
- **Idempotent паблишер.** `publish_post.py` можно запускать руками хоть 100 раз — дедупликация через `recently_sent.json` и `publishing: true` маркеры.
- **Quiet hours защита.** Не публикуем 23:00–08:00 МСК (настраивается). В это время скрипт оставляет post для следующего тика.
- **Anti-dupe стратегия тройная**: (1) URL в `published[]`, (2) URL fingerprint в `recently_sent.json` за 24ч, (3) `publishing: true` лок при отправке.
- **AI Impact Scoring** — отдельный модуль (`impact_scoring.py`) пересчитывает importance по тиру источника + ключевым словам (`release`, `GPT-5`, `Claude 4`, etc.). Запускать после изменения ключевых слов: `python3 pipeline/recompute_importance.py`.

## License

Personal / non-commercial.
