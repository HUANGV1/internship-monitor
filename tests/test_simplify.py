from app.sources.simplify import _is_us_or_canada


def test_us_state_location():
    assert _is_us_or_canada(["San Jose, CA"]) is True


def test_canada_location():
    assert _is_us_or_canada(["Toronto, ON"]) is True


def test_remote_kept():
    assert _is_us_or_canada(["Remote"]) is True


def test_foreign_filtered():
    assert _is_us_or_canada(["London, United Kingdom"]) is False
