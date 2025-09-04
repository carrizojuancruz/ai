"""Tools for the CRUD Budget Agent with in-memory temporary persistence."""

from langchain_core.tools import tool

from app.knowledge.service import KnowledgeService


def _error(code: str, message: str, cause: str | None = None) -> dict:
    return {"code": code, "message": message, "cause": cause}

@tool
def search_kb(query: str) -> str:
    """Search the knowledge base for a query."""
    try:
        kb_service = KnowledgeService()
        results = kb_service.search(query)
        return results
    except Exception as e:
        return str(_error("SEARCH_FAILED", "Failed to search the kb", str(e)))
