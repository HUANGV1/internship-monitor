from datetime import datetime, timezone

from app.timeparse import format_age, parse_relative_age


def test_parse_hours():
    now = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
    result = parse_relative_age("22h", now=now)
    assert result == datetime(2026, 9, 21, 14, 0, tzinfo=timezone.utc)


def test_parse_days():
    now = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
    result = parse_relative_age("1d", now=now)
    assert result == datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def test_parse_minutes():
    now = datetime(2026, 9, 22, 12, 30, tzinfo=timezone.utc)
    result = parse_relative_age("30m", now=now)
    assert result == datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)


def test_parse_invalid():
    assert parse_relative_age("recently") is None
    assert parse_relative_age(None) is None


def test_format_age_hours():
    now = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
    posted = datetime(2026, 9, 22, 9, 0, tzinfo=timezone.utc).isoformat()
    assert format_age(posted, now=now) == "3h ago"


def test_format_age_days():
    now = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
    posted = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc).isoformat()
    assert format_age(posted, now=now) == "2d ago"
