"""
Tools for the CRUD Budget Agent with in-memory temporary persistence.
"""

from langchain_core.tools import tool
from uuid import uuid4
from datetime import datetime

from app.agents.supervisor.subagents.budget_agent.models import Budget

# In-memory store: one active budget per user_id
_BUDGETS: dict[str, Budget] = {}

def _now() -> datetime:
    return datetime.now()

def _error(code: str, message: str, cause: str | None = None) -> dict:
    return {"code": code, "message": message, "cause": cause}

@tool
def create_budget(data: Budget) -> str:
    """
    Create a new budget for a user.
    """
    try:
        user_key = str(data.user_id)
        if user_key in _BUDGETS and _BUDGETS[user_key].is_active:
            return str(_error(
                "BUDGET_ALREADY_EXISTS",
                "This user already has an active budget. Delete it first.",
                None,
            ))

        budget = Budget(
            budget_id=data.budget_id or uuid4(),
            user_id=data.user_id,
            version=(data.version or 1),
            budget_name=data.budget_name,
            category_limits=data.category_limits or {},
            since=data.since,
            until=data.until,
            is_active=True,
            created_at=_now(),
            updated_at=_now(),
        )
        _BUDGETS[user_key] = budget
        return budget.model_dump_json()
    except Exception as e:
        return str(_error("CREATE_FAILED", "Failed to create budget", str(e)))

@tool
def update_budget(data: Budget) -> str:
    """
    Update an existing budget.
    """
    try:
        user_key = str(data.user_id)
        existing = _BUDGETS.get(user_key)
        if not existing or not existing.is_active:
            return str(_error("NOT_FOUND", "No active budget found for user", None))

        updated = Budget(
            budget_id=existing.budget_id,
            user_id=existing.user_id,
            version=existing.version + 1,
            budget_name=data.budget_name or existing.budget_name,
            category_limits=data.category_limits or existing.category_limits,
            since=data.since or existing.since,
            until=data.until or existing.until,
            is_active=True,
            created_at=existing.created_at,
            updated_at=_now(),
        )
        _BUDGETS[user_key] = updated
        return updated.model_dump_json()
    except Exception as e:
        return str(_error("UPDATE_FAILED", "Failed to update budget", str(e)))

@tool
def get_active_budget(user_id: str) -> str:
    """
    Summarize a budget.
    """
    try:
        existing = _BUDGETS.get(str(user_id))
        if not existing or not existing.is_active:
            return str(_error("NOT_FOUND", "No active budget found for user", None))
        return existing.model_dump_json()
    except Exception as e:
        return str(_error("READ_FAILED", "Failed to get active budget", str(e)))

@tool
def delete_budget(user_id: str, budget_id: str) -> str:
    """
    Delete a budget.
    """
    try:
        user_key = str(user_id)
        existing = _BUDGETS.get(user_key)
        if not existing or not existing.is_active:
            return str(_error("NOT_FOUND", "No active budget to delete", None))
        if str(existing.budget_id) != str(budget_id):
            return str(_error("ID_MISMATCH", "Budget ID does not match active budget", None))
        existing.is_active = False
        existing.updated_at = _now()
        _BUDGETS[user_key] = existing
        return existing.model_dump_json()
    except Exception as e:
        return str(_error("DELETE_FAILED", "Failed to delete budget", str(e)))
