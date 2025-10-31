## Finance Capture Agent - Production Plan (LangGraph-native, Human-in-the-loop)

### Goals
- Let users add Assets, Liabilities, or Manual Transactions (income/expenses) via chat.
- Enforce mandatory human confirmation before any write.
- Map categories to Vera POV while internally aligning to Plaid taxonomy (category + subcategory).
- Persist using internal APIs: assets (`/internal/assets/*`), liabilities (`/internal/liabilities/*`), manual transactions (`/internal/financial/transactions/manual/`).
- Use as much built-in LangGraph functionality as possible (StateGraph, ToolNode, interrupts/human-in-the-loop, recursion limits, checkpointer).

### High-level Architecture
- Create a small subagent: `finance_capture_agent`.
- Supervisor delegates via a dedicated handoff tool `transfer_to_finance_capture_agent`.
- Subgraph nodes:
  1) parse_and_normalize → 2) fetch_taxonomy_if_needed → 3) map_categories → 4) validate_schema → 5) confirm_human → 6) persist → 7) handoff_back
- Use LangGraph:
  - `StateGraph` for the flow and `ToolNode` for HTTP/IO tools.
  - `interrupt()` to implement human-in-the-loop confirmation.
  - `MemorySaver` checkpointer (already used globally) for resilience.

### State contract (MessagesState + context)
- Input: `messages`, `configurable.user_id`, `configurable.thread_id`, `configurable.user_context` (for TZ).
- Output: `messages` with a concise result and a standard handoff-back message to supervisor.

### Nodes and responsibilities
1. parse_and_normalize
   - Nova Micro fast intent + slot extraction
     - Configure `NOVA_MICRO_MODEL_ID` (Bedrock) with low temperature and small max tokens.
     - Strict JSON-only response schema with allowed enums and keys.
     - Extract: `kind in {asset, liability, manual_tx}`, and slots: `name`, `amount`, `currency_code`, `date`, `merchant_or_payee`, `notes`.
     - Validate JSON; on parse/enum failure, fall back to main LLM follow-up questions.
    - Log latency and confidence flags; trace input/output via Langfuse.
  - Implementation — completed (see `app/agents/supervisor/finance_capture_agent/nova.py`).
   - Normalize: currency (ISO-4217 uppercase), amount (Decimal), date (user TZ → ISO-8601 date), name strings.
   - If required fields missing, ask targeted follow-ups (stay within agent node; bounded via recursion_limit).

2. fetch_taxonomy_if_needed (ToolNode or model-bound tool call)
   - Only for `manual_tx`.
   - Call `get_taxonomy(scope)` with scope in {`income`, `expenses`, `primaries`, `grouped`} based on the user request/context.
   - Cache taxonomy for the turn to reduce calls.

3. map_categories
   - For manual_tx: choose Plaid category + subcategory strictly from allowed sets returned by `get_taxonomy`.
   - Derive Vera POV category using centralized mapping table.
   - For asset/liability: choose from hardcoded enums (constants module); optional subcategory if defined.

4. validate_schema
   - Validate with Pydantic models: `AssetCreate`, `LiabilityCreate`, `ManualTransactionCreate`.
   - Cross-field rules (e.g., non-negative amounts; due date ≥ today; recurring implies frequency).

5. confirm_human (LangGraph interrupt)
   - Render compact summary:
     - Asset: name, category, estimated_value, currency.
     - Liability: name, category, principal_balance (+ optional fields).
     - Manual Tx: amount, currency, date, merchant/payee, Plaid category/subcategory, Vera POV.
   - `interrupt({ summary, draft })` and wait for Approve or Edit.
   - If Edit: re-collect missing/updated fields and loop back to validate → confirm.

6. persist (ToolNode)
   - Route by `kind`:
     - `persist_asset(**kwargs)` → POST `/internal/assets/user/{user_id}`.
     - `persist_liability(**kwargs)` → POST `/internal/liabilities/user/{user_id}`.
     - `persist_manual_transaction(**kwargs)` → POST `/internal/financial/transactions/manual/` (API decides income vs expense from taxonomy).
   - Idempotency:
     - Manual Tx: deterministic `external_transaction_id = 'manual:' + sha256(user_id|date|amount|merchant|taxonomy_category|taxonomy_subcategory)` if supported; else pre-check via GET and client-side dedupe key cache for the turn.
     - Asset/Liability: pre-check by name+category via GET lists; otherwise rely on backend dedupe if present.

7. handoff_back
   - Emit concise success message with persisted IDs.
   - Return control to supervisor using the standard handoff-back messages.

### Tools (kwargs-first signatures) — implemented
- `get_taxonomy(scope: Literal['income','expenses','primaries','grouped']) -> dict`
  - GET the relevant taxonomy endpoint.
- `persist_asset(**kwargs) -> dict`
  - POST `/internal/assets/user/{user_id}`; payload from validated schema.
- `persist_liability(**kwargs) -> dict`
  - POST `/internal/liabilities/user/{user_id}`; payload from validated schema.
- `persist_manual_transaction(**kwargs) -> dict`
  - POST `/internal/financial/transactions/manual/`; include Plaid category/subcategory; respect idempotency key.

### Category Mapping (Vera POV over Plaid) — implemented
- Principles
  - Assets & Liabilities are manually curated categories (hardcoded enums).
  - Only Income and Expenses map from Plaid category → Plaid subcategory → Vera POV.
  - The agent must pick allowed Plaid values and return Vera POV for UX; persistence uses Plaid values as needed by APIs.

