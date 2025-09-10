## S3 Vectors Memory Implementation Plan (V1)

### Programmer overview: how the memory system works

At a glance, the system captures user memories (facts and recent events), deduplicates them, and retrieves them to personalize responses. It is built with small, focused parts so each concern stays simple and testable.

- What it stores
  - Short summaries of user facts (semantic) and recent events (episodic), each tagged with a category (e.g., Personal, Finance).
  - Data is kept compact; only the summary is embedded for search.

- Where it lives
  - A single Amazon S3 Vectors index stores all users’ vectors. We use Bedrock Titan embeddings so search is semantic.
  - Each memory belongs to a namespace: (user_id, type). We filter every query by namespace and optional category.

- How a memory is created (hot path)
  - Before the main agent runs, a tiny LLM (Nova Micro) quickly decides: should we create a memory from the last user turns? It also proposes type, category, and a 1–2 sentence summary.
  - We immediately emit an SSE event (memory.candidate) so the UI can reflect that “a memory was captured” without waiting.
  - In the background, we search neighbors in the same namespace in high vector space. If a close match exists, we update it; otherwise we create a new one. This is non-blocking for the main flow.

- How dedup works
  - We measure semantic similarity to existing memories. If similarity is high, we auto-update; if it’s borderline, we ask the tiny LLM a second question “is this the same fact?” and update only if yes; otherwise we create a new one.

- How retrieval works
  - A small context node runs before the supervisor and pulls a few relevant memories via semantic search (filtered to the user and type). It feeds a short, human-readable context message into the conversation.

- Why these choices
  - Small nodes → predictable and cheap; easy to test and reason about.
  - Nova Micro for quick decisions → keeps latency low while improving quality over heuristics.
  - S3 Vectors + Titan → managed, scalable search with minimal moving parts.
  - SSE events → immediate feedback to the user without slowing the main agent.

### Objective
Implement a LangGraph `BaseStore` backend using Amazon S3 Vectors (preview) with first-class Bedrock Titan embeddings, aligned to the V1 memory specification. Provide semantic search and CRUD for user memories, filtered by `user_id`, `type` (semantic|episodic), and `category`.

### Target stack and resources
- **AWS Region**: `us-east-1`
- **S3 Vectors bucket**: `vera-ai-dev-s3-vector`
- **S3 Vectors index**: `memory-search`
- **Distance metric**: Cosine
- **Dimensions**: 1024
- **Embedding model**: Bedrock Titan Text Embeddings V2 (`amazon.titan-embed-text-v2:0`)

### Dependencies and configuration
- Add runtime dependency: `boto3`
- Environment variables:
  - `AWS_REGION=us-east-1`
  - `S3V_BUCKET=vera-ai-dev-s3-vector`
  - `S3V_INDEX_MEMORY=memory-search`
  - `S3V_DISTANCE=cosine`
  - `BEDROCK_EMBED_MODEL_ID=amazon.titan-embed-text-v2:0`
- Credentials: standard AWS credentials (env/profile/role) available to the runtime containers

### Files to add/update
- Add: `verde-ai/app/repositories/s3_vectors_store.py`
- Add: `verde-ai/app/agents/supervisor/memory_tools.py` — tools using the V1 schema
- Add: `verde-ai/app/services/memory/store_factory.py` — factory to instantiate the store from env
- Add: `verde-ai/app/agents/supervisor/memory_nodes.py` — hot-path and context nodes
- Add: `verde-ai/app/scripts/dump_memories.py` — CLI utility (search/get/delete)
- Update: `pyproject.toml` to include `boto3`
- Integration: store is wired during supervisor graph compile

### Data model and namespacing
- Use a single S3 Vectors index across all users
- Represent namespaces with two parts via metadata (and redundant fields for convenient filter syntax):
  - `ns_0 = user_id`
  - `ns_1 = type` where `type ∈ {"semantic", "episodic"}`
  - Additional metadata for convenience and filters: `user_id`, `type`, `category`
  - Also store: `namespace=[ns_0, ns_1]`, `ns_depth=2`
- Deterministic keying for physical vectors:
  - Physical S3 Vectors `key = uuid5(NAMESPACE_URL, f"{ns_0}|{ns_1}::{doc_key}")`
  - Persist the logical key as metadata `doc_key`

