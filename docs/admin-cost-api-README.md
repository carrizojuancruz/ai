# Admin Cost API Documentation

This document provides comprehensive documentation for the Verde AI Admin Cost API endpoints.

## Overview

Admin Cost API provides cost analytics for **registered users and guest users**. The API implements **3 core endpoints** that cover all cost analysis needs with a clean, consistent structure.

### 🎯 **Available Endpoints**

1. **`GET /admin/users/total-costs`** - Aggregated cost summaries across all users
2. **`GET /admin/users/daily-costs`** - Daily costs grouped by user (Structure B format)
3. **`GET /admin/users/guest/costs`** - Guest user cost analytics

## Base URL

```
http://localhost:8000
```

## Authentication

⚠️ **No authentication is currently implemented.** These endpoints are open for development/testing purposes.

---

## 📊 **Endpoint 1: Total Costs Summary**

### `GET /admin/users/total-costs`

**Description:** Returns aggregated cost summaries for all registered users. Provides high-level overview with essential fields only.

**Parameters:**
- `from_date` (query): Optional. Start date for range (YYYY-MM-DD)
- `to_date` (query): Optional. End date for range (YYYY-MM-DD)
- `user_id` (query): Optional. Filter by specific user ID

**Date Range Logic:**
- **No params**: Last 30 days for all users
- **user_id only**: Last 30 days for specific user
- **from_date only**: From that date to today
- **Both dates**: From from_date to to_date

**Always returns `List[AdminCostSummary]` with fields: user_id, total_cost, trace_count.**

#### Use Case 1: All Users Total Costs (Last 30 Days)
**Purpose:** Admin dashboard overview
```bash
GET /admin/users/total-costs
```

**Expected Response:**
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

#### Use Case 2: Specific User Total Costs
```bash
GET /admin/users/total-costs?user_id=ba5c5db4-d3fb-4ca8-9445-1c221ea502a8
```

#### Use Case 3: All Users for Date Range
```bash
GET /admin/users/total-costs?from_date=2025-09-01&to_date=2025-09-10
```

---

## 📅 **Endpoint 2: Daily Costs Breakdown (Structure B)**

### `GET /admin/users/daily-costs`

**Description:** Returns daily costs grouped by user in Structure B format. Each user has their daily costs grouped together for easy analysis.

**Parameters:**
- `user_id` (query): Optional. Filter by specific user ID
- `from_date` (query): Optional. Start date for range (YYYY-MM-DD)
- `to_date` (query): Optional. End date for range (YYYY-MM-DD)

**Date Range Logic:**
- **No params**: Last 30 days for all users
- **user_id only**: Last 30 days for specific user
- **from_date only**: From that date to today
- **Both dates**: From from_date to to_date

**Returns `List[UserDailyCosts]` where each user has their daily costs grouped together.**

#### Use Case 1: All Users Daily Costs (Last 30 Days)
**Purpose:** Complete daily breakdown for all users
```bash
GET /admin/users/daily-costs
```

**Expected Response (Structure B):**
```json
[
  {
    "user_id": "ba5c5db4-d3fb-4ca8-9445-1c221ea502a8",
    "daily_costs": [
      {
        "total_cost": 0.189465,
        "trace_count": 4,
        "date": "2025-09-10"
      },
      {
        "total_cost": 3.464079,
        "trace_count": 36,
        "date": "2025-09-09"
      },
      {
        "total_cost": 2.441913,
        "trace_count": 34,
        "date": "2025-09-08"
      }
    ]
  },
  {
    "user_id": "user2-abc-123",
    "daily_costs": [
      {
        "total_cost": 0.125000,
        "trace_count": 2,
        "date": "2025-09-10"
      }
    ]
  }
]
```

#### Use Case 2: Specific User Daily Costs
**Purpose:** Individual user daily breakdown
```bash
GET /admin/users/daily-costs?user_id=ba5c5db4-d3fb-4ca8-9445-1c221ea502a8
```

