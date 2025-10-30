import asyncio
import hashlib
import logging
import pickle
from typing import Any, Optional

from app.core.config import config as app_config

logger = logging.getLogger(__name__)


def _str_to_bool(value: Optional[str]) -> bool:
    if not value:
        return False
    return str(value).lower() in {"1", "true", "yes", "on"}


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


class KVRedisCheckpointer:
    """Shallow KV checkpointer using SET/GET+TTL with aioredis.

    Stores the latest checkpoint per thread under a namespaced key without
    relying on Redis modules (no RediSearch/JSON). Values are serialized with
    pickle for compatibility with LangGraph internals.
    """

    def __init__(self, client, namespace: str, default_ttl: Optional[int]) -> None:
        self._client = client
        self._namespace = namespace.rstrip(":")
        self._default_ttl = int(default_ttl) if default_ttl else None

    def _key(self, thread_id: str) -> str:
        return f"{self._namespace}:checkpoint:{thread_id}"

    def _writes_key(self, task_id: str) -> str:
        return f"{self._namespace}:writes:{task_id}"

    def _normalize_id(self, value: Any) -> str:
        s = str(value)
        if len(s) <= 256:
            return s
        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    def _extract_thread_id(self, config: Any) -> str:
        tid = getattr(config, "thread_id", None)
        if tid:
            return str(tid)
        try:
            if isinstance(config, dict):
                if config.get("thread_id"):
                    return str(config["thread_id"])
                configurable = config.get("configurable") or {}
                if isinstance(configurable, dict) and configurable.get("thread_id"):
                    return str(configurable["thread_id"])
        except Exception:
            pass
        raise ValueError("thread_id missing in checkpoint config")

    async def _ensure_client(self):
        if self._client is None:
            self._client = _build_async_redis_client()
        return self._client

    async def aget_tuple(self, config: Any):
        from langgraph.checkpoint.base import CheckpointTuple  # type: ignore

        thread_id = self._extract_thread_id(config)
        key = self._key(thread_id)
        logger.info("kv_checkpointer.get: thread_id=%s", thread_id)
        client = await self._ensure_client()
        raw = await client.get(key)
        if not raw:
            logger.info("kv_checkpointer.get.miss: thread_id=%s", thread_id)
            return None
        try:
            payload = pickle.loads(raw)
        except Exception as exc:
            logger.warning("kv_checkpointer.get.unpickle_failed: thread_id=%s err=%s", thread_id, exc)
            return None

        logger.info("kv_checkpointer.get.hit: thread_id=%s size=%dB", thread_id, len(raw))

        checkpoint = payload.get("checkpoint")
        metadata = payload.get("metadata")
        pending_writes = payload.get("pending_writes")
        writes = payload.get("writes")
        parent_ts = payload.get("parent_ts")
        parent_config = payload.get("parent_config")
        cfg = payload.get("config") or config

        try:
            return CheckpointTuple(
                config=cfg,
                checkpoint=checkpoint,
                metadata=metadata,
                pending_writes=pending_writes,
                writes=writes,
                parent_ts=parent_ts,
                parent_config=parent_config,
            )
        except Exception:
            return CheckpointTuple(
                config=cfg,
                checkpoint=checkpoint,
                metadata=metadata,
                pending_writes=pending_writes,
            )

    async def aput(self, *args: Any, **kwargs: Any) -> None:
        config = args[0] if len(args) >= 1 else kwargs.get("config")
        if config is None:
            raise TypeError("aput requires config as first argument")
        checkpoint = args[1] if len(args) >= 2 else kwargs.get("checkpoint")
        metadata = args[2] if len(args) >= 3 else kwargs.get("metadata")
        versions = args[3] if len(args) >= 4 else kwargs.get("versions")
        pending_writes = kwargs.get("pending_writes")
        writes = kwargs.get("writes")
        parent_ts = kwargs.get("parent_ts")
        parent_config = kwargs.get("parent_config")

        thread_id = self._extract_thread_id(config)
        key = self._key(thread_id)
        client = await self._ensure_client()
        existing: dict[str, Any] = {}
        raw = await client.get(key)
        if raw:
            try:
                existing = pickle.loads(raw)
            except Exception:
                existing = {}

        existing["checkpoint"] = checkpoint
        existing["metadata"] = metadata
        if pending_writes is not None:
            existing["pending_writes"] = pending_writes
        if writes is not None:
            existing["writes"] = writes
        if parent_ts is not None:
            existing["parent_ts"] = parent_ts
        if parent_config is not None:
            existing["parent_config"] = parent_config
        if versions is not None:
            existing["versions"] = versions

        data = pickle.dumps(existing, protocol=pickle.HIGHEST_PROTOCOL)
        ex = self._default_ttl if self._default_ttl and self._default_ttl > 0 else None
        logger.info("kv_checkpointer.put: thread_id=%s size=%dB ttl=%s", thread_id, len(data), ex)
        if ex:
            await client.set(key, data, ex=ex)
        else:
            await client.set(key, data)

    async def aput_writes(self, *args: Any, **kwargs: Any) -> None:
        if len(args) >= 2:
            task_id = args[0]
            writes = args[1]
        else:
            task_id = kwargs.get("task_id")
            writes = kwargs.get("writes")
        if task_id is None:
            raise TypeError("aput_writes requires task_id")
        key = self._writes_key(self._normalize_id(task_id))
        data = pickle.dumps(writes, protocol=pickle.HIGHEST_PROTOCOL)
        ex = self._default_ttl if self._default_ttl and self._default_ttl > 0 else None
        logger.info("kv_checkpointer.put_writes: task_id=%s size=%dB ttl=%s", str(task_id), len(data), ex)
        client = await self._ensure_client()
        if ex:
            await client.set(key, data, ex=ex)
        else:
            await client.set(key, data)

    async def aget_writes(self, *args: Any, **kwargs: Any):
        task_id = args[0] if len(args) >= 1 else kwargs.get("task_id")
        if task_id is None:
            return None
        key = self._writes_key(self._normalize_id(task_id))
        client = await self._ensure_client()
        raw = await client.get(key)
        if not raw:
            logger.info("kv_checkpointer.get_writes.miss: task_id=%s", str(task_id))
            return None
        logger.info("kv_checkpointer.get_writes.hit: task_id=%s size=%dB", str(task_id), len(raw))
        try:
            return pickle.loads(raw)
        except Exception:
            return None

    def get_tuple(self, config: Any):
        return asyncio.get_event_loop().run_until_complete(self.aget_tuple(config))

    def put(self, config: Any, **kwargs: Any):
        return asyncio.get_event_loop().run_until_complete(self.aput(config, **kwargs))

    def get_next_version(self, *_args: Any, **_kwargs: Any) -> str:
        import time

        return str(time.time_ns())

    async def aget_next_version(self, *args: Any, **kwargs: Any) -> str:
        return self.get_next_version(*args, **kwargs)


def get_supervisor_checkpointer():
    client = None
    ttl_default_raw = app_config.REDIS_TTL_DEFAULT or app_config.REDIS_TTL_SESSION
    ttl_value: Optional[int] = None
    if ttl_default_raw not in (None, ""):
        try:
            ttl_value = int(str(ttl_default_raw))
        except Exception:
            ttl_value = None

    namespace = "langgraph:supervisor"
    saver = KVRedisCheckpointer(client=client, namespace=namespace, default_ttl=ttl_value)
    logger.info("Supervisor checkpointer: using KVRedisCheckpointer (SET/GET, TTL=%s)", ttl_value)
    return saver


async def redis_healthcheck() -> bool:
    try:
        client = _build_async_redis_client()
    except Exception as exc:
        logger.warning("Redis healthcheck skipped: %s", exc)
        return False
    try:
        await client.ping()
        logger.info("Redis healthcheck: healthy")
        return True
    except Exception as exc:
        logger.error("Redis healthcheck failed: %s", exc)
        return False
