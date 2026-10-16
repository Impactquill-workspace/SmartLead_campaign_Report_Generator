import pytest
from datetime import date, datetime
from app.utils.date_utils import get_previous_calendar_week, parse_date_range, format_date_str


def test_previous_calendar_week_wednesday():
    """
    Test Wednesday, September 30, 2026.
    Previous calendar week must be Monday Sep 21, 2026 to Sunday Sep 27, 2026.
    """
    ref_date = date(2026, 9, 30)  # Wednesday
    start_d, end_d = get_previous_calendar_week(ref_date)

    assert start_d == date(2026, 9, 21), f"Expected 2026-09-21, got {start_d}"
    assert end_d == date(2026, 9, 27), f"Expected 2026-09-27, got {end_d}"
    # Verify Monday is weekday 0, Sunday is weekday 6
    assert start_d.weekday() == 0  # Monday
    assert end_d.weekday() == 6  # Sunday


def test_previous_calendar_week_monday():
    """
    If today is Monday, previous week should be the immediately preceding Monday-Sunday.
    """
    ref_date = date(2026, 10, 5)  # Monday
    start_d, end_d = get_previous_calendar_week(ref_date)

    assert start_d == date(2026, 9, 28)
    assert end_d == date(2026, 10, 4)
    assert start_d.weekday() == 0
    assert end_d.weekday() == 6


def test_previous_calendar_week_sunday():
    """
    If today is Sunday, previous week is the prior week's Monday-Sunday.
    """
    ref_date = date(2026, 10, 4)  # Sunday
    start_d, end_d = get_previous_calendar_week(ref_date)

    assert start_d == date(2026, 9, 21)
    assert end_d == date(2026, 9, 27)


def test_custom_date_range_valid():
    start_d, end_d = parse_date_range("2026-08-01", "2026-08-31")
    assert start_d == date(2026, 8, 1)
    assert end_d == date(2026, 8, 31)


def test_custom_date_range_inverted():
    with pytest.raises(ValueError, match="cannot be after"):
        parse_date_range("2026-09-30", "2026-09-01")


def test_custom_date_range_one_missing():
    with pytest.raises(ValueError, match="Both start_date and end_date must be provided"):
        parse_date_range(start_date="2026-09-01", end_date=None)


def test_format_date_str():
    d = date(2026, 9, 21)
    assert format_date_str(d) == "2026-09-21"
    dt = datetime(2026, 9, 21, 14, 30, 0)
    assert format_date_str(dt) == "2026-09-21"
