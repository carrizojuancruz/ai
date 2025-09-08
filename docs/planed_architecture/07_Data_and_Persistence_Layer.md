# 7. Data and Persistence Layer

A robust and well-designed data layer is essential for the security, scalability, and performance of the Vera platform. Our strategy is to use a polyglot persistence approach, selecting the best database technology for each specific type of data and knowledge component.

All data will be encrypted both in transit and at rest, and all services will connect to databases using secure IAM roles and credentials managed by AWS Secrets Manager.

## Security & Compliance (V1, US-only)
- **Regions:** All data is stored and processed in US AWS regions for V1.
- **Encryption at Rest:** Aurora Postgres, DynamoDB, S3, OpenSearch/pgvector use KMS-managed CMKs per environment.
- **Secrets Management:** Access tokens and credentials stored in AWS Secrets Manager; rotation policies applied.
- **Audit Logging:** Write access to memory/artifacts and privileged operations are logged with user, time, and source.
- **PII Redaction:** Logs and traces redact PII; structured fields only.

## 1. User & Application Database

This database stores core user profile information and other central application data, including structured financial plans like budgets.

-   **Technology:** **Amazon Aurora (PostgreSQL compatible)**.
-   **Why?** This data is structured, relational, and requires high integrity. A relational database is the standard and best fit for this purpose.
-   **High-Level Schemas:**
    -   **`users` table:** `user_id`, `email`, `hashed_password`, `subscription_tier`.
    -   **`budgets` table (mutable, standardized schema with version/audit):**
        -   `budget_id` (Primary Key, UUID)
        -   `user_id` (Foreign Key to `users`)
        -   `version` (INT) – increments on update to preserve history
        -   `budget_name` (VARCHAR)
        -   `category_limits` (JSONB) - e.g., `{ "dining": 500, "groceries": 800 }`
        -   `is_active` (BOOLEAN)
        -   `created_at` (TIMESTAMP)
        -   `updated_at` (TIMESTAMP)
    -   **`notes` table:** `note_id`, `user_id`, `content`, `created_at`.

### `user_context` (V1 injection source)

A single, updatable record per user that captures small, high-signal attributes collected during onboarding. This is the only document we inject on every orchestrator request (specialists do not receive it directly in V1).

-   **Table:** `user_context`
-   **Key fields:**
    - `user_id` (UUID, PK/FK → `users`)
    - `identity` (JSONB) — `{ preferred_name, pronouns, age }`
    - `safety` (JSONB) — `{ blocked_categories: string[], allow_sensitive: boolean }`
    - `style` (JSONB) — `{ tone, verbosity, formality, emojis }`
    - `location` (JSONB) — `{ city, region }`
    - `locale` (JSONB) — `{ language, time_zone, currency_code }`  
      Note: `local_now_iso` is computed server-side at request time, not stored.
    - `goals` (JSONB) — `string[]` (store full list; orchestrator may inject top 1–2 as hints)
    - `income` (JSONB)
    - `housing` (JSONB)
    - `tier` (TEXT)  
      Note: canonical tier also exists in `users`; expose via view or keep synchronized.
    - `accessibility` (JSONB) — `{ reading_level_hint, glossary_level_hint }`
    - `budget_posture` (JSONB) — `{ active_budget: boolean, current_month_spend_summary: JSONB|null }`  
      Recommendation: fetch live spend summaries via client financial data service; avoid stale large blobs.
    - `proactivity` (JSONB) — `{ opt_in: boolean }`
    - `household` (JSONB) — `{ dependents_count: int, household_size: int, pets: string[] }`
    - `assets_high_level` (JSONB) — `string[]` (e.g., ["checking","savings","401k"])  
      Detailed balances come from tools, not stored here.
    - `updated_at` (TIMESTAMP)

Injection policy (V1)
- Inject at orchestrator only, every request: a compact header derived from `user_context` (≤1 KB). Specialists receive only what the orchestrator includes in their prompts.
- Heavy or live data (spend summaries, balances) is fetched on demand via tools and not injected.

