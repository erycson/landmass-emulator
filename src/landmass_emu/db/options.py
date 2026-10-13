"""Repositório de `account_options` em SQLAlchemy async. Implementa `OptionsRepository`."""

import asyncio
from dataclasses import asdict, fields
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.db.models import OptionsRow
from landmass_emu.protocol.message import LmRegisterInfo

_NAMES = tuple(f.name for f in fields(LmRegisterInfo))


def _to_domain(row: OptionsRow) -> LmRegisterInfo:
    return LmRegisterInfo(**{name: getattr(row, name) for name in _NAMES})


class SqlOptionsRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions
        # Leitura e depois insert ou update: sem o lock, dois 544 simultâneos da mesma conta
        # poderiam inserir duas linhas e violar `account_options_account_id_unique`.
        self._lock = asyncio.Lock()

    async def get(self, account_id: int) -> LmRegisterInfo:
        async with self._sessions() as session:
            row = await session.scalar(
                select(OptionsRow).where(OptionsRow.account_id == account_id)
            )
        # shortcut: conta sem registro devolve 0 em tudo (sem fonte no RE); confirmar no cliente.
        return LmRegisterInfo() if row is None else _to_domain(row)

    async def save(self, account_id: int, options: LmRegisterInfo) -> None:
        values = asdict(options)
        now = datetime.now(UTC)
        async with self._lock, self._sessions.begin() as session:
            row = await session.scalar(
                select(OptionsRow).where(OptionsRow.account_id == account_id)
            )
            if row is None:
                session.add(
                    OptionsRow(account_id=account_id, created_at=now, updated_at=now, **values)
                )
                return
            for name, value in values.items():
                setattr(row, name, value)
            row.updated_at = now
