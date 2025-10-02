# UX Bug Tickets - Verde Money

This folder contains detailed tickets for each bug identified in the main document `ux-bugs-list.md`. All tickets follow the **team standard bug template**.

## 📁 File Structure

```
tickets/
├── README.md                           # This file
├── chat-navigation-bars-bug.md        # Chat navigation bars bug
├── [bug-name]-bug.md                  # Other tickets (to be created)
└── templates/
    └── bug-template.md                # Team standard template
```

## 🎯 Purpose

Each ticket in this folder provides:

- **Detailed description** of the problem
- **Pre-conditions** for reproduction
- **User testing requirements** 
- **Step-by-step reproduction** guide
- **Current vs Expected results** comparison
- **Environment specifications**
- **Evidence collection** checklist
- **Development workflow** guidance

## 📋 Team Standard Template

All tickets follow this structure:

```markdown
# [BUG-ID] Bug Title

**Priority**: 🔴/🟡/🟢 [Critical/Medium/Low]  
**Status**: Open/In Progress/Resolved/Closed  
**Assigned to**: [Developer name]  
**Report Date**: [DD/MM/YYYY]  
**Resolution Date**: [DD/MM/YYYY]  

## Description
[Detailed description of the problem]

## Pre-conditions
[Conditions that must be met before reproducing the bug]

## User for testing
[Type of user or user role that should test this]

## Steps to reproduce
1. [Step 1]
2. [Step 2]
3. [Step 3]

## Current results
[What is currently happening]

## Expected results
[What should happen]

## Environment
- **Browser**: [Chrome/Firefox/Safari/etc.]
- **OS**: [Windows/Mac/Linux/iOS/Android]
- **Version**: [Specific version]
- **Device**: [Desktop/Mobile/Tablet]
- **Screen Resolution**: [e.g., 1920x1080]

## Evidence attached
- [ ] Screenshots
- [ ] Videos
- [ ] Logs
- [ ] Console errors
- [ ] Network requests
- [ ] Other: [specify]

## Additional Notes
[Any other relevant information]
```

## 📋 Naming Conventions

**Format**: `[component]-[short-description]-bug.md`

**Examples**:
- `chat-navigation-bars-bug.md`
- `home-scroll-issue-bug.md`
- `header-styling-bug.md`
- `goals-filter-dropdown-bug.md`

## 🔄 Workflow

1. **Create ticket** using the team standard template
2. **Assign developer** and QA based on component
3. **Set pre-conditions** and user testing requirements
4. **Develop** following the checklist
5. **Test** according to environment specifications
6. **Collect evidence** as specified in checklist
7. **Deploy** and monitor
8. **Close ticket** when resolved

## 📊 Ticket Status

| Status | Description | Color |
|--------|-------------|-------|
| 🔴 Open | Ticket created, pending assignment | Red |
| 🟡 In Progress | Assigned, being developed | Yellow |
| 🔵 In Review | Developed, pending QA | Blue |
| 🟢 Resolved | Completed and verified | Green |
| ⚫ Closed | Ticket permanently closed | Black |

## 🛠️ Related Tools

- **Jira**: Main project tickets
- **Figma**: Designs and mockups
- **GitHub**: Code and pull requests
- **Slack**: Team communication
- **Testing Tools**: Browser dev tools, testing frameworks

## 📞 Contact

For questions about tickets or bugs:
- **Slack**: #ux-bugs
- **Email**: ux-team@verdemoney.com
- **Product Owner**: [Name and contact]

---

*This folder is kept synchronized with the main document `ux-bugs-list.md` and follows the team standard bug template.*
