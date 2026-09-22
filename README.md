# Internship Monitor

Dockerized web app that checks a Hiring Cafe search about once an hour, stores internship postings, and shows new listings in a browser UI.

Default search:

`https://hiringcafe.com/?searchState=%7B%22searchQuery%22%3A%22software+engineering+intern%22%2C%22dateFetchedPastNDays%22%3A2%7D`

## Quick start

```powershell
docker compose up -d --build
```

Open [http://localhost:8000](http://localhost:8000).

- **New** (`/`): postings not marked reviewed yet
- **Saved** (`/saved`): every stored posting with posted age (when Hiring Cafe shows it) and when this app first found it
- **Check now**: trigger a scan immediately
- **Search URL**: change the Hiring Cafe search without rebuilding the image

Data persists in `./data` (SQLite database and Playwright browser profile).

## Local development

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
pytest
uvicorn app.main:app --reload
```

Set environment variables if you want non-default paths:

- `DATA_DIR`
- `DATABASE_PATH`
- `BROWSER_PROFILE_DIR`
- `SEARCH_URL`
- `SCAN_INTERVAL_MINUTES` (default `60`)
- `PLAYWRIGHT_HEADLESS` (default `true`)

## Playwright codegen (when to run it)

Run codegen on your Windows machine after the repo exists and Playwright is installed locally. Codegen needs a visible browser, so it is meant for the host, not inside Docker.

```powershell
py -m pip install playwright
py -m playwright install chromium
py -m playwright codegen --target python -o recorded_search.py "https://hiringcafe.com/?searchState=%7B%22searchQuery%22%3A%22software+engineering+intern%22%2C%22dateFetchedPastNDays%22%3A2%7D"
```

In the browser window:

1. Dismiss the purple "Did I understand you correctly?" bar if it appears
2. Scroll until the job count stops growing
3. Click one **Job Posting** link so the recorder captures that anchor
4. Close the inspector and leave `recorded_search.py` in the project root

The scraper reads locators from `recorded_search.py` when present. If a scan returns zero jobs, re-run codegen and commit the updated file.

## How deduplication works

Each job is keyed by its full Hiring Cafe job URL (`https://hiringcafe.com/job/...`). Re-scans update `last_seen_at` but do not create duplicates. `board_posted_at` is set once from the card's relative label (`22h`, `1d`, etc.) the first time the job is seen.

## Cloudflare / first-run browser profile

Hiring Cafe sits behind Cloudflare. A fresh headless browser often sees a "Just a moment..." page and returns zero jobs.

Seed the persistent profile once on your machine:

```powershell
$env:PLAYWRIGHT_HEADLESS = "false"
$env:DATA_DIR = "data"
py -m uvicorn app.main:app --reload
```

When the browser window opens, let the Hiring Cafe page finish loading and click **Check now** once. After that, `./data/browser-profile` keeps the cookies and later headless scans on your home server can reuse the same folder via the Docker volume.

If headless scans still fail in Docker, set in `docker-compose.yml`:

```yaml
PLAYWRIGHT_HEADLESS: "false"
```

The Playwright base image includes the browser dependencies needed for that mode.
