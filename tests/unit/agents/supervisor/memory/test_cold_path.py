"""
Unit tests for app.agents.supervisor.memory.cold_path module.

Tests cover:
- _trigger_decide function
- _search_neighbors function
- _do_update and _do_recreate functions
- _same_fact_classify function
- _compose_summaries and _compose_display_summaries
- _normalize_summary_text
- _derive_nudge_metadata
- _sanitize_semantic_time_phrases
- _has_min_token_overlap and _numeric_overlap_or_step
- run_semantic_memory_job
- run_episodic_memory_job
- _emit_sse_safe
"""

from unittest.mock import MagicMock, patch

from app.agents.supervisor.memory.cold_path import (
    _compose_display_summaries,
    _compose_summaries,
    _derive_nudge_metadata,
    _do_recreate,
    _do_update,
    _emit_sse_safe,
    _has_min_token_overlap,
    _normalize_summary_text,
    _numeric_overlap_or_step,
    _same_fact_classify,
    _sanitize_semantic_time_phrases,
    _search_neighbors,
    _trigger_decide,
    run_episodic_memory_job,
    run_semantic_memory_job,
)


class TestTriggerDecide:
    """Test _trigger_decide function."""

    @patch("app.agents.supervisor.memory.cold_path.get_bedrock_runtime_client")
    @patch("app.agents.supervisor.memory.cold_path.prompt_loader")
    def test_trigger_decide_successful_response(self, mock_prompt_loader, mock_get_client):
        """Test successful decision response from Bedrock."""
        mock_client = MagicMock()
        mock_response = {"body": MagicMock()}
        mock_response["body"].read.return_value = b'{"output": {"message": {"content": [{"text": "{\\"should_create\\": true, \\"type\\": \\"semantic\\", \\"category\\": \\"Personal\\", \\"summary\\": \\"User likes coffee.\\", \\"importance\\": 3}"}]}}}'
        mock_client.invoke_model.return_value = mock_response
        mock_get_client.return_value = mock_client
        mock_prompt_loader.load.return_value = "Test prompt"

        result = _trigger_decide("I love coffee")

        assert result["should_create"] is True
        assert result["type"] == "semantic"
        assert result["category"] == "Personal"
        mock_client.invoke_model.assert_called_once()

    @patch("app.agents.supervisor.memory.cold_path.get_bedrock_runtime_client")
    @patch("app.agents.supervisor.memory.cold_path.prompt_loader")
    def test_trigger_decide_empty_response(self, mock_prompt_loader, mock_get_client):
        """Test handling of empty response."""
        mock_client = MagicMock()
        mock_response = {"body": MagicMock()}
        mock_response["body"].read.return_value = b'{"output": {"message": {"content": []}}, "outputText": "", "generation": ""}'
        mock_client.invoke_model.return_value = mock_response
        mock_get_client.return_value = mock_client
        mock_prompt_loader.load.return_value = "Test prompt"

        result = _trigger_decide("Test text")

        assert result == {"should_create": False}

    @patch("app.agents.supervisor.memory.cold_path.get_bedrock_runtime_client")
    @patch("app.agents.supervisor.memory.cold_path.prompt_loader")
    def test_trigger_decide_json_decode_error(self, mock_prompt_loader, mock_get_client):
        """Test handling of invalid JSON response."""
        mock_client = MagicMock()
        mock_response = {"body": MagicMock()}
        mock_response["body"].read.return_value = b'{"outputText": "invalid json"}'
        mock_client.invoke_model.return_value = mock_response
        mock_get_client.return_value = mock_client
        mock_prompt_loader.load.return_value = "Test prompt"

        result = _trigger_decide("Test text")

        assert result == {"should_create": False}



