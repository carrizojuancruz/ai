# Entry point for the FastAPI app.
# Loads environment variables from .env.local (if present) BEFORE importing the app to
# ensure all settings are available.
# Falls back to loading .env (without overriding .env.local values). This avoids linter
# errors and ensures correct env loading.
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT: Path = Path(__file__).resolve().parent

LOCAL_ENV_PATH: Path = PROJECT_ROOT / ".env.local"
if LOCAL_ENV_PATH.exists():
    load_dotenv(LOCAL_ENV_PATH, override=True)

DEFAULT_ENV_PATH: Path = PROJECT_ROOT / ".env"
if DEFAULT_ENV_PATH.exists():
    load_dotenv(DEFAULT_ENV_PATH, override=False)

