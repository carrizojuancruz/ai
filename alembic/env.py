from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection

from alembic import context
from app.db import models  # noqa: F401 - ensure models are imported for metadata
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


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
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")

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


