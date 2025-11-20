## Memory Dump CLI

Utility for inspecting and managing user memories stored in Amazon S3 Vectors.

### Quick Start

```bash
docker compose exec app poetry run python -m app.scripts.dump_memories --help
```

**Pretty-print JSON** (PowerShell): `| ConvertFrom-Json | ConvertTo-Json -Depth 100`  
**Pretty-print JSON** (bash): `| jq .`

### Common Flags

- `--user-id <UUID|STRING>`: Required for most operations. Use `"system"` for procedural memories:
  - Supervisor routing: `--user-id system --type supervisor_procedural`
  - Finance hints: Use `--seed-templates` or `--list-templates` (uses `"system"` internally)
- `--type <TYPE>`: Memory type. Options: `semantic`, `episodic`, `supervisor_procedural`, `finance_procedural_templates`. Default: `semantic`
- `--query "..."`: Semantic query text (required for searches)
- `--limit <N>` / `--offset <N>`: Pagination
- `--env <ENV>`: Environment preset (`dev` or `uat`). Sets bucket, index, and region automatically
- `--aws-profile <PROFILE>`: AWS profile from `~/.aws/credentials` for authentication
- `--source-aws-profile <PROFILE>` / `--target-aws-profile <PROFILE>`: Override AWS profiles for migration source/target (defaults to `--aws-profile`)
- `--force`: Force update existing items (overwrites instead of skipping)
- `--migrate-procedurals-from-env <ENV>`: Copy procedural memories from another environment (requires `--env` for target)
- `--verify-only`: Run migration comparisons without writing (requires `--migrate-procedurals-from-env`)
- `--bucket`, `--index`, `--region`: Override bucket/index/region (usually not needed with `--env`)

**CRUD Operations:**
- `--get-key <KEY>`: Fetch single memory
- `--delete-key <KEY>`: Delete single memory
- `--delete-all`: Delete all memories for user/type (⚠️ destructive)
- `--put-summary <TEXT>`: Create single memory
- `--put-file <PATH>`: Bulk insert from JSONL file

**System Procedural Memories:**
- `--seed-templates`: Seed finance SQL hints (`("system", "finance_procedural_templates")`)
- `--list-templates`: List finance SQL hints
- `--list-indexes`: List all indexes in bucket

### Examples

#### Search Memories

```bash
# Semantic search
docker compose exec app poetry run python -m app.scripts.dump_memories \
  --user-id <USER_ID> --type semantic --query "profile" --limit 10

# With category filter
docker compose exec app poetry run python -m app.scripts.dump_memories \
  --user-id <USER_ID> --type semantic --category Personal --query "name" --limit 5

# Episodic search
docker compose exec app poetry run python -m app.scripts.dump_memories \
  --user-id <USER_ID> --type episodic --query "recent" --limit 5
```

#### CRUD Operations

```bash
# Get single memory
docker compose exec app poetry run python -m app.scripts.dump_memories \
  --user-id <USER_ID> --type semantic --get-key <KEY>

# Create memory
docker compose exec app poetry run python -m app.scripts.dump_memories \
  --user-id <USER_ID> --type semantic --put-summary "User likes sushi." --put-category Personal

# Delete memory
docker compose exec app poetry run python -m app.scripts.dump_memories \
  --user-id <USER_ID> --type semantic --delete-key <KEY>

# Bulk insert from JSONL (format: {"summary": "...", "category": "...", "key": "..."})
docker compose exec app poetry run python -m app.scripts.dump_memories \
  --user-id <USER_ID> --type semantic --put-file /app/data/memories.jsonl
```

#### System Procedural Memories

```bash
# Finance SQL hints (uses default env from container)
docker compose exec app poetry run python -m app.scripts.dump_memories --seed-templates
docker compose exec app poetry run python -m app.scripts.dump_memories --list-templates

# Update existing templates (use --force to overwrite)
docker compose exec app poetry run python -m app.scripts.dump_memories \
  --env uat --aws-profile vera-uat --seed-templates --force

# Supervisor routing examples
docker compose exec app poetry run python -m app.scripts.dump_memories \
  --user-id system --type supervisor_procedural \
  --put-file "/app/app/scripts/procedural memory examples/supervisor_routing_examples.jsonl"

# Update existing routing examples
docker compose exec app poetry run python -m app.scripts.dump_memories \
  --env uat --aws-profile vera-uat --force \
  --user-id system --type supervisor_procedural \
  --put-file "/app/app/scripts/procedural memory examples/supervisor_routing_examples.jsonl"
```

#### Migrate Between Environments

Copy procedural memories from one environment to another (safe for production):

```bash
# Copy from UAT to dev
docker compose exec app poetry run python -m app.scripts.dump_memories \
  --migrate-procedurals-from-env uat --env dev --source-aws-profile vera-uat --target-aws-profile vera-dev

# Copy from dev to UAT (with force to overwrite)
docker compose exec app poetry run python -m app.scripts.dump_memories \
  --migrate-procedurals-from-env dev --env uat --source-aws-profile vera-dev --target-aws-profile vera-uat --force

# Verify differences only (no writes)
docker compose exec app poetry run python -m app.scripts.dump_memories \
  --migrate-procedurals-from-env dev --env uat \
  --source-aws-profile vera-dev --target-aws-profile vera-uat \
  --verify-only
```

**Note**: Migration copies both finance SQL hints and supervisor routing examples. Use `--force` to overwrite existing items in the target environment.

#### Environment Switching

```bash
# Use UAT environment with AWS profile
docker compose exec app poetry run python -m app.scripts.dump_memories \
  --env uat --aws-profile vera-uat \
  --user-id <USER_ID> --type semantic --query "profile" --limit 10

# List indexes in UAT
docker compose exec app poetry run python -m app.scripts.dump_memories \
  --env uat --aws-profile vera-uat --list-indexes
```

**Environment Presets:**
- `--env dev`: Bucket `vera-ai-dev-s3-vector`, Index `memory-search`, Region `us-east-1`
- `--env uat`: Bucket `vera-ai-uat-s3-vector`, Index `memory-search`, Region `us-east-1`

**AWS Profile Setup** (`~/.aws/credentials`):
```ini
[vera-uat]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY
region = us-east-1
```

### Notes

- Namespace structure: `(user_id, type)` where:
  - `user_id` = ns_0 (use `"system"` for procedural memories)
  - `type` = ns_1 (e.g., `semantic`, `episodic`, `supervisor_procedural`, `finance_procedural_templates`)
- Output is JSON. Use `jq` (bash) or `ConvertFrom-Json | ConvertTo-Json` (PowerShell) for pretty printing
- `--delete-all` returns: `deleted_count`, `failed_count`, `total_found`
