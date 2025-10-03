# BUG-003 Summarizer Narrative Perspective Inconsistency

**Priority**: 🟡 Medium  
**Status**: Open  
**Assigned to**: [Developer name]  
**Report Date**: [Current Date]  
**Resolution Date**: [TBD]  
**Component**: ConversationSummarizer  
**Section**: Memory System / Conversation Management  

---

## Description

The `ConversationSummarizer` in `app/agents/supervisor/summarizer.py` generates conversation summaries with inconsistent narrative perspective and person conjugations. The summarizer sometimes refers to Vera in third person ("Vera responded"), other times in second person ("You are Vera"), and uses varying conjugations for the user ("the user asked" vs "You asked"). This creates an inconsistent user experience and weakens Vera's personal assistant identity.

---

## Pre-conditions

- User has an active conversation with Vera
- Conversation has enough messages to trigger summarization (exceeds token budget)
- Summarizer is enabled and functioning

---

## User for testing

- Any user with an active conversation history
- Users who have had multiple conversation turns with Vera
- Users who can observe the conversation summary functionality

---

## Steps to reproduce

1. Start a conversation with Vera
2. Have multiple back-and-forth exchanges (10+ messages)
3. Continue the conversation until summarization is triggered
4. Observe the generated summary in the conversation context
5. Check if the summary maintains consistent narrative perspective

---

## Current results

- Summaries use inconsistent person conjugations
- Sometimes: "The user asked about finances, Vera provided guidance"
- Sometimes: "You asked about finances, I provided guidance"  
- Sometimes: "User inquired about financial planning, assistant responded"
- No consistent narrative perspective maintained across summaries

---

## Expected results

- All summaries should maintain consistent narrative perspective
- Always refer to Vera as "Me" (first person)
- Always refer to the user as "You"
- Use "we" when appropriate for shared context
- Maintain the same perspective throughout the entire summary

---

## Environment
- **Device**: Any (Backend issue)

---

## Additional Notes

- This is a prompt engineering issue, not a code logic issue
- The fix requires modifying the system instruction in the summarizer prompt
- No changes to the core summarization logic are needed
- The fix should be minimal and low-risk
- This affects the user's perception of Vera's consistency and personality
