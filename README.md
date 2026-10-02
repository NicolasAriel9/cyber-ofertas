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

Step 1 (the scraper) is done; the rest needs accounts only you can create.

1. ~~**Re-inspect cyber.cl and implement the real parser.**~~ Done 2026-10-01.
   cyber.cl turned out to be a brand directory with a public JSON API
   (`app.cyber.cl/api/`) but **no products or prices** -- see
   `docs/cyber_cl_inspection_notes.md`. The scraper now reads cyber.cl for the
   official categories and participating stores, and pulls the offers from
   per-store scrapers (`backend/app/scraper/stores/`): Falabella, Paris,
   Ripley, Hites, Sodimac, Easy and Jumbo. Run it locally with:
   ```
   cd backend
   set FORCE_SCRAPE=1
   .venv\Scripts\python.exe -m app.scraper.cyber_scraper
   ```
   Knobs (env vars): `SCRAPE_MAX_PAGES` (pages per department, default 10),
   `SCRAPE_STORES` (e.g. `falabella,paris`), `SCRAPE_REQUEST_DELAY` (seconds
   between requests to the same host, default 1).

2. **Push the code to GitHub.** The local git repo already exists with an
   initial commit (done 2026-09-28). Just create an empty repo on GitHub and
   push:
   ```
   cd "C:\proyectos python\cyber_ofertas"
   git remote add origin <your-new-github-repo-url>
   git push -u origin master
   ```
   (Local git identity was set repo-local, not global -- `git config
   user.name`/`user.email` inside this repo only. Set a global one if you'd
   rather not repeat this per-project.)

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
