import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.agents.supervisor.memory.episodic import (
    _build_human_summary,
    _collect_recent_messages,
    _create_episodic_value,
    _get_neighbors,
    _reset_ctrl_after_capture,
    _resolve_user_tz_from_config,
    _should_merge_neighbor,
    _should_skip_capture,
    _summarize_with_bedrock,
    _update_ctrl_for_new_turn,
    episodic_capture,
)


class TestResolveUserTzFromConfig:
    @pytest.mark.parametrize("tz_name,expected_offset", [
        ("UTC", 0),
        ("America/New_York", -5),
        ("Europe/London", 0),
    ])
    def test_valid_timezones(self, tz_name, expected_offset):
        config = {"configurable": {"user_context": {"locale_info": {"time_zone": tz_name}}}}
        tz = _resolve_user_tz_from_config(config)
        assert tz is not None

    def test_fallback_to_utc_when_invalid(self):
        config = {"configurable": {"user_context": {"locale_info": {"time_zone": "Invalid/Zone"}}}}
        tz = _resolve_user_tz_from_config(config)
        assert tz == timezone.utc

    def test_fallback_to_utc_when_missing(self):
        config = {"configurable": {}}
        tz = _resolve_user_tz_from_config(config)
        assert str(tz) in ["UTC", "UTC+00:00"]


class TestUpdateCtrlForNewTurn:
    def test_resets_count_for_new_day(self):
        ctrl = {"day_iso": "2025-01-01", "count_today": 5, "turns_since_last": 3}
        result = _update_ctrl_for_new_turn(ctrl, "2025-01-02")
        assert result["day_iso"] == "2025-01-02"
        assert result["count_today"] == 0
        assert result["turns_since_last"] == 4

    def test_keeps_count_for_same_day(self):
        ctrl = {"day_iso": "2025-01-01", "count_today": 3, "turns_since_last": 1}
        result = _update_ctrl_for_new_turn(ctrl, "2025-01-01")
        assert result["count_today"] == 3
        assert result["turns_since_last"] == 2


class TestShouldSkipCapture:
    def test_skips_when_max_per_day_reached(self):
        ctrl = {"count_today": 5}
        result = _should_skip_capture(ctrl, datetime.now(timezone.utc), minutes_cooldown=10, turns_cooldown=2, max_per_day=5)
        assert result is True

    def test_skips_when_turns_cooldown_not_met(self):
        ctrl = {"count_today": 0, "turns_since_last": 1}
        result = _should_skip_capture(ctrl, datetime.now(timezone.utc), minutes_cooldown=10, turns_cooldown=3, max_per_day=10)
        assert result is True

    def test_skips_when_minutes_cooldown_not_met(self):
        now = datetime.now(timezone.utc)
        ctrl = {"count_today": 0, "turns_since_last": 5, "last_at_iso": (now - timedelta(minutes=5)).isoformat()}
        result = _should_skip_capture(ctrl, now, minutes_cooldown=10, turns_cooldown=2, max_per_day=10)
        assert result is True

    def test_allows_capture_when_all_conditions_met(self):
        now = datetime.now(timezone.utc)
        ctrl = {"count_today": 0, "turns_since_last": 5, "last_at_iso": (now - timedelta(minutes=15)).isoformat()}
        result = _should_skip_capture(ctrl, now, minutes_cooldown=10, turns_cooldown=2, max_per_day=10)
        assert result is False


class TestCollectRecentMessages:
    def test_collects_user_and_assistant_messages(self):
        msg1 = MagicMock(role="user", content="Hello")
        msg2 = MagicMock(role="assistant", content="Hi there")
        msg3 = MagicMock(role="user", content="How are you?")
        state = {"messages": [msg1, msg2, msg3]}

        result = _collect_recent_messages(state, max_messages=3)

        assert len(result) == 3
        assert result[0] == ("user", "Hello")
        assert result[1] == ("assistant", "Hi there")
        assert result[2] == ("user", "How are you?")

    def test_limits_to_max_messages(self):
        msgs = [MagicMock(role="user", content=f"Message {i}") for i in range(10)]
        state = {"messages": msgs}

        result = _collect_recent_messages(state, max_messages=5)

        assert len(result) == 5

    def test_filters_non_user_assistant_messages(self):
        msg1 = MagicMock(role="system", content="System message")
        msg2 = MagicMock(role="user", content="User message")
        state = {"messages": [msg1, msg2]}

        result = _collect_recent_messages(state, max_messages=5)

        assert len(result) == 1
        assert result[0] == ("user", "User message")


