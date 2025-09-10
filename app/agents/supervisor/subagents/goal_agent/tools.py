"""Tools for the CRUD Goal Agent with in-memory temporary persistence."""

import json
from datetime import datetime
from typing import Any, List
from uuid import UUID, uuid4

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.agents.supervisor.subagents.goal_agent.models import Audit, Goal, GoalStatus, GoalStatusInfo
from app.utils.tools import get_config_value

# In-memory store: multiple goals per user_id
_GOALS: List[Goal] = []

def _now() -> datetime:
    return datetime.now()

def _error(code: str, message: str, cause: str | None = None) -> dict:
    return {"code": code, "message": message, "cause": cause}

def _get_user_goals(user_id: str) -> List[Goal]:
    """Get all goals for a user."""
    return [g for g in _GOALS if str(g.user_id) == str(user_id)]

def _save_user_goal(goal: Goal) -> None:
    """Save goals for a user."""
    _GOALS.append(goal)

def _update_user_goal(goal: Goal) -> None:
    """Update a goal for a user."""
    for i, g in enumerate(_GOALS):
        if g.goal_id == goal.goal_id:
            _GOALS[i] = goal
            break

def _get_in_progress_goal(user_id: str) -> List[Goal]:
    """Get the in progress goal for a user."""
    return [g for g in _get_user_goals(user_id) if g.status.value == GoalStatus.IN_PROGRESS]

def _get_goal_by_id(user_id: str, goal_id: str) -> Goal:
    """Get a goal by id for a user."""
    return [g for g in _get_user_goals(user_id) if g.goal_id == goal_id]

def _get_in_pending_goal(user_id: str) -> Goal:
    """Get a pending goal for a user."""
    return [g for g in _get_user_goals(user_id) if g.status.value == GoalStatus.PENDING]

@tool(
    name_or_callable="get_goal_requirements",
    description="Get the requirements for a goal",
)
def get_goal_requirements() -> dict[str, Any]:
    """Get the requirements for a goal This is infered from the Goal Model."""
    goal_json = Goal.model_json_schema()
    goal_json = json.loads(goal_json)
    # Remove the user_id field
    goal_json.pop("user_id")
    return goal_json

@tool(
    name_or_callable="create_goal",
    description="Create a new financial goal for a user",
)
def create_goal(data: Goal, config: RunnableConfig) -> str:
    """Create a new financial goal for a user. Make sure if the user has no active goals."""
    try:
        user_key = str(get_config_value(config, "user_id"))


        # Set default values
        goal = Goal(
            goal_id=data.goal_id or uuid4(),
            user_id=UUID(user_key),
            version=data.version or 1,
            goal=data.goal,
            category=data.category,
            nature=data.nature,
            frequency=data.frequency,
            amount=data.amount,
            evaluation=data.evaluation,
            thresholds=data.thresholds,
            reminders=data.reminders,
            status=GoalStatusInfo(value=GoalStatus.PENDING),
            progress=None,
            metadata=data.metadata,
            idempotency_key=data.idempotency_key,
            audit=Audit(
                created_at=_now(),
                updated_at=_now()
            )
        )

        # Add to user's goals
        _save_user_goal(goal)

        # Use model_dump_json() for correct serialization
        goal_json = goal.model_dump_json()
        goal_dict = json.loads(goal_json)

        return json.dumps({
            "message": "Goal created",
            "goal": goal_dict,
            "user_id": user_key
        })
    except Exception as e:
        return json.dumps({
            "error": "CREATE_FAILED",
            "message": f"Failed to create goal: {str(e)}",
            "goals": [],
            "user_id": user_key
        })

@tool(
    name_or_callable="update_goal",
    description="Update an existing goal using the new goal data",
)
def update_goal(data: Goal, config: RunnableConfig) -> str:
    """Update an existing goal."""
    try:
        user_key = str(get_config_value(config, "user_id"))
        goal_to_update = _get_goal_by_id(user_key, str(data.goal_id))

        if not goal_to_update:
            return json.dumps({
                "error": "NO_GOAL_TO_UPDATE",
                "message": "No goal to update, please search all goals or create a new goal using the create_goal tool",
                "goal": None,
                "user_id": user_key
            })

        # Update fields
        updated_goal = Goal(
            goal_id=goal_to_update.goal_id,
            user_id=goal_to_update.user_id,
            version=goal_to_update.version + 1,
            goal=data.goal or goal_to_update.goal,
            category=data.category or goal_to_update.category,
            nature=data.nature or goal_to_update.nature,
            frequency=data.frequency or goal_to_update.frequency,
            amount=data.amount or goal_to_update.amount,
            evaluation=data.evaluation or goal_to_update.evaluation,
            thresholds=data.thresholds or goal_to_update.thresholds,
            reminders=data.reminders or goal_to_update.reminders,
            status= data.status or goal_to_update.status,
            progress=data.progress or goal_to_update.progress,
            metadata=data.metadata or goal_to_update.metadata,
            idempotency_key=data.idempotency_key or goal_to_update.idempotency_key,
            audit=Audit(
                created_at=goal_to_update.audit.created_at if goal_to_update.audit else _now(),
                updated_at=_now()
            )
        )
        _update_user_goal(updated_goal)

        # Use model_dump_json() for correct serialization
        goal_json = updated_goal.model_dump_json()
        goal_dict = json.loads(goal_json)

        return json.dumps({
            "message": "Goal updated",
            "goal": goal_dict,
            "user_id": user_key
        })
    except Exception as e:
        return json.dumps({
            "error": "UPDATE_FAILED",
            "message": f"Failed to update goal: {str(e)}",
            "goal": None,
            "user_id": user_key
        })

