import random
from typing import Any, Dict, Optional
from uuid import UUID

from app.observability.logging_config import get_logger
from app.repositories.s3_vectors_store import get_s3_vectors_store
from app.services.nudges.evaluator import NudgeCandidate
from app.services.nudges.strategies.base import NudgeStrategy

logger = get_logger(__name__)


class MemoryNudgeStrategy(NudgeStrategy):
    def __init__(self):
        self.s3_vectors = get_s3_vectors_store()
        self.memory_templates = [
            "Remember this? {memory}...",
            "I was thinking about when you mentioned: {memory}",
            "This came up in my memories: {memory}",
            "Looking back at your journey: {memory}",
        ]

    @property
    def nudge_type(self) -> str:
        return "memory_icebreaker"

    @property
    def requires_fos_text(self) -> bool:
        return False

    async def evaluate(self, user_id: UUID, context: Dict[str, Any]) -> Optional[NudgeCandidate]:
        try:
            importance_filter = context.get("importance", "high")
            topic_filter = context.get("topic")

            filter_dict = {"user_id": str(user_id), "importance_bin": importance_filter}

            if topic_filter:
                filter_dict["topic_key"] = topic_filter

            memories = await self.s3_vectors.search_by_filter(filter_dict=filter_dict, limit=20)

            if not memories:
                logger.debug("memory_strategy.no_memories", user_id=str(user_id), filters=filter_dict)
                return None

            selected_memory = random.choice(memories)

            memory_text = selected_memory.get("text", "")[:100]
            template = random.choice(self.memory_templates)
            notification_text = template.format(memory=memory_text)

            preview_options = [
                "Memory from your past",
                "Something to remember",
                "A moment from your journey",
                f"About {selected_memory.get('topic_key', 'your story')}",
            ]
            preview_text = random.choice(preview_options)

            priority = self.get_priority({"importance": selected_memory.get("importance_bin", "medium")})

            return NudgeCandidate(
                user_id=user_id,
                nudge_type=self.nudge_type,
                priority=priority,
                notification_text=notification_text,
                preview_text=preview_text,
                metadata={
                    "memory_id": selected_memory.get("id"),
                    "memory_text": memory_text,
                    "topic": selected_memory.get("topic_key"),
                    "importance": selected_memory.get("importance_bin"),
                },
            )

        except Exception as e:
            logger.error("memory_strategy.evaluation_failed", user_id=str(user_id), error=str(e))
            return None

    def get_priority(self, context: Dict[str, Any]) -> int:
        importance = context.get("importance", "medium")
        if importance == "high":
            return 2
        else:
            return 1

    async def validate_conditions(self, user_id: UUID) -> bool:
        return True
