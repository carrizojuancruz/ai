# Use uv's Python base image
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim


# Expose port
EXPOSE 8080

# Run application
CMD ["uv", "run", "uvicorn", "src.agent:app", "--host", "0.0.0.0", "--port", "8080"]
