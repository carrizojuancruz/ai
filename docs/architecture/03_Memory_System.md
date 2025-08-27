# 3. Memory System — V1 (LangGraph Store)

This section defines the minimal, production‑ready V1 memory we are shipping now. It is intentionally concise and focused on the pieces that create a believable parasocial memory within 12 workdays.

## V1: What we are shipping now (12 days)
- Storage and namespacing
  - Use LangGraph Store with namespaces: `(user_id, "memories", "semantic"|"episodic")`.
  - Configure embeddings to index the `summary` field.
- Write path (cold by default)
  - Pre‑response trigger: run a tiny LLM (Anthropic Haiku) to detect if a memory should be created.
    - Latency budget: ≤250 ms p95; context: last 1–2 turns; output: {should_create, type_hint, tags_hint, confidence}.
    - If `should_create` true with confidence ≥ threshold (e.g., 0.6): emit SSE `memory.candidate` immediately and enqueue job.
    - Fallback to rules if the LLM times out.
  - After the model responds, the cold‑path worker finalizes memory creation.
  - Two‑stage extraction (in worker): simple rules + small LLM classifier to decide: skip | episodic | semantic and to summarize.
  - Pre‑upsert dedup/update:
    - Embed candidate `summary` → vector search top_k (e.g., 10).
    - If best similarity ≥ `SIM_THRESHOLD` (e.g., 0.85), run a tiny LLM (Haiku) to check semantic equivalence (same_fact?).
    - If equivalent → UPDATE existing memory (merge tags, refresh `last_accessed`, optionally refine `summary`), emit `memory.updated`.
    - Else → CREATE new memory (new id), emit `memory.created`.
  - Drop low‑importance items.
  - Hot‑path writes only for explicit user commands (remember/forget/pin) and high‑trust facts.
- Retrieval (rule‑based + similarity)
  - Semantic: when personalization is needed → top 5 (similarity ≥ 0.75) with scope/trust filters.
  - Episodic: when user references the past or for hooks → top 2–3 recent/similar (prefer summaries).
- Forgetting (light)
  - If `last_accessed > 60d` and `importance ≤ 2` → delete. Pin overrides deletion.
- Admin/ops
  - Simple admin page to list/edit/delete memories with audit trail.

## Minimal JSON schema (V1)
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "type": "semantic|episodic",
  "summary": "1-2 sentences",
  "tags": ["finance", "goals"],
  "source": "chat|external",
  "importance": 1,
  "created_at": "ISO8601",
  "last_accessed": "ISO8601",
  "pinned": false
}
```

## Node sequence (where this plugs into LangGraph)
- Orchestrator turn
  - Decide whether to retrieve semantic and/or episodic; call `store.search` with filters; assemble small memory block.
  - Run `detect_memory_trigger_haiku` (time‑boxed). If positive, emit `memory.candidate` SSE (with temp id) and enqueue background job.
  - Continue streaming the normal reply; do not block on memory creation.
- Memory worker (cold path)
  - Run rules + LLM classifier → decide to skip or write.
  - Upsert memory document; embed `summary`; emit `memory_added` event; record audit.

## Acceptance criteria (V1)
- Memories are written asynchronously with <1s p95 worker latency under load.
- Trigger decision adds ≤250 ms p95 and placeholder (`memory.candidate`) appears <300 ms after user send.
- Retrieval returns ≤5 concise items and measurably improves personalization on test prompts.
- Admin can view/edit/delete items and see who/when created them.
- No raw transcripts used in retrieval; only summaries indexed.

---

## Appendix: Detailed mechanics (V2+)

## 11) Proactivity rules (short)
- Only use memories with `proactivity_weight` and `trust_score` above thresholds.
- Rate-limit proactive outreach; backoff if ignored.
- Tone modulation: positive valence → friendly; negative valence → soft check‑in when user recently engaged.
- Always reference provenance (why this message).

## 12) Metrics & tuning (V2+)
- Track retrieval precision/usefulness, consolidation coverage, promotion accuracy, proactivity accept, decay false-positives, token usage.
- Tuning knobs: similarity cutoff, cluster size threshold, scoring weights, proactivity caps, archive retention.

## V2+ scope (beyond V1)
- Consolidation/summarization pipeline; pattern‑based promotion; advanced decay; emotional valence; cross‑memory links; procedural memory.
## 10) Pseudocode: end-to-end (ingest, consolidate, retrieve)
```
# Ingest worker (cold path)
on message_processed(event):
    raw = event.text + system_metadata
    if rules_accept(raw) or classifier_says_store(raw):
        mem = extractor_summarize(raw)            # 1–3 sentence text
        mem.type = classifier.type
        mem.tags = classifier.tags + ner_entities
        mem.valence, mem.intensity = sentiment(raw)
        mem.trust_score = source_trust(event.source)
        mem.importance_score = compute_importance(mem)
        mem.embedding = embed(mem.summary)
        store.put((user_id, "memories", mem.type), mem.id, mem, index=["summary"])  
        link_to_related(mem)   # neighbor search and create related_ids
        emit_event("memory_added", mem.id)

