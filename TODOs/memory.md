## Memory system – implementation spec (why, source, how)

### 1) Memory Delta Header (turn-level change summary)
- Why: Keep supervisor aware of changes without extra tool calls. Prevents blind spots. Improves plan adaptation.
- Source: Our design; complements memU’s action logs and mem0 history.
- How:
  - State: per-thread `revision` integer. Maintain `changes` log for last N turns.
  - Emit on retrieval as first lines, max 3 bullets.
  - Events captured: created/updated/merged/deleted/soft_deleted/restored.
  - Data model:
    ```sql
    -- per thread
    thread_revision(thread_id text pk, rev bigint)
    change_log(id uuid pk, thread_id text, rev bigint, memory_id text, event text, meta jsonb, ts timestamptz)
    -- index: (thread_id, rev desc)
    ```
  - Injection format:
    ```
    Memory updates since rev {X}:
    - +created: [Personal] Preferred name is Ana (imp=2)
    - ↑updated: [Goals] Ship v1 by Sep
    - ↔merged: Combined 2 notes about lactose intolerance
    ```
  - Acceptance: Header appears when changes exist; size ≤ 3 bullets; rev increments atomically.

### 2) Minimal Relations Layer (lightweight graph edges)
- Why: Explicit links improve retrieval, clustering, UI, and future reasoning. Cheap compared to full graph.
- Source: memU `link_related_memories`, basic-memory relations table.
- How:
  - Table:
    ```sql
    relations(
      id uuid pk,
      from_id text not null,
      to_id text not null,
      relation_type text default 'related_to',
      strength real not null,
      created_at timestamptz default now()
    );
    create index on relations(from_id);
    create index on relations(to_id);
    ```
  - Write path (hot path): when creating/updating a semantic memory, for top-K neighbors with score ≥ link_min, insert edges with `strength = score` (dedupe by (from_id,to_id)).
  - Read path: during rerank, add small boost `+ w_rel*max_related_strength(memory_id)` and include 1–2 related bullets.
  - Acceptance: edge creation ≤ 2 ms/edge; no duplicate edges; retrieval includes related bullets when present.

### 3) Theory of Mind (ToM) Insights (background)
- Why: Capture latent psychological/relational insights (emotions, trust, preference evolution). Boost personalization.
- Source: memU `run_theory_of_mind` action.
- How:
  - Input: latest activity items (N≤5), new semantic items (K≤3), recent conversation snippet (≤1k chars).
  - Prompt constraints: output 1–3 insights; third person; no pronouns referring to AI; ≤280 chars each.
  - Output schema:
    ```json
    {"insights":[{"summary":"User shows increased trust when admitting mistakes.","tags":["trust","style"],"importance":2}]}
    ```
  - Storage: memory type = "insight"; category = "relationship_dynamic"; importance default 2; pinned=false.
  - Budget: temperature 0.0, maxTokens ≤ 220; skip if recent ToM within 24h.
  - Acceptance: only creates when non-empty; never blocks hot path; surfaced in retrieval with low weight.

### 4) Daily Consolidation Worker (cost-controlled)
- Why: Consolidate, merge, link, re-rank without inflating hot-path latency/cost.
- Source: memU background “evolve”; our merge bands; mem0 batch flows.
- How:
  - Schedule: 1/day per tenant (or staggered), with per-user caps (e.g., ≤ 50 pairs/day).
  - Candidate pool:
    - Items created/updated in last 72h OR importance ≥ 3 OR frequently retrieved (top decile).
  - Pre-filters (no LLM): cosine sim band [fallback_low, check_low), recency ≤ 90d, lexical overlap OR numeric step.
  - Batch LLM checks: group 5–10 pairs in one prompt; classify same-fact; apply recreate/update per policy.
  - Fingerprints: store pair hashes `(id_a,id_b,round(score,2))` to avoid rechecks for 14d.
  - Acceptance: daily runtime bounded; token cost budget per tenant; measurable reduction in duplicates.

