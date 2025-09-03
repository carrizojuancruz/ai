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

## List Goals Tool

### Prompt:
```
Update the goal and make me a reminder every day with mail and push. GOAL UUID: 90d81e9d-05be-4fdf-bd77-9ddf4ff29bac USER UUID: 3eac201d-36c2-4d7e-a9ac-07fe2b5c47e4
```
<details>
    <summary>Raw Data</summary>

    ```json
    [
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
            "status": { "value": "pending" },
            "progress": null,
            "metadata": null,
            "idempotency_key": null,
            "audit": {
                "created_at": "2025-09-03T10:39:47.549643",
                "updated_at": "2025-09-03T10:46:38.760459"
            }
        },
        {
            "goal_id": "bf4a9f28-e55b-4080-9c86-5edd185a5176",
            "user_id": "3eac201d-36c2-4d7e-a9ac-07fe2b5c47e4",
            "version": 1,
            "goal": {
                "title": "Japan Travel Fund",
                "description": "Saving for a trip to Japan"
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
                "type": "absolute",
                "absolute": {
                    "currency": "USD",
                    "target": "3000"
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
            "thresholds": null,
            "reminders": {
                "items": [
                    { "type": "email", "when": "weekly" }
                ]
            },
            "status": { "value": "pending" },
            "progress": null,
            "metadata": null,
            "idempotency_key": null,
            "audit": {
                "created_at": "2025-09-03T11:32:27.308916",
                "updated_at": "2025-09-03T11:32:27.308918"
            }
        }
    ]
    ```
</details>

### Errors during execution
```
  File "c:\Users\gonza\OneDrive\Escritorio\Codigo\Promtior\fos-ai\.venv\Lib\site-packages\fastapi\routing.py", line 213, in run_endpoint_function
    return await dependant.call(**values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\gonza\OneDrive\Escritorio\Codigo\Promtior\fos-ai\app\api\routes_supervisor.py", line 44, in supervisor_message    
    await supervisor_service.process_message(thread_id=payload.thread_id, text=payload.text)
  File "C:\Users\gonza\OneDrive\Escritorio\Codigo\Promtior\fos-ai\app\services\supervisor.py", line 384, in process_message        
    sources = self._add_source_from_tool_end(sources, name, data)
  File "C:\Users\gonza\OneDrive\Escritorio\Codigo\Promtior\fos-ai\app\services\supervisor.py", line 154, in _add_source_from_tool_end
    content = json.loads(content)
  File "C:\Users\gonza\AppData\Local\Programs\Python\Python313\Lib\json\__init__.py", line 346, in loads
    return _default_decoder.decode(s)
           ~~~~~~~~~~~~~~~~~~~~~~~^^^
  File "C:\Users\gonza\AppData\Local\Programs\Python\Python313\Lib\json\decoder.py", line 345, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
               ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\gonza\AppData\Local\Programs\Python\Python313\Lib\json\decoder.py", line 361, in raw_decode
    obj, end = self.scan_once(s, idx)
               ~~~~~~~~~~~~~~^^^^^^^^
json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 3 (char 2)
2025-09-03T11:32:06-0300 | INFO | app.main | HTTP POST /supervisor/message
2025-09-03T11:32:08-0300 | INFO | app.agents.supervisor.memory.hotpath | memory.decide: should_create=True type=semantic category=Finance importance=4
```

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

## Calculate Progress Tool

### Prompt:
```
Calculate the progress for my goal. GOAL UUID: 90d81e9d-05be-4fdf-bd77-9ddf4ff29bac USER UUID: 3eac201d-36c2-4d7e-a9ac-07fe2b5c47e4
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
        "progress": {
            "current_value": "0",
            "percent_complete": "0",
            "updated_at": "2025-09-03T11:40:48.790079"
        },
        "metadata": null,
        "idempotency_key": null,
        "audit": {
            "created_at": "2025-09-03T10:39:47.549643",
            "updated_at": "2025-09-03T11:38:47.903003"
        }
    }
    ```
<details>


## Handle Binary Choice Tool

### Prompt:
```
Activate my goal. GOAL UUID: 90d81e9d-05be-4fdf-bd77-9ddf4ff29bac USER UUID: 3eac201d-36c2-4d7e-a9ac-07fe2b5c47e4 CHOICE: activate
```
<details>
    <summary>Raw Data</summary>

    ```json
    {
        "goal_id": "90d81e9d-05be-4fdf-bd77-9ddf4ff29bac",
        "user_id": "3eac201d-36c2-4d7e-a9ac-07fe2b5c47e4",
        "version": 3,
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
        "progress": {
            "current_value": "0",
            "percent_complete": "0",
            "updated_at": "2025-09-03T11:40:48.790079"
        },
        "metadata": null,
        "idempotency_key": null,
        "audit": {
            "created_at": "2025-09-03T10:39:47.549643",
            "updated_at": "2025-09-03T11:45:00.000000"
        }
    }
    ```
<details>


## Get Goals By Status Tool

### Prompts:
```
List all my goals. USER UUID: 3eac201d-36c2-4d7e-a9ac-07fe2b5c47e4 STATUS: DELETED
```
```
List all my goals. USER UUID: 3eac201d-36c2-4d7e-a9ac-07fe2b5c47e4 STATUS: pending
```

### Errors
```
  File "c:\Users\gonza\OneDrive\Escritorio\Codigo\Promtior\fos-ai\.venv\Lib\site-packages\fastapi\routing.py", line 213, in run_endpoint_function
    return await dependant.call(**values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\gonza\OneDrive\Escritorio\Codigo\Promtior\fos-ai\app\api\routes_supervisor.py", line 44, in supervisor_message    
    await supervisor_service.process_message(thread_id=payload.thread_id, text=payload.text)
  File "C:\Users\gonza\OneDrive\Escritorio\Codigo\Promtior\fos-ai\app\services\supervisor.py", line 384, in process_message        
    sources = self._add_source_from_tool_end(sources, name, data)
  File "C:\Users\gonza\OneDrive\Escritorio\Codigo\Promtior\fos-ai\app\services\supervisor.py", line 154, in _add_source_from_tool_end
    content = json.loads(content)
  File "C:\Users\gonza\AppData\Local\Programs\Python\Python313\Lib\json\__init__.py", line 346, in loads
    return _default_decoder.decode(s)
           ~~~~~~~~~~~~~~~~~~~~~~~^^^
  File "C:\Users\gonza\AppData\Local\Programs\Python\Python313\Lib\json\decoder.py", line 345, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
               ~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\gonza\AppData\Local\Programs\Python\Python313\Lib\json\decoder.py", line 361, in raw_decode
    obj, end = self.scan_once(s, idx)
               ~~~~~~~~~~~~~~^^^^^^^^
json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 3 (char 2)
```