class TestSearchNeighbors:
    """Test _search_neighbors function."""

    def test_search_neighbors_with_results(self):
        """Test neighbor search with matching results."""
        mock_store = MagicMock()
        mock_memory1 = MagicMock()
        mock_memory1.value = {"summary": "User likes coffee", "category": "Personal"}
        mock_memory2 = MagicMock()
        mock_memory2.value = {"summary": "User prefers tea", "category": "Personal"}

        mock_store.search.return_value = [mock_memory1, mock_memory2]

        result = _search_neighbors(
            mock_store,
            ("user", "semantic"),
            "User enjoys beverages",
            "Personal",
        )

        assert len(result) == 2
        mock_store.search.assert_called_once()

    def test_search_neighbors_empty_results(self):
        """Test neighbor search with no results."""
        mock_store = MagicMock()
        mock_store.search.return_value = []

        result = _search_neighbors(
            mock_store,
            ("user", "semantic"),
            "Test summary",
            "Personal",
        )

        assert result == []

    def test_search_neighbors_exception_handling(self):
        """Test neighbor search handles exceptions."""
        mock_store = MagicMock()
        mock_store.search.side_effect = Exception("Search error")

        result = _search_neighbors(
            mock_store,
            ("user", "semantic"),
            "Test summary",
            "Personal",
        )

        assert result == []


class TestDoUpdate:
    """Test _do_update function."""

    def test_do_update_with_existing_item(self):
        """Test updating existing memory item."""
        mock_store = MagicMock()
        existing_item = MagicMock()
        existing_item.value = {
            "summary": "Old summary",
            "display_summary": "Old display",
            "last_accessed": None,
        }

        with patch("app.agents.supervisor.memory.cold_path._utc_now_iso") as mock_utc_now:
            mock_utc_now.return_value = "2024-01-01T00:00:00Z"
            
            _do_update(
                mock_store,
                ("user", "semantic"),
                "key-123",
                "New longer summary text",
                existing_item=existing_item,
                candidate_value={"display_summary": "New display"},
            )

            mock_store.put.assert_called_once()
            call_args = mock_store.put.call_args
            assert call_args[0][2]["summary"] == "New longer summary text"
            assert call_args[0][2]["display_summary"] == "New display"

    def test_do_update_without_existing_item(self):
        """Test updating when existing item is fetched from store."""
        mock_store = MagicMock()
        existing_item = MagicMock()
        existing_item.value = {"summary": "Old summary"}
        mock_store.get.return_value = existing_item

        _do_update(
            mock_store,
            ("user", "semantic"),
            "key-123",
            "New summary",
        )

        mock_store.get.assert_called_once()
        mock_store.put.assert_called_once()


class TestDoRecreate:
    """Test _do_recreate function."""

    def test_do_recreate_merges_values(self):
        """Test recreating memory with merged values."""
        mock_store = MagicMock()
        existing_item = MagicMock()
        existing_item.value = {
            "summary": "Old summary",
            "importance": 2,
            "pinned": False,
            "tags": ["tag1"],
            "created_at": "2024-01-01T00:00:00Z",
        }

        candidate_value = {
            "id": "new-id",
            "summary": "New summary",
            "importance": 3,
            "pinned": True,
            "tags": ["tag2"],
            "display_summary": "New display",
        }

        with patch("app.agents.supervisor.memory.cold_path._compose_summaries") as mock_compose:
            mock_compose.return_value = "Composed summary"

            new_id = _do_recreate(
                mock_store,
                ("user", "semantic"),
                "old-key",
                existing_item,
                "New summary",
                "Personal",
                candidate_value,
            )

            assert new_id is not None
            mock_store.put.assert_called_once()
            mock_store.delete.assert_called_once()
            call_args = mock_store.put.call_args
            assert call_args[0][2]["importance"] == 3  # Max of existing and candidate
            assert call_args[0][2]["pinned"] is True


