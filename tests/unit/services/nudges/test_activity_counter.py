"""
Unit tests for app.services.nudges.activity_counter module.

Tests cover:
- ActivityCounter initialization
- Increment nudge count functionality
- Multiple increments for same user/nudge
- Different users and nudge types
- Date tracking
- Last nudge timestamp tracking
- Singleton factory function
"""

from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.services.nudges.activity_counter import ActivityCounter, get_activity_counter


class TestActivityCounterInit:
    """Test ActivityCounter initialization."""

    def test_init_creates_empty_structures(self):
        """Test that initialization creates empty data structures."""
        counter = ActivityCounter()

        assert counter._nudge_counts is not None
        assert counter._last_nudge is not None
        assert len(counter._nudge_counts) == 0
        assert len(counter._last_nudge) == 0


class TestIncrementNudgeCount:
    """Test increment_nudge_count method."""

    @pytest.mark.asyncio
    async def test_increment_first_nudge(self):
        """Test incrementing a nudge count for the first time."""
        counter = ActivityCounter()
        user_id = uuid4()
        nudge_type = "milestone"

        with patch("app.services.nudges.activity_counter.datetime") as mock_dt:
            mock_now = datetime(2024, 1, 15, 10, 30, 0)
            mock_dt.now.return_value = mock_now

            await counter.increment_nudge_count(user_id, nudge_type)

            key = f"{user_id}:{nudge_type}"
            today = "2024-01-15"
            count_key = f"{key}:{today}"

            assert counter._nudge_counts[count_key]["count"] == 1
            assert counter._last_nudge[key] == mock_now

    @pytest.mark.asyncio
    async def test_increment_multiple_times_same_day(self):
        """Test incrementing a nudge count multiple times on the same day."""
        counter = ActivityCounter()
        user_id = uuid4()
        nudge_type = "engagement"

        with patch("app.services.nudges.activity_counter.datetime") as mock_dt:
            mock_now1 = datetime(2024, 1, 15, 10, 30, 0)
            mock_now2 = datetime(2024, 1, 15, 14, 45, 0)
            mock_now3 = datetime(2024, 1, 15, 18, 20, 0)
            mock_dt.now.side_effect = [
                mock_now1, mock_now1,  # First call (now() and date())
                mock_now2, mock_now2,  # Second call
                mock_now3, mock_now3,  # Third call
            ]

            await counter.increment_nudge_count(user_id, nudge_type)
            await counter.increment_nudge_count(user_id, nudge_type)
            await counter.increment_nudge_count(user_id, nudge_type)

            key = f"{user_id}:{nudge_type}"
            today = "2024-01-15"
            count_key = f"{key}:{today}"

            assert counter._nudge_counts[count_key]["count"] == 3
            assert counter._last_nudge[key] == mock_now3

    @pytest.mark.asyncio
    async def test_increment_different_days(self):
        """Test incrementing nudge counts on different days."""
        counter = ActivityCounter()
        user_id = uuid4()
        nudge_type = "daily_tip"

        with patch("app.services.nudges.activity_counter.datetime") as mock_dt:
            # Day 1
            mock_day1 = datetime(2024, 1, 15, 10, 0, 0)
            mock_dt.now.return_value = mock_day1
            await counter.increment_nudge_count(user_id, nudge_type)

            # Day 2
            mock_day2 = datetime(2024, 1, 16, 10, 0, 0)
            mock_dt.now.return_value = mock_day2
            await counter.increment_nudge_count(user_id, nudge_type)

            # Day 3
            mock_day3 = datetime(2024, 1, 17, 10, 0, 0)
            mock_dt.now.return_value = mock_day3
            await counter.increment_nudge_count(user_id, nudge_type)

            key = f"{user_id}:{nudge_type}"
            count_key_day1 = f"{key}:2024-01-15"
            count_key_day2 = f"{key}:2024-01-16"
            count_key_day3 = f"{key}:2024-01-17"

            assert counter._nudge_counts[count_key_day1]["count"] == 1
            assert counter._nudge_counts[count_key_day2]["count"] == 1
            assert counter._nudge_counts[count_key_day3]["count"] == 1
            assert counter._last_nudge[key] == mock_day3

    @pytest.mark.asyncio
    async def test_increment_different_users(self):
        """Test incrementing nudge counts for different users."""
        counter = ActivityCounter()
        user_id_1 = uuid4()
        user_id_2 = uuid4()
        nudge_type = "reminder"

        with patch("app.services.nudges.activity_counter.datetime") as mock_dt:
            mock_now = datetime(2024, 1, 15, 10, 0, 0)
            mock_dt.now.return_value = mock_now

            await counter.increment_nudge_count(user_id_1, nudge_type)
            await counter.increment_nudge_count(user_id_1, nudge_type)
            await counter.increment_nudge_count(user_id_2, nudge_type)

            key1 = f"{user_id_1}:{nudge_type}"
            key2 = f"{user_id_2}:{nudge_type}"
            today = "2024-01-15"
            count_key_1 = f"{key1}:{today}"
            count_key_2 = f"{key2}:{today}"

            assert counter._nudge_counts[count_key_1]["count"] == 2
            assert counter._nudge_counts[count_key_2]["count"] == 1
            assert counter._last_nudge[key1] == mock_now
            assert counter._last_nudge[key2] == mock_now

    @pytest.mark.asyncio
    async def test_increment_different_nudge_types(self):
        """Test incrementing different nudge types for same user."""
        counter = ActivityCounter()
        user_id = uuid4()
        nudge_type_1 = "milestone"
        nudge_type_2 = "engagement"
        nudge_type_3 = "reminder"

        with patch("app.services.nudges.activity_counter.datetime") as mock_dt:
            mock_now = datetime(2024, 1, 15, 10, 0, 0)
            mock_dt.now.return_value = mock_now

            await counter.increment_nudge_count(user_id, nudge_type_1)
            await counter.increment_nudge_count(user_id, nudge_type_2)
            await counter.increment_nudge_count(user_id, nudge_type_2)
            await counter.increment_nudge_count(user_id, nudge_type_3)

            key1 = f"{user_id}:{nudge_type_1}"
            key2 = f"{user_id}:{nudge_type_2}"
            key3 = f"{user_id}:{nudge_type_3}"
            today = "2024-01-15"
            count_key_1 = f"{key1}:{today}"
            count_key_2 = f"{key2}:{today}"
            count_key_3 = f"{key3}:{today}"

            assert counter._nudge_counts[count_key_1]["count"] == 1
            assert counter._nudge_counts[count_key_2]["count"] == 2
            assert counter._nudge_counts[count_key_3]["count"] == 1

    @pytest.mark.asyncio
    async def test_increment_logs_correctly(self):
        """Test that increment_nudge_count logs the correct information."""
        counter = ActivityCounter()
        user_id = uuid4()
        nudge_type = "test_nudge"

        with patch("app.services.nudges.activity_counter.datetime") as mock_dt, \
             patch("app.services.nudges.activity_counter.logger") as mock_logger:
            mock_now = datetime(2024, 1, 15, 10, 30, 45)
            mock_dt.now.return_value = mock_now

            await counter.increment_nudge_count(user_id, nudge_type)

            mock_logger.info.assert_called_once()
            log_message = mock_logger.info.call_args[0][0]

            assert "activity_counter.incremented" in log_message
            assert f"user_id={str(user_id)}" in log_message
            assert f"nudge_type={nudge_type}" in log_message
            assert "date=2024-01-15" in log_message
            assert "new_count=1" in log_message
            assert f"timestamp={mock_now.isoformat()}" in log_message

    @pytest.mark.asyncio
    async def test_increment_preserves_existing_count(self):
        """Test that incrementing preserves and builds on existing count."""
        counter = ActivityCounter()
        user_id = uuid4()
        nudge_type = "milestone"

        with patch("app.services.nudges.activity_counter.datetime") as mock_dt:
            mock_now = datetime(2024, 1, 15, 10, 0, 0)
            mock_dt.now.return_value = mock_now

            # Manually set an initial count
            key = f"{user_id}:{nudge_type}"
            today = "2024-01-15"
            count_key = f"{key}:{today}"
            counter._nudge_counts[count_key]["count"] = 5

            # Increment
            await counter.increment_nudge_count(user_id, nudge_type)

            assert counter._nudge_counts[count_key]["count"] == 6

    @pytest.mark.asyncio
    async def test_increment_updates_last_nudge_timestamp(self):
        """Test that last_nudge timestamp is always updated to most recent."""
        counter = ActivityCounter()
        user_id = uuid4()
        nudge_type = "engagement"

        with patch("app.services.nudges.activity_counter.datetime") as mock_dt:
            key = f"{user_id}:{nudge_type}"

            # First increment
            mock_time1 = datetime(2024, 1, 15, 10, 0, 0)
            mock_dt.now.return_value = mock_time1
            await counter.increment_nudge_count(user_id, nudge_type)
            assert counter._last_nudge[key] == mock_time1

            # Second increment
            mock_time2 = datetime(2024, 1, 15, 11, 30, 0)
            mock_dt.now.return_value = mock_time2
            await counter.increment_nudge_count(user_id, nudge_type)
            assert counter._last_nudge[key] == mock_time2

            # Third increment
            mock_time3 = datetime(2024, 1, 15, 14, 45, 0)
            mock_dt.now.return_value = mock_time3
            await counter.increment_nudge_count(user_id, nudge_type)
            assert counter._last_nudge[key] == mock_time3
