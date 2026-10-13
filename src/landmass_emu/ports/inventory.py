"""Porta do inventário (`account_items` e `account_morats`). Handlers e CLI dependem disto."""

from typing import Protocol

from landmass_emu.domain.inventory import ItemUnit, MoratUnit


class InventoryConflict(Exception):
    """Índice, gate ou guid já ocupado na conta."""


class InventoryRepository(Protocol):
    async def items(self, account_id: int) -> list[ItemUnit]: ...

    async def morats(self, account_id: int) -> list[MoratUnit]: ...

    async def add_item(self, item: ItemUnit) -> None: ...

    async def add_morat(self, morat: MoratUnit) -> None: ...
