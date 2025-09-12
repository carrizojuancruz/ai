import logging
from typing import List, Optional, Tuple
from uuid import UUID

from app.services.nudges.sqs_consumer import NudgeMessage, get_sqs_consumer

logger = logging.getLogger(__name__)


class IcebreakerProcessor:
    """Processes icebreaker nudges to find the best one for conversation start."""

    def __init__(self):
        self.sqs_consumer = get_sqs_consumer()

    async def get_best_icebreaker_for_user(self, user_id: UUID) -> Optional[Tuple[NudgeMessage, List[str]]]:
        try:
            logger.debug(f"icebreaker_processor.polling: user_id={user_id}")

            if not self.sqs_consumer:
                logger.error(f"icebreaker_processor.no_sqs_consumer: user_id={user_id}")
                return None, []

            all_nudges = await self.sqs_consumer.poll_nudges()
            logger.debug(f"icebreaker_processor.polled_total: user_id={user_id}, total_nudges={len(all_nudges)}")

            user_icebreakers = [
                nudge
                for nudge in all_nudges
                if (nudge.nudge_type == "memory_icebreaker" and nudge.user_id == str(user_id))
            ]

            logger.debug(f"icebreaker_processor.filtered: user_id={user_id}, icebreaker_count={len(user_icebreakers)}")

            if not user_icebreakers:
                logger.info(f"icebreaker_processor.no_icebreakers: user_id={user_id}")
                return None, []

            user_icebreakers.sort(key=lambda n: (n.priority, n.timestamp), reverse=True)

            best_nudge = user_icebreakers[0]
            receipt_handles_to_delete = [nudge.receipt_handle for nudge in user_icebreakers]

            logger.info(
                f"icebreaker_processor.found_best: user_id={user_id}, "
                f"best_priority={best_nudge.priority}, best_timestamp={best_nudge.timestamp}, "
                f"total_icebreakers={len(user_icebreakers)}, "
                f"best_message_id={best_nudge.message_id}"
            )

            return best_nudge, receipt_handles_to_delete

        except Exception as e:
            logger.error(f"icebreaker_processor.error: user_id={user_id}, error={str(e)}", exc_info=True)
            return None, []

    async def process_icebreaker_for_user(self, user_id: UUID) -> Optional[str]:
        try:
            logger.debug(f"icebreaker_processor.process_start: user_id={user_id}")

            best_nudge, receipt_handles_to_delete = await self.get_best_icebreaker_for_user(user_id)

            if not best_nudge:
                logger.debug(f"icebreaker_processor.no_best_nudge: user_id={user_id}")
                return None

            logger.debug(f"icebreaker_processor.extracting_text: user_id={user_id}, message_id={best_nudge.message_id}")
            icebreaker_text = self._extract_icebreaker_text(best_nudge)

            if not icebreaker_text:
                logger.warning(f"icebreaker_processor.no_text: user_id={user_id}, message_id={best_nudge.message_id}")
                return None

            logger.debug(f"icebreaker_processor.text_extracted: user_id={user_id}, text_length={len(icebreaker_text)}")

            if receipt_handles_to_delete:
                logger.debug(
                    f"icebreaker_processor.cleanup_start: user_id={user_id}, handles_count={len(receipt_handles_to_delete)}"
                )
                deleted_count = await self.sqs_consumer.delete_nudges(receipt_handles_to_delete)
                logger.info(
                    f"icebreaker_processor.cleanup_complete: user_id={user_id}, "
                    f"deleted_count={deleted_count}, total_queued={len(receipt_handles_to_delete)}"
                )

            logger.info(f"icebreaker_processor.processed: user_id={user_id}, text_preview={icebreaker_text[:100]}...")
            return icebreaker_text

        except Exception as e:
            logger.error(f"icebreaker_processor.process_error: user_id={user_id}, error={str(e)}", exc_info=True)
            return None

    def _extract_icebreaker_text(self, nudge: NudgeMessage) -> Optional[str]:
        try:
            logger.debug(f"icebreaker_processor.extract_start: message_id={nudge.message_id}")
            payload = nudge.nudge_payload
            logger.debug(
                f"icebreaker_processor.payload_keys: message_id={nudge.message_id}, keys={list(payload.keys())}"
            )

            notification_text = payload.get("notification_text")
            if notification_text and notification_text.strip():
                logger.debug(
                    f"icebreaker_processor.found_notification_text: message_id={nudge.message_id}, length={len(notification_text)}"
                )
                return notification_text.strip()

            metadata = payload.get("metadata", {})
            logger.debug(
                f"icebreaker_processor.metadata_keys: message_id={nudge.message_id}, keys={list(metadata.keys())}"
            )

            memory_text = metadata.get("memory_text")
            if memory_text and memory_text.strip():
                logger.debug(
                    f"icebreaker_processor.found_memory_text: message_id={nudge.message_id}, length={len(memory_text)}"
                )
                return f"Remember this? {memory_text.strip()}"

            preview_text = payload.get("preview_text")
            if preview_text and preview_text.strip():
                logger.debug(
                    f"icebreaker_processor.found_preview_text: message_id={nudge.message_id}, length={len(preview_text)}"
                )
                return preview_text.strip()

            logger.warning(f"icebreaker_processor.no_text_found: message_id={nudge.message_id}, payload={payload}")
            return None

        except Exception as e:
            logger.error(
                f"icebreaker_processor.extract_error: message_id={nudge.message_id}, error={str(e)}", exc_info=True
            )
            return None


_icebreaker_processor = None


def get_icebreaker_processor() -> IcebreakerProcessor:
    """Get the global icebreaker processor instance."""
    global _icebreaker_processor
    if _icebreaker_processor is None:
        _icebreaker_processor = IcebreakerProcessor()
    return _icebreaker_processor
