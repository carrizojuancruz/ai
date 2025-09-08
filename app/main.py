from dotenv import load_dotenv

load_dotenv(".env", override=False)
load_dotenv(".env.local", override=True)

from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .api.admin.memories import router as memories_router
from .api.routes import router as api_router
from .api.routes_crawl import router as crawl_router
from .api.routes_cron import router as cron_router
from .api.routes_guest import router as guest_router
from .api.routes_knowledge import router as knowledge_router
from .api.routes_supervisor import router as supervisor_router
from .core.config import config
from .observability.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup - initializing services")

    # Initialize database connection on startup
    try:
        from app.db.session import _get_engine
        _get_engine()  # This will create the engine and start health checks
        logger.info("Database connection initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database connection: {e}")
        # Continue startup even if DB fails (for resilience)

    # Warm up AWS clients to avoid first-request latency
    try:
        from app.core.app_state import warmup_aws_clients
        await warmup_aws_clients()
        logger.info("AWS clients warmed up successfully")
    except Exception as e:
        logger.error(f"Failed to warm up AWS clients: {e}")

    try:
        from app.core.app_state import start_finance_agent_cleanup_task
        await start_finance_agent_cleanup_task()
        logger.info("Finance agent cleanup task started successfully")
    except Exception as e:
        logger.error(f"Failed to start finance agent cleanup task: {e}")

    try:
        yield
    finally:
        logger.info("Application shutdown - cleaning up resources")

        try:
            from app.db.session import dispose_engine
            await dispose_engine()
            logger.info("Database connections disposed successfully")
        except Exception as e:
            logger.error(f"Error disposing database connections: {e}")

        try:
            from app.core.app_state import dispose_aws_clients
            dispose_aws_clients()
            logger.info("AWS clients disposed successfully")
        except Exception as e:
            logger.error(f"Error disposing AWS clients: {e}")

        try:
            from app.core.app_state import dispose_finance_agent_cleanup_task
            dispose_finance_agent_cleanup_task()
            logger.info("Finance agent cleanup task disposed successfully")
        except Exception as e:
            logger.error(f"Error disposing finance agent cleanup task: {e}")

        logger.info("Application shutdown complete")


app = FastAPI(title="Verde AI - Vera Agent System", version="0.1.0", lifespan=lifespan)

# CORS configuration
allowed_origins = [
    # Frontend domains
    "https://fos-dev.tellvera.com",
    "https://fos-uat.tellvera.com",
    "https://fos.tellvera.com",
    # API domains (for Swagger UI, etc.)
    "https://api-dev.tellvera.com",
    "https://api-uat.tellvera.com",
    "https://api.tellvera.com",
    # Local development
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://localhost:8000",
    "http://localhost:8081",
    "http://localhost:8501",  # Streamlit dev UI
    # Expo development (React Native web testing)
    "http://localhost:19006",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


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


@app.get("/health/database")
async def database_health_check() -> dict:
    """Comprehensive database health check."""
    try:
        from app.db.session import _get_engine, _health_check_connection, get_connection_stats

        engine = _get_engine()
        is_healthy = await _health_check_connection(engine)
        stats = get_connection_stats()

        response = {
            "status": "healthy" if is_healthy else "unhealthy",
            "database": {
                "connection_healthy": is_healthy,
                "pool_stats": stats,
            }
        }

        logger.info(f"Database health check: {response['status']}")
        return response

    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "error",
            "database": {
                "connection_healthy": False,
                "error": str(e)
            }
        }

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
app.include_router(crawl_router)
