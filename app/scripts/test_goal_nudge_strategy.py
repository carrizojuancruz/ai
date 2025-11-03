"""Manual test script for GoalNudgeStrategy.

Usage:
    poetry run python -m app.scripts.test_goal_nudge_strategy
"""
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

from app.observability.logging_config import get_logger
from app.services.nudges.strategies.goal_strategy import GoalNudgeStrategy

logger = get_logger(__name__)


async def test_goal_nudge_scenarios():
    strategy = GoalNudgeStrategy()
    test_user_id = uuid4()

    print("\n" + "="*80)
    print("TESTING GOAL NUDGE STRATEGY")
    print("="*80)

    # Test 1: Goal completed with end date
    print("\n[TEST 1] Goal completed with end date")
    context1 = {
        "goal_id": str(uuid4()),
        "notifications_enabled": True,
        "notification_text": "🎉 Congratulations! You've completed your goal!",
        "preview_text": "Goal completed",
        "status": "completed",
        "end_date": datetime.now(),
        "no_end_date": False,
        "percent_complete": 100,
        "metadata": {"source": "test"},
    }
    result1 = await strategy.evaluate(test_user_id, context1)
    print(f"✓ Result: {result1}")
    if result1:
        print(f"  - Nudge ID: {result1.metadata['nudge_id']}")
        print(f"  - Priority: {result1.priority}")
        print(f"  - Text: {result1.notification_text}")

    # Test 2: Goal in progress with high progress
    print("\n[TEST 2] Goal in progress with 80% completion")
    context2 = {
        "goal_id": str(uuid4()),
        "notifications_enabled": True,
        "notification_text": "🚀 You're almost there! 80% complete",
        "preview_text": "High progress",
        "status": "in_progress",
        "percent_complete": 80,
        "metadata": {},
    }
    result2 = await strategy.evaluate(test_user_id, context2)
    print(f"✓ Result: {result2}")
    if result2:
        print(f"  - Nudge ID: {result2.metadata['nudge_id']}")
        print(f"  - Priority: {result2.priority}")

    # Test 3: Goal pending
    print("\n[TEST 3] Goal pending")
    context3 = {
        "goal_id": str(uuid4()),
        "notifications_enabled": True,
        "notification_text": "💪 Ready to start your goal?",
        "preview_text": "Start your goal",
        "status": "pending",
        "percent_complete": 0,
        "metadata": {},
    }
    result3 = await strategy.evaluate(test_user_id, context3)
    print(f"✓ Result: {result3}")
    if result3:
        print(f"  - Nudge ID: {result3.metadata['nudge_id']}")
        print(f"  - Priority: {result3.priority}")

    # Test 4: Goal near deadline (7 days)
    print("\n[TEST 4] Goal near deadline (7 days)")
    target_date = datetime.now() + timedelta(days=7)
    context4 = {
        "goal_id": str(uuid4()),
        "notifications_enabled": True,
        "notification_text": "⏰ Only 7 days left to complete your goal!",
        "preview_text": "Deadline approaching",
        "status": "in_progress",
        "end_date": target_date.isoformat(),
        "percent_complete": 50,
        "metadata": {},
    }
    result4 = await strategy.evaluate(test_user_id, context4)
    print(f"✓ Result: {result4}")
    if result4:
        print(f"  - Nudge ID: {result4.metadata['nudge_id']}")
        print(f"  - Priority: {result4.priority}")

    # Test 5: Notifications disabled (should return None)
    print("\n[TEST 5] Notifications disabled")
    context5 = {
        "goal_id": str(uuid4()),
        "notifications_enabled": False,
        "notification_text": "This should not be sent",
        "preview_text": "Disabled",
        "status": "pending",
        "metadata": {},
    }
    result5 = await strategy.evaluate(test_user_id, context5)
    print(f"✓ Result: {result5} (Expected: None)")

    # Test 6: Goal completed but open-ended (should return None)
    print("\n[TEST 6] Goal completed but open-ended (no nudge expected)")
    context6 = {
        "goal_id": str(uuid4()),
        "notifications_enabled": True,
        "notification_text": "Goal completed",
        "preview_text": "Completed",
        "status": "completed",
        "end_date": None,
        "no_end_date": True,
        "percent_complete": 100,
        "metadata": {},
    }
    result6 = await strategy.evaluate(test_user_id, context6)
    print(f"✓ Result: {result6} (Expected: None)")

    print("\n" + "="*80)
    print("TESTS COMPLETED")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(test_goal_nudge_scenarios())
