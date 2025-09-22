from __future__ import annotations

import logging

from langchain_aws import ChatBedrockConverse
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from app.core.config import config
from app.observability.logging_config import configure_logging
from app.utils.tools import get_config_value

from .prompts import WEALTH_AGENT_PROMPT
from .tools import search_kb

logger = logging.getLogger(__name__)


def get_user_location(config) -> str:
    """Extract user location from config for dynamic context."""
    try:
        if not config:
            return "Arkansas"  # Fallback for testing
            
        user_context = get_config_value("user_context", config)
        if not user_context:
            return "Arkansas"  # Fallback for testing
            
        # Try multiple location extraction patterns
        city = user_context.get("city")
        region = user_context.get("region")
        if city and region:
            return f"{city}, {region}"
            
        if user_context.get("location"):
            location_data = user_context["location"]
            if isinstance(location_data, dict):
                city = location_data.get("city")
                region = location_data.get("region")
                if city and region:
                    return f"{city}, {region}"
            elif isinstance(location_data, str):
                return location_data
                
        return "Arkansas United States"  # Fallback for testing
        
    except Exception as e:
        logger.error(f"[WEALTH_AGENT] Error extracting location: {e}")
        return "Arkansas"  # Fallback for testing


def compile_wealth_agent_graph() -> CompiledStateGraph:
    """Compile the wealth agent graph with dynamic location context."""
    configure_logging()

    guardrails = {
        "guardrailIdentifier": config.WEALTH_AGENT_GUARDRAIL_ID,
        "guardrailVersion": config.WEALTH_AGENT_GUARDRAIL_VERSION,
        "trace": "enabled",
    }

    logger.info(f"[WEALTH_AGENT] Guardrails: {guardrails}")

    chat_bedrock = ChatBedrockConverse(
        model_id=config.WEALTH_AGENT_MODEL_ID,
        region_name=config.WEALTH_AGENT_MODEL_REGION,
        temperature=config.WEALTH_AGENT_TEMPERATURE,
        guardrail_config=guardrails
    )

    def create_location_aware_prompt(state, config=None):
        """Create prompt with dynamic location context."""
        user_location = get_user_location(config)
        logger.info(f"[WEALTH_AGENT] Using location context: {user_location}")
        
        location_aware_prompt = f"""{WEALTH_AGENT_PROMPT}

USER LOCATION: {user_location}
Use this location context when relevant for your search queries (government programs, laws, regulations, local resources).
"""
        return location_aware_prompt

    wealth_agent = create_react_agent(
        model=chat_bedrock,
        tools=[search_kb],
        prompt=create_location_aware_prompt,
        name="wealth_agent",
    )

    builder = StateGraph(MessagesState)

    builder.add_node(wealth_agent)
    builder.add_edge(START, "wealth_agent")
    builder.add_edge("wealth_agent", END)

    return builder.compile()
