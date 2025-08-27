# Node 10: Checkout/Exit (Universal Exit Node)

## Description
Universal exit node that ALL users pass through after Plaid integration (step 9). Both options ("Keep chatting" and "Let's go!") complete the onboarding process, giving users a sense of choice while ensuring consistent completion for all users.

## Node Type
`single_choice` with direct flow to end onboarding

## Trigger Criteria
- **Primary Route**: User has completed the onboarding conversation flow (normal completion)
- **Alternative Route**: User has skipped 3 or more nodes and is redirected early
- **Universal**: ALL users end up at this node regardless of their path through onboarding

## Step Flow

### Step 10.1: Natural Conversation Transition
```json
{
  "id": "natural_transition",
  "type": "single_choice",
  "prompt": "Thanks for sharing all that with me! Now I can help you better. What feels right to you?",
  "target_key": "checkout.final_choice",
  "required": true,
  "conditional_prompt": {
    "early_exit": "No worries, we'll figure things out as we go! What do you feel like doing?",
    "normal_completion": "Perfect! I've got a good sense of your situation now. What sounds good to you?",
    "topic_based": {
      "learning_focused": "Ready to dive into some of those topics you mentioned?",
      "goal_focused": "I can start building your plan based on what you've shared. Ready to begin?",
      "setup_focused": "Now I can help you see your full financial picture. Should we connect your accounts?"
    }
  },
  "choices": [
    {
      "id": "continue_conversation",
      "label": "Keep chatting",
      "value": "setup_app",
      "synonyms": ["chat", "talk", "discuss", "learn", "explore", "dive in", "something else", "questions"]
    },
    {
      "id": "setup_app",
      "label": "Let's go!",
      "value": "setup_app", 
      "synonyms": ["connect", "accounts", "setup", "picture", "budget", "ready", "begin", "start", "build"]
    }
  ]
}
```

## Flow Logic

```python
def determine_next_node(state: OnboardingState) -> str:
    """
    Both choices lead to onboarding completion
    Both paths immediately complete onboarding to ensure consistent UX
    """
    final_choice = state["answers"].get("checkout.final_choice")
    
    # Both choices complete onboarding immediately
    if final_choice == "continue_conversation":
        return "onboarding_complete"
    elif final_choice == "setup_app":
        return "onboarding_complete"
    
    # Fallback also completes onboarding
    return "onboarding_complete"

def should_show_node(state: OnboardingState) -> bool:
    """
    Universal node - ALWAYS shown as final step
    """
    return True

def get_prompt_context(state: OnboardingState) -> str:
    """
    Determine which prompt variant to use based on user path and interests
    """
    skip_count = state.get("skip_count", 0)
    answers = state.get("answers", {})
    
    # Early exit case
    if skip_count >= 3:
        return "early_exit"
    
    # Topic-based prompts for normal completion
    personal_goals = answers.get("identity.personal_goals", "").lower()
    learning_interests = answers.get("learning.interest_areas", [])
    
    # Learning-focused
    if learning_interests or "learn" in personal_goals:
        return "topic_based.learning_focused"
    
    # Goal-focused (has specific financial goals)
    if any(keyword in personal_goals for keyword in ["buy", "save", "debt", "invest", "retire"]):
        return "topic_based.goal_focused"
    
    # Setup-focused (comfortable with money/higher income)
    money_feelings = answers.get("money.feelings", [])
    income_range = answers.get("money.annual_income_range")
    if ("excited" in money_feelings or "feel_great_about_it" in money_feelings or 
        income_range in ["75k_100k", "over_100k"]):
        return "topic_based.setup_focused"
    
    # Default
    return "normal_completion"

def track_skip_event(state: OnboardingState, node_id: str) -> OnboardingState:
    """
    Helper function to track skip events across all nodes
    """
    current_skip_count = state.get("skip_count", 0)
    skipped_nodes = state.get("skipped_nodes", [])
    
    # Increment skip count
    state["skip_count"] = current_skip_count + 1
    
    # Track which node was skipped
    if node_id not in skipped_nodes:
        skipped_nodes.append(node_id)
        state["skipped_nodes"] = skipped_nodes
    
    # If 3+ skips, route to checkout
    if state["skip_count"] >= 3:
        state["next_node"] = "checkout_exit_node"
    
    return state
```

