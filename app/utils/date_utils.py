from datetime import date, datetime, timedelta
from typing import Optional, Tuple, Union


def get_previous_calendar_week(reference_date: Optional[date] = None) -> Tuple[date, date]:
    """
    Calculates the previous calendar week's Monday and Sunday.
    Default definition: Monday 00:00:00 through Sunday 23:59:59.

    Example:
    If reference_date is Wednesday, September 30, 2026:
    Returns (2026-09-21, 2026-09-27)
    """
    if reference_date is None:
        reference_date = date.today()
    elif isinstance(reference_date, datetime):
        reference_date = reference_date.date()

    # In Python, Monday is 0, Sunday is 6
    weekday = reference_date.weekday()
    # Monday of the current week
    current_week_monday = reference_date - timedelta(days=weekday)
    # Sunday of the previous week
    previous_week_sunday = current_week_monday - timedelta(days=1)
    # Monday of the previous week
    previous_week_monday = previous_week_sunday - timedelta(days=6)

    return previous_week_monday, previous_week_sunday


def parse_date_range(
    start_date: Optional[Union[str, date]] = None,
    end_date: Optional[Union[str, date]] = None,
    reference_date: Optional[date] = None,
) -> Tuple[date, date]:
    """
    Parses and validates custom date ranges. If both are omitted, defaults to the previous calendar week.
    Validates that start_date <= end_date.
    """
    if start_date is None and end_date is None:
        return get_previous_calendar_week(reference_date)

    if start_date is None or end_date is None:
        raise ValueError("Both start_date and end_date must be provided if one is specified.")

    parsed_start = (
        datetime.strptime(start_date, "%Y-%m-%d").date()
        if isinstance(start_date, str)
        else start_date
    )
    parsed_end = (
        datetime.strptime(end_date, "%Y-%m-%d").date()
        if isinstance(end_date, str)
        else end_date
    )

    if parsed_start > parsed_end:
        raise ValueError(f"start_date ({parsed_start}) cannot be after end_date ({parsed_end}).")

    return parsed_start, parsed_end


def format_date_str(d: Union[date, datetime]) -> str:
    """Formats a date object to YYYY-MM-DD string."""
    if isinstance(d, datetime):
        return d.date().isoformat()
    return d.isoformat()
