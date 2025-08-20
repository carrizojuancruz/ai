import logging
import json
from typing import Dict, List
from langchain_core.tools import StructuredTool

from knowledge.service import get_knowledge_service

logger = logging.getLogger(__name__)


async def query_knowledge_base(query: str) -> str:
    knowledge_service = get_knowledge_service()
    results: List[Dict] = await knowledge_service.search(query)
    return json.dumps(results, ensure_ascii=False)


knowledge_search_tool = StructuredTool.from_function(
    coroutine=query_knowledge_base,
    name="query_knowledge_base",
    description=(
        "Search the internal knowledge base for relevant passages that ground the current user question. "
        "Use this when the user asks for factual information that should be supported by our internal sources "
    )
)
