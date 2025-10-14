from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from app.models.nudge import NudgeChannel
from app.services.nudges.evaluator import (
    NudgeEvaluator,
    get_nudge_evaluator,
    iter_active_users,
)
from app.services.nudges.models import NudgeCandidate


@pytest.fixture
def mock_managers():
    with patch("app.services.nudges.evaluator.get_sqs_manager") as sqs, \
         patch("app.services.nudges.evaluator.get_fos_nudge_manager") as fos, \
         patch("app.services.nudges.evaluator.get_activity_counter") as counter, \
         patch("app.services.nudges.evaluator.get_strategy_registry") as registry:
        yield {
            "sqs": sqs.return_value,
            "fos": fos.return_value,
            "counter": counter.return_value,
            "registry": registry.return_value,
        }


@pytest.fixture
def evaluator(mock_managers):
    return NudgeEvaluator()


@pytest.fixture
def mock_strategy():
    strategy = AsyncMock()
    strategy.__class__.__name__ = "MockStrategy"
    strategy.validate_conditions.return_value = True
    return strategy


@pytest.fixture
def mock_candidate():
    return NudgeCandidate(
        user_id=uuid4(),
        nudge_type="test_nudge",
        priority=5,
        notification_text="Test notification",
        preview_text="Test preview",
        metadata={"key": "value"}
    )


