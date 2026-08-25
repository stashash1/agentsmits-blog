---
name: channel-publisher
description: "Читает pending_queue.json, готовит пост по шаблону и публикует в @agentsSmits. Генерирует картинку для постов меняющих счётчик AGI."
---

# Channel Publisher

Публикует посты в канал @agentsSmits на основе очереди из pending_queue.json.

## Workflow

1. Читает `pending_queue.json`
2. Читает `selection_queue.json`
3. Если есть pending items:
   - **ОБЯЗАТЕЛЬНО для КАЖДОГО pending поста:** проверь — его id уже есть в published[].id → удали из pending (уже опубликован, пропусти)
   - Проверь: статья есть в selection_queue со status="published" (уже выбрана для deep) — удали из pending
   - Проверь: статья уже сохранена на сайт (id в data/current.json) — пропусти
     - Прочитай /home/stas/dev/project/agentsmits-bot/data/current.json и проверь что id этого поста отсутствует в списке `posts[].id`
   - **Пометь элемент как in_progress** (добавь `publishing: true`) и сохрани pending_queue.json — это защита от дублей при реконнекте
   - Возьми самый важный (importance=5 приоритетнее, потом по дате)
   - Готовит пост по шаблону (краткий)
   - **Проверка перед публикацией:**
     - Орфография, пунктуация
     - Убрать иероглифы / китайские символы / нечитаемые символы → заменить на русский
   - Публикует в @agentsSmits
   - Обновляет счётчик AGI если нужно
   - Генерирует картинку если счётчик изменился
   - **Только после успешной публикации:** перенеси в published[] и удали из pending[]
   - **Сохрани контент на сайт:** вызови `python3 /home/stas/dev/project/agentsmits-bot/scripts/storage_manager.py add '<post_json>'` где post_json содержит:
     - `id`, `source`, `title`, `url`, `published_at`, и `content` (полный отформатированный текст по шаблону)
   - **Ротация архива:** вызови `python3 /home/stas/dev/project/agentsmits-bot/scripts/storage_manager.py rotate` — переместит посты старше 7 дней в archive.json
   - **Декремент AGI-счётчика:** уменьши `current_days` в зависимости от важности новости:
     - `importance: 5` → `-2` дня
     - `importance: 4` → `-1` день
     - `importance: 3` → `-0.5` дня
     - `importance: 1-2` → без изменений
     - Обнови `last_update`
     - Если `current_days` уходит в минус — зафиксируй 0
   - Если публикация не удалась — сними `publishing: false`
4. Если нет pending — ничего не делает

**Глубокий анализ (selection queue):**
- Для importance=5 статей из selection_queue — отдельная публикация с развёрнутым анализом
- Перед публикацией проверить: если id уже есть в published[] — это ОК, публикуем развёрнутую версию (краткая была, теперь будет детальная)
- Заголовок: «Давайте обсудим очень важное событие» + далее название статьи
- Текст-заготовка меняется по смыслу статьи
- Публикуется ТОЛЬКО после разрешения пользователя

## Breakthrough-формат (прорывные статьи)

Статьи, которые детектирует `pipeline/breakthrough_detector.py` как прорыв (новая архитектура / SOTA / agentic AI / VLA / TTT / MoE / JEPA / hybrid / open-source frontier), публикуются в **отдельном формате** с пометкой. Логика:

1. Детектор скорит `item` по паттернам архитектур и SOTA, плюс importance boost (+2 для importance=5, +1 для importance=4), минус анти-паттерны (pricing, case study, energy crisis)
2. `is_breakthrough = score >= 3 AND есть позитивный сигнал (architecture/sota/open-source)`
3. Breakthrough идут ПЕРВЫМИ в сортировке (даже с importance=1-2 получают auto-boost до 3 для прохождения QW4-фильтра)
4. На сайте получают бейдж «🔥 ПРОРЫВ» в hero-card (оранжевый border + акцентный заголовок)
5. В `pending_queue.json.published[]` сохраняются `is_breakthrough`, `breakthrough_score`, `breakthrough_reasons`, `bt_importance_boost`
6. В `current.json` (для сайта) — те же поля, чтобы бейдж отрендерился через `generate_site.py`

**Шаблон breakthrough-поста (вместо стандартного):**

```
🤖 Агенты Смита
[Дата]

🔥 ВАЖНАЯ СТАТЬЯ • ПРОРЫВ

📰 [Название]
🔗 [URL]

📝 [Summary]

🧬 Что нового (прорыв):
• [Архитектура/техника: <человекочитаемая метка>]
• SOTA / milestone: [если есть]
• Open-source достигает frontier-уровня [если есть]

📊 Влияние на разработку агентов:
[Agent impact]

💼 Влияние на бизнес:
[Business impact]

� Влияние на IT-индустрию:
[IT impact]

⏰ ДО AGI: ~XXXX дней [░░░░░░░░░░] ~X%

� Это меняет правила игры.
→ https://stashash1.github.io/agentsmits-blog
```

