"""Repositório de clãs em SQLAlchemy async (`ports.clans.ClanRepository`)."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import ColumnElement, Executable, Select, Update, delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.db.models import AccountRow, ClanMemberRow, ClanRow
from landmass_emu.ports.clans import Clan, ClanConflict, ClanMember

_ClanSelect = Select[int, str, int, int, str]


def _clan_query() -> _ClanSelect:
    """Clã com o nick do mestre."""
    return (
        select(
            ClanRow.id,
            ClanRow.name,
            ClanRow.mark,
            ClanRow.master_account_id,
            AccountRow.nickname,
        )
        .select_from(ClanRow)
        .join(AccountRow, AccountRow.id == ClanRow.master_account_id)
    )


class SqlClanRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def by_account(self, account_id: int) -> Clan | None:
        stmt = _clan_query().join(ClanMemberRow, ClanMemberRow.clan_id == ClanRow.id)
        return await self._first(stmt.where(ClanMemberRow.account_id == account_id))

    async def by_name(self, name: str) -> Clan | None:
        return await self._first(_clan_query().where(ClanRow.name == name))

    async def members(self, clan_id: int) -> tuple[ClanMember, ...]:
        stmt = (
            select(AccountRow.id, AccountRow.nickname, AccountRow.total_exp, ClanMemberRow.grade)
            .select_from(ClanMemberRow)
            .join(AccountRow, AccountRow.id == ClanMemberRow.account_id)
            .where(ClanMemberRow.clan_id == clan_id)
            .order_by(ClanMemberRow.id)
        )
        async with self._sessions() as session:
            rows = (await session.execute(stmt)).all()
        return tuple(ClanMember(r.id, r.nickname, r.total_exp, r.grade) for r in rows)

    async def create(self, name: str, master_account_id: int, mark: int) -> Clan:
        now = datetime.now(UTC)
        try:
            async with self._sessions.begin() as session:
                clan = ClanRow(
                    name=name,
                    master_account_id=master_account_id,
                    mark=mark,
                    created_at=now,
                    updated_at=now,
                )
                session.add(clan)
                await session.flush()
                clan_id = clan.id
                session.add(
                    ClanMemberRow(
                        clan_id=clan_id,
                        account_id=master_account_id,
                        grade=0,
                        created_at=now,
                        updated_at=now,
                    )
                )
        except IntegrityError:
            raise ClanConflict("nome do clã já existe ou a conta já tem clã") from None
        found = await self._first(_clan_query().where(ClanRow.id == clan_id))
        assert found is not None  # acabou de ser gravado na mesma conexão do banco
        return found

    async def add_member(self, clan_id: int, account_id: int, grade: int) -> None:
        now = datetime.now(UTC)
        try:
            async with self._sessions.begin() as session:
                session.add(
                    ClanMemberRow(
                        clan_id=clan_id,
                        account_id=account_id,
                        grade=grade,
                        created_at=now,
                        updated_at=now,
                    )
                )
        except IntegrityError:
            raise ClanConflict("a conta já tem clã") from None

    async def remove_member(self, account_id: int) -> None:
        await self._run(delete(ClanMemberRow).where(ClanMemberRow.account_id == account_id))

    async def delete(self, clan_id: int) -> None:
        async with self._sessions.begin() as session:
            await session.execute(delete(ClanMemberRow).where(ClanMemberRow.clan_id == clan_id))
            await session.execute(delete(ClanRow).where(ClanRow.id == clan_id))

    async def rename(self, clan_id: int, name: str) -> None:
        try:
            await self._run(_touch(ClanRow.id == clan_id).values(name=name))
        except IntegrityError:
            raise ClanConflict("nome do clã já existe") from None

    async def set_mark(self, clan_id: int, mark: int) -> None:
        await self._run(_touch(ClanRow.id == clan_id).values(mark=mark))

    async def _run(self, stmt: Executable) -> None:
        async with self._sessions.begin() as session:
            await session.execute(stmt)

    async def _first(self, stmt: _ClanSelect) -> Clan | None:
        async with self._sessions() as session:
            row: Any = (await session.execute(stmt)).first()
        if row is None:
            return None
        return Clan(row.id, row.name, row.mark, row.master_account_id, row.nickname)


def _touch(where: ColumnElement[bool]) -> Update:
    """`UPDATE clans` com a data de alteração."""
    return update(ClanRow).where(where).values(updated_at=datetime.now(UTC))