class TestNudgeEvaluator:
    @pytest.mark.asyncio
    async def test_evaluate_nudges_batch_success(self, evaluator, mock_managers, mock_strategy, mock_candidate):
        user_ids = [str(uuid4()), str(uuid4())]

        mock_managers["registry"].get_strategy.return_value = mock_strategy
        mock_strategy.evaluate.return_value = mock_candidate
        mock_managers["sqs"].enqueue_nudge = AsyncMock(return_value="msg-123")
        mock_managers["counter"].increment_nudge_count = AsyncMock()

        result = await evaluator.evaluate_nudges_batch(user_ids, "test_nudge")

        assert result["evaluated"] == 2
        assert result["queued"] == 2
        assert result["skipped"] == 0
        assert len(result["results"]) == 2

    @pytest.mark.asyncio
    async def test_evaluate_nudges_batch_unknown_nudge_type(self, evaluator, mock_managers):
        user_ids = [str(uuid4())]

        mock_managers["registry"].get_strategy.return_value = None
        mock_managers["registry"].list_available_strategies.return_value = ["nudge1", "nudge2"]

        result = await evaluator.evaluate_nudges_batch(user_ids, "invalid_type")

        assert result["evaluated"] == 0
        assert result["queued"] == 0
        assert result["skipped"] == 1
        assert "Unknown nudge type" in result["error"]

    @pytest.mark.asyncio
    async def test_evaluate_nudges_batch_strategy_conditions_fail(self, evaluator, mock_managers, mock_strategy):
        user_ids = [str(uuid4())]

        mock_managers["registry"].get_strategy.return_value = mock_strategy
        mock_strategy.validate_conditions.return_value = False

        result = await evaluator.evaluate_nudges_batch(user_ids, "test_nudge")

        assert result["evaluated"] == 1
        assert result["queued"] == 0
        assert result["skipped"] == 1
        assert result["results"][0]["reason"] == "strategy_conditions_not_met"

    @pytest.mark.asyncio
    async def test_evaluate_nudges_batch_no_candidate(self, evaluator, mock_managers, mock_strategy):
        user_ids = [str(uuid4())]

        mock_managers["registry"].get_strategy.return_value = mock_strategy
        mock_strategy.evaluate.return_value = None

        result = await evaluator.evaluate_nudges_batch(user_ids, "test_nudge")

        assert result["evaluated"] == 1
        assert result["queued"] == 0
        assert result["skipped"] == 1
        assert result["results"][0]["reason"] == "no_candidate"

    @pytest.mark.asyncio
    async def test_evaluate_nudges_batch_calls_cleanup(self, evaluator, mock_managers, mock_strategy, mock_candidate):
        user_ids = [str(uuid4())]

        mock_managers["registry"].get_strategy.return_value = mock_strategy
        mock_strategy.evaluate.return_value = mock_candidate
        mock_strategy.cleanup = AsyncMock()
        mock_managers["sqs"].enqueue_nudge = AsyncMock(return_value="msg-123")
        mock_managers["counter"].increment_nudge_count = AsyncMock()

        await evaluator.evaluate_nudges_batch(user_ids, "test_nudge")

        mock_strategy.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_nudges_batch_handles_exception(self, evaluator, mock_managers, mock_strategy):
        user_ids = [str(uuid4())]

        mock_managers["registry"].get_strategy.return_value = mock_strategy
        mock_strategy.evaluate.side_effect = Exception("Test error")

        result = await evaluator.evaluate_nudges_batch(user_ids, "test_nudge")

        assert result["evaluated"] == 1
        assert result["queued"] == 0
        assert result["skipped"] == 1
        assert result["results"][0]["status"] == "error"

    @pytest.mark.asyncio
    async def test_queue_nudge_memory_icebreaker(self, evaluator, mock_managers, mock_candidate):
        mock_candidate.nudge_type = "memory_icebreaker"
        mock_managers["fos"].enqueue_nudge = AsyncMock(return_value="fos-msg-123")
        mock_managers["counter"].increment_nudge_count = AsyncMock()

        message_id = await evaluator._queue_nudge(mock_candidate)

        assert message_id == "fos-msg-123"
        mock_managers["fos"].enqueue_nudge.assert_called_once()
        mock_managers["counter"].increment_nudge_count.assert_called_once_with(
            mock_candidate.user_id, mock_candidate.nudge_type
        )

    @pytest.mark.asyncio
    async def test_queue_nudge_push_notification(self, evaluator, mock_managers, mock_candidate):
        mock_candidate.nudge_type = "bill_reminder"
        mock_managers["sqs"].enqueue_nudge = AsyncMock(return_value="sqs-msg-456")
        mock_managers["counter"].increment_nudge_count = AsyncMock()

        message_id = await evaluator._queue_nudge(mock_candidate)

        assert message_id == "sqs-msg-456"
        mock_managers["sqs"].enqueue_nudge.assert_called_once()

    @pytest.mark.asyncio
    async def test_queue_nudge_creates_correct_message(self, evaluator, mock_managers, mock_candidate):
        mock_managers["sqs"].enqueue_nudge = AsyncMock(return_value="msg-123")
        mock_managers["counter"].increment_nudge_count = AsyncMock()

        await evaluator._queue_nudge(mock_candidate)

        call_args = mock_managers["sqs"].enqueue_nudge.call_args[0][0]
        assert str(call_args.user_id) == str(mock_candidate.user_id)
        assert call_args.nudge_type == mock_candidate.nudge_type
        assert call_args.priority == mock_candidate.priority
        assert call_args.channel == NudgeChannel.PUSH

    def test_register_custom_strategy(self, evaluator, mock_managers):
        mock_strategy_class = MagicMock()
        mock_strategy_class.__name__ = "CustomStrategy"

        evaluator.register_custom_strategy("custom_nudge", mock_strategy_class)

        mock_managers["registry"].register_strategy_class.assert_called_once_with(
            "custom_nudge", mock_strategy_class
        )


class TestGetNudgeEvaluator:
    @patch("app.services.nudges.evaluator.get_sqs_manager")
    @patch("app.services.nudges.evaluator.get_fos_nudge_manager")
    @patch("app.services.nudges.evaluator.get_activity_counter")
    @patch("app.services.nudges.evaluator.get_strategy_registry")
    def test_returns_singleton(self, mock_registry, mock_counter, mock_fos, mock_sqs):
        from app.services.nudges import evaluator as eval_module
        eval_module._nudge_evaluator = None

        evaluator1 = get_nudge_evaluator()
        evaluator2 = get_nudge_evaluator()

        assert evaluator1 is evaluator2


