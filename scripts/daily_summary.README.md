# daily_summary launchers

PowerShell + bash wrappers for the new `agentsblog daily-summary` subcommand
(replaces legacy `pipeline/daily_summary.py` which required fcntl + the broken
openclaw CLI path).

## What `daily-summary` does

- Queries `articles` (SQLite) for entries with `status='published'` whose
  `published_at` falls within `[target_date 00:00 UTC, target_date+1 00:00 UTC)`.
- Target date defaults to YESTERDAY (UTC) - matches a 21:00 MSK cron.
- No LLM call. Pure stdlib aggregate (by source, top-N by importance,
  breakthroughs).
- Sends via `agentsblog.publishing.direct_api.send_from_env` (urllib, no
  openclaw dependency, no fcntl). Skips if env not set.
- Logs to `events` table (same row shape the old `events.log` had).

## Required env

Either set these in `.env` or in the automation env:

```
AGENTSBLOG_BOT_TOKEN_FILE=C:\path\to\bot.token    # 1-line file with bot token
AGENTSBLOG_TELEGRAM_CHAT_ID=-1001234567890       # numeric chat_id
```

`bot.token` must contain ONLY the bot token (no newline, ~46 chars).
`AGENTSBLOG_TELEGRAM_CHAT_ID` is the NUMERIC chat id of the target channel.
Resolve via @RawDataBot or @JsonDumpBot in Telegram.

## Schedule it (Windows)

```
schtasks /Create /SC DAILY /TN "agentsblog-daily-summary" `
         /TR "pwsh -File C:\Users\Admin\dev\project\agentsmits-blog\scripts\daily_summary.ps1" `
         /ST 21:00
```

## Schedule it (cron)

```
0 18 * * * /opt/agentsblog/scripts/daily_summary.sh
```

## Manual test

```
python -m agentsblog daily-summary --dry-run        # yesterday, just print
python -m agentsblog daily-summary --date 2026-09-07
python -m agentsblog daily-summary --date 2026-09-06 --allow-empty
```
