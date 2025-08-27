# Node 6: Family Unit (Optional)

## Description
Conditional node that explores basic family composition and responsibilities. Only shown if user mentions family, children, dependents, spouse, partner, or family-related financial goals in nodes 1-3.

## Node Type
Combination of `single_choice` and `multi_choice`

## Step Flow

### Step 6.1: Dependents Under 18
```json
{
  "id": "dependents_under_18",
  "type": "single_choice",
  "prompt": "Do you have dependents under 18?",
  "target_key": "family.dependents_under_18",
  "required": true,
  "choices": [
    {
      "id": "none",
      "label": "No dependents",
      "value": "none",
      "synonyms": ["no", "none", "no children"]
    },
    {
      "id": "one_child",
      "label": "1 dependent",
      "value": "one_child",
      "synonyms": ["one", "1", "single child"]
    },
    {
      "id": "multiple_children",
      "label": "Multiple dependents",
      "value": "multiple_children",
      "synonyms": ["multiple", "several", "more than one"]
    }
  ]
}
```

### Step 6.2: Do You Have Pets
```json
{
  "id": "pets",
  "type": "single_choice",
  "prompt": "Do you have pets?",
  "target_key": "family.pets",
  "required": false,
  "choices": [
    {
      "id": "yes",
      "label": "Yes",
      "value": "yes",
      "synonyms": ["yes", "have pets"]
    },
    {
      "id": "no",
      "label": "No",
      "value": "no",
      "synonyms": ["no", "no pets"]
    }
  ]
}
```

## Eligibility Criteria

This node is shown only if ANY of the following conditions are met:
- User mentions family, children, kids, dependents, spouse, partner in nodes 1-3
- User mentions saving for children's education
- User indicates family expenses as a concern
- User mentions planning for family growth or family goals
- User asks about family financial planning

## Flow Logic

```python
def should_show_node(state: OnboardingState) -> bool:
    """
    Show only if family-related topics were mentioned
    """
    # Check all previous conversation content for family keywords
    all_responses = extract_all_text_responses(state)
    family_keywords = [
        "family", "children", "kids", "child", "dependents", "spouse", 
        "partner", "husband", "wife", "married", "parent", "parenting",
        "childcare", "education fund", "college savings", "family planning",
        "baby", "pregnancy", "school", "daycare", "family expenses"
    ]
    
    for response in all_responses:
        if any(keyword in response.lower() for keyword in family_keywords):
            return True
    
    return False

def determine_next_node(state: OnboardingState) -> str:
    dependents = state["answers"].get("family.dependents_under_18")
    
    # Check if health coverage should be shown
    if should_show_health_node(state):
        return "health_coverage_node"
    
    return "plaid_integration"
```

## Implementation Notes

- Simplified family information gathering
- Focuses on financial impact of dependents
- Optional and respectful of privacy
