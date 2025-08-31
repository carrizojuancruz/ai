# Node 1: Warm Up

## Description
Introductory node that establishes the onboarding flow, explains the process and captures initial user information.

## Node Type
Sequence of steps with conditional flow using `binary_choice` and `free_text`

## Step Flow

### Step 1.1: Initial Chat Introduction
```json
{
  "id": "chat_intro",
  "type": "binary_choice",
  "prompt": "How about a quick chat so I can get to know you a little and figure out the best way to have your back?",
  "target_key": "warmup.chat_intro",
  "required": true,
  "primary_choice": {
    "id": "continue",
    "label": "Yes, let's do it! 💬",
    "value": "continue",
    "action": "continue_normal_flow",
    "synonyms": ["yes", "sure", "continue", "go ahead", "let's do it", "sounds good", "okay"]
  },
  "secondary_choice": {
    "id": "skip",
    "label": "I'd rather chat freely",
    "value": "skip_onboarding",
    "action": "onboarding_complete",
    "synonyms": ["skip", "no", "pass", "setup only", "just setup", "not now", "maybe later"]
  },
  "routing": {
    "continue": "button_explanation",
    "skip_onboarding": "checkout_exit_node"
  }
}
```


### Step 1.2: About You
```json
{
  "id": "about_you",
  "type": "free_text",
  "prompt": "I'd love to hear about your daily life, your city, your family, or whatever you feel like sharing.",
  "target_key": "about_you",
  "required": true
}
```

## Flow Logic

```python
def determine_next_node(state: OnboardingState) -> str:
    """
    Determines next node based on warmup responses
    """
    chat_intro_choice = state["answers"].get("warmup.chat_intro")
    
    if chat_intro_choice == "skip_onboarding":
        # User chose to skip onboarding entirely
        return "onboarding_complete"
    else:
        # User chose to continue with onboarding
        return "identity_node"
```

## Validations

- **chat_intro**: Required binary choice, validated against synonyms

## Edge Cases

1. **User chooses skip**: Respect choice and route directly to checkout
2. **Ambiguous response to binary choice**: Ask for clarification with buttons
3. **Very long response in about_you**: Truncate at 500 characters with note
4. **Inappropriate content**: Validate against problematic words list

## System Prompts for Node

### Presentation Prompt
```
You are facilitating the warm-up phase of financial onboarding.

Objectives for this node:
1. Create initial rapport and trust
2. Explain the process in a reassuring way
3. Handle the fundamental continue vs skip decision
4. Capture basic information about the user if they continue

For binary_choice steps:
- Present the two options clearly as buttons
- If user responds in natural language, match to closest option using synonyms
- If ambiguous, ask for clarification: "Did you want to continue with the chat or skip to account setup?"

Keep prompts neutral - tone will be handled by the general onboarding prompt (00).
```

### Validation Prompt
```
Validate user responses for Warm Up node:

For binary_choice steps:
- Match user input against synonyms for each option
- If no clear match, present the two options again as buttons
- Accept natural language but confirm the choice

For free_text steps:
- If response seems inappropriate, ask politely for alternative
- If about_you is too short, invite to share a bit more
- Always maintain supportive tone

Respect skip requests immediately - route to checkout without guilt or pressure.
```

## Success Metrics (wip)

- **Completion Rate**: >95% of users complete this node (including skips)
- **Choice Clarity**: <5% need clarification on binary choice
- **Engagement**: at last 1 emotional word included in response
- **Skip Rate**: Track percentage who choose to skip onboarding

## Implementation Notes (wip)

- This node establishes the fundamental onboarding pattern
- The skip decision here bypasses the entire sequence
- Responses here are critical for later personalization
- Button interface improves mobile experience significantly
