"""
Tests for SupervisorService - supervisor agent orchestration and business logic.

Focus on valuable business logic:
- Guardrail detection and intervention handling
- User context loading and export
- Conversation summarization
- Source extraction from tools
- Prior conversation retrieval
- Thread management
"""
import contextlib
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest

from app.models.user import UserContext
from app.services.supervisor import (
    GUARDRAIL_INTERVENED_MARKER,
    SupervisorService,
    _strip_emojis,
)


@pytest.fixture
def supervisor_service():
    """Create SupervisorService instance for testing."""
    return SupervisorService()


@pytest.fixture
def mock_user_id():
    """Fixed UUID for testing."""
    return UUID("12345678-1234-5678-1234-567812345678")


class TestStripEmojis:
    """Test emoji stripping utility function."""

    def test_strips_emojis_and_handles_edge_cases(self):
        """Should remove emojis, handle plain text, and non-string input."""
        # Removes emojis
        text_with_emojis = "Hello 👋 world 🌍 test 🎉"
        result = _strip_emojis(text_with_emojis)
        assert result == "Hello  world  test "
        assert "👋" not in result

        # Handles plain text (no emojis)
        plain_text = "Plain text without emojis"
        assert _strip_emojis(plain_text) == plain_text

        # Handles non-string input
        assert _strip_emojis(None) is None
        assert _strip_emojis(123) == 123
        assert _strip_emojis([]) == []


class TestGuardrailDetection:
    """Test guardrail intervention detection and handling."""

    def test_has_guardrail_intervention_detection(self, supervisor_service):
        """Should detect guardrail marker in text and handle edge cases."""
        # Detects marker
        text_with_marker = f"Normal text {GUARDRAIL_INTERVENED_MARKER} blocked content"
        assert supervisor_service._has_guardrail_intervention(text_with_marker) is True

        # Returns False without marker
        text_without_marker = "Normal conversation text"
        assert supervisor_service._has_guardrail_intervention(text_without_marker) is False

        # Handles non-string input
        assert supervisor_service._has_guardrail_intervention(None) is False
        assert supervisor_service._has_guardrail_intervention(123) is False
        assert supervisor_service._has_guardrail_intervention([]) is False

    def test_strip_guardrail_marker(self, supervisor_service):
        """Should strip guardrail marker and content after it."""
        # Strips marker and after
        text = f"Clean content{GUARDRAIL_INTERVENED_MARKER}blocked content"
        result = supervisor_service._strip_guardrail_marker(text)
        assert result == "Clean content"
        assert GUARDRAIL_INTERVENED_MARKER not in result
        assert "blocked" not in result

        # Handles no marker
        text_no_marker = "Normal text without marker"
        assert supervisor_service._strip_guardrail_marker(text_no_marker) == text_no_marker

        # Handles non-string input
        assert supervisor_service._strip_guardrail_marker(None) == ""
        assert supervisor_service._strip_guardrail_marker(123) == ""


class TestInjectedContextDetection:
    """Test injected context detection."""

    def test_detects_injected_context_prefixes(self, supervisor_service):
        """Should detect CONTEXT_PROFILE and Relevant context prefixes."""
        # Detects CONTEXT_PROFILE
        text_context = "CONTEXT_PROFILE: user information here"
        assert supervisor_service._is_injected_context(text_context) is True

        # Detects Relevant context
        text_relevant = "Relevant context for tailoring this turn: information"
        assert supervisor_service._is_injected_context(text_relevant) is True

        # Returns False for normal text
        normal_text = "This is a normal user message"
        assert supervisor_service._is_injected_context(normal_text) is False

        # Handles non-string input
        assert supervisor_service._is_injected_context(None) is False
        assert supervisor_service._is_injected_context(123) is False


class TestContentToText:
    """Test content extraction from various formats."""

    def test_handles_basic_types(self, supervisor_service):
        """Should handle string, None, and nested content."""
        # Handles string
        text = "Simple string content"
        assert supervisor_service._content_to_text(text) == text

        # Handles None
        assert supervisor_service._content_to_text(None) == ""

        # Handles nested content
        mock_obj = Mock()
        mock_obj.content = "Nested content"
        assert supervisor_service._content_to_text(mock_obj) == "Nested content"

    def test_extracts_from_dict_list(self, supervisor_service):
        """Should extract text from list of dicts."""
        content = [
            {"text": "First part "},
            {"content": "second part"},
            {"text": " third part"}
        ]

        result = supervisor_service._content_to_text(content)

        assert result == "First part second part third part"

    def test_handles_mixed_list(self, supervisor_service):
        """Should handle mixed list of strings and dicts."""
        content = [
            {"text": "Part 1"},
            "ignored string",
            {"content": "Part 2"},
            {"other_key": "ignored"}
        ]

        result = supervisor_service._content_to_text(content)

        assert "Part 1" in result
        assert "Part 2" in result


