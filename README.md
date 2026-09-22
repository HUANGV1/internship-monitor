# Internship Monitor

Dockerized web app that checks internship listings about once an hour, stores them, and shows new roles in a browser UI.

## Default source (MVP)

**[SimplifyJobs/Summer2027-Internships](https://github.com/SimplifyJobs/Summer2027-Internships)** — public `listings.json` on GitHub.

- Software engineering intern roles tagged **Summer 2027**
- Filtered toward US / Canada / Remote
- Plain HTTPS JSON fetch — **no Playwright, no Cloudflare**
- Works cleanly on a headless home server over SSH + Docker

Hiring Cafe Playwright scraping is still in the codebase but **off by default** (`ENABLE_HIRING_CAFE=false`) because Cloudflare blocks most server IPs.

## Quick start

```powershell
docker compose up -d --build
```

Open [http://localhost:8000](http://localhost:8000).

- **New** (`/`): postings not marked reviewed yet
- **Saved** (`/saved`): every stored posting with posted age + when this app first found it
- **Runs** (`/runs`): history of every scan
- **Check now**: trigger a scan immediately

Data persists in `./data` (SQLite database).

## Local development

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pytest
uvicorn app.main:app --reload
```

Useful environment variables:

- `JOB_SOURCE` — `simplify` (default), `hiring_cafe`, or `all`
- `ENABLE_HIRING_CAFE` — `false` by default
- `SIMPLIFY_LISTINGS_URL` — raw GitHub JSON URL
- `SCAN_INTERVAL_MINUTES` — default `60`
- `DATA_DIR` / `DATABASE_PATH`

## Home server

No browser seeding needed for the default Simplify source:

```bash
git clone <repo> internship-monitor
cd internship-monitor
docker compose up -d --build
```

Open `http://<server-ip>:8000` and watch **Runs** for `success`.

## Optional: Hiring Cafe (Playwright)

Set in `docker-compose.yml`:

```yaml
JOB_SOURCE: hiring_cafe
ENABLE_HIRING_CAFE: "true"
```

You will need Cloudflare seeding (headed browser on the same IP). See earlier notes in git history / local README sections if you re-enable it.

## How deduplication works

Each job is keyed by its apply URL. Re-scans update `last_seen_at` but do not create duplicates. `board_posted_at` comes from Simplify's `date_posted` timestamp when available.
