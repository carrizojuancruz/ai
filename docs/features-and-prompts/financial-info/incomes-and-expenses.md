# Incomes & Expenses Management

## Navigation Path

To access the Incomes & Expenses feature, users navigate through the following path:

```
Home
└── Side Menu (☰)
    └── Financial Info
        └── Incomes & Expenses
```

**Navigation Flow:**
1. User opens the main application (Home screen)
2. Opens the **Side Menu** (☰ hamburger menu)
3. Selects **Financial Info** from the menu options
4. Chooses **Incomes & Expenses** from the Financial Info section

## Overview

The Incomes & Expenses system provides visibility into all financial transactions (manual and Plaid) while allowing users to manage only manually created transactions. Plaid transactions are read-only for viewing. This combined visibility is used to generate comprehensive financial reports and track cash flow patterns.

## Main Functionality

### Transaction Management
- **Add**: Users can manually add new income or expense transactions
- **Edit**: Modify details of manually created transactions only
- **Delete**: Remove manually created transactions
- **Filter**: View all transactions, only incomes, or only expenses
- **Sort**: Transactions displayed in newest to oldest order (sorted by `created_at` date)

### Data Sources
- **Plaid Integration**: Automatic transaction import from connected bank accounts
- **Manual Entry**: User-created transactions for cash payments or unlinked accounts
- **Edit Restrictions**: Plaid transactions are read-only, manual transactions are fully editable

## Transaction Categories (Unified)

*Note: Categories are suggested based on Plaid's classification system as a reference. Icons are aligned with Phosphor Icons library.*

| Category | Scope (examples) | Phosphor Icon |
|----------|------------------|---------------|
| bank_fees | Banking fees, overdraft charges, ATM fees | `Bank` |
| entertainment | Movies, concerts, subscriptions, hobbies | `GameController` |
| food_drink | Groceries, restaurants, bars, coffee | `ForkKnife` |
| general_merchandise | Shopping, clothing, electronics, gifts | `ShoppingBag` |
| general_services | Professional services, consulting, repairs | `Gear` |
| government_nonprofit | Taxes, donations, government fees | `Buildings` |
| home_improvement | Renovations, repairs, maintenance | `House` |
| income | Salary, wages, freelance, investments | `Money` |
| loan_payments | Mortgage, car loans, personal loans | `Clock` |
| medical | Healthcare, pharmacy, insurance | `Heart` |
| personal_care | Beauty, fitness, wellness | `User` |
| rent_utilities | Rent, electricity, water, internet | `HouseLine` |
| transfer_in | Money received, gifts, transfers | `ArrowDownLeft` |
| transfer_out | Money sent, gifts given, transfers | `ArrowUpRight` |
| transportation | Gas, public transit, rideshare, parking | `Car` |
| travel | Flights, hotels, vacation expenses | `Briefcase` |

## Suggested JSON Schema (Manual Transactions Only)

*Note: This schema is specifically for transactions created manually by users (by hand). Plaid transactions have a different structure and are not editable.*

```json
{
  "manual_transactions": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000", // UUID string
      "name": "Tesla Model 3 Payment", // Transaction name
      "amount": 3200000, // Amount in cents (32000.00)
      "type": "expense", // "income" or "expense"
      "category": "transportation", // Must be from TransactionCategory enum
      "date": "2024-01-15T10:30:00Z", // ISO 8601 timestamp (auto-generated)
      "created_at": "2024-01-15T10:30:00Z", // ISO 8601 timestamp
      "updated_at": "2024-01-20T14:22:00Z", // ISO 8601 timestamp
      "user_id": "123e4567-e89b-12d3-a456-426614174000" // UUID string
    }
  ]
}
```

### UI Form Fields

1. **Type Selection**: Income or Expense
2. **Category Selection**: Dropdown with TransactionCategory options
3. **Name**: Text input field (transaction name)
4. **Amount**: Numeric input field (stored in cents)

*Note: System fields like `id`, `name`, `created_at`, `updated_at`, and `user_id` are automatically generated and not shown in the UI. The `date` field is automatically set to the current timestamp when creating or editing. Transactions are sorted by `created_at` date (newest to oldest).*

### Enum Definitions

```typescript
// Transaction Categories Enum (Unified - Suggested based on Plaid reference)
enum TransactionCategory {
  BANK_FEES = "bank_fees",
  ENTERTAINMENT = "entertainment",
  FOOD_DRINK = "food_drink",
  GENERAL_MERCHANDISE = "general_merchandise",
  GENERAL_SERVICES = "general_services",
  GOVERNMENT_NONPROFIT = "government_nonprofit",
  HOME_IMPROVEMENT = "home_improvement",
  INCOME = "income",
  LOAN_PAYMENTS = "loan_payments",
  MEDICAL = "medical",
  PERSONAL_CARE = "personal_care",
  RENT_UTILITIES = "rent_utilities",
  TRANSFER_IN = "transfer_in",
  TRANSFER_OUT = "transfer_out",
  TRANSPORTATION = "transportation",
  TRAVEL = "travel"
}
```

