# 5. Core Applications & Backend Services

This document details the primary application components and the backend services that support the Agent Core Engine.

## Core Application Components

These are applications that contain core business logic and are central to Vera's operation.

### 1. Agent Core Engine (Orchestrator & Specialists)

-   **Description:** The primary intelligence of the platform, composed of a top-level **Orchestrator Agent** that delegates tasks to a suite of **Specialist Agents**.
-   **Technology:** Python, LangGraph, hosted on **Amazon Bedrock AgentCore**.
-   **Details:** See `02_Agent_Core_Engine.md` for a full breakdown.

### 2. Heuristics Engine (Proactive Nudges V1)

-   **Description:** A lightweight, serverless component responsible for initiating proactive engagement with users based on a simple set of rules.
-   **Technology:** **AWS Lambda** (Python), triggered by **Amazon EventBridge** (cron + event rules).
-   **Trigger Sources (V1):**
    -   Time-based schedules (daily/weekly checks)
    -   Financial updates (client-provided events/webhooks or scheduled polling)
    -   In-app/user events (e.g., onboarding complete, budget created/updated, goal milestone dates)
    -   Memory-derived signals (e.g., new preference detected, streak updates)
-   **Responsibilities:**
    -   Evaluate heuristics when a trigger arrives; some rules may query the client-managed financial data service or Postgres as needed.
    -   Deduplicate and rate-limit nudges; respect quiet hours and user notification preferences.
    -   Construct a payload (with explainability + source attribution) and invoke the **Agent Orchestrator** to craft and deliver the message.
    -   Designed to evolve into a richer rule engine later without affecting the agent architecture.

## Backend Services (Tools)

These backend services encapsulate specific business logic and are called as "tools" by the Specialist Agents.

### 1. Client Financial Data Service (External)

-   **Description:** An external, client-managed service that provides read APIs over financial data (accounts, transactions, summaries). We do not ingest Plaid or maintain a local mirror.
-   **Technology:** N/A (client-owned). We integrate via HTTPS.
-   **Responsibilities (our side):**
    -   Consume client-provided read APIs for financial insights needed by agents.
    -   Optionally cache lightweight summaries transiently for performance (no raw transaction storage).
    -   Optionally consume client webhooks/events to trigger heuristics, or fall back to scheduled polling.
-   **Example API Calls (client-provided):** `GET /financial/v1/accounts/{id}/balance`, `POST /financial/v1/transactions/query`, `GET /financial/v1/transactions/summary`.

### 2. User Management Service

-   **Description:** Authentication, user profiles, and subscription tiers.
-   **Technology:** Node.js, Python, or Go, hosted on AWS Fargate or Lambda. Integrates with Amazon Cognito.
-   **Responsibilities:**
    -   User registration, login, and profile management.
    -   Managing user subscription tiers (Free, Paid $5, Paid $10) and payment method setup for monthly billing.
    -   Emitting user and app events (e.g., onboarding_completed, payment_method_added, tier_changed) to EventBridge.
-   **API Endpoints:** `GET /users/{userId}/profile`, `GET /users/{userId}/tier`.

### 3. Knowledge Base Service (RAG)

-   **Description:** A Retrieval-Augmented Generation (RAG) service that provides factual, curated answers to general financial questions.
-   **Technology:** Amazon Bedrock with a Knowledge Base.
-   **Responsibilities:**
    -   Storing and indexing a curated library of financial content from whitelisted sites.
    -   Providing a simple search API (`GET /search?query=...`) for any agent to use as a tool.

## Moderation & Guardrails
- **Bedrock Content Filters:** All model calls (orchestrator and specialists) are wrapped with Bedrock safety filters.
- **Blocked Topics:** Enforced pre-response based on user list.

## Observability & Tracing
- **Langfuse Integration:** All requests, tool calls, and model invocations are traced with timing, cost, and prompt/version metadata.
- **Real-time Events:** The Agent Core emits LangGraph Real-time Events consumed by channel adapters for client streaming.

## Configuration
- **Brand Voice Source:** Brand voice prompt insert stored in **AWS AppConfig** (per env/locale). Fallback to **SSM Parameter Store** or `PROMPT_BRAND_VOICE_SNIPPET` env var.
- **Client:** A lightweight config client fetches and caches the snippet (TTL), with circuit breaker and metrics.
