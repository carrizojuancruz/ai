from datetime import datetime
from typing import Any, Dict, List
from uuid import UUID

from app.core.config import config
from app.db.database_service import get_database_service
from app.observability.logging_config import get_logger

logger = get_logger(__name__)


class RecurringTransaction:
    def __init__(
        self,
        merchant: str,
        category: str,
        typical_amount: float,
        last_payment_date: datetime,
        payment_count: int,
        usual_day_of_month: int,
    ):
        self.merchant = merchant
        self.category = category
        self.typical_amount = typical_amount
        self.last_payment_date = last_payment_date
        self.payment_count = payment_count
        self.usual_day_of_month = usual_day_of_month
        self.days_since_last_payment = (datetime.now().date() - last_payment_date.date()).days

    def to_dict(self) -> Dict[str, Any]:
        return {
            "merchant": self.merchant,
            "category": self.category,
            "typical_amount": self.typical_amount,
            "last_payment_date": self.last_payment_date.isoformat(),
            "payment_count": self.payment_count,
            "usual_day_of_month": self.usual_day_of_month,
            "days_since_last_payment": self.days_since_last_payment,
        }


class TransactionPatternService:
    def __init__(self):
        self.db_service = get_database_service()
        self.lookback_days = config.BILL_DETECTION_LOOKBACK_DAYS
        self.min_occurrences = config.BILL_MIN_OCCURRENCES

    async def get_recurring_transactions(self, user_id: UUID) -> List[RecurringTransaction]:
        try:
            async with self.db_service.get_session() as session:
                repo = self.db_service.get_finance_repository(session)
                query = """
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
                    AND STDDEV(EXTRACT(DAY FROM transaction_date)) < 5
                ORDER BY MAX(transaction_date) DESC
                """

                result = await repo.execute_query(
                    query,
                    {
                        "user_id": str(user_id),
                        "lookback_days": f"{self.lookback_days} days",
                        "min_occurrences": self.min_occurrences,
                    },
                )

                transactions = []
                for row in result:
                    transaction = RecurringTransaction(
                        merchant=row["merchant"],
                        category=row["category_detailed"] or "GENERAL",
                        typical_amount=float(row["typical_amount"]),
                        last_payment_date=row["last_payment"],
                        payment_count=row["payment_count"],
                        usual_day_of_month=int(row["usual_day"]),
                    )
                    transactions.append(transaction)

                logger.info("bill_detector.recurring_found", user_id=str(user_id), count=len(transactions))

                return transactions

        except Exception as e:
            logger.error("bill_detector.query_failed", user_id=str(user_id), error=str(e))
            return []

    def get_notification_text(self, transaction: RecurringTransaction) -> Dict[str, str]:
        amount_str = f"${transaction.typical_amount:.2f}"

        if transaction.days_since_last_payment > 25:
            notification_text = (
                f"You usually pay {transaction.merchant} ({amount_str}) "
                f"around day {transaction.usual_day_of_month} of the month. "
                f"Last payment was {transaction.days_since_last_payment} days ago."
            )
            preview_text = f"{transaction.merchant} recurring payment"
        else:
            notification_text = (
                f"You recently paid {transaction.merchant} ({amount_str}). "
                f"This is a recurring payment you've made {transaction.payment_count} times."
            )
            preview_text = f"{transaction.merchant} recently paid"

        return {"notification_text": notification_text, "preview_text": preview_text}


_transaction_pattern_service = None


def get_transaction_pattern_service() -> TransactionPatternService:
    global _transaction_pattern_service
    if _transaction_pattern_service is None:
        _transaction_pattern_service = TransactionPatternService()
    return _transaction_pattern_service
