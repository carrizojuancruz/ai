# Vera — Agent Developer Stories with Expected JSON I/O (Goals V1)

---

## DEV-US-1 — Create a goal (agent → `create_goal`)
Prompt:
```
Create me a goal to save 20% of my incomes, user uuid: 86712140-17df-45dd-8ce6-b56f566d38f4
```
### Expected Output Goal (success)
```json
{
  "goal_id": "8faebf58-eab3-4333-8cc0-579d5c218230",
  "user_id": "5cc952df-51a4-4db4-b012-f450ee6317a4",
  "version": 1,
  "goal": {
    "title": "Save 20% of Income",
    "description": "Recurring goal to save 20% of income"
  },
  "category": {
    "value": "saving"
  },
  "nature": {
    "value": "increase"
  },
  "frequency": {
    "type": "recurrent",
    "specific": null,
    "recurrent": {
      "unit": "month",
      "every": 1,
      "start_date": "2023-06-01T00:00:00Z",
      "end_date": null,
      "anchors": null
    }
  },
  "amount": {
    "type": "percentage",
    "absolute": null,
    "percentage": {
      "target_pct": "20",
      "of": {
        "income": null
      }
    }
  },
  "evaluation": {
    "aggregation": "sum",
    "direction": "≥",
    "rounding": "none",
    "source": "linked_accounts",
    "affected_categories": null
  },
  "thresholds": null,
  "reminders": null,
  "status": {
    "value": "pending"
  },
  "progress": null,
  "metadata": null,
  "idempotency_key": null,
  "audit": {
    "created_at": "2025-09-04T15:59:20.026369",
    "updated_at": "2025-09-04T15:59:20.026375"
  }
}
```

## DEV-US-2 — Update a goal (agent → `update_goal`)
Prompt:
```
Update the goal to save 50% of my incomes, user uuid: 86712140-17df-45dd-8ce6-b56f566d38f4, goal uuid: 8faebf58-eab3-4333-8cc0-579d5c218230
```

### Expected Output Goal (success)
```json
{
  "goal_id": "8faebf58-eab3-4333-8cc0-579d5c218230",
  "user_id": "5cc952df-51a4-4db4-b012-f450ee6317a4",
  "version": 2,
  "goal": {
    "title": "Save 50% of Income",
    "description": "Recurring goal to save 50% of income"
  },
  "category": {
    "value": "saving"
  },
  "nature": {
    "value": "increase"
  },
  "frequency": {
    "type": "recurrent",
    "specific": null,
    "recurrent": {
      "unit": "month",
      "every": 1,
      "start_date": "2023-06-01T00:00:00Z",
      "end_date": null,
      "anchors": null
    }
  },
  "amount": {
    "type": "percentage",
    "absolute": null,
    "percentage": {
      "target_pct": "50",
      "of": {
        "income": null
      }
    }
  },
  "evaluation": {
    "aggregation": "sum",
    "direction": "≥",
    "rounding": "none",
    "source": "linked_accounts",
    "affected_categories": null
  },
  "thresholds": null,
  "reminders": null,
  "status": {
    "value": "pending"
  },
  "progress": null,
  "metadata": null,
  "idempotency_key": null,
  "audit": {
    "created_at": "2025-09-04T15:59:20.026369",
    "updated_at": "2025-09-04T16:03:50.345986"
  }
}
```

