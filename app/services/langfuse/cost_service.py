import json
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

import httpx

from langfuse import Langfuse

from .config import LangfuseConfig
from .models import (
    AdminCostSummary,
    CostSummary,
    DailyCostFields,
    DailyCostResponse,
    UserCostSummary,
    UserDailyCost,
    UserDailyCosts,
)


class LangfuseCostService:
    def __init__(self):
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

    # === CORE METHODS ===

    async def get_costs_per_user_date(
        self,
        target_date: date,
        user_id: Optional[str] = None
    ) -> List[UserCostSummary]:
        """Get costs for users on a specific date."""
        return self._get_costs(self.supervisor_client, target_date, user_id)

    async def get_users_costs_flexible(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        user_id: Optional[str] = None,
        exclude_user_metadata: bool = False
    ) -> List[CostSummary]:
        """Get flexible cost data with date range support."""
        try:
            start_date, end_date = self._get_date_range(from_date, to_date)

            all_costs = []
            current_date = start_date

            while current_date <= end_date:
                daily_costs = self._get_costs(self.supervisor_client, current_date, user_id, exclude_user_metadata)
                all_costs.extend(daily_costs)
                current_date += timedelta(days=1)

            # Aggregate costs by user_id
            user_aggregates = {}
            for cost in all_costs:
                uid = cost.user_id
                if uid not in user_aggregates:
                    user_aggregates[uid] = {'total_cost': 0.0, 'total_tokens': 0, 'trace_count': 0}

                user_aggregates[uid]['total_cost'] += cost.total_cost
                user_aggregates[uid]['total_tokens'] += cost.total_tokens
                user_aggregates[uid]['trace_count'] += cost.trace_count

            # Convert to CostSummary objects
            return [
                CostSummary(
                    user_id=uid,
                    total_cost=data['total_cost'],
                    total_tokens=data['total_tokens'],
                    trace_count=data['trace_count'],
                    date_range={"from": start_date.isoformat(), "to": end_date.isoformat()}
                )
                for uid, data in user_aggregates.items()
            ]
        except Exception:
            return []

    async def get_users_costs(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        user_id: Optional[str] = None,
        exclude_user_metadata: bool = False
    ) -> List[AdminCostSummary]:
        """Get cost data with only essential fields: user_id, total_cost, trace_count."""
        try:
            start_date, end_date = self._get_date_range(from_date, to_date)

            all_costs = []
            current_date = start_date

            while current_date <= end_date:
                daily_costs = self._get_costs(self.supervisor_client, current_date, user_id, exclude_user_metadata)
                all_costs.extend(daily_costs)
                current_date += timedelta(days=1)

            # Aggregate costs by user_id
            user_aggregates = {}
            for cost in all_costs:
                uid = cost.user_id
                if uid not in user_aggregates:
                    user_aggregates[uid] = {'total_cost': 0.0, 'trace_count': 0}

                user_aggregates[uid]['total_cost'] += cost.total_cost
                user_aggregates[uid]['trace_count'] += cost.trace_count

            # Convert to AdminCostSummary objects
            return [
                AdminCostSummary(
                    user_id=uid,
                    total_cost=data['total_cost'],
                    trace_count=data['trace_count']
                )
                for uid, data in user_aggregates.items()
            ]
        except Exception:
            return []

    async def get_user_daily_costs(
        self,
        user_id: str,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> List[DailyCostResponse]:
        """Get daily cost breakdown for a user."""
        try:
            start_date, end_date = self._get_date_range(from_date, to_date)

            daily_costs = []
            current_date = start_date

            while current_date <= end_date:
                costs = self._get_costs(self.supervisor_client, current_date, user_id)
                total_cost = sum(cost.total_cost for cost in costs)
                total_tokens = sum(cost.total_tokens for cost in costs)
                total_traces = sum(cost.trace_count for cost in costs)

                daily_costs.append(DailyCostResponse(
                    user_id=user_id,
                    date=current_date.isoformat(),
                    total_cost=total_cost,
                    total_tokens=total_tokens,
                    trace_count=total_traces
                ))
                current_date += timedelta(days=1)

            return daily_costs
        except Exception:
            return []

    async def get_user_daily_cost_fields(
        self,
        user_id: str,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> List[DailyCostFields]:
        """Get daily cost breakdown for a user with core fields only."""
        try:
            start_date, end_date = self._get_date_range(from_date, to_date)

            daily_costs = []
            current_date = start_date

            while current_date <= end_date:
                costs = self._get_costs(self.supervisor_client, current_date, user_id)
                total_cost = sum(cost.total_cost for cost in costs)
                total_traces = sum(cost.trace_count for cost in costs)

                daily_costs.append(DailyCostFields(
                    date=current_date.isoformat(),
                    total_cost=total_cost,
                    trace_count=total_traces
                ))
                current_date += timedelta(days=1)

            return daily_costs
        except Exception:
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

            user_costs_dict = {}
            for user_cost in all_user_daily_costs:
                if user_cost.user_id not in user_costs_dict:
                    user_costs_dict[user_cost.user_id] = []

                daily_cost_field = DailyCostFields(
                    total_cost=user_cost.total_cost,
                    trace_count=user_cost.trace_count,
                    date=user_cost.date
                )
                user_costs_dict[user_cost.user_id].append(daily_cost_field)

            result = []
            for user_id, daily_costs in user_costs_dict.items():
                result.append(UserDailyCosts(
                    user_id=user_id,
                    daily_costs=daily_costs
                ))

            return result
        except Exception:
            return []

    async def get_all_users_daily_costs(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        user_id: Optional[str] = None
    ) -> List[UserDailyCost]:
        """Get daily cost breakdown for all users with user_id, date, total_cost, and trace_count.

        This method returns costs per date for every user, grouped by user.
        Each record contains user_id, date, total_cost, and trace_count.
        """
        try:
            start_date, end_date = self._get_date_range(from_date, to_date)

            all_daily_costs = []
            current_date = start_date

            while current_date <= end_date:
                costs = self._get_costs(self.supervisor_client, current_date, user_id)

                user_costs = {}
                for cost in costs:
                    uid = cost.user_id
                    if uid not in user_costs:
                        user_costs[uid] = {'total_cost': 0.0, 'trace_count': 0}

                    user_costs[uid]['total_cost'] += cost.total_cost
                    user_costs[uid]['trace_count'] += cost.trace_count

                # Create UserDailyCost objects for each user on this date
                for uid, data in user_costs.items():
                    if uid:  # Only include users with valid user_id
                        all_daily_costs.append(UserDailyCost(
                            user_id=uid,
                            date=current_date.isoformat(),
                            total_cost=data['total_cost'],
                            trace_count=data['trace_count']
                        ))

                current_date += timedelta(days=1)

            return all_daily_costs
        except Exception:
            return []

    async def get_guest_costs(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> CostSummary:
        """Get guest user costs (users without user_id) with date range support."""
        try:
            start_date, end_date = self._get_date_range(from_date, to_date)

            all_costs = []
            current_date = start_date

            while current_date <= end_date:
                daily_costs = self._get_costs(self.guest_client, current_date, exclude_user_metadata=True)
                all_costs.extend(daily_costs)
                current_date += timedelta(days=1)

            total_cost = sum(cost.total_cost for cost in all_costs)
            total_tokens = sum(cost.total_tokens for cost in all_costs)
            total_traces = sum(cost.trace_count for cost in all_costs)

            return CostSummary(
                user_id=None,  # Guest users have no user_id
                total_cost=total_cost,
                total_tokens=total_tokens,
                trace_count=total_traces,
                date_range={"from": start_date.isoformat(), "to": end_date.isoformat()}
            )
        except Exception:
            return CostSummary(user_id=None, total_cost=0.0, total_tokens=0, trace_count=0)

    # === PRIVATE HELPERS ===

    def _get_date_range(self, from_date: Optional[date], to_date: Optional[date]) -> Tuple[date, date]:
        """Get normalized date range."""
        if from_date and to_date:
            return from_date, to_date
        elif from_date and not to_date:
            return from_date, date.today()
        else:
            end_date = date.today()
            return end_date - timedelta(days=30), end_date

    def _get_costs(self, client: Langfuse, target_date: date, user_id: Optional[str] = None, exclude_user_metadata: bool = False) -> List[UserCostSummary]:
        """Get costs for a specific date."""
        try:
            public_key, secret_key, base_url = self._get_client_config(client)
            if not public_key or not secret_key:
                return []

            start_time = datetime.combine(target_date, datetime.min.time())
            end_time = datetime.combine(target_date, datetime.max.time())

            traces_data = self._get_traces(public_key, secret_key, base_url, start_time, end_time)
            return self._process_traces(traces_data, target_date, user_id, exclude_user_metadata)
        except Exception:
            return []

    def _get_client_config(self, client: Langfuse) -> tuple[str, str, str]:
        """Get public key, secret key, and host for client."""
        if client == self.guest_client:
            return self.guest_config.public_key, self.guest_config.secret_key, self.guest_config.host
        elif client == self.supervisor_client:
            return self.supervisor_config.public_key, self.supervisor_config.secret_key, self.supervisor_config.host
        return None, None, "https://cloud.langfuse.com"

    def _get_traces(self, public_key: str, secret_key: str, base_url: str, start_time: datetime, end_time: datetime) -> list:
        """Get traces from API."""
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{base_url}/api/public/traces",
                    auth=(public_key, secret_key),
                    params={
                        "fromTimestamp": start_time.isoformat() + "Z",
                        "toTimestamp": end_time.isoformat() + "Z",
                        "limit": 100
                    },
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get('data', [])

        except Exception:
            pass
        return []

    def _process_traces(self, traces_data: list, target_date: date, user_id: Optional[str], exclude_user_metadata: bool) -> List[UserCostSummary]:
        """Process traces into cost summaries."""
        user_costs = {}

        for trace in traces_data:
            trace_user_id = self._extract_user_id(trace)

            if user_id and trace_user_id != user_id:
                continue
            if exclude_user_metadata and trace_user_id is not None:
                continue

            cost = self._extract_cost(trace)

            if trace_user_id not in user_costs:
                user_costs[trace_user_id] = {'cost': 0.0, 'tokens': 0, 'traces': 0}

            user_costs[trace_user_id]['cost'] += cost
            user_costs[trace_user_id]['traces'] += 1

        return [
            UserCostSummary(
                user_id=uid,
                date=target_date,
                total_cost=data['cost'],
                total_tokens=data['tokens'],
                trace_count=data['traces']
            )
            for uid, data in user_costs.items()
        ]

    def _extract_user_id(self, trace) -> Optional[str]:
        """Extract user ID from trace metadata."""
        try:
            if isinstance(trace, dict) and 'metadata' in trace and trace['metadata']:
                metadata = trace['metadata']

                if isinstance(metadata, dict):
                    return metadata.get('user_id')
                elif isinstance(metadata, str):
                    parsed = json.loads(metadata)
                    return parsed.get('user_id')

            elif hasattr(trace, 'metadata') and trace.metadata:
                metadata = trace.metadata

                if isinstance(metadata, dict):
                    return metadata.get('user_id')
                elif isinstance(metadata, str):
                    parsed = json.loads(metadata)
                    return parsed.get('user_id')
        except Exception:
            pass

        return None

    def _extract_cost(self, trace) -> float:
        """Extract cost from trace."""
        try:
            cost_fields = ['totalCost', 'cost', 'total_cost']

            for field in cost_fields:
                if hasattr(trace, field):
                    value = getattr(trace, field)
                    if value is not None:
                        return float(value)

                if isinstance(trace, dict) and field in trace:
                    value = trace[field]
                    if value is not None:
                        return float(value)

            return 0.0
        except Exception:
            return 0.0
