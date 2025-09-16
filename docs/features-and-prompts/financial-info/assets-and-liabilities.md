# Assets & Liabilities Management

## Navigation Path

To access the Assets & Liabilities feature, users navigate through the following path:

```
Home
└── Side Menu (☰)
    └── Financial Info
        └── Assets & Liabilities
```

**Navigation Flow:**
1. User opens the main application (Home screen)
2. Opens the **Side Menu** (☰ hamburger menu)
3. Selects **Financial Info** from the menu options
4. Chooses **Assets & Liabilities** from the Financial Info section

## Overview

The Assets & Liabilities system allows users to manually manage their financial assets and liabilities. This information is used as input to generate net worth reports in the Reports section.

## Main Functionality

### Manual Item Management
- **Add**: Users can manually add new assets or liabilities
- **Edit**: Modify name, value and category of existing items
- **Delete**: Remove items that are no longer relevant
- **Filter**: View all items, only assets, or only liabilities

### Category Selection
Users select the appropriate category from a predefined enum (finite list) when creating or editing items. The following categories are available:

## Asset Categories

| Category | Type | Scope (examples) | Phosphor Icon |
|----------|------|------------------|---------------|
| Real Estate | Asset | Houses, apartments, land, offices | `house` |
| Vehicles | Asset | Cars, motorcycles, boats, airplanes | `car` |
| Electronics & Equipment | Asset | Computers, cameras, phones, tools, office equipment | `devices` |
| Luxury & Collectibles | Asset | Watches, jewelry, art, instruments | `diamond` |
| Financial Assets | Asset | Savings, stocks, crypto, bonds | `chart-line-up` |
| Other Assets | Asset | Miscellaneous valuables | `archive-box` |

## Liability Categories

| Category | Type | Scope (examples) | Phosphor Icon |
|----------|------|------------------|---------------|
| Mortgages | Liability | Home loans, property loans | `house-line` |
| Loans | Liability | Personal, student, business, car loans | `handshake` |
| Credit & Debt | Liability | Credit cards, credit lines | `credit-card` |
| Bills & Medical | Liability | Medical bills, unpaid services | `file-text` |
| Other Liabilities | Liability | Miscellaneous debts | `warning` |

## Suggested JSON Schema

```json
{
  "assets_and_liabilities": {
    "items": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000", // UUID string
        "name": "Tesla Model 3", // Item name
        "value": 3200000, // Value in cents (32000.00)
        "type": "asset", // "asset" or "liability"
        "category": "vehicles", // Must be from AssetCategory enum if type="asset", LiabilityCategory if type="liability"
        "created_at": "2024-01-15T10:30:00Z", // ISO 8601 timestamp
        "updated_at": "2024-01-20T14:22:00Z", // ISO 8601 timestamp
        "user_id": "123e4567-e89b-12d3-a456-426614174000" // UUID string
      }
    ]
  }
}
```

### Enum Definitions

```typescript
// Asset Categories Enum
enum AssetCategory {
  REAL_ESTATE = "real_estate",
  VEHICLES = "vehicles",
  ELECTRONICS_EQUIPMENT = "electronics_equipment",
  LUXURY_COLLECTIBLES = "luxury_collectibles",
  FINANCIAL_ASSETS = "financial_assets",
  OTHER_ASSETS = "other_assets"
}

// Liability Categories Enum
enum LiabilityCategory {
  MORTGAGES = "mortgages",
  LOANS = "loans",
  CREDIT_DEBT = "credit_debt",
  BILLS_MEDICAL = "bills_medical",
  OTHER_LIABILITIES = "other_liabilities"
}
```

### Category Configuration (for UI display)

```json
{
  "category_config": {
    "real_estate": {
      "name": "Real Estate",
      "icon": "house", // Phosphor Icons
      "type": "asset"
    },
    "vehicles": {
      "name": "Vehicles",
      "icon": "car", // Phosphor Icons
      "type": "asset"
    },
    "electronics_equipment": {
      "name": "Electronics & Equipment",
      "icon": "devices", // Phosphor Icons
      "type": "asset"
    },
    "luxury_collectibles": {
      "name": "Luxury & Collectibles",
      "icon": "diamond", // Phosphor Icons
      "type": "asset"
    },
    "financial_assets": {
      "name": "Financial Assets",
      "icon": "chart-line-up", // Phosphor Icons
      "type": "asset"
    },
    "other_assets": {
      "name": "Other Assets",
      "icon": "archive-box", // Phosphor Icons
      "type": "asset"
    },
    "mortgages": {
      "name": "Mortgages",
      "icon": "house-line", // Phosphor Icons
      "type": "liability"
    },
    "loans": {
      "name": "Loans",
      "icon": "handshake", // Phosphor Icons
      "type": "liability"
    },
    "credit_debt": {
      "name": "Credit & Debt",
      "icon": "credit-card", // Phosphor Icons
      "type": "liability"
    },
    "bills_medical": {
      "name": "Bills & Medical",
      "icon": "file-text", // Phosphor Icons
      "type": "liability"
    },
    "other_liabilities": {
      "name": "Other Liabilities",
      "icon": "warning", // Phosphor Icons
      "type": "liability"
    }
  }
}
```

## User Flow

### 1. Visualization
- List of items with filters (All/Assets/Liabilities)
- Each item shows: name, value, and edit option
- Total items counter

### 2. Add Item
- "Add" button opens modal
- Type selection (Asset/Liability)
- Fields: name, value
- Category selection from predefined enum
- Required field validation

### 3. Edit Item
- Click "Edit" opens edit modal
- Pre-populated with current data
- Modification of all fields
- Delete item option

### 4. Delete Item
- Confirmation required
- Item permanently removed
- Counter updates

## Reports Integration

Assets & Liabilities data is used for:
- **Net Worth Calculation**: Sum of assets - sum of liabilities

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
- Value must be positive numeric
- Name is required
- Type must be "asset" or "liability"
- Category must be selected from predefined enum
- **Category-Type Validation**: 
  - If `type="asset"`, category must be from `AssetCategory` enum
  - If `type="liability"`, category must be from `LiabilityCategory` enum
  - Cross-type categories are not allowed (e.g., "vehicles" cannot be used with `type="liability"`)

### Persistence
- Database storage
- Synchronization with reporting system
- Change history for auditing

## UI States

### Main List
- Loading state during initial load
- Empty state when no items
- Error state for network failures

### Modals
- Real-time validation
- Loading states for operations
- Confirmation for deletion
- Visual feedback for successful actions

## Metrics and Analytics
- Current net worth
- Asset distribution
