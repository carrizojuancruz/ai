from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Available agent types for testing."""

    GUEST = "guest"
    ONBOARDING = "onboarding"
    SUPERVISOR = "supervisor"
    WEALTH = "wealth"
    GOAL = "goal"
    FINANCE = "finance"
    FINANCE_CAPTURE = "finance_capture"


class AgentTestRequest(BaseModel):
    agent: AgentType = Field(..., description="Agent type: guest, onboarding, supervisor, wealth, goal, finance, finance_capture")
    query: Optional[str] = Field(None, description="Optional test query. Defaults to 'Hello World' if not provided.")


class AgentTestResponse(BaseModel):
    success: bool
    agent: str
    model_id: Optional[str]
    region: Optional[str]
    response_message: Optional[str]
    execution_time_seconds: float
    timestamp: str
    error: Optional[str] = None
