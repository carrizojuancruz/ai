"""Utility functions for handling tools and sources."""

from typing import Any, Dict, List


def check_repeated_sources(sources: List[Dict[str, Any]], new_source: Dict[str, Any]) -> bool:
    """Check if a source is not already present in the sources list.

    Args:
        sources: List of existing sources
        new_source: New source to check for duplication

    Returns:
        True if source is not repeated (should be added), False if already exists

    """
    new_source_content = new_source.get("url", "")
    new_source_name = new_source.get("name", "")

    for existing_source in sources:
        existing_content = existing_source.get("url", "")
        existing_name = existing_source.get("name", "")

        # Check for exact match on both name and content
        if existing_name == new_source_name and existing_content == new_source_content:
            return False

        # Check for substantial content overlap (avoid near-duplicates)
        if existing_content and new_source_content:
            # Simple overlap check - you might want to implement more sophisticated logic
            if len(new_source_content) > 50 and new_source_content in existing_content:
                return False
            if len(existing_content) > 50 and existing_content in new_source_content:
                return False

    return True
