"""
Unit tests for app.services.onboarding.service module.

Tests cover:
- User context export functionality
- Onboarding session initialization
- Message processing during onboarding
- Session finalization
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.agents.onboarding.state import OnboardingState
from app.services.external_context.user.profile_metadata import build_profile_metadata_payload
from app.services.onboarding.service import OnboardingService


class TestOnboardingService:
    """Test OnboardingService functionality."""

    @pytest.fixture
    def service(self):
        """OnboardingService instance for testing."""
        return OnboardingService()

    @pytest.fixture
    def sample_user_id(self):
        """Sample user ID for testing."""
        return str(uuid4())

    @pytest.fixture
    def sample_thread_id(self):
        """Sample thread ID for testing."""
        return str(uuid4())

    @pytest.fixture
    def onboarding_state_with_profile(self, sample_user_id):
        """Real onboarding state populated with profile info."""
        state = OnboardingState(user_id=UUID(sample_user_id))
        state.user_context.preferred_name = "Leonardo"
        state.user_context.identity.birth_date = "1999-01-16"
        state.user_context.location.city = "Buenos Aires"
        state.user_context.location.region = "AR"
        return state

    @pytest.fixture
    def mock_onboarding_state(self, sample_user_id):
        """Mock OnboardingState for testing."""
        from app.agents.onboarding.state import OnboardingState

        state = MagicMock(spec=OnboardingState)
        state.user_id = sample_user_id
        state.user_context = MagicMock()
        state.last_agent_response = "Welcome message"
        state.current_flow_step = MagicMock()
        return state

    @pytest.mark.asyncio
    async def test_export_user_context_already_exported(self, service, mock_onboarding_state, sample_thread_id):
        """Test that export is skipped if already exported."""
        mock_session_store = MagicMock()
        mock_session_store.get_session = AsyncMock(return_value={"fos_exported": True})

        with patch("app.services.onboarding.service.get_session_store", return_value=mock_session_store):
            await service._export_user_context(mock_onboarding_state, sample_thread_id)

            # Should not call external repository
            mock_session_store.set_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_message_text_type(self, service, sample_thread_id, mock_onboarding_state):
        """Test processing text message."""
        mock_agent = MagicMock()

        def mock_process_message_with_events(*args, **kwargs):
            return self._mock_async_generator(
                [
                    ({"event": "message.completed", "data": {"text": "Response"}}, mock_onboarding_state),
                ]
            )

        mock_agent.process_message_with_events = mock_process_message_with_events

        mock_queue = MagicMock()
        mock_queue.put = AsyncMock()

        with (
            patch("app.services.onboarding.service.get_thread_state", return_value=mock_onboarding_state),
            patch("app.services.onboarding.service.get_thread_lock", return_value=AsyncMock()),
            patch("app.services.onboarding.service.get_onboarding_agent", return_value=mock_agent),
            patch("app.services.onboarding.service.get_sse_queue", return_value=mock_queue),
            patch("app.services.onboarding.service.get_last_emitted_text", return_value=""),
            patch("app.services.onboarding.service.set_last_emitted_text"),
            patch("app.services.onboarding.service.set_thread_state"),
        ):
            result = await service.process_message(thread_id=sample_thread_id, type="text", text="Hello")

            assert result == {"status": "accepted"}
            assert mock_onboarding_state.last_user_message == "Hello"

    @pytest.mark.asyncio
    async def test_process_message_choice_type(self, service, sample_thread_id, mock_onboarding_state):
        """Test processing choice message."""
        # Mock choices in state
        mock_choice1 = MagicMock()
        mock_choice1.id = "choice1"
        mock_choice1.value = "Option 1"
        mock_choice2 = MagicMock()
        mock_choice2.id = "choice2"
        mock_choice2.value = "Option 2"
        mock_onboarding_state.current_choices = [mock_choice1, mock_choice2]

        mock_agent = MagicMock()

        def mock_process_message_with_events(*args, **kwargs):
            return self._mock_async_generator(
                [
                    ({"event": "step.update", "data": {}}, mock_onboarding_state),
                ]
            )

        mock_agent.process_message_with_events = mock_process_message_with_events

        with (
            patch("app.services.onboarding.service.get_thread_state", return_value=mock_onboarding_state),
            patch("app.services.onboarding.service.get_thread_lock", return_value=AsyncMock()),
            patch("app.services.onboarding.service.get_onboarding_agent", return_value=mock_agent),
            patch("app.services.onboarding.service.get_sse_queue", return_value=AsyncMock()),
            patch("app.services.onboarding.service.get_last_emitted_text", return_value=""),
            patch("app.services.onboarding.service.set_last_emitted_text"),
            patch("app.services.onboarding.service.set_thread_state"),
        ):
            result = await service.process_message(
                thread_id=sample_thread_id, type="choice", choice_ids=["choice1", "choice2"]
            )

            assert result == {"status": "accepted"}
            assert mock_onboarding_state.last_user_message == "Option 1, Option 2"

    @pytest.mark.asyncio
    async def test_process_message_control_back(self, service, sample_thread_id, mock_onboarding_state):
        """Test processing control message with back action."""
        mock_queue = MagicMock()
        mock_queue.put = AsyncMock()

        with (
            patch("app.services.onboarding.service.get_thread_state", return_value=mock_onboarding_state),
            patch("app.services.onboarding.service.get_thread_lock", return_value=AsyncMock()),
            patch("app.services.onboarding.service.get_sse_queue", return_value=mock_queue),
            patch("app.services.onboarding.service.set_thread_state"),
        ):
            result = await service.process_message(thread_id=sample_thread_id, type="control", action="back")

            assert result == {"status": "accepted"}
            mock_queue.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_thread_not_found(self, service, sample_thread_id):
        """Test processing message for non-existent thread."""
        with patch("app.services.onboarding.service.get_thread_state", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await service.process_message(thread_id=sample_thread_id, type="text", text="Hello")

            assert exc_info.value.status_code == 404
            assert "Thread not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_finalize_thread_not_found(self, service, sample_thread_id):
        """Test finalization for non-existent thread."""
        with patch("app.services.onboarding.service.get_thread_state", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await service.finalize(thread_id=sample_thread_id)

            assert exc_info.value.status_code == 404
            assert "Thread not found" in str(exc_info.value.detail)

    def _mock_async_generator(self, items):
        """Helper to create async generator mock."""

        async def async_gen():
            for item in items:
                yield item

        return async_gen()

    def test_build_profile_metadata_payload_with_full_data(self, onboarding_state_with_profile):
        """Profile metadata payload includes available fields."""
        payload = build_profile_metadata_payload(onboarding_state_with_profile.user_context)
        assert payload == {
            "meta_data": {
                "user_profile": {
                    "preferred_name": "Leonardo",
                    "birth_date": "1999-01-16",
                    "location": "Buenos Aires, AR",
                }
            }
        }

    def test_build_profile_metadata_payload_returns_none_when_empty(self):
        """Payload builder skips empty data."""
        empty_state = OnboardingState(user_id=uuid4())
        payload = build_profile_metadata_payload(empty_state.user_context)
        assert payload is None

    @pytest.mark.asyncio
    async def test_export_user_context_updates_metadata(self, service, onboarding_state_with_profile, sample_thread_id):
        """Export triggers context upsert and metadata update."""
        mock_session_store = MagicMock()
        mock_session_store.get_session = AsyncMock(return_value={})
        mock_session_store.set_session = AsyncMock()

        mock_repo = MagicMock()
        mock_repo.upsert = AsyncMock(return_value={"status": "ok"})
        mock_repo.update_user_profile_metadata = AsyncMock(return_value={"meta": "ok"})

        with (
            patch("app.services.onboarding.service.get_session_store", return_value=mock_session_store),
            patch("app.services.onboarding.service.ExternalUserRepository", return_value=mock_repo),
            patch(
                "app.services.onboarding.service.map_user_context_to_ai_context",
                return_value={"context": "data"},
            ),
        ):
            await service._export_user_context(onboarding_state_with_profile, sample_thread_id)

        mock_repo.upsert.assert_awaited_once_with(onboarding_state_with_profile.user_id, {"context": "data"})
        mock_repo.update_user_profile_metadata.assert_awaited_once_with(
            onboarding_state_with_profile.user_id,
            {
                "meta_data": {
                    "user_profile": {
                        "preferred_name": "Leonardo",
                        "birth_date": "1999-01-16",
                        "location": "Buenos Aires, AR",
                    }
                }
            },
        )
        mock_session_store.set_session.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_export_user_context_skips_metadata_when_empty(self, service, sample_thread_id):
        """Metadata update is skipped when payload builder returns None."""
        empty_state = OnboardingState(user_id=uuid4())

        mock_session_store = MagicMock()
        mock_session_store.get_session = AsyncMock(return_value={})
        mock_session_store.set_session = AsyncMock()

        mock_repo = MagicMock()
        mock_repo.upsert = AsyncMock(return_value={"status": "ok"})
        mock_repo.update_user_profile_metadata = AsyncMock()

        with (
            patch("app.services.onboarding.service.get_session_store", return_value=mock_session_store),
            patch("app.services.onboarding.service.ExternalUserRepository", return_value=mock_repo),
            patch(
                "app.services.onboarding.service.map_user_context_to_ai_context",
                return_value={"context": "data"},
            ),
        ):
            await service._export_user_context(empty_state, sample_thread_id)

        mock_repo.upsert.assert_awaited_once()
        mock_repo.update_user_profile_metadata.assert_not_called()
        mock_session_store.set_session.assert_awaited_once()
