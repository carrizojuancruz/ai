"""FOS Nudge Manager - HTTP client for FOS service integration.

This service replaces the DatabaseNudgeManager and provides HTTP-based
communication with the FOS service for nudge operations, leveraging the
existing FOSHttpClient infrastructure.
"""

import logging
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.nudge import NudgeRecord
from app.services.external_context.http_client import FOSHttpClient
from app.services.nudges.models import NudgeMessage

logger = logging.getLogger(__name__)


class FOSNudgeStats(BaseModel):
    """FOS service nudge queue statistics."""

    pending_count: int
    processing_count: int
    total_count: int


class FOSNudgeManager:
    """HTTP client for FOS service nudge operations.

    Provides the same interface as DatabaseNudgeManager but communicates
    with FOS service via HTTP API using the existing FOSHttpClient.
    """

    def __init__(self):
        """Initialize FOS nudge manager using existing FOS HTTP client."""
        self.fos_client = FOSHttpClient()
        logger.info("fos_manager.initialized: using existing FOSHttpClient")

    async def enqueue_nudge(self, message: NudgeMessage) -> str:
        """Enqueue a nudge message via FOS service.

        Args:
            message: Nudge message to enqueue

        Returns:
            Message ID from FOS service

        Raises:
            Exception: If enqueue operation fails

        """
        try:
            logger.debug(f"fos_manager.enqueue_nudge: user_id={message.user_id}, nudge_type={message.nudge_type}")

            # Convert NudgeMessage to dict for JSON serialization
            payload = {
                "user_id": str(message.user_id),
                "nudge_type": message.nudge_type,
                "payload": message.payload,
                "priority": message.priority,
                "channel": message.channel
            }

            response = await self.fos_client.post("/api/nudges", payload)

            if not response:
                raise Exception("FOS service request failed - no response")

            message_id = response.get("message_id")
            if not message_id:
                raise ValueError("FOS service did not return message_id")

            logger.info(f"fos_manager.nudge_enqueued: user_id={message.user_id}, message_id={message_id}")
            return message_id

        except Exception as e:
            logger.error(
                f"fos_manager.enqueue_error: user_id={message.user_id}, error={str(e)}",
                exc_info=True
            )
            raise

    async def get_pending_nudges(self, user_id: UUID) -> List[NudgeRecord]:
        """Get pending nudges for a user from FOS service.

        Args:
            user_id: User ID to get nudges for

        Returns:
            List of pending nudge records

        Raises:
            Exception: If get operation fails

        """
        try:
            logger.debug(f"fos_manager.get_pending_nudges: user_id={user_id}")

            endpoint = f"/api/nudges?user_id={user_id}&status=pending"
            response = await self.fos_client.get(endpoint)

            if not response:
                logger.warning(f"fos_manager.no_response: user_id={user_id}")
                return []

            nudges_data = response.get("nudges", [])
            nudges = []

            for nudge_data in nudges_data:
                try:
                    # Convert FOS response to NudgeRecord
                    nudge = NudgeRecord(
                        id=UUID(nudge_data["id"]),
                        user_id=UUID(nudge_data["user_id"]),
                        nudge_type=nudge_data["nudge_type"],
                        notification_text=nudge_data["notification_text"],
                        preview_text=nudge_data["preview_text"],
                        metadata=nudge_data.get("metadata", {}),
                        priority=nudge_data.get("priority", 1),
                        status=nudge_data["status"],
                        channel=nudge_data.get("channel", "app"),
                        created_at=nudge_data["created_at"],
                        updated_at=nudge_data.get("updated_at")
                    )
                    nudges.append(nudge)
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"fos_manager.invalid_nudge_data: data={nudge_data}, error={str(e)}")
                    continue

            logger.debug(f"fos_manager.pending_nudges_retrieved: user_id={user_id}, count={len(nudges)}")
            return nudges

        except Exception as e:
            logger.error(
                f"fos_manager.get_pending_error: user_id={user_id}, error={str(e)}",
                exc_info=True
            )
            raise

    async def mark_processing(self, nudge_ids: List[UUID]) -> List[NudgeRecord]:
        """Mark nudges as processing via FOS service.

        Args:
            nudge_ids: List of nudge IDs to mark as processing

        Returns:
            List of nudge records that were successfully marked as processing

        Raises:
            Exception: If mark processing operation fails

        """
        try:
            logger.debug(f"fos_manager.mark_processing: nudge_count={len(nudge_ids)}")

            payload = {
                "nudge_ids": [str(nudge_id) for nudge_id in nudge_ids],
                "status": "processing"
            }

            response = await self.fos_client.put("/api/nudges/status", payload)

            if not response:
                logger.warning(f"fos_manager.mark_processing_no_response: nudge_count={len(nudge_ids)}")
                return []

            updated_nudges_data = response.get("updated_nudges", [])
            updated_nudges = []

            for nudge_data in updated_nudges_data:
                try:
                    nudge = NudgeRecord(
                        id=UUID(nudge_data["id"]),
                        user_id=UUID(nudge_data["user_id"]),
                        nudge_type=nudge_data["nudge_type"],
                        notification_text=nudge_data["notification_text"],
                        preview_text=nudge_data["preview_text"],
                        metadata=nudge_data.get("metadata", {}),
                        priority=nudge_data.get("priority", 1),
                        status=nudge_data["status"],
                        channel=nudge_data.get("channel", "app"),
                        created_at=nudge_data["created_at"],
                        updated_at=nudge_data.get("updated_at")
                    )
                    updated_nudges.append(nudge)
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"fos_manager.invalid_updated_nudge: data={nudge_data}, error={str(e)}")
                    continue

            logger.info(f"fos_manager.nudges_marked_processing: updated_count={len(updated_nudges)}")
            return updated_nudges

        except Exception as e:
            logger.error(
                f"fos_manager.mark_processing_error: nudge_count={len(nudge_ids)}, error={str(e)}",
                exc_info=True
            )
            raise

    async def complete_nudge(self, nudge_id: UUID) -> bool:
        """Mark a nudge as completed via FOS service.

        Args:
            nudge_id: ID of nudge to mark as completed

        Returns:
            True if successfully completed, False otherwise

        Raises:
            Exception: If complete operation fails

        """
        try:
            logger.debug(f"fos_manager.complete_nudge: nudge_id={nudge_id}")

            payload = {
                "nudge_ids": [str(nudge_id)],
                "status": "sent"  # FOS uses 'sent' to indicate completion
            }

            response = await self.fos_client.put("/api/nudges/status", payload)

            if not response:
                logger.warning(f"fos_manager.complete_no_response: nudge_id={nudge_id}")
                return False

            updated_count = response.get("updated_count", 0)
            success = updated_count > 0

            if success:
                logger.info(f"fos_manager.nudge_completed: nudge_id={nudge_id}")
            else:
                logger.warning(f"fos_manager.nudge_completion_failed: nudge_id={nudge_id}")

            return success

        except Exception as e:
            logger.error(
                f"fos_manager.complete_error: nudge_id={nudge_id}, error={str(e)}",
                exc_info=True
            )
            raise

    async def get_queue_stats(self, user_id: Optional[UUID] = None) -> FOSNudgeStats:
        """Get nudge queue statistics from FOS service.

        Args:
            user_id: Optional user ID to filter stats

        Returns:
            Queue statistics

        Raises:
            Exception: If stats operation fails

        """
        try:
            logger.debug(f"fos_manager.get_queue_stats: user_id={user_id}")

            endpoint = "/api/nudges/stats"
            if user_id:
                endpoint += f"?user_id={user_id}"

            response = await self.fos_client.get(endpoint)

            if not response:
                logger.warning(f"fos_manager.stats_no_response: user_id={user_id}")
                return FOSNudgeStats(pending_count=0, processing_count=0, total_count=0)

            stats = FOSNudgeStats(
                pending_count=response.get("pending_count", 0),
                processing_count=response.get("processing_count", 0),
                total_count=response.get("total_count", 0)
            )

            logger.debug(
                f"fos_manager.stats_retrieved: user_id={user_id}, "
                f"pending={stats.pending_count}, processing={stats.processing_count}, total={stats.total_count}"
            )

            return stats

        except Exception as e:
            logger.error(
                f"fos_manager.get_stats_error: user_id={user_id}, error={str(e)}",
                exc_info=True
            )
            raise

    async def health_check(self) -> bool:
        """Check if FOS service is healthy and reachable.

        Returns:
            True if service is healthy, False otherwise

        """
        try:
            logger.debug("fos_manager.health_check")

            response = await self.fos_client.get("/api/health")

            if not response:
                return False

            status = response.get("status", "").lower()
            healthy = status in ["ok", "healthy", "up"]

            logger.debug(f"fos_manager.health_check_result: healthy={healthy}, status={status}")
            return healthy

        except Exception as e:
            logger.warning(f"fos_manager.health_check_failed: error={str(e)}")
            return False
