"""Unit tests for finance agent."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.agents.supervisor.finance_agent.agent import (
    FinanceAgent,
    _extract_task_query_text,
    finance_agent,
)


class TestExtractTaskQueryText:
    """Test _extract_task_query_text function."""

    def test_extract_task_before_markers(self):
        """Test extracting task before guidelines or list markers."""
        prompt1 = "Task: Analyze my spending"
        prompt2 = "Task: Analyze my spending\nGuidelines: Be helpful"
        prompt3 = "Task: Analyze my spending\n- Be helpful"

        assert _extract_task_query_text(prompt1) == "Analyze my spending"
        assert _extract_task_query_text(prompt2) == "Analyze my spending"
        assert _extract_task_query_text(prompt3) == "Analyze my spending"

    def test_no_task_marker(self):
        """Test prompt without Task marker."""
        prompt = "Analyze my spending"
        result = _extract_task_query_text(prompt)
        assert result == "Analyze my spending"

    def test_empty_prompt(self):
        """Test empty prompt."""
        result = _extract_task_query_text("")
        assert result == ""

    def test_multiline_task(self):
        """Test multiline task extraction."""
        prompt = "Task: Analyze my spending\non groceries and\nentertainment"
        result = _extract_task_query_text(prompt)
        assert result == "Analyze my spending on groceries and entertainment"


class TestFinanceAgent:
    """Test FinanceAgent class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.user_id = UUID("12345678-1234-5678-9012-123456789012")

    @patch('app.agents.supervisor.finance_agent.agent.ChatBedrock')
    @patch('app.agents.supervisor.finance_agent.agent.get_database_service')
    @patch('app.agents.supervisor.finance_agent.agent.get_finance_samples')
    @patch('app.agents.supervisor.finance_agent.agent.set_finance_samples')
    @pytest.mark.asyncio
    async def test_fetch_shallow_samples_cached(self, mock_set_samples, mock_get_samples, mock_get_db, mock_bedrock):
        """Test fetching samples when cached."""
        mock_bedrock.return_value = MagicMock()
        agent = FinanceAgent()
        mock_get_samples.return_value = ("[]", "[]", "[]", "[]")

        result = await agent._fetch_shallow_samples(self.user_id)

        assert result == ("[]", "[]", "[]", "[]")
        mock_get_samples.assert_called_once_with(self.user_id)
        mock_get_db.assert_not_called()

    @patch('app.agents.supervisor.finance_agent.agent.ChatBedrock')
    @patch('app.agents.supervisor.finance_agent.agent.get_database_service')
    @patch('app.agents.supervisor.finance_agent.agent.get_finance_samples')
    @patch('app.agents.supervisor.finance_agent.agent.set_finance_samples')
    @pytest.mark.asyncio
    async def test_fetch_shallow_samples_from_db(self, mock_set_samples, mock_get_samples, mock_get_db, mock_bedrock):
        """Test fetching samples from database."""
        mock_bedrock.return_value = MagicMock()
        agent = FinanceAgent()
        mock_get_samples.return_value = None

        # Mock database service and repository
        mock_session = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.execute_query = AsyncMock(side_effect=[
            [{"id": 1}],  # tx_rows
            [{"id": 2}],  # asset_rows
            [{"id": 3}],  # liability_rows
            [{"id": 4}],  # account_rows
        ])
        mock_db_service = MagicMock()
        mock_db_service.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_service.get_session.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_db_service.get_finance_repository.return_value = mock_repo
        mock_get_db.return_value = mock_db_service

        result = await agent._fetch_shallow_samples(self.user_id)

        assert len(result) == 4
        assert all(isinstance(r, str) for r in result)
        mock_repo.execute_query.assert_called()

    @patch('app.agents.supervisor.finance_agent.agent.ChatBedrock')
    @patch('app.agents.supervisor.finance_agent.agent.get_finance_procedural_templates')
    @patch('app.services.llm.agent_prompts.build_finance_system_prompt_local')
    @pytest.mark.asyncio
    async def test_create_system_prompt(self, mock_build_prompt, mock_get_templates, mock_bedrock):
        """Test creating system prompt."""
        mock_bedrock.return_value = MagicMock()
        agent = FinanceAgent()
        mock_build_prompt.return_value = "Base prompt"
        mock_get_templates.return_value = []

        result = await agent._create_system_prompt(self.user_id, "Test task")

        assert "Base prompt" in result
        mock_build_prompt.assert_called_once()
        mock_get_templates.assert_called_once()

    @patch('app.agents.supervisor.finance_agent.agent.ChatBedrock')
    @patch('app.agents.supervisor.finance_agent.agent.create_finance_subgraph')
    @patch('app.agents.supervisor.finance_agent.agent.FinanceAgent._create_system_prompt')
    @pytest.mark.asyncio
    async def test_create_agent_with_tools(self, mock_create_prompt, mock_create_subgraph, mock_bedrock):
        """Test creating agent with tools."""
        mock_bedrock.return_value = MagicMock()
        agent = FinanceAgent()
        mock_create_prompt.return_value = "System prompt"
        mock_subgraph = MagicMock()
        mock_create_subgraph.return_value = mock_subgraph

        result = await agent._create_agent_with_tools(self.user_id)

        assert result == mock_subgraph
        mock_create_subgraph.assert_called_once()

    @patch('app.agents.supervisor.finance_agent.agent.ChatBedrock')
    @patch('app.agents.supervisor.finance_agent.agent.get_cached_finance_agent')
    @patch('app.agents.supervisor.finance_agent.agent.set_cached_finance_agent')
    @patch('app.agents.supervisor.finance_agent.agent.FinanceAgent._create_agent_with_tools')
    @pytest.mark.asyncio
    async def test_process_query_with_and_without_cache(self, mock_create_agent, mock_set_cached, mock_get_cached, mock_bedrock):
        """Test processing query with and without cached agent."""
        mock_bedrock.return_value = MagicMock()
        agent = FinanceAgent()

        # Test with cached agent
        mock_cached_agent = MagicMock()
        mock_command_cached = MagicMock()
        mock_cached_agent.ainvoke = AsyncMock(return_value=mock_command_cached)
        mock_get_cached.return_value = mock_cached_agent

        result_cached = await agent.process_query_with_agent("Test query", self.user_id)

        assert result_cached == mock_command_cached
        mock_get_cached.assert_called_with(self.user_id)
        assert mock_create_agent.call_count == 0

        # Reset mocks and test without cached agent
        mock_create_agent.reset_mock()
        mock_get_cached.reset_mock()
        mock_set_cached.reset_mock()

        mock_new_agent = MagicMock()
        mock_command_new = MagicMock()
        mock_new_agent.ainvoke = AsyncMock(return_value=mock_command_new)
        mock_get_cached.return_value = None
        mock_create_agent.return_value = mock_new_agent

        result_new = await agent.process_query_with_agent("Test query", self.user_id)

        assert result_new == mock_command_new
        mock_create_agent.assert_called_once_with(self.user_id)
        mock_set_cached.assert_called_once()