@tool(
    name_or_callable="list_goals",
    description="List all goals for a user",
)
def list_goals(config: RunnableConfig) -> str:
    """List all goals for a user."""
    try:
        user_id = str(get_config_value(config, "user_id"))
        if not user_id:
            return json.dumps({
                "error": "MISSING_USER_ID",
                "message": "User ID not found in context",
                "goals": []
            })

        user_goals = _get_user_goals(user_id)

        if not user_goals:
            return json.dumps({
                "message": "No goals found for user",
                "goals": [],
                "user_id": user_id
            })

        # Return active goals (not deleted)
        active_goals = [g for g in user_goals if g.status.value != GoalStatus.DELETED]

        # Serialize each goal correctly
        active_goals_dict = []
        for g in active_goals:
            goal_json = g.model_dump_json()
            goal_dict = json.loads(goal_json)
            active_goals_dict.append(goal_dict)

        return json.dumps({
            "message": f"Found {len(active_goals)} active goals",
            "goals": active_goals_dict,
            "user_id": user_id,
            "count": len(active_goals)
        })

    except Exception as e:
        print(f"Error listing goals: {e}")
        return json.dumps({
            "error": "READ_FAILED",
            "message": f"Failed to get goals: {str(e)}",
            "goals": []
        })

@tool(
    name_or_callable="get_in_progress_goal",
    description="Get the unique in progress goal for a user",
)
def get_in_progress_goal(config: RunnableConfig) -> str:
    """Get the unique in progress goal for a user."""
    try:
        user_id = str(get_config_value(config, "user_id"))
        if not user_id:
            return json.dumps({
                "error": "MISSING_USER_ID",
                "message": "User ID not found in context",
                "goals": []
            })

        in_progress_goal = _get_in_progress_goal(user_id)

        if not in_progress_goal or len(in_progress_goal) == 0:
            return json.dumps({
                "error": "USER_HAS_NO_IN_PROGRESS_GOALS",
                "message": "User has no in progress goals",
                "goal": None,
                "user_id": user_id
            })


        if isinstance(in_progress_goal, list):
            in_progress_goal = in_progress_goal[0] if len(in_progress_goal) > 0 else None

        # Serialize goal correctly
        in_progress_goal_json = in_progress_goal.model_dump_json()
        in_progress_goal_dict = json.loads(in_progress_goal_json)


        return json.dumps({
            "message": "The user has an in progress goal",
            "goal": in_progress_goal_dict,
            "user_id": user_id
        })
    except Exception as e:
        return json.dumps({
            "error": "READ_FAILED",
            "message": f"Failed to get goal: {str(e)}",
            "goal": None,
            "user_id": user_id
        })

@tool(
    name_or_callable="delete_goal",
    description="Soft delete a goal using the goal_id",
)
def delete_goal(goal_id: str, config: RunnableConfig) -> str:
    """Soft delete a goal (set status to deleted)."""
    try:
        user_key = str(get_config_value(config, "user_id"))
        goal_to_delete = _get_goal_by_id(user_key, goal_id)

        if not goal_to_delete:
            return json.dumps({
                "error": "NO_GOAL_TO_DELETE",
                "message": "No goal to delete, please search all goals and ask to the user what goal to delete",
                "user_id": user_key
            })

        goal_to_delete.status.value = GoalStatus.DELETED
        goal_to_delete.audit.updated_at = _now()
        _update_user_goal(goal_to_delete)

        return json.dumps({
            "message": "Goal deleted",
            "goal": goal_to_delete.model_dump_json(),
            "user_id": user_key
        })
    except Exception as e:
        return json.dumps({
            "error": "DELETE_FAILED",
            "message": f"Failed to delete goal: {str(e)}",
            "goal": None,
            "user_id": user_key
        })

@tool(
    name_or_callable="switch_goal_status",
    description="Switch the status of a goal using the goal_id and the new status",
)
def switch_goal_status(goal_id: str, status: str, config: RunnableConfig) -> str:
    """Switch the status of a goal."""
    try:
        user_key = str(get_config_value(config, "user_id"))
        user_goals = _get_user_goals(user_key)
        # Find the goal by id
        goal_to_switch = [g for g in user_goals if g.goal_id == UUID(goal_id)]
        goal_to_switch = goal_to_switch[0] if len(goal_to_switch) > 0 else None

        if not goal_to_switch:
            return json.dumps({
                "error": "NO_GOAL_TO_SWITCH",
                "message": "No goal to switch, please search all goals and ask to the user what goal to switch",
                "goal": None,
                "user_id": user_key
            })

        goal_to_switch.status.value = status
        goal_to_switch.audit.updated_at = _now()
        _update_user_goal(goal_to_switch)
        print(f"Goal status switched: {goal_to_switch}")
        return json.dumps({
            "message": "Goal status switched",
            "goal": goal_to_switch.model_dump_json(),
            "user_id": user_key
        })
    except Exception as e:
        return json.dumps({
            "error": "SWITCH_FAILED",
            "message": f"Failed to switch goal status: {str(e)}",
            "goal": None,
            "user_id": user_key
        })

