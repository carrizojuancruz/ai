# Summarizer Fix - Consistent Narrative Perspective

## Identified Problem

The `ConversationSummarizer` currently generates summaries with inconsistent person conjugations. Sometimes it uses "the user asked", other times "Vera responded", etc., which creates inconsistencies in the narrative perspective.

## Recommended Solution

Modify the summarizer prompt in `app/agents/supervisor/summarizer.py` to establish a consistent narrative perspective.

### Proposed Change

**Location:** Lines 78-82 in `summarizer.py`

**Current Prompt:**
```python
system_instr = (
    "You are a summarizer. Summarize the following earlier conversation strictly as a concise, "
    "factual summary for internal memory. Do not answer user questions. Do not provide step-by-step instructions. "
    f"Limit to roughly {self.summary_max_tokens} tokens. Use 3-7 bullet points, neutral tone."
)
```

**Improved Prompt:**
```python
system_instr = (
    "You are a summarizer. Summarize the following earlier conversation strictly as a concise, "
    "factual summary for internal memory. Do not answer user questions. Do not provide step-by-step instructions. "
    f"Limit to roughly {self.summary_max_tokens} tokens. Use 3-7 bullet points, neutral tone. "
    "IMPORTANT: Always maintain consistent narrative perspective - refer to Vera as 'Me' "
    "and the user as 'You'. Use 'we' when appropriate. Keep the same perspective throughout the summary."
)
```