"""Repositório de contas em SQLAlchemy async. Implementa `ports.accounts.AccountRepository`."""

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.db.models import AccountRow
from landmass_emu.domain.account import Account
from landmass_emu.domain.inventory import BASE_GATE_COUNT
from landmass_emu.ports.accounts import AccountConflict


def _to_domain(row: AccountRow) -> Account:
    return Account(
        id=row.id,
        username=row.username,
        nickname=row.nickname,
        token_hash=row.token_hash,
        banned_until=_aware(row.banned_until),
        access_level=row.access_level,
    )


def _aware(value: datetime | None) -> datetime | None:
    # SQLite devolve datetime sem fuso; a comparação com `now` (UTC) exige fuso.
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


class SqlAccountRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def find_by_username(self, username: str) -> Account | None:
        async with self._sessions() as session:
            row = await session.scalar(select(AccountRow).where(AccountRow.username == username))
        return None if row is None else _to_domain(row)

    async def find_by_token_hash(self, token_hash: str) -> Account | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(AccountRow).where(AccountRow.token_hash == token_hash)
            )
        return None if row is None else _to_domain(row)

    async def find_by_nickname(self, nickname: str) -> Account | None:
        async with self._sessions() as session:
            row = await session.scalar(select(AccountRow).where(AccountRow.nickname == nickname))
        return None if row is None else _to_domain(row)

    async def create(self, username: str, nickname: str, token_hash: str) -> Account:
        now = datetime.now(UTC)
        row = AccountRow(
            username=username,
            nickname=nickname,
            token_hash=token_hash,
            created_at=now,
            updated_at=now,
        )
        try:
            async with self._sessions.begin() as session:
                session.add(row)
                await session.flush()
                return _to_domain(row)
        except IntegrityError as e:
            raise AccountConflict(f"usuário {username!r} ou nickname {nickname!r} já existe") from e

    async def set_banned_until(self, account_id: int, until: datetime | None) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                update(AccountRow)
                .where(AccountRow.id == account_id)
                .values(banned_until=until, updated_at=datetime.now(UTC))
            )

    async def set_access_level(self, account_id: int, level: int) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                update(AccountRow)
                .where(AccountRow.id == account_id)
                .values(access_level=level, updated_at=datetime.now(UTC))
            )

    async def set_token_hash(self, account_id: int, token_hash: str) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                update(AccountRow)
                .where(AccountRow.id == account_id)
                .values(token_hash=token_hash, updated_at=datetime.now(UTC))
            )

    async def gate_count(self, account_id: int) -> int:
        async with self._sessions() as session:
            count = await session.scalar(
                select(AccountRow.gate_count).where(AccountRow.id == account_id)
            )
        return BASE_GATE_COUNT if count is None else count

    async def regular_nest(self, account_id: int) -> int:
        """Nest regular da conta; 0 quando não escolheu (o 101 manda ucNest 0)."""
        async with self._sessions() as session:
            nest = await session.scalar(
                select(AccountRow.regular_nest_id).where(AccountRow.id == account_id)
            )
        return nest or 0

    async def set_regular(self, account_id: int, nest: int, morat_class: int) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                update(AccountRow)
                .where(AccountRow.id == account_id)
                .values(
                    regular_nest_id=nest,
                    regular_morat_class=morat_class,
                    updated_at=datetime.now(UTC),
                )
            )