class TestSummarizeWithBedrock:
    @patch("app.agents.supervisor.memory.episodic.get_bedrock_runtime_client")
    def test_successful_summarization(self, mock_bedrock):
        mock_client = MagicMock()
        mock_bedrock.return_value = mock_client

        response_data = {
            "output": {
                "message": {
                    "content": [{"text": '{"summary": "Discussed budget", "category": "Plan", "importance": 3}'}]
                }
            }
        }
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(response_data).encode("utf-8")
        mock_client.invoke_model.return_value = {"body": mock_body}

        msgs = [("user", "Let's talk about budget"), ("assistant", "Sure, what's your budget?")]
        summary, category, importance = _summarize_with_bedrock(msgs)

        assert summary == "Discussed budget"
        assert category == "Plan"
        assert importance == 3

    @patch("app.agents.supervisor.memory.episodic.get_bedrock_runtime_client")
    def test_handles_empty_summary(self, mock_bedrock):
        mock_client = MagicMock()
        mock_bedrock.return_value = mock_client

        response_data = {"output": {"message": {"content": [{"text": '{"summary": "", "category": "Update", "importance": 1}'}]}}}
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(response_data).encode("utf-8")
        mock_client.invoke_model.return_value = {"body": mock_body}

        msgs = [("user", "Hi"), ("assistant", "Hello")]
        summary, category, importance = _summarize_with_bedrock(msgs)

        assert summary == ""
        assert category == "Update"
        assert importance == 1


class TestBuildHumanSummary:
    def test_formats_summary_with_date_and_week(self):
        date_iso = "2025-01-15"
        now_local = datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc)

        result = _build_human_summary("User discussed budget", date_iso, now_local)

        assert "2025-01-15" in result
        assert "W" in result
        assert "2025" in result
        assert "User discussed budget" in result


class TestGetNeighbors:
    def test_returns_neighbors_on_success(self):
        mock_store = MagicMock()
        mock_neighbor = MagicMock(score=0.9, key="mem-123")
        mock_store.search.return_value = [mock_neighbor]

        result = _get_neighbors(mock_store, ("user-1", "episodic"), "test query", limit=5)

        assert len(result) == 1
        assert result[0].key == "mem-123"

    def test_returns_empty_list_on_exception(self):
        mock_store = MagicMock()
        mock_store.search.side_effect = Exception("Search error")

        result = _get_neighbors(mock_store, ("user-1", "episodic"), "test query", limit=5)

        assert result == []


class TestShouldMergeNeighbor:
    def test_merges_when_score_high_and_recent(self):
        now = datetime.now(timezone.utc)
        neighbor = MagicMock(score=0.95, updated_at=(now - timedelta(hours=1)).isoformat())

        result = _should_merge_neighbor(neighbor, now, novelty_min=0.9, merge_window_hours=24)

        assert result is True

    def test_skips_when_score_too_low(self):
        now = datetime.now(timezone.utc)
        neighbor = MagicMock(score=0.5, updated_at=(now - timedelta(hours=1)).isoformat())

        result = _should_merge_neighbor(neighbor, now, novelty_min=0.9, merge_window_hours=24)

        assert result is False

    def test_skips_when_outside_window(self):
        now = datetime.now(timezone.utc)
        neighbor = MagicMock(score=0.95, updated_at=(now - timedelta(hours=48)).isoformat())

        result = _should_merge_neighbor(neighbor, now, novelty_min=0.9, merge_window_hours=24)

        assert result is False