**Когда НЕ помечать как breakthrough:**
- Продуктовый релиз без техники (новый pricing, новый тариф, case study, customer story)
- Маркетинговый анонс без тех.деталей
- Статьи с `importance` 1-2 И без architecture/sota/open-source сигналов (даже с importance_boost не пройдут)

## Release digest (QW-3, 2026-08-25)

Несколько релизов одного источника объединяются в один пост-дайджест:

- **Claude Code 2.1.218, 2.1.222, 2.1.237, 2.1.240, 2.1.241** → один пост «Дайджест релизов Claude Code: версии 2.1.241 → 2.1.218 — 5 шт (период ...)»
- **GitHub Copilot changelog** (несколько записей в неделю) → один пост-дайджест с перечислением всех записей
- **Cursor changelog** → один пост-дайджест

Детект релиз-паттерна по 3 сигналам (любой один триггерит):
1. Title содержит версию (`v?N.N(.N)?`) + ключевые слова (release/update/changelog)
2. URL содержит `/changelog/`, `/release`, `/releases/`, `CHANGELOG`
3. Source ∈ {Claude Code, GitHub Copilot, Cursor}

Группировка по source. Минимум 2 элемента для объединения.

**После успешной публикации дайджеста:**
- Все underlying items помечаются в `published[]` с флагом `is_digest_member: True` и `digest_id: <id дайджеста>`
- Удаляются из `pending[]`
- Повторная публикация underlying невозможна

Реализация: `pipeline/release_grouper.py` (group_releases + make_digest_post), интеграция в `pipeline/publish_post.py:main()`.

**Шаблон release-дайджеста:**

```
🤖 Агенты Смита
[Дата]

📦 ДАЙДЖЕСТ РЕЛИЗОВ

📰 [Название: «Дайджест релизов X: версии A → B — N шт (период ...)»]
🔗 [URL главного релиза]

• [Перевод релиза 1] (date) — [1-предложение саммари]
• [Перевод релиза 2] (date) — [1-предложение саммари]
...

Релизы в дайджесте:
• [Title релиза] — [URL]
• [Title релиза] — [URL]
... [max 5 URL в посте]

📊 Влияние на разработку агентов:
[agent_impact из наиболее важного underlying]

💼 Влияние на бизнес:
[business_impact]

� Влияние на IT-индустрию:
[it_impact]

⏰ ДО AGI: ~XXXX дней [░░░░░░░░░░] ~X%

🚀 Несколько релизов одним постом — держим канал плотным.
→ https://stashash1.github.io/agentsmits-blog
```

## Шаблон поста

```
🤖 Агенты Смита
[Дата]

📰 Тема: [Название]
🔗 [URL]

📊 Влияние на разработку агентов:
[内容]

💼 Влияние на бизнес:
[内容]

🖥 Влияние на IT-индустрию:
[内容]


Итого:
[Вывод]

⏰ ДО AGI: ~XXXX дней [░░░░░░░░░░] ~X%

🚀 Полетели.
→ stashash1.github.io/agentsmits-blog
```

## Картинки

Генерировать ЕСЛИ счётчик AGI изменился:
- Стиль: любой (смешной, страшный, добрый)
- Пасхалки: поп-культура всех эпох
- Отражает суть статьи
- Фон: Matrix code rain или тематический

Примеры пасхалок:
- AGI countdown → Fallout vault boy, ядерные часы
- AI agents → Matrix red pill, солярис
- Robots → Терминатор, Я, робот
- Open source → Linux пингвин, опенсорс
- IPO/money → Волл-стрит бык, пузырь тюльпанов
- Safety → 3 закона Азимова
- Productivity → Форрест Гамп, Rocky
- Hardware/chips → Оружие будущего, Железный человек

## Файл очереди

```json
{
  "sources": [...],
  "pending": [
    {id, source, title, url, summary, importance, date}
  ],
  "published": [...],
  "agi_counter": {
    "base_days": 1460,
    "current_days": 30,
    "last_update": "2026-06-12"
  }
}
```

**Формула:** `current_days` = сколько дней осталось до AGI (отображается в посте как `base_days - current_days` для обратного отсчёта, но в посте показываем `current_days`). Прогресс-бар: `current_days / base_days * 100%`.

## Защита от дублей при реконнекте

**Критично:** перед началом публикации элемент должен получить `publishing: true`. При следующем запуске (в т.ч. после Telegram-reconnect drain):
- Пропускать все элементы с `publishing: true` — они уже в процессе
- После успешной публикации — удалять из pending и добавлять в published
- При ошибке — снимать `publishing: false`

Это гарантирует: даже если Telegram отвалился и переподключился во время публикации, повторный запуск не отправит уже отправленные посты.