class TestExtractChatPairs:
    """Test chat message extraction."""

    def test_extracts_and_filters_messages(self, supervisor_service):
        """Should extract user/assistant messages and handle role aliases."""
        # Filters user and assistant messages
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "system", "content": "System message"},
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "I'm good!"}
        ]

        result = supervisor_service._extract_chat_pairs(messages)

        assert len(result) == 4
        assert result[0] == ("user", "Hello")
        assert result[1] == ("assistant", "Hi there")
        assert result[2] == ("user", "How are you?")
        assert result[3] == ("assistant", "I'm good!")

        # Handles 'human' and 'ai' role names
        messages_alt = [
            {"role": "human", "content": "Question"},
            {"role": "ai", "content": "Answer"}
        ]

        result_alt = supervisor_service._extract_chat_pairs(messages_alt)
        assert result_alt == [("user", "Question"), ("assistant", "Answer")]

    def test_handles_edge_cases(self, supervisor_service):
        """Should skip empty content and handle empty list."""
        # Skips empty/whitespace content
        messages = [
            {"role": "user", "content": "Valid message"},
            {"role": "assistant", "content": "  "},
            {"role": "user", "content": ""},
            {"role": "assistant", "content": "Another valid"}
        ]

        result = supervisor_service._extract_chat_pairs(messages)

        assert len(result) == 2
        assert result[0] == ("user", "Valid message")
        assert result[1] == ("assistant", "Another valid")

        # Handles empty list
        assert supervisor_service._extract_chat_pairs([]) == []


class TestLoadUserContextFromExternal:
    """Test user context loading from external service."""

    @pytest.mark.asyncio
    async def test_load_user_context_success(self, supervisor_service, mock_user_id):
        """Should load user context from external service."""
        mock_external_ctx = Mock()
        mock_external_ctx.preferred_name = "John"

        with (
            patch("app.services.supervisor.ExternalUserRepository") as mock_repo_class,
            patch("app.services.supervisor.map_ai_context_to_user_context") as mock_map,
        ):
            mock_repo = AsyncMock()
            mock_repo.get_by_id.return_value = mock_external_ctx
            mock_repo_class.return_value = mock_repo

            expected_ctx = UserContext(user_id=mock_user_id, preferred_name="John")
            mock_map.return_value = expected_ctx

            result = await supervisor_service._load_user_context_from_external(mock_user_id)

            assert result.user_id == mock_user_id
            mock_repo.get_by_id.assert_called_once_with(mock_user_id)


    @pytest.mark.asyncio
    async def test_load_user_context_handles_external_error(self, supervisor_service, mock_user_id):
        """Should fallback to empty context on external service error."""
        with patch("app.services.supervisor.ExternalUserRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_by_id.side_effect = Exception("External service error")
            mock_repo_class.return_value = mock_repo

            result = await supervisor_service._load_user_context_from_external(mock_user_id)

            # Should return fallback UserContext
            assert result.user_id == mock_user_id


class TestExportUserContextToExternal:
    """Test user context export to external service."""

    @pytest.mark.asyncio
    async def test_export_user_context_success(self, supervisor_service, mock_user_id):
        """Should export user context to external service."""
        user_context = UserContext(user_id=mock_user_id, preferred_name="John")
        mock_response = {"success": True}

        with (
            patch("app.services.external_context.user.mapping.map_user_context_to_ai_context") as mock_map,
            patch("app.services.external_context.user.repository.ExternalUserRepository") as mock_repo_class,
        ):
            mock_map.return_value = {"preferred_name": "John"}
            mock_repo = AsyncMock()
            mock_repo.upsert.return_value = mock_response
            mock_repo_class.return_value = mock_repo

            result = await supervisor_service._export_user_context_to_external(user_context)

            assert result is True
            mock_repo.upsert.assert_awaited_once_with(mock_user_id, {"preferred_name": "John"})

    @pytest.mark.asyncio
    async def test_export_user_context_handles_none_response(self, supervisor_service, mock_user_id):
        """Should return False when external API returns None."""
        user_context = UserContext(user_id=mock_user_id)

        with (
            patch("app.services.external_context.user.mapping.map_user_context_to_ai_context"),
            patch("app.services.external_context.user.repository.ExternalUserRepository") as mock_repo_class,
        ):
            mock_repo = AsyncMock()
            mock_repo.upsert.return_value = None
            mock_repo_class.return_value = mock_repo

            result = await supervisor_service._export_user_context_to_external(user_context)

            assert result is False

    @pytest.mark.asyncio
    async def test_export_user_context_handles_error(self, supervisor_service, mock_user_id):
        """Should return False on export error."""
        user_context = UserContext(user_id=mock_user_id)

        with (
            patch("app.services.external_context.user.mapping.map_user_context_to_ai_context"),
            patch("app.services.external_context.user.repository.ExternalUserRepository") as mock_repo_class,
        ):
            mock_repo = AsyncMock()
            mock_repo.upsert.side_effect = Exception("API error")
            mock_repo_class.return_value = mock_repo

            result = await supervisor_service._export_user_context_to_external(user_context)

            assert result is False


class TestLoadConversationMessages:
    """Test conversation message loading from session."""

    def test_load_conversation_messages_returns_messages(self, supervisor_service):
        """Should return conversation messages from session data."""
        mock_store = Mock()
        mock_store.sessions = {
            "thread-123": {
                "conversation_messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi"}
                ]
            }
        }

        result = supervisor_service._load_conversation_messages(mock_store, "thread-123")

        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"

    def test_load_conversation_messages_handles_missing_thread(self, supervisor_service):
        """Should return empty list for missing thread."""
        mock_store = Mock()
        mock_store.sessions = {}

        result = supervisor_service._load_conversation_messages(mock_store, "nonexistent")

        assert result == []

    def test_load_conversation_messages_handles_missing_messages_key(self, supervisor_service):
        """Should return empty list when conversation_messages key missing."""
        mock_store = Mock()
        mock_store.sessions = {
            "thread-123": {"user_id": "user-1"}
        }

        result = supervisor_service._load_conversation_messages(mock_store, "thread-123")

        assert result == []


