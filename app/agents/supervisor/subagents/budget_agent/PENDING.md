# Budget Agent — External CRUD API Requirements

This document defines the minimum endpoints and contracts required for the external team to implement the Budget API. Currently, the subagent uses in-memory persistence; this API will replace that layer.

## Principles
- Currency: USD (no conversion).
- One active budget per `user_id` with no date overlap.
- Standard errors: `{ code: string, message: string, cause?: string }`.
- Idempotency in `POST` with `Idempotency-Key` header.
- Authentication: `Authorization: Bearer <token>`.

## Endpoints

1) GET /users/{userId}/budgets/active
- 200 → `Budget`
- 404 → `{ code: "NOT_FOUND", message: "No active budget found for user" }`

2) POST /users/{userId}/budgets
- Headers: `Idempotency-Key` (optional)
- Body: `CreateBudgetRequest`
- 201 → `Budget`
- 409 → `{ code: "BUDGET_ALREADY_EXISTS", message: "Active budget already exists" }`

3) PATCH /users/{userId}/budgets/{budgetId}
- Headers: `If-Match: <version>` (optional)
- Body: `UpdateBudgetRequest`
- 200 → `Budget`
- 404 → `{ code: "NOT_FOUND", ... }`
- 409 → `{ code: "VERSION_CONFLICT", ... }`

4) DELETE /users/{userId}/budgets/{budgetId}
- 200 → `Budget` (with `status != ACTIVE` and `is_active=false`)
- 404 → `{ code: "NOT_FOUND", ... }`

## Models (JSON)

Budget (response):
```json
{
  "budget_id": "uuid",
  "user_id": "uuid",
  "version": 2,
  "budget_name": "string",
  "category_limits": {
    "dining": { "amount": 500.00, "hard_cap": true, "alert_thresholds": [0.8, 1.0], "notes": "string" },
    "groceries": { "amount": 800.00, "hard_cap": true }
  },
  "since": "2025-10-01T00:00:00Z",
  "until": "2025-10-31T23:59:59Z",
  "is_active": true,
  "status": "ACTIVE",
  "currency_code": "USD",
  "timezone": "America/New_York",
  "schema_version": 1,
  "metadata": { "source": "agent" },
  "idempotency_key": "optional-string",
  "created_at": "2025-09-01T12:00:00Z",
  "updated_at": "2025-09-15T08:30:00Z"
}
```

CreateBudgetRequest:
```json
{
  "budget_name": "string",
  "category_limits": {
    "dining": { "amount": 500.00, "hard_cap": true },
    "groceries": { "amount": 800.00 }
  },
  "since": "2025-10-01T00:00:00Z",
  "until": "2025-10-31T23:59:59Z",
  "timezone": "America/New_York",
  "metadata": { "string": "string" },
  "idempotency_key": "optional-string"
}
```

UpdateBudgetRequest (partial):
```json
{
  "budget_name": "string",
  "category_limits": {
    "dining": { "amount": 600.00, "hard_cap": true },
    "groceries": { "amount": 750.00 }
  },
  "since": "2025-11-01T00:00:00Z",
  "until": "2025-11-30T23:59:59Z",
  "timezone": "America/Los_Angeles",
  "metadata": { "updated_by": "agent" }
}
```

CategoryLimit:
```json
{
  "amount": 500.00,
  "hard_cap": true,
  "alert_thresholds": [0.8, 1.0],
  "notes": "string"
}
```

Error:
```json
{ "code": "NOT_FOUND", "message": "No active budget found for user", "cause": "optional string" }
```

## Validations
- Valid categories (exact): dining, groceries, housing, transport, entertainment, healthcare, utilities, education, travel, other.
- `until > since`.
- One `ACTIVE` per user; 409 in `POST` if already exists.
- `amount` decimal (2 decimal places) and `>= 0`.
- Optimistic concurrency (if applicable): compare `version` and return 409 `VERSION_CONFLICT` if mismatch.

## Security
- `Authorization: Bearer <token>` and subject/permission authorization.

## Idempotency
- Respect `Idempotency-Key` in `POST` and return the same previous result if repeated.

## Pending for external team
- Implement the 4 endpoints.
- Define storage with uniqueness (1 `ACTIVE` per `user_id` and period without overlap).
- Implement validations.
- Support `Idempotency-Key` and `If-Match`.
- Agree on authentication contract and scopes.
- Ensure decimal precision.