### V1 memory value schema (stored as metadata)
- Fields prioritized by the V1 spec (compact, index `summary` only):
  - `id: uuid` (use `doc_key`)
  - `user_id: uuid`
  - `type: "semantic"|"episodic"`
  - `summary: string` (1–2 sentences)
  - `tags: list[str]` (serialized for metadata)
  - `source: "chat"|"external"`
  - `importance: int` (1..5)
  - `pinned: bool`
  - `created_at: ISO8601`
  - `last_accessed: ISO8601`
- System metadata:
  - `is_indexed: bool`, `updated_at: ISO8601`, `namespace`, `ns_depth`, `ns_0`, `ns_1`, `doc_key`
- Storage policy (current implementation):
  - The full memory document is serialized into a single non-filterable string field `value_json` to stay within metadata key limits.
  - Minimal flattened (filterable) keys: `doc_key`, `created_at`, `updated_at`, `is_indexed`, `ns_0`, `ns_1`, optional `category`.
  - Configure `value_json` as non-filterable at index creation; keep the others filterable.
- Indexing policy:
  - Default `index=["summary"]` (embed only `summary` from `value`)

### Store class design
- Location: `verde-ai/app/repositories/s3_vectors_store.py`
- Class: `S3VectorsStore(BaseStore)`
- Constructor signature:
  - `s3v_client: boto3.client("s3vectors", region_name=...)`
  - `bedrock_client: boto3.client("bedrock-runtime", region_name=...)`
  - `vector_bucket_name: str`
  - `index_name: str`
  - `dims: int` (1024)
  - `model_id: str` (`amazon.titan-embed-text-v2:0`)
  - `distance: Literal["COSINE", "EUCLIDEAN"] = "COSINE"`
  - `default_index_fields: list[str] = ["summary"]`
  - `supports_ttl: bool = False`

#### Helper functions (current implementation)
- `_utc_now_iso() -> str`
- `_join_namespace(ns: tuple[str, ...]) -> str`
- `_compose_point_uuid(ns: tuple[str, ...], key: str) -> UUID`
- `_zero_vector() -> list[float]` (length=`dims`)
- `_extract_by_field_paths(value: dict, field_paths: list[str]) -> list[str]` (search source is the `value` document)
- `_build_filter(namespace_prefix: tuple[str, ...], user_filter: dict | None) -> dict` → equality-shorthand JSON filter, e.g. `{ "ns_0": "<user_id>", "ns_1": "semantic", "is_indexed": true, "category": "Personal" }`.
- `_embed_texts(texts: list[str]) -> list[list[float]]` → Bedrock Titan embeddings

#### API methods (current implementation)
- `batch(ops)` / `abatch(ops)`
  - Route ops like the spike: `get`, `search`, `put`, `delete`, `list_namespaces`

- `put(namespace: tuple[str, ...], key: str, value: dict, index: Literal[False]|list[str]|None = None, *, ttl=NOT_PROVIDED) -> None`
  - Compute `point_id = uuid5(ns|key)`
  - Timestamps:
    - Preserve `created_at` if exists; else now
    - Set `updated_at = now`
  - Determine fields to index:
    - `index is None` → use `default_index_fields` (`["summary"]`)
    - `index is False` → no embedding, store zero vector
    - else → use provided list
  - Build embedding (from the `value` document):
    - Extract texts with `_extract_by_field_paths(value, fields)`, join with `\n`, embed via Bedrock Titan; if empty, use zero vector
  - Build metadata:
    - Include (MANDATORY): `value`, `doc_key=key`, `namespace`, `ns_depth`, `ns_0`, `ns_1`, `created_at`, `updated_at`, `is_indexed`
    - Flatten key value fields for filters: `user_id`, `type`, `category`, `summary`, `tags` (serialized), `source`, `importance`, `pinned`, `last_accessed`
  - Write with `s3vectors.put_vectors(vectorBucketName, indexName, vectors=[{ key: point_id, data: {float32: vector}, metadata: {...}}])`

- `get(namespace: tuple[str, ...], key: str, *, refresh_ttl: bool | None = None) -> Item | None`
  - Preferred: if S3 Vectors supports direct fetch-by-key (e.g., `get_vectors(keys=[...])`), use it
  - Fallback: `query_vectors` with a dummy zero vector and strict filter on `ns_0`, `ns_1`, and `doc_key`, `topK=1`
  - Build `Item` from `metadata["value"]`; timestamps from `created_at`/`updated_at`

