from typing import Any, Dict, Optional
from uuid import UUID

from app.observability.logging_config import get_logger
from app.services.nudges.models import NudgeCandidate
from app.services.nudges.plaid_bills import get_plaid_bills_service
from app.services.nudges.strategies.base import NudgeStrategy

logger = get_logger(__name__)


class BillNudgeStrategy(NudgeStrategy):
    def __init__(self):
        self.bills_service = get_plaid_bills_service()

    @property
    def nudge_type(self) -> str:
        return "static_bill"

    @property
    def requires_fos_text(self) -> bool:
        return False

    async def evaluate(self, user_id: UUID, context: Dict[str, Any]) -> Optional[NudgeCandidate]:
        logger.debug(f"bill_strategy.evaluation_started: user_id={str(user_id)}")

        try:
            logger.debug(f"bill_strategy.fetching_bills: user_id={str(user_id)}")
            bills = await self.bills_service.get_upcoming_bills(user_id)

            if not bills:
                logger.info(f"bill_strategy.no_bills_found: user_id={str(user_id)}")
                return None

            logger.info(
                f"bill_strategy.bills_found: user_id={str(user_id)}, bill_count={len(bills)}, next_due_date={bills[0].next_payment_due_date.isoformat() if bills else None}"
            )

            most_urgent = bills[0]

            logger.debug(
                f"bill_strategy.most_urgent_bill: user_id={str(user_id)}, account={most_urgent.account_name}, institution={most_urgent.institution_name}, due_date={most_urgent.next_payment_due_date.isoformat()}, amount={most_urgent.minimum_payment_amount}, days_until_due={most_urgent.days_until_due}"
            )

            priority = self.get_priority({"bill": most_urgent})
            logger.debug(f"bill_strategy.priority_calculated: user_id={str(user_id)}, priority={priority}")

            texts = await self.bills_service.generate_notification(most_urgent)

            logger.debug(
                f"bill_strategy.notification_generated: user_id={str(user_id)}, preview_text={texts['preview_text']}, notification_length={len(texts['notification_text'])}"
            )

            candidate = NudgeCandidate(
                user_id=user_id,
                nudge_type=self.nudge_type,
                priority=priority,
                notification_text=texts["notification_text"],
                preview_text=texts["preview_text"],
                metadata={
                    "bill": most_urgent.to_dict(),
                    "total_bills_detected": len(bills),
                    "data_source": "plaid_liabilities",
                    "is_predicted": False,
                },
            )

            logger.info(
                f"bill_strategy.candidate_created: user_id={str(user_id)}, priority={priority}, bill_account={most_urgent.account_name}, days_until_due={most_urgent.days_until_due}"
            )

            return candidate

        except Exception as e:
            logger.error(
                f"bill_strategy.evaluation_failed: user_id={str(user_id)}, error={str(e)}, error_type={type(e).__name__}"
            )
            return None

    def get_priority(self, context: Dict[str, Any]) -> int:
        bill = context.get("bill")
        if not bill:
            return 2

        return self.bills_service.calculate_priority(bill)

    async def validate_conditions(self, user_id: UUID) -> bool:
        return True
