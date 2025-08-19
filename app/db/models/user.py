from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db.base import Base


class UserContextORM(Base):
    __tablename__ = "user_contexts"

    user_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String, nullable=True, index=True)
    preferred_name = Column(String, nullable=True)
    pronouns = Column(String, nullable=True)
    language = Column(String, nullable=False, default="en-US")
    tone_preference = Column(String, nullable=True)
    city = Column(String, nullable=True)
    dependents = Column(Integer, nullable=True)
    income_band = Column(String, nullable=True)
    rent_mortgage = Column(Float, nullable=True)
    primary_financial_goal = Column(String, nullable=True)
    subscription_tier = Column(String, nullable=False, default="free")
    social_signals_consent = Column(Boolean, nullable=False, default=False)
    ready_for_orchestrator = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    age = Column(Integer, nullable=True)
    age_range = Column(String, nullable=True)
    money_feelings = Column(JSONB, nullable=False, default=list)
    housing_satisfaction = Column(String, nullable=True)
    health_insurance = Column(String, nullable=True)
    health_cost = Column(String, nullable=True)
    learning_interests = Column(JSONB, nullable=False, default=list)
    expenses = Column(JSONB, nullable=False, default=list)
    identity = Column(JSONB, nullable=False, default=dict)
    safety = Column(JSONB, nullable=False, default=dict)
    style = Column(JSONB, nullable=False, default=dict)
    location = Column(JSONB, nullable=False, default=dict)
    locale_info = Column(JSONB, nullable=False, default=dict)
    goals = Column(JSONB, nullable=False, default=list)
    income = Column(String, nullable=True)
    housing = Column(String, nullable=True)
    tier = Column(String, nullable=True)
    accessibility = Column(JSONB, nullable=False, default=dict)
    budget_posture = Column(JSONB, nullable=False, default=dict)
    household = Column(JSONB, nullable=False, default=dict)
    assets_high_level = Column(JSONB, nullable=False, default=list)


