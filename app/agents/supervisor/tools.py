import logging
from typing import Dict, List
from langchain_core.tools import StructuredTool

from knowledge.service import get_knowledge_service

logger = logging.getLogger(__name__)


async def query_knowledge_base(query: str) -> List[Dict]:
    """Search the knowledge base for relevant information."""
    logger.info(f"Tool query_knowledge_base called with: {query}")
    
    try:
        knowledge_service = get_knowledge_service()
        results = await knowledge_service.search(query)
        
        formatted_results = [
            {"content": content, "source": "knowledge_base"}
            for content in results
        ]
        
        logger.info(f"Retrieved {len(formatted_results)} results from knowledge base")
        return formatted_results
        
    except Exception as e:
        logger.error(f"Error querying knowledge base: {e}")
        return []


knowledge_search_tool = StructuredTool.from_function(
    coroutine=query_knowledge_base,
    name="query_knowledge_base",
    description="Search the knowledge base for information relevant to the user's question. Use this when you need to find specific information from the stored documents."
)
