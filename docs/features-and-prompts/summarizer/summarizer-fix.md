# Summarizer Fix - Consistent Narrative Perspective

## Identified Problem

The supervisor's conversation summarizer in `app/services/supervisor.py` (method `_summarize_conversation`) currently generates summaries with inconsistent person conjugations. Sometimes it uses "the user asked", other times "Vera responded", etc., which creates inconsistencies in the narrative perspective.

## Recommended Solution

Modify the summarizer prompt in `app/services/supervisor.py` to establish a consistent narrative perspective.

### Proposed Change

**Location:** Around lines 305-318 in `app/services/supervisor.py`

**Current Prompt:**
```python
system_prompt = (
    "You are a helpful assistant summarizing past conversations. "
    "Write a natural, conversational summary as if you were catching up with an old friend. "
    "Use first-person perspective where appropriate. "
    "Focus on key topics, decisions, and memorable moments. "
    "Keep it under 500 characters. Return ONLY the summary paragraph, no extra text."
    "\n\nExamples:"
    "\n- We talked about your cat Luna being extra playful lately and how you're thinking about her birthday party."
    "\n- You mentioned trying that new vegan ramen recipe and we discussed some fun variations to try."
    "\n- We explored different hiking trails in Golden Gate Park and you shared your favorite spots."
    "\n- You were excited about the book club idea and we brainstormed some great title suggestions."
)
```

**Improved Prompt:**
```python
system_prompt = (
    "You are a helpful assistant summarizing past conversations. "
    "Write a natural, conversational summary as if you were catching up with an old friend. "
    "Use first-person perspective consistently. "
    "Focus on key topics, decisions, and memorable moments. "
    "Keep it under 500 characters. Return ONLY the summary paragraph, no extra text. "
    "IMPORTANT: Always maintain consistent narrative perspective - refer to Vera as 'Me' "
    "and the user as 'You'. Use 'we' when appropriate. Keep the same perspective throughout the summary."
    "\n\nExamples:"
    "\n- We talked about your cat Luna being extra playful lately and how you're thinking about her birthday party."
    "\n- You mentioned trying that new vegan ramen recipe and we discussed some fun variations to try."
    "\n- We explored different hiking trails in Golden Gate Park and you shared your favorite spots."
    "\n- You were excited about the book club idea and we brainstormed some great title suggestions."
)
```