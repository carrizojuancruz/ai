import json
from datetime import date, datetime
from typing import List, Optional

from langfuse import Langfuse

from .config import LangfuseConfig
from .models import UserCostSummary


class LangfuseCostService:
    def __init__(self):
        guest_config = LangfuseConfig.from_env_guest()
        supervisor_config = LangfuseConfig.from_env_supervisor()

        self.guest_client = Langfuse(
            public_key=guest_config.public_key,
            secret_key=guest_config.secret_key,
            host=guest_config.host
        )
        self.supervisor_client = Langfuse(
            public_key=supervisor_config.public_key,
            secret_key=supervisor_config.secret_key,
            host=supervisor_config.host
        )

    async def get_costs_per_user_date(
        self,
        target_date: date,
        user_id: Optional[str] = None
    ) -> List[UserCostSummary]:
        return self._get_metrics_costs(self.supervisor_client, target_date, user_id)

    async def get_guest_costs_per_date(self, target_date: date) -> UserCostSummary:
        # For guest costs, we filter for traces WITHOUT user_id metadata
        results = self._get_metrics_costs(self.guest_client, target_date, exclude_user_metadata=True)
        
        if not results:
            return UserCostSummary(user_id=None, date=target_date)
        
        # Aggregate all guest results
        total_cost = sum(r.total_cost for r in results)
        total_tokens = sum(r.total_tokens for r in results)
        trace_count = sum(r.trace_count for r in results)
        
        return UserCostSummary(
            user_id=None,
            date=target_date,
            total_cost=total_cost,
            total_tokens=total_tokens,
            trace_count=trace_count
        )

    def _get_metrics_costs(
        self,
        client: Langfuse,
        target_date: date,
        user_id: Optional[str] = None,
        exclude_user_metadata: bool = False
    ) -> List[UserCostSummary]:
        """Get cost metrics using Metrics API with fallback to trace fetching."""
        try:
            return self._try_metrics_api(client, target_date, user_id, exclude_user_metadata)
        except Exception:
            return self._fallback_trace_method(client, target_date, user_id, exclude_user_metadata)

    def _try_metrics_api(
        self,
        client: Langfuse,
        target_date: date,
        user_id: Optional[str] = None,
        exclude_user_metadata: bool = False
    ) -> List[UserCostSummary]:
        """Try the new Metrics API approach."""
        start_time = datetime.combine(target_date, datetime.min.time())
        end_time = datetime.combine(target_date, datetime.min.time().replace(hour=23, minute=59, second=59))

        query = {
            "view": "traces",
            "metrics": [
                {"measure": "totalCost", "aggregation": "sum"},
                {"measure": "totalTokens", "aggregation": "sum"},
                {"measure": "count", "aggregation": "count"}
            ],
            "dimensions": [{"field": "userId"}] if not exclude_user_metadata else [],
            "filters": [],
            "fromTimestamp": start_time.isoformat() + "Z",
            "toTimestamp": end_time.isoformat() + "Z"
        }

        if user_id:
            query["filters"].append({
                "column": "metadata",
                "operator": "contains",
                "key": "user_id",
                "value": user_id,
                "type": "stringObject"
            })
        elif exclude_user_metadata:
            query["filters"].append({
                "column": "metadata",
                "operator": "notContains",
                "key": "user_id",
                "type": "stringObject"
            })

        if not hasattr(client, 'httpx_client'):
            raise Exception("HTTP client not available for Metrics API")

        try:
            base_url = client._client_wrapper._base_url
        except AttributeError:
            raise Exception("Could not determine base URL for Metrics API") from None

        response = client.httpx_client.get(
            f"{base_url}/api/public/metrics",
            params={"query": json.dumps(query)}
        )

        if response.status_code != 200:
            raise Exception(f"Metrics API returned {response.status_code}: {response.text}")

        data = response.json()
        return self._transform_metrics_response(data, target_date)

    def _fallback_trace_method(
        self,
        client: Langfuse,
        target_date: date,
        user_id: Optional[str] = None,
        exclude_user_metadata: bool = False
    ) -> List[UserCostSummary]:
        """Fallback to the old trace fetching method."""
        start_time = datetime.combine(target_date, datetime.min.time())
        end_time = datetime.combine(target_date, datetime.min.time().replace(hour=23, minute=59, second=59))

        params = {
            "limit": 100,
            "from_timestamp": start_time,
            "to_timestamp": end_time
        }

        try:
            response = client.api.trace.list(**params)
            all_traces = response.data if hasattr(response, 'data') else []

            filtered_traces = []
            for trace in all_traces:
                trace_user_id = self._get_user_id_from_trace(trace)

                if user_id:
                    if trace_user_id == user_id:
                        filtered_traces.append(trace)
                elif exclude_user_metadata:
                    if not trace_user_id:
                        filtered_traces.append(trace)
                else:
                    filtered_traces.append(trace)

            return self._aggregate_trace_costs(filtered_traces, target_date)

        except Exception:
            return []

    def _get_user_id_from_trace(self, trace) -> Optional[str]:
        """Extract user_id from trace metadata."""
        if hasattr(trace, 'metadata') and trace.metadata:
            return trace.metadata.get('user_id')
        return getattr(trace, 'user_id', None)

    def _aggregate_trace_costs(self, traces, target_date: date) -> List[UserCostSummary]:
        """Aggregate costs from traces."""
        user_data = {}

        for trace in traces:
            user_id = self._get_user_id_from_trace(trace)
            cost = self._get_trace_cost(trace)

            if user_id not in user_data:
                user_data[user_id] = {
                    'total_cost': 0.0,
                    'total_tokens': 0,
                    'trace_count': 0
                }

            user_data[user_id]['total_cost'] += cost
            user_data[user_id]['trace_count'] += 1

        return [
            UserCostSummary(
                user_id=uid,
                date=target_date,
                total_cost=data['total_cost'],
                total_tokens=data['total_tokens'],
                trace_count=data['trace_count']
            )
            for uid, data in user_data.items()
        ]

    def _get_trace_cost(self, trace) -> float:
        """Extract cost from trace."""
        if hasattr(trace, 'total_cost') and trace.total_cost:
            return float(trace.total_cost)
        return 0.0

    def _transform_metrics_response(self, data: dict, target_date: date) -> List[UserCostSummary]:
        """Transform Metrics API response to UserCostSummary objects."""
        results = []
        
        if "data" not in data:
            return results
            
        for item in data["data"]:
            user_id = item.get("userId")  # This will be None for guest users
            total_cost = float(item.get("totalCost_sum", 0))
            total_tokens = int(item.get("totalTokens_sum", 0))
            trace_count = int(item.get("count_count", 0))
            
            results.append(UserCostSummary(
                user_id=user_id,
                date=target_date,
                total_cost=total_cost,
                total_tokens=total_tokens,
                trace_count=trace_count
            ))
            
        return results
