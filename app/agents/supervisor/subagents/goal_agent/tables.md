# PostgreSQL Tentative Database Schema for Goals

## Main Tables

### 1. goals
Main table storing all goal information with JSONB fields for complex nested structures.

```sql
CREATE TABLE goals (
    goal_id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    
    -- Goal definition
    goal_title VARCHAR(255) NOT NULL,
    goal_description TEXT,
    
    -- Categorization
    category_value VARCHAR(100) NOT NULL,
    nature_value VARCHAR(100) NOT NULL,
    
    -- Frequency configuration (JSONB for flexibility)
    frequency JSONB NOT NULL,
    
    -- Amount configuration (JSONB for flexibility)
    amount JSONB NOT NULL,
    
    -- Evaluation settings
    evaluation JSONB NOT NULL,
    
    -- Optional configurations
    thresholds JSONB,
    reminders JSONB NOT NULL DEFAULT '{"items": []}',
    
    -- Status and progress
    status_value VARCHAR(50) NOT NULL DEFAULT 'pending',
    progress JSONB,
    
    -- Additional data
    metadata JSONB,
    idempotency_key VARCHAR(255),
    
    -- Audit trail
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT chk_version_positive CHECK (version > 0),
    CONSTRAINT chk_status_valid CHECK (status_value IN ('pending', 'in_progress', 'completed', 'paused', 'off-track', 'deleted'))
);
```

### 2. goal_categories (Reference table)
Lookup table for valid goal categories.

```sql
CREATE TABLE goal_categories (
    id SERIAL PRIMARY KEY,
    value VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Initial data
INSERT INTO goal_categories (value, description) VALUES 
    ('saving', 'Savings goals'),
    ('spending', 'Spending goals'),
    ('investment', 'Investment goals'),
    ('debt', 'Debt reduction goals');
```

### 3. goal_natures (Reference table)
Lookup table for valid goal natures/directions.

```sql
CREATE TABLE goal_natures (
    id SERIAL PRIMARY KEY,
    value VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Initial data
INSERT INTO goal_natures (value, description) VALUES 
    ('increase', 'Goals to increase something'),
    ('decrease', 'Goals to decrease something'),
    ('maintain', 'Goals to maintain current level');
```

## Indexes

```sql
-- Primary access patterns
CREATE INDEX idx_goals_user_id ON goals (user_id);
CREATE INDEX idx_goals_status ON goals (status_value);
CREATE INDEX idx_goals_user_status ON goals (user_id, status_value);
CREATE INDEX idx_goals_created_at ON goals (created_at);
CREATE INDEX idx_goals_updated_at ON goals (updated_at);

-- JSONB indexes for common queries
CREATE INDEX idx_goals_frequency_type ON goals USING GIN ((frequency->>'type'));
CREATE INDEX idx_goals_amount_type ON goals USING GIN ((amount->>'type'));
CREATE INDEX idx_goals_category ON goals (category_value);
CREATE INDEX idx_goals_nature ON goals (nature_value);

-- Composite indexes for complex queries
CREATE INDEX idx_goals_user_category_status ON goals (user_id, category_value, status_value);
```

## JSON Schema Examples

### frequency field examples:

**Recurrent goal:**
```json
{
  "type": "recurrent",
  "specific": null,
  "recurrent": {
    "unit": "month",
    "every": 1,
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": null,
    "anchors": null
  }
}
```

**One-time goal:**
```json
{
  "type": "one-time",
  "specific": {
    "target_date": "2025-12-31T00:00:00Z"
  },
  "recurrent": null
}
```

### amount field examples:

**Percentage-based:**
```json
{
  "type": "percentage",
  "absolute": null,
  "percentage": {
    "target_pct": "20",
    "of": {
      "income": null
    }
  }
}
```

**Absolute amount:**
```json
{
  "type": "absolute",
  "absolute": {
    "currency": "USD",
    "target": "3000"
  },
  "percentage": null
}
```

### evaluation field example:
```json
{
  "aggregation": "sum",
  "direction": "≥",
  "rounding": "none",
  "source": "linked_accounts",
  "affected_categories": null
}
```

### thresholds field example:
```json
{
  "warn_progress_pct": "80",
  "alert_progress_pct": "90",
  "warn_days_remaining": null
}
```

### reminders field example:
```json
{
  "items": [
    {"type": "push", "when": "daily"},
    {"type": "email", "when": "weekly"},
    {"type": "push", "when": "1 week before"},
    {"type": "email", "when": "3 days before"}
  ]
}
```

### progress field example:
```json
{
  "current_value": "0",
  "percent_complete": "0",
  "updated_at": "2025-09-03T11:40:48.790079"
}
```

## Triggers

### Update version and timestamp trigger:
```sql
CREATE OR REPLACE FUNCTION update_goal_version_and_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.version = OLD.version + 1;
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_goals_update_version
    BEFORE UPDATE ON goals
    FOR EACH ROW
    EXECUTE FUNCTION update_goal_version_and_timestamp();
```

## Views

### Active goals view:
```sql
CREATE VIEW active_goals AS
SELECT 
    goal_id,
    user_id,
    version,
    goal_title,
    goal_description,
    category_value,
    nature_value,
    frequency,
    amount,
    evaluation,
    thresholds,
    reminders,
    status_value,
    progress,
    created_at,
    updated_at
FROM goals 
WHERE status_value NOT IN ('deleted');
```

### Goals with progress summary:
```sql
CREATE VIEW goals_summary AS
SELECT 
    g.goal_id,
    g.user_id,
    g.goal_title,
    g.category_value,
    g.nature_value,
    g.status_value,
    g.amount->>'type' as amount_type,
    CASE 
        WHEN g.amount->>'type' = 'absolute' THEN g.amount->'absolute'->>'target'
        WHEN g.amount->>'type' = 'percentage' THEN g.amount->'percentage'->>'target_pct'
    END as target_value,
    g.progress->>'current_value' as current_value,
    g.progress->>'percent_complete' as percent_complete,
    g.frequency->>'type' as frequency_type,
    g.frequency->'recurrent'->>'unit' as frequency_unit,
    g.created_at,
    g.updated_at
FROM goals g
WHERE g.status_value NOT IN ('deleted');
```

## Sample Queries

### Get all active goals for a user:
```sql
SELECT * FROM active_goals 
WHERE user_id = '3eac201d-36c2-4d7e-a9ac-07fe2b5c47e4'
ORDER BY created_at DESC;
```

### Get recurring monthly savings goals:
```sql
SELECT * FROM goals 
WHERE frequency->>'type' = 'recurrent'
  AND frequency->'recurrent'->>'unit' = 'month'
  AND category_value = 'saving'
  AND status_value = 'in_progress';
```

### Get goals approaching thresholds:
```sql
SELECT 
    goal_id,
    goal_title,
    progress->>'percent_complete' as progress_pct,
    thresholds->>'warn_progress_pct' as warn_threshold
FROM goals 
WHERE thresholds IS NOT NULL
  AND (progress->>'percent_complete')::numeric >= (thresholds->>'warn_progress_pct')::numeric
  AND status_value = 'in_progress';
```