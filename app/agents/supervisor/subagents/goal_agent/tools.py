"""
Tools for the CRUD Goal Agent with in-memory temporary persistence.
"""

from langchain_core.tools import tool
from uuid import uuid4, UUID
from datetime import datetime
from typing import List, Any
import json

from langchain_core.runnables import RunnableConfig

from app.agents.supervisor.subagents.goal_agent.models import (
    Goal, GoalStatus, GoalStatusInfo, Progress, Audit
)

# In-memory store: multiple goals per user_id
_GOALS: List[Goal] = []

def _now() -> datetime:
    return datetime.now()

def _error(code: str, message: str, cause: str | None = None) -> dict:
    return {"code": code, "message": message, "cause": cause}

def _get_user_goals(user_id: str) -> List[Goal]:
    """Get all goals for a user."""
    return [g for g in _GOALS if str(g.user_id) == str(user_id)]

def _save_user_goals(goals: List[Goal]) -> None:
    """Save goals for a user."""
    _GOALS.extend(goals)

def _update_user_goal(goal: Goal) -> None:
    """Update a goal for a user."""
    for i, g in enumerate(_GOALS):
        if g.goal_id == goal.goal_id:
            _GOALS[i] = goal
            break

def _get_in_progress_goal(user_id: str) -> List[Goal]:
    """Get the in progress goal for a user."""
    return [g for g in _get_user_goals(user_id) if g.status.value == GoalStatus.IN_PROGRESS]

@tool
def get_goal_requirements() -> dict[str, Any]:
    """
    Get the requirements for a goal.
    This is infered from the Goal Model
    """
    return Goal.model_json_schema()

@tool
def create_goal(data: Goal, config: RunnableConfig) -> str:
    """
    Create a new financial goal for a user.
    Make sure if the user has no active goals.
    """
    try:
        user_key = str(config.get("configurable", {}).get("user_id"))
        in_progress_goal = _get_in_progress_goal(user_key)

        if in_progress_goal:
            # Serialize the in progress goals correctly
            in_progress_goals_dict = []
            for g in in_progress_goal:
                goal_json = g.model_dump_json()
                goal_dict = json.loads(goal_json)
                in_progress_goals_dict.append(goal_dict)
            
            return json.dumps({
                "error": "GOAL_ALREADY_EXISTS",
                "message": "User already has an active goal",
                "goals": in_progress_goals_dict,
                "user_id": user_key
            })
        
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
        user_goals = _get_user_goals(user_key)
        user_goals.append(goal)
        _save_user_goals(user_goals)

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

@tool
def update_goal(data: Goal, config: RunnableConfig) -> str:
    """
    Update an existing goal.
    """
    try:
        user_key = str(config.get("configurable", {}).get("user_id"))
        user_goals = _get_user_goals(user_key)

        # Check if the status goal is not "error" or "deleted"
        if data.status.value in [GoalStatus.ERROR, GoalStatus.DELETED]:
            return json.dumps({
                "error": "INVALID_STATUS",
                "message": "Goal status is not valid",
                "goals": [],
                "user_id": user_key
            })
        
        # Find the goal to update
        goal_index = None
        for i, g in enumerate(user_goals):
            if g.goal_id == data.goal_id:
                goal_index = i
                break
        
        if goal_index is None:
            return json.dumps({
                "error": "NOT_FOUND",
                "message": "Goal not found",
                "goals": [],
                "user_id": user_key
            })
        
        existing_goal = user_goals[goal_index]
        
        # Update fields
        updated_goal = Goal(
            goal_id=existing_goal.goal_id,
            user_id=existing_goal.user_id,
            version=existing_goal.version + 1,
            goal=data.goal or existing_goal.goal,
            category=data.category or existing_goal.category,
            nature=data.nature or existing_goal.nature,
            frequency=data.frequency or existing_goal.frequency,
            amount=data.amount or existing_goal.amount,
            evaluation=data.evaluation or existing_goal.evaluation,
            thresholds=data.thresholds or existing_goal.thresholds,
            reminders=data.reminders or existing_goal.reminders,
            status= data.status or existing_goal.status,
            progress=data.progress or existing_goal.progress,
            metadata=data.metadata or existing_goal.metadata,
            idempotency_key=data.idempotency_key or existing_goal.idempotency_key,
            audit=Audit(
                created_at=existing_goal.audit.created_at if existing_goal.audit else _now(),
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
            "goals": [],
            "user_id": user_key
        })

@tool
def list_goals(config: RunnableConfig) -> str:
    """
    List all goals for a user.
    """
    try:
        user_id = str(config.get("configurable", {}).get("user_id"))
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

@tool
def get_in_progress_goal(config: RunnableConfig) -> str:
    """
    Get the unique in progress goal for a user.
    """
    try:
        user_id = str(config.get("configurable", {}).get("user_id"))
        if not user_id:
            return json.dumps({
                "error": "MISSING_USER_ID",
                "message": "User ID not found in context",
                "goals": []
            })
        
        user_goals = _get_user_goals(user_id)

        in_progress_goals = [g for g in user_goals if g.status.value == GoalStatus.IN_PROGRESS]

        # Serialize each goal correctly
        in_progress_goals_dict = []
        for g in in_progress_goals:
            goal_json = g.model_dump_json()
            goal_dict = json.loads(goal_json)
            in_progress_goals_dict.append(goal_dict)

        return json.dumps({
            "message": f"Found {len(in_progress_goals)} in progress goals",
            "goals": in_progress_goals_dict,
            "user_id": user_id,
            "count": len(in_progress_goals)
        })
    except Exception as e:
        return json.dumps({
            "error": "READ_FAILED",
            "message": f"Failed to get goal: {str(e)}",
            "goals": []
        })

