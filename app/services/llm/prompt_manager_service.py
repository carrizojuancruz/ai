"""Prompt Manager Service for fetching agent prompts from external API."""

import logging
from typing import Optional

from app.services.external_context.http_client import FOSHttpClient

logger = logging.getLogger(__name__)


class PromptManagerService:
    """Service for managing agent prompts from external API."""

    def __init__(self):
        """Initialize the prompt manager service with FOSHttpClient."""
        self.client = FOSHttpClient()
        self._cache: dict[str, str] = {}

    async def get_agent_prompt(self, agent: str, use_cache: bool = True) -> Optional[str]:
        """Fetch agent prompt from external API.

        Args:
            agent: Agent identifier (supervisor, wealth-agent, finance-agent, guest-agent, goal-agent)
            use_cache: Whether to use cached prompt if available

        Returns:
            Prompt template string or None if fetch fails

        """
        # Check cache first
        if use_cache and agent in self._cache:
            logger.debug(f"Using cached prompt for agent: {agent}")
            return self._cache[agent]

        # Fetch from API
        endpoint = f"/internal/prompt-manager/agent/{agent}/default"
        logger.info(f"Fetching prompt for agent: {agent} from endpoint: {endpoint}")

        try:
            response = await self.client.get(endpoint)

            if not response:
                logger.warning(f"No response received for agent: {agent}")
                return None

            # Extract prompt from response
            prompt = response.get("template") or response.get("prompt") or response.get("content")

            if not prompt:
                logger.warning(f"No prompt found in response for agent: {agent}")
                return None

            # Cache the prompt
            self._cache[agent] = prompt
            logger.info(f"Successfully fetched and cached prompt for agent: {agent}")

            return prompt

        except Exception as e:
            logger.error(f"Failed to fetch prompt for agent {agent}: {type(e).__name__}: {e}")
            return None

    def clear_cache(self, agent: Optional[str] = None) -> None:
        """Clear cached prompts.

        Args:
            agent: Specific agent to clear from cache. If None, clears all cache.

        """
        if agent:
            self._cache.pop(agent, None)
            logger.info(f"Cleared cache for agent: {agent}")
        else:
            self._cache.clear()
            logger.info("Cleared all prompt cache")

    def get_cached_prompt(self, agent: str) -> Optional[str]:
        """Get cached prompt without API call.

        Args:
            agent: Agent identifier

        Returns:
            Cached prompt or None if not in cache

        """
        return self._cache.get(agent)


# Singleton instance
_prompt_manager_service: Optional[PromptManagerService] = None


def get_prompt_manager_service() -> PromptManagerService:
    """Get or create singleton instance of PromptManagerService.

    Returns:
        PromptManagerService instance

    """
    global _prompt_manager_service
    if _prompt_manager_service is None:
        _prompt_manager_service = PromptManagerService()
    return _prompt_manager_service