## DEV-US-3 — List all goals (agent → `list_goals`)
Prompt:
```
Please list all my goals, user uuid: 86712140-17df-45dd-8ce6-b56f566d38f4
```
### Expected Output Goal (success)
```json
[
  {
    "goal_id": "8faebf58-eab3-4333-8cc0-579d5c218230",
    "user_id": "5cc952df-51a4-4db4-b012-f450ee6317a4",
    "version": 1,
    "goal": {
      "title": "Save 20% of Income",
      "description": "Recurring goal to save 20% of income"
    },
    "category": {
      "value": "saving"
    },
    "nature": {
      "value": "increase"
    },
    "frequency": {
      "type": "recurrent",
      "specific": null,
      "recurrent": {
        "unit": "month",
        "every": 1,
        "start_date": "2023-06-01T00:00:00Z",
        "end_date": null,
        "anchors": null
      }
    },
    "amount": {
      "type": "percentage",
      "absolute": null,
      "percentage": {
        "target_pct": "20",
        "of": {
          "income": null
        }
      }
    },
    "evaluation": {
      "aggregation": "sum",
      "direction": "≥",
      "rounding": "none",
      "source": "linked_accounts",
      "affected_categories": null
    },
    "thresholds": null,
    "reminders": null,
    "status": {
      "value": "pending"
    },
    "progress": null,
    "metadata": null,
    "idempotency_key": null,
    "audit": {
      "created_at": "2025-09-04T15:59:20.026369",
      "updated_at": "2025-09-04T15:59:20.026375"
    }
  },
  {
    "goal_id": "8faebf58-eab3-4333-8cc0-579d5c218230",
    "user_id": "5cc952df-51a4-4db4-b012-f450ee6317a4",
    "version": 1,
    "goal": {
      "title": "Save 20% of Income",
      "description": "Recurring goal to save 20% of income"
    },
    "category": {
      "value": "saving"
    },
    "nature": {
      "value": "increase"
    },
    "frequency": {
      "type": "recurrent",
      "specific": null,
      "recurrent": {
        "unit": "month",
        "every": 1,
        "start_date": "2023-06-01T00:00:00Z",
        "end_date": null,
        "anchors": null
      }
    },
    "amount": {
      "type": "percentage",
      "absolute": null,
      "percentage": {
        "target_pct": "20",
        "of": {
          "income": null
        }
      }
    },
    "evaluation": {
      "aggregation": "sum",
      "direction": "≥",
      "rounding": "none",
      "source": "linked_accounts",
      "affected_categories": null
    },
    "thresholds": null,
    "reminders": null,
    "status": {
      "value": "pending"
    },
    "progress": null,
    "metadata": null,
    "idempotency_key": null,
    "audit": {
      "created_at": "2025-09-04T15:59:20.026369",
      "updated_at": "2025-09-04T15:59:20.026375"
    }
  },
  {
    "goal_id": "1cb59976-3b41-4e62-b4c8-7483c22fd059",
    "user_id": "5cc952df-51a4-4db4-b012-f450ee6317a4",
    "version": 1,
    "goal": {
      "title": "Acquire $40,000",
      "description": "Save up $40,000 for future financial security"
    },
    "category": {
      "value": "saving"
    },
    "nature": {
      "value": "increase"
    },
    "frequency": {
      "type": "recurrent",
      "specific": null,
      "recurrent": {
        "unit": "month",
        "every": 1,
        "start_date": "2023-06-01T00:00:00Z",
        "end_date": null,
        "anchors": null
      }
    },
    "amount": {
      "type": "absolute",
      "absolute": {
        "currency": "USD",
        "target": "40000"
      },
      "percentage": null
    },
    "evaluation": {
      "aggregation": "sum",
      "direction": "≥",
      "rounding": "none",
      "source": "linked_accounts",
      "affected_categories": null
    },
    "thresholds": {
      "warn_progress_pct": "25",
      "alert_progress_pct": "10",
      "warn_days_remaining": null
    },
    "reminders": {
      "items": [
        {
          "type": "push",
          "when": "monthly"
        }
      ]
    },
    "status": {
      "value": "pending"
    },
    "progress": null,
    "metadata": null,
    "idempotency_key": null,
    "audit": {
      "created_at": "2025-09-04T16:07:52.650591",
      "updated_at": "2025-09-04T16:07:52.650595"
    }
  }
]
```

## DEV-US-4 — Update a goal (agent → `get_in_progress_goal`)
Prompt:
```
I want to know my in progress goals, user uuid: 2a4ea2a1-de4b-477c-9b23-5111fb0cca78
```
### Expected Output Goal (success)
```json
[
  {
    "goal_id": "6f1f5353-15c6-4b8f-b546-f94a6478b48c",
    "user_id": "ab6dd8fe-f7a2-47a4-b540-fc5fc94943aa",
    "version": 2,
    "goal": {
      "title": "Save 20% of Income",
      "description": null
    },
    "category": {
      "value": "saving"
    },
    "nature": {
      "value": "increase"
    },
    "frequency": {
      "type": "recurrent",
      "specific": null,
      "recurrent": {
        "unit": "month",
        "every": 1,
        "start_date": "2023-06-01T00:00:00Z",
        "end_date": null,
        "anchors": null
      }
    },
    "amount": {
      "type": "percentage",
      "absolute": null,
      "percentage": {
        "target_pct": "20",
        "of": {
          "income": null
        }
      }
    },
    "evaluation": {
      "aggregation": "sum",
      "direction": "≤",
      "rounding": "none",
      "source": "mixed",
      "affected_categories": null
    },
    "thresholds": {
      "warn_progress_pct": "50",
      "alert_progress_pct": "25",
      "warn_days_remaining": null
    },
    "reminders": {
      "items": [
        {
          "type": "push",
          "when": "1 week before"
        },
        {
          "type": "email",
          "when": "1 day before"
        }
      ]
    },
    "status": {
      "value": "in_progress"
    },
    "progress": null,
    "metadata": null,
    "idempotency_key": null,
    "audit": {
      "created_at": "2025-09-04T16:37:41.952861",
      "updated_at": "2025-09-04T16:40:03.518409"
    }
  }
]
```

## DEV-US-5 — Update a goal (agent → `delete_goal`)
Prompt:
```
Update the goal to save 50% of my incomes, user uuid: 86712140-17df-45dd-8ce6-b56f566d38f4, goal uuid: 8faebf58-eab3-4333-8cc0-579d5c218230
```

### Expected Output Goal (success)
```json

```