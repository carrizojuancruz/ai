"""Tools for the CRUD Goal Agent with in-memory temporary persistence."""

import json
import logging
from datetime import datetime
from uuid import UUID, uuid4

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.utils.tools import get_config_value

from .models import Audit, Goal, GoalStatus, GoalStatusInfo
from .utils import (
    delete_goal_api,
    edit_goal,
    fetch_goal_by_id,
    get_goals_for_user,
    get_in_progress_goals_for_user,
    preprocess_goal_data,
    save_goal,
    switch_goal_status_api,
)


def _now() -> datetime:
    return datetime.now()


@tool(
    name_or_callable="create_goal",
    description="Create a new financial goal for a user",
)
async def create_goal(data, config: RunnableConfig) -> str:
    """Create a new financial goal for a user. Make sure if the user has no active goals."""
    try:
        user_key = str(get_config_value(config, "user_id"))

        # Validate and convert user_id to proper UUID
        try:
            if isinstance(user_key, str) and len(user_key.replace('-', '')) == 32:
                user_uuid = UUID(user_key)
            else:
                # If not a valid UUID string, generate a new one or use a default
                user_uuid = uuid4()
        except (ValueError, TypeError):
            user_uuid = uuid4()

        # Preprocess data to fix common validation issues and add defaults
        processed_data = preprocess_goal_data(data, str(user_uuid))

        # Add default values to processed data
        processed_data['user_id'] = str(user_uuid)
        processed_data['version'] = processed_data.get('version') or 1
        processed_data['status'] = GoalStatusInfo(value=GoalStatus.PENDING)
        processed_data['progress'] = None
        processed_data['audit'] = Audit(created_at=_now(), updated_at=_now())

        # Validate that all required fields are present before creating Goal
        required_fields = ['goal', 'category', 'nature', 'frequency', 'amount']
        missing_fields = [field for field in required_fields if field not in processed_data or not processed_data[field]]

        if missing_fields:
            return json.dumps({
                "error": "MISSING_REQUIRED_FIELDS",
                "message": f"Missing required fields: {', '.join(missing_fields)}. All goals need: title, category, nature, frequency, and amount.",
                "missing_fields": missing_fields,
                "user_id": user_key
            })

        # Create Goal object from processed data
        try:
            goal = Goal(**processed_data)
        except Exception as validation_error:
            return json.dumps({
                "error": "VALIDATION_ERROR",
                "message": f"Goal validation failed: {str(validation_error)}",
                "processed_data": processed_data,
                "user_id": user_key
            })

        # Save goal using async function
        response_goal = await save_goal(goal)

        return json.dumps({
            "message": "Goal created",
            "goal": response_goal.get('goal'),
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
async def update_goal(data, config: RunnableConfig) -> str:
    """Update an existing goal."""
    try:
        user_key = str(get_config_value(config, "user_id"))

        # Preprocess the input data
        if hasattr(data, 'goal_id'):
            goal_id = str(data.goal_id)
        elif isinstance(data, dict):
            goal_id = str(data.get('goal_id'))
        else:
            return json.dumps({
                "error": "INVALID_DATA",
                "message": "Invalid goal data provided",
                "goal": None,
                "user_id": user_key
            })

        goal_to_update_response = await fetch_goal_by_id(goal_id,user_id=user_key)

        if not goal_to_update_response or not goal_to_update_response.get('goal'):
            return json.dumps({
                "error": "NO_GOAL_TO_UPDATE",
                "message": "No goal to update, please search all goals or create a new goal using the create_goal tool",
                "goal": None,
                "user_id": user_key
            })

        # Extract goal data from response
        existing_goal_data = goal_to_update_response.get('goal', {})

        # Preprocess the new data
        processed_data = preprocess_goal_data(data, user_key)

        # Merge existing data with new data (new data takes precedence)
        updated_data = existing_goal_data.copy()
        for key, value in processed_data.items():
            if value is not None:
                updated_data[key] = value

        # Update version and audit info
        updated_data['version'] = updated_data.get('version', 1) + 1
        updated_data['audit'] = {
            'created_at': existing_goal_data.get('audit', {}).get('created_at', _now().isoformat()),
            'updated_at': _now().isoformat()
        }

        # Create Goal object from updated data
        updated_goal = Goal(**updated_data)

        # Save the updated goal
        await edit_goal(updated_goal)

        # Use model_dump_json() for correct serialization
        goal_json = updated_goal.model_dump_json()
        goal_dict = json.loads(goal_json)

        return json.dumps({
            "message": "Goal updated",
            "goal": goal_dict,
            "user_id": user_key
        })
    except Exception as e:
        logging.error(f"Error updating goal: {e}")
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
async def list_goals(config: RunnableConfig) -> str:
    """List all goals for a user."""
    try:
        user_id = str(get_config_value(config, "user_id"))
        if not user_id:
            return json.dumps({
                "error": "MISSING_USER_ID",
                "message": "User ID not found in context",
                "goals": []
            })

        user_goals_response = await get_goals_for_user(user_id)

        if not user_goals_response or not user_goals_response.get('goals'):
            return json.dumps({
                "message": "No goals found for user",
                "goals": [],
                "user_id": user_id
            })

        goals_data = user_goals_response.get('goals', [])
        active_goals = [g for g in goals_data if g.get('status', {}).get('value') != 'deleted']

        active_goals_dict = active_goals

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
async def get_in_progress_goal(config: RunnableConfig) -> str:
    """Get the unique in progress goal for a user."""
    try:
        user_id = str(get_config_value(config, "user_id"))
        if not user_id:
            return json.dumps({
                "error": "MISSING_USER_ID",
                "message": "User ID not found in context",
                "goals": []
            })

        in_progress_response = await get_in_progress_goals_for_user(user_id)

        if not in_progress_response or not in_progress_response.get('goals'):
            return json.dumps({
                "error": "USER_HAS_NO_IN_PROGRESS_GOALS",
                "message": "User has no in progress goals",
                "goal": None,
                "user_id": user_id
            })

        goals_data = in_progress_response.get('goals', [])
        if not goals_data:
            return json.dumps({
                "error": "USER_HAS_NO_IN_PROGRESS_GOALS",
                "message": "User has no in progress goals",
                "goal": None,
                "user_id": user_id
            })

        # Get the first in-progress goal (should be unique)
        in_progress_goal_dict = goals_data[0]


        return json.dumps({
            "message": "The user has an in progress goal",
            "goal": in_progress_goal_dict,
            "user_id": user_id
        })
    except Exception as e:
        logging.error(f"Error getting in-progress goal: {e}")
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
async def delete_goal(goal_id: str, config: RunnableConfig) -> str:
    """Soft delete a goal (set status to deleted)."""
    try:
        user_key = str(get_config_value(config, "user_id"))

        # First check if goal exists
        goal_response = await fetch_goal_by_id(goal_id, user_key)

        if not goal_response or not goal_response.get('goal'):
            return json.dumps({
                "error": "NO_GOAL_TO_DELETE",
                "message": "No goal to delete, please search all goals and ask to the user what goal to delete",
                "user_id": user_key
            })

        # Delete via API
        delete_response = await delete_goal_api(goal_id, user_key)

        if delete_response:
            return json.dumps({
                "message": "Goal deleted",
                "goal": goal_response.get('goal'),
                "user_id": user_key
            })
        else:
            return json.dumps({
                "error": "DELETE_FAILED",
                "message": "Failed to delete goal via API",
                "goal": None,
                "user_id": user_key
            })
    except Exception as e:
        logging.error(f"Error deleting goal: {e}")
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
async def switch_goal_status(goal_id: str, status: str, config: RunnableConfig) -> str:
    """Switch the status of a goal."""
    try:
        user_key = str(get_config_value(config, "user_id"))

        # Validate status
        try:
            GoalStatus(status)  # Just validate, don't store
        except ValueError:
            return json.dumps({
                "error": "INVALID_STATUS",
                "message": f"Invalid status '{status}'. Valid statuses are: {[s.value for s in GoalStatus]}",
                "goal": None,
                "user_id": user_key
            })

        # First check if goal exists
        goal_response = await fetch_goal_by_id(goal_id, user_key)

        if not goal_response or not goal_response.get('goal'):
            return json.dumps({
                "error": "NO_GOAL_TO_SWITCH",
                "message": "No goal to switch, please search all goals and ask to the user what goal to switch",
                "goal": None,
                "user_id": user_key
            })

        # Switch status via API
        switch_response = await switch_goal_status_api(goal_id, status, user_key)

        if switch_response:
            # Get updated goal to return
            updated_goal_response = await fetch_goal_by_id(goal_id, user_key)
            updated_goal = updated_goal_response.get('goal', {}) if updated_goal_response else {}

            return json.dumps({
                "message": "Goal status switched",
                "goal": updated_goal,
                "user_id": user_key
            })
        else:
            return json.dumps({
                "error": "SWITCH_FAILED",
                "message": "Failed to switch goal status via API",
                "goal": None,
                "user_id": user_key
            })

    except Exception as e:
        logging.error(f"Error switching goal status: {e}")
        return json.dumps({
            "error": "SWITCH_FAILED",
            "message": f"Failed to switch goal status: {str(e)}",
            "goal": None,
            "user_id": user_key
        })


@tool(
    name_or_callable="get_goal_by_id",
    description="Get a specific goal by its ID",
)
async def get_goal_by_id(goal_id: str, config: RunnableConfig) -> str:
    """Get a specific goal by its ID."""
    try:
        user_key = str(config.get("configurable", {}).get("user_id"))
        goal_response = await fetch_goal_by_id(goal_id, user_key)

        if not goal_response or not goal_response.get('goal'):
            return json.dumps({
                "error": "GOAL_NOT_FOUND",
                "message": f"No goal found with ID: {goal_id}",
                "goal": None,
                "user_id": user_key
            })

        # Extract goal from response
        goal_dict = goal_response.get('goal', {})

        return json.dumps({
            "message": "Goal found",
            "goal": goal_dict,
            "user_id": user_key
        })
    except Exception as e:
        logging.error(f"Error fetching goal by ID: {e}")
        return json.dumps({
            "error": "READ_FAILED",
            "message": f"Failed to get goal: {str(e)}",
            "goal": None,
            "user_id": user_key
        })
