"""Repositório do histórico de partidas em SQLAlchemy async. Implementa `MatchRepository`."""

from dataclasses import asdict, fields
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from landmass_emu.db.models import AccountRow, MatchPlayerRow, MatchRow
from landmass_emu.domain.match_stats import MatchRecord

# Campos de `MatchRecord` que são colunas de `matches`; `players` vai para `match_players`.
_MATCH_FIELDS = tuple(f.name for f in fields(MatchRecord) if f.name != "players")


class SqlMatchRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def save(self, match: MatchRecord) -> int:
        now = datetime.now(UTC)
        values = {name: getattr(match, name) for name in _MATCH_FIELDS}
        # Uma transação: se algum jogador violar `match_players_match_id_account_id_unique`,
        # a partida inteira é desfeita e o IntegrityError sobe para quem chamou.
        async with self._sessions.begin() as session:
            row = MatchRow(**values, created_at=now, updated_at=now)
            session.add(row)
            await session.flush()
            match_id = row.id
            session.add_all(
                [
                    MatchPlayerRow(match_id=match_id, created_at=now, updated_at=now, **asdict(p))
                    for p in match.players
                ]
            )
            # Recompensa: só quem tem exp ou LD no bloco GameEnded. Sem dado, saldo fica como está.
            for p in match.players:
                if p.exp is None and p.money is None:
                    continue
                await session.execute(
                    update(AccountRow)
                    .where(AccountRow.id == p.account_id)
                    .values(
                        total_exp=AccountRow.total_exp + (p.exp or 0),
                        ld=AccountRow.ld + (p.money or 0),
                        updated_at=now,
                    )
                )
        return match_id
