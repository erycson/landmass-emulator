"""Ranking em SQLAlchemy async: consulta sobre `accounts` (`ports.ranking.RankingRepository`).

Sem tabela e sem cache (D18, 07-progression §4.10). Ordem: `total_exp` decrescente, depois id."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.db.models import AccountRow, ClanMemberRow
from landmass_emu.domain.ranking import RankedAccount


class SqlRankingRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def top(self, limit: int) -> tuple[RankedAccount, ...]:
        stmt = (
            select(
                AccountRow.id,
                AccountRow.nickname,
                AccountRow.total_exp,
                ClanMemberRow.clan_id,
            )
            .select_from(AccountRow)
            .outerjoin(ClanMemberRow, ClanMemberRow.account_id == AccountRow.id)
            .order_by(AccountRow.total_exp.desc(), AccountRow.id)
            .limit(limit)
        )
        async with self._sessions() as session:
            rows = (await session.execute(stmt)).all()
        return tuple(RankedAccount(r.id, r.nickname, r.total_exp, r.clan_id or 0) for r in rows)
