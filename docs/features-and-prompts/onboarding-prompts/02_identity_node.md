# Node 2: Identity

## Description
Captures basic demographic information and explores user's personal goals to understand their life context and aspirations.

## Node Type
Combination of `single_choice` and `free_text`

## Step Flow

### Step 2.1a: Age (Open-ended)
```json
{
  "id": "age_open_ended",
  "type": "free_text", 
  "prompt": "What is your age?",
  "target_key": "identity.age",
  "required": false,
  "validation_hints": {
    "expected_format": "number between 1-150",
    "fallback_to_ranges": true
  },
  "age_restriction": {
    "min_age": 18,
    "restriction_message": "I’m really sorry, but you need to be at least 18 to chat with me. It’s for safety and privacy reasons.
I hope we can talk in the future!",
    "redirect_action": "end_conversation"
  }
}
```

### Step 2.1b: Age Ranges (Fallback)
```json
{
  "id": "age_range",
  "type": "single_choice",
  "prompt": "No worries! Could you share your age range instead?",
  "target_key": "identity.age_range", 
  "required": true,
  "conditional_display": {
    "show_if": "age_open_ended is empty or unclear"
  },
  "age_restriction": {
    "min_age": 18,
    "restriction_message": "I’m really sorry, but you need to be at least 18 to chat with me. It’s for safety and privacy reasons.
I hope we can talk in the future!",
    "redirect_action": "end_conversation"
  },
  "choices": [
    {
      "id": "under_18",
      "label": "I'm under 18",
      "value": "under_18",
      "synonyms": ["minor", "teenager", "young"]
    },
    {
      "id": "18_24", 
      "label": "18 - 24",
      "value": "18_24",
      "synonyms": ["college", "university", "recent graduate"]
    },
    {
      "id": "25_30",
      "label": "25 - 30",
      "value": "25_30", 
      "synonyms": ["twenties", "young professional"]
    },
    {
      "id": "30_34",
      "label": "30 - 34",
      "value": "30_34",
      "synonyms": ["early thirties"]
    },
    {
      "id": "35_44",
      "label": "35 - 44", 
      "value": "35_44",
      "synonyms": ["late thirties", "early forties"]
    },
    {
      "id": "45_plus",
      "label": "45+",
      "value": "45_plus",
      "synonyms": ["older", "mature", "senior"]
    }
  ]
}
```

### Step 2.2: Location
```json
{
  "id": "location",
  "type": "free_text",
  "prompt": "Where do you live?",
  "target_key": "identity.location",
  "required": true,
  "validation_hints": {
    "min_length": 2,
    "expected_format": "city, state, country or just state"
  }
}
```

### Step 2.3: Personal Goals and Dreams
```json
{
  "id": "personal_goals",
  "type": "free_text",
  "prompt": "Do you have any big dreams or personal goals?",
  "target_key": "identity.personal_goals",
  "required": false,
  "note": "If the answer is 'I want to learn' or something similar -> send them to the learning path"
}
```

### Step 2.4: Goal Achievement Help
```json
{
  "id": "goal_achievement_help",
  "type": "multi_choice",
  "prompt": "And how do you think I could help you achieve that goal?",
  "target_key": "identity.help_methods",
  "required": true,
  "conditional_display": {
    "condition": "identity.personal_goals is not empty AND not 'learn' response"
  },
  "note": "If not (response similar to 'not sure') -> skip onboarding",
  "choices": [
    {
      "id": "budget_smarter",
      "label": "Budget smarter",
      "value": "budget_smarter",
      "synonyms": ["budgeting", "plan expenses", "financial control"]
    },
    {
      "id": "track_money_better", 
      "label": "Track my money better",
      "value": "track_money_better",
      "synonyms": ["tracking", "monitoring", "control"]
    },
    {
      "id": "save_for_goal",
      "label": "Save for a real goal",
      "value": "save_for_goal",
      "synonyms": ["saving", "goal saving", "systematic saving"]
    },
    {
      "id": "build_habits",
      "label": "Build better money habits",
      "value": "build_habits",
      "synonyms": ["habits", "discipline", "consistency"]
    },
    {
      "id": "learn_about_finances",
      "label": "Learn about finances",
      "value": "learn_about_finances", 
      "synonyms": ["learning", "education", "financial knowledge"]
    }
  ]
}
```

### Step 2.5: Tell Us Anything Else
```json
{
  "id": "anything_else",
  "type": "free_text",
  "prompt": "Would you like to tell us anything else about them?",
  "target_key": "identity.additional_info",
  "required": false,
  "conditional_display": {
    "condition": "identity.personal_goals is not empty"
  }
}
```

## Flow Logic

