import asyncio
import logging
from typing import Optional

from app.core.config import config as app_config

logger = logging.getLogger(__name__)

_redis_client_singleton = None
_redis_client_lock = asyncio.Lock()


def _str_to_bool(value: Optional[str]) -> bool:
    if not value:
        return False
    return str(value).lower() in {"1", "true", "yes", "on"}


def is_dev_env() -> bool:
    env = (app_config.REDIS_ENVIRONMENT or "").lower()
    return env in {"develop", "dev", "local", "test"}


def _build_async_redis_client():
    import redis.asyncio as aioredis
    from redis.backoff import ExponentialBackoff
    from redis.retry import Retry

    host = app_config.REDIS_HOST
    port_raw = app_config.REDIS_PORT
    password = app_config.REDIS_PASSWORD
    username = getattr(app_config, "REDIS_USERNAME", None)
    use_tls = _str_to_bool(app_config.REDIS_TLS)
    try:
        port = int(port_raw)
    except Exception:
        port = 6379

    if not host:
        raise RuntimeError("REDIS_HOST not configured")

    return aioredis.Redis(
        host=host,
        port=port,
        password=password,
        username=username,
        ssl=use_tls or False,
        decode_responses=False,
        retry=Retry(ExponentialBackoff(), 3),
        retry_on_timeout=True,
        socket_connect_timeout=3,
        socket_timeout=5,
        health_check_interval=30,
        socket_keepalive=True,
        max_connections=64,
    )


async def get_redis_client_singleton():
    global _redis_client_singleton
    if is_dev_env():
        raise RuntimeError("Redis client disabled in dev environment")
    if _redis_client_singleton is None:
        async with _redis_client_lock:
            if _redis_client_singleton is None:
                _redis_client_singleton = _build_async_redis_client()
                logger.debug("Redis singleton client created")
    return _redis_client_singleton


async def redis_healthcheck() -> bool:
    if is_dev_env():
        logger.info("Redis healthcheck skipped in dev environment")
        return False
    try:
        client = await get_redis_client_singleton()
    except Exception as exc:
        logger.warning("Redis healthcheck skipped err=%s", exc)
        return False
    try:
        await client.ping()
        return True
    except Exception as exc:
        logger.error("Redis healthcheck failed err=%s", exc)
        return False
