
import logging

from app.services.external_context.http_client import FOSHttpClient

logger = logging.getLogger(__name__)

class PaymentRemindersService:

    def __init__(self):
        self.http_client = FOSHttpClient()

    def _format_payment_reminders(self, reminders: list[dict]) -> list[dict]:
        formatted: list[dict] = []
        for reminder in reminders:
            title = reminder.get("title") or "Reminder"
            status = reminder.get("status") or "unknown"
            parts: list[str] = []

            frequency = reminder.get("frequency")
            if frequency == "monthly":
                day_of_month = reminder.get("day_of_month")
                if day_of_month:
                    parts.append(f"monthly on day {day_of_month}")
                else:
                    parts.append("monthly")
            elif frequency == "weekly":
                day_of_week = reminder.get("day_of_week")
                if day_of_week is not None:
                    days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
                    day_name = days[day_of_week] if 0 <= day_of_week < 7 else f"day {day_of_week}"
                    parts.append(f"weekly on {day_name}")
                else:
                    parts.append("weekly")
            elif frequency == "yearly":
                month_of_year = reminder.get("month_of_year")
                day_of_month = reminder.get("day_of_month")
                if month_of_year and day_of_month:
                    parts.append(f"yearly on {month_of_year}/{day_of_month}")
                elif month_of_year:
                    parts.append(f"yearly in month {month_of_year}")
                else:
                    parts.append("yearly")
            elif frequency:
                parts.append(f"{frequency}")

            next_run_at = reminder.get("next_run_at")
            if next_run_at:
                parts.append(f"next scheduled for {next_run_at}")

            last_triggered_at = reminder.get("last_triggered_at")
            if last_triggered_at:
                parts.append(f"last sent {last_triggered_at}")

            amount = reminder.get("amount")
            currency_code = reminder.get("currency_code")
            if amount is not None and currency_code:
                parts.append(f"amount {amount} {currency_code}")
            elif amount is not None:
                parts.append(f"amount {amount}")

            description = reminder.get("description")
            if description:
                parts.append(description)

            summary = f"{title} ({status})"
            if parts:
                summary = f"{summary}: " + ", ".join(parts)

            formatted.append(
                {
                    "title": title,
                    "status": status,
                    "summary": summary,
                }
            )

        return formatted

    async def get_payment_reminders(self, user_id: str) -> dict | list[dict]:
        """Fetch payment reminders for a user."""
        try:
            response = await self.http_client.get(f"/internal/payment_reminders/{user_id}")
            reminders = response.get("reminders", [])
            return {"payment_reminders": self._format_payment_reminders(reminders)}
        except Exception as e:
            logger.error("Error fetching payment reminders for user %s: %s: %s", user_id, type(e).__name__, e)
            return []

