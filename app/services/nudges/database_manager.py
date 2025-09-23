from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict
from uuid import UUID

from app.models.nudge import NudgeRecord, NudgeStatus
from app.repositories.database_service import get_database_service
from app.services.queue.sqs_manager import NudgeMessage

logger = logging.getLogger(__name__)


class DatabaseNudgeManager:
    """Database-backed nudge manager that replaces SQS functionality."""

    def __init__(self):
        self.db_service = get_database_service()
        self._in_flight_messages: Dict[str, datetime] = {}

    async def enqueue_nudge(self, nudge: NudgeMessage) -> str:
        """Store nudge in database instead of SQS queue."""
        try:
            dedup_key = nudge.deduplication_key

            logger.debug(
                f"database.enqueue_attempt: user_id={nudge.user_id}, nudge_type={nudge.nudge_type}, "
                f"priority={nudge.priority}, dedup_key={dedup_key}, expires_at={nudge.expires_at.isoformat()}"
            )

            # Mark existing nudges as replaced (soft deduplication)
            await self._mark_as_replaced(dedup_key)

            # Create NudgeRecord from NudgeMessage
            nudge_record = NudgeRecord(
                id=UUID(nudge.message_id),
                user_id=UUID(nudge.user_id),
                nudge_type=nudge.nudge_type,
                priority=nudge.priority,
                status=NudgeStatus.PENDING,
                channel=nudge.channel,
                notification_text=nudge.payload.get("notification_text", ""),
                preview_text=nudge.payload.get("preview_text"),
                metadata=nudge.payload.get("metadata", {}),
                deduplication_key=dedup_key,
                is_processed=False,
                processed_at=None,
                created_at=nudge.timestamp,
                updated_at=nudge.timestamp,
            )

            # Store in database
            async with self.db_service.get_session() as session:
                nudge_repo = self.db_service.get_nudge_repository(session)
                saved_record = await nudge_repo.create_nudge(nudge_record)

            # Track in memory for deduplication
            self._in_flight_messages[dedup_key] = nudge.timestamp

            logger.info(
                f"database.nudge_enqueued: id={saved_record.id}, user_id={nudge.user_id}, "
                f"nudge_type={nudge.nudge_type}, priority={nudge.priority}, dedup_key={dedup_key}"
            )

            return str(saved_record.id)

        except Exception as e:
            logger.error(
                f"database.enqueue_failed: {str(e)}",
                extra={"user_id": nudge.user_id, "nudge_type": nudge.nudge_type}
            )
            raise

    async def _mark_as_replaced(self, dedup_key: str) -> None:
        """Mark existing nudges with same deduplication key as replaced."""
        if dedup_key in self._in_flight_messages:
            logger.debug(f"database.replacing_inflight_nudge: dedup_key={dedup_key}")

        self._in_flight_messages[dedup_key] = datetime.now(timezone.utc)

    async def get_pending_nudges(self, user_id: UUID, limit: int = 100) -> list[NudgeRecord]:
        """Get pending nudges for a user (replaces SQS polling)."""
        try:
            async with self.db_service.get_session() as session:
                nudge_repo = self.db_service.get_nudge_repository(session)
                nudges = await nudge_repo.get_user_nudges(
                    user_id=user_id,
                    status=NudgeStatus.PENDING,
                    limit=limit
                )

            # Filter expired nudges
            now = datetime.utcnow()
            valid_nudges = []
            expired_ids = []

            for nudge in nudges:
                # Calculate expiration (12 hours after creation by default)
                expires_at = nudge.created_at + timedelta(hours=12)
                if now > expires_at:
                    expired_ids.append(nudge.id)
                else:
                    valid_nudges.append(nudge)

            # Clean up expired nudges
            if expired_ids:
                await self._cleanup_expired_nudges(expired_ids)

            logger.debug(
                f"database.pending_nudges: user_id={user_id}, valid={len(valid_nudges)}, "
                f"expired={len(expired_ids)}"
            )

            return valid_nudges

        except Exception as e:
            logger.error(f"database.get_pending_failed: user_id={user_id}, error={str(e)}")
            return []

    async def mark_processing(self, nudge_ids: list[UUID]) -> list[NudgeRecord]:
        """Mark nudges as processing (replaces SQS message visibility timeout)."""
        try:
            async with self.db_service.get_session() as session:
                nudge_repo = self.db_service.get_nudge_repository(session)
                processing_nudges = await nudge_repo.mark_processing(nudge_ids)

            logger.info(f"database.marked_processing: count={len(processing_nudges)}")
            return processing_nudges

        except Exception as e:
            logger.error(f"database.mark_processing_failed: nudge_ids={nudge_ids}, error={str(e)}")
            return []

    async def complete_nudge(self, nudge_id: UUID) -> bool:
        """Mark nudge as completed (replaces SQS message deletion)."""
        try:
            async with self.db_service.get_session() as session:
                nudge_repo = self.db_service.get_nudge_repository(session)
                updated_nudge = await nudge_repo.update_status(
                    nudge_id=nudge_id,
                    status=NudgeStatus.PROCESSED,
                    processed_at=True
                )

            if updated_nudge:
                logger.info(f"database.nudge_completed: id={nudge_id}")
                return True
            else:
                logger.warning(f"database.nudge_not_found: id={nudge_id}")
                return False

        except Exception as e:
            logger.error(f"database.complete_failed: nudge_id={nudge_id}, error={str(e)}")
            return False

    async def delete_nudges(self, nudge_ids: list[UUID]) -> int:
        """Delete nudges from database (cleanup operation)."""
        try:
            async with self.db_service.get_session() as session:
                nudge_repo = self.db_service.get_nudge_repository(session)
                deleted_count = await nudge_repo.delete_by_ids(nudge_ids)

            logger.info(f"database.nudges_deleted: count={deleted_count}")
            return deleted_count

        except Exception as e:
            logger.error(f"database.delete_failed: nudge_ids={nudge_ids}, error={str(e)}")
            return 0

    async def _cleanup_expired_nudges(self, expired_ids: list[UUID]) -> None:
        """Clean up expired nudges."""
        try:
            deleted_count = await self.delete_nudges(expired_ids)
            logger.info(f"database.expired_cleanup: deleted={deleted_count}")
        except Exception as e:
            logger.error(f"database.cleanup_failed: error={str(e)}")

    async def is_latest_nudge(self, user_id: str, nudge_type: str, timestamp: str) -> bool:
        """Check if nudge is still the latest (for backward compatibility)."""
        dedup_key = f"{user_id}:{nudge_type}"
        latest_timestamp = self._in_flight_messages.get(dedup_key)
        if not latest_timestamp:
            return True

        try:
            message_time = datetime.fromisoformat(timestamp)
            return message_time >= latest_timestamp
        except Exception as e:
            logger.error(f"database.timestamp_comparison_failed: {str(e)}")
            return True
