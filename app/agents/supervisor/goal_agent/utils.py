from app.services.external_context.http_client import FOSHttpClient

from .models import Goal


def preprocess_goal_data(data, user_id: str, is_update: bool = False) -> dict:
    """Preprocess goal data to fix common validation issues and provide sensible defaults.

    Args:
        data: The goal data to preprocess
        user_id: The user ID
        is_update: If True, only normalizes data without adding defaults for missing fields

    """
    from datetime import datetime, timedelta

    from .models import (
        EvaluationConfig,
        FrequencyUnit,
        GoalCategory,
        GoalKind,
        GoalNature,
        GoalStatus,
        Progress,
        WindowState,
    )

    # Create a copy to avoid mutating the original
    if hasattr(data, 'model_dump'):
        data_dict = data.model_dump()
    elif isinstance(data, dict):
        data_dict = data.copy()
    else:
        data_dict = dict(data)

    # Ensure user_id is set
    data_dict['user_id'] = user_id

    # Only add defaults for missing fields if NOT an update
    if not is_update:
        # Ensure 'goal' field (GoalBase) has required title
        if 'goal' not in data_dict or not data_dict['goal']:
            if 'title' in data_dict:
                # Move title to goal structure if provided at top level
                data_dict['goal'] = {'title': data_dict['title']}
            else:
                # Provide default title if completely missing
                data_dict['goal'] = {'title': 'Enter goal title'}
        elif isinstance(data_dict['goal'], dict) and 'title' not in data_dict['goal']:
            data_dict['goal']['title'] = 'Enter goal title'

        # Ensure 'category' field exists with default
        if 'category' not in data_dict or not data_dict['category']:
            data_dict['category'] = {'value': GoalCategory.SAVING.value}

        # Ensure 'nature' field exists with default
        if 'nature' not in data_dict or not data_dict['nature']:
            data_dict['nature'] = {'value': GoalNature.INCREASE.value}

        # Ensure 'kind' field exists with default (financial habit)
        if 'kind' not in data_dict or not data_dict['kind']:
            data_dict['kind'] = GoalKind.FINANCIAL_HABIT.value

        # Ensure 'frequency' field exists with default recurrent monthly
        if 'frequency' not in data_dict or not data_dict['frequency']:
            kind = data_dict.get('kind')
            is_habit = kind in [GoalKind.FINANCIAL_HABIT.value, GoalKind.NONFIN_HABIT.value]
            
            if is_habit:
                now = datetime.now()
                data_dict['frequency'] = {
                    'type': 'recurrent',
                    'recurrent': {
                        'unit': FrequencyUnit.MONTH.value,
                        'every': 1,
                        'start_date': now.isoformat(),
                        'end_date': (now + timedelta(days=365)).isoformat()  # 1 year from now
                    }
                }
        elif isinstance(data_dict['frequency'], dict) and data_dict['frequency'].get('type') == 'recurrent':
            # Ensure recurrent frequency has all required fields
            if 'recurrent' not in data_dict['frequency']:
                now = datetime.now()
                data_dict['frequency']['recurrent'] = {
                    'unit': FrequencyUnit.MONTH.value,
                    'every': 1,
                    'start_date': now.isoformat(),
                    'end_date': (now + timedelta(days=365)).isoformat()
                }

        # Ensure 'amount' field exists with proper structure
        if 'amount' not in data_dict or not data_dict['amount']:
            data_dict['amount'] = {
                'type': 'absolute',
                'absolute': {
                    'currency': 'USD',
                    'target': 1000
                }
            }

        # Ensure 'evaluation' field exists with defaults
        if 'evaluation' not in data_dict or not data_dict['evaluation']:
            data_dict['evaluation'] = EvaluationConfig().model_dump(mode='json')

        # Ensure 'state' field exists with default
        if 'state' not in data_dict or not data_dict['state']:
            data_dict['state'] = WindowState().model_dump(mode='json')

        # Ensure 'status' field exists with default
        if 'status' not in data_dict or not data_dict['status']:
            data_dict['status'] = {'value': GoalStatus.PENDING.value}

        # Ensure 'progress' field exists with default
        if 'progress' not in data_dict or not data_dict['progress']:
            data_dict['progress'] = Progress().model_dump(mode='json')

        # Ensure 'cadence' field exists with default (if recurrent frequency)
        if 'cadence' not in data_dict or not data_dict['cadence']:
            # Default to 30 days if not specified
            data_dict['cadence'] = {'days': 30}

        # Ensure 'no_end_date' is set to False by default
        if 'no_end_date' not in data_dict:
            data_dict['no_end_date'] = False

    # Always normalize structure if fields are present (for both create and update)
    if 'category' in data_dict and isinstance(data_dict['category'], str):
        # Convert string category to proper structure
        data_dict['category'] = {'value': data_dict['category']}

    if 'nature' in data_dict and isinstance(data_dict['nature'], str):
        # Convert string nature to proper structure
        data_dict['nature'] = {'value': data_dict['nature']}

    if 'status' in data_dict and isinstance(data_dict['status'], str):
        # Convert string status to proper structure
        data_dict['status'] = {'value': data_dict['status']}

    if 'amount' in data_dict and isinstance(data_dict['amount'], dict):
        amount = data_dict['amount']
        # Fix amount structure if it's a simple value or incomplete
        if 'type' not in amount:
            amount['type'] = 'absolute'

        if amount.get('type') == 'absolute':
            if 'absolute' not in amount:
                # If no absolute structure but we have a direct value
                target_value = 1000  # default
                if isinstance(amount.get('target'), (int, float)):
                    target_value = amount['target']
                elif isinstance(amount.get('value'), (int, float)):
                    target_value = amount['value']

                amount['absolute'] = {
                    'currency': 'USD',
                    'target': target_value
                }
            elif isinstance(amount['absolute'], (int, float)):
                # Convert direct number to proper structure
                amount['absolute'] = {
                    'currency': 'USD',
                    'target': amount['absolute']
                }
            elif isinstance(amount['absolute'], dict):
                # Ensure currency is set
                if 'currency' not in amount['absolute']:
                    amount['absolute']['currency'] = 'USD'
                # Ensure target is set
                if 'target' not in amount['absolute']:
                    amount['absolute']['target'] = 1000

    # Fix evaluation direction symbols
    if 'evaluation' in data_dict and data_dict['evaluation']:
        evaluation = data_dict['evaluation']
        if isinstance(evaluation, dict) and 'direction' in evaluation:
            direction_map = {
                '>=': '≥',
                '<=': '≤',
                '=': '=',
                '>': '≥',  # Common mistake
                '<': '≤'   # Common mistake
            }
            old_direction = evaluation['direction']
            if old_direction in direction_map:
                evaluation['direction'] = direction_map[old_direction]

    # Return the fixed data dictionary
    return data_dict

