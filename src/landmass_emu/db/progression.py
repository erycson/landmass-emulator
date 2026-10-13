"""Repositório de progressão em SQLAlchemy async (`ports.progression.ProgressionRepository`)."""

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.db.models import AccountRow
from landmass_emu.domain.progression import Grant, Progression


def _to_domain(row: AccountRow | None) -> Progression:
    # shortcut: conta sem linha devolve zeros; hoje só acontece se a conta foi apagada à mão.
    if row is None:
        return Progression()
    return Progression(
        total_exp=row.total_exp,
        ld=row.ld,
        cash=row.cash,
        tutorial_clear=row.tutorial_clear,
    )


class SqlProgressionRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get(self, account_id: int) -> Progression:
        async with self._sessions() as session:
            row = await session.scalar(select(AccountRow).where(AccountRow.id == account_id))
        return _to_domain(row)

    async def mark_tutorial(self, account_id: int, bit: int) -> Progression:
        # OR feito no banco: sem leitura antes da escrita, então dois passos concorrentes da
        # mesma conta não perdem bits. `bitwise_or` gera `|`, válido em SQLite, PostgreSQL e MySQL.
        async with self._sessions.begin() as session:
            await session.execute(
                update(AccountRow)
                .where(AccountRow.id == account_id)
                .values(
                    tutorial_clear=AccountRow.tutorial_clear.bitwise_or(bit),
                    updated_at=datetime.now(UTC),
                )
            )
            row = await session.scalar(select(AccountRow).where(AccountRow.id == account_id))
        return _to_domain(row)

    async def grant(self, account_id: int, grant: Grant) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                update(AccountRow)
                .where(AccountRow.id == account_id)
                .values(
                    total_exp=AccountRow.total_exp + grant.exp,
                    ld=AccountRow.ld + grant.ld,
                    cash=AccountRow.cash + grant.cash,
                    updated_at=datetime.now(UTC),
                )
            )