class TestSameFactClassify:
    """Test _same_fact_classify function."""

    @patch("app.agents.supervisor.memory.cold_path.get_bedrock_runtime_client")
    @patch("app.agents.supervisor.memory.cold_path.prompt_loader")
    def test_same_fact_classify_true(self, mock_prompt_loader, mock_get_client):
        """Test classification returns True for same facts."""
        mock_client = MagicMock()
        mock_response = {"body": MagicMock()}
        mock_response["body"].read.return_value = b'{"output": {"message": {"content": [{"text": "{\\"same_fact\\": true}"}]}}}'
        mock_client.invoke_model.return_value = mock_response
        mock_get_client.return_value = mock_client
        mock_prompt_loader.load.return_value = "Test prompt"

        result = _same_fact_classify("User likes coffee", "User likes coffee", "Personal")

        assert result is True

    @patch("app.agents.supervisor.memory.cold_path.get_bedrock_runtime_client")
    @patch("app.agents.supervisor.memory.cold_path.prompt_loader")
    def test_same_fact_classify_false(self, mock_prompt_loader, mock_get_client):
        """Test classification returns False for different facts."""
        mock_client = MagicMock()
        mock_response = {"body": MagicMock()}
        mock_response["body"].read.return_value = b'{"output": {"message": {"content": [{"text": "{\\"same_fact\\": false}"}]}}}'
        mock_client.invoke_model.return_value = mock_response
        mock_get_client.return_value = mock_client
        mock_prompt_loader.load.return_value = "Test prompt"

        result = _same_fact_classify("User likes coffee", "User likes tea", "Personal")

        assert result is False

    @patch("app.agents.supervisor.memory.cold_path.get_bedrock_runtime_client")
    @patch("app.agents.supervisor.memory.cold_path.prompt_loader")
    @patch("app.agents.supervisor.memory.cold_path.logger")
    def test_same_fact_classify_exception(self, mock_logger, mock_prompt_loader, mock_get_client):
        """Test classification handles exceptions."""
        from botocore.exceptions import BotoCoreError
        
        mock_get_client.side_effect = BotoCoreError()
        mock_prompt_loader.load.return_value = "Test prompt"

        result = _same_fact_classify("User likes coffee", "User likes tea", "Personal")

        assert result is False


class TestComposeSummaries:
    """Test _compose_summaries function."""

    @patch("app.agents.supervisor.memory.cold_path.get_bedrock_runtime_client")
    @patch("app.agents.supervisor.memory.cold_path.prompt_loader")
    def test_compose_summaries_success(self, mock_prompt_loader, mock_get_client):
        """Test successful summary composition."""
        mock_client = MagicMock()
        mock_response = {"body": MagicMock()}
        mock_response["body"].read.return_value = b'{"output": {"message": {"content": [{"text": "Composed summary text"}]}}}'
        mock_client.invoke_model.return_value = mock_response
        mock_get_client.return_value = mock_client
        mock_prompt_loader.load.return_value = "Test prompt"

        result = _compose_summaries("Old summary", "New summary", "Personal")

        assert result == "Composed summary text"
        mock_client.invoke_model.assert_called_once()

    @patch("app.agents.supervisor.memory.cold_path.get_bedrock_runtime_client")
    @patch("app.agents.supervisor.memory.cold_path.prompt_loader")
    @patch("app.agents.supervisor.memory.cold_path.logger")
    def test_compose_summaries_fallback(self, mock_logger, mock_prompt_loader, mock_get_client):
        """Test fallback when LLM fails."""
        from botocore.exceptions import BotoCoreError
        
        mock_get_client.side_effect = BotoCoreError()
        mock_prompt_loader.load.return_value = "Test prompt"

        result = _compose_summaries("Old summary", "New summary", "Personal")

        assert result is not None
        assert len(result) <= 280
        assert "Old summary" in result or "New summary" in result


