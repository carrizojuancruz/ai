# Prompt Testing Suite

Enforces prompt quality through static analysis and ensures no hardcoded prompts.

## File Organization

```
app/services/llm/
├── agent_prompts.py       # Agent system prompts (supervisor, finance, wealth, goal, guest)
├── memory_prompts.py      # Memory processing prompts (hotpath, episodic, icebreaker)
├── utility_prompts.py     # Utility prompts (title gen, conversation summarizer, welcome)
├── onboarding_prompts.py  # Onboarding prompts (name/location extraction)
└── prompt_loader.py       # Centralized loader

tests/supervisor_prompts/
├── static/test_prompt_format.py  # Static validation tests
├── semantic/test_prompts.py      # LLM judge evaluation (work in progress)
├── prompt_specs.json             # Prompt registry for testing
├── supervisor_prompts_inventory.json # Rich prompt metadata (work in progress)
├── plan.md                        # Implementation roadmap
└── README.md
```

# Running Tests

```bash
# Static tests only (recommended for CI - fast, no LLM calls)
poetry run pytest tests/supervisor_prompts/static/ -v

# Individual test categories
poetry run pytest tests/supervisor_prompts/static/test_prompt_format.py -k "test_prompt_utf8_valid"
poetry run pytest tests/supervisor_prompts/static/test_prompt_format.py -k "test_no_hardcoded_prompt_literals"

# With markers
poetry run pytest -m prompt_static -v
```

## ⚠️ Work in Progress

**Semantic Tests:** The `semantic/` directory contains LLM-based evaluation tests that are currently broken due to import issues. These are infrastructure for future P1 semantic validation but are not functional yet.

**Prompt Inventory:** The `supervisor_prompts_inventory.json` file contains rich metadata about prompts for evaluation purposes but is also work in progress.

## ⚠️ Important: Use Poetry

**The project uses `package-mode = false` in Poetry, so you MUST use Poetry to run tests:**

```bash
# ✅ CORRECT - Use Poetry
poetry run pytest tests/supervisor_prompts/static/ -v

# ❌ WRONG - Won't find app modules
pytest tests/supervisor_prompts/static/ -v
```
