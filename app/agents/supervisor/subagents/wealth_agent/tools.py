"""Tools for the CRUD Budget Agent with in-memory temporary persistence."""

import json

from langchain_core.tools import tool

from app.knowledge.service import get_knowledge_service


def _error(code: str, message: str, cause: str | None = None) -> dict:
    return {"code": code, "message": message, "cause": cause}

@tool
async def search_kb(query: str) -> str:
    """Search the knowledge base for a query."""
    try:
        kb_service = get_knowledge_service()
        results = await kb_service.search(query)

        formatted_results = []
        for result in results:
            section_url = result.get("section_url", "")
            source_url = result.get("source_url", "")
            source_reference = section_url if section_url else source_url

            if source_reference:
                formatted_results.append({
                    "source": source_reference,
                    "metadata": {
                        "source_url": source_url,
                        "section_url": section_url,
                        "name": result.get("name", ""),
                        "type": result.get("type", ""),
                        "category": result.get("category", "")
                    }
                })
        return json.dumps(formatted_results, ensure_ascii=False)
    except Exception as e:
        return json.dumps([{"source": str(_error("SEARCH_FAILED", "Failed to search the kb", str(e)))}], ensure_ascii=False)
