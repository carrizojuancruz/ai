from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.app_state import get_onboarding_agent, get_user_sessions
from app.agents.onboarding import OnboardingState

router = APIRouter()


class ChatMessage(BaseModel):
    user_id: UUID | None = None
    message: str


class ChatResponse(BaseModel):
    response: str
    user_id: str
    session_id: str
    current_step: str
    completed_steps: list[str]
    ready_for_orchestrator: bool


@router.post("/onboarding/chat", response_model=ChatResponse)
async def onboarding_chat(chat_message: ChatMessage) -> ChatResponse:
    agent = get_onboarding_agent()
    sessions = get_user_sessions()
    user_id = chat_message.user_id or uuid4()
    if user_id not in sessions:
        sessions[user_id] = OnboardingState(user_id=user_id)
    state = sessions[user_id]

    response, updated_state = await agent.process_message(
        user_id=user_id,
        message=chat_message.message,
        state=state,
    )

    sessions[user_id] = updated_state

    return ChatResponse(
        response=response,
        user_id=str(user_id),
        session_id=str(updated_state.conversation_id),
        current_step=updated_state.current_step.value,
        completed_steps=[step.value for step in updated_state.completed_steps],
        ready_for_orchestrator=updated_state.user_context.ready_for_orchestrator,
    )


@router.get("/onboarding/status/{user_id}")
async def get_onboarding_status(user_id: UUID) -> dict:
    sessions = get_user_sessions()
    state = sessions.get(user_id)
    if state is None:
        return {"error": "User session not found"}
    return {
        "user_id": str(user_id),
        "current_step": state.current_step.value,
        "completed_steps": [step.value for step in state.completed_steps],
        "skipped_steps": [step.value for step in state.skipped_steps],
        "ready_for_orchestrator": state.user_context.ready_for_orchestrator,
        "user_context": state.user_context.model_dump(),
        "semantic_memories_count": len(state.semantic_memories),
        "blocked_topics_count": len(state.blocked_topics),
        "conversation_turns": state.turn_number,
    }
