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
    """
    Parses a comma-separated string of key=value pairs into a dictionary of weights.
    
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
    name = ((ctx.get("identity", {}) or {}).get("preferred_name") or ctx.get("preferred_name") or None)
    tone = ctx.get("tone_preference") or (ctx.get("style", {}) or {}).get("tone") or None
    lang = ctx.get("language") or (ctx.get("locale_info", {}) or {}).get("language") or None
    city = ctx.get("city") or (ctx.get("location", {}) or {}).get("city") or None
    goals = ctx.get("goals") or []
    goals_str = ", ".join([str(g) for g in goals[:3] if isinstance(g, str)]) if isinstance(goals, list) else ""
    parts: list[str] = []
    if name:
        parts.append(f"name={name}")
    if city:
        parts.append(f"city={city}")
    if lang:
        parts.append(f"language={lang}")
    if tone:
        parts.append(f"tone={tone}")
    if goals_str:
        parts.append(f"goals={goals_str}")
    if not parts:
        return None
    core = "; ".join(parts)
    guidance = (
        " Use these details to personalize tone and examples. "
        "Do not restate this line verbatim. Do not override with assumptions. "
        "If the user contradicts this, prefer the latest user message."
    )
    return f"CONTEXT_PROFILE: {core}.{guidance}"


