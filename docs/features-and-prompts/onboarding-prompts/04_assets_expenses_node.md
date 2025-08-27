# Node 4: Assets & Expenses (Optional)

## Description
Optional node that captures basic information about significant assets and fixed expenses.

## Node Type
Combination of `single_choice` and `multi_choice` with conditional flow

## Step Flow

### Step 4.1: Significant Assets
```json
{
  "id": "significant_assets",
  "type": "multi_choice",
  "prompt": "Do you have any assets worth considering?",
  "target_key": "assets.types",
  "required": false,
  "choices": [
    {
      "id": "home_owned",
      "label": "Own my home",
      "value": "home_owned",
      "synonyms": ["house", "property", "real estate"]
    },
    {
      "id": "investment_accounts",
      "label": "Investment accounts",
      "value": "investment_accounts", 
      "synonyms": ["investments", "stocks", "funds"]
    },
    {
      "id": "retirement_accounts",
      "label": "Retirement accounts",
      "value": "retirement_accounts",
      "synonyms": ["retirement", "401k", "IRA"]
    },
    {
      "id": "none_significant",
      "label": "Nothing significant",
      "value": "none_significant",
      "synonyms": ["nothing", "none", "no assets"]
    }
  ]
}
```

### Step 4.2: Fixed Monthly Expenses
```json
{
  "id": "fixed_expenses",
  "type": "multi_choice",
  "prompt": "What are your main fixed monthly expenses?",
  "target_key": "expenses.fixed_categories",
  "required": true,
  "choices": [
    {
      "id": "rent_mortgage",
      "label": "Rent or mortgage",
      "value": "rent_mortgage",
      "synonyms": ["rent", "mortgage", "housing"]
    },
    {
      "id": "car_payment",
      "label": "Car payment",
      "value": "car_payment",
      "synonyms": ["car", "auto", "vehicle"]
    },
    {
      "id": "utilities",
      "label": "Utilities",
      "value": "utilities", 
      "synonyms": ["electric", "water", "gas", "internet"]
    },
    {
      "id": "minimal_expenses",
      "label": "Very minimal expenses",
      "value": "minimal_expenses", 
      "synonyms": ["minimal", "basic", "simple"]
    }
  ]
}
```

## Flow Logic

```python
def determine_next_node(state: OnboardingState) -> str:
    # Check for conditional nodes based on mentioned topics
    if should_show_home_node(state):
        return "home_node"
    elif should_show_family_node(state):
        return "family_unit_node"
    elif should_show_health_node(state):
        return "health_coverage_node"
    
    # If no conditional nodes apply, go to Plaid
    return "plaid_integration"

def should_show_node(state: OnboardingState) -> bool:
    income_range = state["answers"].get("money.annual_income_range")
    age_range = state["answers"].get("identity.age_range") 
    
    if income_range in ["under_25k", "25k_49k"]:
        return False
        
    if age_range in ["under_18", "18_24"]:
        return False
        
    return True
```

## Implementation Notes

- This node is completely optional
- Information helps with personalized recommendations
- Users can skip if uncomfortable sharing
- Simple structure focusing on essential information only