- `search(namespace_prefix: tuple[str, ...], *, query: str | None, filter: dict | None, limit: int = 10, offset: int = 0, refresh_ttl: bool | None = None) -> list[SearchItem]`
  - Only semantic search is supported (per scope).
  - If `query` is falsy → return `[]`.
  - Else embed the query via Titan and call `query_vectors` with a filter that includes `ns_0`, `ns_1`, `is_indexed=true`, and optional user filters (e.g., `category`).
  - S3 Vectors returns a distance; the implementation converts this to a similarity score in [0,1] (cosine: `1 - distance`) before applying thresholds.
  - Results are sliced to emulate `offset`; `value` is reconstructed from `value_json`.

- `delete(namespace: tuple[str, ...], key: str) -> None`
  - Compute `point_id` via deterministic UUID and call `s3vectors.delete_vectors(keys=[point_id])`

- `list_namespaces(...) -> list[tuple[str, ...]]`
  - Not required for product scope; return `[]`

- Async variants (`aget`, `asearch`, `aput`, `adelete`, `alist_namespaces`) delegate to sync implementations

### Filters and metadata (current implementation)
- Mandatory filters on all searches: `ns_0`, `ns_1`, and `is_indexed=true`; optional: `category`.
- The store retries alternate filter shapes (`{"$and": [...]}`) on validation errors and finally without a filter for debugging.
- Minimal flattened filterable keys; full document lives in `value_json` (non-filterable).

### LangGraph tools (summary-first)
- Location: `verde-ai/app/agents/supervisor/memory_tools.py`
- Category normalization: `[Finance, Budget, Goals, Personal, Education, Conversation_Summary, Other]` → TitleCase with underscores; default to `Other`
- Tools:
  - `semantic_memory_search(topic: Optional[str], query: Optional[str], limit: int, config) -> list[dict]`
    - Namespace `(user_id, "semantic")`
    - Filter by `category` (if provided) + `user_id` + `type="semantic"`
    - If `query` empty → return `[]` (semantic-only)
  - `episodic_memory_fetch(topic: Optional[str], limit: int, config) -> list[dict]`
    - Namespace `(user_id, "episodic")`
    - Use last user message as query if available; otherwise return `[]` (semantic-only scope)
  - `semantic_memory_put(summary: str, category: Optional[str], key: Optional[str], config) -> dict`
    - Normalize `category`; key = provided or UUID4; `put` with `index=["summary"]`
  - `episodic_memory_put(summary: str, category: Optional[str], key: Optional[str], config) -> dict`
    - Same, with `type="episodic"`
  - `semantic_memory_update(key: str, summary: Optional[str], category: Optional[str], config) -> dict`
    - `get` → mutate fields → `put` (re-embed if `summary` changed)
  - `episodic_memory_update(...)` analogous

### Subagents (future) and category routing
- V1: category-only filtering. Keep categories coarse and aligned with future subagent domains: `Finance`, `Budget`, `Coach` (Wealth), `Personal`, etc.
- Future: may add filterable metadata keys `agent` (e.g., finance|budget|coach) and `status` (current|superseded) to refine routing and ranking while staying within metadata key limits.

Retrieval budgets and reranking (applies now; subagents can reuse later):
- Query by `(ns_0, ns_1)` plus `category=<Domain>`, `topK=24` (env-tunable).
- Rerank locally and trim to `N=5` using a composite score:
  - `score_final = 0.55*similarity + 0.20*norm_importance + 0.15*recency_decay + 0.10*(pinned?1:0)`
- Supervisor keeps a smaller budget (e.g., 3 bullets) using merged/summarized items.

### Wiring into the app
- Store creation during graph compile or app init:
  - Instantiate `boto3` clients:
    - `s3v = boto3.client("s3vectors", region_name=AWS_REGION)`
    - `bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)`
  - Create store: `S3VectorsStore(s3v, bedrock, S3V_BUCKET, S3V_INDEX_MEMORY, dims=1024, model_id=BEDROCK_EMBED_MODEL_ID)`
  - Provide to `graph.compile(..., store=store)` or app-level DI
- Always pass `config.configurable.user_id` in LangGraph runs to enable proper filtering

### CRUD guarantees
- Create/Update: upsert by deterministic key; re-embed when `summary` changes
- Read (get): by `(user_id, type, key)` using direct get if available, else filtered query
- Delete: by deterministic key
- Search: semantic-only, filtered by `user_id`, `type`, and optional `category`

### Error handling and robustness
- Validate dims (1024) and distance (Cosine) during init
- Catch and wrap AWS client errors with actionable messages
- Enforce `summary` presence for indexed writes; allow `index=False` for non-indexed system records
- Log Bedrock timeouts and fallback to zero-vector (with `is_indexed=false`) only if explicitly requested; otherwise fail fast

