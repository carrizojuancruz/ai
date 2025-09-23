from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db.base import Base


class NudgeORM(Base):
    __tablename__ = "nudges"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    nudge_type = Column(String(50), nullable=False)
    priority = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default="pending")
    channel = Column(String(10), nullable=False, default="app")
    notification_text = Column(Text, nullable=False)
    preview_text = Column(Text, nullable=True)
    nudge_metadata = Column(JSONB, nullable=False, default=dict)
    deduplication_key = Column(String(255), nullable=False)
    is_processed = Column(Boolean, nullable=False, default=False)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
