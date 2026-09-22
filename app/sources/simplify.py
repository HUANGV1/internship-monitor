from __future__ import annotations

import json
import logging
import re
import urllib.request
from datetime import datetime, timezone
from typing import Any

from app.config import SIMPLIFY_LISTINGS_URL

logger = logging.getLogger(__name__)

SOFTWARE_CATEGORIES = {
    "Software",
    "Software Engineering",
}

TARGET_TERMS = {
    "Summer 2027",
}

US_CA_LOCATION_HINTS = (
    "usa",
    "u.s.",
    "united states",
    "canada",
    "remote",
    "toronto",
    "vancouver",
    "montreal",
    "ottawa",
    "calgary",
    "edmonton",
    "waterloo",
    "ontario",
    "quebec",
    "british columbia",
    "alberta",
    "san francisco",
    "new york",
    "seattle",
    "austin",
    "boston",
    "chicago",
    "los angeles",
    "bay area",
    "nyc",
)

FOREIGN_ONLY_HINTS = (
    "united kingdom",
    "london, uk",
    "india",
    "germany",
    "singapore",
    "australia",
    "china",
    "japan",
    "korea",
    "ireland",
    "netherlands",
    "sweden",
    "switzerland",
    "france",
    "spain",
    "italy",
    "poland",
    "israel",
    "brazil",
    "mexico city",
    "hong kong",
    "taiwan",
)

US_STATE_RE = re.compile(
    r",\s*(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|"
    r"MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|"
    r"WV|WI|WY|DC)\b",
    re.IGNORECASE,
)
CA_PROVINCE_RE = re.compile(
    r",\s*(ON|BC|AB|QC|MB|SK|NS|NB|NL|PE|YT|NT|NU)\b",
    re.IGNORECASE,
)


def fetch_simplify_jobs() -> list[dict[str, Any]]:
    logger.info("Fetching SimplifyJobs listings from %s", SIMPLIFY_LISTINGS_URL)
    request = urllib.request.Request(
        SIMPLIFY_LISTINGS_URL,
        headers={"User-Agent": "internship-monitor/1.0"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        listings = json.loads(response.read().decode("utf-8"))

    jobs: list[dict[str, Any]] = []
    for listing in listings:
        if not _is_relevant(listing):
            continue
        jobs.append(_to_job(listing))

    logger.info(
        "SimplifyJobs matched %s software intern roles (Summer 2027, US/Canada)",
        len(jobs),
    )
    return jobs


def _is_relevant(listing: dict[str, Any]) -> bool:
    if not listing.get("active"):
        return False
    if listing.get("is_visible") is False:
        return False
    if not listing.get("url"):
        return False

    category = (listing.get("category") or "").strip()
    title = (listing.get("title") or "").lower()
    is_software = category in SOFTWARE_CATEGORIES or (
        "software" in title and "intern" in title
    )
    if not is_software:
        return False

    terms = set(listing.get("terms") or [])
    if TARGET_TERMS and not (terms & TARGET_TERMS):
        return False

    return _is_us_or_canada(listing.get("locations") or [])


def _is_us_or_canada(locations: list[str]) -> bool:
    if not locations:
        return True

    text = ", ".join(locations).lower()
    if "remote" in text:
        return True
    if US_STATE_RE.search(", ".join(locations)) or CA_PROVINCE_RE.search(", ".join(locations)):
        return True
    if any(hint in text for hint in US_CA_LOCATION_HINTS):
        return True
    if any(hint in text for hint in FOREIGN_ONLY_HINTS):
        return False
    # Ambiguous locations (city only): keep them for MVP.
    return True


def _to_job(listing: dict[str, Any]) -> dict[str, Any]:
    locations = listing.get("locations") or []
    location = ", ".join(locations) if locations else None
    workplace = "Remote" if location and "remote" in location.lower() else None
    posted_at = _unix_to_iso(listing.get("date_posted"))
    return {
        "url": listing["url"].split("?")[0],
        "title": listing.get("title") or "Untitled role",
        "company": listing.get("company_name"),
        "location": location,
        "salary": None,
        "workplace": workplace,
        "board_posted_label": None,
        "board_posted_at": posted_at,
        "source": "simplify",
    }


def _unix_to_iso(value: Any) -> str | None:
    if value is None:
        return None
    try:
        ts = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
