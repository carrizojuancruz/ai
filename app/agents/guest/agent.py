from functools import lru_cache

from langchain_aws import ChatBedrock  # type: ignore
from langgraph.prebuilt import create_react_agent  # type: ignore

from app.core.config import config

from .prompts import get_guest_system_prompt


@lru_cache(maxsize=1)
def get_guest_graph():
    model_id = config.GUEST_AGENT_MODEL_ID
    region = config.GUEST_AGENT_MODEL_REGION

    chat_bedrock = ChatBedrock(model_id=model_id, region_name=region, streaming=True)

    prompt = get_guest_system_prompt(max_messages=config.GUEST_MAX_MESSAGES)

    graph = create_react_agent(
        model=chat_bedrock,
        tools=[],
        prompt=prompt,
        name="guestAgent",
    )
    return graph
