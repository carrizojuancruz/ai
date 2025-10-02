import logging
from typing import Optional
from uuid import UUID

from app.core.app_state import get_fos_nudge_manager
from app.models.nudge import NudgeRecord

logger = logging.getLogger(__name__)


class IcebreakerProcessor:
    """Processes memory_icebreaker nudges exclusively to find the best one for conversation start."""

    def __init__(self):
        self.fos_manager = get_fos_nudge_manager()

    async def get_best_icebreaker_for_user(self, user_id: UUID) -> Optional[NudgeRecord]:
        try:
            logger.debug(f"icebreaker_processor.querying_fos: user_id={user_id}")

            memory_icebreakers = await self.fos_manager.get_pending_nudges(
                user_id,
                nudge_type="memory_icebreaker",
                status=["pending", "processing"]
            )

            logger.debug(f"icebreaker_processor.filtered: user_id={user_id}, icebreaker_count={len(memory_icebreakers)}")

            if not memory_icebreakers:
                logger.info(f"icebreaker_processor.no_icebreakers: user_id={user_id}")
                return None

            memory_icebreakers.sort(key=lambda n: (-n.priority, n.created_at))

            best_nudge = memory_icebreakers[0]

            logger.info(
                f"icebreaker_processor.found_best: user_id={user_id}, "
                f"best_priority={best_nudge.priority}, best_created={best_nudge.created_at}, "
                f"total_icebreakers={len(memory_icebreakers)}, unused_icebreakers={len(memory_icebreakers) - 1}, "
                f"best_nudge_id={best_nudge.id}"
            )

            return best_nudge

        except Exception as e:
            logger.error(f"icebreaker_processor.error: user_id={user_id}, error={str(e)}", exc_info=True)
            return None

    async def process_icebreaker_for_user(self, user_id: UUID) -> Optional[str]:
        try:
            logger.debug(f"icebreaker_processor.process_start: user_id={user_id}")

            best_nudge = await self.get_best_icebreaker_for_user(user_id)

            if not best_nudge:
                logger.debug(f"icebreaker_processor.no_best_nudge: user_id={user_id}")
                return None

            logger.debug(f"icebreaker_processor.extracting_text: user_id={user_id}, nudge_id={best_nudge.id}")
            icebreaker_text = self._extract_icebreaker_text(best_nudge)

            if not icebreaker_text:
                logger.warning(f"icebreaker_processor.no_text: user_id={user_id}, nudge_id={best_nudge.id}")
                return None

            logger.debug(f"icebreaker_processor.text_extracted: user_id={user_id}, text_length={len(icebreaker_text)}")

            logger.debug(f"icebreaker_processor.marking_processing: user_id={user_id}, nudge_id={best_nudge.id}")

            try:
                await self.fos_manager.mark_processing([best_nudge.id])
            except Exception as e:
                logger.warning(f"icebreaker_processor.mark_processing_failed: user_id={user_id}, error={str(e)}")

            try:
                success = await self.fos_manager.complete_nudge(best_nudge.id)
                if success:
                    logger.info(f"icebreaker_processor.cleanup_complete: user_id={user_id}, nudge_completed=True")
                else:
                    logger.warning(f"icebreaker_processor.cleanup_failed: user_id={user_id}, nudge_id={best_nudge.id}")
            except Exception as e:
                logger.error(f"icebreaker_processor.nudge_completion_error: user_id={user_id}, nudge_id={best_nudge.id}, error={str(e)}")

            logger.info(f"icebreaker_processor.processed: user_id={user_id}, text_preview={icebreaker_text[:100]}...")
            return icebreaker_text

        except Exception as e:
            logger.error(f"icebreaker_processor.process_error: user_id={user_id}, error={str(e)}", exc_info=True)
            return None

    def _extract_icebreaker_text(self, nudge: NudgeRecord) -> Optional[str]:
        try:
            logger.debug(f"icebreaker_processor.extract_start: nudge_id={nudge.id}")

            if nudge.notification_text and nudge.notification_text.strip():
                logger.debug(
                    f"icebreaker_processor.found_notification_text: nudge_id={nudge.id}, length={len(nudge.notification_text)}"
                )
                return nudge.notification_text.strip()

            memory_text = nudge.memory_text
            logger.debug(
                f"icebreaker_processor.memory_fields: nudge_id={nudge.id}, memory_id={nudge.memory_id}, has_text={bool(memory_text)}"
            )

            if memory_text and memory_text.strip():
                logger.debug(
                    f"icebreaker_processor.found_memory_text: nudge_id={nudge.id}, length={len(memory_text)}"
                )
                return f"Remember this? {memory_text.strip()}"

            if nudge.preview_text and nudge.preview_text.strip():
                logger.debug(
                    f"icebreaker_processor.found_preview_text: nudge_id={nudge.id}, length={len(nudge.preview_text)}"
                )
                return nudge.preview_text.strip()

            logger.warning(f"icebreaker_processor.no_text_found: nudge_id={nudge.id}, memory_id={nudge.memory_id}")
            return None

        except Exception as e:
            logger.error(
                f"icebreaker_processor.extract_error: nudge_id={nudge.id}, error={str(e)}", exc_info=True
            )
            return None


_icebreaker_processor = None


def get_icebreaker_processor() -> IcebreakerProcessor:
    """Get the global icebreaker processor instance."""
    global _icebreaker_processor
    if _icebreaker_processor is None:
        _icebreaker_processor = IcebreakerProcessor()
    return _icebreaker_processor
