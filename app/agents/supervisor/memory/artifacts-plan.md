## Artifacts and Budget Plan (V1)

### Overview

Artifacts are first‑class, structured records the system and user care about (e.g., Budget, Checklist, Report). Each artifact has:
- A live record (current state)
- Immutable versions (full snapshots over time)
- An append‑only event log (what happened, when, why)

For Budget V1 (single budget per user): the plan is immutable unless the user approves a change. “How it’s going” is computed from a Postgres mirror of transactions and stored as period snapshots, not by mutating the plan. This supports automatic updates, explainability, and a parasocial experience without building a full tracker app.

Key pieces:
- Budget artifact (the plan)
- Period snapshots (planned vs actual, adherence)
- Proposals (optional changes that require consent)
- Events (created, updated, violation, on_track, closed)
- Rules Engine integration (proactive notifications)
- Widget read model (fast, denormalized summary for iOS)

### Data Model (storage shape)

- artifacts: live record per artifact
  - id, user_id, type (budget|checklist|report|asset|proposal|insight?), title, status (active|archived), current_version, schema_version, created_at, updated_at, payload_preview (short text)

- artifact_versions: immutable snapshots
  - id, artifact_id, version (int), payload_json (JSONB), created_at, updated_by (agent|user)

- artifact_events: append‑only lifecycle/events
  - id, artifact_id, user_id, type (created|updated|checkin|violation|on_track|closed|proposal_created|proposal_approved|proposal_rejected), meta (JSONB), ts

- budget_periods: computed progress per period (read/write by daily job)
  - id, artifact_id, user_id, period_start, period_end, planned_total, actual_total, remaining_total, adherence_pct, days_elapsed, period_days, ideal_burn, burn_gap, per_category (JSONB), last_updated

- ingest_state: incremental processing watermark for the Postgres mirror
  - user_id, last_txn_updated_at

- category_rules: small editable ruleset for merchant→category mapping
  - id, user_id, match_type (exact|prefix|regex), pattern, category, priority

- budget_widget_summary: denormalized read model for iOS widget (one row per user + current period)
  - user_id, period_start, period_end, progress_pct, planned_total, actual_total, remaining_total, top_over (JSONB), top_under (JSONB), last_updated

Notes:
- Reports store binaries in S3; only metadata lives here.
- Checklists can use either a dedicated table (existing) or be wrapped as an artifact with payload items.

### Budget Schema (payload_json, v1)

- metadata: { period: monthly|weekly, start_date, currency }
- incomes: [{ name, amount }]
- categories: [{ name, planned_amount, notes? }]
- targets: [{ metric: savings_rate|debt_reduction, value }]
- computed (server‑populated on create/update): { planned_total }

The plan is not auto‑mutated. Revisions create new versions with consent.

### Workflows

1) Create Budget (plan, version 1)
- Supervisor detects intent; runs a brief schema‑driven interview to fill required fields (≥ 5 core questions).
- Validate, create artifact + version=1, emit artifact_event(created).
- Write a short semantic memory and relation (e.g., “Budget created”), surfaced in deltas.

2) Daily Rollup from Postgres Mirror
- Read transactions updated since `ingest_state.last_txn_updated_at`.
- Normalize merchants; map to categories via `category_rules`; fallback to “uncategorized”.
- Compute current (and previous) period aggregates: planned vs actual, per‑category deltas, adherence, ideal burn vs actual burn.
- Upsert `budget_periods` and `budget_widget_summary` for the user; set `last_updated`.
- If thresholds crossed (e.g., category > X% over mid‑period), emit artifact_event(violation) or on_track.
- Update ingest watermark.

3) Supervisor Behavior
- Acknowledge changes via memory delta only when the user engages (“We’re 12% under Groceries—nice.” / “Dining is 18% over; adjust?”).
- When deviations persist, create a lightweight Proposal artifact (e.g., shift $100 from Dining to Groceries this month). Approval in chat creates a new budget version; emit proposal_approved + updated.

4) Rules Engine Integration
- Inputs: `budget_periods`, artifact_events, streaks.
- Cron or event triggers evaluate rules and emit proactive notifications: type, severity, title, summary, suggested_reply, related_artifact_id, metrics, dedupe_key, cooldown.
- App shows notification; Supervisor opens with that context. Memory delta is written only on user action (accept/decline/clarify).

5) Widget
- iOS widget reads a compact `budget_widget_summary` via one endpoint.
- Fields: progress % (actual/planned), remaining_total, top over/under categories, last_updated.
- Plan remains immutable; widget reflects the latest snapshot.

### Minimal APIs/Tools (internal contracts)

- artifact.create(type, payload) → { artifact_id, version }
- artifact.update(id, payload, expected_version) → { version }
- artifact.get(id), artifact.history(id), artifact.search(type, filters)
- proposal.create(artifact_id, payload), proposal.approve(id)
- budget.summary(user_id) → `budget_widget_summary` for current period
- rules.fire(event_payload) (internal), rules.snooze(dedupe_key)

These are internal service boundaries; they can be implemented as functions/tools without public API exposure in V1.

### Consent, Explainability, Memory

- Budgets change only via explicit approval; versions are immutable; events track why changes happened.
- Supervisor cites snapshots and events in conversation; short semantic deltas maintain a “felt” continuity without spamming memory.

### Acceptance Criteria (V1)

- A single Budget per user can be created, versioned on approval, and never auto‑mutated.
- Daily job computes `budget_periods` and `budget_widget_summary` from the Postgres mirror; late transactions are absorbed by recomputing the current and previous period.
- Rules Engine produces proactive notifications with cooldowns and dedupe.
- Supervisor acknowledges changes, proposes adjustments when needed, and writes deltas only on engagement.
- iOS widget shows progress, remaining, top over/under categories, and “as of” timestamp.


