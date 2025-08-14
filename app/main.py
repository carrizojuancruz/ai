from dotenv import load_dotenv
from fastapi import FastAPI, Request

load_dotenv(".env", override=False)
load_dotenv(".env.local", override=True)

from .observability.logging_config import configure_logging, get_logger

configure_logging()
app = FastAPI(title="Verde AI - Vera Agent System", version="0.1.0")
logger = get_logger(__name__)

from .api.routes import router as api_router


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"HTTP {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"HTTP {request.method} {request.url.path} -> {response.status_code}")
    return response


@app.get("/")
def read_root() -> dict[str, str]:
    logger.info("Health check requested")
    return {"message": "Verde AI - Vera Agent System", "status": "online"}


app.include_router(api_router)
