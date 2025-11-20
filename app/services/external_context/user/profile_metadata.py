from __future__ import annotations

from typing import Any

from app.models.user import UserContext


def build_profile_metadata_payload(user_ctx: UserContext) -> dict[str, Any] | None:
    """Build the payload for updating user profile metadata."""
    user_profile: dict[str, Any] = {}

    preferred_name = user_ctx.preferred_name or user_ctx.identity.preferred_name
    if preferred_name:
        user_profile["preferred_name"] = preferred_name

    birth_date = getattr(user_ctx.identity, "birth_date", None)
    if birth_date:
        user_profile["birth_date"] = birth_date

    city = getattr(user_ctx.location, "city", None)
    region = getattr(user_ctx.location, "region", None)
    location_parts = [part for part in (city, region) if part]
    if location_parts:
        user_profile["location"] = ", ".join(location_parts)

    if not user_profile:
        return None

    return {"meta_data": {"user_profile": user_profile}}
