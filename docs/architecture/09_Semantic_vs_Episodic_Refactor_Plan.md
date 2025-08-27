## Semantic vs Episodic Memory Refactor Plan

### Objective
- Align memory handling with LangGraph guidance and our product goals:
  - Semantic memory stores durable user facts, preferences, identity, and attributes of close entities (e.g., pet’s age).
  - Episodic memory stores noteworthy interactions/events/outcomes of the agent’s turns.
- Move creation logic so the entry node manages semantic only; create episodic selectively after the agent completes the turn.

### Current State (Summary)
- Entry node `memory_hotpath` both decides and writes memories (semantic and episodic), performs nearest-neighbor search, and may update.
- Retrieval node `memory_context` pulls both semantic and episodic with a local re-rank.
- Issues observed:
  - Fact corrections sometimes end up as episodic inserts instead of semantic updates.
  - Prompt payloads were logged verbosely (now reduced).
  - Post-turn outcomes are not explicitly captured as episodic; creation is input-driven instead of outcome-driven.

### Target Architecture (Graph-Level)
- Nodes
  - `memory_hotpath` (entry, pre-agent): semantic-only create/update, no episodic writes.
  - `memory_context` (pre-agent): retrieve semantic (priority) + a small set of recent episodic; boost episodic only on recall intent.
  - `supervisor` (+ tools) (core agent): orchestrates reasoning and tools.
  - `episodic_capture` (post-agent): selectively create/merge/skip episodic memories based on turn outcome, novelty, and policies.

- Edges (high-level)
  - START → memory_hotpath → memory_context → supervisor → episodic_capture → END
  - Tool nodes return to `supervisor`, then to `episodic_capture`.

### Node Responsibilities
- `memory_hotpath` (semantic-only)
  - Detect semantic candidates from last user turns.
  - Cross-namespace neighbor search within semantic to prefer update over insert.
  - Always re-embed on update; track `last_accessed` and `last_verified_at`.
  - Deterministic keys for common entities (e.g., profile:pet:luna:age) when extractable.
  - Never create episodic here.

- `memory_context`
  - Default retrieval: prioritize semantic; include 1–3 recent episodic.
  - On recall intent (e.g., “remember what we talked about”), increase episodic top-k and recency weight; still include a short semantic recap if helpful.

- `episodic_capture` (post-agent)
  - Decide to create/merge/skip episodic for the turn using:
    - Outcome signals: tool calls and results, decisions taken, next steps set.
    - Notability/novelty: similarity vs past N episodic entries.
    - Cooldown/quotas: minimum turns/time between episodic entries; max per day.
  - Merge into last episode (same theme within time window) rather than always insert.
  - Log concise decisions: episodic.decide/skip/merge/create.
  - Summarize last N messages (user+assistant only) via tiny LLM into 1–2 sentences focused on what was discussed/decided/done. Output strict JSON.
  - Use user’s timezone from `user_context.locale_info.time_zone` (fallback UTC) to stamp date buckets; construct human summary string as:
    - "On {YYYY-MM-DD} (W{WW}, {YYYY}) we discussed {topic}. Approach: {approach}."
  - Store additional metadata for retrieval: `date_iso`, `week`, `year`.

### Creation/Update Policies
- Semantic
  - Classifier prompts must prefer semantic for stable facts and fact corrections (e.g., “Luna turned 4”).
  - Update > Insert: fallback to semantic neighbor search when trigger says episodic but it’s a fact correction.
  - Deterministic keys when entity is known; else semantic nearest-neighbor.
  - Always re-embed on change; update `updated_at` and `last_verified_at`.

- Episodic
  - Create only if notability is high or outcome occurred (tool result, decision, milestone), or recall-intent recap is desired.
  - Enforce cooldown (e.g., ≥3 turns or ≥10 minutes) and daily cap (e.g., ≤5/day).
  - Merge recent related episodes (same theme) within a window (e.g., 24–72 hours).
  - Skip by default on routine turns and pure fact updates.
  - Summary source: tiny LLM on last N user+assistant messages; filter out boilerplate/tool traces.
  - Time buckets: include `date_iso`, `week` (ISO week), `year` in metadata to support time phrase retrieval (e.g., "last week").

