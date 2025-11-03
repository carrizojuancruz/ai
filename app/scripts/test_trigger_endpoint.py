"""Test trigger endpoint for goal nudges.

Usage with server running:
    poetry run python -m app.scripts.test_trigger_endpoint
"""
import sys

import requests

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8000"
USER_ID = "ba5c5db4-d3fb-4ca8-9445-1c221ea502a8"


def test_trigger_goal_nudge():
    print("\n" + "="*80)
    print("TESTING /nudges/trigger ENDPOINT FOR GOAL_BASED NUDGES")
    print("="*80)

    print(f"\n[TEST] Triggering goal nudges for user: {USER_ID}")
    print("Request:")
    payload = {
        "user_id": USER_ID,
        "nudge_type": "goal_based",
        "force": True
    }
    print(f"  POST {BASE_URL}/nudges/trigger")
    print(f"  Body: {payload}")

    try:
        response = requests.post(
            f"{BASE_URL}/nudges/trigger",
            json=payload,
            timeout=30
        )

        print(f"\nResponse Status: {response.status_code}")
        print("Response Body:")

        if response.status_code == 200:
            data = response.json()
            print(f"  Status: {data.get('status')}")
            print(f"  Goals Checked: {data.get('goals_checked', 'N/A')}")
            print(f"  Nudges Triggered: {data.get('nudges_triggered', 'N/A')}")

            if data.get("status") == "success":
                print("\n[SUCCESS] Nudges triggered!")
                if data.get("results"):
                    print(f"  Details: {data['results']}")
            elif data.get("status") == "skipped":
                print(f"\n[SKIPPED] {data.get('reason')}")
            else:
                print("\n[UNKNOWN] Unknown status")
        else:
            print(f"[ERROR] {response.text}")

    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Could not connect to server")
        print("  Make sure the server is running:")
        print("  poetry run python -m uvicorn app.main:app --reload")
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")

    print("\n" + "="*80)
    print("TEST COMPLETED")
    print("="*80 + "\n")


if __name__ == "__main__":
    test_trigger_goal_nudge()
