from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator, Callable
from typing import Any
from uuid import UUID

from langfuse.callback import CallbackHandler
from langgraph.graph import END, StateGraph

from .state import OnboardingState, OnboardingStep

langfuse_handler = CallbackHandler(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST"),
)

logger = logging.getLogger(__name__)

if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY") and os.getenv("LANGFUSE_HOST")):
    logger.warning("Langfuse env vars missing or incomplete; callback tracing will be disabled")


class OnboardingAgent:
    def __init__(self) -> None:
        self.graph = self._create_graph()

    def _create_graph(self) -> StateGraph:
        workflow = StateGraph(OnboardingState)

        steps = [
            "warmup",
            "identity",
            "income_money",
            "assets_expenses",
            "home",
            "family_unit",
            "health_coverage",
            "learning_path",
            "plaid_integration",
            "checkout_exit",
        ]

        for step_name in steps:
            workflow.add_node(step_name, self._create_step_handler(step_name))

        workflow.add_node("route", lambda state: state)

        workflow.add_conditional_edges("route", lambda state: state.current_step.value, {step: step for step in steps})

        for step_name in steps:
            workflow.add_edge(step_name, END)

        workflow.set_entry_point("route")
        return workflow.compile()

    def _create_step_handler(self, step_name: str) -> Callable:
        async def handler(state: OnboardingState) -> OnboardingState:
            from app.services.onboarding.step_handler import step_handler_service

            step = OnboardingStep(step_name)
            return await step_handler_service.handle_step(state, step)

        return handler

    async def process_message(
        self, user_id: UUID, message: str, state: OnboardingState | None = None
    ) -> tuple[str, OnboardingState]:
        if state is None:
            state = OnboardingState(user_id=user_id)
        state.last_user_message = message

        state_dict = state.model_dump()
        result = await self.graph.ainvoke(
            state_dict,
            config={
                "callbacks": [langfuse_handler],
                "thread_id": str(state.conversation_id),
                "tags": ["onboarding", "verde-ai"],
                "configurable": {
                    "session_id": str(state.conversation_id),
                    "original_query": message,
                },
            },
        )
        new_state = OnboardingState(**result) if isinstance(result, dict) else result

        return (new_state.last_agent_response or "", new_state)

    async def process_message_with_events(
        self,
        user_id: UUID,
        message: str,
        state: OnboardingState | None,
    ) -> AsyncGenerator[tuple[dict[str, Any], OnboardingState], None]:
        from app.services.onboarding.step_handler import step_handler_service

        if state is None:
            state = OnboardingState(user_id=user_id)
        state.last_user_message = message

        prev_completed = set(s.value for s in state.completed_steps)
        current_state = state

        yield (
            {
                "event": "step.update",
                "data": {"status": "validating", "step_id": state.current_step.value},
            },
            current_state,
        )

        step = state.current_step

        accumulated_text = ""
        async for chunk, updated_state in step_handler_service.handle_step_stream(state, step):
            current_state = updated_state

            if chunk:
                accumulated_text += chunk
                yield ({"event": "token.delta", "data": {"text": chunk}}, current_state)

        new_completed = set(s.value for s in current_state.completed_steps)
        for step_value in sorted(new_completed - prev_completed):
            yield (
                {
                    "event": "step.update",
                    "data": {"status": "completed", "step_id": step_value},
                },
                current_state,
            )

        yield (
            {
                "event": "step.update",
                "data": {
                    "status": "presented",
                    "step_id": current_state.current_step.value,
                },
            },
            current_state,
        )

        if current_state.current_interaction_type != "free_text":
            interaction_data = {
                "type": current_state.current_interaction_type,
                "step_id": current_state.current_step.value,
            }

            if current_state.current_interaction_type == "binary_choice":
                interaction_data["primary_choice"] = current_state.current_binary_choices.get("primary_choice")
                interaction_data["secondary_choice"] = current_state.current_binary_choices.get("secondary_choice")
            elif current_state.current_interaction_type in ["single_choice", "multi_choice"]:
                interaction_data["choices"] = current_state.current_choices
                if current_state.current_interaction_type == "multi_choice":
                    interaction_data["multi_min"] = current_state.multi_min
                    interaction_data["multi_max"] = current_state.multi_max

            yield (
                {
                    "event": "interaction.update",
                    "data": interaction_data,
                },
                current_state,
            )

        if current_state.ready_for_completion and current_state.user_context.ready_for_orchestrator:
            yield ({"event": "onboarding.status", "data": {"status": "done"}}, current_state)

        yield (None, current_state)
