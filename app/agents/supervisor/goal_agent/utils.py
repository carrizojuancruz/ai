from app.services.external_context.http_client import FOSHttpClient

from .models import Goal


def preprocess_goal_data(data, user_id: str) -> dict:
    """Preprocess goal data to fix common validation issues."""
    # Create a copy to avoid mutating the original
    if hasattr(data, 'model_dump'):
        data_dict = data.model_dump()
    elif isinstance(data, dict):
        data_dict = data.copy()
    else:
        data_dict = dict(data)

    # Ensure user_id is set
    data_dict['user_id'] = user_id

    # Fix amount structure if it's a simple integer
    if 'amount' in data_dict and data_dict['amount']:
        amount = data_dict['amount']
        if isinstance(amount, dict) and amount.get('type') == 'absolute' and 'absolute' in amount:
                abs_val = amount['absolute']
                if isinstance(abs_val, (int, float)):
                    # Convert to proper AbsoluteAmount structure
                    amount['absolute'] = {
                        'currency': 'USD',
                        'target': abs_val
                    }

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

async def save_goal(goal: Goal):
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
