"""Date utility functions for cost service."""

from datetime import date, timedelta
from typing import Generator, Optional, Tuple

DEFAULT_DAYS_RANGE = 30


def get_date_range(from_date: Optional[date], to_date: Optional[date]) -> Tuple[date, date]:
    """Get normalized date range with default fallbacks."""
    if from_date and to_date:
        return from_date, to_date
    elif from_date and not to_date:
        return from_date, date.today()
    else:
        end_date = date.today()
        return end_date - timedelta(days=DEFAULT_DAYS_RANGE), end_date


def iterate_date_range(start_date: date, end_date: date) -> Generator[date, None, None]:
    """Iterate through date range day by day."""
    current_date = start_date
    while current_date <= end_date:
        yield current_date
        current_date += timedelta(days=1)
