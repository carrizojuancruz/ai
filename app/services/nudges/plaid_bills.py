from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.core.config import config
from app.observability.logging_config import get_logger
from app.repositories.database_service import get_database_service

logger = get_logger(__name__)


class PlaidBill:
    def __init__(
        self,
        account_name: str,
        institution_name: str,
        account_type: str,
        next_payment_due_date: datetime,
        minimum_payment_amount: float,
        last_payment_date: Optional[datetime] = None,
        last_payment_amount: Optional[float] = None,
        account_id: Optional[str] = None,
        is_overdue: bool = False,
    ):
        self.account_name = account_name
        self.institution_name = institution_name
        self.account_type = account_type
        self.next_payment_due_date = next_payment_due_date
        self.minimum_payment_amount = minimum_payment_amount
        self.last_payment_date = last_payment_date
        self.last_payment_amount = last_payment_amount
        self.account_id = account_id
        self.is_overdue = is_overdue
        self.days_until_due = (next_payment_due_date.date() - datetime.now().date()).days

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_name": self.account_name,
            "institution_name": self.institution_name,
            "account_type": self.account_type,
            "next_payment_due_date": self.next_payment_due_date.isoformat(),
            "minimum_payment_amount": self.minimum_payment_amount,
            "last_payment_date": self.last_payment_date.isoformat() if self.last_payment_date else None,
            "last_payment_amount": self.last_payment_amount,
            "days_until_due": self.days_until_due,
            "account_id": self.account_id,
            "is_overdue": self.is_overdue,
        }


class PlaidBillsService:
    SUPPORTED_ACCOUNT_TYPES = ("credit", "loan")
    DEFAULT_WINDOW_DAYS = 35
    PRIORITY_OVERDUE = 5
    PRIORITY_TODAY_TOMORROW = 5
    PRIORITY_THREE_DAYS = 4
    PRIORITY_ONE_WEEK = 3
    PRIORITY_TWO_WEEKS = 2
    PRIORITY_DEFAULT = 1

    def __init__(self):
        self.db_service = get_database_service()
        self.window_days = config.BILL_PREDICTION_WINDOW_DAYS

    async def get_upcoming_bills(self, user_id: UUID) -> List[PlaidBill]:
        try:
            async with self.db_service.get_session() as session:
                repo = self.db_service.get_finance_repository(session)

                query = """
                SELECT
                    id as account_id,
                    name as account_name,
                    institution_name,
                    account_type,
                    account_subtype,
                    next_payment_due_date,
                    minimum_payment_amount,
                    last_payment_date,
                    last_payment_amount,
                    current_balance,
                    is_overdue
                FROM public.unified_accounts
                WHERE user_id = :user_id
                    AND next_payment_due_date IS NOT NULL
                    AND next_payment_due_date > CURRENT_DATE
                    AND next_payment_due_date <= CURRENT_DATE + INTERVAL :window_days
                    AND is_active = true
                    AND account_type IN :account_types
                ORDER BY next_payment_due_date ASC
                """

                result = await repo.execute_query(
                    query,
                    {
                        "user_id": str(user_id),
                        "window_days": f"{self.window_days} days",
                        "account_types": self.SUPPORTED_ACCOUNT_TYPES,
                    },
                )

                bills = self._parse_bills(result)

                logger.info(
                    f"plaid_bills.retrieved: user_id={str(user_id)}, count={len(bills)}, next_due={bills[0].next_payment_due_date.isoformat() if bills else None}"
                )

                return bills

        except Exception as e:
            logger.error(f"plaid_bills.retrieval_failed: {str(e)}", extra={"user_id": str(user_id)})
            return []

    def _parse_bills(self, query_result: List[Dict[str, Any]]) -> List[PlaidBill]:
        bills = []
        for row in query_result:
            if not row.get("minimum_payment_amount") or float(row["minimum_payment_amount"]) <= 0:
                continue

            bill = PlaidBill(
                account_name=row["account_name"],
                institution_name=row["institution_name"],
                account_type=self._format_account_type(row["account_type"], row.get("account_subtype")),
                next_payment_due_date=row["next_payment_due_date"],
                minimum_payment_amount=float(row["minimum_payment_amount"]),
                last_payment_date=row.get("last_payment_date"),
                last_payment_amount=float(row["last_payment_amount"]) if row.get("last_payment_amount") else None,
                account_id=row.get("account_id"),
                is_overdue=row.get("is_overdue", False),
            )
            bills.append(bill)

        return bills

    @staticmethod
    def _format_account_type(account_type: str, account_subtype: Optional[str]) -> str:
        if account_subtype:
            return f"{account_type.title()} - {account_subtype.replace('_', ' ').title()}"
        return account_type.title()

    def calculate_priority(self, bill: PlaidBill) -> int:
        if bill.is_overdue or bill.days_until_due < 0:
            return self.PRIORITY_OVERDUE
        elif bill.days_until_due <= 1:
            return self.PRIORITY_TODAY_TOMORROW
        elif bill.days_until_due <= 3:
            return self.PRIORITY_THREE_DAYS
        elif bill.days_until_due <= 7:
            return self.PRIORITY_ONE_WEEK
        elif bill.days_until_due <= 14:
            return self.PRIORITY_TWO_WEEKS
        else:
            return self.PRIORITY_DEFAULT

    async def generate_notification(self, bill: PlaidBill, user_name: Optional[str] = None) -> Dict[str, str]:
        amount_str = f"${bill.minimum_payment_amount:.2f}"
        due_date_str = bill.next_payment_due_date.strftime("%B %d")

        if bill.is_overdue or bill.days_until_due < 0:
            preview_text = f"⚠️ {bill.account_name} OVERDUE"
            notification_text = (
                f"URGENT: Your {bill.account_name} payment of {amount_str} is OVERDUE. "
                f"Please pay immediately to avoid late fees."
            )
        elif bill.days_until_due == 0:
            preview_text = f"{bill.account_name} due TODAY"
            notification_text = f"Your {bill.account_name} payment of {amount_str} is due TODAY!"
        elif bill.days_until_due == 1:
            preview_text = f"{bill.account_name} due tomorrow"
            notification_text = f"Your {bill.account_name} payment of {amount_str} is due tomorrow ({due_date_str})."
        elif bill.days_until_due <= 3:
            preview_text = f"{bill.account_name} due in {bill.days_until_due} days"
            notification_text = (
                f"Reminder: Your {bill.account_name} payment of {amount_str} "
                f"is due on {due_date_str} ({bill.days_until_due} days)."
            )
        else:
            preview_text = f"{bill.account_name} due {due_date_str}"
            notification_text = (
                f"Heads up! Your {bill.account_name} payment of {amount_str} is coming up on {due_date_str}."
            )

        notification_text += f" [{bill.institution_name}]"

        if user_name:
            notification_text = f"Hi {user_name}! {notification_text}"

        return {"notification_text": notification_text, "preview_text": preview_text}


_plaid_bills_service = None


def get_plaid_bills_service() -> PlaidBillsService:
    global _plaid_bills_service
    if _plaid_bills_service is None:
        _plaid_bills_service = PlaidBillsService()
    return _plaid_bills_service
