# Finance Agent Migration Plan: Replacing Math Agent with Plaid SQL Agent

## Executive Summary

This document outlines the comprehensive migration plan to replace the current math agent with a sophisticated finance agent capable of querying Plaid financial data from PostgreSQL tables. The new agent will handle natural language queries about accounts, transactions, balances, and spending patterns.

## Current State Analysis

### Math Agent Current Implementation
- **Location**: `app/agents/supervisor/workers.py`
- **Function**: Simple LLM-based calculator
- **Integration**: Connected via supervisor's `assign_to_math_agent_with_description` tool
- **Response Format**: "The result is <result>"
- **Limitations**: Only handles basic mathematical calculations

### Supervisor Integration Points
```python
# Current math agent integration in supervisor/agent.py
assign_to_math_agent_with_description = create_task_description_handoff_tool(
    agent_name="math_agent", description="Assign task to a math agent."
)

# In supervisor graph
builder.add_node("math_agent", math_agent)
builder.add_edge("supervisor", "math_agent")
builder.add_edge("math_agent", "supervisor")
```

## Target Architecture

### Finance Agent Components

#### 1. Finance SQL Agent Worker
**Location**: `app/agents/supervisor/workers.py`
**Purpose**: Main entry point replacing math_agent()
**Key Features**:
- Parameter extraction from natural language
- SQL query generation for Plaid data
- Result formatting and analysis
- Error handling and fallbacks

#### 2. Parameter Extraction System
**Components**:
- **Finance Parameter Extractor**: LLM-based entity detection for financial queries
- **Entity Types**: accounts, transactions, balances, categories, date ranges
- **Validation**: Financial business rules and normalization

#### 3. Query Generation Engine
**Features**:
- Template-based SQL generation
- Support for joins between Plaid tables
- Aggregation and filtering logic
- Financial calculations (totals, averages, trends)

#### 4. Database Integration
**Tables**: 2-3 Plaid mirror tables
- `plaid_accounts`: Account information
- `plaid_transactions`: Transaction history
- `plaid_balances`: Account balances (optional)

## Model Selection (AWS Bedrock)

- Generation (primary): Anthropic Claude 3.7 Sonnet on Bedrock
  - Purpose: SQL synthesis, multi-step reasoning, tool use, chart planning
- Validation (secondary): Anthropic Claude 3.5 Haiku Standard on Bedrock
  - Purpose: fast schema/JSON/function-call conformance checks and query sanity

Operational notes:
- Use Sonnet for initial parameter extraction and SQL generation; run Haiku to validate structure and safety before execution.
- On validation failure or complex joins, escalate to Sonnet for a regeneration pass.

## Implementation Phases

### Phase 1: Core Finance Agent (Week 1-2)

#### Step 1.1: Create Finance Agent Worker
```python
async def finance_sql_agent(state: MessagesState) -> dict[str, Any]:
    """Finance agent for querying Plaid data from PostgreSQL."""
    # Extract parameters from user query
    # Generate SQL query
    # Execute query
    # Format results
    # Return structured response
```

#### Step 1.2: Database Configuration
```python
# Database configuration for Plaid tables
PLAID_DB_CONFIG = {
    "schema": "finance",
    "tables": {
        "accounts": "plaid_accounts",
        "transactions": "plaid_transactions",
        "balances": "plaid_balances"
    },
    "connection_string": os.getenv("PLAID_DB_CONNECTION")
}
```

#### Step 1.3: Basic Parameter Extraction
```python
FINANCE_ENTITIES = {
    "accounts": ["checking", "savings", "credit", "investment"],
    "categories": ["food", "transport", "entertainment", "utilities"],
    "time_periods": ["last week", "last month", "this month", "last 30 days"]
}
```

### Phase 2: Advanced Features (Week 3-4)

#### Step 2.1: Complex Query Patterns
- Multi-table joins (accounts + transactions)
- Date range filtering
- Category-based aggregations
- Spending pattern analysis

#### Step 2.2: Financial Business Rules
```python
# Account type normalization
ACCOUNT_TYPE_MAPPING = {
    "depository": ["checking", "savings"],
    "credit": ["credit card", "line of credit"],
    "investment": ["brokerage", "retirement"]
}

# Transaction category standardization
TRANSACTION_CATEGORIES = [
    "food_and_drink", "transportation", "entertainment",
    "utilities", "healthcare", "shopping", "transfer"
]
```