class TestGetActivityCounter:
    """Test get_activity_counter factory function."""

    def test_get_activity_counter_returns_singleton(self):
        """Test that get_activity_counter returns same instance."""
        # Reset global state
        import app.services.nudges.activity_counter as module
        module._activity_counter = None

        counter1 = get_activity_counter()
        counter2 = get_activity_counter()
        counter3 = get_activity_counter()

        assert counter1 is counter2
        assert counter2 is counter3
        assert isinstance(counter1, ActivityCounter)

    def test_get_activity_counter_creates_instance_on_first_call(self):
        """Test that get_activity_counter creates instance on first call."""
        import app.services.nudges.activity_counter as module
        module._activity_counter = None

        assert module._activity_counter is None

        counter = get_activity_counter()

        assert module._activity_counter is not None
        assert counter is module._activity_counter

    def test_get_activity_counter_reuses_existing_instance(self):
        """Test that get_activity_counter reuses existing instance."""
        import app.services.nudges.activity_counter as module

        # Create an instance directly
        existing_counter = ActivityCounter()
        module._activity_counter = existing_counter

        # Get counter via function
        counter = get_activity_counter()

        assert counter is existing_counter


class TestActivityCounterIntegration:
    """Integration tests for ActivityCounter."""

    @pytest.mark.asyncio
    async def test_realistic_usage_scenario(self):
        """Test a realistic scenario with multiple users and nudges."""
        counter = ActivityCounter()

        # Setup users and nudge types
        user1 = uuid4()
        user2 = uuid4()
        user3 = uuid4()

        with patch("app.services.nudges.activity_counter.datetime") as mock_dt:
            # Day 1 - Multiple activities
            mock_dt.now.return_value = datetime(2024, 1, 15, 9, 0, 0)
            await counter.increment_nudge_count(user1, "milestone")
            await counter.increment_nudge_count(user1, "engagement")
            await counter.increment_nudge_count(user2, "milestone")

            # Day 1 - Later in the day
            mock_dt.now.return_value = datetime(2024, 1, 15, 15, 30, 0)
            await counter.increment_nudge_count(user1, "milestone")
            await counter.increment_nudge_count(user3, "reminder")

            # Day 2
            mock_dt.now.return_value = datetime(2024, 1, 16, 10, 0, 0)
            await counter.increment_nudge_count(user1, "milestone")
            await counter.increment_nudge_count(user2, "engagement")

            # Verify counts
            assert counter._nudge_counts[f"{user1}:milestone:2024-01-15"]["count"] == 2
            assert counter._nudge_counts[f"{user1}:milestone:2024-01-16"]["count"] == 1
            assert counter._nudge_counts[f"{user1}:engagement:2024-01-15"]["count"] == 1
            assert counter._nudge_counts[f"{user2}:milestone:2024-01-15"]["count"] == 1
            assert counter._nudge_counts[f"{user2}:engagement:2024-01-16"]["count"] == 1
            assert counter._nudge_counts[f"{user3}:reminder:2024-01-15"]["count"] == 1

            # Verify last nudge timestamps
            assert counter._last_nudge[f"{user1}:milestone"] == datetime(2024, 1, 16, 10, 0, 0)
            assert counter._last_nudge[f"{user2}:engagement"] == datetime(2024, 1, 16, 10, 0, 0)
            assert counter._last_nudge[f"{user3}:reminder"] == datetime(2024, 1, 15, 15, 30, 0)

    @pytest.mark.asyncio
    async def test_state_isolation_between_instances(self):
        """Test that different ActivityCounter instances have isolated state."""
        counter1 = ActivityCounter()
        counter2 = ActivityCounter()

        user_id = uuid4()

        with patch("app.services.nudges.activity_counter.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 15, 10, 0, 0)

            await counter1.increment_nudge_count(user_id, "type1")
            await counter2.increment_nudge_count(user_id, "type2")

            key1 = f"{user_id}:type1:2024-01-15"
            key2 = f"{user_id}:type2:2024-01-15"

            # counter1 should only have type1
            assert counter1._nudge_counts[key1]["count"] == 1
            assert key2 not in counter1._nudge_counts

            # counter2 should only have type2
            assert counter2._nudge_counts[key2]["count"] == 1
            assert key1 not in counter2._nudge_counts