### Testing strategy
- Unit tests (mocked `s3vectors` and `bedrock-runtime`):
  - `put` (indexed and non-indexed) → metadata shape, embedding call, deterministic key
  - `get` happy-path (direct get if mocked) and fallback via filtered query
  - `search` with filters and offset emulation
  - `delete` by deterministic key
  - Filter composition correctness: `{user_id, type, category}`
- Integration smoke (optional, env-gated):
  - Requires real AWS credentials and the configured index

### Known limitations (V1)
- No non-semantic listing/scrolling; `search(query=None)` returns `[]`
- `list_namespaces` not implemented (returns empty)
- Metadata size limits apply; avoid large payloads; keep `summary` concise

### Observability, performance, and security
- Metrics: record Bedrock latency, S3 Vectors latency, error rates, and topK sizes; surface via logs/metrics
- Tracing: annotate graph runs with memory-search spans (query text truncated, counts only — no PII)
- Idempotency: deterministic keys ensure `put` is idempotent per `(namespace, key)`
- IAM: least-privilege policies for `s3vectors:*` on the specific bucket/index and `bedrock:InvokeModel` on the Titan model; consider KMS if/when using SSE-KMS
- Throughput: single-vector writes are fine; batch up to small groups (≤16) if needed; scale horizontally via containers

### Rollout checklist
- [ ] Add `boto3` to `pyproject.toml`
- [ ] Implement `S3VectorsStore` with Bedrock embedding integration
- [ ] Implement tools in `memory_tools.py` using `summary`
- [ ] Wire store into graph/supervisor (ensure `user_id` flows in `config`)
- [ ] Add unit tests and optional integration smoke test
- [ ] Validate in a staging environment with the real bucket/index

### Senior review (alignment, risks, mitigations)
- Alignment with architecture:
  - Uses LangGraph Store as the memory API with two-part namespaces `(user_id, type)` and indexes only `summary` per V1 spec.
  - Retrieval is semantic-only with strict filters (`user_id`, `type`, `category`), fitting the orchestrator’s memory-context node.
  - CRUD is complete for admin/ops needs (edit/delete) and supports future cold-path ingestion.
- Key trade-offs:
  - S3 Vectors (preview) lacks list/scroll and direct get-by-key; we compensate with filtered semantic queries and deterministic IDs. This is acceptable for V1 given we don’t need listing.
  - Embedding inside the store simplifies integration but couples us to Bedrock; that’s intended per requirements.
- Risks:
  - API changes in S3 Vectors preview could break behavior.
  - Bedrock latency spikes could affect `put/search` P95.
  - Metadata limits (size/keys) — mitigated by storing compact `summary` and flattening only essential filter fields.
- Mitigations:
  - Keep the store stateless and small; encapsulate all AWS calls behind a thin interface to ease updates.
  - Add configurable timeouts/retries for Bedrock and S3 Vectors; emit structured errors.
  - Add metrics and alarms for latency and error rates; load test with representative traffic.
- Extensibility:
  - Easy to add additional filter keys (e.g., `scope`, `trust_score`) without changing the contract.
  - Cold-path consolidation and promotion can reuse the same `put/get/search` surface.

### Hot path memory creation (non-blocking)
- Goals:
  - Emit a `memory.candidate` event immediately while the orchestrator is “thinking”, with the concrete memory payload (summary/category/type/id), without blocking tool calls.
  - Persist a record quickly, then perform embedding asynchronously.
- Design:
  - Add a `memory_hotpath` node early in the graph (before the main agent). It:
    - Runs a fast trigger (rules or small LLM) to decide `should_create` (≤250ms p95).
    - If positive, constructs a compact `summary` (rules or tiny LLM), normalizes `category`, and generates a `doc_key` (UUID4).
    - Emits SSE `memory.candidate` with `{id, type, category, summary, created_at}`.
    - Schedules background tasks (fire-and-forget):
      1) `store.aput(..., index=False)` to persist the document immediately (zero vector) so CRUD works.
      2) Embed `summary` via Bedrock and `store.aput(..., index=["summary"])` to upsert vector (makes it retrievable).
      3) On success, emit `memory.created` (and `memory.updated` if a merge/dedupe occurs later).
  - LangGraph integration:
    - Within the `memory_hotpath` node, use `asyncio.create_task(...)` for background steps; return state immediately to continue the main path.
    - Use `graph.stream(...)` or server-side SSE bridge to forward `memory.*` events derived from node outputs.
  - Orchestrator continues unaffected to perform tool calls and response assembly.