class TestIterActiveUsers:
    @pytest.mark.asyncio
    @patch("app.services.nudges.evaluator.httpx.AsyncClient")
    @patch("app.services.nudges.evaluator.config")
    async def test_yields_user_pages(self, mock_config, mock_client_class):
        mock_config.FOS_SERVICE_URL = "http://test.com"
        mock_config.FOS_API_KEY = "test-key"

        mock_response1 = MagicMock()
        mock_response1.json.return_value = [
            {"id": "user-1"}, {"id": "user-2"}
        ]

        mock_response2 = MagicMock()
        mock_response2.json.return_value = []

        mock_client = AsyncMock()
        mock_client.get.side_effect = [mock_response1, mock_response2]
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        pages = []
        async for page in iter_active_users(page_size=2, max_pages=5):
            pages.append(page)

        assert len(pages) == 1
        assert pages[0] == ["user-1", "user-2"]

    @pytest.mark.asyncio
    @patch("app.services.nudges.evaluator.config")
    async def test_raises_on_missing_url(self, mock_config):
        mock_config.FOS_SERVICE_URL = None

        with pytest.raises(ValueError, match="FOS_SERVICE_URL not configured"):
            async for _ in iter_active_users():
                pass

    @pytest.mark.asyncio
    @patch("app.services.nudges.evaluator.httpx.AsyncClient")
    @patch("app.services.nudges.evaluator.config")
    async def test_handles_dict_response_with_items(self, mock_config, mock_client_class):
        mock_config.FOS_SERVICE_URL = "http://test.com"
        mock_config.FOS_API_KEY = None
        mock_config.FOS_SECRETS_ID = None

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [{"user_id": "user-1"}]
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        pages = []
        async for page in iter_active_users(page_size=1, max_pages=1):
            pages.append(page)

        assert len(pages) == 1
        assert "user-1" in pages[0]

    @pytest.mark.asyncio
    @patch("app.services.nudges.evaluator.httpx.AsyncClient")
    @patch("app.services.nudges.evaluator.config")
    async def test_stops_at_max_pages(self, mock_config, mock_client_class):
        mock_config.FOS_SERVICE_URL = "http://test.com"
        mock_config.FOS_API_KEY = "test-key"

        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": f"user-{i}"} for i in range(10)]

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        pages = []
        async for page in iter_active_users(page_size=10, max_pages=2):
            pages.append(page)

        assert len(pages) == 2

    @pytest.mark.asyncio
    @patch("app.services.nudges.evaluator.httpx.AsyncClient")
    @patch("app.services.nudges.evaluator.config")
    async def test_handles_http_error(self, mock_config, mock_client_class):
        mock_config.FOS_SERVICE_URL = "http://test.com"
        mock_config.FOS_API_KEY = "test-key"
        mock_config.FOS_USERS_PAGE_SIZE = 100
        mock_config.FOS_USERS_MAX_PAGES = 10

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server error"

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response)
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            async for _ in iter_active_users():
                pass

    @pytest.mark.asyncio
    @patch("app.services.nudges.evaluator.httpx.AsyncClient")
    @patch("app.services.nudges.evaluator.config")
    async def test_extracts_id_from_various_fields(self, mock_config, mock_client_class):
        mock_config.FOS_SERVICE_URL = "http://test.com"
        mock_config.FOS_API_KEY = "test-key"

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "user-1"},
            {"user_id": "user-2"},
            {"clerk_user_id": "user-3"}
        ]

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        pages = []
        async for page in iter_active_users(page_size=10, max_pages=1):
            pages.append(page)

        assert len(pages[0]) == 3
        assert "user-1" in pages[0]
        assert "user-2" in pages[0]
        assert "user-3" in pages[0]
