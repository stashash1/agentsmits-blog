---
name: post-illustrator
description: "Генерирует иллюстрацию к посту канала 'Агенты Смита' с поп-культурными пасхалками и отсылками. Публикует в канал."
---

# Post Illustrator

Генерирует тематическую иллюстрацию после каждого поста в канале @agentsSmits.

## Workflow

1. Принимает тему/содержание поста
2. Придумывает поп-культурную отсылку (из разных эпох) которая отражает суть
3. Генерирует изображение через image_generate
4. Публикует в @agentsSmits

## Примеры пасхалок

| Пост | Отсылка |
|------|---------|
| AGI countdown | Fallout terminal / Nuclear war clock |
| AI agents replacing humans | Matrix red pill |
| Open source AI | Linux penguin |
| Robot revolution | Terminator / I, Robot |
| AI safety | Asimov laws |
| Productivity boost | Wall Street bull |
| AI hype | Tulip mania |
| Anthropic | Matrix Agent Smith |

## Правила

- Отсылка должна быть узнаваема но не 1:1 копия
- Фон как Matrix (зелёный code rain)
- Агент Смита всегда яркий на переднем плане
- Публиковать после поста с коротким описанием пасхалки

## Использование

```
Сгенерируй иллюстрацию к посту: [тема поста]
```

Или автоматически после публикации поста.