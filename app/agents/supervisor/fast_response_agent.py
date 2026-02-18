from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langgraph.graph import MessagesState
from langgraph.types import RunnableConfig

from app.core.config import config
from app.services.llm.prompt_loader import prompt_loader
from app.services.llm.safe_cerebras import SafeChatCerebras

logger = logging.getLogger(__name__)

DEFAULT_FAST_MODEL: str = config.FAST_PATH_MODEL_ID
DEFAULT_FAST_TEMPERATURE: float = config.FAST_PATH_TEMPERATURE
FAST_SYSTEM_PROMPT: str = prompt_loader.load("fast_smalltalk_prompt")


async def _generate_response(llm_messages: list[BaseMessage]) -> str:
    model_id = DEFAULT_FAST_MODEL
    logger.info(
        "[FAST_PATH] _generate_response model=%s msg_count=%d",
        model_id,
        len(llm_messages),
    )
    try:
        llm = SafeChatCerebras(
            model=model_id,
            api_key=config.CEREBRAS_API_KEY,
            temperature=DEFAULT_FAST_TEMPERATURE,
            input_config={
                "use_llm_classifier": True,
                "llm_confidence_threshold": 0.7,
                "enabled_checks": ["injection", "blocked_topics", "internal_exposure"],
            },
            output_config={
                "use_llm_classifier": True,
                "llm_confidence_threshold": 0.7,
                "llm_fail_open": False,
                "enabled_checks": ["pii_leakage", "context_exposure", "internal_exposure"],
            },
            user_context={"blocked_topics": []},
            fail_open=True,
        )
        result = await llm.ainvoke(llm_messages)
        content = getattr(result, "content", "")
        return content if isinstance(content, str) else ""
    except Exception as exc:
        logger.warning("fast_response.cerebras.error err=%s", exc)
        return ""


async def fast_response_agent(
    state: MessagesState,
    run_config: RunnableConfig | None = None,  # noqa: ARG001
) -> dict[str, Any]:
    messages = state.get("messages") or []
    if not messages:
        return {}

    llm_messages: list[BaseMessage] = [SystemMessage(content=FAST_SYSTEM_PROMPT), *messages]

    logger.info("[FAST_PATH] invoked msg_count=%d", len(messages))

    response = await _generate_response(llm_messages)
    if not response:
        response = "Hi! How can I help you today?"

    logger.info("[FAST_PATH] emitting len=%d preview=%s", len(response), response[:80])
    return {"messages": [AIMessage(content=response, name="fast_response")]}
