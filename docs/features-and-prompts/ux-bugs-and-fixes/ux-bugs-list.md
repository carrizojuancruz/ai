# UX Bugs & Fixes - Vera AI

> **Fuente original**: [Atlassian Wiki - VA Space](https://verdemoney.atlassian.net/wiki/spaces/VA/pages/180617234/UX+Bugs+Fixes)  
> **Última sincronización**: 29 de septiembre de 2024  
> **Mantenedor**: Equipo de UX/UI - Verde Money

---

## 🐛 Bugs de UI/UX Identificados

| Título | Descripción | Comportamiento Esperado | Imágenes (app actual) | Path/Location | Jira ticket |
|--------|-------------|------------------------|----------------------|---------------|-------------|
| Fix width for user messages | User messages have a maximum width but for smaller sizes, the container adapts to the message width. For larger sizes, content overflows vertically. | User message should wrap around the text written, and have a maximum size. (the current max size seems ok) | ![image-20250929-172858.png](image-20250929-172858.png) | /chat -> all apps | [EN-667: Fix width handling for user messages](https://verdemoney.atlassian.net/browse/EN-667) - To Do |
| Skip button - Stepper disabled state | The skip button doesn't appear disabled in the stepper when asking for age. | The "Skip ->" label should show reduced opacity when disabled. | | Guided path -> Age question | [EN-668: Onboarding - Skip button should be disabled for age question](https://verdemoney.atlassian.net/browse/EN-668) - PROD |
| Multiple options hierarchy | Multiple options should not have one prioritized option - all options should be at the same hierarchical level. | | | Guided path -> Multiple options | [EN-672: First button in multiple-choice question appears preselected](https://verdemoney.atlassian.net/browse/EN-672) - DEV |
| Home vertical scroll issue | On the home page, vertical scrolling cuts off hidden content instead of allowing it to scroll underneath. | Content should scroll behind the icebreaker chat, not cut off. | ![image-20250929-173319.png](image-20250929-173319.png) | Home & sections | TBD |
| Header bar styling | Polish the top bar styling to match the design specifications. In some screens the hamburger menu appears inside the bar, in others on top. | All screens (Except chat) should have the top bar either showing the filters, or a breadcrumb. | ![image-20250929-173209.png](image-20250929-173209.png) ![image-20250929-173218.png](image-20250929-173218.png) | Global - Header component | [EN-675: Goals view in home screen (not goals section)](https://verdemoney.atlassian.net/browse/EN-675) - To Do |
| Icebreaker icon spacing | Add an 4px gap between the icon and text in the icebreaker component. | | ![image-20250929-173314.png](image-20250929-173314.png) | Home & sections | TBD |
| Reminder options issue | The reminder feature displays both options simultaneously, which creates confusion and needs to be redesigned. | | | /settings - Payment reminders | TBD |
| Admin spacing adjustments | Adjust spacing between header, navigation bar, and content in admin panel. Ensure 12px spacing between bar and content. | | | /All app | TBD |
| **Table markdown formatting** | Response returned a table that should be formatted with proper markdown styling for at least basic formatting layers. | | | /Chat - All app | [EN-673: Markdown parser formatting issues with lists and headings](https://verdemoney.atlassian.net/browse/EN-673) - PROD |
| Free trial banner | The text inside the free trial banner is too small and lacks hierarchy | First line should be H6/medium, color/text/light/first; and the second line should be body/regular/small & color/text/light/third | ![image-20250929-173459.png](image-20250929-173459.png) | | TBD |
| Side menu transparency | The side drawer containing the menu is full opacity white | Its fill should be the style named "glass-bg-1". Its border the style "glass_border-2" | ![image-20250929-173823.png](image-20250929-173823.png) | | TBD |
| Repeated titles | In some screens, in addition to the double hamburger menu, the page title is repeated. | There should only be one. The white background one that also acts as a breadcrumb. | ![image-20250929-173947.png](image-20250929-173947.png) | | TBD |
| Home indicator white bg | The home indicator (the horizontal line at the bottom of the screen) is currently being displayed with a white bg | The home indicator should appear on top of the app's background. | | | TBD |
| Adjust top elements as design | The hamburger menu is separated from top elements. | | | | [EN-675: Goals view in home screen (not goals section)](https://verdemoney.atlassian.net/browse/EN-675) - To Do |

---

## 🤖 Agent-Specific Fixes

### Guest:
- [x] Do not mention "guest agent" or "guest chat." Use "conversation" instead.
- [x] Add a hardcoded extra system message after the 5th message: "Hey, by the way, our chat here is a bit limited... If you sign up or log in, I can remember everything we talk about and help you reach your goals. Sounds good?"

### Supervisor:
- [x] Use "I'm Vera, an AI made by Verde." Do not mention Verde Inc, Verde Money, OpenAI, or Anthropic models.
- [x] Do not mention Plaid in general UI, onboarding, or flows. Only if the user explicitly asks about account connections, respond with: "We use Plaid, our trusted partner for securely connecting accounts."
- [x] Remove em dashes from content.
- [x] Remove emojis from all content.
- [x] Ensure tone shows empathy and follow-up questions. Prioritize emotions over finances. - [EN-703: Supervisor Prompt Improvements](https://verdemoney.atlassian.net/browse/EN-703) - In Progress
- [ ] [Checklist for supervisor](https://verdemoney.atlassian.net/wiki/spaces/VA/pages/183205903/Checkist+for+Supervisor+improvements)
- [ ] Use bullet points instead of dashes for lists. (FRONT) - [EN-672: First button in multiple-choice question appears preselected](https://verdemoney.atlassian.net/browse/EN-672) - DEV

### Onboarding:
- [x] Use either binary buttons or text, not both. - [EN-671: Text input enabled when binary choice buttons are presented](https://verdemoney.atlassian.net/browse/EN-671) - PROD
- [ ] Generate multiple categories as non-prioritized suggestions. - [EN-672: First button in multiple-choice question appears preselected](https://verdemoney.atlassian.net/browse/EN-672) - DEV
- [ ] Last step on onboarding is missed (subscription) after connecting accounts - [EN-693: Subscription screen is skipped after connecting accounts](https://verdemoney.atlassian.net/browse/EN-693) - To Do

---

## Pinned Messages:
- [ ] Fix pinned messages rendering: currently showing markdown and returning JSON instead of proper chat display - [EN-645: Android - Pinned messages show broken formatting](https://verdemoney.atlassian.net/browse/EN-645) - To Do
- [ ] Improve chat experience when user starts conversation from a pinned message as context

## Chat:
- [ ] Are we missing the initialize, close, and context bars. Instead, we need to remove the navigation bar when we're inside a conversation. - [EN-702: Missing initialize, close, and context bars in chat](https://verdemoney.atlassian.net/browse/EN-702) - To Do

## Thinking timeline:
- [ ] Fix thinking timeline: intermediate steps should stay in "current" status and not move to "completed" (dictionary issue). - [EN-702: Missing initialize, close, and context bars in chat](https://verdemoney.atlassian.net/browse/EN-702) - To Do
- [ ] Fix thinking timeline bug: repeated events are appearing. - [EN-680: Thinking Timeline bug – repeated messages](https://verdemoney.atlassian.net/browse/EN-680) - To Do
- [ ] Fix thinking timeline icons and styles that are incorrectly applied. Check Figma for correct implementation. - [EN-708: Improvements on Thinking Timeline Implementation](https://verdemoney.atlassian.net/browse/EN-708) - To Do

## Home page
- [ ] Fix excess space at the top. Menu bar is misaligned and the 'All' category is missing. Check Figma. - [EN-675: Goals view in home screen (not goals section)](https://verdemoney.atlassian.net/browse/EN-675) - To Do
- [ ] Remove white bottom margin from all screens. - [EN-676: Remove white bottom margin from all screens (iOS)](https://verdemoney.atlassian.net/browse/EN-676) - To Do
- [ ] Polish empty state for Goals in app - it doesn't reflect the Figma design. - [EN-675: Goals view in home screen (not goals section)](https://verdemoney.atlassian.net/browse/EN-675) - To Do

## Goals section - [EN-678: Improvements to Goals section](https://verdemoney.atlassian.net/browse/EN-678) - To Do
- [ ] Remove summary view from specific goal chats in the goals agent.
- [ ] When expanding a goal summary, content should overlay the rest of the content with frozen background (not scrollable) while overlay is active.
- [ ] Fix date formatting visual error in goals.
- [ ] Hide end date on frontend when not set. End date is not mandatory.
- [ ] Fix Goals filter dropdown behavior on home page: chevron should point **down** when closed, **up** when open.
- [ ] Disable filter states that don't have any goals included to avoid empty state screen - [EN-682: Improvement Goals section filtering](https://verdemoney.atlassian.net/browse/EN-682) - To Do

## Memories section - [EN-677: Bugs in Memories section (wording and classification)](https://verdemoney.atlassian.net/browse/EN-677) - To Do
- [ ] Add sorting functionality: show newest to oldest.
- [ ] Change phrasing from "User is..." to **"You are..."**.
- [ ] Fix date display: memories only show one date without indicating if it's created or updated.
- [ ] Add "used" information to memories display.

## Empty states
- Empty state for Income & Expenses
- Empty state for Reminder sections

---

## 📋 Bug Template (Team Standard)

```markdown
### [BUG-ID] Bug Title

**Priority**: 🔴/🟡/🟢 [Critical/Medium/Low]  
**Status**: Open/In Progress/Resolved/Closed  
**Assigned to**: [Developer name]  
**Report Date**: [DD/MM/YYYY]  
**Resolution Date**: [DD/MM/YYYY]  

**Description**:
[Detailed description of the problem]

**Pre-conditions**:
[Conditions that must be met before reproducing the bug]

**User for testing**:
[Type of user or user role that should test this]

**Steps to reproduce**:
1. [Step 1]
2. [Step 2]
3. [Step 3]

**Current results**:
[What is currently happening]

**Expected results**:
[What should happen]

**Environment**:
- **Browser**: [Chrome/Firefox/Safari/etc.]
- **OS**: [Windows/Mac/Linux/iOS/Android]
- **Version**: [Specific version]
- **Device**: [Desktop/Mobile/Tablet]
- **Screen Resolution**: [e.g., 1920x1080]

**Evidence attached**:
- [ ] Screenshots
- [ ] Videos
- [ ] Logs
- [ ] Console errors
- [ ] Network requests
- [ ] Other: [specify]

**Additional Notes**:
[Any other relevant information]
```

---

## 🛠️ Herramientas y Recursos

### Herramientas de Reporte
- **Atlassian Jira**: [Proyecto EN](https://verdemoney.atlassian.net/browse/EN-667)
- **Figma**: [Enlace a designs]
- **Sentry**: [Enlace a errores en producción]

### Tickets Detallados
- **Carpeta de Tickets**: [`tickets/`](./tickets/) - Tickets detallados para cada bug
- **Plantilla del Equipo**: [`tickets/templates/bug-template.md`](./tickets/templates/bug-template.md) - Template estándar del equipo
- **Ejemplo de Ticket**: [`tickets/chat-navigation-bars-bug.md`](./tickets/chat-navigation-bars-bug.md) - Bug de barras de navegación en chat

---

*Este documento está sincronizado con la página de Confluence. Última actualización: 29 de septiembre de 2024.*
