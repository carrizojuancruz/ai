
import json
import os

BLOCKED_TOPICS_FILE = os.path.join(os.path.dirname(__file__), "blocked_topics.json")

def _load_blocked_topics():
    if os.path.exists(BLOCKED_TOPICS_FILE):
        with open(BLOCKED_TOPICS_FILE, "r") as f:
            return json.load(f)
    return {}

def _save_blocked_topics(data):
    with open(BLOCKED_TOPICS_FILE, "w") as f:
        json.dump(data, f, indent=4)
