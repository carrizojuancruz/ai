"""Memory system data models."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MemoryCategory(str, Enum):
    """Memory category tags as defined in the architecture."""

    FINANCE = "Finance"
    BUDGET = "Budget"
    GOALS = "Goals"
    PERSONAL = "Personal"
    EDUCATION = "Education"
    CONVERSATION_SUMMARY = "Conversation_Summary"
    OTHER = "Other"


class SemanticMemory(BaseModel):
    """User preferences and profile information stored as semantic memories."""

    memory_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    content: str = Field(description="The semantic memory content")
    category: MemoryCategory
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default="onboarding", description="Source of this memory")


class EpisodicMemory(BaseModel):
    """Turn-by-turn conversation history stored as episodic memories."""

    memory_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    conversation_id: UUID
    turn_number: int
    user_message: str
    agent_response: str
    category: MemoryCategory
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(default="onboarding", description="Source agent")


class BlockedTopic(BaseModel):
    """Topics the user does not want to discuss."""

    topic_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    topic: str = Field(description="Description of the blocked topic")
    reason: str | None = Field(None, description="Optional reason for blocking")
    created_at: datetime = Field(default_factory=datetime.utcnow)
