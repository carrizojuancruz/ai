"""Onboarding-related prompts for user data extraction.

This module contains prompts used during the onboarding process to extract
user information like names, locations, and other profile data.
"""

# Onboarding Name Extraction
ONBOARDING_NAME_EXTRACTION_LOCAL = """Extract the user's preferred name. If the entire message itself looks like a name (1-3 words using letters, apostrophes, or hyphens), use it directly.
If greeting phrasing appears (e.g., 'my name is', 'I am', 'I'm'), extract only the name portion.
If no clear name, return null. Return ONLY JSON: {"preferred_name": string|null}.

Message: {message}
Extracted:"""

# Onboarding Location Extraction
ONBOARDING_LOCATION_EXTRACTION_LOCAL = """Extract the user's location as city and state/region.

Infer full names from common abbreviations (e.g., 'LA' -> 'Los Angeles' with region 'California').

If only a city is provided, infer the most commonly implied state/region when unambiguous; otherwise leave region null.

Return JSON: {"city": string|null, "region": string|null}. Return ONLY JSON."""
