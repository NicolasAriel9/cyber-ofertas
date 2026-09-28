# Cyber Ofertas

Personal web app for Nico + Paula to track deals during Chile's "Cyber" shopping
events (next one: Cyber Monday, Oct 5-7 2026). Aggregates offers scraped from
the official `cyber.cl` event site, lets you compare prices across stores,
favorite products, and get a Telegram alert when a followed product drops in
price.

See `docs/cyber_cl_inspection_notes.md` for scraping notes and
`C:\Users\nreta\.claude\plans\giggly-finding-thimble.md` for the original
architecture plan.

## Layout

- `backend/` -- FastAPI + SQLAlchemy + Alembic. Own venv (`backend/.venv`).
- `frontend/` -- Next.js (App Router, static export). Own `node_modules`.
- `render.yaml` -- Render Blueprint: deploys both plus a scraper cron job.

## Local development

Backend:

```
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe scripts\seed_dev_data.py   # optional: sample data
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Frontend (separate terminal):

```
cd frontend
npm run dev
```

Open http://localhost:3000, enter `http://127.0.0.1:8000` as the backend URL
plus the Basic Auth credentials (defaults in `app/config.py`: `nico` /
`changeme` -- override via a `backend/.env` file, see `.env.example`), then
pick Nico or Paula.

Default local DB is SQLite (`backend/dev.db`, gitignored). Swap to Postgres
(e.g. Neon) by setting `DATABASE_URL` in `backend/.env` -- no code changes
needed.

## What's left before this is fully live (do close to Oct 5, 2026)

Everything below was intentionally deferred because `cyber.cl`'s real catalog
isn't populated yet outside an active event window (confirmed 2026-09-28, see
inspection notes). Do these in order, a few days before the event:

1. **Re-inspect cyber.cl and implement the real parser.**
   Use Chrome (claude-in-chrome or manually) on `https://cyber.cl/cyber/marcas/<category>`
   once the event is live, check the Network tab for how offers are actually
   loaded, then fill in `backend/app/scraper/parser.py::parse_category_html`
   (currently raises `NotImplementedError` on purpose). Update
   `backend/app/scraper/fetch.py::CATEGORY_SLUGS` if the real category slugs
   differ from what was seen during Phase 0.

2. **Push the code to GitHub.** Git is installed locally but no repo exists
   yet:
   ```
   cd "C:\proyectos python\cyber_ofertas"
   git init
   git add .
   git commit -m "Initial Cyber Ofertas scaffold"
   ```
   Then create an empty repo on GitHub and push it there.

3. **Create a free Neon Postgres project** (neon.tech, no credit card) and
   copy its connection string -- you'll paste it as `DATABASE_URL` in step 5.

4. **Create a Telegram bot** via [@BotFather](https://t.me/BotFather)
   (`/newbot`) -- note the bot token and the `@username` it gives you.

5. **Deploy on Render:** dashboard -> New -> Blueprint -> point it at the
   GitHub repo. Render reads `render.yaml` and creates all three services
   (API, scraper cron, static frontend). You'll be prompted for the
   `sync: false` secrets: `DATABASE_URL` (from step 3), `BASIC_AUTH_USER` /
   `BASIC_AUTH_PASSWORD` (pick your own), `TELEGRAM_BOT_TOKEN` /
   `TELEGRAM_BOT_USERNAME` (from step 4).

6. **Register the Telegram webhook** once the API service has a public URL:
   ```
   curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=<API_URL>/telegram/webhook"
   ```

7. **Open the deployed frontend URL from a phone**, log in with the API URL
   + the Basic Auth credentials from step 5, pick Nico or Paula, and check
   that offers, favorites, the comparator, and a forced price-drop alert
   (edit a price in the DB manually to test) all work end-to-end.
