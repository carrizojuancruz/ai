import logging
import threading
from datetime import date, datetime
from typing import List, Optional

from langfuse import Langfuse

from . import aggregators, date_utils, trace_processor
from .config import LangfuseConfig
from .http_client import LangfuseHttpClient
from .models import (
    AdminCostSummary,
    DailyCostFields,
    GuestCostSummary,
    UserCostSummary,
    UserDailyCost,
    UserDailyCosts,
)

logger = logging.getLogger(__name__)

_instance: Optional['LangfuseCostService'] = None
_lock = threading.Lock()


class LangfuseCostService:
    """Main service for retrieving and processing Langfuse cost data."""

    def __init__(self):
        self._initialize_clients()

    @classmethod
    def get_instance(cls) -> 'LangfuseCostService':
        """Get thread-safe singleton instance of the service."""
        global _instance, _lock

        if _instance is None:
            with _lock:
                if _instance is None:
                    _instance = cls()
        return _instance

    def _initialize_clients(self):
        """Initialize Langfuse clients for guest and supervisor."""
        self.guest_config = LangfuseConfig.from_env_guest()
        self.supervisor_config = LangfuseConfig.from_env_supervisor()

        self.guest_client = Langfuse(
            public_key=self.guest_config.public_key,
            secret_key=self.guest_config.secret_key,
            host=self.guest_config.host
        )
        self.supervisor_client = Langfuse(
            public_key=self.supervisor_config.public_key,
            secret_key=self.supervisor_config.secret_key,
            host=self.supervisor_config.host
        )

        self.guest_http_client = LangfuseHttpClient(
            self.guest_config.public_key,
            self.guest_config.secret_key,
            self.guest_config.host
        )
        self.supervisor_http_client = LangfuseHttpClient(
            self.supervisor_config.public_key,
            self.supervisor_config.secret_key,
            self.supervisor_config.host
        )

    async def get_costs_per_user_date(
        self,
        target_date: date,
        user_id: Optional[str] = None
    ) -> List[UserCostSummary]:
        """Get costs for users on a specific date."""
        return await self._get_costs_for_date(target_date, user_id)

    async def get_users_costs(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        user_id: Optional[str] = None,
        exclude_user_metadata: bool = False
    ) -> List[AdminCostSummary]:
        """Get aggregated cost data with essential fields: user_id, total_cost, trace_count.

        Date Range Logic:
        - No params: Last 30 days (default behavior)
        - from_date only: From that date to today
        - to_date only: Single day (that date only)
        - Both dates: From from_date to to_date
        """
        try:
            start_date, end_date = date_utils.get_date_range(from_date, to_date)
            all_costs = await self._collect_costs_for_date_range(
                start_date, end_date, user_id, exclude_user_metadata
            )

            user_aggregates = aggregators.aggregate_by_user(all_costs)
            return aggregators.create_admin_summaries(user_aggregates)

        except Exception as e:
            logger.error(f"Failed to get user costs: {e}")
            return []

    async def get_user_daily_cost_fields(
        self,
        user_id: str,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> List[DailyCostFields]:
        """Get daily cost breakdown for a user with core fields only."""
        try:
            start_date, end_date = date_utils.get_date_range(from_date, to_date)
            daily_costs = []

            for current_date in date_utils.iterate_date_range(start_date, end_date):
                costs = await self._get_costs_for_date(current_date, user_id)
                daily_cost_fields = aggregators.create_daily_cost_fields(costs, current_date)
                daily_costs.append(daily_cost_fields)

            return daily_costs

        except Exception as e:
            logger.error(f"Failed to get user daily cost fields: {e}")
            return []

    async def get_all_users_daily_costs_grouped(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        user_id: Optional[str] = None
    ) -> List[UserDailyCosts]:
        """Get daily costs for all users or a specific user, grouped by user."""
        try:
            all_user_daily_costs = await self.get_all_users_daily_costs(
                from_date=from_date,
                to_date=to_date,
                user_id=user_id
            )

            return aggregators.group_daily_costs_by_user(all_user_daily_costs)

        except Exception as e:
            logger.error(f"Failed to get grouped daily costs: {e}")
            return []

    async def get_all_users_daily_costs(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        user_id: Optional[str] = None
    ) -> List[UserDailyCost]:
        """Get daily cost breakdown for all users with user_id, date, total_cost, and trace_count."""
        try:
            start_date, end_date = date_utils.get_date_range(from_date, to_date)
            all_daily_costs = []

            for current_date in date_utils.iterate_date_range(start_date, end_date):
                daily_costs = await self._create_user_daily_costs_for_date(current_date, user_id)
                all_daily_costs.extend(daily_costs)

            return all_daily_costs

        except Exception as e:
            logger.error(f"Failed to get all users daily costs: {e}")
            return []

    async def get_guest_costs(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> GuestCostSummary:
        """Get guest user costs with core fields only: total_cost and trace_count."""
        try:
            start_date, end_date = date_utils.get_date_range(from_date, to_date)
            all_costs = await self._collect_guest_costs_for_date_range(start_date, end_date)

            total_cost = sum(cost.total_cost for cost in all_costs)
            total_traces = sum(cost.trace_count for cost in all_costs)

            return GuestCostSummary(total_cost=total_cost, trace_count=total_traces)

        except Exception as e:
            logger.error(f"Failed to get guest costs: {e}")
            return GuestCostSummary(total_cost=0.0, trace_count=0)


    async def _collect_costs_for_date_range(
        self,
        start_date: date,
        end_date: date,
        user_id: Optional[str] = None,
        exclude_user_metadata: bool = False
    ) -> List[UserCostSummary]:
        """Collect costs for a date range using supervisor client."""
        all_costs = []
        for current_date in date_utils.iterate_date_range(start_date, end_date):
            daily_costs = await self._get_costs_for_date(current_date, user_id, exclude_user_metadata)
            all_costs.extend(daily_costs)
        return all_costs

    async def _collect_guest_costs_for_date_range(self, start_date: date, end_date: date) -> List[UserCostSummary]:
        """Collect guest costs for a date range using guest client."""
        all_costs = []
        for current_date in date_utils.iterate_date_range(start_date, end_date):
            daily_costs = await self._get_guest_costs_for_date(current_date)
            all_costs.extend(daily_costs)
        return all_costs

    async def _create_user_daily_costs_for_date(
        self,
        target_date: date,
        user_id: Optional[str] = None
    ) -> List[UserDailyCost]:
        """Create UserDailyCost objects for a specific date."""
        costs = await self._get_costs_for_date(target_date, user_id)
        user_costs = {}

        for cost in costs:
            uid = cost.user_id
            if uid not in user_costs:
                user_costs[uid] = {'total_cost': 0.0, 'trace_count': 0}

            user_costs[uid]['total_cost'] += cost.total_cost
            user_costs[uid]['trace_count'] += cost.trace_count

        return [
            UserDailyCost(
                user_id=uid,
                date=target_date.isoformat(),
                total_cost=data['total_cost'],
                trace_count=data['trace_count']
            )
            for uid, data in user_costs.items()
            if uid
        ]

    async def _get_costs_for_date(
        self,
        target_date: date,
        user_id: Optional[str] = None,
        exclude_user_metadata: bool = False
    ) -> List[UserCostSummary]:
        """Get costs for a specific date using supervisor client."""
        return await self._get_costs_from_client(
            self.supervisor_http_client, target_date, user_id, exclude_user_metadata
        )

    async def _get_guest_costs_for_date(self, target_date: date) -> List[UserCostSummary]:
        """Get guest costs for a specific date using guest client."""
        return await self._get_costs_from_client(
            self.guest_http_client, target_date, exclude_user_metadata=True
        )

    async def _get_costs_from_client(
        self,
        http_client: LangfuseHttpClient,
        target_date: date,
        user_id: Optional[str] = None,
        exclude_user_metadata: bool = False
    ) -> List[UserCostSummary]:
        """Get costs from a specific Langfuse client."""
        try:
            start_time = datetime.combine(target_date, datetime.min.time())
            end_time = datetime.combine(target_date, datetime.max.time())

            traces_data = await http_client.get_traces(start_time, end_time)
            return trace_processor.process_traces(
                traces_data, target_date, user_id, exclude_user_metadata
            )

        except Exception as e:
            logger.error(f"Failed to get costs from client: {e}")
            return []
