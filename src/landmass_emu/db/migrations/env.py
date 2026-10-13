"""Ambiente Alembic: conexão recebida em `config.attributes` ou URL das settings."""

import asyncio

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from landmass_emu.db.models import Base
from landmass_emu.settings import Settings


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_standalone(url: str) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_run)
    finally:
        await engine.dispose()


connection: Connection | None = context.config.attributes.get("connection")
if connection is not None:
    _run(connection)
else:
    asyncio.run(_run_standalone(Settings().database_url))
