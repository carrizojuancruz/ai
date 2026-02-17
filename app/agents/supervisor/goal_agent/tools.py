"""Tools for the CRUD Goal Agent with in-memory temporary persistence."""

import json
import logging
from datetime import datetime
from uuid import UUID, uuid4

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.utils.tools import get_config_value

from .constants import ErrorCodes
from .helpers import extract_goal_from_response, extract_goal_id
from .models import Goal, GoalStatus
from .response_builder import ResponseBuilder
from .state_machine import GoalStatusTransitionValidator
from .tools_descriptions import ToolDescriptions
from .utils import (
    create_history_api,
    delete_goal_api,
    delete_history_api,
    edit_goal,
    fetch_goal_by_id,
    get_goal_history_api,
    get_in_progress_goals_for_user,
    preprocess_goal_data,
    save_goal,
    switch_goal_status_api,
    update_history_api,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now()


def _format_decimal(value) -> str:
    normalized = value.normalize()
    value_str = format(normalized, 'f')
    if '.' in value_str:
        value_str = value_str.rstrip('0').rstrip('.')
    return value_str


@tool(
    name_or_callable="create_goal",
    description=ToolDescriptions.GOAL_CREATION_TOOL,
)
async def create_goal(data, config: RunnableConfig) -> str:
    """Create a new financial goal for a user. Make sure if the user has no active goals."""
    try:
        data = dict(data) if not isinstance(data, dict) else data

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

        # Add default values to processed data (only what's not handled by preprocess)
        processed_data['user_id'] = str(user_uuid)
        processed_data['version'] = processed_data.get('version') or 1
        processed_data['audit'] = {'created_at': _now().isoformat(), 'updated_at': _now().isoformat()}

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
        # Serialize goal properly
        goal_dict = response_goal

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
    description="Update an existing goal using the new goal data. Cannot change status - use switch_goal_status tool instead.",
)
async def update_goal(data, config: RunnableConfig) -> str:
    """Update an existing goal. Status changes are not allowed through this tool - use switch_goal_status instead."""
    try:
        user_key = str(get_config_value(config, "user_id"))

        # Extract goal_id using helper
        goal_id = extract_goal_id(data)
        if not goal_id:
            return ResponseBuilder.invalid_data(user_key, "Invalid goal data provided")

        # Fetch existing goal
        goal_to_update_response = await fetch_goal_by_id(goal_id, user_id=user_key)
        existing_goal_data = extract_goal_from_response(goal_to_update_response)

        if not existing_goal_data:
            return ResponseBuilder.error(
                error_code=ErrorCodes.NO_GOAL_TO_UPDATE,
                message="No goal to update, please search all goals or create a new goal using the create_goal tool",
                user_id=user_key
            )

        # Preprocess the new data (is_update=True to avoid adding defaults)
        processed_data = preprocess_goal_data(data, user_key, is_update=True)

        # Check if status change is being attempted
        status_change_attempted = False
        if 'status' in processed_data and processed_data['status'] is not None:
            status_change_attempted = True
            del processed_data['status']

        # Merge existing data with new data (new data takes precedence)
        updated_data = existing_goal_data.copy()
        for key, value in processed_data.items():
            if value is not None:
                updated_data[key] = value

        # Remove metadata to avoid validation issues with backend format
        if 'metadata' in updated_data:
            del updated_data['metadata']

        # Auto-calculate percent_complete if progress.current_value was updated
        if 'progress' in updated_data and updated_data['progress']:
            from decimal import Decimal

            progress = updated_data['progress']
            try:
                current_value = Decimal(str(progress.get('current_value', 0)))

                # Get target from amount
                amount = updated_data.get('amount', {})
                if amount.get('type') == 'absolute' and amount.get('absolute'):
                    target = Decimal(str(amount['absolute'].get('target', 0)))

                    if target > 0:
                        percent = (current_value / target) * Decimal('100')
                        # Cap at 100% and format as string
                        progress['percent_complete'] = str(min(percent, Decimal('100')))
                    else:
                        progress['percent_complete'] = '0'

                # Always update timestamp
                progress['updated_at'] = _now().isoformat()
            except (ValueError, TypeError, ZeroDivisionError) as e:
                logger.warning(f"Error calculating percent_complete: {e}")
                # Keep existing percent_complete if calculation fails

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

        # Build response message
        message = "Goal updated"
        if status_change_attempted:
            available_statuses = [status.value for status in GoalStatus]
            message += f" except the status. To change the status, use the switch_goal_status tool with one of these values: {', '.join(available_statuses)}"

        return ResponseBuilder.success(message=message, user_id=user_key, goal=goal_dict)

    except Exception as e:
        logger.error(f"Error updating goal: {e}", exc_info=True)
        return ResponseBuilder.error(
            error_code=ErrorCodes.UPDATE_FAILED,
            message=f"Failed to update goal: {str(e)}",
            user_id=user_key
        )

