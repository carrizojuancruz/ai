from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

import boto3
from boto3.session import Session

from app.core.config import config
from app.services.memory.store_factory import create_s3_vectors_store_from_env

ENV_PRESETS: dict[str, dict[str, Any]] = {
    "dev": {
        "bucket": "vera-ai-dev-s3-vector",
        "index": "memory-search",
        "region": "us-east-1",
    },
    "uat": {
        "bucket": "vera-ai-uat-s3-vector",
        "index": "memory-search",
        "region": "us-east-1",
    },
}


def _eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


def _verify_namespace(
    namespace: tuple[str, str],
    source_items: Sequence[Any],
    target_store: Any,
    *,
    query: str,
) -> dict[str, Any]:
    """Compare namespace contents between source list and target store without mutating."""
    missing_keys: list[str] = []
    payload_mismatches: list[str] = []

    for item in source_items:
        target_item = target_store.get(namespace, item.key)
        if not target_item:
            missing_keys.append(item.key)
            continue
        if target_item.value != item.value:
            payload_mismatches.append(item.key)

    target_items = target_store.search(namespace, query=query, limit=100) or []
    target_keys = {it.key for it in target_items}
    source_keys = {it.key for it in source_items}
    extra_keys = sorted(target_keys - source_keys)

    return {
        "source_count": len(source_items),
        "target_count": len(target_items),
        "missing_in_target": missing_keys,
        "payload_mismatches": payload_mismatches,
        "extra_in_target": extra_keys,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump user memories from S3 Vectors via the Store API")
    parser.add_argument("--user-id", required=False, help="User ID to inspect (required for most operations, not needed for template operations)")
    parser.add_argument("--type", default="semantic", help="Memory type (e.g., semantic, episodic, supervisor_procedural, finance_contracts)")
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
    parser.add_argument("--seed-templates", dest="seed_templates", action="store_true", help="Seed finance procedural templates into the store")
    parser.add_argument("--list-templates", dest="list_templates", action="store_true", help="List all finance procedural templates in the store")
    parser.add_argument("--list-indexes", dest="list_indexes", action="store_true", help="List all indexes in the specified bucket")
    parser.add_argument("--force", dest="force", action="store_true", help="Force update existing items (overwrites instead of skipping)")
    parser.add_argument("--migrate-procedurals-from-env", dest="migrate_procedurals_from_env", default=None, choices=list(ENV_PRESETS.keys()), help="Copy procedural memories from another environment (requires --env for target)")
    parser.add_argument("--env", dest="env", default=None, choices=list(ENV_PRESETS.keys()), help=f"Environment preset (choices: {', '.join(ENV_PRESETS.keys())}). Sets bucket, index, and region automatically.")
    parser.add_argument("--aws-profile", dest="aws_profile", default=None, help="AWS profile name to use for credentials (from ~/.aws/credentials)")
    parser.add_argument("--source-aws-profile", dest="source_aws_profile", default=None, help="AWS profile to read procedural memories from (defaults to --aws-profile)")
    parser.add_argument("--target-aws-profile", dest="target_aws_profile", default=None, help="AWS profile to write procedural memories to (defaults to --aws-profile)")
    parser.add_argument("--bucket", dest="bucket", default=None, help="Override S3 bucket name (e.g., vera-ai-uat-s3-vector for UAT)")
    parser.add_argument("--index", dest="index", default=None, help="Override index name (e.g., for UAT environment)")
    parser.add_argument("--region", dest="region", default=None, help="Override AWS region (e.g., us-east-1, us-west-2)")
    parser.add_argument("--verify-only", dest="verify_only", action="store_true", help="Compare source and target procedural memories without writing")
    parser.add_argument("--list-all", dest="list_all", action="store_true", help="List all memories using boto3 paginator (bypasses search limit of 100; use with --user-id and --type)")
    args = parser.parse_args()

    # Apply environment preset if specified
    if args.env:
        preset = ENV_PRESETS[args.env]
        if not args.bucket:
            args.bucket = preset["bucket"]
        if not args.index:
            args.index = preset["index"]
        if not args.region:
            args.region = preset["region"]

    # Set AWS profile if specified
    if args.aws_profile:
        os.environ["AWS_PROFILE"] = args.aws_profile

    # List indexes operation doesn't need store, handle it early
    if args.list_indexes:
        bucket_name = args.bucket or config.S3V_BUCKET
        if not bucket_name:
            _eprint("--bucket is required for --list-indexes operation")
            print(json.dumps({"ok": False, "error": "bucket_required"}, ensure_ascii=False, default=str))
            sys.exit(2)

        try:
            region = args.region or config.get_aws_region()
            if not region:
                _eprint("AWS region is required. Set AWS_REGION env var or use --region")
                print(json.dumps({"ok": False, "error": "region_required"}, ensure_ascii=False, default=str))
                sys.exit(2)
            s3v_client = boto3.client("s3vectors", region_name=region)
            response = s3v_client.list_indexes(vectorBucketName=bucket_name)
            indexes = response.get("indexes", [])
            results = []
            for idx in indexes:
                results.append(
                    {
                        "vectorBucketName": idx.get("vectorBucketName"),
                        "indexName": idx.get("indexName"),
                        "indexArn": idx.get("indexArn"),
                        "creationTime": idx.get("creationTime"),
                    }
                )
            _eprint(f"Found {len(results)} indexes in bucket '{bucket_name}'")
            print(json.dumps({"ok": True, "bucket": bucket_name, "count": len(results), "indexes": results}, ensure_ascii=False, default=str))
        except Exception as exc:
            _eprint(f"Error listing indexes: {exc}")
            print(json.dumps({"ok": False, "error": str(exc), "bucket": bucket_name}, ensure_ascii=False, default=str))
        return

    # Migration: copy procedural memories from one env to another
    if args.migrate_procedurals_from_env:
        if not args.env:
            _eprint("--env is required when using --migrate-procedurals-from-env (specifies target environment)")
            print(json.dumps({"ok": False, "error": "env_required_for_migration"}, ensure_ascii=False, default=str))
            sys.exit(2)

        source_preset = ENV_PRESETS[args.migrate_procedurals_from_env]
        target_preset = ENV_PRESETS[args.env]

        def _build_session(profile_name: Optional[str]) -> Optional[Session]:
            if not profile_name:
                return None
            try:
                return Session(profile_name=profile_name)
            except Exception as exc:  # pragma: no cover - boto specific
                _eprint(f"Failed to load AWS profile '{profile_name}': {exc}")
                sys.exit(2)

        source_profile = args.source_aws_profile or args.aws_profile
        target_profile = args.target_aws_profile or args.aws_profile

        source_session = _build_session(source_profile)
        target_session = _build_session(target_profile)

        try:
            source_store = create_s3_vectors_store_from_env(
                bucket_name=source_preset["bucket"],
                index_name=source_preset["index"],
                region_name=source_preset["region"],
                session=source_session,
            )
            target_store = create_s3_vectors_store_from_env(
                bucket_name=target_preset["bucket"],
                index_name=target_preset["index"],
                region_name=target_preset["region"],
                session=target_session,
            )

            finance_ns = ("system", "finance_procedural_templates")
            supervisor_ns = ("system", "supervisor_procedural")
            finance_items = source_store.search(finance_ns, query="finance sql patterns", limit=100)
            supervisor_items = source_store.search(supervisor_ns, query="routing", limit=100)

            if args.verify_only:
                finance_verification = _verify_namespace(
                    finance_ns,
                    finance_items,
                    target_store,
                    query="finance sql patterns",
                )
                supervisor_verification = _verify_namespace(
                    supervisor_ns,
                    supervisor_items,
                    target_store,
                    query="routing",
                )
                verification_result = {
                    "ok": True,
                    "mode": "verify_only",
                    "source_env": args.migrate_procedurals_from_env,
                    "target_env": args.env,
                    "finance": finance_verification,
                    "supervisor": supervisor_verification,
                }
                print(json.dumps(verification_result, ensure_ascii=False, default=str))
                return

            finance_migrated = 0
            finance_skipped = 0
            for item in finance_items:
                template_id = item.key
                if not args.force and target_store.get(finance_ns, template_id):
                    finance_skipped += 1
                    _eprint(f"Finance template '{template_id}' already exists in target; skipping (use --force to overwrite)")
                    continue
                target_store.put(finance_ns, template_id, item.value, index=["name", "description", "tags"])
                finance_migrated += 1
                _eprint(f"Migrated finance template '{template_id}'")

            supervisor_migrated = 0
            supervisor_skipped = 0
            for item in supervisor_items:
                routing_key = item.key
                if not args.force and target_store.get(supervisor_ns, routing_key):
                    supervisor_skipped += 1
                    _eprint(f"Routing example '{routing_key}' already exists in target; skipping (use --force to overwrite)")
                    continue
                target_store.put(supervisor_ns, routing_key, item.value, index=["summary"])
                supervisor_migrated += 1
                _eprint(f"Migrated routing example '{routing_key}'")

            result = {
                "ok": True,
                "source_env": args.migrate_procedurals_from_env,
                "target_env": args.env,
                "finance": {"migrated": finance_migrated, "skipped": finance_skipped},
                "supervisor": {"migrated": supervisor_migrated, "skipped": supervisor_skipped},
            }
            print(json.dumps(result, ensure_ascii=False, default=str))
        except Exception as exc:
            _eprint(f"Migration failed: {exc}")
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, default=str))
        return

    # Sanity: ensure env (only if bucket/index not overridden)
    if not args.bucket and not args.index:
        missing = config.validate_required_s3_vars()
        if missing:
            _eprint(f"Missing required env vars: {', '.join(missing)}")
            sys.exit(2)

    store = create_s3_vectors_store_from_env(bucket_name=args.bucket, index_name=args.index, region_name=args.region)
    template_namespace = ("system", "finance_procedural_templates")

    if args.seed_templates:
        templates_file = Path(__file__).resolve().parents[2] / "finance_procedural_templates.jsonl"
        if not templates_file.exists():
            message = f"Templates file not found: {templates_file}"
            _eprint(message)
            print(json.dumps({"ok": False, "error": "templates_file_missing", "message": message}, ensure_ascii=False, default=str))
            return

        seeded_count = 0
        with templates_file.open("r", encoding="utf-8") as f:
            for line_num, raw_line in enumerate(f, 1):
                line = raw_line.strip()
                if not line:
                    continue

                try:
                    template_data = json.loads(line)
                except json.JSONDecodeError as exc:
                    _eprint(f"Failed to parse template on line {line_num}: {exc}")
                    _eprint(f"Line content: {line[:100]}...")
                    continue

                template_id = template_data.get("id")
                if not template_id:
                    _eprint(f"Template on line {line_num} is missing 'id'; skipping")
                    continue

                try:
                    existing_item = store.get(template_namespace, template_id)
                    is_update = existing_item is not None

                    if existing_item and not args.force:
                        _eprint(f"Template '{template_id}' already exists; skipping (use --force to update)")
                        continue

                    store.put(
                        template_namespace,
                        template_id,
                        template_data,
                        index=["name", "description", "tags"],
                    )
                    seeded_count += 1
                    action = "Updated" if is_update else "Seeded"
                    _eprint(f"{action} template '{template_id}'")
                except Exception as exc:  # pragma: no cover - operational logging
                    _eprint(f"Failed to seed template '{template_id}': {exc}")
                    continue

        print(json.dumps({"ok": True, "seeded_templates": seeded_count, "force": args.force}, ensure_ascii=False, default=str))
        return

    if args.list_templates:
        try:
            items = store.search(template_namespace, query="finance sql patterns", limit=100)
            results = []
            for item in items:
                results.append(
                    {
                        "key": item.key,
                        "namespace": item.namespace,
                        "created_at": item.created_at,
                        "updated_at": item.updated_at,
                        "score": item.score,
                        "value": item.value,
                    }
                )
            _eprint(f"Found {len(results)} finance procedural templates")
            print(json.dumps({"ok": True, "count": len(results), "templates": results}, ensure_ascii=False, default=str))
        except Exception as exc:
            _eprint(f"Error listing templates: {exc}")
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, default=str))
        return

    if not args.user_id:
        _eprint("--user-id is required for this operation")
        sys.exit(2)

    namespace = (args.user_id, args.type)

    # Bulk insert from JSONL: each line: {"summary": str, "category": str, "key": str|null}
    if args.put_file:
        import uuid
        path = args.put_file
        ok = 0
        updated = 0
        skipped = 0
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

                    existing_item = store.get(namespace, key)
                    is_update = existing_item is not None

                    if existing_item and not args.force:
                        skipped += 1
                        _eprint(f"Memory '{key}' already exists; skipping (use --force to update)")
                        continue

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
                    if is_update:
                        updated += 1
                    else:
                        ok += 1
                except Exception:
                    fail += 1
        print(json.dumps({"ok": True, "inserted": ok, "updated": updated, "skipped": skipped, "failed": fail}, ensure_ascii=False, default=str))
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
            items = store.list_by_namespace(
                namespace,
                return_metadata=True,
                max_results=1000,
                limit=None,
            )

            all_keys = [item.key for item in items]

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

    if args.list_all:
        if not args.user_id:
            _eprint("--user-id is required for --list-all operation")
            sys.exit(2)

        try:
            # Use boto3 paginator directly (recommended approach) - bypasses store layer
            s3v_client = store._s3v
            bucket_name = store._bucket
            index_name = store._index

            # For --list-all, ignore default limit of 20 - only apply if user explicitly sets a higher limit
            effective_limit = None if args.limit == 20 else args.limit

            all_items = []
            paginator = s3v_client.get_paginator("list_vectors")
            page_iterator = paginator.paginate(
                vectorBucketName=bucket_name,
                indexName=index_name,
                returnMetadata=True,
                returnData=False,
                PaginationConfig={"PageSize": 1000},
            )

            for page in page_iterator:
                for vector in page.get("vectors", []):
                    # Filter by namespace
                    metadata = vector.get("metadata", {})
                    ns0 = metadata.get("ns_0", "")
                    ns1 = metadata.get("ns_1", "")

                    # Match namespace
                    if namespace[0] != ns0 or namespace[1] != ns1:
                        continue

                    # Parse vector value
                    try:
                        value_json = metadata.get("value_json", "")
                        value = json.loads(value_json) if value_json else {}
                    except json.JSONDecodeError:
                        value = {}

                    # Apply category filter if specified
                    if args.category and value.get("category") != args.category:
                        continue

                    all_items.append(
                        {
                            "key": metadata.get("doc_key", vector.get("key", "")),
                            "namespace": [ns0, ns1],
                            "created_at": metadata.get("created_at", ""),
                            "updated_at": metadata.get("updated_at", metadata.get("created_at", "")),
                            "score": None,
                            "value": value,
                        }
                    )

                    # Apply limit only if explicitly set (not default)
                    if effective_limit and effective_limit > 0 and len(all_items) >= effective_limit:
                        break

                # Break outer loop if limit reached
                if effective_limit and effective_limit > 0 and len(all_items) >= effective_limit:
                    break

            print(json.dumps({"ok": True, "count": len(all_items), "items": all_items}, ensure_ascii=False, default=str))
        except Exception as e:
            _eprint(f"Error listing all memories: {e}")
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False, default=str))
        return

    # S3 Vectors requires a semantic query; provide a sensible default if not given
    if args.query:
        eff_query: Optional[str] = args.query
    else:
        if args.type == "episodic":
            eff_query = "recent conversation"
        elif "procedural" in str(args.type or ""):
            eff_query = "routing"
        else:
            eff_query = "profile"

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


