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
   Ripley, Hites, Sodimac, Easy, Jumbo and Mercado Libre (its public
   /ofertas page), plus ~200 brand-owned stores (Under Armour, Columbia,
   Levi's, New Balance, Sony...) read through their platform's public catalog
   (Shopify, VTEX or Magento, see `stores/brand_sites.py`). The brand list is
   generated from cyber.cl -- refresh it before each event with
   `python scripts/discover_brand_sites.py`. Run it locally with:
   ```
   cd backend
   set FORCE_SCRAPE=1
   .venv\Scripts\python.exe -m app.scraper.cyber_scraper
   ```
   Knobs (env vars): `SCRAPE_MAX_PAGES` (pages per department, default 10),
   `SCRAPE_STORES` (store slugs or job groups, e.g. `falabella,marcas-vtex`),
   `SCRAPE_REQUEST_DELAY` (seconds
   between requests to the same host, default 1).

2. **Push the code to a private GitHub repo.** Create an empty private repo
   on github.com (no README/license), then:
   ```
   cd "C:\proyectos python\cyber_ofertas"
   git remote add origin https://github.com/<you>/cyber-ofertas.git
   git push -u origin master
   ```

3. **Create a free Neon Postgres project** (neon.tech, no card), region
   **AWS US East 2 (Ohio)** to match the Render region. Copy the connection
   string (`postgresql://...?sslmode=require`).

4. **Deploy on Render:** dashboard -> New -> Blueprint -> pick the repo.
   `render.yaml` creates two free services: the API (`cyber-ofertas-api`)
   and the static frontend. Fill in the prompted secrets: `DATABASE_URL`
   (Neon), `BASIC_AUTH_USER` / `BASIC_AUTH_PASSWORD` (pick your own),
   `TELEGRAM_BOT_TOKEN` / `TELEGRAM_BOT_USERNAME` (from `backend/.env`), and
   for the frontend `NEXT_PUBLIC_API_BASE` -- leave it empty at first, and
   once the API has its `https://...onrender.com` URL, set it and redeploy
   the frontend.

5. **Scheduled scraper on GitHub Actions** (Render cron has no free plan).
   In the GitHub repo: Settings -> Secrets and variables -> Actions -> add
   `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`. The
   workflow (`.github/workflows/scrape.yml`) runs on Oct 4-8: a quick pass
   every 10 min (first pages of each department, where new deals show up)
   and a full sweep every 3 h, each store as its own parallel job. The repo
   is public so Actions minutes are unlimited. Run it by hand from Actions ->
   Scrape offers -> Run workflow (mode quick/full, optional store list).

6. **Switch Telegram to the real webhook.** Stop the local poller
   (`scripts/telegram_poll_dev.py`) first -- a bot can't poll and use a
   webhook at the same time -- then:
   ```
   curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=<API_URL>/telegram/webhook"
   ```
   The free API sleeps after 15 min idle; the first message after that
   takes ~1 min to be answered while it wakes up.

7. **Open the frontend URL from your phone**, log in, pick Nico or Paula,
   and check offers, favorites, the comparator and a Telegram question.