# Nightly consolidation
for user in users:
    episodics = fetch_recent_episdics(user,last_90_days)
    clusters = cluster_by_embedding(episodics)
    for cluster in clusters:
        if cluster.size == 1 and cluster.average_importance < low_threshold:
            archive(cluster.items)
        else:
            summary = call_llm_summarize(cluster.items)
            consolidated = create_consolidated(summary, consolidated_from=cluster.ids)
            compute_importance(consolidated)
            save(consolidated)
            archive(cluster.items)

# Retrieval (orchestrator)
function retrieve_for_prompt(user_id, prompt_text, prompt_tokens, T_mem):
    slots = allocate_retrieval_slots(T_mem, prompt_tokens, weights)
    results = {}
    for type,slot in slots:
        initial = store.search((user_id, "memories", type), query=prompt_text, limit=50, filter=scope_match)
        scored = [combine_score(r.similarity, r.metadata.importance, recency(r)) for r in initial]
        top = rerank_with_llm(prompt_text, top_candidates=scored[:12], final_k=slot)
        results[type] = top
    return assemble_context(results)
```
## 9) Memory JSON schema (example)
```
{
  "id": "uuid",
  "user_id": "uuid",
  "type": "episodic|semantic|procedural|consolidated",
  "title": "short headline",
  "summary": "1-3 sentence summary",
  "raw_text_refs": ["event_id1", "event_id2"],
  "tags": ["finance", "budget", "travel"],
  "scope": ["finance"],
  "source": "chat|instagram|bank_api",
  "trust_score": 0.85,
  "valence": "positive",
  "intensity": 0.7,
  "importance_score": 0.63,
  "proactivity_weight": 0.5,
  "pinned": false,
  "private": false,
  "created_at": "ISO8601",
  "last_accessed": "ISO8601",
  "access_count": 3,
  "consolidated_from": ["uuid", "uuid"],
  "related_ids": ["uuid", "uuid"],
  "embedding_ref": "vector-db-id",
  "archived": false,
  "deleted": false,
  "audit": [{"action": "created", "by": "system", "at": "ISO8601"}]
}
```
## 8) Tag taxonomy examples
- Fixed: finance, budget, travel, health, relationship, work, hobby, security, legal, entertainment
- Free: loves-black-coffee, hates-spreadsheets, trip-london-2025
- Scope tags for subagents: finance_agent_scope, social_agent_scope, inbox_agent_scope
## 7) Promotion rules (episodic → semantic)
- Promote when tag/fact repeats > N times within P days (e.g., 3 in 60d), trust > 0.7, and no conflict with canonical `user_context`.
- Background job creates semantic candidate with provenance; human review if confidence < 0.9.
- Upon approval, persist as semantic with links to consolidated items.
## 6) Forgetting & decay
- Half-life by importance: ≥0.85→365d; 0.5–0.85→180d; 0.2–0.5→90d; <0.2→30d.
- Daily: `current_weight = importance * 0.5^(days_since_last_access / half_life)`.
- If `current_weight < 0.05` and `last_accessed > 30d` → `archived=true`.
- Retain archived 180d; hard-delete unless pinned or legal hold. Provide user controls for pin/forget.
## 5) Retrieval — counts and algorithm
Defaults
- Semantic: top 5 (cutoff ≥ 0.72)
- Episodic: top 3 (prefer consolidated; pull 1–2 underlying if needed)
- Procedural: 1–2

Dynamic allocation
```
def allocate_retrieval_slots(T_mem, prompt_size_tokens, weights):
    available = max(0, T_mem - prompt_size_tokens)
    est = {"semantic": 120, "episodic": 250, "procedural": 200}
    MAX = {"semantic": 10, "episodic": 5, "procedural": 3}
    slots = {}
    for t, w in weights.items():
        budget = available * w
        slots[t] = max(1, min(MAX[t], int(budget // est[t])))
    return slots
```

Reranking
- Candidate pool via `store.search(..., limit=50, filter=scope/trust)`
- Score = 0.5*similarity + 0.25*importance + 0.15*recency + 0.05*scope + 0.05*trust
- Final LLM reranker on top ~8 → pick K.
## 4) Consolidation & summarization pipeline
When to run
- Nightly per user; immediate mini‑consolidation if > X episodic events in 24h; on‑demand when retrieval quality drops.

Steps
- Cluster episodic embeddings with time windows.
- If cluster size=1 and low importance → archive/drop (after grace period).
- Else create `consolidated_summary` (1–3 sentences with dates/actors/outcome; highlight decisions/tasks/tone).
- Save consolidated memory with `consolidated_from` links; compute new `importance_score`; set `last_accessed`.
- Mark originals `archived: true` and keep in cold storage. Consider promotion to semantic if patterns repeat.
## 3) Importance score formula (concrete)
Compute normalized `importance_score` on ingestion.

```
importance_raw =  0.25*pinned_flag
                + 0.20*trust_score
                + 0.20*min(1, log(1 + access_count)/log(10))
                + 0.20*valence_intensity_norm   # 0..1
                + 0.15*explicit_user_importance_flag
importance_score = clamp(importance_raw, 0, 1)

valence_intensity_norm = intensity * (valence == negative ? 0.8 : 1.0)
```
## 2) What to store & how to tag it
Two-stage extractor
- Rules (fast filters):
  - Save entities (PERSON, ORG, MONEY, DATE, LOCATION, PRODUCT)
  - Save personal relevance (preferences, planning, scheduling, financial decisions)
  - Save explicit commands: “remember this”, “remind me”, “this is private”
  - Save attachments as episodic pointers
- LLM classifier (cold path):
  - Output: `memory_type`, `tags`, `valence` + `intensity`, `importance_suggestion`, `proactivity_suggestion`, `trust_suggestion`

Tagging fields (metadata)
- `scope` (list), `source` (chat|instagram|bank_api|system), `trust_score`, `valence`, `intensity`, `proactivity_weight`, `pinned`, `private`, `archived`, `created_at`, `last_accessed`, `access_count`.
# 3. Memory System — Mechanics (Create, Tag, Compress, Retrieve, Forget)

This document specifies how Vera's long‑term memory works using LangGraph's Store pattern and namespaces, aligned with Bedrock AgentCore. It focuses on concrete mechanics to create, tag, compress, retrieve, and forget memories so Vera feels personal without becoming noisy or slow.

Core principle
- Use LangGraph's Store as the memory API and namespaces for organization, backed by background jobs so memory stays selective and transparent.

Summary (short)
- Cold-path ingestion (async after response) to avoid latency.
- Decide what to store via rules + small LLM classifier (entities, sentiment, intent, importance).
- Tag with: scope, source, trust_score, valence/intensity, importance_score, proactivity_weight, created_at, last_accessed.
- Consolidate episodic memories periodically: cluster → summarize → create consolidated memory and link originals.
- Promote repeated patterns to semantic facts (frequency thresholds).
- Retrieval = vector similarity + importance + recency + scope/trust filtering + reranker; type-dependent counts.
- Forget via decay curves (half-life tuned by importance), with soft-archive and user pin/override/audit.

## Memory Tagging and Access Control

To ensure data integrity, relevance, and security, all memory systems adhere to the following principles:

-   **Read-Only Access for Specialists:** All Specialist Agents (`Budget`, `Finance`, `Education & Wealth Coach`) have **read-only** access to the user's Semantic and Episodic memory. Only the core system or a dedicated memory management process can write new entries.
-   **Category Tagging:** Every memory entry is tagged with a relevant category to allow for filtered retrieval and better contextual understanding.
-   **Timestamps:** Every memory entry is timestamped with its creation date.

**Memory Categories:** `[Finance, Budget, Goals, Personal, Education, Conversation_Summary, Other]`

Access model
- Specialist Agents have read-only access to Semantic and Episodic memory; writes occur via orchestrator or memory service.
- Expose a Memory Registry UI to list, edit, pin/unpin, archive/restore, and delete with provenance.
- All writes/archives/deletes create audit entries.

---

## Implementation blueprint with LangGraph Store

- Namespaces:
  - `(user_id, "memories", "semantic")`
  - `(user_id, "memories", "episodic")`
  - `(user_id, "memories", "procedural")`
  - `(org_id, "policy", "proactivity")`
- Keys: `memory_id` (UUID). Values: memory JSON documents.
- Indexing: configure Store to embed `summary` (and optionally `$`) with dims/model in `langgraph.json`.
- Retrieval: orchestrator node calls `store.search(namespace, query, limit, filter)`, then performs reranking by combining similarity + importance + recency + trust + scope.
- Writes: hot-path only for explicit commands/critical facts; default to cold-path background worker.

---

## 1. User-Centric Memory (The User's History)

This memory is focused on the individual user (semantic and episodic) and is persisted as JSON documents in LangGraph's Store under user-scoped namespaces.

-   **a. Semantic Memory (User Preferences & Profile):**
    -   **What it is:** A dedicated, user-specific vector database containing enriched information about the user's preferences, inferred goals, and communication style.
    -   **How it works:** When a user interacts with Vera, key information is summarized and stored as a memory document with tags and timestamps. The Store is configured to embed the `summary` field for semantic search. Specialist Agents can perform a **read-only** search to retrieve relevant context.
    -   **Purpose:** To build a deep, evolving understanding of the user for personalization.

-   **b. Episodic Memory (Conversations & Moments):**
    -   **What it is:** Compact summaries of past interactions/events, tagged and timestamped; consolidated periodically to avoid bloat.
    -   **Purpose:** Maintain narrative continuity and recall past interactions with minimal tokens. Specialists read-only.

## 2. Agent Operational Memory (How the Agent Works)

This memory is not about the user, but about how the agent itself operates and accesses knowledge (procedures, examples).

-   **a. Procedural Memory (Routing & Task Execution Examples):**
    -   **What it is:** A developer-curated vector database loaded with hundreds of examples. Each example consists of a sample user input and the ideal corresponding action or sequence of Specialist Agent invocations.
    -   **How it works:** The **Orchestrator Agent** performs a semantic search over these examples using the Store; optionally self-updates instructions via a dedicated `instructions` namespace with human review.
    -   **Purpose:** To teach the Orchestrator how to delegate tasks effectively.

-   **b. Textbook Knowledge Base (General Financial Knowledge):**
    -   **What it is:** A curated, read-only knowledge base separate from personal memory.
    -   **How it works:** Queried via a dedicated RAG service/tool; results merged with memory retrieval but not stored as personal memory.
    -   **Purpose:** Provide cited, reliable answers to general questions without polluting personal memory.

---

## User Controls, Privacy, and Governance

To honor user control and transparency, the memory layer exposes two user-facing controls:

- **Blocked Topics (Do-Not-Discuss List):**
  - A user-maintained list of topics the assistant must avoid. Stored with category tags and creation timestamps. All Specialist Agents must consult this list (read-only) before proposing content or suggestions.
  - Enforcement happens at the Orchestrator and Specialist layers (pre-response guardrail) to filter intents and content.
  - Enforced in retrieval filters and prompt assembly.

- **User Knowledge Registry (What Vera Knows About Me):**
  - A browsable list of user-related facts and preferences (grouped by category and timestamped). Items are editable and deletable by the user.
  - Retrieval is category-filtered and time-aware to support auditing and redaction.
  - Exposes provenance (which events created each memory) and supports pin/forget.

Access model:
- Specialist Agents have read-only access; writes are performed by orchestrator or memory service via controlled pathways (e.g., post-turn extractors) to preserve integrity.

---

## 1) Cold-path ingestion — architecture & flow (why and how)
Why cold path? avoids adding latency to the user interaction and enables heavier extraction and enrichment.

Flow (high level)
- User message → Orchestrator → Specialists → response.
- After response returns, enqueue message + response to `memory_ingest_queue`.
- Worker runs extractor pipeline (NER, intent classifier, sentiment, topic clustering, policy checks).
- Candidate memory objects are scored & tagged; write summarized `summary` + metadata; embed for search.
- Emit events: `memory_added`, `maybe_promote_to_semantic`, `proactivity_candidates`.

Notes
- Keep raw text stored for audit but don’t expose raw in retrieval—use summarized chunks.
- Run linking: neighbor search to find related memories and create `related_ids` links.

Hot-path exceptions
- Immediate writes for explicit user commands (remember/forget/pin), consent flags, or high-trust API facts needed within the same session.
