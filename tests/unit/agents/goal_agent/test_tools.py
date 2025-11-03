"""Unit tests for Goal Agent tools (CRUD operations with @tool decorator).

Tests cover all LangChain tool functions with comprehensive mocking of external dependencies.
Following Verde AI testing architecture - deterministic tests only.
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from langchain_core.runnables import RunnableConfig

from app.agents.supervisor.goal_agent.constants import ErrorCodes
from app.agents.supervisor.goal_agent.tools import (
    create_goal,
    delete_goal,
    get_goal_by_id,
    get_in_progress_goal,
    list_goals,
    switch_goal_status,
    update_goal,
)

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_user_id():
    """Generate a consistent test user ID."""
    return str(uuid4())


@pytest.fixture
def mock_config(mock_user_id):
    """Create a mock RunnableConfig with user_id."""
    return RunnableConfig(configurable={"user_id": mock_user_id})


@pytest.fixture
def sample_goal_data(mock_user_id):
    """Sample goal data for testing."""
    return {
        "goal": {"title": "Save for vacation"},
        "category": {"value": "saving"},
        "nature": {"value": "increase"},
        "kind": "financial_habit",
        "frequency": {
            "type": "recurrent",
            "recurrent": {
                "unit": "month",
                "every": 1,
                "start_date": "2025-01-01T00:00:00",
                "end_date": "2025-12-31T23:59:59"
            }
        },
        "amount": {
            "type": "absolute",
            "absolute": {
                "currency": "USD",
                "target": 5000
            }
        },
        "evaluation": {
            "affected_categories": ["INCOME", "TRANSFER_IN"]
        },
        "notifications": {"enabled": True},
        "user_id": mock_user_id
    }


@pytest.fixture
def sample_goal_dict(mock_user_id):
    """Sample goal dictionary response."""
    goal_id = str(uuid4())
    return {
        "id": goal_id,
        "user_id": mock_user_id,
        "goal": {"title": "Save for vacation"},
        "category": {"value": "saving"},
        "nature": {"value": "increase"},
        "kind": "financial_habit",
        "status": {"value": "pending"},
        "frequency": {
            "type": "recurrent",
            "recurrent": {
                "unit": "month",
                "every": 1,
                "start_date": "2025-01-01T00:00:00",
                "end_date": "2025-12-31T23:59:59"
            }
        },
        "amount": {
            "type": "absolute",
            "absolute": {
                "currency": "USD",
                "target": 5000
            }
        },
        "evaluation": {
            "affected_categories": ["INCOME", "TRANSFER_IN"]
        },
        "notifications": {"enabled": True},
        "progress": {
            "current_value": 0,
            "percent_complete": 0,
            "updated_at": "2025-01-01T00:00:00"
        },
        "version": 1,
        "audit": {
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00"
        }
    }


@pytest.fixture
def mock_datetime():
    """Mock datetime.now() to return a fixed datetime."""
    with patch('app.agents.supervisor.goal_agent.tools._now') as mock_now:
        fixed_time = datetime(2025, 10, 12, 12, 0, 0)
        mock_now.return_value = fixed_time
        yield fixed_time


# ============================================================================
# CREATE GOAL TESTS
# ============================================================================

class TestCreateGoal:
    """Test cases for create_goal tool."""

    @pytest.mark.asyncio
    async def test_create_goal_success(self, mock_config, sample_goal_data, sample_goal_dict, mock_datetime):
        """Test successful goal creation."""
        with patch('app.agents.supervisor.goal_agent.tools.save_goal', new_callable=AsyncMock) as mock_save:
            mock_save.return_value = {"goal": sample_goal_dict}

            result_str = await create_goal.ainvoke({"data": sample_goal_data}, config=mock_config)
            result = json.loads(result_str)

            assert result["message"] == "Goal created"
            assert "goal" in result
            assert result["goal"]["goal"]["goal"]["title"] == "Save for vacation"
            mock_save.assert_called_once()


    @pytest.mark.asyncio
    async def test_create_goal_save_exception(self, mock_config, sample_goal_data):
        """Test goal creation when save fails."""
        with patch('app.agents.supervisor.goal_agent.tools.save_goal', new_callable=AsyncMock) as mock_save:
            mock_save.side_effect = Exception("Database error")

            result_str = await create_goal.ainvoke({"data": sample_goal_data}, config=mock_config)
            result = json.loads(result_str)

            assert result["error"] == "CREATE_FAILED"


# ============================================================================
# UPDATE GOAL TESTS
# ============================================================================

class TestUpdateGoal:
    """Test cases for update_goal tool."""

    @pytest.mark.asyncio
    async def test_update_goal_success(self, mock_config, sample_goal_dict):
        """Test successful goal update."""
        goal_id = sample_goal_dict["id"]
        update_data = {"goal_id": goal_id, "goal": {"title": "Updated vacation fund"}}

        with patch('app.agents.supervisor.goal_agent.tools.fetch_goal_by_id', new_callable=AsyncMock) as mock_fetch, \
             patch('app.agents.supervisor.goal_agent.tools.edit_goal', new_callable=AsyncMock):

            mock_fetch.return_value = {"goal": sample_goal_dict}

            result_str = await update_goal.ainvoke({"data": update_data}, config=mock_config)
            result = json.loads(result_str)

            assert result["message"].startswith("Goal updated")
            assert result["goal"]["version"] == 2

    @pytest.mark.asyncio
    async def test_update_goal_not_found(self, mock_config):
        """Test updating a non-existent goal."""
        update_data = {"goal_id": str(uuid4())}

        with patch('app.agents.supervisor.goal_agent.tools.fetch_goal_by_id', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {}

            result_str = await update_goal.ainvoke({"data": update_data}, config=mock_config)
            result = json.loads(result_str)

            assert result["error"] == ErrorCodes.NO_GOAL_TO_UPDATE


# ============================================================================
# LIST GOALS TESTS
# ============================================================================

class TestListGoals:
    """Test cases for list_goals tool."""

    @pytest.mark.asyncio
    async def test_list_goals_success(self, mock_config, sample_goal_dict):
        """Test successfully listing goals."""
        goals_list = [sample_goal_dict]

        with patch('app.agents.supervisor.goal_agent.tools.get_goals_for_user', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"goals": goals_list}

            result_str = await list_goals.ainvoke({}, config=mock_config)
            result = json.loads(result_str)

            assert result["count"] == 1
            assert len(result["goals"]) == 1

    @pytest.mark.asyncio
    async def test_list_goals_filters_deleted(self, mock_config, sample_goal_dict):
        """Test that deleted goals are filtered out."""
        deleted_goal = {**sample_goal_dict, "id": str(uuid4()), "status": {"value": "deleted"}}
        active_goal = sample_goal_dict

        with patch('app.agents.supervisor.goal_agent.tools.get_goals_for_user', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"goals": [active_goal, deleted_goal]}

            result_str = await list_goals.ainvoke({}, config=mock_config)
            result = json.loads(result_str)

            assert result["count"] == 1


# ============================================================================
# GET IN PROGRESS GOAL TESTS
# ============================================================================

class TestGetInProgressGoal:
    """Test cases for get_in_progress_goal tool."""

    @pytest.mark.asyncio
    async def test_get_in_progress_goal_success(self, mock_config, sample_goal_dict):
        """Test getting in-progress goal successfully."""
        in_progress_goal = {**sample_goal_dict, "status": {"value": "in_progress"}}

        with patch('app.agents.supervisor.goal_agent.tools.get_in_progress_goals_for_user', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"goals": [in_progress_goal]}

            result_str = await get_in_progress_goal.ainvoke({}, config=mock_config)
            result = json.loads(result_str)

            assert result["message"] == "The user has an in progress goal"

    @pytest.mark.asyncio
    async def test_get_in_progress_goal_none_found(self, mock_config):
        """Test when user has no in-progress goals."""
        with patch('app.agents.supervisor.goal_agent.tools.get_in_progress_goals_for_user', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"goals": []}

            result_str = await get_in_progress_goal.ainvoke({}, config=mock_config)
            result = json.loads(result_str)

            assert result["error"] == ErrorCodes.USER_HAS_NO_IN_PROGRESS_GOALS


# ============================================================================
# DELETE GOAL TESTS
# ============================================================================

class TestDeleteGoal:
    """Test cases for delete_goal tool."""

    @pytest.mark.asyncio
    async def test_delete_goal_success(self, mock_config, sample_goal_dict):
        """Test successful goal deletion (soft delete)."""
        goal_id = sample_goal_dict["id"]

        with patch('app.agents.supervisor.goal_agent.tools.fetch_goal_by_id', new_callable=AsyncMock) as mock_fetch, \
             patch('app.agents.supervisor.goal_agent.tools.delete_goal_api', new_callable=AsyncMock) as mock_delete:

            mock_fetch.return_value = {"goal": sample_goal_dict}
            mock_delete.return_value = True

            result_str = await delete_goal.ainvoke({"goal_id": goal_id}, config=mock_config)
            result = json.loads(result_str)

            assert result["message"] == "Goal deleted"

    @pytest.mark.asyncio
    async def test_delete_goal_not_found(self, mock_config):
        """Test deleting a non-existent goal."""
        goal_id = str(uuid4())

        with patch('app.agents.supervisor.goal_agent.tools.fetch_goal_by_id', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {}

            result_str = await delete_goal.ainvoke({"goal_id": goal_id}, config=mock_config)
            result = json.loads(result_str)

            assert result["error"] == ErrorCodes.NO_GOAL_TO_DELETE


# ============================================================================
# SWITCH GOAL STATUS TESTS
# ============================================================================

class TestSwitchGoalStatus:
    """Test cases for switch_goal_status tool."""

    @pytest.mark.asyncio
    async def test_switch_status_pending_to_in_progress(self, mock_config, sample_goal_dict):
        """Test valid transition from pending to in_progress."""
        goal_id = sample_goal_dict["id"]
        new_status = "in_progress"

        with patch('app.agents.supervisor.goal_agent.tools.fetch_goal_by_id', new_callable=AsyncMock) as mock_fetch, \
             patch('app.agents.supervisor.goal_agent.tools.switch_goal_status_api', new_callable=AsyncMock) as mock_switch:

            pending_goal = {**sample_goal_dict, "status": {"value": "pending"}}
            in_progress_goal = {**sample_goal_dict, "status": {"value": "in_progress"}}

            mock_fetch.side_effect = [{"goal": pending_goal}, {"goal": in_progress_goal}]
            mock_switch.return_value = True

            result_str = await switch_goal_status.ainvoke({"goal_id": goal_id, "status": new_status}, config=mock_config)
            result = json.loads(result_str)

            assert "Goal status switched" in result["message"]

    @pytest.mark.asyncio
    async def test_switch_status_to_deleted_blocked(self, mock_config, sample_goal_dict):
        """Test that switching to 'deleted' status is blocked."""
        goal_id = sample_goal_dict["id"]

        with patch('app.agents.supervisor.goal_agent.tools.fetch_goal_by_id', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"goal": sample_goal_dict}

            result_str = await switch_goal_status.ainvoke({"goal_id": goal_id, "status": "deleted"}, config=mock_config)
            result = json.loads(result_str)

            assert result["error"] == ErrorCodes.INVALID_TRANSITION


# ============================================================================
# GET GOAL BY ID TESTS
# ============================================================================

class TestGetGoalById:
    """Test cases for get_goal_by_id tool."""

    @pytest.mark.asyncio
    async def test_get_goal_by_id_success(self, mock_config, sample_goal_dict):
        """Test successfully getting a goal by ID."""
        goal_id = sample_goal_dict["id"]

        with patch('app.agents.supervisor.goal_agent.tools.fetch_goal_by_id', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"goal": sample_goal_dict}

            result_str = await get_goal_by_id.ainvoke({"goal_id": goal_id}, config=mock_config)
            result = json.loads(result_str)

            assert result["message"] == "Goal found"

    @pytest.mark.asyncio
    async def test_get_goal_by_id_not_found(self, mock_config):
        """Test getting a non-existent goal."""
        goal_id = str(uuid4())

        with patch('app.agents.supervisor.goal_agent.tools.fetch_goal_by_id', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {}

            result_str = await get_goal_by_id.ainvoke({"goal_id": goal_id}, config=mock_config)
            result = json.loads(result_str)

            assert result["error"] == ErrorCodes.GOAL_NOT_FOUND
