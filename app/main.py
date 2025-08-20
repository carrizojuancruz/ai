import os

from dotenv import load_dotenv

load_dotenv(".env", override=False)
load_dotenv(".env.local", override=True)

from .core.aws_config import load_aws_secrets

if os.getenv("FOS_SECRETS_ID"):
    load_aws_secrets()

from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response

from .api.routes import router as api_router
from .api.routes_supervisor import router as supervisor_router
from .api.admin.sources import router as admin_router
from .db.session import engine
from .observability.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncEngine

    async_engine: AsyncEngine = engine
    async with async_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connection established")
    try:
        yield
    finally:
        await engine.dispose()
        logger.info("Database engine disposed")


app = FastAPI(title="Verde AI - Vera Agent System", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next: Callable[[Request], Response]) -> Response:
    logger.info(f"HTTP {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"HTTP {request.method} {request.url.path} -> {response.status_code}")
    return response


@app.get("/health")
def read_root() -> dict[str, str]:
    logger.info("Health check requested")
    return {"message": "Verde AI - Vera Agent System", "status": "online"}


app.include_router(api_router)
app.include_router(supervisor_router)
app.include_router(admin_router)