class TestComposeDisplaySummaries:
    """Test _compose_display_summaries function."""

    def test_compose_display_summaries_both_present(self):
        """Test composing when both summaries exist."""
        result = _compose_display_summaries("Short", "Longer display summary")

        assert result == "Longer display summary"
        assert len(result) <= 280

    def test_compose_display_summaries_one_empty(self):
        """Test composing when one summary is empty."""
        result = _compose_display_summaries("", "Display summary")
        assert result == "Display summary"

        result = _compose_display_summaries("Display summary", "")
        assert result == "Display summary"

    def test_compose_display_summaries_containment(self):
        """Test that longer summary is preferred."""
        result = _compose_display_summaries("Short", "This is a longer display summary")
        assert result == "This is a longer display summary"


class TestNormalizeSummaryText:
    """Test _normalize_summary_text function."""

    def test_normalize_summary_text_basic(self):
        """Test basic text normalization."""
        result = _normalize_summary_text("User likes coffee")
        assert result == "User likes coffee"

    def test_normalize_summary_text_unicode(self):
        """Test unicode normalization."""
        result = _normalize_summary_text("User's café")
        assert isinstance(result, str)

    def test_normalize_summary_text_non_string(self):
        """Test handling of non-string input."""
        result = _normalize_summary_text(None)
        assert result == ""

        result = _normalize_summary_text(123)
        assert result == ""


class TestDeriveNudgeMetadata:
    """Test _derive_nudge_metadata function."""

    def test_derive_nudge_metadata_personal(self):
        """Test metadata for Personal category."""
        result = _derive_nudge_metadata("Personal", "User info", 3)
        assert result["topic_key"] == "personal_info"
        assert result["importance_bin"] == "med"

    def test_derive_nudge_metadata_finance(self):
        """Test metadata for Finance category."""
        result = _derive_nudge_metadata("Finance", "User has subscription", 4)
        assert result["topic_key"] == "subscription"
        assert result["importance_bin"] == "high"

    def test_derive_nudge_metadata_importance_bins(self):
        """Test importance binning."""
        result_high = _derive_nudge_metadata("Personal", "Test", 4)
        assert result_high["importance_bin"] == "high"

        result_med = _derive_nudge_metadata("Personal", "Test", 2)
        assert result_med["importance_bin"] == "med"

        result_low = _derive_nudge_metadata("Personal", "Test", 1)
        assert result_low["importance_bin"] == "low"


class TestSanitizeSemanticTimePhrases:
    """Test _sanitize_semantic_time_phrases function."""

    def test_sanitize_semantic_time_phrases_today(self):
        """Test removal of 'today' phrases."""
        result = _sanitize_semantic_time_phrases("User went to the store today")
        assert "today" not in result.lower()

    def test_sanitize_semantic_time_phrases_yesterday(self):
        """Test removal of 'yesterday' phrases."""
        result = _sanitize_semantic_time_phrases("User worked yesterday")
        assert "yesterday" not in result.lower()

    def test_sanitize_semantic_time_phrases_non_string(self):
        """Test handling of non-string input."""
        result = _sanitize_semantic_time_phrases(None)
        assert result == ""


class TestHasMinTokenOverlap:
    """Test _has_min_token_overlap function."""

    def test_has_min_token_overlap_sufficient(self):
        """Test with sufficient token overlap."""
        result = _has_min_token_overlap("User likes coffee", "User enjoys coffee")
        assert isinstance(result, bool)

    def test_has_min_token_overlap_insufficient(self):
        """Test with insufficient token overlap."""
        result = _has_min_token_overlap("User likes coffee", "Weather is nice")
        assert isinstance(result, bool)


class TestNumericOverlapOrStep:
    """Test _numeric_overlap_or_step function."""

    def test_numeric_overlap_or_step_same_number(self):
        """Test with same numbers."""
        result = _numeric_overlap_or_step("User is 25 years old", "User's age is 25")
        assert result is True

    def test_numeric_overlap_or_step_different_numbers(self):
        """Test with different numbers."""
        result = _numeric_overlap_or_step("User is 25 years old", "User is 30 years old")
        assert result is False

    def test_numeric_overlap_or_step_consecutive(self):
        """Test with consecutive numbers."""
        result = _numeric_overlap_or_step("User has 2 cats", "User has 3 cats")
        assert result is True


