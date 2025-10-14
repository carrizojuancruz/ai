"""Unit tests for finance procedural templates."""

from unittest.mock import MagicMock, patch

import pytest

# Import models directly, but mock the manager and functions that use langgraph
from app.agents.supervisor.finance_agent.procedural_memory.sql_hints.procedural_templates import (
    FinanceProcedureTemplate,
)


class TestFinanceProcedureTemplate:
    """Test FinanceProcedureTemplate model."""

    def test_template_creation(self):
        """Test creating a FinanceProcedureTemplate."""
        template = FinanceProcedureTemplate(
            id="test-1",
            name="Test Template",
            description="A test template",
            sql_hint="SELECT * FROM test",
            tags=["test", "finance"],
            examples=["Example 1"],
            version="1.0"
        )

        assert template.id == "test-1"
        assert template.name == "Test Template"
        assert template.description == "A test template"
        assert template.sql_hint == "SELECT * FROM test"
        assert template.tags == ["test", "finance"]
        assert template.examples == ["Example 1"]
        assert template.version == "1.0"
        assert template.deprecated is False

    def test_template_defaults(self):
        """Test template default values."""
        template = FinanceProcedureTemplate(
            id="test-2",
            name="Test Template 2",
            description="Another test",
            sql_hint="SELECT 1"
        )

        assert template.tags == []
        assert template.examples == []
        assert template.version == "1.0"
        assert template.deprecated is False


class TestProceduralTemplatesManager:
    """Test ProceduralTemplatesManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        from app.agents.supervisor.finance_agent.procedural_memory.sql_hints.procedural_templates import (
            ProceduralTemplatesManager,
        )
        self.manager = ProceduralTemplatesManager()

    @patch('langgraph.config.get_store')
    @patch('app.agents.supervisor.memory.context._timed_search')
    @patch('app.agents.supervisor.memory.context._safe_extract_score')
    @pytest.mark.asyncio
    async def test_get_templates_success(self, mock_safe_extract, mock_timed_search, mock_get_store):
        """Test successful template retrieval."""
        from app.agents.supervisor.finance_agent.procedural_memory.sql_hints.procedural_templates import (
            ProceduralTemplatesManager,
        )

        # Mock the store and search results
        mock_store = MagicMock()
        mock_get_store.return_value = mock_store

        mock_result = MagicMock()
        mock_result.value = {
            "id": "template-1",
            "name": "Test Template",
            "description": "Test description",
            "sql_hint": "SELECT * FROM test",
            "tags": ["test"],
            "examples": ["example"],
            "version": "1.0",
            "deprecated": False
        }
        mock_safe_extract.return_value = 0.9
        mock_timed_search.return_value = [mock_result]

        manager = ProceduralTemplatesManager()
        templates = await manager.get_templates("test query", topk=5, min_score=0.8)

        assert len(templates) == 1
        assert templates[0].id == "template-1"
        assert templates[0].name == "Test Template"

    @patch('langgraph.config.get_store')
    @patch('app.agents.supervisor.memory.context._timed_search')
    @patch('app.agents.supervisor.memory.context._safe_extract_score')
    @pytest.mark.asyncio
    async def test_get_templates_below_min_score(self, mock_safe_extract, mock_timed_search, mock_get_store):
        """Test filtering templates below minimum score."""

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store

        mock_result = MagicMock()
        mock_result.value = {
            "id": "template-1",
            "name": "Test Template",
            "description": "Test description",
            "sql_hint": "SELECT * FROM test"
        }

        # Mock score below threshold
        with patch('app.agents.supervisor.memory.context._safe_extract_score', return_value=0.5):
            mock_timed_search.return_value = [mock_result]

            templates = await self.manager.get_templates("test query", min_score=0.8)

            assert len(templates) == 0

    @patch('langgraph.config.get_store')
    @patch('app.agents.supervisor.memory.context._timed_search')
    @patch('app.agents.supervisor.memory.context._safe_extract_score')
    @pytest.mark.asyncio
    async def test_get_templates_deprecated_filtered(self, mock_safe_extract, mock_timed_search, mock_get_store):
        """Test filtering deprecated templates."""
        from app.agents.supervisor.finance_agent.procedural_memory.sql_hints.procedural_templates import (
            ProceduralTemplatesManager,
        )

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store

        mock_result = MagicMock()
        mock_result.value = {
            "id": "template-1",
            "name": "Test Template",
            "description": "Test description",
            "sql_hint": "SELECT * FROM test",
            "deprecated": True
        }
        mock_safe_extract.return_value = 0.9
        mock_timed_search.return_value = [mock_result]

        manager = ProceduralTemplatesManager()
        templates = await manager.get_templates("test query")

        assert len(templates) == 0

    @patch('langgraph.config.get_store')
    @patch('app.agents.supervisor.memory.context._timed_search')
    @pytest.mark.asyncio
    async def test_get_template_by_id_success(self, mock_timed_search, mock_get_store):
        """Test successful retrieval by ID."""
        from app.agents.supervisor.finance_agent.procedural_memory.sql_hints.procedural_templates import (
            ProceduralTemplatesManager,
        )

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store

        mock_result = MagicMock()
        mock_result.value = {
            "id": "template-1",
            "name": "Test Template",
            "description": "Test description",
            "sql_hint": "SELECT * FROM test"
        }
        mock_timed_search.return_value = [mock_result]

        manager = ProceduralTemplatesManager()
        template = await manager.get_template_by_id("template-1")

        assert template is not None
        assert template.id == "template-1"

    @patch('langgraph.config.get_store')
    @patch('app.agents.supervisor.memory.context._timed_search')
    @pytest.mark.asyncio
    async def test_get_template_by_id_not_found(self, mock_timed_search, mock_get_store):
        """Test retrieval by ID when not found."""
        from app.agents.supervisor.finance_agent.procedural_memory.sql_hints.procedural_templates import (
            ProceduralTemplatesManager,
        )

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store

        mock_timed_search.return_value = []

        manager = ProceduralTemplatesManager()
        template = await manager.get_template_by_id("nonexistent")

        assert template is None


class TestGlobalFunctions:
    """Test global functions."""

    @patch('langgraph.config.get_store')
    def test_get_procedural_templates_manager(self, mock_get_store):
        """Test getting the global manager instance."""
        from app.agents.supervisor.finance_agent.procedural_memory.sql_hints.procedural_templates import (
            ProceduralTemplatesManager,
            get_procedural_templates_manager,
        )

        manager = get_procedural_templates_manager()
        assert isinstance(manager, ProceduralTemplatesManager)

    @patch('langgraph.config.get_store')
    @patch('app.agents.supervisor.memory.context._timed_search')
    @patch('app.agents.supervisor.memory.context._safe_extract_score')
    @pytest.mark.asyncio
    async def test_get_finance_procedural_templates(self, mock_safe_extract, mock_timed_search, mock_get_store):
        """Test the global get_finance_procedural_templates function."""
        from app.agents.supervisor.finance_agent.procedural_memory.sql_hints.procedural_templates import (
            get_finance_procedural_templates,
        )

        mock_store = MagicMock()
        mock_get_store.return_value = mock_store

        mock_result = MagicMock()
        mock_result.value = {
            "id": "template-1",
            "name": "Test Template",
            "description": "Test description",
            "sql_hint": "SELECT * FROM test",
            "tags": ["test"],
            "examples": ["example"],
            "version": "1.0",
            "deprecated": False
        }
        mock_safe_extract.return_value = 0.9
        mock_timed_search.return_value = [mock_result]

        templates = await get_finance_procedural_templates("test query")

        assert len(templates) == 1
        assert templates[0].id == "template-1"
