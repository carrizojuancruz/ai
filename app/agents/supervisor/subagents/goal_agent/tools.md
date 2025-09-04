## Create Goal Tool

### Prompt:
```
Create me a goal to save 20% of my incomes, use the goal_agent and the create_goal tool, the user UUID is: 3eac201d-36c2-4d7e-a9ac-07fe2b5c47e4
```
---

<details>
    <summary>Raw Data</summary>

    ```json
    {
        "goal_id": "90d81e9d-05be-4fdf-bd77-9ddf4ff29bac",
        "user_id": "3eac201d-36c2-4d7e-a9ac-07fe2b5c47e4",
        "version": 1,
        "goal": {
            "title": "Save 20% of Income",
            "description": "Recurring goal to save 20% of income"
        },
        "category": { "value": "saving" },
        "nature": { "value": "increase" },
        "frequency": {
            "type": "recurrent",
            "recurrent": {
                "unit": "month",
                "every": 1,
                "start_date": "2023-06-01T00:00:00Z"
            }
        },
        "amount": {
            "type": "percentage",
            "percentage": { "target_pct": "20", "of": { "income": null } }
        },
        "evaluation": {
            "aggregation": "sum",
            "direction": "≥",
            "rounding": "none",
            "source": "linked_accounts"
        },
        "thresholds": {
            "warn_progress_pct": "80",
            "alert_progress_pct": "90"
        },
        "reminders": {
            "items": [
                { "type": "push", "when": "1 week before" },
                { "type": "email", "when": "3 days before" }
            ]
        },
        "status": { "value": "pending" },
        "audit": {
            "created_at": "2025-09-03T10:39:47.549643",
            "updated_at": "2025-09-03T10:39:47.549645"
        }
    }
    ```
</details>


## Update Goal Tool

### Prompt:
```
Update the goal and make me a reminder every day with mail and push. GOAL UUID: 90d81e9d-05be-4fdf-bd77-9ddf4ff29bac USER UUID: 3eac201d-36c2-4d7e-a9ac-07fe2b5c47e4
```
---

<details>
    <summary>Raw Data</summary>

    ```json
    {
    "goal_id": "90d81e9d-05be-4fdf-bd77-9ddf4ff29bac",
    "user_id": "3eac201d-36c2-4d7e-a9ac-07fe2b5c47e4",
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
    "thresholds": {
        "warn_progress_pct": "80",
        "alert_progress_pct": "90",
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
            "when": "3 days before"
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
        "created_at": "2025-09-03T10:39:47.549643",
        "updated_at": "2025-09-03T10:39:47.549645"
    }
    }

    ```
</details>


## Get Goal Tool

### Prompt:
```
Update the goal and make me a reminder every day with mail and push. GOAL UUID: 90d81e9d-05be-4fdf-bd77-9ddf4ff29bac USER UUID: 3eac201d-36c2-4d7e-a9ac-07fe2b5c47e4
```
---

<details>
    <summary>Raw Data</summary>

    ```json
    {
    "goal_id": "90d81e9d-05be-4fdf-bd77-9ddf4ff29bac",
    "user_id": "3eac201d-36c2-4d7e-a9ac-07fe2b5c47e4",
    "version": 2,
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
    "thresholds": {
        "warn_progress_pct": "80",
        "alert_progress_pct": "90",
        "warn_days_remaining": null
    },
    "reminders": {
        "items": [
        {
            "type": "push",
            "when": "daily"
        },
        {
            "type": "email",
            "when": "daily"
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
        "created_at": "2025-09-03T10:39:47.549643",
        "updated_at": "2025-09-03T10:46:38.760459"
    }
    }
    ```
</details>

## Delete Goals Tool

### Prompt:
```
Delete my goal. GOAL UUID: 90d81e9d-05be-4fdf-bd77-9ddf4ff29bac USER UUID: 3eac201d-36c2-4d7e-a9ac-07fe2b5c47e4
```

<details>
    <summary>Raw Data</summary>

    ```json
    {
        "goal_id": "90d81e9d-05be-4fdf-bd77-9ddf4ff29bac",
        "user_id": "3eac201d-36c2-4d7e-a9ac-07fe2b5c47e4",
        "version": 2,
        "goal": {
            "title": "Save 20% of Income",
            "description": "Recurring goal to save 20% of income"
        },
        "category": { "value": "saving" },
        "nature": { "value": "increase" },
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
                "of": { "income": null }
            }
        },
        "evaluation": {
            "aggregation": "sum",
            "direction": "≥",
            "rounding": "none",
            "source": "linked_accounts",
            "affected_categories": null
        },
        "thresholds": {
            "warn_progress_pct": "80",
            "alert_progress_pct": "90",
            "warn_days_remaining": null
        },
        "reminders": {
            "items": [
                { "type": "push", "when": "daily" },
                { "type": "email", "when": "daily" }
            ]
        },
        "status": { "value": "deleted" },
        "progress": null,
        "metadata": null,
        "idempotency_key": null,
        "audit": {
            "created_at": "2025-09-03T10:39:47.549643",
            "updated_at": "2025-09-03T11:38:47.903003"
        }
    }
    ```
<details>
