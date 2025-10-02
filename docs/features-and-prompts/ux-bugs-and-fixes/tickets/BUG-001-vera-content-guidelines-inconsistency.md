# BUG-001 Vera Content Guidelines Inconsistency

**Priority**: 🟡 Medium  
**Status**: Open  
**Assigned to**: [Developer name]  
**Report Date**: [DD/MM/YYYY]  
**Resolution Date**: [DD/MM/YYYY]  
**Component**: Content Guidelines / AI Presentation  
**Section**: User Experience / Brand Consistency  

---

## Description

Vera AI assistant is not consistently following established content guidelines regarding self-presentation, third-party service mentions, and content formatting. The AI is not adhering to the specified rules for introducing itself, mentioning Plaid, using em dashes, emojis, and maintaining empathetic tone.
---

## Pre-conditions

- Vera AI assistant is active and responding to user queries
- Content guidelines are defined but not being consistently applied
- User interactions are being processed through the AI system
---

## User for testing

- End users interacting with Vera AI
- QA team testing content consistency
- Product team reviewing brand presentation
---

## Steps to reproduce

1. Start a conversation with Vera AI assistant
2. Ask general questions about the service or company
3. Observe how Vera introduces itself
4. Check if Plaid is mentioned inappropriately in general UI
5. Review content for em dashes and emojis
6. Evaluate tone and empathy in responses
---

## Current results

- Vera may not consistently use "I'm Vera, an AI made by Verde" introduction
- Plaid may be mentioned in general UI instead of only when users ask about account connections
- Content may contain em dashes that should be removed
- Emojis may be present in content when they should be removed
- Tone may not consistently show empathy and follow-up questions
- Financial information may be prioritized over emotional support
---

## Expected results

- Vera should consistently introduce itself as "I'm Vera, an AI made by Verde"
- Plaid should only be mentioned when users explicitly ask about account connections, with the response: "We use Plaid, our trusted partner for securely connecting accounts"
- All content should be free of em dashes
- All content should be free of emojis
- Tone should consistently show empathy and include follow-up questions
- Emotional support should be prioritized over financial information

---

## Environment

- **Browser**: All browsers
- **OS**: All operating systems
- **Version**: Current production version
- **Device**: All devices
- **Screen Resolution**: All resolutions

---

## Evidence attached

- [ ] Screenshots of inconsistent introductions
- [ ] Screenshots of inappropriate Plaid mentions
- [ ] Content samples showing em dashes and emojis
- [ ] Examples of non-empathetic responses
- [ ] Console errors
- [ ] Other: Content audit logs

---

## Additional Notes

This bug affects brand consistency and user experience. The content guidelines appear to be well-defined but are not being consistently enforced across all AI interactions. This could lead to confusion about the service and inconsistent user experience.

---

## Related Links

- **Jira Ticket**: [Jira ticket link]
- **Figma Design**: [Figma design link]
- **Documentation**: Content Guidelines Documentation
- **Related Bugs**: [Links to related bugs]

---

## Development Checklist

### Analysis
- [ ] Review current AI prompt/instruction system
- [ ] Audit existing content for guideline violations
- [ ] Identify all places where content guidelines should be applied
- [ ] Create content consistency testing framework

### Development
- [ ] Update AI prompt system to enforce content guidelines
- [ ] Implement content validation checks
- [ ] Create automated content filtering for em dashes and emojis
- [ ] Update response templates to ensure consistent tone

### Testing
- [ ] Unit test content guideline enforcement
- [ ] Integration test with AI response system
- [ ] Regression test to ensure no new violations
- [ ] User acceptance test for tone and empathy
- [ ] Content audit across all user touchpoints

### Deployment
- [ ] Code review of content guideline changes
- [ ] Testing in staging environment
- [ ] Production deployment with monitoring
- [ ] Post-deployment content monitoring

---

## Contact and Assignment

**Assigned Developer**: [Name]  
**Assigned QA**: [Name]  
**Assigned Designer**: [Name]  
**Product Owner**: [Name]  

**Slack Channel**: #ux-bugs  
**Sprint**: [Assigned sprint]  

---

*Ticket created using the team standard bug template*
