import re
from datetime import datetime, timedelta, timezone

RELATIVE_AGE_PATTERN = re.compile(
    r"^(?P<value>\d+)\s*(?P<unit>[mhdw]|min|mins|minute|minutes|hour|hours|day|days|week|weeks)$",
    re.IGNORECASE,
)

UNIT_TO_MINUTES = {
    "m": 1,
    "min": 1,
    "mins": 1,
    "minute": 1,
    "minutes": 1,
    "h": 60,
    "hour": 60,
    "hours": 60,
    "d": 60 * 24,
    "day": 60 * 24,
    "days": 60 * 24,
    "w": 60 * 24 * 7,
    "week": 60 * 24 * 7,
    "weeks": 60 * 24 * 7,
}


def parse_relative_age(label: str | None, *, now: datetime | None = None) -> datetime | None:
    if not label:
        return None

    cleaned = label.strip().lower()
    match = RELATIVE_AGE_PATTERN.match(cleaned)
    if not match:
        return None

    value = int(match.group("value"))
    unit = match.group("unit").lower()
    minutes = value * UNIT_TO_MINUTES[unit]
    reference = now or datetime.now(timezone.utc)
    return reference - timedelta(minutes=minutes)


def format_age(dt_iso: str | None, *, now: datetime | None = None) -> str | None:
    if not dt_iso:
        return None

    reference = now or datetime.now(timezone.utc)
    dt = datetime.fromisoformat(dt_iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    delta = reference - dt
    total_seconds = max(int(delta.total_seconds()), 0)

    if total_seconds < 60:
        return "just now"
    if total_seconds < 3600:
        minutes = total_seconds // 60
        return f"{minutes}m ago"
    if total_seconds < 86400:
        hours = total_seconds // 3600
        return f"{hours}h ago"
    days = total_seconds // 86400
    if days < 7:
        return f"{days}d ago"
    weeks = days // 7
    return f"{weeks}w ago"
