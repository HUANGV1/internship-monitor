"""Optional locators from Playwright codegen (recorded_search.py on the host)."""

from pathlib import Path

DEFAULT_CONSENT_BUTTON = "button:has-text('Accept All')"
DEFAULT_JOB_LINK = 'a[href*="/job/"]'


def load_codegen_locators() -> dict[str, str]:
    locators = {
        "consent_button": DEFAULT_CONSENT_BUTTON,
        "job_link": DEFAULT_JOB_LINK,
    }

    recorded_path = Path(__file__).resolve().parent.parent / "recorded_search.py"
    if not recorded_path.exists():
        return locators

    try:
        content = recorded_path.read_text(encoding="utf-8")
    except OSError:
        return locators

    for line in content.splitlines():
        stripped = line.strip()
        if "Accept All" in stripped and "click" in stripped:
            locators["consent_button"] = _extract_locator(stripped) or locators["consent_button"]
        if "/job/" in stripped and "click" in stripped:
            locators["job_link"] = _extract_locator(stripped) or locators["job_link"]

    return locators


def _extract_locator(line: str) -> str | None:
    for quote in ('"', "'"):
        marker = f"locator({quote}"
        if marker in line:
            start = line.index(marker) + len(marker)
            end = line.index(quote, start)
            return line[start:end]
    return None