async def save_goal(goal: Goal) -> dict:
    fos_client = FOSHttpClient()
    response = await fos_client.post(endpoint="/internal/goals", data=goal.model_dump(mode='json'))
    return response

async def get_goals_for_user(user_id: str):
    fos_client = FOSHttpClient()
    response = await fos_client.get(endpoint=f"/internal/goals/user/{user_id}")
    return response

async def get_in_progress_goals_for_user(user_id: str):
    fos_client = FOSHttpClient()
    response = await fos_client.get(endpoint=f"/internal/goals/user/{user_id}/in-progress")
    return response

async def fetch_goal_by_id(goal_id: str, user_id: str):
    fos_client = FOSHttpClient()
    response = await fos_client.get(endpoint=f"/internal/goals/{goal_id}/{user_id}")
    return response

async def edit_goal(goal: Goal):
    fos_client = FOSHttpClient()
    response = await fos_client.put(endpoint="/internal/goals", data=goal.model_dump(mode='json'))
    return response

async def delete_goal_api(goal_id: str, user_id: str):
    fos_client = FOSHttpClient()
    response = await fos_client.delete(endpoint=f"/internal/goals/user/{user_id}/{goal_id}")
    return response

async def switch_goal_status_api(goal_id: str, status: str, user_id: str):
    fos_client = FOSHttpClient()
    data = {
        "user_id": user_id,
        "status": status
    }
    response = await fos_client.post(endpoint=f"/internal/goals/{goal_id}/status", data=data)
    return response

async def get_goal_history_api(goal_id: str):
    """Get all progress history records for a goal (KISS version)."""
    fos_client = FOSHttpClient()
    response = await fos_client.get(endpoint=f"/internal/goal-progress-history/{goal_id}")
    return response

async def create_history_api(data: dict):
    """Create a new goal progress history record (KISS version)."""
    fos_client = FOSHttpClient()
    response = await fos_client.post(endpoint="/internal/goal-progress-history/", data=data)
    return response

async def update_history_api(record_id: str, data: dict):
    """Update an existing goal progress history record (KISS version)."""
    fos_client = FOSHttpClient()
    response = await fos_client.patch(endpoint=f"/internal/goal-progress-history/{record_id}", data=data)
    return response

async def delete_history_api(record_id: str):
    """Delete a goal progress history record (KISS version)."""
    fos_client = FOSHttpClient()
    response = await fos_client.delete(endpoint=f"/internal/goal-progress-history/{record_id}")
    return response
