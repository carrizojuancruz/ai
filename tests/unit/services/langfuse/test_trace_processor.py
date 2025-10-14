from datetime import date
from unittest.mock import MagicMock

import pytest

from app.services.langfuse.trace_processor import (
    _accumulate_cost,
    _create_cost_summaries,
    _should_include_trace,
    extract_cost,
    extract_user_id,
    process_traces,
)


class TestExtractUserId:
    def test_extracts_from_dict_metadata(self):
        trace = {"metadata": {"user_id": "user-123"}}
        assert extract_user_id(trace) == "user-123"

    def test_extracts_from_object_metadata(self):
        trace = MagicMock(metadata={"user_id": "user-456"})
        assert extract_user_id(trace) == "user-456"

    def test_extracts_from_json_string_metadata(self):
        trace = {"metadata": '{"user_id": "user-789"}'}
        assert extract_user_id(trace) == "user-789"

    def test_returns_none_when_no_metadata(self):
        trace = {"data": "value"}
        assert extract_user_id(trace) is None

    def test_returns_none_when_invalid_json(self):
        trace = {"metadata": "invalid-json"}
        assert extract_user_id(trace) is None


class TestExtractCost:
    @pytest.mark.parametrize("field,value,expected", [
        ("totalCost", 1.5, 1.5),
        ("cost", 2.0, 2.0),
        ("total_cost", 3.5, 3.5),
    ])
    def test_extracts_from_dict_fields(self, field, value, expected):
        trace = {field: value}
        assert extract_cost(trace) == expected

    @pytest.mark.parametrize("field,value,expected", [
        ("totalCost", 1.5, 1.5),
        ("cost", 2.0, 2.0),
        ("total_cost", 3.5, 3.5),
    ])
    def test_extracts_from_object_attributes(self, field, value, expected):
        trace = MagicMock(spec=[field])
        setattr(trace, field, value)
        assert extract_cost(trace) == expected

    def test_returns_zero_when_no_cost_field(self):
        trace = {"data": "value"}
        assert extract_cost(trace) == 0.0

    def test_returns_zero_when_cost_is_none(self):
        trace = {"totalCost": None}
        assert extract_cost(trace) == 0.0

    def test_returns_zero_when_invalid_value(self):
        trace = {"totalCost": "invalid"}
        assert extract_cost(trace) == 0.0


class TestShouldIncludeTrace:
    def test_includes_when_no_filters(self):
        assert _should_include_trace("user-1", None, False) is True

    def test_excludes_when_user_id_mismatch(self):
        assert _should_include_trace("user-1", "user-2", False) is False

    def test_includes_when_user_id_matches(self):
        assert _should_include_trace("user-1", "user-1", False) is True

    def test_excludes_registered_when_exclude_flag_true(self):
        assert _should_include_trace("user-1", None, True) is False

    def test_includes_guest_when_exclude_flag_true(self):
        assert _should_include_trace(None, None, True) is True


class TestAccumulateCost:
    def test_creates_new_entry_for_user(self):
        user_costs = {}
        _accumulate_cost(user_costs, "user-1", 1.5)

        assert "user-1" in user_costs
        assert user_costs["user-1"]["cost"] == 1.5
        assert user_costs["user-1"]["traces"] == 1

    def test_accumulates_for_existing_user(self):
        user_costs = {"user-1": {"cost": 2.0, "tokens": 0, "traces": 1}}
        _accumulate_cost(user_costs, "user-1", 1.5)

        assert user_costs["user-1"]["cost"] == 3.5
        assert user_costs["user-1"]["traces"] == 2

    def test_handles_none_user_id(self):
        user_costs = {}
        _accumulate_cost(user_costs, None, 1.0)

        assert None in user_costs
        assert user_costs[None]["cost"] == 1.0


class TestCreateCostSummaries:
    def test_creates_summaries_from_costs(self):
        user_costs = {
            "user-1": {"cost": 5.0, "tokens": 100, "traces": 3},
            "user-2": {"cost": 3.0, "tokens": 50, "traces": 2}
        }
        target = date(2025, 1, 15)

        summaries = _create_cost_summaries(user_costs, target)

        assert len(summaries) == 2
        assert any(s.user_id == "user-1" and s.total_cost == 5.0 and s.trace_count == 3 for s in summaries)
        assert any(s.user_id == "user-2" and s.total_cost == 3.0 and s.trace_count == 2 for s in summaries)

    def test_returns_empty_list_for_no_costs(self):
        summaries = _create_cost_summaries({}, date(2025, 1, 15))
        assert summaries == []


class TestProcessTraces:
    def test_processes_all_traces_by_default(self):
        traces = [
            {"metadata": {"user_id": "user-1"}, "totalCost": 1.0},
            {"metadata": {"user_id": "user-2"}, "totalCost": 2.0}
        ]
        target = date(2025, 1, 15)

        summaries = process_traces(traces, target)

        assert len(summaries) == 2

    def test_filters_by_user_id(self):
        traces = [
            {"metadata": {"user_id": "user-1"}, "totalCost": 1.0},
            {"metadata": {"user_id": "user-2"}, "totalCost": 2.0}
        ]
        target = date(2025, 1, 15)

        summaries = process_traces(traces, target, user_id="user-1")

        assert len(summaries) == 1
        assert summaries[0].user_id == "user-1"

    def test_excludes_user_metadata_when_flag_true(self):
        traces = [
            {"metadata": {"user_id": "user-1"}, "totalCost": 1.0},
            {"totalCost": 2.0}
        ]
        target = date(2025, 1, 15)

        summaries = process_traces(traces, target, exclude_user_metadata=True)

        assert len(summaries) == 1
        assert summaries[0].user_id is None

    def test_accumulates_costs_for_same_user(self):
        traces = [
            {"metadata": {"user_id": "user-1"}, "totalCost": 1.0},
            {"metadata": {"user_id": "user-1"}, "totalCost": 2.0},
            {"metadata": {"user_id": "user-1"}, "totalCost": 1.5}
        ]
        target = date(2025, 1, 15)

        summaries = process_traces(traces, target)

        assert len(summaries) == 1
        assert summaries[0].total_cost == 4.5
        assert summaries[0].trace_count == 3

    def test_handles_empty_traces_list(self):
        summaries = process_traces([], date(2025, 1, 15))
        assert summaries == []

    def test_handles_traces_without_cost(self):
        traces = [{"metadata": {"user_id": "user-1"}}]
        target = date(2025, 1, 15)

        summaries = process_traces(traces, target)

        assert len(summaries) == 1
        assert summaries[0].total_cost == 0.0
