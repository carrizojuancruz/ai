# Thinking Timeline Dictionary

## Purpose

This document defines a communication scheme that masks internal calls to our agents for the frontend. The goal is to provide a smooth user experience where the end user always perceives Vera as a single entity, hiding the technical complexity of the agent system.

## Dictionary Structure

The dictionary maps each type of agent or internal process with:
- **Active state phrase** that is shown to the user while working
- **Completed state phrase** that is shown when finished

## State Mapping Table

| Type | Definition | if current | if completed |
|------|------------|------------|--------------|
| Step Planning | Deciding what the next step is | **Option 1:** "Just a sec, I'm thinking... "<br>**Option 2:** "Let me think this through..."<br>**Option 3:** "Let me figure out the best approach..." | **Option 1:** "All set with the next move"<br>**Option 2:** "Next step's ready to roll"<br>**Option 3:** "All mapped out!" |
| BudgetAgent | BudgetAgent call | **Option 1:** "Reviewing your goals..."<br>**Option 2:** "Checking progress on your goals..."<br>**Option 3:** "Analyzing your goals to see the path ahead..." | **Option 1:** "Goals checked!"<br>**Option 2:** "Goals check-in finished"<br>**Option 3:** "I've completed your goals review" |
| BudgetAgent | BudgetAgent query for financial information | **Option 1:** "Analyzing your goals with financial data..."<br>**Option 2:** "Checking your goals against your info..."<br>**Option 3:** "Reviewing your info to track goals..." | **Option 1:** "Your goals just got a money check-up"<br>**Option 2:** "Goals insights ready"<br>**Option 3:** "Fresh insights on your goals are ready" |
| FinanceAgent | FinanceAgent call | **Option 1:** "Diving into your financial snapshot..."<br>**Option 2:** "Taking a quick look at your finances..."<br>**Option 3:** "Analyzing your financial info..." | **Option 1:** "I've scanned your finances."<br>**Option 2:** "Financial snapshot checked!"<br>**Option 3:** "Financial analysis complete!" |
| Finance Agent | FinanceAgent query to Knowledge Base | **Option 1:** "Checking my financial references..."<br>**Option 2:** "Flipping through my financial notes..."<br>**Option 3:** "Looking up financial guidance..." | **Option 1:** "Financial references checked"<br>**Option 2:** "Notes found and ready"<br>**Option 3:** "Found the insights you need!" |
| Education & Wealth CoachAgent | Education & Wealth CoachAgent call | **Option 1:** "Switching to guide mode for a sec..."<br>**Option 2:** "Switching to brainy mode..."<br>**Option 3:** "Activating coaching expertise..." | **Option 1:** "Knowledge mode activated"<br>**Option 2:** "Wisdom mode activated"<br>**Option 3:** "Learning mode ready to roll" |
| Education & Wealth CoachAgent | E&WCA query to KB or notes | **Option 1:** "Pulling together some articles..."<br>**Option 2:** "Gathering helpful info for you..."<br>**Option 3:** "Collecting relevant resources..." | **Option 1:** "Helpful resources pulled together"<br>**Option 2:** "Found some info you can use"<br>**Option 3:** "Your learning notes are ready to go" |

## Dictionary Usage

### Multiple Options Strategy
Each agent state now includes **3 different phrase options** to:
- **Prevent Repetition**: Avoid showing the same message repeatedly to users
- **Add Variety**: Keep the conversation feeling natural and dynamic
- **Context Adaptation**: Allow the system to choose the most appropriate phrase based on context
- **A/B Testing**: Enable testing different phrasings to optimize user experience

### Selection Logic
The system can choose phrases using:
- **Random Selection**: Simple randomization for variety
- **Context-Based**: Choose based on user history, time of day, or conversation flow
- **Round-Robin**: Cycle through options systematically
- **User Preference**: Learn from user interactions to prefer certain phrasings

### For the Product Team
- **State Communication**: Each agent has clear phrases indicating its current state
- **User Experience**: Phrases are friendly and don't expose technical architecture
- **Consistency**: Maintains uniform tone throughout the application
- **Variety**: Multiple options prevent monotonous repetition

### For the Development Team
- **State Mapping**: Connects internal agent states with user messages
- **Frontend Implementation**: Provides multiple phrases to display in each state
- **Maintenance**: Facilitates message updates without changing agent logic
- **Flexibility**: Easy to add new options or modify existing ones