@tool(
    name_or_callable="get_in_progress_goal",
    description="Get the unique in progress goal for a user",
)
async def get_in_progress_goal(config: RunnableConfig) -> str:
    """Get the unique in progress goal for a user."""
    try:
        user_id = str(get_config_value(config, "user_id"))
        if not user_id:
            return ResponseBuilder.missing_user_id()

        in_progress_response = await get_in_progress_goals_for_user(user_id)

        if not in_progress_response or not in_progress_response.get('goals'):
            return ResponseBuilder.error(
                error_code=ErrorCodes.USER_HAS_NO_IN_PROGRESS_GOALS,
                message="User has no in progress goals",
                user_id=user_id
            )

        goals_data = in_progress_response.get('goals', [])
        if not goals_data:
            return ResponseBuilder.error(
                error_code=ErrorCodes.USER_HAS_NO_IN_PROGRESS_GOALS,
                message="User has no in progress goals",
                user_id=user_id
            )

        # Get the first in-progress goal (should be unique)
        in_progress_goal = goals_data[0]

        return ResponseBuilder.success(
            message="The user has an in progress goal",
            user_id=user_id,
            goal=in_progress_goal
        )

    except Exception as e:
        logger.error(f"Error getting in-progress goal: {e}", exc_info=True)
        return ResponseBuilder.error(
            error_code=ErrorCodes.READ_FAILED,
            message=f"Failed to get goal: {str(e)}",
            user_id=user_id if 'user_id' in locals() else ""
        )

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
        existing_goal = extract_goal_from_response(goal_response)

        if not existing_goal:
            return ResponseBuilder.error(
                error_code=ErrorCodes.NO_GOAL_TO_DELETE,
                message="No goal to delete, please search all goals and ask to the user what goal to delete",
                user_id=user_key
            )

        # Delete via API
        delete_response = await delete_goal_api(goal_id, user_key)

        if delete_response:
            return ResponseBuilder.success(
                message="Goal deleted",
                user_id=user_key,
                goal=existing_goal
            )
        else:
            return ResponseBuilder.error(
                error_code=ErrorCodes.DELETE_FAILED,
                message="Failed to delete goal via API",
                user_id=user_key
            )

    except Exception as e:
        logger.error(f"Error deleting goal: {e}", exc_info=True)
        return ResponseBuilder.error(
            error_code=ErrorCodes.DELETE_FAILED,
            message=f"Failed to delete goal: {str(e)}",
            user_id=user_key if 'user_key' in locals() else ""
        )

