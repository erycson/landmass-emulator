"""Repositório de contas em SQLAlchemy async. Implementa `ports.accounts.AccountRepository`."""

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.db.models import AccountRow
from landmass_emu.domain.account import Account
from landmass_emu.ports.accounts import AccountConflict


def _to_domain(row: AccountRow) -> Account:
    return Account(
        id=row.account_code,
        user_id=row.userid,
        nickname=row.nick,
        token_hash=row.token_hash,
    )


class SqlAccountRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def find_by_user_id(self, user_id: str) -> Account | None:
        async with self._sessions() as session:
            row = await session.scalar(select(AccountRow).where(AccountRow.userid == user_id))
        return None if row is None else _to_domain(row)

    async def find_by_token_hash(self, token_hash: str) -> Account | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(AccountRow).where(AccountRow.token_hash == token_hash)
            )
        return None if row is None else _to_domain(row)

    async def create(self, user_id: str, nickname: str, token_hash: str) -> Account:
        row = AccountRow(
            userid=user_id,
            nick=nickname,
            token_hash=token_hash,
            create_date=datetime.now(UTC),
        )
        try:
            async with self._sessions.begin() as session:
                session.add(row)
                await session.flush()
                return _to_domain(row)
        except IntegrityError as e:
            raise AccountConflict(f"usuário {user_id!r} ou nickname {nickname!r} já existe") from e

    async def set_token_hash(self, account_id: int, token_hash: str) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                update(AccountRow)
                .where(AccountRow.account_code == account_id)
                .values(token_hash=token_hash)
            )
