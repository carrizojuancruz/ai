Write-Host "Running ConversationSummarizer tests..." -ForegroundColor Green

# Move pyproject.toml temporarily to avoid coverage config issues
if (Test-Path "pyproject.toml") {
    Move-Item "pyproject.toml" "pyproject.toml.backup"
}

try {
    & python -m pytest tests/summarizer/test_conversation_summarizer.py -v --tb=short
    Write-Host "`nTests completed!" -ForegroundColor Green
} finally {
    # Restore pyproject.toml
    if (Test-Path "pyproject.toml.backup") {
        Move-Item "pyproject.toml.backup" "pyproject.toml"
    }
}
