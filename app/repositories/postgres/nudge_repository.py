from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import NudgeORM
from app.models.nudge import NudgeChannel, NudgeRecord, NudgeStatus
from app.repositories.interfaces.nudge_repository import NudgeRepository


class PostgresNudgeRepository(NudgeRepository):
    """PostgreSQL implementation of NudgeRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_nudge(
        self,
        user_id: UUID,
        nudge_type: str,
        priority: int,
        channel: NudgeChannel,
        notification_text: str,
        preview_text: str,
        metadata: dict | None = None,
        scheduled_for: datetime | None = None
    ) -> UUID:
        """Create a new nudge and return its ID."""
        nudge_orm = NudgeORM(
            user_id=user_id,
            nudge_type=nudge_type,
            priority=priority,
            channel=channel.value,
            notification_text=notification_text,
            preview_text=preview_text,
            nudge_metadata=metadata or {},
            status=NudgeStatus.PENDING.value
        )

        self.session.add(nudge_orm)
        await self.session.commit()
        await self.session.refresh(nudge_orm)
        return nudge_orm.id

    async def get_pending_nudges(self, limit: int = 10) -> list[NudgeRecord]:
        """Get pending nudges that are ready to be processed."""
        query = (
            select(NudgeORM)
            .where(NudgeORM.status == NudgeStatus.PENDING.value)
            .where(
                # Either no scheduled time or scheduled time has passed
                (NudgeORM.scheduled_for.is_(None)) |
                (NudgeORM.scheduled_for <= datetime.utcnow())
            )
            .order_by(NudgeORM.priority.asc(), NudgeORM.created_at.asc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        nudges = result.scalars().all()
        return [self._to_nudge_record(nudge) for nudge in nudges]

    async def mark_processing(self, nudge_id: UUID) -> bool:
        """Mark nudge as processing using row-level locking. Returns True if successful."""
        # Use FOR UPDATE SKIP LOCKED for atomic processing without blocking
        query = (
            select(NudgeORM)
            .where(NudgeORM.id == nudge_id)
            .where(NudgeORM.status == NudgeStatus.PENDING.value)
            .with_for_update(skip_locked=True)
        )

        result = await self.session.execute(query)
        nudge = result.scalar_one_or_none()

        if not nudge:
            # Nudge is already being processed or doesn't exist
            return False

        # Update status to processing
        nudge.status = NudgeStatus.PROCESSING.value
        nudge.updated_at = datetime.utcnow()

        await self.session.commit()
        return True

    async def update_status(
        self,
        nudge_id: UUID,
        status: NudgeStatus,
        sent_at: datetime | None = None,
        error_message: str | None = None
    ) -> None:
        """Update nudge status and related fields."""
        update_data = {
            "status": status.value,
            "updated_at": datetime.utcnow()
        }

        if sent_at:
            update_data["sent_at"] = sent_at
        if error_message:
            update_data["error_message"] = error_message

        query = (
            update(NudgeORM)
            .where(NudgeORM.id == nudge_id)
            .values(**update_data)
        )

        await self.session.execute(query)
        await self.session.commit()

    async def delete_by_ids(self, nudge_ids: list[UUID]) -> None:
        """Delete nudges by their IDs."""
        if not nudge_ids:
            return

        query = select(NudgeORM).where(NudgeORM.id.in_(nudge_ids))
        result = await self.session.execute(query)
        nudges = result.scalars().all()

        for nudge in nudges:
            await self.session.delete(nudge)

        await self.session.commit()

    async def get_user_nudges(self, user_id: UUID, limit: int = 100) -> list[NudgeRecord]:
        """Get all nudges for a specific user."""
        query = (
            select(NudgeORM)
            .where(NudgeORM.user_id == user_id)
            .order_by(NudgeORM.created_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        nudges = result.scalars().all()
        return [self._to_nudge_record(nudge) for nudge in nudges]

    def _to_nudge_record(self, orm_nudge: NudgeORM) -> NudgeRecord:
        """Convert NudgeORM to NudgeRecord."""
        return NudgeRecord(
            id=orm_nudge.id,
            user_id=orm_nudge.user_id,
            nudge_type=orm_nudge.nudge_type,
            priority=orm_nudge.priority,
            status=NudgeStatus(orm_nudge.status),
            channel=NudgeChannel(orm_nudge.channel),
            notification_text=orm_nudge.notification_text,
            preview_text=orm_nudge.preview_text or "",
            created_at=orm_nudge.created_at,
            updated_at=orm_nudge.updated_at,
            scheduled_for=None,  # Add this field to ORM if needed
            sent_at=None,  # Add this field to ORM if needed
            error_message=None,  # Add this field to ORM if needed
            metadata=orm_nudge.nudge_metadata or {}
        )
