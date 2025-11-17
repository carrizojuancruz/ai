"""Knowledge base constants."""

from pathlib import Path

PROFILE_S3_KEY = "Profile/Profile.md"
PROFILE_SOURCE_PATH = Path(__file__).parent.parent.parent / "docs" / "Profile.md"

VERA_GUIDANCE_NAME = "Vera In-App Guidance"
VERA_GUIDANCE_TYPE = "Internal Documentation"
VERA_GUIDANCE_CATEGORY = "In-App Guidance"
VERA_GUIDANCE_DESCRIPTION = "Vera help center documentation"
VERA_GUIDANCE_CONTENT_SOURCE = "internal"
