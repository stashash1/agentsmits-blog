# agentsmits-blog 🤖

Автоматический блог + Telegram-канал про ИИ-агентов и автономные системы.
Коробочное решение: `pip install -e .` → `agentsblog scan` → работает.

```
[ 22 scanners ] ──> [ SQLite + DB ] ──> [ impact + breakthrough + narratives ]
                                          │
                  ┌───────────────────────┴─────────────────────┐
                  ▼                                             ▼
        [ publish_post.py ]                        [ build_site.py ]
                  │                                             │
                  ▼                                             ▼
        Telegram @agentsSmits                      public/ → GitHub Pages
```

## Что внутри

| | |
|---|---|
| **Канал:** | [@agentsSmits](https://t.me/agentsSmits) |
| **Сайт:** | https://stashash1.github.io/agentsmits-blog |
| **Бот:** | [@AgentsSmits_bot](https://t.me/AgentsSmits_bot) (Telegram Bot API через OpenClaw) |
| **Источники:** | 22: Anthropic, OpenAI, DeepMind, HuggingFace, Mistral, Meta, Microsoft, Cohere, Claude Code, Cursor, GitHub Copilot, DeepSeek, xAI, Perplexity, РБК, VC.ru, TechCrunch, arXiv cs.AI, JustAI, Neural Digest, Google AI Blog, Stanford HAI |

## Что нового в v0.2 (рефакторинг)

- **SQLite вместо 14 JSON файлов** — одна правда, транзакции, индексы
- **Типизация через Pydantic** — Article/Source/Narrative с валидацией
- **22 маленьких source-модуля** вместо god-файла 1100 строк (avg 20 строк каждый)
- **Jinja2 шаблоны** вместо inline CSS в Python-строке + вынесенный styles.css
- **`articles.html` — реально отдельная страница** (в старом коде это была копия `index.html`)
- **115 unit-тестов** покрывают парсеры, scoring, dedup, publishing, site builder
- **`agentsblog add-manual`** — ручной постинг через CLI (было только ручное редактирование JSON)
- **`agentsblog serve`** — HTTP API (нужен `pip install -e '.[api]'`)

## Деплой за 3 шага

### 1. Установка

```bash
git clone https://github.com/stashash1/agentsmits-blog.git
cd agentsmits-blog

# Требуется: Python 3.10+ и OpenClaw (для отправки в Telegram)
python3 --version            # должно быть 3.10+
openclaw --version           # ≥ 2026.7
openclaw channels status #   убедись, что telegram подключён

pip install -e .             # editable install (pip ставит в venv)
```

Если `openclaw` нет — Telegram-рассылка работать не будет (сайт и сборщик будут).

### 2. Bootstrap (только на свежей машине)

```bash
./bootstrap.sh
```

Создаёт SQLite БД + проверяет зависимости.

### 3. Подключи GitHub Pages (опционально, для сайта)

```bash
git remote add origin git@github.com:stashash1/agentsmits-blog.git
git push -u origin main

# В GitHub UI: Settings → Pages → Source → GitHub Actions
```

CI workflow в `.github/workflows/deploy.yml` пересобирает сайт при изменении `public/`.

## Использование (CLI)

```bash
# Lifecycle
agentsblog init-db                  # создать SQLite (idempotent)
agentsblog migrate                  # one-shot импорт из legacy JSON

# Pipeline
agentsblog scan [--source openai] [--dry-run] [--limit N]
agentsblog status                   # показать состояние
agentsblog health                   # source health
agentsblog publish [--dry-run] [--limit N] [--allow-during-quiet]
agentsblog publish-article --id <article_id> [--dry-run]

# Manual entry (NEW — missing in legacy code)
agentsblog add-manual \
    --title "Anthropic releases Claude 4" \
    --url "https://www.anthropic.com/news/claude-4" \
    --source anthropic \
    --agent-impact "Tool use is dramatically improved" \
    --business-impact "Enterprise adoption grows" \
    --importance 5

# Site
agentsblog build-site               # регенерация public/

# HTTP API (нужен pip install -e '.[api]')
agentsblog serve [--port 8080]

# Sources
agentsblog sources list
agentsblog sources disable <id>
agentsblog sources enable <id>
```

## Cron / scheduled tasks

Проект **не запускается сам по себе** — нужно настроить расписание.

### Вариант A: OpenClaw cron (рекомендуется)

```bash
# Сбор новостей — каждые 30 минут
openclaw cron add "scan-sources" \
    --every 30m \
    --command "agentsblog scan"

# Публикация в Telegram — каждый час в :05 и :35
openclaw cron add "publish-posts" \
    --cron "5,35 * * * *" \
    --command "agentsblog publish"

# Пересборка сайта — каждый час в :10
openclaw cron add "rebuild-site" \
    --cron "10 * * * *" \
    --command "PUSH=1 ./sync_and_deploy.sh"
```

### Вариант B: системный cron

```bash
# /etc/cron.d/agentsmits-blog
*/30 * * * *  stas  cd /home/stas/dev/project/agentsmits-blog && agentsblog scan >> data/events.log 2>&1
5,35 * * * *  stas  cd /home/stas/dev/project/agentsmits-blog && agentsblog publish >> data/events.log 2>&1
10 * * * *    stas  cd /home/stas/dev/project/agentsmits-blog && PUSH=1 ./sync_and_deploy.sh >> data/events.log 2>&1
```

## Конфигурация через ENV

Все ENV начинаются с `AGENTSBLOG_`. Полный список — в `.env.example`.

| ENV | Default | Что делает |
|---|---|---|
| `AGENTSBLOG_TELEGRAM_ACCOUNT` | `default` | OpenClaw Telegram account id |
| `AGENTSBLOG_TELEGRAM_TARGET`  | `@agentsSmits` | Telegram target (channel) |
| `AGENTSBLOG_TELEGRAM_CHANNEL` | `telegram` | OpenClaw channel name |
| `AGENTSBLOG_TELEGRAM_PARSE_MODE` | `HTML` | HTML / MARKDOWN / None |
| `AGENTSBLOG_QUIET_HOURS_START` | `23` | С какого МСК-час не публиковать |
| `AGENTSBLOG_QUIET_HOURS_END`   | `8`  | С какого часа снова публиковать |
| `AGENTSBLOG_TZ_OFFSET`         | `3`  | UTC offset (МСК = 3) |
| `AGENTSBLOG_MAX_PUBLISH_PER_RUN` | `5` | Лимит публикаций за один прогон |
| `AGENTSBLOG_DATA_DIR`          | `<project>/data` | Override пути к данным |
| `AGENTSBLOG_ROOT`              | auto-detect | Полностью override project root |
| `AGENTSBLOG_API_HOST` / `_PORT` / `_TOKEN` | `127.0.0.1` / `8765` / `` | HTTP API (serve) |

## Архитектура

```
agentsblog/                      # основной пакет
├── config.py                    # Settings (pydantic-settings)
├── models.py                    # Article, Source, Narrative, ...
├── db.py                        # SQLite слой + repository functions
├── migration.py                 # legacy JSON → SQLite
├── scanner.py                   # scan orchestrator
├── cli.py + cli_*.py            # argparse subcommands
├── sources/                     # 22 source modules (avg 20 строк)
│   ├── base.py                  # SourceBase, RssSource, HtmlSource, ChangelogMdSource
│   ├── registry.py              # @register decorator
│   └── {anthropic,openai,...}.py
├── scoring/                     # pure functions
│   ├── impact.py                # compute_impact() → ImportanceResult
│   └── breakthrough.py          # detect_breakthrough() → BreakthroughResult
├── clustering/
│   └── narratives.py            # create/attach/find
├── publishing/                  # 6 модулей вместо god-файла
│   ├── telegram.py              # openclaw CLI wrapper
│   ├── dedup.py                 # 3-уровневый dedup
│   ├── decay.py                 # soft age decay
│   ├── formatter.py             # 4 формата (standard/breakthrough/digest)
│   └── publisher.py             # orchestrator (~200 строк)
├── site/                        # Jinja2 templates + RSS
│   ├── builder.py               # reads DB → renders 3 distinct pages
│   ├── rss.py                   # RSS 2.0 generator
│   ├── templates/               # base.html.j2, feed.html.j2, articles.html.j2
│   └── assets/styles.css
└── api/                         # FastAPI server (optional)

tests/                           # 115 unit-тестов (все green)
├── conftest.py                  # tmp_settings, db, make_article factories
├── test_models.py               # 8 tests
├── test_db.py                   # 13 tests
├── test_config.py               # 5 tests
├── test_utils.py                # 6 tests
├── test_smoke.py                # 4 tests
├── test_sources.py              # 18 tests (RSS parsing, ID gen)
├── test_scanner.py              # 5 tests (orchestrator, dedup)
├── test_scoring.py              # 26 tests (impact + breakthrough + narratives)
├── test_publisher.py            # 22 tests (formatter + dedup + orchestrator)
└── test_site.py                 # 8 tests (build + structural difference)
```

## Как добавить новый источник

1. Создай `agentsblog/sources/{your_source}.py`:
   ```python
   from agentsblog.models import SourceKind
   from agentsblog.sources.base import Registry, RssSource
   from agentsblog.sources.registry import add_meta

   @Registry.register("my_source")
   class MySource(RssSource):
       feed_url = "https://example.com/feed.xml"
       cutoff_days = 14

   add_meta(id="my_source", name="My Source",
            url="https://example.com/feed.xml",
            kind=SourceKind.RSS, tier=2)
   ```

2. Добавь в `agentsblog/sources/registry.py::register_all()`.

3. Добавь запись в `data/sources.md`.

4. Проверь: `agentsblog scan --source my_source`.

## License

Personal / non-commercial.