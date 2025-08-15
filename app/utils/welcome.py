from __future__ import annotations

import os
from typing import Any, Dict

from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage


def _format_user_context_for_prompt(user_context: Dict[str, Any]) -> str:
    name = (
        user_context.get("identity", {}).get("preferred_name")
        or user_context.get("preferred_name")
        or "there"
    )
    tone = user_context.get("tone", "friendly")
    locale = user_context.get("locale", "en-US")
    goals = user_context.get("goals", [])
    goals_str = ", ".join(goals[:3]) if isinstance(goals, list) and goals else ""
    return f"name={name}; tone={tone}; locale={locale}; goals={goals_str}"


async def generate_personalized_welcome(user_context: Dict[str, Any]) -> str:
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
    if not region:
        # Fallback if Bedrock is not configured
        name = user_context.get("identity", {}).get("preferred_name") or "there"
        return f"Hi {name}! I’m Vera. Tell me what you need and I’ll route it to the right assistant."

    chat = ChatBedrock(model_id=model_id, region_name=region)

    system = (
        "You are Vera, a warm, concise financial assistant.\n"
        "Greet the user personally if a name is available.\n"
        "Keep the welcome to one short sentence (<= 30 words).\n"
        "Do not include emojis. Do not ask multiple questions."
    )
    context_str = _format_user_context_for_prompt(user_context)
    human = f"User context: {context_str}. Compose the welcome."

    try:
        msg = await chat.ainvoke([SystemMessage(content=system), HumanMessage(content=human)])
        content = getattr(msg, "content", None)
        if isinstance(content, str) and content.strip():
            return content.strip()
    except Exception:
        pass

    # Fallback
    name = user_context.get("identity", {}).get("preferred_name") or "there"
    return f"Hi {name}! I’m Vera. How can I help you today?"


