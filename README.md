# verde-ai
This repository will store AI Agents for Vera app

## Database

- Postgres service is defined in `docker-compose.yml`.
- Default URL: `postgresql+asyncpg://verde:verde@localhost:5432/verde`

## Migrations (Alembic)

Since the app runs in Docker, use these commands:

```bash
# Generate migration
docker compose exec app poetry run alembic revision -m "message" --autogenerate

# Apply migration
docker compose exec app poetry run alembic upgrade head
```

docker compose exec app poetry run alembic revision -m "add_user_context" --autogenerate
