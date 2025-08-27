'''
This module provides a mapping of tool names to their descriptions.
'''

SOURCE_MAPPING = {
    "query_knowledge_base": "Knowledge base",
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