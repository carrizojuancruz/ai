# ConversationSummarizer Tests

This directory contains comprehensive tests for the `ConversationSummarizer` component used in the Verde AI supervisor agent.

## Overview

The `ConversationSummarizer` is responsible for:
- Summarizing long conversation histories to prevent context window overflow
- Filtering out injected context and system messages from summarization
- Preserving recent conversational messages in a "tail"
- Maintaining conversation continuity through incremental summarization

## Test Coverage

### Test Cases (17 total)

1. **`test_summarizer_filters_injected_context`** - Ensures CONTEXT_PROFILE and memory injection messages are excluded from summarization
2. **`test_summarizer_filters_handoff_markers`** - Ensures handoff back messages are excluded from summarization
3. **`test_summarizer_preserves_conversational_tail`** - Verifies recent conversational messages are preserved when summarization occurs
4. **`test_summarizer_no_summarization_when_all_fit_in_tail`** - Confirms no summarization when all messages fit within token budget
5. **`test_summarizer_handles_empty_messages`** - Tests graceful handling of empty message lists
6. **`test_summarizer_creates_proper_output_structure`** - Validates correct LangGraph output format with messages and context
7. **`test_default_include_predicate`** - Tests the message filtering logic for include/exclude predicates

## Running the Tests

### Quick Start (Windows)
```batch
# From the project root directory
.\tests\summarizer\run_summarizer_tests.bat
```

### Quick Start (PowerShell)
```powershell
# From the project root directory
.\tests\summarizer\run_summarizer_tests.ps1
```

### Manual pytest execution
```bash
# Windows PowerShell/Bash
python -m pytest tests/summarizer/test_conversation_summarizer.py -v

# Or with coverage
python -m pytest tests/summarizer/test_conversation_summarizer.py -v --cov=app
```

### Inside Docker Container
```bash
# If running in Docker
docker-compose exec app python -m pytest tests/summarizer/test_conversation_summarizer.py -v
```

### Alternative Scripts
- **`run_summarizer_tests.bat`** - Main Windows batch script (recommended)
- **`run_summarizer_tests.ps1`** - PowerShell script (alternative)

## Test Results

All tests should pass with output similar to:
```
============================= test session starts =============================
collected 17 items

tests/summarizer/test_conversation_summarizer.py::TestConversationSummarizer::test_summarizer_filters_injected_context PASSED
tests/summarizer/test_conversation_summarizer.py::TestConversationSummarizer::test_summarizer_filters_handoff_markers PASSED
tests/summarizer/test_conversation_summarizer.py::TestConversationSummarizer::test_summarizer_preserves_conversational_tail PASSED
tests/summarizer/test_conversation_summarizer.py::TestConversationSummarizer::test_summarizer_no_summarization_when_all_fit_in_tail PASSED
tests/summarizer/test_conversation_summarizer.py::TestConversationSummarizer::test_summarizer_handles_empty_messages PASSED
tests/summarizer/test_conversation_summarizer.py::TestConversationSummarizer::test_summarizer_creates_proper_output_structure PASSED
tests/summarizer/test_conversation_summarizer.py::TestConversationSummarizer::test_default_include_predicate PASSED
tests/summarizer/test_conversation_summarizer.py::TestConversationSummarizer::test_tail_excludes_injected_context_and_handoff PASSED
tests/summarizer/test_conversation_summarizer.py::TestConversationSummarizer::test_running_summary_last_id_is_last_head_included PASSED
tests/summarizer/test_conversation_summarizer.py::TestConversationSummarizer::test_model_failure_returns_no_change PASSED
tests/summarizer/test_conversation_summarizer.py::TestConversationSummarizer::test_empty_summary_returns_no_change PASSED
tests/summarizer/test_conversation_summarizer.py::TestConversationSummarizer::test_compacts_noise_when_no_conversational_head PASSED
tests/summarizer/test_conversation_summarizer.py::TestConversationSummarizer::test_custom_include_predicates_are_respected PASSED
tests/summarizer/test_conversation_summarizer.py::TestConversationSummarizer::test_tail_order_is_chronological PASSED
tests/summarizer/test_conversation_summarizer.py::TestConversationSummarizer::test_system_message_in_head_is_removed_post_summary PASSED
tests/summarizer/test_conversation_summarizer.py::TestConversationSummarizer::test_block_content_is_normalized PASSED
tests/summarizer/test_conversation_summarizer.py::TestConversationSummarizer::test_messages_without_ids_do_not_break PASSED

============================== 17 passed in 0.99s ==============================
```

## Architecture

The tests use:
- **Mock token counter** - Simple character-based token approximation
- **Mock LLM model** - Returns predefined summary responses
- **Direct imports** - Avoids package-level import conflicts
- **Comprehensive assertions** - Validates both functionality and data structures

## Dependencies

- `pytest` - Test framework
- `pytest-asyncio` - Async test support (if needed)
- `langchain-core` - Message types
- `langgraph` - Graph message utilities
- `langmem` - Running summary types

## Notes

- Tests temporarily move `pyproject.toml` to avoid pytest configuration conflicts
- All tests run in isolation with mocked dependencies
- Tests validate both the summarization logic and proper state management
- The summarizer correctly handles production scenarios with injected context and handoff markers
