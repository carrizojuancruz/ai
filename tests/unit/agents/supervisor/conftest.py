import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage


def pytest_configure(config):
    config.addinivalue_line("markers", "unit: Unit tests (no external dependencies)")
    config.addinivalue_line("markers", "integration: Integration tests (with external dependencies)")
    config.addinivalue_line("markers", "slow: Slow running tests")


@pytest.fixture
def mock_bedrock_client(mocker):
    mock = mocker.patch("app.core.app_state.get_bedrock_runtime_client")
    mock_client = MagicMock()

    def mock_invoke_model(modelId: str, body: str) -> dict[str, Any]:
        return {
            "body": MagicMock(
                read=lambda: json.dumps(
                    {
                        "output": {
                            "message": {
                                "content": [
                                    {"text": "This is a summary of the conversation."}
                                ]
                            }
                        }
                    }
                ).encode()
            )
        }

    mock_client.invoke_model.side_effect = mock_invoke_model
    mock.return_value = mock_client
    return mock_client


@pytest.fixture
def mock_chat_bedrock(mocker):
    mock = mocker.patch("app.agents.supervisor.agent.ChatBedrockConverse")
    mock_instance = MagicMock()

    mock_response = MagicMock()
    mock_response.content = "AI response to user query"
    mock_instance.invoke.return_value = mock_response

    mock_instance.get_num_tokens_from_messages.return_value = 100

    mock_instance.bind.return_value = mock_instance

    mock.return_value = mock_instance
    return mock_instance


@pytest.fixture
def mock_langgraph_store(mocker):
    mock_store = MagicMock()

    mock_item = MagicMock()
    mock_item.value = {
        "id": "test_memory_123",
        "user_id": "test_user",
        "type": "semantic",
        "summary": "User prefers casual communication",
        "category": "Personal",
        "tags": ["communication"],
        "source": "chat",
        "importance": 3,
        "pinned": False,
        "created_at": datetime.now(UTC).isoformat(),
        "last_accessed": datetime.now(UTC).isoformat(),
    }
    mock_store.search.return_value = [mock_item]

    mock_store.put.return_value = None

    mock_store.get.return_value = mock_item

    mock_store.delete.return_value = None

    mocker.patch("app.agents.supervisor.memory_tools.get_store", return_value=mock_store)

    return mock_store


@pytest.fixture
def mock_session_store(mocker):
    mock_store = MagicMock()

    default_session = {
        "has_financial_accounts": True,
        "has_plaid_accounts": True,
        "has_financial_data": True,
        "episodic_control": {
            "day_iso": datetime.now(UTC).date().isoformat(),
            "count_today": 0,
            "turns_since_last": 5,
            "last_at_iso": None,
        },
        "user_id": "test_user_123",
    }

    mock_store.get_session = AsyncMock(return_value=default_session)
    mock_store.update_session = AsyncMock(return_value=None)

    mocker.patch(
        "app.repositories.session_store.get_session_store",
        return_value=mock_store,
    )
    mocker.patch(
        "app.agents.supervisor.workers.get_session_store",
        return_value=mock_store,
    )
    return mock_store


@pytest.fixture
def mock_knowledge_service(mocker):
    mock_service = AsyncMock()

    mock_service.search = AsyncMock(
        return_value=[
            {
                "content": "Sample knowledge content about financial planning",
                "source": "https://example.com/article1",
                "score": 0.85,
            },
            {
                "content": "Additional information about budgeting",
                "source": "https://example.com/article2",
                "score": 0.72,
            },
        ]
    )

    mocker.patch("app.agents.supervisor.tools.get_knowledge_service", return_value=mock_service)

    return mock_service


@pytest.fixture
def sample_messages():
    return [
        HumanMessage(content="Hello, how can I track my spending?", id="msg_1"),
        AIMessage(
            content="I can help you track your spending. Let me analyze your recent transactions.",
            id="msg_2",
        ),
        HumanMessage(content="What about my grocery expenses?", id="msg_3"),
        AIMessage(
            content="Your grocery expenses last month were $450.",
            id="msg_4",
        ),
    ]


@pytest.fixture
def sample_long_messages():
    messages = []
    for i in range(20):
        messages.append(
            HumanMessage(
                content=f"User message {i}: " + ("Long content " * 50),
                id=f"msg_user_{i}",
            )
        )
        messages.append(
            AIMessage(
                content=f"AI response {i}: " + ("Detailed response " * 50),
                id=f"msg_ai_{i}",
            )
        )
    return messages


