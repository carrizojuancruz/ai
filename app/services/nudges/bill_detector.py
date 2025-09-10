from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.core.config import config
from app.db.database_service import get_database_service
from app.observability.logging_config import get_logger

logger = get_logger(__name__)


class BillInfo:
    def __init__(
        self,
        merchant: str,
        category: str,
        amount: float,
        predicted_due_date: datetime,
        last_payment_date: datetime,
        confidence: float = 0.8,
    ):
        self.merchant = merchant
        self.category = category
        self.amount = amount
        self.predicted_due_date = predicted_due_date
        self.last_payment_date = last_payment_date
        self.confidence = confidence
        self.days_until_due = (predicted_due_date.date() - datetime.now().date()).days

    def to_dict(self) -> Dict[str, Any]:
        return {
            "merchant": self.merchant,
            "category": self.category,
            "amount": self.amount,
            "predicted_due_date": self.predicted_due_date.isoformat(),
            "last_payment_date": self.last_payment_date.isoformat(),
            "days_until_due": self.days_until_due,
            "confidence": self.confidence,
        }


class BillDetector:
    def __init__(self):
        self.db_service = get_database_service()
        self.lookback_days = config.BILL_DETECTION_LOOKBACK_DAYS
        self.min_occurrences = config.BILL_MIN_OCCURRENCES
        self.prediction_window = config.BILL_PREDICTION_WINDOW_DAYS

    async def detect_upcoming_bills(self, user_id: UUID) -> List[BillInfo]:
        try:
            async with self.db_service.get_session() as session:
                repo = self.db_service.get_finance_repository(session)
                bills_query = """
                WITH monthly_recurring AS (
                    SELECT
                        COALESCE(merchant_name, name) as merchant,
                        category_detailed,
                        AVG(amount) as typical_amount,
                        EXTRACT(DAY FROM MAX(transaction_date)) as usual_day,
                        MAX(transaction_date) as last_payment,
                        COUNT(*) as payment_count,
                        STDDEV(EXTRACT(DAY FROM transaction_date)) as day_variance
                    FROM public.unified_transactions
                    WHERE user_id = :user_id
                        AND transaction_date >= CURRENT_DATE - INTERVAL :lookback_days
                        AND amount > 0
                        AND pending = false
                        AND category IN (
                            'RENT_AND_UTILITIES',
                            'LOAN_PAYMENTS',
                            'GENERAL_SERVICES',
                            'ENTERTAINMENT',
                            'INSURANCE',
                            'SUBSCRIPTION'
                        )
                    GROUP BY COALESCE(merchant_name, name), category_detailed
                    HAVING COUNT(*) >= :min_occurrences
                )
                SELECT
                    merchant,
                    category_detailed,
                    typical_amount,
                    usual_day,
                    last_payment,
                    payment_count,
                    day_variance,
                    CASE
                        WHEN usual_day <= EXTRACT(DAY FROM CURRENT_DATE)
                        THEN DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month' + (usual_day - 1) * INTERVAL '1 day'
                        ELSE DATE_TRUNC('month', CURRENT_DATE) + (usual_day - 1) * INTERVAL '1 day'
                    END as predicted_due_date
                FROM monthly_recurring
                WHERE last_payment < CURRENT_DATE - INTERVAL '20 days'
                    AND day_variance < 5
                ORDER BY predicted_due_date ASC
                """

                result = await repo.execute_query(
                    bills_query,
                    {
                        "user_id": str(user_id),
                        "lookback_days": f"{self.lookback_days} days",
                        "min_occurrences": self.min_occurrences,
                    },
                )

                bills = []
                for row in result:
                    confidence = min(0.95, 0.5 + (row["payment_count"] * 0.1) - (row["day_variance"] * 0.05))
                    predicted_date = row["predicted_due_date"]
                    if (predicted_date - datetime.now()).days <= self.prediction_window:
                        bill = BillInfo(
                            merchant=row["merchant"],
                            category=row["category_detailed"] or "GENERAL",
                            amount=float(row["typical_amount"]),
                            predicted_due_date=predicted_date,
                            last_payment_date=row["last_payment"],
                            confidence=confidence,
                        )
                        bills.append(bill)

                logger.info(
                    "bill_detector.bills_detected",
                    user_id=str(user_id),
                    count=len(bills),
                    next_due=bills[0].predicted_due_date.isoformat() if bills else None,
                )

                return bills

        except Exception as e:
            logger.error("bill_detector.detection_failed", user_id=str(user_id), error=str(e))
            return []

    def assign_bill_priority(self, bill: BillInfo) -> int:
        days_until_due = bill.days_until_due
        if days_until_due <= 1:
            return 5
        elif days_until_due <= 3:
            return 4
        elif days_until_due <= 7:
            return 3
        elif days_until_due <= 14:
            return 2
        else:
            return 1

    async def get_bill_notification_text(self, bill: BillInfo, user_name: Optional[str] = None) -> Dict[str, str]:
        amount_str = f"${bill.amount:.2f}"
        due_date_str = bill.predicted_due_date.strftime("%B %d")
        if bill.days_until_due == 0:
            preview_text = f"{bill.merchant} due today"
            notification_text = f"Your {bill.merchant} payment of {amount_str} is due today!"
        elif bill.days_until_due == 1:
            preview_text = f"{bill.merchant} due tomorrow"
            notification_text = f"Your {bill.merchant} payment of {amount_str} is due tomorrow."
        elif bill.days_until_due <= 3:
            preview_text = f"{bill.merchant} due in {bill.days_until_due} days"
            notification_text = f"Reminder: Your {bill.merchant} payment of {amount_str} is due on {due_date_str}."
        else:
            preview_text = f"{bill.merchant} due {due_date_str}"
            notification_text = (
                f"Heads up! Your {bill.merchant} payment of {amount_str} is coming up on {due_date_str}."
            )
        if user_name:
            notification_text = f"Hi {user_name}! {notification_text}"
        return {"notification_text": notification_text, "preview_text": preview_text}


_bill_detector = None


def get_bill_detector() -> BillDetector:
    global _bill_detector
    if _bill_detector is None:
        _bill_detector = BillDetector()
    return _bill_detector
