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