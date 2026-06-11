# AI Агенты Смита — Блог

Автоматический блог на базе новостной рассылки Telegram канала @agentsSmits.

## Структура

```
ai-blog/
├── generate_site.py      # Генератор сайта
├── public/               # Сгенерированный сайт (публикуется на GitHub Pages)
│   ├── index.html        # Лента публикаций
│   ├── articles.html     # Развёрнутые статьи
│   └── rss.xml           # RSS для Яндекс Дзен
├── .github/
│   └── workflows/
│       └── deploy.yml    # CI/CD для GitHub Pages
└── requirements.txt
```

## Настройка GitHub Pages

1. Создай репозиторий на GitHub (например: `agentsmits-blog`)
2. Пушим код:
   ```bash
   git remote add origin https://github.com/ТВОЙ_НИК/agentsmits-blog.git
   git add .
   git commit -m "Initial commit"
   git push -u origin main
   ```
3. В репозитории → Settings → Pages → Source: **GitHub Actions**
4. Добавь telegram-ai-channel как submodule:
   ```bash
   git submodule add https://github.com/ТВОЙ_НИК/telegram-ai-channel.git _data
   ```
5. Обнови workflow: измени `publish_dir` на корень, так как данные будут в `_data/`

## Альтернатива: обновление данных через cron

Каждый раз после публикации в Telegram, cron job обновляет файлы данных и пушит изменения — GitHub Pages автоматически пересобирается.

## Яндекс Дзен

В настройках Дзен (Студия → Свой сайт) привяжи домен и укажи RSS: `https://твойdomain.github.io/agentsmits-blog/rss.xml`