@tool(
    name_or_callable="switch_goal_status",
    description="Switch the status of a goal using the goal_id and the new status. Valid transitions: pending/paused/off_track → in_progress, in_progress → completed/paused/off_track/error. Note: To delete a goal, use delete_goal tool instead.",
)
async def switch_goal_status(goal_id: str, status: str, config: RunnableConfig) -> str:
    """Switch the status of a goal with validation of state transitions. Cannot transition to 'deleted' - use delete_goal tool instead."""
    try:
        user_key = str(get_config_value(config, "user_id"))

        # Validate status exists in enum
        try:
            new_status = GoalStatus(status)
        except ValueError:
            available_statuses = [s.value for s in GoalStatus]
            return ResponseBuilder.error(
                error_code=ErrorCodes.INVALID_STATUS,
                message=f"Invalid status '{status}'. Valid statuses are: {', '.join(available_statuses)}",
                user_id=user_key
            )

        # Check if trying to delete - should use delete_goal tool instead
        if new_status == GoalStatus.DELETED:
            return ResponseBuilder.error(
                error_code=ErrorCodes.INVALID_TRANSITION,
                message="To delete a goal, use the delete_goal tool instead of changing status to 'deleted'",
                user_id=user_key
            )

        # First check if goal exists and get current status
        goal_response = await fetch_goal_by_id(goal_id, user_key)
        current_goal = extract_goal_from_response(goal_response)

        if not current_goal:
            return ResponseBuilder.error(
                error_code=ErrorCodes.NO_GOAL_TO_SWITCH,
                message="No goal to switch, please search all goals and ask to the user what goal to switch",
                user_id=user_key
            )

        # Extract current status
        current_status_str = current_goal.get('status', {}).get('value')

        if not current_status_str:
            return ResponseBuilder.error(
                error_code=ErrorCodes.INVALID_GOAL_STATE,
                message="Cannot determine current goal status",
                user_id=user_key
            )

        # Validate state transition using state machine
        current_status = GoalStatus(current_status_str)
        is_valid, error_message = GoalStatusTransitionValidator.can_transition(current_status, new_status)

        if not is_valid:
            available_transitions = GoalStatusTransitionValidator.get_valid_transitions(current_status)
            return ResponseBuilder.error(
                error_code=ErrorCodes.INVALID_TRANSITION,
                message=error_message,
                user_id=user_key,
                goal=current_goal,
                current_status=current_status.value,
                attempted_status=status,
                valid_transitions=available_transitions
            )

        # Switch status via API
        switch_response = await switch_goal_status_api(goal_id, status, user_key)

        if switch_response:
            # Get updated goal to return
            updated_goal_response = await fetch_goal_by_id(goal_id, user_key)
            updated_goal = extract_goal_from_response(updated_goal_response) or {}

            return ResponseBuilder.success(
                message=f"Goal status switched from '{current_status.value}' to '{status}'",
                user_id=user_key,
                goal=updated_goal,
                previous_status=current_status.value,
                new_status=status
            )
        else:
            return ResponseBuilder.error(
                error_code=ErrorCodes.SWITCH_FAILED,
                message="Failed to switch goal status via API. The transition may not be allowed by the backend.",
                user_id=user_key,
                goal=current_goal
            )

    except Exception as e:
        logger.error(f"Error switching goal status: {e}", exc_info=True)
        return ResponseBuilder.error(
            error_code=ErrorCodes.SWITCH_FAILED,
            message=f"Failed to switch goal status: {str(e)}",
            user_id=user_key
        )


@tool(
    name_or_callable="get_goal_by_id",
    description="Get a specific goal by its ID",
)
async def get_goal_by_id(goal_id: str, config: RunnableConfig) -> str:
    """Get a specific goal by its ID."""
    try:
        user_key = str(config.get("configurable", {}).get("user_id"))
        goal_response = await fetch_goal_by_id(goal_id, user_key)
        goal_dict = extract_goal_from_response(goal_response)

        if not goal_dict:
            return ResponseBuilder.error(
                error_code=ErrorCodes.GOAL_NOT_FOUND,
                message=f"No goal found with ID: {goal_id}",
                user_id=user_key
            )

        return ResponseBuilder.success(
            message="Goal found",
            user_id=user_key,
            goal=goal_dict
        )

    except Exception as e:
        logger.error(f"Error fetching goal by ID: {e}", exc_info=True)
        return ResponseBuilder.error(
            error_code=ErrorCodes.READ_FAILED,
            message=f"Failed to get goal: {str(e)}",
            user_id=user_key if 'user_key' in locals() else ""
        )


