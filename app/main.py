from collections.abc import Callable

from fastapi import FastAPI, Request, Response

from .api.routes import router as api_router
from .api.routes_supervisor import router as supervisor_router
from .api.admin.sources import router as admin_router
from .observability.logging_config import configure_logging, get_logger

configure_logging()
app = FastAPI(title="Verde AI - Vera Agent System", version="0.1.0")
logger = get_logger(__name__)


@app.middleware("http")
async def log_requests(request: Request, call_next: Callable[[Request], Response]) -> Response:
    logger.info(f"HTTP {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"HTTP {request.method} {request.url.path} -> {response.status_code}")
    return response


@app.get("/")
def read_root() -> dict[str, str]:
    logger.info("Health check requested")
    return {"message": "Verde AI - Vera Agent System", "status": "online"}


app.include_router(api_router)
app.include_router(supervisor_router)
app.include_router(admin_router)
