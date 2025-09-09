# 2. Agent Core Engine (Orchestrator Model)

This document details the architecture of Vera's "brain": the **Agent Core Engine**. This design uses a **Multi-Agent Orchestrator model** to support modularity, scalability, and the distinct feature set of Vera V1.

**Guiding Principles:**
- **Delegation over Execution:** A top-level Orchestrator agent delegates tasks to specialized agents rather than executing them with tools directly.
- **Specialization:** Each specialist agent has a single, well-defined responsibility, allowing for fine-tuned prompts and dedicated tools.
- **Hosted on Managed Infrastructure:** The entire multi-agent system is deployed on **Amazon Bedrock AgentCore**, which can execute multiple agents in parallel.
- **Tier-Aware Execution:** The Orchestrator checks user tier (Free, Paid $5, Paid $10) and gates tool/agent access accordingly.
- **Safety & Observability:** Bedrock content filters wrap every model call; Langfuse captures traces/metrics; per-turn source attribution is emitted.

## Component 1: The Orchestrator Agent

The Orchestrator is the "Project Manager" of the system. It is a LangGraph agent whose primary purpose is to understand the user's intent and delegate the task to the appropriate specialist agent.

-   **Input:** Receives the user's request and high-level context.
-   **Primary Logic:**
    1.  **Tier & Consent Check:** Resolve user tier and channel; determine allowed capabilities (Free = Orchestrator + KB only; Paid $5/$10 = full specialists + memory).
    2.  **Intent Analysis:** Performs a semantic search against its **Procedural Memory** to find the most similar example and determine the user's goal.
    3.  **Delegation:** Invokes the chosen specialist agent(s) (e.g., `BudgetAgent`, `FinanceAgent`) based on the procedure, passing the necessary context.
    4.  **Moderation:** All prompts and completions pass through **Bedrock content filters**.
    5.  **Source Attribution:** Build a structured list of sources used (KB, Semantic/Episodic Memory, Client Financial Data Service, Postgres Budgets) to accompany the response.
    6.  **Tracing:** Emit Langfuse spans for each step and tool call with cost/latency.

### Per-turn user context injection (V1)
- The orchestrator retrieves a compact `user_context` header from Postgres on each turn and injects it into prompt construction. This header contains:
  - identity: preferred_name, pronouns, age
  - safety: blocked_categories, allow_sensitive
  - style: tone, verbosity, formality, emojis
  - location: city/region
  - locale: language, time_zone, currency_code, local_now_iso (computed at request time)
  - goals: string[] (or truncated hints)
  - income, housing
  - tier
  - accessibility: reading_level_hint, glossary_level_hint
  - budget_posture: active_budget, current_month_spend_summary (optional; prefer tool fetch)
  - proactivity: opt_in
  - household: dependents_count, household_size, pets
  - assets_high_level: string[]

Note: In V1, specialists only see this context via the orchestrator’s assembled prompt; they do not fetch `user_context` directly.

## Component 2: The Specialist Agents

These are the "subcontractors," each an expert in a specific domain. Each is a self-contained LangGraph agent with **read-only access** to the user's Semantic and Episodic memory.

### V1 Principal Specialist Agents:

1.  **`BudgetAgent`**
    -   **Purpose:** Guides users through creating, reviewing, and managing their budget.
    -   **Tools:**
        -   Reads/writes budget data to the **PostgreSQL database** via the `Personal Finance Engine`.
        -   Reads transaction data from the client-managed financial data service (read-only APIs).
        -   Has read-only access to the user's `Semantic Memory` to understand their financial goals.

2.  **`FinanceAgent`**
    -   **Purpose:** Handles analysis of a user's overall financial health, including debt, investments, and spending trends.
    -   **Tools:**
        -   Reads data from the client-managed financial data service (read-only APIs).
        -   Can query the `Textbook Knowledge Base` for financial concepts.
        -   Has read-only access to both `Episodic` and `Semantic` memory to understand the user's history and stated goals.

3.  **`Education & Wealth CoachAgent`**
    -   **Purpose:** Financial education and supportive, empathetic dialogue. Answers definitional questions via curated KB; adapts tone using mood/preferences.
    -   **Tools:**
        -   Performs semantic search on the `Textbook Knowledge Base` to answer financial questions.
        -   Can read/write to a dedicated `notes` table in the PostgreSQL database (optional V1 scope).
        -   Acts as the default "Generalist Agent" for simple conversational turns or for users on a free tier.

## Streaming & Source Attribution

- **Real-time Events:** The Orchestrator publishes LangGraph Real-time Events for each step (routing decision, tool call start/finish, token deltas) and application-level events (e.g., `memory.candidate`, `memory.created`).
- **Client Streaming:** Channel adapters stream events and tokens to clients via WebSocket or Server-Sent Events (SSE).
- **Attribution Payload:** Each response includes a compact list of sources used, e.g. `{ type: "kb"|"memory_semantic"|"memory_episodic"|"dynamodb"|"postgres", ids: [...] }`.
- **Session Model:** Sessions reset on app/channel close; persistent personalization comes from Semantic/Episodic memory rather than long-lived sessions.

## Prompt Composition & Brand Voice Tuning

- **Stable Core + Inserts:** The Orchestrator builds prompts from stable blocks with placeholders: `[core_behavior] + [compliance_block] + [brand_voice] + [tier_constraints] + [task_context]`.
- **Config-Driven Brand Voice:** The `[brand_voice]` block is loaded at runtime from **AWS AppConfig** (per env/locale), with a fallback to `PROMPT_BRAND_VOICE_SNIPPET` env var. Example key: `app/vera/brand_voice/en-US`.
- **Specialist Inheritance:** Specialist agents inherit the `[brand_voice]` as a constraint (tone/vocabulary), not as a persona override, to prevent drift.
- **Caching & Fallbacks:** Cache the block with a short TTL; if AppConfig is unavailable, use env fallback; surface version and source.
- **Tracing:** Each turn is tagged in Langfuse with `brand_voice_version` and source (`appconfig|env`).
