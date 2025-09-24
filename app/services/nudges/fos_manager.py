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


            payload = {
                "user_id": str(message.user_id),
                "nudge_type": message.nudge_type,
                "notification_text": message.payload.get("notification_text"),
                "preview_text": message.payload.get("preview_text"),
                "nudge_metadata": message.payload.get("metadata", {}),
                "priority": message.priority,
                "channel": message.channel,
                "deduplication_key": message.payload.get("deduplication_key"),
                "expires_at": message.expires_at.isoformat() if message.expires_at else None
            }
            
            response = await self.fos_client.post("/internal/nudges/", payload)

            if not response:
                raise Exception("FOS service request failed - no response")

            message_id = response.get("id") or response.get("message_id") or response.get("nudge_id")
            if not message_id:
                raise ValueError(f"FOS service did not return valid ID. Response: {response}")


            return str(message_id)

        except Exception as e:
            logger.error(f"fos_manager.enqueue_error: user_id={message.user_id}, error={str(e)}")
            raise

    async def get_pending_nudges(
        self,
        user_id: UUID,
        nudge_type: Optional[str] = None,
        status: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[NudgeRecord]:
        """Get nudges for a user from FOS service with enhanced filtering.

        Args:
            user_id: User ID to get nudges for
            nudge_type: Optional nudge type filter
            status: Optional list of statuses (defaults to ["pending"])
            limit: Optional limit on number of results

        Returns:
            List of nudge records matching filters

        Raises:
            Exception: If get operation fails

        """
        try:
            if status is None:
                status = ["pending"]



            endpoint = f"/internal/nudges/users/{user_id}"
            params = []

            if status:
                params.append(f"status={','.join(status)}")
            if nudge_type:
                params.append(f"nudge_type={nudge_type}")
            if limit:
                params.append(f"limit={limit}")

            if params:
                endpoint += "?" + "&".join(params)
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
                        metadata=nudge_data.get("nudge_metadata", {}),
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


            return nudges

        except Exception as e:
            logger.error(f"fos_manager.get_pending_error: user_id={user_id}, error={str(e)}")
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


            payload = {
                "nudge_ids": [str(nudge_id) for nudge_id in nudge_ids],  # Convert UUIDs to strings for JSON
                "status": "processing"   # NudgeStatus enum value
            }

            response = await self.fos_client.patch("/internal/nudges/bulk/status", payload)

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
                        metadata=nudge_data.get("nudge_metadata", {}),
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


            return updated_nudges

        except Exception as e:
            logger.error(f"fos_manager.mark_processing_error: nudge_count={len(nudge_ids)}, error={str(e)}")
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


            payload = {
                "nudge_ids": [str(nudge_id)],
                "status": "sent"
            }

            response = await self.fos_client.patch("/internal/nudges/bulk/status", payload)

            if not response:
                logger.warning(f"fos_manager.complete_no_response: nudge_id={nudge_id}")
                return False

            updated_count = response.get("updated_count", 0)
            success = updated_count > 0

            if not success:
                logger.warning(f"fos_manager.nudge_completion_failed: nudge_id={nudge_id}")

            return success

        except Exception as e:
            logger.error(f"fos_manager.complete_error: nudge_id={nudge_id}, error={str(e)}")
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


            endpoint = "/internal/nudges/stats"
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



            return stats

        except Exception as e:
            logger.error(f"fos_manager.get_stats_error: user_id={user_id}, error={str(e)}")
            raise
