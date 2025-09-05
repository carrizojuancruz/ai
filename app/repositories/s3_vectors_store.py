from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Literal, Optional, Sequence, Tuple, TypeAlias, cast
from uuid import NAMESPACE_URL, UUID, uuid5

try:
    from langgraph.store.base import NOT_PROVIDED, BaseStore, Item, NotProvided, Op, Result, SearchItem
except Exception:  # pragma: no cover
    from typing import Protocol

    class NotProvided:  # type: ignore
        pass

    NOT_PROVIDED: NotProvided = NotProvided()  # type: ignore

    @dataclass
    class Item:  # type: ignore
        value: dict[str, Any]
        key: str
        namespace: list[str]
        created_at: str
        updated_at: str

    @dataclass
    class SearchItem(Item):  # type: ignore
        score: Optional[float] = None

    class Op(Protocol):  # type: ignore
        op: str
        args: tuple[Any, ...]
        kwargs: dict[str, Any]

    Result: TypeAlias = Any  # type: ignore

    class BaseStore:  # type: ignore
        supports_ttl: bool = False

        def batch(self, ops: Iterable[Op]) -> list[Any]:
            raise NotImplementedError

        async def abatch(self, ops: Iterable[Op]) -> list[Any]:
            raise NotImplementedError

from botocore.client import BaseClient
from botocore.exceptions import ClientError

Namespace = Tuple[str, ...]


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _join_namespace(namespace: Namespace) -> str:
    return "|".join(namespace)


def _compose_point_uuid(namespace: Namespace, key: str) -> UUID:
    materialized_path = f"{_join_namespace(namespace)}::{key}"
    return uuid5(NAMESPACE_URL, materialized_path)


def _flatten_all_strings(data: Any) -> list[str]:
    stack: list[Any] = [data]
    strings: list[str] = []
    while stack:
        cur = stack.pop()
        if isinstance(cur, str):
            strings.append(cur)
        elif isinstance(cur, dict):
            stack.extend(cur.values())
        elif isinstance(cur, (list, tuple)):
            stack.extend(cur)
    return strings


def _extract_by_field_paths(value: dict[str, Any], field_paths: Sequence[str]) -> list[str]:
    if not field_paths:
        return _flatten_all_strings(value)

    def iter_path(obj: Any, tokens: list[str]) -> Iterable[Any]:
        if not tokens:
            yield obj
            return
        head, *tail = tokens
        if isinstance(obj, dict):
            if head in obj:
                yield from iter_path(obj[head], tail)
            return
        if isinstance(obj, list):
            if head == "*":
                for el in obj:
                    yield from iter_path(el, tail)
            else:
                try:
                    idx = int(head)
                except Exception:
                    return
                if 0 <= idx < len(obj):
                    yield from iter_path(obj[idx], tail)

    results: list[str] = []
    for path in field_paths:
        if path == "$":
            results.extend(_flatten_all_strings(value))
            continue
        tokens: list[str] = []
        for raw in path.split("."):
            if "[" in raw and raw.endswith("]"):
                name, index = raw[:-1].split("[")
                if name:
                    tokens.append(name)
                tokens.append("*" if index == "*" else index)
            else:
                tokens.append(raw)
        for match in iter_path(value, tokens):
            if isinstance(match, str):
                results.append(match)
            else:
                results.extend(_flatten_all_strings(match))
    return results


