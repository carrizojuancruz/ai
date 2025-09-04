# Goal Object Specification

## Complete JSON Schema Documentation

Based on analysis of multiple Goal objects from the tools testing data.

### Root Object Structure

```json
{
  "goal_id": "string (UUID)",
  "user_id": "string (UUID)", 
  "version": "integer",
  "goal": {
    "title": "string",
    "description": "string"
  },
  "category": {
    "value": "string"
  },
  "nature": {
    "value": "string"
  },
  "frequency": {
    "type": "string",
    "specific": "null | object",
    "recurrent": {
      "unit": "string",
      "every": "integer",
      "start_date": "string (ISO datetime)",
      "end_date": "null | string (ISO datetime)",
      "anchors": "null | array"
    }
  },
  "amount": {
    "type": "string",
    "absolute": "null | object",
    "percentage": "null | object"
  },
  "evaluation": {
    "aggregation": "string",
    "direction": "string",
    "rounding": "string",
    "source": "string",
    "affected_categories": "null | array"
  },
  "thresholds": "null | object",
  "reminders": {
    "items": "array"
  },
  "status": {
    "value": "string"
  },
  "progress": "null | object",
  "metadata": "null | object",
  "idempotency_key": "null | string",
  "audit": {
    "created_at": "string (ISO datetime)",
    "updated_at": "string (ISO datetime)"
  }
}
```

### Field Descriptions

#### Core Identification
- **goal_id**: UUID string identifier for the goal (e.g., "90d81e9d-05be-4fdf-bd77-9ddf4ff29bac")
- **user_id**: UUID string identifier for the user (e.g., "3eac201d-36c2-4d7e-a9ac-07fe2b5c47e4")
- **version**: Integer version number, increments on updates (1, 2, 3, etc.)

#### Goal Definition
- **goal.title**: Short descriptive title (e.g., "Save 20% of Income", "Japan Travel Fund")
- **goal.description**: Longer description (e.g., "Recurring goal to save 20% of income", "Saving for a trip to Japan")

#### Categorization
- **category.value**: Goal category type
  - Observed values: "saving"
  - Likely values: "saving", "spending", "investment", etc.

- **nature.value**: Goal nature/direction
  - Observed values: "increase"
  - Likely values: "increase", "decrease", "maintain"

#### Frequency Configuration
- **frequency.type**: Frequency type
  - Observed values: "recurrent"
  - Likely values: "recurrent", "one-time", "specific"

- **frequency.specific**: Configuration for specific date goals (null when type is "recurrent")

- **frequency.recurrent**: Configuration for recurring goals
  - **unit**: Time unit ("month", "week", "day", "year")
  - **every**: Interval multiplier (1 = every unit, 2 = every 2 units, etc.)
  - **start_date**: ISO datetime string for when goal starts
  - **end_date**: ISO datetime string for when goal ends (null for indefinite)
  - **anchors**: Additional timing constraints (null in observed data)

#### Amount Configuration
- **amount.type**: Amount calculation method
  - Observed values: "percentage", "absolute"

- **amount.absolute**: For fixed amount goals
  ```json
  {
    "currency": "USD",
    "target": "3000"
  }
  ```

- **amount.percentage**: For percentage-based goals
  ```json
  {
    "target_pct": "20",
    "of": {
      "income": null
    }
  }
  ```

#### Evaluation Settings
- **evaluation.aggregation**: How to aggregate progress ("sum", "average", etc.)
- **evaluation.direction**: Comparison operator ("≥", "≤", "=")
- **evaluation.rounding**: Rounding method ("none", "round", etc.)
- **evaluation.source**: Data source ("linked_accounts", "manual", etc.)
- **evaluation.affected_categories**: Categories to include/exclude (null in observed data)

#### Thresholds
Can be null or object with warning configurations:
```json
{
  "warn_progress_pct": "80",
  "alert_progress_pct": "90", 
  "warn_days_remaining": null
}
```

#### Reminders
- **reminders.items**: Array of reminder configurations
  ```json
  [
    {"type": "push", "when": "daily"},
    {"type": "email", "when": "weekly"},
    {"type": "push", "when": "1 week before"},
    {"type": "email", "when": "3 days before"}
  ]
  ```

#### Status and Progress
- **status.value**: Current goal status
  - Observed values: "pending", "deleted"
  - Likely values: "pending", "in_progress", "completed", "paused", "off-track", "deleted"

- **progress**: Progress tracking (null initially)
  ```json
  {
    "current_value": "0",
    "percent_complete": "0", 
    "updated_at": "2025-09-03T11:40:48.790079"
  }
  ```

#### Metadata and Tracking
- **metadata**: Additional custom data (null in observed data)
- **idempotency_key**: For preventing duplicate operations (null in observed data)

#### Audit Trail
- **audit.created_at**: ISO datetime when goal was created
- **audit.updated_at**: ISO datetime when goal was last modified

### State Transitions

Based on observed data, goals follow this lifecycle:
1. **Created**: status = "pending", version = 1, progress = null
2. **Updated**: version increments, updated_at changes
3. **Activated**: status changes from "pending" to "in_progress" 
4. **Progress Calculated**: progress object populated
5. **Off-track**: status = "off-track" when goal exceeds thresholds or negative progress
6. **Completed**: status = "completed" when goal target is reached
7. **Deleted**: status = "deleted" (soft delete)

### Validation Rules

1. **goal_id** and **user_id** must be valid UUIDs
2. **version** must be positive integer, increments on updates
3. **frequency.recurrent.start_date** must be valid ISO datetime
4. **amount.type** determines which amount sub-object is populated
5. **status.value** controls goal visibility and behavior
6. **audit.updated_at** must be updated on any modification
7. Only one of **amount.absolute** or **amount.percentage** should be populated based