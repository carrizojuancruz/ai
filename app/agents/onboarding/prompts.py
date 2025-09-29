from __future__ import annotations


def name_extraction_instructions() -> str:
    return (
        "Extract the user's preferred name. If the entire message itself looks like a name "
        "(1-3 words using letters, apostrophes, or hyphens), use it directly. "
        "If greeting phrasing appears (e.g., 'my name is', 'I am', 'I'm'), extract only the name portion. "
        "If no clear name, return null. Return ONLY JSON: {\"preferred_name\": string|null}."
    )


def location_extraction_instructions() -> str:
    return (
        "Extract the user's location as city and state/region. "
        "Infer full names from common abbreviations (e.g., 'LA' -> 'Los Angeles' with region 'California'). "
        "If only a city is provided, infer the most commonly implied state/region when unambiguous; otherwise leave region null. "
        'Return JSON: {"city": string|null, "region": string|null}. Return ONLY JSON.'
    )