class S3VectorsStore(BaseStore):
    supports_ttl: bool = False

    def __init__(
        self,
        *,
        s3v_client: BaseClient,
        bedrock_client: BaseClient,
        vector_bucket_name: str,
        index_name: str,
        dims: int,
        model_id: str,
        distance: Literal["COSINE", "EUCLIDEAN"] = "COSINE",
        default_index_fields: Optional[list[str]] = None,
    ) -> None:
        self._s3v = s3v_client
        self._bedrock = bedrock_client
        self._bucket = vector_bucket_name
        self._index = index_name
        self._dims = int(dims)
        self._model_id = model_id
        self._distance = distance
        self._default_index_fields = default_index_fields or ["summary"]

    # region BaseStore API
    def batch(self, ops: Iterable[Op]) -> list[Any]:
        results: list[Any] = []
        for op in ops:
            name = getattr(op, "op", None) or getattr(op, "name", None)
            args = list(getattr(op, "args", ()))
            kwargs = dict(getattr(op, "kwargs", {}))
            if name == "get":
                results.append(self.get(*cast(tuple, tuple(args)), **kwargs))
            elif name == "search":
                results.append(self.search(*cast(tuple, tuple(args)), **kwargs))
            elif name == "put":
                self.put(*cast(tuple, tuple(args)), **kwargs)
                results.append(None)
            elif name == "delete":
                self.delete(*cast(tuple, tuple(args)))
                results.append(None)
            elif name == "list_namespaces":
                results.append(self.list_namespaces(**kwargs))
            else:
                raise ValueError(f"Unsupported op: {name}")
        return results

    async def abatch(self, ops: Iterable[Op]) -> list[Any]:
        return self.batch(ops)

    def get(
        self,
        namespace: Namespace,
        key: str,
        *,
        refresh_ttl: bool | None = None,
    ) -> Item | None:
        point_id = str(_compose_point_uuid(namespace, key))
        try:
            # Prefer direct key fetch if available in preview at runtime
            if hasattr(self._s3v, "get_vectors"):
                res = self._s3v.get_vectors(
                    vectorBucketName=self._bucket,
                    indexName=self._index,
                    keys=[point_id],
                    returnMetadata=True,
                )
                vectors = cast(list[dict[str, Any]], res.get("vectors") or [])
                if not vectors:
                    return None
                md = cast(dict[str, Any], vectors[0].get("metadata") or {})
                raw = cast(str, md.get("value_json") or "")
                try:
                    value = json.loads(raw) if raw else {}
                except Exception:
                    value = {}
                created_at = cast(str, md.get("created_at") or _utc_now_iso())
                updated_at = cast(str, md.get("updated_at") or created_at)
                ns0 = cast(str, md.get("ns_0") or (namespace[0] if len(namespace) > 0 else ""))
                ns1 = cast(str, md.get("ns_1") or (namespace[1] if len(namespace) > 1 else ""))
                ns_list = [ns0] + ([ns1] if ns1 else [])
                doc_key = cast(str, md.get("doc_key") or key)
        except Exception:
            logging.exception("Error in direct key fetch in get")

        # Build a JSON filter using equality shorthand per S3 Vectors docs
        flt = self._build_filter(namespace, {"doc_key": key}, include_is_indexed=False)

        zero = self._zero_vector()
        res = self._safe_query_vectors(
            query_vector=zero,
            top_k=1,
            flt=flt,
            return_distance=False,
        )
        vectors = cast(list[dict[str, Any]], res.get("vectors") or [])
        if not vectors:
            return None
        md = cast(dict[str, Any], vectors[0].get("metadata") or {})
        raw = cast(str, md.get("value_json") or "")
        try:
            value = json.loads(raw) if raw else {}
        except Exception:
            value = {}
        created_at = cast(str, md.get("created_at") or _utc_now_iso())
        updated_at = cast(str, md.get("updated_at") or created_at)
        ns0 = cast(str, md.get("ns_0") or (namespace[0] if len(namespace) > 0 else ""))
        ns1 = cast(str, md.get("ns_1") or (namespace[1] if len(namespace) > 1 else ""))
        ns_list = [ns0] + ([ns1] if ns1 else [])
        doc_key = cast(str, md.get("doc_key") or key)
        return Item(value=value, key=doc_key, namespace=ns_list, created_at=created_at, updated_at=updated_at)

    def search(
        self,
        namespace_prefix: Namespace,
        /,
        *,
        query: str | None = None,
        filter: dict[str, Any] | None = None,
        limit: int = 10,
        offset: int = 0,
        refresh_ttl: bool | None = None,
    ) -> list[SearchItem]:
        if not query:
            return []

        query_vec = self._embed_texts([query])[0]

        flt = self._build_filter(namespace_prefix, filter)
        eff_limit = limit + offset if offset else limit
        res = self._safe_query_vectors(
            query_vector=query_vec,
            top_k=max(1, eff_limit),
            flt=flt,
            return_distance=True,
        )
        vectors = cast(list[dict[str, Any]], res.get("vectors") or [])
        iterable = vectors[offset : offset + limit] if offset else vectors
        items: list[SearchItem] = []
        for v in iterable:
            md = cast(dict[str, Any], v.get("metadata") or {})
            raw = cast(str, md.get("value_json") or "")
            try:
                value = json.loads(raw) if raw else {}
            except Exception:
                value = {}
            created_at = cast(str, md.get("created_at") or _utc_now_iso())
            updated_at = cast(str, md.get("updated_at") or created_at)
            ns0 = cast(str, md.get("ns_0") or "")
            ns1 = cast(str, md.get("ns_1") or "")
            ns_list = [ns0] + ([ns1] if ns1 else [])
            doc_key = cast(str, md.get("doc_key") or "")
            # S3 Vectors returns a distance. Convert to a similarity score in [0,1] where higher is better.
            raw_distance = cast(Optional[float], v.get("distance"))
            score: Optional[float]
            if isinstance(raw_distance, (int, float)):
                d = float(raw_distance)
                # Use ternary operator for score calculation
                score = max(0.0, min(1.0, 1.0 - d)) if self._distance == "COSINE" else 1.0 / (1.0 + max(0.0, d))
            else:
                score = None
            items.append(
                SearchItem(
                    value=value,
                    key=doc_key,
                    namespace=ns_list,
                    created_at=created_at,
                    updated_at=updated_at,
                    score=score,
                )
            )
        return items

    def put(
        self,
        namespace: Namespace,
        key: str,
        value: dict[str, Any],
        index: Literal[False] | list[str] | None = None,
        *,
        ttl: float | None | NotProvided = NOT_PROVIDED,
    ) -> None:
        point_id = str(_compose_point_uuid(namespace, key))
        now = _utc_now_iso()
        created_at = cast(str, value.get("created_at") or now)
        updated_at = now

        default_fields = self._default_index_fields
        if index is None:
            fields_to_index: Optional[list[str]] = default_fields
        elif index is False:
            fields_to_index = None
        else:
            fields_to_index = list(index)

        is_indexed = fields_to_index is not None
        vector = self._zero_vector()
        if is_indexed:
            texts = _extract_by_field_paths(value, fields_to_index)
            joined = "\n".join([t for t in texts if t])
            vector = self._embed_texts([joined])[0] if joined else self._zero_vector()

        # S3 Vectors preview: metadata values must be primitive/arrays and capped number of keys.
        payload: dict[str, Any] = {
            "value_json": json.dumps(value, ensure_ascii=False),  # 1 as string
            "doc_key": key,  # 2
            "created_at": created_at,  # 3
            "updated_at": updated_at,  # 4
            "is_indexed": is_indexed,  # 5
            "ns_0": namespace[0] if len(namespace) > 0 else "",  # 6
            "ns_1": namespace[1] if len(namespace) > 1 else "",  # 7
        }
        # Only include category as filter key if present
        if "category" in value:
            payload["category"] = value["category"]  # 8

        if "topic_key" in value:
            payload["topic_key"] = value["topic_key"]
        if "importance_bin" in value:
            payload["importance_bin"] = value["importance_bin"]
        if "bucket_week" in value:
            payload["bucket_week"] = value["bucket_week"]
        if "valid_until" in value:
            payload["valid_until"] = value["valid_until"]
        if "nudge_cooldown_until" in value:
            payload["nudge_cooldown_until"] = value["nudge_cooldown_until"]
        if "provider" in value:
            payload["provider"] = value["provider"]
        if "progress_pct" in value:
            payload["progress_pct"] = value["progress_pct"]
        if "budget_used_pct" in value:
            payload["budget_used_pct"] = value["budget_used_pct"]
        if "trailing_30d_spend" in value:
            payload["trailing_30d_spend"] = value["trailing_30d_spend"]
        if "baseline_30d_spend" in value:
            payload["baseline_30d_spend"] = value["baseline_30d_spend"]

        self._s3v.put_vectors(
            vectorBucketName=self._bucket,
            indexName=self._index,
            vectors=[
                {
                    "key": point_id,
                    "data": {"float32": vector},
                    "metadata": payload,
                }
            ],
        )

    def delete(self, namespace: Namespace, key: str) -> None:
        point_id = str(_compose_point_uuid(namespace, key))
        if hasattr(self._s3v, "delete_vectors"):
            self._s3v.delete_vectors(
                vectorBucketName=self._bucket,
                indexName=self._index,
                keys=[point_id],
            )
            return
        # Fallback: some previews may expose a generic delete API
        if hasattr(self._s3v, "delete"):
            self._s3v.delete(
                vectorBucketName=self._bucket,
                indexName=self._index,
                keys=[point_id],
            )

    def list_namespaces(
        self,
        *,
        prefix: Optional[Sequence[str]] = None,
        suffix: Optional[Sequence[str]] = None,
        max_depth: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[tuple[str, ...]]:
        return []

    async def aget(
        self,
        namespace: Namespace,
        key: str,
        *,
        refresh_ttl: bool | None = None,
    ) -> Item | None:
        return self.get(namespace, key, refresh_ttl=refresh_ttl)

    async def asearch(
        self,
        namespace_prefix: Namespace,
        /,
        *,
        query: str | None = None,
        filter: dict[str, Any] | None = None,
        limit: int = 10,
        offset: int = 0,
        refresh_ttl: bool | None = None,
    ) -> list[SearchItem]:
        return self.search(
            namespace_prefix,
            query=query,
            filter=filter,
            limit=limit,
            offset=offset,
            refresh_ttl=refresh_ttl,
        )

    async def aput(
        self,
        namespace: Namespace,
        key: str,
        value: dict[str, Any],
        index: Literal[False] | list[str] | None = None,
        *,
        ttl: float | None | NotProvided = NOT_PROVIDED,
    ) -> None:
        self.put(namespace, key, value, index, ttl=ttl)

    async def adelete(self, namespace: Namespace, key: str) -> None:
        self.delete(namespace, key)

    async def alist_namespaces(
        self,
        *,
        prefix: Optional[Sequence[str]] = None,
        suffix: Optional[Sequence[str]] = None,
        max_depth: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[tuple[str, ...]]:
        return self.list_namespaces(
            prefix=prefix,
            suffix=suffix,
            max_depth=max_depth,
            limit=limit,
            offset=offset,
        )

    def search_by_filter(
        self,
        namespace: Namespace,
        filter: dict[str, Any],
        limit: int = 10,
        offset: int = 0,
    ) -> list[SearchItem]:
        zero_vec = self._zero_vector()
        flt = self._build_filter(namespace, filter, include_is_indexed=False)
        eff_limit = limit + offset if offset else limit
        res = self._safe_query_vectors(
            query_vector=zero_vec,
            top_k=max(1, eff_limit),
            flt=flt,
            return_distance=False,
        )
        vectors = cast(list[dict[str, Any]], res.get("vectors") or [])
        iterable = vectors[offset : offset + limit] if offset else vectors
        items: list[SearchItem] = []
        for v in iterable:
            md = cast(dict[str, Any], v.get("metadata") or {})
            raw = cast(str, md.get("value_json") or "")
            try:
                value = json.loads(raw) if raw else {}
            except Exception:
                value = {}
            value.update(
                {
                    k: v
                    for k, v in md.items()
                    if k not in ["value_json", "doc_key", "created_at", "updated_at", "is_indexed", "ns_0", "ns_1"]
                }
            )
            created_at = cast(str, md.get("created_at") or _utc_now_iso())
            updated_at = cast(str, md.get("updated_at") or created_at)
            ns0 = cast(str, md.get("ns_0") or "")
            ns1 = cast(str, md.get("ns_1") or "")
            ns_list = [ns0] + ([ns1] if ns1 else [])
            doc_key = cast(str, md.get("doc_key") or "")
            items.append(
                SearchItem(
                    value=value,
                    key=doc_key,
                    namespace=ns_list,
                    created_at=created_at,
                    updated_at=updated_at,
                    metadata=md,
                    score=None,
                )
            )
        return items

    async def asearch_by_filter(
        self,
        namespace: Namespace,
        filter: dict[str, Any],
        limit: int = 10,
        offset: int = 0,
    ) -> list[SearchItem]:
        return self.search_by_filter(namespace, filter, limit, offset)

    def update_metadata(
        self,
        namespace: Namespace,
        key: str,
        metadata_update: dict[str, Any],
    ) -> None:
        item = self.get(namespace, key)
        if not item:
            raise ValueError(f"Item not found: {namespace}/{key}")
        updated_value = item.value.copy()
        updated_value.update(metadata_update)
        updated_value["created_at"] = item.created_at
        self.put(namespace, key, updated_value)

    async def aupdate_metadata(
        self,
        namespace: Namespace,
        key: str,
        metadata_update: dict[str, Any],
    ) -> None:
        self.update_metadata(namespace, key, metadata_update)

    # endregion

    def _zero_vector(self) -> list[float]:
        return [0.0] * self._dims

    def _safe_query_vectors(
        self,
        *,
        query_vector: list[float],
        top_k: int,
        flt: Optional[dict[str, Any]],
        return_distance: bool,
    ) -> dict[str, Any]:
        # Primary attempt with provided filter
        attempts: list[Optional[dict[str, Any]]] = []
        attempts.append(flt if flt else None)
        if flt:
            # Alt 1: wrap as $and of equality shorthand
            attempts.append({"$and": [{k: v} for k, v in flt.items()]})
            # Alt 2: wrap each as $eq
            attempts.append({"$and": [{k: {"$eq": v}} for k, v in flt.items()]})
        # Final fallback: no filter
        attempts.append(None)

        last_error: Exception | None = None
        for candidate in attempts:
            try:
                return self._s3v.query_vectors(
                    vectorBucketName=self._bucket,
                    indexName=self._index,
                    queryVector={"float32": query_vector},
                    topK=max(1, top_k),
                    filter=candidate,
                    returnMetadata=True,
                    returnDistance=return_distance,
                )
            except ClientError as e:
                message = str(e)
                # Retry only on filter validation issues; otherwise raise
                if "Invalid query filter" in message or "ValidationException" in message:
                    last_error = e
                    continue
                raise
        # If all attempts failed, re-raise last validation error
        if last_error:
            raise last_error
        # Should not reach here; return empty result
        return {"vectors": []}

    def _build_filter(
        self,
        namespace_prefix: Namespace,
        user_filter: Optional[dict[str, Any]],
        *,
        include_is_indexed: bool = True,
    ) -> dict[str, Any]:
        # Build filter using equality shorthand supported by S3 Vectors metadata filtering
        # e.g., {"ns_0": "<user_id>", "ns_1": "semantic", "is_indexed": true, "category": "finance"}
        flt: dict[str, Any] = {}
        if len(namespace_prefix) > 0 and namespace_prefix[0]:
            flt["ns_0"] = namespace_prefix[0]
        if len(namespace_prefix) > 1 and namespace_prefix[1]:
            flt["ns_1"] = namespace_prefix[1]
        if include_is_indexed:
            flt["is_indexed"] = True
        if user_filter:
            for k, v in user_filter.items():
                if v is None:
                    continue
                flt[k] = v
        return flt

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        joined: list[list[float]] = []
        for text in texts:
            payload = {"inputText": text}
            res = self._bedrock.invoke_model(modelId=self._model_id, body=json.dumps(payload))
            body = res.get("body")
            data = json.loads(body.read()) if hasattr(body, "read") else json.loads(body)
            embedding = cast(list[float], data.get("embedding") or [])
            if len(embedding) != self._dims:
                # Coerce or pad/truncate defensively
                if len(embedding) > self._dims:
                    embedding = embedding[: self._dims]
                else:
                    embedding = embedding + [0.0] * (self._dims - len(embedding))
            joined.append(embedding)
        return joined


_s3_vectors_store_instance = None


def get_s3_vectors_store():
    global _s3_vectors_store_instance

    if _s3_vectors_store_instance is None:
        from app.services.memory.store_factory import create_s3_vectors_store_from_env

        _s3_vectors_store_instance = create_s3_vectors_store_from_env()

    return _s3_vectors_store_instance
