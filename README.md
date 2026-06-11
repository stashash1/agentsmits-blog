# AI Агенты Смита — Блог 🤖

Автоматический блог на базе новостной рассылки Telegram канала @agentsSmits.

## Структура

| Файл | Описание |
|------|----------|
| `generate_site.py` | Генератор сайта (Python) |
| `public/index.html` | Лента — краткие посты |
| `public/articles.html` | Статьи — развёрнутый анализ |
| `public/rss.xml` | RSS для Яндекс Дзен |
| `.github/workflows/deploy.yml` | CI/CD для GitHub Pages |

## Как запустить (3 шага)

### 1. Создай GitHub репозиторий

На GitHub создай новый репозиторий (например: `agentsmits-blog`).

### 2. Подключи remote и запушь

```bash
cd /home/stas/.openclaw/workspace/projects/ai-blog
git remote add origin https://github.com/ТВОЙ_НИК/agentsmits-blog.git
git push -u origin main
```

### 3. Включи GitHub Pages

В репозитории: **Settings → Pages → Source → GitHub Actions**

---

## Что происходит автоматически

| Время | Действие |
|-------|----------|
| Каждый час (в :05) | Publisher публикует посты в Telegram |
| Каждый час (в :10) | Blog пересобирается и пушится на GitHub Pages |
| Яндекс Дзен | Читает RSS `rss.xml` каждые ~15 минут |

## Подключение Яндекс Дзен

1. Открой [Студию Дзен](https://dzen.ru/media/zen/login)
2. Настройки → Свой сайт → добавь домен `https://ТВОЙ_НИК.github.io/agentsmits-blog`
3. Подтверди права на домен (HTML-файл или метатег)
4. Настройка трансляции → укажи RSS: `https://ТВОЙ_НИК.github.io/agentsmits-blog/rss.xml`
5. Отправь на проверку

## Ручной деплой

```bash
cd /home/stas/.openclaw/workspace/projects/ai-blog
./sync_and_deploy.sh
```

## Текущий статус

- ✅ Генератор работает
- ✅ Лента: 5 постов
- ✅ Статьи: 1 статья  
- ✅ RSS: 6 записей
- ⏳ GitHub Pages: в процессе настройки