import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import SCAN_INTERVAL_MINUTES
from app.db import (
    get_latest_scan,
    get_new_jobs,
    get_saved_jobs,
    get_scans,
    get_search_url,
    init_db,
    mark_reviewed,
    set_setting,
)
from app.scraper import ScanInProgressError, run_scan
from app.timeparse import format_age

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="app/templates")
scheduler = AsyncIOScheduler()


def _serialize_job(row) -> dict:
    now = datetime.now(timezone.utc)
    board_posted_display = format_age(row["board_posted_at"], now=now)
    first_seen_display = format_age(row["first_seen_at"], now=now)
    return {
        "url": row["url"],
        "title": row["title"],
        "company": row["company"],
        "location": row["location"],
        "salary": row["salary"],
        "workplace": row["workplace"],
        "board_posted_label": row["board_posted_label"],
        "board_posted_display": board_posted_display,
        "first_seen_display": first_seen_display,
        "first_seen_at": row["first_seen_at"],
        "reviewed_at": row["reviewed_at"],
    }


def _serialize_scan(row) -> dict:
    started = _parse_utc(row["started_at"])
    finished = _parse_utc(row["finished_at"])
    duration = None
    if started and finished:
        seconds = max(int((finished - started).total_seconds()), 0)
        if seconds < 60:
            duration = f"{seconds}s"
        else:
            duration = f"{seconds // 60}m {seconds % 60}s"
    trigger = row["trigger"] if "trigger" in row.keys() else None
    return {
        "id": row["id"],
        "trigger": trigger or "unknown",
        "status": row["status"],
        "started_at": _display_time(row["started_at"]),
        "finished_at": _display_time(row["finished_at"]),
        "duration": duration,
        "jobs_found": row["jobs_found"],
        "new_jobs": row["new_jobs"],
        "message": row["message"],
    }


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _display_time(value: str | None) -> str | None:
    if not value:
        return None
    return value[:19].replace("T", " ") + " UTC"


async def scheduled_scan() -> None:
    logger.info("Starting scheduled scan")
    result = await run_scan(trigger="scheduler")
    logger.info("Scheduled scan finished: %s", result)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    scheduler.add_job(
        scheduled_scan,
        trigger="interval",
        minutes=SCAN_INTERVAL_MINUTES,
        id="hourly_scan",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    asyncio.create_task(run_scan(trigger="startup"))
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Internship Monitor", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def new_jobs_page(request: Request):
    jobs = [_serialize_job(row) for row in get_new_jobs()]
    latest_scan = get_latest_scan()
    return templates.TemplateResponse(
        request,
        "new.html",
        {
            "jobs": jobs,
            "latest_scan": latest_scan,
            "search_url": get_search_url(),
            "page_title": "New internships",
        },
    )


@app.get("/saved", response_class=HTMLResponse)
async def saved_jobs_page(request: Request):
    jobs = [_serialize_job(row) for row in get_saved_jobs()]
    latest_scan = get_latest_scan()
    return templates.TemplateResponse(
        request,
        "saved.html",
        {
            "jobs": jobs,
            "latest_scan": latest_scan,
            "search_url": get_search_url(),
            "page_title": "Saved internships",
        },
    )


@app.get("/runs", response_class=HTMLResponse)
async def runs_page(request: Request):
    scans = [_serialize_scan(row) for row in get_scans()]
    return templates.TemplateResponse(
        request,
        "runs.html",
        {
            "scans": scans,
            "page_title": "Scan history",
            "scan_interval_minutes": SCAN_INTERVAL_MINUTES,
        },
    )


@app.post("/check-now")
async def check_now(next: str = Form(default="/")):
    if next not in {"/", "/saved", "/runs"}:
        next = "/"
    try:
        await run_scan(trigger="manual")
    except ScanInProgressError:
        pass
    return RedirectResponse(url=next, status_code=303)


@app.post("/mark-reviewed")
async def mark_jobs_reviewed(urls: list[str] = Form(default=[])):
    mark_reviewed(urls)
    return RedirectResponse(url="/", status_code=303)


@app.post("/settings/search-url")
async def update_search_url(search_url: str = Form(...)):
    set_setting("search_url", search_url.strip())
    return RedirectResponse(url="/", status_code=303)