## System Integration

### Skip Tracking Implementation
```python
# Add this to ALL nodes except 01 and 02 (nodes 3, 4, 5, 6, 7, 8)

def handle_skip_event(state: OnboardingState, current_node_id: str) -> str:
    """
    Universal skip handler for all nodes
    """
    # Track the skip
    state = track_skip_event(state, current_node_id)
    
    # Check if we should route to checkout
    if state["skip_count"] >= 3:
        return "checkout_exit_node"
    
    # Otherwise continue normal flow
    return determine_next_node_normal_flow(state)
```

### State Schema Updates
```python
# Add to OnboardingState TypedDict
class OnboardingState(TypedDict):
    user_id: str
    thread_id: str
    cursor: int
    steps: List[Dict]
    answers: Dict[str, Any]
    skip_count: int  # NEW: Track number of skips
    skipped_nodes: List[str]  # NEW: Track which nodes were skipped
```

## Exit Flow Handling

### For "Keep Chatting" Choice
```python
def handle_keep_chatting(state: OnboardingState) -> Dict:
    """
    Handle users who select the conversation option
    Completes onboarding immediately like "Let's go!" option
    """
    return {
        "onboarding_status": "ready_to_complete",
        "completion_type": "conversation_choice", 
        "collected_data": extract_available_profile(state),
        "next_action": "onboarding_complete",
        "user_preference": "preferred_conversation_first",
        "conversation_preference": True,
        "final_destination": "onboarding_complete"
    }
```

### For "Let's Go!" Choice  
```python
def handle_lets_go(state: OnboardingState) -> Dict:
    """
    Handle users who want to complete onboarding directly
    Same outcome as "Keep chatting" in placebo implementation
    """
    return {
        "onboarding_status": "ready_to_complete",
        "completion_type": "direct_to_complete",
        "collected_data": extract_available_profile(state),
        "next_action": "onboarding_complete",
        "user_preference": "preferred_direct_setup",
        "plaid_completed": True,
        "conversation_preference": False
    }
```

## Data Collection Summary

Even with early exit, capture what we have:

```python
def suggest_conversation_topics(state: OnboardingState) -> List[str]:
    """
    Suggest relevant conversation topics based on collected data
    """
    answers = state.get("answers", {})
    topics = []
    
    # Base topics everyone gets
    topics.extend(["budgeting basics", "financial goals"])
    
    # Add topics based on their answers
    if answers.get("identity.primary_goal"):
        goal = answers["identity.primary_goal"]
        if "buy" in goal.lower() and "house" in goal.lower():
            topics.append("home buying process")
        if "debt" in goal.lower():
            topics.append("debt payoff strategies")
        if "invest" in goal.lower():
            topics.append("investment basics")
        if "save" in goal.lower():
            topics.append("saving strategies")
    
    # Add topics based on income/money feelings
    money_feelings = answers.get("money.feelings", [])
    if "stressed_out" in money_feelings:
        topics.append("stress-free money management")
    if "excited" in money_feelings:
        topics.append("advanced financial planning")
    
    return topics[:4]  # Limit to 4 topics

def handle_extended_conversation_2_messages(state: OnboardingState) -> Dict:
    """
    Handle the brief 2-message conversation extension
    """
    return {
        "mode": "extended_conversation_brief",
        "message_count": 0,  # Track current message
        "max_messages": 2,
        "topics": suggest_conversation_topics(state),
        "auto_transition_after": 2,
        "final_destination": "onboarding_complete",
        "conversation_style": "exploratory_brief"
    }

def extract_minimal_profile(state: OnboardingState) -> Dict:
    """
    Extract whatever data we collected before exit
    """
    answers = state.get("answers", {})
    
    return {
        "identity": {
            "age_range": answers.get("identity.age_range"),
            "location": answers.get("identity.location"),
            "primary_goal": answers.get("identity.primary_goal")
        },
        "money": {
            "feelings": answers.get("money.feelings", []),
            "income_range": answers.get("money.annual_income_range"),
            "learning_motivation": answers.get("money.learning_motivation")
        },
        "completion_percentage": calculate_completion_percentage(state),
        "exit_reason": "frequent_skipping"
    }
```

