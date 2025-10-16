"""Math calculation tool for Goal Agent."""

import math
import statistics
from datetime import datetime, timedelta
from decimal import Decimal

from langchain_core.tools import tool

ALLOWED_MODULES = {'math', 'statistics', 'datetime', 'decimal', 'calendar', 'time'}


def safe_import(name, *args, **kwargs):
    """Allow imports only for whitelisted modules."""
    base_module = name.split('.')[0]
    if base_module not in ALLOWED_MODULES:
        raise ImportError(f"Module '{name}' is not allowed")
    return __import__(name, *args, **kwargs)


def get_calculate_description():
    """Dynamically generate tool description based on available modules."""
    available_modules = sorted(ALLOWED_MODULES)
    modules_str = ", ".join(available_modules)
    return f"Execute Python math calculations. Must assign result to 'result' variable. Available modules: {modules_str}."


SAFE_GLOBALS = {
    '__builtins__': {
        'abs': abs, 'round': round, 'min': min, 'max': max, 'sum': sum,
        'len': len, 'int': int, 'float': float, 'str': str, 'list': list,
        'print': print, '__import__': safe_import,
    },
    'math': math,
    'statistics': statistics,
    'datetime': datetime,
    'timedelta': timedelta,
    'Decimal': Decimal,
}


@tool(
    name_or_callable="calculate",
    description=get_calculate_description(),
)
def calculate(code: str) -> str:
    """Execute Python math calculations safely.

    REQUIRED: Assign final result to `result` variable.

    Available: math, statistics, datetime, timedelta, Decimal

    Example:
        code = "result = (50000 - 5000) / 1200"
        # Returns: "37.5"

    Args:
        code: Python code to execute

    Returns:
        String result or error message

    """
    locals_dict = {}
    try:
        exec(code, SAFE_GLOBALS, locals_dict)
    except ZeroDivisionError:
        return "Error: Division by zero"
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"

    if 'result' not in locals_dict:
        return "Error: Must assign to 'result' variable. Example: result = 100 * 1.05"

    return str(locals_dict['result'])
