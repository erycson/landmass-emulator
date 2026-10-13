"""Migrações Alembic no start, na conexão do próprio engine (sem `asyncio.run` aninhado)."""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

MIGRATIONS = Path(__file__).parent / "migrations"
logging.getLogger("alembic").setLevel(logging.WARNING)


def _ensure_sqlite_dir(url: str) -> None:
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite" and parsed.database:
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)


def _upgrade(connection: Connection) -> None:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    cfg.attributes["connection"] = connection
    command.upgrade(cfg, "head")


async def migrate(url: str) -> None:
    _ensure_sqlite_dir(url)
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_upgrade)
    finally:
        await engine.dispose()
