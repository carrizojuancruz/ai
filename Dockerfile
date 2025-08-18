FROM python:3.13-slim

# Install system dependencies for PostgreSQL
RUN apt-get update && apt-get install -y \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --upgrade pip && pip install poetry

# Set Poetry configs
RUN poetry config virtualenvs.create true \
    && poetry config virtualenvs.in-project true

# Copy dependency files first
WORKDIR /app
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry install --no-interaction --no-ansi \
    && poetry run pip install watchfiles

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Default command to run the app via run:app to ensure envs load early
CMD ["poetry", "run", "uvicorn", "run:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

