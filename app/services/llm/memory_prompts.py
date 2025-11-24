"""Memory processing and contextual prompts.

This module contains prompts related to memory processing, episodic memory summarization,
semantic memory extraction, and contextual icebreaker generation.
"""


# Memory Hotpath Trigger Classifier
MEMORY_HOTPATH_TRIGGER_CLASSIFIER_LOCAL = """You classify whether to CREATE a user memory from recent user messages.
This node ONLY creates semantic memories (durable, re-usable facts).

CRITICAL: When multiple messages are provided, extract ONLY from the MOST RECENT (last) user message.
DO NOT mix information from different messages. Focus ONLY on the NEWEST MESSAGE'S CONTENT.

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
- When birthdays, ages, or dates are mentioned ONLY as part of a goal, plan, or event for someone else (for example, saving for another person's birthday), treat them as GOAL CONTEXT, not as the user's own identity attributes.
- NEVER rephrase another person's age or birthday as if it were the user's age or birthday.
- When the content is primarily about a financial goal or target (amounts, deadlines, goal progress), prefer {{"should_create": false}} and let the specialized goal/finance systems own those details.
- Do NOT create semantic memories when the message is primarily a greeting or conversation opener (for example, "hi", "hello", "hey Vera", "good morning") where no durable user fact is clearly stated.
- Only create name-related memories when the user explicitly states their own name (for example, "my name is Ana", "call me Ana", "I am Ana") instead of inferring from greetings that simply address the assistant.
- Choose category from: [{categories}].
- summary must be 1–2 sentences, concise and neutral (third person).
- Also produce display_summary for UI in second person (address the user as "you"). Keep the meaning identical to summary, without time words.
- importance: Rate 1-5 based on how critical this fact is for personalization (1=trivial, 3=useful, 5=essential like name/pronouns).
- Output ONLY strict JSON: {{"should_create": bool, "type": "semantic", "category": string, "summary": string, "display_summary": string, "importance": int}}.

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
- Input: 'Please remember my name is Ana' -> {{"should_create": true, "type": "semantic", "category": "Personal_Identity", "summary": "User's preferred name is Ana.", "display_summary": "Your preferred name is Ana.", "importance": 5}}
- Input: 'We usually speak Spanish at home' -> {{"should_create": true, "type": "semantic", "category": "Personal_Identity", "summary": "User usually speaks Spanish at home.", "display_summary": "You usually speak Spanish at home.", "importance": 4}}
- Input: 'I prefer email over phone calls' -> {{"should_create": true, "type": "semantic", "category": "Communication_Preferences", "summary": "User prefers email communication over calls.", "display_summary": "You prefer email communication over calls.", "importance": 3}}
- Input: 'I go to the gym on Tue/Thu' -> {{"should_create": true, "type": "semantic", "category": "Routines_Habits", "summary": "User goes to the gym on Tuesdays and Thursdays.", "display_summary": "You go to the gym on Tuesdays and Thursdays.", "importance": 3}}
- Input: 'My favorite book is Rich Dad Poor Dad' -> {{"should_create": true, "type": "semantic", "category": "Interests_Preferences", "summary": "User's favorite book is 'Rich Dad Poor Dad'.", "display_summary": "Your favorite book is 'Rich Dad Poor Dad'.", "importance": 3}}
- Input: 'My favorite restaurant is Bella Italia' -> {{"should_create": true, "type": "semantic", "category": "Interests_Preferences", "summary": "User's favorite restaurant is Bella Italia.", "display_summary": "Your favorite restaurant is Bella Italia.", "importance": 3}}
- Input: 'I prefer dark mode in apps' -> {{"should_create": true, "type": "semantic", "category": "Communication_Preferences", "summary": "User prefers dark mode in applications.", "display_summary": "You prefer dark mode in applications.", "importance": 2}}

Examples (corrections/updates):
- Input: 'Actually, my favorite book is El Inversor Inteligente' -> {{"should_create": true, "type": "semantic", "category": "Interests_Preferences", "summary": "User's favorite book on finance is 'El Inversor Inteligente'.", "importance": 3}}
- Input: 'I meant my name is Carlos, not Juan' -> {{"should_create": true, "type": "semantic", "category": "Personal_Identity", "summary": "User's preferred name is Carlos.", "importance": 5}}
- Input: 'Sorry, I go to the gym on Mon/Wed, not Tue/Thu' -> {{"should_create": true, "type": "semantic", "category": "Routines_Habits", "summary": "User goes to the gym on Mondays and Wednesdays.", "importance": 3}}

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

CRITICAL: If both summaries describe the SAME ATTRIBUTE (e.g., favorite book, age, city), return same_fact=true EVEN IF THE VALUES DIFFER.
EXCEPTION: Contradictory preferences (opposite choices for the same attribute, e.g., "prefers email" vs "prefers phone") are NOT the same fact.

Core rules
1) Same subject: Treat these as the same subject: exact same name (e.g., Luna), or clear role synonyms
   (pet/cat/dog; spouse/partner/wife/husband; kid/child/son/daughter).
2) Same attribute: If both describe the same attribute (e.g., age, name, favorite X, count of Y),
   then they are the SAME FACT even if phrased differently or values changed.
3) Numeric/value updates: If the attribute is the same but the value changed (3→4 years, Book A→Book B),
   treat as SAME FACT (updated value).
4) Different entities: If the summaries describe different entities (Luna vs Bruno) for different attributes,
   they are NOT the same.
5) Contradictory preferences: If the attribute is a PREFERENCE or CHOICE (prefers X, likes Y, chooses Z) and
   the values are opposites or mutually exclusive options, they are NOT the same fact.
   Examples: "prefers email" vs "prefers phone", "prefers casual tone" vs "prefers formal tone",
   "prefers dark mode" vs "prefers light mode".
6) Multilingual: Treat cross-language synonyms as equivalent (e.g., 'español' == 'Spanish').

Examples
- 'Luna is 3 years old.' vs 'Luna is 4 years old.' -> same_fact=true (same attribute, value changed)
- 'User's spouse is Natalia.' vs 'User's partner is Natalia.' -> same_fact=true (synonyms, same person)
- 'Has two children.' vs 'Has 2 kids.' -> same_fact=true (synonyms, same attribute)
- 'User's favorite book is Padre Rico Padre Pobre.' vs 'User's favorite book is El Inversor Inteligente.' -> same_fact=true (same attribute, value changed)
- 'User prefers email.' vs 'User prefers phone calls.' -> same_fact=false (contradictory preferences)
- 'User prefers casual tone.' vs 'User prefers professional tone.' -> same_fact=false (contradictory preferences)
- 'User prefers dark mode.' vs 'User prefers light mode.' -> same_fact=false (contradictory preferences)
- 'Lives in Austin.' vs 'Moved to Dallas.' -> same_fact=false (different locations, no clear update)
- 'Lives in Austin.' vs 'Lives in Dallas.' -> same_fact=true (same attribute - city, value changed)
- 'Luna is a cat.' vs 'Luna is a dog.' -> same_fact=false (conflicting species)
- 'User has a cat named Luna.' vs 'User has a dog named Bruno.' -> same_fact=false (different entities)

Output: Return Strict JSON only: {{"same_fact": true|false}}. No extra text.
Category: {category}
Existing: {existing_summary}
Candidate: {candidate_summary}"""

