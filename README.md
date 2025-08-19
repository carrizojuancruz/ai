# verde-ai
This repository will store AI Agents for Vera app

## Database

- Postgres service is defined in `docker-compose.yml`.
- Default URL: `postgresql+asyncpg://verde:verde@localhost:5432/verde`

## Migrations (Alembic)

From the `verde-ai` folder:

```bash
poetry run alembic upgrade head
poetry run alembic revision -m "message" --autogenerate
```