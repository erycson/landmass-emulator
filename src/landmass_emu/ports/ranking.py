"""Porta do ranking: consulta sobre `accounts`, sem tabela de ranking (D18)."""

from typing import Protocol

from landmass_emu.domain.ranking import RankedAccount


class RankingRepository(Protocol):
    async def top(self, limit: int) -> tuple[RankedAccount, ...]:
        """Contas por `total_exp` decrescente e id crescente, no máximo `limit`."""
        ...
