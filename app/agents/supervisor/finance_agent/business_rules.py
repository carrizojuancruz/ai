"""
Business rules for transaction categories.
Provides category context for the finance agent without embedding all values in prompts.
"""

# Transaction Categories - Based on Plaid's official PRIMARY categories
# These match the exact categories from Plaid's transaction categorization system
PLAID_PRIMARY_CATEGORIES = [
    # Income & Transfers
    "INCOME", "TRANSFER_IN", "TRANSFER_OUT",

    # Payments & Fees
    "LOAN_PAYMENTS", "BANK_FEES",

    # Lifestyle Expenses
    "ENTERTAINMENT", "FOOD_AND_DRINK", "GENERAL_MERCHANDISE",
    "HOME_IMPROVEMENT", "MEDICAL", "PERSONAL_CARE",

    # Services
    "GENERAL_SERVICES", "GOVERNMENT_AND_NON_PROFIT",

    # Transportation & Travel
    "TRANSPORTATION", "TRAVEL",

    # Housing
    "RENT_AND_UTILITIES"
]

# Category groupings based on Plaid's PRIMARY categories
CATEGORY_GROUPS = {
    # Primary Plaid categories
    "income": ["INCOME", "Income", "Salary", "Payroll", "Dividends", "Interest", "Pension", "Tax Refund", "Unemployment"],
    "transfers_in": ["TRANSFER_IN", "Transfer", "Deposit", "Cash Advance", "Loan"],
    "transfers_out": ["TRANSFER_OUT", "Withdrawal", "Account Transfer", "Investment Transfer", "Savings Transfer"],
    "loan_payments": ["LOAN_PAYMENTS", "Credit Card Payment", "Loan Payment", "Mortgage Payment", "Car Payment", "Student Loan Payment"],
    "bank_fees": ["BANK_FEES", "Bank Fee", "ATM Fee", "Overdraft Fee", "Foreign Transaction Fee"],
    "entertainment": ["ENTERTAINMENT", "Entertainment", "Movies", "Music", "Games", "Sports", "Casino"],
    "food_and_drink": ["FOOD_AND_DRINK", "Food and Drink", "Groceries", "Restaurants", "Fast Food", "Coffee", "Beer, Wine and Liquor"],
    "shopping": ["GENERAL_MERCHANDISE", "Shopping", "Clothing", "Electronics", "Books", "Department Stores", "Online Marketplaces"],
    "home_improvement": ["HOME_IMPROVEMENT", "Home Improvement", "Furniture", "Hardware"],
    "medical": ["MEDICAL", "Healthcare", "Medical", "Pharmacy", "Dental Care", "Eye Care"],
    "personal_care": ["PERSONAL_CARE", "Personal Care", "Gym", "Hair and Beauty", "Laundry"],
    "services": ["GENERAL_SERVICES", "Services", "Education", "Insurance", "Consulting", "Legal", "Accounting"],
    "government": ["GOVERNMENT_AND_NON_PROFIT", "Government", "Taxes", "Donations", "Charity"],
    "transportation": ["TRANSPORTATION", "Transportation", "Gas", "Parking", "Public Transit", "Taxi", "Ride Share", "Tolls"],
    "travel": ["TRAVEL", "Travel", "Flights", "Hotels", "Lodging", "Rental Cars"],
    "rent_and_utilities": ["RENT_AND_UTILITIES", "Rent and Utilities", "Rent", "Electricity", "Gas", "Water", "Internet", "Phone"]
}


def get_business_rules_context_str() -> str:
    """Generate smart context string for prompts without listing all categories."""

    # Primary Plaid categories (most important)
    primary_info = f"Plaid PRIMARY Categories: {', '.join(PLAID_PRIMARY_CATEGORIES[:8])}... and {len(PLAID_PRIMARY_CATEGORIES)-8} more"

    # Group information
    groups_info = ", ".join([f"{group.replace('_', ' ').title()} ({len(categories)} types)"
                           for group, categories in list(CATEGORY_GROUPS.items())[:6]])

    # Common user queries patterns - focused on primary categories
    query_patterns = """
Common Query Patterns:
• "food spending" → FOOD_AND_DRINK categories (groceries, restaurants, coffee)
• "shopping expenses" → GENERAL_MERCHANDISE (clothing, electronics, stores)
• "entertainment costs" → ENTERTAINMENT (movies, music, games, sports)
• "medical expenses" → MEDICAL (healthcare, pharmacy, dental care)
• "transportation costs" → TRANSPORTATION (gas, parking, ride share, transit)
• "utility bills" → RENT_AND_UTILITIES (rent, electricity, internet, phone)
• "bank fees" → BANK_FEES (ATM fees, overdraft, foreign transaction)
• "loan payments" → LOAN_PAYMENTS (credit card, mortgage, student loans)
• "income sources" → INCOME (salary, dividends, interest, pension)
• "transfers" → TRANSFER_IN/TRANSFER_OUT (deposits, withdrawals)

General Analysis Patterns:
• Use "general_[group]_analysis" (e.g., "general_food_and_drink_analysis")
• Use primary category names: "FOOD_AND_DRINK", "GENERAL_MERCHANDISE", etc.
• System handles 100+ category variations automatically"""

    return f"""{primary_info}

{query_patterns}

Category Groups: {groups_info}.

Fallback Handling: Unknown categories map to "Other" or "Uncategorized". System supports Plaid PRIMARY categories and user-friendly names."""
