import asyncio
import logging
import time
from typing import Any, AsyncIterator, Dict, Optional, Sequence, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    PendingWrite,
    get_checkpoint_id,
)

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


class KVRedisCheckpointer(BaseCheckpointSaver[str]):
    """Redis-backed checkpointer that uses typed LangGraph serialization."""

    def __init__(self, client, namespace: str, default_ttl: Optional[int]) -> None:
        super().__init__()
        self._client = client
        self._namespace = namespace.rstrip(":")
        self._default_ttl = int(default_ttl) if default_ttl else None
        self._lock = asyncio.Lock()

    def _checkpoint_key(self, thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> str:
        return f"{self._namespace}:cp:{thread_id}:{checkpoint_ns}:{checkpoint_id}"

    def _checkpoint_pattern(self, thread_id: str, checkpoint_ns: str) -> str:
        return f"{self._namespace}:cp:{thread_id}:{checkpoint_ns}:*"

    def _latest_pointer_key(self, thread_id: str, checkpoint_ns: str) -> str:
        return f"{self._namespace}:latest:{thread_id}:{checkpoint_ns}"

    def _writes_pattern(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
    ) -> str:
        return f"{self._namespace}:wr:{thread_id}:{checkpoint_ns}:{checkpoint_id}:*"

    def _writes_index_key(self, thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> str:
        return f"{self._namespace}:wrindex:{thread_id}:{checkpoint_ns}:{checkpoint_id}"

    @staticmethod
    def _order_pending_writes(entries: Sequence[PendingWrite]) -> list[PendingWrite]:
        enumerated = list(enumerate(entries))
        ordered_pairs = sorted(
            enumerated,
            key=lambda item: (
                WRITES_IDX_MAP.get(item[1][1], item[0]),
                item[0],
            ),
        )
        return [entry for _, entry in ordered_pairs]

    def _deserialize_pending_blob(
        self,
        type_blob: bytes | str | None,
        data_blob: bytes | None,
    ) -> tuple[bool, list[PendingWrite]]:
        if type_blob is None or data_blob is None:
            return False, []

        type_value = type_blob.decode() if isinstance(type_blob, bytes) else str(type_blob)
        try:
            raw_list = self.serde.loads_typed((type_value, data_blob))
        except Exception as exc:
            logger.warning("kv_checkpointer.pending_blob.deserialize_failed err=%s", exc)
            return False, []

        if not isinstance(raw_list, Sequence):
            return True, []

        normalized: list[PendingWrite] = []
        for entry in raw_list:
            if not isinstance(entry, Sequence) or len(entry) < 3:
                continue
            task_id_raw, channel_raw, value = entry[0], entry[1], entry[2]
            task_id = str(task_id_raw)
            channel = str(channel_raw)
            normalized.append((task_id, channel, value))

        return True, self._order_pending_writes(normalized)

    def _serialize_pending_writes(self, pending: Sequence[PendingWrite]) -> tuple[str, bytes]:
        ordered = self._order_pending_writes(list(pending))
        return self.serde.dumps_typed(ordered)

    async def _load_pending_blob_direct(
        self,
        client,
        checkpoint_key: str,
    ) -> tuple[bool, list[PendingWrite], bool]:
        type_blob, data_blob = await client.hmget(
            checkpoint_key,
            "pending_writes_type",
            "pending_writes",
        )
        found, entries = self._deserialize_pending_blob(type_blob, data_blob)
        both_none = bool(type_blob is None and data_blob is None)
        return found, entries, both_none

    async def _load_legacy_pending_writes(
        self,
        client,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
    ) -> list[PendingWrite]:
        t0 = time.perf_counter()
        pattern = self._writes_pattern(thread_id, checkpoint_ns, checkpoint_id)
        keys: list[str] = []
        async for key in client.scan_iter(match=pattern, count=100):
            keys.append(key.decode() if isinstance(key, bytes) else str(key))
        t1 = time.perf_counter()

        if not keys:
            logger.info(
                "kv_checkpointer.timing.legacy_scan thread_id=%s ns=%s cp=%s ms=%d keys=%d",
                thread_id,
                checkpoint_ns,
                checkpoint_id,
                int((t1 - t0) * 1000),
                0,
            )
            return []

        logger.info(
            "kv_checkpointer.timing.legacy_scan thread_id=%s ns=%s cp=%s ms=%d keys=%d",
            thread_id,
            checkpoint_ns,
            checkpoint_id,
            int((t1 - t0) * 1000),
            len(keys),
        )

        t2 = time.perf_counter()
        pipe = client.pipeline(transaction=False)
        for key in keys:
            pipe.hgetall(key)
        raw_results = await pipe.execute()
        t3 = time.perf_counter()
        logger.info(
            "kv_checkpointer.timing.legacy_hgetall thread_id=%s ns=%s cp=%s ms=%d batches=%d",
            thread_id,
            checkpoint_ns,
            checkpoint_id,
            int((t3 - t2) * 1000),
            len(keys),
        )

        entries: list[tuple[int, PendingWrite]] = []
        for key, write_data in zip(keys, raw_results, strict=False):
            if not write_data:
                continue
            try:
                task_id_bytes = write_data[b"task_id"]
                channel_bytes = write_data[b"channel"]
                value_type = write_data[b"type"].decode()
                value_bytes = write_data[b"value"]
                idx_bytes = write_data.get(b"idx")
            except KeyError:
                logger.warning("kv_checkpointer.legacy_load.missing_fields key=%s", key)
                continue

            try:
                value = self.serde.loads_typed((value_type, value_bytes))
            except Exception as exc:
                logger.warning("kv_checkpointer.legacy_load.deserialize_failed key=%s err=%s", key, exc)
                continue

            idx = int(idx_bytes.decode()) if idx_bytes else len(entries)
            task_id = task_id_bytes.decode()
            channel = channel_bytes.decode()
            entries.append((idx, (task_id, channel, value)))

        ordered = [item for _, item in sorted(entries, key=lambda entry: entry[0])]
        logger.info(
            "kv_checkpointer.timing.legacy_result thread_id=%s ns=%s cp=%s total_entries=%d total_ms=%d",
            thread_id,
            checkpoint_ns,
            checkpoint_id,
            len(ordered),
            int((t3 - t0) * 1000),
        )
        return self._order_pending_writes(ordered)

    async def _clear_legacy_pending_writes(
        self,
        client,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
    ) -> None:
        pattern = self._writes_pattern(thread_id, checkpoint_ns, checkpoint_id)
        keys: list[str] = []
        async for key in client.scan_iter(match=pattern, count=100):
            keys.append(key.decode() if isinstance(key, bytes) else str(key))
        if keys:
            await client.delete(*keys)
        index_key = self._writes_index_key(thread_id, checkpoint_ns, checkpoint_id)
        await client.delete(index_key)

    async def _load_pending_writes(
        self,
        client,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
    ) -> list[PendingWrite]:
        checkpoint_key = self._checkpoint_key(thread_id, checkpoint_ns, checkpoint_id)
        found, entries, both_none = await self._load_pending_blob_direct(client, checkpoint_key)
        if found:
            return entries
        # FAST PATH: if no blob fields exist at all, skip legacy scan entirely
        if both_none:
            logger.info(
                "kv_checkpointer.pending_blob.absent thread_id=%s ns=%s cp=%s -> returning empty writes (skip legacy)",
                thread_id,
                checkpoint_ns,
                checkpoint_id,
            )
            return []

        legacy_entries = await self._load_legacy_pending_writes(
            client,
            thread_id,
            checkpoint_ns,
            checkpoint_id,
        )
        if not legacy_entries:
            return []

        pending_type, pending_bytes = self._serialize_pending_writes(legacy_entries)
        pipe = client.pipeline(transaction=False)
        pipe.hset(
            checkpoint_key,
            mapping={
                "pending_writes_type": pending_type,
                "pending_writes": pending_bytes,
            },
        )
        if self._default_ttl:
            pipe.expire(checkpoint_key, self._default_ttl)
        await pipe.execute()
        await self._clear_legacy_pending_writes(client, thread_id, checkpoint_ns, checkpoint_id)
        return legacy_entries

    async def _ensure_client(self):
        if self._client is None:
            self._client = _build_async_redis_client()
        return self._client

    @staticmethod
    def _get_thread_id(config: RunnableConfig) -> str:
        configurable = cast(Dict[str, Any], config.get("configurable") or {})
        thread_id = configurable.get("thread_id")
        if thread_id is None:
            raise ValueError("KVRedisCheckpointer requires thread_id in config.configurable")
        return str(thread_id)

    @staticmethod
    def _get_checkpoint_ns(config: RunnableConfig) -> str:
        configurable = cast(Dict[str, Any], config.get("configurable") or {})
        checkpoint_ns = configurable.get("checkpoint_ns")
        return str(checkpoint_ns) if checkpoint_ns is not None else ""

    async def _load_checkpoint_tuple(
        self,
        client,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
    ) -> CheckpointTuple | None:
        key = self._checkpoint_key(thread_id, checkpoint_ns, checkpoint_id)
        data = await client.hgetall(key)
        if not data:
            return None

        try:
            checkpoint_type = data[b"checkpoint_type"].decode()
            checkpoint_bytes = data[b"checkpoint"]
            metadata_type = data[b"metadata_type"].decode()
            metadata_bytes = data[b"metadata"]
        except KeyError:
            logger.warning("kv_checkpointer.load_checkpoint.missing_fields key=%s", key)
            return None

        try:
            checkpoint = self.serde.loads_typed((checkpoint_type, checkpoint_bytes))
            metadata = self.serde.loads_typed((metadata_type, metadata_bytes))
        except Exception as exc:
            logger.warning("kv_checkpointer.load_checkpoint.deserialize_failed key=%s err=%s", key, exc)
            return None

        parent_checkpoint_id_bytes = data.get(b"parent_checkpoint_id")
        parent_checkpoint_id = parent_checkpoint_id_bytes.decode() if parent_checkpoint_id_bytes else None

        pending_found, pending_writes = self._deserialize_pending_blob(
            data.get(b"pending_writes_type"),
            data.get(b"pending_writes"),
        )
        if not pending_found:
            pending_writes = await self._load_pending_writes(
                client,
                thread_id,
                checkpoint_ns,
                checkpoint_id,
            )

        resume_config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }
        parent_config: RunnableConfig | None = None
        if parent_checkpoint_id:
            parent_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": parent_checkpoint_id,
                }
            }

        return CheckpointTuple(
            config=resume_config,
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_config,
            pending_writes=pending_writes or None,
        )

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        t_total0 = time.perf_counter()
        thread_id = self._get_thread_id(config)
        checkpoint_ns = self._get_checkpoint_ns(config)
        checkpoint_id = get_checkpoint_id(config)

        client = await self._ensure_client()
        if checkpoint_id:
            t_l0 = time.perf_counter()
            result = await self._load_checkpoint_tuple(client, thread_id, checkpoint_ns, checkpoint_id)
            t_l1 = time.perf_counter()
            logger.info(
                "kv_checkpointer.timing.load_checkpoint direct thread_id=%s ns=%s cp=%s ms=%d found=%s",
                thread_id,
                checkpoint_ns,
                checkpoint_id,
                int((t_l1 - t_l0) * 1000),
                bool(result),
            )
            return result

        pointer_key = self._latest_pointer_key(thread_id, checkpoint_ns)
        t_p0 = time.perf_counter()
        pointer_raw = await client.get(pointer_key)
        t_p1 = time.perf_counter()
        logger.info(
            "kv_checkpointer.timing.pointer_get thread_id=%s ns=%s ms=%d has_pointer=%s",
            thread_id,
            checkpoint_ns,
            int((t_p1 - t_p0) * 1000),
            bool(pointer_raw),
        )
        if pointer_raw:
            pointer_id = pointer_raw.decode() if isinstance(pointer_raw, bytes) else str(pointer_raw)
            t_l0 = time.perf_counter()
            tuple_candidate = await self._load_checkpoint_tuple(
                client,
                thread_id,
                checkpoint_ns,
                pointer_id,
            )
            t_l1 = time.perf_counter()
            logger.info(
                "kv_checkpointer.timing.load_checkpoint from_pointer thread_id=%s ns=%s cp=%s ms=%d found=%s",
                thread_id,
                checkpoint_ns,
                pointer_id,
                int((t_l1 - t_l0) * 1000),
                bool(tuple_candidate),
            )
            if tuple_candidate:
                t_total1 = time.perf_counter()
                logger.info(
                    "kv_checkpointer.timing.aget_tuple.total thread_id=%s ns=%s ms=%d",
                    thread_id,
                    checkpoint_ns,
                    int((t_total1 - t_total0) * 1000),
                )
                return tuple_candidate

        # FAST PATH: do not perform expensive SCAN fallback if pointer missing
        limited_result: CheckpointTuple | None = None
        logger.info(
            "kv_checkpointer.timing.alist_fallback.skipped thread_id=%s ns=%s reason=no_pointer",
            thread_id,
            checkpoint_ns,
        )
        t_total1 = time.perf_counter()
        logger.info(
            "kv_checkpointer.timing.aget_tuple.total thread_id=%s ns=%s ms=%d",
            thread_id,
            checkpoint_ns,
            int((t_total1 - t_total0) * 1000),
        )
        return limited_result

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        thread_id = self._get_thread_id(config)
        checkpoint_ns = self._get_checkpoint_ns(config)
        checkpoint_id = checkpoint["id"]
        parent_checkpoint_id = get_checkpoint_id(config)

        checkpoint_type, checkpoint_bytes = self.serde.dumps_typed(checkpoint)
        metadata_type, metadata_bytes = self.serde.dumps_typed(metadata)

        key = self._checkpoint_key(thread_id, checkpoint_ns, checkpoint_id)
        hash_data: Dict[str, Any] = {
            "checkpoint_type": checkpoint_type,
            "checkpoint": checkpoint_bytes,
            "metadata_type": metadata_type,
            "metadata": metadata_bytes,
        }
        if parent_checkpoint_id:
            hash_data["parent_checkpoint_id"] = parent_checkpoint_id

        client = await self._ensure_client()
        pointer_key = self._latest_pointer_key(thread_id, checkpoint_ns)
        async with self._lock:
            pipe = client.pipeline(transaction=False)
            pipe.hset(key, mapping=hash_data)
            if self._default_ttl:
                pipe.expire(key, self._default_ttl)
            pipe.set(pointer_key, checkpoint_id)
            # Do NOT expire the latest pointer to avoid slow fallback paths
            t0 = time.perf_counter()
            await pipe.execute()
            t1 = time.perf_counter()
            logger.info(
                "kv_checkpointer.timing.aput.pipeline thread_id=%s ns=%s cp=%s ms=%d ttl=%s",
                thread_id,
                checkpoint_ns,
                checkpoint_id,
                int((t1 - t0) * 1000),
                self._default_ttl,
            )

        logger.debug(
            "kv_checkpointer.put checkpoint thread_id=%s checkpoint_ns=%s checkpoint_id=%s ttl=%s",
            thread_id,
            checkpoint_ns,
            checkpoint_id,
            self._default_ttl,
        )

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        _ = task_path
        if not writes:
            return

        thread_id = self._get_thread_id(config)
        checkpoint_ns = self._get_checkpoint_ns(config)
        checkpoint_id = get_checkpoint_id(config)
        if not checkpoint_id:
            raise ValueError("aput_writes requires checkpoint_id in config.configurable")

        client = await self._ensure_client()
        async with self._lock:
            checkpoint_key = self._checkpoint_key(thread_id, checkpoint_ns, checkpoint_id)
            t_lw0 = time.perf_counter()
            existing_writes = await self._load_pending_writes(
                client,
                thread_id,
                checkpoint_ns,
                checkpoint_id,
            )
            t_lw1 = time.perf_counter()
            logger.info(
                "kv_checkpointer.timing.aput_writes.load_existing thread_id=%s ns=%s cp=%s ms=%d existing=%d new=%d",
                thread_id,
                checkpoint_ns,
                checkpoint_id,
                int((t_lw1 - t_lw0) * 1000),
                len(existing_writes),
                len(writes),
            )
            combined_writes = list(existing_writes)
            combined_writes.extend((task_id, channel, value) for channel, value in writes)
            pending_type, pending_bytes = self._serialize_pending_writes(combined_writes)
            pipe = client.pipeline(transaction=False)
            pipe.hset(
                checkpoint_key,
                mapping={
                    "pending_writes_type": pending_type,
                    "pending_writes": pending_bytes,
                },
            )
            if self._default_ttl:
                pipe.expire(checkpoint_key, self._default_ttl)
                # Do NOT expire the latest pointer to avoid slow fallback paths
            t0 = time.perf_counter()
            await pipe.execute()
            t1 = time.perf_counter()
            logger.info(
                "kv_checkpointer.timing.aput_writes.pipeline thread_id=%s ns=%s cp=%s ms=%d combined=%d",
                thread_id,
                checkpoint_ns,
                checkpoint_id,
                int((t1 - t0) * 1000),
                len(combined_writes),
            )

        logger.debug(
            "kv_checkpointer.put_writes.commit thread_id=%s checkpoint_ns=%s checkpoint_id=%s task_id=%s count=%d",
            thread_id,
            checkpoint_ns,
            checkpoint_id,
            task_id,
            len(writes),
        )

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: Dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        if config is None:
            return

        thread_id = self._get_thread_id(config)
        checkpoint_ns = self._get_checkpoint_ns(config)

        client = await self._ensure_client()
        tuples: list[CheckpointTuple] = []
        async for key in client.scan_iter(match=self._checkpoint_pattern(thread_id, checkpoint_ns), count=100):
            key_str = key.decode() if isinstance(key, bytes) else str(key)
            checkpoint_id = key_str.split(":")[-1]
            checkpoint_tuple = await self._load_checkpoint_tuple(client, thread_id, checkpoint_ns, checkpoint_id)
            if checkpoint_tuple:
                tuples.append(checkpoint_tuple)

        tuples.sort(key=lambda item: item.checkpoint["ts"], reverse=True)

        for idx, item in enumerate(tuples):
            if limit is not None and idx >= limit:
                break
            yield item


def get_supervisor_checkpointer():
    ttl_default_raw = app_config.REDIS_TTL_DEFAULT or app_config.REDIS_TTL_SESSION
    ttl_value: Optional[int] = None
    if ttl_default_raw not in (None, ""):
        try:
            ttl_value = int(str(ttl_default_raw))
        except Exception:
            ttl_value = None

    namespace = "langgraph:supervisor"

    try:
        client = _build_async_redis_client()
        saver = KVRedisCheckpointer(client=client, namespace=namespace, default_ttl=ttl_value)
        logger.info("Supervisor checkpointer: using KVRedisCheckpointer (SET/GET, TTL=%s)", ttl_value)
        return saver
    except Exception as exc:
        logger.warning("Redis checkpointer unavailable err=%s", exc)


async def redis_healthcheck() -> bool:
    try:
        client = _build_async_redis_client()
    except Exception as exc:
        logger.warning("Redis healthcheck skipped err=%s", exc)
        return False
    try:
        await client.ping()
        logger.info("Redis healthcheck: healthy")
        return True
    except Exception as exc:
        logger.error("Redis healthcheck failed err=%s", exc)
        return False
