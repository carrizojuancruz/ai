'''
This module provides a mapping of tool names to their descriptions.
'''

SOURCE_MAPPING = {
    "query_knowledge_base": "Knowledge base",
    "episodic_capture": "Episodic capture",
    "research_agent": "Research agent",
    "math_agent": "Math agent",
    "supervisor": "Supervisor",
}


def get_source_name(tool_name: str) -> str:
    '''
    Get the name of the source for a given tool name.

    Args:
        tool_name: The name of the tool.

    Returns:
        The name of the source.
    '''
    return SOURCE_MAPPING.get(tool_name, tool_name)

def get_all_source_key_names() -> list[str]:
    """
    Get the key names of all sources.
    """
    return list(SOURCE_MAPPING.keys())