class TestEmitSseSafe:
    """Test _emit_sse_safe function."""

    def test_emit_sse_safe_success(self):
        """Test successful SSE emission."""
        mock_event_loop = MagicMock()
        mock_queue = MagicMock()
        mock_future = MagicMock()

        with patch("app.agents.supervisor.memory.cold_path.get_sse_queue", return_value=mock_queue), \
             patch("app.agents.supervisor.memory.cold_path.asyncio.run_coroutine_threadsafe", return_value=mock_future):

            _emit_sse_safe(mock_event_loop, "thread-123", "memory.created", {"id": "mem-123"})

            assert mock_queue.put.call_count == 1
            mock_future.result.assert_not_called()

    def test_emit_sse_safe_error_handling(self):
        """Test SSE emission error handling."""
        mock_event_loop = MagicMock()

        with patch("app.agents.supervisor.memory.cold_path.get_sse_queue", side_effect=Exception("Queue error")), \
             patch("app.agents.supervisor.memory.cold_path.logger") as mock_logger:

            _emit_sse_safe(mock_event_loop, "thread-123", "memory.created", {"id": "mem-123"})

            mock_logger.warning.assert_called_once()


class TestRunSemanticMemoryJob:
    """Test run_semantic_memory_job function."""

    def test_run_semantic_memory_job_no_recent_texts(self):
        """Test job skips when no recent user texts."""
        mock_event_loop = MagicMock()

        run_semantic_memory_job(
            user_id="user-123",
            thread_id="thread-123",
            user_context={},
            conversation_window=[],
            event_loop=mock_event_loop,
            store=MagicMock(),
        )

        # Should complete without error

    def test_run_semantic_memory_job_should_create_false(self):
        """Test job skips when should_create is False."""
        mock_event_loop = MagicMock()

        with patch("app.agents.supervisor.memory.cold_path._trigger_decide") as mock_decide:
            mock_decide.return_value = {"should_create": False}

            run_semantic_memory_job(
                user_id="user-123",
                thread_id="thread-123",
                user_context={},
                conversation_window=[{"role": "user", "content": "Hello"}],
                event_loop=mock_event_loop,
                store=MagicMock(),
            )

            mock_decide.assert_called_once()

    def test_run_semantic_memory_job_creates_memory(self):
        """Test job creates memory when conditions are met."""
        mock_event_loop = MagicMock()
        user_id = "user-123"
        thread_id = "thread-123"

        with patch("app.agents.supervisor.memory.cold_path._trigger_decide") as mock_decide, \
             patch("app.agents.supervisor.memory.cold_path.memory_service") as mock_memory_service, \
             patch("app.agents.supervisor.memory.cold_path._emit_sse_safe") as mock_emit_sse, \
             patch("app.agents.supervisor.memory.cold_path._profile_sync_from_memory_sync"), \
             patch("asyncio.run_coroutine_threadsafe") as mock_run_coro:

            mock_decide.return_value = {
                "should_create": True,
                "type": "semantic",
                "category": "Personal",
                "summary": "User likes coffee",
                "importance": 3,
            }

            mock_store = MagicMock()
            mock_store.search.return_value = []
            store = mock_store

            mock_future = MagicMock()
            mock_future.result.return_value = {"ok": True}
            mock_run_coro.return_value = mock_future

            run_semantic_memory_job(
                user_id=user_id,
                thread_id=thread_id,
                user_context={},
                conversation_window=[{"role": "user", "content": "I like coffee"}],
                event_loop=mock_event_loop,
                store=store,
            )

            mock_decide.assert_called_once()
            mock_store.search.assert_called_once()
            mock_run_coro.assert_called_once()
            mock_emit_sse.assert_called_once()


