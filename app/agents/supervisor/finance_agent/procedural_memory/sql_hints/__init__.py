"""Finance procedural templates - optional SQL hints for the finance agent.

Provides helpful patterns that the agent can use or ignore when generating SQL.
"""

from .procedural_templates import (
    FinanceProcedureTemplate,
    ProceduralTemplatesManager,
    get_finance_procedural_templates,
    get_procedural_templates_manager,
)

__all__ = [
    "FinanceProcedureTemplate",
    "ProceduralTemplatesManager",
    "get_procedural_templates_manager",
    "get_finance_procedural_templates",
]
