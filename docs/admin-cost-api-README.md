# Admin Cost API Documentation

This document provides comprehensive documentation for the Verde AI Admin Cost API endpoints. 

## Overview
---

## 📅 **Endpoint 2: Daily Cost Breakdown**

### `GET /admin/users/{user_id}/costs`Admin Cost API provides cost analytics for **registered users only** (users with user_id). The API currently implements **2 core endpoints** that cover all cost analysis needs.

### 🎯 **Available Endpoints**

1. **`GET /admin/users/costs`** - Flexible endpoint for cost summaries with multiple query options
2. **`GET /admin/users/{user_id}/costs`** - Daily cost breakdown for specific users

## Base URL

```
http://localhost:8000
```

## Authentication

⚠️ **No authentication is currently implemented.** These endpoints are open for development/testing purposes.

---

## 📊 **Endpoint 1: Flexible User Costs**

### `GET /admin/users/costs`

**Description:** Single flexible endpoint that handles all user cost scenarios with consistent response format. Returns aggregated cost summaries.

**Parameters:**
- `user_id` (query): Optional. Filter by specific user ID
- `from_date` (query): Optional. Start date for range (YYYY-MM-DD)
- `to_date` (query): Optional. End date for range (YYYY-MM-DD)

**Parameter Logic:**
- **No params**: All users historical costs 
- **user_id only**: Specific user historical costs
- **from_date=to_date**: All/specific users for single date
- **date range**: All/specific users aggregated for date range

**Always returns `List[AdminCostSummary]` with only essential fields: user_id, total_cost, trace_count.**

#### Use Case 1: All Users Historical Costs
**Purpose:** Admin dashboard overview of all registered users
```bash
GET /admin/users/costs
```

**Expected Response:** *(List of all users)*
```json
[
  {
    "user_id": "ba5c5db4-d3fb-4ca8-9445-1c221ea502a8",
    "total_cost": 8.561042599928,
    "trace_count": 151
  },
  {
    "user_id": "user2-abc-123",
    "total_cost": 1.580669999984,
    "trace_count": 82
  }
]
```

#### Use Case 2: Specific User Historical Costs
**Purpose:** Customer support - check user's lifetime usage
```bash
GET /admin/users/costs?user_id=ba5c5db4-d3fb-4ca8-9445-1c221ea502a8
```

**Expected Response:**
```json
[
  {
    "user_id": "ba5c5db4-d3fb-4ca8-9445-1c221ea502a8",
    "total_cost": 8.561042599928,
    "trace_count": 151
  }
]
```

#### Use Case 3: All Users for Specific Date
**Purpose:** Daily operations report
```bash
GET /admin/users/costs?from_date=2025-09-10&to_date=2025-09-10
```

**Expected Response:**
```json
[
  {
    "user_id": "ba5c5db4-d3fb-4ca8-9445-1c221ea502a8",
    "total_cost": 0.189464999999,
    "trace_count": 4
  },
  {
    "user_id": "27c4b928-59f7-46fa-be5a-f6795f4fda6f",
    "total_cost": 0.041343,
    "trace_count": 4
  }
]
```

#### Use Case 4: Specific User for Date Range
**Purpose:** Monthly billing calculation
```bash
GET /admin/users/costs?user_id=ba5c5db4-d3fb-4ca8-9445-1c221ea502a8&from_date=2025-09-01&to_date=2025-09-10
```

**Expected Response:**
```json
[
  {
    "user_id": "ba5c5db4-d3fb-4ca8-9445-1c221ea502a8",
    "total_cost": 7.895123456789,
    "trace_count": 142
  }
]
```

#### Use Case 5: No Data Found
**Purpose:** Handle cases with no activity
```bash
GET /admin/users/costs?user_id=nonexistent-user
GET /admin/users/costs?from_date=2025-01-01&to_date=2025-01-01
```

**Expected Response:**
```json
[]
```

---

## � **Endpoint 2: Daily Cost Breakdown**

### `GET /admin/users/{user_id}/costs`

**Description:** Returns daily cost breakdown for a specific registered user. Returns a list where each object represents one day's activity.

**Parameters:**
- `user_id` (path): Required. The specific user ID
- `from_date` (query): Optional. Start date (YYYY-MM-DD). Default: 30 days ago
- `to_date` (query): Optional. End date (YYYY-MM-DD). Default: today

**Date Range Logic:**
- **No params**: Last 30 days (from 30 days ago to today)
- **from_date only**: From that date to today
- **to_date only**: From that date to that date (single day)
- **Both dates**: From from_date to to_date

