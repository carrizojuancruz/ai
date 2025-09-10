"""Mapping of tool names to their descriptions."""

SOURCE_MAPPING = {
    "query_knowledge_base": "Knowledge base",
    "episodic_capture": "Episodic capture",
    "math_agent": "Math agent",
    "supervisor": "Supervisor",
}

def get_source_name(tool_name: str) -> str:
    """Map tool names to readable source names.

    Args:
        tool_name: The name of the tool/agent used

    Returns:
        A user-friendly source name

    """
    source_mapping = {
        "knowledge_search": "Knowledge Base",
        "kb_search": "Knowledge Base",
        "search_kb": "Knowledge Base",
        "search_knowledge": "Knowledge Base",
        "query_knowledge_base": "Knowledge Base",
        "web_search": "Web Search",
        "document_search": "Documents",
        "memory_search": "Memory",
        "context_search": "Context",
    }

    return source_mapping.get(tool_name, tool_name.replace("_", " ").title())

def get_all_source_key_names() -> list[str]:
    """Get the key names of all sources."""
    return list(SOURCE_MAPPING.keys())



