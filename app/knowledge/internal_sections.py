"""Static configuration and enum for internal source subcategories."""
from enum import Enum


class InternalSubcategory(str, Enum):
    REPORTS = "reports"
    CONNECT_ACCOUNT = "connect-account"
    PROFILE = "profile"


INTERNAL_URL_SECTIONS = {
    InternalSubcategory.REPORTS.value: [
        "12634022-see-how-you-re-doing-reports-made-simple",
        "12634538-cash-flow-report",
        "12634527-net-worth-report"
    ],
    InternalSubcategory.CONNECT_ACCOUNT.value: [
        "12461218-how-can-i-connect-my-accounts"
    ],
    InternalSubcategory.PROFILE.value: [
        "12770905-profile"
    ]
}
INTERNAL_S3_SECTIONS = {}