class TestFinanceAgentNode:
    """Test finance_agent node function."""

    @patch('app.agents.supervisor.finance_agent.agent.get_config_value')
    @patch('app.agents.supervisor.finance_agent.agent.get_finance_agent')
    @patch('app.agents.supervisor.finance_agent.agent._get_last_user_message_text')
    @patch('app.agents.supervisor.finance_agent.agent._get_user_id_from_messages')
    @pytest.mark.asyncio
    async def test_finance_agent_success(self, mock_get_user_id, mock_get_text, mock_get_agent, mock_get_config):
        """Test successful finance agent execution."""
        mock_get_config.return_value = None
        mock_get_user_id.return_value = UUID("12345678-1234-5678-9012-123456789012")
        mock_get_text.return_value = "Test query"
        mock_agent = MagicMock()
        mock_command = MagicMock()
        mock_agent.process_query_with_agent = AsyncMock(return_value=mock_command)
        mock_get_agent.return_value = mock_agent

        state = {"messages": []}
        config = {}

        result = await finance_agent(state, config)

        assert result == mock_command

    @patch('app.agents.supervisor.finance_agent.agent.get_config_value')
    @patch('app.agents.supervisor.finance_agent.agent._get_last_user_message_text')
    @patch('app.agents.supervisor.finance_agent.agent._get_user_id_from_messages')
    @pytest.mark.asyncio
    async def test_finance_agent_validation_errors(self, mock_get_user_id, mock_get_text, mock_get_config):
        """Test finance agent validation errors (no user_id and no query)."""
        mock_get_config.return_value = None
        state = {"messages": []}
        config = {}

        # Test with no user_id
        mock_get_user_id.return_value = None
        result_no_user = await finance_agent(state, config)
        assert "Cannot access financial data" in result_no_user.update["messages"][0]["content"]

        # Test with no query
        mock_get_user_id.return_value = UUID("12345678-1234-5678-9012-123456789012")
        mock_get_text.return_value = ""
        result_no_query = await finance_agent(state, config)
        assert "No task description provided" in result_no_query.update["messages"][0]["content"]
