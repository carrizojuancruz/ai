# Vera Goals — User Stories (V1, Cashflow-Only)

**Scope:** V1 is **reactive** (cashflow-only: money-in/money-out, manual entries). No forecasting, envelopes, or earmarking.  
**Audience:** Product, Engineering, and Design teams working on Vera’s multi-agent assistant.

---

## Table of Contents
- [US-1 — Onboarding & Conversational Goal Creation](#us-1--onboarding--conversational-goal-creation)
- [US-2 — Categorization & Filtering (Plaid + Manual)](#us-2--categorization--filtering-plaid--manual)
- [US-3 — Frequency & Amount (Absolute / Percentage)](#us-3--frequency--amount-absolute--percentage)
- [US-4 — Data Sources & Manual Entries](#us-4--data-sources--manual-entries)
- [US-5 — Progress & Evaluation](#us-5--progress--evaluation)
- [US-6 — Alerts & Reminders (Heuristics Engine)](#us-6--alerts--reminders-heuristics-engine)
- [US-7 — States, Transitions & Errors](#us-7--states-transitions--errors)
- [US-8 — Multi-Agent Coaching & Education](#us-8--multi-agent-coaching--education)
- [US-9 — Goals UI/UX](#us-9--goals-uiux)
- [US-10 — Persistence, Security & Audit](#us-10--persistence-security--audit)
- [US-11 — Performance & Scalability](#us-11--performance--scalability)
- [US-12 — Integrations & Inter-System Communication](#us-12--integrations--inter-system-communication)
- [Definition of Done — V1 (Cross-cutting)](#definition-of-done--v1-cross-cutting)
- [V2+ (Out of Scope)](#v2-out-of-scope)

---

## US-1 — Onboarding & Conversational Goal Creation
**Goal:** Create goals via dialogue; keep `pending` until activation.

- **US-1.1 (P0)** Create a goal from a single utterance (title, category, nature, frequency, amount).  
  **AC (Gherkin):**
  ```gherkin
  Given I start "Create goal"
  When I say "Reduce entertainment by $200 per month"
  Then a draft is proposed with category=spending, nature=reduce,
       frequency=recurrent:month/1, amount.absolute=200 USD, status=pending
  ```

- **US-1.2 (P0)** Autosave each captured detail with SSE/WebSocket and `{revert}` link.  
  **AC:** Changing `amount` from 200 → 250 emits a `goal_autosave` event with `old_value`, `new_value`, and a message containing `{revert}`.

- **US-1.3 (P0)** Binary choice to **Activate** or **Keep refining**.  
  **AC:** Choosing “Yes, activate” sets `status=in_progress`; choosing “Keep refining” keeps `pending`.

- **US-1.4 (P1)** Edit any field in `pending` using natural language.

- **US-1.5 (P1)** Duplicate a goal as a template.

---

## US-2 — Categorization & Filtering (Plaid + Manual)
**Goal:** Apply category filters and combine sources per V1 rules.

- **US-2.1 (P0)** Category-reduction goals only consider transactions from selected categories (including manual where applicable).  
  **AC:** With filter `entertainment` and `source=mixed|manual_input`, only Plaid `entertainment` + manual `entertainment` count.

- **US-2.2 (P0)** Multi-category filters with mode: **any** / **all**.

- **US-2.3 (P0)** Recategorize a transaction (Plaid or manual) and immediately recompute progress.

- **US-2.4 (P1)** Temporal anchors for evaluation windows (e.g., “last day of month”).

- **US-2.5 (P2)** Change logs for category edits (audit).

---

## US-3 — Frequency & Amount (Absolute / Percentage)
**Goal:** Support specific date or recurring; absolute or % over bases.

- **US-3.1 (P0)** Recurrence: `day|week|month|quarter|year`, `every` ≥ 1, anchors `day_of_month|weekday`.  
  **AC:** “Every 2 weeks on Friday” ⇒ `unit=week`, `every=2`, `anchors.weekday=fri`.

- **US-3.2 (P0)** Absolute amounts with ISO 4217 currency validation.

- **US-3.3 (P0)** Percentage amounts with basis `income|spending|category|account|net_worth|custom_query` and optional `ref_id`.  
  **AC:** “Save 20% of my income” ⇒ `percentage.target_pct=20`, `of.basis=income`.

- **US-3.4 (P1)** Rounding control `none|floor|ceil|round` affecting compute + display.

- **US-3.5 (P1)** One-off goals with a **specific** target date.

---

## US-4 — Data Sources & Manual Entries
**Goal:** Operate with `linked_accounts`, `manual_input`, or `mixed`.

- **US-4.1 (P0)** Select the **source** at creation.  
  **AC:** `linked_accounts` ⇒ Plaid categories only; `manual_input` ⇒ manual/custom only; `mixed` ⇒ both.

- **US-4.2 (P0)** Create manual expenses/incomes with amount, concept, category, date.

- **US-4.3 (P0)** Edit/delete manual entries and trigger recompute.

- **US-4.4 (P1)** Import cash expenses as manual with category.

---

## US-5 — Progress & Evaluation
**Goal:** Reactive tracking with aggregation & direction.

- **US-5.1 (P0)** Show `current_value`, `% complete`, `updated_at`; respect `aggregation (sum|avg|max|min)` and `direction (≤|≥|=)`.

- **US-5.2 (P0)** Recurrent goals evaluate per active period; reset metrics at new period start.

- **US-5.3 (P0)** For `direction=≤` (reduce spend), treat staying **at or below** target as on-track (≥100% when target not exceeded).

- **US-5.4 (P1)** Period history (prior months/weeks) without forecasting.

- **US-5.5 (P1)** Contribution breakdown by categories/entities.

**US-5.2b (P0) — Monthly period reset (AC, Gherkin)**
```gherkin
Given a monthly goal with start_date=2025-09-01 and $120 progress on 2025-09-25
When it becomes 2025-10-01 00:00 (user TZ)
Then visible accumulation resets to 0 for October
And September remains available in history
```

---

## US-6 — Alerts & Reminders (Heuristics Engine)
**Goal:** Proactivity via thresholds and reminders.

- **US-6.1 (P0)** Configure `warn_progress_pct`, `alert_progress_pct`, `warn_days_remaining`.  
  **AC:** If `% < alert_progress_pct` ⇒ critical alert; if `% < warn_progress_pct` ⇒ warning; if `warn_days_remaining` met ⇒ time-based alert.

- **US-6.2 (P0)** Reminders: `push` or `in_app_message` with expressions like `"monthly:day=27"`, `"weekly:weekday=fri"`, `"days_before:7"`.

- **US-6.3 (P1)** Nudge dormant `pending` goals after N days with **binary_choice** (Activate | Keep refining).

- **US-6.4 (P2)** Celebrations & course-correction suggestions.

**US-6.1b (P0) — Critical alert (AC)**
```gherkin
Given alert_progress_pct=50 and a goal "save $500/month"
When by day 25 the saved amount is $200 (40%)
Then a critical alert is sent with a BudgetAgent suggestion
```

---

## US-7 — States, Transitions & Errors
**Goal:** Manage `pending|in_progress|completed|error|deleted` with rules.

- **US-7.1 (P0)** Activation moves `pending → in_progress`.  
  **AC (Gherkin):**
  ```gherkin
  Given a complete pending goal
  When I choose "Yes, activate"
  Then status becomes in_progress and tracking starts for the current period
  ```

- **US-7.2 (P0)** Achieving the target within the window sets `completed` and stores achievement date.

- **US-7.3 (P0)** Sync failures > 48h set `error` with details; automatic retries every 6h.  
  **AC:** Show `error_details.type=connection_lost`, `last_successful_sync` and “Reconnect” CTA.

- **US-7.4 (P0)** Archive (soft delete) and restore; validate on restore before `in_progress`.

- **US-7.5 (P1)** Pause/resume without archiving.

**US-7.3b (P0) — Error transition (AC)**
```gherkin
Given last successful sync was more than 48h ago
When reconnection fails
Then status becomes error
And UI shows last_successful_sync and a "Reconnect" CTA
```

---

## US-8 — Multi-Agent Coaching & Education
**Goal:** Route to BudgetAgent; provide contextual guidance.

- **US-8.1 (P0)** Route `saving|spending|debt|investment|income|net_worth` goals to **BudgetAgent** for tactics.

- **US-8.2 (P1)** Any goal can receive contextual content from **Education & Wealth Coach**.

- **US-8.3 (P1)** Reactive recommendations (e.g., “You’re at 80% of entertainment target; consider X”).

---

## US-9 — Goals UI/UX
**Goal:** Consistent visual states, progress, and views.

- **US-9.1 (P0)** Status badges (pending/in-progress/completed/error) with provided styles and state-specific quick actions.

- **US-9.2 (P0)** Progress bar and visible percentage for `in_progress`.

- **US-9.3 (P1)** Archived view with restore.

- **US-9.4 (P1)** Permanent delete from archive (with confirmation).

---

## US-10 — Persistence, Security & Audit
**Goal:** Store in Aurora Postgres with encryption, ACL, and audit.

- **US-10.1 (P0)** Persist goals in `goals(goal_id, user_id, version, goal_data JSONB, …)` per DDL.

- **US-10.2 (P0)** Encrypt at rest; verify `user_id` on every operation.

- **US-10.3 (P0)** Keep audit trail `created_at`, `updated_at` and key changes (e.g., recategorization).

- **US-10.4 (P1)** Version `goal_data` to support migrations without downtime.

---

## US-11 — Performance & Scalability
**Goal:** Low latency and horizontal scale.

- **US-11.1 (P0)** Cache `in_progress` goals in memory.

- **US-11.2 (P0)** Run progress calculations **async** (non-blocking UI).

- **US-11.3 (P1)** Daily jobs to evaluate thresholds and dispatch alerts.

- **US-11.4 (P1)** Partition by `user_id` for horizontal scaling.

---

## US-12 — Integrations & Inter-System Communication
**Goal:** Clean coupling with accounts and other modules.

- **US-12.1 (P0)** Consume linked accounts (Plaid) and manual data via internal APIs; no shared storage with Memory module.

- **US-12.2 (P1)** Webhooks for third parties (activation, achieved, alert).

- **US-12.3 (P2)** `custom_query` basis (sandboxed) for advanced % goals.

---

## Definition of Done — V1 (Cross-cutting)
- Validate **ISO currencies**, **percentages (0–100)**, and **frequencies**.  
- **No forecasting / envelopes / earmarking** (out of scope V1).  
- **Accessibility AA** for badges, buttons, key text.  
- **Localization** of dates/currencies per user region.  
- Error logs and basic metrics (calc latency, sync retry rate).

---

## V2+ (Out of Scope)
- Budgeting with envelopes, trade-offs, earmarking.  
- Forecasting & “what-if”.  
- Automated contributions/simulations.  
- Collaborative (multi-user) goals.
