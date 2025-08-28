# Node 7: Health Coverage (Optional)

## Description
Conditional node that captures basic health insurance information. Only shown if user mentions health-related concerns, medical expenses, or insurance topics in previous conversations.

## Node Type
Simple `single_choice` questions

## Step Flow

### Step 7.1: Health Insurance Status
```json
{
  "id": "health_insurance_status",
  "type": "single_choice",
  "prompt": "Do you have health insurance? Is it through an employer, self-paid, or via a public program?",
  "target_key": "health.insurance_status",
  "required": true,
  "choices": [
    {
      "id": "employer_provided",
      "label": "Employer provided",
      "value": "employer_provided",
      "synonyms": ["work", "employer", "company"]
    },
    {
      "id": "self_paid_private",
      "label": "Self-paid private",
      "value": "self_paid_private",
      "synonyms": ["private", "self-pay", "individual"]
    },
    {
      "id": "government_program",
      "label": "Government program",
      "value": "government_program",
      "synonyms": ["government", "public", "state"]
    },
    {
      "id": "no_insurance",
      "label": "No health insurance",
      "value": "no_insurance",
      "synonyms": ["no insurance", "uninsured", "none"]
    }
  ]
}
```

### Step 7.2: Monthly Cost (Conditional)
```json
{
  "id": "monthly_health_cost",
  "type": "single_choice",
  "prompt": "How much do you pay per month approximately?",
  "target_key": "health.monthly_cost",
  "required": false,
  "conditional_display": {
    "condition": "health.insurance_status == 'self_paid_private'"
  },
  "choices": [
    {
      "id": "under_200",
      "label": "Less than $200",
      "value": "under_200"
    },
    {
      "id": "200_500",
      "label": "$200 - $500",
      "value": "200_500"
    },
    {
      "id": "over_500",
      "label": "More than $500",
      "value": "over_500"
    }
  ]
}
```

## Eligibility Criteria

This node is shown only if ANY of the following conditions are met:
- User mentions health, medical, doctor, insurance, hospital, medication in nodes 1-3
- User mentions medical expenses as a concern
- User indicates health issues affect their finances
- User explicitly asks about health insurance

## Flow Logic

```python
def should_show_node(state: OnboardingState) -> bool:
    """
    Show only if health-related topics were mentioned
    """
    # Check all previous conversation content for health keywords
    all_responses = extract_all_text_responses(state)
    health_keywords = [
        "health", "medical", "doctor", "hospital", "medication", 
        "insurance", "sick", "treatment", "therapy", "prescription",
        "medical bills", "healthcare", "clinic", "surgery"
    ]
    
    for response in all_responses:
        if any(keyword in response.lower() for keyword in health_keywords):
            return True
    
    return False

def determine_next_node(state: OnboardingState) -> str:
    return "plaid_integration"
```

## Implementation Notes

- Simplified health coverage information
- Only essential questions
- Respects privacy and keeps it brief
