"""Extended tool descriptions for the Goal Agent. Including detailed explanations of each tool's purpose."""

class ToolDescriptions:
    GOAL_CREATION_TOOL = """Create a new goal (financial or non-financial, habit or punctual) for a user.
    MINIMUM REQUIRED FOR ACTIVATION (in_progress status):

    Non-Financial Goals (3 critical fields):
    - goal: {title: str, description: str} - BOTH title AND description required
    - amount: {type: "absolute", absolute: {currency: "times|books|pages|...", target: NUMBER}}
    - Auto-completed if not provided: kind, category ("other"), nature, frequency, notifications

    Financial Goals (4 critical fields - same as above PLUS):
    - evaluation: {affected_categories: [...]} - MUST include valid Plaid categories for tracking
    - Auto-completed if not provided: kind, category (inferred), nature, frequency, notifications

    STATUS ON CREATION:
    - If ALL minimum fields provided → status = "in_progress" (activated and ready to track)
    - If missing ANY critical field → status = "pending" (draft that needs completion)

    The agent should automatically determine the correct status based on field completeness.
    Do NOT create goals in pending status when all minimum fields are available.

    ** IMPORTANT **
    If the goal has all the required fields to be activated, the agent MUST set the status to "in_progress".

    FULL FIELD REFERENCE:

    REQUIRED FIELDS FOR ACTIVATION:
    - goal: {title: str, description: str} - Goal title and description (WHY the user wants this goal)
    - amount: {type: str, ...} - Object defining target (see Amount section below)
    - evaluation.affected_categories: REQUIRED for financial goals ONLY (see Evaluation section)

    OPTIONAL FIELDS (auto-completed with defaults):
    - category: {value: str} - One of: saving, spending, debt, income, investment, net_worth, other
    - nature: {value: str} - Either "increase" or "reduce"
    - kind: str - One of: financial_habit, financial_punctual, nonfin_habit, nonfin_punctual
    - frequency: {type: str, ...} - Object defining evaluation calendar (see Frequency section below)
    - notifications: {enabled: bool} - Default: false (less intrusive)

    GOAL KINDS:
    - financial_habit: Recurring financial goals (e.g., save $500/month). REQUIRES evaluation.affected_categories.
    - financial_punctual: One-time financial goals (e.g., save $10,000 by Dec 31). REQUIRES evaluation.affected_categories.
    - nonfin_habit: Recurring non-financial goals (e.g., exercise 3x/week). Optional nonfin_category for taxonomy.
    - nonfin_punctual: One-time non-financial goals (e.g., read 12 books this year). Optional nonfin_category.

    AMOUNT TYPES:
    - Absolute: {"type": "absolute", "absolute": {"currency": "USD", "target": 5000}}
    - Percentage: {"type": "percentage", "percentage": {"target_pct": 20, "of": {"basis": "income", "ref": null}}}

    FREQUENCY TYPES:
    - Specific (one-time): {"type": "specific", "specific": {"date": "2025-12-31T00:00:00"}}
    - Recurrent: {"type": "recurrent", "recurrent": {"unit": "month", "every": 1, "start_date": "2025-01-01T00:00:00", "end_date": null}}
      * For habit goals: unit MUST be "day", "week", or "month" (not quarter/year)

    EVALUATION (for financial goals):
    - affected_categories: REQUIRED for financial goals. List of Plaid categories (e.g., ["food_drink", "entertainment"])
    - Valid Plaid categories: bank_fees, home_improvement, rent_utilities, entertainment, income, transfer_in,
      food_drink, loan_payments, transfer_out, general_merchandise, medical, transportation, general_services,
      personal_care, travel, government_non_profit, manual_expenses, cash_transactions, custom_category
    - aggregation: "sum" (default), "average", "max", "min"
    - direction: "≥" (default), "≤", "="
    - source: "linked_accounts" (default), "manual_input", "mixed"

    NOTIFICATIONS (REQUIRED):
    - enabled: bool - MUST be set explicitly (true or false). No default value.
    - min_gap_hours: int - Minimum hours between notifications (default: 24)
    - If enabled=false, no notifications will be sent regardless of reminders configuration

    REMINDERS (optional):
    - items: List of reminder schedules
    - Each item has a "schedule" with:
      * type: "one_time" or "recurring"
      * unit: "day", "week", or "month" (for recurring)
      * every: int (e.g., 1 = every unit, 2 = every other unit)
      * weekdays: ["mon", "tue", ...] (for weekly schedules)
      * month_day: int (1-31, for monthly schedules)
      * start_date: ISO datetime string (anchor date)
      * time_of_day: "HH:MM" in 24h format (e.g., "09:00", "14:30")

    THRESHOLDS (optional):
    - warn_progress_pct: Percentage for warning (0-100)
    - alert_progress_pct: Percentage for critical alert (0-100)
    - warn_days_remaining: Days remaining threshold

    CADENCE (optional, for habit goals):
    - days: Number of days in cadence window
    - Automatically tracks window rollover and streak counting

    EXAMPLES:

    Example 1 - Financial Habit (Auto-Activated with minimum fields):
    ```
    create_goal({
        "goal": {"title": "Reduce dining out", "description": "Save money for vacation fund"},
        "amount": {"type": "absolute", "absolute": {"currency": "USD", "target": 300}},
        "evaluation": {"affected_categories": ["food_drink"]}
    })
    # Result: Created with status = "in_progress" (all 4 critical fields present)
    # Auto-completed: kind=financial_habit, category=spending, nature=reduce, frequency=monthly, notifications.enabled=false
    ```

    Example 2 - Non-Financial Habit (Auto-Activated with minimum fields):
    ```
    create_goal({
        "goal": {"title": "Exercise regularly", "description": "Improve health and energy levels"},
        "amount": {"type": "absolute", "absolute": {"currency": "times", "target": 3}}
    })
    # Result: Created with status = "in_progress" (all 3 critical fields present)
    # Auto-completed: kind=nonfin_habit, category=other, nature=increase, frequency=weekly, notifications.enabled=false
    ```

    Example 3 - Financial Goal with Full Configuration:
    ```
    create_goal({
        "goal": {"title": "Reduce dining out", "description": "Limit restaurant spending to save for vacation"},
        "category": {"value": "spending"},
        "nature": {"value": "reduce"},
        "kind": "financial_habit",
        "amount": {"type": "absolute", "absolute": {"currency": "USD", "target": 300}},
        "frequency": {"type": "recurrent", "recurrent": {"unit": "month", "every": 1, "start_date": "2025-01-01T00:00:00"}},
        "evaluation": {"affected_categories": ["food_drink"]},
        "notifications": {"enabled": true, "min_gap_hours": 48},
        "reminders": {"items": [
            {"schedule": {"type": "recurring", "unit": "week", "every": 1, "weekdays": ["mon"], "time_of_day": "09:00"}}
        ]},
        "cadence": {"days": 30}
    })
    # Result: Created with status = "in_progress" (fully configured)
    ```

    Example 4 - Non-Financial Punctual (Auto-Activated):
    ```
    create_goal({
        "goal": {"title": "Read 12 books", "description": "Expand knowledge and improve focus"},
        "amount": {"type": "absolute", "absolute": {"currency": "books", "target": 12}},
        "frequency": {"type": "specific", "specific": {"date": "2025-12-31T23:59:59"}}
    })
    # Result: Created with status = "in_progress" (all 3 critical fields present)
    # Auto-completed: kind=nonfin_punctual, category=other, nature=increase, notifications.enabled=false
    ```

    Example 5 - Incomplete Goal (Created as Pending):
    ```
    create_goal({
        "goal": {"title": "Save money"}
        # Missing: description, target amount
    })
    # Result: Created with status = "pending" (missing critical fields)
    # Agent should ask: "To activate this goal, I need to know: why you want to save (description) and how much (target)?"
    ```
    """

    UPDATE_GOAL_TOOL = """Update an existing goal's configuration (target, cadence, categories, notifications, reminders).

    Use this tool to modify goal properties. All fields are optional - only include fields you want to change.

    UPDATABLE FIELDS:
    - goal: {title?: str, description?: str}
    - amount: Target configuration (see AMOUNT TYPES in create_goal)
    - frequency: Evaluation calendar (see FREQUENCY TYPES in create_goal)
    - evaluation: For financial goals, affected_categories must remain valid Plaid categories
    - notifications: {enabled?: bool, min_gap_hours?: int}
    - reminders: {items: [...]} - Replace entire reminder list
    - thresholds: {warn_progress_pct?: number, alert_progress_pct?: number, warn_days_remaining?: number}
    - cadence: {days: int} - Update cadence window for habits
    - nonfin_category: str - Update non-financial taxonomy

    VALIDATION RULES:
    - For financial goals: affected_categories must contain only valid Plaid categories
    - For habit goals: frequency.recurrent.unit must be "day", "week", or "month"
    - Cannot change kind (financial_habit, etc.) after creation
    - Cannot change status through this tool (use switch_goal_status instead)

    Note: For progress updates, use the register_progress tool instead.

    Example - Update target and add weekly reminder:
    ```
    update_goal({
        "goal_id": "123e4567-e89b-12d3-a456-426614174000",
        "amount": {"type": "absolute", "absolute": {"target": 6000}},
        "reminders": {"items": [
            {"schedule": {"type": "recurring", "unit": "week", "every": 1, "weekdays": ["wed", "fri"], "time_of_day": "10:00"}}
        ]}
    })
    ```

    Example - Disable notifications:
    ```
    update_goal({
        "goal_id": "123e4567-e89b-12d3-a456-426614174000",
        "notifications": {"enabled": false}
    })
    ```

    Example - Update affected categories for financial goal:
    ```
    update_goal({
        "goal_id": "123e4567-e89b-12d3-a456-426614174000",
        "evaluation": {"affected_categories": ["food_drink", "entertainment", "general_merchandise"]}
    })
    ```
    """

    LIST_GOALS_TOOL = """List all active goals for a user with optional filtering.

    Returns only non-deleted goals with their complete configuration including:
    - Goal definition (title, description, kind)
    - Current progress and status
    - Target amount and frequency
    - Notification settings (enabled status, last notification time)
    - Reminder schedules (if configured)
    - Thresholds and cadence configuration
    - For financial goals: affected_categories with Plaid categories
    - For non-financial goals: nonfin_category taxonomy

    FILTER OPTIONS:
    - kind: Filter by goal kind (financial_habit, financial_punctual, nonfin_habit, nonfin_punctual)
    - status: Filter by status (pending, in_progress, completed, off_track)

    Results show:
    - notifications.enabled: Whether user has enabled notifications for this goal
    - reminders.items: List of configured reminder schedules
    - state.current_accomplished: Whether current window is accomplished (for habits)
    - state.streak_count: Current streak of accomplished windows

    Example usage:
    ```
    # List all active goals
    list_goals()

    # List only financial habits
    list_goals(kind="financial_habit")

    # List only in-progress goals
    list_goals(status="in_progress")
    ```
    """

    REGISTER_PROGRESS_TOOL = """Register incremental progress towards a goal.

    Updates the goal's current_value and percent_complete. Automatically rounds to 2 decimal places.
    For habit goals, respects cadence windows.

    Example usage:
    ```
    # Register $150 saved towards a savings goal
    register_progress(
        goal_id="123e4567-e89b-12d3-a456-426614174000",
        delta=150.00
    )

    # Register negative progress (e.g., spending reduction goal)
    register_progress(
        goal_id="123e4567-e89b-12d3-a456-426614174000",
        delta=-25.50
    )
    ```
    """

    SWITCH_GOAL_STATUS_TOOL = """Switch a goal's status with state machine validation.    Vali transitions:
    - PENDING → IN_PROGRESS, OFF_TRACK
    - IN_PROGRESS → COMPLETED, OFF_TRACK
    - OFF_TRACK → IN_PROGRESS
    - COMPLETED → OFF_TRACK

    Use this for explicit status changes (e.g., marking off-track, resetting to pending).
    For deletion, use delete_goal instead.

    Example usage:
    ```
    # Mark a goal as off-track
    switch_goal_status(
        goal_id="123e4567-e89b-12d3-a456-426614174000",
        target_status="off_track"
    )

    # Resume an off-track goal
    switch_goal_status(
        goal_id="123e4567-e89b-12d3-a456-426614174000",
        target_status="in_progress"
    )
    ```
    """

    DELETE_GOAL_TOOL = """Permanently delete a goal.

    Removes the goal from the user's active goals. This action cannot be undone.
    Always confirm with the user before deletion.

    Example usage:
    ```
    delete_goal(goal_id="123e4567-e89b-12d3-a456-426614174000")
    ```
    """

    GET_GOAL_BY_ID_TOOL = """Retrieve a specific goal by its unique identifier.

    Returns the complete goal object with all fields:
    - Goal definition (title, description, category, nature, kind)
    - Target and frequency configuration
    - Evaluation config (including affected_categories for financial goals)
    - Current progress and status (including window state for habits)
    - Notification configuration (enabled, last_notified_at, min_gap_hours)
    - Reminder schedules (type, unit, frequency, time_of_day, weekdays, etc.)
    - Thresholds for alerts
    - Cadence configuration (for habit goals)
    - Audit trail (created_at, updated_at)

    RETURNED FIELDS INCLUDE:
    - notifications.enabled: Whether notifications are active
    - notifications.status: Whether a pending notification exists
    - reminders.items[].schedule: Complete schedule configuration
    - state.current_accomplished: Current window accomplishment status
    - state.streak_count: Number of consecutive accomplished windows
    - state.nudge_level: Dynamic nudge intensity based on failures

    Example usage:
    ```
    get_goal_by_id(goal_id="123e4567-e89b-12d3-a456-426614174000")
    ```
    """

