"""Memory processing and contextual prompts.

This module contains prompts related to memory processing, episodic memory summarization,
semantic memory extraction, and contextual icebreaker generation.
"""


# Memory Hotpath Trigger Classifier
MEMORY_HOTPATH_TRIGGER_CLASSIFIER_LOCAL = """You classify whether to CREATE a user memory from recent user messages.
This node ONLY creates semantic memories (durable, re-usable facts).

Semantic scope includes (non-exhaustive):
- Identity & relationships: preferred name/pronouns; partner/family/pets; roles (student/parent/manager).
- Stable attributes: age/birthday, home city/region, employer/school, time zone, languages.
- Preferences & constraints: communication channel, tone, dietary, risk tolerance, price caps, brand/tool choices.
- Recurring routines/schedules: weekly reviews on Sundays, gym Tue/Thu.
- Memberships/subscriptions/providers: bank, insurer, plan tiers.

Rules:
- If the user explicitly asks to 'remember' something, set should_create=true.
- Create semantic if the message states OR UPDATES a stable fact about the user or close entities.
- DO NOT create here for time-bound events/experiences or one-off actions (episodic handled later).
- DO NOT create for meta/capability questions such as 'what do you know about me', 'do you remember me',
  'what's in my profile', 'what have you saved about me'.
- For the summary: NEVER include absolute dates or relative-time words (today, yesterday, this morning/afternoon/evening/tonight, last/next week/month/year, recently, soon).
- If the input mixes time-bound details with a durable fact, EXTRACT ONLY the durable fact and DROP time phrasing.
- If uncertain about durability or domain, return {{"should_create": false}}.
- Extract only explicitly stated facts; do not infer or summarize plans/requests as facts.
- Choose category from: [{categories}].
- summary must be 1–2 sentences, concise and neutral (third person).
- Output ONLY strict JSON: {{"should_create": bool, "type": "semantic", "category": string, "summary": string, "importance": 1..5}}.

AUTHORITATIVE DOMAINS POLICY — NEVER create semantic memories for facts owned by specialized agents:
- Finance (Plaid/SQL): budgets, balances, account details, transaction totals, spending amounts/trends, bills due, interest rates.
- Goals system: goal targets/amounts/percentages, dates/timelines, statuses (in_progress/completed/etc.).
- Wealth knowledge: investment returns/rules, financial program/tax rules, general financial facts.
If the input asserts a numeric financial value or any detail above, return {{"should_create": false}}.
Even if the user says 'remember ...', still return {{"should_create": false}} for these domains.

Hard negatives — Finance/Goals/Wealth actions & queries:
- If the input is a question or command about amounts, targets, budgets, bills, balances, accounts, transactions,
  goals, interest, investments, etc., return {{"should_create": false}} even if the user says "remember".
- Heuristics (non-exhaustive):
  - Imperatives with finance/goal terms: set/create/update/change/increase/decrease/add/remove/track/calculate/review
    + (budget|spend(ing)|expense(s)|bill(s)|payment(s)|balance(s)|account(s)|transaction(s)|goal|target|percent(age)|interest|rate|APR|investment(s)).
  - Currency cues: presence of $, €, £, or amounts tied to those terms.
  - Pure queries for amounts/status/dates (e.g., "How much did I spend last month?").

Examples (create):
- Input: 'Please remember my name is Ana' -> {{"should_create": true, "type": "semantic", "category": "Personal_Identity", "summary": "User's preferred name is Ana.", "importance": 2}}
- Input: 'We usually speak Spanish at home' -> {{"should_create": true, "type": "semantic", "category": "Personal_Identity", "summary": "User usually speaks Spanish at home.", "importance": 2}}
- Input: 'I prefer email over phone calls' -> {{"should_create": true, "type": "semantic", "category": "Communication_Preferences", "summary": "User prefers email communication over calls.", "importance": 2}}
- Input: 'I go to the gym on Tue/Thu' -> {{"should_create": true, "type": "semantic", "category": "Routines_Habits", "summary": "User goes to the gym on Tuesdays and Thursdays.", "importance": 2}}

Examples (do not create here):
- Input: 'We celebrated at the park today' -> {{"should_create": false}}
- Input: 'Book an appointment' -> {{"should_create": false}}
- Input: 'What do you know about me?' -> {{"should_create": false}}
- Input: 'Do you remember me?' -> {{"should_create": false}}
- Input: 'What have you saved in my profile?' -> {{"should_create": false}}
- Input: 'Increase my groceries budget to $400.' -> {{"should_create": false}}
- Input: 'Set my emergency fund goal to 2000.' -> {{"should_create": false}}
RecentMessages:
{text}
JSON:"""

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
