"""Porta do histórico de partidas (`matches` e `match_players`). Quem grava depende disto."""

from typing import Protocol

from landmass_emu.domain.match_stats import MatchRecord


class MatchRepository(Protocol):
    async def save(self, match: MatchRecord) -> int: ...
