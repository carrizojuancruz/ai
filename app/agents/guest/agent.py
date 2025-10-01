import logging
from functools import lru_cache

from langchain_aws import ChatBedrock  # type: ignore
from langfuse.callback import CallbackHandler  # type: ignore
from langgraph.prebuilt import create_react_agent  # type: ignore

from app.core.config import config

from .prompts import get_guest_system_prompt

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_guest_graph():
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
            callbacks = [CallbackHandler(public_key=guest_pk, secret_key=guest_sk, host=guest_host)]
        except Exception as e:
            logger.warning("[Langfuse][guest] Failed to init callback handler: %s: %s", type(e).__name__, e)
            callbacks = []
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

    prompt = get_guest_system_prompt(max_messages=config.GUEST_MAX_MESSAGES)

    graph = create_react_agent(
        model=chat_bedrock,
        tools=[],
        prompt=prompt,
        name="guestAgent",
    )
    return graph
