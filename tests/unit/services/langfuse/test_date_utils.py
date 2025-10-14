"""Tests for langfuse/date_utils.py - date range utilities."""

from datetime import date, timedelta

from app.services.langfuse.date_utils import DEFAULT_DAYS_RANGE, get_date_range, iterate_date_range


class TestGetDateRange:
    """Test get_date_range function with various inputs."""

    def test_both_dates_provided(self):
        """Should return exact dates when both provided."""
        from_date = date(2024, 1, 1)
        to_date = date(2024, 1, 31)

        start, end = get_date_range(from_date, to_date)

        assert start == from_date
        assert end == to_date

    def test_only_from_date_uses_today_as_end(self):
        """Should use today as end date when only from_date provided."""
        from_date = date(2024, 1, 1)
        today = date.today()

        start, end = get_date_range(from_date, None)

        assert start == from_date
        assert end == today

    def test_no_dates_defaults_to_last_30_days(self):
        """Should default to last 30 days when no dates provided."""
        today = date.today()
        expected_start = today - timedelta(days=DEFAULT_DAYS_RANGE)

        start, end = get_date_range(None, None)

        assert start == expected_start
        assert end == today

    def test_from_date_equals_to_date(self):
        """Should handle same from/to date (single day range)."""
        same_date = date(2024, 6, 15)

        start, end = get_date_range(same_date, same_date)

        assert start == same_date
        assert end == same_date


class TestIterateDateRange:
    """Test iterate_date_range generator."""

    def test_single_day_range(self):
        """Should yield single date when start equals end."""
        target_date = date(2024, 6, 15)

        dates = list(iterate_date_range(target_date, target_date))

        assert len(dates) == 1
        assert dates[0] == target_date

    def test_multiple_days_range(self):
        """Should yield all dates in range including boundaries."""
        start = date(2024, 1, 1)
        end = date(2024, 1, 5)

        dates = list(iterate_date_range(start, end))

        assert len(dates) == 5
        assert dates[0] == date(2024, 1, 1)
        assert dates[1] == date(2024, 1, 2)
        assert dates[2] == date(2024, 1, 3)
        assert dates[3] == date(2024, 1, 4)
        assert dates[4] == date(2024, 1, 5)

    def test_empty_range_when_start_after_end(self):
        """Should return empty when start > end (inverted range)."""
        start = date(2024, 1, 10)
        end = date(2024, 1, 1)

        dates = list(iterate_date_range(start, end))

        # No dates should be yielded when range is inverted
        assert len(dates) == 0