- Income mappings
  - Income → Wages → Vera POV: Salary & Wages
  - Income → Dividends, Interest earned, Investment and retirement funds → Vera POV: Investment Income
  - Income → Retirement pension → Vera POV: Retirement Income
  - Income → Tax refund, Unemployment → Vera POV: Government Benefits
  - Income → Other income → Vera POV: Other Income
  - Income → Account transfer, Cash advances and loans, Deposit, Other transfer in, Savings → Vera POV: Transfers & Deposits

- Expense mappings
  - Food & Dining → [Beer wine and liquor, Coffee, Fast food, Groceries, Other food and drinks, Restaurant, Vending machines] → Vera POV: Food & Dining
  - Shopping & Entertainment → [Bookstores and newsstands, Clothing and accessories, Convenience stores, Department stores, Discount stores, Electronics, Gift and novelties, Office supplies, Online marketplaces, Other general merchandise, Pet supplies, Sporting goods, Superstores, Tobacco and vape, Casinos and gambling, Music and audio, Other entertainment, Sporting events amusement parks, TV and movies, Video games] → Vera POV: Shopping & Entertainment
  - Housing & Utilities → [Rent, Gas and electricity, Internet and cable, Other utilities, Sewage and waste management, Telephone, Water] → Vera POV: Housing & Utilities
  - Transportation & Travel → [Bikes and scooters, Gas, Other transportation, Parking, Public transit, Taxis and ride shares, Tolls, Flights, Lodging, Other travel, Rental cars] → Vera POV: Transportation & Travel
  - Healthcare & Personal Care → [Dental care, Eye care, Nursing care, Other medical, Pharmacies and supplements, Primary care, Veterinary services, Gyms and fitness centers, Hair and beauty, Laundry and dry cleaning, Other personal care] → Vera POV: Healthcare & Personal Care
  - Professional Services → [Accounting and financial planning, Automotive, Childcare, Consulting and legal, Education, Insurance, Other general services, Postage and shipping, Storage] → Vera POV: Professional Services
  - Debt & Government → [Car payment, Credit card payment, Mortgage payment, Other payment, Personal loan payment, Student loan payment, Donations, Government department and agencies, Other government and non profit, Tax payment] → Vera POV: Debt & Government
  - Home & Other (split) →
    - [ATM fees, Foreign transaction fees, Insufficient funds, Interest charge, Other bank fees, Overdraft fees, Uncategorized] → Vera POV: Fees & Other
    - [Furniture, Hardware, Other home improvement, Repair and maintenance, Security] → Vera POV: Home & Maintenance

- Asset categories (enums)
  - Real Estate, Vehicles, Electronics & Equipment, Luxury & Collectibles, Financial Assets, Other Assets

- Liability categories (enums)
  - Mortgages, Loans, Credit & Debt, Bills & Medical, Other Liabilities

- Implementation notes
  - Keep the mapping table centralized (constants) and versioned for easy updates.
  - The agent prompt must list only allowed Plaid categories/subcategories and instruct selection from those.
  - Vera POV is user-facing; persistence for manual transactions should include Plaid category/subcategory.

### Pydantic Schemas — implemented
- `AssetCreate`
  - name: str
  - category: Enum[RealEstate, Vehicles, ElectronicsEquipment, LuxuryCollectibles, FinancialAssets, OtherAssets]
  - estimated_value: Decimal (>= 0)
  - currency_code: str (ISO-4217)
  - is_active: bool = True

- `LiabilityCreate`
  - name: str
  - category: Enum[Mortgages, Loans, CreditDebt, BillsMedical, OtherLiabilities]
  - principal_balance: Decimal (>= 0)
  - minimum_payment_amount: Decimal | None
  - next_payment_due_date: date | None (>= today)
  - is_active: bool = True

- `ManualTransactionCreate`
  - amount: Decimal (>= 0)
  - currency_code: str (ISO-4217)
  - date: date (user TZ normalized)
  - merchant_or_payee: str
  - taxonomy_category: str (must be in taxonomy)
  - taxonomy_subcategory: str (must be in taxonomy for category)
  - notes: str | None
  - recurring: bool | None
  - frequency: Enum[weekly, biweekly, monthly, quarterly, yearly] | None

### Prompt & guardrails — implemented
- New system prompt: `finance_capture_agent_system_prompt`
  - Rules: mandatory confirm; only allowed taxonomy; never accept `user_id` from content; short, precise confirmations; ask for missing fields; keep tool calls minimal.
- Bind tools with the Bedrock model via `bind_tools`.
- Use `recursion_limit` and `MemorySaver` checkpointer from LangGraph.

### Supervisor wiring
- Add handoff tool: `transfer_to_finance_capture_agent` with guidelines (collect→map→validate→confirm→persist).
- Register node `finance_capture_agent` and edge to supervisor in `app/agents/supervisor/agent.py`.

### Observability & Security
- Langfuse callbacks on the agent (input drafts, taxonomy mapping, final writes).
- Structured logs with `user_id`, `thread_id`, `entity_kind`, `dedupe_key`, `request_id`.
- No PII beyond last4; strict field allowlist; parameterized HTTP payloads.

### Testing plan
- Unit: schema validation, normalization, taxonomy constraints, dedupe key.
- Integration: multi-turn approve/edit loops, HTTP error handling.
- E2E: supervisor→handoff→persist; idempotency (no duplicates on repeat).

### Rollout
- Feature flag in supervisor prompt.
- Start with manual_tx, then assets, then liabilities.
- Add admin-only verbose audit for initial rollout, disable later.

### Open items to confirm
- Whether `/internal/financial/transactions/manual/` supports an external idempotency key. If not, we'll pre-check GET and cache dedupe within the session.
- Any additional fields required by assets/liabilities POST payloads beyond schemas above.


