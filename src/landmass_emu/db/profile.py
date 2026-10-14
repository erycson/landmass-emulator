"""Ficha do jogador em SQLAlchemy async (`ports.profile.PlayerProfileRepository`).

Consulta sob demanda sobre `accounts`, `clan_members`, `clans` e `match_players`; sem tabela nova
(D107). Partidas contam só quando têm resultado: a partida em que algum jogador tem `won` não nulo
conta para todos os seus jogadores (D105). Abates, mortes e headshots somam todas as partidas.
"""

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.db.models import AccountRow, ClanMemberRow, ClanRow, MatchPlayerRow
from landmass_emu.domain.profile import PlayerProfile


class SqlPlayerProfileRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def profile(self, account_id: int) -> PlayerProfile | None:
        async with self._sessions() as session:
            account = (
                await session.execute(
                    select(AccountRow.total_exp, AccountRow.regular_nest_id).where(
                        AccountRow.id == account_id
                    )
                )
            ).first()
            if account is None:
                return None
            # Empate na menor posição (D18): a posição é 1 + quem tem exp estritamente maior.
            above = await session.scalar(
                select(func.count(AccountRow.id)).where(AccountRow.total_exp > account.total_exp)
            )
            with_result = select(MatchPlayerRow.match_id).where(MatchPlayerRow.won.is_not(None))
            games, wins, losses = (
                await session.execute(
                    select(
                        func.count(MatchPlayerRow.id),
                        func.coalesce(
                            func.sum(case((MatchPlayerRow.won.is_(True), 1), else_=0)), 0
                        ),
                        func.coalesce(
                            func.sum(case((MatchPlayerRow.won.is_(False), 1), else_=0)), 0
                        ),
                    ).where(
                        MatchPlayerRow.account_id == account_id,
                        MatchPlayerRow.match_id.in_(with_result),
                    )
                )
            ).one()
            kills, deaths, headshots = (
                await session.execute(
                    select(
                        func.coalesce(func.sum(MatchPlayerRow.kills), 0),
                        func.coalesce(func.sum(MatchPlayerRow.deaths), 0),
                        func.coalesce(func.sum(MatchPlayerRow.headshots), 0),
                    ).where(MatchPlayerRow.account_id == account_id)
                )
            ).one()
            clan = (
                await session.execute(
                    select(ClanRow.name, ClanRow.mark)
                    .join(ClanMemberRow, ClanMemberRow.clan_id == ClanRow.id)
                    .where(ClanMemberRow.account_id == account_id)
                )
            ).first()
        return PlayerProfile(
            rank=int(above or 0) + 1,
            games=games or 0,
            wins=wins or 0,
            losses=losses or 0,
            kills=kills or 0,
            deaths=deaths or 0,
            headshots=headshots or 0,
            total_exp=account.total_exp,
            nest=account.regular_nest_id or 0,
            clan_mark=0 if clan is None else clan.mark,
            clan_name="" if clan is None else clan.name,
        )
