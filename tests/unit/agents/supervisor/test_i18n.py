import pytest

from app.agents.supervisor.i18n import (
    _get_random_budget_completed,
    _get_random_budget_current,
    _get_random_finance_completed,
    _get_random_finance_current,
    _get_random_step_planning_completed,
    _get_random_step_planning_current,
    _get_random_wealth_completed,
    _get_random_wealth_current,
)


@pytest.mark.unit
class TestI18nRandomMessages:

    def test_get_random_step_planning_current(self):
        """Test step_planning_current returns valid string from expected options."""
        expected_options = [
            "Just a sec, I'm thinking...",
            "Let me think this through...",
            "Let me figure out the best approach...",
        ]
        result = _get_random_step_planning_current()
        assert isinstance(result, str)
        assert len(result) > 0
        assert result in expected_options

    def test_get_random_step_planning_completed(self):
        """Test step_planning_completed returns valid string from expected options."""
        expected_options = [
            "All done here!",
            "That's everything for now",
            "Response complete",
        ]
        result = _get_random_step_planning_completed()
        assert isinstance(result, str)
        assert len(result) > 0
        assert result in expected_options

    def test_get_random_finance_current(self):
        """Test finance_current returns valid string from expected options."""
        expected_options = [
            "Diving into your financial information...",
            "Taking a quick look at your finances...",
            "Analyzing your financial info...",
        ]
        result = _get_random_finance_current()
        assert isinstance(result, str)
        assert len(result) > 0
        assert result in expected_options

    def test_get_random_finance_completed(self):
        """Test finance_completed returns valid string from expected options."""
        expected_options = [
            "Done, I've scanned your finances.",
            "All set, financial statements checked!",
            "Financial analysis complete!",
        ]
        result = _get_random_finance_completed()
        assert isinstance(result, str)
        assert len(result) > 0
        assert result in expected_options

    def test_get_random_budget_current(self):
        """Test budget_current returns valid string from expected options."""
        expected_options = [
            "Reviewing your goals...",
            "Checking progress on your goals...",
            "Analyzing your goals to see the path ahead...",
        ]
        result = _get_random_budget_current()
        assert isinstance(result, str)
        assert len(result) > 0
        assert result in expected_options

    def test_get_random_budget_completed(self):
        """Test budget_completed returns valid string from expected options."""
        expected_options = [
            "Done, goals checked!",
            "All set, here's your goals update",
            "Finished! Your goals review is complete",
        ]
        result = _get_random_budget_completed()
        assert isinstance(result, str)
        assert len(result) > 0
        assert result in expected_options

    def test_get_random_wealth_current(self):
        """Test wealth_current returns valid string from expected options."""
        expected_options = [
            "Switching to guide mode for a sec...",
            "Switching to brainy mode...",
            "Activating coaching expertise...",
        ]
        result = _get_random_wealth_current()
        assert isinstance(result, str)
        assert len(result) > 0
        assert result in expected_options

    def test_get_random_wealth_completed(self):
        """Test wealth_completed returns valid string from expected options."""
        expected_options = [
            "Done, here's a clear explanation",
            "All set, here's the wisdom straight up",
            "All set, here's the insight you need!",
        ]
        result = _get_random_wealth_completed()
        assert isinstance(result, str)
        assert len(result) > 0
        assert result in expected_options

    def test_randomness_step_planning_current(self):
        results = {_get_random_step_planning_current() for _ in range(50)}
        assert len(results) >= 2

    def test_randomness_finance_current(self):
        results = {_get_random_finance_current() for _ in range(50)}
        assert len(results) >= 2

    def test_randomness_budget_current(self):
        results = {_get_random_budget_current() for _ in range(50)}
        assert len(results) >= 2

    def test_randomness_wealth_current(self):
        results = {_get_random_wealth_current() for _ in range(50)}
        assert len(results) >= 2

    def test_all_functions_return_non_empty_strings(self):
        functions = [
            _get_random_step_planning_current,
            _get_random_step_planning_completed,
            _get_random_finance_current,
            _get_random_finance_completed,
            _get_random_budget_current,
            _get_random_budget_completed,
            _get_random_wealth_current,
            _get_random_wealth_completed,
        ]

        for func in functions:
            result = func()
            assert isinstance(result, str), f"{func.__name__} should return a string"
            assert len(result) > 0, f"{func.__name__} should return a non-empty string"
            assert result.strip() == result, f"{func.__name__} should not have leading/trailing whitespace"
