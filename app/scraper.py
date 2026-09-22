import asyncio
import logging
import sys
import time
from typing import Any

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from app.config import (
    BROWSER_PROFILE_DIR,
    ENABLE_HIRING_CAFE,
    JOB_SOURCE,
    PLAYWRIGHT_HEADLESS,
)
from app.db import finish_scan, get_search_url, start_scan, upsert_jobs
from app.locators import load_codegen_locators
from app.sources.simplify import fetch_simplify_jobs
from app.timeparse import parse_relative_age

logger = logging.getLogger(__name__)

EXTRACT_JOBS_SCRIPT = """
() => {
  const agePattern = /^(\\d+\\s*(m|h|d|w|min|mins|minute|minutes|hour|hours|day|days|week|weeks))$/i;
  const salaryPattern = /^\\$[\\d,.]+(?:\\/\\w+)?$/;
  const workplacePattern = /^(Remote|Hybrid|Onsite|Field)$/i;

  const links = [...document.querySelectorAll('a[href*="/job/"]')];
  const seen = new Set();
  const jobs = [];

  for (const link of links) {
    const url = link.href.split('?')[0];
    if (!url || seen.has(url)) continue;
    seen.add(url);

    let card = link;
    for (let i = 0; i < 8 && card.parentElement; i++) {
      card = card.parentElement;
      const text = (card.innerText || '').trim();
      if (text.length > 80 && text.length < 2500) break;
    }

    const lines = (card.innerText || '')
      .split('\\n')
      .map((line) => line.trim())
      .filter(Boolean);

    let boardPostedLabel = null;
    let title = null;
    let location = null;
    let salary = null;
    let workplace = null;
    let company = null;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (!boardPostedLabel && agePattern.test(line)) {
        boardPostedLabel = line;
        continue;
      }
      if (!title && line.length > 3 && !agePattern.test(line) && !salaryPattern.test(line) && !workplacePattern.test(line)) {
        title = line;
        continue;
      }
      if (title && !location && line.length > 2 && !salaryPattern.test(line) && !workplacePattern.test(line) && !line.includes(':')) {
        location = line;
        continue;
      }
      if (!salary && salaryPattern.test(line)) {
        salary = line;
        continue;
      }
      if (!workplace && workplacePattern.test(line)) {
        workplace = line;
        continue;
      }
      if (!company && line.includes(':')) {
        company = line.split(':')[0].trim();
      }
    }

    if (!title) {
      title = link.textContent.trim() || 'Untitled role';
    }

    jobs.push({
      url,
      title,
      company,
      location,
      salary,
      workplace,
      board_posted_label: boardPostedLabel,
    });
  }

  return jobs;
}
"""


class ScanInProgressError(RuntimeError):
    pass


_scan_lock = asyncio.Lock()


async def run_scan(*, trigger: str = "scheduled") -> dict[str, Any]:
    if _scan_lock.locked():
        raise ScanInProgressError("A scan is already running")

    async with _scan_lock:
        scan_id = start_scan(trigger)
        try:
            jobs = await _collect_jobs()
            enriched = _enrich_jobs(jobs)
            new_jobs = upsert_jobs(enriched)
            source_label = JOB_SOURCE
            if ENABLE_HIRING_CAFE:
                source_label = f"{JOB_SOURCE}+hiring_cafe"
            finish_scan(
                scan_id,
                status="success",
                jobs_found=len(enriched),
                new_jobs=new_jobs,
                message=f"Scan triggered by {trigger} via {source_label}",
            )
            return {
                "status": "success",
                "jobs_found": len(enriched),
                "new_jobs": new_jobs,
                "scan_id": scan_id,
            }
        except Exception as exc:
            logger.exception("Scan failed")
            finish_scan(scan_id, status="error", message=str(exc))
            return {
                "status": "error",
                "message": str(exc),
                "scan_id": scan_id,
            }


