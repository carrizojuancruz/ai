"""Extended tool descriptions for the Goal Agent. Including detailed explanations of each tool's purpose."""


class ToolDescriptions:
    GOAL_CREATION_TOOL = """Create a new goal (financial or non-financial, habit or punctual) for a user.
    MINIMUM REQUIRED FOR ACTIVATION (in_progress status):

    Non-Financial Goals (3 critical fields):
    - goal: {title: str, description: str} - BOTH title AND description required
    - amount: {type: "absolute", absolute: {currency: "times|books|pages|...", target: NUMBER}}
    - Auto-completed if not provided: kind, category ("other"), nature, frequency

    Financial Goals (4 critical fields - same as above PLUS):
    - evaluation: {affected_categories: [...]} - MUST include valid Plaid categories for tracking. This must be assigned by the agent.
    - Auto-completed if not provided: kind, category (inferred), nature, frequency

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

    CONDITIONAL FIELDS (Important):
    - kind: str - Defaults to "financial_habit". MUST be set to "financial_punctual" for one-time goals.
    - frequency: {type: str, ...} - REQUIRED for punctual goals (specific date). Defaults to monthly recurrent for habits.
    - notifications: {enabled: bool, min_gap_hours?: int} - Do not assume a default; only set this if the user explicitly asks to enable/disable reminders. If omitted, do not state a notifications status.

    GOAL KINDS:
    - financial_habit: Recurring financial goals (e.g., save $500/month). REQUIRES evaluation.affected_categories.
    - financial_punctual: One-time financial goals (e.g., save $10,000 by Dec 31). REQUIRES evaluation.affected_categories AND frequency.specific.date.
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

    IMPORTANT - Category Translation for Supervisor:
    - When preparing responses, translate Plaid tags to human-readable labels
    - The supervisor will receive your translated categories and pass them to the user
    - Example: "HOME_IMPROVEMENT" → "Home improvements" (not the raw tag)
    - See Category Translation Rules in system prompt for full mapping

    NOTIFICATIONS:
    - enabled: bool - Set ONLY when the user explicitly asks to change notifications for the goal.
    - CRITICAL: Do NOT assume they are OFF by default.
    - When reading goal details: If notifications field is missing or null, state "Notification configuration not set" rather than inventing a status.
    - When available, read the current value from the goal using get_goal_by_id and reflect it accurately.
    - min_gap_hours: int - Minimum hours between notifications (default behavior is 24 if configured)
    - If enabled=false, no notifications will be sent regardless of reminders configuration
    - App-level/device notification status is not visible to this agent. Do NOT assert that app/device notifications are on/off. Prefer a neutral phrasing: "Push notifications depend on your device/app settings; I can configure goal reminders here."

    REMINDERS (optional):
    - This field is OPTIONAL and can be null or have an empty items list
    - ONLY mention reminder details when reminders.items actually contains schedules
    - NEVER fabricate reminder times or schedules when this field is absent or empty
    - items: List of reminder schedules (can be empty list)
    - Each item has a "schedule" with:
      * type: "one_time" or "recurring"
      * unit: "day", "week", or "month" (for recurring)
      * every: int (e.g., 1 = every unit, 2 = every other unit)
      * weekdays: ["mon", "tue", ...] (for weekly schedules)
      * month_day: int (1-31, for monthly schedules)
      * start_date: ISO datetime string (anchor date)
      * time_of_day: "HH:MM" in 24h format (e.g., "09:00", "14:30")

        SUPPORTED REMINDER CAPABILITIES ONLY:
        - Do NOT invent unsupported options like "daily nudges" as a separate feature, "weekly check-ins" as a distinct type, "per-book prompts", or custom intervals beyond the fields above. If the user requests something outside this schema, offer the closest supported equivalent (e.g., recurring weekly Mondays at 09:00).

        CRITICAL REMINDER RULES:
        - Before displaying goal details, check if reminders.items exists and is non-empty
        - If reminders is null or items is empty: "No reminders configured"
        - NEVER invent reminder times when none exist in the data

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
    # Auto-completed: kind=financial_habit, category=spending, nature=reduce, frequency=monthly
    ```

    Example 2 - Non-Financial Habit (Auto-Activated with minimum fields):
    ```
    create_goal({
        "goal": {"title": "Exercise regularly", "description": "Improve health and energy levels"},
        "amount": {"type": "absolute", "absolute": {"currency": "times", "target": 3}}
    })
    # Result: Created with status = "in_progress" (all 3 critical fields present)
    # Auto-completed: kind=nonfin_habit, category=other, nature=increase, frequency=weekly
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
    # Auto-completed: kind=nonfin_punctual, category=other, nature=increase
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

    SWITCH_GOAL_STATUS_TOOL = """Switch a goal's status with state machine validation.    Valid transitions:
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
    - Reminder schedules (OPTIONAL - may be null or have empty items list)
    - Thresholds for alerts
    - Cadence configuration (for habit goals)
    - Audit trail (created_at, updated_at)

    RETURNED FIELDS INCLUDE:
    - notifications.enabled: Whether notifications are active
    - notifications.status: Whether a pending notification exists
    - reminders: OPTIONAL - Can be null or have empty items list
      * If present and non-empty: reminders.items[].schedule contains complete schedule configuration
      * If null or empty: NO reminders are configured - do NOT invent or assume any reminder data
      * When displaying: ONLY mention reminders if items list is populated
    - state.current_accomplished: Current window accomplishment status
    - state.streak_count: Number of consecutive accomplished windows
    - state.nudge_level: Dynamic nudge intensity based on failures

    CRITICAL REMINDER HANDLING:
    - ALWAYS check if reminders field exists and items list is non-empty before mentioning reminder times
    - If reminders is null or items is empty, state "No reminders configured"
    - NEVER fabricate reminder times, schedules, or frequencies

    Example usage:
    ```
    get_goal_by_id(goal_id="123e4567-e89b-12d3-a456-426614174000")
    ```
    """

    GET_GOAL_HISTORY_TOOL = """Get all progress history records for a specific goal.

    Retrieves complete history for a goal, ordered by most recent period first.
    Returns all historical snapshots showing how the goal progressed over time.

    USE CASES:
    - Show user their progress timeline
    - Compare current vs past performance
    - Audit historical goal data

    Example:
    ```
    get_goal_history(goal_id="123e4567-e89b-12d3-a456-426614174000")
    ```
    """

    CREATE_HISTORY_RECORD_TOOL = """Create a new progress history record for a goal.

    Creates a historical snapshot for a specific time period.
    Automatically calculates percent_complete and was_completed based on values provided.

    REQUIRED FIELDS:
    - goal_id: The goal this record belongs to
    - period_start: When this period started (datetime)
    - period_end: When this period ended (datetime, must be after period_start)
    - period_type: Type of period (day, week, month, quarter, year)

    OPTIONAL FIELDS:
    - final_value: Final accumulated value for the period
    - target_value: Target value for the period

    AUTO-CALCULATED:
    - percent_complete: Calculated from final_value/target_value
    - was_completed: True if percent_complete >= 100
    - Timestamps and counters

    Example:
    ```
    create_history_record({
        "goal_id": "123e4567-e89b-12d3-a456-426614174000",
        "period_start": "2025-11-01T00:00:00Z",
        "period_end": "2025-11-30T23:59:59Z",
        "period_type": "month",
        "final_value": 750,
        "target_value": 1000
    })
    ```
    """

    UPDATE_HISTORY_RECORD_TOOL = """Update an existing progress history record.

    Modifies the progress values of a historical record.
    Automatically recalculates percent_complete when values change.

    UPDATABLE FIELDS:
    - final_value: Update the accumulated value
    - target_value: Update the target
    - was_completed: Mark as completed/incomplete

    AUTO-RECALCULATED:
    - percent_complete: Recalculated if final_value or target_value changes
    - last_updated: Set to current time
    - update_count: Incremented by 1

    IMPORTANT: Cannot update goal_id, period dates, or period_type (these define the record identity).

    Example:
    ```
    update_history_record(
        record_id="987e6543-e21b-12d3-a456-426614174999",
        final_value=850.50
    )
    ```
    """

    DELETE_HISTORY_RECORD_TOOL = """Delete a progress history record.

    Permanently removes a historical record from the database.
    Use with caution - this action cannot be undone.

    USE CASES:
    - Remove incorrect historical data
    - Clean up test records
    - Delete duplicate entries

    Example:
    ```
    delete_history_record(record_id="987e6543-e21b-12d3-a456-426614174999")
    ```
    """

    LINK_ASSET_TO_GOAL_TOOL = """Add the value of an asset to a goal's current progress.

    Use this when the user wants to link an existing asset to a goal.
    This simply adds the asset's value to the goal's current progress.

    REQUIRED:
    - goal_id: The ID of the goal to update
    - amount: The asset value to add to the goal's progress (must be positive)

    OPTIONAL:
    - asset_name: Name of the asset being linked (for confirmation message)

    Example:
    ```
    link_asset_to_goal(
        goal_id="123e4567-e89b-12d3-a456-426614174000",
        amount=22000,
        asset_name="Tesla Model 3"
    )
    ```
    """