### Category Configuration (for UI display)

```json
{
  "category_config": {
    "bank_fees": {
      "name": "Bank Fees",
      "icon": "Bank"
    },
    "entertainment": {
      "name": "Entertainment",
      "icon": "GameController"
    },
    "food_drink": {
      "name": "Food & Drink",
      "icon": "ForkKnife"
    },
    "general_merchandise": {
      "name": "General Merchandise",
      "icon": "ShoppingBag"
    },
    "general_services": {
      "name": "General Services",
      "icon": "Gear"
    },
    "government_nonprofit": {
      "name": "Government & Non-profit",
      "icon": "Buildings"
    },
    "home_improvement": {
      "name": "Home Improvement",
      "icon": "House"
    },
    "income": {
      "name": "Income",
      "icon": "Money"
    },
    "loan_payments": {
      "name": "Loan Payments",
      "icon": "Clock"
    },
    "medical": {
      "name": "Medical",
      "icon": "Heart"
    },
    "personal_care": {
      "name": "Personal Care",
      "icon": "User"
    },
    "rent_utilities": {
      "name": "Rent & Utilities",
      "icon": "HouseLine"
    },
    "transfer_in": {
      "name": "Transfer In",
      "icon": "ArrowDownLeft"
    },
    "transfer_out": {
      "name": "Transfer Out",
      "icon": "ArrowUpRight"
    },
    "transportation": {
      "name": "Transportation",
      "icon": "Car"
    },
    "travel": {
      "name": "Travel",
      "icon": "Briefcase"
    }
  }
}
```

## User Flow

### 1. Visualization
- List of transactions with filters (All/Incomes/Expenses)
- Each transaction shows: name, amount, date, and edit option (if editable)
- Total items counter
- Last update timestamp
- Net income summary

### 2. Add/Edit Transaction (Manual)
- **Add**: "Add" button opens modal
- **Edit**: Click "Edit" opens edit modal (only for manual transactions)
- **Fields**:
  - Type Selection: Income or Expense (radio buttons)
  - Category Selection: Dropdown with TransactionCategory options
  - Name: Text input field (required, transaction name)
  - Amount: Numeric input field (required, stored in cents)
- Real-time validation for all required fields
- Date automatically set/updated to current timestamp (sorting remains by `created_at`)
- **Edit only**: Pre-populated with current data, delete option, warning message about report impact

### 3. Delete Transaction
- Confirmation required
- Transaction permanently removed
- Counter updates

### 4. Plaid Transactions
- Displayed with "Plaid" badge
- Read-only (no edit option)
- Show merchant information when available
- Include location data if provided by Plaid

## Reports Integration

Incomes & Expenses data is used for:
- **Cash Flow Analysis**: Income vs expenses over time
- **Category Breakdown**: Spending patterns by category
- **Monthly/Yearly Summaries**: Financial performance tracking

## Technical Considerations

### Data Types and Identifiers

#### UUID
- **Usage**: `id` and `user_id` fields

#### Enum
- **Usage**: `category` field selection
- **Benefits**: Data consistency, validation, type safety

**Implementation Approach:**
- **Enums**: Define the valid category values in code
- **Category Config**: Separate configuration object for UI display (names, icons)
- **Data Storage**: Only store the enum value in the database
- **UI Rendering**: Use category config to display names and icons

### Validations
- **Type**: Must be "income" or "expense" (required)
- **Category**: Must be selected from `TransactionCategory` enum (required)
- **Name**: Required text field (non-empty string)
- **Amount**: Required numeric field (stored in cents, can be positive or negative)
- **Date**: Automatically set to current timestamp when creating or editing
- **Category Logic**: Same categories work for both income and expense transactions

### Plaid Integration & Persistence
- **Transaction Sync**: Automatic import of new transactions
- **Category Mapping**: Map Plaid categories to our enum values (suggested mapping)

## UI States

### Main List
- Loading, empty, and error states
- Last update indicator
- **Manual Transactions**: Show "Edit" button
- **Plaid Transactions**: Show "Plaid" badge with read-only indicator
- **Amount Display**: Format with proper currency symbols
- **Date Display**: Relative time (e.g., "2 hours ago") with full date on hover

### Modals
- Real-time validation
- Loading states for operations
- Confirmation for deletion
- Visual feedback for successful actions

## Metrics and Analytics
- Net income calculation (total income - total expenses)
- Category spending breakdown
- Monthly/yearly trends
