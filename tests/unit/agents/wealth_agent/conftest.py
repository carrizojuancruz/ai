"""Fixtures for wealth_agent tests."""

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage


def pytest_configure(config):
    """Configure pytest markers for wealth_agent tests."""
    config.addinivalue_line("markers", "unit: Unit tests (no external dependencies)")
    config.addinivalue_line("markers", "integration: Integration tests (with external dependencies)")


@pytest.fixture
def mock_llm():
    """Mock ChatBedrockConverse LLM."""
    mock = MagicMock()
    mock.bind_tools = MagicMock(return_value=mock)

    # Mock ainvoke response
    mock_response = MagicMock()
    mock_response.content = "This is a test response about financial planning."
    mock_response.tool_calls = []
    mock.ainvoke = AsyncMock(return_value=mock_response)

    return mock


@pytest.fixture
def mock_knowledge_service(mocker):
    """Mock knowledge service for search_kb tool."""
    mock_service = AsyncMock()

    mock_service.search = AsyncMock(
        return_value=[
            {
                "content": "Emergency funds are savings set aside for unexpected expenses.",
                "section_url": "https://example.com/emergency-fund#section1",
                "source_url": "https://example.com/emergency-fund",
                "name": "Emergency Fund Guide",
                "type": "article",
                "category": "Financial Planning",
                "description": "Comprehensive guide to emergency funds",
            },
            {
                "content": "It is recommended to have 3-6 months of expenses saved.",
                "section_url": "https://example.com/savings#section2",
                "source_url": "https://example.com/savings",
                "name": "Savings Best Practices",
                "type": "guide",
                "category": "Savings",
                "description": "Best practices for building savings",
            },
        ]
    )

    mocker.patch("app.agents.supervisor.wealth_agent.tools.get_knowledge_service", return_value=mock_service)

    return mock_service


@pytest.fixture
def mock_config():
    """Mock RunnableConfig with user_id and thread_id."""
    return {
        "configurable": {
            "user_id": str(uuid4()),
            "thread_id": f"test_thread_{uuid4().hex[:8]}",
        }
    }


@pytest.fixture
def sample_user_id():
    """Sample UUID for user_id."""
    return uuid4()


@pytest.fixture
def sample_messages():
    """Sample messages for testing."""
    return [
        HumanMessage(content="What is an emergency fund?", id="msg_1"),
        AIMessage(
            content="An emergency fund is savings for unexpected expenses.",
            name="wealth_agent",
            id="msg_2",
        ),
    ]


@pytest.fixture
def mock_wealth_agent_instance(mocker, mock_llm):
    """Mock WealthAgent instance."""
    mocker.patch("app.agents.supervisor.wealth_agent.agent.ChatBedrockConverse", return_value=mock_llm)

    from app.agents.supervisor.wealth_agent.agent import WealthAgent

    return WealthAgent()


@pytest.fixture
def mock_tool_message():
    """Create a mock ToolMessage with search results."""
    from langchain_core.messages import ToolMessage

    search_results = [
        {
            "content": "Emergency funds should cover 3-6 months of expenses.",
            "source": "https://example.com/guide#emergency",
            "metadata": {
                "source_url": "https://example.com/guide",
                "section_url": "https://example.com/guide#emergency",
                "name": "Financial Planning Guide",
                "type": "guide",
                "category": "Emergency Planning",
                "description": "Complete guide to emergency planning",
            }
        }
    ]

    return ToolMessage(
        content=json.dumps(search_results),
        tool_call_id="test_tool_call",
        name="search_kb",
    )


@pytest.fixture
def wealth_state_with_messages():
    """WealthState with sample messages."""
    from app.agents.supervisor.wealth_agent.subgraph import WealthState

    return WealthState(
        messages=[
            HumanMessage(content="What is an emergency fund?"),
        ],
        tool_call_count=0,
        retrieved_sources=[],
        used_sources=[],
        filtered_sources=[],
    )


@pytest.fixture
def wealth_state_with_tool_calls():
    """WealthState with tool calls in progress."""
    from app.agents.supervisor.wealth_agent.subgraph import WealthState

    mock_msg = MagicMock()
    mock_msg.content = ""
    mock_msg.tool_calls = [{"name": "search_kb", "args": {"query": "emergency fund"}}]

    return WealthState(
        messages=[
            HumanMessage(content="What is an emergency fund?"),
            mock_msg,
        ],
        tool_call_count=1,
        retrieved_sources=[],
        used_sources=[],
        filtered_sources=[],
    )


@pytest.fixture
def wealth_state_max_tools():
    """WealthState at max tool call limit."""
    from app.agents.supervisor.wealth_agent.subgraph import WealthState
    from app.core.config import config

    return WealthState(
        messages=[HumanMessage(content="Test query")],
        tool_call_count=config.WEALTH_AGENT_MAX_TOOL_CALLS,
        retrieved_sources=[],
        used_sources=[],
        filtered_sources=[],
    )
