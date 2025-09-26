@echo off
echo Running ConversationSummarizer tests...

REM Temporarily move pyproject.toml to avoid pytest config issues
if exist pyproject.toml move pyproject.toml pyproject.toml.backup

python -m pytest tests/summarizer/test_conversation_summarizer.py -v --tb=short

REM Restore pyproject.toml
if exist pyproject.toml.backup move pyproject.toml.backup pyproject.toml

echo.
echo Tests completed!