@tool(
    name_or_callable="get_goal_history",
    description=ToolDescriptions.GET_GOAL_HISTORY_TOOL,
)
async def get_goal_history(goal_id: str, config: RunnableConfig) -> str:
    """Get all progress history records for a specific goal."""
    try:
        user_key = str(get_config_value(config, "user_id"))

        response = await get_goal_history_api(goal_id=goal_id)

        if not response:
            return ResponseBuilder.error(
                error_code=ErrorCodes.HISTORY_READ_FAILED,
                message=f"Failed to retrieve history for goal {goal_id}",
                user_id=user_key
            )

        # Extract records from response object
        records = response.get('records', []) if isinstance(response, dict) else []
        total = response.get('total', len(records)) if isinstance(response, dict) else len(records)

        return json.dumps({
            "message": f"Found {len(records)} history records for goal",
            "goal_id": goal_id,
            "records": records,
            "total": total,
            "user_id": user_key
        })

    except Exception as e:
        logger.error(f"Error getting goal history: {e}", exc_info=True)
        return ResponseBuilder.error(
            error_code=ErrorCodes.HISTORY_READ_FAILED,
            message=f"Failed to get goal history: {str(e)}",
            user_id=user_key if 'user_key' in locals() else ""
        )


@tool(
    name_or_callable="create_history_record",
    description=ToolDescriptions.CREATE_HISTORY_RECORD_TOOL,
)
async def create_history_record(data: dict, config: RunnableConfig) -> str:
    """Create a new progress history record for a goal."""
    try:
        user_key = str(get_config_value(config, "user_id"))

        # Ensure user_id is set
        if 'user_id' not in data or not data['user_id']:
            data['user_id'] = user_key

        # Validate required fields
        required_fields = ['goal_id', 'period_start', 'period_end', 'period_type']
        missing_fields = [field for field in required_fields if field not in data or not data[field]]

        if missing_fields:
            return ResponseBuilder.error(
                error_code=ErrorCodes.MISSING_REQUIRED_FIELDS,
                message=f"Missing required fields: {', '.join(missing_fields)}",
                user_id=user_key,
                missing_fields=missing_fields
            )

        # Validate period_type
        valid_period_types = ['day', 'week', 'month', 'quarter', 'year']
        if data.get('period_type') not in valid_period_types:
            return ResponseBuilder.error(
                error_code=ErrorCodes.HISTORY_INVALID_PERIOD,
                message=f"Invalid period_type. Must be one of: {', '.join(valid_period_types)}",
                user_id=user_key
            )

        # Create the record via API
        response = await create_history_api(data=data)

        if not response or not response.get('success'):
            error_msg = response.get('message', 'Unknown error') if response else 'API call failed'
            return ResponseBuilder.error(
                error_code=ErrorCodes.HISTORY_CREATE_FAILED,
                message=f"Failed to create history record: {error_msg}",
                user_id=user_key
            )

        record = response.get('record', {})
        message = response.get('message', 'History record created')

        return json.dumps({
            "message": message,
            "record": record,
            "user_id": user_key
        })

    except Exception as e:
        logger.error(f"Error creating history record: {e}", exc_info=True)
        return ResponseBuilder.error(
            error_code=ErrorCodes.HISTORY_CREATE_FAILED,
            message=f"Failed to create history record: {str(e)}",
            user_id=user_key if 'user_key' in locals() else ""
        )


@tool(
    name_or_callable="update_history_record",
    description=ToolDescriptions.UPDATE_HISTORY_RECORD_TOOL,
)
async def update_history_record(record_id: str, data: dict, config: RunnableConfig) -> str:
    """Update an existing progress history record."""
    try:
        user_key = str(get_config_value(config, "user_id"))

        # Validate that non-updatable fields are not included
        non_updatable_fields = ['goal_id', 'user_id', 'period_start', 'period_end', 'period_type']
        attempted_updates = [field for field in non_updatable_fields if field in data]

        if attempted_updates:
            return ResponseBuilder.error(
                error_code=ErrorCodes.HISTORY_UPDATE_FAILED,
                message=f"Cannot update these fields: {', '.join(attempted_updates)}. These define the record identity.",
                user_id=user_key
            )

        # Update the record via API
        response = await update_history_api(record_id=record_id, data=data)

        if not response or not response.get('success'):
            error_msg = response.get('message', 'Unknown error') if response else 'API call failed'
            return ResponseBuilder.error(
                error_code=ErrorCodes.HISTORY_UPDATE_FAILED,
                message=f"Failed to update history record: {error_msg}",
                user_id=user_key
            )

        record = response.get('record', {})
        message = response.get('message', 'History record updated')

        return json.dumps({
            "message": message,
            "record": record,
            "user_id": user_key
        })

    except Exception as e:
        logger.error(f"Error updating history record: {e}", exc_info=True)
        return ResponseBuilder.error(
            error_code=ErrorCodes.HISTORY_UPDATE_FAILED,
            message=f"Failed to update history record: {str(e)}",
            user_id=user_key if 'user_key' in locals() else ""
        )


