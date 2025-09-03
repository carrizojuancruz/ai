from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Optional

from app.core.config import config
from app.services.memory.store_factory import create_s3_vectors_store_from_env


def _eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump user memories from S3 Vectors via the Store API")
    parser.add_argument("--user-id", required=True, help="User ID to inspect")
    parser.add_argument("--type", choices=["semantic", "episodic"], default="semantic", help="Memory type")
    parser.add_argument("--category", default=None, help="Optional category filter")
    parser.add_argument("--query", default=None, help="Semantic query to retrieve memories (required by S3 Vectors)")
    parser.add_argument("--limit", type=int, default=20, help="Max items to return")
    parser.add_argument("--offset", type=int, default=0, help="Offset for paging")
    parser.add_argument("--get-key", dest="get_key", default=None, help="If provided, fetch a single memory by key")
    parser.add_argument("--delete-key", dest="delete_key", default=None, help="If provided, delete a single memory by key")
    parser.add_argument("--delete-all", dest="delete_all", action="store_true", help="If provided, delete all memories for the user and type")
    parser.add_argument("--put-file", dest="put_file", default=None, help="Path to JSONL file to bulk insert memories")
    parser.add_argument("--put-summary", dest="put_summary", default=None, help="Summary text for a single insert (semantic)")
    parser.add_argument("--put-category", dest="put_category", default=None, help="Category for insert (e.g., Personal)")
    parser.add_argument("--put-key", dest="put_key", default=None, help="Optional key for single insert")
    args = parser.parse_args()

    # Sanity: ensure env
    missing = config.validate_required_s3_vars()
    if missing:
        _eprint(f"Missing required env vars: {', '.join(missing)}")
        sys.exit(2)

    store = create_s3_vectors_store_from_env()
    namespace = (args.user_id, args.type)

    # Bulk insert from JSONL: each line: {"summary": str, "category": str, "key": str|null}
    if args.put_file:
        import uuid
        path = args.put_file
        ok = 0
        fail = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    summary = str(rec.get("summary") or "").strip()
                    category = rec.get("category")
                    key = rec.get("key") or uuid.uuid4().hex
                    if not summary:
                        raise ValueError("missing summary")
                    value = {
                        "id": key,
                        "user_id": args.user_id,
                        "type": args.type,
                        "summary": summary,
                        "category": category or "Other",
                        "tags": [],
                        "source": "external",
                        "importance": 1,
                        "pinned": False,
                        "created_at": None,
                        "last_accessed": None,
                    }
                    store.put(namespace, key, value, index=["summary"])
                    ok += 1
                except Exception:
                    fail += 1
        print(json.dumps({"ok": True, "inserted": ok, "failed": fail}, ensure_ascii=False, default=str))
        return

    # Single insert
    if args.put_summary:
        import uuid
        key = args.put_key or uuid.uuid4().hex
        value = {
            "id": key,
            "user_id": args.user_id,
            "type": args.type,
            "summary": args.put_summary,
            "category": args.put_category or "Other",
            "tags": [],
            "source": "external",
            "importance": 1,
            "pinned": False,
            "created_at": None,
            "last_accessed": None,
        }
        store.put(namespace, key, value, index=["summary"])
        print(json.dumps({"ok": True, "inserted_key": key}, ensure_ascii=False, default=str))
        return

    if args.delete_key:
        try:
            store.delete((args.user_id, args.type), args.delete_key)
            print(json.dumps({"ok": True, "deleted_key": args.delete_key}, ensure_ascii=False, default=str))
        except Exception as e:
            print(json.dumps({"ok": False, "error": str(e), "key": args.delete_key}, ensure_ascii=False, default=str))
        return

    if args.delete_all:
        try:
            # Search for all memories in batches (S3 Vectors has a limit of 30)
            all_keys = []
            offset = 0
            limit = 30

            # Use a generic query to find all memories
            query = "profile" if args.type == "semantic" else "recent conversation"

            while True:
                items = store.search(namespace, query=query, limit=limit, offset=offset)
                batch_keys = [item.key for item in items]

                if not batch_keys:
                    break

                all_keys.extend(batch_keys)
                offset += limit

                # If we got fewer than the limit, we've reached the end
                if len(batch_keys) < limit:
                    break

            if not all_keys:
                print(json.dumps({"ok": True, "deleted_count": 0, "message": "No memories found to delete"}, ensure_ascii=False, default=str))
                return

            # Delete all memories
            deleted_count = 0
            failed_count = 0

            for key in all_keys:
                try:
                    store.delete(namespace, key)
                    deleted_count += 1
                except Exception:
                    failed_count += 1

            result = {
                "ok": True,
                "deleted_count": deleted_count,
                "failed_count": failed_count,
                "total_found": len(all_keys)
            }
            print(json.dumps(result, ensure_ascii=False, default=str))
        except Exception as e:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False, default=str))
        return

    if args.get_key:
        item = store.get(namespace, args.get_key)
        if not item:
            print(json.dumps({"ok": False, "error": "not_found", "key": args.get_key}))
            return
        out = {
            "key": item.key,
            "namespace": item.namespace,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "value": item.value,
        }
        print(json.dumps(out, ensure_ascii=False, default=str))
        return

    # S3 Vectors requires a semantic query; provide a sensible default if not given
    eff_query: Optional[str] = args.query if args.query else "recent conversation" if args.type == "episodic" else "profile"

    user_filter: Optional[dict[str, Any]] = {"category": args.category} if args.category else None
    items = store.search(namespace, query=eff_query, filter=user_filter, limit=args.limit, offset=args.offset)
    results = []
    for it in items:
        results.append(
            {
                "key": it.key,
                "namespace": it.namespace,
                "created_at": it.created_at,
                "updated_at": it.updated_at,
                "score": it.score,
                "value": it.value,
            }
        )
    print(json.dumps({"ok": True, "count": len(results), "items": results}, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()