**Use Cases:**
- Get daily cost breakdown for billing analysis
- Track user spending patterns over time
- Monitor cost trends for specific users

#### Example 1: Default Range (Last 30 Days)
```bash
GET /admin/users/ba5c5db4-d3fb-4ca8-9445-1c221ea502a8/costs
```

**Expected Response:**
```json
[
  {
    "user_id": "ba5c5db4-d3fb-4ca8-9445-1c221ea502a8",
    "total_cost": 0.189465,
    "total_tokens": 0,
    "trace_count": 4,
    "date": "2025-09-10"
  },
  {
    "user_id": "ba5c5db4-d3fb-4ca8-9445-1c221ea502a8",
    "total_cost": 3.464079,
    "total_tokens": 0,
    "trace_count": 36,
    "date": "2025-09-09"
  },
  {
    "user_id": "ba5c5db4-d3fb-4ca8-9445-1c221ea502a8",
    "total_cost": 2.441913,
    "total_tokens": 0,
    "trace_count": 34,
    "date": "2025-09-08"
  }
]
```

#### Example 2: From Specific Date to Today
```bash
GET /admin/users/ba5c5db4-d3fb-4ca8-9445-1c221ea502a8/costs?from_date=2025-09-08
```

#### Example 3: Specific Date Range
```bash
GET /admin/users/ba5c5db4-d3fb-4ca8-9445-1c221ea502a8/costs?from_date=2025-09-08&to_date=2025-09-10
```

---

## 📋 **Data Models**

### DailyCostResponse
Used by `/admin/users/{user_id}/costs` endpoint.
```json
{
  "user_id": "string",
  "total_cost": 0.0,
  "total_tokens": 0,
  "trace_count": 0,
  "date": "YYYY-MM-DD"
}
```

### AdminCostSummary
Used by `/admin/users/costs` endpoint.
```json
{
  "user_id": "string",
  "total_cost": 0.0,
  "trace_count": 0
}
```

### CostSummary
Used by `/admin/users/guest/costs` endpoint.
```json
{
  "user_id": null,
  "total_cost": 0.0,
  "total_tokens": 0,
  "trace_count": 0,
  "date_range": {
    "from": "YYYY-MM-DD",
    "to": "YYYY-MM-DD"
  }
}
```

---

## ⚠️ **Error Handling**

### Validation Errors (HTTP 422)
```json
{
  "detail": [
    {
      "loc": ["query", "from_date"],
      "msg": "invalid date format",
      "type": "value_error"
    }
  ]
}
```

### Server Errors (HTTP 500)
```json
{
  "detail": "Failed to fetch user costs: <error_message>"
}
```

---

## 🧪 **Testing Examples**

### Complete Test Suite
```bash
# Flexible endpoint tests
curl "http://localhost:8000/admin/users/costs"
curl "http://localhost:8000/admin/users/costs?user_id=ba5c5db4-d3fb-4ca8-9445-1c221ea502a8"
curl "http://localhost:8000/admin/users/costs?from_date=2025-09-10&to_date=2025-09-10"
curl "http://localhost:8000/admin/users/costs?user_id=ba5c5db4-d3fb-4ca8-9445-1c221ea502a8&from_date=2025-09-02&to_date=2025-09-10"

# Daily breakdown tests
curl "http://localhost:8000/admin/users/ba5c5db4-d3fb-4ca8-9445-1c221ea502a8/costs"
curl "http://localhost:8000/admin/users/ba5c5db4-d3fb-4ca8-9445-1c221ea502a8/costs?from_date=2025-09-08"
curl "http://localhost:8000/admin/users/ba5c5db4-d3fb-4ca8-9445-1c221ea502a8/costs?from_date=2025-09-08&to_date=2025-09-10"
```

### PowerShell Test Script
```powershell
# Set base URL
$baseUrl = "http://localhost:8000"
$userId = "ba5c5db4-d3fb-4ca8-9445-1c221ea502a8"

Write-Output "=== Testing Admin Cost API ==="

# Test flexible endpoint
Write-Output "`n--- Flexible Endpoint Tests ---"

# All users historical
$response = Invoke-WebRequest -Uri "$baseUrl/admin/users/costs" -Method GET
$response.Content | ConvertFrom-Json | Format-List

# Specific user historical
$response = Invoke-WebRequest -Uri "$baseUrl/admin/users/costs?user_id=$userId" -Method GET
$response.Content | ConvertFrom-Json | Format-List

