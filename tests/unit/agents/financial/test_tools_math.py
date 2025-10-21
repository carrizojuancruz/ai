"""Unit tests for Finance Agent math calculation tool."""

import pytest

from app.agents.supervisor.finance_agent.tools import create_calculate_tool


class TestCalculateTool:
    """Test the calculate tool for finance agent."""

    @pytest.fixture(autouse=True)
    def setup_calculate_tool(self):
        """Set up the calculate tool for all tests."""
        self.calculate = create_calculate_tool()

    def test_basic_calculation(self):
        """Test basic math calculation with result variable."""
        result = self.calculate.invoke("result = 100 * 1.05 ** 3")
        assert "115.76" in result

    def test_missing_result(self):
        """Test error when result variable is not assigned."""
        result = self.calculate.invoke("x = 100")
        assert "result" in result.lower()
        assert "error" in result.lower()

    def test_division_by_zero(self):
        """Test error handling for division by zero."""
        result = self.calculate.invoke("result = 100 / 0")
        assert "division by zero" in result.lower()

    def test_post_query_calculation(self):
        """Test realistic post-query calculation (months coverage)."""
        # Simulates: balance / burn_rate
        result = self.calculate.invoke("result = 15000 / 2500")
        assert "6" in result or "6.0" in result

    def test_fire_number_formula(self):
        """Test FIRE number calculation."""
        # FIRE number = (annual_expenses * 25) - current_investments
        result = self.calculate.invoke("result = (25000 * 25) - 150000")
        assert "475000" in result

    def test_percentage_calculation(self):
        """Test percentage calculation."""
        result = self.calculate.invoke("result = (3500 / 5000) * 100")
        assert "70" in result

    def test_compound_interest(self):
        """Test compound interest calculation."""
        result = self.calculate.invoke("result = 10000 * (1 + 0.07) ** 5")
        assert "14025" in result

    def test_math_module(self):
        """Test using math module functions."""
        result = self.calculate.invoke("result = math.sqrt(144)")
        assert "12" in result

    def test_statistics_module(self):
        """Test using statistics module."""
        result = self.calculate.invoke("result = statistics.mean([10, 20, 30, 40, 50])")
        assert "30" in result

    def test_decimal_precision(self):
        """Test using Decimal for precise financial calculations."""
        result = self.calculate.invoke("result = Decimal('100.50') * Decimal('1.05')")
        assert "105.525" in result

    def test_invalid_syntax(self):
        """Test error handling for invalid Python syntax."""
        result = self.calculate.invoke("result = 100 +")
        assert "error" in result.lower()

    def test_print_statements(self):
        """Test that print statements work for debugging."""
        result = self.calculate.invoke("print('Debug: calculating'); result = 42")
        assert "42" in result

    def test_allowed_imports(self):
        """Test that allowed imports work (math, datetime, etc.)."""
        result = self.calculate.invoke("""
import math
from datetime import datetime
result = math.ceil(10.5)
""")
        assert "11" in result

    def test_security_import_blocked(self):
        """Test that dangerous imports are blocked for security."""
        result = self.calculate.invoke("import os; result = 1")
        assert "error" in result.lower()
        assert "not allowed" in result.lower()

    def test_security_no_file_operations(self):
        """Test that file operations are blocked for security."""
        result = self.calculate.invoke("result = open('/etc/passwd')")
        assert "error" in result.lower()

    def test_multi_step_calculation(self):
        """Test complex multi-step calculation with intermediate variables."""
        code = """
principal = 100000
rate = 0.045
years = 30
monthly_rate = rate / 12
months = years * 12
monthly_payment = principal * monthly_rate * (1 + monthly_rate)**months / ((1 + monthly_rate)**months - 1)
result = round(monthly_payment, 2)
"""
        result = self.calculate.invoke(code)
        assert "error" not in result.lower()
        assert "506" in result or "507" in result

    def test_dti_calculation(self):
        """Test debt-to-income ratio calculation."""
        result = self.calculate.invoke("result = round(1500 / 5000 * 100, 2)")
        assert "30" in result

    def test_savings_rate(self):
        """Test savings rate calculation."""
        result = self.calculate.invoke("result = round((1 - (3500 / 5000)) * 100, 2)")
        assert "30" in result

    def test_emergency_fund_months(self):
        """Test emergency fund months coverage."""
        result = self.calculate.invoke("result = 18000 / 2500")
        assert "7.2" in result

    def test_credit_utilization(self):
        """Test credit utilization calculation."""
        result = self.calculate.invoke("result = round((2500 / 10000) * 100, 2)")
        assert "25" in result
