# Node 8: Learning Path (Optional)

## Description
Optional node for users who expressed interest in learning about finances. Presents educational topics to help them get started with financial literacy.

## Node Type
`multi_choice` selection for learning preferences

## Eligibility Criteria
- User mentioned "learn" in personal goals
- Routed from Identity node when learning focus detected

## Step Flow

### Step 8.1: Learning Interest Areas
```json
{
  "id": "learning_interests",
  "type": "multi_choice",
  "prompt": "What topics are you most interested in right now?",
  "target_key": "learning.interest_areas",
  "required": true,
  "multi_min": 1,
  "multi_max": 6,
  "choices": [
    {
      "id": "budgeting",
      "label": "Budgeting",
      "value": "budgeting",
      "synonyms": ["budget", "spending plan", "expense tracking"]
    },
    {
      "id": "saving_for_goals",
      "label": "Saving for goals",
      "value": "saving_for_goals",
      "synonyms": ["saving", "goals", "goal setting", "target saving"]
    },
    {
      "id": "credit_debt",
      "label": "Credit & debt basics",
      "value": "credit_debt_basics",
      "synonyms": ["credit", "debt", "credit score", "loans"]
    },
    {
      "id": "big_purchases",
      "label": "Big purchases & housing",
      "value": "big_purchases_housing",
      "synonyms": ["house", "car", "major purchase", "financing"]
    },
    {
      "id": "taxes",
      "label": "Taxes",
      "value": "taxes",
      "synonyms": ["tax", "filing", "deductions", "IRS"]
    },
    {
      "id": "investing",
      "label": "Investing",
      "value": "investing",
      "synonyms": ["investment", "stocks", "retirement", "portfolio"]
    }
  ]
}
```

## Flow Logic

```python
def determine_next_node(state: OnboardingState) -> str:
    """
    Determines next node based on learning path selection
    """
    learning_interests = state["answers"].get("learning.interest_areas", [])
    
    # After learning path selection, go to Plaid integration
    # The learning content will be delivered in the main app
    return "plaid_integration"

def should_show_node(state: OnboardingState) -> bool:
    """
    Determines if this node should be shown
    """
    personal_goals = state["answers"].get("identity.personal_goals", "")
    
    # Show if user expressed learning interest
    return "learn" in personal_goals.lower()
```

## Validations

- **learning_interests**: At least 1 selection required, maximum 6
- Must validate that user came from appropriate routing path

## Edge Cases

1. **No learning interests**: Redirect to standard onboarding path
2. **All topics selected**: Suggest focusing on 2-3 prioritized areas
3. **Advanced user**: Detect if selections indicate advanced knowledge level

## System Prompts for Node

### Presentation Prompt
```
You are facilitating the learning path selection for financial education.

Objectives for this node:
1. Identify specific learning interests and priorities
2. Set up personalized educational content delivery
3. Create learning goals and milestones

Keep prompts neutral - tone will be handled by the general onboarding prompt (00).
Focus on practical, actionable learning areas.
```

### Validation Prompt
```
Validate responses for Learning Path node:

- Learning interests: At least one area must be selected
- If too many areas selected, suggest prioritization
- Ensure selections align with expressed learning goals

Validate that user reached this node through appropriate routing.
```

## Learning Content Mapping

### By Interest Area
- **Budgeting**: expense tracking, spending awareness
- **Saving for Goals**: SMART goals, automatic savings, emergency funds
- **Credit & Debt**: Credit scores, debt payoff strategies, credit building
- **Big Purchases**: Down payments, financing options, affordability calculations
- **Taxes**: Basic tax concepts, deductions, filing requirements
- **Investing**: Risk tolerance, diversification, retirement accounts

### Delivery Method
- Educational content delivered through main chat system
- Progressive curriculum based on selected interests
- Interactive exercises and practical applications
- Regular check-ins and progress tracking

## Success Metrics

- **Selection Rate**: Average number of topics selected per user
- **Completion Rate**: % who complete onboarding after learning path
- **Engagement**: Interaction with delivered learning content
- **Learning Progression**: Advancement through educational materials

## Impact on User Experience

- **Personalized Education**: Custom learning track based on interests
- **Content Prioritization**: Focus chat interactions on selected topics
- **Goal Setting**: Automatic creation of learning-based financial goals
- **Progress Tracking**: Monitor advancement through educational content

## Implementation Notes

- This node creates a different user experience focused on education
- Selected topics influence content delivery in main chat system
- Learning progress should be tracked and surfaced in user dashboard
- Educational content should be practical and immediately applicable
- Regular assessment of learning progress and adjustment of content difficulty

## Content Integration

- Learning selections stored in user context for main chat system
- Educational content delivery prioritized based on selected interests
- Progress tracking integrated with overall financial goal tracking
