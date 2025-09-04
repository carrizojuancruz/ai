"""Utility functions for mapping and source management."""


def get_source_name(tool_name: str) -> str:
    """Map tool names to readable source names.

    Args:
        tool_name: The name of the tool/agent used

    Returns:
        A user-friendly source name

    """
    # Map tool names to readable source names
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
        # Add more mappings as needed for your specific tools
    }

    return source_mapping.get(tool_name, tool_name.replace("_", " ").title())
