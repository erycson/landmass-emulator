"""Porta da progressão da conta (tutorial, exp e saldos). Handlers e CLI dependem disto."""

from typing import Protocol

from landmass_emu.domain.progression import Grant, Progression


class ProgressionRepository(Protocol):
    async def get(self, account_id: int) -> Progression: ...

    async def mark_tutorial(self, account_id: int, bit: int) -> Progression:
        """Liga `bit` na máscara do tutorial e devolve a progressão já gravada."""
        ...

    async def grant(self, account_id: int, grant: Grant) -> None: ...