```python
def determine_next_node(state: OnboardingState) -> str:
    """
    Determines next node based on Identity responses
    """
    age = state["answers"].get("identity.age")
    age_range = state["answers"].get("identity.age_range") 
    personal_goals = state["answers"].get("identity.personal_goals", "")
    help_methods = state["answers"].get("identity.help_methods", [])
    
    # Age restriction: block users under 18 (check both exact age and range)
    if age and int(age) < 18:
        return "end_conversation"
    if age_range == "under_18":
        return "end_conversation"
    
    # If wants to learn, go to learning path
    if "learn" in personal_goals.lower():
        return "learning_path_node"
    
    # If unsure about how to help, skip onboarding
    if not help_methods or "not sure" in help_methods:
        return "orchestrator_path"
    
    # Normal flow to income & money
    return "income_money_node"

def should_show_age_range_step(state: OnboardingState) -> bool:
    """
    Determines if age range step should be shown
    """
    age = state["answers"].get("identity.age")
    
    # Show ranges if:
    # 1. No age provided at all
    # 2. Age is not a valid number
    # 3. Age seems unclear or invalid
    if not age:
        return True
    
    try:
        age_num = int(age)
        # If age is reasonable, don't show ranges
        if 1 <= age_num <= 150:
            return False
    except (ValueError, TypeError):
        # If can't convert to number, show ranges
        return True
    
    # Default to showing ranges for safety
    return True

def get_effective_age_range(state: OnboardingState) -> str:
    """
    Get the effective age range from either exact age or selected range
    """
    age = state["answers"].get("identity.age")
    age_range = state["answers"].get("identity.age_range")
    
    # If we have a range selection, use it
    if age_range:
        return age_range
    
    # If we have exact age, convert to range
    if age:
        try:
            age_num = int(age)
            if age_num < 18:
                return "under_18"
            elif 18 <= age_num <= 24:
                return "18_24"
            elif 25 <= age_num <= 30:
                return "25_30"
            elif 31 <= age_num <= 34:
                return "30_34"
            elif 35 <= age_num <= 44:
                return "35_44"
            else:
                return "45_plus"
        except (ValueError, TypeError):
            pass
    
    return None
```

## Validations

- **age (open-ended)**: Optional, but if provided should be a reasonable number (1-150)
- **age_range**: Required if age open-ended is not provided or unclear
- **location**: Minimum 2 characters, basic format validation
- **personal_goals**: Optional, but if provided minimum 10 characters
- **help_methods**: At least 1 selection if goals provided

## Edge Cases

1. **Under 18**: Display age restriction message (see code snippet below) and end conversation immediately
2. **Learning focus**: Route to learning path node
3. **No personal goals**: Skip conditional questions
4. **Uncertain about help**: Skip onboarding entirely

### Age Restriction Message
```json
{
  "restriction_message": "I’m really sorry, but you need to be at least 18 to chat with me. It’s for safety and privacy reasons.
I hope we can talk in the future!"
}
```

## System Prompts for Node

### Presentation Prompt  
```
You are facilitating the identity phase of financial onboarding.

Objectives for this node:
1. Understand their life stage (age and context) - use two-step approach
2. Know their location for economic context
3. Explore their dreams and personal goals
4. Identify preferred help methods

Age Collection Strategy:
- Start with open-ended: "What is your age?" - let them share actual age if comfortable
- If no clear number or hesitant response, follow up with ranges naturally
- Both approaches are equally valid - respect different comfort levels

Keep prompts neutral - tone will be handled by the general onboarding prompt (00).
```

### Validation Prompt
```
Validate responses for Identity node:

- Age (open-ended): If provided, should be reasonable number; if unclear/missing, proceed to ranges
- Age (ranges): Must be one of the valid options if ranges step is shown
- Location: Flexible format but minimum useful information
- Personal goals: If too generic, invite to be more specific
- Help methods: At least one option if goals are defined

Keep validation light - better incomplete information than frustrated user.
```

## User Segmentation

Based on responses from this node, initial profiles can be created:

### Profiles by Age
- **Young (18-24)**: Educational focus and habits
- **Young Adults (25-34)**: Big goals (home, family)
- **Middle Age (35-44)**: Optimization and planning
- **Mature (45+)**: Security and transition

### Profiles by Goal Type
- **Learning-focused**: Route to educational content
- **Goal-driven**: Clear goals with financial component
- **Uncertain**: Need guidance and exploration

## Success Metrics

- **Completion Rate**: >90% complete basic information
- **Engagement**: >70% provide personal goals
- **Quality Score**: Average response length >30 characters
- **Routing Success**: Correct routing to learning vs income paths

## Implementation Notes

- Information from this node is critical for later personalization
- Store segmentation profile for use in subsequent nodes
- Responses here determine which optional nodes are relevant
- Learning path routing is a key decision point
