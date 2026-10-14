"""Porta da montagem e do prazo (F6, F7). Cada método é uma transação: o repositório grava tudo ou
nada. Conflito de índice ou slot ocupado levanta `InventoryConflict` (ports/inventory.py)."""

from datetime import datetime
from typing import Protocol

from landmass_emu.domain.currency import Currency


class EquipmentRepository(Protocol):
    async def mount(
        self, account_id: int, inventory_index: int, morat_id: int, slot_name: str
    ) -> None:
        """Monta a peça no morat. Peça que já ocupava o mesmo slot sai antes (mesma transação)."""
        ...

    async def unmount(self, account_id: int, inventory_index: int) -> None: ...

    async def set_system_slot(self, account_id: int, inventory_index: int, slot: int) -> None: ...

    async def destroy_item(self, account_id: int, inventory_index: int) -> None:
        """Apaga a linha (sem histórico, D12). Quem estava montado sai com ela."""
        ...

    async def destroy_morat(self, account_id: int, morat_id: int) -> None:
        """Desmonta as peças (o SQLite não aplica ON DELETE sem PRAGMA) e apaga o morat."""
        ...

    async def extend(
        self,
        account_id: int,
        currency: Currency,
        price: int,
        inventory_index: int,
        expires_at: datetime,
    ) -> bool:
        """Debita `price` se o saldo cobre e grava o novo prazo na mesma transação (R-DEB-01).
        False = saldo insuficiente, e nada foi gravado."""
        ...
