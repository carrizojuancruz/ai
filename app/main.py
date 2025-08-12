from uuid import UUID, uuid4

from fastapi import FastAPI
from pydantic import BaseModel

from .agents.onboarding import OnboardingAgent, OnboardingState

app = FastAPI(title="Verde AI - Vera Agent System", version="0.1.0")

onboarding_agent = OnboardingAgent()
user_sessions: dict[UUID, OnboardingState] = {}


class ChatMessage(BaseModel):
    """Chat message request model."""

    user_id: str | None = None
    message: str


class ChatResponse(BaseModel):
    """Chat message response model."""

    response: str
    user_id: str
    session_id: str
    current_step: str
    completed_steps: list[str]
    ready_for_orchestrator: bool


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Verde AI - Vera Agent System", "status": "online"}


@app.post("/onboarding/chat", response_model=ChatResponse)
async def onboarding_chat(chat_message: ChatMessage) -> ChatResponse:
    """Chat endpoint for the onboarding agent.

    This endpoint allows users to go through the 8-story onboarding flow:
    1. Greeting & Name/Pronouns
    2. Language, Tone & Blocked Topics
    3. Mood Check (Initial)
    4. Manual Personal Info (Minimal)
    5. Manual Financial Snapshot (Optional)
    6. Socials Opt-In (Optional)
    7. KB Education Small Talk (Static RAG)
    8. Handoff Summary & Completion Token
    """
    user_id = UUID(chat_message.user_id) if chat_message.user_id else uuid4()

    if user_id not in user_sessions:
        user_sessions[user_id] = OnboardingState(user_id=user_id)

    state = user_sessions[user_id]

    response, updated_state = await onboarding_agent.process_message(
        user_id=user_id,
        message=chat_message.message,
        state=state,
    )

    user_sessions[user_id] = updated_state

    return ChatResponse(
        response=response,
        user_id=str(user_id),
        session_id=str(updated_state.conversation_id),
        current_step=updated_state.current_step.value,
        completed_steps=[step.value for step in updated_state.completed_steps],
        ready_for_orchestrator=updated_state.user_context.ready_for_orchestrator,
    )


@app.get("/onboarding/status/{user_id}")
async def get_onboarding_status(user_id: str) -> dict:
    """Get the current onboarding status for a user."""
    user_uuid = UUID(user_id)

    if user_uuid not in user_sessions:
        return {"error": "User session not found"}

    state = user_sessions[user_uuid]

    return {
        "user_id": str(user_uuid),
        "current_step": state.current_step.value,
        "completed_steps": [step.value for step in state.completed_steps],
        "skipped_steps": [step.value for step in state.skipped_steps],
        "ready_for_orchestrator": state.user_context.ready_for_orchestrator,
        "user_context": {
            "preferred_name": state.user_context.preferred_name,
            "pronouns": state.user_context.pronouns,
            "language": state.user_context.language,
            "tone_preference": state.user_context.tone_preference,
            "primary_financial_goal": state.user_context.primary_financial_goal,
            "social_signals_consent": state.user_context.social_signals_consent,
        },
        "semantic_memories_count": len(state.semantic_memories),
        "blocked_topics_count": len(state.blocked_topics),
        "conversation_turns": state.turn_number,
    }