#### Step 2.3: Result Analysis
- Spending trend identification
- Budget vs actual comparisons
- Anomaly detection
- Financial insights generation

### Phase 3: Supervisor Integration (Week 5-6)

#### Step 3.1: Update Supervisor Worker Import
```python
# Update app/agents/supervisor/workers.py import
from .workers import finance_sql_agent  # instead of math_agent
```

#### Step 3.2: Update Supervisor Agent Configuration
```python
# Update supervisor/agent.py
assign_to_finance_agent_with_description = create_task_description_handoff_tool(
    agent_name="finance_agent",
    description="Assign task to a finance agent for account and transaction queries."
)

# Update graph configuration
builder.add_node("finance_agent", finance_sql_agent)
builder.add_edge("supervisor", "finance_agent")
builder.add_edge("finance_agent", "supervisor")
```

#### Step 3.3: Update Supervisor Prompts
```python
# Update prompts to route financial queries instead of math
FINANCE_ROUTING_EXAMPLE = '''
User: "What's my spending on groceries last month?"
Assistant: Use finance_agent to query transaction data

User: "Show me my account balances"
Assistant: Use finance_agent to get current balances
'''
```

## Database Schema (Existing)

### public.unified_accounts
```sql
-- Key columns (as provided)
id uuid PRIMARY KEY,
user_id uuid NOT NULL,
name varchar NOT NULL,
description varchar NULL,
account_type varchar NOT NULL,
account_subtype varchar NULL,
account_number_last4 varchar NULL,
institution_name varchar NULL,
image_url varchar NULL,
external_account_id varchar NULL,
external_institution_id varchar NULL,
provider varchar NULL,
last_sync_at timestamptz NULL,
sync_status varchar NULL,
sync_error text NULL,
plaid_sync_cursor varchar NULL,
currency_code varchar NULL,
current_balance numeric NULL,
available_balance numeric NULL,
total_value numeric NULL,
credit_limit numeric NULL,
available_credit numeric NULL,
minimum_payment_amount numeric NULL,
next_payment_due_date timestamptz NULL,
last_payment_amount numeric NULL,
last_payment_date timestamptz NULL,
original_principal numeric NULL,
principal_balance numeric NULL,
interest_rate numeric NULL,
loan_term_months integer NULL,
origination_date timestamptz NULL,
maturity_date timestamptz NULL,
escrow_balance numeric NULL,
purchase_apr numeric NULL,
cash_advance_apr numeric NULL,
balance_transfer_apr numeric NULL,
special_financing_apr numeric NULL,
is_active boolean NULL,
is_overdue boolean NULL,
is_closed boolean NULL,
meta_data json NULL,
created_at timestamptz NOT NULL,
updated_at timestamptz NOT NULL
```

### public.unified_transactions
```sql
-- Key columns (as provided)
id uuid PRIMARY KEY,
user_id uuid NOT NULL,
account_id uuid NOT NULL,
transaction_type varchar NOT NULL,
amount numeric NOT NULL,
transaction_date timestamptz NOT NULL,
external_transaction_id varchar NULL,
currency_code varchar NULL,
name text NULL,
description text NULL,
notes text NULL,
merchant_name varchar NULL,
merchant_logo_url varchar NULL,
category_icon_url varchar NULL,
location_address varchar NULL,
location_city varchar NULL,
location_region varchar NULL,
location_postal_code varchar NULL,
location_country varchar NULL,
location_lat numeric NULL,
location_lon numeric NULL,
payment_channel varchar NULL,
authorized_date timestamptz NULL,
pending boolean NULL,
is_cancelled boolean NULL,
is_recurring boolean NULL,
is_subscription boolean NULL,
is_payment boolean NULL,
category varchar NULL,
category_detailed varchar NULL,
provider_tx_category varchar NULL,
provider_tx_category_detailed varchar NULL,
personal_finance_category json NULL,
security_id uuid NULL,
external_account_id varchar NULL,
fees numeric NULL,
price numeric NULL,
quantity numeric NULL,
settlement_date timestamptz NULL,
type varchar NULL,
subtype varchar NULL,
transaction_subtype varchar NULL,
meta_data json NULL,
created_at timestamptz NOT NULL,
updated_at timestamptz NOT NULL
```