class TestRunEpisodicMemoryJob:
    """Test run_episodic_memory_job function."""

    def test_run_episodic_memory_job_skips_cooldown(self):
        """Test job skips when cooldown conditions are met."""
        mock_event_loop = MagicMock()
        thread_id = "thread-123"

        with patch("app.agents.supervisor.memory.cold_path._load_session_store_and_ctrl_sync") as mock_load_session, \
             patch("app.agents.supervisor.memory.cold_path._update_ctrl_for_new_turn") as mock_update_ctrl, \
             patch("app.agents.supervisor.memory.cold_path._should_skip_capture") as mock_should_skip, \
             patch("app.agents.supervisor.memory.cold_path._persist_session_ctrl_sync") as mock_persist, \
             patch("app.agents.supervisor.memory.cold_path.get_session_store"):

            mock_session_store = MagicMock()
            mock_sess = {}
            mock_ctrl = {"turns_since_last": 0}
            mock_load_session.return_value = (mock_session_store, mock_sess, mock_ctrl)
            mock_update_ctrl.return_value = mock_ctrl
            mock_should_skip.return_value = True

            run_episodic_memory_job(
                user_id="user-123",
                thread_id=thread_id,
                user_context={},
                conversation_window=[{"role": "user", "content": "Hello"}],
                event_loop=mock_event_loop,
                store=MagicMock(),
            )

            mock_should_skip.assert_called_once()
            mock_persist.assert_called_once()

    def test_run_episodic_memory_job_creates_memory(self):
        """Test job creates episodic memory when conditions are met."""
        mock_event_loop = MagicMock()
        user_id = "user-123"
        thread_id = "thread-123"

        with patch("app.agents.supervisor.memory.cold_path._load_session_store_and_ctrl_sync") as mock_load_session, \
             patch("app.agents.supervisor.memory.cold_path._update_ctrl_for_new_turn") as mock_update_ctrl, \
             patch("app.agents.supervisor.memory.cold_path._should_skip_capture") as mock_should_skip, \
             patch("app.agents.supervisor.memory.cold_path._summarize_with_bedrock") as mock_summarize, \
             patch("app.agents.supervisor.memory.cold_path._build_human_summary") as mock_build_summary, \
             patch("app.agents.supervisor.memory.cold_path._get_neighbors") as mock_get_neighbors, \
             patch("app.agents.supervisor.memory.cold_path._create_memory_sync") as mock_create_memory, \
             patch("app.agents.supervisor.memory.cold_path._emit_memory_event_sync") as mock_emit_event, \
             patch("app.agents.supervisor.memory.cold_path._persist_session_ctrl_sync") as mock_persist, \
             patch("app.agents.supervisor.memory.cold_path._create_episodic_value") as mock_create_value, \
             patch("app.agents.supervisor.memory.cold_path._reset_ctrl_after_capture") as mock_reset_ctrl:

            mock_session_store = MagicMock()
            mock_sess = {}
            mock_ctrl = {"turns_since_last": 10}
            mock_load_session.return_value = (mock_session_store, mock_sess, mock_ctrl)
            mock_update_ctrl.return_value = mock_ctrl
            mock_should_skip.return_value = False
            mock_summarize.return_value = ("Summary text", "Conversation_Summary", 2)
            mock_build_summary.return_value = "On 2024-01-01 Summary text"
            mock_get_neighbors.return_value = []
            mock_create_value.return_value = {"id": "mem-123", "summary": "Summary text"}
            mock_reset_ctrl.return_value = mock_ctrl
            
            mock_store = MagicMock()
            store = mock_store

            run_episodic_memory_job(
                user_id=user_id,
                thread_id=thread_id,
                user_context={},
                conversation_window=[
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there"},
                ],
                event_loop=mock_event_loop,
                store=store,
            )

            mock_summarize.assert_called_once()
            mock_create_memory.assert_called_once()
            mock_emit_event.assert_called_once()
            mock_persist.assert_called_once()

