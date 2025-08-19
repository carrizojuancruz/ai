from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Optional

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
    args = parser.parse_args()

    # Sanity: ensure env
    missing = [name for name in ("S3V_BUCKET", "S3V_INDEX", "AWS_REGION") if not os.getenv(name)]
    if missing:
        _eprint(f"Missing required env vars: {', '.join(missing)}")
        sys.exit(2)

    store = create_s3_vectors_store_from_env()
    namespace = (args.user_id, args.type)

    if args.delete_key:
        try:
            store.delete((args.user_id, args.type), args.delete_key)
            print(json.dumps({"ok": True, "deleted_key": args.delete_key}, ensure_ascii=False, default=str))
        except Exception as e:
            print(json.dumps({"ok": False, "error": str(e), "key": args.delete_key}, ensure_ascii=False, default=str))
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
    eff_query: Optional[str]
    if args.query:
        eff_query = args.query
    else:
        eff_query = "recent conversation" if args.type == "episodic" else "profile"

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


