import json
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.agents.supervisor.memory.profile_sync import _profile_sync_from_memory


@pytest.fixture
def mock_user_id():
    return str(uuid4())


@pytest.fixture
def mock_thread_id():
    return "thread-123"


@pytest.fixture
def mock_bedrock_response():
    def _create_response(extracted_data):
        if "about_user" not in extracted_data:
            extracted_data = dict(extracted_data)
            extracted_data["about_user"] = True
        return {
            "body": MagicMock(
                read=lambda: json.dumps(
                    {"output": {"message": {"content": [{"text": json.dumps(extracted_data)}]}}}
                ).encode("utf-8")
            )
        }

    return _create_response


class TestProfileSyncFromMemory:
    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.profile_sync.get_bedrock_runtime_client")
    @patch("app.agents.supervisor.memory.profile_sync.ExternalUserRepository")
    @patch("app.agents.supervisor.memory.profile_sync.context_patching_service")
    async def test_extracts_and_syncs_profile_data(
        self, mock_patching, mock_repo_class, mock_bedrock, mock_user_id, mock_thread_id, mock_bedrock_response
    ):
        mock_client = MagicMock()
        mock_bedrock.return_value = mock_client

        extracted_data = {"preferred_name": "Alice", "city": "San Francisco", "age": 30, "tone": "friendly"}
        mock_client.invoke_model.return_value = mock_bedrock_response(extracted_data)

        mock_repo = AsyncMock()
        mock_repo.get_by_id.return_value = None
        mock_repo.upsert.return_value = {"status": "ok"}
        mock_repo.update_user_profile_metadata = AsyncMock(return_value={"status": "ok"})
        mock_repo_class.return_value = mock_repo

        def _apply_patch_side_effect(state, *_args, **_kwargs):
            state.user_context.preferred_name = "Alice"
            state.user_context.location.city = "San Francisco"

        mock_patching.apply_context_patch.side_effect = _apply_patch_side_effect

        value = {"summary": "User mentioned their name is Alice and they live in SF", "category": "Identity"}

        await _profile_sync_from_memory(mock_user_id, mock_thread_id, value)

        mock_client.invoke_model.assert_called_once()
        mock_patching.apply_context_patch.assert_called_once()
        mock_repo.upsert.assert_called_once()
        mock_repo.update_user_profile_metadata.assert_awaited_once_with(
            ANY,
            {"meta_data": {"user_profile": {"preferred_name": "Alice", "location": "San Francisco"}}},
        )

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.profile_sync.context_patching_service")
    @patch("app.agents.supervisor.memory.profile_sync.get_bedrock_runtime_client")
    @patch("app.agents.supervisor.memory.profile_sync.ExternalUserRepository")
    async def test_handles_goals_addition(
        self, mock_repo_class, mock_bedrock, mock_patching, mock_user_id, mock_thread_id, mock_bedrock_response
    ):
        mock_client = MagicMock()
        mock_bedrock.return_value = mock_client

        extracted_data = {"goals_add": ["save for vacation", "pay off debt"]}
        mock_client.invoke_model.return_value = mock_bedrock_response(extracted_data)

        mock_repo = AsyncMock()
        mock_repo.get_by_id.return_value = None
        mock_repo.upsert.return_value = {"status": "ok"}
        mock_repo_class.return_value = mock_repo

        value = {"summary": "User wants to save for vacation and pay off debt", "category": "Goals"}

        await _profile_sync_from_memory(mock_user_id, mock_thread_id, value)

        mock_repo.upsert.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.profile_sync.context_patching_service")
    @patch("app.agents.supervisor.memory.profile_sync.get_bedrock_runtime_client")
    @patch("app.agents.supervisor.memory.profile_sync.ExternalUserRepository")
    async def test_handles_income_band_and_money_feelings(
        self, mock_repo_class, mock_bedrock, mock_patching, mock_user_id, mock_thread_id, mock_bedrock_response
    ):
        mock_client = MagicMock()
        mock_bedrock.return_value = mock_client

        extracted_data = {"income_band": "50k_75k", "money_feelings": "anxious"}
        mock_client.invoke_model.return_value = mock_bedrock_response(extracted_data)

        mock_repo = AsyncMock()
        mock_repo.get_by_id.return_value = None
        mock_repo.upsert.return_value = {"status": "ok"}
        mock_repo_class.return_value = mock_repo

        value = {"summary": "User earns 50-75k and feels anxious about money", "category": "Finance"}

        await _profile_sync_from_memory(mock_user_id, mock_thread_id, value)

        mock_repo.upsert.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.profile_sync.context_patching_service")
    @patch("app.agents.supervisor.memory.profile_sync.get_bedrock_runtime_client")
    @patch("app.agents.supervisor.memory.profile_sync.ExternalUserRepository")
    async def test_handles_json_extraction_from_text(
        self, mock_repo_class, mock_bedrock, mock_patching, mock_user_id, mock_thread_id
    ):
        mock_client = MagicMock()
        mock_bedrock.return_value = mock_client

        response_text = 'Here is the JSON: {"city": "Boston", "age": 25, "about_user": true} and some extra text'
        mock_client.invoke_model.return_value = {
            "body": MagicMock(
                read=lambda: json.dumps({"output": {"message": {"content": [{"text": response_text}]}}}).encode("utf-8")
            )
        }

        mock_repo = AsyncMock()
        mock_repo.get_by_id.return_value = None
        mock_repo.upsert.return_value = {"status": "ok"}
        mock_repo_class.return_value = mock_repo

        value = {"summary": "User lives in Boston, age 25", "category": "Identity"}

        await _profile_sync_from_memory(mock_user_id, mock_thread_id, value)

        mock_repo.upsert.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.profile_sync.get_bedrock_runtime_client")
    @patch("app.agents.supervisor.memory.profile_sync.ExternalUserRepository")
    async def test_skips_empty_or_whitespace_values(
        self, mock_repo_class, mock_bedrock, mock_user_id, mock_thread_id, mock_bedrock_response
    ):
        mock_client = MagicMock()
        mock_bedrock.return_value = mock_client

        extracted_data = {"preferred_name": "  ", "city": "", "age": 0}
        mock_client.invoke_model.return_value = mock_bedrock_response(extracted_data)

        mock_repo = AsyncMock()
        mock_repo.get_by_id.return_value = None
        mock_repo_class.return_value = mock_repo

        value = {"summary": "Empty data test", "category": "Test"}

        await _profile_sync_from_memory(mock_user_id, mock_thread_id, value)

        mock_repo.upsert.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.profile_sync.context_patching_service")
    @patch("app.agents.supervisor.memory.profile_sync.get_bedrock_runtime_client")
    @patch("app.agents.supervisor.memory.profile_sync.ExternalUserRepository")
    async def test_handles_existing_external_context(
        self, mock_repo_class, mock_bedrock, mock_patching, mock_user_id, mock_thread_id, mock_bedrock_response
    ):
        mock_client = MagicMock()
        mock_bedrock.return_value = mock_client

        extracted_data = {"city": "Denver"}
        mock_client.invoke_model.return_value = mock_bedrock_response(extracted_data)

        existing_context = {"profile": {"preferred_name": "Bob", "goals": ["save money"]}}

        mock_repo = AsyncMock()
        mock_repo.get_by_id.return_value = existing_context
        mock_repo.upsert.return_value = {"status": "ok"}
        mock_repo_class.return_value = mock_repo

        value = {"summary": "User moved to Denver", "category": "Location"}

        await _profile_sync_from_memory(mock_user_id, mock_thread_id, value)

        mock_repo.get_by_id.assert_called_once()
        mock_repo.upsert.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.profile_sync.context_patching_service")
    @patch("app.agents.supervisor.memory.profile_sync.get_bedrock_runtime_client")
    @patch("app.agents.supervisor.memory.profile_sync.ExternalUserRepository")
    async def test_handles_upsert_failure(
        self, mock_repo_class, mock_bedrock, mock_patching, mock_user_id, mock_thread_id, mock_bedrock_response
    ):
        mock_client = MagicMock()
        mock_bedrock.return_value = mock_client

        extracted_data = {"city": "Seattle"}
        mock_client.invoke_model.return_value = mock_bedrock_response(extracted_data)

        mock_repo = AsyncMock()
        mock_repo.get_by_id.return_value = None
        mock_repo.upsert.return_value = None
        mock_repo_class.return_value = mock_repo

        value = {"summary": "User in Seattle", "category": "Location"}

        await _profile_sync_from_memory(mock_user_id, mock_thread_id, value)

        mock_repo.upsert.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.profile_sync.get_bedrock_runtime_client")
    async def test_handles_bedrock_exception(self, mock_bedrock, mock_user_id, mock_thread_id):
        mock_client = MagicMock()
        mock_bedrock.return_value = mock_client
        mock_client.invoke_model.side_effect = Exception("Bedrock error")

        value = {"summary": "Test", "category": "Test"}

        await _profile_sync_from_memory(mock_user_id, mock_thread_id, value)

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.profile_sync.context_patching_service")
    @patch("app.agents.supervisor.memory.profile_sync.get_bedrock_runtime_client")
    @patch("app.agents.supervisor.memory.profile_sync.ExternalUserRepository")
    async def test_handles_repo_exception(
        self, mock_repo_class, mock_bedrock, mock_patching, mock_user_id, mock_thread_id, mock_bedrock_response
    ):
        mock_client = MagicMock()
        mock_bedrock.return_value = mock_client

        extracted_data = {"city": "Portland"}
        mock_client.invoke_model.return_value = mock_bedrock_response(extracted_data)

        mock_repo = AsyncMock()
        mock_repo.get_by_id.side_effect = Exception("Repo error")
        mock_repo_class.return_value = mock_repo

        value = {"summary": "User in Portland", "category": "Location"}

        await _profile_sync_from_memory(mock_user_id, mock_thread_id, value)

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.profile_sync.get_bedrock_runtime_client")
    @patch("app.agents.supervisor.memory.profile_sync.ExternalUserRepository")
    async def test_handles_invalid_json_response(self, mock_repo_class, mock_bedrock, mock_user_id, mock_thread_id):
        mock_client = MagicMock()
        mock_bedrock.return_value = mock_client

        mock_client.invoke_model.return_value = {
            "body": MagicMock(
                read=lambda: json.dumps(
                    {"output": {"message": {"content": [{"text": "not valid json at all"}]}}}
                ).encode("utf-8")
            )
        }

        mock_repo = AsyncMock()
        mock_repo_class.return_value = mock_repo

        value = {"summary": "Test invalid JSON", "category": "Test"}

        await _profile_sync_from_memory(mock_user_id, mock_thread_id, value)

        mock_repo.upsert.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.agents.supervisor.memory.profile_sync.context_patching_service")
    @patch("app.agents.supervisor.memory.profile_sync.get_bedrock_runtime_client")
    @patch("app.agents.supervisor.memory.profile_sync.ExternalUserRepository")
    async def test_truncates_long_summary_and_category(
        self, mock_repo_class, mock_bedrock, mock_patching, mock_user_id, mock_thread_id, mock_bedrock_response
    ):
        mock_client = MagicMock()
        mock_bedrock.return_value = mock_client

        extracted_data = {"city": "Austin"}
        mock_client.invoke_model.return_value = mock_bedrock_response(extracted_data)

        mock_repo = AsyncMock()
        mock_repo.get_by_id.return_value = None
        mock_repo.upsert.return_value = {"status": "ok"}
        mock_repo_class.return_value = mock_repo

        long_summary = "A" * 1000
        long_category = "B" * 100
        value = {"summary": long_summary, "category": long_category}

        await _profile_sync_from_memory(mock_user_id, mock_thread_id, value)

        call_args = mock_client.invoke_model.call_args
        body_json = json.loads(call_args[1]["body"])
        prompt = body_json["messages"][0]["content"][0]["text"]

        assert len([line for line in prompt.split("\n") if line.startswith("Summary:")][0]) <= 520
        assert len([line for line in prompt.split("\n") if line.startswith("Category:")][0]) <= 80
