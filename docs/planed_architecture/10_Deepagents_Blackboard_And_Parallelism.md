## Deepagents Blackboard Architecture (V1) + Opportunistic Parallelism

This document describes the adopted multi‑agent architecture for Vera V1 using a deepagents‑style shared blackboard, and a simple, safe pattern for opportunistic parallel fan‑out when tasks are independent.

### Goals
- Keep subagent collaboration simple and observable
- Support Budget multi‑turn flows via supervisor mediation
- Allow rare Finance↔Budget collaboration without lossy handoffs
- Enforce tier‑based capabilities
- Stay under ~10s p95 latency without premature complexity

### High‑level Graph (unchanged)
- START → `memory_hotpath` → `memory_context` → `supervisor` → `episodic_capture` → END
- Memory nodes are read‑only; creation/updates handled elsewhere as per memory docs.

### Core Pattern: Shared Blackboard (deepagents)
- All subagents share a common state with two key fields:
  - `files: dict[str, str]` — shared artifacts and structured payloads
  - `todos: list[Todo]` — lightweight progress/trace entries
- The supervisor is a deepagent configured with subagents:
  - `finance` (text‑to‑SQL over Plaid → charts/aggregates)
  - `budget` (compose/update budget JSON, multi‑turn with user)
  - `coach` (KB grounding)
- Subagents never message the user directly. They:
  1) Write asks/results to `files`
  2) Optionally update `todos`
  3) Return a concise tool message
- The supervisor turns these into user prompts/answers and re‑invokes subagents with the updated blackboard.

### Tier‑based Gating
- The supervisor receives `user_context.tier` in its config.
- It filters available subagents/tools per tier (e.g., Free → coach + KB only; Paid → add finance/budget).

### File Conventions (shared `files`)
- Context: `files['context/user.json']` — compact snapshot for subagents
- Budget:
  - `files['budget/spec.json']` — inputs/constraints collected from user
  - `files['budget/budget.json']` — final structured budget
- Finance:
  - `files['finance/query.sql']` — latest generated SQL
  - `files['finance/result.json']` — aggregates/table rows
  - `files['finance/chart.vl.json']` — Vega‑Lite chart (or `files['finance/chart.png']` URL)
- KB/Citations: `files['kb/citations.json']`
- Subagent asks → Supervisor → User:
  - `files['ui/asks.json']` → `{ "asks": [{"id","prompt","type","options"?}] }`
- Optional justifications: `files['justifications/<task-id>.md']`

### Budget Multi‑turn Flow (sequential, supervised)
1) Supervisor calls Budget via deepagents `task`.
2) Budget reads `context/user.json`; if missing data, writes `ui/asks.json` and returns.
3) Supervisor asks user; on reply, updates `context/user.json` and re‑invokes Budget.
4) If needed, Budget calls Finance via `task(subagent_type='finance')` to fetch aggregates.
5) Finance writes `finance/result.json` and optional `chart.vl.json`.
6) Budget produces `budget/budget.json` and a concise summary; supervisor replies to user.

### Opportunistic Parallel Fan‑out (safe & simple)
Use parallelism only when subtasks are independent and read‑only. Two patterns:

1) Parallel fan‑out tool (optional small utility)
   - A `transfer_to_many` tool issues two Sends (e.g., to `finance` and `coach`) with the same state snapshot.
   - The supervisor waits for both to complete, then proceeds. No UI or approvals required.
   - Example: For a general finance question, run KB grounding and a Finance aggregate in parallel.

2) Prefetch instead of true parallel
   - Kick off a lightweight Finance snapshot at the start of Budget flows and write to `finance/cache.json`.
   - Budget continues user Q&A and uses the snapshot when available.

Where not to parallelize
- Budget’s user Q&A — maintain sequential supervisor‑mediated turns.
- Any dependency chain (Budget needs Finance result first) — execute in order.

### Outputs & Frontend Contracts
- Charts: Prefer Vega‑Lite JSON in `finance/chart.vl.json` for native rendering (fallback to `chart.png` URL).
- Budget: Read `budget/budget.json` and display with client‑side components.
- Asks: Render `ui/asks.json` as inputs/chips; POST answers, then the server updates `context/user.json` and resumes.

### Observability
- Langfuse spans around supervisor and subagent calls.
- `todos` updated on significant steps for traceability.
- Optional: subagents write a short justification per completed task.

### Guardrails & Models
- All agents run on Bedrock with guardrails (Anthropic models), configured in `app/core/config.Config`.

### Latency Tactics
- Small memory bullets (already in `memory_context`).
- Batch Finance SQLs per turn (fewer tool calls).
- Use fan‑out only for clearly independent read‑only subtasks.

### Migration Plan (from current code)
- Replace supervisor’s `create_react_agent` with a deepagent via `create_deep_agent` or `create_configurable_agent`.
- Define subagents (`finance`, `budget`, `coach`) and wire their tools.
- Adopt file conventions above; update frontend to consume `files` artifacts.
- Optionally add `transfer_to_many` for safe fan‑out.

### Future Extensions
- Add approval interrupts for any future write actions.
- Add more subagents (new sources/artifacts) with the same blackboard contract.


### Supervisor → Frontend Response Envelope
The supervisor returns a compact response envelope. The frontend renders `text`, pulls artifacts by key from the blackboard `files`, and shows attribution when present.

```json
{
  "text": "Friendly, empathetic answer summarizing what was found or next steps.",
  "routing": { "agents": ["budget"] },
  "artifacts": {
    "budget_json": "files://budget/budget.json",
    "chart_vl": "files://finance/chart.vl.json"
  },
  "attribution": {
    "kb": "files://kb/citations.json",
    "memory": ["semantic", "episodic"]
  }
}
```

Notes
- `artifacts` keys are stable handles the FE understands; values point to paths in shared `files`.
- `attribution.kb` references `files['kb/citations.json']` when the Coach/KB tool is used.
- `attribution.memory` indicates which memory types were consulted by `memory_context`.
- For Finance charts prefer `files['finance/chart.vl.json']` (Vega-Lite). If using images, expose a signed URL at `files['finance/chart.png']` and reference it instead.


