"""API routes for prompt management and configuration."""

import logging
import os

from fastapi import APIRouter
from pydantic import BaseModel

from app.core import app_state
from app.core.config import config
from app.services.llm.prompt_manager_service import get_prompt_manager_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/prompts", tags=["prompts"])


class TestModeUpdateRequest(BaseModel):
    """Request model for updating test mode."""

    supervisor: bool | None = None
    wealth: bool | None = None
    finance: bool | None = None
    guest: bool | None = None
    goal: bool | None = None


@router.patch("/test-mode")
async def update_test_mode(request: TestModeUpdateRequest):
    """Update TEST_MODE configuration for specific agents.

    This endpoint allows you to toggle TEST_MODE for individual agents without
    restarting the application. Changes are applied immediately.

    Request body example:
    ```json
    {
        "supervisor": true,
        "wealth": false,
        "finance": true,
        "guest": false,
        "goal": true
    }
    ```

    You can update one or multiple agents in a single request.
    Only provide the agents you want to update.

    Returns:
        dict: Updated configuration status

    """
    try:
        updated = {}

        # Map of request fields to config attributes and env vars
        agent_mapping = {
            "supervisor": "SUPERVISOR_PROMPT_TEST_MODE",
            "wealth": "WEALTH_PROMPT_TEST_MODE",
            "finance": "FINANCE_PROMPT_TEST_MODE",
            "guest": "GUEST_PROMPT_TEST_MODE",
            "goal": "GOAL_PROMPT_TEST_MODE",
        }

        # Update each agent that was provided in request
        for agent_key, config_key in agent_mapping.items():
            value = getattr(request, agent_key)
            if value is not None:
                # Update environment variable
                os.environ[config_key] = str(value).lower()
                # Update config class attribute
                config.set_env_var(config_key, str(value).lower())
                updated[config_key] = getattr(config, config_key)
                logger.info(f"Updated {config_key} = {updated[config_key]}")

        if not updated:
            return {
                "status": "warning",
                "message": "No agents specified for update",
                "updated": {},
            }

        # Clear cache for updated agents to force fresh fetch
        prompt_service = get_prompt_manager_service()
        for agent_key in agent_mapping:
            if getattr(request, agent_key) is not None:
                agent_name = f"{agent_key}-agent" if agent_key != "supervisor" else "supervisor"
                prompt_service.clear_cache(agent_name)

        return {
            "status": "success",
            "message": f"Updated TEST_MODE for {len(updated)} agent(s)",
            "updated": updated,
            "current_config": config.get_prompt_config_status(),
        }

    except Exception as e:
        logger.error(f"Failed to update TEST_MODE: {e}")
        return {
            "status": "error",
            "message": f"Failed to update TEST_MODE: {str(e)}",
            "updated": {},
        }


@router.post("/reload")
async def reload_prompts():
    """Reload prompt configuration and clear ALL agent-related caches.

    This endpoint clears:
    - Prompt service cache (API-fetched prompts)
    - Finance agent cache (per-user compiled agents)
    - Wealth agent cache (per-user compiled agents)
    - Finance samples cache (per-user transaction/asset/liability/account data)
    - Guest agent LRU cache (compiled graph)

    Returns:
        dict: Status of reload operation with updated configuration

    """
    try:
        # 1. Reload prompt-specific config variables from environment
        reloaded_config = config.reload_prompt_config()

        # 2. Clear prompt service cache (for API-fetched prompts)
        prompt_service = get_prompt_manager_service()
        prompt_service.clear_cache()

        app_state.reset_agents()


        return {
            "status": "success",
            "message": "All agent caches cleared successfully",
            "reloaded_variables": reloaded_config,
        }
    except Exception as e:
        logger.error(f"Failed to reload and clear caches: {e}")
        return {
            "status": "error",
            "message": f"Failed to reload configuration: {str(e)}",
            "reloaded_variables": {},
            "cache_cleared": False,
        }


@router.get("/status")
async def get_prompts_status():
    """Get current status of prompt configuration and cache.

    Returns detailed information about:
    - Current TEST_MODE settings for each agent
    - PROMPT_SERVICE_URL configuration
    - Cached prompts status

    Returns:
        dict: Current prompt configuration and cache status

    """
    try:
        # Get current config status
        config_status = config.get_prompt_config_status()

        # Get cache status
        prompt_service = get_prompt_manager_service()
        cached_agents = list(prompt_service._cache.keys())

        return {
            "status": "success",
            "configuration": config_status,
            "cache": {
                "cached_agents": cached_agents,
                "cache_count": len(cached_agents),
            },
        }
    except Exception as e:
        logger.error(f"Failed to get prompt status: {e}")
        return {
            "status": "error",
            "message": f"Failed to get status: {str(e)}",
            "configuration": {},
            "cache": {},
        }


@router.delete("/cache")
async def clear_prompt_cache(agent: str | None = None):
    """Clear prompt cache for specific agent or all agents.

    Args:
        agent: Optional agent name to clear specific cache. If not provided, clears all cache.
               Valid values: supervisor, wealth-agent, finance-agent, guest-agent, goal-agent

    Returns:
        dict: Status of cache clear operation

    """
    try:
        prompt_service = get_prompt_manager_service()

        if agent:
            prompt_service.clear_cache(agent)
            message = f"Cache cleared for agent: {agent}"
            logger.info(message)
        else:
            prompt_service.clear_cache()
            message = "All prompt cache cleared"
            logger.info(message)

        return {
            "status": "success",
            "message": message,
            "agent": agent,
        }
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        return {
            "status": "error",
            "message": f"Failed to clear cache: {str(e)}",
            "agent": agent,
        }
