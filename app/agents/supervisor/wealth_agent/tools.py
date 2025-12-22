"""Tools for the CRUD Budget Agent with in-memory temporary persistence."""

import json
import logging

from langchain_core.tools import tool

from app.knowledge.service import get_knowledge_service

logger = logging.getLogger(__name__)


def _error(code: str, message: str, cause: str | None = None) -> dict:
    return {"code": code, "message": message, "cause": cause}


@tool
async def search_kb(query: str, content_source: str = "external") -> str:
    """Search the knowledge base for a query.

    Args:
        query: The search query string.
        content_source: Filter results by content source. Options:
            - "internal": Search only Vera app content (features, navigation, how-tos)
            - "external": Search only external financial education content (default)
            - "all": Search across all content sources

    Use "internal" for app-related questions (e.g., "How do I connect my bank?", "Where is the goals section?").
    Use "external" for financial education (e.g., "What is debt-to-income ratio?", "What is a 401k?").
    Use "all" when the query spans both domains (e.g., "How do I track my 401k in Vera?") or when uncertain.

    Returns:
        JSON string containing search results with content and source information.

    """
    if content_source not in ["internal", "external", "all"]:
        return json.dumps(
            [
                {
                    "source": str(
                        _error(
                            "INVALID_PARAMETER",
                            f"content_source must be 'internal', 'external', or 'all', got '{content_source}'",
                            None,
                        )
                    )
                }
            ],
            ensure_ascii=False,
        )

    try:
        kb_service = get_knowledge_service()

        filter_param = None
        if content_source == "internal":
            filter_param = {"content_source": "internal"}
        elif content_source == "external":
            filter_param = {"content_source": "external"}

        logger.info(f"Searching KB with content_source={content_source}, query='{query}'")
        results = await kb_service.search(query, filter=filter_param)

        formatted_results = []
        for result in results:
            content = result.get("content", "")
            section_url = result.get("section_url", "")
            source_url = result.get("source_url", "")
            source_reference = section_url if section_url else source_url

            if content:
                metadata = {
                    "source_url": source_url,
                    "section_url": section_url,
                    "name": result.get("name", ""),
                    "type": result.get("type", ""),
                    "category": result.get("category", ""),
                    "description": result.get("description", ""),
                    "content_source": result.get("content_source", ""),
                }

                if "subcategory" in result:
                    metadata["subcategory"] = result["subcategory"]

                formatted_results.append(
                    {
                        "content": content,
                        "source": source_reference or result.get("name", "Unknown source"),
                        "metadata": metadata,
                    }
                )
        return json.dumps(formatted_results, ensure_ascii=False)
    except Exception as e:
        return json.dumps(
            [{"source": str(_error("SEARCH_FAILED", "Failed to search the kb", str(e)))}], ensure_ascii=False
        )