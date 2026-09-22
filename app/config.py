import os
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = Path(os.getenv("DATABASE_PATH", DATA_DIR / "internship-monitor.db"))
BROWSER_PROFILE_DIR = Path(os.getenv("BROWSER_PROFILE_DIR", DATA_DIR / "browser-profile"))
BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SEARCH_URL = (
    "https://hiringcafe.com/?searchState=%7B%22searchQuery%22%3A%22software+engineering+intern%22"
    "%2C%22dateFetchedPastNDays%22%3A2%7D"
)
SEARCH_URL = os.getenv("SEARCH_URL", DEFAULT_SEARCH_URL)
SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", "60"))
PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() in {"1", "true", "yes"}

# Default MVP source: SimplifyJobs GitHub listings (no Cloudflare / no browser).
JOB_SOURCE = os.getenv("JOB_SOURCE", "simplify").strip().lower()
SIMPLIFY_LISTINGS_URL = os.getenv(
    "SIMPLIFY_LISTINGS_URL",
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json",
)
ENABLE_HIRING_CAFE = os.getenv("ENABLE_HIRING_CAFE", "false").lower() in {"1", "true", "yes"}
