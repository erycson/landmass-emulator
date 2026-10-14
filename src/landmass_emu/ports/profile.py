"""Porta da ficha do jogador. O Channel depende disto, nunca do SQLAlchemy."""

from typing import Protocol

from landmass_emu.domain.profile import PlayerProfile


class PlayerProfileRepository(Protocol):
    async def profile(self, account_id: int) -> PlayerProfile | None:
        """Ficha da conta, ou None se ela não existe."""
        ...
