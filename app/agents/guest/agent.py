import logging
from functools import lru_cache
from typing import Any, Sequence

from langchain_aws import ChatBedrock  # type: ignore
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler  # type: ignore
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.config import config
from app.services.memory.checkpointer import get_guest_checkpointer

logger = logging.getLogger(__name__)


def _is_system_message(message: Any) -> bool:
    if isinstance(message, SystemMessage):
        return True
    if isinstance(message, BaseMessage):
        return getattr(message, "type", "") == "system"
    if isinstance(message, dict):
        return str(message.get("role", "")).lower() == "system"
    if isinstance(message, (list, tuple)) and message:
        return str(message[0]).lower() == "system"
    return False


@lru_cache(maxsize=1)
def get_guest_graph() -> CompiledStateGraph:
    model_id = config.GUEST_AGENT_MODEL_ID
    region = config.GUEST_AGENT_MODEL_REGION
    guardrails = {
        "guardrailIdentifier": config.GUEST_AGENT_GUARDRAIL_ID,
        "guardrailVersion": config.GUEST_AGENT_GUARDRAIL_VERSION,
        "trace": "enabled",
    }

    guest_pk = config.LANGFUSE_GUEST_PUBLIC_KEY
    guest_sk = config.LANGFUSE_GUEST_SECRET_KEY
    guest_host = config.LANGFUSE_HOST

    callbacks = []
    if guest_pk and guest_sk and guest_host:
        try:
            Langfuse(public_key=guest_pk, secret_key=guest_sk, host=guest_host)
            callbacks = [CallbackHandler(public_key=guest_pk)]
        except Exception as e:
            logger.warning(
                "[Langfuse][guest] Failed to init callback handler: %s: %s",
                type(e).__name__,
                e
            )
    else:
        logger.warning(
            "[Langfuse][guest] Env vars missing or incomplete; tracing disabled (host=%s)",
            guest_host,
        )

    chat_bedrock = ChatBedrock(
        model_id=model_id,
        region_name=region,
        streaming=True,
        guardrails=guardrails,
        callbacks=callbacks,
    )

    from app.services.llm.prompt_loader import prompt_loader

    prompt = prompt_loader.load("guest_system_prompt", max_messages=config.GUEST_MAX_MESSAGES)
    system_message = SystemMessage(content=prompt)

    def chatbot_node(state: MessagesState, config_params: RunnableConfig | None = None) -> dict[str, Any]:
        config_with_defaults = config_params or {}
        messages: Sequence[BaseMessage] = state.get("messages", [])
        messages_for_model = list(messages)
        if not any(_is_system_message(m) for m in messages_for_model):
            messages_for_model.insert(0, system_message)
        response = chat_bedrock.invoke(messages_for_model, config=config_with_defaults)
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("chatbot", chatbot_node)
    builder.add_edge(START, "chatbot")
    builder.add_edge("chatbot", END)

    checkpointer = get_guest_checkpointer()
    if checkpointer is not None:
        logger.info(
            "[GUEST][GRAPH] Compiling guest graph with checkpointer %s",
            type(checkpointer).__name__
        )
    else:
        logger.warning(
            "[GUEST][GRAPH] Guest checkpointer unavailable; compiling graph without persistence"
        )

    return builder.compile(checkpointer=checkpointer)