### 5) Categories Config + Agent Allowlists
- Why: Consistent org, context mode policy, and secure per-agent access.
- Source: memU `memory_cat_config.yaml`.
- How:
  - YAML:
    ```yaml
    categories:
      system:
        - name: profile
          context: all
        - name: event
          context: rag
          rag_length: 30
        - name: activity
          context: rag
          rag_length: 50
      custom: []
    allowlists:
      supervisor: [profile, goals, preferences, event, activity, relationships, tasks]
      planner:    [goals, tasks, projects]
      stylist:    [preferences, tone, style]
      researcher: [knowledge, interests, history]
      executor:   [tasks, recent_activity, constraints]
    ```
  - Enforce server-side: requested categories ⊆ allowlist[agent].
  - Acceptance: requests with disallowed categories are rejected; context mode respected.

### 6) Single Tool: memory.query (supervisor + scoped subagents)
- Why: One minimal interface; avoids supervisor acting as router for many tools.
- Source: Our design; aligns with mem0 flexible filters and memU compact retrieval.
- How (API):
  ```json
  {
    "agent":"planner",
    "query":"deployment plan context",
    "categories":["tasks","projects"],
    "filters":{ "user_id":"...", "agent_id":"...", "run_id":"...", "actor_id":"...", "role":"assistant", "pinned":false, "importance_min":1, "importance_max":5, "updated_after":"2025-07-01", "updated_before":null },
    "top_k":3,
    "return":"bullets",
    "budget_tokens":512
  }
  ```
  - Response (bullets): `[ {"id":"...","category":"tasks","text":"[tasks] ..."} ]` (full returns full summaries + metadata).
  - Filters are optional; server enforces category allowlist regardless of filters. Threshold parameter is supported to drop low-similarity results: `threshold: 0.65`.
  - Acceptance: server-side allowlist enforced; token/budget respected; latency < 150ms for bullets.

### 6.1) Provider integration for filters (note)
- The provider interface (BaseStorage) must accept a filters dict and apply it server-side (not client-side) to ensure security and performance.
- Minimal required filter keys: `user_id, agent_id, run_id, actor_id, role, category, pinned, importance_min/max, updated_after/before`.

### 7) TTL + Soft-Delete Lifecycle
- Why: Prevent unbounded growth; declutter retrieval; respect user control.
- Source: memU “adaptive forgetting” concept; standard lifecycle management.
- How:
  - Policy: if `last_accessed > 60d` AND `importance < T` AND `!pinned` → `state=soft_deleted`, `purge_at=+30d`.
  - Retrieval excludes soft-deleted; users can restore; delta surfaces transition once.
  - Acceptance: no soft-deleted items in context; purge job removes post `purge_at`.

### 8) Audit/History Log
- Why: Transparency, debugging, and user-facing timelines.
- Source: mem0 SQLite history.
- How:
  ```sql
  history(
    id uuid pk,
    memory_id text,
    event text, -- ADD|UPDATE|DELETE|MERGE|LINK|TTL|RESTORE
    old_ref text null,
    new_ref text null,
    actor text null,
    meta jsonb,
    ts timestamptz default now()
  );
  create index on history(memory_id, ts desc);
  ```
  - API: GET /memory/{id}/history returns recent events.
  - Acceptance: events recorded for all write operations; exportable per user.

### 9) Writing Constraints (Prompt Policies)
- Why: Improve memory quality and downstream retrieval.
- Source: memU formatting; our constraints.
- How:
  - Semantic prompt guard:
    - “Write a complete, self-contained, third-person summary with no pronouns; neutral tone; 1–2 sentences; ≤280 chars.”
  - Episodic prompt guard:
    - “Past tense; 1–2 sentences; focus on what was discussed/decided/done; exclude stable facts unless updated.”
  - Validator: reject/trim outputs violating length or empty after normalization.
  - Acceptance: ≥ 95% of new items pass format checks on first pass.

