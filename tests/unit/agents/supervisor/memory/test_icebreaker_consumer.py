import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage

from app.agents.supervisor.memory.icebreaker_consumer import (
    _create_natural_icebreaker,
    debug_icebreaker_flow,
    icebreaker_consumer,
)


@pytest.fixture
def mock_user_id():
    return uuid4()


@pytest.fixture
def mock_config(mock_user_id):
    return {"configurable": {"user_id": str(mock_user_id)}}


@pytest.fixture
def mock_state():
    return {"messages": [MagicMock(role="user", content="Hello")]}


class TestCreateNaturalIcebreaker:
    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.icebreaker_consumer.get_bedrock_runtime_client")
    async def test_creates_natural_icebreaker_success(self, mock_bedrock, mock_user_id):
        mock_client = MagicMock()
        mock_bedrock.return_value = mock_client

        response_data = {
            "output": {
                "message": {
                    "content": [{"text": "I noticed you love hiking! How's that been going lately?"}]
                }
            }
        }
        mock_body = MagicMock()
        mock_body.read.return_value.decode.return_value = json.dumps(response_data)
        mock_client.invoke_model.return_value = {"body": mock_body}

        result = await _create_natural_icebreaker("Rick enjoys hiking in Golden Gate Park", mock_user_id)

        assert result == "I noticed you love hiking! How's that been going lately?"
        mock_client.invoke_model.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.icebreaker_consumer.get_bedrock_runtime_client")
    async def test_handles_string_content(self, mock_bedrock, mock_user_id):
        mock_client = MagicMock()
        mock_bedrock.return_value = mock_client

        response_data = {
            "output": {
                "message": {
                    "content": "You mentioned loving coffee!"
                }
            }
        }
        mock_body = MagicMock()
        mock_body.read.return_value.decode.return_value = json.dumps(response_data)
        mock_client.invoke_model.return_value = {"body": mock_body}

        result = await _create_natural_icebreaker("User loves coffee", mock_user_id)

        assert result == "You mentioned loving coffee!"

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.icebreaker_consumer.get_bedrock_runtime_client")
    async def test_returns_none_on_empty_output(self, mock_bedrock, mock_user_id):
        mock_client = MagicMock()
        mock_bedrock.return_value = mock_client

        response_data = {"output": {"message": {"content": []}}}
        mock_body = MagicMock()
        mock_body.read.return_value.decode.return_value = json.dumps(response_data)
        mock_client.invoke_model.return_value = {"body": mock_body}

        result = await _create_natural_icebreaker("Memory text", mock_user_id)

        assert result is None

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.icebreaker_consumer.get_bedrock_runtime_client")
    async def test_strips_whitespace(self, mock_bedrock, mock_user_id):
        mock_client = MagicMock()
        mock_bedrock.return_value = mock_client

        response_data = {
            "output": {
                "message": {
                    "content": [{"text": "  Generated text with spaces  "}]
                }
            }
        }
        mock_body = MagicMock()
        mock_body.read.return_value.decode.return_value = json.dumps(response_data)
        mock_client.invoke_model.return_value = {"body": mock_body}

        result = await _create_natural_icebreaker("Memory", mock_user_id)

        assert result == "Generated text with spaces"

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.icebreaker_consumer.get_bedrock_runtime_client")
    async def test_handles_bedrock_exception(self, mock_bedrock, mock_user_id):
        mock_client = MagicMock()
        mock_bedrock.return_value = mock_client
        mock_client.invoke_model.side_effect = Exception("Bedrock error")

        result = await _create_natural_icebreaker("Memory text", mock_user_id)

        assert result is None

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.icebreaker_consumer.get_bedrock_runtime_client")
    async def test_handles_json_decode_error(self, mock_bedrock, mock_user_id):
        mock_client = MagicMock()
        mock_bedrock.return_value = mock_client

        mock_body = MagicMock()
        mock_body.read.return_value.decode.return_value = "invalid json"
        mock_client.invoke_model.return_value = {"body": mock_body}

        result = await _create_natural_icebreaker("Memory", mock_user_id)

        assert result is None


class TestDebugIcebreakerFlow:
    @pytest.mark.asyncio
    @patch("app.core.app_state.get_fos_nudge_manager")
    async def test_returns_icebreaker_stats(self, mock_manager):
        user_id = str(uuid4())

        mock_nudge1 = MagicMock(id=uuid4(), priority=10, metadata={"text": "Test"})
        mock_nudge2 = MagicMock(id=uuid4(), priority=5, metadata={"text": "Test2"})

        mock_fos = AsyncMock()
        mock_fos.get_pending_nudges.return_value = [mock_nudge1, mock_nudge2]
        mock_manager.return_value = mock_fos

        result = await debug_icebreaker_flow(user_id)

        assert result["icebreakers"] == 2
        assert result["user_icebreakers"] == 2
        assert result["best_nudge"] == mock_nudge1.id

    @pytest.mark.asyncio
    @patch("app.core.app_state.get_fos_nudge_manager")
    async def test_handles_no_icebreakers(self, mock_manager):
        user_id = str(uuid4())

        mock_fos = AsyncMock()
        mock_fos.get_pending_nudges.return_value = []
        mock_manager.return_value = mock_fos

        result = await debug_icebreaker_flow(user_id)

        assert result["icebreakers"] == 0
        assert result["user_icebreakers"] == 0
        assert result["best_nudge"] is None

    @pytest.mark.asyncio
    @patch("app.core.app_state.get_fos_nudge_manager")
    async def test_handles_exception(self, mock_manager):
        user_id = str(uuid4())
        mock_manager.side_effect = Exception("Manager error")

        result = await debug_icebreaker_flow(user_id)

        assert "error" in result
        assert "Manager error" in result["error"]


