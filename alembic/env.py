from __future__ import annotations

import asyncio
import logging
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection

from alembic import context
from app.core.config import config as app_config
from app.db.base import Base
from app.db.models.user import UserContextORM  # noqa: F401 - explicit import to populate metadata

# Ensure project root is on sys.path for 'from app...' imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
logger = logging.getLogger("alembic.env")
logger.info("Loaded metadata tables: %s", list(target_metadata.tables.keys()))


def _run_sync_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations() -> None:

    url = app_config.get_database_url()

    if "+asyncpg" in url:
        from sqlalchemy.ext.asyncio import create_async_engine

        async def _run_async() -> None:
            connectable = create_async_engine(url, poolclass=pool.NullPool)
            async with connectable.connect() as connection:
                await connection.run_sync(_run_sync_migrations)

        asyncio.run(_run_async())
    else:
        connectable = create_engine(url, poolclass=pool.NullPool)
        with connectable.connect() as connection:
            _run_sync_migrations(connection)


run_migrations()


