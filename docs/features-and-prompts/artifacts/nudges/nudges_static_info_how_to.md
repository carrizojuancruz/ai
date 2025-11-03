# Info Nudges Quick Reference

A concise guide for implementing and troubleshooting info-based nudges.

---

## Quick Start

```python
from app.services.nudges.strategies import InfoNudgeStrategy

strategy = InfoNudgeStrategy(data_access=my_data_layer)
candidate = await strategy.evaluate(
    user_id,
    {
        "nudge_id": "spending_alert",
        "notification_text": "Your spending is up!",
        "preview_text": "Spending Alert",
    }
)
```

---

## Available Nudge Types

| Nudge ID              | Priority | Description                    | Status     |
|-----------------------|----------|--------------------------------|------------|
| payment_failed        | 5        | Payment failure alert          | 🔧 Pending |
| spending_alert        | 4        | Spending increase alert        | 🔧 Pending |
| goal_milestone        | 3        | Goal achievement celebration   | 🔧 Pending |
| budget_warning        | 3        | Budget limit warning           | 🔧 Pending |
| category_insight      | 2        | Category spending insight      | 🔧 Pending |
| subscription_reminder | 2        | Subscription due reminder      | 🔧 Pending |
| savings_opportunity   | 1        | Savings suggestion             | 🔧 Pending |

**Legend**: ✅ Ready | 🔧 Needs Data Integration | ❌ Not Implemented

---

## Context Fields

**Required:**
```python
context = {
    "nudge_id": str,              # Which evaluator
    "notification_text": str,     # Main message (from FOS)
    "preview_text": str,          # Preview (from FOS)
}
```

**Optional:**
```python
context = {
    # ...required...
    "metadata": dict,             # Extra context
    "threshold": float,           # Custom evaluator threshold
    # ...other evaluator fields...
}
```

---

## Configuration

_View current settings:_
```python
config = strategy.get_evaluator_config("spending_alert")
print(config.priority)
print(config.enabled)
print(config.threshold)
```

_Update config:_
```python
strategy.update_evaluator_config(
    "spending_alert",
    enabled=True,
    threshold=0.8,
    priority=5,
    cooldown_hours=48
)
```

_List all nudges:_
```python
print(strategy.list_available_nudges())
```

---

## Data Access Layer (Protocol)

```python
class DataAccessLayer(Protocol):
    async def get_user_spending_trend(self, user_id: UUID, days: int = 30): ...
    async def get_user_goals(self, user_id: UUID): ...
    async def get_budget_usage(self, user_id: UUID): ...
    async def get_upcoming_subscriptions(self, user_id: UUID, days_ahead: int = 7): ...
    async def get_failed_payments(self, user_id: UUID): ...
    async def get_category_trends(self, user_id: UUID, days: int = 30): ...
```

**Implement with:**
```python
class MyDataAccessLayer:
    async def get_user_spending_trend(self, user_id: UUID, days: int = 30):
        return {
            "current_period_total": 2500.0,
            "average_period_total": 1800.0
        }
    # ...other methods...
```

---

## Custom Evaluator Example

```python
from app.services.nudges.strategies.info_evaluators import InfoNudgeEvaluator, EvaluatorConfig

class MyEvaluator(InfoNudgeEvaluator):
    async def evaluate_condition(self, user_id, context):
        return some_condition
    async def get_metadata(self, user_id, context):
        return {"evaluator": self.nudge_id, "custom_field": "value"}

config = EvaluatorConfig(nudge_id="my_custom", priority=3)
evaluator = MyEvaluator(config, data_layer)
strategy.register_custom_evaluator(evaluator)

candidate = await strategy.evaluate(user_id, {
    "nudge_id": "my_custom",
    "notification_text": "...",
    "preview_text": "..."
})
```

---

## Testing

_Mock data:_
```python
from unittest.mock import AsyncMock, MagicMock

mock_data = MagicMock()
mock_data.get_user_spending_trend = AsyncMock(return_value={
    "current_period_total": 2000,
    "average_period_total": 1000
})
strategy = InfoNudgeStrategy(data_access=mock_data)
```

