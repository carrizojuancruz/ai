from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import MessagesState

from app.utils.tools import get_config_value

from .utils import _build_profile_line

logger = logging.getLogger(__name__)

CONTEXT_PROFILE_PREFIX: str = "CONTEXT_PROFILE:"


def _collect_recent_user_texts(messages: list[Any], max_messages: int = 3) -> list[str]:
    """Collect recent user messages from LangGraph state."""
    recent_user_texts: list[str] = []
    for m in reversed(messages):
        role = getattr(m, "role", getattr(m, "type", None))
        if role in ("user", "human"):
            content = getattr(m, "content", None)
            if isinstance(content, str) and content.strip():
                recent_user_texts.append(content.strip())
                if len(recent_user_texts) >= max_messages:
                    break
    return list(reversed(recent_user_texts))


def _has_existing_context_profile(messages: list[Any]) -> bool:
    for m in messages:
        content = getattr(m, "content", None)
        if isinstance(content, str) and content.startswith(CONTEXT_PROFILE_PREFIX):
            return True
    return False


def _should_inject_profile(
    messages: list[Any],
    user_context_changed: bool,
) -> bool:
    has_existing = _has_existing_context_profile(messages)

    return not has_existing or user_context_changed


async def memory_hotpath(state: MessagesState, config: RunnableConfig) -> dict:
    """Inject profile line and trigger cold-path memory creation if needed.

    Profile injection is conditional:
    - First request: always inject profile
    - Subsequent requests: only inject if user context has changed
    """
    ctx = get_config_value(config, "user_context") or {}
    user_context_changed = get_config_value(config, "user_context_changed") or False
    messages = state.get("messages", [])

    should_inject = _should_inject_profile(messages, user_context_changed)
    prof = None

    if should_inject:
        prof = _build_profile_line(ctx) if isinstance(ctx, dict) else None
        if prof:
            logger.info(
                "memory.hotpath.profile.inject thread_id=%s context_changed=%s",
                get_config_value(config, "thread_id"),
                user_context_changed,
            )
    else:
        logger.debug(
            "memory.hotpath.profile.skip thread_id=%s context_changed=%s",
            get_config_value(config, "thread_id"),
            user_context_changed,
        )

    # Collect recent user texts and submit cold-path memory processing if needed.
    # All LLM decisions and memory write/merge operations happen in the cold path.
    recent_user_texts = _collect_recent_user_texts(messages, max_messages=3)

    if recent_user_texts:
        thread_id = get_config_value(config, "thread_id")
        user_id = get_config_value(config, "user_id")

        if thread_id and user_id:
            try:
                from langgraph.config import get_store

                from app.services.memory.cold_path_manager import get_memory_cold_path_manager

                # Build conversation window from messages
                conversation_window: list[dict[str, Any]] = []
                for m in messages[-10:]:
                    role = getattr(m, "role", getattr(m, "type", None))
                    content = getattr(m, "content", None)
                    if isinstance(content, str):
                        conversation_window.append({"role": role, "content": content})

                cold_path_manager = get_memory_cold_path_manager()
                event_loop = asyncio.get_running_loop()
                store = get_store()
                cold_path_manager.submit_turn(
                    thread_id=thread_id,
                    user_id=str(user_id),
                    user_context=ctx if isinstance(ctx, dict) else {},
                    conversation_window=conversation_window,
                    store=store,
                    event_loop=event_loop,
                )
            except Exception as e:
                logger.error(
                    "memory.hotpath.submit.error: thread_id=%s user_id=%s error=%s",
                    thread_id,
                    user_id,
                    str(e),
                    exc_info=True,
                )

    return {"messages": [AIMessage(content=prof)]} if prof else {}