### Retrieval Policy (memory_context)
- Normal turns
  - semantic: topk=24 (env), rerank by similarity + importance + recency + pinned.
  - episodic: topk small (e.g., 6–12), emphasize recency.
- Recall intent
  - episodic: raise topk and recency weight; semantic: include condensed profile bullet(s).
  - If time phrase detected (e.g., "last week", "yesterday"), translate to `week/year` or `date_iso` and add metadata filters when available; otherwise bias to recency.

### Decision Logic (Pseudocode)
- `memory_hotpath` (semantic-only)
  - parse last user messages → propose candidate
  - if should_create and type == semantic:
    - neighbors = search((user_id, "semantic"), query=summary, filter={category})
    - if best.score ≥ auto_update or (≥ low and same_fact == True): update(best)
    - else: create new semantic
  - if type == episodic: do not create here (defer to `episodic_capture`).

- `episodic_capture` (post-agent)
  - extract outcome signals (tools/decisions), detect recall intent
  - if notability < threshold or cooldown/quota violated: skip
  - candidate = concise summary (theme, outcome/status)
  - neighbors_recent = episodic in window
  - if similar theme exists: merge into latest episode; else: create new episodic

### Config Knobs (env)
- Semantic thresholds: `MEMORY_SEM_AUTO`, `MEMORY_SEM_LOW` (by type/category)
- Episodic: `EPISODIC_COOLDOWN_TURNS`, `EPISODIC_COOLDOWN_MINUTES`, `EPISODIC_MAX_PER_DAY`, `EPISODIC_NOVELTY_MIN`, `EPISODIC_MERGE_WINDOW_HOURS`
- Episodic summarizer: `EPISODIC_WINDOW_N` (default 10), `MEMORY_TINY_LLM_MODEL_ID`
- Retrieval: `MEMORY_CONTEXT_TOPK`, `MEMORY_CONTEXT_TOPN`, `MEMORY_RERANK_WEIGHTS`
- Logging: reuse simplified logging; emit structured decision logs.

### Observability
- Logs
  - semantic: memory.decide, memory.search, memory.match, memory.update, memory.create
  - episodic: episodic.decide, episodic.skip (cooldown/quota/low_notability), episodic.merge, episodic.create
- Metrics (optional)
  - counters: semantic_updates, semantic_creates, episodic_creates, episodic_merges, episodic_skips
  - histograms: similarity_scores, notability_scores, decision_latencies

### Migration Plan
- Identify misclassified episodic items that are stable facts; migrate to semantic or mark for update.
- Introduce deterministic keys for common profile entities (pet, pronouns, city, etc.) going forward.
- No destructive changes to storage schema; operate via store APIs.

### Rollout Steps
1) Phase 1 (Safe):
   - Enforce semantic-only behavior in `memory_hotpath` (episodic writes disabled).
   - Adjust classifier prompt to favor semantic for fact updates.
   - Keep `memory_context` as-is.
2) Phase 2 (Introduce episodic_capture):
   - Add `episodic_capture` after `supervisor`.
   - Implement cooldown/quota/novelty checks and merge-first policy.
   - Gate by env flag; monitor logs/metrics.
3) Phase 3 (Retrieval tuning):
   - Add recall-intent detection in `memory_context` to boost episodic retrieval.
   - Tune weights/top-k via env; evaluate with regression tests.

### Testing Strategy
- Unit tests
  - semantic update vs create decisions across score bands; same_fact classifier path
  - episodic_capture: cooldown/quota/novelty and merge vs create
- Integration
  - E2E scenarios: fact correction (e.g., pet age), decision with tool success, recall intent
- Regression
  - Ensure non-memory flows untouched; verify latency budget and error handling

### Acceptance Criteria
- Fact-correction messages (e.g., “Luna turned 4”) update existing semantic memory or create a semantic one; no episodic insertion from entry node.
- Episodic entries appear only on notable outcomes or recall-intents, respecting cooldown and merge policy.
- Retrieval behavior: semantic prioritized by default; episodic boosted on recall intents.
- Decision logs are concise and actionable.

### Future Work
- Deterministic key extraction via lightweight IE (entity tags for people/pets/places).
- Trustcall-like structured updating for complex semantic documents.
- Evaluation harness with labeled scenarios; automated threshold tuning.