_Evaluator test:_
```python
@pytest.mark.asyncio
async def test_spending_alert():
    config = EvaluatorConfig(nudge_id="spending_alert", priority=4)
    evaluator = SpendingAlertEvaluator(config, mock_data)
    result = await evaluator.should_send(user_id, {})
    assert result is True
```

---

## NudgeCandidate Structure

```python
{
    "user_id": UUID,
    "nudge_type": "info_based",
    "priority": int,                # 1-5
    "notification_text": str,       # From FOS
    "preview_text": str,            # From FOS
    "metadata": {
        "nudge_id": str,
        "fos_controlled": True,
        "evaluation_context": dict,
        "evaluator_metadata": {
            "evaluator": str,
            # ...custom fields...
        }
    }
}
```

---

## Troubleshooting

**Evaluator Not Found**
```
WARNING: info_strategy.unknown_nudge_id
```
_Check available nudges & register custom if missing:_
```python
print(strategy.list_available_nudges())
strategy.register_custom_evaluator(my_evaluator)
```

**Always Returns None**
```
DEBUG: info_strategy.condition_not_met
```
_Check: enabled? data access? threshold? logs?_
```python
config = strategy.get_evaluator_config(nudge_id)
print(config.enabled)
print(config.threshold)
```

**Missing Required Fields**
```
WARNING: info_strategy.missing_required_fields
```
_Add required context keys:_
```python
context = {
    "nudge_id": "spending_alert",
    "notification_text": "...",
    "preview_text": "..."
}
```

---

## Architecture Patterns

- **Strategy Pattern:** `InfoNudgeStrategy` uses multiple evaluators.
- **Factory Pattern:** `EvaluatorFactory.create_evaluator(nudge_id)` returns evaluator.
- **Dependency Injection:** Inject data layer to strategy and evaluators.
- **Protocol Interface:** Any compatible class can serve as `DataAccessLayer`.

---

## Priority Levels

- **5 - Critical**: Urgent action needed (e.g., payment failure)
- **4 - High**: Major event to act on soon (e.g., spending spike)
- **3 - Medium-High**: Notable notification (e.g., budget warning)
- **2 - Medium**: Informational (e.g., category insight)
- **1 - Low**: Suggestions (e.g., savings tip)

---

## Related APIs

**Get strategy from registry:**
```python
from app.services.nudges.strategies import get_strategy_registry
strategy = get_strategy_registry().get_strategy("info_based")
```

**Check FOS control:**
```python
registry = get_strategy_registry()
is_fos = registry.is_fos_controlled("info_based")
```

**List all strategies:**
```python
strategies = get_strategy_registry().list_available_strategies()
```

---

## Documentation

- [Technical Guide](./INFO_NUDGES_TECHNICAL_GUIDE.md)
- [Nudge Overview](./nudges.md)
- [Strategies README](../../../../app/services/nudges/strategies/README.md)
- [API Examples](./nudge_eval_api_examples.md)

---

## Best Practices

**Do:**
- Supply a real data access layer
- Handle missing data gracefully
- Use logging for debugging
- Supply clear metadata
- Write comprehensive tests
- Document business logic & overrides

**Don’t:**
- Hardcode thresholds
- Ignore errors or fail silently
- Skip validations
- Use mock data in prod
- Cause N+1 queries
- Forget cooldown checks

---

## Debugging Tips

```python
config = strategy.get_evaluator_config(nudge_id)
print(config)
print(strategy.list_available_nudges())
data = await data_layer.get_user_spending_trend(user_id)
print(data)
import logging
logging.getLogger("app.services.nudges").setLevel(logging.DEBUG)
```

---

## Performance Tips

1. Batch database queries.
2. Cache expensive calculations.
3. Use async (all evaluators are async).
4. Strategies load lazily on demand.
5. Pool DB connections.

---

## Implementation Status

**Complete:**
- Framework, base evaluators, factory, config, error handling, docs

**Needs Work:**
- Data access methods
- Evaluator business logic
- Cooldown logic
- DB-config storage
- Analytics pipeline

**Planned:**
- ML-driven logic
- A/B tests
- Scheduling
- Per-user overrides
- Advanced cooldowns
