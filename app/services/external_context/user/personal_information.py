from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from app.services.external_context.http_client import FOSHttpClient

logger = logging.getLogger(__name__)


class PersonalInformationService:
    """Service for fetching personal information from external sources."""

    def __init__(self):
        self.http_client = FOSHttpClient()

    def _format_profile(self, data: Dict[str, Any]) -> str:
        """Format profile data into natural language."""
        if not data:
            return ""
        birth_date = data.get("birth_date", "unknown")
        location = data.get("location", "unknown")
        preferred_name = data.get("preferred_name", "unknown")
        pronoun_id = data.get("pronoun_id", "unknown")
        return f"The user was born on {birth_date} in {location}. Their preferred name is {preferred_name} and they use {pronoun_id.replace('_', '/')} pronouns."

    def _format_vera_approach(self, data: Dict[str, Any]) -> str:
        """Format vera approach data into natural language."""
        if not data:
            return ""
        interaction_style = data.get("interaction_style", "unknown")
        topics_to_avoid = data.get("topics_to_avoid", [])
        topics_str = ", ".join(topics_to_avoid) if topics_to_avoid else "none specified"
        return f"The user prefers an interaction style that is {interaction_style}. Topics to avoid include: {topics_str}."

    def _format_learning_topics(self, data: Dict[str, Any]) -> str:
        """Format learning topics data into natural language."""
        if not data:
            return ""
        topics = data.get("topics", [])
        topics_str = ", ".join(topics) if topics else "none specified"
        return f"The user's learning topics include: {topics_str}."

    def _format_health_insurance(self, data: Dict[str, Any]) -> str:
        """Format health insurance data into natural language."""
        if not data:
            return ""
        coverage = data.get("coverage_description", "unknown")
        pays_for_self = data.get("pays_for_self", False)
        pays_str = "they pay for it themselves" if pays_for_self else "it's covered by someone else"
        return f"Regarding health insurance: {coverage}, and {pays_str}."

    def _format_financial_goals(self, data: Dict[str, Any]) -> str:
        """Format financial goals data into natural language."""
        if not data:
            return ""
        goals = data.get("financial_goals", [])
        goals_str = ", ".join(goals) if goals else "none specified"
        return f"The user's financial goals are: {goals_str}."

    async def get_all_personal_info(self, user_id: str) -> str | None:
        """Fetch all personal information for a user and format in natural language."""
        endpoints = {
            # "profile": f"/internal/users/profile/{user_id}", TODO: Verify if this information is needed
            "vera_approach": f"/internal/users/profile/vera-approach/{user_id}",
            "learning_topics": f"/internal/users/profile/learning-topics/{user_id}",
            "health_insurance": f"/internal/users/profile/health-insurance/{user_id}",
            "financial_goals": f"/internal/users/profile/financial-goals/{user_id}",
        }

        tasks = [self.http_client.get(endpoint) for endpoint in endpoints.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        combined_data = {}
        for key, result in zip(endpoints.keys(), results, strict=True):
            if isinstance(result, Exception):
                logger.warning(f"Failed to fetch {key}: {result}")
                combined_data[key] = None
            else:
                combined_data[key] = result

        # Format each section into natural language
        formatted_sections = [
            # self._format_profile(combined_data.get("profile")), TODO: Verify if this information is needed
            self._format_vera_approach(combined_data.get("vera_approach")),
            self._format_learning_topics(combined_data.get("learning_topics")),
            self._format_health_insurance(combined_data.get("health_insurance")),
            self._format_financial_goals(combined_data.get("financial_goals")),
        ]

        # Combine all sections into one natural language string
        natural_description = " ".join(filter(None, formatted_sections))
        return natural_description if natural_description else None

    def _format_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format the combined response data."""
        # Implement any necessary formatting logic here
        return data
