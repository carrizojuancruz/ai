# Supervisor & Agents Testing System

## Scope & Goals

- Enforce meta-invariants: no hardcoded prompts in code, formatting/unicode rules.
- Validate prompt semantics (white-box): ensure each prompt text encodes required rules; leverage LLM judge only where needed.
- Validate behavior (grey/black-box): assert routing/refusals/icebreaker/memory usage on the compiled supervisor graph; use LLM judge for nuanced text.
- Run locally and in Docker CI with markers to control cost.

## ✅ P0 — Meta-Invariants (COMPLETED)

1) Centralize prompt loading

- ✅ Created `app/services/llm/prompt_loader.py` with local-only loading
- ✅ All prompts loaded from `app/services/llm/local_prompts.py`
- ✅ **REMOVED config overrides** - always use local prompts for simplicity
- ✅ Replaced direct prompt usage with `prompt_loader.load("prompt_name")`

2) No hardcoded prompt literals

- ✅ Consolidated into `tests/supervisor_prompts/static/test_prompt_format.py`
- ✅ AST parsing detects hardcoded prompts outside allowed files
- ✅ Fails on triple-quoted strings with prompt keywords

3) Prompt formatting policies

- ✅ Implemented in `tests/supervisor_prompts/static/test_prompt_format.py`
- ✅ Validates: UTF-8 encoding, no tabs, no trailing spaces, proper headers (`##`), bullets (`- ` or `---`)
- ✅ All prompts pass validation rules

**Current Test Structure:**
```
tests/supervisor_prompts/
├── static/test_prompt_format.py    ✅ Working - consolidated format + hardcoded detection
├── semantic/test_prompts.py        🚧 Added - LLM judge evaluation (broken - work in progress)
├── supervisor_prompts_inventory.json 🚧 Added - Rich prompt metadata (work in progress)
└── README.md                       ✅ Updated documentation
```

**Known Gap:** Dynamic prompts with runtime variables (routing examples, memory context) are not tested - only base prompt validation works.

## 🚧 P1 — White-Box Prompt Semantics (INFRASTRUCTURE ADDED)

**Current State:** Semantic testing infrastructure exists but is broken (import errors) - Work in Progress

**Needed:**
- Fix `tests/supervisor_prompts/semantic/test_prompts.py` import issues
- `prompt_specs.json` lists each prompt with `evaluation.instructions` (rubrics)
- `loader.py` imports or calls prompt builders (handles async)
- `test_prompts.py` runs string presence/forbidden assertions + LLM judge for nuanced checks
- Expand `evaluation.instructions` for supervisor/finance/wealth/goal/memory prompts

**Gap:** Dynamic prompt validation (runtime variables like routing examples, memory context)

## 🚧 P2 — Behavior Scenario Tests (NOT STARTED)

**Needed for dynamic prompt validation:**
- Create `tests/supervisor_scenarios/helpers.py`:
- `compile_graph()` → `compile_supervisor_graph()`
- `run_turn(user_text, ctx=None)` → returns `events`, `final_message`
- helpers: `saw_tool(name, events)`, `final_text(events)`

**Scenario Tests Needed:**
- `test_routing_finance.py`: Financial queries → `transfer_to_finance_agent`
- `test_routing_goal_priority.py`: Goal changes → `transfer_to_goal_agent` first
- `test_icebreaker_usage.py`: ICEBREAKER_CONTEXT → direct response, no tools
- `test_safety_refusal.py`: Harmful requests → no tools, proper refusal
- `test_memory_personalization.py`: Context bullets → personalized responses
- `test_sequential_routing_cap.py`: Max one agent chain per turn
- **NEW:** `test_dynamic_prompt_injection.py`: Validate runtime variable injection works

## 🚧 P3 — Config & CI (PARTIAL)

**Current State:**
- ✅ No config overrides (removed for simplicity - always local)
- ✅ Test markers implemented: `@pytest.mark.prompt_static`
- ❌ No scenario markers yet
- ❌ No CI integration

**Still Needed:**
- Add scenario test markers: `-m scenarios`
- Docker CI integration
- `docker compose exec app bash -lc "poetry run pytest -m 'prompt_static or scenarios'"`

## 🚧 P4 — Dynamic Prompt Testing (NEW PRIORITY)

**Critical Gap Identified:** How to test prompts with runtime variables

**Options:**
1. **Integration Tests:** Test actual agent execution with mock variables
2. **Parameterized Static Tests:** Test base prompts with sample variables
3. **Validation Middleware:** Runtime validation of injected prompts
4. **End-to-End Scenarios:** Full pipeline testing with variable injection

**Example Dynamic Prompts:**
- Supervisor: gets `top_k_routing_examples` at runtime
- Memory prompts: get conversation context
- Finance agent: gets `user_id`, transaction samples, etc.
- Guest agent: gets `max_messages` count

## 🚧 P5 — Optional Scale-Up (FUTURE)

- Batch multi-turn evaluations (Neo/agents-evals-core) for regression dashboards
- Adversarial/fuzz suites for safety/privacy, rate-limited in CI

## ✅ Files Already Changed/Added

- ✅ `app/services/llm/prompt_loader.py` - Centralized loader (local-only)
- ✅ `app/services/llm/local_prompts.py` - All prompt definitions
- ✅ `tests/supervisor_prompts/static/test_prompt_format.py` - Consolidated static tests
- ✅ `tests/supervisor_prompts/semantic/test_prompts.py` - Semantic testing infrastructure (work in progress)
- ✅ `supervisor_prompts_inventory.json` - Rich prompt metadata (work in progress)
- ✅ `tests/supervisor_prompts/README.md` - Updated documentation
- ✅ `app/agents/supervisor/agent.py` - Uses `prompt_loader.load()`
- ✅ `app/core/config.py` - **REMOVED** prompt override fields (simplified)

## ❌ Files Still Needed

- `tests/supervisor_scenarios/helpers.py` - Graph compilation helpers
- `tests/supervisor_scenarios/test_routing_finance.py` - Finance routing validation
- `tests/supervisor_scenarios/test_dynamic_prompt_injection.py` - Dynamic variable testing
- Fix: `tests/supervisor_prompts/semantic/test_prompts.py` - Import issues

## 📋 Updated Rollout Steps

1) ✅ **COMPLETED:** Implement P0 (loader + meta tests) and migrate prompts; run `prompt_static`
2) 🚧 **CURRENT GAP:** Address dynamic prompt testing (P4) - how to test runtime variable injection
3) 🚧 Fix P1 semantic tests or determine if they're needed
4) 🚧 Add P2 scenario tests for behavior validation
5) 🚧 Wire into CI with markers; expand scenarios over time