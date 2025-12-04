from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _parse_weights(s: str) -> dict[str, float]:
    """Parse a comma-separated string of key=value pairs into a dictionary of weights.

    Args:
        s (str): String in format "key1=value1,key2=value2" where values are floats.

    Returns:
        dict[str, float]: Dictionary with parsed weights. Falls back to default weights
                         if parsing fails.

    Notes:
        - Default weights: sim=0.55, imp=0.20, recency=0.15, pinned=0.10
        - Handles malformed input gracefully by returning defaults

    """
    out: dict[str, float] = {"sim": 0.55, "imp": 0.20, "recency": 0.15, "pinned": 0.10}
    try:
        for part in s.split(","):
            if not part.strip():
                continue
            k, v = part.split("=")
            out[k.strip()] = float(v.strip())
    except Exception:
        pass
    return out


def _build_profile_line(ctx: dict[str, Any]) -> Optional[str]:
    if not isinstance(ctx, dict):
        return None
    name = (ctx.get("identity", {}) or {}).get("preferred_name") or ctx.get("preferred_name") or None
    age = (ctx.get("identity", {}) or {}).get("age") or ctx.get("age") or None
    age_range = ctx.get("age_range") or None
    tone = ctx.get("tone_preference") or (ctx.get("style", {}) or {}).get("tone") or None
    lang = ctx.get("language") or (ctx.get("locale_info", {}) or {}).get("language") or None
    city = ctx.get("city") or (ctx.get("location", {}) or {}).get("city") or None
    income_band = ctx.get("income_band") or ctx.get("income") or None
    rent_mortgage = ctx.get("rent_mortgage") or ctx.get("housing") or None
    money_feelings = ctx.get("money_feelings", [])
    money_feelings_str = (
        ", ".join([str(f) for f in money_feelings[:3] if isinstance(f, str)])
        if isinstance(money_feelings, list)
        else ""
    )
    housing_satisfaction = ctx.get("housing_satisfaction") or None
    health_insurance = ctx.get("health_insurance") or None
    goals = ctx.get("goals") or []
    goals_str = ", ".join([str(g) for g in goals[:3] if isinstance(g, str)]) if isinstance(goals, list) else ""
    personal_information = ctx.get("personal_information") or None
    sentences: list[str] = []

    if name and age is not None:
        sentences.append(f"The user's name is {name} and they are {age} years old")
    elif name:
        sentences.append(f"The user's name is {name}")
    elif age is not None:
        sentences.append(f"The user is {age} years old")

    if age_range and age is None:
        sentences.append(f"They are in the {age_range} age range")

    if city:
        sentences.append(f"They live in {city}")

    if lang:
        lang_display = lang.replace("-", " - ").replace("en", "English").replace("es", "Spanish")
        sentences.append(f"Their preferred language is {lang_display}")

    if tone:
        sentences.append(f"They prefer a {tone} communication tone")

    if income_band:
        sentences.append(f"Their income band is {income_band}")

    if rent_mortgage:
        sentences.append(f"Their monthly housing cost is ${rent_mortgage}")

    if money_feelings_str:
        sentences.append(f"They feel {money_feelings_str} about money")

    if housing_satisfaction:
        sentences.append(f"Their housing satisfaction is {housing_satisfaction}")

    if health_insurance:
        sentences.append(f"They have {health_insurance} health insurance")

    if goals_str:
        sentences.append(f"Their financial goals include: {goals_str}")

    if personal_information:
        sentences.append(personal_information)

    if not sentences:
        return None

    core = ". ".join(sentences) + "."
    guidance = (
        " Use these details to personalize tone and examples. "
        "Do not restate this information verbatim. Do not override with assumptions. "
        "If the user contradicts this context, prefer the latest user message. "
        "Respect blocked topics by not discussing them unless the user initiates."
    )
    return f"CONTEXT_PROFILE: {core}{guidance}"