class TestIcebreakerConsumer:
    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.icebreaker_consumer.get_icebreaker_processor")
    @patch("app.agents.supervisor.memory.icebreaker_consumer._create_natural_icebreaker")
    async def test_injects_icebreaker_message(self, mock_create, mock_processor, mock_state, mock_config, mock_user_id):
        mock_proc = AsyncMock()
        mock_proc.process_icebreaker_for_user.return_value = "Raw icebreaker text"
        mock_processor.return_value = mock_proc

        mock_create.return_value = "Natural icebreaker message"

        result = await icebreaker_consumer(mock_state, mock_config)

        assert "messages" in result
        assert len(result["messages"]) == 2
        assert isinstance(result["messages"][0], HumanMessage)
        assert "ICEBREAKER_CONTEXT: Natural icebreaker message" in result["messages"][0].content

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_user_id(self, mock_state):
        config = {"configurable": {}}

        result = await icebreaker_consumer(mock_state, config)

        assert result == {}

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.icebreaker_consumer.get_icebreaker_processor")
    async def test_returns_empty_when_processor_fails(self, mock_processor, mock_state, mock_config):
        mock_processor.side_effect = Exception("Processor error")

        result = await icebreaker_consumer(mock_state, mock_config)

        assert result == {}

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.icebreaker_consumer.get_icebreaker_processor")
    async def test_returns_empty_when_no_icebreaker_text(self, mock_processor, mock_state, mock_config):
        mock_proc = AsyncMock()
        mock_proc.process_icebreaker_for_user.return_value = None
        mock_processor.return_value = mock_proc

        result = await icebreaker_consumer(mock_state, mock_config)

        assert result == {}

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.icebreaker_consumer.get_icebreaker_processor")
    @patch("app.agents.supervisor.memory.icebreaker_consumer._create_natural_icebreaker")
    async def test_returns_empty_when_llm_fails(self, mock_create, mock_processor, mock_state, mock_config):
        mock_proc = AsyncMock()
        mock_proc.process_icebreaker_for_user.return_value = "Raw text"
        mock_processor.return_value = mock_proc

        mock_create.return_value = None

        result = await icebreaker_consumer(mock_state, mock_config)

        assert result == {}

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.icebreaker_consumer.get_icebreaker_processor")
    @patch("app.agents.supervisor.memory.icebreaker_consumer._create_natural_icebreaker")
    async def test_handles_string_user_id(self, mock_create, mock_processor, mock_state, mock_user_id):
        config = {"configurable": {"user_id": str(mock_user_id)}}

        mock_proc = AsyncMock()
        mock_proc.process_icebreaker_for_user.return_value = "Raw text"
        mock_processor.return_value = mock_proc

        mock_create.return_value = "Natural text"

        result = await icebreaker_consumer(mock_state, config)

        assert "messages" in result
        mock_proc.process_icebreaker_for_user.assert_called_once_with(mock_user_id)

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.icebreaker_consumer.get_icebreaker_processor")
    async def test_handles_process_exception(self, mock_processor, mock_state, mock_config):
        mock_proc = AsyncMock()
        mock_proc.process_icebreaker_for_user.side_effect = Exception("Process error")
        mock_processor.return_value = mock_proc

        result = await icebreaker_consumer(mock_state, mock_config)

        assert result == {}

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.icebreaker_consumer.get_icebreaker_processor")
    @patch("app.agents.supervisor.memory.icebreaker_consumer._create_natural_icebreaker")
    async def test_handles_critical_exception(self, mock_create, mock_processor, mock_state, mock_config):
        mock_processor.side_effect = Exception("Critical error")

        result = await icebreaker_consumer(mock_state, mock_config)

        assert result == {}

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.icebreaker_consumer.get_icebreaker_processor")
    @patch("app.agents.supervisor.memory.icebreaker_consumer._create_natural_icebreaker")
    async def test_preserves_existing_messages(self, mock_create, mock_processor, mock_user_id):
        msg1 = MagicMock(role="user", content="First message")
        msg2 = MagicMock(role="assistant", content="Response")
        state = {"messages": [msg1, msg2]}
        config = {"configurable": {"user_id": str(mock_user_id)}}

        mock_proc = AsyncMock()
        mock_proc.process_icebreaker_for_user.return_value = "Raw"
        mock_processor.return_value = mock_proc

        mock_create.return_value = "Natural"

        result = await icebreaker_consumer(state, config)

        assert len(result["messages"]) == 3
        assert result["messages"][1] == msg1
        assert result["messages"][2] == msg2
