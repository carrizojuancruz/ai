from dotenv import load_dotenv

load_dotenv(".env", override=False)
load_dotenv(".env.local", override=True)

from .core.config import config

from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response

from .api.admin.memories import router as memories_router
from .api.routes import router as api_router
from .api.routes_cron import router as cron_router
from .api.routes_guest import router as guest_router
from .api.routes_knowledge import router as knowledge_router
from .api.routes_supervisor import router as supervisor_router
from .observability.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup complete")
    try:
        yield
    finally:
        logger.info("Application shutdown complete")


app = FastAPI(title="Verde AI - Vera Agent System", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next: Callable[[Request], Response]) -> Response:
    logger.info(f"HTTP {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"HTTP {request.method} {request.url.path} -> {response.status_code}")
    return response


@app.get("/health")
async def health_check() -> dict[str, str]:
    logger.info("Health check requested")
    return {"message": "Verde AI - Vera Agent System", "status": "healthy"}

@app.get("/actual_config")
async def actual_config() -> dict[str, Any]:
    actual_config_data = config.get_actual_config()
    logger.info(f"Actual config requested: {actual_config_data}")

    return actual_config_data

app.include_router(api_router)
app.include_router(supervisor_router)
app.include_router(memories_router)
app.include_router(guest_router)
app.include_router(cron_router)
app.include_router(knowledge_router)
