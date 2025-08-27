# Node 3: Income & Money

## Description
Skippable node that explores user's emotional relationship with money and captures basic income information to establish fundamental financial context. While valuable for personalization, users can skip if uncomfortable sharing financial details.

## Node Type
Combination of `multi_choice` and `single_choice`

## Step Flow

### Step 3.1: Feelings About Money
```json
{
  "id": "money_feelings",
  "type": "multi_choice", 
  "prompt": "Feelings about money in general",
  "target_key": "money.feelings",
  "required": true,
  "multi_min": 1,
  "multi_max": 3,
  "choices": [
    {
      "id": "stressed",
      "label": "It stresses me out",
      "value": "stressed_out",
      "synonyms": ["stress", "anxiety", "worry", "overwhelm"]
    },
    {
      "id": "figuring_out",
      "label": "I'm figuring it out",
      "value": "figuring_it_out", 
      "synonyms": ["learning", "confused", "trying", "studying"]
    },
    {
      "id": "feel_great",
      "label": "I feel great about it",
      "value": "feel_great_about_it",
      "synonyms": ["good", "calm", "secure", "confident"]
    },
    {
      "id": "indifferent", 
      "label": "Quite indifferent",
      "value": "quite_indifferent",
      "synonyms": ["indifferent", "neutral", "don't care", "normal"]
    }
  ]
}
```

### Step 3.2a: Annual Income (Open-ended)
```json
{
  "id": "annual_income_open_ended",
  "type": "free_text",
  "prompt": "What is your average annual income?",
  "target_key": "money.annual_income",
  "required": false,
  "validation_hints": {
    "expected_format": "dollar amount or number (e.g., $65000, 65k, 65000)",
    "fallback_to_ranges": true,
    "privacy_sensitive": true
  }
}
```

### Step 3.2b: Annual Income Range (Fallback)
```json
{
  "id": "annual_income_range",
  "type": "single_choice",
  "prompt": "Can you give us an approximate range so we can adjust the experience?",
  "target_key": "money.annual_income_range", 
  "required": true,
  "conditional_display": {
    "show_if": "annual_income_open_ended is empty, unclear, or user indicates reluctance"
  },
  "choices": [
    {
      "id": "under_25k",
      "label": "Less than $25k",
      "value": "under_25k",
      "synonyms": ["little", "minimum", "student", "part-time"]
    },
    {
      "id": "25k_49k", 
      "label": "$25k to $49k",
      "value": "25k_49k",
      "synonyms": ["entry", "junior", "beginner"]
    },
    {
      "id": "50k_74k",
      "label": "$50k to $74k", 
      "value": "50k_74k",
      "synonyms": ["middle", "average", "stable"]
    },
    {
      "id": "75k_100k",
      "label": "$75k to $100k",
      "value": "75k_100k", 
      "synonyms": ["good", "comfortable", "senior"]
    },
    {
      "id": "over_100k",
      "label": "More than $100k",
      "value": "over_100k",
      "synonyms": ["high", "executive", "professional"]
    },
    {
      "id": "prefer_not_say",
      "label": "I'd rather not to say",
      "value": "prefer_not_to_say",
      "synonyms": ["private", "don't want", "personal", "skip"]
    }
  ]
}
```

## Flow Logic

