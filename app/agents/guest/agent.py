from __future__ import annotations

import os
from functools import lru_cache

try:
    from langchain_aws.chat_models.bedrock import ChatBedrock  # type: ignore
except Exception:
    from langchain_aws import ChatBedrock  # type: ignore

try:
    from langgraph.prebuilt.chat_agent_executor import create_react_agent  # type: ignore
except Exception:
    from langgraph.prebuilt import create_react_agent  # type: ignore

from .prompts import get_guest_system_prompt


@lru_cache(maxsize=1)
def get_guest_graph():
    model_id = os.getenv("BEDROCK_MODEL_ID")
    region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION"))

    chat_bedrock = ChatBedrock(model_id=model_id, region_name=region, streaming=True)

    prompt = get_guest_system_prompt(max_messages=int(os.getenv("GUEST_MAX_MESSAGES")))

    graph = create_react_agent(
        model=chat_bedrock,
        tools=[],
        prompt=prompt,
        name="guestAgent",
    )
    return graph
