from __future__ import annotations

from enum import Enum


class AssetCategory(str, Enum):
    REAL_ESTATE = "Real Estate"
    VEHICLES = "Vehicles"
    ELECTRONICS_EQUIPMENT = "Electronics & Equipment"
    LUXURY_COLLECTIBLES = "Luxury & Collectibles"
    FINANCIAL_ASSETS = "Financial Assets"
    OTHER_ASSETS = "Other Assets"


class LiabilityCategory(str, Enum):
    MORTGAGES = "Mortgages"
    LOANS = "Loans"
    CREDIT_DEBT = "Credit & Debt"
    BILLS_MEDICAL = "Bills & Medical"
    OTHER_LIABILITIES = "Other Liabilities"


class ManualTransactionFrequency(str, Enum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class ManualTransactionKind(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"


class VeraPovIncomeCategory(str, Enum):
    SALARY_WAGES = "Salary & Wages"
    INVESTMENT_INCOME = "Investment Income"
    RETIREMENT_INCOME = "Retirement Income"
    GOVERNMENT_BENEFITS = "Government Benefits"
    OTHER_INCOME = "Other Income"
    TRANSFERS_DEPOSITS = "Transfers & Deposits"


class VeraPovExpenseCategory(str, Enum):
    FOOD_DINING = "Food & Dining"
    SHOPPING_ENTERTAINMENT = "Shopping & Entertainment"
    HOUSING_UTILITIES = "Housing & Utilities"
    TRANSPORTATION_TRAVEL = "Transportation & Travel"
    HEALTHCARE_PERSONAL_CARE = "Healthcare & Personal Care"
    PROFESSIONAL_SERVICES = "Professional Services"
    DEBT_GOVERNMENT = "Debt & Government"
    FEES_OTHER = "Fees & Other"
    HOME_MAINTENANCE = "Home & Maintenance"


VERA_INCOME_TO_PLAID_SUBCATEGORIES: dict[VeraPovIncomeCategory, dict[str, tuple[str, ...]]] = {
    VeraPovIncomeCategory.SALARY_WAGES: {
        "Income": (
            "Wages",
        ),
    },
    VeraPovIncomeCategory.INVESTMENT_INCOME: {
        "Income": (
            "Dividends",
            "Interest earned",
            "Investment and retirement funds",
        ),
    },
    VeraPovIncomeCategory.RETIREMENT_INCOME: {
        "Income": (
            "Retirement pension",
        ),
    },
    VeraPovIncomeCategory.GOVERNMENT_BENEFITS: {
        "Income": (
            "Tax refund",
            "Unemployment",
        ),
    },
    VeraPovIncomeCategory.OTHER_INCOME: {
        "Income": (
            "Other income",
        ),
    },
    VeraPovIncomeCategory.TRANSFERS_DEPOSITS: {
        "Income": (
            "Account transfer",
            "Cash advances and loans",
            "Deposit",
            "Other transfer in",
            "Savings",
        ),
    },
}


def to_fos_category(category: AssetCategory | LiabilityCategory | str) -> str:
    """Convert Vera POV category to FOS API AssetCategory/LiabilityCategory enum format.

    FOS API expects snake_case category strings (e.g., "real_estate", "vehicles").
    This function converts Vera user-facing categories to FOS API format.

    Conversion rules:
    - Convert to lowercase
    - Replace spaces with underscores
    - Remove ampersands and special characters

    Examples:
        "Real Estate" -> "real_estate"
        "Electronics & Equipment" -> "electronics_equipment"
        "Vehicles" -> "vehicles"

    Args:
        category: Vera category enum or string

    Returns:
        FOS API compatible category string matching FOS AssetCategory/LiabilityCategory enum

    """
    category_str = category.value if isinstance(category, (AssetCategory, LiabilityCategory)) else str(category)

    return (
        category_str.lower()
        .replace(" & ", "_")
        .replace("&", "")
        .replace(" ", "_")
    )

VERA_EXPENSE_TO_PLAID_SUBCATEGORIES: dict[VeraPovExpenseCategory, dict[str, tuple[str, ...]]] = {
    VeraPovExpenseCategory.FOOD_DINING: {
        "Food & Dining": (
            "Beer wine and liquor",
            "Coffee",
            "Fast food",
            "Groceries",
            "Other food and drinks",
            "Restaurant",
            "Vending machines",
        ),
    },
    VeraPovExpenseCategory.SHOPPING_ENTERTAINMENT: {
        "Shopping & Entertainment": (
            "Bookstores and newsstands",
            "Clothing and accessories",
            "Convenience stores",
            "Department stores",
            "Discount stores",
            "Electronics",
            "Gift and novelties",
            "Office supplies",
            "Online marketplaces",
            "Other general merchandise",
            "Pet supplies",
            "Sporting goods",
            "Superstores",
            "Tobacco and vape",
            "Casinos and gambling",
            "Music and audio",
            "Other entertainment",
            "Sporting events amusement parks",
            "TV and movies",
            "Video games",
        ),
    },
    VeraPovExpenseCategory.HOUSING_UTILITIES: {
        "Housing & Utilities": (
            "Rent",
            "Gas and electricity",
            "Internet and cable",
            "Other utilities",
            "Sewage and waste management",
            "Telephone",
            "Water",
        ),
    },
    VeraPovExpenseCategory.TRANSPORTATION_TRAVEL: {
        "Transportation & Travel": (
            "Bikes and scooters",
            "Gas",
            "Other transportation",
            "Parking",
            "Public transit",
            "Taxis and ride shares",
            "Tolls",
            "Flights",
            "Lodging",
            "Other travel",
            "Rental cars",
        ),
    },
    VeraPovExpenseCategory.HEALTHCARE_PERSONAL_CARE: {
        "Healthcare & Personal Care": (
            "Dental care",
            "Eye care",
            "Nursing care",
            "Other medical",
            "Pharmacies and supplements",
            "Primary care",
            "Veterinary services",
            "Gyms and fitness centers",
            "Hair and beauty",
            "Laundry and dry cleaning",
            "Other personal care",
        ),
    },
    VeraPovExpenseCategory.PROFESSIONAL_SERVICES: {
        "Professional Services": (
            "Accounting and financial planning",
            "Automotive",
            "Childcare",
            "Consulting and legal",
            "Education",
            "Insurance",
            "Other general services",
            "Postage and shipping",
            "Storage",
        ),
    },
    VeraPovExpenseCategory.DEBT_GOVERNMENT: {
        "Debt & Government": (
            "Car payment",
            "Credit card payment",
            "Mortgage payment",
            "Other payment",
            "Personal loan payment",
            "Student loan payment",
            "Donations",
            "Government department and agencies",
            "Other government and non profit",
            "Tax payment",
        ),
    },
    VeraPovExpenseCategory.FEES_OTHER: {
        "Home & Other": (
            "ATM fees",
            "Foreign transaction fees",
            "Insufficient funds",
            "Interest charge",
            "Other bank fees",
            "Overdraft fees",
            "Uncategorized",
        ),
    },
    VeraPovExpenseCategory.HOME_MAINTENANCE: {
        "Home & Other": (
            "Furniture",
            "Hardware",
            "Other home improvement",
            "Repair and maintenance",
            "Security",
        ),
    },
}


