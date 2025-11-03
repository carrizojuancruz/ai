from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Literal, Optional, Sequence, Tuple, TypeAlias, cast
from uuid import NAMESPACE_URL, UUID, uuid5

try:
    from langgraph.store.base import NOT_PROVIDED, BaseStore, Item, NotProvided, Op, SearchItem
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

from app.core.config import config

Namespace = Tuple[str, ...]


logger = logging.getLogger(__name__)


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
    MAX_PAGINATION_PAGES: int = 100
    ABSOLUTE_MAX_VECTORS: int = 100_000

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
                logger.info("s3v.get: method=direct_key")
                return Item(value=value, key=doc_key, namespace=ns_list, created_at=created_at, updated_at=updated_at)
        except Exception:
            logging.exception("Error in direct key fetch in get")

        # Build a JSON filter using equality shorthand per S3 Vectors docs
        flt = self._build_filter(namespace, {"doc_key": key}, include_is_indexed=False)

        logger.info("s3v.get: method=fallback_query")
        query_vec = self._embed_texts([key])[0]
        res = self._safe_query_vectors(
            query_vector=query_vec,
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
        aws_query_limit = 100
        safe_top_k = max(1, min(eff_limit, min(config.S3V_MAX_TOP_K, aws_query_limit)))
        res = self._safe_query_vectors(
            query_vector=query_vec,
            top_k=safe_top_k,
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
        """Delete a single item by its key."""
        point_id = str(_compose_point_uuid(namespace, key))
        self._s3v.delete_vectors(
            vectorBucketName=self._bucket,
            indexName=self._index,
            keys=[point_id],
        )

    def batch_delete_by_keys(
        self,
        namespace: Namespace,
        keys: list[str],
        batch_size: int = 100,
    ) -> dict[str, Any]:
        """Delete multiple items by their keys using efficient batch deletion."""
        if not keys:
            return {
                "deleted_count": 0,
                "failed_count": 0,
                "total_found": 0,
            }

        deleted_count = 0
        failed_count = 0

        for i in range(0, len(keys), batch_size):
            batch_keys = keys[i:i + batch_size]
            point_ids = [str(_compose_point_uuid(namespace, key)) for key in batch_keys]

            try:
                self._s3v.delete_vectors(
                    vectorBucketName=self._bucket,
                    indexName=self._index,
                    keys=point_ids,
                )
                deleted_count += len(batch_keys)
                logger.debug(f"Batch {i // batch_size + 1}: Deleted {len(batch_keys)} items")
            except Exception as e:
                logger.error(f"Failed to delete batch {i // batch_size + 1}: {str(e)}")
                failed_count += len(batch_keys)

        return {
            "deleted_count": deleted_count,
            "failed_count": failed_count,
            "total_found": len(keys),
        }

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


    def get_random_recent_high_importance(
        self,
        user_id: str,
        *,
        include_current_week: bool = True,
        fallback_to_med: bool = True,
        limit: int = None,
    ) -> dict[str, Any] | None:
        """Return one random semantic memory with high importance.

        - Filters by importance >= 1 (high importance)
        - Falls back to any memory if none found (optional)
        """
        if limit is None:
            limit = config.S3V_MAX_TOP_K
        namespace: Namespace = (user_id, "semantic")

        candidates: list[SearchItem] = []

        dummy_query = "memory"
        query_vec = self._embed_texts([dummy_query])[0]

        flt = self._build_filter(namespace, {}, include_is_indexed=False)
        res = self._safe_query_vectors(
            query_vector=query_vec,
            top_k=limit,
            flt=flt,
            return_distance=False,
        )
        vectors = cast(list[dict[str, Any]], res.get("vectors") or [])
        for v in vectors:
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

            importance = value.get("importance", 0)
            if importance >= 1:
                candidates.append(
                    SearchItem(
                        value=value,
                        key=doc_key,
                        namespace=ns_list,
                        created_at=created_at,
                        updated_at=updated_at,
                        score=None,
                    )
                )

        if not candidates and fallback_to_med:
            for v in vectors:
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
                candidates.append(
                    SearchItem(
                        value=value,
                        key=doc_key,
                        namespace=ns_list,
                        created_at=created_at,
                        updated_at=updated_at,
                        score=None,
                    )
                )

        if not candidates:
            return None

        def sort_key(candidate):
            importance_bin = candidate.value.get("importance_bin", "low")
            bin_priority = {"high": 3, "med": 2, "low": 1}.get(importance_bin, 0)
            importance = candidate.value.get("importance", 0)
            created_at = candidate.created_at or "1970-01-01T00:00:00+00:00"  # Fallback for None
            return (bin_priority, importance, created_at)

        candidates.sort(key=sort_key, reverse=True)

        chosen = candidates[0]
        return getattr(chosen, "value", None) or None

    async def aget_random_recent_high_importance(
        self,
        user_id: str,
        *,
        include_current_week: bool = True,
        fallback_to_med: bool = True,
        limit: int = None,
    ) -> dict[str, Any] | None:
        return self.get_random_recent_high_importance(
            user_id,
            include_current_week=include_current_week,
            fallback_to_med=fallback_to_med,
            limit=limit,
        )

    def list_by_namespace(
        self,
        namespace: Namespace,
        *,
        return_metadata: bool = True,
        max_results: int = 500,
        limit: int | None = None,
    ) -> list[SearchItem]:
        """List vectors in a namespace with filtering during pagination.

        Args:
            namespace: Tuple of namespace values to filter by. None values act as
                wildcards matching any value at that position.
            return_metadata: Whether to include metadata in results
            max_results: Maximum results to fetch per page
            limit: Maximum total results to return (None for all)

        Returns:
            List of SearchItems matching the namespace filter

        """
        filtered_items = self._fetch_and_filter_paginated(
            namespace=namespace,
            return_metadata=return_metadata,
            max_results=max_results,
            limit=limit,
        )

        return filtered_items

    def _fetch_and_filter_paginated(
        self,
        namespace: Namespace,
        return_metadata: bool,
        max_results: int,
        limit: int | None = None,
    ) -> list[SearchItem]:
        """Fetch vectors with pagination, filtering by namespace on each page."""
        filtered_items: list[SearchItem] = []
        next_token: str | None = None
        page_count = 0

        while page_count < self.MAX_PAGINATION_PAGES:
            page_count += 1

            response = self._fetch_single_page(return_metadata, max_results, next_token)
            vectors = response.get("vectors", [])

            for vector in vectors:
                if not self._vector_matches_namespace(vector, namespace):
                    continue

                item = self._parse_vector_to_search_item(vector, namespace, return_metadata)
                if item:
                    filtered_items.append(item)
                    if limit and len(filtered_items) >= limit:
                        return filtered_items

            next_token = response.get("nextToken")
            if not next_token:
                break

        if page_count >= self.MAX_PAGINATION_PAGES:
            logger.warning(
                f"Reached max page limit ({self.MAX_PAGINATION_PAGES}). "
                f"Retrieved {len(filtered_items)} matching vectors. Results may be incomplete."
            )

        return filtered_items

    def _fetch_single_page(
        self,
        return_metadata: bool,
        max_results: int,
        next_token: str | None,
    ) -> dict[str, Any]:
        """Fetch a single page of vectors from S3 Vectors API."""
        params = {
            "vectorBucketName": self._bucket,
            "indexName": self._index,
            "maxResults": max_results,
            "returnData": False,
            "returnMetadata": return_metadata,
        }

        if next_token:
            params["nextToken"] = next_token

        try:
            return self._s3v.list_vectors(**params)
        except ClientError as e:
            logger.error(f"S3 Vectors list_vectors failed: {e}")
            raise

    def _vector_matches_namespace(
        self,
        vector: dict[str, Any],
        namespace: Namespace,
    ) -> bool:
        """Check if vector metadata matches all namespace components.

        Args:
            vector: Vector dictionary with metadata
            namespace: Tuple of namespace values to match

        Returns:
            True if vector matches all namespace components

        Note:
            None values in the namespace tuple act as wildcards that match any value
            at that position.

        """
        metadata = vector.get("metadata", {})

        return all(
            val is None or metadata.get(f"ns_{i}") == val
            for i, val in enumerate(namespace)
        )

    def _parse_vector_to_search_item(
        self,
        vector: dict[str, Any],
        namespace: Namespace,
        return_metadata: bool,
    ) -> SearchItem | None:
        """Parse AWS vector response into SearchItem."""
        try:
            value = self._parse_vector_value(vector, return_metadata)
            metadata = vector.get("metadata", {})

            actual_namespace = []
            for i, val in enumerate(namespace):
                if val is None:
                    actual_namespace.append(metadata.get(f"ns_{i}", ""))
                else:
                    actual_namespace.append(val)

            return SearchItem(
                key=metadata.get("doc_key", vector.get("key", "")),
                namespace=actual_namespace,
                value=value,
                score=None,
                created_at=metadata.get("created_at", ""),
                updated_at=metadata.get("updated_at", ""),
            )
        except Exception as e:
            logger.warning(f"Failed to parse vector {vector.get('key')}: {e}")
            return None

    def _parse_vector_value(
        self,
        vector: dict[str, Any],
        return_metadata: bool,
    ) -> dict[str, Any]:
        """Parse value_json from vector metadata."""
        if not return_metadata:
            return {}

        metadata = vector.get("metadata", {})
        value_json = metadata.get("value_json", "")

        if not value_json:
            return {}

        try:
            return json.loads(value_json)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in value_json: {e}")
            return {}

    async def alist_by_namespace(
        self,
        namespace: Namespace,
        *,
        return_metadata: bool = True,
        max_results: int = 500,
        limit: int | None = None,
    ) -> list[SearchItem]:
        """Async version of list_by_namespace."""
        return self.list_by_namespace(
            namespace,
            return_metadata=return_metadata,
            max_results=max_results,
            limit=limit,
        )

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
        attempts: list[Optional[dict[str, Any]]] = []
        attempts.append(flt if flt else None)
        if flt:
            attempts.append({"$and": [{k: v} for k, v in flt.items()]})
            attempts.append({"$and": [{k: {"$eq": v}} for k, v in flt.items()]})
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
                if "Invalid query filter" in message or "ValidationException" in message:
                    last_error = e
                    continue
                raise
        if last_error:
            raise last_error
        return {"vectors": []}

    def _build_filter(
        self,
        namespace_prefix: Namespace,
        user_filter: Optional[dict[str, Any]],
        *,
        include_is_indexed: bool = True,
    ) -> dict[str, Any]:
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
