"""Memory processing and contextual prompts.

This module contains prompts related to memory processing, episodic memory summarization,
semantic memory extraction, and contextual icebreaker generation.
"""

# Memory Hotpath Trigger Classifier
MEMORY_HOTPATH_TRIGGER_CLASSIFIER_LOCAL = """You are a classifier that determines if user messages contain information worth storing as durable user facts (semantic memory).

Your task: Analyze the message and classify whether it contains NEW, DURABLE user information that should be remembered for future conversations.

## Classification Criteria

**STORE (return "store")** if the message contains:
- Personal facts about the user (age, location, occupation, family, preferences)
- Financial situation details (income, expenses, goals, challenges)
- Life circumstances (moving, job changes, relationship changes)
- Preferences or habits (how they like to be communicated with)
- Important context for future conversations

**IGNORE (return "ignore")** if the message contains:
- Casual conversation or small talk
- Questions asking for information
- Commands or requests for actions
- Emotional expressions without factual content
- Temporary states or current activities

## Response Format
Return ONLY a JSON object:
{"classification": "store|ignore", "reason": "brief explanation"}

## Examples

Input: "I'm 35 years old and work as a software engineer in San Francisco"
Output: {"classification": "store", "reason": "contains personal facts about age, occupation, and location"}

Input: "How much should I save for retirement?"
Output: {"classification": "ignore", "reason": "question asking for information, no personal facts"}

Input: "I'm feeling stressed about money lately"
Output: {"classification": "ignore", "reason": "emotional expression without durable facts"}"""

# Memory Same Fact Classifier
MEMORY_SAME_FACT_CLASSIFIER_LOCAL = """Same-Fact Classifier (language-agnostic)
Your job: Return whether two short summaries express the SAME underlying fact about the user.
Decide by meaning, not wording. Ignore casing, punctuation, and minor phrasing differences.

Core rules
1) Same subject: Treat these as the same subject: exact same name (e.g., Luna), or clear role synonyms
   (pet/cat/dog; spouse/partner/wife/husband; kid/child/son/daughter).
2) Same attribute: If both describe the same attribute (e.g., age in years, relationship/name, number of kids),
   then they are the SAME FACT even if phrased differently.
3) Numeric updates: If the attribute is numeric or count-like and changes plausibly (e.g., 3→4 years), treat as
   the SAME FACT (updated value).
4) Different entities: If the named entities differ (e.g., Luna vs Bruno) for the same attribute, NOT the same.
5) Preference contradictions: Opposite preferences (e.g., prefers email vs prefers phone) are NOT the same.
6) Episodic vs stable: One-off events vs stable facts are NOT the same.
7) Multilingual: Treat cross-language synonyms as equivalent (e.g., 'español' == 'Spanish').

Examples
- 'Luna is 3 years old.' vs 'Luna is 4 years old.' -> same_fact=true (numeric update)
- 'User's spouse is Natalia.' vs 'User's partner is Natalia.' -> same_fact=true (synonyms, same person)
- 'Has two children.' vs 'Has 2 kids.' -> same_fact=true (synonyms, same count)
- 'User prefers email.' vs 'User prefers phone calls.' -> same_fact=false (contradictory preference)
- 'Lives in Austin.' vs 'Moved to Dallas.' -> same_fact=false (different locations, not a numeric update)
- 'Luna is a cat.' vs 'Luna is a dog.' -> same_fact=false (conflicting species)

Output: Return STRICT JSON only: {"same_fact": true|false}. No extra text.
Category: {category}
Existing: {existing_summary}
Candidate: {candidate_summary}"""

# Memory Compose Summaries
MEMORY_COMPOSE_SUMMARIES_LOCAL = """Task: Combine two short summaries about the SAME user fact into one concise statement.
- Keep it neutral, third person, and include both details without redundancy.
- 1-2 sentences, max 280 characters.
- Do NOT include absolute dates or relative-time words (today, yesterday, this morning/afternoon/evening/tonight, last/next week/month/year, recently, soon).
- Express the timeless fact only.
Output ONLY the composed text.
Category: {category}
Existing: {existing_summary}
New: {candidate_summary}"""

# Episodic Memory Summarizer
MEMORY_EPISODIC_SUMMARIZER_LOCAL = """Episodic Summarizer
Task: Summarize the most recent interaction in 1-2 sentences focusing on what was decided, requested, clarified, planned, or acted on. Keep it short (≤160 chars).

Authority & Redaction:
- Do NOT include specific numeric financial values or facts owned by specialized agents.
- If budgets, balances, transactions, bills, investments, or goal targets/status/dates appear, summarize generically (e.g., 'Discussed budgeting approach', 'Reviewed spending trends').

Dates Policy:
- Do NOT include absolute dates or relative-time words in the summary. The system will add 'On YYYY-MM-DD (WNN, YYYY) ...' automatically.

Content Rules:
- Prefer decisions, actions, outcomes, next steps, or clear user asks over chit-chat.
- Neutral third person; no quotes; no PII.
- If nothing materially new happened, set summary to an empty string.

Category (choose one): Decision | Action | Plan | Request | Issue | Update | Reflection | Conversation_Summary
Importance (1..5): 1=chit-chat/minor; 2=question/clarification; 3=meaningful discussion; 4=decision/action; 5=commitment/urgent issue.

Output strict JSON only: {"summary": string, "category": string, "importance": 1..5}.

Conversation:
{conversation}
JSON:"""

# Profile Sync Extractor
MEMORY_PROFILE_SYNC_EXTRACTOR_LOCAL = """Task: From the memory summary below, extract user profile information that should be stored permanently.
Extract only explicitly stated facts. Do not infer or assume.

Output strict JSON with these optional keys:
{
  "preferred_name": string (only if the user stated their name),
  "language": string (e.g., "en-US", "es-ES"),
  "city": string (current city of residence),
  "tone": string (preferred communication style: "casual", "professional", "friendly"),
  "age": integer (user's age in years),
  "income_band": string (e.g., "under_25k", "25k_50k", "50k_75k", "75k_100k", "over_100k"),
  "money_feelings": string (how they feel about money: "anxious", "confused", "zen", "motivated"),
  "goals_add": [string] (list of financial goals to add, e.g., ["save for vacation", "pay off debt"])
}

Category: {category}
Summary: {summary}

JSON (only include fields explicitly mentioned):"""

# Icebreaker Generation Prompt
MEMORY_ICEBREAKER_GENERATION_PROMPT_LOCAL = """Create a warm, natural conversation starter based on this memory:

Memory:{icebreaker_text}

Requirements:
- Sound like a friendly, personal assistant (Vera)
- Use "you" instead of third person (e.g., "you enjoy hiking" not "Rick enjoys hiking")
- Make it conversational and engaging
- Keep it 1-2 sentences
- Don't mention "memories" or "I remember" - just reference it naturally
- Use a warm, encouraging tone

Examples:
- Memory: "Rick enjoys hiking in Golden Gate Park"
- Good: "I noticed you love hiking in Golden Gate Park! How's that been going lately?"
- Bad: "This came up in my memories: Rick enjoys hiking in Golden Gate Park."

Memory:{icebreaker_text}
Natural icebreaker:"""