# All users for today
$response = Invoke-WebRequest -Uri "$baseUrl/admin/users/costs?from_date=2025-09-10&to_date=2025-09-10" -Method GET
$response.Content | ConvertFrom-Json | Format-List

# Specific user for date range
$response = Invoke-WebRequest -Uri "$baseUrl/admin/users/costs?user_id=$userId&from_date=2025-09-08&to_date=2025-09-10" -Method GET
$response.Content | ConvertFrom-Json | Format-List

# Test daily breakdown endpoint
Write-Output "`n--- Daily Breakdown Tests ---"

# User daily costs (last 30 days)
$response = Invoke-WebRequest -Uri "$baseUrl/admin/users/$userId/costs" -Method GET
$response.Content | ConvertFrom-Json | Format-List

# User daily costs from specific date to today
$response = Invoke-WebRequest -Uri "$baseUrl/admin/users/$userId/costs?from_date=2025-09-08" -Method GET
$response.Content | ConvertFrom-Json | Format-List

# User daily costs for specific range
$response = Invoke-WebRequest -Uri "$baseUrl/admin/users/$userId/costs?from_date=2025-09-08&to_date=2025-09-10" -Method GET
$response.Content | ConvertFrom-Json | Format-List
```

---

## 🎯 **Best Practices**

### 1. Endpoint Selection
- **Daily cost breakdown**: Use `/admin/users/{user_id}/costs` for day-by-day analysis
- **Aggregated costs**: Use `/admin/users/costs` for summary analytics
- **Single user focus**: Use the path parameter version for detailed analysis
- **Multi-user reports**: Use the query parameter version for dashboards

### 2. Parameter Usage
- **Historical data**: No date parameters for lifetime data
- **Single date**: Set `from_date=to_date` for specific day analysis
- **Date ranges**: Use both parameters for period analysis
- **User filtering**: Add `user_id` parameter to focus on specific users

### 3. Performance Considerations
- **Large datasets**: Be cautious with all-users queries
- **Date ranges**: Limit ranges to reasonable periods (≤ 30 days)
- **Single user queries**: Generally faster and recommended when possible

### 4. Error Handling
- Always handle HTTP 422 for validation errors
- Implement retry logic for HTTP 500 errors
- Validate date formats client-side before sending

---

## 🔧 **Configuration**

### Time Windows
- **Daily breakdown**: Last 30 days default for single user queries
- **Aggregated costs**: No time limits (returns all available data)
- **Date ranges**: Recommended maximum of 30 days for performance

### Performance Notes
- All-users queries may return large datasets
- Consider pagination for large result sets in the future
- Date filtering improves query performance

---

## 📊 **Common Use Cases**

### Daily Cost Analysis
```bash
# Get user's daily cost breakdown for last 30 days
GET /admin/users/ba5c5db4-d3fb-4ca8-9445-1c221ea502a8/costs

# Get user's daily costs from a specific date to today
GET /admin/users/ba5c5db4-d3fb-4ca8-9445-1c221ea502a8/costs?from_date=2025-09-01

# Get user's daily costs for a specific range
GET /admin/users/ba5c5db4-d3fb-4ca8-9445-1c221ea502a8/costs?from_date=2025-09-01&to_date=2025-09-10
```

### Cost Summary Dashboard
```bash
# Get today's costs for all users
GET /admin/users/costs?from_date=2025-09-10&to_date=2025-09-10

# Get all users' historical costs (admin overview)
GET /admin/users/costs

# Get specific user's historical summary
GET /admin/users/costs?user_id=ba5c5db4-d3fb-4ca8-9445-1c221ea502a8
```

### Cost Investigation & Monitoring
```bash
# Monthly billing calculation
GET /admin/users/costs?user_id=ba5c5db4-d3fb-4ca8-9445-1c221ea502a8&from_date=2025-09-01&to_date=2025-09-30

# Weekly trend analysis (summary)
GET /admin/users/costs?user_id=ba5c5db4-d3fb-4ca8-9445-1c221ea502a8&from_date=2025-09-03&to_date=2025-09-10

# Weekly trend analysis (daily breakdown)
GET /admin/users/ba5c5db4-d3fb-4ca8-9445-1c221ea502a8/costs?from_date=2025-09-03&to_date=2025-09-10
```

---

This documentation covers the **2 actual endpoints** that are currently implemented in the Admin Cost API. For any questions or issues, please refer to the API logs or contact the development team.

**Note:** This API currently handles **registered users only**. Guest user cost tracking is not yet implemented but may be added in future versions.
