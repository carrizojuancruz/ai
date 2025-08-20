FROM python:3.13-slim

# Install system deps for PostgreSQL drivers (psycopg2 and asyncpg)
RUN apt-get update && apt-get install -y \
    libpq-dev gcc build-essential && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip and install Poetry
RUN pip install --upgrade pip && pip install poetry

# Configure Poetry to use in-project venv
RUN poetry config virtualenvs.create true \
    && poetry config virtualenvs.in-project true

WORKDIR /app

# Copy dependency files (poetry.lock is optional)
COPY pyproject.toml ./
COPY poetry.lock* ./

# Install deps (if lock file is present, it will be used)
RUN poetry install --no-interaction --no-ansi

# Extra tools
RUN poetry run pip install watchfiles

# Copy application code
COPY . .

EXPOSE 8000

CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

