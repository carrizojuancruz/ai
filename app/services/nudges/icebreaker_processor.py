import logging
from typing import List, Optional, Tuple
from uuid import UUID

from app.core.app_state import get_fos_nudge_manager
from app.models.nudge import NudgeRecord

logger = logging.getLogger(__name__)


class IcebreakerProcessor:
    """Processes icebreaker nudges to find the best one for conversation start."""

    def __init__(self):
        self.fos_manager = get_fos_nudge_manager()

    async def get_best_icebreaker_for_user(self, user_id: UUID) -> Optional[Tuple[NudgeRecord, List[UUID]]]:
        try:
            logger.debug(f"icebreaker_processor.querying_fos: user_id={user_id}")

            memory_icebreakers = await self.fos_manager.get_pending_nudges(
                user_id,
                nudge_type="memory_icebreaker"
            )

            logger.debug(f"icebreaker_processor.filtered: user_id={user_id}, icebreaker_count={len(memory_icebreakers)}")

            if not memory_icebreakers:
                logger.info(f"icebreaker_processor.no_icebreakers: user_id={user_id}")
                return None, []

            # Sort by priority (desc) then created_at (asc) - highest priority, oldest first
            memory_icebreakers.sort(key=lambda n: (-n.priority, n.created_at))

            best_nudge = memory_icebreakers[0]
            nudge_ids_to_delete = [nudge.id for nudge in memory_icebreakers]

            logger.info(
                f"icebreaker_processor.found_best: user_id={user_id}, "
                f"best_priority={best_nudge.priority}, best_created={best_nudge.created_at}, "
                f"total_icebreakers={len(memory_icebreakers)}, "
                f"best_nudge_id={best_nudge.id}"
            )

            return best_nudge, nudge_ids_to_delete

        except Exception as e:
            logger.error(f"icebreaker_processor.error: user_id={user_id}, error={str(e)}", exc_info=True)
            return None, []

    async def process_icebreaker_for_user(self, user_id: UUID) -> Optional[str]:
        try:
            logger.debug(f"icebreaker_processor.process_start: user_id={user_id}")

            best_nudge, nudge_ids_to_delete = await self.get_best_icebreaker_for_user(user_id)

            if not best_nudge:
                logger.debug(f"icebreaker_processor.no_best_nudge: user_id={user_id}")
                return None

            logger.debug(f"icebreaker_processor.extracting_text: user_id={user_id}, nudge_id={best_nudge.id}")
            icebreaker_text = self._extract_icebreaker_text(best_nudge)

            if not icebreaker_text:
                logger.warning(f"icebreaker_processor.no_text: user_id={user_id}, nudge_id={best_nudge.id}")
                return None

            logger.debug(f"icebreaker_processor.text_extracted: user_id={user_id}, text_length={len(icebreaker_text)}")

            # Mark nudges as processing to prevent concurrent access
            if nudge_ids_to_delete:
                logger.debug(
                    f"icebreaker_processor.marking_processing: user_id={user_id}, nudge_count={len(nudge_ids_to_delete)}"
                )
                processing_nudges = await self.fos_manager.mark_processing(nudge_ids_to_delete)

                # Complete the processed nudges
                for nudge in processing_nudges:
                    await self.fos_manager.complete_nudge(nudge.id)

                logger.info(
                    f"icebreaker_processor.cleanup_complete: user_id={user_id}, "
                    f"processed_count={len(processing_nudges)}, total_queued={len(nudge_ids_to_delete)}"
                )

            logger.info(f"icebreaker_processor.processed: user_id={user_id}, text_preview={icebreaker_text[:100]}...")
            return icebreaker_text

        except Exception as e:
            logger.error(f"icebreaker_processor.process_error: user_id={user_id}, error={str(e)}", exc_info=True)
            return None

    def _extract_icebreaker_text(self, nudge: NudgeRecord) -> Optional[str]:
        try:
            logger.debug(f"icebreaker_processor.extract_start: nudge_id={nudge.id}")

            # First try notification_text
            if nudge.notification_text and nudge.notification_text.strip():
                logger.debug(
                    f"icebreaker_processor.found_notification_text: nudge_id={nudge.id}, length={len(nudge.notification_text)}"
                )
                return nudge.notification_text.strip()

            # Then try metadata
            metadata = nudge.metadata or {}
            logger.debug(
                f"icebreaker_processor.metadata_keys: nudge_id={nudge.id}, keys={list(metadata.keys())}"
            )

            memory_text = metadata.get("memory_text")
            if memory_text and memory_text.strip():
                logger.debug(
                    f"icebreaker_processor.found_memory_text: nudge_id={nudge.id}, length={len(memory_text)}"
                )
                return f"Remember this? {memory_text.strip()}"

            # Finally try preview_text
            if nudge.preview_text and nudge.preview_text.strip():
                logger.debug(
                    f"icebreaker_processor.found_preview_text: nudge_id={nudge.id}, length={len(nudge.preview_text)}"
                )
                return nudge.preview_text.strip()

            logger.warning(f"icebreaker_processor.no_text_found: nudge_id={nudge.id}, metadata={metadata}")
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