## System Prompts for Node

### Presentation Prompt
```
You are naturally transitioning from information gathering to next steps in the conversation.

This should feel like a natural progression, not a system decision point.

Context-aware approach:
1. For normal completion: Reference what they've shared and suggest natural next steps
2. For early exit: Keep it casual and exploratory without making them feel rushed
3. For topic-specific: Reference their interests directly (learning, goals, etc.)

Key principles:
- Never reveal this is a "checkout" or decision node
- Make it feel like Vera is naturally offering what comes next
- Use their name and reference specific things they mentioned
- Sound excited about helping them, not system-like
```

### Validation Prompt  
```
This transition should feel completely natural and conversational.

Both response paths are equally valuable:
- Conversation: Natural exploration of topics they're interested in
- Setup: Practical next step to see their financial picture

The user should never feel like they're making a "system choice" - they should feel like Vera is naturally asking what they'd like to focus on based on their conversation.

Validate that the chosen prompt variant matches their onboarding journey and interests.
```

### Example Natural Transitions

#### Learning-Focused User
```
"Alright, let's dive in! 

By the way, you can pin anything we talk about for quick access. 

Ready to learn something new?"
```

#### Goal-Focused User  
```
"Thanks for all the info!

Now I can build your budget so we can start working on your goals. Ready to begin?"
```

#### Early Exit User
```
"No worries, Michael, we'll figure them out as we go. 

Do you feel like talking about something else today?"
```

#### Setup-Ready User
```
"Perfect! I've got everything I need to show you the full picture.

Should we connect your accounts so you can see where you stand?"
```

## Success Metrics

- **Path Distribution**: Percentage choosing "continue conversation" vs "setup app"
- **Conversion Rates**: How many users who choose "continue conversation" eventually setup accounts
- **User Satisfaction**: Feedback on the choice presentation and subsequent experience
- **Engagement Quality**: Performance metrics for both post-checkout paths
- **Completion Analysis**: Correlation between onboarding completion level and long-term engagement

## Implementation Notes

- **Post-Plaid Transition**: This node occurs AFTER Plaid integration (step 9) is complete
- **Universal Exit**: ALL users pass through this node as the final onboarding step
- **Unified Flow**: Both choices immediately complete onboarding - no extended conversation
- **Invisible Transition**: Users should never know they're at a "checkout" - feels like natural conversation flow
- **Context-Aware Prompting**: Vera references specific things the user mentioned to feel personal
- **Choice Tracking**: System tracks user preference for analytics but both paths have identical outcomes
- **Seamless Experience**: Both paths feel like natural next steps, leading to immediate completion
- **Accounts Already Connected**: Plaid integration is complete by this point
- **User Preference Data**: Choice is stored for future personalization but doesn't affect immediate flow

### Natural Language Processing
- **Synonym Detection**: Wide range of natural responses should map to the two core choices
- **Context Inference**: System should infer user intent from conversational responses
- **Fallback Handling**: If unclear, default to conversation mode with clarification

### Personalization Elements
- **Name Usage**: Include user's name naturally in the transition
- **Reference Specific Details**: Mention things they shared (goals, interests, concerns)
- **Tone Matching**: Adapt energy level to match their engagement during onboarding

### Response Handling Philosophy
- **Accept Natural Language**: Users should be able to respond conversationally ("Yeah, let's chat", "Sure, show me", "I'm ready")
- **No Forced Choices**: Never make users feel they have to pick from a rigid menu
- **Conversation Flow**: Responses should feel like natural dialogue continuation
- **Clarification When Needed**: If ambiguous, Vera asks naturally: "Did you want to explore X or should we Y?"

## Integration with Existing Nodes

All nodes except warmup and identity (3, 4, 5, 6, 7, 8) need to implement skip tracking:

```javascript
// Example for any optional node
{
  "skip_option": {
    "available": true,
    "label": "Skip this for now",
    "action": "track_skip_and_continue"
  }
}
```