@tool
def delete_goal(config: RunnableConfig) -> str:
    """
    Soft delete a goal (set status to deleted).
    """
    try:
        user_key = str(config.get("configurable", {}).get("user_id"))
        user_goals = _get_user_goals(user_key)
        
        # Find and update the goal
        for i, goal in enumerate(user_goals):
            if str(goal.goal_id) == str(config.get("configurable", {}).get("goal_id")):
                # Soft delete
                goal.status.value = GoalStatus.DELETED
                if goal.audit:
                    goal.audit.updated_at = _now()
                else:
                    goal.audit = Audit(created_at=_now(), updated_at=_now())
                
                _update_user_goal(goal)
                
                # Use model_dump_json() for correct serialization
                goal_json = goal.model_dump_json()
                goal_dict = json.loads(goal_json)
                
                return json.dumps({
                    "message": "Goal deleted",
                    "goal": goal_dict,
                    "user_id": user_key
                })
        
        return json.dumps({
            "error": "NOT_FOUND",
            "message": "Goal not found",
            "goals": [],
            "user_id": user_key
        })
    except Exception as e:
        return json.dumps({
            "error": "DELETE_FAILED",
            "message": f"Failed to delete goal: {str(e)}",
            "goals": [],
            "user_id": user_key
        })

# @tool
# def calculate_progress(user_id: str, goal_id: str) -> str:
#     """
#     Calculate and update progress for a goal.
#     """
#     try:
#         user_key = str(user_id)
#         user_goals = _get_user_goals(user_key)
        
#         # Find the goal
#         goal_index = None
#         for i, g in enumerate(user_goals):
#             if str(g.goal_id) == str(goal_id):
#                 goal_index = i
#                 break
        
#         if goal_index is None:
#             return json.dumps({
#                 "error": "NOT_FOUND",
#                 "message": "Goal not found",
#                 "goals": [],
#                 "user_id": user_key
#             })
        
#         goal = user_goals[goal_index]
        
#         # Simple progress calculation (dummy for now)
#         # In real implementation, this would query transaction data
#         if goal.amount.type == "absolute" and goal.amount.absolute:
#             target = goal.amount.absolute.target
#             # Simulate progress (replace with real calculation)
#             current_value = target * Decimal("0.6")  # 60% progress
#             percent_complete = (current_value / target) * 100
#         else:
#             current_value = Decimal("0")
#             percent_complete = Decimal("0")
        
#         # Update progress
#         goal.progress = Progress(
#             current_value=current_value,
#             percent_complete=percent_complete,
#             updated_at=_now()
#         )
        
#         # Check if goal is completed
#         if percent_complete >= 100:
#             goal.status.value = GoalStatus.COMPLETED
        
#         user_goals[goal_index] = goal
#         _save_user_goals(user_goals)
        
#         return goal.model_dump_json()
#     except Exception as e:
#         return str(_error("PROGRESS_CALCULATION_FAILED", "Failed to calculate progress", str(e)))

# @tool
# def handle_binary_choice(goal_id: str, choice: str, user_id: str) -> str:
#     """
#     Handle binary choices for goal state transitions and confirmations.
#     """
#     try:
#         user_key = str(user_id)
#         user_goals = _get_user_goals(user_key)
        
#         # Find the goal
#         goal_index = None
#         for i, g in enumerate(user_goals):
#             if str(g.goal_id) == str(goal_id):
#                 goal_index = i
#                 break
        
#         if goal_index is None:
#             return str(_error("NOT_FOUND", "Goal not found", None))
        
#         goal = user_goals[goal_index]
        
#         # Handle different choice types
#         if choice == "activate" and goal.status.value == GoalStatus.PENDING:
#             # Activate goal (pending → in_progress)
#             goal.status.value = GoalStatus.IN_PROGRESS
#             if goal.audit:
#                 goal.audit.updated_at = _now()
            
#         elif choice == "keep_pending":
#             # Keep goal in pending state
#             pass
            
#         elif choice == "save":
#             # Save changes (already handled in update_goal)
#             pass
            
#         elif choice == "discard":
#             # Discard changes (revert to previous state)
#             # In real implementation, this would restore from backup
#             pass
            
#         elif choice == "archive":
#             # Archive goal (soft delete)
#             goal.status.value = GoalStatus.DELETED
#             if goal.audit:
#                 goal.audit.updated_at = _now()
                
#         elif choice == "restore":
#             # Restore deleted goal
#             if goal.status.value == GoalStatus.DELETED:
#                 goal.status.value = GoalStatus.PENDING
#                 if goal.audit:
#                     goal.audit.updated_at = _now()
        
#         user_goals[goal_index] = goal
#         _save_user_goals(user_goals)
        
#         return goal.model_dump_json()
#     except Exception as e:
#         return str(_error("BINARY_CHOICE_FAILED", "Failed to handle binary choice", str(e)))

# @tool
# def get_goals_by_status(user_id: str, status: str) -> str:
#     """
#     Get goals filtered by status.
#     """
#     try:
#         user_goals = _get_user_goals(str(user_id))
        
#         if not user_goals:
#             return str(_error("NOT_FOUND", "No goals found for user", None))
        
#         # Filter by status
#         filtered_goals = [g for g in user_goals if g.status.value == status]
        
#         if not filtered_goals:
#             return str(_error("NOT_FOUND", f"No goals found with status: {status}", None))
        
#         return str([g.model_dump() for g in filtered_goals])
#     except Exception as e:
#         return str(_error("READ_FAILED", "Failed to get goals by status", str(e)))
