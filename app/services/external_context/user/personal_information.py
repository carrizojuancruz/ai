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
        """Format profile data into natural language.

        Rules:
        - Skip any field that is missing/None/empty.
        - If both birth_date and location exist -> "The user was born on May 10, 1990 in Buenos Aires."
          If only birth_date -> "The user was born on May 10, 1990."
          If only location -> "The user is based in Buenos Aires."
        - preferred_name -> "Their preferred name is Gonza."
        - pronoun_id -> map common ids (she_her, he_him, they_them) to she/her, he/him, they/them; otherwise replace '_' with '/'.
        - Return empty string if nothing to say.
        """
        if not data:
            return ""

        def _truthy_str(value: Any) -> str | None:
            if value is None:
                return None
            if isinstance(value, str):
                v = value.strip()
                return v if v else None
            return str(value)

        from datetime import datetime

        raw_birth_date = _truthy_str(data.get("birth_date"))
        location = _truthy_str(data.get("location"))
        preferred_name = _truthy_str(data.get("preferred_name"))
        raw_pronoun_id = _truthy_str(data.get("pronoun_id"))

        # Format birth date as "Month D, YYYY" (e.g., May 10, 1990)
        birth_date_str: str | None = None
        if raw_birth_date:
            iso_candidate = raw_birth_date.rstrip("Z")
            dt: datetime | None = None
            try:
                dt = datetime.fromisoformat(iso_candidate)
            except Exception:
                try:
                    dt = datetime.strptime(iso_candidate, "%Y-%m-%d")
                except Exception:
                    dt = None
            if dt:
                birth_date_str = f"{dt.strftime('%B')} {dt.day}, {dt.year}"

        # Map pronouns
        pronoun_str: str | None = None
        if raw_pronoun_id:
            mapping = {
                "she_her": "she/her",
                "he_him": "he/him",
                "they_them": "they/them",
            }
            lowered = raw_pronoun_id.lower()
            pronoun_fmt = mapping.get(lowered, raw_pronoun_id.replace("_", "/"))
            pronoun_str = f"They use {pronoun_fmt} pronouns."

        parts: list[str] = []
        # Birth + location sentence(s)
        if birth_date_str and location:
            parts.append(f"The user was born on {birth_date_str} in {location}.")
        elif birth_date_str:
            parts.append(f"The user was born on {birth_date_str}.")
        elif location:
            parts.append(f"The user is based in {location}.")

        if preferred_name:
            parts.append(f"Their preferred name is {preferred_name}.")

        if pronoun_str:
            parts.append(pronoun_str)

        return " ".join(parts)

    def _format_vera_approach(self, data: Dict[str, Any]) -> str:
        """Format vera approach data into natural language."""
        if not data:
            return ""

        def _truthy_str(value: Any) -> str | None:
            if value is None:
                return None
            if isinstance(value, str):
                v = value.strip()
                return v if v else None
            return str(value)

        interaction_style = _truthy_str(data.get("interaction_style"))
        topics = data.get("topics_to_avoid", []) or []

        parts: list[str] = []
        if interaction_style:
            parts.append(f"The user prefers an interaction style that is {interaction_style}.")
        if topics:
            topics_str = ", ".join(topics)
            parts.append(f"Topics to avoid include: {topics_str}.")
        return " ".join(parts)

    def _format_learning_topics(self, data: Dict[str, Any]) -> str:
        """Format learning topics data into natural language."""
        if not data:
            return ""
        topics = data.get("topics", []) or []
        if not topics:
            return ""
        topics_str = ", ".join(topics)
        return f"The user's learning topics include: {topics_str}."

    def _format_health_insurance(self, data: Dict[str, Any]) -> str:
        """Format health insurance data into natural language."""
        if not data:
            return ""

        def _truthy_str(value: Any) -> str | None:
            if value is None:
                return None
            if isinstance(value, str):
                v = value.strip()
                return v if v else None
            return str(value)

        coverage = _truthy_str(data.get("coverage_description"))
        pays_for_self = data.get("pays_for_self")
        pays_clause: str | None
        if pays_for_self is True:
            pays_clause = "they pay for it themselves"
        elif pays_for_self is False:
            pays_clause = "it's covered by someone else"
        else:
            pays_clause = None

        if not coverage and not pays_clause:
            return ""

        if coverage and pays_clause:
            return f"Regarding health insurance: {coverage}, and {pays_clause}."
        if coverage:
            return f"Regarding health insurance: {coverage}."
        return f"Regarding health insurance: {pays_clause}."

    def _format_financial_goals(self, data: Dict[str, Any]) -> str:
        """Format financial goals data into natural language."""
        if not data:
            return ""
        goals = data.get("financial_goals", []) or []
        if not goals:
            return ""
        goals_str = ", ".join(goals)
        return f"The user's financial goals are: {goals_str}."

    def _format_housing_household_info(self, data: Dict[str, Any]) -> str:
        """Format housing household info into natural language."""
        if not data:
            return ""
        housing_info = data.get("housing_household_info", [])
        if not housing_info:
            return ""

        housing_items = []
        dependents_count = 0

        for item in housing_info:
            if isinstance(item, dict):
                display = item.get("display_value", "")
                supports_under_18 = item.get("supports_under_18", False)
                value = item.get("value", 0)

                if display:
                    housing_items.append(display.lower())

                if supports_under_18 and value > 0:
                    dependents_count = value

        if not housing_items and dependents_count == 0:
            return ""

        parts = []
        if housing_items:
            housing_str = ", ".join(housing_items)
            parts.append(f"The user's housing situation: {housing_str}")

        if dependents_count > 0:
            dependent_text = "dependent" if dependents_count == 1 else "dependents"
            parts.append(f"They support {dependents_count} minor {dependent_text}")

        return ". ".join(parts) + "." if parts else ""

    async def get_all_personal_info(self, user_id: str) -> str | None:
        """Fetch all personal information for a user and format in natural language."""
        endpoints = {
            "profile": f"/internal/users/profile/{user_id}",
            "vera_approach": f"/internal/users/profile/vera-approach/{user_id}",
            "learning_topics": f"/internal/users/profile/learning-topics/{user_id}",
            "health_insurance": f"/internal/users/profile/health-insurance/{user_id}",
            "financial_goals": f"/internal/users/profile/financial-goals/{user_id}",
            "housing_household_info": f"/internal/users/profile/housing-info/{user_id}"
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
            self._format_vera_approach(combined_data.get("vera_approach")),
            self._format_learning_topics(combined_data.get("learning_topics")),
            self._format_health_insurance(combined_data.get("health_insurance")),
            self._format_financial_goals(combined_data.get("financial_goals")),
            self._format_housing_household_info(combined_data.get("housing_household_info")),
            self._format_profile(combined_data.get("profile")),
        ]

        # Combine all sections into one natural language string
        natural_description = " ".join(filter(None, formatted_sections))
        return natural_description if natural_description else None
