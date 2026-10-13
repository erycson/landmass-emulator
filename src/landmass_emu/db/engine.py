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


class Migrator:
    def __init__(self, url: str) -> None:
        self._url = url

    async def upgrade(self) -> None:
        self._ensure_sqlite_dir()
        engine = create_async_engine(self._url)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(self._upgrade)
        finally:
            await engine.dispose()

    def _ensure_sqlite_dir(self) -> None:
        parsed = make_url(self._url)
        if parsed.get_backend_name() == "sqlite" and parsed.database:
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _upgrade(connection: Connection) -> None:
        cfg = Config()
        cfg.set_main_option("script_location", str(MIGRATIONS))
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")
