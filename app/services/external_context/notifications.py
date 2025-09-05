from typing import Any, Dict, Literal, Optional
from uuid import UUID

from app.observability.logging_config import get_logger

from .http_client import FOSHttpClient

logger = get_logger(__name__)


class NotificationsClient:
    def __init__(self):
        self.fos_client = FOSHttpClient()

    async def create_notification(
        self,
        user_id: UUID,
        thread_id: str,
        channel: Literal["push", "in_app"],
        preview_text: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        try:
            payload = {
                "user_id": str(user_id),
                "thread_id": thread_id,
                "channel": channel,
                "preview_text": preview_text,
                "manifestation": {"timing": "immediate"},
            }

            if title:
                payload["title"] = title

            if metadata:
                payload["metadata"] = metadata

            logger.info(
                "nudge.notification.create",
                extra={
                    "user_id": str(user_id),
                    "thread_id": thread_id,
                    "channel": channel,
                },
            )

            response = await self.fos_client.post("/notifications/create", payload)

            if response:
                logger.info(
                    "nudge.notification.created",
                    extra={
                        "user_id": str(user_id),
                        "thread_id": thread_id,
                        "notification_id": response.get("notification_id"),
                    },
                )
                return True

            logger.warning(
                "nudge.notification.failed",
                extra={
                    "user_id": str(user_id),
                    "reason": "no_response",
                },
            )
            return False

        except Exception as e:
            logger.error(
                "nudge.notification.error",
                extra={
                    "user_id": str(user_id),
                    "error": str(e),
                },
            )
            return False

    async def update_notification_status(
        self,
        notification_id: str,
        status: Literal["delivered", "read", "dismissed", "failed"],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        try:
            payload = {
                "status": status,
            }

            if metadata:
                payload["metadata"] = metadata

            response = await self.fos_client.put(f"/notifications/{notification_id}/status", payload)

            return response is not None

        except Exception as e:
            logger.error(f"Failed to update notification status: {e}")
            return False

    async def get_user_notifications(
        self,
        user_id: UUID,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> Optional[list[Dict[str, Any]]]:
        try:
            endpoint = f"/notifications/user/{user_id}"
            params = []

            if status:
                params.append(f"status={status}")
            params.append(f"limit={limit}")

            if params:
                endpoint += "?" + "&".join(params)

            response = await self.fos_client.get(endpoint)

            if response:
                return response.get("notifications", [])

            return None

        except Exception as e:
            logger.error(f"Failed to get user notifications: {e}")
            return None