- Idempotency and dedupe:
  - Use deterministic keys only for explicit updates; for hot-path new items use UUID4 keys.
  - Optional: lightweight nearest-neighbor check post-embed (top-10) to merge with high-similarity existing memory; emit `memory.updated` if merged.
- Error path:
  - If the background write fails, emit `memory.error` with a minimal code and message; retry once with backoff.
- Latency expectations:
  - `memory.candidate` emitted within 200–300ms after user send.
  - `memory.created` typically within 300–900ms depending on Bedrock latency and S3 Vectors p95.

### Create vs Update decision policy (dedup/merge)
- Scope neighbor search to the same logical namespace and filters:
  - Namespace: `(user_id, type)` where `type ∈ {"semantic","episodic"}`
  - Filter: `category` if provided
  - TopK neighbors: 10
- Similarity thresholds (cosine) and actions:
  - Semantic:
    - `AUTO_UPDATE ≥ 0.90` → update existing (same fact)
    - `CHECK_RANGE = [0.80, 0.90)` → run tiny LLM "same_fact?" check; if true → update; else → create
    - `CREATE < 0.80` → create new
  - Episodic (stricter, time-windowed):
    - `AUTO_UPDATE ≥ 0.92` AND neighbor `created_at ≤ 72h` ago → update
    - `CHECK_RANGE = [0.85, 0.92)` within 72h → tiny LLM check; if true → update; else → create
    - Otherwise → create new
- Same-fact classifier (only for `CHECK_RANGE`):
  - Inputs: `{existing.summary, candidate.summary, category, salient entities/numbers}`
  - Output: `{same_fact: true|false}`; length-bound prompt to keep latency small
  - Heuristics to bias the decision:
    - If normalized entity overlap ≥ 70% and no conflicting numerics/dates → bias same_fact=true
    - Category mismatch → bias same_fact=false
- Update/merge policy (when updating):
  - `tags = union(existing.tags, candidate.tags)`
  - `last_accessed = now`; `access_count += 1` (if tracked)
  - `importance = max(existing.importance, candidate.importance)` (or small bump)
  - Optional: refine `summary` via a 1–2 sentence merge prompt (tiny LLM)
  - Audit: if a provisional hot-path record was created, link with `merged_from = [candidate_id]` then delete the provisional record after merge
- Create policy:
  - New UUID (for hot path, provisional key can be UUID4)
  - Set `created_at = last_accessed = now`; carry `category`, `tags`, `importance`, `pinned`
- Conflict changes (semantic contradictions):
  - If candidate contradicts a canonical fact (e.g., city change), create a new semantic memory that reflects the current value; mark prior memory with a tag (e.g., `superseded`) and link via `related_ids`
  - Optionally emit `memory.changed_fact` event for UI transparency
- Noise controls:
  - Type-aware merging: semantic merges are aggressive; episodic merges only within recency window
  - Category guardrail: never merge across categories unless `same_fact` is true
  - Rate limiting: cap hot-path writes per user per hour; down-rank `importance` when rate-limited

#### Background dedup/merge flow (async)
- After emitting `memory.candidate`, run:
  1) Optional provisional `aput(index=False)` (zero-vector) for immediate CRUD visibility
  2) Embed `candidate.summary`; neighbor search with `(user_id, type)` and `category`
  3) Apply thresholds; if `CHECK_RANGE`, call tiny LLM `same_fact?`
  4) Update or create accordingly using `aput(index=["summary"])`
  5) Emit `memory.updated` or `memory.created`; if merged, optionally `memory.merged` with `{from, into}`

#### Configuration knobs (env or settings)
- `SEMANTIC_AUTO_UPDATE=0.90`
- `SEMANTIC_CHECK_LOW=0.80`
- `EPISODIC_AUTO_UPDATE=0.92`
- `EPISODIC_CHECK_LOW=0.85`
- `EPISODIC_MERGE_WINDOW_HOURS=72`
- `MEMORY_NEIGHBORS_K=10`
- `MEMORY_WRITE_RATE_LIMIT_PER_HOUR=20` (example)
- `MEMORY_ENABLE_ENTITY_HEURISTICS=true|false`
- `MEMORY_TINY_LLM_MODEL_ID` (if using a small classifier distinct from Titan embeddings)
