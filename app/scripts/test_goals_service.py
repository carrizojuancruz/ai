"""Test script for Goals Service integration with nudges.

Usage:
    poetry run python -m app.scripts.test_goals_service
"""
import asyncio
from uuid import UUID

from app.observability.logging_config import get_logger
from app.services.goals import get_goals_service

logger = get_logger(__name__)


async def test_goals_service():
    print("\n" + "="*80)
    print("TESTING GOALS SERVICE + NUDGES INTEGRATION")
    print("="*80)

    # User ID from your streamlit app
    test_user_id = UUID("ba5c5db4-d3fb-4ca8-9445-1c221ea502a8")

    goals_service = get_goals_service()

    # Test 1: Get user goals
    print("\n[TEST 1] Fetching user goals...")
    try:
        goals = await goals_service.get_user_goals(test_user_id)
        print(f"✓ Found {len(goals)} goal(s)")
        for goal in goals:
            print(f"  - Goal: {goal.goal.title}")
            print(f"    Status: {goal.status.value}")
            print(f"    Progress: {goal.progress.percent_complete}%")
            print(f"    Notifications: {'enabled' if goal.notifications_enabled else 'disabled'}")
    except Exception as e:
        print(f"✗ Error: {e}")

    # Test 2: Check nudges for specific goals
    print("\n[TEST 2] Checking nudges for each goal...")
    if goals:
        for goal in goals:
            try:
                result = await goals_service.check_and_trigger_nudge(goal)
                if result:
                    print(f"✓ Nudge triggered for: {goal.goal.title}")
                    print(f"  Result: {result}")
                else:
                    print(f"- No nudge needed for: {goal.goal.title}")
            except Exception as e:
                print(f"✗ Error checking goal {goal.goal.title}: {e}")
    else:
        print("- No goals found for user")

    # Test 3: Batch check all goals
    print("\n[TEST 3] Running batch check for all goals needing notifications...")
    try:
        result = await goals_service.check_all_goals_for_nudges(days_ahead=7)
        print("✓ Batch check complete:")
        print(f"  Total goals checked: {result['total']}")
        print(f"  Nudges triggered: {result['triggered']}")
        print(f"  Skipped: {result['skipped']}")
    except Exception as e:
        print(f"✗ Error: {e}")

    print("\n" + "="*80)
    print("TESTS COMPLETED")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(test_goals_service())
