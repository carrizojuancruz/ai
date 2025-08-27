# Node 5: Home (Optional)

## Description
Conditional node that explores user's housing situation to understand housing expenses, residential stability and possible housing-related goals. Only shown if user mentions housing, rent, mortgage, home buying, or living situation topics in nodes 1-3.

## Node Type
Combination of `single_choice` and `free_text` with complex conditional flow

## Eligibility Criteria

This node is shown only if ANY of the following conditions are met:
- User mentions housing, home, house, rent, mortgage, apartment in nodes 1-3
- User mentions wanting to buy a home or move
- User indicates housing costs as a concern
- User mentions living situation as a goal or problem
- User asks about home buying or real estate

## Step Flow

### Step 5.1: Housing Type
```json
{
  "id": "housing_type",
  "type": "single_choice",
  "prompt": "Type of home do you live in?",
  "target_key": "housing.type",
  "required": true,
  "choices": [
    {
      "id": "rent_apartment",
      "label": "Apartment",
      "value": "apartment",
      "synonyms": ["apartment", "flat", "unit", "rental"]
    },
    {
      "id": "rent_house",
      "label": "House",
      "value": "house",
      "synonyms": ["house", "home", "single family"]
    },
    {
      "id": "own_house",
      "label": "Own my home",
      "value": "own_house",
      "synonyms": ["own", "homeowner", "my house"]
    },
    {
      "id": "live_with_family",
      "label": "Live with family/friends",
      "value": "live_with_family",
      "synonyms": ["family", "parents", "roommates", "shared"]
    },
    {
      "id": "other_temporary",
      "label": "Other temporary situation",
      "value": "other_temporary",
      "synonyms": ["temporary", "transitional", "other"]
    }
  ]
}
```

### Step 5.2: Current Situation Satisfaction
```json
{
  "id": "housing_satisfaction",
  "type": "single_choice",
  "prompt": "How do you feel about your current housing situation?",
  "target_key": "housing.satisfaction",
  "required": true,
  "choices": [
    {
      "id": "very_happy",
      "label": "Very happy",
      "value": "very_happy",
      "synonyms": ["happy", "great", "perfect"]
    },
    {
      "id": "generally_good",
      "label": "Generally good",
      "value": "generally_good",
      "synonyms": ["good", "content", "satisfied"]
    },
    {
      "id": "okay_for_now", 
      "label": "It's okay for now",
      "value": "okay_for_now",
      "synonyms": ["temporary", "for now", "acceptable"]
    },
    {
      "id": "want_to_change",
      "label": "I'd like to change",
      "value": "want_to_change",
      "synonyms": ["change", "move", "improve"]
    },
    {
      "id": "need_to_change",
      "label": "Need to change soon",
      "value": "need_to_change",
      "synonyms": ["urgent", "need to", "bad"]
    }
  ]
}
```

### Step 5.3: Monthly Housing Cost (Conditional - Renters Only)
```json
{
  "id": "monthly_housing_cost",
  "type": "single_choice",
  "prompt": "Approximately how much do you pay per month for housing? (rent + basic utilities)",
  "target_key": "housing.monthly_cost_range",
  "required": false,
  "conditional_display": {
    "condition": "housing.type in ['apartment', 'house']"
  },
  "choices": [
    {
      "id": "under_500",
      "label": "Less than $500",
      "value": "under_500",
      "synonyms": ["cheap", "affordable", "low"]
    },
    {
      "id": "500_1000",
      "label": "$500 - $1,000",
      "value": "500_1000", 
      "synonyms": ["moderate", "average low"]
    },
    {
      "id": "1000_1500",
      "label": "$1,000 - $1,500",
      "value": "1000_1500",
      "synonyms": ["average", "standard"]
    },
    {
      "id": "1500_2500",
      "label": "$1,500 - $2,500",
      "value": "1500_2500",
      "synonyms": ["high", "city", "expensive"]
    },
    {
      "id": "over_2500",
      "label": "More than $2,500",
      "value": "over_2500", 
      "synonyms": ["very high", "premium", "luxury"]
    },
    {
      "id": "prefer_not_say",
      "label": "Prefer not to say",
      "value": "prefer_not_say",
      "synonyms": ["private", "don't want", "personal"]
    }
  ]
}
```

## Flow Logic

```python
def determine_next_node(state: OnboardingState) -> str:
    """
    Determines next node based on Home responses
    """
    housing_type = state["answers"].get("housing.type")
    housing_satisfaction = state["answers"].get("housing.satisfaction")
    
    # If lives with family or needs urgent change, family context is important
    if housing_type == "live_with_family" or housing_satisfaction == "need_to_change":
        return "family_unit_node"
        
    # Normal flow
    return "family_unit_node"

def should_show_node(state: OnboardingState) -> bool:
    """
    Show only if housing-related topics were mentioned
    """
    # Check all previous conversation content for housing keywords
    all_responses = extract_all_text_responses(state)
    housing_keywords = [
        "house", "home", "housing", "rent", "mortgage", "apartment", 
        "buy a house", "home buying", "real estate", "property",
        "living", "move", "relocate", "downsize", "upgrade home",
        "landlord", "lease", "down payment", "homeowner"
    ]
    
    for response in all_responses:
        if any(keyword in response.lower() for keyword in housing_keywords):
            return True
    
    return False
```

## Validations

- **housing_type**: Required, must be valid option
- **housing_satisfaction**: Required to understand motivation for change
- **monthly_cost_range**: Only for renters, optional
- **future_plans**: Required for financial planning

## System Prompts for Node

### Presentation Prompt
```
You are facilitating the housing situation phase of onboarding.

Objectives for this node:
1. Understand current housing situation
2. Evaluate satisfaction and need for change
3. Capture housing costs (if comfortable sharing)
4. Identify future housing plans

Keep prompts neutral - tone will be handled by the general onboarding prompt (00).
```

### Validation Prompt
```
Validate responses for Home node:

- Housing type: Required to understand basic situation
- Satisfaction: Important to calibrate urgency of change
- Costs: Only ask renters, respect if they prefer not to share
- Future plans: Critical for financial planning

If planning to buy house or needs change soon, this will be important for recommendations.
```

## Housing Profiles

### By Housing Type
- **Renters**: Focus on cost optimization and planning for ownership
- **Owners**: Optimization of equity and maintenance
- **Family Living**: Transition planning and financial independence
- **Temporary**: Flexibility and short-term options

### By Future Plans
- **Homebuying**: Savings goals, credit optimization, down payment planning
- **Upgrading**: Income optimization, market timing
- **Downsizing**: Cost reduction, lifestyle optimization
- **Relocating**: Cost comparison, emergency fund, transition planning

## Success Metrics

- **Completion Rate**: >85% of eligible users complete
- **Cost Sharing**: >50% of renters share cost ranges
- **Future Planning**: >90% have some defined plan vs "not sure"
- **Satisfaction Distribution**: Tracking of satisfaction levels

## Impact on Recommendations

- **Housing Costs**: Affects availability for other goals
- **Ownership Status**: Influences investment and emergency fund recommendations
- **Future Plans**: Determines timeline for savings goals
- **Satisfaction Level**: Calibrates urgency of optimization vs growth

## Implementation Notes

- Housing is often the largest expense - critical information for budgeting
- Home buying plans require specific timeline and major savings goal
- Temporary situations need flexibility in recommendations
- This information connects directly with emergency fund and down payment savings planning