class TestCreateEpisodicValue:
    def test_creates_complete_value_dict(self):
        user_id = str(uuid4())
        candidate_id = uuid4().hex
        now_iso = datetime.now(timezone.utc).isoformat()

        result = _create_episodic_value(
            user_id=user_id,
            candidate_id=candidate_id,
            human_summary="Test summary",
            category="Decision",
            importance=4,
            now_iso=now_iso
        )

        assert result["id"] == candidate_id
        assert result["user_id"] == user_id
        assert result["type"] == "episodic"
        assert result["summary"] == "Test summary"
        assert result["category"] == "Decision"
        assert result["importance"] == 4
        assert result["pinned"] is False
        assert result["created_at"] == now_iso


class TestResetCtrlAfterCapture:
    def test_resets_turns_and_updates_counters(self):
        now_utc = datetime.now(timezone.utc)
        ctrl = {"turns_since_last": 5, "count_today": 2}

        result = _reset_ctrl_after_capture(ctrl, now_utc)

        assert result["turns_since_last"] == 0
        assert result["count_today"] == 3
        assert "last_at_iso" in result


class TestEpisodicCapture:
    @pytest.fixture
    def mock_dependencies(self):
        with patch("app.agents.supervisor.memory.episodic.get_session_store") as mock_store, \
             patch("app.agents.supervisor.memory.episodic.get_store") as mock_mem_store, \
             patch("app.agents.supervisor.memory.episodic.get_bedrock_runtime_client") as mock_bedrock, \
             patch("app.agents.supervisor.memory.episodic.get_sse_queue") as mock_queue:

            mock_session = AsyncMock()
            mock_session.get_session.return_value = {"episodic_control": {}}
            mock_session.set_session.return_value = None
            mock_store.return_value = mock_session

            mock_memory = MagicMock()
            mock_memory.search.return_value = []
            mock_memory.put.return_value = None
            mock_mem_store.return_value = mock_memory

            mock_client = MagicMock()
            response_data = {
                "output": {"message": {"content": [{"text": '{"summary": "Test", "category": "Plan", "importance": 3}'}]}}
            }
            mock_body = MagicMock()
            mock_body.read.return_value = json.dumps(response_data).encode("utf-8")
            mock_client.invoke_model.return_value = {"body": mock_body}
            mock_bedrock.return_value = mock_client

            mock_sse = AsyncMock()
            mock_queue.return_value = mock_sse

            yield {
                "session_store": mock_session,
                "memory_store": mock_memory,
                "bedrock": mock_client,
                "sse_queue": mock_sse
            }

    @pytest.mark.asyncio
    async def test_skips_when_no_user_id(self, mock_dependencies):
        state = {"messages": []}
        config = {"configurable": {}}

        result = await episodic_capture(state, config)

        assert result == {}

    @pytest.mark.asyncio
    async def test_skips_when_no_messages(self, mock_dependencies):
        state = {"messages": []}
        config = {"configurable": {"user_id": str(uuid4()), "thread_id": "thread-1"}}

        result = await episodic_capture(state, config)

        assert result == {}

    @pytest.mark.asyncio
    async def test_creates_new_memory_when_conditions_met(self, mock_dependencies):
        mock_dependencies["session_store"].get_session.return_value = {
            "episodic_control": {
                "day_iso": "2020-01-01",
                "count_today": 0,
                "turns_since_last": 10,
                "last_at_iso": "2020-01-01T00:00:00+00:00"
            }
        }

        msg1 = MagicMock(role="user", content="Let's plan a budget")
        msg2 = MagicMock(role="assistant", content="Great idea")
        state = {"messages": [msg1, msg2]}

        config = {
            "configurable": {
                "user_id": str(uuid4()),
                "thread_id": "thread-1",
                "user_context": {"locale_info": {"time_zone": "UTC"}}
            }
        }

        result = await episodic_capture(state, config)

        assert result == {}
        assert mock_dependencies["memory_store"].put.called

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self, mock_dependencies):
        mock_dependencies["session_store"].get_session.side_effect = Exception("DB error")

        state = {"messages": [MagicMock(role="user", content="Test")]}
        config = {"configurable": {"user_id": str(uuid4()), "thread_id": "thread-1"}}

        result = await episodic_capture(state, config)

        assert result == {}
