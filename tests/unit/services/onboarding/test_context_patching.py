from unittest.mock import MagicMock

import pytest

from app.agents.onboarding.state import OnboardingState
from app.services.onboarding.context_patching import (
    ContextPatchingService,
    context_patching_service,
)


@pytest.fixture
def patching_service():
    return ContextPatchingService()


@pytest.fixture
def mock_state():
    state = MagicMock(spec=OnboardingState)
    state.user_context = MagicMock()
    state.user_context.age_range = None
    state.user_context.sync_nested_to_flat = MagicMock()
    state.user_context.model_dump = MagicMock(return_value={})
    return state


@pytest.fixture
def mock_step():
    step = MagicMock()
    step.value = "test_step"
    return step


class TestNormalizePatchForStep:
    def test_normalizes_warmup_fields(self, patching_service):
        patch = {"preferred_name": "Alice"}

        result = patching_service.normalize_patch_for_step("warmup", patch)

        assert result == {"identity.preferred_name": "Alice"}

    def test_normalizes_identity_fields(self, patching_service):
        patch = {"age": 25, "city": "San Francisco", "personal_goals": ["save money"]}

        result = patching_service.normalize_patch_for_step("identity", patch)

        assert result == {"age": 25, "location.city": "San Francisco", "goals": ["save money"]}

    def test_normalizes_income_money_fields(self, patching_service):
        patch = {"annual_income": 75000, "money_feelings": "stressed"}

        result = patching_service.normalize_patch_for_step("income_money", patch)

        assert result == {"income": 75000, "money_feelings": "stressed"}

    def test_passes_through_unmapped_fields(self, patching_service):
        patch = {"custom_field": "value", "age": 30}

        result = patching_service.normalize_patch_for_step("identity", patch)

        assert result["custom_field"] == "value"
        assert result["age"] == 30

    def test_returns_empty_for_non_dict_patch(self, patching_service):
        result = patching_service.normalize_patch_for_step("warmup", "not a dict")

        assert result == {}

    def test_handles_unknown_step(self, patching_service):
        patch = {"field": "value"}

        result = patching_service.normalize_patch_for_step("unknown_step", patch)

        assert result == {"field": "value"}


class TestApplyContextPatch:
    def test_applies_simple_field_patch(self, patching_service, mock_state, mock_step):
        patch = {"income": 50000}

        patching_service.apply_context_patch(mock_state, mock_step, patch)

        assert hasattr(mock_state.user_context, "income")
        mock_state.user_context.sync_nested_to_flat.assert_called_once()

    def test_applies_nested_field_patch(self, patching_service, mock_state, mock_step):
        mock_state.user_context.identity = MagicMock()
        mock_step.value = "warmup"
        patch = {"preferred_name": "Bob"}

        patching_service.apply_context_patch(mock_state, mock_step, patch)

        mock_state.user_context.sync_nested_to_flat.assert_called_once()

    def test_skips_age_inference_when_age_provided(self, patching_service, mock_state, mock_step):
        mock_state.last_user_message = "25-34"
        mock_state.user_context.age_range = None
        mock_step.value = "identity"
        patch = {"age": 28}

        patching_service.apply_context_patch(mock_state, mock_step, patch)

        assert mock_state.user_context.age_range is None

    def test_returns_early_for_empty_patch(self, patching_service, mock_state, mock_step):
        patching_service.apply_context_patch(mock_state, mock_step, {})

        mock_state.user_context.sync_nested_to_flat.assert_not_called()

    def test_handles_exceptions_gracefully(self, patching_service, mock_state, mock_step):
        mock_state.user_context.sync_nested_to_flat.side_effect = Exception("Sync error")
        patch = {"income": 50000}

        patching_service.apply_context_patch(mock_state, mock_step, patch)


class TestSetByPath:
    def test_sets_simple_nested_attribute(self, patching_service):
        obj = MagicMock()
        obj.location = MagicMock()

        patching_service._set_by_path(obj, "location.city", "Boston")

        assert obj.location.city == "Boston"

    def test_sets_deeply_nested_attribute(self, patching_service):
        obj = MagicMock()
        obj.level1 = MagicMock()
        obj.level1.level2 = MagicMock()

        patching_service._set_by_path(obj, "level1.level2.value", 42)

        assert obj.level1.level2.value == 42

    def test_converts_to_list_when_target_is_list(self, patching_service):
        obj = MagicMock()
        obj.items = []

        patching_service._set_by_path(obj, "items", "single_value")

        assert obj.items == ["single_value"]

    def test_handles_none_intermediate_object(self, patching_service):
        obj = MagicMock()
        obj.nested = None

        patching_service._set_by_path(obj, "nested.field", "value")

    def test_handles_missing_attribute(self, patching_service):
        obj = MagicMock()
        del obj.nonexistent
        type(obj).nonexistent = property(lambda self: (_ for _ in ()).throw(AttributeError))

        patching_service._set_by_path(obj, "nonexistent.field", "value")

    def test_handles_empty_path(self, patching_service):
        obj = MagicMock()

        patching_service._set_by_path(obj, "", "value")

    def test_handles_exception_on_setattr(self, patching_service):
        obj = MagicMock()
        obj.field = property(lambda self: None, lambda self, v: (_ for _ in ()).throw(Exception("Cannot set")))

        patching_service._set_by_path(obj, "field", "value")


class TestSingletonInstance:
    def test_context_patching_service_is_singleton(self):
        assert context_patching_service is not None
        assert isinstance(context_patching_service, ContextPatchingService)