@tool(
    name_or_callable="delete_history_record",
    description=ToolDescriptions.DELETE_HISTORY_RECORD_TOOL,
)
async def delete_history_record(record_id: str, config: RunnableConfig) -> str:
    """Delete a progress history record permanently."""
    try:
        user_key = str(get_config_value(config, "user_id"))

        # Delete via API
        response = await delete_history_api(record_id=record_id)

        if not response or not response.get('success'):
            error_msg = response.get('message', 'Unknown error') if response else 'API call failed'
            return ResponseBuilder.error(
                error_code=ErrorCodes.HISTORY_UPDATE_FAILED,
                message=f"Failed to delete history record: {error_msg}",
                user_id=user_key
            )

        message = response.get('message', 'History record deleted')

        return json.dumps({
            "message": message,
            "deleted_id": record_id,
            "user_id": user_key
        })

    except Exception as e:
        logger.error(f"Error deleting history record: {e}", exc_info=True)
        return ResponseBuilder.error(
            error_code=ErrorCodes.HISTORY_UPDATE_FAILED,
            message=f"Failed to delete history record: {str(e)}",
            user_id=user_key if 'user_key' in locals() else ""
        )


@tool(
    name_or_callable="link_asset_to_goal",
    description=ToolDescriptions.LINK_ASSET_TO_GOAL_TOOL,
)
async def link_asset_to_goal(goal_id: str, amount: float, config: RunnableConfig, asset_name: str = None) -> str:
    """Add the value of an asset to a goal's current progress."""
    try:
        user_key = str(get_config_value(config, "user_id"))

        # Validate amount is positive
        if amount <= 0:
            return ResponseBuilder.error(
                error_code=ErrorCodes.INVALID_DATA,
                message="Amount must be positive",
                user_id=user_key
            )

        # Fetch existing goal
        goal_response = await fetch_goal_by_id(goal_id, user_id=user_key)
        existing_goal_data = extract_goal_from_response(goal_response)

        if not existing_goal_data:
            return ResponseBuilder.error(
                error_code=ErrorCodes.NO_GOAL_TO_UPDATE,
                message="Goal not found",
                user_id=user_key
            )

        # Get current progress value
        from decimal import Decimal
        current_value = Decimal(str(existing_goal_data.get('progress', {}).get('current_value', 0)))
        amount_decimal = Decimal(str(amount))
        new_value = current_value + amount_decimal
        new_value_str = _format_decimal(new_value)
        amount_str = _format_decimal(amount_decimal)

        # Merge with existing data
        updated_data = existing_goal_data.copy()
        updated_data['progress']['current_value'] = new_value_str
        updated_data['progress']['updated_at'] = _now().isoformat()

        # Update version and audit
        updated_data['version'] = updated_data.get('version', 1) + 1
        updated_data['audit'] = {
            'created_at': existing_goal_data.get('audit', {}).get('created_at', _now().isoformat()),
            'updated_at': _now().isoformat()
        }

        # Remove metadata if present
        if 'metadata' in updated_data:
            del updated_data['metadata']

        # Create and save updated goal
        updated_goal = Goal(**updated_data)
        await edit_goal(updated_goal)

        # Build response
        goal_json = updated_goal.model_dump_json()
        goal_dict = json.loads(goal_json)

        asset_context = f" ({asset_name})" if asset_name else ""
        message = f"Added {amount_str} from asset{asset_context} to goal. New progress: {new_value_str}"

        return ResponseBuilder.success(
            message=message,
            user_id=user_key,
            goal=goal_dict
        )

    except Exception as e:
        logger.error(f"Error linking asset to goal: {e}", exc_info=True)
        return ResponseBuilder.error(
            error_code=ErrorCodes.UPDATE_FAILED,
            message=f"Failed to link asset to goal: {str(e)}",
            user_id=user_key if 'user_key' in locals() else ""
        )
