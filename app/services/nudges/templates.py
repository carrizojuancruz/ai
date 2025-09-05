from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional


class NudgeType(str, Enum):
    STATIC_BILL = "static_bill"
    MEMORY_ICEBREAKER = "memory_icebreaker"
    INFO_BASED = "info_based"


class NudgeChannel(str, Enum):
    PUSH = "push"
    IN_APP = "in_app"


@dataclass
class NudgeTemplate:
    rule_id: str
    name: str
    description: str
    nudge_type: NudgeType
    required_metadata_keys: list[str] = field(default_factory=list)
    topic_keys: list[str] = field(default_factory=list)
    predicate: Optional[Callable[[dict, dict, dict, datetime], bool]] = None
    prompt_template: str = ""
    preview_template: str = "You have a new insight from Vera"
    default_channel: NudgeChannel = NudgeChannel.PUSH
    priority: int = 100
    quiet_hours_start: Optional[int] = 22
    quiet_hours_end: Optional[int] = 8
    cooldown_days: int = 3
    max_per_day: int = 1
    max_per_week: int = 3


class NudgeRegistry:
    def __init__(self):
        self.templates: dict[str, NudgeTemplate] = {}
        self._register_default_templates()

    def register(self, template: NudgeTemplate) -> None:
        self.templates[template.rule_id] = template

    def get(self, rule_id: str) -> Optional[NudgeTemplate]:
        return self.templates.get(rule_id)

    def get_by_type(self, nudge_type: NudgeType) -> list[NudgeTemplate]:
        return [t for t in self.templates.values() if t.nudge_type == nudge_type]

    def _register_default_templates(self) -> None:
        self.register(
            NudgeTemplate(
                rule_id="goal_milestone_soon",
                name="Goal Milestone Approaching",
                description="User is close to reaching a savings or budget goal",
                nudge_type=NudgeType.INFO_BASED,
                topic_keys=["goal_active", "savings_goal", "budget_goal"],
                required_metadata_keys=["progress_pct", "goal_name"],
                predicate=lambda user_ctx, mem_val, mem_meta, now: (
                    mem_meta.get("progress_pct", 0) >= 80
                    and mem_meta.get("progress_pct", 0) < 95
                    and _days_since(mem_meta.get("updated_at"), now) <= 30
                ),
                prompt_template=(
                    "NUDGE_CONTEXT: The user is {progress_pct}% towards their {goal_name} goal. "
                    "Open with encouragement about their progress and offer tips to reach the finish line."
                ),
                preview_template="You're close to reaching your {goal_name} goal! 🎯",
                priority=90,
            )
        )
        self.register(
            NudgeTemplate(
                rule_id="spending_pattern_alert",
                name="Unusual Spending Pattern",
                description="Detected unusual spending in a category",
                nudge_type=NudgeType.INFO_BASED,
                topic_keys=["spending_pattern", "expense_trend"],
                required_metadata_keys=["category", "trailing_30d_spend"],
                predicate=lambda user_ctx, mem_val, mem_meta, now: (
                    mem_meta.get("trailing_30d_spend", 0) >= 200
                    and _spending_increased(mem_meta)
                    and _days_since(mem_meta.get("created_at"), now) <= 7
                ),
                prompt_template=(
                    "NUDGE_CONTEXT: Spending in {category} has increased recently. "
                    "Open with a friendly observation and offer to review spending patterns together."
                ),
                preview_template="I noticed a change in your {category} spending",
                priority=85,
                cooldown_days=7,
            )
        )
        self.register(
            NudgeTemplate(
                rule_id="subscription_renewal",
                name="Subscription Renewal",
                description="Subscription renewing soon",
                nudge_type=NudgeType.INFO_BASED,
                topic_keys=["subscription", "recurring_charge"],
                required_metadata_keys=["provider", "valid_until"],
                predicate=lambda user_ctx, mem_val, mem_meta, now: (
                    _days_until(mem_meta.get("valid_until"), now) <= 7
                    and _days_until(mem_meta.get("valid_until"), now) >= 0
                ),
                prompt_template=(
                    "NUDGE_CONTEXT: The user has a {provider} subscription renewing on {valid_until}. "
                    "Open with a friendly reminder and offer to review or help with cancellation if needed."
                ),
                preview_template="Your {provider} subscription renews soon",
                priority=80,
                cooldown_days=30,
            )
        )
        self.register(
            NudgeTemplate(
                rule_id="budget_checkin",
                name="Budget Check-in",
                description="Mid-month budget review",
                nudge_type=NudgeType.INFO_BASED,
                topic_keys=["budget_status", "monthly_budget"],
                required_metadata_keys=["budget_used_pct", "days_remaining"],
                predicate=lambda user_ctx, mem_val, mem_meta, now: (
                    user_ctx.get("budget_posture", {}).get("active_budget", False)
                    and mem_meta.get("budget_used_pct", 0) >= 60
                    and mem_meta.get("days_remaining", 0) >= 10
                ),
                prompt_template=(
                    "NUDGE_CONTEXT: The user has used {budget_used_pct}% of their budget with "
                    "{days_remaining} days left in the month. Open with a supportive check-in."
                ),
                preview_template="Time for a quick budget check-in 📊",
                priority=75,
                max_per_week=1,
            )
        )
        self.register(
            NudgeTemplate(
                rule_id="positive_milestone",
                name="Positive Milestone",
                description="Celebrate a financial achievement",
                nudge_type=NudgeType.INFO_BASED,
                topic_keys=["achievement", "milestone", "savings_increase"],
                required_metadata_keys=["achievement_type", "achievement_detail"],
                predicate=lambda user_ctx, mem_val, mem_meta, now: (
                    mem_meta.get("importance_bin") == "high" and _days_since(mem_meta.get("created_at"), now) <= 3
                ),
                prompt_template=(
                    "NUDGE_CONTEXT: The user achieved {achievement_type}: {achievement_detail}. "
                    "Open with celebration and positive reinforcement."
                ),
                preview_template="Great news about your {achievement_type}! 🎉",
                priority=95,
                cooldown_days=1,
            )
        )


def _days_since(date_str: Optional[str], now: datetime) -> int:
    if not date_str:
        return float("inf")
    try:
        date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return (now - date).days
    except (ValueError, AttributeError):
        return float("inf")


def _days_until(date_str: Optional[str], now: datetime) -> int:
    if not date_str:
        return float("inf")
    try:
        date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return (date - now).days
    except (ValueError, AttributeError):
        return float("inf")


def _spending_increased(meta: dict) -> bool:
    trailing = meta.get("trailing_30d_spend", 0)
    baseline = meta.get("baseline_30d_spend", trailing)
    if baseline == 0:
        return trailing > 100
    increase_pct = ((trailing - baseline) / baseline) * 100
    return increase_pct >= 30