### 10) Consent Policy (user_context vs semantic)
- Why: Respect user privacy; avoid silent PII mutations.
- Source: Our design; aligns with product norms.
- How:
  - Sensitive fields (preferred_name, pronouns, city, language) → require consent (UI or explicit chat ack) before applying; queue proposed patch for 7d.
  - Benign fields (tone, goals_add) → auto-apply if corroborated by ≥ 2 signals or ToM with high confidence.
  - Keep semantic merge bands as-is; apply stricter bands for context updates.
  - Acceptance: no sensitive field changes without consent; audit trail contains decision.

### 11) On-Demand Recall (safety valve)
- Why: Fix rare misses without overloading the supervisor with tools.
- Source: Our design; complements pre-injection.
- How:
  - Use `memory.query(..., return="bullets", top_k=3, budget_tokens≤N)` only when supervisor confidence is low.
  - Acceptance: < 10% of turns trigger recall; latency < 200ms.

### 12) Procedural Memory (optional, future)
- Why: Capture “how to” steps/skills/workflows distinct from facts/events; useful for agent execution and repeated tasks.
- Source: mem0 `procedural_memory` support.
- How:
  - Type: `procedural` with fields: `{ id, user_id, agent_id?, run_id?, steps_text, tags, importance, pinned, created_at, last_accessed }`.
  - Creation path: when supervisor or executor produces a stable workflow, summarize into 1–N numbered steps (imperative mood). Token budget small; no ToM.
  - Retrieval: excluded from default conversational context; only fetched by agents that need execution hints (executor/planner) via `memory.query(categories:["procedural"])`.
  - Acceptance: created only on explicit trigger or high-confidence detection; never pollutes semantic/episodic channels.

### 13) Optional Multi‑Fact Extraction Pass (future)
- Why: Some turns contain multiple durable facts; batching increases throughput and reduces missed captures.
- Source: mem0 multi-fact ADD/UPDATE flow.
- How:
  - Trigger only when user turn length > N chars or classifier confidence high.
  - Tiny LLM extracts 1–5 candidate facts with categories + importance; each fact runs through existing merge bands (auto/update/recreate/fallback).
  - Caps: ≤ 3 final writes/turn; global per-user/day cap to control cost.
  - Acceptance: improves recall without noticeable latency increase; hot path remains sub-150ms by offloading merges to background if needed.

### 14) Operational Tracking (minimal, fits current flow)
- Why: Basic visibility without needing extra instrumentation everywhere.
- Source: Our usage; scoped to places we already touch (hotpath, context, episodic).
- How:
  ```sql
  events(
    id uuid primary key,
    user_id text,
    thread_id text null,
    node text,       -- hotpath | context | episodic | worker
    op text,         -- classify | search | create | update | merge | delete
    status text,     -- ok | error | skipped
    memory_id text null,
    category text null,
    sim real null,   -- best neighbor score if available
    ts timestamptz default now()
  );
  create index on events(user_id, ts desc);
  create index on events(node, ts desc);
  ```
  - Emit where data already exists:
    - hotpath: classify (ok/skipped), search (sim if best), create/update/merge events.
    - episodic: create/merge events.
    - context: search (no sim optional).
    - worker (later): merge/link/ttl.
  - Keep fields minimal; add more later if needed. No token/latency metrics required now.
  - Acceptance: basic counts by op/node over time; enables answering “what changed and when” without logs.

### 15) Supervisor Checkpointer Migration to PostgreSQL
- Why: Move from in-memory checkpointer to persistent PostgreSQL storage for better reliability, scalability, and state persistence across restarts.
- Source: Current in-memory implementation; need for production-grade state management.
- How:
  - Create checkpointer table:
    ```sql
    supervisor_checkpoints(
      id uuid primary key,
      user_id text not null,
      thread_id text not null,
      checkpoint_data jsonb not null,
      created_at timestamptz default now(),
      updated_at timestamptz default now()
    );
    create unique index on supervisor_checkpoints(user_id, thread_id);
    create index on supervisor_checkpoints(updated_at desc);
    ```
  - Checkpoint data includes: current graph state, memory context, conversation history, agent states.
  - Acceptance: checkpoints persist across service restarts; no data loss during migration; sub-100ms checkpoint save/load times.


