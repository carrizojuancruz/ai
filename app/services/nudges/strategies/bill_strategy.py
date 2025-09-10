from typing import Any, Dict, Optional
from uuid import UUID

from app.observability.logging_config import get_logger
from app.services.nudges.evaluator import NudgeCandidate
from app.services.nudges.plaid_bills import get_plaid_bills_service
from app.services.nudges.strategies.base import NudgeStrategy

logger = get_logger(__name__)


class BillNudgeStrategy(NudgeStrategy):
    """Strategy for evaluating bill payment nudges using REAL Plaid data.

    This uses actual due dates from financial institutions via Plaid's Liabilities API,
    NOT predictions or guesses based on transaction patterns.
    """

    def __init__(self):
        self.bills_service = get_plaid_bills_service()

    @property
    def nudge_type(self) -> str:
        return "static_bill"

    @property
    def requires_fos_text(self) -> bool:
        return False

    async def evaluate(self, user_id: UUID, context: Dict[str, Any]) -> Optional[NudgeCandidate]:
        try:
            # Get upcoming bills from Plaid Liabilities data
            bills = await self.bills_service.get_upcoming_bills(user_id)

            if not bills:
                logger.debug("bill_strategy.no_bills", user_id=str(user_id))
                return None

            most_urgent = bills[0]

            priority = self.get_priority({"bill": most_urgent})

            # Generate notification text for bill with actual due date
            texts = await self.bills_service.generate_notification(most_urgent)

            return NudgeCandidate(
                user_id=user_id,
                nudge_type=self.nudge_type,
                priority=priority,
                notification_text=texts["notification_text"],
                preview_text=texts["preview_text"],
                metadata={
                    "bill": most_urgent.to_dict(),
                    "total_bills_detected": len(bills),
                    "data_source": "plaid_liabilities",
                    "is_predicted": False  # This is REAL data, not predictions!
                },
            )

        except Exception as e:
            logger.error("bill_strategy.evaluation_failed", user_id=str(user_id), error=str(e))
            return None

    def get_priority(self, context: Dict[str, Any]) -> int:
        bill = context.get("bill")
        if not bill:
            return 2

        return self.bills_service.calculate_priority(bill)

    async def validate_conditions(self, user_id: UUID) -> bool:
        """Validate bill-specific conditions."""
        # Could add checks like:
        # - User has active Plaid connections with liabilities data
        # - User has opted into bill reminders
        # - User has at least one credit/loan account
        return True
