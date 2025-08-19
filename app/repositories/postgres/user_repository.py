from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserContextORM
from app.models.user import UserContext
from app.repositories.interfaces.user_repository import UserRepository


def _to_domain(row: UserContextORM) -> UserContext:
    data: dict[str, Any] = {
        "user_id": row.user_id,
        "email": row.email,
        "preferred_name": row.preferred_name,
        "pronouns": row.pronouns,
        "language": row.language,
        "tone_preference": row.tone_preference,
        "city": row.city,
        "dependents": int(row.dependents) if row.dependents is not None else None,
        "income_band": row.income_band,
        "rent_mortgage": float(row.rent_mortgage) if row.rent_mortgage is not None else None,
        "primary_financial_goal": row.primary_financial_goal,
        "subscription_tier": row.subscription_tier,
        "social_signals_consent": row.social_signals_consent,
        "ready_for_orchestrator": row.ready_for_orchestrator,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "age": int(row.age) if row.age is not None else None,
        "age_range": row.age_range,
        "money_feelings": row.money_feelings or [],
        "housing_satisfaction": row.housing_satisfaction,
        "health_insurance": row.health_insurance,
        "health_cost": row.health_cost,
        "learning_interests": row.learning_interests or [],
        "expenses": row.expenses or [],
        "identity": row.identity or {},
        "safety": row.safety or {},
        "style": row.style or {},
        "location": row.location or {},
        "locale_info": row.locale_info or {},
        "goals": row.goals or [],
        "income": row.income,
        "housing": row.housing,
        "tier": row.tier,
        "accessibility": row.accessibility or {},
        "budget_posture": row.budget_posture or {},
        "household": row.household or {},
        "assets_high_level": row.assets_high_level or [],
    }
    return UserContext(**data)


class PostgresUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: UUID) -> UserContext | None:
        result = await self.session.execute(select(UserContextORM).where(UserContextORM.user_id == user_id))
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return _to_domain(row)

    async def upsert(self, user: UserContext) -> UserContext:
        data = user.model_dump()
        stmt = pg_insert(UserContextORM).values(**data).on_conflict_do_update(
            index_elements=[UserContextORM.user_id],
            set_=data,
        )
        await self.session.execute(stmt)
        await self.session.commit()
        return user

    async def delete(self, user_id: UUID) -> None:
        row = await self.session.get(UserContextORM, user_id)
        if row is not None:
            await self.session.delete(row)
            await self.session.commit()


