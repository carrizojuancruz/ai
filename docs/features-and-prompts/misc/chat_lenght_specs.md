# Chat Message Length Specifications

## Overview

This document provides **flexible guidelines** for message lengths across different communication contexts within Vera. These are **soft guidelines** designed to optimize user experience, comprehension, and engagement - not rigid rules that must be followed in every interaction.

> **Note:** These are flexible guidelines that should adapt to user needs, conversation context, and emotional state. Prioritize natural conversation flow over strict adherence to character counts.

---

## Message Categories & Guidelines

| **Context** | **Length Range** | **Tone** | **Primary Use** |
|-------------|------------------|----------|-----------------|
| **Quick Support & Chat** | 200-400 chars | Warm, direct, conversational with hook questions | Direct responses, quick clarifications, simple confirmations |
| **Onboarding & Setup** | 300-500 chars | Supportive, explanatory, with clear next steps | Guided explanations, setup processes, user guidance |
| **Educational & Complex Queries** | 500-1,500 chars | Educational, encouraging, with detailed explanations | Financial education, investment explanations, complex planning |

---

## Message Examples

### Quick Support & Chat (200-400 characters)

#### Example 1: (134 characters)
```text
"Thanks for sharing that! It helps me understand your situation better. What's your biggest financial concern right now?"
```

#### Example 2: (130 characters)
```text
"I get that money can feel overwhelming sometimes. What would make you feel more confident about your finances?"
```

#### Example 3: (102 characters)
```text
"That's a great goal! Want to explore some practical steps to get there together?"
```

### Onboarding & Setup (300-500 characters)

#### Example 1: (320 characters)
```text
"I appreciate you being open with me about your income situation. This helps me tailor recommendations that actually work for your reality and connect you with the right resources. You can share a general range or skip this entirely - no pressure. What feels comfortable for you?"
```

#### Example 2: (350 characters)
```text
"Money stress is so common, and you're not alone in feeling this way. Understanding your current expenses helps me suggest realistic changes that won't add more pressure to your daily life. Would you like to walk through this together? We can start with just one category."
```

### Educational & Complex Queries (500-1,500 characters)

#### Example 1: Emergency Fund Education (1,180 characters)
```text
"I love that you're thinking about building an emergency fund - it's one of the most powerful financial moves you can make. Think of it as your financial safety net that gives you peace of mind when life throws curveballs. 

The Consumer Financial Protection Bureau (CFPB) recommends 3-6 months of expenses, but here's the thing: start small. Even $500 can prevent you from going into debt for unexpected car repairs or medical bills. The key is consistency over perfection.

Here's a practical approach: First, calculate your essential monthly expenses (rent, utilities, groceries, minimum debt payments). Then set a realistic first goal - maybe $1,000 or one month's expenses. The CFPB has a great emergency fund guide that breaks this down step by step.

You can also explore high-yield savings accounts or even Treasury I-Bonds through TreasuryDirect.gov, which are inflation-protected and backed by the U.S. government. These often offer better returns than traditional savings accounts.

What feels like a realistic first goal for your emergency fund? We can break it down into manageable monthly amounts and I can point you to some trusted government resources to help you get started."
```

#### Example 2: Investment Education (1,050 characters)
```text
"You mentioned feeling lost about investing, and honestly, that's exactly how most people feel at first. The financial world has made investing seem way more complicated than it needs to be.

Here's what I want you to know: you don't need to be a Wall Street expert to build wealth over time. The magic happens through compound interest - basically, your money making money on itself. Even small, regular contributions can grow significantly over decades.

The SEC's Investor.gov has excellent educational resources that break down investing basics without the jargon. They explain everything from how compound interest works to how to avoid common investment scams. FINRA also provides unbiased investor education that's perfect for beginners.

For young adults, I often recommend starting with low-cost index funds or target-date funds through your employer's 401(k) or an IRA. The key is starting early and staying consistent, even when markets feel scary. Remember, you're investing for the long term, not trying to time the market.

What's your timeline for wanting to see growth? This helps me suggest the right approach and point you to the most relevant government resources for your situation."
```

#### Example 3: Complex Financial Planning (1,200 characters)
```text
"You're asking about balancing debt payoff with retirement savings - this is one of the most common financial dilemmas people face. The answer depends on several factors: your debt interest rates, employer 401(k) matching, your age, and your risk tolerance.

Here's a framework to think through this: First, always contribute enough to your 401(k) to get the full employer match - that's free money. Second, if your debt has high interest rates (above 6-7%), prioritize paying that down aggressively. Third, consider your timeline - if you're young, compound interest in retirement accounts can be incredibly powerful over decades.

The CFPB has excellent resources on debt management strategies, and the SEC's Investor.gov explains how compound interest works in retirement accounts. What's your current debt situation like, and do you have access to an employer 401(k) with matching?"
```

---

## Hook Questions by Context

### Quick Support & Chat
```text
"Would you like me to help you set up your financial profile?"
"Is there something specific about your budget you'd like to review?"
"Want to explore some savings options together?"
```

### Educational & Complex Queries
```text
"Are you interested in diving deeper into any of these strategies?"
"How do you feel about your current level of financial knowledge?"
"What's your current debt situation like, and do you have access to an employer 401(k) with matching?"
```

---

## UX Considerations

### Context-Aware Adaptation
- **User Preference:** Adjust message length based on user's demonstrated preference
- **Conversation History:** Consider previous interactions and engagement patterns  
- **Topic Complexity:** Adapt to the complexity of the subject being discussed
- **Device Context:** Consider mobile vs desktop experience
- **Emotional State:** Shorter messages when user seems overwhelmed, longer when engaged

### Best Practices
- **Natural Flow:** Hook questions should feel natural and relevant to the conversation context
- **Personalization:** Avoid generic questions; personalize based on user's current situation and goals
- **Language Clarity:** Use clear, concise language regardless of message length
- **Chunking Strategy:** Break longer messages into digestible paragraphs when possible
- **Consistent Voice:** Maintain Vera's tone and personality across all message lengths

---

## Implementation Notes

### Testing & Optimization
These guidelines serve as starting points and should be refined based on user feedback

- A/B Testing: Test different message lengths to optimize engagement metrics
- User Analytics: Monitor response rates, completion rates, and user satisfaction
- Feedback Loop: Regularly review user feedback and conversation analytics