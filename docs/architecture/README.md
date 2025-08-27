# Vera V1 - Solution Architecture

This directory contains the comprehensive solution architecture for the **Vera V1** AI financial coach. This architecture is designed to be robust, scalable, and modular, directly supporting all features defined in the V1 project scope while establishing a strong foundation for future versions.

## Guiding Principles

- **Agent-First:** The core logic resides in a stateful, multi-agent system where a central **Orchestrator** delegates tasks to specialized agents.
- **Managed & Serverless:** We leverage AWS-managed services (Bedrock AgentCore, Lambda, EventBridge, SNS, managed databases) to minimize operational overhead and maximize scalability.
- **Decoupled Components:** Each part of the system has a single responsibility, allowing for independent development, testing, and deployment.
- **Pragmatic Proactivity:** For V1, proactive engagement is driven by a straightforward, code-driven **Heuristics Engine**, with a clear path to evolve into a more advanced system in the future.
- **Observability & Streaming:** Langfuse traces the full agent/tool graph; LangGraph Real-time Events stream step-by-step progress and partial tokens to clients.

## Tiers (V1)
- **Free (Not Logged):** Orchestrator + curated KB only; no specialists; no memory; no `user_context` injection.
- **Free (Logged):** Orchestrator + curated KB only; no specialists; no memory; does inject compact `user_context` from onboarding for personalization.
- **Paid ($5):** Full Orchestrator with specialist agents and memory.
- **Paid ($10):** Same as $5 with headroom for enhanced features/limits;

## Core Components

The architecture is broken down into several key components. Each component has a dedicated document providing detailed specifications.

1.  [**01_C4_Model_and_System_Diagram.md**](./01_C4_Model_and_System_Diagram.md)
    -   *Contains: High-level system diagrams using the C4 model to visualize the overall structure and interactions.*

2.  [**02_Agent_Core_Engine.md**](./02_Agent_Core_Engine.md)
    -   *Contains: A detailed breakdown of the central multi-agent system, including the **Orchestrator Agent** and the various **Specialist Agents**, built with LangGraph and hosted on Bedrock AgentCore.*

3.  [**03_Memory_and_Knowledge_System.md**](./03_Memory_and_Knowledge_System.md)
    -   *Contains: A specification for the four information components: **Semantic/Episodic Memory**, **Procedural Memory**, and the curated **Knowledge Base**.*

4.  [**05_Core_Applications_and_Backend_Services.md**](./05_Core_Applications_and_Backend_Services.md)
    -   *Contains: A description of the primary application components, including the **Heuristics Engine**, and the supporting backend services and tools the agents will use.*

5.  [**06_Omnichannel_Integration_Layer.md**](./06_Omnichannel_Integration_Layer.md)
    -   *Contains: The architectural plan for supporting multiple channels (Mobile App, WhatsApp, etc.), including streaming events and session reset behavior.*

6.  [**07_Data_and_Persistence_Layer.md**](./07_Data_and_Persistence_Layer.md)
    -   *Contains: The data schema and strategy for all persistence layers that support the application, with encryption-at-rest and US-region scope for V1.*

## Feature Mapping

This architecture directly supports the following key Vera V1 features:

-   **Credit & Debt Coach:** Enabled by the specialized `DebtCoachAgent`.
-   **My Tools Hub / Budget & Goal Builder:** Enabled by the specialized `BudgetBuilderAgent`.
-   **Engagement & Nudges / Personality & Copy:** Driven by the `Heuristics Engine` and the agents' sophisticated memory and LLM-powered personality.
-   **Visualization & Insights:** Enabled by the specialized `InsightsAgent`.
-   **Financial Coaching & Guidance:** The combination of specialist agents and the `Knowledge Base` allows for deep, contextual guidance.

## Vera V1 Summary (Features & Components)

- **What Vera does**
  - Personalized life-and-money coaching with empathetic tone
  - Answers finance questions with cited, curated KB
  - Builds and updates budgets; summarizes progress
  - Surfaces basic finance snapshots from your transaction mirror
  - Proactive nudges with "why you received this" and deep links

- **Agents (Multi‑Agent on Bedrock AgentCore)**
  - Orchestrator: intent routing, tier gating, safety filters, source attribution
  - Specialists (3):
    - BudgetAgent: create/update mutable, versioned budgets in Postgres; summarize latest
    - FinanceAgent (V1 minimal): 4–5 basic checks from client financial data service (trends/spikes/ratios)
    - Education & Wealth Coach: empathetic KB‑grounded education; memory‑aware tone

- **Memory & Knowledge**
  - Semantic + Episodic (read‑only to specialists), with category tags and timestamps
  - Procedural memory for routing examples (orchestrator‑only)
  - Curated KB (3–4 whitelisted domains) with weekly recrawl and citation
  - Memory Registry: user‑visible list with delete and edit
  - User Context: compact profile persisted in Postgres and injected by the Orchestrator on every turn (identity, safety, style, location/locale, goals, income, housing, tier, accessibility, budget posture, proactivity, household, assets_high_level)

-- **Data & Persistence**
  - Financial data: provided by client via external service (read-only APIs). No local Plaid ingestion/mirror.
  - Budgets: mutable with versioning (`version`, `updated_at`) in Postgres
  - Reports/Artifacts metadata in Postgres; binaries in S3 (future)

- **Proactive (Heuristics V1)**
  - EventBridge‑driven triggers (time, client events/webhooks, in‑app signals, memory‑derived)
  - Quiet hours, snooze, dedupe; payload includes explainability + attribution

- **Omnichannel & Streaming**
  - Channels via API Gateway + Lambda adapters (mobile chat, messaging)
  - SSE streaming of LangGraph real‑time events + application events (memory.candidate/created, conversation.summary)
  - Sessions reset per channel close; personalization from memory

- **Safety, Observability, Config**
  - Bedrock content filters on all model calls
  - Langfuse tracing (spans, prompts/versions, cost)
  - Brand voice via ENV snippet (AppConfig later), inherited by specialists

- **Tiers (V1)**
  - Free (Not Logged): Orchestrator + KB; no memory; no specialists; no user_context injection
  - Free (Logged): Orchestrator + KB; no memory; no specialists; user_context injected
  - Paid ($5): full orchestrator + specialists + memory
  - Paid ($10): full orchestrator + specialists + memory (future enhanced features/limits)

- **Scope & Region**
  - US‑only; KMS encryption at rest, Secrets Manager, audit logs for writes
