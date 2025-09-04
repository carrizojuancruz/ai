"""
This module provides tools for the app.
"""
from typing import Any

def include_in_array(sources: list[str], item: str) -> bool:
    """
    Check if the item should be included in the array
    """
    return item in sources



def check_repeated_sources(sources: list[dict[str, Any]], source: dict[str, Any]) -> bool:
    """
    Check if the sources are repeated
    """
    # Get source name
    source_name = source.get("name")
    source_text = source.get("source", "")
    
    # Check if the source is already in the list using the source name and source text
    for s in sources:
        if s.get("name") == source_name and s.get("source") == source_text:
            return False
    return True