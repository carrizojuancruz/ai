# Goal Agent — External Goals API Requirements

This document defines the minimum endpoints and contracts required for the external team to implement the Goals API (Goals System V1). Currently, the subagent uses in-memory persistence; this API will replace that layer.

## Principles
- Currency: USD (no conversion).
- Multiple goals per user with different states and categories.
- Standard errors: `{ code: string, message: string, cause?: string }`.
- Idempotency in `POST` with `Idempotency-Key` header.
- Authentication: `Authorization: Bearer <token>`.
- State transitions: pending → in_progress → completed/error, with soft delete support.

## Endpoints

1) GET /users/{userId}/goals
- 200 → `List[Goal]`
- 404 → `{ code: "NOT_FOUND", message: "No goals found for user" }`

2) GET /users/{userId}/goals/{goalId}
- 200 → `Goal`
- 404 → `{ code: "NOT_FOUND", message: "Goal not found" }`

3) GET /users/{userId}/goals/status/{status}
- 200 → `List[Goal]` (filtered by status)
- 404 → `{ code: "NOT_FOUND", message: "No goals found with status" }`

4) POST /users/{userId}/goals
- Headers: `Idempotency-Key` (optional)
- Body: `CreateGoalRequest`
- 201 → `Goal`
- 400 → `{ code: "VALIDATION_ERROR", message: "Invalid goal configuration" }`

5) PATCH /users/{userId}/goals/{goalId}
- Headers: `If-Match: <version>` (optional)
- Body: `UpdateGoalRequest`
- 200 → `Goal`
- 404 → `{ code: "NOT_FOUND", ... }`
- 409 → `{ code: "VERSION_CONFLICT", ... }`

6) DELETE /users/{userId}/goals/{goalId}
- 200 → `Goal` (with `status = "deleted"`)
- 404 → `{ code: "NOT_FOUND", ... }`

7) POST /users/{userId}/goals/{goalId}/progress
- Body: `CalculateProgressRequest`
- 200 → `Goal` (with updated progress)
- 404 → `{ code: "NOT_FOUND", ... }`

8) POST /users/{userId}/goals/{goalId}/transitions
- Body: `StateTransitionRequest`
- 200 → `Goal` (with updated status)
- 400 → `{ code: "INVALID_TRANSITION", message: "Invalid state transition" }`

## Models (JSON)

Goal (response):
```json
{
  "goal_id": "uuid",
  "user_id": "uuid",
  "version": 2,
  "goal": {
    "title": "Emergency Fund Building",
    "description": "Build 6-month emergency fund"
  },
  "category": { "value": "saving" },
  "nature": { "value": "increase" },
  "frequency": {
    "type": "recurrent",
    "recurrent": {
      "unit": "month",
      "every": 1,
      "start_date": "2024-01-01T00:00:00Z"
    }
  },
  "amount": {
    "type": "absolute",
    "absolute": {
      "currency": "USD",
      "target": 500.00
    }
  },
  "evaluation": {
    "aggregation": "sum",
    "direction": "≥",
    "source": "mixed",
    "affected_categories": ["income", "manual_expenses"]
  },
  "thresholds": {
    "warn_progress_pct": 75.0,
    "warn_days_remaining": 7
  },
  "reminders": {
    "items": [
      {
        "type": "push",
        "when": "monthly:day=15"
      }
    ]
  },
  "status": { "value": "in_progress" },
  "progress": {
    "current_value": 375.00,
    "percent_complete": 75.0,
    "updated_at": "2024-02-15T08:30:00Z"
  },
  "metadata": { "source": "agent" },
  "idempotency_key": "optional-string",
  "audit": {
    "created_at": "2024-01-01T12:00:00Z",
    "updated_at": "2024-02-15T08:30:00Z"
  }
}
```

CreateGoalRequest:
```json
{
  "goal": {
    "title": "string",
    "description": "string"
  },
  "category": { "value": "saving" },
  "nature": { "value": "increase" },
  "frequency": {
    "type": "recurrent",
    "recurrent": {
      "unit": "month",
      "every": 1,
      "start_date": "2024-01-01T00:00:00Z"
    }
  },
  "amount": {
    "type": "absolute",
    "absolute": {
      "currency": "USD",
      "target": 500.00
    }
  },
  "evaluation": {
    "source": "mixed",
    "affected_categories": ["entertainment"]
  },
  "thresholds": {
    "warn_progress_pct": 80.0
  },
  "metadata": { "string": "string" },
  "idempotency_key": "optional-string"
}
```

UpdateGoalRequest (partial):
```json
{
  "goal": {
    "title": "Updated Goal Title"
  },
  "amount": {
    "type": "absolute",
    "absolute": {
      "target": 600.00
    }
  },
  "thresholds": {
    "warn_progress_pct": 85.0
  }
}
```

CalculateProgressRequest:
```json
{
  "force_recalculation": false,
  "data_sources": ["linked_accounts", "manual_input"]
}
```

StateTransitionRequest:
```json
{
  "action": "activate",
  "confirmation": true
}
```

## Validations
- Valid categories: saving, spending, debt, income, investment, net_worth, other.
- Valid natures: increase, reduce.
- Valid statuses: pending, in_progress, completed, error, deleted.
- Frequency validation: specific requires date, recurrent requires unit/every/start_date.
- Amount validation: absolute requires target, percentage requires target_pct and basis.
- State transitions: follow defined rules (pending → in_progress, etc.).
- affected_categories: must be valid Plaid categories if specified.

## State Transitions
- pending → in_progress: Only when configuration complete and confirmed
- in_progress → completed: Automatic when target reached within timeline
- in_progress → error: Automatic when sync failures > 48 hours
- error → in_progress: Automatic when connectivity/data restored
- Any state → deleted: Manual user action (soft delete)
- deleted → in_progress: Manual restore with re-validation

## Security
- `Authorization: Bearer <token>` and subject/permission authorization.
- Goals contain financial PII - encryption at rest mandatory.

## Idempotency
- Respect `Idempotency-Key` in `POST` and return the same previous result if repeated.

## Performance
- in_progress goals cached in memory for low-latency access.
- Progress calculations executed async to avoid blocking.
- State transitions evaluated in real-time for immediate updates.
- Thresholds evaluated daily via scheduled jobs.

## Pending for external team
- Implement the 8 endpoints.
- Define storage with support for multiple goals per user and state management.
- Implement validations and state transition logic.
- Support `Idempotency-Key` and `If-Match`.
- Agree on authentication contract and scopes.
- Ensure decimal precision for monetary amounts.
- Implement progress calculation engine (query transaction data).
- Support for Plaid categories and manual input categorization.