async def _collect_jobs() -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []

    if JOB_SOURCE == "simplify" or JOB_SOURCE == "all":
        jobs.extend(await asyncio.to_thread(fetch_simplify_jobs))

    if ENABLE_HIRING_CAFE or JOB_SOURCE == "hiring_cafe":
        search_url = get_search_url()
        locators = load_codegen_locators()
        hiring_jobs = await _scrape_search(search_url, locators)
        for job in hiring_jobs:
            job.setdefault("source", "hiring_cafe")
        jobs.extend(hiring_jobs)

    if not jobs and JOB_SOURCE not in {"simplify", "hiring_cafe", "all"}:
        raise RuntimeError(f"Unknown JOB_SOURCE={JOB_SOURCE!r}. Use simplify or hiring_cafe.")

    # Deduplicate by URL if multiple sources overlap.
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for job in jobs:
        url = job.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append(job)
    return unique


async def _scrape_search(search_url: str, locators: dict[str, str]) -> list[dict[str, Any]]:
    # Uvicorn on Windows uses SelectorEventLoop, which cannot spawn subprocesses.
    # Playwright needs ProactorEventLoop to launch Chromium, so run it there.
    if sys.platform == "win32":
        return await asyncio.to_thread(
            _scrape_search_in_proactor, search_url, locators
        )
    return await _scrape_with_playwright(search_url, locators)


def _scrape_search_in_proactor(
    search_url: str, locators: dict[str, str]
) -> list[dict[str, Any]]:
    with asyncio.Runner(loop_factory=asyncio.ProactorEventLoop) as runner:
        return runner.run(_scrape_with_playwright(search_url, locators))


async def _scrape_with_playwright(
    search_url: str, locators: dict[str, str]
) -> list[dict[str, Any]]:
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE_DIR),
            headless=PLAYWRIGHT_HEADLESS,
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else await context.new_page()

        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=90000)
            await _wait_for_results(page, locators["job_link"])
            await _dismiss_consent(page, locators["consent_button"])
            await _scroll_results(page)
            jobs = await page.evaluate(EXTRACT_JOBS_SCRIPT)
            if not jobs:
                raise RuntimeError(
                    "No jobs extracted. Hiring Cafe may be showing a Cloudflare challenge. "
                    "Seed ./data/browser-profile once with PLAYWRIGHT_HEADLESS=false, "
                    "or re-run Playwright codegen on your machine."
                )
            return jobs
        finally:
            await context.close()


async def _wait_for_results(page, job_link_selector: str, timeout_seconds: int = 90) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_title = ""

    while time.monotonic() < deadline:
        title = await page.title()
        last_title = title
        job_count = await page.locator(job_link_selector).count()
        if job_count > 0:
            return

        if "just a moment" in title.lower():
            logger.info("Waiting for Cloudflare verification to finish...")
        await page.wait_for_timeout(2000)

    raise PlaywrightTimeoutError(
        "Timed out waiting for job results. "
        f"Last page title: {last_title!r}. "
        "If Cloudflare blocked the scan, run once with PLAYWRIGHT_HEADLESS=false "
        "to seed the browser profile in ./data/browser-profile."
    )


async def _dismiss_consent(page, consent_selector: str) -> None:
    consent = page.locator(consent_selector)
    if await consent.count() == 0:
        return
    try:
        await consent.first.click(timeout=3000)
        await page.wait_for_timeout(1000)
    except Exception:
        logger.debug("Consent banner not clickable; continuing")


async def _scroll_results(page) -> None:
    previous_count = 0
    stable_rounds = 0

    for _ in range(12):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1200)
        current_count = await page.locator('a[href*="/job/"]').count()
        if current_count == previous_count:
            stable_rounds += 1
            if stable_rounds >= 2:
                break
        else:
            stable_rounds = 0
            previous_count = current_count

    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(500)


def _enrich_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for job in jobs:
        label = job.get("board_posted_label")
        posted_at = job.get("board_posted_at")
        if not posted_at:
            parsed = parse_relative_age(label)
            posted_at = parsed.isoformat() if parsed else None
        enriched.append(
            {
                **job,
                "board_posted_at": posted_at,
            }
        )
    return enriched
