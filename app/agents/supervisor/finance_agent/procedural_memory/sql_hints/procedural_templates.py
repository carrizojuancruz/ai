"""Finance procedural templates - optional SQL hints for the finance agent.

These are not mandatory - the agent can ignore them and generate fully dynamic SQL.
They're stored in ("system", "finance_procedural_templates") namespace.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.config import config

logger = logging.getLogger(__name__)


class FinanceProcedureTemplate(BaseModel):
    """A procedural template providing SQL hints for finance queries."""

    id: str
    name: str
    description: str
    tags: List[str] = Field(default_factory=list)
    sql_hint: str
    examples: List[str] = Field(default_factory=list)
    version: str = "1.0"
    deprecated: bool = False




class ProceduralTemplatesManager:
    """Manager for finance procedural templates (optional hints)."""

    def __init__(self):
        self._cache: dict[str, FinanceProcedureTemplate] = {}
        self._cache_timestamp: Optional[float] = None
        self._cache_ttl = 300  # 5 minutes

    async def get_templates(
        self,
        query: str,
        topk: Optional[int] = None,
        min_score: Optional[float] = None
    ) -> List[FinanceProcedureTemplate]:
        """Get procedural templates matching the query (optional hints)."""
        try:
            from langgraph.config import get_store

            from app.agents.supervisor.memory.context import _safe_extract_score, _timed_search

            topk = int(topk or config.FINANCE_PROCEDURAL_TOPK)
            min_score = float(min_score or config.FINANCE_PROCEDURAL_MIN_SCORE)

            store = get_store()
            results = await _timed_search(
                store,
                ("system", "finance_procedural_templates"),
                query=query or "finance sql patterns",
                limit=topk,
                label="finance_templates"
            )

            templates: List[FinanceProcedureTemplate] = []
            for r in (results or []):
                score = _safe_extract_score(r)
                if score < min_score:
                    continue

                val = getattr(r, "value", None) or {}
                if not isinstance(val, dict):
                    continue

                try:
                    template = FinanceProcedureTemplate(**val)
                    if not template.deprecated:
                        templates.append(template)
                except Exception as e:
                    logger.debug("Failed to parse template: %s", e)
                    continue

            if templates:
                logger.info("Found %d matching procedural templates for query '%s'", len(templates), query)
                return templates

        except Exception as e:
            logger.error("Error retrieving procedural templates: %s", e)

        logger.info("No procedural templates found in store")
        return []

    async def get_template_by_id(self, template_id: str) -> Optional[FinanceProcedureTemplate]:
        """Get a specific template by ID."""
        try:
            from langgraph.config import get_store

            from app.agents.supervisor.memory.context import _timed_search

            store = get_store()
            results = await _timed_search(
                store,
                ("system", "finance_procedural_templates"),
                query=f"template_id:{template_id}",
                limit=1,
                label="template_by_id"
            )

            if results and len(results) > 0:
                val = getattr(results[0], "value", None) or {}
                if isinstance(val, dict):
                    return FinanceProcedureTemplate(**val)

        except Exception as e:
            logger.error("Error retrieving template by ID: %s", e)

        return None


# Global instance
procedural_templates_manager = ProceduralTemplatesManager()


def get_procedural_templates_manager() -> ProceduralTemplatesManager:
    """Get the global procedural templates manager instance."""
    return procedural_templates_manager


async def get_finance_procedural_templates(
    query: str,
    topk: Optional[int] = None,
    min_score: Optional[float] = None
) -> List[FinanceProcedureTemplate]:
    """Get finance procedural templates."""
    manager = get_procedural_templates_manager()
    return await manager.get_templates(query, topk, min_score)
