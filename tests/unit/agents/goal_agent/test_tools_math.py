"""Unit tests for Goal Agent math calculation tool."""

from app.agents.supervisor.goal_agent.tools_math import calculate


def test_basic_calculation():
    """Test basic math calculation with result variable."""
    result = calculate.invoke("result = 100 * 1.05 ** 3")
    assert "115.76" in result


def test_missing_result():
    """Test error when result variable is not assigned."""
    result = calculate.invoke("x = 100")
    assert "result" in result.lower()


def test_division_by_zero():
    """Test error handling for division by zero."""
    result = calculate.invoke("result = 100 / 0")
    assert "division by zero" in result.lower()


def test_financial_projection():
    """Test realistic financial projection calculation."""
    result = calculate.invoke("result = (50000 - 5000) / 1200")
    assert "37.5" in result


def test_percentage_calculation():
    """Test percentage calculation."""
    result = calculate.invoke("result = (12500 / 50000) * 100")
    assert "25" in result


def test_compound_interest():
    """Test compound interest calculation."""
    result = calculate.invoke("result = 10000 * (1 + 0.07) ** 5")
    assert "14025" in result


def test_math_module():
    """Test using math module functions."""
    result = calculate.invoke("result = math.sqrt(144)")
    assert "12" in result


def test_statistics_module():
    """Test using statistics module."""
    result = calculate.invoke("result = statistics.mean([10, 20, 30, 40, 50])")
    assert "30" in result


def test_decimal_precision():
    """Test using Decimal for precise financial calculations."""
    result = calculate.invoke("result = Decimal('100.50') * Decimal('1.05')")
    assert "105.525" in result


def test_invalid_syntax():
    """Test error handling for invalid Python syntax."""
    result = calculate.invoke("result = 100 +")
    assert "error" in result.lower()


def test_print_statements():
    """Test that print statements work for debugging/logging."""
    result = calculate.invoke("print('Debug: starting'); result = 42")
    assert "42" in result


def test_allowed_imports():
    """Test that allowed imports work (math, datetime, etc.)."""
    result = calculate.invoke("""
import math
from datetime import datetime
result = math.ceil(10.5)
""")
    assert "11" in result


def test_security_import_blocked():
    """Test that imports are blocked for security."""
    result = calculate.invoke("import os; result = 1")
    assert "error" in result.lower()
    assert "not allowed" in result.lower()


def test_security_open_blocked():
    """Test that file operations are blocked for security."""
    result = calculate.invoke("result = open('/etc/passwd')")
    assert "error" in result.lower()


def test_complex_llm_generated_code():
    """Test complex multi-step calculation like LLM would generate."""
    code = """# Calculate months needed to reach savings goal
current_savings = 5000
target_savings = 50000
monthly_savings = 1200

# Amount still needed to save
remaining_amount = target_savings - current_savings
print(f"Amount still needed: ${remaining_amount:,}")

# Calculate months needed (rounded up since we can't have partial months)
import math
months_needed = math.ceil(remaining_amount / monthly_savings)
print(f"Months needed: {months_needed}")

# Calculate target date from current date (2025-10-15)
from datetime import datetime, timedelta
import calendar

current_date = datetime(2025, 10, 15)
print(f"Current date: {current_date.strftime('%Y-%m-%d')}")

# Add months to current date
target_year = current_date.year
target_month = current_date.month + months_needed

# Handle year rollover
while target_month > 12:
    target_month -= 12
    target_year += 1

# Create target date (using day 15 to match current date)
target_date = datetime(target_year, target_month, 15)
print(f"Target date: {target_date.strftime('%Y-%m-%d')}")
print(f"Target month/year: {target_date.strftime('%B %Y')}")

# Verification calculation
total_saved_by_target = current_savings + (months_needed * monthly_savings)
print(f"Total amount by target date: ${total_saved_by_target:,}")
print(f"Exceeds goal by: ${total_saved_by_target - target_savings:,}")

# Store results
result = {
    "months_needed": months_needed,
    "target_date": target_date.strftime('%Y-%m-%d'),
    "target_month_year": target_date.strftime('%B %Y'),
    "remaining_amount": remaining_amount,
    "total_by_target": total_saved_by_target,
    "excess_amount": total_saved_by_target - target_savings
}"""
    result = calculate.invoke(code)
    assert "months_needed" in result
    assert "38" in result
    assert "2028-12-15" in result
    assert "total_by_target" in result
    assert "excess_amount" in result