@pytest.fixture
def sample_supervisor_state():
    return {
        "messages": [
            HumanMessage(content="What's my balance?", id="msg_1"),
        ],
        "context": {},
        "total_tokens": 0,
    }


@pytest.fixture
def mock_config():
    return {
        "configurable": {
            "user_id": str(uuid4()),
            "thread_id": f"thread_{uuid4().hex[:8]}",
            "user_context": {
                "identity": {"preferred_name": "Alex", "age": 30},
                "locale_info": {
                    "language": "en-US",
                    "time_zone": "America/New_York",
                },
                "tone_preference": "casual",
            },
        }
    }


@pytest.fixture
def mock_config_no_user():
    return {"configurable": {}}


@pytest.fixture
def mock_wealth_agent_graph(mocker):
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "messages": [
                AIMessage(
                    content="Here's information about emergency funds from our knowledge base.",
                    name="wealth_agent",
                )
            ]
        }
    )

    mocker.patch(
        "app.core.app_state.get_wealth_agent_graph",
        return_value=mock_graph,
    )
    return mock_graph


@pytest.fixture
def mock_goal_agent_graph(mocker):
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "messages": [
                AIMessage(
                    content="Your savings goal is on track. You've saved $1,200 of your $5,000 target.",
                    name="goal_agent",
                )
            ]
        }
    )

    mocker.patch(
        "app.core.app_state.get_goal_agent_graph",
        return_value=mock_graph,
    )
    mock_goal_agent_instance = mocker.MagicMock()
    mock_goal_agent_instance._create_agent_with_tools.return_value = mock_graph
    mocker.patch(
        "app.agents.supervisor.goal_agent.agent.GoalAgent",
        return_value=mock_goal_agent_instance,
    )
    return mock_graph


@pytest.fixture
def mock_finance_agent(mocker):
    mock_finance = AsyncMock(
        return_value={
            "messages": [
                AIMessage(
                    content="Your current balance is $2,450.75",
                    name="finance_agent",
                )
            ]
        }
    )

    mocker.patch(
        "app.agents.supervisor.workers.finance_worker",
        new=mock_finance,
    )
    return mock_finance


@pytest.fixture
def mock_s3_vector_store(mocker):
    mock_store = MagicMock()

    mocker.patch("app.services.memory.store_factory.config.S3V_BUCKET", "test-bucket")
    mocker.patch("app.services.memory.store_factory.config.S3V_INDEX_MEMORY", "test-index")

    mocker.patch(
        "app.services.memory.store_factory.create_s3_vectors_store_from_env",
        return_value=mock_store,
    )
    return mock_store


@pytest.fixture
def mock_memory_service(mocker):
    """Mock memory_service for testing memory operations."""
    mock_service = MagicMock()

    def create_memory_side_effect(user_id, memory_type, key, value, **kwargs):
        return {
            "ok": True,
            "key": key,
            "value": value
        }

    mock_service.create_memory.side_effect = create_memory_side_effect

    mock_service.count_memories.return_value = 50

    mock_service.find_oldest_memory.return_value = None

    mocker.patch("app.agents.supervisor.memory_tools.memory_service", mock_service)
    mocker.patch("app.agents.supervisor.memory.hotpath.memory_service", mock_service)
    mocker.patch("app.agents.supervisor.memory.episodic.memory_service", mock_service)

    return mock_service


@pytest.fixture
def mock_memory_saver(mocker):
    mock = mocker.patch("app.agents.supervisor.agent.MemorySaver")
    mock_instance = MagicMock()
    mock.return_value = mock_instance
    return mock_instance


@pytest.fixture
def mock_sse_queue(mocker):
    mock_queue = MagicMock()
    mocker.patch("app.core.app_state.get_sse_queue", return_value=mock_queue)
    return mock_queue


@pytest.fixture
def sample_running_summary():
    from langmem.short_term import RunningSummary

    return RunningSummary(
        summary="User asked about spending tracking and grocery expenses. Assistant provided spending analysis.",
        summarized_message_ids={"msg_1", "msg_2"},
        last_summarized_message_id="msg_2",
    )