**Expected Response:**
```json
[
  {
    "user_id": "ba5c5db4-d3fb-4ca8-9445-1c221ea502a8",
    "daily_costs": [
      {
        "total_cost": 0.189465,
        "trace_count": 4,
        "date": "2025-09-10"
      },
      {
        "total_cost": 3.464079,
        "trace_count": 36,
        "date": "2025-09-09"
      }
    ]
  }
]
```

#### Use Case 3: Date Range for All Users
```bash
GET /admin/users/daily-costs?from_date=2025-09-08&to_date=2025-09-10
```

---

## 👤 **Endpoint 3: Guest User Costs**

### `GET /admin/users/guest/costs`

**Description:** Returns cost analytics for guest users (users without user_id). Uses the 'verde-money-onboarding-agent' Langfuse project.

**Parameters:**
- `from_date` (query): Optional. Start date for range (YYYY-MM-DD)
- `to_date` (query): Optional. End date for range (YYYY-MM-DD)

**Date Range Logic:**
- **No params**: Last 30 days
- **from_date only**: From that date to today
- **Both dates**: From from_date to to_date

**Returns `GuestCostSummary` with simplified fields: total_cost, trace_count.**

#### Example: Guest Costs for Today
```bash
GET /admin/users/guest/costs?from_date=2025-09-11&to_date=2025-09-11
```

**Expected Response:**
```json
{
  "total_cost": 1.25,
  "trace_count": 15
}
```

#### Example: Guest Costs (Last 30 Days)
```bash
GET /admin/users/guest/costs
```

---

## 📋 **Data Models**

### AdminCostSummary
Used by `/admin/users/total-costs` endpoint.
```json
{
  "user_id": "string",
  "total_cost": 0.0,
  "trace_count": 0
}
```

### UserDailyCosts
Used by `/admin/users/daily-costs` endpoint (Structure B).
```json
{
  "user_id": "string",
  "daily_costs": [
    {
      "total_cost": 0.0,
      "trace_count": 0,
      "date": "YYYY-MM-DD"
    }
  ]
}
```

### DailyCostFields
Individual daily cost entry within UserDailyCosts.
```json
{
  "total_cost": 0.0,
  "trace_count": 0,
  "date": "YYYY-MM-DD"
}
```

### GuestCostSummary
Used by `/admin/users/guest/costs` endpoint.
```json
{
  "total_cost": 0.0,
  "trace_count": 0
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
  "detail": "Failed to fetch total costs: <error_message>"
}
```

---

## 🧪 **Testing Examples**

### Complete Test Suite
```bash
# Total costs endpoint
curl "http://localhost:8000/admin/users/total-costs"
curl "http://localhost:8000/admin/users/total-costs?user_id=ba5c5db4-d3fb-4ca8-9445-1c221ea502a8"
curl "http://localhost:8000/admin/users/total-costs?from_date=2025-09-10&to_date=2025-09-10"

# Daily costs endpoint (Structure B)
curl "http://localhost:8000/admin/users/daily-costs"
curl "http://localhost:8000/admin/users/daily-costs?user_id=ba5c5db4-d3fb-4ca8-9445-1c221ea502a8"
curl "http://localhost:8000/admin/users/daily-costs?from_date=2025-09-08&to_date=2025-09-10"

# Guest costs endpoint
curl "http://localhost:8000/admin/users/guest/costs"
curl "http://localhost:8000/admin/users/guest/costs?from_date=2025-09-11&to_date=2025-09-11"
```

### PowerShell Test Script
```powershell
# Set base URL
$baseUrl = "http://localhost:8000"
$userId = "ba5c5db4-d3fb-4ca8-9445-1c221ea502a8"

Write-Output "=== Testing Admin Cost API ==="

# Test total costs endpoint
Write-Output "`n--- Total Costs Endpoint ---"

# All users total costs (last 30 days)
$response = Invoke-WebRequest -Uri "$baseUrl/admin/users/total-costs" -Method GET
$response.Content | ConvertFrom-Json | ConvertTo-Json

# Specific user total costs
$response = Invoke-WebRequest -Uri "$baseUrl/admin/users/total-costs?user_id=$userId" -Method GET
$response.Content | ConvertFrom-Json | ConvertTo-Json

# Test daily costs endpoint (Structure B)
Write-Output "`n--- Daily Costs Endpoint (Structure B) ---"

