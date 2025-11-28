# Code Review: Uncommitted Changes

## Instructions
Review all uncommitted changes in the working directory. Get the full git diff, analyze each changed file systematically against the checklist below, and provide a comprehensive review with issues categorized as **Critical** or **Nitpicks**.

## Step 1: Get the Diff
First, run `git diff` to get all uncommitted changes. Also run `git status` to see which files are modified, added, or deleted. Read all changed files to understand the full context.

For each changed function, class, or exported symbol, search the codebase to find where it's used. This helps identify potential breaking changes.

## Step 2: Systematic Review
For each changed file, go through this checklist and document findings:

### Functionality
- [ ] **Code does what it's supposed to do**: Verify logic correctness, check if implementation matches intent
- [ ] **Edge cases are handled**: Null/None checks, empty collections, boundary conditions, error states
- [ ] **Error handling is appropriate**: Specific exceptions caught, proper error propagation, no silent failures
- [ ] **No obvious bugs or logic errors**: Off-by-one errors, incorrect conditions, wrong variable usage
- [ ] **No breaking changes to related functionality**: Check if changes break any related code:
  - Function signatures changed (parameters added/removed/changed, return types changed)
  - Class interfaces modified (methods added/removed/changed, properties changed)
  - Imports/exports changed that might break dependencies
  - Constants, enums, or configuration values changed
  - Search for usages of changed functions/classes to verify compatibility
  - Check if any callers would break due to signature changes
  - Verify that removed code isn't used elsewhere in the codebase

### Code Quality
- [ ] **Code is readable and well-structured**: Clear flow, proper indentation, logical organization
- [ ] **Functions are small and focused**: Single responsibility, ideally < 50 lines, no god functions
- [ ] **Variable names are descriptive**: Clear intent, no abbreviations unless standard, follows naming conventions
- [ ] **No code duplication**: DRY principle followed, shared logic extracted
- [ ] **Follows project conventions**: Matches existing codebase style, uses project patterns
- [ ] **Remove any logs and comments**: No debug logs, no unnecessary comments (per project rules)
- [ ] **Run ruff check . --fix**: Check for linting issues that should be auto-fixed

### Security
- [ ] **No obvious security vulnerabilities**: SQL injection risks, XSS, authentication bypasses, unsafe deserialization
- [ ] **Input validation is present**: User inputs validated, type checking, range validation
- [ ] **Sensitive data is handled properly**: No secrets in code, proper encryption, secure storage
- [ ] **No hardcoded secrets**: API keys, passwords, tokens should be in env vars or config

### Type Safety & Best Practices
- [ ] **Type hints present**: All functions have parameter and return type annotations
- [ ] **No `Any` types**: Proper typing used, no type suppression
- [ ] **Proper exception handling**: No bare `except:`, specific exceptions caught, errors logged appropriately
- [ ] **Follows LangGraph patterns**: If applicable, nodes are small, typed, composable

## Step 3: Categorize Issues

### Critical Issues (Must Fix)
- Bugs that break functionality
- **Breaking changes**: Function/class signatures changed without updating callers, removed code still in use, incompatible interface changes
- Security vulnerabilities
- Logic errors that cause incorrect behavior
- Missing error handling that could cause crashes
- Hardcoded secrets or sensitive data exposure
- Type safety violations that could cause runtime errors
- Missing input validation that could cause security issues

### Nitpicks (Nice to Fix)
- Code style inconsistencies
- Minor readability improvements
- Variable naming that could be clearer
- Functions that are slightly too long but work correctly
- Missing type hints where code is otherwise correct
- Code duplication that doesn't affect functionality
- Minor refactoring opportunities

## Step 4: Generate Report

Provide a comprehensive review report with:

1. **Summary**: Brief overview of changes (what was modified, added, deleted)
2. **Critical Issues**: List all critical issues with:
   - File path and line numbers
   - Description of the issue
   - Why it's critical
   - Suggested fix
3. **Nitpicks**: List all nitpicks with:
   - File path and line numbers
   - Description
   - Suggested improvement
4. **Checklist Summary**: Show which checklist items passed/failed for each category
5. **Overall Assessment**: Is this code ready to commit? What must be fixed first?

Format findings clearly with code references using the proper citation format (startLine:endLine:filepath).