## UX Considerations

### Voice and Tone
- **Friendly and Conversational**: Phrases sound natural, not technical
- **Informative**: Each message clearly communicates what's happening
- **Consistent**: Maintains the same communication style from Vera's POV

### User States
- **Active State**: Indicates something is happening, keeps user informed
- **Completed State**: Confirms task completion, prepares for next step

### Response Flow
- **Message Replacement**: Once the process completes, the status message is replaced by the response stream
- **Persistent Access**: Users can still access the completed status message through an icon in the thinking-timeline within the response detail
- **State History**: Maintains a record of all process states for transparency and debugging
- **Intermediate Text Steps**: All intermediate text steps are permanently recorded in the timeline, creating a complete audit trail of Vera's thinking process

### Transitions
- **Smooth**: Messages guide user through the process
- **Contextual**: Each message relates to the specific agent action

## Intermediate Text Steps & Timeline Persistence

### Text Step Recording
Every intermediate text step that occurs during agent processing is **permanently recorded** in the thinking timeline. This includes:

- **Agent State Messages**: All current and completed state phrases from the dictionary
- **Processing Steps**: Internal reasoning and decision-making text
- **Context Switching**: Transitions between different agents or processes
- **Error Handling**: Any error messages or recovery steps
- **Debug Information**: Technical details for troubleshooting (when enabled)

### Timeline Structure
The thinking timeline maintains a chronological record of:

1. **During the process**: Users see steps in real-time
2. **Upon completion**: Steps are saved in the timeline
3. **Later access**: Users can view the complete process whenever they want

### What Gets Recorded
- ✅ **State messages** (e.g., "Just a sec, I'm thinking...", "Goals checked!")
- ✅ **Processing steps** (e.g., "Reviewing your goals...")
- ✅ **Agent switches** (e.g., "Switching to guide mode for a sec...")


### User Experience
- **Transparency**: Users see exactly how Vera arrived at her response
- **Trust**: Complete visibility into the reasoning process
- **Learning**: Users understand Vera's decision-making patterns

### Practical Example

**User asks**: "How much should I save for retirement?"

**Timeline the user sees**:
```
⏳ "Just a sec, I'm thinking..."
✅ "All set with the next move"
⏳ "Reviewing your goals..."
✅ "Goals checked!"
⏳ "Checking my financial references..."
✅ "Found the insights you need!"
⏳ "Switching to guide mode for a sec..."
✅ "Knowledge mode activated"
```

**Result**: The user sees each step of the process and can expand the timeline to view all detailed steps.

## Extensibility

This scheme is designed to grow with new agents and processes:
- **New Agents**: Add new rows following the same pattern
- **New States**: Expand with additional states if needed
- **Customization**: Adapt phrases according to each agent's specific context

## Frontend Implementation

### Suggested Data Structure
```json
{
  "user_message": "How much should I save for retirement?",
  "thinking_timeline": [
    {
      "step": 1,
      "message": "Just a sec, I'm thinking...",
      "status": "active",
      "timestamp": "2024-01-15T10:30:15Z"
    },
    {
      "step": 2,
      "message": "All set with the next move",
      "status": "completed",
      "timestamp": "2024-01-15T10:30:16Z"
    },
    {
      "step": 3,
      "message": "Reviewing your goals...",
      "status": "active",
      "timestamp": "2024-01-15T10:30:17Z"
    },
    {
      "step": 4,
      "message": "Goals checked!",
      "status": "completed",
      "timestamp": "2024-01-15T10:30:18Z"
    },
    {
      "step": 5,
      "message": "Checking my financial references...",
      "status": "active",
      "timestamp": "2024-01-15T10:30:19Z"
    },
    {
      "step": 6,
      "message": "Found the insights you need!",
      "status": "completed",
      "timestamp": "2024-01-15T10:30:20Z"
    },
    {
      "step": 7,
      "message": "Switching to guide mode for a sec...",
      "status": "active",
      "timestamp": "2024-01-15T10:30:21Z"
    },
    {
      "step": 8,
      "message": "Knowledge mode activated",
      "status": "completed",
      "timestamp": "2024-01-15T10:30:22Z"
    }
  ],
  "final_response": "Based on your current budget and financial goals, I recommend saving 15-20% of your income for retirement. This would put you on track to maintain your current lifestyle..."
}
```

