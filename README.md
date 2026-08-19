# AI Daily Intelligence — Telegram Mini App

Daily AI-news report app served via GitHub Pages, embedded in a Telegram bot as a Mini App.

- `docs/index.html` — the Mini App (Telegram WebApp-ready, also works in a normal browser)
- `docs/reports/YYYY-MM-DD.json` — one report per day
- `docs/reports/index.json` — manifest of available dates (newest handled client-side)

Report schema:

```json
{
  "date": "2026-08-19",
  "generated_at": "2026-08-19T06:12:00Z",
  "highlights": ["..."],
  "sections": [
    {"org": "OpenAI", "items": [
      {"title": "...", "summary": "...", "url": "https://...", "source": "TechCrunch", "date": "2026-08-18"}
    ]}
  ]
}
```

Reports are generated daily by a Hermes Agent cron job, committed to this repo, and published
automatically by GitHub Pages. Open the app via the bot's menu button or `https://t.me/<bot>/app`.