```python
def determine_next_node(state: OnboardingState) -> str:
    """
    Determines next node based on Income & Money responses
    """
    money_feelings = state["answers"].get("money.feelings", [])
    income = state["answers"].get("money.annual_income")
    income_range = state["answers"].get("money.annual_income_range")
    
    # Get effective income level (from exact or range)
    effective_income_level = get_effective_income_level(state)
    
    # If very stressed, skip optional nodes and go to Plaid
    if "stressed_out" in money_feelings:
        return "plaid_integration"
    
    # If high income or comfortable with money, show optional assets/expenses
    if effective_income_level in ["75k_100k", "over_100k"] or "feel_great_about_it" in money_feelings:
        return "assets_expenses_node"
    
    # Check for conditional nodes based on mentioned topics
    if should_show_home_node(state):
        return "home_node"
    elif should_show_family_node(state):
        return "family_unit_node"
    elif should_show_health_node(state):
        return "health_coverage_node"
    
    # Default flow to Plaid integration
    return "plaid_integration"

def should_show_income_range_step(state: OnboardingState) -> bool:
    """
    Determines if income range step should be shown
    """
    income = state["answers"].get("money.annual_income")
    
    # Show ranges if:
    # 1. No income provided at all
    # 2. User indicates reluctance ("don't want to say", "private", etc.)
    # 3. Income is unclear or invalid format
    if not income:
        return True
    
    # Check for reluctance indicators
    reluctance_indicators = [
        "don't want", "private", "rather not", "personal", 
        "skip", "prefer not", "none of your business"
    ]
    
    if any(indicator in income.lower() for indicator in reluctance_indicators):
        return True
    
    # Try to parse as number - if fails, show ranges
    try:
        # Remove common formatting and convert
        clean_income = income.replace("$", "").replace(",", "").replace("k", "000").replace("K", "000")
        float(clean_income)
        return False  # Valid number, don't show ranges
    except (ValueError, TypeError):
        return True  # Invalid format, show ranges
    
    return False

def get_effective_income_level(state: OnboardingState) -> str:
    """
    Get the effective income level from either exact income or selected range
    """
    income = state["answers"].get("money.annual_income")
    income_range = state["answers"].get("money.annual_income_range")
    
    # If we have a range selection, use it
    if income_range:
        return income_range
    
    # If we have exact income, convert to range
    if income:
        try:
            # Clean and parse income
            clean_income = income.replace("$", "").replace(",", "")
            
            # Handle "k" notation
            if "k" in clean_income.lower():
                clean_income = clean_income.lower().replace("k", "")
                income_num = float(clean_income) * 1000
            else:
                income_num = float(clean_income)
            
            # Convert to range categories
            if income_num < 25000:
                return "under_25k"
            elif 25000 <= income_num < 50000:
                return "25k_49k"
            elif 50000 <= income_num < 75000:
                return "50k_74k"
            elif 75000 <= income_num < 100000:
                return "75k_100k"
            else:
                return "over_100k"
                
        except (ValueError, TypeError):
            pass
    
    # Default to unknown if we can't determine
    return None
```

## Validations

- **money_feelings**: Minimum 1, maximum 3 selections
- **annual_income (open-ended)**: Optional, accepts various formats ($65000, 65k, 65000)
- **annual_income_range**: Required if open-ended income is not provided or unclear
- **budget_adjustment_experience**: Only show if shared income information
- **learning_motivation**: Required, must be valid value

## Edge Cases

1. **Very stressed about money**: Adapt tone and avoid overly detailed questions
2. **Irregular income**: Adjust budget-related questions  
3. **Prefers not to share income**: Respect boundaries and continue without pressure
4. **Highly motivated to learn**: Offer additional educational content

## System Prompts for Node

### Presentation Prompt
```
You are facilitating the income and money relationship phase of onboarding.

Objectives for this node:
1. Understand their emotional relationship with finances
2. Capture income information using two-step approach (respecting privacy)
3. Evaluate budgeting experience
4. Measure learning motivation

Income Collection Strategy:
- Start with open-ended: "What is your average annual income?" - let them share exact amount if comfortable
- If they don't respond, seem hesitant, or say they don't want to share, follow up naturally: "Can you give us an approximate range so we can adjust the experience?"
- Both approaches are equally valid - respect different comfort levels with financial privacy

Tone: Empathetic and non-judgmental. Money can be very sensitive - normalize all responses.
Focus: Emotional information is as important as numbers.
Privacy: Never pressure for information they don't want to share.
```

### Validation Prompt
```
Validate responses for Income & Money node:

- Feelings: At least one option, maximum 3 to maintain clarity
- Income (open-ended): Optional, accepts various formats; if unclear or missing, proceed to ranges
- Income (ranges): Required if open-ended was not provided or unclear
- Budget experience: Only ask if they shared income information
- Learning motivation: Required for planning educational content

If you detect financial stress or reluctance to share income, adapt tone to be more supportive and don't pressure for specific numbers.
```

## Financial Segmentation

### By Emotional Relationship
- **Stressed/Overwhelmed**: Focus on reassurance and basic education
- **Figuring Out**: Structured educational support
- **Confident**: Advanced optimization tools
- **Indifferent**: Motivation through goal-connection

### By Income Level
- **Under 50k**: Focus on budgeting and emergency fund
- **50k-100k**: Optimization and medium-term goals
- **100k+**: Investments and tax optimization
- **Irregular**: Cash flow management and planning

### By Learning Motivation
- **Low (1-2)**: Simple tools, automatic features
- **Medium (3)**: Digestible education, practical tips  
- **High (4-5)**: Deep content, detailed analysis

## Success Metrics

- **Emotional Engagement**: >80% select at least 2 feelings
- **Income Sharing**: >60% share income range
- **Learning Interest**: Clear distribution of motivation levels
- **Flow Optimization**: Correct routing based on emotional profile

## Implementation Notes

- Emotional information is critical for tone personalization
- Income range affects tool and goal recommendations
- Budgeting experience determines educational content level
- Learning motivation controls depth of explanations
- This node establishes the foundation for all subsequent financial recommendations