# Memory Compose Summaries
MEMORY_COMPOSE_SUMMARIES_LOCAL = """Task: Combine two short summaries about the SAME user fact into one concise statement.
- Keep it neutral, third person, and include both details without redundancy.
- 1-2 sentences, max 280 characters.
- Do NOT include absolute dates or relative-time words (today, yesterday, this morning/afternoon/evening/tonight, last/next week/month/year, recently, soon).
- Express the timeless fact only.

Existing: {existing_summary}
New: {candidate_summary}

Output only the combined sentence. No preamble, no labels, just the merged fact."""

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

Output strict JSON with these keys:
{{
  "about_user": bool (true only if the summary clearly refers to the user themself; false otherwise),
  "preferred_name": string (only if the user stated their name),
  "language": string (e.g., "en-US", "es-ES"),
  "city": string (current city of residence),
  "tone": string (preferred communication style: "casual", "professional", "friendly"),
  "age": integer (user's age in years),
  "income_band": string (e.g., "under_25k", "25k_50k", "50k_75k", "75k_100k", "over_100k"),
  "money_feelings": string (how they feel about money: "anxious", "confused", "zen", "motivated"),
  "goals_add": [string] (list of financial goals to add, e.g., ["save for vacation", "pay off debt"])
}}

Rules:
- Set "about_user" to true ONLY when the summary clearly describes the user themself (first person statements like "I am 30", "my birthday is May 5", "I live in Austin", or explicit "the user" phrasing).
- If the summary is primarily about someone else (family member, friend, colleague, pet, etc.) or about a shared event (for example, saving for another person's birthday), set "about_user" to false.
- When "about_user" is false, you MUST NOT output identity fields for the user ("preferred_name", "language", "city", "tone", "age", "income_band", "money_feelings"); only "goals_add" is allowed in that case.
- Only extract age when it unambiguously refers to the user's own age. Do NOT treat another person's age or birthday as the user's age.
- Names that appear only as part of a greeting or direct address to someone else (for example, "hey Ana") MUST NOT be treated as the user's "preferred_name". Only set "preferred_name" when the summary clearly states the user's own name (for example, "User's preferred name is Ana.", "my name is Ana").
- If the summary mentions an assistant or product name (for example, "Vera") without explicitly stating that it is the user's name, you MUST NOT set "preferred_name" to that value.
- Use "goals_add" for goal descriptions (for example, "save for father's birthday") without turning other people's attributes into user identity.

Category: {category}
Summary: {summary}

JSON (include only fields that are explicitly supported above and actually mentioned in the summary):"""

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

MEMORY_MERGE_SUMMARIES_LOCAL = """You are an expert at consolidating and merging memory summaries for a financial advisory AI assistant named Vera.

You will receive multiple memory summaries that are similar in content. Your task is to:
1. Deduplicate the information across all summaries
2. Create a single, unified summary that captures all unique information
3. Preserve the style and format of the original summaries
4. **CRITICAL:** When summaries contain CONTRADICTORY information (different values for the same fact), use ONLY the information from the NEWEST summary (listed last). Do not combine or mention both values.
5. Determine an appropriate importance score (1-10) for the merged memory

**Memory Type:** {memory_type}
**Category:** {category}

**Original Summaries (oldest to newest):**
{summaries_text}

**Original Importance Scores:**
{importances_text}

Please provide your response as a JSON object with this exact format:
{{
  "merged_summary": "your unified, deduplicated summary here",
  "importance": 5,
  "reasoning": "brief explanation of why you chose this importance"
}}

Guidelines:
- Keep the merged summary concise but comprehensive (max 300 characters)
- **For contradictory facts:** Use ONLY the newest value, ignore older values completely
- Preserve key facts, preferences, and details that are NOT contradictory
- Avoid redundancy - don't repeat the same information
- Maintain the conversational, natural style
- The importance score should reflect the significance of this information to the user's profile
- For episodic memories, preserve temporal context if present
- Examples of contradictions: different ages, different amounts, different locations for the same thing

JSON:"""

