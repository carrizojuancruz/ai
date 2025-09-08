import json
import logging
import os
from typing import Dict, List

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool, tool

from app.knowledge.service import get_knowledge_service

logger = logging.getLogger(__name__)

BLOCKED_TOPICS_FILE = os.path.join(os.path.dirname(__file__), "blocked_topics.json")

def _load_blocked_topics():
    if os.path.exists(BLOCKED_TOPICS_FILE):
        with open(BLOCKED_TOPICS_FILE, "r") as f:
            return json.load(f)
    return {}

def _save_blocked_topics(data):
    with open(BLOCKED_TOPICS_FILE, "w") as f:
        json.dump(data, f, indent=4)

@tool
def manage_blocked_topics(config: RunnableConfig, topic: str, action: str) -> str:
    """Manage blocked topics for a user.

    - action: 'add' to add, 'remove' to remove.
    """
    user_id = config.get("configurable", {}).get("user_id")
    print(f"manage_blocked_topics called with user_id={user_id}, topic={topic}, action={action}")
    data = _load_blocked_topics()
    if user_id not in data:
        data[user_id] = []
    if action == "add" and topic not in data[user_id]:
        data[user_id].append(topic)
        _save_blocked_topics(data)
        return f"Topic '{topic}' added for user {user_id}."
    elif action == "remove" and topic in data[user_id]:
        data[user_id].remove(topic)
        _save_blocked_topics(data)
        return f"Topic '{topic}' removed for user {user_id}."
    return f"Invalid action '{action}' or topic already in desired state."

@tool
def check_blocked_topic(user_id: str, topic: str) -> bool:
    """Check if a topic is blocked for a user.

    Returns True if blocked, False otherwise.
    """
    data = _load_blocked_topics()
    return topic in data.get(user_id, [])

async def query_knowledge_base(query: str) -> str:
    knowledge_service = get_knowledge_service()
    results: List[Dict] = await knowledge_service.search(query)
    return json.dumps(results, ensure_ascii=False)


knowledge_search_tool = StructuredTool.from_function(
    coroutine=query_knowledge_base,
    name="query_knowledge_base",
    description=(
        "Search the internal knowledge base for relevant passages that ground the current user question. "
        "Use this when the user asks for factual information that should be supported by our internal sources "
    )
)
