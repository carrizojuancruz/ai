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
| Step Planning | Deciding what the next step is | **Option 1:** "I'm Thinking... "<br>**Option 2:** "Hmm, let me think this through..."<br>**Option 3:** "Let me figure out the best approach..." | **Option 1:** "I thought for a moment"<br>**Option 2:** "Aha! Got the next step lined up."<br>**Option 3:** "Perfect! I've got a plan." |
| BudgetAgent | BudgetAgent call | **Option 1:** "Let me peek into the budget for a sec..."<br>**Option 2:** "Peeking into your financial snapshot real quick..."<br>**Option 3:** "Taking a quick look at your budget..." | **Option 1:** "Budget checked"<br>**Option 2:** "All set, financial snapshot checked!"<br>**Option 3:** "Done! Budget analysis complete." |
| BudgetAgent | BudgetAgent query for financial information | **Option 1:** "I'm going over your budget numbers..."<br>**Option 2:** "Running the numbers behind the scenes..."<br>**Option 3:** "Crunching your financial data..." | **Option 1:** "Got it! Budget figures are ready"<br>**Option 2:** "Got it! Your numbers are ready to roll."<br>**Option 3:** "All done! Your budget insights are ready." |
| FinanceAgent | FinanceAgent call | **Option 1:** "I'm diving into the financial picture..."<br>**Option 2:** "Peeking into your financial snapshot real quick..."<br>**Option 3:** "Analyzing your financial landscape..." | **Option 1:** "I've got a scan on the finances."<br>**Option 2:** "All set, financial snapshot checked!"<br>**Option 3:** "Financial analysis complete!" |
| Finance Agent | FinanceAgent query to Knowledge Base | **Option 1:** "I'm checking my financial references..."<br>**Option 2:** "Flipping through my financial notes..."<br>**Option 3:** "Looking up financial guidance..." | **Option 1:** "I've gone trough the financial references."<br>**Option 2:** "All done, notes found and ready."<br>**Option 3:** "Found the financial insights you need!" |
| Education & Wealth CoachAgent | Education & Wealth CoachAgent call | **Option 1:** "Let me switch to guide mode for this one..."<br>**Option 2:** "Switching on brainy mode..."<br>**Option 3:** "Activating my coaching expertise..." | **Option 1:** "Here we go, a clear explanation ready"<br>**Option 2:** "All set, here's the wisdom straight up."<br>**Option 3:** "Ready! Here's your personalized guidance." |
| Education & Wealth CoachAgent | E&WCA query to KB or notes | **Option 1:** "I'm pulling together some articles..."<br>**Option 2:** "Gathering some helpful info for you..."<br>**Option 3:** "Collecting relevant resources..." | **Option 1:** "Found them useful info in hand"<br>**Option 2:** "All set, found some useful insights you can use."<br>**Option 3:** "Perfect! I've gathered some valuable resources." |

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

### Transitions
- **Smooth**: Messages guide user through the process
- **Contextual**: Each message relates to the specific agent action

## Extensibility

This scheme is designed to grow with new agents and processes:
- **New Agents**: Add new rows following the same pattern
- **New States**: Expand with additional states if needed
- **Customization**: Adapt phrases according to each agent's specific context

## Frontend Implementation

### Suggested Data Structure
```json
{
  "agent_states": {
    "planning": {
      "current": [
        "I'm Thinking... ",
        "Hmm, let me think this through...",
        "Let me figure out the best approach..."
      ],
      "completed": [
        "I thought for a moment",
        "Aha! Got the next step lined up.",
        "Perfect! I've got a plan."
      ]
    },
    "budget_agent": {
      "current": [
        "Let me peek into the budget for a sec...",
        "Peeking into your financial snapshot real quick...",
        "Taking a quick look at your budget..."
      ],
      "completed": [
        "Budget checked",
        "All set, financial snapshot checked!",
        "Done! Budget analysis complete."
      ]
    }
  }
}
```