# All users daily costs
$response = Invoke-WebRequest -Uri "$baseUrl/admin/users/daily-costs" -Method GET
$response.Content | ConvertFrom-Json | ConvertTo-Json

# Specific user daily costs
$response = Invoke-WebRequest -Uri "$baseUrl/admin/users/daily-costs?user_id=$userId" -Method GET
$response.Content | ConvertFrom-Json | ConvertTo-Json

# Test guest costs endpoint
Write-Output "`n--- Guest Costs Endpoint ---"

# Guest costs (last 30 days)
$response = Invoke-WebRequest -Uri "$baseUrl/admin/users/guest/costs" -Method GET
$response.Content | ConvertFrom-Json | ConvertTo-Json

# Guest costs for today
$response = Invoke-WebRequest -Uri "$baseUrl/admin/users/guest/costs?from_date=2025-09-11&to_date=2025-09-11" -Method GET
$response.Content | ConvertFrom-Json | ConvertTo-Json
```

---

## 🎯 **Best Practices**

### 1. Endpoint Selection
- **High-level overview**: Use `/total-costs` for dashboard summaries
- **Detailed analysis**: Use `/daily-costs` for day-by-day breakdown
- **Guest analytics**: Use `/guest/costs` for anonymous user tracking
- **Structure B benefits**: Daily costs grouped by user for easier processing

### 2. Parameter Usage
- **Historical data**: No date parameters for last 30 days default
- **Single date**: Set `from_date=to_date` for specific day analysis
- **Date ranges**: Use both parameters for period analysis
- **User filtering**: Add `user_id` parameter for individual user focus

### 3. Performance Considerations
- **Large datasets**: Structure B format reduces response complexity
- **Date ranges**: Limit ranges to reasonable periods (≤ 30 days)
- **Single user queries**: Generally faster when focusing on specific users

### 4. Error Handling
- Always handle HTTP 422 for validation errors
- Implement retry logic for HTTP 500 errors
- Validate date formats client-side before sending

---

## 🔧 **Configuration**

### Time Windows
- **Default range**: Last 30 days for all endpoints
- **Date ranges**: Recommended maximum of 30 days for performance
- **Guest tracking**: Uses 'verde-money-onboarding-agent' Langfuse project

### Langfuse Projects
- **Registered users**: Uses supervisor Langfuse project
- **Guest users**: Uses 'verde-money-onboarding-agent' project
- **Project isolation**: Separate tracking for different user types

---

## 📊 **Common Use Cases**

### Dashboard Analytics
```bash
# Admin overview - total costs across all users
GET /admin/users/total-costs

# Guest usage tracking
GET /admin/users/guest/costs
```

### Detailed Cost Analysis
```bash
# Daily breakdown for all users (Structure B)
GET /admin/users/daily-costs

# Individual user daily analysis
GET /admin/users/daily-costs?user_id=ba5c5db4-d3fb-4ca8-9445-1c221ea502a8
```

### Billing & Monitoring
```bash
# Monthly billing calculation (total)
GET /admin/users/total-costs?user_id=ba5c5db4-d3fb-4ca8-9445-1c221ea502a8&from_date=2025-09-01&to_date=2025-09-30

# Monthly billing calculation (daily breakdown)
GET /admin/users/daily-costs?user_id=ba5c5db4-d3fb-4ca8-9445-1c221ea502a8&from_date=2025-09-01&to_date=2025-09-30

# Today's activity across all users
GET /admin/users/total-costs?from_date=2025-09-11&to_date=2025-09-11
GET /admin/users/daily-costs?from_date=2025-09-11&to_date=2025-09-11
```

---

This documentation covers the **3 current endpoints** implemented in the Admin Cost API. The API now supports both registered and guest user cost tracking with a clean, consistent interface.

**Key Features:**
- ✅ **Structure B format** for daily costs (grouped by user)
- ✅ **Guest user tracking** with dedicated endpoint
- ✅ **Consistent date handling** across all endpoints
- ✅ **Simplified response models** with essential fields only
- ✅ **30-day default ranges** for optimal performance