## 2. Financial Data (Client-Managed)

Financial account and transaction data is provided by the client via an external service. We do not ingest Plaid or maintain a local mirror.

-   **Technology:** Client-owned. We integrate over HTTPS with authentication.
-   **Why?** Client consolidates data; we avoid duplicating ingestion, storage, and compliance scope.
-   **Access Pattern:** Read-only APIs (balances, transactions, summaries). Optional event/webhook integration for triggers.

### PII Handling (V1)
- Do not store raw transactions. If short-term caching is necessary, store non-PII summaries with strict TTL.
- Redact PII in logs/traces; enforce minimum fields returned from client service.

## 3. Textbook Knowledge Base (Vector DB)

This database powers the Retrieval-Augmented Generation (RAG) system by storing and indexing Vera's curated "textbook" knowledge.

-   **Technology:** **Amazon OpenSearch Serverless** or **Amazon RDS for PostgreSQL with `pgvector`**.
-   **Why?** This database needs to store text chunks and their corresponding vector embeddings for efficient semantic search.
-   **High-Level Schema (`knowledge_chunks` table):** `chunk_id`, `source_document_url`, `content_text`, `embedding_vector`.

## 4. Conversational Memory (Managed by AgentCore)

This is the stateful memory of the conversation itself and is **fully managed by the Bedrock AgentCore service**. We do not provision or manage this database directly. It is comprised of two logical parts, both of which are tagged with categories and timestamps:

-   **a. Episodic Memory (Raw Chat History)**
-   **b. Semantic Memory (Key-Fact Summary)**

## 5. Artifacts (User-Facing Structured Outputs)

Artifacts are first-class records produced or acknowledged during interactions. They are persisted to enable retrieval and auditing.

-   **Checklists (manual update in V1):**
    -   Updates occur in two ways: (1) user clicks in a checklist UI; (2) user confirms completion in chat.
    -   Table: **`checklist_entries`**
        -   `entry_id` (UUID, PK)
        -   `user_id` (FK)
        -   `label` (VARCHAR)
        -   `status` (ENUM: `pending`, `done`)
        -   `source` (ENUM: `ui_click`, `chat_confirmation`)
        -   `category` (VARCHAR)
        -   `created_at` (TIMESTAMP)
        -   `updated_at` (TIMESTAMP)

-   **Guides & Education (delivered resources log):**
    -   Persist references to education resources provided to the user, so they can revisit later.
    -   Table: **`education_resources_delivered`**
        -   `delivery_id` (UUID, PK)
        -   `user_id` (FK)
        -   `title` (VARCHAR)
        -   `source_url` (VARCHAR)
        -   `conversation_id` (VARCHAR)
        -   `snapshot_text` (TEXT, optional)
        -   `delivered_at` (TIMESTAMP)

-   **Budgets:**
    -   Budgets are editable (mutable) using a standardized schema. Each update increments `version` and records `updated_at`. Prior versions are preserved via versioning/audit.

-   **Reports (PDF/Image):**
    -   Binary assets are stored in **Amazon S3**; metadata is recorded in Postgres.
    -   Table: **`reports`**
        -   `report_id` (UUID, PK)
        -   `user_id` (FK)
        -   `report_type` (VARCHAR)
        -   `format` (ENUM: `pdf`, `png`, `jpg`)
        -   `s3_key` (VARCHAR)
        -   `generated_by_agent` (VARCHAR)
        -   `created_at` (TIMESTAMP)

## 6. Manual Assets (Houses, Cars, etc.)

Beyond financial account data, users may register assets manually (e.g., homes, vehicles). Include in V1 if within scope; otherwise, design now for easy addition later.

-   Table: **`user_assets`**
    -   `asset_id` (UUID, PK)
    -   `user_id` (FK)
    -   `asset_type` (ENUM: `house`, `car`, `other`)
    -   `name` (VARCHAR)
    -   `estimated_value` (NUMERIC, optional)
    -   `metadata` (JSONB)
    -   `created_at` (TIMESTAMP)
    -   `updated_at` (TIMESTAMP)
