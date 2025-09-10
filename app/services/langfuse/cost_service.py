import json
from datetime import date, datetime, timedelta
from typing import List, Optional

import httpx

from langfuse import Langfuse

from .config import LangfuseConfig
from .models import CostSummary, DailyCostResponse, UserCostSummary


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

    async def get_costs_per_user_all_time(self, user_id: str) -> CostSummary:
        """Get all-time aggregated costs for a specific user."""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=30)

            all_costs = []
            current_date = start_date

            while current_date <= end_date:
                daily_costs = self._get_costs(self.supervisor_client, current_date, user_id)
                all_costs.extend(daily_costs)
                current_date += timedelta(days=1)

            total_cost = sum(cost.total_cost for cost in all_costs)
            total_tokens = sum(cost.total_tokens for cost in all_costs)
            total_traces = sum(cost.trace_count for cost in all_costs)

            return CostSummary(
                user_id=user_id,
                total_cost=total_cost,
                total_tokens=total_tokens,
                trace_count=total_traces,
                date_range={"from": start_date.isoformat(), "to": end_date.isoformat()}
            )
        except Exception:
            return CostSummary(user_id=user_id, total_cost=0.0, total_tokens=0, trace_count=0)

    async def get_users_costs_flexible(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        user_id: Optional[str] = None,
        exclude_user_metadata: bool = False
    ) -> List[UserCostSummary]:
        """Get flexible cost data with date range support."""
        try:
            start_date, end_date = self._get_date_range(from_date, to_date)
            
            all_costs = []
            current_date = start_date

            while current_date <= end_date:
                daily_costs = self._get_costs(self.supervisor_client, current_date, user_id, exclude_user_metadata)
                all_costs.extend(daily_costs)
                current_date += timedelta(days=1)

            return all_costs
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

    # === PRIVATE HELPERS ===

    def _get_date_range(self, from_date: Optional[date], to_date: Optional[date]) -> tuple[date, date]:
        """Get normalized date range."""
        if from_date and to_date:
            return from_date, to_date
        elif from_date and not to_date:
            return from_date, date.today()
        else:
            end_date = date.today()
            return end_date - timedelta(days=7), end_date

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