class TestFindLatestPriorThread:
    """Test finding latest prior conversation thread."""

    @pytest.mark.asyncio
    async def test_find_latest_prior_thread_returns_most_recent(self, supervisor_service):
        """Should return most recent thread excluding current."""
        mock_store = AsyncMock()
        mock_store.get_user_threads.return_value = ["thread-1", "thread-2", "thread-3"]
        mock_store.sessions = {
            "thread-1": {"last_accessed": datetime(2024, 1, 1)},
            "thread-2": {"last_accessed": datetime(2024, 1, 3)},  # Most recent
            "thread-3": {"last_accessed": datetime(2024, 1, 2)},
        }

        result = await supervisor_service._find_latest_prior_thread(
            mock_store, "user-1", "thread-2"
        )

        # Should skip thread-2 (current) and return thread-3 as most recent
        assert result == "thread-3"

    @pytest.mark.asyncio
    async def test_find_latest_prior_thread_excludes_current(self, supervisor_service):
        """Should exclude current thread from results."""
        mock_store = AsyncMock()
        mock_store.get_user_threads.return_value = ["thread-1", "thread-2"]
        mock_store.sessions = {
            "thread-1": {"last_accessed": datetime(2024, 1, 1)},
            "thread-2": {"last_accessed": datetime(2024, 1, 5)},  # Current thread
        }

        result = await supervisor_service._find_latest_prior_thread(
            mock_store, "user-1", "thread-2"
        )

        assert result == "thread-1"

    @pytest.mark.asyncio
    async def test_find_latest_prior_thread_returns_none_when_no_others(self, supervisor_service):
        """Should return None when no other threads exist."""
        mock_store = AsyncMock()
        mock_store.get_user_threads.return_value = ["thread-1"]
        mock_store.sessions = {
            "thread-1": {"last_accessed": datetime(2024, 1, 1)},
        }

        result = await supervisor_service._find_latest_prior_thread(
            mock_store, "user-1", "thread-1"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_find_latest_prior_thread_handles_empty_threads(self, supervisor_service):
        """Should return None when user has no threads."""
        mock_store = AsyncMock()
        mock_store.get_user_threads.return_value = []
        mock_store.sessions = {}

        result = await supervisor_service._find_latest_prior_thread(
            mock_store, "user-1", "thread-1"
        )

        assert result is None


class TestSummarizeConversation:
    """Tests for _summarize_conversation method."""

    @pytest.mark.asyncio
    async def test_summarize_conversation_generates_summary(self, supervisor_service):
        """Should generate a summary from conversation pairs."""
        pairs = [
            ("user", "How's the weather today?"),
            ("assistant", "It's sunny and warm!"),
            ("user", "Great, I'll go for a walk."),
            ("assistant", "That sounds wonderful! Enjoy your walk."),
        ]

        with patch("app.services.supervisor.call_llm") as mock_llm:
            mock_llm.return_value = "We talked about the weather and you decided to go for a walk."

            result = await supervisor_service._summarize_conversation(pairs)

            assert result == "We talked about the weather and you decided to go for a walk."
            mock_llm.assert_awaited_once()
            call_args = mock_llm.call_args
            assert "Past conversation:" in call_args[0][1]
            assert "How's the weather today?" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_summarize_conversation_handles_empty_pairs(self, supervisor_service):
        """Should return None for empty conversation."""
        result = await supervisor_service._summarize_conversation([])
        assert result is None

    @pytest.mark.asyncio
    async def test_summarize_conversation_handles_llm_error(self, supervisor_service):
        """Should return None when LLM fails."""
        pairs = [("user", "Hello"), ("assistant", "Hi there!")]

        with patch("app.services.supervisor.call_llm") as mock_llm:
            mock_llm.side_effect = Exception("LLM timeout")

            result = await supervisor_service._summarize_conversation(pairs)

            assert result is None

    @pytest.mark.asyncio
    async def test_summarize_conversation_truncates_long_transcript(self, supervisor_service):
        """Should truncate transcript to max 3000 chars."""
        # Create a very long conversation
        pairs = [("user", "A" * 500), ("assistant", "B" * 500)] * 10

        with patch("app.services.supervisor.call_llm") as mock_llm:
            mock_llm.return_value = "Long conversation summary"

            await supervisor_service._summarize_conversation(pairs)

            # Check that the transcript was truncated
            call_args = mock_llm.call_args[0][1]
            assert len(call_args) < 3500  # Some overhead for formatting


class TestGetPriorConversationSummary:
    """Tests for _get_prior_conversation_summary method."""

    @pytest.mark.asyncio
    async def test_get_prior_summary_returns_summary(self, supervisor_service, mock_user_id):
        """Should get and summarize prior conversation."""
        mock_store = AsyncMock()
        mock_store.get_user_threads.return_value = ["thread-1", "thread-2"]
        mock_store.sessions = {
            "thread-1": {
                "last_accessed": 100,
                "conversation_messages": [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there!"},
                ],
            },
            "thread-2": {"last_accessed": 50},
        }

        with patch("app.services.supervisor.call_llm") as mock_llm:
            mock_llm.return_value = "We greeted each other."

            result = await supervisor_service._get_prior_conversation_summary(
                mock_store, str(mock_user_id), "thread-current"
            )

            assert result == "We greeted each other."

    @pytest.mark.asyncio
    async def test_get_prior_summary_handles_no_prior_thread(self, supervisor_service, mock_user_id):
        """Should return None when no prior thread exists."""
        mock_store = AsyncMock()
        mock_store.get_user_threads.return_value = ["current-thread"]
        mock_store.sessions = {}

        result = await supervisor_service._get_prior_conversation_summary(
            mock_store, str(mock_user_id), "current-thread"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_prior_summary_handles_error(self, supervisor_service, mock_user_id):
        """Should return None on error."""
        mock_store = AsyncMock()
        mock_store.get_user_threads.side_effect = Exception("Database error")

        result = await supervisor_service._get_prior_conversation_summary(
            mock_store, str(mock_user_id), "thread-current"
        )

        assert result is None


class TestInitialize:
    """Tests for initialize method."""

    @pytest.mark.asyncio
    async def test_initialize_creates_thread_and_welcome(self, supervisor_service, mock_user_id):
        """Should initialize conversation with thread and welcome message."""
        with (
            patch("app.services.supervisor.get_sse_queue") as mock_queue,
            patch("app.services.supervisor.get_session_store") as mock_store_getter,
            patch("app.services.supervisor.get_database_service") as mock_db,
            patch("app.services.supervisor.generate_personalized_welcome") as mock_welcome,
        ):
            mock_q = AsyncMock()
            mock_queue.return_value = mock_q

            mock_store = AsyncMock()
            mock_store.set_session = AsyncMock()
            mock_store.get_session.return_value = {"user_context": {}}
            mock_store.get_user_threads.return_value = []
            mock_store_getter.return_value = mock_store

            mock_db_service = AsyncMock()
            mock_db_service.get_session = AsyncMock()
            mock_db.return_value = mock_db_service

            mock_welcome.return_value = "Welcome to Vera!"

            # Mock external context loading
            supervisor_service._load_user_context_from_external = AsyncMock(
                return_value=UserContext(user_id=mock_user_id)
            )

            result = await supervisor_service.initialize(user_id=mock_user_id)

            assert "thread_id" in result
            assert "welcome" in result
            assert "sse_url" in result
            assert result["welcome"] == "Welcome to Vera!"
            mock_q.put.assert_any_call(
                {"event": "conversation.started", "data": {"thread_id": result["thread_id"]}}
            )

    @pytest.mark.asyncio
    async def test_initialize_with_prior_conversation(self, supervisor_service, mock_user_id):
        """Should include prior conversation summary when available."""
        with (
            patch("app.services.supervisor.get_sse_queue") as mock_queue,
            patch("app.services.supervisor.get_session_store") as mock_store_getter,
            patch("app.services.supervisor.get_database_service") as mock_db,
            patch("app.services.supervisor.generate_personalized_welcome") as mock_welcome,
            patch("app.services.supervisor.call_llm") as mock_llm,
        ):
            mock_q = AsyncMock()
            mock_queue.return_value = mock_q

            mock_store = AsyncMock()
            mock_store.set_session = AsyncMock()
            mock_store.get_session.return_value = {"user_context": {}}
            mock_store.get_user_threads.return_value = ["thread-1", "thread-2"]
            mock_store.sessions = {
                "thread-1": {
                    "last_accessed": 100,
                    "conversation_messages": [
                        {"role": "user", "content": "Previous chat"}
                    ],
                }
            }
            mock_store_getter.return_value = mock_store

            mock_db_service = AsyncMock()
            mock_db_service.get_session = AsyncMock()
            mock_db.return_value = mock_db_service

            mock_llm.return_value = "We talked about your goals last time."
            mock_welcome.return_value = "Welcome back!"

            supervisor_service._load_user_context_from_external = AsyncMock(
                return_value=UserContext(user_id=mock_user_id)
            )

            result = await supervisor_service.initialize(user_id=mock_user_id)

            assert result["prior_conversation_summary"] == "We talked about your goals last time."

    @pytest.mark.asyncio
    async def test_initialize_handles_icebreaker(self, supervisor_service, mock_user_id):
        """Should include icebreaker hint when available."""
        with (
            patch("app.services.supervisor.get_sse_queue") as mock_queue,
            patch("app.services.supervisor.get_session_store") as mock_store_getter,
            patch("app.services.supervisor.get_database_service") as mock_db,
            patch("app.services.supervisor.generate_personalized_welcome") as mock_welcome,
            patch("app.services.nudges.icebreaker_processor.get_icebreaker_processor") as mock_ice,
        ):
            mock_q = AsyncMock()
            mock_queue.return_value = mock_q

            mock_store = AsyncMock()
            mock_store.set_session = AsyncMock()
            mock_store.get_session.return_value = {"user_context": {}}
            mock_store.get_user_threads.return_value = []
            mock_store_getter.return_value = mock_store

            mock_db_service = AsyncMock()
            mock_db_service.get_session = AsyncMock()
            mock_db.return_value = mock_db_service

            mock_processor = AsyncMock()
            mock_processor.process_icebreaker_for_user.return_value = "Ask about their weekend plans"
            mock_ice.return_value = mock_processor

            mock_welcome.return_value = "Hey! How was your weekend?"

            supervisor_service._load_user_context_from_external = AsyncMock(
                return_value=UserContext(user_id=mock_user_id)
            )

            await supervisor_service.initialize(user_id=mock_user_id)

            # Check that welcome was called with icebreaker hint
            mock_welcome.assert_awaited_once()
            call_args = mock_welcome.call_args[0]
            assert len(call_args) == 3  # user_context, prior_summary, icebreaker_hint
            assert call_args[2] == "Ask about their weekend plans"


class TestProcessMessage:
    """Tests for process_message method."""

    @pytest.mark.asyncio
    async def test_validates_message_text(self, supervisor_service):
        """Should reject empty and whitespace-only messages."""
        # Rejects empty text
        with pytest.raises(ValueError, match="must not be empty"):
            await supervisor_service.process_message(thread_id="thread-1", text="")

        # Rejects whitespace-only
        with pytest.raises(ValueError, match="must not be empty"):
            await supervisor_service.process_message(thread_id="thread-1", text="   \n\t  ")

    @pytest.mark.asyncio
    async def test_process_message_updates_step_status(self, supervisor_service):
        """Should emit step.update event when processing starts."""
        with (
            patch("app.services.supervisor.get_sse_queue") as mock_queue,
            patch("app.services.supervisor.get_session_store") as mock_store_getter,
        ):
            mock_q = AsyncMock()
            mock_queue.return_value = mock_q

            mock_store = AsyncMock()
            mock_store.get_session.return_value = None
            mock_store_getter.return_value = mock_store

            with contextlib.suppress(Exception):
                await supervisor_service.process_message(thread_id="thread-1", text="Hello")

            # Check that step.update was emitted
            step_updates = [
                call for call in mock_q.put.call_args_list
                if call[0][0].get("event") == "step.update"
            ]
            assert len(step_updates) > 0
            assert step_updates[0][0][0]["data"]["status"] == "processing"

    @pytest.mark.asyncio
    async def test_process_message_refreshes_user_context(self, supervisor_service, mock_user_id):
        """Should refresh user context from external API each turn."""
        with (
            patch("app.services.supervisor.get_sse_queue") as mock_queue,
            patch("app.services.supervisor.get_session_store") as mock_store_getter,
            patch("app.services.supervisor.get_supervisor_graph") as mock_graph,
        ):
            mock_q = AsyncMock()
            mock_queue.return_value = mock_q

            mock_store = AsyncMock()
            session_data = {
                "user_id": str(mock_user_id),
                "user_context": {"preferred_name": "Old Name"},
                "conversation_messages": [],
            }
            mock_store.get_session.return_value = session_data
            mock_store.set_session = AsyncMock()
            mock_store_getter.return_value = mock_store

            # Mock graph streaming
            mock_compiled = AsyncMock()

            async def mock_stream(*args, **kwargs):
                # Emit minimal events to complete the flow
                yield {"event": "on_chain_end", "name": "supervisor", "data": {
                    "output": {"messages": []}
                }}

            mock_compiled.astream_events = mock_stream
            mock_graph.return_value = mock_compiled

            # Mock external context loading
            updated_context = UserContext(user_id=mock_user_id, preferred_name="New Name")
            supervisor_service._load_user_context_from_external = AsyncMock(
                return_value=updated_context
            )

            await supervisor_service.process_message(thread_id="thread-1", text="Hello")

            # Verify context was refreshed
            supervisor_service._load_user_context_from_external.assert_awaited_once_with(mock_user_id)

            # Verify updated context was stored
            mock_store.set_session.assert_any_call(
                "thread-1",
                {
                    "user_id": str(mock_user_id),
                    "user_context": updated_context.model_dump(mode="json"),
                    "conversation_messages": [{"role": "user", "content": "Hello", "sources": []}],
                }
            )

    @pytest.mark.asyncio
    async def test_process_message_stores_conversation(self, supervisor_service, mock_user_id):
        """Should store user message and assistant response in conversation history."""
        with (
            patch("app.services.supervisor.get_sse_queue") as mock_queue,
            patch("app.services.supervisor.get_session_store") as mock_store_getter,
            patch("app.services.supervisor.get_supervisor_graph") as mock_graph,
        ):
            mock_q = AsyncMock()
            mock_queue.return_value = mock_q

            mock_store = AsyncMock()
            session_data = {
                "user_id": str(mock_user_id),
                "user_context": {},
                "conversation_messages": [],
            }
            mock_store.get_session.return_value = session_data
            mock_store.set_session = AsyncMock()
            mock_store_getter.return_value = mock_store

            # Mock graph with response
            mock_compiled = AsyncMock()

            async def mock_stream(*args, **kwargs):
                # Simulate supervisor response
                class MockMessage:
                    def __init__(self):
                        self.content = [{"type": "text", "text": "Hi there! How can I help?"}]

                yield {
                    "event": "on_chain_end",
                    "name": "supervisor",
                    "data": {
                        "output": {
                            "messages": [MockMessage()]
                        }
                    }
                }

            mock_compiled.astream_events = mock_stream
            mock_graph.return_value = mock_compiled

            supervisor_service._load_user_context_from_external = AsyncMock(
                return_value=UserContext(user_id=mock_user_id)
            )
            supervisor_service._export_user_context_to_external = AsyncMock()

            await supervisor_service.process_message(thread_id="thread-1", text="Hello Vera")

            # Check final session contains both messages
            final_call = [call for call in mock_store.set_session.call_args_list if call[0][0] == "thread-1"][-1]
            final_session = final_call[0][1]
            messages = final_session["conversation_messages"]

            assert len(messages) == 2
            assert messages[0]["role"] == "user"
            assert messages[0]["content"] == "Hello Vera"
            assert messages[1]["role"] == "assistant"
            assert "Hi there" in messages[1]["content"]

    @pytest.mark.asyncio
    async def test_process_message_handles_guardrail_intervention(self, supervisor_service, mock_user_id):
        """Should detect and handle guardrail interventions."""
        with (
            patch("app.services.supervisor.get_sse_queue") as mock_queue,
            patch("app.services.supervisor.get_session_store") as mock_store_getter,
            patch("app.services.supervisor.get_supervisor_graph") as mock_graph,
        ):
            mock_q = AsyncMock()
            mock_queue.return_value = mock_q

            mock_store = AsyncMock()
            session_data = {
                "user_id": str(mock_user_id),
                "user_context": {},
                "conversation_messages": [],
            }
            mock_store.get_session.return_value = session_data
            mock_store.set_session = AsyncMock()
            mock_store_getter.return_value = mock_store

            # Mock graph with guardrail response
            mock_compiled = AsyncMock()

            async def mock_stream(*args, **kwargs):
                class MockMessage:
                    def __init__(self):
                        # Guardrail marker appears after assistant content
                        # Strip will remove everything from marker onwards, leaving "I cannot help with that."
                        self.content = [{"type": "text", "text": "I cannot help with that. [GUARDRAIL_INTERVENED]"}]

                yield {
                    "event": "on_chain_end",
                    "name": "supervisor",
                    "data": {
                        "output": {
                            "messages": [MockMessage()]
                        }
                    }
                }

            mock_compiled.astream_events = mock_stream
            mock_graph.return_value = mock_compiled

            supervisor_service._load_user_context_from_external = AsyncMock(
                return_value=UserContext(user_id=mock_user_id)
            )
            supervisor_service._export_user_context_to_external = AsyncMock()

            await supervisor_service.process_message(thread_id="thread-1", text="Bad request")

            # Check that session was updated with conversation messages
            final_call = [call for call in mock_store.set_session.call_args_list if call[0][0] == "thread-1"][-1]
            final_session = final_call[0][1]
            messages = final_session["conversation_messages"]

            # Should have both messages
            assert len(messages) == 2

            # User message exists (should be replaced with placeholder when guardrail triggers)
            assert messages[0]["role"] == "user"
            # Guardrail replaces user message with placeholder constant from supervisor.py
            assert messages[0]["content"] == "THIS MESSAGE HIT THE BEDROCK GUARDRAIL, SO IT WAS REMOVED"

            # Assistant response should have marker stripped
            assert messages[1]["role"] == "assistant"
            assert "GUARDRAIL_INTERVENED" not in messages[1]["content"]
            assert "I cannot help with that" in messages[1]["content"]

    @pytest.mark.asyncio
    async def test_process_message_emits_tool_events(self, supervisor_service, mock_user_id):
        """Should emit tool start/end events during processing."""
        with (
            patch("app.services.supervisor.get_sse_queue") as mock_queue,
            patch("app.services.supervisor.get_session_store") as mock_store_getter,
            patch("app.services.supervisor.get_supervisor_graph") as mock_graph,
        ):
            mock_q = AsyncMock()
            mock_queue.return_value = mock_q

            mock_store = AsyncMock()
            session_data = {
                "user_id": str(mock_user_id),
                "user_context": {},
                "conversation_messages": [],
            }
            mock_store.get_session.return_value = session_data
            mock_store.set_session = AsyncMock()
            mock_store_getter.return_value = mock_store

            # Mock graph with tool usage
            mock_compiled = AsyncMock()

            async def mock_stream(*args, **kwargs):
                yield {"event": "on_tool_start", "name": "search_knowledge", "data": {}}
                yield {"event": "on_tool_end", "name": "search_knowledge", "data": {}}

                class MockMessage:
                    def __init__(self):
                        self.content = [{"type": "text", "text": "Found some info!"}]

                yield {
                    "event": "on_chain_end",
                    "name": "supervisor",
                    "data": {"output": {"messages": [MockMessage()]}}
                }

            mock_compiled.astream_events = mock_stream
            mock_graph.return_value = mock_compiled

            supervisor_service._load_user_context_from_external = AsyncMock(
                return_value=UserContext(user_id=mock_user_id)
            )

            await supervisor_service.process_message(thread_id="thread-1", text="Search for info")

            # Check tool events were emitted
            tool_starts = [
                call for call in mock_q.put.call_args_list
                if call[0][0].get("event") == "tool.start"
            ]
            tool_ends = [
                call for call in mock_q.put.call_args_list
                if call[0][0].get("event") == "tool.end"
            ]

            assert len(tool_starts) > 0
            assert len(tool_ends) > 0

    @pytest.mark.asyncio
    async def test_process_message_exports_context_after_completion(self, supervisor_service, mock_user_id):
        """Should export user context to external API after processing."""
        with (
            patch("app.services.supervisor.get_sse_queue") as mock_queue,
            patch("app.services.supervisor.get_session_store") as mock_store_getter,
            patch("app.services.supervisor.get_supervisor_graph") as mock_graph,
        ):
            mock_q = AsyncMock()
            mock_queue.return_value = mock_q

            mock_store = AsyncMock()
            user_context = UserContext(user_id=mock_user_id, preferred_name="Test User")
            session_data = {
                "user_id": str(mock_user_id),
                "user_context": user_context.model_dump(mode="json"),
                "conversation_messages": [],
            }
            mock_store.get_session.return_value = session_data
            mock_store.set_session = AsyncMock()
            mock_store_getter.return_value = mock_store

            # Mock graph
            mock_compiled = AsyncMock()

            async def mock_stream(*args, **kwargs):
                class MockMessage:
                    def __init__(self):
                        self.content = [{"type": "text", "text": "Response"}]

                yield {
                    "event": "on_chain_end",
                    "name": "supervisor",
                    "data": {"output": {"messages": [MockMessage()]}}
                }

            mock_compiled.astream_events = mock_stream
            mock_graph.return_value = mock_compiled

            supervisor_service._load_user_context_from_external = AsyncMock(
                return_value=user_context
            )
            supervisor_service._export_user_context_to_external = AsyncMock()

            await supervisor_service.process_message(thread_id="thread-1", text="Hello")

            # Verify export was called
            supervisor_service._export_user_context_to_external.assert_awaited_once()
            exported_ctx = supervisor_service._export_user_context_to_external.call_args[0][0]
            assert exported_ctx.user_id == mock_user_id
            assert exported_ctx.preferred_name == "Test User"


class TestAddSourceFromToolEnd:
    """Tests for _add_source_from_tool_end method."""

    def test_add_source_extracts_from_tool_output_with_source_field(self, supervisor_service):
        """Should extract sources from tool output with 'source' field."""
        sources = []
        data = {
            "output": {
                "content": [
                    {
                        "source": "https://example.com/doc1",
                        "metadata": {"name": "Document 1", "type": "pdf"}
                    },
                    {
                        "source": "https://example.com/doc2",
                        "metadata": {"name": "Document 2"}
                    }
                ]
            }
        }

        result = supervisor_service._add_source_from_tool_end(
            sources, "search_knowledge", data, None
        )

        assert len(result) == 2
        assert result[0]["url"] == "https://example.com/doc1"
        assert result[0]["source_name"] == "Document 1"
        assert result[0]["type"] == "pdf"
        assert result[1]["url"] == "https://example.com/doc2"

    def test_add_source_handles_string_content(self, supervisor_service):
        """Should handle tool output with plain string URL."""
        sources = []
        data = {
            "output": {
                "content": "https://example.com/page"
            }
        }

        result = supervisor_service._add_source_from_tool_end(
            sources, "web_search", data, None
        )

        assert len(result) == 1
        assert result[0]["url"] == "https://example.com/page"

    def test_add_source_handles_no_output(self, supervisor_service):
        """Should handle tool data with no output."""
        sources = [{"url": "https://existing.com"}]
        data = {}

        result = supervisor_service._add_source_from_tool_end(
            sources, "some_tool", data, None
        )

        assert len(result) == 1
        assert result[0]["url"] == "https://existing.com"

    def test_add_source_skips_finance_agent_sources(self, supervisor_service):
        """Should skip sources when current agent is finance_agent."""
        sources = []
        data = {
            "output": {
                "content": [{"source": "https://example.com"}]
            }
        }

        result = supervisor_service._add_source_from_tool_end(
            sources, "tool", data, "transfer_to_finance_agent"
        )

        assert len(result) == 0

    def test_add_source_skips_goal_agent_sources(self, supervisor_service):
        """Should skip sources when current agent is goal_agent."""
        sources = []
        data = {
            "output": {
                "content": [{"source": "https://example.com"}]
            }
        }

        result = supervisor_service._add_source_from_tool_end(
            sources, "tool", data, "transfer_to_goal_agent"
        )

        assert len(result) == 0

    def test_add_source_skips_search_kb_tool(self, supervisor_service):
        """Should skip sources from search_kb tool."""
        sources = []
        data = {
            "output": {
                "content": [{"source": "https://example.com"}]
            }
        }

        result = supervisor_service._add_source_from_tool_end(
            sources, "search_kb", data, None
        )

        assert len(result) == 0

    def test_add_source_handles_dict_with_source(self, supervisor_service):
        """Should handle single dict with source field."""
        sources = []
        data = {
            "output": {
                "content": {
                    "source": "https://example.com/article",
                    "metadata": {"name": "Article Title"}
                }
            }
        }

        result = supervisor_service._add_source_from_tool_end(
            sources, "fetch_article", data, None
        )

        assert len(result) == 1
        assert result[0]["url"] == "https://example.com/article"
        assert result[0]["source_name"] == "Article Title"

    def test_add_source_skips_invalid_items(self, supervisor_service):
        """Should skip items without 'source' field or with invalid source."""
        sources = []
        data = {
            "output": {
                "content": [
                    {"source": "https://valid.com"},
                    {"no_source": "invalid"},
                    {"source": ""},  # empty source
                    {"source": None},  # null source
                ]
            }
        }

        result = supervisor_service._add_source_from_tool_end(
            sources, "tool", data, None
        )

        # Only the first valid source should be added
        assert len(result) == 1
        assert result[0]["url"] == "https://valid.com"