## Query Patterns & Templates (public.unified_*)

### Basic Account Query
```sql
SELECT
    name,
    account_type,
    account_subtype,
    institution_name,
    account_number_last4,
    currency_code,
    available_balance,
    current_balance
FROM public.unified_accounts
WHERE user_id = $1
ORDER BY account_type, name;
```

### Transaction Aggregation Query (generic)
```sql
SELECT
    date_trunc('month', transaction_date)::date AS month,
    category,
    COUNT(*) AS transaction_count,
    SUM(amount) AS total_amount,
    AVG(amount) AS avg_amount
FROM public.unified_transactions
WHERE user_id = $1
  AND transaction_date BETWEEN $2 AND $3
GROUP BY 1, 2
ORDER BY month DESC, total_amount DESC;
```

### Category Totals (generic)
```sql
SELECT
    category,
    COUNT(*) AS transactions,
    SUM(amount) AS total_amount,
    AVG(amount) AS avg_transaction
FROM public.unified_transactions
WHERE user_id = $1
  AND transaction_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY category
ORDER BY total_amount DESC
LIMIT 10;
```


## Performance Considerations

### Database Optimization
- Proper indexing on user_id, dates, categories
- Query result caching
- Connection pooling
- Read replica usage for heavy queries

### Agent Performance
- Query template caching
- Parameter extraction optimization
- Result size limits
- Timeout handling

## Security Considerations

### Data Protection
- User data isolation
- Query parameter sanitization
- Result data filtering
- Audit logging

### API Security
- Authentication validation
- Rate limiting
- Query complexity limits
- Sensitive data masking

## Deployment Plan

### Environment Setup
1. Database schema creation
2. Connection string configuration
3. Environment variable setup
4. Agent configuration updates


### Monitoring & Alerting
1. Query success/failure rates
2. Response time tracking
3. Error rate monitoring
4. Database performance metrics


## Risk Mitigation

### Technical Risks
- Database performance under load
- Complex query handling
- LLM hallucination prevention
- Backward compatibility

### Business Risks
- User privacy concerns
- Financial data accuracy
- Regulatory compliance
- Cost of implementation

## Timeline & Milestones

### Week 1-2: Foundation
- [ ] Database schema design and implementation
- [ ] Basic finance agent worker creation
- [ ] Simple query patterns implementation
- [ ] Initial supervisor integration

### Week 3-4: Enhancement
- [ ] Advanced query patterns
- [ ] Financial business rules implementation
- [ ] Result analysis and insights
- [ ] Performance optimization

### Week 5-6: Production
- [ ] Comprehensive testing
- [ ] Supervisor prompt updates
- [ ] Security review and implementation
- [ ] Production deployment

## Next Steps

1. **Immediate**: Review and approve database schema
2. **Short-term**: Create basic finance agent worker
3. **Medium-term**: Implement parameter extraction and query generation
4. **Long-term**: Full integration and production deployment

---

## Appendices

### Appendix A: Current Math Agent Code
```python
async def math_agent(state: MessagesState) -> dict[str, Any]:
    system: str = (
        "You are a math assistant. Compute the result. Return 'The result is <result>'."
    )
    prompt: str = _get_last_user_message_text(state["messages"]) or "Answer the math question briefly."
    content: str = await call_llm(system, prompt)
    content = content or "I could not compute that right now."
    return {"messages": [{"role": "assistant", "content": content, "name": "math_agent"}]}
```

### Appendix B: Sample Financial Queries
1. "What's my account balance?"
2. "How much did I spend on groceries last month?"
3. "Show me my transactions from last week"
4. "What's my biggest expense category this month?"
5. "How much did I spend vs earn last quarter?"

### Appendix C: Plaid Data Structure Reference
- **Accounts**: Basic account information, types, and masks
- **Transactions**: Detailed transaction history with amounts, dates, categories
- **Balances**: Current and available balances for each account
- **Institutions**: Financial institution details and metadata

---

*This document serves as the comprehensive roadmap for migrating from math agent to finance agent. Implementation should follow the phases outlined above with regular reviews and adjustments based on testing results.*
