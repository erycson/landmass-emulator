"""Porta do Depósito (`gifts`): envio com débito do remetente, página de pendentes e resgate.
Handlers e serviço dependem disto, nunca do SQLAlchemy."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from landmass_emu.domain.currency import Currency
from landmass_emu.domain.inventory import ItemUnit

if TYPE_CHECKING:
    from landmass_emu.domain.gift import Gift


class GiftRepository(Protocol):
    async def page(self, account_id: int, page: int, size: int) -> list[Gift]:
        """Pendentes da conta, por chave, na página `page` (0 a n) de `size` registros."""
        ...

    async def pending(self, account_id: int, slot: int) -> Gift | None:
        """Presente pendente da conta com a chave `slot`, ou None."""
        ...

    async def send(
        self,
        sender_id: int,
        receiver_id: int,
        currency: Currency,
        price: int,
        catalog_id: int,
        days: int,
    ) -> bool:
        """Debita `price` do remetente e grava o presente pendente do destinatário na mesma
        transação. False = saldo insuficiente, e nada é gravado."""
        ...

    async def claim(self, gift: Gift, unit: ItemUnit) -> bool:
        """Marca o presente como resgatado e grava `unit` no inventário na mesma transação. False =
        já resgatado, e nada é gravado. Índice ocupado levanta `InventoryConflict`."""
        ...
