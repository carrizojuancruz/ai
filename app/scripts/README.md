## Memory Dump CLI

Utility for inspecting and managing user memories stored in Amazon S3 Vectors via the `S3VectorsStore`.

### Prerequisites

- The app must run inside Docker Compose and use Poetry (as in this repo).
- AWS credentials and required env vars available to the running container:
  - `AWS_REGION` (or `AWS_DEFAULT_REGION`)
  - `S3V_BUCKET`
  - `S3V_INDEX`

### Basic usage

Run all commands through Poetry inside the container:

```bash
docker compose exec app poetry run python -m app.scripts.dump_memories --help
```

On Windows/PowerShell, to pretty-print JSON outputs:

```powershell
docker compose exec app poetry run python -m app.scripts.dump_memories --help | ConvertFrom-Json | ConvertTo-Json -Depth 100
```

Common flags:

- `--user-id <UUID|STRING>`: Required. The user namespace (ns_0).
- `--type semantic|episodic`: Memory type (ns_1). Default: `semantic`.
- `--query "..."`: Semantic query text (required for searches).
- `--category <Category>`: Optional category filter (e.g., `Finance`, `Personal`).
- `--limit <N>` / `--offset <N>`: Paging.
- `--get-key <KEY>`: Fetch a single memory by key.
- `--delete-key <KEY>`: Delete a single memory by key.

### Examples

#### 1) Semantic search (top 10)

```bash
docker compose exec app poetry run python -m app.scripts.dump_memories \
  --user-id <USER_ID> \
  --type semantic \
  --query "profile" \
  --limit 10
```

PowerShell pretty-print:

```powershell
docker compose exec app poetry run python -m app.scripts.dump_memories `
  --user-id <USER_ID> `
  --type semantic `
  --query "profile" `
  --limit 10 |
  ConvertFrom-Json | ConvertTo-Json -Depth 100
```

#### 2) Semantic search filtered by category

```bash
docker compose exec app poetry run python -m app.scripts.dump_memories \
  --user-id <USER_ID> \
  --type semantic \
  --category Personal \
  --query "name" \
  --limit 5
```

PowerShell pretty-print:

```powershell
docker compose exec app poetry run python -m app.scripts.dump_memories `
  --user-id <USER_ID> `
  --type semantic `
  --category Personal `
  --query "name" `
  --limit 5 |
  ConvertFrom-Json | ConvertTo-Json -Depth 100
```

#### 3) Episodic search

```bash
docker compose exec app poetry run python -m app.scripts.dump_memories \
  --user-id <USER_ID> \
  --type episodic \
  --query "recent" \
  --limit 5
```

PowerShell pretty-print:

```powershell
docker compose exec app poetry run python -m app.scripts.dump_memories `
  --user-id <USER_ID> `
  --type episodic `
  --query "recent" `
  --limit 5 |
  ConvertFrom-Json | ConvertTo-Json -Depth 100
```

#### 4) Get a single memory by key

```bash
docker compose exec app poetry run python -m app.scripts.dump_memories \
  --user-id <USER_ID> \
  --type semantic \
  --get-key <KEY>
```

PowerShell pretty-print:

```powershell
docker compose exec app poetry run python -m app.scripts.dump_memories `
  --user-id <USER_ID> `
  --type semantic `
  --get-key <KEY> |
  ConvertFrom-Json | ConvertTo-Json -Depth 100
```

#### 5) Delete a memory by key

```bash
docker compose exec app poetry run python -m app.scripts.dump_memories \
  --user-id <USER_ID> \
  --type semantic \
  --delete-key <KEY>
```

PowerShell pretty-print:

```powershell
docker compose exec app poetry run python -m app.scripts.dump_memories `
  --user-id <USER_ID> `
  --type semantic `
  --delete-key <KEY> |
  ConvertFrom-Json | ConvertTo-Json -Depth 100
```

### Notes

- The tool prints strict JSON to stdout. If you need pretty output:

  - PowerShell:

  ```powershell
  docker compose exec app poetry run python -m app.scripts.dump_memories `
    --user-id <USER_ID> ` --type semantic ` --query "profile" ` --limit 5 |
    ConvertFrom-Json | ConvertTo-Json -Depth 100
  ```

  - bash with `jq`:

  ```bash
  docker compose exec app poetry run python -m app.scripts.dump_memories \
    --user-id <USER_ID> --type semantic --query "profile" --limit 5 | jq .
  ```

- The `user-id` and `type` together form the memory namespace.
- The store uses `value_json` as non-filterable metadata in S3 Vectors and keeps filterable fields like `ns_0`, `ns_1`, `category`, `doc_key`, and `is_indexed` for querying.


